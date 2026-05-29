# PRD — Noctua

> *"An AI that never sleeps."*
> A proactive, multi-domain artifact factory that runs missions overnight in sandboxed environments and hands you reviewable artifacts in the morning — code PRs, social posts, clinical-trial analyses, mechanic diagnostic kits, machining diagrams, anything.

**Author:** Hugo (hugod@carmool.com)
**Date:** 2026-05-29
**Status:** Draft v0.1 (hackathon scope)
**Codename:** Noctua (the owl that hunts at night)

---

## 1. Problem

Knowledge workers and operators across every field share the same nightly bottleneck: **work that could happen while they sleep, doesn't.** A developer wakes to the same backlog they left. A mechanic doesn't get a diagnostic worksheet built from last night's telematics. A clinical researcher hand-builds the same cohort analysis a fresh GPT could have prepared. The throughput cap isn't intelligence — it's *orchestration of overnight agency*, with safe sandboxes, real data, and review-ready outputs.

Existing agent products either:
- Run *during* the user's day (Cursor, Copilot) — they amplify, but don't extend, the workday.
- Produce text only — no executable validation, no domain artifacts (CAD, datasets, dashboards), no reproducible sandbox.
- Are single-domain (devin = code only) — they can't cross from PRs to social posts to diagnostic reports.

**Noctua is the missing layer:** a domain-agnostic *mission runner* that boots its own sandboxes, fabricates tools on the fly, validates the work, and queues the output for human review.

---

## 2. Users & jobs-to-be-done

| Persona | Overnight job |
|---|---|
| **Solo founder / lead engineer** *(primary, hackathon demo)* | "While I sleep, ship 1–3 well-tested PRs against my repo for backlog items I tagged `noctua`." |
| **Field mechanic** | "Ingest last night's telematics from the fleet, surface 3 vehicles at risk, generate a one-page diagnostic worksheet + parts list per vehicle, flag any that need a custom-machined part with a draft DXF." |
| **Clinical researcher** | "Pull yesterday's trial data drops, run pre-registered cohort comparisons, produce a one-page significance summary with caveats." |
| **Marketing operator** | "From this week's product changelog + analytics, draft 5 social posts in our voice with image briefs." |

The unifying pattern: **input signal → overnight reasoning + execution in a sandbox → reviewable artifact bundle by morning.**

---

## 3. Product principles

1. **Review-first, not autonomy-first.** Noctua's output is *always* a reviewable artifact. Never auto-merge, auto-post, or auto-act on the world without a morning human approval — unless the user explicitly grants per-mission auto-act.
2. **Sandbox by default.** Every mission runs in an isolated environment (container + ephemeral DB + seeded data). Nothing touches prod without a signed promotion step.
3. **Validate, don't just generate.** A PR isn't done until tests pass *inside the sandbox*. A diagnostic isn't done until it runs against synthetic telematics. A clinical analysis isn't done until the stats reproduce on a held-out slice.
4. **Tools on the fly.** When a mission needs a capability that doesn't exist (a DXF generator, a Postgres seed script, a stats notebook), Noctua *builds* the tool, tests it, and reuses it next time.
5. **Domain-agnostic spine, domain-specific producers.** The orchestration spine knows nothing about code or cars; *producers* know domains. New verticals = new producers.
6. **Cheap to kill.** Every mission is reproducible from its mission spec; artifacts are throwaway until reviewed. And it also should have a cap on tokens/times and tools usage to be careful about not exceeding resources. 

---

## 4. Core concepts

```
Mission ──► Plan ──► Sandbox ──► Producer ──► Artifact ──► Review Queue
                        ▲             │
                        └── Tools ◄───┘   (tools fabricated on demand,
                                           persisted to the Tool Library)
```

