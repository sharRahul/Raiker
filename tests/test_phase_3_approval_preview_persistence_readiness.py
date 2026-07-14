from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.approvals.readiness import (
    DISABLED_RUNTIME_FLAGS,
    ApprovalPreviewPersistenceReadinessContract,
    create_approval_preview_persistence_readiness_contract,
)
from raiker.approvals.readiness_registry import (
    approval_readiness_summary,
    create_approval_readiness_metadata,
    get_approval_readiness_metadata,
    list_approval_readiness_metadata,
)
from raiker.cli.commands import handle_slash_command
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_contract_deterministic_ids_flags_and_serialization() -> None:
    first = create_approval_preview_persistence_readiness_contract(workspace_id="workspace")
    second = create_approval_preview_persistence_readiness_contract(workspace_id="workspace")
    assert first.readiness_id == second.readiness_id
    assert first.readiness_id.startswith("appr_")
    data = first.to_dict()
    assert data["metadata_only"] is True
    assert data["ready_for_persistence"] is False
    for key, value in DISABLED_RUNTIME_FLAGS.items():
        assert data[key] is value is False
    assert first.to_json() == second.to_json()
    assert json.loads(first.to_json()) == data


def test_contract_rejects_empty_blockers_and_non_json_safe_metadata() -> None:
    with pytest.raises(ValueError, match="blockers must be non-empty"):
        ApprovalPreviewPersistenceReadinessContract(blockers=())
    with pytest.raises(ValueError, match="metadata must contain only JSON-safe values"):
        create_approval_preview_persistence_readiness_contract(metadata={"bad": object()})
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        create_approval_preview_persistence_readiness_contract(metadata={1: "bad"})  # type: ignore[dict-item]


def test_registry_create_list_get_summary_and_sqlite_boundaries(tmp_path: Path) -> None:
    record = create_approval_readiness_metadata(workspace_root=tmp_path, persist=True)
    assert get_approval_readiness_metadata(record.readiness_id) == record
    assert record in list_approval_readiness_metadata(workspace_root=tmp_path)
    summary = approval_readiness_summary(workspace_root=tmp_path)
    assert summary["approval_readiness_contract_available"] is True
    assert summary["latest_readiness_id"].startswith("appr_")
    tables = SQLiteStore(tmp_path).table_names()
    assert "phase3_approval_preview_persistence_readiness" in tables
    forbidden = {
        "approval_execution_queue",
        "approval_relay_runtime_state",
        "approval_workers",
        "approval_scheduler_state",
        "approval_daemon_state",
        "approval_action_dispatch",
    }
    assert forbidden.isdisjoint(tables)


def test_approval_readiness_cli_modes_are_metadata_only(tmp_path: Path) -> None:
    output = handle_slash_command("/approval-readiness", workspace_root=tmp_path)
    assert "Approval preview persistence readiness:" in output
    assert "approval_execution_enabled: False" in output
    assert "durable_approval_queues_enabled: False" in output
    summary = handle_slash_command("/approval-readiness --summary", workspace_root=tmp_path)
    assert "Approval preview persistence readiness summary:" in summary
    assert "approval_relay_runtime_enabled: False" in summary
    payload = json.loads(handle_slash_command("/approval-readiness --json", workspace_root=tmp_path))
    assert payload["metadata_only"] is True
    assert payload["ready_for_persistence"] is False
    assert handle_slash_command("/approval-readiness --start", workspace_root=tmp_path) == "Usage: /approval-readiness [--summary|--json]"
    assert "/approval-readiness [--summary|--json]" in handle_slash_command("/help", workspace_root=tmp_path)


def test_workspace_surfaces_include_approval_readiness(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    readiness = inspection["approval_preview_persistence_readiness"]
    assert readiness["metadata_only"] is True
    assert readiness["ready_for_persistence"] is False
    assert readiness["approval_execution_enabled"] is False
    assert readiness["approval_relay_runtime_enabled"] is False
    assert readiness["durable_approval_queues_enabled"] is False
    assert readiness["approval_workers_enabled"] is False
    view = workspace_view_summary(inspection)["approval_preview_persistence_readiness"]
    assert view["latest_readiness_id"].startswith("appr_")
    assert view["blocker_count"] > 0


def test_docs_catalog_event_consistency() -> None:
    for path in [
        Path("docs/IMPLEMENTATION_STATUS.md"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "Slice L" in text
        assert "approval preview persistence" in text.lower()
        assert (
            "Phase 3 remains incomplete" in text
            or "Phase 3 is complete" in text
        )
        assert "Phase 4 remains blocked" in text
