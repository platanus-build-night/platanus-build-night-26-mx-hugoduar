import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from noctua.core.models import Connection

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_headers(settings):
    settings.NOCTUA_API_TOKEN = "test-token"
    return {"HTTP_AUTHORIZATION": "Bearer test-token"}


def test_list_connections_empty(auth_headers):
    r = Client().get("/api/connections", **auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_connections_returns_all_rows(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    Connection.objects.create(toolkit="NOTION", status="pending", composio_conn_id="c2")
    r = Client().get("/api/connections", **auth_headers)
    assert r.status_code == 200
    bodies = {row["toolkit"]: row for row in r.json()}
    assert set(bodies.keys()) == {"LINKEDIN", "NOTION"}
    assert bodies["LINKEDIN"]["status"] == "active"


def test_initiate_creates_pending_row_and_returns_oauth_url(auth_headers, settings):
    settings.COMPOSIO_USER_ID = "noctua_default"
    with patch("noctua.core.api.get_client") as get_client:
        get_client.return_value.initiate_connection.return_value = MagicMock(
            redirect_url="https://oauth.example/x",
            composio_conn_id="conn_new",
            auth_config_id="ac_new",
        )
        r = Client().post("/api/connections/LINKEDIN/initiate", **auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["toolkit"] == "LINKEDIN"
    assert body["redirect_url"] == "https://oauth.example/x"
    assert body["composio_conn_id"] == "conn_new"
    assert body["status"] == "pending"
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.status == "pending"
    assert row.composio_conn_id == "conn_new"


def test_initiate_replaces_existing_row_for_same_toolkit(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="expired", composio_conn_id="old")
    with patch("noctua.core.api.get_client") as get_client:
        get_client.return_value.initiate_connection.return_value = MagicMock(
            redirect_url="https://oauth.example/x",
            composio_conn_id="conn_new",
            auth_config_id="ac_new",
        )
        r = Client().post("/api/connections/LINKEDIN/initiate", **auth_headers)
    assert r.status_code == 201
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.composio_conn_id == "conn_new"
    assert row.status == "pending"
    assert row.last_error == ""


def test_refresh_flips_to_active_when_composio_reports_active(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="pending", composio_conn_id="conn_abc")
    with patch("noctua.core.api.get_client") as get_client:
        get_client.return_value.fetch_connection_status.return_value = "ACTIVE"
        r = Client().post("/api/connections/LINKEDIN/refresh", **auth_headers)
    assert r.status_code == 200
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.status == "active"
    assert row.connected_at is not None


def test_refresh_keeps_pending_when_composio_not_yet_active(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="pending", composio_conn_id="conn_abc")
    with patch("noctua.core.api.get_client") as get_client:
        get_client.return_value.fetch_connection_status.return_value = "INITIATED"
        r = Client().post("/api/connections/LINKEDIN/refresh", **auth_headers)
    assert r.status_code == 200
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.status == "pending"


def test_refresh_404_when_no_row(auth_headers):
    r = Client().post("/api/connections/LINKEDIN/refresh", **auth_headers)
    assert r.status_code == 404


def test_disconnect_flips_to_revoked(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="conn_abc")
    r = Client().post("/api/connections/LINKEDIN/disconnect", **auth_headers)
    assert r.status_code == 200
    assert Connection.objects.get(toolkit="LINKEDIN").status == "revoked"
