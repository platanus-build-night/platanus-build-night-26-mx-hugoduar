# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Noctua is an **overnight artifact factory**: a mission goes in, an artifact (PR, social post, clinical analysis, mechanic diagnostic, CAD spec, or fabricated tool) comes out, ready for human review in the morning. Read `README.md` for the product framing and `docs/superpowers/specs/2026-05-29-noctua-mvp-design.md` for the buildable design — it is the source of truth, not the README.

The system is a Django Ninja control plane + Postgres + Celery worker + Docker-backed sandbox + Next.js review UI. Producers are plugins registered via Python entry points.

## Day-to-day commands

```bash
# First-time setup
cp .env.example .env                    # fill in ANTHROPIC_API_KEY, NOCTUA_API_TOKEN, GITHUB_TOKEN
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make up && make migrate && make seed   # postgres+redis up, schema applied, Producer rows seeded

# Three terminals (each must `source .venv/bin/activate` first, and `set -a; source .env; set +a`)
make api      # Django Ninja on :8000
make worker   # Celery worker (also runs the orphan-reaper beat task)
cd ui && npm install && npm run dev   # Next.js on :3000

# Fire a mission
noctua run --producer pr --repo <url> --issue <url> --goal "..."
noctua run --producer social_post --goal "Draft a launch tweet"   # no repo needed for content-only producers
```

### Tests

```bash
make test                                     # pytest -x, full suite
pytest tests/runner/test_lifecycle.py -v      # one file
pytest tests/runner/test_executor.py::test_executes_tool_steps_in_order -v   # one test
pytest tests/sandbox/ -v                      # one tree; sandbox tests hit real Docker
```

Tests rely on `pytest-django` (settings = `noctua.settings`) and an autouse fixture in `tests/core/conftest.py` that sets `CELERY_TASK_ALWAYS_EAGER=True` for that tree. `tests/sandbox/` tests boot real containers and need Docker running; everything else can run without it.

The known pre-existing flake is `tests/core/test_mission_api.py::test_create_mission` (it exercises the full eager mission lifecycle, which requires Docker + an Anthropic key in the test process). Treat it as flaky, not a regression signal.

### Useful manage.py commands

```bash
./manage.py seed_producers          # idempotent — re-syncs Producer rows from rubric markdown
./manage.py seed_stub_artifacts     # now a no-op pointing at `noctua run --producer ...`
./manage.py replay <mission_id>     # dumps archive/<id>/{mission,plans,artifacts}.json
./manage.py shell                   # Django ORM REPL
```

## Architecture

### The mission flow (memorize this)

1. **CLI / API** — `noctua run` (Click) POSTs to `POST /api/missions`. The view persists a `Mission` row and calls `run_mission.delay(mission_id)`.
2. **Worker** (`noctua/runner/tasks.py:run_mission`) is the lifecycle conductor. It branches on `producer.content_only`:
   - **Content-only producers** (social_post, clinical_analysis, diagnostic, cad): skip sandbox + planner + executor; call `producer.finalize` which does a single Claude call and creates an `Artifact`.
   - **PR producer** (anything where `content_only=False`): boots a `Sandbox`, calls `plan_for_mission`, runs `execute_plan`, calls `producer.finalize`. For each `Tool` row marked `fabricated_sandbox_only` during the mission, an extra `Artifact(kind="tool")` is emitted so it can be reviewed and graduated.
3. **Mission archival** runs in the `finally` block — writes `archive/<id>/{mission,plans,artifacts}.json`. Best-effort; never blocks the mission.

The lifecycle distinguishes terminal states explicitly: `succeeded`, `failed`, `stopped` (budget exceeded), `needs_input` (paused for user clarification). `NeedsInput` and `StoppedByBudget` are exceptions raised by the executor and caught by the worker.

### Module responsibilities

| Module | Job | Don't touch unless you mean it |
|---|---|---|
| `noctua/core/` | Django app: models, schemas, API routes, auth, management commands. All HTTP lives here. | `models.py` choices fields, `migrations/` |
| `noctua/runner/` | Mission orchestration: planner, executor, budget enforcer, Celery task, archive, LLM wrapper. | The `_TERMINAL` states list in `api.py:stream_mission_logs` |
| `noctua/sandbox/` | `Sandbox` (Docker SDK wrapper) and `NestedSandbox` (no-network, tighter caps, used by fabricator). Boot also persists a `SandboxRun` row when `mission_id` is set. | `nano_cpus` kwarg (NOT `cpu_count` — Windows-only in docker-py) |
| `noctua/tools/` | `ToolRegistry` (lookup precedence: graduated > hardcoded > fabricated-for-this-mission), 8 bundled tools in `bundled.py`, and `ToolFabricator`. | The precedence order in `registry.py:lookup` |
| `noctua/producers/` | Producer plugins. `pr/` is the real one; `stub/` holds `ContentProducer` and four content-only kinds. Registered via `pyproject.toml`'s `[project.entry-points."noctua.producers"]`. | Entry-point group name |
| `ui/` | Next.js 16 App Router. `app/queue`, `app/missions`, `app/sandboxes`. **READ `ui/AGENTS.md` BEFORE TOUCHING UI.** |

### Data model

Six tables in Postgres (all in `noctua/core/models.py`):

