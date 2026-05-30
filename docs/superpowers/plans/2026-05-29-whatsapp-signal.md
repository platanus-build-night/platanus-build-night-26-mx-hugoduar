# WhatsApp Signal Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WhatsApp as a Signal source: inbound Kapso webhook → Haiku classifier picks producer + drafts goal → Mission. Ack on receipt and final-artifact reply when the mission terminates.

**Architecture:** New `noctua/whatsapp/` peer module (signature, media, client, replies). New `WhatsAppRouter` registered in `noctua/signals/router.py`. New `POST /api/signals/whatsapp` endpoint mirroring `ingest_sentry_signal`. Hook into the existing `run_mission` `finally` blocks for the completion reply. UI unchanged — the existing `/signals` views are source-agnostic.

**Tech Stack:** Python 3.12, Django 5, Django Ninja, Celery, Anthropic SDK (Haiku for classification), httpx (Kapso HTTP — both inbound media fetch and outbound replies), respx (test mocking). No new runtime deps.

**Spec:** `docs/superpowers/specs/2026-05-29-whatsapp-signal-design.md`

---

## Conventions

- **Working dir:** `/Users/hugoduar/workspace/platanus` (run all commands from here).
- **Activate venv first:** `source .venv/bin/activate` and `set -a; source .env; set +a` for every shell where you run `make test` or `./manage.py`.
- **Tests:** pytest with `pytest-django`. Use `pytestmark = pytest.mark.django_db` at the top of any test file that hits the ORM. `mocker` fixture is from `pytest-mock` (already a dev dep).
- **DB session in tests:** the conftest fixture at `tests/core/conftest.py` enables `CELERY_TASK_ALWAYS_EAGER=True` for that tree only. For our `tests/whatsapp/` tree we'll patch `run_mission.delay` directly (faster than eager-run and avoids touching Docker).
- **Auth on the new endpoint:** pass `auth=None` to bypass the global `BearerAuth`. Kapso authenticates via `X-Webhook-Signature` header (HMAC-SHA256 hex of `KAPSO_WEBHOOK_SECRET` over raw body) — we verify that ourselves.
- **Commit cadence:** one commit per task. Use the `git commit -F /tmp/<slug>-msg.txt` pattern (HEREDOC-piping has been flaky in this environment).

---

## Task 1: Scaffold module, test tree, env keys, deps

**Files:**
- Create: `noctua/whatsapp/__init__.py`
- Create: `tests/whatsapp/__init__.py`
- Modify: `.env.example`
- Modify: `pyproject.toml`
- Modify: `noctua/settings.py` (to expose the new env vars as Django settings)

- [ ] **Step 1: Create `noctua/whatsapp/__init__.py`** with placeholder no-op:

```python
"""WhatsApp integration module: signature verify, media fetch, outbound replies."""
```

- [ ] **Step 2: Create `tests/whatsapp/__init__.py`** as an empty file (Python package marker):

```python
```

- [ ] **Step 3: Append new env keys to `.env.example`.** First read the file to see its existing format, then add at the bottom:

```
# --- WhatsApp (Kapso) ---
KAPSO_API_KEY=
KAPSO_WEBHOOK_SECRET=
KAPSO_PHONE_NUMBER_ID=597907523413541
KAPSO_API_BASE_URL=https://api.kapso.ai
NOCTUA_WHATSAPP_ALLOWLIST=525529404910
```

- [ ] **Step 4: Add `respx>=0.21` to dev deps in `pyproject.toml`.** Read `pyproject.toml` first to find the `[project.optional-dependencies] dev = [...]` block and append `"respx>=0.21",` to the list.

- [ ] **Step 5: Add Django settings for the new env vars.** Read `noctua/settings.py` to find where other env-driven settings live (e.g. `ANTHROPIC_API_KEY`, `NOCTUA_API_TOKEN`), and add right next to them:

```python
KAPSO_API_KEY = os.getenv("KAPSO_API_KEY", "")
KAPSO_WEBHOOK_SECRET = os.getenv("KAPSO_WEBHOOK_SECRET", "")
KAPSO_PHONE_NUMBER_ID = os.getenv("KAPSO_PHONE_NUMBER_ID", "")
KAPSO_API_BASE_URL = os.getenv("KAPSO_API_BASE_URL", "https://api.kapso.ai")
NOCTUA_WHATSAPP_ALLOWLIST = [
    n.strip() for n in os.getenv("NOCTUA_WHATSAPP_ALLOWLIST", "").split(",") if n.strip()
]
```

(If `import os` is missing at the top of `settings.py`, add it.)

- [ ] **Step 6: Install the new dev dep.**

Run: `pip install -e ".[dev]"`
Expected: completes successfully; `pip show respx` confirms install.

- [ ] **Step 7: Smoke-import to catch typos.**

Run: `python -c "from noctua import whatsapp; import respx; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 8: Commit.**

```bash
git add noctua/whatsapp/__init__.py tests/whatsapp/__init__.py .env.example pyproject.toml noctua/settings.py
cat > /tmp/wa-task1-msg.txt <<'EOF'
feat(whatsapp): scaffold module, env vars, respx dev dep

Empty noctua/whatsapp package + tests/whatsapp tree.
New env vars: KAPSO_API_KEY, KAPSO_WEBHOOK_SECRET, KAPSO_PHONE_NUMBER_ID,
KAPSO_API_BASE_URL, NOCTUA_WHATSAPP_ALLOWLIST.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task1-msg.txt
```

---

## Task 2: HMAC signature verification

**Files:**
- Create: `noctua/whatsapp/signature.py`
- Test: `tests/whatsapp/test_signature.py`

Kapso signs webhook bodies with `X-Webhook-Signature: <hex(HMAC-SHA256(secret, raw_body))>` per `references/webhooks-overview.md`.

- [ ] **Step 1: Write the failing test.** Create `tests/whatsapp/test_signature.py`:

```python
import hashlib
import hmac
from noctua.whatsapp.signature import verify


SECRET = "test-secret"
BODY = b'{"hello": "world"}'
EXPECTED = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()


def test_verify_accepts_matching_signature():
    assert verify(BODY, EXPECTED, SECRET) is True


