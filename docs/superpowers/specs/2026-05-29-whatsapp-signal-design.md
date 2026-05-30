# WhatsApp signal source — design

**Status:** approved (brainstorm), pending implementation plan
**Date:** 2026-05-29
**Owner:** Hugo

## Summary

Add WhatsApp as a new `Signal` source alongside `sentry`. Inbound messages (text, image, audio, document) hit a webhook, are classified by a small Haiku call into a producer + goal, become a `Mission`, and the user gets an ack on receipt plus the final artifact when the mission terminates.

This is an extension of the existing `Signal` infrastructure (`noctua/core/models.py:83`, `noctua/signals/router.py`, `POST /api/signals/sentry`, `ui/app/signals/`), not a new abstraction.

## Background

Noctua already routes external events to missions through `Signal` rows:
- `Signal(source, external_id, payload, routing_status, mission)` with unique `(source, external_id)` for idempotency.
- `SignalRouter` Protocol with a `decide(payload) -> RouteDecision` method.
- A POST endpoint per source that verifies, dedupes, persists, routes, enqueues.
- A generic UI at `/signals` and `/signals/[id]` that already renders any source.

Currently `SIGNAL_SOURCES = ["sentry", "manual"]`. We add `"whatsapp"`.

Kapso is the WhatsApp Business API provider. Sandbox config (already set up):
- Phone Number ID: `597907523413541`
- Business Account ID: `2102230076919824`
- Config ID: `0797acb8-2962-4f46-896e-7a3bc76f104d`
- Active test number: `525529404910`

## Resolved design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Producer routing | LLM classifier (Haiku) reads message + media kind, picks producer + drafts goal | Most natural UX; user doesn't learn commands. Cheap (Haiku, classification only). |
| Reply UX | Ack on receipt + final artifact when mission terminates | Two outbound messages per mission. User gets feedback before mission starts and the result without opening the UI. |
| Auth | Phone-number allowlist via `NOCTUA_WHATSAPP_ALLOWLIST` env var | Cheap, sufficient for sandbox/demo. Non-allowlisted messages stored as `Signal(routing_status="ignored")` for triage. |
| Audio handling | Download from Kapso → OpenAI Whisper → transcript in goal | Predictable, cheap, debuggable. Adds `OPENAI_API_KEY` dep. |
| Webhook delivery (dev) | User runs `ngrok http 8000` and pastes the public URL when creating the Kapso webhook | Standard hackathon dev loop. |

## Architecture

WhatsApp slots into the existing Signal pattern. New code in three places:

### `noctua/signals/router.py` — add `WhatsAppRouter`
Single Claude Haiku call. System prompt assembled from `Producer.objects.all()` rubrics. The classifier picks `producer_key` and drafts a `goal` via a `route` tool. It does **not** plan or author — that's the planner's job.

```python
class WhatsAppRouter:
    source = "whatsapp"
    def decide(self, payload: dict) -> RouteDecision:
        # Build user message from {kind, text, caption, transcript}
        # Call call_with_cache(CLASSIFIER_MODEL, system=<rubrics>, tools=[route_tool])
        # tool_use → RouteDecision(action="route", **tool_input, inputs={wa_from, media_paths, transcript, kind})
        # else    → RouteDecision(action="ignore", reason=...)
```

Validation in `decide`:
- Producer key must be in `Producer.objects.values_list("key", flat=True)`.
- For `producer_key == "pr"`, the classifier must extract a repo URL from the message. No hidden default repo — fail loud with `action="ignore"`, reason `"pr producer requires repo URL"`.

Anthropic API failure → `RouteDecision(action="ignore", reason="classifier unavailable: <err>")`. Returns 200 to Kapso (no retry). Trade-off: a brief Anthropic outage drops messages; users re-send. Better than infinite Kapso retries during a multi-hour outage.

Model: `claude-haiku-4-5`. Constant in `router.py`: `CLASSIFIER_MODEL = "claude-haiku-4-5"`.

