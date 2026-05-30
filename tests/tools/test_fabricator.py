# tests/tools/test_fabricator.py
import json
import pytest
from unittest.mock import patch, MagicMock
from noctua.tools.fabricator import ToolFabricator
from noctua.core.models import Tool, Mission

pytestmark = pytest.mark.django_db

CANNED_SOURCE = '''
import json, sys
def call(args, sandbox=None):
    return {"inserted": int(args.get("rows", 0))}
if __name__ == "__main__":
    print(json.dumps(call(json.loads(sys.argv[1]))))
'''


def test_seed_db_fabrication(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    fab = ToolFabricator()
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=CANNED_SOURCE)]
    with patch.object(fab.client.messages, "create", return_value=fake_resp):
        m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
        entry = fab.fabricate("seed_db", {}, mission_id=m.id)
    assert entry.name == "seed_db"
    assert entry.status == "fabricated_sandbox_only"
    assert Tool.objects.filter(name="seed_db", status="fabricated_sandbox_only").exists()
    result = entry.callable({"rows": 3}, sandbox=None)
    assert result == {"inserted": 3}


def test_fabricate_unknown_tool_raises(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    fab = ToolFabricator()
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    with pytest.raises(NotImplementedError, match="only seed_db"):
        fab.fabricate("unknown_tool", {}, mission_id=m.id)