def test_verify_rejects_tampered_body():
    tampered = BODY + b" "
    assert verify(tampered, EXPECTED, SECRET) is False


def test_verify_rejects_bad_signature():
    assert verify(BODY, "deadbeef", SECRET) is False


def test_verify_rejects_empty_header():
    assert verify(BODY, "", SECRET) is False


def test_verify_rejects_empty_secret():
    assert verify(BODY, EXPECTED, "") is False
```

- [ ] **Step 2: Run test to verify failure.**

Run: `pytest tests/whatsapp/test_signature.py -v`
Expected: FAIL — `ModuleNotFoundError: noctua.whatsapp.signature`.

- [ ] **Step 3: Write minimal implementation.** Create `noctua/whatsapp/signature.py`:

```python
import hashlib
import hmac


def verify(raw_body: bytes, header_value: str, secret: str) -> bool:
    if not header_value or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value)
```

- [ ] **Step 4: Run test to verify pass.**

Run: `pytest tests/whatsapp/test_signature.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit.**

```bash
git add noctua/whatsapp/signature.py tests/whatsapp/test_signature.py
cat > /tmp/wa-task2-msg.txt <<'EOF'
feat(whatsapp): HMAC-SHA256 signature verification

Verifies Kapso's X-Webhook-Signature against raw request body using
compare_digest. Rejects empty headers and empty secrets explicitly.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task2-msg.txt
```

---

## Task 3: Add "whatsapp" to SIGNAL_SOURCES + migration

**Files:**
- Modify: `noctua/core/models.py:4`
- Create: `noctua/core/migrations/000X_signal_whatsapp.py` (X is the next migration number)

- [ ] **Step 1: Find the next migration number.**

Run: `ls noctua/core/migrations/ | grep -E '^00' | sort | tail -3`
Note the highest number prefix (e.g. `0004_connection.py` → next is `0005`).

- [ ] **Step 2: Edit `noctua/core/models.py:4`** to add `"whatsapp"`:

Change:
```python
SIGNAL_SOURCES = [(s, s) for s in ["sentry", "manual"]]
```
To:
```python
SIGNAL_SOURCES = [(s, s) for s in ["sentry", "manual", "whatsapp"]]
```

- [ ] **Step 3: Generate the migration.**

Run: `./manage.py makemigrations core --name signal_whatsapp_source`
Expected: creates `noctua/core/migrations/0005_signal_whatsapp_source.py` (or next number) with a single `AlterField` operation on `Signal.source`.

- [ ] **Step 4: Apply the migration.**

Run: `./manage.py migrate`
Expected: applies the new migration cleanly.

- [ ] **Step 5: Smoke test — create a Signal row with the new source.**

Run:
```bash
./manage.py shell -c "from noctua.core.models import Signal; s = Signal.objects.create(source='whatsapp', external_id='smoke-test', title='x', payload={}); print(s.id, s.source); s.delete()"
```
Expected: prints an id followed by `whatsapp`, no validation error.

- [ ] **Step 6: Run full test suite to catch regressions.**

Run: `make test`
Expected: same baseline as before (the known `test_create_mission` flake is acceptable; nothing else regresses).

- [ ] **Step 7: Commit.**

```bash
git add noctua/core/models.py noctua/core/migrations/0005_signal_whatsapp_source.py
cat > /tmp/wa-task3-msg.txt <<'EOF'
feat(core): add "whatsapp" to SIGNAL_SOURCES

Allows Signal rows with source="whatsapp". One AlterField migration on
Signal.source choices.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task3-msg.txt
```

(Adjust the filename in `git add` if your migration number differs from `0005`.)

---

## Task 4: Media downloader (no transcription — Kapso provides it)

**Files:**
- Create: `noctua/whatsapp/media.py`
- Test: `tests/whatsapp/test_media.py`

Kapso v2 payloads put media at `message.kapso.media_url` (signed Kapso URL) and the transcript for audio at `message.kapso.transcript.text`. We download images/audio/video/documents into `archive/whatsapp_media/<signal_id>/<filename>` with `X-API-Key: $KAPSO_API_KEY`. For text messages we no-op. The function returns a dict the router and producers consume.

- [ ] **Step 1: Write the failing test.** Create `tests/whatsapp/test_media.py`:

```python
import json
import re
from pathlib import Path

import httpx
import pytest
import respx

from noctua.whatsapp.media import download


@pytest.fixture
def settings_kapso(settings, tmp_path):
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"
    settings.NOCTUA_ARCHIVE_DIR = tmp_path
    return settings


def _text_msg():
    return {
        "type": "text",
        "text": {"body": "draft a tweet"},
        "kapso": {"content": "draft a tweet"},
    }


def _image_msg():
    return {
        "type": "image",
        "image": {"id": "media_id_123", "caption": "x-ray hand"},
        "kapso": {
            "content": "x-ray hand Image attached",
            "has_media": True,
            "media_url": "https://api.kapso.test/media/abc.jpg",
            "media_data": {
                "url": "https://api.kapso.test/media/abc.jpg",
                "filename": "xray.jpg",
                "content_type": "image/jpeg",
                "byte_size": 4,
            },
            "message_type_data": {"caption": "x-ray hand"},
        },
    }


def _audio_msg(with_transcript=True):
    msg = {
        "type": "audio",
        "audio": {"id": "media_id_456"},
        "kapso": {
            "has_media": True,
            "media_url": "https://api.kapso.test/media/voice.ogg",
            "media_data": {
                "url": "https://api.kapso.test/media/voice.ogg",
                "filename": "voice.ogg",
                "content_type": "audio/ogg",
                "byte_size": 4,
            },
        },
    }
    if with_transcript:
        msg["kapso"]["transcript"] = {"text": "Hello, I need help with my order"}
    return msg


def test_text_message_no_io(settings_kapso):
    result = download(_text_msg(), signal_id=1)
    assert result == {
        "kind": "text",
        "media_paths": [],
        "transcript": None,
        "caption": "",
    }


@respx.mock
def test_image_download_writes_file(settings_kapso, tmp_path):
    route = respx.get("https://api.kapso.test/media/abc.jpg").mock(
        return_value=httpx.Response(200, content=b"PNG!")
    )
    result = download(_image_msg(), signal_id=42)
    assert result["kind"] == "image"
    assert result["caption"] == "x-ray hand"
    assert len(result["media_paths"]) == 1
    p = Path(result["media_paths"][0])
    assert p.exists()
    assert p.read_bytes() == b"PNG!"
    assert p.parent == tmp_path / "whatsapp_media" / "42"
    assert route.called
    # The auth header is sent
    assert route.calls.last.request.headers.get("X-API-Key") == "k-test"


@respx.mock
def test_audio_with_kapso_transcript(settings_kapso, tmp_path):
    respx.get("https://api.kapso.test/media/voice.ogg").mock(
        return_value=httpx.Response(200, content=b"OGG!")
    )
    result = download(_audio_msg(with_transcript=True), signal_id=7)
    assert result["kind"] == "audio"
    assert result["transcript"] == "Hello, I need help with my order"


@respx.mock
def test_audio_without_transcript_does_not_raise(settings_kapso):
    respx.get("https://api.kapso.test/media/voice.ogg").mock(
        return_value=httpx.Response(200, content=b"OGG!")
    )
    result = download(_audio_msg(with_transcript=False), signal_id=8)
    assert result["transcript"] is None


@respx.mock
def test_download_is_idempotent(settings_kapso, tmp_path):
    route = respx.get("https://api.kapso.test/media/abc.jpg").mock(
        return_value=httpx.Response(200, content=b"PNG!")
    )
    download(_image_msg(), signal_id=99)
    download(_image_msg(), signal_id=99)
    assert route.call_count == 1
```

