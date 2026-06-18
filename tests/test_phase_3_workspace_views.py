from __future__ import annotations

import json
from typing import Any, cast

from raiker.contracts.models import ToolAction
from raiker.events.writer import EventLogWriter
from raiker.memory.candidates import create_deferred_candidate
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import (
    render_client_capability_summary,
    render_dashboard_summary,
    render_plugin_plan_summary,
    render_workspace_json_view,
    render_workspace_text_view,
)


def test_workspace_views_use_shared_inspection_contract(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summary = inspect_workspace("desktop", workspace_root=tmp_path)
    json_view = render_workspace_json_view(summary)
    dashboard = render_dashboard_summary(summary)
    client = render_client_capability_summary(summary)
    plugin = render_plugin_plan_summary(summary)
    assert cast(dict[str, Any], json_view["contract"])["service"] == "workspace_inspection"
    assert dashboard["service"] == "workspace_inspection"
    assert client["read_only"] is True
    assert plugin["read_only"] is True
    assert plugin["execution_enabled"] is False


def test_workspace_text_view_is_deterministic(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summary = inspect_workspace("terminal", workspace_root=tmp_path)
    assert render_workspace_text_view(summary) == render_workspace_text_view(summary)


def test_json_and_dashboard_views_are_json_serializable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summary = inspect_workspace("web", workspace_root=tmp_path)
    json.dumps(render_workspace_json_view(summary), sort_keys=True)
    json.dumps(render_dashboard_summary(summary), sort_keys=True)


def test_clients_receive_equivalent_read_only_view_data(tmp_path) -> None:  # type: ignore[no-untyped-def]
    views = [render_dashboard_summary(inspect_workspace(client, workspace_root=tmp_path)) for client in ("terminal", "desktop", "web", "dashboard")]
    counts = [view["counts"] for view in views]
    assert counts[0] == counts[1] == counts[2] == counts[3]
    for view in views:
        assert view["read_only"] is True
        assert cast(dict[str, Any], view["safety"])["privileged"] is False


def test_views_do_not_mutate_state_or_activate_disabled_runtime_paths(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    store.create_session("sess_test", str(tmp_path), "test")
    task = TaskManager(store, writer).create_task(session_id="sess_test", title="Read", objective="Only")
    action = ToolAction(action_id="act_test", tool_name="write_file", arguments={}, risk_level="high", requires_approval=True)
    store.insert_tool_action(action, "sess_test", None, "approval_required")
    store.insert_approval("approval_test", action.action_id)
    store.insert_memory_candidate(create_deferred_candidate("evt_test", "remember later"))
    before = (len(store.list_tasks()), len(store.list_approvals()), len(store.list_memory_candidates()))

    summary = inspect_workspace("dashboard", workspace_root=tmp_path)
    render_workspace_text_view(summary)
    render_workspace_json_view(summary)
    render_dashboard_summary(summary)
    render_client_capability_summary(summary)
    render_plugin_plan_summary(summary)

    after_summary = inspect_workspace("dashboard", workspace_root=tmp_path)
    after = (len(store.list_tasks()), len(store.list_approvals()), len(store.list_memory_candidates()))
    assert before == after == (1, 1, 1)
    assert after_summary["tasks"][0]["task_id"] == task.task_id
    assert after_summary["semantic_memory"]["semantic_writes_enabled"] is False
    assert after_summary["capability_gates"]["plugin_execution"]["runtime_enabled"] is False
    assert after_summary["capability_gates"]["external_channels"]["runtime_enabled"] is False
    assert after_summary["capability_gates"]["remote_execution"]["runtime_enabled"] is False
    assert after_summary["capability_gates"]["container_execution"]["runtime_enabled"] is False


def test_workspace_views_redact_secret_like_values() -> None:
    view = render_workspace_json_view({"api_token": "abc", "nested": {"password": "pw"}})
    assert view["api_token"] == "[redacted]"
    assert cast(dict[str, Any], view["nested"])["password"] == "[redacted]"


def test_workspace_views_handle_unknown_or_missing_fields_gracefully() -> None:
    text = render_workspace_text_view({"unexpected": object()})
    dashboard = render_dashboard_summary({"unexpected": object()})
    assert "Workspace view:" in text
    assert dashboard["read_only"] is True
