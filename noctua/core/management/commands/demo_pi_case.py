"""Pre-baked demo: CAD spec → cad artifact.

  ./manage.py demo_pi_case
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import build_payload, post_signal


TITLE = "Fanless aluminum case — Raspberry Pi 5"
GOAL = (
    "Design a fanless aluminum case for the Raspberry Pi 5 (8GB). The case "
    "body itself acts as the heatsink — direct thermal contact with the SoC "
    "via a copper or thermal-pad bridge, with fins on the top surface for "
    "passive convection.\n\n"
    "Constraints:\n"
    "  • External footprint ≤ 95 × 65 × 30 mm.\n"
    "  • Cutouts for USB-C power, dual micro-HDMI, 2× USB-A, ethernet, and "
    "the 40-pin GPIO header (with header passthrough so HATs still fit).\n"
    "  • Press-fit assembly — no screws if possible.\n"
    "  • Material: 6061 aluminum, anodized black.\n\n"
    "Produce: a structured geometric spec (dimensions, wall thicknesses, "
    "cutout coordinates, fin pitch + height), a bill of materials, and a "
    "short thermal justification (expected ΔT vs. the official Pi 5 active "
    "cooler under sustained 100% load)."
)


class Command(BaseCommand):
    help = "Demo: CAD spec — fanless Raspberry Pi 5 aluminum case."

    def handle(self, *args, **opts):
        payload = build_payload(kind="cad", title=TITLE, goal=GOAL)
        post_signal(payload, stdout=self.stdout, style=self.style)
