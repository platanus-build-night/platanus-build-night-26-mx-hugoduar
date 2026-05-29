# Noctua — Hackathon MVP

Minimal, build-ordered feature spec. Pairs with [PRD.md](./PRD.md). One vertical: **overnight PR builder**. Other domains shown as canned-artifact stubs in the UI to convey the platform thesis.

---

## North-star demo (3 min)

1. `noctua run <github-issue-url>` from the CLI.
2. Sandbox boots in a Docker container; logs stream live.
3. Planner emits a step graph; executor edits code, runs tests, iterates.
4. A draft PR opens on GitHub with the Noctua report embedded.
5. Open the web Review Queue → approve → PR flips to ready-for-review.
6. Click "Social posts" tab → canned artifact from a stub producer. *"Same spine, different producer."*

If the judge can do step 1 and reach step 5 unaided, we win.

---

## Feature list — must-have

| # | Feature | Acceptance criterion |
|---|---|---|
| F1 | **Mission CLI** `noctua run <issue-url>` | Accepts URL, posts to control plane, returns mission ID. |
| F2 | **Control plane** (FastAPI + SQLite) | `POST /missions`, `GET /missions/:id`, `GET /queue`, `POST /artifacts/:id/approve`. |
| F3 | **Sandbox manager** (Docker) | Boots a container from repo `Dockerfile` (or fallback `python:3.12-slim` / `node:20`), mounts repo, runs commands, streams logs, tears down. Hard 30-min TTL. |
| F4 | **Planner** (Claude Sonnet) | Reads issue body + repo `README`/`package.json`/`pyproject.toml`; emits JSON plan: `[{step_id, kind: tool\|exec\|edit, payload, retries: 0/3}]`. |
| F5 | **Executor loop** | Walks plan, runs each step, retries failing exec steps up to 3× with new Claude turn, halts on hard failure. |
| F6 | **PR producer** | After green tests: `git checkout -b noctua/<mission-id>`, commit, push, `gh pr create --draft` with Noctua report in body. |
| F7 | **Tool fabricator — `seed_db` only** | Hardcoded: when planner emits step `{kind: tool, name: seed_db}` and tool isn't registered, write a Python seeder, exec inside sandbox, persist to `tools/seed_db.py`. |
| F8 | **Review UI** (Next.js, one page) | `/queue` lists artifacts; click → PR link + sandbox log tail + Approve / Reject. Approve = `gh pr ready`. |
| F9 | **Stub producers** | Static JSON of one example artifact each for: social-post, clinical-analysis, diagnostic-worksheet. Shown as separate tabs in `/queue`. No backend. |
| F10 | **Demo repo** | Public repo with 3 ready-to-solve issues (one trivial, one needs seed_db, one needs a multi-file edit). |

## Cut for hackathon

- Auth, multi-user, billing, multi-tenant.
- Tool reuse across missions (each mission re-fabricates).
- Snapshot / replay (live logs only).
- Proactivity loop / cron / signal scanners (user fires missions manually).
- Compose-stack sandboxes (single-container only).
- Real social-post / clinical / CAD producers.

## Stretch (only if shipped early)

- **S1** — Real social-post producer from `CHANGELOG.md` diff using Claude. Cheap, visual, reinforces the platform thesis.
- **S2** — Sandbox snapshot to a tarball, attached to artifact.
- **S3** — `noctua propose` — scan the demo repo's issues, auto-create missions for any tagged `noctua`.

---

## Suggested stack

| Layer | Choice | Why |
|---|---|---|
| Control plane | **FastAPI + SQLite** | Zero-config, async, fast to ship. |
| Worker | **Same process, asyncio task queue** | No Redis / Celery for hackathon. |
| Sandbox | **Docker SDK for Python** | Direct, scriptable, no compose for MVP. |
| LLM | **Anthropic SDK (Claude Sonnet 4.6 for planning, Opus 4.7 for code edits)** | Caching enabled on repo context. |
| Review UI | **Next.js + Tailwind, server actions hitting FastAPI** | Fastest path to a polished single page. |
| Git ops | **`gh` CLI shelled out** | Avoid Octokit bring-up. |

