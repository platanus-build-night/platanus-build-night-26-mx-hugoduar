import shutil
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from ninja import NinjaAPI
from noctua.core.auth import BearerAuth
from noctua.core.models import Mission, Artifact, Tool
from noctua.core.schemas import MissionCreate, MissionOut, RespondIn, ArtifactOut
from noctua.producers.registry import get_producer

api = NinjaAPI(title="Noctua", auth=BearerAuth())

DEFAULT_BUDGET = {"max_wall_seconds": 1800, "max_tokens": 200_000, "max_tool_calls": 50}

@api.post("/missions", response={201: MissionOut})
def create_mission(request, payload: MissionCreate):
    from noctua.runner.tasks import run_mission  # local import to avoid Celery at import time
    budget = payload.budget or DEFAULT_BUDGET
    m = Mission.objects.create(
        goal=payload.goal,
        inputs=payload.inputs,
        success_criteria=payload.success_criteria,
        domain=payload.domain,
        producer_key=payload.producer_key,
        repo_url=payload.repo_url,
        issue_url=payload.issue_url,
        budget=budget,
        auto_act=payload.auto_act,
    )
    run_mission.delay(m.id)
    return 201, m

@api.get("/missions/{mission_id}", response=MissionOut)
def get_mission(request, mission_id: int):
    return get_object_or_404(Mission, id=mission_id)

@api.post("/missions/{mission_id}/cancel", response=MissionOut)
def cancel_mission(request, mission_id: int):
    m = get_object_or_404(Mission, id=mission_id)
    if m.state in ("queued", "running", "needs_input"):
        m.state = "failed"
        m.state_reason = "cancelled_by_user"
        m.save(update_fields=["state", "state_reason"])
    return m

@api.post("/missions/{mission_id}/respond", response=MissionOut)
def respond_to_mission(request, mission_id: int, payload: RespondIn):
    from noctua.runner.tasks import run_mission
    m = get_object_or_404(Mission, id=mission_id)
    if m.state != "needs_input":
        return m
    m.needs_input_response = payload.response
    m.state = "queued"
    m.save(update_fields=["needs_input_response", "state"])
    run_mission.delay(m.id)
    return m

@api.get("/queue", response=list[ArtifactOut])
def list_queue(request, kind: str | None = None, queue_state: str | None = None):
    qs = Artifact.objects.all().order_by("-created_at")
    if kind:
        qs = qs.filter(kind=kind)
    if queue_state:
        qs = qs.filter(queue_state=queue_state)
    return list(qs[:100])

@api.get("/artifacts/{artifact_id}", response=ArtifactOut)
def get_artifact(request, artifact_id: int):
    return get_object_or_404(Artifact, id=artifact_id)

@api.post("/artifacts/{artifact_id}/approve", response=ArtifactOut)
def approve_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "approved"
    a.reviewed_at = now()
    a.save(update_fields=["queue_state", "reviewed_at"])
    if a.kind == "tool" and a.tool:
        a.tool.status = "graduated"
        a.tool.save(update_fields=["status"])
        src = settings.NOCTUA_TOOLS_DIR / a.tool.source_path
        if not src.is_absolute():
            src = settings.NOCTUA_TOOLS_DIR.parent / a.tool.source_path
        dst = settings.NOCTUA_TOOLS_DIR / "graduated" / f"{a.tool.name}.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src if src.exists() else a.tool.source_path, dst)
    else:
        producer = get_producer(a.producer_key)
        producer.on_approve(a)
    return a

@api.post("/artifacts/{artifact_id}/reject", response=ArtifactOut)
def reject_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "rejected"
    a.reviewed_at = now()
    a.save(update_fields=["queue_state", "reviewed_at"])
    if a.kind == "tool" and a.tool:
        a.tool.delete()
    return a

@api.post("/artifacts/{artifact_id}/promote", response=ArtifactOut)
def promote_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "promoted"
    a.save(update_fields=["queue_state"])
    producer = get_producer(a.producer_key)
    producer.on_promote(a)
    return a
