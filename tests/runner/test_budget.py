import pytest
from noctua.core.models import Mission
from noctua.runner.budget import increment_spent, check_budget

pytestmark = pytest.mark.django_db

@pytest.fixture
def mission():
    return Mission.objects.create(
        goal="g", producer_key="pr", repo_url="r",
        budget={"max_wall_seconds": 100, "max_tokens": 1000, "max_tool_calls": 5},
    )

def test_increment_and_check_under(mission):
    spent = increment_spent(mission.id, tokens=500, tool_calls=2)
    assert spent["tokens"] == 500
    assert check_budget(mission.id) is None  # under

def test_increment_breaches_tokens(mission):
    increment_spent(mission.id, tokens=1500)
    breach = check_budget(mission.id)
    assert breach == "tokens"
