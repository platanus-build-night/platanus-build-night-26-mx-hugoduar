"""Pre-baked demo: tool fabrication → tool artifact.

  ./manage.py demo_csv_table
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import build_payload, post_signal


TITLE = "Fabricate: csv_to_markdown"
GOAL = (
    "Build a sandbox-only tool named `csv_to_markdown` that converts a CSV "
    "string into a GitHub-flavored markdown table.\n\n"
    "Signature: `csv_to_markdown(csv_text: str, has_header: bool = True) -> str`.\n\n"
    "Requirements:\n"
    "  • If `has_header=True`, the first row is the header; otherwise "
    "synthesize headers as `col1`, `col2`, ….\n"
    "  • Handle quoted fields containing commas and embedded newlines.\n"
    "  • Pad each column to the widest cell in that column for readability.\n"
    "  • Right-align columns where every non-header cell parses as a number; "
    "left-align otherwise.\n"
    "  • Include a `---` separator row with alignment markers (`---`, `:---`, "
    "`---:`).\n\n"
    "Include three unit tests: a vanilla case, a header-less case, and a case "
    "with quoted-field commas. No external dependencies — stdlib only."
)


class Command(BaseCommand):
    help = "Demo: tool fabrication — csv_to_markdown helper."

    def handle(self, *args, **opts):
        payload = build_payload(kind="tool", title=TITLE, goal=GOAL)
        post_signal(payload, stdout=self.stdout, style=self.style)
