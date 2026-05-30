"""Base class for the per-kind mock_* convenience commands.

The aliases share the same UX: positional words become the goal (so demos
don't need quotes), `--sample-index N` picks a fixture, `--title` overrides
the queue label. Code-only flags (`--repo-url`, `--issue-url`) live on the
code subclass.
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import (
    DEFAULT_REPO,
    SAMPLES,
    build_payload,
    pick_sample,
    post_signal,
)


class MockAliasCommand(BaseCommand):
    """Shared scaffolding. Subclasses set `kind` and customize `help`."""

    kind: str = ""

    def add_arguments(self, parser):
        parser.add_argument(
            "goal_words",
            nargs="*",
            help="Free-form goal text. If omitted, a sample is used.",
        )
        parser.add_argument(
            "--sample-index",
            type=int,
            default=None,
            help=f"Pick sample 0..{len(SAMPLES[self.kind]) - 1} instead of random.",
        )
        parser.add_argument("--title", default=None, help="Override the queue title.")
        parser.add_argument(
            "--external-id",
            default=None,
            help="Override the external id (otherwise random; used for dedupe).",
        )

    def handle(self, *args, **opts):
        sample_title, sample_goal = pick_sample(self.kind, opts["sample_index"])
        goal_words = opts.get("goal_words") or []
        goal = " ".join(goal_words).strip() or sample_goal
        title = opts["title"] or (goal[:80] if goal_words else sample_title)
        payload = build_payload(
            kind=self.kind,
            title=title,
            goal=goal,
            external_id=opts["external_id"],
        )
        post_signal(payload, stdout=self.stdout, style=self.style)


class MockCodeAliasCommand(MockAliasCommand):
    """Code-kind variant: also accepts --repo-url and --issue-url."""

    kind = "code"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--repo-url",
            default=None,
            help=f"Repo URL (defaults to {DEFAULT_REPO}).",
        )
        parser.add_argument("--issue-url", default="", help="Optional GitHub issue URL.")

    def handle(self, *args, **opts):
        sample_title, sample_goal = pick_sample(self.kind, opts["sample_index"])
        goal_words = opts.get("goal_words") or []
        goal = " ".join(goal_words).strip() or sample_goal
        title = opts["title"] or (goal[:80] if goal_words else sample_title)
        payload = build_payload(
            kind=self.kind,
            title=title,
            goal=goal,
            external_id=opts["external_id"],
            repo_url=opts["repo_url"],
            issue_url=opts["issue_url"],
        )
        post_signal(payload, stdout=self.stdout, style=self.style)
