import pytest

from noctua.core.models import Artifact, Mission, Signal
from noctua.whatsapp import maybe_reply_to_whatsapp

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.KAPSO_API_KEY = "k-test"
    settings.KAPSO_PHONE_NUMBER_ID = "597907523413541"
    settings.KAPSO_API_BASE_URL = "https://api.kapso.test"


def _mission_with_signal(producer="social_post", wa_from="525529404910"):
    m = Mission.objects.create(goal="x", producer_key=producer, state="succeeded")
    Signal.objects.create(
        source="whatsapp", external_id=f"ext-{m.id}", title="t",
        payload={"router_input": {"wa_from": wa_from}}, mission=m,
        routing_status="routed",
    )
    return m


def test_no_signal_is_noop(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = Mission.objects.create(goal="x", producer_key="social_post", state="succeeded")
    maybe_reply_to_whatsapp(m)
    spy.assert_not_called()


def test_non_whatsapp_signal_is_noop(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = Mission.objects.create(goal="x", producer_key="social_post", state="succeeded")
    Signal.objects.create(source="sentry", external_id="s-1", title="t",
                          payload={}, mission=m, routing_status="routed")
    maybe_reply_to_whatsapp(m)
    spy.assert_not_called()


def test_social_post_sends_post_body_verbatim(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = _mission_with_signal(producer="social_post")
    Artifact.objects.create(
        mission=m, producer_key="social_post", kind="social_post",
        uri="", preview={"body": "Hello world from Noctua"},
    )
    maybe_reply_to_whatsapp(m)
    spy.assert_called_once()
    assert spy.call_args.kwargs.get("to") or spy.call_args.args[0] == "525529404910"
    body = spy.call_args.kwargs.get("body") or spy.call_args.args[1]
    assert "Hello world from Noctua" in body


def test_pr_artifact_sends_url(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = _mission_with_signal(producer="pr")
    Artifact.objects.create(
        mission=m, producer_key="pr", kind="pr",
        uri="https://github.com/me/repo/pull/42", preview={},
    )
    maybe_reply_to_whatsapp(m)
    spy.assert_called_once()
    body = spy.call_args.kwargs.get("body") or spy.call_args.args[1]
    assert "https://github.com/me/repo/pull/42" in body


def test_send_text_failure_does_not_raise(mocker):
    mocker.patch("noctua.whatsapp.client.send_text", side_effect=RuntimeError("boom"))
    m = _mission_with_signal()
    Artifact.objects.create(
        mission=m, producer_key="social_post", kind="social_post",
        uri="", preview={"body": "hi"},
    )
    # Must not raise.
    maybe_reply_to_whatsapp(m)


def test_mission_with_no_artifact_is_noop(mocker):
    spy = mocker.patch("noctua.whatsapp.client.send_text")
    m = _mission_with_signal()
    maybe_reply_to_whatsapp(m)
    spy.assert_not_called()
