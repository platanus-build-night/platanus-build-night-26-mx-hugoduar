# Noctua MVP — Design Spec

**Date:** 2026-05-29
**Status:** Draft for review
**Scope:** Hackathon MVP only — the overnight PR builder vertical, with stub tabs in the Review UI for the other producer kinds to convey the platform thesis. See [PRD.md](../../planning/PRD.md) for the full vision and [HACKATHON_MVP.md](../../planning/HACKATHON_MVP.md) for the build order.

---

## 1. Goal

Ship a demoable system where a user fires a mission against a GitHub issue, an isolated Docker sandbox boots, a Claude-driven planner+executor edits code and runs tests until they pass, a draft PR opens against the target repo, and the morning Review UI lets the user approve to mark the PR ready-for-review. Stub producer tabs render canned artifacts to communicate the multi-domain thesis.

The demo target: judge fires `noctua run <issue-url>`, watches a sandbox boot, sees a real GitHub draft PR open against a controlled demo repo with tests passing, approves it in the UI — all in under 4 minutes.

## 2. Constraints decided during brainstorming

| Decision | Value | Source |
|---|---|---|
| Scope | Hackathon MVP only (one vertical end-to-end, others stubbed) | User Q1 |
| Resource caps | Hard ceilings: wall-clock, tokens, tool/sandbox calls. Mission halts → `stopped` on breach. | User Q2 |
| Producer training | Markdown rubric per producer (`producers/<key>/rubric.md`); user-editable; injected into planner prompt | User Q3 |
| Mission states | `queued → running → (succeeded \| failed \| stopped \| needs_input)` | User Q4 |
| Demo repo | Brand-new tiny Python repo we own (`noctua-demo-app`), 3 baked issues | User Q5 |
| Worker | Celery + Redis | User Q6 |
| Stack | Django Ninja + Postgres (control plane), Next.js + Tailwind (Review UI), Docker SDK for Python (sandbox), Anthropic SDK (LLM) | PRD edit |
| Architecture | Monolithic Django + Celery, single-host Docker (Option A from brainstorm) | Recommendation |
| Tools-as-artifacts | Fabricated tools persist across missions; appear in a Tools tab in the Review Queue; user approval ("graduate") promotes them to a reusable Tool Library. Fabrication itself stays scoped to the hardcoded `seed_db` template. | User Q7 |

## 3. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                  Review UI — Next.js + Tailwind                    │
│       /queue · /queue/:artifact_id · producer rubric editor        │
└────────────────────────┬───────────────────────────────────────────┘
                         │ HTTP + SSE (logs)
┌────────────────────────▼───────────────────────────────────────────┐
│                Django Ninja API (control plane)                    │
│  missions · plans · artifacts · sandboxes · producers · queue      │
│                Postgres (single source of truth)                   │
└──────────┬─────────────────────────────────────────────────────────┘
           │ enqueue (Celery)             ▲
           ▼                              │ writes state
┌──────────────────────────────┐          │
│  Celery worker — Mission     │──────────┘
│  Runner                      │
│  ┌────────────────────────┐  │
│  │ Planner (Claude)       │  │
│  │ Executor loop          │  │
│  │ Budget enforcer        │  │
│  └─────────┬──────────────┘  │
│            │                 │
│  ┌─────────▼─────┐  ┌───────────────┐  ┌───────────────────┐
│  │ Sandbox Mgr   │  │ Tool Registry │  │ Producers (in-proc)│
│  │ (Docker SDK)  │  │ + Fabricator  │  │ pr / stubs         │
│  └───────────────┘  └───────────────┘  └───────────────────┘
└──────────────────────────────┘
           │
           ▼ docker daemon (host)
   one container per mission + nested containers for tool fabrication
