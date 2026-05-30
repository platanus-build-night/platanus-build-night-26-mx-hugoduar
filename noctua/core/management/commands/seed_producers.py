from pathlib import Path
from django.core.management.base import BaseCommand
from noctua.core.models import Producer

SEED = [
    ("pr", "pr", "noctua/producers/pr/rubric.md"),
    ("social_post", "social_post", "noctua/producers/external/rubrics/social_post.md"),
    ("clinical_analysis", "analysis", "noctua/producers/external/rubrics/clinical_analysis.md"),
    ("diagnostic", "diagnostic", "noctua/producers/external/rubrics/diagnostic.md"),
    ("cad", "cad", "noctua/producers/external/rubrics/cad.md"),
]

class Command(BaseCommand):
    help = "Seed Producer rows from on-disk rubric markdown files."

    def handle(self, *args, **kwargs):
        for key, kind, rubric_path in SEED:
            md = Path(rubric_path).read_text() if Path(rubric_path).exists() else ""
            obj, created = Producer.objects.update_or_create(
                key=key, defaults={"kind": kind, "rubric_md": md, "default_budget": {"max_wall_seconds": 1800, "max_tokens": 200000, "max_tool_calls": 50}}
            )
            self.stdout.write(f"{'created' if created else 'updated'} producer {key}")
