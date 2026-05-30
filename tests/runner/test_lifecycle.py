import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Artifact, Plan
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db

CANNED_PLAN = '''{"steps":[
  {"step_id":"s1","kind":"exec","payload":{"cmd":["bash","-lc","echo hi"]}},
  {"step_id":"s2","kind":"tool","payload":{"name":"gh_pr_create","args":{"title":"t","body":"b","draft":true}}}
],"rendered_md":"x"}'''


def test_full_lifecycle_succeeds(monkeypatch):
    Producer.objects.create(key="pr", kind="pr", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="https://github.com/x/y", issue_url="", budget={"max_wall_seconds": 60, "max_tokens": 10000, "max_tool_calls": 5})

    fake_planner_resp = MagicMock()
    fake_planner_resp.content = [MagicMock(text=CANNED_PLAN)]
    fake_planner_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

    fake_sandbox = MagicMock()
    fake_sandbox.boot.return_value = MagicMock(container_id="c", state="ready")
    fake_sandbox.exec.return_value = MagicMock(exit_code=0, stdout="https://github.com/x/y/pull/1", stderr="")

    with patch("noctua.runner.planner.call_with_cache", return_value=fake_planner_resp), \
         patch("noctua.runner.tasks.Sandbox", return_value=fake_sandbox):
        run_mission(m.id)

    m.refresh_from_db()
    assert m.state == "succeeded"
    assert Artifact.objects.filter(mission=m, kind="pr").exists()