- [ ] **Step 2: Run test to verify failure.**

Run: `pytest tests/whatsapp/test_media.py -v`
Expected: FAIL — `ModuleNotFoundError: noctua.whatsapp.media`.

- [ ] **Step 3: Write minimal implementation.** Create `noctua/whatsapp/media.py`:

```python
"""Download inbound WhatsApp media from Kapso. No transcription — Kapso provides it."""
from pathlib import Path

import httpx
from django.conf import settings


def download(message: dict, signal_id: int) -> dict:
    """Fetch any media on the message and pluck the Kapso-provided transcript.

    Returns a dict with keys: kind, media_paths (list[str]), transcript (str|None),
    caption (str).
    """
    kind = message.get("type", "text")
    kapso = message.get("kapso") or {}
    media_url = kapso.get("media_url") or ""
    media_data = kapso.get("media_data") or {}
    transcript_block = kapso.get("transcript") or {}
    transcript = transcript_block.get("text") if isinstance(transcript_block, dict) else None
    caption = (kapso.get("message_type_data") or {}).get("caption", "")

    if kind == "text" or not media_url:
        return {"kind": kind, "media_paths": [], "transcript": transcript, "caption": caption}

    dest_dir = Path(settings.NOCTUA_ARCHIVE_DIR) / "whatsapp_media" / str(signal_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = media_data.get("filename") or _filename_from_url(media_url)
    dest = dest_dir / filename

    if not dest.exists():
        with httpx.Client(timeout=30.0) as client:
            r = client.get(media_url, headers={"X-API-Key": settings.KAPSO_API_KEY})
            r.raise_for_status()
            dest.write_bytes(r.content)

    return {
        "kind": kind,
        "media_paths": [str(dest)],
        "transcript": transcript,
        "caption": caption,
    }


def _filename_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1] or "media.bin"
```

- [ ] **Step 4: Run test to verify pass.**

Run: `pytest tests/whatsapp/test_media.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit.**

```bash
git add noctua/whatsapp/media.py tests/whatsapp/test_media.py
cat > /tmp/wa-task4-msg.txt <<'EOF'
feat(whatsapp): inbound media downloader

Pulls bytes from message.kapso.media_url with X-API-Key into
archive/whatsapp_media/<signal_id>/. No-op for text messages. Audio
transcripts come from message.kapso.transcript.text (Kapso transcribes
server-side); no Whisper dep. Idempotent on filename.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task4-msg.txt
```

---

## Task 5: Kapso outbound text client

**Files:**
- Create: `noctua/whatsapp/client.py`
- Test: `tests/whatsapp/test_client.py`

Outbound text via Kapso Meta proxy: `POST /meta/whatsapp/v24.0/{phone_number_id}/messages` with `X-API-Key`. Body shape per Meta spec.

- [ ] **Step 1: Write the failing test.** Create `tests/whatsapp/test_client.py`:

```python
import httpx
import pytest
import respx

from noctua.whatsapp.client import send_text


@pytest.fixture
def settings_kapso(settings):
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"
    settings.KAPSO_PHONE_NUMBER_ID = "597907523413541"
    return settings


@respx.mock
def test_send_text_posts_to_meta_proxy(settings_kapso):
    route = respx.post(
        "https://api.kapso.test/meta/whatsapp/v24.0/597907523413541/messages"
    ).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.x"}]}))

    send_text(to="525529404910", body="Hello")

    assert route.called
    req = route.calls.last.request
    assert req.headers["X-API-Key"] == "k-test"
    import json as _json
    payload = _json.loads(req.content)
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "525529404910"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hello"


@respx.mock
def test_send_text_swallows_http_errors(settings_kapso, caplog):
    respx.post(
        "https://api.kapso.test/meta/whatsapp/v24.0/597907523413541/messages"
    ).mock(return_value=httpx.Response(500, text="boom"))

    # Should not raise — best-effort.
    send_text(to="525529404910", body="Hello")
    # Failure is logged.
    assert any("send_text" in rec.message or "boom" in rec.message for rec in caplog.records)
```

- [ ] **Step 2: Run test to verify failure.**

Run: `pytest tests/whatsapp/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: noctua.whatsapp.client`.

- [ ] **Step 3: Write minimal implementation.** Create `noctua/whatsapp/client.py`:

```python
"""Kapso Meta-proxy outbound client (text-only, best-effort, never raises)."""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def send_text(to: str, body: str) -> None:
    base = settings.KAPSO_API_BASE_URL.rstrip("/")
    phone_id = settings.KAPSO_PHONE_NUMBER_ID
    url = f"{base}/meta/whatsapp/v24.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                url, json=payload, headers={"X-API-Key": settings.KAPSO_API_KEY}
            )
            r.raise_for_status()
    except Exception as exc:
        logger.exception("whatsapp send_text failed: %s", exc)
