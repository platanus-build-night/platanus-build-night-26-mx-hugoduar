import pytest
from django.test import Client
from noctua.core.models import Signal, Mission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup(settings):
    settings.NOCTUA_API_TOKEN = "tt"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


def _auth():
    return {"HTTP_AUTHORIZATION": "Bearer tt"}


def _sentry_payload(issue_id="42", level="error", action="created", slug="noctua-demo-app"):
    return {
        "action": action,
        "data": {"issue": {
            "id": issue_id,
            "title": "TypeError: 'NoneType' object is not iterable",
            "level": level,
            "culprit": "src/app.py in foo",
            "project": {"slug": slug, "name": slug},
            "permalink": f"https://sentry.example/{slug}/issues/{issue_id}/",
        }},
    }


def test_routed_creates_mission(mocker):
    # Don't actually run the planner inside the test.
    spy = mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    r = c.post("/api/signals/sentry", data=_sentry_payload(), content_type="application/json", **_auth())
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "routed"
    assert body["mission_id"]
    assert Signal.objects.count() == 1
    assert Mission.objects.filter(id=body["mission_id"]).exists()
    spy.assert_called_once_with(body["mission_id"])


def test_ignored_does_not_create_mission():
    c = Client()
    r = c.post("/api/signals/sentry", data=_sentry_payload(level="warning"),
               content_type="application/json", **_auth())
    assert r.status_code == 201
    body = r.json()
    assert body["routing_status"] == "ignored"
    assert body["mission_id"] is None
    assert Mission.objects.count() == 0


def test_dedup_returns_existing(mocker):
    mocker.patch("noctua.runner.tasks.run_mission.delay")
    c = Client()
    p = _sentry_payload(issue_id="dup-1")
    r1 = c.post("/api/signals/sentry", data=p, content_type="application/json", **_auth())
    r2 = c.post("/api/signals/sentry", data=p, content_type="application/json", **_auth())
    assert r1.status_code == 201
    assert r2.status_code == 200  # the second is the cached row
    assert r1.json()["id"] == r2.json()["id"]
    assert Signal.objects.count() == 1
    assert Mission.objects.count() == 1
