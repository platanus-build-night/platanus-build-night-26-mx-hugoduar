# Noctua

> *"An AI that never sleeps."*

A proactive, multi-domain artifact factory: queue a goal before bed, wake up to a reviewable artifact. Code PRs, reusable tools, social posts, clinical analyses, mechanic diagnostics — same orchestration spine, different producers.

<img width="1408" height="768" alt="Generated Image May 29, 2026 - 5_13PM" src="https://github.com/user-attachments/assets/086a6b46-16da-49c3-94f6-849a217471c1" />


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

## Hackathon MVP

One vertical end-to-end:

- **CLI:** `noctua run <github-issue-url>` fires a mission.
- **Sandbox:** Docker container per mission (single-host).
- **Producer:** PR builder — clones repo, drives a code-edit + test-run loop, opens a draft PR via `gh`.
- **Tool fabrication:** hardcoded template fabricates a `seed_db` script when the planner needs one; fabricated tools persist and can be **graduated** to the reusable Tool Library via the Review UI.
- **Review UI:** one Next.js page with tabs per producer kind. Approve → `gh pr ready`.
- **Stub producers** (social post, clinical analysis, diagnostic) appear as tabs with canned artifacts so the multi-domain thesis is visible from minute one.

## Architecture

```
┌───────────────────────────────┐    HTTP        ┌─────────────────────┐
│       Next.js Review UI       │ ──────────── ► │  Django Ninja API   │
│   /queue · detail · rubrics   │               │   + Postgres        │
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
                                              ┌──────▼─────┬─────────┐
                                              │  Sandbox   │ Tools + │
                                              │  (Docker)  │ Fabricator│
                                              └────────────┴─────────┘
```

## Stack

| Layer | Choice |
|---|---|
| Control plane | Django Ninja + Postgres |
| Worker | Celery + Redis |
| Sandbox | Docker SDK for Python |
| LLM | Anthropic SDK (Sonnet 4.6 planner, Opus 4.7 code edits & fabrication, prompt caching enabled) |
| Review UI | Next.js + Tailwind |
| Git ops | `gh` CLI shelled out |

## Run it yourself

Prereqs: Docker (Desktop or Colima), Python 3.12+, Node 20+, `gh` CLI, an Anthropic API key.

```bash
# 1. Bring up the stack
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY, NOCTUA_API_TOKEN (any random string), GITHUB_TOKEN
make up           # postgres + redis via docker-compose
make migrate      # apply Django migrations
make seed         # seed Producer rows

# 2. Run the API + worker (two terminals)
make api          # Django Ninja API on :8000
make worker       # Celery worker (in another terminal)

# 3. Run the Review UI (third terminal)
cd ui && cp .env.local.example .env.local
# edit .env.local: set NEXT_PUBLIC_NOCTUA_TOKEN to the same NOCTUA_API_TOKEN
npm install && npm run dev

# 4. Fire a mission
export NOCTUA_API_TOKEN=...  # same as in .env
export NOCTUA_API_URL=http://localhost:8000
noctua run \
  --repo https://github.com/hugoduar/noctua-demo-app \
  --issue https://github.com/hugoduar/noctua-demo-app/issues/1 \
  --goal "Add /healthz endpoint returning {ok: true}"

# 5. Open http://localhost:3000/queue and review the result
```

## Read first

- **[Design spec](./docs/superpowers/specs/2026-05-29-noctua-mvp-design.md)** — the buildable design, the source of truth.
- **[Implementation plan](./docs/superpowers/plans/2026-05-29-noctua-mvp.md)** — task-by-task build with tests, code, and commits.
- **[PRD](./docs/planning/PRD.md)** — full product vision, principles, multi-domain personas.
- **[Hackathon MVP scope](./docs/planning/HACKATHON_MVP.md)** — feature list and dependency order.

## What this is *not*

Not Devin/Cursor (those amplify the workday — Noctua extends it overnight). Not n8n/Zapier (deterministic). Not AutoGPT (no reviewable artifact). Not a CI system (CI validates code humans wrote; Noctua writes the code *and* validates it).

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
