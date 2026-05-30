# stub — full version in Task 22
class _Stub:
    def on_approve(self, artifact): pass
    def on_promote(self, artifact): pass

class SocialPostStub(_Stub):
    key = "social_post"
    kind = "social_post"

class ClinicalAnalysisStub(_Stub):
    key = "clinical_analysis"
    kind = "analysis"

class DiagnosticStub(_Stub):
    key = "diagnostic"
    kind = "diagnostic"
