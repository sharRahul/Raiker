from __future__ import annotations

from raiker.agents.subagents import plan_subagent
from raiker.channels.governance import external_channel_activation_status
from raiker.cli.commands import handle_slash_command
from raiker.execution.profiles import list_execution_profiles, plan_remote_execution
from raiker.graph.schema import GraphEdgePlan, GraphNodePlan, plan_codemap_record
from raiker.memory.semantic import semantic_memory_status
from raiker.plugins.manifest import validate_plugin_manifest


def test_plugin_manifest_validation_never_enables_execution() -> None:
    result = validate_plugin_manifest(
        {"id": "demo", "name": "Demo", "version": "1.0.0", "permissions": ["tool:read_file"]}
    )
    assert result.valid is True
    assert result.execution_enabled is False
    assert validate_plugin_manifest({"id": "bad", "permissions": ["shell"]}).valid is False


def test_graph_codemap_plan_is_schema_only_and_detects_dangling_edges() -> None:
    plan = plan_codemap_record(
        [GraphNodePlan("file", "a.py", "a.py", "test")],
        [GraphEdgePlan("a.py", "missing.py", "imports", "test")],
    )
    assert plan["can_index"] is False
    assert plan["dangling_edge_count"] == 1


def test_semantic_memory_status_is_disabled_by_default() -> None:
    status = semantic_memory_status(candidate_count=2)
    assert status["semantic_writes_enabled"] is False
    assert status["candidate_count"] == 2


def test_execution_profiles_are_listable_but_remote_execution_is_denied() -> None:
    profile_ids = {profile.profile_id for profile in list_execution_profiles()}
    assert "container_default" in profile_ids
    assert plan_remote_execution("container_default", "echo hi")["can_execute"] is False


def test_subagents_and_external_channels_are_planned_but_inert() -> None:
    assert plan_subagent("task_1", "reviewer", "review").can_spawn is False
    channel = external_channel_activation_status("channel.slack", paired=True)
    assert channel["active"] is False
    assert channel["approval_relay_enabled"] is False


def test_phase_3_phase_4_terminal_inspection_commands(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert "plugin_execution: disabled" in handle_slash_command(
        "/capabilities", workspace_root=tmp_path
    )
    assert "container_default" in handle_slash_command(
        "/execution-profiles", workspace_root=tmp_path
    )
    assert "semantic_writes_enabled: False" in handle_slash_command(
        "/semantic-memory", workspace_root=tmp_path
    )
