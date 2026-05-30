# noctua/runner/executor.py
from noctua.core.models import Mission, Plan
from noctua.tools.registry import ToolRegistry
from noctua.runner.budget import increment_spent, check_budget

MAX_RETRIES_PER_STEP = 3


class NeedsInput(Exception):
    def __init__(self, prompt):
        self.prompt = prompt


class StoppedByBudget(Exception):
    def __init__(self, field):
        self.field = field


def execute_plan(mission: Mission, plan: Plan, sandbox) -> list[dict]:
    registry = ToolRegistry()
    results = []
    for step in plan.steps:
        if step["status"] == "succeeded":
            results.append(step)
            continue
        breach = check_budget(mission.id)
        if breach:
            raise StoppedByBudget(breach)
        for attempt in range(MAX_RETRIES_PER_STEP):
            step["attempt"] = attempt + 1
            try:
                if step["kind"] == "tool":
                    name = step["payload"]["name"]
                    args = step["payload"].get("args", {})
                    entry = registry.lookup(name, current_mission_id=mission.id)
                    if entry is None:
                        from noctua.tools.fabricator import ToolFabricator
                        entry = ToolFabricator().fabricate(name, {"args_schema": {}, "returns_schema": {}}, mission_id=mission.id)
                    result = entry.callable(args, sandbox)
                    increment_spent(mission.id, tool_calls=1)
                    step["result"] = {"ok": result.ok, "value": result.value, "error": result.error}
                    step["status"] = "succeeded" if result.ok else "failed"
                elif step["kind"] == "exec":
                    r = sandbox.exec(step["payload"]["cmd"], timeout=step["payload"].get("timeout", 60))
                    step["result"] = {"ok": r.exit_code == 0, "value": r.stdout, "error": r.stderr}
                    step["status"] = "succeeded" if r.exit_code == 0 else "failed"
                elif step["kind"] == "edit":
                    # delegated to producer; see Task 21
                    raise NotImplementedError("edit dispatched via producer")
                else:
                    raise ValueError(f"unknown step kind: {step['kind']}")
                if step["status"] == "succeeded":
                    break
            except (NeedsInput, StoppedByBudget):
                raise
            except Exception as e:
                step["status"] = "failed"
                step["result"] = {"ok": False, "error": str(e)}
        results.append(step)
        plan.steps = plan.steps  # mark JSONB dirty
        plan.save(update_fields=["steps"])
    return results