- **Mission** — the work order. `state` (queued → running → terminal), `budget` + `spent` jsonb pair, `needs_input_prompt/response` for resume.
- **Plan** — `JSONField` list of steps (`{step_id, kind: 'exec'|'tool'|'edit', payload, status, attempt, result}`). The planner emits, the executor mutates step status in place (re-saves trigger JSONB-dirty via `plan.steps = plan.steps` reassignment).
- **SandboxRun** — Docker container metadata per mission. `state` lifecycle: booting → ready → torn_down.
- **Tool** — `status` is the gradient: `hardcoded` (bundled) > `fabricated_sandbox_only` (mission-scoped) > `graduated` (reusable). Source lives under `tools/{fabricated,graduated}/`.
- **Artifact** — what lands in the queue. `queue_state` (pending → approved/rejected/promoted). For tool artifacts, `tool` FK points to the Tool row.
- **Producer** — `key` (primary key), `rubric_md`. The rubric is injected into the planner prompt; user-editable via `PUT /api/producers/{key}/rubric` which also writes back to disk.

### LLM conventions

- `noctua/runner/llm.py:call_with_cache` is the single entry point. System prompt always gets `cache_control: {type: "ephemeral"}`.
- Anthropic tool-use loop: **branch on `stop_reason == "tool_use"` first**, then `end_turn`, then `max_tokens`, then abort on `refusal`/`stop_sequence`/`pause_turn`. The opposite ordering is a real bug (the executor's edit dispatch was caught at v1).
- `PLANNER_MODEL = "claude-sonnet-4-6"`, `CODER_MODEL = "claude-opus-4-7"`.
- The runtime guard in `call_with_cache` raises `RuntimeError("ANTHROPIC_API_KEY is empty...")` early if the worker missed loading `.env`. This is intentional — keep it.

### Sandbox conventions

- `Sandbox.boot` always installs git + gh, sets `git config --global user.email/user.name`, and runs `gh auth setup-git` (gated on `$GITHUB_TOKEN`). This is the only way Claude-emitted raw `git commit` commands work — don't move it back inside the `if repo_url:` branch.
- `repo_url` is validated against `^https://github\.com/[\w.-]+/[\w.-]+(\.git)?/?$` before `git clone`. Likewise PR URL for `gh pr ready`. Both pass `--` to defeat git/gh argument injection. **Never** interpolate user/LLM-supplied URLs into `bash -lc` strings.
- Token comparison in `BearerAuth.authenticate` uses `hmac.compare_digest`. Don't regress to `==`.
- The fabricator uses `Sandbox` (with network) for validation, NOT `NestedSandbox` — pip needs network. NestedSandbox is reserved for trusted-tool execution at runtime.

### UI conventions

- **Read `ui/AGENTS.md` before touching anything in `ui/`.** It mandates reading `node_modules/next/dist/docs/` for the actual Next.js version's API. Training data on Next.js may not apply.
- Tailwind 4 — no `tailwind.config.ts`; classes work via `@tailwindcss/postcss` plugin in `postcss.config.mjs`.
- All client-side API calls go through the helper `call()` in `ui/lib/api.ts` which throws on non-OK responses. **Don't** introduce bare `fetch().json()` — the previous error mode (silent objects becoming `.filter is not a function`) is the precise thing that helper prevents. The SSE log stream is the only exception: it's proxied through a Next.js Route Handler at `ui/app/api/missions/[id]/logs/route.ts` so the token stays server-side.
- Token wiring is double-tracked: `NEXT_PUBLIC_NOCTUA_TOKEN` for client-side fetches (visible in the bundle, known security trade-off) and server-only `NOCTUA_API_TOKEN` for the SSE proxy. Don't conflate them.

## Gotchas surfaced the hard way

- **macOS `localhost` resolves to `::1` first in Node.** `manage.py runserver` binds IPv4 only. Use `http://127.0.0.1:8000` in `ui/.env.local` (the project ships this way). Don't switch back to `localhost` without also running the API on `0.0.0.0`.
- **`NEXT_PUBLIC_*` envs are baked at `npm run dev` startup.** Restart the dev server after editing `ui/.env.local`. HMR won't pick them up.
- **`pip install -e ".[dev]"` was breaking on package auto-discovery** because of the `ui/` directory. Fixed by `[tool.setuptools.packages.find] include = ["noctua*"]` in `pyproject.toml` — leave it.
- **Worker process must inherit `.env`.** `noctua/settings.py` calls `load_dotenv(BASE_DIR / ".env")` explicitly. If you ever start the worker without `set -a; source .env; set +a`, the runtime guard in `call_with_cache` will say so.
- **Sandbox cold boot is ~30s** because of the apt + gh install. Pre-baking a `noctua/sandbox-runtime` image is the obvious follow-up; not done yet.
- **JSONField in-place mutation is invisible to Django ORM.** The executor reassigns `plan.steps = plan.steps` before `save(update_fields=["steps"])` to mark it dirty. Don't drop the reassignment.

## Where to look first

| Want to change | Start at |
|---|---|
| How a mission progresses through states | `noctua/runner/tasks.py:run_mission` |
| Add a new artifact kind | Add to `ARTIFACT_KINDS` in `models.py`, write a producer in `noctua/producers/`, register in `pyproject.toml` entry points |
| What Claude is told | `noctua/runner/prompts/plan.md` (planner), `noctua/producers/pr/prompts/edit.md` (code edits), `noctua/producers/stub/prompts/*.md` (content kinds), `noctua/tools/prompts/seed_db.md` (fabrication) |
| The API surface | `noctua/core/api.py` — single file, all endpoints |
| The Review UI | `ui/app/{queue,missions,sandboxes}/` |
| Live log streaming | `noctua/core/api.py:stream_mission_logs` (Django SSE) + `ui/app/api/missions/[id]/logs/route.ts` (Next.js proxy) + `ui/components/LogPane.tsx` (EventSource client) |
