from __future__ import annotations

from pathlib import Path

import pytest

from raiker.approval_preview_registry import approval_preview_summary
from raiker.approval_previews import (
    create_graph_indexing_approval_preview,
    create_semantic_memory_write_approval_preview,
    render_approval_preview,
)
from raiker.cli.commands import handle_slash_command
from raiker.graph.planner import GraphCodemapPlanner, create_graph_codemap_plan
from raiker.memory.review import MemoryReviewQueue
from raiker.phase_gates import get_capability_gate
from raiker.workspace.inspection import inspect_workspace


def _require_directory_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Directory symlink creation is not permitted in this environment.")
        raise


def test_graph_approval_preview_from_dry_run_plan_does_not_write_indexes(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("print('safe')\n", encoding="utf-8")
    plan = create_graph_codemap_plan(tmp_path)
    before = inspect_workspace("terminal", workspace_root=tmp_path)
    preview = create_graph_indexing_approval_preview(plan)
    after = inspect_workspace("terminal", workspace_root=tmp_path)
    assert preview.target_capability == "graph_codemap_indexing"
    assert preview.can_execute_now is False
    assert preview.execution_enabled is False
    assert preview.requires_user_approval is True
    assert preview.policy_decision == "denied_or_preview_only"
    assert "graph_runtime_indexing_disabled" in preview.reasons
    assert after["graph_codemap"]["graph_indexing_enabled"] is False
    assert after["graph_codemap"]["runtime_indexing_enabled"] is False
    assert before["runtime_status"] == after["runtime_status"]


def test_unsafe_graph_plan_produces_denied_high_risk_preview(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-preview-target"
    outside.mkdir(exist_ok=True)
    _require_directory_symlink(tmp_path / "escape", outside)
    plan = GraphCodemapPlanner(tmp_path).create_plan()
    preview = create_graph_indexing_approval_preview(plan)
    assert preview.can_execute_now is False
    assert preview.execution_enabled is False
    assert preview.risk_level == "high"
    assert "unsafe_graph_plan_denied" in preview.reasons


def test_semantic_memory_approval_preview_from_review_item_does_not_write_vectors(
    tmp_path: Path,
) -> None:
    queue = MemoryReviewQueue(tmp_path)
    item = queue.add_candidate("Raiker project prefers local-first docs")
    before = queue.export_summary()
    preview = create_semantic_memory_write_approval_preview(item)
    after = queue.export_summary()
    assert preview.target_capability == "semantic_memory_writes"
    assert preview.can_execute_now is False
    assert preview.execution_enabled is False
    assert preview.requires_user_approval is True
    assert preview.policy_decision == "denied_or_preview_only"
    assert "semantic_vector_writes_disabled" in preview.reasons
    assert after["semantic_writes_enabled"] is False
    assert after["embedding_records_written"] == 0
    assert after["vector_records_written"] == 0
    assert before == after


def test_secret_like_memory_candidate_produces_denied_redacted_preview(tmp_path: Path) -> None:
    item = MemoryReviewQueue(tmp_path).add_candidate(
        "api_key = 'sk_test_1234567890abcdef1234567890'"
    )
    preview = create_semantic_memory_write_approval_preview(item)
    rendered = render_approval_preview(preview)
    assert item.decision == "denied"
    assert preview.risk_level == "high"
    assert "secret_or_credential_like_candidate_blocked" in preview.reasons
    assert "sk_test_1234567890abcdef1234567890" not in rendered
    assert "[REDACTED]" in rendered


def test_preview_rendering_is_deterministic(tmp_path: Path) -> None:
    item = MemoryReviewQueue(tmp_path).add_candidate("public documentation note")
    preview = create_semantic_memory_write_approval_preview(item)
    assert render_approval_preview(preview) == render_approval_preview(preview)


def test_workspace_inspection_includes_approval_preview_summary(tmp_path: Path) -> None:
    MemoryReviewQueue(tmp_path).add_candidate("api_key = 'sk_test_1234567890abcdef1234567890'")
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    summary = inspection["approval_preview_summary"]
    assert summary["graph_indexing_preview_available"] is True
    assert summary["semantic_memory_write_preview_available"] is True
    assert summary["pending_preview_count"] == 0
    assert summary["denied_preview_count"] == 1
    assert summary["preview_only_mode"] is True
    assert summary["runtime_execution_enabled"] is False


def test_approval_preview_cli_commands_are_preview_only(tmp_path: Path) -> None:
    MemoryReviewQueue(tmp_path).add_candidate("Raiker project memory candidate")
    assert "Approval previews:" in handle_slash_command(
        "/approval-previews", workspace_root=tmp_path
    )
    graph = handle_slash_command("/graph-approval-preview", workspace_root=tmp_path)
    memory = handle_slash_command("/memory-approval-preview", workspace_root=tmp_path)
    lookup = handle_slash_command("/approval-preview aprev_missing", workspace_root=tmp_path)
    assert "Graph/codemap indexing approval preview" in graph
    assert "can_execute_now: False" in graph
    assert "execution_enabled: False" in graph
    assert "Semantic memory write approval preview" in memory
    assert "can_execute_now: False" in memory
    assert "execution_enabled: False" in memory
    assert "not persisted" in lookup


def test_unsafe_runtime_paths_remain_disabled(tmp_path: Path) -> None:
    summary = approval_preview_summary(workspace_root=tmp_path)
    assert summary["runtime_execution_enabled"] is False
    assert get_capability_gate("plugin_execution").runtime_enabled is False
    assert get_capability_gate("graph_codemap_indexing").runtime_enabled is False
    assert get_capability_gate("semantic_memory_writes").runtime_enabled is False
    assert get_capability_gate("external_channels").runtime_enabled is False
    assert get_capability_gate("remote_execution").runtime_enabled is False
    assert get_capability_gate("container_execution").runtime_enabled is False
