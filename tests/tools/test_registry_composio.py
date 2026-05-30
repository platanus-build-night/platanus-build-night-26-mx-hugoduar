import pytest
from unittest.mock import patch, MagicMock
from noctua.tools.registry import ToolRegistry
from noctua.tools.base import ToolEntry

pytestmark = pytest.mark.django_db


def test_lookup_dispatches_composio_prefix_to_adapter():
    with patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
        fake_entry = ToolEntry(name="composio:X.Y", signature={}, status="composio", callable=lambda a, s: None)
        Adapter.return_value.lookup.return_value = fake_entry
        reg = ToolRegistry()
        entry = reg.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST", current_mission_id=1)
    assert entry is fake_entry
    Adapter.return_value.lookup.assert_called_once_with(
        "composio:LINKEDIN.LINKEDIN_CREATE_POST"
    )


def test_lookup_falls_through_for_bundled_names():
    reg = ToolRegistry()
    entry = reg.lookup("read_file", current_mission_id=1)
    assert entry is not None
    assert entry.status == "hardcoded"


def test_all_available_includes_composio_actions_when_producer_passed():
    with patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
        fake_entry = ToolEntry(name="composio:LINKEDIN.LINKEDIN_CREATE_POST", signature={}, status="composio", callable=lambda a, s: None)
        Adapter.return_value.list_actions_for_producer.return_value = [fake_entry]
        producer = MagicMock(composio_actions={"LINKEDIN": ["LINKEDIN_CREATE_POST"]})
        reg = ToolRegistry()
        entries = reg.all_available(current_mission_id=1, producer=producer)
    names = [e.name for e in entries]
    assert "composio:LINKEDIN.LINKEDIN_CREATE_POST" in names
    # bundled still included
    assert "read_file" in names


def test_all_available_without_producer_returns_no_composio_entries():
    reg = ToolRegistry()
    entries = reg.all_available(current_mission_id=1)
    assert not any(e.name.startswith("composio:") for e in entries)
