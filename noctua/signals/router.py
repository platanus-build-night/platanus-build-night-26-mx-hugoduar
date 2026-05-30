"""Signal → Mission router.

Pluggable per-source. Each router decides whether to ignore the signal,
fail (cannot proceed), or route to a Mission with a chosen producer key
and goal. The router does NOT enqueue the mission — it returns a plan
the caller (API view) acts on, so retries and idempotency are easier.
"""
import logging
import re
from dataclasses import dataclass
from typing import Protocol

from noctua.core.models import Producer
from noctua.runner.llm import call_with_cache

logger = logging.getLogger(__name__)

CLASSIFIER_MODEL = "claude-haiku-4-5"

_REPO_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?")


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


# --- Mock router ------------------------------------------------------------

# Maps the payload `kind` field to (producer_key, artifact_label).
# `kind` is the public name we accept on the wire; producer_key is the entry
# point key registered in pyproject.toml.
_MOCK_KIND_TO_PRODUCER = {
    "code": "pr",
    "tool": "tool_demo",
    "social": "social_post",
    "clinical": "clinical_analysis",
    "diagnostic": "diagnostic",
    "cad": "cad",
}


class MockRouter:
    """Dispatch a synthetic signal to any producer.

    Designed for local dev and demos: lets you fire a signal that simulates
    "something from the outside world arrived" without standing up Sentry,
    Zendesk, etc. The payload tells the router which artifact kind to produce.

    Expected payload shape:
      {
        "kind": "code" | "tool" | "social" | "clinical" | "diagnostic" | "cad",
        "external_id": "abc123",          # used for idempotent dedupe at the
                                          # endpoint layer; not required here
        "title": "short label",           # optional, surfaced in the queue
        "goal": "free-form instruction",  # required — what the producer does
        "repo_url": "https://...",        # required for kind=code
        "issue_url": "https://...",       # optional, for kind=code
        "inputs": { ... }                 # passed through to Mission.inputs
      }
    """

    source = "mock"

    def decide(self, payload: dict) -> RouteDecision:
        kind = (payload.get("kind") or "").strip().lower()
        if not kind:
            return RouteDecision(action="ignore", reason="missing 'kind' in payload")

        producer_key = _MOCK_KIND_TO_PRODUCER.get(kind)
        if not producer_key:
            return RouteDecision(
                action="ignore",
                reason=f"unknown kind {kind!r} (expected one of {sorted(_MOCK_KIND_TO_PRODUCER)})",
            )

        goal = (payload.get("goal") or "").strip()
        if not goal:
            return RouteDecision(action="ignore", reason="missing 'goal' in payload")

        repo_url = (payload.get("repo_url") or "").strip()
        if kind == "code" and not repo_url:
            return RouteDecision(
                action="ignore",
                reason="kind='code' requires a 'repo_url'",
            )

        inputs = dict(payload.get("inputs") or {})
        inputs.setdefault("mock_kind", kind)

        return RouteDecision(
            action="route",
            reason=f"mock signal for kind={kind!r}",
            producer_key=producer_key,
            goal=goal,
            repo_url=repo_url,
            issue_url=(payload.get("issue_url") or "").strip(),
            inputs=inputs,
        )


# --- Feature request router -------------------------------------------------

class FeatureRequestRouter:
    """Route a feature request directly to a PR mission.

    Payload shape: {goal, repo_url?, base?}
    """
    source = "feature_request"

    def decide(self, payload: dict) -> RouteDecision:
        goal = (payload.get("goal") or "").strip()
        if not goal:
            return RouteDecision(action="ignore", reason="missing goal")
        repo_url = payload.get("repo_url") or "https://github.com/hugoduar/noctua-demo-app"
        return RouteDecision(
            action="route",
            reason="feature request",
            producer_key="pr",
            goal=goal,
            repo_url=repo_url,
            issue_url="",
            inputs={"base": payload.get("base", "main")},
        )


# --- WhatsApp router --------------------------------------------------------

