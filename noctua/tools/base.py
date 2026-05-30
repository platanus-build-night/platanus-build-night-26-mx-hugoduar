# noctua/tools/base.py
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass
class ToolResult:
    ok: bool
    value: Any = None
    error: str = ""

class ToolCallable(Protocol):
    def __call__(self, args: dict, sandbox) -> ToolResult: ...

@dataclass
class ToolEntry:
    name: str
    signature: dict
    status: str  # 'hardcoded' | 'fabricated_sandbox_only' | 'graduated'
    callable: ToolCallable
    source_path: str = ""