```

**Component responsibilities:**

- **Django Ninja API** — REST surface for the CLI and Review UI. Owns Postgres. Auth = single shared bearer token from env.
- **Celery worker** — runs the mission lifecycle. One mission per task. Hard `time_limit` enforced by Celery in addition to in-code budget checks.
- **Sandbox manager** — Python class wrapping Docker SDK. One container per mission with CPU/memory caps, TTL, no docker socket mount.
- **Planner + executor** — emits a JSON DAG of steps, executes each, retries up to 3× on transient failure, re-plans on hard failure once.
- **Tool registry + fabricator** — registered tools callable from steps AND from LLM tool-use during code edits. Fabricator runs LLM-authored Python in a nested locked-down sandbox before registering.
- **Producers** — Python plugins. `PRProducer` fully implemented; `social_post`, `clinical_analysis`, `diagnostic` are stubs returning canned artifacts.
- **Review UI** — single Next.js page `/queue` with tabs per producer; detail page per artifact. SSE for live sandbox logs.

## 4. Data model (Postgres / Django ORM)

```
Mission
  id, goal, inputs (jsonb), success_criteria (text),
  domain ('code'|'social'|'clinical'|'diagnostic'|'cad'),
  producer_key, repo_url, issue_url,
  state ('queued'|'running'|'succeeded'|'failed'|'stopped'|'needs_input'),
  state_reason (text, e.g. 'budget_exceeded: tokens'),
  budget (jsonb: {max_wall_seconds, max_tokens, max_tool_calls}),
  spent  (jsonb: {wall_seconds, tokens, tool_calls}),
  needs_input_prompt (text, nullable),
  needs_input_response (text, nullable),
  auto_act (bool, default false),
  created_at, started_at, finished_at

Plan
  id, mission_id, version (int),
  steps (jsonb: [{step_id, kind, payload, status, attempt, result}]),
  rendered_md (text),
  created_at

SandboxRun
  id, mission_id, image_ref (str),
  container_id (nullable), state ('booting'|'ready'|'exited'|'torn_down'),
  log_path (filesystem ref), ttl_seconds,
  started_at, finished_at

Tool
  id, name, signature (jsonb: {args_schema, returns_schema}),
  source_path (filesystem ref), source_hash,
  fabricated_by_mission_id (nullable),
  status ('hardcoded'|'fabricated_sandbox_only'|'graduated'),
  created_at

Artifact
  id, mission_id, producer_key,
  kind ('pr'|'social_post'|'analysis'|'diagnostic'|'cad'|'tool'),
  uri (str),
  preview (jsonb),
  provenance (jsonb: {plan_version, sandbox_run_id, tool_ids[]}),
  validation (jsonb: {tests_passed, summary}),
  queue_state ('pending'|'approved'|'rejected'|'promoted'),
  tool_id (nullable fk — set when kind='tool' for promotion flow),
  created_at, reviewed_at

Producer
  key, kind, rubric_md (text), default_budget (jsonb), version
