from __future__ import annotations

from raiker.cli.commands import handle_slash_command
from raiker.graph.readiness import create_readiness_contract
from raiker.graph.readiness_registry import (
    create_graph_readiness_metadata,
    get_graph_readiness_metadata,
    graph_readiness_summary,
    list_graph_readiness_metadata,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_graph_readiness_contract_is_deterministic_and_disabled(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first = create_graph_readiness_metadata(workspace_root=tmp_path)
    second = create_graph_readiness_metadata(workspace_root=tmp_path)
    assert first.readiness_id == second.readiness_id
    data = first.to_dict()
    assert data["metadata_only"] is True
    assert data["ready_for_indexing"] is False
    assert data["graph_indexing_enabled"] is False
    assert data["graph_writes_enabled"] is False
    assert data["codemap_indexing_enabled"] is False
    assert data["indexing_jobs_enabled"] is False
    assert data["workers_enabled"] is False
    assert data["schedulers_enabled"] is False
    assert data["file_watchers_enabled"] is False
    assert data["daemons_enabled"] is False
    assert data["runtime_execution_enabled"] is False
    assert data["blockers"]


def test_graph_readiness_registry_create_list_get_summary(tmp_path) -> None:  # type: ignore[no-untyped-def]
    record = create_graph_readiness_metadata(workspace_root=tmp_path, persist=True)
    assert get_graph_readiness_metadata(record.readiness_id) == record
    assert record in list_graph_readiness_metadata(workspace_root=tmp_path)
    summary = graph_readiness_summary(workspace_root=tmp_path)
    assert summary["graph_readiness_contract_available"] is True
    assert summary["ready_for_indexing"] is False
    assert summary["runtime_jobs_enabled"] is False
    assert summary["indexing_jobs_enabled"] is False
    assert summary["runtime_execution_enabled"] is False
    assert summary["graph_readiness_record_count"] >= 1
    assert "phase3_graph_codemap_readiness" in SQLiteStore(tmp_path).table_names()


def test_graph_readiness_cli_and_workspace_surfaces_are_read_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    output = handle_slash_command("/graph-readiness", workspace_root=tmp_path)
    assert "Graph/codemap indexing readiness:" in output
    assert "ready_for_indexing: False" in output
    assert "runtime_jobs_enabled: False" in output
    assert "indexing_jobs_enabled: False" in output
    summary_output = handle_slash_command("/graph-readiness --summary", workspace_root=tmp_path)
    assert "Graph/codemap indexing readiness summary:" in summary_output
    json_output = handle_slash_command("/graph-readiness --json", workspace_root=tmp_path)
    assert '"runtime_execution_enabled": false' in json_output
    assert handle_slash_command("/graph-readiness --start", workspace_root=tmp_path) == "Usage: /graph-readiness [--summary|--json]"
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    view = workspace_view_summary(inspection)
    readiness = view["graph_codemap_readiness"]
    assert readiness["metadata_only"] is True
    assert readiness["ready_for_indexing"] is False
    assert readiness["graph_indexing_enabled"] is False


def test_graph_readiness_rejects_non_json_safe_metadata() -> None:
    try:
        create_readiness_contract(metadata={"bad": object()})
    except ValueError as exc:
        assert "JSON-safe" in str(exc)
    else:
        raise AssertionError("non-JSON-safe metadata was accepted")
