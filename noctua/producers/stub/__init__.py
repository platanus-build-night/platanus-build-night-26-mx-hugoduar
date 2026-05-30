"""Content-generation producers.

These producers don't touch code or run a sandbox. They ask Claude to draft
the artifact in a kind-specific shape, then land it in the queue. The
mission lifecycle in `noctua.runner.tasks.run_mission` checks the
`content_only = True` class attribute to skip the sandbox + planner +
executor.
"""

import json
import re
from pathlib import Path
from noctua.core.models import Mission, Artifact, Producer
from noctua.runner.llm import call_with_cache, PLANNER_MODEL
from noctua.runner.budget import increment_spent


PROMPTS = Path(__file__).parent / "prompts"


class ContentProducer:
    """Base for kind-specific content producers.

    Subclasses set `key`, `kind`, `system_prompt_file` (filename under PROMPTS),
    and `expected_validation_keys` (what they expect Claude to put in
    artifact.validation).
    """

    content_only: bool = True
    key: str = ""
    kind: str = ""
    system_prompt_file: str = ""

    def on_approve(self, artifact: Artifact) -> None:
        # No external side-effect for content artifacts.
        pass

    def on_promote(self, artifact: Artifact) -> None:
        pass

    def generate(self, mission: Mission) -> dict:
        """Ask Claude for an artifact spec. Returns a dict shaped like:
        {uri: str, preview: {title, snippet}, validation: {...}}.
        """
        system = (PROMPTS / self.system_prompt_file).read_text()
        rubric = ""
        try:
            rubric = Producer.objects.get(key=self.key).rubric_md
        except Producer.DoesNotExist:
            pass
        user = (
            f"Goal:\n{mission.goal}\n\n"
            f"Inputs:\n{json.dumps(mission.inputs or {})}\n\n"
            f"Producer rubric:\n{rubric}\n"
        )
        resp = call_with_cache(
            messages=[{"role": "user", "content": user}],
            system=system,
            model=PLANNER_MODEL,
            max_tokens=2000,
        )
        # Count tokens against the mission budget.
        try:
            increment_spent(
                mission.id,
                tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            )
        except Exception:
            pass
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            # Strip code fences leniently.
            text = text.strip("`")
            text = text.split("\n", 1)[1] if text.startswith("json") else text
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"{self.key} producer: Claude did not return valid JSON.\n"
                f"First 500 chars: {text[:500]}\n"
                f"Error: {e}"
            )

    def finalize(self, mission: Mission, sandbox=None) -> Artifact:
        spec = self.generate(mission)
        return Artifact.objects.create(
            mission=mission,
            producer_key=self.key,
            kind=self.kind,
            uri=spec.get("uri", f"draft://{self.key}/{mission.id}"),
            preview=spec.get("preview", {}),
            provenance={"generated_by": self.key},
            validation=spec.get("validation", {}),
            queue_state="pending",
        )


# --- Concrete content producers ------------------------------------------


class SocialPostStub(ContentProducer):
    key = "social_post"
    kind = "social_post"
    system_prompt_file = "social_post.md"


class ClinicalAnalysisStub(ContentProducer):
    key = "clinical_analysis"
    kind = "analysis"
    system_prompt_file = "clinical.md"


class DiagnosticStub(ContentProducer):
    key = "diagnostic"
    kind = "diagnostic"
    system_prompt_file = "diagnostic.md"


class CADStub(ContentProducer):
    key = "cad"
    kind = "cad"
    system_prompt_file = "cad.md"


class ToolStub(ContentProducer):
    """Placeholder so the entry-point still resolves; not invoked via CLI."""
    key = "tool_demo"
    kind = "tool"
    system_prompt_file = "tool_demo.md"
