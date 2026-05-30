"""Pre-baked demo: launch tweet → social_post artifact.

  ./manage.py demo_launch_tweet
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import build_payload, post_signal


TITLE = "Launch tweet — Noctua public beta"
GOAL = (
    "Draft a launch tweet (≤270 characters) announcing Noctua's public beta. "
    "Frame: an overnight AI artifact factory — one mission in, one reviewable "
    "artifact out by morning. Highlight Docker sandbox isolation and human-in-"
    "the-loop review. No emojis, no hashtags, no exclamation marks. End with "
    "one soft call to action. Output only the tweet text — no preamble."
)


class Command(BaseCommand):
    help = "Demo: social post — Noctua public-beta launch tweet."

    def handle(self, *args, **opts):
        payload = build_payload(kind="social", title=TITLE, goal=GOAL)
        post_signal(payload, stdout=self.stdout, style=self.style)
