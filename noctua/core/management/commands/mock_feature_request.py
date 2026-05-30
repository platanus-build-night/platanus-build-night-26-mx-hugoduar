import os
import json
from django.core.management.base import BaseCommand


# Curated goals chosen because they're tractable against the
# noctua-demo-app fixture (FastAPI with @app.get("/") + tests/test_app.py).
# Each is small enough that the PR producer's edit loop has a high chance
# of finishing in one pass.
_SAMPLES = [
    'Add a /healthz endpoint that returns {"ok": true} on GET. Add a test for it.',
    'Add a /version endpoint that returns {"version": "0.1.0"}. Add a test for it.',
    "Add type hints to the root() function in src/app.py. No behavior change.",
    "Wrap src/app.py root() in a try/except that returns a 500 with the error message on failure. Add a test.",
    "Add a CONTRIBUTING.md at the repo root with a short 'how to run tests' section.",
]


class Command(BaseCommand):
    help = "Inject a feature_request signal to trigger a real code PR."

    def add_arguments(self, parser):
        parser.add_argument("--goal", default=None, help="Override the goal (otherwise picks a sample).")
        parser.add_argument("--repo-url", default=None, help="Override the repo URL.")
        parser.add_argument("--base", default="main")
        parser.add_argument("--sample-index", type=int, default=None, help="0..4 — pick a specific sample.")

    def handle(self, *args, **opts):
        import httpx
        import random

        if opts["sample_index"] is not None:
            goal = _SAMPLES[opts["sample_index"] % len(_SAMPLES)]
        else:
            goal = opts["goal"] or random.choice(_SAMPLES)

        payload = {
            "goal": goal,
            "base": opts["base"],
        }
        if opts["repo_url"]:
            payload["repo_url"] = opts["repo_url"]

        api_url = os.environ.get("NOCTUA_API_URL", "http://127.0.0.1:8000")
        token = os.environ.get("NOCTUA_API_TOKEN", "")

        self.stdout.write(self.style.NOTICE(f"POST {api_url}/api/signals/feature_request"))
        self.stdout.write(json.dumps(payload, indent=2))

        r = httpx.post(
            f"{api_url}/api/signals/feature_request",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        self.stdout.write(self.style.SUCCESS(f"\nResponse: {r.status_code}"))
        self.stdout.write(json.dumps(r.json(), indent=2))
