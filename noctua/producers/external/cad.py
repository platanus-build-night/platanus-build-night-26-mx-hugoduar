from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class CADProducer(ExternalToolsProducer):
    key = "cad"
    kind = "cad"
    required_toolkits = ["GOOGLEDRIVE"]
    optional_toolkits = ["NOTION"]
    composio_actions = {
        "GOOGLEDRIVE": ["GOOGLEDRIVE_DOWNLOAD_FILE", "GOOGLEDRIVE_UPLOAD_FILE"],
        "NOTION":      ["NOTION_APPEND_BLOCK"],
    }
    edit_prompt_file = "cad.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        file_url = ""
        for s in steps:
            v = s.get("result") if isinstance(s.get("result"), dict) else None
            if v and "file_url" in v:
                file_url = v["file_url"]
        return {
            "goal": mission.goal,
            "file_url": file_url,
            "steps": steps,
        }
