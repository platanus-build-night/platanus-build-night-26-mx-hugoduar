"""Base class for producers that drive external SaaS tools via Composio.

These producers:
- declare required and optional toolkits (the API pre-flights `required`)
- declare a composio_actions map (toolkit → list of action slugs) exposed to the planner
- use the external_tools=True lane in run_mission (no sandbox boot)
- handle `kind: "edit"` steps by running a pure Claude call (no shell, sandbox=None)
"""

from __future__ import annotations

import json
from pathlib import Path
from noctua.core.models import Mission, Artifact, Producer
from noctua.runner.llm import call_with_cache, PLANNER_MODEL
from noctua.runner.budget import increment_spent
from noctua.tools.base import ToolResult


class ExternalToolsProducer:
    """Subclass and set the class attributes. See SocialPostProducer for an example."""

    # Lifecycle hints for run_mission
    external_tools: bool = True
    content_only: bool = False

    # Manifest
    key: str = ""
    kind: str = ""              # one of ARTIFACT_KINDS
    required_toolkits: list[str] = []   # at-least-one semantics
    optional_toolkits: list[str] = []   # not pre-flight-checked
    composio_actions: dict[str, list[str]] = {}   # planner-visible catalog

    # Prompt for the Claude edit step (relative to noctua/producers/external/prompts/)
    edit_prompt_file: str = ""

    # ---- Lifecycle hooks (no-op defaults) ----

    def on_approve(self, artifact: Artifact) -> None: pass
    def on_promote(self, artifact: Artifact) -> None: pass

    # ---- Edit step: Claude call without a sandbox ----

    def execute_step(self, step: dict, sandbox, mission: Mission) -> ToolResult:
        """Default edit-step handler: read the edit prompt, ask Claude, return text.

        The result.value is the raw Claude text; subclasses may override to parse
        it differently. `sandbox` is always None for external_tools producers.
        """
        if not self.edit_prompt_file:
            return ToolResult(ok=False, error=f"{self.key}: no edit_prompt_file set")
        prompts_dir = Path(__file__).parent / "prompts"
        system = (prompts_dir / self.edit_prompt_file).read_text()
        context = step.get("payload", {})
        # Roll prior tool-step results into the user message so Claude has them.
        prior = self._collect_prior_results(mission, step)
        user = (
            f"Step goal:\n{context.get('goal', '')}\n\n"
            f"Step context:\n{json.dumps(context, indent=2)}\n\n"
            f"Prior step results:\n{json.dumps(prior, indent=2)}\n"
        )
        try:
            resp = call_with_cache(
                messages=[{"role": "user", "content": user}],
                system=system, model=PLANNER_MODEL, max_tokens=4000,
            )
        except Exception as e:
            return ToolResult(ok=False, error=str(e))
        try:
            increment_spent(mission.id, tokens=resp.usage.input_tokens + resp.usage.output_tokens)
        except Exception:
            pass
        text = resp.content[0].text
        return ToolResult(ok=True, value=text)

    def _collect_prior_results(self, mission: Mission, current_step: dict) -> list[dict]:
        plan = mission.plans.order_by("-version").first()
        if not plan:
            return []
        out = []
        for s in plan.steps:
            if s.get("step_id") == current_step.get("step_id"):
                break
            if s.get("status") == "succeeded":
                out.append({"step_id": s["step_id"], "result": s.get("result", {}).get("value")})
        return out

    # ---- Finalize: persist Artifact ----

    def finalize(self, mission: Mission, sandbox=None) -> Artifact:
        """Default: bundle all step results into the Artifact preview."""
        plan = mission.plans.order_by("-version").first()
        step_summary = []
        if plan:
            for s in plan.steps:
                step_summary.append({
                    "step_id": s.get("step_id"),
                    "kind": s.get("kind"),
                    "status": s.get("status"),
                    "result": s.get("result", {}).get("value"),
                })
        return Artifact.objects.create(
            mission=mission,
            producer_key=self.key,
            kind=self.kind,
            uri=self._artifact_uri(mission, step_summary),
            preview=self._artifact_preview(mission, step_summary),
            provenance={"generated_by": self.key, "external_tools": True},
            validation={"steps": len(step_summary)},
            queue_state="pending",
        )

    def _artifact_uri(self, mission: Mission, steps: list[dict]) -> str:
        return f"draft://{self.key}/{mission.id}"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        return {"goal": mission.goal, "steps": steps}
