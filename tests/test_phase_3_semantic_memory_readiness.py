from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.cli.commands import handle_slash_command
from raiker.memory.readiness import (
    DISABLED_RUNTIME_FLAGS,
    SemanticMemoryReadinessContract,
    create_semantic_memory_readiness_contract,
)
from raiker.memory.readiness_registry import (
    create_semantic_memory_readiness_metadata,
    get_semantic_memory_readiness_metadata,
    list_semantic_memory_readiness_metadata,
    semantic_memory_readiness_summary,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_semantic_memory_readiness_contract_is_deterministic_and_disabled() -> None:
    first = create_semantic_memory_readiness_contract(workspace_id="workspace")
    second = create_semantic_memory_readiness_contract(workspace_id="workspace")
    assert first.readiness_id == second.readiness_id
    assert first.readiness_id.startswith("smr_")
    data = first.to_dict()
    assert data["metadata_only"] is True
    assert data["ready_for_memory_writes"] is False
    for key, value in DISABLED_RUNTIME_FLAGS.items():
        assert data[key] is value is False
    assert data["blockers"]
    assert first.to_json() == second.to_json()


def test_semantic_memory_readiness_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="blockers must be non-empty"):
        SemanticMemoryReadinessContract(blockers=())
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        SemanticMemoryReadinessContract(metadata={1: "bad"})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="JSON-safe"):
        SemanticMemoryReadinessContract(metadata={"bad": object()})


def test_semantic_memory_readiness_registry_create_list_get_summary_and_sqlite(tmp_path: Path) -> None:
    record = create_semantic_memory_readiness_metadata(workspace_root=tmp_path, persist=True)
    assert get_semantic_memory_readiness_metadata(record.readiness_id) == record
    assert record in list_semantic_memory_readiness_metadata(workspace_root=tmp_path)
    summary = semantic_memory_readiness_summary(workspace_root=tmp_path)
    assert summary["semantic_memory_readiness_contract_available"] is True
    assert summary["latest_readiness_id"].startswith("smr_")
    assert summary["ready_for_memory_writes"] is False
    tables = SQLiteStore(tmp_path).table_names()
    assert "phase3_semantic_memory_readiness" in tables
    forbidden = {
        "semantic_memory_writes",
        "vector_records",
        "embeddings",
        "embedding_jobs",
        "vector_indexes",
        "memory_write_jobs",
        "memory_workers",
        "memory_schedulers",
        "memory_daemons",
    }
    assert forbidden.isdisjoint(tables)


def test_memory_readiness_cli_modes_are_metadata_only(tmp_path: Path) -> None:
    output = handle_slash_command("/memory-readiness", workspace_root=tmp_path)
    assert "Semantic memory write readiness:" in output
    assert "ready_for_memory_writes: False" in output
    assert "semantic_memory_writes_enabled: False" in output
    assert "vector_writes_enabled: False" in output
    summary = handle_slash_command("/memory-readiness --summary", workspace_root=tmp_path)
    assert "Semantic memory write readiness summary:" in summary
    assert "memory_write_jobs_enabled: False" in summary
    payload = json.loads(handle_slash_command("/memory-readiness --json", workspace_root=tmp_path))
    assert payload["metadata_only"] is True
    assert payload["embedding_creation_enabled"] is False
    assert handle_slash_command("/memory-readiness --start", workspace_root=tmp_path) == "Usage: /memory-readiness [--summary|--json]"
    assert "/memory-readiness [--summary|--json]" in handle_slash_command("/help", workspace_root=tmp_path)


def test_workspace_surfaces_include_semantic_memory_readiness(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    readiness = inspection["semantic_memory_readiness"]
    assert readiness["metadata_only"] is True
    assert readiness["ready_for_memory_writes"] is False
    assert readiness["semantic_memory_writes_enabled"] is False
    view = workspace_view_summary(inspection)
    assert view["semantic_memory_readiness"]["latest_readiness_id"].startswith("smr_")
    text = handle_slash_command("/workspace-view", workspace_root=tmp_path)
    assert "semantic_memory_readiness_metadata_only: True" in text
    assert "semantic_memory_ready_for_writes: False" in text


def test_docs_catalog_reserve_metadata_only_events() -> None:
    for path in ["docs/IMPLEMENTATION_STATUS.md", "docs/EVENT_CATALOG.md", "README.md"]:
        text = Path(path).read_text(encoding="utf-8")
        assert "Phase 3 Slice K" in text
        assert "metadata-only" in text or "metadata_only" in text
        assert "Phase 4 remains blocked" in text
