import pytest


@pytest.fixture(autouse=True, scope="session")
def _eager_celery_config():
    """Configure Celery to run tasks eagerly during tests."""
    from noctua.celery import app
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


@pytest.fixture(autouse=True)
def _eager_celery_settings(settings):
    """Update Django settings for eager celery."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
