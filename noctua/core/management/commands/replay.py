from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Replay an archived mission to stdout."

    def add_arguments(self, parser):
        parser.add_argument("mission_id", type=int)

    def handle(self, *args, mission_id, **kwargs):
        base = settings.NOCTUA_ARCHIVE_DIR / str(mission_id)
        if not base.exists():
            self.stderr.write(f"No archive found for mission {mission_id} at {base}")
            return
        for name in ("mission.json", "plans.json", "artifacts.json"):
            self.stdout.write(f"=== {name} ===")
            f = base / name
            if f.exists():
                self.stdout.write(f.read_text())
            else:
                self.stdout.write("(missing)")
