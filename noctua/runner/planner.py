import json
import re
from pathlib import Path
from noctua.core.models import Mission, Plan, Producer
from noctua.runner.llm import call_with_cache, PLANNER_MODEL

PLAN_PROMPT = Path(__file__).parent / "prompts" / "plan.md"

# Valid JSON string escapes per RFC 8259 §7: " \ / b f n r t uXXXX
_VALID_JSON_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _parse_plan_json(text: str) -> dict:
    """Parse Claude's plan output, repairing common escape mistakes.

    Claude sometimes emits stray single backslashes (e.g. inside regex
    literals or shell paths). Strict `json.loads` rejects them. We try
    strict first, then double up any backslash that's not a valid JSON
    escape and retry. If both fail, the original exception is raised.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if text.startswith("json") else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = _VALID_JSON_ESCAPE.sub(r"\\\\", text)
        return json.loads(repaired)


def plan_for_mission(mission: Mission, producer=None) -> tuple[Plan, int]:
    """Return (Plan, total_tokens_used).

    `producer` is forwarded to `ToolRegistry.all_available` so producer-specific
    composio tools appear in the planner's tool catalog. If None, only bundled
    and graduated tools are exposed.
    """
    system = PLAN_PROMPT.read_text()
    rubric = Producer.objects.get(key=mission.producer_key).rubric_md

    from noctua.tools.registry import ToolRegistry
    registry = ToolRegistry()
    available = registry.all_available(current_mission_id=mission.id, producer=producer)
    tool_catalog = "\n".join(
        f"- {e.name} ({e.status}): {e.signature}" for e in available
    )

    user = f"""Mission:
Goal: {mission.goal}
Repo: {mission.repo_url}
Issue: {mission.issue_url}
Inputs: {json.dumps(mission.inputs)}
Success criteria: {mission.success_criteria}

Producer rubric:
{rubric}

Available tools (use these exact names in step payload.name):
{tool_catalog}
"""
    resp = call_with_cache([{"role": "user", "content": user}], system, PLANNER_MODEL)
    text = resp.content[0].text.strip()
    obj = _parse_plan_json(text)
    next_version = mission.plans.count() + 1
    plan = Plan.objects.create(
        mission=mission,
        version=next_version,
        steps=[{**s, "status": "pending", "attempt": 0, "result": None} for s in obj["steps"]],
        rendered_md=obj.get("rendered_md", ""),
    )
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    return plan, tokens