```

- [ ] **Step 4: Run test to verify pass.**

Run: `pytest tests/whatsapp/test_client.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit.**

```bash
git add noctua/whatsapp/client.py tests/whatsapp/test_client.py
cat > /tmp/wa-task5-msg.txt <<'EOF'
feat(whatsapp): outbound text client (Kapso Meta proxy)

POST {KAPSO_API_BASE_URL}/meta/whatsapp/v24.0/{phone_id}/messages
with X-API-Key. Best-effort: logs and swallows failures so the
calling request handler / worker finally-block never raises.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task5-msg.txt
```

---

## Task 6: WhatsAppRouter (Haiku classifier)

**Files:**
- Modify: `noctua/signals/router.py`
- Test: `tests/whatsapp/test_router.py`

Single Haiku call with all `Producer.rubric_md` text inlined as system context. The classifier must emit a `route` tool call. Goal is drafted from the message text/caption/transcript; producer is one of the registered producer keys.

- [ ] **Step 1: Read existing `router.py`** to remind yourself of the `RouteDecision`/`SignalRouter` interface and `_ROUTERS` registry shape:

Run: `cat noctua/signals/router.py`

- [ ] **Step 2: Write the failing test.** Create `tests/whatsapp/test_router.py`:

```python
from unittest.mock import MagicMock

import pytest

from noctua.core.models import Producer
from noctua.signals.router import route_signal

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _producers(db):
    Producer.objects.get_or_create(
        key="social_post", defaults={"kind": "social_post", "rubric_md": "Drafts short social posts."}
    )
    Producer.objects.get_or_create(
        key="clinical_analysis", defaults={"kind": "analysis", "rubric_md": "Reads medical images and writes a one-paragraph analysis."}
    )
    Producer.objects.get_or_create(
        key="pr", defaults={"kind": "pr", "rubric_md": "Opens a draft PR against a GitHub repo."}
    )


def _patch_anthropic(mocker, tool_input):
    """Make WhatsAppRouter's Claude call return a single tool_use block."""
    fake = MagicMock()
    fake.stop_reason = "tool_use"
    fake.content = [MagicMock(type="tool_use", name="route", input=tool_input)]
    fake.usage = MagicMock(input_tokens=10, output_tokens=10)
    return mocker.patch("noctua.signals.router.call_with_cache", return_value=fake)


def _patch_anthropic_end_turn(mocker, text="off-topic chatter"):
    fake = MagicMock()
    fake.stop_reason = "end_turn"
    block = MagicMock(type="text", text=text)
    fake.content = [block]
    fake.usage = MagicMock(input_tokens=10, output_tokens=5)
    return mocker.patch("noctua.signals.router.call_with_cache", return_value=fake)


def test_text_message_routes_to_social_post(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "social_post",
        "goal": "Draft a launch tweet about overnight AI factories",
    })
    decision = route_signal("whatsapp", {
        "kind": "text",
        "text": "Draft a launch tweet about overnight AI factories",
        "caption": "",
        "transcript": None,
        "wa_from": "525529404910",
        "media_paths": [],
    })
    assert decision.action == "route"
    assert decision.producer_key == "social_post"
    assert "launch tweet" in decision.goal
    assert decision.inputs["wa_from"] == "525529404910"


def test_image_message_routes_to_clinical(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "clinical_analysis",
        "goal": "Analyze the attached x-ray for fractures",
    })
    decision = route_signal("whatsapp", {
        "kind": "image",
        "text": "",
        "caption": "x-ray hand",
        "transcript": None,
        "wa_from": "525529404910",
        "media_paths": ["/tmp/xray.jpg"],
    })
    assert decision.action == "route"
    assert decision.producer_key == "clinical_analysis"
    assert decision.inputs["media_paths"] == ["/tmp/xray.jpg"]


def test_audio_transcript_lands_in_goal(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "social_post",
        "goal": "Draft a tweet: \"Hello, I need help with my order\"",
    })
    decision = route_signal("whatsapp", {
        "kind": "audio",
        "text": "",
        "caption": "",
        "transcript": "Hello, I need help with my order",
        "wa_from": "525529404910",
        "media_paths": ["/tmp/voice.ogg"],
    })
    assert decision.action == "route"
    assert "Hello, I need help with my order" in decision.goal


def test_pr_without_repo_url_is_ignored(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "pr",
        "goal": "Refactor the auth middleware",
    })
    decision = route_signal("whatsapp", {
        "kind": "text",
        "text": "Refactor the auth middleware",
        "caption": "",
        "transcript": None,
        "wa_from": "525529404910",
        "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "repo" in decision.reason.lower()


def test_unknown_producer_key_is_ignored(mocker):
    _patch_anthropic(mocker, {"producer_key": "gibberish", "goal": "x"})
    decision = route_signal("whatsapp", {
        "kind": "text", "text": "hello", "caption": "",
        "transcript": None, "wa_from": "1", "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "unknown producer" in decision.reason.lower()


def test_classifier_end_turn_is_ignored(mocker):
    _patch_anthropic_end_turn(mocker, text="this looks like spam")
    decision = route_signal("whatsapp", {
        "kind": "text", "text": "lol", "caption": "",
        "transcript": None, "wa_from": "1", "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "declined" in decision.reason.lower()


def test_anthropic_failure_is_ignored(mocker):
    mocker.patch("noctua.signals.router.call_with_cache", side_effect=RuntimeError("boom"))
    decision = route_signal("whatsapp", {
        "kind": "text", "text": "hi", "caption": "",
        "transcript": None, "wa_from": "1", "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "classifier unavailable" in decision.reason.lower()
```

- [ ] **Step 3: Run test to verify failure.**

Run: `pytest tests/whatsapp/test_router.py -v`
Expected: FAIL — `route_signal("whatsapp", ...)` returns `action="ignore"` with reason `"no router for source 'whatsapp'"` (the existing default).

- [ ] **Step 4: Implement `WhatsAppRouter`.** Edit `noctua/signals/router.py`. Add the imports at the top (next to the existing `dataclass`/`Protocol` imports):

