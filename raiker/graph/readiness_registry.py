from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.graph.readiness import (
    DISABLED_RUNTIME_FLAGS,
    GraphCodemapReadinessContract,
    create_readiness_contract,
)
from raiker.readiness.registry import (
    get_readiness_by_id,
    render_readiness_records,
    sort_readiness_records,
    summarize_readiness_records,
)
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
                    json.dumps(DISABLED_RUNTIME_FLAGS, sort_keys=True),
                    json.dumps(record.to_dict()["blockers"], sort_keys=True),
                    json.dumps(record.to_dict(), sort_keys=True),
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
    return sort_readiness_records(records)


def get_graph_readiness_metadata(readiness_id: str) -> GraphCodemapReadinessContract | None:
    return get_readiness_by_id(list(_RECORDS.values()), readiness_id)


def graph_readiness_summary(*, workspace_root: str | Path = ".") -> dict[str, Any]:
    records = list_graph_readiness_metadata(workspace_root=workspace_root)
    latest = records[-1] if records else create_graph_readiness_metadata(workspace_root=workspace_root)
    summary = summarize_readiness_records(
        records,
        latest_key="latest_readiness_id",
        count_key="graph_readiness_record_count",
        metadata_only_key="graph_readiness_contract_available",
    )
    summary.update({
        "ready_for_indexing": False,
        "graph_indexing_enabled": False,
        "graph_writes_enabled": False,
        "codemap_indexing_enabled": False,
        "indexing_jobs_enabled": False,
        "runtime_jobs_enabled": False,
        "workers_enabled": False,
        "schedulers_enabled": False,
        "file_watchers_enabled": False,
        "daemons_enabled": False,
        "runtime_execution_enabled": False,
        "blocker_count": len(latest.blockers),
        "required_gate_count": len(latest.required_gates),
    })
    return summary


def render_graph_readiness(*, workspace_root: str | Path = ".") -> str:
    summary = graph_readiness_summary(workspace_root=workspace_root)
    lines = ["Graph/codemap indexing readiness:", "persistence: metadata_only_optional_sqlite", "runtime_jobs_enabled: False"]
    lines.extend(render_readiness_records(summary))
    return "\n".join(lines)
