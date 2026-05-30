from anthropic import Anthropic
from django.conf import settings

PLANNER_MODEL = "claude-sonnet-4-6"
CODER_MODEL = "claude-opus-4-7"


def client():
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def call_with_cache(messages, system, model, max_tokens=4000, tools=None):
    """Call Claude with prompt caching enabled on the system block."""
    kw = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
    }
    if tools:
        kw["tools"] = tools
    return client().messages.create(**kw)