Register in `_ROUTERS = {"sentry": ..., "whatsapp": WhatsAppRouter()}`.

### `noctua/core/api.py` — add `POST /api/signals/whatsapp`
Mirrors `ingest_sentry_signal` (`noctua/core/api.py:213`). ~80 lines including signature check, allowlist gate, media-download branch, and ack call. Schema `WhatsAppWebhookIn` uses `extra=allow` like `SentryWebhookIn` so Kapso fields aren't rejected.

Handler flow detailed in §Data flow below.

### `noctua/whatsapp/` — new module (peer to `signals/`, not nested)
Three files. Module is a peer because both the request handler (inbound: media download) and the Celery worker (outbound: final reply) need it.

- `signature.py` — `verify(raw_body: bytes, header: str, secret: str) -> bool`. HMAC-SHA256 with `hmac.compare_digest`. Header name (`X-Kapso-Signature` or similar) confirmed against `references/webhooks-overview.md` in the integrate-whatsapp skill at implementation time.

- `media.py` — `download(message: dict, signal_id: int) -> dict` returning `{"media_paths": [Path, ...], "transcript": str | None, "kind": "text"|"image"|"audio"|"document"|"video"}`. Fetches via Kapso Meta proxy (`GET /meta/whatsapp/v24.0/{media_id}` returns a signed URL; second GET pulls bytes). Writes to `archive/whatsapp_media/<signal_id>/<media_id>.<ext>`. Idempotent — skips download if the file already exists. For `kind="audio"`, calls `_transcribe(path)` using OpenAI Whisper (`openai.audio.transcriptions.create(model="whisper-1")`).

- `client.py` — `send_text(to: str, body: str) -> None`. Thin `httpx.Client` wrapper around Kapso's `POST /meta/whatsapp/v24.0/{phone_number_id}/messages` with a text body. Logs on failure, never raises. Reads `KAPSO_API_KEY` and `KAPSO_PHONE_NUMBER_ID` from env.

We use raw HTTP (httpx is already a transitive dep) instead of the Kapso JS SDK because we're a Python codebase.

### `noctua/runner/tasks.py` — completion-reply hook
Add to the existing `finally` block in `run_mission`, after `_archive_mission(mission)`:

```python
try:
    _maybe_reply_to_whatsapp(mission)  # no-op if mission.signal is None or source != "whatsapp"
except Exception:
    logger.exception("whatsapp reply failed for mission %s", mission.id)
```

`_maybe_reply_to_whatsapp` lives in `noctua/whatsapp/__init__.py` (or `replies.py` if it grows). Best-effort, same discipline as `_archive_mission`.

Artifact-to-message formatting:
- `social_post` → post body verbatim.
- `clinical_analysis` / `diagnostic` → first 1000 chars of the markdown summary + `(full report at <ui>/queue/<id>)`.
- `pr` → `PR ready for review: <pr_url>`.
- `cad` / `tool` → `<kind> ready at <ui>/queue/<id>`.

### Config additions (`.env.example`)

```
KAPSO_API_KEY=
KAPSO_WEBHOOK_SECRET=
KAPSO_PHONE_NUMBER_ID=597907523413541
NOCTUA_WHATSAPP_ALLOWLIST=525529404910
OPENAI_API_KEY=                 # for Whisper transcription
```

### Model + migration

Add `"whatsapp"` to `SIGNAL_SOURCES` in `noctua/core/models.py:4`. One-liner Django migration (no schema change — just a choices update, but Django still generates one).

### `pyproject.toml`

Add `openai>=1.40` to runtime dependencies.

### UI

Zero changes. The existing `/signals` list and `/signals/[id]` detail page render any source generically.

## Data flow

