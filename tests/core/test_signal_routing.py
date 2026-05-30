"""Tests: preflight toolkit check applied at signal-ingestion paths.

Verifies that every signal endpoint (sentry, mock, feature_request, whatsapp)
refuses to create a Mission when the routed producer has required_toolkits and
none of them are actively connected — and that the Signal is marked
routing_status="failed" with a routing_reason that names the missing toolkits.
Also verifies the happy path: when a matching Connection is active, the mission
IS created.

Design:
  - "fails" tests: patch ``noctua.core.api._check_required_toolkits`` to return a
    list of toolkits.  This tests endpoint control-flow in isolation from the
    registry and DB, and avoids ordering issues with cache warm-up.
  - "creates_mission" tests: no fake producers needed.  The real ``social_post``
    producer already declares ``required_toolkits = ["LINKEDIN", "TWITTER",
    "BLUESKY"]``; we just create an active Connection row.  For ``pr``-based
    endpoints (sentry, feature_request) the real ``pr`` producer has no
    required_toolkits so the check is a no-op and the mission is always created.
  - ``run_mission.delay`` is wrapped in ``transaction.on_commit`` in the API, so it
    only fires after the DB transaction commits.  In tests the transaction is
    rolled back, so we use ``django_capture_on_commit_callbacks`` to fire
    on_commit hooks explicitly and capture the delay call.
"""
import json
import pytest
from unittest.mock import patch
from django.test import Client
from noctua.core.models import Mission, Signal, Connection

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def base_settings(settings):
    settings.NOCTUA_API_TOKEN = "tt"
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.CELERY_TASK_EAGER_PROPAGATES = False


def _auth():
    return {"HTTP_AUTHORIZATION": "Bearer tt"}


# ---------------------------------------------------------------------------
# Sentry signal endpoint
# ---------------------------------------------------------------------------

def _sentry_payload(issue_id="99", level="error", slug="noctua-demo-app"):
    return {
        "action": "created",
        "data": {"issue": {
            "id": issue_id,
            "title": "KeyError: 'user'",
            "level": level,
            "culprit": "src/app.py in view",
            "project": {"slug": slug, "name": slug},
            "permalink": f"https://sentry.example/{slug}/issues/{issue_id}/",
        }},
    }


