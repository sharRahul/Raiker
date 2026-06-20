from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from raiker.cli.commands import handle_slash_command
from raiker.remote.readiness import (
    DISABLED_RUNTIME_FLAGS,
    RemoteContainerCloudReadinessContract,
    create_remote_container_cloud_readiness_contract,
)
from raiker.remote.readiness_registry import (
    create_remote_readiness_metadata,
    get_remote_readiness_metadata,
    list_remote_readiness_metadata,
    remote_readiness_summary,
    render_remote_readiness,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_deterministic_readiness_ids_and_serialization() -> None:
    first = create_remote_container_cloud_readiness_contract(workspace_id="ws")
    second = create_remote_container_cloud_readiness_contract(workspace_id="ws")
    assert first.readiness_id == second.readiness_id
    assert first.readiness_id.startswith("rccr_")
    assert first.to_json() == second.to_json()
    assert json.loads(first.to_json())["metadata_only"] is True


def test_disabled_runtime_flags_all_false() -> None:
    contract = create_remote_container_cloud_readiness_contract()
    data = contract.to_dict()
    assert data["ready_for_remote_execution"] is False
    assert data["ready_for_container_execution"] is False
    assert data["ready_for_cloud_execution"] is False
    for flag, expected in DISABLED_RUNTIME_FLAGS.items():
        assert expected is False
        assert data[flag] is False


def test_blockers_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="blockers must be non-empty"):
        RemoteContainerCloudReadinessContract(blockers=())


def test_json_safe_metadata_validation() -> None:
    create_remote_container_cloud_readiness_contract(metadata={"nested": ["ok", 1, False]})
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        create_remote_container_cloud_readiness_contract(metadata={1: "bad"})
    with pytest.raises(ValueError, match="JSON-safe"):
        create_remote_container_cloud_readiness_contract(metadata={"bad": object()})


def test_registry_create_list_get_summary_and_render(tmp_path: Path) -> None:
    record = create_remote_readiness_metadata(workspace_root=tmp_path)
    assert get_remote_readiness_metadata(record.readiness_id) == record
    listed = list_remote_readiness_metadata(workspace_root=tmp_path)
    assert listed == sorted(listed, key=lambda item: item.readiness_id)
    summary = remote_readiness_summary(workspace_root=tmp_path)
    assert summary["latest_readiness_id"] == record.readiness_id
    assert summary["metadata_only"] is True
    assert summary["blocker_count"] > 0
    rendered = render_remote_readiness(workspace_root=tmp_path)
    assert "Remote/container/cloud execution readiness:" in rendered
    assert "remote_execution_enabled: False" in rendered


def test_sqlite_metadata_only_table_and_forbidden_tables(tmp_path: Path) -> None:
    create_remote_readiness_metadata(workspace_root=tmp_path, persist=True)
    store = SQLiteStore(tmp_path)
    tables = store.table_names()
    assert "phase3_remote_container_cloud_readiness" in tables
    forbidden = {
        "remote_execution_jobs",
        "container_execution_jobs",
        "cloud_execution_jobs",
        "hosted_routine_state",
        "job_dispatch_state",
        "worker_queues",
        "scheduler_state",
        "daemon_state",
        "client_transport_state",
        "external_dispatch_state",
        "credential_store",
        "secret_injection_state",
        "provider_integration_state",
        "sandbox_runtime_state",
        "process_execution_state",
        "shell_execution_state",
        "network_execution_state",
        "runtime_execution_state",
    }
    assert tables.isdisjoint(forbidden)
    with sqlite3.connect(store.db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM phase3_remote_container_cloud_readiness"
        ).fetchone()[0]
    assert count == 1


def test_cli_modes_and_invalid_usage(tmp_path: Path) -> None:
    default = handle_slash_command("/remote-readiness", workspace_root=tmp_path)
    assert "metadata_only" in default
    summary = handle_slash_command("/remote-readiness --summary", workspace_root=tmp_path)
    assert "ready_for_remote_execution: False" in summary
    as_json = handle_slash_command("/remote-readiness --json", workspace_root=tmp_path)
    assert json.loads(as_json)["container_execution_enabled"] is False
    invalid = handle_slash_command("/remote-readiness --start", workspace_root=tmp_path)
    assert invalid == "Usage: /remote-readiness [--summary|--json]"


def test_workspace_inspection_and_view_summary_fields(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    summary = inspection["remote_container_cloud_readiness"]
    assert summary["metadata_only"] is True
    assert summary["ready_for_remote_execution"] is False
    assert summary["ready_for_container_execution"] is False
    assert summary["ready_for_cloud_execution"] is False
    assert summary["remote_execution_enabled"] is False
    assert summary["container_execution_enabled"] is False
    assert summary["cloud_execution_enabled"] is False
    assert summary["hosted_routines_enabled"] is False
    assert summary["runtime_jobs_enabled"] is False
    assert summary["job_dispatch_enabled"] is False
    assert summary["worker_queues_enabled"] is False
    assert summary["workers_enabled"] is False
    assert summary["schedulers_enabled"] is False
    assert summary["file_watchers_enabled"] is False
    assert summary["daemons_enabled"] is False
    assert summary["client_transport_enabled"] is False
    assert summary["external_dispatch_enabled"] is False
    assert summary["credential_materialization_enabled"] is False
    assert summary["secret_injection_enabled"] is False
    assert summary["provider_integrations_enabled"] is False
    assert summary["sandbox_runtime_enabled"] is False
    assert summary["process_execution_enabled"] is False
    assert summary["shell_execution_enabled"] is False
    assert summary["network_execution_enabled"] is False
    assert summary["runtime_execution_enabled"] is False
    view = workspace_view_summary(inspection)
    assert view["remote_container_cloud_readiness"]["latest_readiness_id"].startswith("rccr_")


def test_docs_catalog_event_consistency(tmp_path: Path) -> None:
    paths = [
        "README.md",
        "docs/IMPLEMENTATION_STATUS.md",
        "docs/EVENT_CATALOG.md",
        "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md",
        "docs/completed/PHASE_3_SLICE_P_REMOTE_CONTAINER_CLOUD_READINESS_SPEC.md",
    ]
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        assert "Slice P" in text
        assert "metadata" in text.lower()
    event_text = Path("docs/EVENT_CATALOG.md").read_text(encoding="utf-8")
    assert "phase3.remote_container_cloud_readiness.metadata_created" in event_text
    assert "phase3.remote_container_cloud_readiness.summary_viewed" in event_text
    assert "phase3.remote_container_cloud_readiness.exported" in event_text