```
WhatsApp user (525529404910)
  │ sends "draft a launch tweet about overnight AI factories" (+ optional image/audio)
  ▼
Kapso (sandbox phone 597907523413541)
  │ POST <public-url>/api/signals/whatsapp
  │ headers: X-Kapso-Signature: <hmac-sha256>
  │ body:   {event: "whatsapp.message.received", data: {message: {...}}}
  ▼
ingest_whatsapp_signal (noctua/core/api.py)
  │ 1. verify_signature(raw_body, header, KAPSO_WEBHOOK_SECRET)        → 401 on mismatch
  │ 2. extract message.id, from, type, text/media
  │ 3. allowlist check on `from`                                       → Signal(ignored, "not allowlisted"); 200
  │ 4. Signal.objects.get_or_create(source="whatsapp",                  → 200 on dup
  │       external_id=message.id, defaults={title, payload})
  │ 5. for media messages: media.download(message, signal.id)
  │    if audio: media.transcribe()
  │    attach {media_paths, transcript, kind, wa_from} to signal.payload (re-save)
  │ 6. route_signal("whatsapp", signal.payload)
  ▼
WhatsAppRouter.decide (single Haiku call)
  │ → RouteDecision(action="route", producer_key=..., goal=..., inputs={...})
  ▼
ingest_whatsapp_signal (continued)
  │ Mission.objects.create(...)
  │ signal.mission = mission; routing_status="routed"
  │ run_mission.delay(mission.id)
  │ whatsapp.client.send_text(to=wa_from, body="Got it — mission #N queued (producer). ...")  ← ACK
  │ return 201
  ▼
Celery worker — run_mission (existing)
  │ planner → executor → finalize → Artifact(s)
  ▼
finally block addition:
  │ if mission.signal and mission.signal.source == "whatsapp":
  │     whatsapp.client.send_text(to=..., body=_format_artifact_for_whatsapp(...))
```

Idempotency points:
- **Dedup at step 4** — Kapso retries on 5xx. Unique `(source, external_id)` prevents duplicate missions.
- **Media download is idempotent** — files keyed by media id; retried webhooks skip download.

Two intentional placements:
- **Ack happens inside the request handler**, not the worker. Slower webhook response (~300ms for the Kapso send call) but the user gets feedback before the mission starts. If Redis/worker is down, the user still got an ack and the Signal row exists for triage.
- **Media is downloaded inside the handler too**, not the worker. The router needs media context to classify. Webhook latency grows with media size; Kapso media is usually <5MB so this is acceptable.

## Error handling

Webhook handler responses (Kapso retries on 5xx, not on 4xx):

| Failure | Response | Persisted? |
|---|---|---|
| Missing/invalid signature | `401` | No |
| Malformed JSON / missing `message.id` | `200` + `Signal(failed, "missing message.id")` | Yes |
| Allowlist miss | `200` + `Signal(ignored, "from <num> not in allowlist")` | Yes; no ack reply (anti-abuse) |
| Duplicate `message.id` | `200` + existing Signal | Already there |
| Media download fails | `200` + `Signal(failed, "media download: <err>")` | Yes; no automatic retry |
| Whisper transcription fails | Route with empty transcript; `payload["transcription_error"]` set | Yes (graceful degradation) |
| Classifier ignores (no tool_use) | `200` + `Signal(ignored, "classifier declined: <text>")` | Yes; no ack |
| Classifier picks `pr` without repo URL | `200` + `Signal(ignored, "pr producer requires repo URL")` | Yes |
| Mission creation throws (DB error) | `500` | No; Kapso retries |
| Ack send fails (Kapso outbound 5xx) | Log via `logger.exception`. Mission still queued. Return `201`. | Mission row exists |

Worker completion-reply: wrapped in try/except like `_archive_mission`. Never blocks terminal state.

Router failure modes:
1. Anthropic API down → ignore with reason; 200 to Kapso (no retry).
2. Invalid producer key → ignore with validation reason.
3. Tool input validation fails → ignore with the validation error.

Intentional non-defenses:
- **No per-number rate limit.** Allowlist is the gate; allowlisted users are trusted.
- **No retry on Whisper failure.** Fall back to text-only routing. OpenAI SDK already retries internally.

