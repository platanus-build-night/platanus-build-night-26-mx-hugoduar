# noctua/tools/fabricator.py
import hashlib
import json
import importlib.util
from pathlib import Path
from django.conf import settings
from anthropic import Anthropic
# Deliberately using Sandbox (bridge network) rather than NestedSandbox (network=none)
# because fabrication validation requires pip install. The tradeoff is accepted: a
# hostile tool could reach the network during validation, but it cannot persist beyond
# the container teardown, and the tool only graduates after human review.
# Future: pre-bake a psycopg2-equipped image and switch back to NestedSandbox.
from noctua.sandbox.manager import Sandbox
from noctua.core.models import Tool
from noctua.tools.base import ToolEntry, ToolResult

PROMPT = Path(__file__).parent / "prompts" / "seed_db.md"


class ToolFabricator:
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def fabricate(self, name: str, signature: dict, mission_id: int, context: dict | None = None) -> ToolEntry:
        if name != "seed_db":
            raise NotImplementedError(f"only seed_db is implemented in MVP, got: {name}")
        prompt = PROMPT.read_text()
        resp = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            system=prompt,
            messages=[{"role": "user", "content": f"Signature: {json.dumps(signature)}\nContext: {json.dumps(context or {})}"}],
        )
        source = resp.content[0].text
        source_hash = hashlib.sha256(source.encode()).hexdigest()[:12]
        out_dir = settings.NOCTUA_TOOLS_DIR / "fabricated" / source_hash
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{name}.py"
        out_file.write_text(source)

        # Validate in a Sandbox container (bridge network so pip install works).
        # repo_url=None skips the git/gh install branch — boots fast.
        ns = Sandbox()
        ns.boot("python:3.12-slim", None)
        try:
            ns.exec(["pip", "install", "-q", "psycopg2-binary"], timeout=120)
            # Write to /tmp (not /work) — Docker put_archive cannot write into tmpfs mounts.
            ns.write_file("/tmp/tool.py", source.encode())
            r = ns.exec(["python", "/tmp/tool.py", json.dumps({"rows": 0})], timeout=30)
            if r.exit_code != 0:
                raise RuntimeError(f"fabrication validation failed: {r.stderr}")
        finally:
            ns.teardown()

        tool_row = Tool.objects.create(
            name=name,
            signature=signature,
            source_path=str(out_file),
            source_hash=source_hash,
            status="fabricated_sandbox_only",
            fabricated_by_mission_id=mission_id,
        )
        spec = importlib.util.spec_from_file_location(name, str(out_file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return ToolEntry(
            name=name,
            signature=signature,
            status="fabricated_sandbox_only",
            callable=mod.call,
            source_path=str(out_file),
        )
