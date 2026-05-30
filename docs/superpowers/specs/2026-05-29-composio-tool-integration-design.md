# Composio tool integration

**Status:** Design accepted, ready for implementation plan.
**Date:** 2026-05-29
**Scope:** Wire Composio's managed-tools service into Noctua so the four currently-stubbed producers (`social_post`, `clinical_analysis`, `diagnostic`, `cad`) can perform real external work (LinkedIn / X / Bluesky / Notion / Linear / Slack / Gmail / Google Drive). The PR producer is unaffected.

---

## 1. Goal and non-goals

**Goal.** Give Noctua's content-only producers reach into external SaaS tools through Composio, without breaking the plan→execute→artifact spine that the PR producer relies on. After this work, the four stub producers actually post / fetch / file / upload instead of returning canned content.

**Non-goals.**
- Replacing the bundled GitHub tools (`gh_pr_create`, `git_push`, etc.) with Composio's GitHub toolkit. The PR producer is happy with the gh CLI.
- Using Composio's tool catalog as a fallback before fabrication. Tool fabrication stays as-is.
- Multi-user / multi-tenant Composio identities. Single shared `user_id`.
- Building a permission / approval gate for which Composio actions a producer can use. Producers declare their action allowlist in code.

## 2. Architectural shape

Composio becomes a **fourth source in `ToolRegistry`** alongside `bundled` / `fabricated` / `graduated`. The plan-then-execute spine is preserved: planner still emits explicit `kind: "tool"` steps with composio-prefixed names, executor still runs them through the registry, budget / retries / step records work unchanged.

Composio calls execute against Composio's HTTPS gateway (which in turn calls LinkedIn / Notion / etc.) — **outside the Docker sandbox**. This is consistent with how the sandbox already bounds *code execution*, not arbitrary network egress for tools (the existing `gh_pr_create` is also network-side from the sandbox's perspective).

Tool naming convention: `composio:<TOOLKIT>.<ACTION>` (e.g. `composio:LINKEDIN.CREATE_POST`). The registry dispatches by prefix.

User identity: all Composio calls use `user_id = settings.COMPOSIO_USER_ID` (default `"noctua_default"`). Composio's OAuth state is keyed on this identity; one shared identity means a single operator pre-connects each toolkit once.

OAuth posture: **pre-flight only**. If a producer's required toolkit isn't connected, the API refuses to create the mission. We do not pause missions mid-flight for OAuth — the overnight-unattended thesis depends on missions either running clean or refusing to start.

## 3. New module: `noctua/integrations/composio.py`

Single new module that owns everything Composio-shaped.

```python
class ComposioClient:
    """Thin wrapper around the composio SDK; one per process."""

    def __init__(self):
        if not settings.COMPOSIO_API_KEY:
            raise RuntimeError("COMPOSIO_API_KEY is empty; check .env loading")
        self._sdk = Composio(api_key=settings.COMPOSIO_API_KEY)

    def execute(self, slug: str, arguments: dict, user_id: str) -> ExecutionResult: ...
    def get_action_spec(self, slug: str) -> ActionSpec: ...                 # cached per-process
    def initiate_connection(self, toolkit: str, user_id: str) -> ConnectionInit: ...
    def fetch_connection_status(self, composio_conn_id: str) -> str: ...


class ComposioToolAdapter:
    """Synthesizes ToolEntry instances for composio:<TOOLKIT>.<ACTION> names."""

    def lookup(self, name: str) -> ToolEntry:
        toolkit, action = name.removeprefix("composio:").split(".", 1)
        spec = self._client.get_action_spec(action)
        def call(args, sandbox):
            try:
                r = self._client.execute(slug=action, arguments=args, user_id=settings.COMPOSIO_USER_ID)
                return ToolResult(ok=r.successful, value=r.data, error=r.error or "")
            except ComposioAuthError as e:
                Connection.objects.filter(toolkit=toolkit).update(
                    status="expired", last_error=str(e),
                )
                return ToolResult(ok=False, error=f"connection_expired:{toolkit}")
            except Exception as e:
                return ToolResult(ok=False, error=str(e))
        return ToolEntry(
            name=name,
            signature=spec.input_schema,
            status="composio",
            callable=call,
        )

    def list_actions_for_producer(self, producer) -> list[ToolEntry]:
        """Used by registry.all_available; returns entries only for toolkits whose Connection is active."""
        ...
```

