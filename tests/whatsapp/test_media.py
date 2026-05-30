import json
import re
from pathlib import Path

import httpx
import pytest
import respx

from noctua.whatsapp.media import download


@pytest.fixture
def settings_kapso(settings, tmp_path):
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"
    settings.NOCTUA_ARCHIVE_DIR = tmp_path
    return settings


def _text_msg():
    return {
        "type": "text",
        "text": {"body": "draft a tweet"},
        "kapso": {"content": "draft a tweet"},
    }


def _image_msg():
    return {
        "type": "image",
        "image": {"id": "media_id_123", "caption": "x-ray hand"},
        "kapso": {
            "content": "x-ray hand Image attached",
            "has_media": True,
            "media_url": "https://api.kapso.test/media/abc.jpg",
            "media_data": {
                "url": "https://api.kapso.test/media/abc.jpg",
                "filename": "xray.jpg",
                "content_type": "image/jpeg",
                "byte_size": 4,
            },
            "message_type_data": {"caption": "x-ray hand"},
        },
    }


def _audio_msg(with_transcript=True):
    msg = {
        "type": "audio",
        "audio": {"id": "media_id_456"},
        "kapso": {
            "has_media": True,
            "media_url": "https://api.kapso.test/media/voice.ogg",
            "media_data": {
                "url": "https://api.kapso.test/media/voice.ogg",
                "filename": "voice.ogg",
                "content_type": "audio/ogg",
                "byte_size": 4,
            },
        },
    }
    if with_transcript:
        msg["kapso"]["transcript"] = {"text": "Hello, I need help with my order"}
    return msg


def test_text_message_no_io(settings_kapso):
    result = download(_text_msg(), signal_id=1)
    assert result == {
        "kind": "text",
        "media_paths": [],
        "transcript": None,
        "caption": "",
    }


@respx.mock
def test_image_download_writes_file(settings_kapso, tmp_path):
    route = respx.get("https://api.kapso.test/media/abc.jpg").mock(
        return_value=httpx.Response(200, content=b"PNG!")
    )
    result = download(_image_msg(), signal_id=42)
    assert result["kind"] == "image"
    assert result["caption"] == "x-ray hand"
    assert len(result["media_paths"]) == 1
    p = Path(result["media_paths"][0])
    assert p.exists()
    assert p.read_bytes() == b"PNG!"
    assert p.parent == tmp_path / "whatsapp_media" / "42"
    assert route.called
    # The auth header is sent
    assert route.calls.last.request.headers.get("X-API-Key") == "k-test"


@respx.mock
def test_audio_with_kapso_transcript(settings_kapso, tmp_path):
    respx.get("https://api.kapso.test/media/voice.ogg").mock(
        return_value=httpx.Response(200, content=b"OGG!")
    )
    result = download(_audio_msg(with_transcript=True), signal_id=7)
    assert result["kind"] == "audio"
    assert result["transcript"] == "Hello, I need help with my order"


@respx.mock
def test_audio_without_transcript_does_not_raise(settings_kapso):
    respx.get("https://api.kapso.test/media/voice.ogg").mock(
        return_value=httpx.Response(200, content=b"OGG!")
    )
    result = download(_audio_msg(with_transcript=False), signal_id=8)
    assert result["transcript"] is None


@respx.mock
def test_download_is_idempotent(settings_kapso, tmp_path):
    route = respx.get("https://api.kapso.test/media/abc.jpg").mock(
        return_value=httpx.Response(200, content=b"PNG!")
    )
    download(_image_msg(), signal_id=99)
    download(_image_msg(), signal_id=99)
    assert route.call_count == 1


@respx.mock
def test_filename_with_path_traversal_is_sanitized(settings_kapso, tmp_path):
    respx.get("https://api.kapso.test/media/evil.bin").mock(
        return_value=httpx.Response(200, content=b"EVIL")
    )
    msg = {
        "type": "document",
        "document": {"id": "media_id_x"},
        "kapso": {
            "has_media": True,
            "media_url": "https://api.kapso.test/media/evil.bin",
            "media_data": {
                "url": "https://api.kapso.test/media/evil.bin",
                "filename": "../../../etc/evil",
                "content_type": "application/octet-stream",
                "byte_size": 4,
            },
        },
    }
    result = download(msg, signal_id=123)
    p = Path(result["media_paths"][0])
    assert p.exists()
    # The file is inside dest_dir, not escaped
    assert p.parent == tmp_path / "whatsapp_media" / "123"
    assert p.name == "evil"  # basename only
