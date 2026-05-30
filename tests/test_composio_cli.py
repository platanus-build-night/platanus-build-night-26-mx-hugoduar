import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from noctua.cli import cli

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("NOCTUA_API_URL", "http://api.test")
    monkeypatch.setenv("NOCTUA_API_TOKEN", "test-token")


def test_composio_list_calls_api(env):
    fake_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    fake_resp.json.return_value = [
        {"toolkit": "LINKEDIN", "status": "active", "composio_conn_id": "c1",
         "connected_at": "2026-05-29T00:00:00+00:00", "last_error": ""},
    ]
    with patch("noctua.cli.httpx") as httpx:
        httpx.get.return_value = fake_resp
        result = CliRunner().invoke(cli, ["composio", "list"])
    assert result.exit_code == 0, result.output
    assert "LINKEDIN" in result.output
    assert "active" in result.output


def test_composio_connect_polls_until_active(env):
    initiate_resp = MagicMock(status_code=201, raise_for_status=MagicMock())
    initiate_resp.json.return_value = {
        "toolkit": "LINKEDIN", "redirect_url": "https://o.example/x",
        "composio_conn_id": "c1", "status": "pending",
    }
    pending_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    pending_resp.json.return_value = {
        "toolkit": "LINKEDIN", "status": "pending", "composio_conn_id": "c1",
        "connected_at": None, "last_error": "",
    }
    active_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    active_resp.json.return_value = {
        "toolkit": "LINKEDIN", "status": "active", "composio_conn_id": "c1",
        "connected_at": "2026-05-29T00:00:00+00:00", "last_error": "",
    }
    with patch("noctua.cli.httpx") as httpx, patch("noctua.cli.time.sleep"):
        # POST sequence: initiate, then refresh (pending), then refresh (active)
        httpx.post.side_effect = [initiate_resp, pending_resp, active_resp]
        result = CliRunner().invoke(
            cli, ["composio", "connect", "LINKEDIN", "--timeout-seconds", "60"],
        )
    assert result.exit_code == 0, result.output
    assert "https://o.example/x" in result.output
    assert "active" in result.output.lower()


def test_composio_connect_times_out_when_never_active(env):
    initiate_resp = MagicMock(status_code=201, raise_for_status=MagicMock())
    initiate_resp.json.return_value = {
        "toolkit": "LINKEDIN", "redirect_url": "https://o.example/x",
        "composio_conn_id": "c1", "status": "pending",
    }
    pending_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    pending_resp.json.return_value = {
        "toolkit": "LINKEDIN", "status": "pending", "composio_conn_id": "c1",
        "connected_at": None, "last_error": "",
    }
    # Many pendings so the loop times out
    with patch("noctua.cli.httpx") as httpx, patch("noctua.cli.time.sleep"), \
         patch("noctua.cli.time.monotonic", side_effect=[0.0, 0.0, 100.0]):
        httpx.post.side_effect = [initiate_resp] + [pending_resp] * 5
        result = CliRunner().invoke(
            cli, ["composio", "connect", "LINKEDIN", "--timeout-seconds", "30"],
        )
    assert result.exit_code != 0
    assert "timed out" in result.output.lower()


def test_composio_disconnect_calls_api(env):
    disconnect_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    disconnect_resp.json.return_value = {
        "toolkit": "LINKEDIN", "status": "revoked", "composio_conn_id": "c1",
        "connected_at": None, "last_error": "",
    }
    with patch("noctua.cli.httpx") as httpx:
        httpx.post.return_value = disconnect_resp
        result = CliRunner().invoke(cli, ["composio", "disconnect", "LINKEDIN"])
    assert result.exit_code == 0, result.output
    assert "revoked" in result.output.lower()