def test_sentry_signal_fails_when_producer_missing_required_toolkit():
    """When _check_required_toolkits finds the routed producer has missing
    connections, the sentry endpoint marks the signal failed and skips mission creation."""
    with patch("noctua.core.api._check_required_toolkits", return_value=["GITHUB"]):
        c = Client()
        r = c.post(
            "/api/signals/sentry",
            data=json.dumps(_sentry_payload()),
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "failed"
    assert "GITHUB" in body["routing_reason"]
    assert body["mission_id"] is None
    assert Mission.objects.count() == 0


def test_sentry_signal_creates_mission_when_toolkit_connected(
    mocker, django_capture_on_commit_callbacks
):
    """pr producer has no required_toolkits so the mission is always created
    when sentry routes to it (the standard sentry→pr flow)."""
    spy = mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(
            "/api/signals/sentry",
            data=json.dumps(_sentry_payload(issue_id="100")),
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"] is not None
    assert Mission.objects.count() == 1
    spy.assert_called_once()


# ---------------------------------------------------------------------------
# Mock signal endpoint
# ---------------------------------------------------------------------------

def test_mock_signal_fails_when_social_post_missing_required_toolkit():
    """social_post routed via mock with no active connection → signal failed."""
    with patch("noctua.core.api._check_required_toolkits", return_value=["LINKEDIN", "TWITTER"]):
        c = Client()
        r = c.post(
            "/api/signals/mock",
            data=json.dumps({
                "kind": "social",
                "external_id": "mock-sp-1",
                "title": "launch tweet",
                "goal": "Tweet about our product launch",
            }),
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "failed"
    # routing_reason should name at least one of the missing toolkits
    for tk in ("LINKEDIN", "TWITTER"):
        if tk in body["routing_reason"]:
            break
    else:
        pytest.fail(f"Expected toolkit name in routing_reason, got: {body['routing_reason']!r}")
    assert body["mission_id"] is None
    assert Mission.objects.count() == 0


def test_mock_signal_creates_mission_when_one_toolkit_active(
    mocker, django_capture_on_commit_callbacks
):
    """Any one active required toolkit unblocks the mission creation.

    Uses the real social_post producer (required_toolkits = LINKEDIN/TWITTER/
    BLUESKY) and satisfies the check by creating one active Connection.
    """
    # The real social_post producer requires LINKEDIN, TWITTER, or BLUESKY.
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c-li-1")

    spy = mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(
            "/api/signals/mock",
            data=json.dumps({
                "kind": "social",
                "external_id": "mock-sp-2",
                "title": "launch tweet",
                "goal": "Tweet about our product launch",
            }),
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"] is not None
    assert Mission.objects.count() == 1
    spy.assert_called_once()


# ---------------------------------------------------------------------------
# Feature-request signal endpoint
# ---------------------------------------------------------------------------

def test_feature_request_fails_when_pr_producer_missing_toolkit():
    """feature_request → pr; if pr requires a toolkit that is absent, fail."""
    with patch("noctua.core.api._check_required_toolkits", return_value=["GITHUB"]):
        c = Client()
        r = c.post(
            "/api/signals/feature_request",
            data=json.dumps({"goal": "Add a /healthz endpoint"}),
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "failed"
    assert "GITHUB" in body["routing_reason"]
    assert body["mission_id"] is None
    assert Mission.objects.count() == 0


def test_feature_request_creates_mission_when_toolkit_connected(
    mocker, django_capture_on_commit_callbacks
):
    """pr producer has no required_toolkits; feature_request always creates mission."""
    spy = mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(
            "/api/signals/feature_request",
            data=json.dumps({"goal": "Add a /healthz endpoint"}),
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"] is not None
    assert Mission.objects.count() == 1
    spy.assert_called_once()


# ---------------------------------------------------------------------------
# WhatsApp signal endpoint
# ---------------------------------------------------------------------------

def _wa_payload(msg_id="wa-msg-1", phone="+15551234567", text="tweet about our launch"):
    return {
        "message": {
            "id": msg_id,
            "type": "text",
            "text": {"body": text},
            "kapso": {"content": text},
        },
        "conversation": {"phone_number": phone},
    }


@pytest.fixture
def wa_settings(settings):
    settings.KAPSO_WEBHOOK_SECRET = "testsecret"
    settings.NOCTUA_WHATSAPP_ALLOWLIST = ["15551234567"]


def _wa_auth_headers(payload_bytes: bytes, secret: str) -> dict:
    """Compute a valid X-Webhook-Signature for the given raw payload."""
    import hmac, hashlib
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return {"HTTP_X_WEBHOOK_SIGNATURE": sig, **_auth()}


@patch("noctua.whatsapp.media.download", return_value={"kind": "text", "media_paths": []})
@patch("noctua.whatsapp.client.send_text")
def test_whatsapp_signal_fails_when_producer_missing_toolkit(
    _send_text, _download, wa_settings
):
    """WhatsApp → social_post with no active connection → signal failed, no mission."""
    from noctua.signals.router import RouteDecision
    with patch("noctua.core.api._check_required_toolkits", return_value=["LINKEDIN"]), \
         patch(
             "noctua.signals.router.WhatsAppRouter.decide",
             return_value=RouteDecision(
                 action="route",
                 reason="whatsapp classifier",
                 producer_key="social_post",
                 goal="Tweet about our launch",
             ),
         ):
        raw = json.dumps(_wa_payload()).encode()
        headers = _wa_auth_headers(raw, "testsecret")
        c = Client()
        r = c.post(
            "/api/signals/whatsapp",
            data=raw,
            content_type="application/json",
            **headers,
        )

    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "failed"
    assert "LINKEDIN" in body["routing_reason"]
    assert body["mission_id"] is None
    assert Mission.objects.count() == 0


@patch("noctua.whatsapp.media.download", return_value={"kind": "text", "media_paths": []})
@patch("noctua.whatsapp.client.send_text")
def test_whatsapp_signal_creates_mission_when_toolkit_connected(
    _send_text, _download, wa_settings, mocker, django_capture_on_commit_callbacks
):
    """WhatsApp → social_post, LINKEDIN active → mission created.

    Uses the real social_post producer (required_toolkits = LINKEDIN/TWITTER/
    BLUESKY) satisfied by one active Connection, routing decision mocked so
    we don't need to call the Haiku classifier.
    """
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c-li-2")

    spy = mocker.patch("noctua.runner.tasks.run_mission.delay")

    from noctua.signals.router import RouteDecision
    with patch(
        "noctua.signals.router.WhatsAppRouter.decide",
        return_value=RouteDecision(
            action="route",
            reason="whatsapp classifier",
            producer_key="social_post",
            goal="Tweet about our launch",
        ),
    ):
        raw = json.dumps(_wa_payload(msg_id="wa-msg-2")).encode()
        headers = _wa_auth_headers(raw, "testsecret")
        c = Client()
        with django_capture_on_commit_callbacks(execute=True):
            r = c.post(
                "/api/signals/whatsapp",
                data=raw,
                content_type="application/json",
                **headers,
            )

    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"] is not None
    assert Mission.objects.count() == 1
    spy.assert_called_once()
