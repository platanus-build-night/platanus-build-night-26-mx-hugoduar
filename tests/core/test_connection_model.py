import pytest
from django.db import IntegrityError
from noctua.core.models import Connection

pytestmark = pytest.mark.django_db


def test_create_connection_with_defaults():
    c = Connection.objects.create(
        toolkit="LINKEDIN", status="pending", composio_conn_id="conn_abc",
    )
    assert c.connected_at is None
    assert c.last_error == ""
    assert c.created_at is not None


def test_toolkit_is_unique():
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    with pytest.raises(IntegrityError):
        Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c2")


def test_status_choices_cover_lifecycle():
    # All four states are accepted at the field level (no validators reject them).
    for state in ("active", "expired", "revoked", "pending"):
        Connection.objects.create(toolkit=f"TK_{state}", status=state, composio_conn_id="x").full_clean()
