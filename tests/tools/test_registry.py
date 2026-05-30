# tests/tools/test_registry.py
import pytest
from noctua.tools.registry import ToolRegistry
from noctua.core.models import Tool

pytestmark = pytest.mark.django_db

def test_lookup_precedence(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    # hardcoded bundled tool always available
    reg = ToolRegistry()
    t = reg.lookup("read_file", current_mission_id=1)
    assert t is not None
    assert t.status == "hardcoded"

def test_graduated_wins_over_hardcoded(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    (tmp_path / "graduated").mkdir()
    (tmp_path / "graduated" / "read_file.py").write_text("def call(args, sandbox): return 'graduated'\n")
    Tool.objects.create(name="read_file", signature={}, source_path=str(tmp_path / "graduated/read_file.py"), source_hash="h", status="graduated")
    reg = ToolRegistry()
    t = reg.lookup("read_file", current_mission_id=1)
    assert t.status == "graduated"
