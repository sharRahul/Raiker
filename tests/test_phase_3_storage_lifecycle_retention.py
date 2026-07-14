from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.cli.commands import handle_slash_command
from raiker.graph.governance import graph_governance_status
from raiker.memory.semantic import semantic_memory_status
from raiker.phase_gates import list_capability_states
from raiker.storage.lifecycle_registry import (
    create_approval_handoff_metadata,
    create_cleanup_preview_metadata,
    create_lifecycle_record,
    create_retention_policy_metadata,
    get_approval_handoff,
    get_cleanup_preview,
    get_retention_policy,
    list_approval_handoffs,
    list_cleanup_previews,
    list_retention_policies,
    retention_cleanup_handoff_summary,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_slice_h_contracts_are_deterministic_json_safe_and_redacted() -> None:
    kwargs = dict(
        lifecycle_target_type="semantic_memory_writes",
        retention_class="audit_metadata",
        expiry_rule="manual_review_required",
        cleanup_eligible=True,
        reason_summary="password=super-secret-token",
        metadata={"api_key": "abcdef1234567890"},
    )
    first = create_retention_policy_metadata(**kwargs)
    second = create_retention_policy_metadata(**kwargs)
    assert first.policy_id == second.policy_id
    encoded = json.dumps(first.to_dict(), sort_keys=True)
    assert "abcdef1234567890" not in encoded
    assert "super-secret-token" not in encoded
    assert get_retention_policy(first.policy_id) == first
    assert first.metadata_only is True
    for flag in (
        first.execution_enabled,
        first.cleanup_execution_enabled,
        first.graph_indexing_enabled,
        first.semantic_memory_writes_enabled,
        first.vector_writes_enabled,
        first.embedding_creation_enabled,
        first.rollback_execution_enabled,
        first.plugin_execution_enabled,
        first.mcp_lsp_plugin_server_startup_enabled,
        first.monitor_watch_daemon_enabled,
        first.external_channel_enabled,
        first.approval_relay_enabled,
        first.subagent_execution_enabled,
        first.multi_agent_team_execution_enabled,
        first.remote_execution_enabled,
        first.container_execution_enabled,
        first.cloud_execution_enabled,
        first.hosted_routines_enabled,
        first.marketplace_installs_enabled,
        first.hosted_push_notifications_enabled,
        first.share_links_enabled,
    ):
        assert flag is False

    preview = create_cleanup_preview_metadata(
        linked_lifecycle_ids=["slc_b", "slc_a"],
        expired_candidate_count=1,
        superseded_candidate_count=2,
        summaries=["token=secret-value-123456789"],
    )
    assert preview == create_cleanup_preview_metadata(
        linked_lifecycle_ids=["slc_a", "slc_b"],
        expired_candidate_count=1,
        superseded_candidate_count=2,
        summaries=["token=secret-value-123456789"],
    )
    assert preview.can_cleanup_now is False
    for flag in (
        preview.cleanup_execution_enabled,
        preview.graph_execution_enabled,
        preview.memory_execution_enabled,
        preview.vector_execution_enabled,
        preview.embedding_execution_enabled,
        preview.rollback_execution_enabled,
        preview.plugin_execution_enabled,
        preview.mcp_lsp_plugin_server_startup_enabled,
        preview.monitor_watch_daemon_enabled,
        preview.external_channel_enabled,
        preview.approval_relay_enabled,
        preview.subagent_execution_enabled,
        preview.multi_agent_team_execution_enabled,
        preview.remote_execution_enabled,
        preview.container_execution_enabled,
        preview.cloud_execution_enabled,
        preview.hosted_routines_enabled,
        preview.marketplace_installs_enabled,
        preview.hosted_push_notifications_enabled,
        preview.share_links_enabled,
    ):
        assert flag is False
    assert "secret-value-123456789" not in json.dumps(preview.to_dict())

    handoff = create_approval_handoff_metadata(
        linked_lifecycle_ids=preview.linked_lifecycle_ids,
        source_preview_ids=[preview.preview_id],
        target_capability="storage_lifecycle_metadata",
        approval_state="handoff_planned",
        summary="api_key=abcdef1234567890",
    )
    assert handoff.can_execute_now is False
    for flag in (
        handoff.execution_enabled,
        handoff.cleanup_execution_enabled,
        handoff.graph_indexing_enabled,
        handoff.semantic_memory_writes_enabled,
        handoff.vector_writes_enabled,
        handoff.embedding_creation_enabled,
        handoff.rollback_execution_enabled,
        handoff.plugin_execution_enabled,
        handoff.mcp_lsp_plugin_server_startup_enabled,
        handoff.monitor_watch_daemon_enabled,
        handoff.external_channel_enabled,
        handoff.approval_relay_enabled,
        handoff.subagent_execution_enabled,
        handoff.multi_agent_team_execution_enabled,
        handoff.remote_execution_enabled,
        handoff.container_execution_enabled,
        handoff.cloud_execution_enabled,
        handoff.hosted_routines_enabled,
        handoff.marketplace_installs_enabled,
        handoff.hosted_push_notifications_enabled,
        handoff.share_links_enabled,
    ):
        assert flag is False
    assert "abcdef1234567890" not in json.dumps(handoff.to_dict())


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"retention_class": "forever"}, "invalid_retention_class"),
        ({"expiry_rule": "run_cleanup_now"}, "invalid_expiry_rule"),
    ],
)
def test_invalid_retention_classes_and_rules_rejected(kwargs: dict[str, str], message: str) -> None:
    base = {
        "lifecycle_target_type": "graph_codemap_indexing",
        "retention_class": "ephemeral",
        "expiry_rule": "none",
    }
    base.update(kwargs)
    with pytest.raises(ValueError, match=message):
        create_retention_policy_metadata(**base)


