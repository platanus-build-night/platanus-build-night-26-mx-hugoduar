import pytest
from noctua.core.models import Mission, Producer, Plan

pytestmark = pytest.mark.django_db


def test_diagnostic_manifest():
    from noctua.producers.external.diagnostic import DiagnosticProducer
    p = DiagnosticProducer()
    assert p.key == "diagnostic"
    assert p.kind == "diagnostic"
    assert p.required_toolkits == ["LINEAR"]
    assert p.optional_toolkits == ["SLACK"]
    assert "LINEAR_GET_ISSUE" in p.composio_actions["LINEAR"]
    assert "LINEAR_CREATE_COMMENT" in p.composio_actions["LINEAR"]


def test_diagnostic_finalize_includes_comment_link():
    from noctua.producers.external.diagnostic import DiagnosticProducer
    Producer.objects.create(key="diagnostic", kind="diagnostic", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="diagnose issue ABC-123", producer_key="diagnostic", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:LINEAR.LINEAR_GET_ISSUE", "args": {"issue_id": "ABC-123"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"title": "Brakes squeal"}, "error": ""}},
        {"step_id": "s2", "kind": "edit", "payload": {"goal": "diagnose"},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": "Possible pad wear...", "error": ""}},
        {"step_id": "s3", "kind": "tool",
         "payload": {"name": "composio:LINEAR.LINEAR_CREATE_COMMENT", "args": {}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"comment_url": "https://linear.app/c/1"}, "error": ""}},
    ], rendered_md="")

    p = DiagnosticProducer()
    a = p.finalize(m, sandbox=None)
    assert a.preview["comment_url"] == "https://linear.app/c/1"
