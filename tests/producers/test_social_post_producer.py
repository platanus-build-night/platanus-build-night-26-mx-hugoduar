import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Connection, Plan, Artifact

pytestmark = pytest.mark.django_db


def _budget():
    return {"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60}


def test_social_post_manifest():
    from noctua.producers.external.social_post import SocialPostProducer
    p = SocialPostProducer()
    assert p.key == "social_post"
    assert p.kind == "social_post"
    assert p.external_tools is True
    assert set(p.required_toolkits) == {"LINKEDIN", "TWITTER", "BLUESKY"}
    assert "LINKEDIN" in p.composio_actions
    assert "LINKEDIN_CREATE_POST" in p.composio_actions["LINKEDIN"]


def test_social_post_finalize_records_post_urls_in_artifact_preview():
    from noctua.producers.external.social_post import SocialPostProducer
    Producer.objects.create(key="social_post", kind="social_post", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="launch tweet", producer_key="social_post", budget=_budget())
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:LINKEDIN.LINKEDIN_CREATE_POST", "args": {"text": "hi"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"url": "https://linkedin.com/p/1"}, "error": ""}},
        {"step_id": "s2", "kind": "tool",
         "payload": {"name": "composio:TWITTER.TWITTER_CREATE_TWEET", "args": {"text": "hi"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"url": "https://x.com/p/2"}, "error": ""}},
    ], rendered_md="")

    p = SocialPostProducer()
    a = p.finalize(m, sandbox=None)
    assert a.kind == "social_post"
    assert a.queue_state == "pending"
    posted = a.preview.get("posted_urls", [])
    assert "https://linkedin.com/p/1" in posted
    assert "https://x.com/p/2" in posted