```

Notes:
- `Mission.spent` is incremented atomically (`UPDATE ... RETURNING`) on every LLM call and sandbox exec. Cap breach moves mission to `stopped`.
- `Plan.steps` is JSONB (append-only within a version). The planner can emit a new `Plan` row (incremented `version`) if it re-plans mid-mission.
- `Tool.status` is the gradient from the PRD; MVP ships all three: `hardcoded` (bundled), `fabricated_sandbox_only` (just created, queued for review), and `graduated` (user-approved, reusable across missions).
- `Artifact.preview` is what the queue card renders without loading the full artifact (diff stat, first-200 chars, etc.).

**Open data-model questions for user review:**
- Should `auto_act` live on `Mission` (per-mission opt-in) or on `Producer` (pre-approve a whole producer)? Default in this spec: **`Mission`**, because per-mission opt-in matches the PRD's review-first principle.

## 5. API surface

Django Ninja, all under `/api/`.

```
POST   /api/missions                  create mission
GET    /api/missions/:id              full state, spent, plan, artifact ref
POST   /api/missions/:id/cancel       soft kill (stop worker, teardown sandbox)
POST   /api/missions/:id/respond      resolve needs_input
GET    /api/queue                     list artifacts (filterable)
GET    /api/artifacts/:id             full artifact + provenance
POST   /api/artifacts/:id/approve     producer.on_approve()
POST   /api/artifacts/:id/reject      mark rejected
POST   /api/artifacts/:id/promote     producer.on_promote() (e.g. merge PR)
GET    /api/sandboxes/:id/logs        SSE stream of live container logs
GET    /api/producers                 list with rubric previews
PUT    /api/producers/:key/rubric     save edited rubric markdown
```

- **Auth:** single bearer token from env, used by both CLI and UI. No multi-user.
- **SSE for logs:** Django Ninja `StreamingHttpResponse`; the worker writes log lines to `SandboxRun.log_path` and the SSE endpoint tails the file.

## 6. Sandbox interface

```python
class Sandbox:
    def boot(self, image: str, repo_url: str | None) -> SandboxRun: ...
    def exec(self, cmd: list[str], stdin: str = "", timeout: int = 60) -> ExecResult: ...
    def write_file(self, path: str, content: bytes) -> None: ...
    def read_file(self, path: str) -> bytes: ...
    def stream_logs(self) -> Iterator[str]: ...
    def snapshot(self) -> str: ...      # MVP: returns image SHA only
    def teardown(self) -> None: ...
```

- **Container defaults:** `--cpus=2 --memory=2g --read-only` with `/work` tmpfs, `--network=bridge` (clone needs net), no docker socket mount.
- **TTL enforcement:** Celery beat task `noctua.tasks.reap_orphans` runs every 5 min and kills containers older than `ttl_seconds`.
- **Nested sandbox for fabrication:** `NestedSandbox` subclass — `--network=none`, `--cpus=1 --memory=512m`, no volume mounts, 60s exec timeout. Used only by the tool fabricator.

## 7. Producer interface

```python
class Producer(Protocol):
    key: str
    kind: str
    rubric_path: str

    def plan(self, mission: Mission, ctx: PlannerContext) -> Plan: ...
    def execute_step(self, step: Step, sandbox: Sandbox, llm: LLM) -> StepResult: ...
    def finalize(self, mission: Mission, sandbox: Sandbox) -> Artifact: ...
    def on_approve(self, artifact: Artifact) -> None: ...
    def on_promote(self, artifact: Artifact) -> None: ...
```

Discovery via entry points in `pyproject.toml`:

```toml
[project.entry-points."noctua.producers"]
pr = "noctua.producers.pr:PRProducer"
social_post = "noctua.producers.stub:SocialPostStub"
clinical_analysis = "noctua.producers.stub:ClinicalAnalysisStub"
diagnostic = "noctua.producers.stub:DiagnosticStub"
```

**`PRProducer` (real)** — clones repo into sandbox, reads issue via `gh issue view`, drives an LLM code-edit loop (Claude tool-use for `read_file`/`write_file`/`run_pytest`), iterates on failing tests up to 3×, branches/commits/pushes, opens draft PR via `gh pr create --draft`. `on_approve` runs `gh pr ready`. `on_promote` is no-op in MVP.

**Stub producers** — return a canned `Artifact` from a fixture file (`producers/stub/fixtures/<kind>.json`). They exist so the Review UI tabs render real items and the platform thesis lands.

**Rubric injection** — at planning time, `Producer.plan()` reads `rubric_md` from the `Producer` table and injects it into the planner prompt as a system message. **The DB row is authoritative.** Disk files (`producers/<key>/rubric.md`) are seed templates loaded into the DB on first migration, and are also the path the UI editor writes back to (via `PUT /api/producers/:key/rubric`, which updates both the DB row and the on-disk file so the rubric is git-tracked).

## 8. Tool interface + fabrication

```python
class Tool(Protocol):
    name: str
    signature: dict       # {args_schema, returns_schema} — JSON Schema
    def call(self, args: dict, sandbox: Sandbox) -> ToolResult: ...
