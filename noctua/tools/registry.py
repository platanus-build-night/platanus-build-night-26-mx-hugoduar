# noctua/tools/registry.py
import importlib.util
from pathlib import Path
from django.conf import settings
from noctua.core.models import Tool
from noctua.tools.base import ToolEntry
from noctua.tools.bundled import BUNDLED


class ToolRegistry:
    def __init__(self):
        self._bundled = {t.name: t for t in BUNDLED}

    def lookup(self, name: str, current_mission_id: int | None = None) -> ToolEntry | None:
        # 1. graduated
        graduated = Tool.objects.filter(name=name, status="graduated").first()
        if graduated:
            return self._load_from_disk(graduated)
        # 2. hardcoded
        if name in self._bundled:
            return self._bundled[name]
        # 3. fabricated for THIS mission
        if current_mission_id:
            fab = Tool.objects.filter(name=name, status="fabricated_sandbox_only", fabricated_by_mission_id=current_mission_id).first()
            if fab:
                return self._load_from_disk(fab)
        return None

    def _load_from_disk(self, tool_row: Tool) -> ToolEntry:
        spec = importlib.util.spec_from_file_location(tool_row.name, tool_row.source_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return ToolEntry(name=tool_row.name, signature=tool_row.signature, status=tool_row.status, callable=mod.call, source_path=tool_row.source_path)

    def all_available(self, current_mission_id: int | None = None) -> list[ToolEntry]:
        entries = list(self._bundled.values())
        for row in Tool.objects.filter(status="graduated"):
            entries.append(self._load_from_disk(row))
        if current_mission_id:
            for row in Tool.objects.filter(status="fabricated_sandbox_only", fabricated_by_mission_id=current_mission_id):
                entries.append(self._load_from_disk(row))
        return entries
