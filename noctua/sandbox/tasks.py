import docker
import time
import datetime
from celery import shared_task


@shared_task
def reap_orphans():
    client = docker.from_env()
    now = time.time()
    for c in client.containers.list(filters={"label": "noctua.role"}):
        try:
            started = c.attrs["State"]["StartedAt"]
            t = datetime.datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
            if now - t > 1800:
                c.kill()
                c.remove(force=True)
        except Exception:
            pass
