from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from raiker.channels.readiness import (
    DISABLED_RUNTIME_FLAGS,
    ExternalChannelsNotificationsReadinessContract,
    create_external_channels_notifications_readiness_contract,
)
from raiker.channels.readiness_registry import (
    channel_readiness_summary,
    create_channel_readiness_metadata,
    get_channel_readiness_metadata,
    list_channel_readiness_metadata,
    render_channel_readiness,
)
from raiker.cli.commands import handle_slash_command
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_deterministic_readiness_ids_and_serialization() -> None:
    first = create_external_channels_notifications_readiness_contract(workspace_id="ws")
    second = create_external_channels_notifications_readiness_contract(workspace_id="ws")
    assert first.readiness_id == second.readiness_id
    assert first.readiness_id.startswith("ecnr_")
    assert first.to_json() == second.to_json()
    assert json.loads(first.to_json())["metadata_only"] is True


def test_disabled_runtime_flags_required() -> None:
    contract = create_external_channels_notifications_readiness_contract()
    data = contract.to_dict()
    assert data["ready_for_external_channels"] is False
    for flag, expected in DISABLED_RUNTIME_FLAGS.items():
        assert expected is False
        assert data[flag] is False


def test_blockers_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="blockers must be non-empty"):
        ExternalChannelsNotificationsReadinessContract(blockers=())


def test_json_safe_metadata_validation() -> None:
    create_external_channels_notifications_readiness_contract(metadata={"nested": ["ok", 1, False]})
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        create_external_channels_notifications_readiness_contract(metadata={1: "bad"})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="JSON-safe"):
        create_external_channels_notifications_readiness_contract(metadata={"bad": object()})


def test_registry_create_list_get_summary_and_render(tmp_path: Path) -> None:
    record = create_channel_readiness_metadata(workspace_root=tmp_path)
    assert get_channel_readiness_metadata(record.readiness_id) == record
    listed = list_channel_readiness_metadata(workspace_root=tmp_path)
    assert listed == sorted(listed, key=lambda item: item.readiness_id)
    summary = channel_readiness_summary(workspace_root=tmp_path)
    assert summary["latest_readiness_id"] == record.readiness_id
    assert summary["metadata_only"] is True
    assert summary["blocker_count"] > 0
    rendered = render_channel_readiness(workspace_root=tmp_path)
    assert "External channels/notifications readiness:" in rendered
    assert "external_channels_enabled: False" in rendered


def test_sqlite_metadata_only_table_and_forbidden_tables(tmp_path: Path) -> None:
    create_channel_readiness_metadata(workspace_root=tmp_path, persist=True)
    store = SQLiteStore(tmp_path)
    tables = store.table_names()
    assert "phase3_external_channels_notifications_readiness" in tables
    forbidden = {
        "channel_dispatch_jobs",
        "notification_jobs",
        "push_notification_records",
        "share_link_records",
        "webhook_dispatch_state",
        "client_transport_state",
        "hosted_channel_state",
        "hosted_routine_state",
        "approval_relay_runtime_state",
        "channel_relay_runtime_state",
        "worker_queues",
        "scheduler_state",
        "daemon_state",
        "runtime_execution_state",
    }
    assert tables.isdisjoint(forbidden)
    with sqlite3.connect(store.db_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM phase3_external_channels_notifications_readiness").fetchone()[0]
    assert count == 1


def test_channel_readiness_cli_modes_and_invalid_usage(tmp_path: Path) -> None:
    default = handle_slash_command("/channel-readiness", workspace_root=tmp_path)
    assert "metadata_only" in default
    summary = handle_slash_command("/channel-readiness --summary", workspace_root=tmp_path)
    assert "ready_for_external_channels: False" in summary
    as_json = handle_slash_command("/channel-readiness --json", workspace_root=tmp_path)
    assert json.loads(as_json)["webhook_dispatch_enabled"] is False
    invalid = handle_slash_command("/channel-readiness --start", workspace_root=tmp_path)
    assert invalid == "Usage: /channel-readiness [--summary|--json]"


def test_workspace_inspection_and_view_summary_fields(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    summary = inspection["external_channels_notifications_readiness"]
    assert summary["metadata_only"] is True
    assert summary["ready_for_external_channels"] is False
    assert summary["external_channels_enabled"] is False
    assert summary["notifications_enabled"] is False
    assert summary["push_notifications_enabled"] is False
    assert summary["share_links_enabled"] is False
    assert summary["webhook_dispatch_enabled"] is False
    assert summary["channel_relay_runtime_enabled"] is False
    assert summary["workers_enabled"] is False
    assert summary["runtime_execution_enabled"] is False
    view = workspace_view_summary(inspection)
    assert view["external_channels_notifications_readiness"]["latest_readiness_id"].startswith("ecnr_")


def test_docs_catalog_event_consistency() -> None:
    paths = [
        "README.md",
        "docs/IMPLEMENTATION_STATUS.md",
        "docs/EVENT_CATALOG.md",
        "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md",
        "docs/completed/PHASE_3_SLICE_O_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_SPEC.md",
    ]
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        assert "Slice O" in text
        assert "metadata" in text.lower()
    event_text = Path("docs/EVENT_CATALOG.md").read_text(encoding="utf-8")
    assert "phase3.external_channels_notifications.readiness.metadata_defined" in event_text
    assert "runtime dispatch events are introduced" in event_text
