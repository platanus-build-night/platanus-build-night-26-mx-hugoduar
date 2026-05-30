import pytest
from django.test import Client

from noctua.core.models import Connection, Mission, Signal
from noctua.signals.router import route_signal

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup(settings):
    settings.NOCTUA_API_TOKEN = "tt"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


def _auth():
    return {"HTTP_AUTHORIZATION": "Bearer tt"}


# --- Router-level ----------------------------------------------------------

@pytest.mark.parametrize(
    "kind, expected_producer",
    [
        ("social", "social_post"),
        ("clinical", "clinical_analysis"),
        ("diagnostic", "diagnostic"),
        ("cad", "cad"),
        ("tool", "tool_demo"),
    ],
)
def test_mock_routes_each_content_kind(kind, expected_producer):
    d = route_signal("mock", {"kind": kind, "goal": "do the thing"})
    assert d.action == "route"
    assert d.producer_key == expected_producer
    assert d.goal == "do the thing"
    assert d.inputs == {"mock_kind": kind}


def test_mock_code_requires_repo_url():
    d = route_signal("mock", {"kind": "code", "goal": "fix it"})
    assert d.action == "ignore"
    assert "repo_url" in d.reason


def test_mock_code_with_repo_routes_to_pr():
    d = route_signal(
        "mock",
        {"kind": "code", "goal": "fix it", "repo_url": "https://github.com/x/y"},
    )
    assert d.action == "route"
    assert d.producer_key == "pr"
    assert d.repo_url == "https://github.com/x/y"


def test_mock_unknown_kind_ignored():
    d = route_signal("mock", {"kind": "blockchain", "goal": "moon"})
    assert d.action == "ignore"
    assert "unknown kind" in d.reason


def test_mock_missing_goal_ignored():
    d = route_signal("mock", {"kind": "cad"})
    assert d.action == "ignore"
    assert "goal" in d.reason


def test_mock_missing_kind_ignored():
    d = route_signal("mock", {"goal": "x"})
    assert d.action == "ignore"
    assert "kind" in d.reason


# --- Endpoint-level --------------------------------------------------------

def test_mock_endpoint_routes_cad(mocker, django_capture_on_commit_callbacks):
    # cad producer requires GOOGLEDRIVE; set up an active connection so the
    # preflight check passes and the mission is actually created.
    Connection.objects.create(toolkit="GOOGLEDRIVE", status="active", composio_conn_id="gd-1")
    spy = mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    # run_mission.delay is wrapped in transaction.on_commit; use
    # django_capture_on_commit_callbacks to fire on-commit hooks eagerly.
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(
            "/api/signals/mock",
            data={"kind": "cad", "external_id": "cad-1", "title": "bracket", "goal": "design a bracket"},
            content_type="application/json",
            **_auth(),
        )
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"]
    m = Mission.objects.get(id=body["mission_id"])
    assert m.producer_key == "cad"
    assert m.goal == "design a bracket"
    spy.assert_called_once_with(m.id)


def test_mock_endpoint_dedups_on_external_id(mocker):
    # social_post producer requires LINKEDIN/TWITTER/BLUESKY; provide one
    # active connection so the preflight check passes and the mission is created.
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="li-dup")
    mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    payload = {"kind": "social", "external_id": "dup", "goal": "tweet it"}
    r1 = c.post("/api/signals/mock", data=payload, content_type="application/json", **_auth())
    r2 = c.post("/api/signals/mock", data=payload, content_type="application/json", **_auth())
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert Signal.objects.count() == 1
    assert Mission.objects.count() == 1


def test_mock_endpoint_auto_external_id_dedups_on_payload(mocker):
    mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    payload = {"kind": "clinical", "goal": "review labs"}
    r1 = c.post("/api/signals/mock", data=payload, content_type="application/json", **_auth())
    r2 = c.post("/api/signals/mock", data=payload, content_type="application/json", **_auth())
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert Signal.objects.count() == 1


def test_mock_endpoint_ignored_records_reason():
    c = Client()
    r = c.post(
        "/api/signals/mock",
        data={"kind": "code", "goal": "fix something"},  # no repo_url
        content_type="application/json",
        **_auth(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "ignored"
    assert body["mission_id"] is None
    assert "repo_url" in body["routing_reason"]
    assert Mission.objects.count() == 0