```python
import logging
import re
from noctua.core.models import Producer
from noctua.runner.llm import call_with_cache

logger = logging.getLogger(__name__)

CLASSIFIER_MODEL = "claude-haiku-4-5"

_REPO_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?")
```

Then add the router class **above** the `_ROUTERS` dict:

```python
class WhatsAppRouter:
    """Classify an inbound WhatsApp message into producer + goal via Haiku."""

    source = "whatsapp"

    def decide(self, payload: dict) -> RouteDecision:
        valid_keys = set(Producer.objects.values_list("key", flat=True))
        if not valid_keys:
            return RouteDecision(action="ignore", reason="no producers registered")

        system = self._build_system_prompt(valid_keys)
        user = self._build_user_message(payload)
        tools = [{
            "name": "route",
            "description": "Pick a producer and draft the mission goal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "producer_key": {"type": "string", "enum": sorted(valid_keys)},
                    "goal": {"type": "string"},
                },
                "required": ["producer_key", "goal"],
            },
        }]

        try:
            resp = call_with_cache(
                messages=[{"role": "user", "content": user}],
                system=system,
                model=CLASSIFIER_MODEL,
                max_tokens=1024,
                tools=tools,
            )
        except Exception as exc:
            logger.warning("whatsapp classifier call failed: %s", exc)
            return RouteDecision(
                action="ignore",
                reason=f"classifier unavailable: {exc}",
            )

        if resp.stop_reason != "tool_use":
            text = ""
            for block in resp.content or []:
                if getattr(block, "type", None) == "text":
                    text = block.text or ""
                    break
            return RouteDecision(
                action="ignore",
                reason=f"classifier declined: {text[:200]}",
            )

        tool_input = {}
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "route":
                tool_input = block.input
                break

        producer_key = tool_input.get("producer_key", "")
        goal = tool_input.get("goal", "")
        if producer_key not in valid_keys:
            return RouteDecision(
                action="ignore",
                reason=f"unknown producer {producer_key!r}",
            )
        if not goal.strip():
            return RouteDecision(
                action="ignore",
                reason="classifier returned empty goal",
            )

        repo_url = ""
        if producer_key == "pr":
            text_blob = " ".join([payload.get("text", ""), payload.get("caption", ""), payload.get("transcript") or ""])
            m = _REPO_RE.search(text_blob)
            if not m:
                return RouteDecision(
                    action="ignore",
                    reason="pr producer requires a GitHub repo URL in the message",
                )
            repo_url = m.group(0)

        inputs = {
            "wa_from": payload.get("wa_from", ""),
            "media_paths": payload.get("media_paths", []),
            "transcript": payload.get("transcript"),
            "kind": payload.get("kind", "text"),
        }

        return RouteDecision(
            action="route",
            reason="whatsapp classifier",
            producer_key=producer_key,
            goal=goal,
            repo_url=repo_url,
            inputs=inputs,
        )

    def _build_system_prompt(self, valid_keys: set[str]) -> str:
        lines = [
            "You route inbound WhatsApp messages to one of these producers.",
            "Each producer accepts a free-text 'goal'. Use the most appropriate producer.",
            "If the message is off-topic chatter (greetings, jokes, spam), respond with text instead of calling the route tool.",
            "",
            "Producers:",
        ]
        for p in Producer.objects.filter(key__in=valid_keys).order_by("key"):
            rubric = (p.rubric_md or "(no rubric)").strip().split("\n")[0]
            lines.append(f"- {p.key}: {rubric}")
        lines.append("")
        lines.append("Use the 'route' tool with the chosen producer_key and a clear goal.")
        return "\n".join(lines)

    def _build_user_message(self, payload: dict) -> str:
        parts = [f"kind: {payload.get('kind', 'text')}"]
        if payload.get("text"):
            parts.append(f"text: {payload['text']}")
        if payload.get("caption"):
            parts.append(f"caption: {payload['caption']}")
        if payload.get("transcript"):
            parts.append(f"transcript: {payload['transcript']}")
        if payload.get("media_paths"):
            parts.append(f"media_count: {len(payload['media_paths'])}")
        return "\n".join(parts)
```

Then register it by changing:

```python
_ROUTERS: dict[str, SignalRouter] = {
    "sentry": SentryRouter(),
}
```

To:

```python
_ROUTERS: dict[str, SignalRouter] = {
    "sentry": SentryRouter(),
    "whatsapp": WhatsAppRouter(),
}
```

- [ ] **Step 5: Run test to verify pass.**

Run: `pytest tests/whatsapp/test_router.py -v`
Expected: 7 passed.

- [ ] **Step 6: Re-run sentry router tests to confirm no regression.**

Run: `pytest tests/signals/ -v`
Expected: same baseline as before.

- [ ] **Step 7: Commit.**

```bash
git add noctua/signals/router.py tests/whatsapp/test_router.py
cat > /tmp/wa-task6-msg.txt <<'EOF'
feat(signals): WhatsApp router (Haiku classifier)

Single Haiku call with all Producer rubrics inlined as system prompt;
classifier emits a `route` tool call with producer_key + goal. Validates
producer key, refuses `pr` without a GitHub repo URL in the message,
treats Anthropic failures / end_turn as ignore.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task6-msg.txt
```

---

## Task 7: `POST /api/signals/whatsapp` endpoint

**Files:**
- Modify: `noctua/core/api.py`
- Test: `tests/whatsapp/test_api.py`

Mirrors `ingest_sentry_signal` but adds: signature verify, allowlist check (using `conversation.phone_number` from the Kapso payload), media download, ack reply. Bypasses `BearerAuth` via `auth=None` because Kapso authenticates via `X-Webhook-Signature`.

- [ ] **Step 1: Write the failing test.** Create `tests/whatsapp/test_api.py`:

