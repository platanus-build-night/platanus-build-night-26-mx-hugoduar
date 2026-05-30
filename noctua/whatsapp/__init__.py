"""WhatsApp integration: signature verify, media fetch, outbound replies."""
import logging

from django.conf import settings as _settings  # noqa: F401  (kept for symmetry/imports)

from noctua.whatsapp import client as _client

logger = logging.getLogger(__name__)


def maybe_reply_to_whatsapp(mission) -> None:
    """If this mission was triggered by a WhatsApp signal, send the artifact back.

    Best-effort: any failure is logged and swallowed. Callers should still wrap
    in try/except so a stray import/AttributeError can't bubble up.
    """
    signal = _get_whatsapp_signal(mission)
    if signal is None:
        return

    wa_from = ((signal.payload or {}).get("router_input") or {}).get("wa_from", "")
    if not wa_from:
        logger.warning("whatsapp reply skipped: no wa_from for mission %s", mission.id)
        return

    artifact = mission.artifacts.order_by("-id").first()
    if artifact is None:
        return

    body = _format_artifact(artifact)
    try:
        _client.send_text(to=wa_from, body=body)
    except Exception:
        logger.exception("whatsapp reply failed for mission %s", mission.id)


def _get_whatsapp_signal(mission):
    try:
        sig = mission.signal  # OneToOneField reverse accessor
    except Exception:
        return None
    if sig is None or sig.source != "whatsapp":
        return None
    return sig


def _format_artifact(artifact) -> str:
    kind = artifact.kind
    preview = artifact.preview or {}
    if kind == "social_post":
        return preview.get("body") or "(empty post)"
    if kind == "pr":
        return f"PR ready for review: {artifact.uri or '(no url)'}"
    if kind in ("analysis", "diagnostic"):
        summary = preview.get("summary") or preview.get("body") or "(empty analysis)"
        return f"{summary[:1000]}"
    if kind in ("cad", "tool"):
        return f"{kind} ready at /queue/{artifact.id}"
    return f"Artifact #{artifact.id} ({kind}) ready at /queue/{artifact.id}"
