import shutil
import time
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from ninja import NinjaAPI, Schema
from noctua.core.auth import BearerAuth
from noctua.core.models import Mission, Artifact, Tool, Producer, Plan, Connection
from noctua.core.schemas import MissionCreate, MissionOut, MissionListOut, PlanOut, RespondIn, ArtifactOut, ConnectionOut, ConnectionInitiateOut, ProducerToolkitsOut
from noctua.integrations.composio import get_client
from noctua.producers.registry import get_producer

api = NinjaAPI(title="Noctua", auth=BearerAuth())

def _warm_producer_cache():
    """Pre-resolve all registered producers so their manifests are visible to
    the Connections UI without waiting for the first mission of each kind."""
    from importlib.metadata import entry_points
    from noctua.producers.registry import get_producer
    for ep in entry_points(group="noctua.producers"):
        try:
            get_producer(ep.name)
        except Exception:
            pass  # producer with broken import — fail soft; will surface elsewhere

_warm_producer_cache()

DEFAULT_BUDGET = {"max_wall_seconds": 1800, "max_tokens": 200_000, "max_tool_calls": 50}

def _check_required_toolkits(producer_key: str) -> list[str]:
    """Return required toolkits with no active Connection (empty list = OK).

    Returns the list of ``required_toolkits`` declared by the producer if NONE
    of them has an active Connection row — i.e. the mission should be refused.
    An empty return means at least one required toolkit is connected (the "any
    one suffices" semantic) OR the producer has no required_toolkits at all.
    """
    try:
        producer = get_producer(producer_key)
    except LookupError:
        return []  # Unknown producer: let the caller surface that error
    required = list(getattr(producer, "required_toolkits", []) or [])
    if not required:
        return []
    active = set(Connection.objects.filter(
        toolkit__in=required, status="active",
    ).values_list("toolkit", flat=True))
    if active:
        return []
    return required


@api.post("/missions", response={201: MissionOut, 400: dict})
def create_mission(request, payload: MissionCreate):
    from noctua.runner.tasks import run_mission  # local import to avoid Celery at import time
    # Pre-flight: validate producer resolves.
    try:
        get_producer(payload.producer_key)
    except LookupError:
        return 400, {"error": "unknown_producer", "producer_key": payload.producer_key}
    # Pre-flight: producer's required_toolkits must each be reachable
    # via at least one active Connection. (Any one toolkit in the list suffices —
    # see spec §5 "alternatives, any of which suffices".)
    missing = _check_required_toolkits(payload.producer_key)
    if missing:
        return 400, {"error": "missing_connections", "toolkits": missing}
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
    transaction.on_commit(lambda: run_mission.delay(m.id))
    # Refresh to get the latest state from the database (especially when running Celery tasks eagerly in tests)
    m.refresh_from_db()
    return 201, m

@api.get("/missions", response=list[MissionListOut])
def list_missions(request, state: str | None = None, producer_key: str | None = None):
    qs = Mission.objects.all().order_by("-id")
    if state:
        qs = qs.filter(state=state)
    if producer_key:
        qs = qs.filter(producer_key=producer_key)
    return [
        {
            "id": m.id, "goal": m.goal, "state": m.state,
            "state_reason": m.state_reason, "producer_key": m.producer_key,
            "spent": m.spent or {}, "budget": m.budget or {},
            "created_at": m.created_at.isoformat() if m.created_at else "",
            "finished_at": m.finished_at.isoformat() if m.finished_at else None,
        }
        for m in qs[:200]
    ]

@api.get("/missions/{mission_id}", response=MissionOut)
def get_mission(request, mission_id: int):
    m = get_object_or_404(Mission, id=mission_id)
    try:
        sig_id = m.signal.id
    except Exception:
        sig_id = None
    return {
        "id": m.id,
        "goal": m.goal,
        "state": m.state,
        "state_reason": m.state_reason,
        "producer_key": m.producer_key,
        "repo_url": m.repo_url,
        "issue_url": m.issue_url,
        "budget": m.budget or {},
        "spent": m.spent or {},
        "needs_input_prompt": m.needs_input_prompt,
        "created_at": m.created_at,
        "started_at": m.started_at,
        "finished_at": m.finished_at,
        "signal_id": sig_id,
    }

