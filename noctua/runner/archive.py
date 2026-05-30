import json
from pathlib import Path
from django.conf import settings
from noctua.core.models import Mission


def archive_mission(mission_id: int):
    m = Mission.objects.get(id=mission_id)
    base = settings.NOCTUA_ARCHIVE_DIR / str(m.id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "mission.json").write_text(json.dumps({
        "id": m.id,
        "goal": m.goal,
        "state": m.state,
        "state_reason": m.state_reason,
        "producer_key": m.producer_key,
        "spent": m.spent,
        "budget": m.budget,
    }, indent=2))
    plans = [{"version": p.version, "steps": p.steps, "rendered_md": p.rendered_md} for p in m.plans.all()]
    (base / "plans.json").write_text(json.dumps(plans, indent=2))
    artifacts = [
        {"id": a.id, "kind": a.kind, "uri": a.uri, "preview": a.preview, "validation": a.validation}
        for a in m.artifacts.all()
    ]
    (base / "artifacts.json").write_text(json.dumps(artifacts, indent=2))
