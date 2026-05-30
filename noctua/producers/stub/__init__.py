import json
from pathlib import Path
from noctua.core.models import Mission, Artifact

FIXTURES = Path(__file__).parent / "fixtures"


class _Stub:
    fixture: str = ""  # filename stem (e.g. "social_post")
    key: str = ""
    kind: str = ""

    def on_approve(self, artifact):
        pass

    def on_promote(self, artifact):
        pass

    def finalize(self, mission, sandbox=None):
        """Create one Artifact per fixture entry, skipping ones we already wrote."""
        data = json.loads((FIXTURES / f"{self.fixture}.json").read_text())
        if isinstance(data, dict):
            data = [data]  # backwards-compat
        created = []
        for entry in data:
            slug = entry.get("slug", entry["uri"])
            existing = Artifact.objects.filter(
                mission=mission, producer_key=self.key, kind=self.kind,
                provenance__slug=slug,
            ).first()
            if existing:
                continue
            artifact = Artifact.objects.create(
                mission=mission, producer_key=self.key, kind=self.kind,
                uri=entry["uri"],
                preview=entry["preview"],
                provenance={"slug": slug, **entry.get("provenance", {})},
                validation=entry["validation"],
                queue_state="pending",
            )
            created.append(artifact)
        return created[0] if created else None


class SocialPostStub(_Stub):
    key = "social_post"
    kind = "social_post"
    fixture = "social_post"


class ClinicalAnalysisStub(_Stub):
    key = "clinical_analysis"
    kind = "analysis"
    fixture = "clinical"


class DiagnosticStub(_Stub):
    key = "diagnostic"
    kind = "diagnostic"
    fixture = "diagnostic"


class CADStub(_Stub):
    key = "cad"
    kind = "cad"
    fixture = "cad"


class ToolStub(_Stub):
    key = "tool_demo"
    kind = "tool"
    fixture = "tools"
