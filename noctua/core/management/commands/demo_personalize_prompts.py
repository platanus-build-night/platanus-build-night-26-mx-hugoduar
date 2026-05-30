"""Pre-baked demo: feature request → code PR.

  ./manage.py demo_personalize_prompts
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import build_payload, post_signal


TITLE = "Personalize the root response"
GOAL = (
    "Update src/app.py so the root endpoint accepts an optional `name` query "
    "parameter. When `name` is provided, return {\"message\": f\"Hello, {name}!\"}; "
    "otherwise return the current response. Add tests in tests/test_app.py covering "
    "both the personalized and anonymous cases. Keep the change minimal — no new "
    "files, no dependencies."
)


class Command(BaseCommand):
    help = "Demo: code PR — personalize the demo-app's root endpoint."

    def handle(self, *args, **opts):
        payload = build_payload(kind="code", title=TITLE, goal=GOAL)
        post_signal(payload, stdout=self.stdout, style=self.style)
