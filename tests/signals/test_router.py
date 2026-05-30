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


# --- FeatureRequestRouter tests ---------------------------------------------

def test_feature_request_routes_with_goal():
    d = route_signal("feature_request", {"goal": "Add a /healthz endpoint."})
    assert d.action == "route"
    assert d.producer_key == "pr"
    assert d.goal == "Add a /healthz endpoint."
    assert d.repo_url == "https://github.com/hugoduar/noctua-demo-app"
    assert d.inputs == {"base": "main"}


def test_feature_request_uses_custom_repo_url():
    d = route_signal("feature_request", {
        "goal": "Fix the login bug",
        "repo_url": "https://github.com/acme/webapp",
    })
    assert d.action == "route"
    assert d.repo_url == "https://github.com/acme/webapp"


def test_feature_request_passes_base_branch():
    d = route_signal("feature_request", {
        "goal": "Refactor the API",
        "base": "develop",
    })
    assert d.action == "route"
    assert d.inputs["base"] == "develop"


def test_feature_request_ignores_missing_goal():
    d = route_signal("feature_request", {})
    assert d.action == "ignore"
    assert "missing goal" in d.reason


def test_feature_request_ignores_blank_goal():
    d = route_signal("feature_request", {"goal": "   "})
    assert d.action == "ignore"
    assert "missing goal" in d.reason
