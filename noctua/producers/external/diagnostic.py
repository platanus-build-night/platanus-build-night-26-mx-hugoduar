from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class DiagnosticProducer(ExternalToolsProducer):
    key = "diagnostic"
    kind = "diagnostic"
    required_toolkits = ["LINEAR"]
    optional_toolkits = ["SLACK"]
    composio_actions = {
        "LINEAR": ["LINEAR_GET_ISSUE", "LINEAR_CREATE_COMMENT"],
        "SLACK":  ["SLACK_POST_MESSAGE"],
    }
    edit_prompt_file = "diagnostic.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        comment_url = ""
        slack_ts = ""
        for s in steps:
            v = s.get("result") if isinstance(s.get("result"), dict) else None
            if not v:
                continue
            if "comment_url" in v:
                comment_url = v["comment_url"]
            if "ts" in v:
                slack_ts = v["ts"]
        return {
            "goal": mission.goal,
            "comment_url": comment_url,
            "slack_ts": slack_ts,
            "steps": steps,
        }
