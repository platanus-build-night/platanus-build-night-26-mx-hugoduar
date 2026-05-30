import pytest
from noctua.runner.llm import call_with_cache


def test_call_with_cache_raises_on_missing_key(settings):
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(RuntimeError) as exc:
        call_with_cache(
            messages=[{"role": "user", "content": "hi"}],
            system="x",
            model="claude-opus-4-7",
        )
    assert "ANTHROPIC_API_KEY is empty" in str(exc.value)
