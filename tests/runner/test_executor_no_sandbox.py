import pytest
from unittest.mock import MagicMock, patch
from noctua.core.models import Mission, Plan
from noctua.runner.executor import execute_plan
from noctua.tools.base import ToolEntry, ToolResult

pytestmark = pytest.mark.django_db


def _budget():
    return {"max_tool_calls": 10, "max_tokens": 10_000, "max_wall_seconds": 60}


def test_execute_tool_step_without_sandbox_passes_none_to_callable():
    m = Mission.objects.create(goal="g", producer_key="social_post", budget=_budget())
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:LINKEDIN.LINKEDIN_CREATE_POST", "args": {"text": "hi"}},
         "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    captured = {}
    def fake_call(args, sandbox):
        captured["args"] = args
        captured["sandbox"] = sandbox
        return ToolResult(ok=True, value={"url": "https://x/1"})
    fake_entry = ToolEntry(name="composio:LINKEDIN.LINKEDIN_CREATE_POST",
                           signature={}, status="composio", callable=fake_call)

    with patch("noctua.runner.executor.ToolRegistry") as Reg:
        Reg.return_value.lookup.return_value = fake_entry
        results = execute_plan(m, plan, sandbox=None)

    assert results[0]["status"] == "succeeded"
    assert captured["args"] == {"text": "hi"}
    assert captured["sandbox"] is None


def test_execute_exec_step_without_sandbox_raises():
    m = Mission.objects.create(goal="g", producer_key="social_post", budget=_budget())
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "exec",
         "payload": {"cmd": ["echo", "hi"]},
         "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    results = execute_plan(m, plan, sandbox=None)
    # All retries fail the same way → step status is failed; result.error mentions sandbox.
    assert results[0]["status"] == "failed"
    assert "sandbox" in results[0]["result"]["error"].lower()


def test_execute_edit_step_without_sandbox_passes_none_to_producer():
    m = Mission.objects.create(goal="g", producer_key="clinical_analysis", budget=_budget())
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "edit",
         "payload": {"goal": "analyze"},
         "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    captured = {}
    fake_producer = MagicMock()
    def fake_execute_step(step, sandbox, mission):
        captured["sandbox"] = sandbox
        return ToolResult(ok=True, value="ok")
    fake_producer.execute_step.side_effect = fake_execute_step

    results = execute_plan(m, plan, sandbox=None, producer=fake_producer)
    assert results[0]["status"] == "succeeded"
    assert captured["sandbox"] is None
