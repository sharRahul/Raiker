from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.approval_audit_registry import create_workspace_audit_records
from raiker.approval_preview_registry import (
    create_fresh_graph_preview_for_workspace,
    create_fresh_memory_preview_for_workspace,
)
from raiker.contracts.ids import utc_now
from raiker.rollback_registry import create_workspace_rollback_plans
from raiker.storage.lifecycle import (
    StorageLifecycleRecord,
    create_storage_lifecycle_record,
    lifecycle_from_approval_audit,
    lifecycle_from_approval_preview,
    lifecycle_from_rollback_plan,
)

_RECORDS: dict[str, StorageLifecycleRecord] = {}
_WORKSPACE_RECORDS: dict[str, dict[str, StorageLifecycleRecord]] = {}


def create_lifecycle_record(
    record: StorageLifecycleRecord | None = None, **kwargs: Any
) -> StorageLifecycleRecord:
    lifecycle = record or create_storage_lifecycle_record(**kwargs)
    _RECORDS[lifecycle.lifecycle_id] = lifecycle
    return lifecycle


def seed_workspace_lifecycle_records(
    workspace_root: str | Path = ".",
) -> list[StorageLifecycleRecord]:
    workspace_key = str(Path(workspace_root).resolve())
    records: list[StorageLifecycleRecord] = []
    graph_preview = create_fresh_graph_preview_for_workspace(workspace_root)
    records.append(create_lifecycle_record(lifecycle_from_approval_preview(graph_preview)))
    memory_preview = create_fresh_memory_preview_for_workspace(workspace_root)
    if memory_preview is not None:
        records.append(create_lifecycle_record(lifecycle_from_approval_preview(memory_preview)))
    for audit in create_workspace_audit_records(workspace_root):
        records.append(create_lifecycle_record(lifecycle_from_approval_audit(audit)))
    for plan in create_workspace_rollback_plans(workspace_root):
        records.append(create_lifecycle_record(lifecycle_from_rollback_plan(plan)))
    workspace_records = {r.lifecycle_id: r for r in records}
    _WORKSPACE_RECORDS[workspace_key] = workspace_records
    return sorted(workspace_records.values(), key=lambda r: r.lifecycle_id)


def list_lifecycle_records(
    *, target_capability: str | None = None, workspace_root: str | Path | None = None
) -> list[StorageLifecycleRecord]:
    if workspace_root is not None:
        return (
            seed_workspace_lifecycle_records(workspace_root)
            if target_capability is None
            else [
                r
                for r in seed_workspace_lifecycle_records(workspace_root)
                if r.target_capability == target_capability
            ]
        )
    records = list(_RECORDS.values())
    if target_capability is not None:
        records = [r for r in records if r.target_capability == target_capability]
    return sorted(records, key=lambda r: r.lifecycle_id)


def get_lifecycle_record(lifecycle_id: str) -> StorageLifecycleRecord | None:
    return _RECORDS.get(lifecycle_id)


def _with_status(record: StorageLifecycleRecord, status: str) -> StorageLifecycleRecord:
    updated = create_storage_lifecycle_record(
        target_capability=record.target_capability,
        record_type=record.record_type,
        status=status,
        source_preview_id=record.source_preview_id,
        source_audit_id=record.source_audit_id,
        rollback_plan_id=record.rollback_plan_id,
        reasons=record.reasons + [f"lifecycle_status_changed_to_{status}"],
        metadata=record.metadata,
        created_at=record.created_at,
    )
    updated = StorageLifecycleRecord(
        **(updated.to_dict() | {"lifecycle_id": record.lifecycle_id, "updated_at": utc_now()})
    )
    _RECORDS[record.lifecycle_id] = updated
    return updated


def expire_lifecycle_record(lifecycle_id: str) -> StorageLifecycleRecord:
    record = _RECORDS[lifecycle_id]
    return _with_status(record, "expired")


def supersede_lifecycle_record(lifecycle_id: str) -> StorageLifecycleRecord:
    record = _RECORDS[lifecycle_id]
    return _with_status(record, "superseded")


def storage_lifecycle_summary(*, workspace_root: str | Path = ".") -> dict[str, Any]:
    records = list_lifecycle_records(workspace_root=workspace_root)
    by_target: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for record in records:
        by_target[record.target_capability] = by_target.get(record.target_capability, 0) + 1
        by_status[record.status] = by_status.get(record.status, 0) + 1
    return {
        "lifecycle_planning_available": True,
        "lifecycle_record_count": len(records),
        "graph_lifecycle_records": by_target.get("graph_codemap_indexing", 0),
        "memory_lifecycle_records": by_target.get("semantic_memory_writes", 0),
        "preview_only_count": by_status.get("preview_only", 0),
        "runtime_blocked_count": by_status.get("runtime_blocked", 0),
        "runtime_writes_enabled": False,
        "graph_runtime_writes_enabled": False,
        "semantic_runtime_writes_enabled": False,
        "counts_by_target_capability": dict(sorted(by_target.items())),
        "counts_by_status": dict(sorted(by_status.items())),
    }


def render_lifecycle_summary(
    *,
    workspace_root: str | Path = ".",
    target_capability: str | None = None,
    summary_only: bool = False,
) -> str:
    summary = storage_lifecycle_summary(workspace_root=workspace_root)
    records = list_lifecycle_records(
        target_capability=target_capability, workspace_root=workspace_root
    )
    lines = [
        "Storage lifecycle metadata:",
        "persistence: in_memory_only_not_persisted",
        "runtime_writes_enabled: False",
    ]
    if summary_only:
        lines.extend(f"{k}: {v}" for k, v in summary.items())
        return "\n".join(lines)
    lines.append(f"record_count: {len(records)}")
    if target_capability:
        lines.append(f"target_capability: {target_capability}")
    for record in records[:20]:
        lines.append(
            f"- {record.lifecycle_id} target={record.target_capability} type={record.record_type} status={record.status} runtime_writes_enabled={record.runtime_writes_enabled}"
        )
    return "\n".join(lines)
