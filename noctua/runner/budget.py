from django.db import transaction
from noctua.core.models import Mission


def increment_spent(mission_id: int, *, wall_seconds: int = 0, tokens: int = 0, tool_calls: int = 0) -> dict:
    with transaction.atomic():
        m = Mission.objects.select_for_update().get(id=mission_id)
        s = dict(m.spent or {"wall_seconds": 0, "tokens": 0, "tool_calls": 0})
        s["wall_seconds"] += wall_seconds
        s["tokens"] += tokens
        s["tool_calls"] += tool_calls
        m.spent = s
        m.save(update_fields=["spent"])
        return s


def check_budget(mission_id: int) -> str | None:
    """Return the field name of the breached cap, or None."""
    m = Mission.objects.get(id=mission_id)
    b, s = m.budget or {}, m.spent or {}
    for field in ("wall_seconds", "tokens", "tool_calls"):
        cap = b.get(f"max_{field}")
        if cap is not None and s.get(field, 0) > cap:
            return field
    return None
