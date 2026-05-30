import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Plan
from noctua.runner.executor import execute_plan

pytestmark = pytest.mark.django_db


def test_executes_tool_steps_in_order():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={"max_tool_calls": 10, "max_tokens": 10000, "max_wall_seconds": 60})
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool", "payload": {"name": "read_file", "args": {"path": "/work/x"}}, "status": "pending", "attempt": 0, "result": None}
    ], rendered_md="")
    fake_sandbox = MagicMock()
    fake_sandbox.read_file.return_value = b"hello"
    results = execute_plan(m, plan, sandbox=fake_sandbox)
    assert results[0]["status"] == "succeeded"
    assert "hello" in results[0]["result"]["value"]