def test_registry_list_get_create_are_deterministic_and_non_executing() -> None:
    record = create_lifecycle_record(
        target_capability="graph_codemap_indexing",
        record_type="approval_preview_metadata",
        status="expired",
        metadata={"summary": "expired metadata"},
        created_at="2026-06-18T00:00:00Z",
    )
    preview = create_cleanup_preview_metadata(
        linked_lifecycle_ids=[record.lifecycle_id], expired_candidate_count=1
    )
    handoff = create_approval_handoff_metadata(
        linked_lifecycle_ids=[record.lifecycle_id],
        source_preview_ids=[preview.preview_id],
        target_capability="storage_lifecycle_metadata",
        approval_state="requires_future_policy",
    )
    assert get_cleanup_preview(preview.preview_id) == preview
    assert get_approval_handoff(handoff.handoff_id) == handoff
    assert list_cleanup_previews() == sorted(list_cleanup_previews(), key=lambda p: p.preview_id)
    assert list_approval_handoffs() == sorted(list_approval_handoffs(), key=lambda h: h.handoff_id)
    assert list_retention_policies() == sorted(list_retention_policies(), key=lambda p: p.policy_id)
    assert preview.can_cleanup_now is False
    assert handoff.can_execute_now is False


def test_cli_commands_render_read_only_summaries_and_usage(tmp_path: Path) -> None:
    for command in (
        "/storage-lifecycle-retention",
        "/storage-lifecycle-retention --summary",
        "/storage-lifecycle-cleanup-preview",
        "/storage-lifecycle-cleanup-preview --summary",
        "/storage-lifecycle-handoff",
        "/storage-lifecycle-handoff --summary",
    ):
        output = handle_slash_command(command, workspace_root=tmp_path)
        assert "metadata" in output
        assert "execution_enabled: False" in output or "execution_enabled=False" in output
        assert "No graph indexing" in output
    assert "Usage:" in handle_slash_command(
        "/storage-lifecycle-retention --bad", workspace_root=tmp_path
    )


def test_workspace_inspection_and_views_include_slice_h_summary(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    view = workspace_view_summary(inspection)
    summary = retention_cleanup_handoff_summary(workspace_root=tmp_path)
    for source in (
        inspection["storage_lifecycle_retention_summary"],
        view["storage_lifecycle_retention_summary"],
        summary,
    ):
        assert source["retention_policy_count"] >= 1
        assert source["cleanup_preview_count"] >= 1
        assert source["approval_handoff_count"] >= 1
        assert source["metadata_only"] is True
        assert source["cleanup_execution_enabled"] is False


def test_sqlite_migration_only_creates_allowed_metadata_tables(tmp_path: Path) -> None:
    tables = SQLiteStore(tmp_path).table_names()
    assert "phase3_storage_lifecycle_retention" in tables
    assert "phase3_storage_lifecycle_cleanup_previews" in tables
    assert "phase3_storage_lifecycle_approval_handoffs" in tables
    assert "phase3_storage_lifecycle_retention_events" in tables
    forbidden = {
        "graph_nodes",
        "graph_edges",
        "vectors",
        "vector_embeddings",
        "embeddings",
        "semantic_memory_writes",
        "rollback_execution",
        "plugin_execution",
        "external_channel_runtime",
        "remote_execution",
        "container_execution",
    }
    assert forbidden.isdisjoint(tables)


def test_all_unsafe_runtime_features_remain_disabled() -> None:
    assert graph_governance_status()["runtime_indexing_enabled"] is False
    status = semantic_memory_status()
    assert status["semantic_writes_enabled"] is False
    assert status["vector_writes_enabled"] is False
    assert status["embedding_backend"] == "disabled"
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


def test_catalog_contains_new_tools() -> None:
    text = Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    assert "Tool Name | Descriptions | Permissions | Implemented" in text
    for command in (
        "/storage-lifecycle-retention",
        "/storage-lifecycle-cleanup-preview",
        "/storage-lifecycle-handoff",
    ):
        assert command in text
