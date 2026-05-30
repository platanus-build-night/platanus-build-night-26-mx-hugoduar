import pytest
from unittest.mock import MagicMock
from noctua.integrations.composio import (
    ComposioToolAdapter,
    ComposioAuthError,
    ExecutionResult,
    ActionSpec,
)
from noctua.tools.base import ToolResult


@pytest.fixture
def fake_client():
    c = MagicMock()
    c.get_action_spec.return_value = ActionSpec(
        name="LINKEDIN_CREATE_POST",
        description="",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    )
    return c


def test_lookup_returns_tool_entry_with_composio_status(fake_client):
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    assert entry.name == "composio:LINKEDIN.LINKEDIN_CREATE_POST"
    assert entry.status == "composio"
    assert entry.signature == {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }


def test_lookup_caches_entries(fake_client):
    adapter = ComposioToolAdapter(client=fake_client)
    e1 = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    e2 = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    assert e1 is e2


def test_lookup_raises_on_malformed_name(fake_client):
    adapter = ComposioToolAdapter(client=fake_client)
    with pytest.raises(ValueError, match="malformed composio tool name"):
        adapter.lookup("composio:NO_DOT_HERE")
    with pytest.raises(ValueError, match="malformed composio tool name"):
        adapter.lookup("LINKEDIN.CREATE_POST")  # missing prefix


def test_call_returns_tool_result_on_success(fake_client, settings):
    settings.COMPOSIO_USER_ID = "noctua_default"
    fake_client.execute.return_value = ExecutionResult(
        successful=True, data={"url": "https://x/1"}, error=""
    )
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({"text": "hello"}, sandbox=None)
    assert isinstance(r, ToolResult)
    assert r.ok is True
    assert r.value == {"url": "https://x/1"}
    fake_client.execute.assert_called_once_with(
        slug="LINKEDIN_CREATE_POST",
        arguments={"text": "hello"},
        user_id="noctua_default",
    )


def test_call_returns_failed_tool_result_on_sdk_error(fake_client):
    fake_client.execute.return_value = ExecutionResult(
        successful=False, data=None, error="rate limited"
    )
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({}, sandbox=None)
    assert r.ok is False
    assert r.error == "rate limited"


@pytest.mark.django_db
def test_call_flips_connection_to_expired_on_auth_error(fake_client):
    from noctua.core.models import Connection  # will exist after Task 4
    Connection.objects.create(
        toolkit="LINKEDIN", status="active", composio_conn_id="c1",
    )
    fake_client.execute.side_effect = ComposioAuthError("token revoked")
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({}, sandbox=None)
    assert r.ok is False
    assert r.error == "connection_expired:LINKEDIN"
    Connection.objects.get(toolkit="LINKEDIN")  # still there
    assert Connection.objects.get(toolkit="LINKEDIN").status == "expired"


def test_call_returns_failed_result_on_unexpected_exception(fake_client):
    fake_client.execute.side_effect = ValueError("boom")
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({}, sandbox=None)
    assert r.ok is False
    assert "boom" in r.error


@pytest.mark.django_db
def test_list_actions_for_producer_returns_entries_for_active_toolkits_only(fake_client):
    from noctua.core.models import Connection
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    Connection.objects.create(toolkit="TWITTER", status="expired", composio_conn_id="c2")
    # BLUESKY: no row at all

    class FakeProducer:
        composio_actions = {
            "LINKEDIN": ["LINKEDIN_CREATE_POST"],
            "TWITTER": ["TWITTER_CREATE_TWEET"],
            "BLUESKY": ["BLUESKY_CREATE_POST"],
        }

    adapter = ComposioToolAdapter(client=fake_client)
    entries = adapter.list_actions_for_producer(FakeProducer())
    names = {e.name for e in entries}
    assert names == {"composio:LINKEDIN.LINKEDIN_CREATE_POST"}


@pytest.mark.django_db
def test_list_actions_for_producer_returns_empty_when_no_composio_actions(fake_client):
    class FakeProducer:
        pass  # no composio_actions attr
    adapter = ComposioToolAdapter(client=fake_client)
    assert adapter.list_actions_for_producer(FakeProducer()) == []