- **Mission** — A user-authored or AI-proposed objective. JSON-ish: `{goal, inputs, success_criteria, domain, deadline, auto_act: false}`.
- **Plan** — A directed graph of steps the planner emits before execution. Reviewable in the UI; rejectable before the sandbox boots.
- **Sandbox** — An ephemeral environment: Docker Compose stack (app + db + queues + mocks), seeded with synthetic or snapshotted data. Lifecycle: `boot → exec → snapshot → teardown`.
- **Producer** — A domain plugin that knows how to turn a Plan into Artifacts of a specific kind: `pr_producer`, `social_post_producer`, `diagnostic_producer`, `clinical_analysis_producer`, `cad_producer`. Each producer declares its required tools and validation checks. This producers should be trained by users to meet the quality/standars that they want. 
- **Tool** — A small, callable unit Noctua can invoke (`run_pytest`, `seed_postgres`, `generate_dxf`, `query_telematics`). Tools can be fabricated mid-mission and cached in the **Tool Library**. I think it's fine to add tools that you can create from a computer terminal, but let it open for any harness. 
- **Artifact** — The deliverable: a PR URL, a `.md` post draft, a PDF report, a DXF file, a Jupyter notebook. Each artifact carries: provenance (mission, plan, sandbox snapshot), validation report, and reviewer affordances (diff, preview, "run again with X"). And those artifacts should also have a way to export them into another tools, but the first is code and docs which is just text. 
- **Review Queue** — Morning inbox. Each item: artifact + one-tap actions (approve / request-change / kill / promote-to-real-world). Also should mention if it needs extra input for the user or if it stopped. 
- **Proactivity Loop** — Noctua's nightly scheduler also *proposes* missions from signal scans (telematics anomalies, error budgets burning, trial data drops). User picks from proposed missions or pre-approves classes of them. Signals are selected by the user and the tool to detect them is also something that AI can help the user build via a sandbox environment. 

---

## 5. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Review UI (web)                        │
│  Mission inbox · Plan preview · Artifact viewer · Approve   │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼─────────────┐   ┌────────────────────────┐
│         Control Plane          │   │     Proactivity Loop   │
│  Missions · Plans · Queue · DB │◄──┤  Signal scanners cron  │
└──────────────────┬─────────────┘   └────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                Mission Runner (orchestrator)                │
│   Planner LLM ─► Step graph ─► Producer selection ─► Exec   │
└────┬────────────────┬───────────────┬───────────────────────┘
     │                │               │
