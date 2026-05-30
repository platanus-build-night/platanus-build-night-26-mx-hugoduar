# Noctua

> *"An AI that never sleeps."*

A proactive, multi-domain artifact factory: queue a goal before bed, wake up to a reviewable artifact. Code PRs, reusable tools, social posts, clinical analyses, mechanic diagnostics — same orchestration spine, different producers.

<img width="1408" height="768" alt="Noctua hero image" src="https://github.com/user-attachments/assets/086a6b46-16da-49c3-94f6-849a217471c1" />

**Hacker:** Hugo Jimenez ([@hugoduar](https://github.com/hugoduar)) — Platanus Build Night Ciudad de México.

---

## What Noctua does

You give Noctua a **Mission** — a goal plus optional inputs and success criteria. While you sleep:

1. A **Planner** (Claude) emits a step graph.
2. A **Docker sandbox** boots — isolated, capped, ephemeral.
3. A **Producer** (domain plugin) drives the work: edits code, runs tests, queries data, generates a post.
4. If a needed **Tool** doesn't exist, Noctua **fabricates** one in a nested sandbox, validates it, persists it for next time.
5. The output lands as an **Artifact** in your morning **Review Queue** — approve, reject, or graduate (for tools).

Hard caps on tokens, wall-clock, and tool calls keep cost bounded. Every artifact is reproducible from its mission spec.

## Architecture

```
┌───────────────────────────────┐    HTTP        ┌─────────────────────┐
│       Next.js Review UI       │ ────────────► │  Django Ninja API   │
│   /queue /missions /signals   │               │   + Postgres        │
└───────────────────────────────┘               └──────────┬──────────┘
                                                            │ enqueue
                                                            ▼
                                            ┌──────────────────────────┐
                                            │  Celery worker (Redis)   │
                                            │  ┌────────────────────┐  │
                                            │  │ Planner (Claude)   │  │
                                            │  │ Executor           │  │
                                            │  │ Budget enforcer    │  │
                                            │  └─────┬──────────────┘  │
                                            └────────┼─────────────────┘
                                              ┌──────▼─────┬─────────────┐
                                              │  Sandbox   │ Tools +     │
                                              │  (Docker)  │ Fabricator  │
                                              └────────────┴─────────────┘
```

## Stack

| Layer | Choice |
|---|---|
| Control plane | Django Ninja + Postgres |
| Worker | Celery + Redis |
| Sandbox | Docker SDK for Python |
| LLM | Anthropic SDK (Sonnet 4.6 planner, Opus 4.7 code edits & fabrication, prompt caching enabled) |
| External tools | Composio (managed gateway for social/clinical/diagnostic/cad producers) |
| Inbound triggers | Signals: Sentry webhooks, GitHub-style feature requests, WhatsApp via Kapso, manual mock CLI |
| Review UI | Next.js + Tailwind |
| Git ops | `gh` CLI shelled out from inside the sandbox |

## Run it yourself

### 0 · Prereqs

- **Docker** (Desktop or Colima) running on your host.
- **Python 3.12+**, **Node 20+**, **`gh` CLI** authenticated (`gh auth login`).
- An **Anthropic API key** — at minimum. Composio + Kapso are optional.

### 1 · One-time setup

```bash
git clone <this-repo> noctua
cd noctua

# Python deps + Postgres + Redis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure env — see .env.example for what each var does
cp .env.example .env
$EDITOR .env                            # fill in NOCTUA_API_TOKEN, ANTHROPIC_API_KEY, GITHUB_TOKEN, NOCTUA_DEMO_REPO

make up                                 # postgres + redis via docker-compose
make migrate                            # apply Django migrations
make seed                               # seed Producer rows from rubric markdown files
```

If you want PRs against a target repo, fork [`hugoduar/noctua-demo-app`](https://github.com/hugoduar/noctua-demo-app) (or any small Python repo with tests) and set `NOCTUA_DEMO_REPO` to your fork.

### 2 · Run the stack (three terminals)

Every terminal needs the venv activated and `.env` loaded:

```bash
source .venv/bin/activate
set -a; source .env; set +a
```

Then in three separate terminals:

| Terminal | Command | What it does |
|---|---|---|
| 1 | `make api` | Django Ninja on `:8000` |
| 2 | `make worker` | Celery worker — runs mission lifecycles + the orphan-container reaper |
| 3 | `cd ui && cp .env.local.example .env.local && $EDITOR .env.local && npm install && npm run dev` | Next.js review UI on `:3000`. Set `NEXT_PUBLIC_NOCTUA_TOKEN` and `NOCTUA_API_TOKEN` in `.env.local` to the **same** value as `NOCTUA_API_TOKEN` in the project root `.env`. |

Then open <http://localhost:3000>.

### 3 · Fire a mission

Three ways to trigger one (any of them works once the stack is up):

**a) CLI** — full control:

```bash
noctua run \
  --repo $NOCTUA_DEMO_REPO \
  --issue $NOCTUA_DEMO_REPO/issues/1 \
  --goal "Add /healthz endpoint returning {ok: true}"
```

**b) Feature request signal** — most direct path to a code PR:

```bash
./manage.py mock_feature_request --sample-index 0
```

Five curated sample goals (run with `--help` to see all). Each one's tractable against the demo repo's tiny FastAPI surface.

**c) Mock Sentry signal** — exercises the auto-routing flow:

