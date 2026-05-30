import pytest
from noctua.core.models import Mission, Producer, Plan

pytestmark = pytest.mark.django_db


def test_cad_manifest():
    from noctua.producers.external.cad import CADProducer
    p = CADProducer()
    assert p.key == "cad"
    assert p.kind == "cad"
    assert p.required_toolkits == ["GOOGLEDRIVE"]
    assert p.optional_toolkits == ["NOTION"]
    assert "GOOGLEDRIVE_DOWNLOAD_FILE" in p.composio_actions["GOOGLEDRIVE"]
    assert "GOOGLEDRIVE_UPLOAD_FILE" in p.composio_actions["GOOGLEDRIVE"]


def test_cad_finalize_includes_uploaded_file_url():
    from noctua.producers.external.cad import CADProducer
    Producer.objects.create(key="cad", kind="cad", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="bracket spec", producer_key="cad", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:GOOGLEDRIVE.GOOGLEDRIVE_DOWNLOAD_FILE", "args": {"file_id": "ref1"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"content": "ref dims..."}, "error": ""}},
        {"step_id": "s2", "kind": "edit", "payload": {"goal": "generate svg"},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": "<svg>...</svg>", "error": ""}},
        {"step_id": "s3", "kind": "tool",
         "payload": {"name": "composio:GOOGLEDRIVE.GOOGLEDRIVE_UPLOAD_FILE", "args": {}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"file_url": "https://drive.google.com/file/d/abc"}, "error": ""}},
    ], rendered_md="")

    p = CADProducer()
    a = p.finalize(m, sandbox=None)
    assert a.preview["file_url"] == "https://drive.google.com/file/d/abc"
