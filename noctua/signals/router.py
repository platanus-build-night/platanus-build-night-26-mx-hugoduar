"""Signal → Mission router.

Pluggable per-source. Each router decides whether to ignore the signal,
fail (cannot proceed), or route to a Mission with a chosen producer key
and goal. The router does NOT enqueue the mission — it returns a plan
the caller (API view) acts on, so retries and idempotency are easier.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RouteDecision:
    """The router's verdict for a signal."""
    action: str  # 'route', 'ignore'
    reason: str = ""
    # Populated only when action == 'route':
    producer_key: str = ""
    goal: str = ""
    repo_url: str = ""
    issue_url: str = ""
    inputs: dict | None = None


class SignalRouter(Protocol):
    source: str

    def decide(self, payload: dict) -> RouteDecision: ...


# --- Sentry router ----------------------------------------------------------

class SentryRouter:
    """Map a Sentry issue webhook payload to a mission.

    Sentry's webhook payload shape (simplified):
      {
        "action": "created" | "resolved" | ...,
        "data": {
          "issue": {
            "id": "12345",
            "title": "TypeError: 'NoneType' object is not iterable",
            "level": "error",
            "culprit": "noctua.runner.executor in execute_plan",
            "project": {"name": "noctua-demo-app", "slug": "noctua-demo-app"},
            "permalink": "https://sentry.io/...",
            "metadata": {"type": "TypeError", "value": "'NoneType' object is not iterable"}
          }
        }
      }

    Routing rules for MVP:
      - action != 'created'        → ignore (only fix newly-fired issues)
      - level == 'warning' or 'info' → ignore (only errors trigger missions)
      - otherwise                  → route to a `pr` mission against
        the demo repo with a goal describing the exception.
    """

    source = "sentry"

    def decide(self, payload: dict) -> RouteDecision:
        action = payload.get("action", "")
        if action and action != "created":
            return RouteDecision(action="ignore", reason=f"action={action!r} (only 'created' is routed)")

        issue = (payload.get("data") or {}).get("issue") or {}
        if not issue:
            return RouteDecision(action="ignore", reason="missing data.issue in payload")

        level = issue.get("level", "error")
        if level not in ("error", "fatal"):
            return RouteDecision(action="ignore", reason=f"level={level!r} below threshold (error/fatal)")

        title = issue.get("title") or "Untitled Sentry issue"
        culprit = issue.get("culprit") or ""
        permalink = issue.get("permalink") or ""

        # Resolve repo from project slug (MVP: hardcode mapping).
        # In production this would consult a project→repo mapping table.
        project_slug = (issue.get("project") or {}).get("slug", "")
        repo_map = {
            "noctua-demo-app": "https://github.com/hugoduar/noctua-demo-app",
        }
        repo_url = repo_map.get(project_slug, "")
        if not repo_url:
            return RouteDecision(
                action="ignore",
                reason=f"no repo configured for sentry project slug {project_slug!r}",
            )

        goal = (
            f"Investigate and fix Sentry error: \"{title}\". "
            f"Culprit: {culprit or 'unknown'}. "
            f"Reference: {permalink or '(no link)'}."
        )

        return RouteDecision(
            action="route",
            reason="sentry error in mapped project",
            producer_key="pr",
            goal=goal,
            repo_url=repo_url,
            issue_url="",  # Sentry issues aren't GH issues
            inputs={"sentry_issue_id": issue.get("id"), "level": level, "culprit": culprit},
        )


_ROUTERS: dict[str, SignalRouter] = {
    "sentry": SentryRouter(),
}


def route_signal(source: str, payload: dict) -> RouteDecision:
    """Public entry point; looks up the source's router."""
    router = _ROUTERS.get(source)
    if router is None:
        return RouteDecision(action="ignore", reason=f"no router for source {source!r}")
    return router.decide(payload)
