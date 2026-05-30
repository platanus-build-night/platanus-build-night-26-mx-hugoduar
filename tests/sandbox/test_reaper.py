from noctua.sandbox.tasks import reap_orphans


def test_reaper_runs_without_error():
    # don't care about behavior — only that calling it doesn't raise
    reap_orphans()