class WhatsAppRouter:
    """Classify an inbound WhatsApp message into producer + goal via Haiku."""

    source = "whatsapp"

    def decide(self, payload: dict) -> RouteDecision:
        valid_keys = set(Producer.objects.values_list("key", flat=True))
        if not valid_keys:
            return RouteDecision(action="ignore", reason="no producers registered")

        system = self._build_system_prompt(valid_keys)
        user = self._build_user_message(payload)
        tools = [{
            "name": "route",
            "description": "Pick a producer and draft the mission goal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "producer_key": {"type": "string", "enum": sorted(valid_keys)},
                    "goal": {"type": "string"},
                },
                "required": ["producer_key", "goal"],
            },
        }]

        try:
            resp = call_with_cache(
                messages=[{"role": "user", "content": user}],
                system=system,
                model=CLASSIFIER_MODEL,
                max_tokens=1024,
                tools=tools,
            )
        except Exception as exc:
            logger.warning("whatsapp classifier call failed: %s", exc)
            return RouteDecision(
                action="ignore",
                reason=f"classifier unavailable: {exc}",
            )

        if resp.stop_reason != "tool_use":
            text = ""
            for block in resp.content or []:
                if getattr(block, "type", None) == "text":
                    text = block.text or ""
                    break
            return RouteDecision(
                action="ignore",
                reason=f"classifier declined: {text[:200]}",
            )

        tool_input = {}
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                tool_input = block.input
                break

        producer_key = tool_input.get("producer_key", "")
        goal = tool_input.get("goal", "")
        if producer_key not in valid_keys:
            return RouteDecision(
                action="ignore",
                reason=f"unknown producer {producer_key!r}",
            )
        if not goal.strip():
            return RouteDecision(
                action="ignore",
                reason="classifier returned empty goal",
            )

        repo_url = ""
        if producer_key == "pr":
            text_blob = " ".join([
                payload.get("text", ""),
                payload.get("caption", ""),
                payload.get("transcript") or "",
            ])
            m = _REPO_RE.search(text_blob)
            if not m:
                return RouteDecision(
                    action="ignore",
                    reason="pr producer requires a GitHub repo URL in the message",
                )
            repo_url = m.group(0)

        inputs = {
            "wa_from": payload.get("wa_from", ""),
            "media_paths": payload.get("media_paths", []),
            "transcript": payload.get("transcript"),
            "kind": payload.get("kind", "text"),
        }

        return RouteDecision(
            action="route",
            reason="whatsapp classifier",
            producer_key=producer_key,
            goal=goal,
            repo_url=repo_url,
            inputs=inputs,
        )

    def _build_system_prompt(self, valid_keys: set[str]) -> str:
        lines = [
            "You route inbound WhatsApp messages to one of these producers.",
            "Each producer accepts a free-text 'goal'. Use the most appropriate producer.",
            "If the message is off-topic chatter (greetings, jokes, spam), respond with text instead of calling the route tool.",
            "",
            "Producers:",
        ]
        for p in Producer.objects.filter(key__in=valid_keys).order_by("key"):
            rubric = (p.rubric_md or "(no rubric)").strip().split("\n")[0]
            lines.append(f"- {p.key}: {rubric}")
        lines.append("")
        lines.append("Use the 'route' tool with the chosen producer_key and a clear goal.")
        return "\n".join(lines)

    def _build_user_message(self, payload: dict) -> str:
        parts = [f"kind: {payload.get('kind', 'text')}"]
        if payload.get("text"):
            parts.append(f"text: {payload['text']}")
        if payload.get("caption"):
            parts.append(f"caption: {payload['caption']}")
        if payload.get("transcript"):
            parts.append(f"transcript: {payload['transcript']}")
        if payload.get("media_paths"):
            parts.append(f"media_count: {len(payload['media_paths'])}")
        return "\n".join(parts)


_ROUTERS: dict[str, SignalRouter] = {
    "sentry": SentryRouter(),
    "mock": MockRouter(),
    "feature_request": FeatureRequestRouter(),
    "whatsapp": WhatsAppRouter(),
}


def route_signal(source: str, payload: dict) -> RouteDecision:
    """Public entry point; looks up the source's router."""
    router = _ROUTERS.get(source)
    if router is None:
        return RouteDecision(action="ignore", reason=f"no router for source {source!r}")
    return router.decide(payload)
