from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.plugins.readiness import (
    DISABLED_RUNTIME_FLAGS,
    PluginServerStartupReadinessContract,
    create_plugin_server_startup_readiness_contract,
)
from raiker.readiness.registry import (
    get_readiness_by_id,
    render_readiness_records,
    sort_readiness_records,
    summarize_readiness_records,
)
from raiker.storage.sqlite import SQLiteStore

_RECORDS: dict[str, PluginServerStartupReadinessContract] = {}


def _workspace_id(workspace_root: str | Path) -> str:
    return str(Path(workspace_root).resolve())


def create_plugin_readiness_metadata(*, workspace_root: str | Path = ".", persist: bool = False, **kwargs: Any) -> PluginServerStartupReadinessContract:
    record = create_plugin_server_startup_readiness_contract(workspace_id=_workspace_id(workspace_root), **kwargs)
    _RECORDS[record.readiness_id] = record
    if persist:
        store = SQLiteStore(workspace_root)
        with store.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO phase3_plugin_server_startup_readiness
                (readiness_id, target, status, blockers_json, disabled_runtime_flags_json, contract_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.readiness_id,
                    record.target_capability,
                    "metadata_only_blocked",
                    json.dumps(record.to_dict()["blockers"], sort_keys=True),
                    json.dumps(DISABLED_RUNTIME_FLAGS, sort_keys=True),
                    json.dumps(record.to_dict(), sort_keys=True),
                ),
            )
    return record


def list_plugin_readiness_metadata(*, workspace_root: str | Path | None = None) -> list[PluginServerStartupReadinessContract]:
    records = list(_RECORDS.values())
    if workspace_root is not None:
        workspace = _workspace_id(workspace_root)
        records = [record for record in records if record.workspace_id == workspace]
        if not records:
            records = [create_plugin_readiness_metadata(workspace_root=workspace_root)]
    return sort_readiness_records(records)


def get_plugin_readiness_metadata(readiness_id: str) -> PluginServerStartupReadinessContract | None:
    return get_readiness_by_id(list(_RECORDS.values()), readiness_id)


def plugin_readiness_summary(*, workspace_root: str | Path = ".") -> dict[str, Any]:
    records = list_plugin_readiness_metadata(workspace_root=workspace_root)
    latest = records[-1] if records else create_plugin_readiness_metadata(workspace_root=workspace_root)
    summary = summarize_readiness_records(
        records,
        latest_key="latest_readiness_id",
        count_key="plugin_server_readiness_record_count",
        metadata_only_key="plugin_server_readiness_contract_available",
    )
    summary.update({
        "ready_for_plugin_server_startup": False,
        **DISABLED_RUNTIME_FLAGS,
        "blocker_count": len(latest.blockers),
        "required_gate_count": len(latest.required_gates),
    })
    return summary


def render_plugin_readiness(*, workspace_root: str | Path = ".") -> str:
    summary = plugin_readiness_summary(workspace_root=workspace_root)
    lines = [
        "Plugin/server startup readiness:",
        "persistence: metadata_only_optional_sqlite",
        "plugin_server_startup_enabled: False",
    ]
    lines.extend(render_readiness_records(summary))
    return "\n".join(lines)
