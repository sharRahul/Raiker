from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.cli.commands import handle_slash_command
from raiker.plugins.readiness import (
    DISABLED_RUNTIME_FLAGS,
    PluginServerStartupReadinessContract,
    create_plugin_server_startup_readiness_contract,
)
from raiker.plugins.readiness_registry import (
    create_plugin_readiness_metadata,
    get_plugin_readiness_metadata,
    list_plugin_readiness_metadata,
    plugin_readiness_summary,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import workspace_view_summary


def test_contract_deterministic_ids_flags_and_serialization() -> None:
    first = create_plugin_server_startup_readiness_contract(workspace_id="workspace")
    second = create_plugin_server_startup_readiness_contract(workspace_id="workspace")
    assert first.readiness_id == second.readiness_id
    assert first.readiness_id.startswith("pssr_")
    data = first.to_dict()
    assert data["metadata_only"] is True
    assert data["ready_for_plugin_server_startup"] is False
    for key, value in DISABLED_RUNTIME_FLAGS.items():
        assert data[key] is value is False
    assert first.to_json() == second.to_json()
    assert json.loads(first.to_json()) == data


def test_contract_rejects_empty_blockers_and_non_json_safe_metadata() -> None:
    with pytest.raises(ValueError, match="blockers must be non-empty"):
        PluginServerStartupReadinessContract(blockers=())
    with pytest.raises(ValueError, match="metadata must contain only JSON-safe values"):
        create_plugin_server_startup_readiness_contract(metadata={"bad": object()})
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        create_plugin_server_startup_readiness_contract(metadata={1: "bad"})  # type: ignore[dict-item]


def test_registry_create_list_get_summary_and_sqlite_boundaries(tmp_path: Path) -> None:
    record = create_plugin_readiness_metadata(workspace_root=tmp_path, persist=True)
    assert get_plugin_readiness_metadata(record.readiness_id) == record
    assert record in list_plugin_readiness_metadata(workspace_root=tmp_path)
    summary = plugin_readiness_summary(workspace_root=tmp_path)
    assert summary["plugin_server_readiness_contract_available"] is True
    assert summary["latest_readiness_id"].startswith("pssr_")
    tables = SQLiteStore(tmp_path).table_names()
    assert "phase3_plugin_server_startup_readiness" in tables
    forbidden = {
        "plugin_execution_jobs",
        "plugin_activation_records",
        "mcp_server_runtime_state",
        "lsp_server_runtime_state",
        "plugin_server_runtime_state",
        "monitor_daemon_state",
        "hosted_routine_state",
        "marketplace_install_state",
        "external_channel_state",
        "approval_relay_runtime_state",
        "worker_queues",
        "scheduler_state",
        "daemon_state",
        "runtime_execution_state",
    }
    assert forbidden.isdisjoint(tables)


def test_plugin_readiness_cli_modes_are_metadata_only(tmp_path: Path) -> None:
    output = handle_slash_command("/plugin-readiness", workspace_root=tmp_path)
    assert "Plugin/server startup readiness:" in output
    assert "plugin_server_startup_enabled: False" in output
    assert "workers_enabled: False" in output
    summary = handle_slash_command("/plugin-readiness --summary", workspace_root=tmp_path)
    assert "Plugin/server startup readiness summary:" in summary
    assert "runtime_execution_enabled: False" in summary
    payload = json.loads(handle_slash_command("/plugin-readiness --json", workspace_root=tmp_path))
    assert payload["metadata_only"] is True
    assert payload["ready_for_plugin_server_startup"] is False
    assert handle_slash_command("/plugin-readiness --start", workspace_root=tmp_path) == "Usage: /plugin-readiness [--summary|--json]"
    assert "/plugin-readiness [--summary|--json]" in handle_slash_command("/help", workspace_root=tmp_path)


def test_workspace_surfaces_include_plugin_readiness(tmp_path: Path) -> None:
    inspection = inspect_workspace("terminal", workspace_root=tmp_path)
    readiness = inspection["plugin_server_startup_readiness"]
    assert readiness["metadata_only"] is True
    assert readiness["ready_for_plugin_server_startup"] is False
    assert readiness["plugin_execution_enabled"] is False
    assert readiness["plugin_installation_enabled"] is False
    assert readiness["plugin_activation_enabled"] is False
    assert readiness["mcp_server_startup_enabled"] is False
    assert readiness["lsp_server_startup_enabled"] is False
    assert readiness["plugin_server_startup_enabled"] is False
    assert readiness["monitor_daemon_startup_enabled"] is False
    assert readiness["marketplace_installs_enabled"] is False
    assert readiness["external_channels_enabled"] is False
    assert readiness["workers_enabled"] is False
    view = workspace_view_summary(inspection)["plugin_server_startup_readiness"]
    assert view["latest_readiness_id"].startswith("pssr_")
    assert view["blocker_count"] > 0


def test_docs_catalog_event_consistency() -> None:
    for path in [
        Path("docs/architecture/IMPLEMENTATION_STATUS.md"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "Slice N" in text
        assert "plugin" in text.lower()
        assert (
            "Phase 3 remains incomplete" in text
            or "Phase 3 is complete" in text
        )
        assert "Phase 4 remains blocked" in text
