from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class ClinicalAnalysisProducer(ExternalToolsProducer):
    key = "clinical_analysis"
    kind = "analysis"
    required_toolkits = ["NOTION"]
    optional_toolkits = ["GMAIL"]
    composio_actions = {
        "NOTION": ["NOTION_FETCH_PAGE", "NOTION_CREATE_PAGE", "NOTION_APPEND_BLOCK"],
        "GMAIL":  ["GMAIL_SEND_EMAIL"],
    }
    edit_prompt_file = "clinical_analysis.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        analysis_url = ""
        email_sent_to = ""
        for s in steps:
            v = s.get("result") if isinstance(s.get("result"), dict) else None
            if not v:
                continue
            if "page_url" in v:
                analysis_url = v["page_url"]
            if "to" in v and "subject" in v:
                email_sent_to = v["to"]
        return {
            "goal": mission.goal,
            "analysis_url": analysis_url,
            "email_sent_to": email_sent_to,
            "steps": steps,
        }
