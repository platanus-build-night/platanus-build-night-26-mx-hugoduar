from django.core.management.base import BaseCommand
from noctua.core.models import Mission, Artifact
from noctua.producers.registry import get_producer


class Command(BaseCommand):
    help = "Create canned artifacts per stub producer (idempotent via per-slug dedup)."

    def handle(self, *args, **kwargs):
        for key in ("social_post", "clinical_analysis", "diagnostic", "cad", "tool_demo"):
            m, _ = Mission.objects.get_or_create(
                goal=f"stub-demo-{key}",
                defaults={"producer_key": key, "repo_url": "", "budget": {}, "state": "succeeded"},
            )
            # The existence check is now per-slug inside the stub's finalize,
            # so we always call finalize and it handles dedup.
            producer = get_producer(key)
            producer.finalize(m)
            self.stdout.write(f"seeded stub artifacts for {key}")
