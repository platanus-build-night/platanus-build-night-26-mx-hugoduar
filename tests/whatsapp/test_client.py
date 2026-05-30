import httpx
import pytest
import respx

from noctua.whatsapp.client import send_text


@pytest.fixture
def settings_kapso(settings):
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"
    settings.KAPSO_PHONE_NUMBER_ID = "597907523413541"
    return settings


@respx.mock
def test_send_text_posts_to_meta_proxy(settings_kapso):
    route = respx.post(
        "https://api.kapso.test/meta/whatsapp/v24.0/597907523413541/messages"
    ).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.x"}]}))

    send_text(to="525529404910", body="Hello")

    assert route.called
    req = route.calls.last.request
    assert req.headers["X-API-Key"] == "k-test"
    import json as _json
    payload = _json.loads(req.content)
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "525529404910"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hello"


@respx.mock
def test_send_text_swallows_http_errors(settings_kapso, caplog):
    respx.post(
        "https://api.kapso.test/meta/whatsapp/v24.0/597907523413541/messages"
    ).mock(return_value=httpx.Response(500, text="boom"))

    # Should not raise — best-effort.
    send_text(to="525529404910", body="Hello")
    # Failure is logged.
    assert any("send_text" in rec.message or "boom" in rec.message for rec in caplog.records)
