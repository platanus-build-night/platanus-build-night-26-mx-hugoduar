import json
from pathlib import Path
from noctua.core.models import Mission, Plan, Producer
from noctua.runner.llm import call_with_cache, PLANNER_MODEL

PLAN_PROMPT = Path(__file__).parent / "prompts" / "plan.md"


def plan_for_mission(mission: Mission) -> tuple[Plan, int]:
    """Return (Plan, total_tokens_used)."""
    system = PLAN_PROMPT.read_text()
    rubric = Producer.objects.get(key=mission.producer_key).rubric_md
    user = f"""Mission:
Goal: {mission.goal}
Repo: {mission.repo_url}
Issue: {mission.issue_url}
Inputs: {json.dumps(mission.inputs)}
Success criteria: {mission.success_criteria}

Producer rubric:
{rubric}
"""
    resp = call_with_cache([{"role": "user", "content": user}], system, PLANNER_MODEL)
    text = resp.content[0].text.strip()
    # be lenient with code fences
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if text.startswith("json") else text
    obj = json.loads(text)
    next_version = mission.plans.count() + 1
    plan = Plan.objects.create(
        mission=mission,
        version=next_version,
        steps=[{**s, "status": "pending", "attempt": 0, "result": None} for s in obj["steps"]],
        rendered_md=obj.get("rendered_md", ""),
    )
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    return plan, tokens