```python
import hashlib
import hmac
import json
from unittest.mock import MagicMock

import pytest
from django.test import Client

from noctua.core.models import Mission, Producer, Signal
from noctua.signals.router import RouteDecision

pytestmark = pytest.mark.django_db

SECRET = "wh-secret"
ALLOW = "525529404910"


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.NOCTUA_API_TOKEN = "tt"
    settings.KAPSO_WEBHOOK_SECRET = SECRET
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_PHONE_NUMBER_ID = "597907523413541"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"
    settings.NOCTUA_WHATSAPP_ALLOWLIST = [ALLOW]
    settings.NOCTUA_ARCHIVE_DIR = tmp_path
    settings.CELERY_TASK_ALWAYS_EAGER = False


@pytest.fixture(autouse=True)
def _producers():
    Producer.objects.get_or_create(
        key="social_post", defaults={"kind": "social_post", "rubric_md": "x"}
    )


@pytest.fixture(autouse=True)
def _patch_externals(mocker):
    """Stub out everything that would do real I/O: Anthropic, Kapso outbound, run_mission.delay."""
    mocker.patch(
        "noctua.signals.router.route_signal",
        return_value=RouteDecision(
            action="route", producer_key="social_post",
            goal="Draft a tweet", repo_url="", inputs={"wa_from": ALLOW},
        ),
    )
    mocker.patch("noctua.runner.tasks.run_mission.delay")
    mocker.patch("noctua.whatsapp.client.send_text")
    # Media download — return text-message shape unless overridden per test
    mocker.patch(
        "noctua.whatsapp.media.download",
        return_value={"kind": "text", "media_paths": [], "transcript": None, "caption": ""},
    )


def _payload(message_id="wamid.1", from_number=ALLOW, body="draft a tweet"):
    return {
        "message": {
            "id": message_id,
            "type": "text",
            "text": {"body": body},
            "kapso": {"content": body, "direction": "inbound"},
        },
        "conversation": {
            "id": "conv_1",
            "phone_number": from_number,
            "phone_number_id": "597907523413541",
        },
        "phone_number_id": "597907523413541",
    }


def _sig(body_bytes: bytes) -> str:
    return hmac.new(SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()


def _post(body):
    raw = json.dumps(body).encode()
    return Client().post(
        "/api/signals/whatsapp",
        data=raw,
        content_type="application/json",
        HTTP_X_WEBHOOK_SIGNATURE=_sig(raw),
    )


def test_valid_request_creates_signal_and_mission():
    r = _post(_payload())
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"]
    assert Signal.objects.filter(source="whatsapp").count() == 1
    assert Mission.objects.filter(id=body["mission_id"]).exists()


def test_invalid_signature_returns_401():
    raw = json.dumps(_payload()).encode()
    r = Client().post(
        "/api/signals/whatsapp",
        data=raw,
        content_type="application/json",
        HTTP_X_WEBHOOK_SIGNATURE="deadbeef",
    )
    assert r.status_code == 401
    assert Signal.objects.count() == 0


def test_allowlist_miss_is_ignored_no_mission_no_ack(mocker):
    spy_ack = mocker.patch("noctua.whatsapp.client.send_text")
    r = _post(_payload(from_number="9999999999"))
    assert r.status_code == 201
    assert r.json()["routing_status"] == "ignored"
    assert "allowlist" in r.json()["routing_reason"].lower()
    assert Mission.objects.count() == 0
    spy_ack.assert_not_called()


def test_duplicate_message_id_returns_200_and_no_second_mission(mocker):
    spy_delay = mocker.patch("noctua.runner.tasks.run_mission.delay")
    r1 = _post(_payload(message_id="dup-1"))
    r2 = _post(_payload(message_id="dup-1"))
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert Signal.objects.count() == 1
    assert Mission.objects.count() == 1
    spy_delay.assert_called_once()


def test_missing_message_id_yields_failed_signal():
    bad = _payload()
    del bad["message"]["id"]
    r = _post(bad)
    assert r.status_code == 201
    assert r.json()["routing_status"] == "failed"
    assert "message.id" in r.json()["routing_reason"]
    assert Mission.objects.count() == 0


def test_ack_is_sent_on_routed_signal(mocker):
    spy_ack = mocker.patch("noctua.whatsapp.client.send_text")
    r = _post(_payload())
    assert r.status_code == 201
    spy_ack.assert_called_once()
    args, kwargs = spy_ack.call_args
    # to + body, either positional or kw
    call = {**dict(zip(("to", "body"), args)), **kwargs}
    assert call["to"] == ALLOW
    assert "queued" in call["body"].lower()
```

- [ ] **Step 2: Run test to verify failure.**

