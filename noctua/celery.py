import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noctua.settings")

app = Celery("noctua")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["noctua.runner"])

app.conf.beat_schedule = {
    "reap-orphans": {
        "task": "noctua.sandbox.tasks.reap_orphans",
        "schedule": 300.0,  # every 5 minutes
    },
}