```

**Two invocation paths:**
1. **Plan steps of kind `tool`** — planner emits `{kind: 'tool', name: 'run_pytest', args: {...}}`; executor dispatches.
2. **LLM tool-use during code edits** — `PRProducer.execute_step` passes the tool registry as Anthropic tool-use definitions; Claude can call `read_file`, `write_file`, `run_pytest`, etc. mid-response.

**Bundled (hardcoded) tools shipped in MVP:**
- `read_file(path)`, `write_file(path, content)`
- `run_pytest(args)`
- `git_branch(name)`, `git_commit(message)`, `git_push()`
- `gh_pr_create(title, body, draft=True)`, `gh_pr_ready(pr_url)`

**Fabrication path (MVP — `seed_db` only, hardcoded fabrication template):**
1. Planner emits `{kind: 'tool', name: 'seed_db', args: {...}}`.
2. Executor checks Tool registry. **Lookup precedence:** `graduated` > `hardcoded` > `fabricated_sandbox_only` (current mission only) > miss.
3. On miss: `ToolFabricator.fabricate('seed_db', signature, context)` prompts Claude with the desired signature + repo's `pyproject.toml` + a fabrication prompt template; Claude returns Python source.
4. Source written to a fresh `NestedSandbox`, exec'd against a synthetic invocation (`python /work/tool.py {"rows": 3}`).
5. On non-zero exit: mark fabrication failed; mission step retries up to 3× with the error fed back to Claude.
6. On success: persist source to `tools/fabricated/<hash>/seed_db.py`, insert `Tool` row with `status='fabricated_sandbox_only'`, **also create an `Artifact` of `kind='tool'` linked to the Tool**, dispatch normally inside the mission sandbox.

Generalization of the fabrication prompt is post-MVP; for the hackathon the template hardcodes `seed_db`'s shape (factory-style row inserts against the sandbox Postgres). What IS general in the MVP: the **persist-and-graduate flow** — any fabricated tool becomes a reviewable Artifact, and on approval becomes reusable.

**Tool reuse across missions:**
- When a planner emits a `tool` step, the Tool registry is searched in the precedence order above. A `graduated` tool is picked up automatically — no re-fabrication.
- The planner's prompt context includes a registry summary (`{name, signature, status, last_used_at}` per available tool) so it can prefer tools that exist over fabricating new ones.
- A graduated tool is just Python source in `tools/graduated/<name>.py`. It's imported and called in the mission sandbox like any bundled tool.

**Tool promotion flow (user-driven):**
- User approves an Artifact of `kind='tool'` in the Review Queue.
- `Tool.status` flips to `graduated`. Source is copied to `tools/graduated/`.
- Next mission picks it up via the registry without re-fabrication.
- Rejecting removes the Tool row and deletes the source.

## 9. Mission lifecycle (worker)

```
queued
  └─► Celery picks up mission task
        ├─► mission.state = 'running', started_at = now()
        ├─► planner.plan(mission) → Plan v1 (persisted)
        ├─► sandbox.boot(image=resolve_image(mission), repo_url=mission.repo_url)
        │       resolve_image: if repo has a Dockerfile at root, build & use it;
        │                      otherwise fall back to `python:3.12-slim`.
        ├─► for step in plan.steps:
        │     spent = budget_increment_atomic(mission, step)
        │     if spent > budget:
        │         mission.state = 'stopped'; reason = 'budget_exceeded: <field>'; break
        │     try:
        │         result = producer.execute_step(step, sandbox, llm)
        │     except TransientFailure:
        │         retry up to 3×
        │     except NeedsInput as e:
        │         mission.state = 'needs_input'; needs_input_prompt = e.prompt; return
        │     except HardFailure:
        │         planner.replan(mission, failed_step) → Plan v(n+1) (once only)
        │         if still failing → mission.state = 'failed'; break
        ├─► artifact = producer.finalize(mission, sandbox)
        ├─► persist Artifact (kind = producer.kind), queue_state = 'pending'
        ├─► for each Tool fabricated during this mission:
        │     persist a second Artifact of kind='tool' linked to the Tool row
        │     (so the user sees and can graduate it independently)
        ├─► mission.state = 'succeeded', finished_at = now()
        └─► sandbox.teardown() (in finally)

