from __future__ import annotations

import json
from pathlib import Path

from raiker.approval_audit import create_approval_audit_record
from raiker.approval_previews import (
    create_graph_indexing_approval_preview,
    create_semantic_memory_write_approval_preview,
)
from raiker.cli.commands import handle_slash_command
from raiker.graph.governance import graph_governance_status
from raiker.graph.planner import create_graph_codemap_plan
from raiker.memory.governance import memory_governance_summary
from raiker.memory.review import MemoryReviewQueue
from raiker.phase_gates import list_capability_states
from raiker.rollback_plans import create_graph_rollback_plan, create_memory_rollback_plan
from raiker.workspace.inspection import inspect_workspace


def test_approval_audit_records_are_deterministic_serialisable_and_redacted(tmp_path: Path) -> None:
    item = MemoryReviewQueue(tmp_path).add_candidate("api_key=abcdefghijklmnopqrstuvwxyz123456")
    preview = create_semantic_memory_write_approval_preview(item)
    plan = create_memory_rollback_plan(preview)
    record_one = create_approval_audit_record(preview, decision="denied", rollback_plan=plan)
    record_two = create_approval_audit_record(preview, decision="denied", rollback_plan=plan)
    assert record_one == record_two
    payload = record_one.to_dict()
    json.dumps(payload, sort_keys=True)
    assert "abcdefghijklmnopqrstuvwxyz" not in str(payload)
    assert "[REDACTED]" in str(payload["redacted_summary"])
    assert record_one.decision == "denied"
    assert record_one.can_execute_now is False
    assert record_one.execution_enabled is False


def test_graph_and_memory_audit_approvals_for_later_do_not_execute(tmp_path: Path) -> None:
    graph_preview = create_graph_indexing_approval_preview(create_graph_codemap_plan(tmp_path))
    memory_item = MemoryReviewQueue(tmp_path).add_candidate("Remember project preference")
    memory_preview = create_semantic_memory_write_approval_preview(memory_item)
    for preview in (graph_preview, memory_preview):
        record = create_approval_audit_record(preview, decision="approved_for_later")
        assert record.decision == "approved_for_later"
        assert record.decision_status == "execution_blocked"
        assert record.can_execute_now is False
        assert record.execution_enabled is False


def test_rollback_plans_are_deterministic_preview_only_and_do_not_write(tmp_path: Path) -> None:
    graph_preview = create_graph_indexing_approval_preview(create_graph_codemap_plan(tmp_path))
    memory_item = MemoryReviewQueue(tmp_path).add_candidate("Remember safe detail")
    memory_preview = create_semantic_memory_write_approval_preview(memory_item)
    graph_one = create_graph_rollback_plan(graph_preview)
    graph_two = create_graph_rollback_plan(graph_preview)
    memory_one = create_memory_rollback_plan(memory_preview)
    assert graph_one == graph_two
    json.dumps(graph_one.to_dict(), sort_keys=True)
    assert graph_one.rollback_execution_enabled is False
    assert graph_one.can_execute_rollback_now is False
    assert "no graph data is created or deleted" in " ".join(graph_one.safety_notes)
    assert memory_one.rollback_execution_enabled is False
    assert memory_one.can_execute_rollback_now is False
    assert "no semantic memory records" in " ".join(memory_one.safety_notes)
    summary = memory_governance_summary(tmp_path)
    assert summary["embedding_records_written"] == 0
    assert summary["vector_records_written"] == 0


def test_workspace_inspection_includes_audit_and_rollback_summaries(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    assert inspection["approval_audit_summary"]["audit_preview_available"] is True
    assert inspection["approval_audit_summary"]["execution_enabled"] is False
    assert inspection["rollback_plan_summary"]["graph_rollback_plan_available"] is True
    assert inspection["rollback_plan_summary"]["memory_rollback_plan_available"] is True
    assert inspection["rollback_plan_summary"]["rollback_execution_enabled"] is False
    assert inspection["rollback_plan_summary"]["preview_only_mode"] is True


def test_cli_audit_and_rollback_commands_return_helpful_output(tmp_path: Path) -> None:
    commands = {
        "/approval-audit": "Approval audit previews:",
        "/approval-audit --summary": "Approval audit summary:",
        "/rollback-plan": "Rollback planning surfaces:",
        "/graph-rollback-plan": "Rollback plan preview:",
        "/memory-rollback-plan": "rollback_execution_enabled: False",
    }
    for command, expected in commands.items():
        assert expected in handle_slash_command(command, workspace_root=tmp_path)


def test_disabled_runtime_surfaces_remain_disabled(tmp_path: Path) -> None:
    gates = list_capability_states()
    assert gates["plugin_execution"]["runtime_enabled"] is False
    assert gates["graph_codemap_indexing"]["runtime_enabled"] is False
    assert gates["semantic_memory_writes"]["runtime_enabled"] is False
    assert gates["external_channels"]["runtime_enabled"] is False
    assert gates["subagents"]["runtime_enabled"] is False
    assert gates["multi_agent_teams"]["runtime_enabled"] is False
    assert gates["remote_execution"]["runtime_enabled"] is False
    assert gates["container_execution"]["runtime_enabled"] is False
    assert graph_governance_status()["runtime_indexing_enabled"] is False
    assert memory_governance_summary(tmp_path)["semantic_writes_enabled"] is False
