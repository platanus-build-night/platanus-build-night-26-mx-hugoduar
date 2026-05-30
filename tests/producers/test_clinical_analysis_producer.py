import pytest
from noctua.core.models import Mission, Producer, Plan

pytestmark = pytest.mark.django_db


def test_clinical_analysis_manifest():
    from noctua.producers.external.clinical_analysis import ClinicalAnalysisProducer
    p = ClinicalAnalysisProducer()
    assert p.key == "clinical_analysis"
    assert p.kind == "analysis"
    assert p.required_toolkits == ["NOTION"]
    assert p.optional_toolkits == ["GMAIL"]
    assert "NOTION_FETCH_PAGE" in p.composio_actions["NOTION"]
    assert "NOTION_CREATE_PAGE" in p.composio_actions["NOTION"]


def test_clinical_analysis_finalize_includes_analysis_uri_in_artifact():
    from noctua.producers.external.clinical_analysis import ClinicalAnalysisProducer
    Producer.objects.create(key="clinical_analysis", kind="analysis", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="analyze patient X", producer_key="clinical_analysis", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:NOTION.NOTION_FETCH_PAGE", "args": {"page_id": "p1"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"content": "notes..."}, "error": ""}},
        {"step_id": "s2", "kind": "edit", "payload": {"goal": "summarize"},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": "analysis text", "error": ""}},
        {"step_id": "s3", "kind": "tool",
         "payload": {"name": "composio:NOTION.NOTION_CREATE_PAGE", "args": {}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"page_url": "https://notion.so/p/new"}, "error": ""}},
    ], rendered_md="")

    p = ClinicalAnalysisProducer()
    a = p.finalize(m, sandbox=None)
    assert a.kind == "analysis"
    assert a.preview["analysis_url"] == "https://notion.so/p/new"
