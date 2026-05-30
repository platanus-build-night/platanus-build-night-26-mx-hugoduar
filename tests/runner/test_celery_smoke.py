import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db

CANNED_PLAN = '{"steps":[],"rendered_md":"smoke"}'


def test_run_mission_advances_state(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    Producer.objects.get_or_create(key="pr", defaults={"kind": "pr", "rubric_md": "", "default_budget": {}})
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="", budget={})

    fake_planner_resp = MagicMock()
    fake_planner_resp.content = [MagicMock(text=CANNED_PLAN)]
    fake_planner_resp.usage = MagicMock(input_tokens=5, output_tokens=5)

    fake_sandbox = MagicMock()
    fake_sandbox.boot.return_value = MagicMock(container_id="c", state="ready")

    fake_producer = MagicMock()
    fake_producer.finalize.return_value = MagicMock()

    with patch("noctua.runner.planner.call_with_cache", return_value=fake_planner_resp), \
         patch("noctua.runner.tasks.Sandbox", return_value=fake_sandbox), \
         patch("noctua.runner.tasks.get_producer", return_value=fake_producer):
        run_mission(m.id)

    m.refresh_from_db()
    assert m.state == "succeeded"