@api.get("/missions/{mission_id}/plans", response=list[PlanOut])
def list_mission_plans(request, mission_id: int):
    qs = Plan.objects.filter(mission_id=mission_id).order_by("version")
    return [{"id": p.id, "version": p.version, "steps": p.steps, "rendered_md": p.rendered_md} for p in qs]

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
    # Re-check toolkits: a connection may have been revoked while the mission
    # was paused waiting for input. If that happened, leave state as needs_input
    # and surface the reason so the operator knows to reconnect before resuming.
    missing = _check_required_toolkits(m.producer_key)
    if missing:
        m.state_reason = f"missing_connections:{','.join(missing)}"
        m.save(update_fields=["state_reason"])
        return m
    m.needs_input_response = payload.response
    m.state = "queued"
    m.save(update_fields=["needs_input_response", "state"])
    transaction.on_commit(lambda: run_mission.delay(m.id))
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

class CreatePROverrides(Schema):
    title: str | None = None
    body: str | None = None
    branch: str | None = None
    base: str | None = None


@api.post("/artifacts/{artifact_id}/create_pr", response=ArtifactOut)
def create_artifact_pr(request, artifact_id: int, payload: CreatePROverrides | None = None):
    """Enqueue a Celery task that opens a draft PR for this artifact on GitHub."""
    from noctua.runner.tasks import create_pr_for_artifact  # local import to avoid Celery at import time
    a = get_object_or_404(Artifact, id=artifact_id)
    overrides = {}
    if payload:
        if payload.title is not None:
            overrides["title"] = payload.title
        if payload.body is not None:
            overrides["body"] = payload.body
        if payload.branch is not None:
            overrides["branch"] = payload.branch
        if payload.base is not None:
            overrides["base"] = payload.base
    create_pr_for_artifact.delay(artifact_id, overrides)
    # Refresh in case eager Celery (tests) already updated the artifact
    a.refresh_from_db()
    return a


@api.post("/artifacts/{artifact_id}/promote", response=ArtifactOut)
def promote_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "promoted"
    a.save(update_fields=["queue_state"])
    producer = get_producer(a.producer_key)
    producer.on_promote(a)
    return a

class SentryWebhookIn(Schema):
    """Wrapper schema so Ninja treats the body as JSON (not query params).

    Sentry POSTs a raw JSON object; we forward the whole thing as-is.
    The actual payload fields are accessed dynamically via .dict() / payload.
    """
    action: str = ""
    data: dict = {}

    class Config:
        extra = "allow"  # accept any additional Sentry fields without validation errors


class SignalOut(Schema):
    id: int
    source: str
    external_id: str
    title: str
    routing_status: str
    routing_reason: str
    received_at: str
    mission_id: int | None = None


class SignalDetailOut(Schema):
    id: int
    source: str
    external_id: str
    title: str
    routing_status: str
    routing_reason: str
    received_at: str
    mission_id: int | None = None
    payload: dict


def _serialize_signal(s) -> dict:
    return {
        "id": s.id,
        "source": s.source,
        "external_id": s.external_id,
        "title": s.title,
        "routing_status": s.routing_status,
        "routing_reason": s.routing_reason,
        "received_at": s.received_at.isoformat() if s.received_at else "",
        "mission_id": s.mission_id,
    }


def _short_hash(payload) -> str:
    import hashlib, json
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]


