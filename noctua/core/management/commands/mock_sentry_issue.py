import json
import os
from django.core.management.base import BaseCommand


# Samples reference code that ACTUALLY exists in the noctua-demo-app
# fixture repo so Claude can find what the error describes.
# Demo repo currently has: src/app.py with FastAPI app + @app.get("/")
#                          tests/test_app.py with test_root
_SAMPLE_TITLES = [
    (
        "AttributeError: 'NoneType' object has no attribute 'lower'",
        "src/app.py in root",
    ),
    (
        "RuntimeError: missing required header 'X-Request-Id'",
        "src/app.py in root",
    ),
    (
        "AssertionError: expected status 200, got 500",
        "tests/test_app.py in test_root",
    ),
    (
        "TypeError: root() got an unexpected keyword argument 'name'",
        "src/app.py in root",
    ),
    (
        "ValueError: invalid query parameter 'limit'",
        "src/app.py in root",
    ),
]


class Command(BaseCommand):
    help = "Inject a mock Sentry issue into the signal pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--title", default=None, help="Override the title (otherwise picks a sample).")
        parser.add_argument("--culprit", default=None)
        parser.add_argument("--level", default="error", choices=["debug", "info", "warning", "error", "fatal"])
        parser.add_argument("--project-slug", default="noctua-demo-app")
        parser.add_argument("--issue-id", default=None, help="Override the Sentry issue id (otherwise random).")
        parser.add_argument("--action", default="created", choices=["created", "resolved", "ignored", "assigned"])

    def handle(self, *args, **opts):
        import random
        import string
        import httpx

        title, culprit_default = random.choice(_SAMPLE_TITLES)
        title = opts["title"] or title
        culprit = opts["culprit"] or culprit_default
        level = opts["level"]
        slug = opts["project_slug"]
        action = opts["action"]
        external_id = opts["issue_id"] or "".join(random.choices(string.digits, k=8))

        payload = {
            "action": action,
            "data": {
                "issue": {
                    "id": external_id,
                    "title": title,
                    "level": level,
                    "culprit": culprit,
                    "project": {"name": slug, "slug": slug},
                    "permalink": f"https://sentry.example/{slug}/issues/{external_id}/",
                    "metadata": {"type": title.split(":")[0], "value": title.split(":", 1)[-1].strip()},
                },
            },
        }

        api_url = os.environ.get("NOCTUA_API_URL", "http://127.0.0.1:8000")
        token = os.environ.get("NOCTUA_API_TOKEN", "")

        self.stdout.write(self.style.NOTICE(f"POST {api_url}/api/signals/sentry"))
        self.stdout.write(json.dumps(payload, indent=2))

        r = httpx.post(
            f"{api_url}/api/signals/sentry",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        self.stdout.write(self.style.SUCCESS(f"\nResponse: {r.status_code}"))
        self.stdout.write(json.dumps(r.json(), indent=2))
