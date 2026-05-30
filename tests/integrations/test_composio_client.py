import pytest
from unittest.mock import MagicMock, patch
from composio import exceptions as composio_exc
from noctua.integrations.composio import (
    ComposioClient,
    ExecutionResult,
    ActionSpec,
    ConnectionInit,
    ComposioAuthError,
)


def test_init_raises_when_api_key_missing(settings):
    settings.COMPOSIO_API_KEY = ""
    with pytest.raises(RuntimeError, match="COMPOSIO_API_KEY is empty"):
        ComposioClient()


def test_init_constructs_sdk_when_api_key_present(settings):
    settings.COMPOSIO_API_KEY = "test-key"
    with patch("noctua.integrations.composio.Composio") as sdk:
        c = ComposioClient()
        sdk.assert_called_once_with(api_key="test-key")
        assert c._sdk is sdk.return_value


def test_execute_returns_successful_result(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.execute.return_value = MagicMock(
            successful=True, data={"url": "https://x/123"}, error=None
        )
        c = ComposioClient()
        r = c.execute(slug="LINKEDIN_CREATE_POST", arguments={"text": "hi"}, user_id="u")
        assert isinstance(r, ExecutionResult)
        assert r.successful is True
        assert r.data == {"url": "https://x/123"}
        assert r.error == ""


def test_execute_returns_failed_result_with_error(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.execute.return_value = MagicMock(
            successful=False, data=None, error="rate limited"
        )
        c = ComposioClient()
        r = c.execute(slug="X", arguments={}, user_id="u")
        assert r.successful is False
        assert r.error == "rate limited"


def test_execute_translates_api_key_error(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        # ApiKeyError is raised when the configured API key is invalid.
        sdk.return_value.tools.execute.side_effect = composio_exc.ApiKeyError("invalid key")
        c = ComposioClient()
        with pytest.raises(ComposioAuthError):
            c.execute(slug="X", arguments={}, user_id="u")


def test_execute_translates_connected_account_error(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        # ConnectedAccountNotFoundError is a subclass of ConnectedAccountError —
        # covers expired/revoked OAuth tokens.
        sdk.return_value.tools.execute.side_effect = composio_exc.ConnectedAccountNotFoundError(
            "connected account expired"
        )
        c = ComposioClient()
        with pytest.raises(ComposioAuthError):
            c.execute(slug="X", arguments={}, user_id="u")


def test_execute_translates_http_401(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        # HTTPError with status 401 is the raw HTTP auth rejection.
        sdk.return_value.tools.execute.side_effect = composio_exc.HTTPError(
            "401 Unauthorized", status_code=401
        )
        c = ComposioClient()
        with pytest.raises(ComposioAuthError):
            c.execute(slug="X", arguments={}, user_id="u")


def test_execute_translates_http_403(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.execute.side_effect = composio_exc.HTTPError(
            "403 Forbidden", status_code=403
        )
        c = ComposioClient()
        with pytest.raises(ComposioAuthError):
            c.execute(slug="X", arguments={}, user_id="u")


def test_execute_does_not_swallow_non_auth_http_error(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        # A 500 HTTPError must NOT be translated — it should propagate as-is.
        sdk.return_value.tools.execute.side_effect = composio_exc.HTTPError(
            "Internal Server Error", status_code=500
        )
        c = ComposioClient()
        with pytest.raises(composio_exc.HTTPError):
            c.execute(slug="X", arguments={}, user_id="u")


def test_get_action_spec_caches_per_slug(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.get.return_value = MagicMock(
            name="LINKEDIN_CREATE_POST",
            description="Create a LinkedIn post",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        )
        c = ComposioClient()
        s1 = c.get_action_spec("LINKEDIN_CREATE_POST")
        s2 = c.get_action_spec("LINKEDIN_CREATE_POST")
        assert isinstance(s1, ActionSpec)
        assert s1.input_schema == {"type": "object", "properties": {"text": {"type": "string"}}}
        # Cached — SDK called only once
        sdk.return_value.tools.get.assert_called_once()
        assert s1 is s2


def test_initiate_connection_returns_redirect_url_and_id(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.connected_accounts.initiate.return_value = MagicMock(
            redirect_url="https://oauth.example/x", id="conn_abc"
        )
        c = ComposioClient()
        r = c.initiate_connection(toolkit="LINKEDIN", user_id="u")
        assert isinstance(r, ConnectionInit)
        assert r.redirect_url == "https://oauth.example/x"
        assert r.composio_conn_id == "conn_abc"


def test_fetch_connection_status_returns_status_string(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.connected_accounts.get.return_value = MagicMock(status="ACTIVE")
        c = ComposioClient()
        assert c.fetch_connection_status("conn_abc") == "ACTIVE"