@api.post("/signals/sentry", response={200: SignalOut, 201: SignalOut})
def ingest_sentry_signal(request, body: SentryWebhookIn):
    """Sentry-issue webhook intake. Body is the raw Sentry payload."""
    import json as _json
    from noctua.core.models import Signal, Mission
    from noctua.signals.router import route_signal

    # Re-parse the raw request body so we store/route the full payload including
    # any extra fields Sentry sends that aren't declared in SentryWebhookIn.
    try:
        payload = _json.loads(request.body)
    except Exception:
        payload = body.dict()

    issue = (payload.get("data") or {}).get("issue") or {}
    external_id = str(issue.get("id") or "")
    title = issue.get("title") or "(no title)"
    if not external_id:
        signal = Signal.objects.create(
            source="sentry", external_id=f"missing:{_short_hash(payload)}",
            title=title, payload=payload,
            routing_status="failed", routing_reason="missing data.issue.id",
        )
        return 201, _serialize_signal(signal)

    signal, created = Signal.objects.get_or_create(
        source="sentry",
        external_id=external_id,
        defaults={"title": title, "payload": payload},
    )
    if not created:
        return 200, _serialize_signal(signal)

    decision = route_signal("sentry", payload)
    if decision.action == "ignore":
        signal.routing_status = "ignored"
        signal.routing_reason = decision.reason
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    # action == 'route'
    from noctua.runner.tasks import run_mission
    mission = Mission.objects.create(
        goal=decision.goal,
        producer_key=decision.producer_key,
        repo_url=decision.repo_url,
        issue_url=decision.issue_url,
        inputs=decision.inputs or {},
        budget=DEFAULT_BUDGET,
    )
    signal.mission = mission
    signal.routing_status = "routed"
    signal.routing_reason = decision.reason
    signal.save(update_fields=["mission", "routing_status", "routing_reason"])
    transaction.on_commit(lambda mid=mission.id: run_mission.delay(mid))
    return 201, _serialize_signal(signal)


class MockSignalIn(Schema):
    """Payload schema for the generic mock signal endpoint.

    All fields are optional at the schema layer; the MockRouter validates
    what's actually required for the requested artifact kind.
    """
    kind: str = ""
    external_id: str = ""
    title: str = ""
    goal: str = ""
    repo_url: str = ""
    issue_url: str = ""
    inputs: dict = {}

    class Config:
        extra = "allow"


@api.post("/signals/mock", response={200: SignalOut, 201: SignalOut})
def ingest_mock_signal(request, body: MockSignalIn):
    """Generic dev/demo signal intake — routes to any producer based on `kind`."""
    import json as _json
    from noctua.core.models import Signal, Mission
    from noctua.signals.router import route_signal

    try:
        payload = _json.loads(request.body)
    except Exception:
        payload = body.dict()

    # external_id is caller-supplied; fall back to a content hash so retries
    # of the same payload dedupe even when the caller forgets to set one.
    external_id = str(payload.get("external_id") or "").strip()
    if not external_id:
        external_id = f"auto:{_short_hash(payload)}"
    title = str(payload.get("title") or payload.get("goal") or "(no title)")[:512]

    signal, created = Signal.objects.get_or_create(
        source="mock",
        external_id=external_id,
        defaults={"title": title, "payload": payload},
    )
    if not created:
        return 200, _serialize_signal(signal)

    decision = route_signal("mock", payload)
    if decision.action == "ignore":
        signal.routing_status = "ignored"
        signal.routing_reason = decision.reason
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    from noctua.runner.tasks import run_mission
    mission = Mission.objects.create(
        goal=decision.goal,
        producer_key=decision.producer_key,
        repo_url=decision.repo_url,
        issue_url=decision.issue_url,
        inputs=decision.inputs or {},
        budget=DEFAULT_BUDGET,
    )
    signal.mission = mission
    signal.routing_status = "routed"
    signal.routing_reason = decision.reason
    signal.save(update_fields=["mission", "routing_status", "routing_reason"])
    transaction.on_commit(lambda mid=mission.id: run_mission.delay(mid))
    return 201, _serialize_signal(signal)


class FeatureRequestIn(Schema):
    """Payload schema for the feature_request signal endpoint."""
    goal: str = ""
    repo_url: str = ""
    base: str = "main"

    class Config:
        extra = "allow"