`status="composio"` joins the existing `hardcoded | fabricated_sandbox_only | graduated` set in `ToolEntry.status`. No new model field on `Tool` — composio tools aren't `Tool` rows (they live in Composio's catalog).

## 4. Connection data model

New Django model `Connection` in `noctua/core/models.py`:

```python
class Connection(models.Model):
    toolkit          = models.CharField(max_length=64, unique=True)   # e.g. "LINKEDIN"
    status           = models.CharField(max_length=16)                # active|expired|revoked|pending
    composio_conn_id = models.CharField(max_length=128)               # ID from composio.connected_accounts.initiate
    connected_at     = models.DateTimeField(null=True, blank=True)
    last_error       = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
```

One row per toolkit (single shared user_id, so toolkit is the natural key). Migration: standard `makemigrations` + `migrate`.

## 5. Producer manifest extension

Each producer class grows two class attributes:

```python
class SocialPostProducer:
    key = "social_post"
    external_tools = True                          # new producer mode (see §7)
    required_toolkits = ["LINKEDIN", "TWITTER", "BLUESKY"]
    composio_actions = {
        "LINKEDIN": ["LINKEDIN_CREATE_POST"],
        "TWITTER":  ["TWITTER_CREATE_TWEET"],
        "BLUESKY":  ["BLUESKY_CREATE_POST"],
    }
```

- `required_toolkits` — *connection requirement*. Semantics: **at least one** toolkit in the list must have an `active` Connection row at mission-queue time, or the API rejects. The list is "alternatives, any of which suffices" — `social_post` works whether the operator has connected LinkedIn, X, Bluesky, or any subset. Producers that need *all* of several toolkits (e.g. clinical needs Notion AND Gmail) split the requirement: `required_toolkits = ["NOTION"]` covers the must-have, optional toolkits go in a separate `optional_toolkits` field that is *not* pre-flight checked.
- `composio_actions` — *planner-visible catalog*. Only actions for toolkits with active connections are exposed to the planner.
- `external_tools` — see §7.

The existing PR producer leaves all three at defaults (none / empty / False); behavior unchanged.

## 6. Registry change

`ToolRegistry.lookup(name, current_mission_id=None)` gets a 4th branch:

```python
if name.startswith("composio:"):
    return self._composio.lookup(name)
```

`ToolRegistry.all_available(...)` grows a `producer` kwarg. When passed, it appends `composio_adapter.list_actions_for_producer(producer)` — which itself filters by Connection status, so the planner only sees actions whose auth is live.

The planner already receives the producer name; `plan_for_mission` is updated to pass the resolved producer through to `all_available`.

## 7. New producer execution lane: `external_tools=True`

Today `noctua/runner/tasks.py:run_mission` has two branches:
- `content_only=True` — skip sandbox + planner + executor; call `producer.finalize` directly.
- otherwise — boot sandbox, plan, execute, finalize.

Adding a third branch:

```python
if producer.external_tools:
    sandbox = None
    plan = plan_for_mission(mission, sandbox=None, producer=producer)
    execute_plan(mission, plan, sandbox=None, producer=producer)
    producer.finalize(mission, sandbox=None)
elif producer.content_only:
    ...                              # existing path
else:
    ...                              # existing PR path
```