Logging: every branch logs with `mission_id` (where available) and `signal_id` so the existing log-streaming UI shows it.

## Testing

Unit tests (no Docker, no live API; run in every `make test`):

`tests/whatsapp/test_signature.py`
- Known HMAC vector round-trips.
- Tampered body fails.
- Constant-time compare (equivalent strings of different identity accepted).

`tests/whatsapp/test_router.py` — mocks `call_with_cache`.
- Text-only → routes to expected producer with extracted goal.
- Image with caption → image-appropriate producer.
- Audio with transcript → transcript appears in goal.
- Classifier returns `end_turn` → ignore.
- Classifier picks `pr` without repo URL → ignore.
- Invalid producer key → ignore.
- Anthropic raises → ignore.

`tests/whatsapp/test_media.py` — uses `respx` to stub Kapso HTTP.
- Image download → file written, kind="image".
- Audio download + Whisper mocked → transcript returned.
- Whisper raises → transcript=None plus payload error key.
- Idempotency: second `download()` with same media id makes no HTTP call.

`tests/whatsapp/test_api.py` — Ninja test client, full handler. Mocks: `verify_signature` real, `media.download` patched, `WhatsAppRouter.decide` patched, `client.send_text` patched.
- Valid sig + text from allowlisted number → 201, Signal + Mission, ack sent.
- Invalid signature → 401, no row.
- Allowlist miss → 200, `Signal(ignored)`, no Mission, no ack.
- Duplicate message.id → 200, no second Mission.
- Missing message.id → 200, `Signal(failed)`.

`tests/whatsapp/test_reply.py`
- Mission with `signal.source == "whatsapp"` → `client.send_text` called with expected body per artifact kind.
- Mission without WhatsApp signal → no-op.
- `client.send_text` raises → no exception bubbles out of `run_mission`.

Acknowledged coverage gaps (not blocking):
- Real Kapso signature format calibrated at implementation time against the `integrate-whatsapp` skill references.
- Classifier *quality* is not asserted — only the contract. Iterate the system prompt manually.
- Pre-existing `test_create_mission` flake stays; not our concern.

## Out of scope

- WhatsApp templates (outbound notifications outside the 24h session window).
- WhatsApp Flows (native forms).
- Multi-tenant `WhatsAppUser` model with per-user budgets.
- Per-number rate limiting.
- Streaming progress updates back to WhatsApp during mission execution.
- Sending images/audio back as replies (only text outbound for now).
- Receiving from multiple Kapso phone numbers (single `KAPSO_PHONE_NUMBER_ID`).

## Files touched

| File | Change |
|---|---|
| `noctua/core/models.py` | `SIGNAL_SOURCES` adds `"whatsapp"` |
| `noctua/core/migrations/000X_whatsapp_source.py` | New migration (choices update) |
| `noctua/core/api.py` | New `POST /api/signals/whatsapp` handler + `WhatsAppWebhookIn` schema |
| `noctua/signals/router.py` | New `WhatsAppRouter` + register in `_ROUTERS` |
| `noctua/whatsapp/__init__.py` | New — exports `_maybe_reply_to_whatsapp` |
| `noctua/whatsapp/signature.py` | New |
| `noctua/whatsapp/media.py` | New |
| `noctua/whatsapp/client.py` | New |
| `noctua/runner/tasks.py` | Add `_maybe_reply_to_whatsapp` call in `run_mission` finally |
| `pyproject.toml` | Add `openai>=1.40`; add `noctua.whatsapp` to `[tool.setuptools.packages.find]` (already covered by `noctua*` glob) |
| `.env.example` | New keys: `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`, `KAPSO_PHONE_NUMBER_ID`, `NOCTUA_WHATSAPP_ALLOWLIST`, `OPENAI_API_KEY` |
| `tests/whatsapp/` | New test tree (signature, router, media, api, reply) |
