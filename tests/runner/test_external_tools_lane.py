import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Plan, Artifact
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db


CANNED_PLAN = '{"steps":[{"step_id":"s1","kind":"tool","payload":{"name":"composio:LINKEDIN.LINKEDIN_CREATE_POST","args":{"text":"hi"}}}],"rendered_md":"x"}'


@pytest.fixture
def external_producer():
    """A minimal producer with external_tools=True, registered in the cache."""
    from noctua.tools.base import ToolResult
    from noctua.producers import registry as preg

    class _P:
        key = "test_external"
        kind = "social_post"
        external_tools = True
        content_only = False
        required_toolkits = ["LINKEDIN"]
        optional_toolkits: list[str] = []
        composio_actions = {"LINKEDIN": ["LINKEDIN_CREATE_POST"]}

        def execute_step(self, step, sandbox, mission):
            return ToolResult(ok=True)

        def finalize(self, mission, sandbox=None):
            return Artifact.objects.create(
                mission=mission, producer_key=self.key, kind=self.kind,
                uri=f"draft://{self.key}/{mission.id}", queue_state="pending",
            )

        def on_approve(self, a): pass
        def on_promote(self, a): pass

    p = _P()
    preg._cache["test_external"] = p
    yield p
    preg._cache.pop("test_external", None)


def test_external_tools_lane_skips_sandbox(external_producer):
    Producer.objects.create(key="test_external", kind="social_post", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="test_external", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})

    planner_resp = MagicMock()
    planner_resp.content = [MagicMock(text=CANNED_PLAN)]
    planner_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

    # Fake adapter so composio:* lookups don't need real Composio
    from noctua.tools.base import ToolEntry, ToolResult
    fake_entry = ToolEntry(
        name="composio:LINKEDIN.LINKEDIN_CREATE_POST", signature={}, status="composio",
        callable=lambda a, s: ToolResult(ok=True, value={"url": "https://x/1"}),
    )

    with patch("noctua.runner.planner.call_with_cache", return_value=planner_resp), \
         patch("noctua.runner.tasks.Sandbox") as Sandbox, \
         patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
        Adapter.return_value.lookup.return_value = fake_entry
        Adapter.return_value.list_actions_for_producer.return_value = [fake_entry]
        run_mission(m.id)
        Sandbox.assert_not_called()  # boot/teardown never happens

    m.refresh_from_db()
    assert m.state == "succeeded"
    assert Artifact.objects.filter(mission=m).exists()


def test_external_tools_lane_archives_on_failure(external_producer, monkeypatch):
    Producer.objects.create(key="test_external", kind="social_post", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="test_external", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})

    with patch("noctua.runner.tasks.plan_for_mission", side_effect=RuntimeError("planner_broke")):
        run_mission(m.id)

    m.refresh_from_db()
    assert m.state == "failed"
    assert "planner_broke" in m.state_reason
