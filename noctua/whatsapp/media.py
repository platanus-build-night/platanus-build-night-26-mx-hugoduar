"""Download inbound WhatsApp media from Kapso. No transcription — Kapso provides it."""
from pathlib import Path

import httpx
from django.conf import settings


def download(message: dict, signal_id: int) -> dict:
    """Fetch any media on the message and pluck the Kapso-provided transcript.

    Returns a dict with keys: kind, media_paths (list[str]), transcript (str|None),
    caption (str).
    """
    kind = message.get("type", "text")
    kapso = message.get("kapso") or {}
    media_url = kapso.get("media_url") or ""
    media_data = kapso.get("media_data") or {}
    transcript_block = kapso.get("transcript") or {}
    transcript = transcript_block.get("text") if isinstance(transcript_block, dict) else None
    caption = (kapso.get("message_type_data") or {}).get("caption", "")

    if kind == "text" or not media_url:
        return {"kind": kind, "media_paths": [], "transcript": transcript, "caption": caption}

    dest_dir = Path(settings.NOCTUA_ARCHIVE_DIR) / "whatsapp_media" / str(signal_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = media_data.get("filename") or _filename_from_url(media_url)
    dest = dest_dir / filename

    if not dest.exists():
        with httpx.Client(timeout=30.0) as client:
            r = client.get(media_url, headers={"X-API-Key": settings.KAPSO_API_KEY})
            r.raise_for_status()
            dest.write_bytes(r.content)

    return {
        "kind": kind,
        "media_paths": [str(dest)],
        "transcript": transcript,
        "caption": caption,
    }


def _filename_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1] or "media.bin"
