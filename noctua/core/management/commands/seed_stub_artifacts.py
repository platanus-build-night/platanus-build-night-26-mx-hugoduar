from django.core.management.base import BaseCommand
from noctua.core.models import Mission, Artifact
from noctua.producers.registry import get_producer


class Command(BaseCommand):
    help = "Create one canned artifact per stub producer."

    def handle(self, *args, **kwargs):
        for key in ("social_post", "clinical_analysis", "diagnostic"):
            m, _ = Mission.objects.get_or_create(
                goal=f"stub-demo-{key}",
                defaults={"producer_key": key, "repo_url": "", "budget": {}, "state": "succeeded"},
            )
            if Artifact.objects.filter(mission=m).exists():
                self.stdout.write(f"skipped {key} (artifact already exists)")
                continue
            producer = get_producer(key)
            producer.finalize(m)
            self.stdout.write(f"seeded stub artifact for {key}")
