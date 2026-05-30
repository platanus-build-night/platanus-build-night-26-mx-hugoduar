import pytest


@pytest.fixture(autouse=True, scope="session")
def _prewarm_api():
    """Import noctua.core.api once per session so _warm_producer_cache() runs
    before any test manipulates the producer registry cache.  Without this,
    the first HTTP request inside a test triggers the import mid-test and can
    overwrite a fake producer injected by the test with the real one from the
    entry-points registry.
    """
    import noctua.core.api  # noqa: F401 — side-effect import only


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