```bash
./manage.py mock_sentry_issue --project-slug noctua-demo-app
```

Routes the fake error to the PR producer through the same signal pipeline real Sentry webhooks use.

Watch the mission progress at `/missions/<id>` — full plan with per-step status, live sandbox log streaming, and the resulting artifact landing in `/queue`.

### 4 · Optional integrations

These are gated by their respective env vars; leave them blank to skip.

| Feature | Vars in `.env` | What unlocks |
|---|---|---|
| **Composio** | `COMPOSIO_API_KEY` | Non-PR producers (social_post, clinical_analysis, diagnostic, cad). The Connections page in the UI lets you OAuth into LinkedIn, Twitter, Google Drive, etc. |
| **WhatsApp** (Kapso) | `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`, `KAPSO_PHONE_NUMBER_ID`, `NOCTUA_WHATSAPP_ALLOWLIST` | Fire missions and receive completion replies via WhatsApp. Expose `POST /api/signals/whatsapp` over the public internet (ngrok works) and point Kapso at it. |
| **Sentry webhook** | (uses `NOCTUA_API_TOKEN`) | Configure Sentry's webhook to `POST <noctua>/api/signals/sentry` with `Authorization: Bearer $NOCTUA_API_TOKEN`. Only `error` / `fatal` issues from projects mapped in `noctua/signals/router.py` route to a PR mission. |

## Read first

- **[Design spec](./docs/superpowers/specs/2026-05-29-noctua-mvp-design.md)** — buildable design, source of truth.
- **[Implementation plan](./docs/superpowers/plans/2026-05-29-noctua-mvp.md)** — task-by-task build with tests, code, and commits.
- **[PRD](./docs/planning/PRD.md)** — full product vision, principles, multi-domain personas.
- **[`CLAUDE.md`](./CLAUDE.md)** — gotchas, conventions, and "where to look first" for future contributors (human or AI).

## What this is *not*

Not Devin/Cursor (those amplify the workday — Noctua extends it overnight). Not n8n/Zapier (deterministic). Not AutoGPT (no reviewable artifact). Not a CI system (CI validates code humans wrote; Noctua writes the code *and* validates it).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `npm run dev` works but `/queue` shows "Queue failed to load" 401 | `NEXT_PUBLIC_NOCTUA_TOKEN` in `ui/.env.local` doesn't match `NOCTUA_API_TOKEN` in `.env` | Sync the values, restart `npm run dev` (NEXT_PUBLIC_* are baked at startup) |
| Page renders but every API call says "Failed to fetch" | Node resolves `localhost` to IPv6 (`::1`), Django binds only IPv4 | Use `127.0.0.1` instead of `localhost` in `NEXT_PUBLIC_NOCTUA_API` |
| Worker logs `ANTHROPIC_API_KEY is empty` | `.env` not loaded into the worker process | `set -a; source .env; set +a` then `make worker` again |
| Mission stays in `queued` forever | Worker not running, or `.env` not loaded into it | See above |
| Mission says `Mission matching query does not exist` | (Fixed in `48ab09b` — pre-`on_commit` race) | Pull latest |
| Sandbox boot takes 30+s on a fresh image | apt + gh install runs in the container; first boot pulls layers | Pre-pull: `docker pull python:3.12-slim`. Long-term, bake a custom image. |
| Mission opens a draft PR with only `NOCTUA.md` | You used the manual "Create PR" button; that path commits a placeholder. | For real code PRs, fire a regular mission via `noctua run` or `mock_feature_request`. |

---

## ⚠️ Deploying (Vercel, Render, etc.)

Deploy platforms can't connect to org repos. Mirror to a personal repo:

1. Create a **personal** repo on your own GitHub account.
2. Point local `origin` at both:

   ```bash
   git remote set-url --add --push origin https://github.com/platanus-build-night/platanus-build-night-26-mx-hugoduar.git
   git remote set-url --add --push origin https://github.com/<your-user>/<your-repo>.git
   ```

3. Connect your deploy service to the personal repo.
