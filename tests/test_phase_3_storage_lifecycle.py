from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from raiker.cli.commands import handle_slash_command
from raiker.graph.governance import graph_governance_status
from raiker.memory.semantic import semantic_memory_status
from raiker.phase_gates import list_capability_states
from raiker.storage.lifecycle import create_storage_lifecycle_record
from raiker.storage.lifecycle_registry import (
    create_lifecycle_record,
    expire_lifecycle_record,
    storage_lifecycle_summary,
    supersede_lifecycle_record,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_lifecycle_records_are_deterministic_json_safe_and_redacted() -> None:
    kwargs: dict[str, Any] = {
        "target_capability": "semantic_memory_writes",
        "record_type": "semantic_memory_review_metadata",
        "status": "runtime_blocked",
        "source_preview_id": "aprev_memory_1",
        "reasons": ["password=super-secret-value", "no_vectors_created"],
        "metadata": {
            "candidate_id": "memcand_1",
            "proposed_text": "api_key=abcdef1234567890",
            "nested": {"token": "bearer abcdefghijklmnop"},
        },
        "created_at": "2026-06-18T00:00:00Z",
    }
    first = create_storage_lifecycle_record(**kwargs)
    second = create_storage_lifecycle_record(**kwargs)
    assert first.lifecycle_id == second.lifecycle_id
    assert first.can_write_runtime_data is False
    assert first.runtime_writes_enabled is False
    encoded = json.dumps(first.to_dict(), sort_keys=True)
    assert "abcdef1234567890" not in encoded
    assert "super-secret-value" not in encoded
    assert "[REDACTED]" in encoded


def test_graph_and_memory_lifecycle_records_keep_runtime_writes_disabled() -> None:
    graph = create_storage_lifecycle_record(
        target_capability="graph_codemap_indexing",
        record_type="graph_index_plan_metadata",
        metadata={"path_count": 2},
        created_at="2026-06-18T00:00:00Z",
    )
    memory = create_storage_lifecycle_record(
        target_capability="semantic_memory_writes",
        record_type="semantic_memory_review_metadata",
        metadata={"candidate_count": 1},
        created_at="2026-06-18T00:00:00Z",
    )
    assert graph.can_write_runtime_data is False
    assert graph.runtime_writes_enabled is False
    assert memory.can_write_runtime_data is False
    assert memory.runtime_writes_enabled is False


def test_status_changes_do_not_enable_execution_or_rollback() -> None:
    record = create_lifecycle_record(
        target_capability="graph_codemap_indexing",
        record_type="approval_preview_metadata",
        status="approved_for_later",
        metadata={"summary": "approved metadata only"},
        created_at="2026-06-18T00:00:00Z",
    )
    expired = expire_lifecycle_record(record.lifecycle_id)
    superseded = supersede_lifecycle_record(record.lifecycle_id)
    assert record.runtime_writes_enabled is False
    assert expired.runtime_writes_enabled is False
    assert superseded.runtime_writes_enabled is False
    assert graph_governance_status()["runtime_indexing_enabled"] is False
    assert semantic_memory_status()["semantic_writes_enabled"] is False


def test_lifecycle_summary_cli_workspace_and_disabled_gates(tmp_path: Path) -> None:
    root = tmp_path
    summary = storage_lifecycle_summary(workspace_root=root)
    assert summary["runtime_writes_enabled"] is False
    assert summary["graph_runtime_writes_enabled"] is False
    assert summary["semantic_runtime_writes_enabled"] is False
    assert summary == storage_lifecycle_summary(workspace_root=root)

    output = handle_slash_command("/storage-lifecycle --summary", workspace_root=root)
    assert "Storage lifecycle metadata:" in output
    assert "runtime_writes_enabled: False" in output
    assert "lifecycle_record_count" in output
    assert "Usage:" in handle_slash_command("/storage-lifecycle --bad", workspace_root=root)

    inspection = inspect_workspace("terminal", workspace_root=root)
    view = workspace_view_summary(inspection)
    assert inspection["storage_lifecycle_summary"]["runtime_writes_enabled"] is False
    assert view["storage_lifecycle_summary"]["lifecycle_planning_available"] is True

    gates = list_capability_states()
    for capability in (
        "plugin_execution",
        "graph_codemap_indexing",
        "semantic_memory_writes",
        "external_channels",
        "remote_execution",
        "container_execution",
    ):
        assert gates[capability]["runtime_enabled"] is False
    # subagents / multi_agent_teams are integrated (real executors) -> enabled by default.
    assert gates["subagents"]["runtime_enabled"] is True
    assert gates["multi_agent_teams"]["runtime_enabled"] is True
    assert semantic_memory_status()["embedding_backend"] == "disabled"


def test_sqlite_lifecycle_metadata_tables_are_safe(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    tables = store.table_names()
    assert "phase3_storage_lifecycle" in tables
    assert "phase3_storage_lifecycle_events" in tables
    assert "graph_nodes" not in tables
    assert "vector_embeddings" not in tables
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "INSERT INTO phase3_storage_lifecycle VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "slc_test",
                "semantic_memory_writes",
                "approval_preview_metadata",
                "aprev_memory_1",
                None,
                None,
                "runtime_blocked",
                "2026-06-18T00:00:00Z",
                "2026-06-18T00:00:00Z",
                "metadata_only_until_phase3_runtime_storage_policy",
                "secret_like_values_redacted_no_raw_memory_text",
                0,
                0,
                json.dumps(["runtime_writes_disabled"]),
                json.dumps({"summary": "[REDACTED]"}),
            ),
        )
        row = connection.execute(
            "SELECT metadata_json, runtime_writes_enabled FROM phase3_storage_lifecycle WHERE lifecycle_id = 'slc_test'"
        ).fetchone()
    assert row is not None
    assert "secret" not in row[0].lower()
    assert row[1] == 0
