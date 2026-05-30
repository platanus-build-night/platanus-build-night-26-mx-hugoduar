"""Pre-baked demo: service intake → diagnostic artifact.

  ./manage.py demo_brake_squeal
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import build_payload, post_signal


TITLE = "Service intake — 2019 Honda Civic brake squeal"
GOAL = (
    "Customer report: 2019 Honda Civic LX, 78,400 miles. High-pitched squeal "
    "when applying the brakes at low speed (under 25 mph), intermittent — "
    "happens maybe one stop in three. Goes away on harder braking. No "
    "vibration through the pedal, no pulling to one side, no warning lights. "
    "Front pads + rotors replaced eight months ago at a chain shop. The "
    "customer says it started about three weeks ago and is getting more "
    "frequent.\n\n"
    "Produce: a structured diagnostic write-up including (a) the top three "
    "likely causes ranked by probability, (b) the specific checks the tech "
    "should perform to confirm, (c) a parts/labor estimate range for each "
    "likely fix, and (d) what to tell the customer at intake."
)


class Command(BaseCommand):
    help = "Demo: mechanic diagnostic — brake squeal on a 2019 Civic."

    def handle(self, *args, **opts):
        payload = build_payload(kind="diagnostic", title=TITLE, goal=GOAL)
        post_signal(payload, stdout=self.stdout, style=self.style)
