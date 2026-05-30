import pytest
from noctua.core.models import Mission
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db

def test_run_mission_placeholder_advances_state(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    run_mission(m.id)  # call directly, no broker needed
    m.refresh_from_db()
    assert m.state == "succeeded"