needs_input
  └─► POST /api/missions/:id/respond writes needs_input_response, re-enqueues
       └─► worker resumes from the next step in the current plan
```

- **Budget enforcement:** `Mission.spent` updated via `UPDATE ... SET spent = spent || %s::jsonb RETURNING spent` per LLM call (tokens from Anthropic SDK response) and per `sandbox.exec` (wall-clock + tool_calls). Post-update check; breach → `stopped`.
- **`needs_input`:** raised by `Producer.execute_step` when the LLM emits a structured `<needs_input prompt="..." />` block. Worker stores prompt on `Mission.needs_input_prompt`, marks the in-flight step's `status = 'paused'`, returns. On `POST /respond`, the response is written to `Mission.needs_input_response`, the paused step's `status` is reset to `pending`, and the mission is re-enqueued. The worker resumes by re-executing the paused step with `needs_input_response` available in the LLM context. **MVP supports one needs_input cycle per mission**; a second `needs_input` after resume fails the mission (multi-cycle is a v0.2 item).
- **Wall-clock budget vs Celery `time_limit`:** Celery's `time_limit` is set to `max_wall_seconds + 30s` and is the hard kill of last resort. The in-code budget check is the graceful breaker — it lets us write a clean `stopped` reason and run teardown. Celery hard kill only fires if the in-code check is bypassed by a stuck syscall.

## 10. Review UI

**Layout — `/queue`:**

```
┌──────────────────────────────────────────────────────────────┐
│  Noctua · last night                            [⚙ rubrics]  │
│  [Code (3)] [Tools (1)] [Social (1)] [Clinical (1)] [Diag.]  │
├──────────────────────────────────────────────────────────────┤
│  ▼ pending (4)                                               │
│  ┌─ PR · noctua-demo-app#42 ─────────── 2 min ago ─┐         │
│  │  Add /healthz endpoint                          │         │
│  │  +12 -0 · tests ✓ · used tool: seed_db (new)    │         │
│  │  [view] [approve] [reject]                      │         │
│  └─────────────────────────────────────────────────┘         │
│  ┌─ Tool · seed_db ──────────────────── 3 min ago ─┐         │
│  │  Postgres factory-style seeder                  │         │
│  │  fabricated · tested ✓ · 42 lines               │         │
│  │  [view source] [graduate] [reject]              │         │
│  └─────────────────────────────────────────────────┘         │
│  ▼ needs input (1)                                           │
│  ▼ stopped (1)  "budget_exceeded: tokens"                    │
└──────────────────────────────────────────────────────────────┘
```

- One route lists everything. Tabs filter by artifact kind (Code = PRs, Tools = fabricated tools, then stub tabs).
- Sections: `pending`, `needs input`, `stopped`, `failed`, `recently approved` (collapsed).
- Detail page `/queue/:artifact_id`:
  - Breadcrumb: Mission goal → Plan version → Sandbox run.
  - For PR artifacts: GitHub diff embed (`<iframe>` of the PR's files view).
  - For Tool artifacts: source viewer (monaco read-only), signature card, the synthetic invocation that validated it, list of missions that have used it (empty on first review).
  - Live or final sandbox log (SSE if still running, file dump if done).
  - Fabricated tools used by this mission, linked to their own Artifact pages.
  - Action buttons:
    - PR artifact: **Approve** (`gh pr ready`) / Reject / Promote (no-op MVP).
    - Tool artifact: **Graduate** (promotes Tool to reusable) / Reject (deletes).
- Producer rubric editor at `/producers/:key/rubric` — monaco editor over `Producer.rubric_md`.
- **Stub tabs** render real Artifact rows seeded from `producers/stub/fixtures/*.json` at app startup; the platform thesis is visually present from minute one.

## 11. Error handling

- **Sandbox failures during boot** → mission goes `failed` with `reason='sandbox_boot: <docker error>'`.
- **Clone failures** → `failed` with `reason='clone: <git error>'`.
- **Planner produced invalid JSON** → 1 reprompt with the schema violation, then `failed`.
- **Step transient (e.g. test flakes)** → retry ≤3×, then re-plan once, then `failed`.
- **Hit `time_limit` in Celery** → `stopped` with `reason='budget_exceeded: wall_seconds'`.
- **Teardown always runs in `finally`.** Beat task sweeps orphans every 5 min.

## 12. Testing strategy

| Component | Approach |
|---|---|
| Sandbox manager | Integration test against real Docker daemon: boot a `python:3.12-slim` container, exec, write/read file, teardown. |
| Budget enforcement | Unit test the atomic increment SQL with a forced multi-thread race. |
| Planner | Schema-validate output against a JSON Schema; golden-file test on three example missions. |
| PR producer happy path | Run against a fixture repo (in `tests/fixtures/sample_repo`) with a known issue; assert PR creation call args. |
| Fabricator | Round-trip test: seed_db is fabricated, executed, validated against a sandboxed Postgres, source persisted, Artifact of kind='tool' created. |
| Tool graduation | Approve a `kind='tool'` Artifact → Tool.status flips to `graduated`, source copied to `tools/graduated/`, a follow-up mission resolves the tool from the graduated registry without re-fabrication. |
| API | Django Ninja test client; auth-required, queue filtering, approve flow updates state. |
| UI | Manual + Playwright smoke for the demo flow (mission appears in queue → click view → click approve → PR state flips). |

## 13. Demo safety

- Every mission archives its `Plan`, `SandboxRun.log_path`, and `Artifact` to `./archive/<mission-id>/` on teardown.
- A `noctua replay <mission-id>` CLI command exists for the demo: it re-emits the archived events (planner output, log lines, artifact creation) to the API without actually running Docker. If the live demo fails, we cut to a replayed mission.
- The demo repo `noctua-demo-app` is pinned to a known commit; a `make reset-demo` target deletes branches and closes prior PRs between runs.

## 14. Out of scope (explicit)

- Multi-user / multi-tenant — single bearer token.
- Generalized tool fabrication — fabrication prompt template is hardcoded for `seed_db` shape only. Other tool fabrications fail until the template is generalized post-MVP. (Tool **persistence and reuse** of the seed_db Tool *is* in scope.)
- Build-a-tool-as-primary-deliverable (`ToolProducer`) — tools are only produced incidentally during code missions; no mission can have "build me a tool" as its top-level goal in MVP.
- Full-repo artifacts — a Tool is a single Python file in MVP, not a multi-file repo.
- Proactivity loop / signal scanners — missions are user-fired only.
- Snapshot/replay of *sandbox state* — only event archival, not container snapshots.
- Sandbox-stack via docker-compose — single container per mission only.
- Real social-post / clinical / CAD / diagnostic producers — stubs only.
- Producer training via examples — rubric markdown only in MVP.
- Auto-merge / auto-act on approval — `on_promote` is a no-op for MVP.

## 15. Open items for user review

1. **`auto_act` location** — `Mission` (proposed) vs `Producer`. Default: Mission.
2. **Plan storage** — JSONB (proposed) vs separate `Step` table. Default: JSONB.
3. **Hosting for the demo** — localhost only? Public ngrok URL for the judge? Default: localhost (laptop reliability beats theatrics).
4. **LLM models** — Claude Sonnet 4.6 for planner, Opus 4.7 for code edits and fabrication. Prompt caching enabled on repo context. Default: ship.
5. **Demo repo issues** — proposed three: (a) trivial `add /healthz`, (b) needs `seed_db` fabrication, (c) multi-file edit (`add unit conversion module`). Default: ship.
