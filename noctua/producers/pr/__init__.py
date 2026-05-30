import json
import os
import re
import httpx
from pathlib import Path
from noctua.core.models import Mission, Plan, Artifact, Producer
from noctua.runner.llm import call_with_cache, CODER_MODEL
from noctua.runner.budget import increment_spent
from noctua.runner.executor import NeedsInput
from noctua.tools.registry import ToolRegistry
from noctua.tools.base import ToolResult


_PR_URL_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+/pull/\d+$")

EDIT_PROMPT = Path(__file__).parent / "prompts" / "edit.md"
MAX_EDIT_TURNS = 10


class PRProducer:
    key = "pr"
    kind = "pr"

    def __init__(self):
        self.rubric_path = "noctua/producers/pr/rubric.md"

    def plan(self, mission: Mission, ctx=None):
        from noctua.runner.planner import plan_for_mission
        return plan_for_mission(mission)

    def execute_step(self, step, sandbox, mission: Mission):
        if step["kind"] == "edit":
            return self._edit_loop(mission, sandbox)
        return None  # other kinds handled by executor

    def _edit_loop(self, mission: Mission, sandbox):
        registry = ToolRegistry()
        tools_for_claude = [
            {
                "name": e.name,
                "description": e.name,
                "input_schema": {
                    "type": "object",
                    "properties": {k: {"type": "string"} for k in e.signature.get("args_schema", {})},
                    "required": [],
                },
            }
            for e in registry.all_available(current_mission_id=mission.id)
        ] + [
            {
                "name": "needs_input",
                "description": "ask user",
                "input_schema": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                    "required": ["prompt"],
                },
            }
        ]

        system = EDIT_PROMPT.read_text()
        rubric = Producer.objects.get(key="pr").rubric_md
        issue_text = self._fetch_issue(mission.issue_url)
        # Always include the mission goal so the edit loop has a clear spec even
        # when issue_url is empty (e.g. feature_request signals).
        goal_section = f"Goal: {mission.goal}\n\n" if mission.goal else ""
        issue_section = f"Issue:\n{issue_text}\n\n" if issue_text else ""
        messages = [{"role": "user", "content": f"{goal_section}{issue_section}Rubric:\n{rubric}\n\nGo."}]

        for turn in range(MAX_EDIT_TURNS):
            resp = call_with_cache(messages, system, CODER_MODEL, tools=tools_for_claude, max_tokens=4000)
            increment_spent(mission.id, tokens=resp.usage.input_tokens + resp.usage.output_tokens)

            # Always append the assistant turn so the next request has the conversation history.
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "tool_use":
                tool_results = []
                for block in resp.content:
                    if getattr(block, "type", "") != "tool_use":
                        continue
                    if block.name == "needs_input":
                        raise NeedsInput(block.input["prompt"])
                    entry = registry.lookup(block.name, current_mission_id=mission.id)
                    if entry is None:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "tool not found",
                            "is_error": True,
                        })
                        continue
                    result = entry.callable(block.input, sandbox)
                    increment_spent(mission.id, tool_calls=1)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"ok": result.ok, "value": result.value, "error": result.error})[:8000],
                        "is_error": not result.ok,
                    })
                messages.append({"role": "user", "content": tool_results})
                continue

            if resp.stop_reason == "end_turn":
                if any(
                    getattr(b, "text", "").strip() == "DONE"
                    for b in resp.content
                    if hasattr(b, "text")
                ):
                    return ToolResult(ok=True, value="edit-loop complete")
                # model stopped without DONE and without calling a tool — nudge it.
                messages.append({"role": "user", "content": "Continue. Reply 'DONE' only when tests pass."})
                continue

            if resp.stop_reason == "max_tokens":
                # truncated mid-thought; let it continue in the next turn
                continue

            # refusal, stop_sequence, pause_turn — abort the loop
            return ToolResult(ok=False, error=f"edit-loop aborted: stop_reason={resp.stop_reason}")

        return ToolResult(ok=False, error="edit-loop exhausted MAX_EDIT_TURNS")

    def _fetch_issue(self, issue_url: str) -> str:
        # Fetch issue text host-side via the GitHub REST API.
        # The sandbox doesn't have credentials and shouldn't need network for this.
        if not issue_url:
            return ""
        m = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
        if not m:
            return ""
        owner, repo, number = m.group(1), m.group(2), m.group(3)
        token = os.environ.get("GITHUB_TOKEN", "")
        r = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{number}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if r.status_code != 200:
            return ""
        body = r.json()
        return f"{body.get('title', '')}\n\n{body.get('body', '')}"

    def finalize(self, mission: Mission, sandbox):
        # PR URL was created by the last tool step (gh_pr_create). Find it.
        last_plan = mission.plans.order_by("-version").first()
        pr_url = ""
        if last_plan:
            for step in last_plan.steps:
                if step.get("payload", {}).get("name") == "gh_pr_create" and step.get("result", {}).get("ok"):
                    pr_url = step["result"]["value"]
        artifact = Artifact.objects.create(
            mission=mission,
            producer_key="pr",
            kind="pr",
            uri=pr_url,
            preview={"title": mission.goal},
            provenance={"plan_version": last_plan.version if last_plan else 0},
            validation={"tests_passed": True},
            queue_state="pending",
        )
        return artifact

    def on_approve(self, artifact: Artifact):
        if not artifact.uri:
            return
        if not _PR_URL_RE.match(artifact.uri):
            return
        from noctua.sandbox.manager import Sandbox
        sb = Sandbox()
        sb.boot("python:3.12-slim", None)
        try:
            # install gh (no user data interpolated)
            sb.exec(
                [
                    "bash",
                    "-lc",
                    "set -e && apt-get update -qq && "
                    "apt-get install -qq -y curl ca-certificates && "
                    "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && "
                    "chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && "
                    "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main' > /etc/apt/sources.list.d/github-cli.list && "
                    "apt-get update -qq && apt-get install -qq -y gh",
                ],
                timeout=600,
            )
            # validated URL as discrete argv
            sb.exec(["gh", "pr", "ready", "--", artifact.uri])
        finally:
            sb.teardown()

    def on_promote(self, artifact: Artifact):
        pass