---

## Build order (Fri night → Sun demo)

### Friday night — spine
- [ ] Repo skeleton: `cli/`, `control_plane/`, `sandbox/`, `producers/`, `ui/`, `demo_repo/`.
- [ ] **F2** control plane with the four endpoints + SQLite migrations.
- [ ] **F1** CLI that POSTs to control plane.
- [ ] **F3** sandbox manager: boot, exec, stream logs, teardown. Unit-tested with `python:3.12-slim`.

### Saturday morning — brain
- [ ] **F4** planner: prompt + JSON-schema output + repo-context prompt cache.
- [ ] **F5** executor loop with retry budget.
- [ ] First end-to-end smoke: hardcoded issue → plan → echoed commands in sandbox.

### Saturday afternoon — producer + tools
- [ ] **F6** PR producer (git ops + `gh`).
- [ ] **F7** hardcoded `seed_db` fabrication path.
- [ ] **F10** demo repo with 3 issues; verify all three close end-to-end via CLI.

### Saturday night — UI
- [ ] **F8** Review UI: queue list, detail page, approve action.
- [ ] **F9** stub producer tabs with canned artifacts.

### Sunday morning — demo polish
- [ ] Pre-record a sandbox boot as fallback if Docker is flaky on judge wifi.
- [ ] Write the 3-minute script. Practice it twice.
- [ ] Make the README dazzle: GIF of the queue, one-line install, link to PRD.

---

## Repo layout

```
platanus/
├── PRD.md
├── HACKATHON_MVP.md
├── README.md
├── cli/
│   └── noctua/                # `pip install -e cli/`
├── control_plane/
│   ├── api.py                 # FastAPI app
│   ├── db.py                  # SQLite models (mission, plan, artifact)
│   └── worker.py              # async mission runner
├── sandbox/
│   ├── manager.py             # Docker SDK wrapper
│   └── templates/
│       └── default.Dockerfile
├── planner/
│   ├── prompts/
│   │   ├── plan.md
│   │   └── repo_context.md
│   └── planner.py
├── producers/
│   ├── pr/
│   │   └── producer.py
│   ├── social_post/           # stub w/ canned artifact
│   ├── clinical/              # stub
│   └── diagnostic/            # stub
├── tools/
│   ├── fabricator.py
│   └── seed_db.py             # hardcoded fabrication target
├── ui/                        # Next.js
│   └── app/queue/page.tsx
└── demo_repo/                 # pushed to a public GitHub repo
    ├── README.md
    ├── pyproject.toml
    └── ISSUES.md              # 3 ready-to-solve issues
```

---

## Open decisions to make before Friday

1. **Demo repo language** — Python (faster sandbox boot, simpler test runner). Decision: **Python**.
2. **Single host vs. cloud** — Run sandboxes on the demo laptop or a cheap VPS? **Laptop** for demo reliability; cloud only if we add S2.
3. **Auth on control plane** — Skip entirely; bind to localhost.
4. **Where do artifacts live?** — Postgres BLOBs vs. filesystem refs. **Filesystem** under `./artifacts/<mission-id>/`.
5. **Demo issue difficulty curve** — One should fail-then-recover live to show the retry loop without scaring the judge.

---

## What success looks like at the demo table

- Judge types one command. Things happen. Three minutes later a real GitHub PR exists, with passing CI, and a story embedded in the body.
- The Review UI feels finished. Stub tabs convince the judge the spine is real even though only one vertical is live.
- We can answer "what's the moat?" in one sentence: **"Domain-agnostic mission spine with on-the-fly tool fabrication and sandboxed validation. We're not a code agent — we're an overnight artifact factory, and code is just our first producer."**
