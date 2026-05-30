from celery import shared_task
from django.utils.timezone import now
from noctua.core.models import Mission

@shared_task
def run_mission(mission_id: int):
    m = Mission.objects.get(id=mission_id)
    m.state = "running"
    m.started_at = now()
    m.save(update_fields=["state", "started_at"])
    # placeholder — replaced by full lifecycle in Task 23
    m.state = "succeeded"
    m.finished_at = now()
    m.save(update_fields=["state", "finished_at"])
    return mission_id
