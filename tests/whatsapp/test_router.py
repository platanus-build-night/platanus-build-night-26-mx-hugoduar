from unittest.mock import MagicMock

import pytest

from noctua.core.models import Producer
from noctua.signals.router import route_signal

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _producers(db):
    Producer.objects.get_or_create(
        key="social_post", defaults={"kind": "social_post", "rubric_md": "Drafts short social posts."}
    )
    Producer.objects.get_or_create(
        key="clinical_analysis", defaults={"kind": "analysis", "rubric_md": "Reads medical images and writes a one-paragraph analysis."}
    )
    Producer.objects.get_or_create(
        key="pr", defaults={"kind": "pr", "rubric_md": "Opens a draft PR against a GitHub repo."}
    )


def _patch_anthropic(mocker, tool_input):
    """Make WhatsAppRouter's Claude call return a single tool_use block."""
    fake = MagicMock()
    fake.stop_reason = "tool_use"
    fake.content = [MagicMock(type="tool_use", name="route", input=tool_input)]
    fake.usage = MagicMock(input_tokens=10, output_tokens=10)
    return mocker.patch("noctua.signals.router.call_with_cache", return_value=fake)


def _patch_anthropic_end_turn(mocker, text="off-topic chatter"):
    fake = MagicMock()
    fake.stop_reason = "end_turn"
    block = MagicMock(type="text", text=text)
    fake.content = [block]
    fake.usage = MagicMock(input_tokens=10, output_tokens=5)
    return mocker.patch("noctua.signals.router.call_with_cache", return_value=fake)


def test_text_message_routes_to_social_post(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "social_post",
        "goal": "Draft a launch tweet about overnight AI factories",
    })
    decision = route_signal("whatsapp", {
        "kind": "text",
        "text": "Draft a launch tweet about overnight AI factories",
        "caption": "",
        "transcript": None,
        "wa_from": "525529404910",
        "media_paths": [],
    })
    assert decision.action == "route"
    assert decision.producer_key == "social_post"
    assert "launch tweet" in decision.goal
    assert decision.inputs["wa_from"] == "525529404910"


def test_image_message_routes_to_clinical(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "clinical_analysis",
        "goal": "Analyze the attached x-ray for fractures",
    })
    decision = route_signal("whatsapp", {
        "kind": "image",
        "text": "",
        "caption": "x-ray hand",
        "transcript": None,
        "wa_from": "525529404910",
        "media_paths": ["/tmp/xray.jpg"],
    })
    assert decision.action == "route"
    assert decision.producer_key == "clinical_analysis"
    assert decision.inputs["media_paths"] == ["/tmp/xray.jpg"]


def test_audio_transcript_lands_in_goal(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "social_post",
        "goal": "Draft a tweet: \"Hello, I need help with my order\"",
    })
    decision = route_signal("whatsapp", {
        "kind": "audio",
        "text": "",
        "caption": "",
        "transcript": "Hello, I need help with my order",
        "wa_from": "525529404910",
        "media_paths": ["/tmp/voice.ogg"],
    })
    assert decision.action == "route"
    assert "Hello, I need help with my order" in decision.goal


def test_pr_without_repo_url_is_ignored(mocker):
    _patch_anthropic(mocker, {
        "producer_key": "pr",
        "goal": "Refactor the auth middleware",
    })
    decision = route_signal("whatsapp", {
        "kind": "text",
        "text": "Refactor the auth middleware",
        "caption": "",
        "transcript": None,
        "wa_from": "525529404910",
        "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "repo" in decision.reason.lower()


def test_unknown_producer_key_is_ignored(mocker):
    _patch_anthropic(mocker, {"producer_key": "gibberish", "goal": "x"})
    decision = route_signal("whatsapp", {
        "kind": "text", "text": "hello", "caption": "",
        "transcript": None, "wa_from": "1", "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "unknown producer" in decision.reason.lower()


def test_classifier_end_turn_is_ignored(mocker):
    _patch_anthropic_end_turn(mocker, text="this looks like spam")
    decision = route_signal("whatsapp", {
        "kind": "text", "text": "lol", "caption": "",
        "transcript": None, "wa_from": "1", "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "declined" in decision.reason.lower()


def test_anthropic_failure_is_ignored(mocker):
    mocker.patch("noctua.signals.router.call_with_cache", side_effect=RuntimeError("boom"))
    decision = route_signal("whatsapp", {
        "kind": "text", "text": "hi", "caption": "",
        "transcript": None, "wa_from": "1", "media_paths": [],
    })
    assert decision.action == "ignore"
    assert "classifier unavailable" in decision.reason.lower()