**Executor change.** `execute_plan` accepts `sandbox=None`. It still works for `kind: "tool"` steps (composio adapter ignores the sandbox arg) and `kind: "edit"` steps (producer's `execute_step` for these producers does a pure Claude call, no shell). It raises `RuntimeError` if a `kind: "exec"` step appears with `sandbox=None`, or a non-composio tool step that expects a real sandbox.

Why a separate lane and not just flip `content_only=False`: those producers would boot a sandbox (~30s cold start, container resources) for code they never run. The `external_tools` lane skips sandbox entirely; missions complete in seconds rather than minutes.

**`content_only` lives on.** Producers that genuinely don't need tools (none today, but the slot exists) keep the fast path.

## 8. Pre-flight check in `POST /api/missions`

`noctua/core/api.py`'s `create_mission` view resolves the producer, reads `required_toolkits`, and queries `Connection.objects.filter(toolkit__in=required_toolkits, status="active")`. If the result is **empty** (no toolkit in the list is connected), return:

```http
400 Bad Request
{"error": "missing_connections", "toolkits": ["LINKEDIN", "TWITTER", "BLUESKY"]}
```

The mission row is never created in that state. The error message in the response body points the operator at the Connections page and lists every toolkit that *would* satisfy the requirement.

(`optional_toolkits` is not checked here — producers handle "feature missing because toolkit X isn't connected" at plan time.)

## 9. CLI: `noctua composio connect <toolkit>`

New command group in `noctua/cli.py`:

```
noctua composio connect <TOOLKIT>     # initiate OAuth, persist Connection row
noctua composio list                  # show all connections and statuses
noctua composio disconnect <TOOLKIT>  # mark revoked, remove from active set
```

`connect` flow:
1. Calls `ComposioClient.initiate_connection(toolkit, user_id)`.
2. Persists `Connection` row with `status="pending"` and the returned `composio_conn_id`.
3. Prints the OAuth redirect URL.
4. Polls Composio every 2s for up to 5min; on `ACTIVE`, flips row to `active` and sets `connected_at`.
5. On timeout, leaves the row in `pending` and exits with a non-zero status code — operator can re-run `noctua composio list` later to refresh.

## 10. Connections UI

New page `ui/app/connections/page.tsx`:
- Lists every toolkit referenced in any registered producer's `required_toolkits` (a new API endpoint `GET /api/producers/toolkits` exposes this list).
- For each toolkit, shows status (active / expired / pending / not_connected) pulled from `GET /api/connections`.
- "Connect" button calls `POST /api/connections/{toolkit}/initiate`, opens the returned OAuth URL in a new tab.
- "Refresh" button calls `POST /api/connections/{toolkit}/refresh` which re-queries Composio for current status.

All requests go through `ui/lib/api.ts`'s `call()` helper. No bare `fetch().json()`.

## 11. Per-producer specs

All four producers move from `noctua/producers/stub/` to `noctua/producers/external/` (new module). `pyproject.toml` entry points re-point. The old `stub/` module becomes a deletion candidate (kept for one commit so the migration is reviewable, then deleted in the same PR).

### social_post
- `required_toolkits = ["LINKEDIN", "TWITTER", "BLUESKY"]` (any one suffices)
- `optional_toolkits = []`
- Input: `goal` (post idea), optional `platforms` list (defaults to all connected).
- Plan: one tool step per chosen connected platform, each emitting the platform's create-post action.
- Finalize: Artifact `content` lists URLs of created posts; `metadata` carries raw tool results.

### clinical_analysis
- `required_toolkits = ["NOTION"]`
- `optional_toolkits = ["GMAIL"]`
- Input: `goal` containing a Notion page ID or URL.
- Plan: `NOTION.FETCH_PAGE` → `kind: "edit"` Claude analysis → `NOTION.CREATE_PAGE` (analysis as child of source). If GMAIL is connected and a recipient is in `goal`, also emit `GMAIL.SEND_EMAIL`.
- The edit step is a pure Claude call; producer's `execute_step` takes `sandbox=None`.

### diagnostic
- `required_toolkits = ["LINEAR"]`
- `optional_toolkits = ["SLACK"]`
- Input: `goal` with a Linear issue ID.
- Plan: `LINEAR.GET_ISSUE` → edit-step Claude diagnostic → `LINEAR.CREATE_COMMENT`. If SLACK is connected, also emit `SLACK.POST_MESSAGE`.

### cad
- `required_toolkits = ["GOOGLEDRIVE"]`
- `optional_toolkits = ["NOTION"]`
- Input: `goal` with reference doc URL.
- Plan: `GOOGLEDRIVE.DOWNLOAD_FILE` → edit-step Claude SVG generation → `GOOGLEDRIVE.UPLOAD_FILE` for the rendered SVG. If NOTION is connected and a target page is in `goal`, also emit `NOTION.APPEND_BLOCK` linking the uploaded file.

**Rubric files.** Each producer already has a rubric markdown under `noctua/producers/.../rubric.md`. Copy is updated to describe real external work instead of canned-artifact framing. `seed_producers` management command re-runs to sync `Producer.rubric_md` to disk.

## 12. Settings and dependencies

`noctua/settings.py`:
```python
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "noctua_default")
```

`.env.example`:
```
COMPOSIO_API_KEY=
# COMPOSIO_USER_ID=noctua_default   # override if you run multiple Noctua instances against one Composio org
```

`pyproject.toml` `dependencies`:
```
"composio>=0.7",
```

**Not** adding `composio-claude-agent-sdk`. The architecture chose explicit plan-then-execute, not the MCP / ClaudeSDKClient path.

## 13. Budget

`increment_spent(tool_calls=1)` is called per executed step regardless of source, so the existing budget caps apply to Composio calls automatically. No separate `composio_calls` counter — if cost becomes a concern, Composio's own dashboard is the authoritative source.

## 14. Error handling

| Failure mode | Where caught | Behavior |
|---|---|---|
| Composio HTTP 5xx / network | adapter `callable` | `ToolResult(ok=False, error=...)` → executor retries up to `MAX_RETRIES_PER_STEP`, then step fails, mission `failed`. |
| Composio auth expired | adapter `callable` | `Connection.status="expired"` + `last_error` set. `ToolResult(ok=False, error="connection_expired:<toolkit>")`. Mission fails. Operator sees the toolkit flipped in the Connections UI. |
| Connection unknown at queue time | `POST /api/missions` | 400 with `toolkits=[...]`; mission not created. |
| Composio rate limit (429) | adapter `callable` | Same as 5xx — retried. If still failing, mission fails with the rate-limit message in the step's `error`. |
| Operator revokes mid-mission | adapter `callable` | Same as auth expired. |
| Planner emits `composio:` tool whose toolkit isn't in producer's manifest | `registry.lookup` | Returns `None` → executor falls through to fabricator (current behavior), which raises `NotImplementedError`. Step fails fast, mission fails with a clear error. Future hardening: validate planner output before execution. |

No silent fallbacks anywhere. Every failure either fails the mission with context or refuses to create it.

## 15. Tests

All tests mock the Composio SDK. No test hits the real Composio API. (Consistent with `tests/sandbox/` being the only tree that touches real infra.)

- `tests/integrations/test_composio_adapter.py` — adapter synthesizes the right `ToolEntry`; `callable` maps success / error / auth-expired correctly; auth-expired flips the `Connection` row to `expired`.
- `tests/tools/test_registry_composio.py` — registry dispatches `composio:*` to adapter; `all_available(producer=...)` includes actions only for connected toolkits.
- `tests/core/test_mission_preflight.py` — `POST /api/missions` rejects missing / expired connections, accepts when all required are active.
- `tests/core/test_connections_api.py` — `initiate` persists a `pending` row and returns the OAuth URL; `list` returns all rows.
- `tests/runner/test_external_tools_lane.py` — `run_mission` skips sandbox for `external_tools=True` producers; plan runs; finalize is called.
- `tests/producers/test_social_post.py`, `test_clinical_analysis.py`, `test_diagnostic.py`, `test_cad.py` — each producer with mocked Composio + mocked Claude, asserts plan structure and final Artifact shape.

## 16. Rollout order

Dependency-correct; each step is independently verifiable. Steps 1–5 ship a working substrate without changing visible behavior; step 6 is where producers start doing real work.

1. `ComposioClient` wrapper + settings + tests (mocked SDK).
2. `Connection` model + migration + API endpoints + Connections UI page.
3. `ComposioToolAdapter` + registry's 4th branch + tests.
4. `external_tools` lane in `run_mission` + executor's `sandbox=None` handling + tests.
5. Producer manifest fields (`required_toolkits`, `composio_actions`, `external_tools`) + pre-flight check in `POST /api/missions` + tests.
6. Replace the four stub producers one at a time, in this order: `social_post` (smallest), `clinical_analysis`, `diagnostic`, `cad`.
7. CLI command `noctua composio connect <toolkit>` last — by then every dependency exists.

## 17. Known limitations

- **Cold action-spec fetch.** `ComposioClient.get_action_spec` is a network call. Cached per-process, but first invocation of a given action in a worker process adds ~50–200ms. Acceptable; flagged so it doesn't surprise.
- **Single user_id.** Multi-tenant Composio is out of scope. When Noctua grows a real user model, `user_id` becomes a per-user value and `Connection` keys on `(user_id, toolkit)` instead of just `toolkit`. Migration is straightforward but deferred.
- **No mid-mission OAuth recovery.** A token that expires between pre-flight and execution fails the mission. Pre-flight + good Connections UI is the chosen tradeoff over `NeedsInput` pause; revisit if expirations become routine.
- **Sandbox-image cleanup.** Steps 1–6 don't change the Docker base image. Some toolkits Composio supports (e.g. ones that need a downloadable binary) aren't covered here, but none of the four target producers need them.
