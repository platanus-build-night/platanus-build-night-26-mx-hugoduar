import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Plan
from noctua.runner.planner import plan_for_mission

pytestmark = pytest.mark.django_db

CANNED = '''{"steps": [
  {"step_id":"s1","kind":"exec","payload":{"cmd":["bash","-lc","echo hi"]}},
  {"step_id":"s2","kind":"tool","payload":{"name":"run_pytest","args":{"args":""}}},
  {"step_id":"s3","kind":"tool","payload":{"name":"gh_pr_create","args":{"title":"t","body":"b","draft":true}}}
],"rendered_md":"hi"}'''


def test_plan_for_mission_persists():
    Producer.objects.create(key="pr", kind="pr", rubric_md="rubric", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    fake = MagicMock()
    fake.content = [MagicMock(text=CANNED)]
    fake.usage = MagicMock(input_tokens=100, output_tokens=200)
    with patch("noctua.runner.planner.call_with_cache", return_value=fake):
        plan, tokens = plan_for_mission(m)
    assert plan.steps[0]["kind"] == "exec"
    assert tokens == 300
    assert Plan.objects.filter(mission=m).count() == 1
