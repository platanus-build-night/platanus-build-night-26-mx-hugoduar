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
