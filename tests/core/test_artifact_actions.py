import pytest
from django.test import Client
from noctua.core.models import Mission, Artifact, Tool

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def token(settings):
    settings.NOCTUA_API_TOKEN = "tt"

def auth():
    return {"HTTP_AUTHORIZATION": "Bearer tt"}

@pytest.fixture
def pr_artifact():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    return Artifact.objects.create(mission=m, producer_key="pr", kind="pr", uri="https://github.com/x/y/pull/1", preview={}, provenance={}, validation={}, queue_state="pending")

@pytest.fixture
def tool_artifact():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    t = Tool.objects.create(name="seed_db", signature={}, source_path="tools/fabricated/h/seed_db.py", source_hash="h", status="fabricated_sandbox_only")
    return Artifact.objects.create(mission=m, producer_key="pr", kind="tool", uri="file://...", preview={}, provenance={}, validation={}, queue_state="pending", tool=t)

def test_approve_pr_calls_on_approve(pr_artifact, mocker):
    spy = mocker.patch("noctua.producers.pr.PRProducer.on_approve")
    c = Client()
    r = c.post(f"/api/artifacts/{pr_artifact.id}/approve", **auth())
    assert r.status_code == 200
    assert r.json()["queue_state"] == "approved"
    assert spy.called

def test_reject_pr(pr_artifact):
    c = Client()
    r = c.post(f"/api/artifacts/{pr_artifact.id}/reject", **auth())
    assert r.status_code == 200
    assert r.json()["queue_state"] == "rejected"

def test_graduate_tool(tool_artifact, tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    (tmp_path / "fabricated/h").mkdir(parents=True)
    (tmp_path / "fabricated/h/seed_db.py").write_text("def call(args, sandbox): pass\n")
    tool_artifact.tool.source_path = str(tmp_path / "fabricated/h/seed_db.py")
    tool_artifact.tool.save()
    c = Client()
    r = c.post(f"/api/artifacts/{tool_artifact.id}/approve", **auth())
    assert r.status_code == 200
    tool_artifact.tool.refresh_from_db()
    assert tool_artifact.tool.status == "graduated"
    assert (tmp_path / "graduated/seed_db.py").exists()
