from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Deprecated: stub fixture-based seeding has been replaced with real "
        "content-producer missions. Use `noctua run --producer <kind> --goal "
        "'...'` to land real artifacts in each tab."
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(
            "seed_stub_artifacts is now a no-op.\n"
            "To populate the queue with real artifacts, run:\n"
            "  noctua run --producer social_post --goal 'Draft a launch thread for Noctua v0.4'\n"
            "  noctua run --producer clinical_analysis --goal 'Summarize last week\\'s safety signals'\n"
            "  noctua run --producer diagnostic --goal 'Brake wear advisory for a high-mileage Civic'\n"
            "  noctua run --producer cad --goal 'Sketch a replacement turbo bracket'\n"
        )
