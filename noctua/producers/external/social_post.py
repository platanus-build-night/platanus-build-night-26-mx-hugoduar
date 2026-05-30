from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class SocialPostProducer(ExternalToolsProducer):
    key = "social_post"
    kind = "social_post"
    required_toolkits = ["LINKEDIN", "TWITTER", "BLUESKY"]
    optional_toolkits: list[str] = []
    composio_actions = {
        "LINKEDIN": ["LINKEDIN_CREATE_POST"],
        "TWITTER":  ["TWITTER_CREATE_TWEET"],
        "BLUESKY":  ["BLUESKY_CREATE_POST"],
    }
    edit_prompt_file = "social_post.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        posted_urls = []
        for s in steps:
            if s.get("status") != "succeeded":
                continue
            value = s.get("result") or {}
            if isinstance(value, dict) and "url" in value:
                posted_urls.append(value["url"])
        return {
            "goal": mission.goal,
            "posted_urls": posted_urls,
            "steps": steps,
        }
