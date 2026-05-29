import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_run_mission_delay():
    """Prevent Celery tasks from hitting a real broker during tests."""
    with patch("noctua.runner.tasks.run_mission.delay") as m:
        yield m