@api.post("/signals/feature_request", response={201: SignalOut})
def ingest_feature_request_signal(request, body: FeatureRequestIn):
    """Feature-request signal intake — routes directly to a PR mission.

    Payload: {goal, repo_url?, base?}
    """
    import json as _json
    from noctua.core.models import Signal, Mission
    from noctua.signals.router import route_signal
    import uuid

    try:
        payload = _json.loads(request.body)
    except Exception:
        payload = body.dict()

    goal = (payload.get("goal") or "").strip()
    title = (goal[:120] + "…") if len(goal) > 120 else goal or "(no goal)"
    external_id = f"manual-{uuid.uuid4().hex[:12]}"

    signal = Signal.objects.create(
        source="feature_request",
        external_id=external_id,
        title=title,
        payload=payload,
    )

    decision = route_signal("feature_request", payload)
    if decision.action == "ignore":
        signal.routing_status = "ignored"
        signal.routing_reason = decision.reason
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    from noctua.runner.tasks import run_mission
    mission = Mission.objects.create(
        goal=decision.goal,
        producer_key=decision.producer_key,
        repo_url=decision.repo_url,
        issue_url=decision.issue_url,
        inputs=decision.inputs or {},
        budget=DEFAULT_BUDGET,
    )
    signal.mission = mission
    signal.routing_status = "routed"
    signal.routing_reason = decision.reason
    signal.save(update_fields=["mission", "routing_status", "routing_reason"])
    transaction.on_commit(lambda mid=mission.id: run_mission.delay(mid))
    return 201, _serialize_signal(signal)


class WhatsAppWebhookIn(Schema):
    """Loose wrapper so Ninja accepts the JSON body; we re-parse raw bytes."""
    message: dict = {}
    conversation: dict = {}

    class Config:
        extra = "allow"


@api.post("/signals/whatsapp", response={200: SignalOut, 201: SignalOut, 401: dict}, auth=None)
def ingest_whatsapp_signal(request, body: WhatsAppWebhookIn):
    """Kapso WhatsApp webhook intake (phone-number scope, v2 payloads)."""
    import json as _json
    import logging
    from django.conf import settings
    from noctua.core.models import Signal, Mission
    from noctua.signals.router import route_signal
    from noctua.whatsapp import signature as wa_sig, media as wa_media, client as wa_client

    logger = logging.getLogger(__name__)

    raw = request.body
    sig = request.headers.get("X-Webhook-Signature", "")
    if not wa_sig.verify(raw, sig, settings.KAPSO_WEBHOOK_SECRET):
        return 401, {"error": "invalid signature"}

    try:
        payload = _json.loads(raw)
    except Exception:
        payload = body.dict()

    message = payload.get("message") or {}
    conversation = payload.get("conversation") or {}
    external_id = str(message.get("id") or "")
    wa_from = conversation.get("phone_number") or ""
    if wa_from.startswith("+"):
        wa_from = wa_from[1:]
    title = (message.get("kapso") or {}).get("content") or message.get("type") or "(no title)"

    if not external_id:
        signal = Signal.objects.create(
            source="whatsapp", external_id=f"missing:{_short_hash(payload)}",
            title=title[:512], payload=payload,
            routing_status="failed", routing_reason="missing message.id",
        )
        return 201, _serialize_signal(signal)

    if wa_from not in settings.NOCTUA_WHATSAPP_ALLOWLIST:
        signal, created = Signal.objects.get_or_create(
            source="whatsapp", external_id=external_id,
            defaults={"title": title[:512], "payload": payload,
                      "routing_status": "ignored",
                      "routing_reason": f"from {wa_from!r} not in allowlist"},
        )
        return (201 if created else 200), _serialize_signal(signal)

    signal, created = Signal.objects.get_or_create(
        source="whatsapp", external_id=external_id,
        defaults={"title": title[:512], "payload": payload},
    )
    if not created:
        return 200, _serialize_signal(signal)

    try:
        media_info = wa_media.download(message, signal.id)
    except Exception as exc:
        signal.routing_status = "failed"
        signal.routing_reason = f"media download: {exc}"
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    router_payload = {
        **media_info,
        "text": (message.get("text") or {}).get("body", ""),
        "wa_from": wa_from,
    }
    signal.payload = {**payload, "router_input": router_payload}
    signal.save(update_fields=["payload"])

    decision = route_signal("whatsapp", router_payload)
    if decision.action == "ignore":
        signal.routing_status = "ignored"
        signal.routing_reason = decision.reason
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    missing = _check_required_toolkits(decision.producer_key)
    if missing:
        signal.routing_status = "failed"
        signal.routing_reason = f"missing_connections:{','.join(missing)}"
        signal.save(update_fields=["routing_status", "routing_reason"])
        return 201, _serialize_signal(signal)

    from noctua.runner.tasks import run_mission
    mission = Mission.objects.create(
        goal=decision.goal,
        producer_key=decision.producer_key,
        repo_url=decision.repo_url,
        issue_url=decision.issue_url,
        inputs=decision.inputs or {},
        budget=DEFAULT_BUDGET,
    )
    signal.mission = mission
    signal.routing_status = "routed"
    signal.routing_reason = decision.reason
    signal.save(update_fields=["mission", "routing_status", "routing_reason"])
    transaction.on_commit(lambda mid=mission.id: run_mission.delay(mid))

    try:
        wa_client.send_text(
            to=wa_from,
            body=f"Got it — mission #{mission.id} queued ({decision.producer_key}). I'll send the result when ready.",
        )
    except Exception:
        logger.exception("whatsapp ack send failed for mission %s", mission.id)

    return 201, _serialize_signal(signal)


