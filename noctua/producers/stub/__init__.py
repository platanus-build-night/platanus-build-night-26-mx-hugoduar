import json
from pathlib import Path
from noctua.core.models import Mission, Artifact

FIXTURES = Path(__file__).parent / "fixtures"


class _Stub:
    def on_approve(self, artifact): pass
    def on_promote(self, artifact): pass
    def finalize(self, mission, sandbox=None):
        data = json.loads((FIXTURES / f"{self.fixture}.json").read_text())
        return Artifact.objects.create(
            mission=mission, producer_key=self.key, kind=self.kind,
            uri=data["uri"], preview=data["preview"], provenance={},
            validation=data["validation"], queue_state="pending",
        )


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