Run: `pytest tests/whatsapp/test_api.py -v`
Expected: FAIL — 404 on `/api/signals/whatsapp` (endpoint doesn't exist yet).

- [ ] **Step 3: Implement the endpoint.** Edit `noctua/core/api.py`. Add this block right after `ingest_sentry_signal` (after the function ends, before `@api.get("/signals", ...)`):

```python
class WhatsAppWebhookIn(Schema):
    """Loose wrapper so Ninja accepts the JSON body; we re-parse raw bytes."""
    message: dict = {}
    conversation: dict = {}

    class Config:
        extra = "allow"


@api.post("/signals/whatsapp", response={200: SignalOut, 201: SignalOut, 401: dict}, auth=None)
def ingest_whatsapp_signal(request, body: WhatsAppWebhookIn):
    """Kapso WhatsApp webhook intake (phone-number scope, v2 payloads)."""
    import json as _json
    import logging
    from django.conf import settings
    from noctua.core.models import Signal, Mission
    from noctua.signals.router import route_signal
    from noctua.whatsapp import signature as wa_sig, media as wa_media, client as wa_client

    logger = logging.getLogger(__name__)

    raw = request.body
    sig = request.headers.get("X-Webhook-Signature", "")
    if not wa_sig.verify(raw, sig, settings.KAPSO_WEBHOOK_SECRET):
        return 401, {"error": "invalid signature"}

    try:
        payload = _json.loads(raw)
    except Exception:
        payload = body.dict()

    message = payload.get("message") or {}
    conversation = payload.get("conversation") or {}
    external_id = str(message.get("id") or "")
    wa_from = conversation.get("phone_number") or ""
    if wa_from.startswith("+"):
        wa_from = wa_from[1:]
    title = (message.get("kapso") or {}).get("content") or message.get("type") or "(no title)"

    if not external_id:
        signal = Signal.objects.create(
            source="whatsapp", external_id=f"missing:{_short_hash(payload)}",
            title=title[:512], payload=payload,
            routing_status="failed", routing_reason="missing message.id",
        )
        return 201, _serialize_signal(signal)

    if wa_from not in settings.NOCTUA_WHATSAPP_ALLOWLIST:
        signal, created = Signal.objects.get_or_create(
            source="whatsapp", external_id=external_id,
            defaults={"title": title[:512], "payload": payload,
                      "routing_status": "ignored",
                      "routing_reason": f"from {wa_from!r} not in allowlist"},
        )
        return (201 if created else 200), _serialize_signal(signal)

    signal, created = Signal.objects.get_or_create(
        source="whatsapp", external_id=external_id,
        defaults={"title": title[:512], "payload": payload},
    )
    if not created:
        return 200, _serialize_signal(signal)

    try:
        media_info = wa_media.download(message, signal.id)
    except Exception as exc:
        signal.routing_status = "failed"
        signal.routing_reason = f"media download: {exc}"
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    router_payload = {
        **media_info,
        "text": (message.get("text") or {}).get("body", ""),
        "wa_from": wa_from,
    }
    signal.payload = {**payload, "router_input": router_payload}
    signal.save(update_fields=["payload"])

    decision = route_signal("whatsapp", router_payload)
    if decision.action == "ignore":
        signal.routing_status = "ignored"
        signal.routing_reason = decision.reason
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    from noctua.runner.tasks import run_mission
    mission = Mission.objects.create(
        goal=decision.goal,
        producer_key=decision.producer_key,
        repo_url=decision.repo_url,
        issue_url=decision.issue_url,
        inputs=decision.inputs or {},
        budget=DEFAULT_BUDGET,
    )
    signal.mission = mission
    signal.routing_status = "routed"
    signal.routing_reason = decision.reason
    signal.save(update_fields=["mission", "routing_status", "routing_reason"])
    run_mission.delay(mission.id)

    try:
        wa_client.send_text(
            to=wa_from,
            body=f"Got it — mission #{mission.id} queued ({decision.producer_key}). I'll send the result when ready.",
        )
    except Exception:
        logger.exception("whatsapp ack send failed for mission %s", mission.id)

    return 201, _serialize_signal(signal)
```

- [ ] **Step 4: Run test to verify pass.**

Run: `pytest tests/whatsapp/test_api.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the entire signals tree to confirm no Sentry regression.**

Run: `pytest tests/signals/ tests/whatsapp/ -v`
Expected: all green (Sentry tests still pass; WhatsApp tests pass).

- [ ] **Step 6: Commit.**

```bash
git add noctua/core/api.py tests/whatsapp/test_api.py
cat > /tmp/wa-task7-msg.txt <<'EOF'
feat(api): POST /api/signals/whatsapp

Kapso webhook intake (phone-number scope, v2 payload). Verifies
X-Webhook-Signature, bypasses BearerAuth via auth=None, gates on
NOCTUA_WHATSAPP_ALLOWLIST, downloads media, routes through the
Haiku classifier, creates a Mission, enqueues run_mission, and sends
an ack message back via Kapso.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task7-msg.txt
```

---

## Task 8: Completion-reply hook in `run_mission`

**Files:**
- Modify: `noctua/whatsapp/__init__.py`
- Modify: `noctua/runner/tasks.py` (three `finally` blocks)
- Test: `tests/whatsapp/test_reply.py`

Reply to the WhatsApp sender with the artifact when a mission terminates. Best-effort like `archive_mission`.

- [ ] **Step 1: Write the failing test.** Create `tests/whatsapp/test_reply.py`:

```python
import pytest

from noctua.core.models import Artifact, Mission, Signal
from noctua.whatsapp import maybe_reply_to_whatsapp

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_PHONE_NUMBER_ID = "597907523413541"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"


def _mission_with_signal(producer="social_post", wa_from="525529404910"):
    m = Mission.objects.create(goal="x", producer_key=producer, state="succeeded")
    Signal.objects.create(
        source="whatsapp", external_id=f"ext-{m.id}", title="t",
        payload={"router_input": {"wa_from": wa_from}}, mission=m,
        routing_status="routed",
    )
    return m


def test_no_signal_is_noop(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = Mission.objects.create(goal="x", producer_key="social_post", state="succeeded")
    maybe_reply_to_whatsapp(m)
    spy.assert_not_called()


def test_non_whatsapp_signal_is_noop(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = Mission.objects.create(goal="x", producer_key="social_post", state="succeeded")
    Signal.objects.create(source="sentry", external_id="s-1", title="t",
                          payload={}, mission=m, routing_status="routed")
    maybe_reply_to_whatsapp(m)
    spy.assert_not_called()


def test_social_post_sends_post_body_verbatim(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = _mission_with_signal(producer="social_post")
    Artifact.objects.create(
        mission=m, producer_key="social_post", kind="social_post",
        uri="", preview={"body": "Hello world from Noctua"},
    )
    maybe_reply_to_whatsapp(m)
    spy.assert_called_once()
    assert spy.call_args.kwargs.get("to") or spy.call_args.args[0] == "525529404910"
    body = spy.call_args.kwargs.get("body") or spy.call_args.args[1]
    assert "Hello world from Noctua" in body


def test_pr_artifact_sends_url(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = _mission_with_signal(producer="pr")
    Artifact.objects.create(
        mission=m, producer_key="pr", kind="pr",
        uri="https://github.com/me/repo/pull/42", preview={},
    )
    maybe_reply_to_whatsapp(m)
    spy.assert_called_once()
    body = spy.call_args.kwargs.get("body") or spy.call_args.args[1]
    assert "https://github.com/me/repo/pull/42" in body


def test_send_text_failure_does_not_raise(mocker):
    mocker.patch("noctua.whatsapp.client.send_text", side_effect=RuntimeError("boom"))
    m = _mission_with_signal()
    Artifact.objects.create(
        mission=m, producer_key="social_post", kind="social_post",
        uri="", preview={"body": "hi"},
    )
    # Must not raise.
    maybe_reply_to_whatsapp(m)


def test_mission_with_no_artifact_is_noop(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = _mission_with_signal()
    maybe_reply_to_whatsapp(m)
    spy.assert_not_called()
```

- [ ] **Step 2: Run test to verify failure.**

Run: `pytest tests/whatsapp/test_reply.py -v`
Expected: FAIL — `ImportError: cannot import name 'maybe_reply_to_whatsapp' from 'noctua.whatsapp'`.

- [ ] **Step 3: Implement `maybe_reply_to_whatsapp`.** Replace the contents of `noctua/whatsapp/__init__.py`:

```python
"""WhatsApp integration: signature verify, media fetch, outbound replies."""
import logging

from django.conf import settings as _settings  # noqa: F401  (kept for symmetry/imports)

from noctua.whatsapp import client as _client

logger = logging.getLogger(__name__)


def maybe_reply_to_whatsapp(mission) -> None:
    """If this mission was triggered by a WhatsApp signal, send the artifact back.

    Best-effort: any failure is logged and swallowed. Callers should still wrap
    in try/except so a stray import/AttributeError can't bubble up.
    """
    signal = _get_whatsapp_signal(mission)
    if signal is None:
        return

    wa_from = ((signal.payload or {}).get("router_input") or {}).get("wa_from", "")
    if not wa_from:
        logger.warning("whatsapp reply skipped: no wa_from for mission %s", mission.id)
        return

    artifact = mission.artifacts.order_by("-id").first()
    if artifact is None:
        return

    body = _format_artifact(artifact)
    _client.send_text(to=wa_from, body=body)


def _get_whatsapp_signal(mission):
    try:
        sig = mission.signal  # OneToOneField reverse accessor
    except Exception:
        return None
    if sig is None or sig.source != "whatsapp":
        return None
    return sig


def _format_artifact(artifact) -> str:
    kind = artifact.kind
    preview = artifact.preview or {}
    if kind == "social_post":
        return preview.get("body") or "(empty post)"
    if kind == "pr":
        return f"PR ready for review: {artifact.uri or '(no url)'}"
    if kind in ("analysis", "diagnostic"):
        summary = preview.get("summary") or preview.get("body") or "(empty analysis)"
        return f"{summary[:1000]}"
    if kind in ("cad", "tool"):
        return f"{kind} ready at /queue/{artifact.id}"
    return f"Artifact #{artifact.id} ({kind}) ready at /queue/{artifact.id}"
```

- [ ] **Step 4: Run reply tests in isolation.**

Run: `pytest tests/whatsapp/test_reply.py -v`
Expected: 6 passed.

- [ ] **Step 5: Wire the hook into all three `run_mission` `finally` blocks.** Edit `noctua/runner/tasks.py`. There are three `finally:` blocks (one per producer branch). In each, find the existing `archive_mission` try/except and add right after it:

```python
            try:
                from noctua.whatsapp import maybe_reply_to_whatsapp
                maybe_reply_to_whatsapp(m)
            except Exception:
                pass
```

Concretely, after this existing block (which appears three times):

```python
            from noctua.runner.archive import archive_mission
            try:
                archive_mission(m.id)
            except Exception:
                pass
```

Add the new try/except in the same `finally` block.

- [ ] **Step 6: Run the runner tests to confirm no regression.**

Run: `pytest tests/runner/ tests/whatsapp/test_reply.py -v`
Expected: same baseline as before; WhatsApp reply tests still green.

- [ ] **Step 7: Run the full suite once.**

Run: `make test`
Expected: same baseline. The known `tests/core/test_mission_api.py::test_create_mission` flake is acceptable; nothing else regresses.

- [ ] **Step 8: Commit.**

```bash
git add noctua/whatsapp/__init__.py noctua/runner/tasks.py tests/whatsapp/test_reply.py
cat > /tmp/wa-task8-msg.txt <<'EOF'
feat(whatsapp): completion-reply hook in run_mission

maybe_reply_to_whatsapp(mission) lives in noctua/whatsapp/__init__.py
and is called from all three run_mission finally blocks (content-only,
external-tools, and full PR lifecycle). Best-effort: failures are
swallowed so the worker never dies because the user's phone is off.

Per-kind formatters: social_post (verbatim body), pr (PR URL),
analysis/diagnostic (first 1000 chars of summary), cad/tool (queue link).

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
git commit -F /tmp/wa-task8-msg.txt
```

---

## Done — sanity sweep

- [ ] **Step 1: One last clean test run.**

Run: `make test`
Expected: same baseline as the start of this plan.

- [ ] **Step 2: Verify the module surface.**

Run: `python -c "from noctua.whatsapp import maybe_reply_to_whatsapp; from noctua.whatsapp import signature, media, client; from noctua.signals.router import route_signal, WhatsAppRouter; print('imports OK')"`
Expected: prints `imports OK`.

- [ ] **Step 3: Confirm the endpoint shows up in the OpenAPI schema.**

Run: `./manage.py shell -c "from noctua.core.api import api; print(sorted(p for p in api.urls_namespace_map.get(api.urls_namespace, {}).keys()) if False else [r.url_name for r in api.urls[0]])" 2>/dev/null | grep -i whatsapp || ./manage.py shell -c "from noctua.core.api import api; import json; print(json.dumps(list(sorted(api.get_openapi_schema().get('paths', {}).keys()))))" | grep -i whatsapp`
Expected: `/signals/whatsapp` appears in the output. (If the long inline doesn't work, just check by hitting the endpoint with curl after `make api`.)

Live validation (running ngrok + Kapso webhook creation + real message round-trip) is **out of scope of this plan per the user's request** — you'll run it yourself.

---

## Self-Review Notes

Spec coverage:
- §Architecture covered by tasks 1, 6, 7, 8.
- §Data flow covered by task 7.
- §Error handling covered by tasks 6 (router branches) and 7 (handler branches).
- §Testing covered by tests in tasks 2, 4, 5, 6, 7, 8.
- §Out of scope respected (no templates, Flows, multi-tenant, rate limit, streaming).
- §Files touched — every entry maps to a task.

Placeholder scan: no TBDs, no "implement later", every test/impl block contains the actual code.

Type consistency: `RouteDecision` shape matches between router emit and handler consume (`producer_key`, `goal`, `repo_url`, `issue_url`, `inputs`); `download()` return shape matches between media tests and router payload shape; `maybe_reply_to_whatsapp` name matches between `__init__.py` export, test imports, and runner wiring.
