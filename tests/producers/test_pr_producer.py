import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer
from noctua.producers.pr import PRProducer

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    Producer.objects.create(key="pr", kind="pr", rubric_md="rubric", default_budget={})


def test_edit_loop_terminates_on_DONE(setup):
    m = Mission.objects.create(
        goal="g",
        producer_key="pr",
        repo_url="r",
        issue_url="",
        budget={"max_wall_seconds": 60, "max_tokens": 100000, "max_tool_calls": 50},
    )
    sandbox = MagicMock()
    sandbox.exec.return_value = MagicMock(stdout="", exit_code=0, stderr="")
    fake_resp = MagicMock()
    fake_resp.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.text = "DONE"
    fake_resp.content = [text_block]
    fake_resp.usage = MagicMock(input_tokens=10, output_tokens=10)
    p = PRProducer()
    with patch("noctua.producers.pr.call_with_cache", return_value=fake_resp):
        r = p._edit_loop(m, sandbox)
    assert r.ok is True
