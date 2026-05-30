"""Inject a synthetic mock signal — routes to any producer.

  ./manage.py mock_signal --kind cad
  ./manage.py mock_signal --kind social --sample-index 2
  ./manage.py mock_signal --kind code --goal "Add a /metrics endpoint"

Hits POST /api/signals/mock so the full pipeline (Signal row → router →
Mission → Celery dispatch) runs the same way an external webhook would.
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import (
    DEFAULT_REPO,
    SAMPLES,
    build_payload,
    pick_sample,
    post_signal,
)


class Command(BaseCommand):
    help = "Inject a mock signal that routes to any artifact-producing producer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kind",
            required=True,
            choices=sorted(SAMPLES.keys()),
            help="Which artifact kind to produce.",
        )
        parser.add_argument("--title", default=None, help="Override the sample title.")
        parser.add_argument("--goal", default=None, help="Override the sample goal.")
        parser.add_argument(
            "--sample-index",
            type=int,
            default=None,
            help="Pick a specific sample by index instead of random.",
        )
        parser.add_argument(
            "--repo-url",
            default=None,
            help=f"Repo URL (kind=code requires one; defaults to {DEFAULT_REPO}).",
        )
        parser.add_argument("--issue-url", default="", help="Optional issue URL (code only).")
        parser.add_argument(
            "--external-id",
            default=None,
            help="Override the external id (otherwise random; used for dedupe).",
        )

    def handle(self, *args, **opts):
        kind = opts["kind"]
        sample_title, sample_goal = pick_sample(kind, opts["sample_index"])
        payload = build_payload(
            kind=kind,
            title=opts["title"] or sample_title,
            goal=opts["goal"] or sample_goal,
            external_id=opts["external_id"],
            repo_url=opts["repo_url"],
            issue_url=opts["issue_url"],
        )
        post_signal(payload, stdout=self.stdout, style=self.style)