@api.get("/signals", response=list[SignalOut])
def list_signals(request, status: str | None = None, source: str | None = None):
    from noctua.core.models import Signal
    qs = Signal.objects.all().order_by("-id")
    if status:
        qs = qs.filter(routing_status=status)
    if source:
        qs = qs.filter(source=source)
    return [_serialize_signal(s) for s in qs[:200]]


@api.get("/signals/{signal_id}", response=SignalOut)
def get_signal(request, signal_id: int):
    from noctua.core.models import Signal
    s = get_object_or_404(Signal, id=signal_id)
    return _serialize_signal(s)


@api.get("/signals/{signal_id}/detail", response=SignalDetailOut)
def get_signal_detail(request, signal_id: int):
    from noctua.core.models import Signal
    s = get_object_or_404(Signal, id=signal_id)
    return {**_serialize_signal(s), "payload": s.payload}


class SandboxRunOut(Schema):
    id: int
    mission_id: int
    image_ref: str
    container_id: str | None = None
    state: str
    log_path: str
    ttl_seconds: int
    started_at: str | None = None
    finished_at: str | None = None


def _serialize_sandbox(s) -> dict:
    return {
        "id": s.id,
        "mission_id": s.mission_id,
        "image_ref": s.image_ref,
        "container_id": s.container_id,
        "state": s.state,
        "log_path": s.log_path,
        "ttl_seconds": s.ttl_seconds,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
    }


@api.get("/sandboxes", response=list[SandboxRunOut])
def list_sandboxes(request, state: str | None = None, mission_id: int | None = None):
    from noctua.core.models import SandboxRun
    qs = SandboxRun.objects.all().order_by("-id")
    if state:
        qs = qs.filter(state=state)
    if mission_id:
        qs = qs.filter(mission_id=mission_id)
    return [_serialize_sandbox(s) for s in qs[:200]]


@api.get("/missions/{mission_id}/sandboxes", response=list[SandboxRunOut])
def list_mission_sandboxes(request, mission_id: int):
    from noctua.core.models import SandboxRun
    qs = SandboxRun.objects.filter(mission_id=mission_id).order_by("id")
    return [_serialize_sandbox(s) for s in qs]


class ProducerOut(Schema):
    key: str
    kind: str
    rubric_md: str
    version: int

class RubricIn(Schema):
    rubric_md: str

@api.get("/producers", response=list[ProducerOut])
def list_producers(request):
    return list(Producer.objects.all())

@api.get("/producers/toolkits", response=ProducerToolkitsOut)
def list_producer_toolkits(request):
    """Union of every required and optional toolkit across producers currently
    resolvable via the registry cache. Used by the Connections UI."""
    from noctua.producers import registry as preg
    toolkits: set[str] = set()
    for producer in preg._cache.values():
        toolkits.update(getattr(producer, "required_toolkits", []) or [])
        toolkits.update(getattr(producer, "optional_toolkits", []) or [])
    return {"toolkits": sorted(toolkits)}

@api.put("/producers/{key}/rubric", response=ProducerOut)
def update_rubric(request, key: str, payload: RubricIn):
    p = get_object_or_404(Producer, key=key)
    p.rubric_md = payload.rubric_md
    p.version += 1
    p.save(update_fields=["rubric_md", "version"])
    # also write to disk so it's git-trackable
    paths = {"pr": "noctua/producers/pr/rubric.md"}
    if key in paths:
        Path(paths[key]).write_text(payload.rubric_md)
    return p


