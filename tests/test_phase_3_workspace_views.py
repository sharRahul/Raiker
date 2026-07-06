from __future__ import annotations

import json
from copy import deepcopy

from raiker.cli.commands import handle_slash_command
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import (
    render_client_capability_summary,
    render_plugin_plan_summary,
    render_workspace_dashboard_summary,
    render_workspace_json_summary,
    render_workspace_text_summary,
)


def test_workspace_views_are_generated_from_shared_inspection_output(tmp_path) -> None:  # type: ignore[no-untyped-def]
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    view = render_workspace_json_summary(inspection)
    assert view["contract"] == inspection["contract"]
    assert view["runtime_status"] == inspection["runtime_status"]
    assert view["counts"]["tasks"] == len(inspection["tasks"])
    assert view["counts"]["approvals"] == len(inspection["approvals"])


def test_workspace_view_output_is_deterministic_and_json_serialisable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    inspection = inspect_workspace("dashboard", workspace_root=tmp_path)
    first = render_workspace_json_summary(inspection)
    second = render_workspace_json_summary(deepcopy(inspection))
    assert first == second
    json.dumps(first, sort_keys=True)
    json.dumps(render_workspace_dashboard_summary(inspection), sort_keys=True)
    assert render_workspace_text_summary(inspection) == render_workspace_text_summary(inspection)


def test_workspace_view_clients_receive_equivalent_read_only_data(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summaries = {
        client: render_workspace_json_summary(inspect_workspace(client, workspace_root=tmp_path))
        for client in ("terminal", "desktop", "web", "dashboard")
    }
    baseline = summaries["terminal"]
    for summary in summaries.values():
        assert set(summary) == set(baseline)
        assert summary["contract"]["read_only"] is True
        assert summary["contract"]["shared_contract_path"] is True
        assert summary["counts"] == baseline["counts"]
        assert summary["capability_gates"] == baseline["capability_gates"]


def test_workspace_view_does_not_mutate_or_activate_unsafe_runtime_paths(tmp_path) -> None:  # type: ignore[no-untyped-def]
    before = render_workspace_json_summary(inspect_workspace("terminal", workspace_root=tmp_path))
    _ = render_workspace_text_summary(inspect_workspace("desktop", workspace_root=tmp_path))
    after = render_workspace_json_summary(inspect_workspace("dashboard", workspace_root=tmp_path))
    assert after["counts"]["tasks"] == before["counts"]["tasks"] == 0
    assert after["counts"]["approvals"] == before["counts"]["approvals"] == 0
    assert after["semantic_memory"]["semantic_writes_enabled"] is False
    assert after["capability_gates"]["plugin_execution"]["runtime_enabled"] is False
    assert after["capability_gates"]["graph_codemap_indexing"]["runtime_enabled"] is False
    assert after["capability_gates"]["semantic_memory_writes"]["runtime_enabled"] is False
    assert after["capability_gates"]["external_channels"]["runtime_enabled"] is False
    # subagents / multi_agent_teams are integrated (real executors) -> enabled by default.
    assert after["capability_gates"]["subagents"]["runtime_enabled"] is True
    assert after["capability_gates"]["multi_agent_teams"]["runtime_enabled"] is True
    assert after["capability_gates"]["remote_execution"]["runtime_enabled"] is False
    assert after["capability_gates"]["container_execution"]["runtime_enabled"] is False
    assert all(
        profile["state"] != "enabled_runtime"
        for profile in after["execution_profiles"]
        if profile["kind"] in {"container", "ssh", "daytona"}
    )


def test_workspace_view_summaries_are_specific_and_redact_secret_like_values() -> None:
    inspection = {
        "contract": {
            "read_only": True,
            "shared_contract_path": True,
            "client": {"type": "terminal", "api_token": "secret-value"},
        },
        "runtime_status": {
            "workspace_root": "/tmp/example",
            "session_count": 0,
            "latest_session_id": None,
        },
        "recent_events": [],
        "checkpoint_timeline": [],
        "tasks": [],
        "approvals": [],
        "model_profiles": [],
        "channel_connectors": [],
        "capability_gates": {"plugin_execution": {"runtime_enabled": False}},
        "semantic_memory": {"semantic_writes_enabled": False},
        "execution_profiles": [],
        "plugin_registration_plans": [{"plugin_id": "demo", "password": "super-secret"}],
    }
    view = render_workspace_json_summary(inspection)
    assert view["contract"]["client"]["api_token"] == "[REDACTED]"
    assert (
        render_plugin_plan_summary(inspection)["plugin_registration_plans"][0]["password"]
        == "[REDACTED]"
    )
    assert render_client_capability_summary(inspection)["client"]["api_token"] == "[REDACTED]"


def test_workspace_view_cli_command_is_in_help_and_read_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert "/workspace-view" in handle_slash_command("/help", workspace_root=tmp_path)
    output = handle_slash_command("/workspace-view", workspace_root=tmp_path)
    assert "Workspace view:" in output
    assert "read_only: True" in output
    assert "shared_contract_path: True" in output
    assert handle_slash_command("/tasks", workspace_root=tmp_path) == "No tasks."
    assert handle_slash_command("/approvals", workspace_root=tmp_path) == "No pending approvals."
