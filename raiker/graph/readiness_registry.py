from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.graph.readiness import GraphCodemapReadinessContract, create_readiness_contract
from raiker.storage.sqlite import SQLiteStore

_RECORDS: dict[str, GraphCodemapReadinessContract] = {}


def _workspace_id(workspace_root: str | Path) -> str:
    return str(Path(workspace_root).resolve())


def create_graph_readiness_metadata(*, workspace_root: str | Path = ".", persist: bool = False, **kwargs: Any) -> GraphCodemapReadinessContract:
    record = create_readiness_contract(workspace_id=_workspace_id(workspace_root), **kwargs)
    _RECORDS[record.readiness_id] = record
    if persist:
        store = SQLiteStore(workspace_root)
        with store.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO phase3_graph_codemap_readiness
                (readiness_id, workspace_id, target_capability, metadata_only, ready_for_indexing, runtime_flags_json, blockers_json, contract_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.readiness_id,
                    record.workspace_id,
                    record.target_capability,
                    1,
                    0,
                    '{"graph_indexing_enabled": false, "graph_writes_enabled": false, "runtime_jobs_enabled": false}',
                    __import__("json").dumps(record.to_dict()["blockers"], sort_keys=True),
                    __import__("json").dumps(record.to_dict(), sort_keys=True),
                ),
            )
    return record


def list_graph_readiness_metadata(*, workspace_root: str | Path | None = None) -> list[GraphCodemapReadinessContract]:
    records = list(_RECORDS.values())
    if workspace_root is not None:
        workspace = _workspace_id(workspace_root)
        records = [record for record in records if record.workspace_id == workspace]
        if not records:
            records = [create_graph_readiness_metadata(workspace_root=workspace_root)]
    return sorted(records, key=lambda record: record.readiness_id)


def get_graph_readiness_metadata(readiness_id: str) -> GraphCodemapReadinessContract | None:
    return _RECORDS.get(readiness_id)


def graph_readiness_summary(*, workspace_root: str | Path = ".") -> dict[str, Any]:
    records = list_graph_readiness_metadata(workspace_root=workspace_root)
    latest = records[-1] if records else create_graph_readiness_metadata(workspace_root=workspace_root)
    return {
        "graph_readiness_contract_available": True,
        "graph_readiness_record_count": len(records),
        "latest_readiness_id": latest.readiness_id,
        "metadata_only": True,
        "ready_for_indexing": False,
        "graph_indexing_enabled": False,
        "graph_writes_enabled": False,
        "runtime_jobs_enabled": False,
        "workers_enabled": False,
        "schedulers_enabled": False,
        "file_watchers_enabled": False,
        "daemons_enabled": False,
        "blocker_count": len(latest.blockers),
        "required_gate_count": len(latest.required_gates),
    }


def render_graph_readiness(*, workspace_root: str | Path = ".") -> str:
    summary = graph_readiness_summary(workspace_root=workspace_root)
    lines = ["Graph/codemap indexing readiness:", "persistence: metadata_only_optional_sqlite", "runtime_jobs_enabled: False"]
    lines.extend(f"{key}: {value}" for key, value in summary.items())
    return "\n".join(lines)
