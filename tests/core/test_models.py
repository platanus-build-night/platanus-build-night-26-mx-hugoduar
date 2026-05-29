import pytest
from noctua.core.models import Mission, Plan, SandboxRun, Tool, Artifact, Producer

pytestmark = pytest.mark.django_db

def test_mission_defaults():
    m = Mission.objects.create(
        goal="Add /healthz",
        producer_key="pr",
        repo_url="https://github.com/x/y",
        budget={"max_wall_seconds": 1800, "max_tokens": 200000, "max_tool_calls": 50},
    )
    assert m.state == "queued"
    assert m.spent == {"wall_seconds": 0, "tokens": 0, "tool_calls": 0}
    assert m.auto_act is False

def test_plan_versioning():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    p1 = Plan.objects.create(mission=m, version=1, steps=[], rendered_md="")
    p2 = Plan.objects.create(mission=m, version=2, steps=[], rendered_md="")
    assert p1.version == 1 and p2.version == 2

def test_tool_status_choices():
    t = Tool.objects.create(name="seed_db", signature={}, source_path="x", source_hash="h", status="fabricated_sandbox_only")
    assert t.status == "fabricated_sandbox_only"

def test_artifact_links_tool():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    t = Tool.objects.create(name="seed_db", signature={}, source_path="x", source_hash="h", status="fabricated_sandbox_only")
    a = Artifact.objects.create(mission=m, producer_key="pr", kind="tool", uri="file://x", preview={}, provenance={}, validation={}, queue_state="pending", tool=t)
    assert a.tool_id == t.id
