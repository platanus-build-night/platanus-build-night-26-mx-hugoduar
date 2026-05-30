import pytest
import json
from unittest.mock import patch
from django.test import Client
from noctua.core.models import Mission, Connection

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_headers(settings):
    settings.NOCTUA_API_TOKEN = "test-token"
    return {"HTTP_AUTHORIZATION": "Bearer test-token"}


def _make_external_producer_in_cache(key="social_post", required=("LINKEDIN", "TWITTER", "BLUESKY")):
    from noctua.producers import registry as preg

    class _P:
        external_tools = True
        content_only = False
        required_toolkits = list(required)
        optional_toolkits: list[str] = []
        composio_actions = {tk: [f"{tk}_DO_THING"] for tk in required}
    preg._cache[key] = _P()


def test_create_mission_rejected_when_no_required_toolkit_connected(auth_headers):
    _make_external_producer_in_cache("social_post", ("LINKEDIN", "TWITTER", "BLUESKY"))
    payload = {
        "goal": "post about the launch",
        "producer_key": "social_post",
        "inputs": {}, "success_criteria": "", "domain": "social",
        "repo_url": "", "issue_url": "", "auto_act": False,
    }
    r = Client().post("/api/missions",
                      data=json.dumps(payload),
                      content_type="application/json", **auth_headers)
    assert r.status_code == 400
    body = r.json()
    assert body.get("error") == "missing_connections"
    assert set(body.get("toolkits", [])) == {"LINKEDIN", "TWITTER", "BLUESKY"}
    assert Mission.objects.count() == 0


def test_create_mission_accepted_when_at_least_one_required_toolkit_active(auth_headers):
    _make_external_producer_in_cache("social_post", ("LINKEDIN", "TWITTER", "BLUESKY"))
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    payload = {
        "goal": "post about the launch",
        "producer_key": "social_post",
        "inputs": {}, "success_criteria": "", "domain": "social",
        "repo_url": "", "issue_url": "", "auto_act": False,
    }
    # Patch run_mission so we don't actually fire it during the API test
    with patch("noctua.runner.tasks.run_mission") as run:
        r = Client().post("/api/missions",
                          data=json.dumps(payload),
                          content_type="application/json", **auth_headers)
    assert r.status_code == 201
    assert Mission.objects.count() == 1
    run.delay.assert_called_once()


def test_create_mission_rejected_when_only_expired_connection_present(auth_headers):
    _make_external_producer_in_cache("social_post", ("LINKEDIN",))
    Connection.objects.create(toolkit="LINKEDIN", status="expired", composio_conn_id="c1")
    payload = {
        "goal": "x", "producer_key": "social_post",
        "inputs": {}, "success_criteria": "", "domain": "social",
        "repo_url": "", "issue_url": "", "auto_act": False,
    }
    r = Client().post("/api/missions",
                      data=json.dumps(payload),
                      content_type="application/json", **auth_headers)
    assert r.status_code == 400


def test_create_mission_skips_preflight_for_pr_producer(auth_headers):
    # PR producer has no required_toolkits; pre-flight should be a no-op.
    payload = {
        "goal": "fix the bug", "producer_key": "pr",
        "inputs": {}, "success_criteria": "", "domain": "code",
        "repo_url": "https://github.com/x/y", "issue_url": "", "auto_act": False,
    }
    with patch("noctua.runner.tasks.run_mission"):
        r = Client().post("/api/missions",
                          data=json.dumps(payload),
                          content_type="application/json", **auth_headers)
    assert r.status_code == 201