┌────▼─────┐   ┌──────▼─────┐   ┌─────▼───────┐
│ Sandbox  │   │  Tool      │   │  Producers  │
│ manager  │   │  Library   │   │  (plugins)  │
│ (Docker, │   │  + Tool    │   │  pr · post  │
│  compose,│   │  Fabricator│   │  diag · cad │
│  seeds)  │   │            │   │  clinical   │
└──────────┘   └────────────┘   └─────────────┘
```

### Key components

- **Control plane** — Postgres + a small API (Django Ninja). Stores missions, plans, sandbox refs, artifacts, queue state.
- **Mission runner** — A worker process that picks pending missions, asks the planner LLM for a step graph, and executes step-by-step. Each step is either: (a) a tool call, (b) a sandbox action, (c) a producer call.
- **Sandbox manager** — Wraps Docker / Docker Compose. Knows how to: boot a stack from a `noctua.compose.yml` template, seed it (factories / SQL dumps / synthetic generators), exec inside it, snapshot, teardown. Hard timeouts + resource caps.
- **Tool library** — A registry of callable tools with signatures + source. The **tool fabricator** can generate new tools at runtime (LLM-authored Python), run them in a nested sandbox, validate, and persist on success.
- **Producers** — Domain plugins. Each producer implements `plan(mission) → steps` and `finalize(steps) → Artifact`. Producers are independently versioned.
- **Review UI** — Lightweight web app. The morning experience. Diff viewer for PRs, markdown preview for posts, DXF/PDF viewer for diagrams, table/notebook viewer for analyses.

### Data flow for the canonical "overnight PR" mission

1. User tags GitHub issues with `noctua` before bed. 
2. Proactivity loop ingests tagged issues → creates a Mission per issue.
3. Planner LLM produces a Plan: `clone repo → boot sandbox (compose) → seed db → write code → run tests → iterate up to N times → open PR draft`.
4. Sandbox manager boots `docker-compose.test.yml`, runs seed factories.
5. PR producer drives the code edits, runs `pytest`/`vitest` after each change, iterates on failures.
6. On green, producer opens a draft PR with: commit message, test output, sandbox snapshot ID, mission link.
7. Artifact lands in Review Queue. User reviews PR diff + sandbox replay in the morning.

---

## 6. Hackathon scope (MVP)

**One vertical, end-to-end, demoable.** Pick the **overnight PR builder** because it's the most self-contained, has tight feedback loops (tests as ground truth), and is the founder's own pain.

### In scope (must build)
1. **Mission API** — `POST /missions` accepting `{repo_url, issue_url, success_criteria}`. CLI wrapper: `noctua run <issue-url>`.
2. **Sandbox manager (Docker only)** — Spins up a container from a target repo's `Dockerfile` or a fallback Python/Node image. Mounts repo. Runs commands. Captures logs. Teardown on exit.
3. **Planner + executor loop** — Claude-powered. Reads issue, reads repo (limited), proposes 5–15 step plan, executes, retries failing steps up to 3×.
4. **PR producer** — Knows how to: branch, commit, push, open draft PR via `gh`. Embeds a "Noctua report" in PR body: plan, test output, sandbox image ref.
5. **Tool fabricator (one tool only for demo)** — Hardcode the fabrication of a `seed_db` script when planner asks for it. Don't generalize yet.
6. **Review UI (single page)** — `/queue` lists artifacts. Click → PR link + sandbox log + approve/reject buttons. Approve = mark PR ready-for-review on GitHub.
7. **One demo repo** preloaded with 3 ready-to-solve issues for the hackathon demo.

### Out of scope (cut for hackathon)
- Multi-domain producers (social posts, clinical, CAD) — show them as **stubs in the UI**, with one canned example artifact each, to communicate the vision without building them.
- Tool library persistence / reuse across missions — single-mission tools only.
- Proactivity loop / signal scanners — the user manually fires missions.
- Auth, multi-tenancy, billing.
- Snapshotting / replay — only live logs.

### Stretch (only if ahead by Saturday noon)
- A second producer end-to-end: **social post producer** from a `CHANGELOG.md` diff. Cheap, demoable, hammers home the "domain-agnostic spine" message.

### Demo script (3 minutes)
1. Show user tagging two issues + firing `noctua run`.
2. Fast-forward (or pre-record) the sandbox boot + test loop.
3. Open the morning Review Queue: 2 draft PRs waiting, one with a fabricated `seed_db` tool surfaced.
4. Approve one PR → it flips to ready-for-review on GitHub live.
5. Click the "Social posts" tab → show canned artifact. "Same spine, different producer."

---

## 7. Success criteria

**Hackathon:**
- A judge can fire a mission, watch a sandbox boot, and see a real PR open against a real repo with passing tests, in under 4 minutes live.
- The Review UI feels like a *product*, not a debug log.

**Post-hackathon (north star):**
- A user can leave Noctua running unattended for 7 nights and wake to ≥1 mergeable artifact per night across ≥2 domains.
- Tool library has fabricated ≥10 reusable tools.
- Sandbox boot p50 < 60s for cached templates.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Planner generates plausible-but-wrong plans** | Validation gates (tests must pass) + step retry budget; surface failed plans in queue for human salvage. |
| **Sandbox sprawl / cost** | Hard TTL (default 30 min), CPU/mem caps, single-host Docker for hackathon. |
| **Tool fabrication = arbitrary code exec** | Fabricated tools run in nested rootless containers, no network by default, capability allowlist. |
| **"Does too much" pitch problem at demo** | Show ONE vertical fully working; surface other producers as stubs to convey the platform thesis without diluting the demo. |
| **GitHub rate limits / auth** | Personal access token in env, single demo repo, draft PRs only. |
| **LLM cost overnight** | Per-mission token budget; cheap model for planning, expensive only for code generation. |

---

## 9. Open questions

- **Substrate for sandboxes** — Docker on host vs. Firecracker vs. Modal. Hackathon: Docker on host. Production: revisit.
- **Plan format** — JSON DAG vs. Markdown checklist vs. code. Leaning JSON DAG with a Markdown rendering for review.
- **Tool fabrication policy** — Who reviews fabricated tools? For MVP: no review, sandboxed only. Later: tools graduate to library only after human approval.
- **Multi-tenant model** — Personal tool first; team-shared tool library is the obvious v2 wedge.

---

## 10. What this is *not*

- Not Devin / Cursor — those amplify the workday; Noctua extends it overnight.
- Not n8n / Zapier — those run deterministic workflows; Noctua reasons and fabricates.
- Not AutoGPT — that runs forever in a loop; Noctua produces *reviewable artifacts* and stops.
- Not a CI system — CI validates code humans wrote; Noctua writes the code *and* validates it.
