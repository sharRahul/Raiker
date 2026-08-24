from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.cli.commands import handle_slash_command
from raiker.storage.cleanup_readiness import (
    DISABLED_RUNTIME_FLAGS,
    StorageCleanupExecutionReadinessContract,
    create_storage_cleanup_execution_readiness_contract,
)
from raiker.storage.cleanup_readiness_registry import (
    cleanup_readiness_summary,
    create_cleanup_readiness_metadata,
    get_cleanup_readiness_metadata,
    list_cleanup_readiness_metadata,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_contract_deterministic_ids_flags_and_serialization() -> None:
    first = create_storage_cleanup_execution_readiness_contract(workspace_id="workspace")
    second = create_storage_cleanup_execution_readiness_contract(workspace_id="workspace")
    assert first.readiness_id == second.readiness_id
    assert first.readiness_id.startswith("scer_")
    data = first.to_dict()
    assert data["metadata_only"] is True
    assert data["ready_for_cleanup_execution"] is False
    for key, value in DISABLED_RUNTIME_FLAGS.items():
        assert data[key] is value is False
    assert first.to_json() == second.to_json()
    assert json.loads(first.to_json()) == data


def test_contract_rejects_empty_blockers_and_non_json_safe_metadata() -> None:
    with pytest.raises(ValueError, match="blockers must be non-empty"):
        StorageCleanupExecutionReadinessContract(blockers=())
    with pytest.raises(ValueError, match="metadata must contain only JSON-safe values"):
        create_storage_cleanup_execution_readiness_contract(metadata={"bad": object()})
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        create_storage_cleanup_execution_readiness_contract(metadata={1: "bad"})  # type: ignore[dict-item]


def test_registry_create_list_get_summary_and_sqlite_boundaries(tmp_path: Path) -> None:
    record = create_cleanup_readiness_metadata(workspace_root=tmp_path, persist=True)
    assert get_cleanup_readiness_metadata(record.readiness_id) == record
    assert record in list_cleanup_readiness_metadata(workspace_root=tmp_path)
    summary = cleanup_readiness_summary(workspace_root=tmp_path)
    assert summary["storage_cleanup_readiness_contract_available"] is True
    assert summary["latest_readiness_id"].startswith("scer_")
    tables = SQLiteStore(tmp_path).table_names()
    assert "phase3_storage_cleanup_execution_readiness" in tables
    forbidden = {
        "cleanup_jobs",
        "deletion_jobs",
        "purge_jobs",
        "tombstone_jobs",
        "rollback_execution_state",
        "worker_queues",
        "worker_state",
        "scheduler_state",
        "daemon_state",
        "runtime_execution_state",
        "deletion_dispatch",
        "cleanup_dispatch",
    }
    assert forbidden.isdisjoint(tables)


def test_cleanup_readiness_cli_modes_are_metadata_only(tmp_path: Path) -> None:
    output = handle_slash_command("/cleanup-readiness", workspace_root=tmp_path)
    assert "Storage cleanup execution readiness:" in output
    assert "cleanup_execution_enabled: False" in output
    assert "workers_enabled: False" in output
    summary = handle_slash_command("/cleanup-readiness --summary", workspace_root=tmp_path)
    assert "Storage cleanup execution readiness summary:" in summary
    assert "runtime_execution_enabled: False" in summary
    payload = json.loads(handle_slash_command("/cleanup-readiness --json", workspace_root=tmp_path))
    assert payload["metadata_only"] is True
    assert payload["ready_for_cleanup_execution"] is False
    assert handle_slash_command("/cleanup-readiness --start", workspace_root=tmp_path) == "Usage: /cleanup-readiness [--summary|--json]"
    assert "/cleanup-readiness [--summary|--json]" in handle_slash_command("/help", workspace_root=tmp_path)


def test_workspace_surfaces_include_cleanup_readiness(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    readiness = inspection["storage_cleanup_execution_readiness"]
    assert readiness["metadata_only"] is True
    assert readiness["ready_for_cleanup_execution"] is False
    assert readiness["cleanup_execution_enabled"] is False
    assert readiness["deletion_execution_enabled"] is False
    assert readiness["purge_execution_enabled"] is False
    assert readiness["tombstone_execution_enabled"] is False
    assert readiness["rollback_execution_enabled"] is False
    assert readiness["workers_enabled"] is False
    view = workspace_view_summary(inspection)["storage_cleanup_execution_readiness"]
    assert view["latest_readiness_id"].startswith("scer_")
    assert view["blocker_count"] > 0


def test_docs_catalog_event_consistency() -> None:
    for path in [
        Path("docs/architecture/IMPLEMENTATION_STATUS.md"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "Slice M" in text
        assert "cleanup" in text.lower()
        assert (
            "Phase 3 remains incomplete" in text
            or "Phase 3 is complete" in text
        )
        assert "Phase 4 remains blocked" in text