# ---- Composio connections --------------------------------------------------


def _serialize_connection(c: Connection) -> dict:
    return {
        "toolkit": c.toolkit,
        "status": c.status,
        "composio_conn_id": c.composio_conn_id,
        "connected_at": c.connected_at.isoformat() if c.connected_at else None,
        "last_error": c.last_error,
    }


@api.get("/connections", response=list[ConnectionOut])
def list_connections(request):
    return [_serialize_connection(c) for c in Connection.objects.all().order_by("toolkit")]


@api.post("/connections/{toolkit}/initiate", response={201: ConnectionInitiateOut})
def initiate_connection(request, toolkit: str):
    toolkit = toolkit.upper()
    client = get_client()
    init = client.initiate_connection(toolkit=toolkit, user_id=settings.COMPOSIO_USER_ID)
    obj, _ = Connection.objects.update_or_create(
        toolkit=toolkit,
        defaults={
            "status": "pending",
            "composio_conn_id": init.composio_conn_id,
            "last_error": "",
            "connected_at": None,
        },
    )
    return 201, {
        "toolkit": obj.toolkit,
        "redirect_url": init.redirect_url,
        "composio_conn_id": obj.composio_conn_id,
        "status": obj.status,
    }


@api.post("/connections/{toolkit}/refresh", response=ConnectionOut)
def refresh_connection(request, toolkit: str):
    toolkit = toolkit.upper()
    obj = get_object_or_404(Connection, toolkit=toolkit)
    client = get_client()
    raw_status = client.fetch_connection_status(obj.composio_conn_id).upper()
    if raw_status == "ACTIVE":
        obj.status = "active"
        obj.connected_at = now()
        obj.last_error = ""
    elif raw_status in ("EXPIRED", "FAILED", "REVOKED"):
        obj.status = "expired"
    else:
        obj.status = "pending"
    obj.save(update_fields=["status", "connected_at", "last_error", "updated_at"])
    return _serialize_connection(obj)


@api.post("/connections/{toolkit}/disconnect", response=ConnectionOut)
def disconnect_connection(request, toolkit: str):
    toolkit = toolkit.upper()
    obj = get_object_or_404(Connection, toolkit=toolkit)
    obj.status = "revoked"
    obj.save(update_fields=["status", "updated_at"])
    return _serialize_connection(obj)


# Terminal mission states (logs stream until any of these)
_TERMINAL = ("succeeded", "failed", "stopped", "needs_input")


@api.get("/missions/{mission_id}/logs")
def stream_mission_logs(request, mission_id: int):
    """Server-Sent Events stream of the sandbox log file for this mission.

    Auth is via standard BearerAuth (Authorization: Bearer <token> header).
    Streams until the mission reaches a terminal state or 30 min, whichever first.
    """
    log_path = Path(settings.NOCTUA_ARCHIVE_DIR) / str(mission_id) / "sandbox.log"

    def event_stream():
        last_pos = 0
        deadline = time.time() + 1800  # 30 min
        sent_anything = False
        # Heartbeat every 15s so proxies don't time us out
        last_heartbeat = time.time()
        while time.time() < deadline:
            if log_path.exists():
                try:
                    with open(log_path, "r", errors="replace") as f:
                        f.seek(last_pos)
                        chunk = f.read()
                        if chunk:
                            for line in chunk.splitlines():
                                # SSE: each event is `data: <text>\n\n`
                                yield f"data: {line}\n\n".encode()
                                sent_anything = True
                            last_pos = f.tell()
                except OSError:
                    pass
            # Check mission terminal state
            try:
                m = Mission.objects.get(id=mission_id)
                if m.state in _TERMINAL:
                    if not sent_anything:
                        yield b"data: (no log written)\n\n"
                    yield f"event: done\ndata: {m.state}\n\n".encode()
                    return
            except Mission.DoesNotExist:
                yield b"event: error\ndata: mission not found\n\n"
                return
            # Heartbeat
            now_ts = time.time()
            if now_ts - last_heartbeat > 15:
                yield b": heartbeat\n\n"  # SSE comment line
                last_heartbeat = now_ts
            time.sleep(1)
        yield b"event: timeout\ndata: 1800s elapsed\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # for nginx if ever in front
    return response
