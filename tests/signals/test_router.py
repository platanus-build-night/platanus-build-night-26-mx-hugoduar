import pytest
from noctua.signals.router import route_signal


def test_sentry_routes_an_error():
    payload = {
        "action": "created",
        "data": {"issue": {
            "id": "1",
            "title": "TypeError: x",
            "level": "error",
            "culprit": "src/app.py in foo",
            "project": {"slug": "noctua-demo-app"},
            "permalink": "https://sentry.example/x/issues/1/",
        }},
    }
    d = route_signal("sentry", payload)
    assert d.action == "route"
    assert d.producer_key == "pr"
    assert "TypeError: x" in d.goal
    assert d.repo_url == "https://github.com/hugoduar/noctua-demo-app"


def test_sentry_ignores_warning():
    payload = {
        "action": "created",
        "data": {"issue": {
            "id": "2", "title": "x", "level": "warning",
            "project": {"slug": "noctua-demo-app"},
        }},
    }
    d = route_signal("sentry", payload)
    assert d.action == "ignore"
    assert "warning" in d.reason


def test_sentry_ignores_resolved_action():
    payload = {"action": "resolved", "data": {"issue": {"id": "3", "level": "error"}}}
    d = route_signal("sentry", payload)
    assert d.action == "ignore"


def test_sentry_ignores_unknown_project():
    payload = {
        "action": "created",
        "data": {"issue": {
            "id": "4", "title": "x", "level": "error",
            "project": {"slug": "some-other-project"},
        }},
    }
    d = route_signal("sentry", payload)
    assert d.action == "ignore"
    assert "no repo" in d.reason


def test_unknown_source():
    d = route_signal("github", {})
    assert d.action == "ignore"
    assert "no router" in d.reason
