import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Plan
from noctua.runner.tasks import run_mission
from noctua.runner.executor import NeedsInput

pytestmark = pytest.mark.django_db


def test_needs_input_pauses_and_resumes():
    Producer.objects.create(key="pr", kind="pr", rubric_md="r", default_budget={})
    m = Mission.objects.create(
        goal="g", producer_key="pr", repo_url="r", issue_url="",
        budget={"max_wall_seconds": 60, "max_tokens": 10000, "max_tool_calls": 5},
    )
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "edit", "payload": {}, "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    fake_sandbox = MagicMock()
    fake_sandbox.boot.return_value = MagicMock(container_id="c", state="ready")
    with patch("noctua.runner.tasks.Sandbox", return_value=fake_sandbox), \
         patch("noctua.runner.tasks.plan_for_mission", return_value=(plan, 50)), \
         patch("noctua.runner.tasks.execute_plan", side_effect=NeedsInput("clarify X?")):
        run_mission(m.id)

    m.refresh_from_db()
    assert m.state == "needs_input"
    assert m.needs_input_prompt == "clarify X?"
