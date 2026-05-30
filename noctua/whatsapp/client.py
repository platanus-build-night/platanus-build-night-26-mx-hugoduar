"""Kapso Meta-proxy outbound client (text-only, best-effort, never raises)."""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def send_text(to: str, body: str) -> None:
    base = settings.KAPSO_API_BASE_URL.rstrip("/")
    phone_id = settings.KAPSO_PHONE_NUMBER_ID
    url = f"{base}/meta/whatsapp/v24.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                url, json=payload, headers={"X-API-Key": settings.KAPSO_API_KEY}
            )
            r.raise_for_status()
    except Exception as exc:
        logger.exception("whatsapp send_text failed: %s", exc)
