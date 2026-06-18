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
from raiker.storage.lifecycle_retention import (
    StorageLifecycleApprovalHandoff,
    StorageLifecycleCleanupPreview,
    StorageLifecycleRetentionPolicy,
)
from raiker.storage.lifecycle_retention import (
    create_approval_handoff as _create_approval_handoff,
)
from raiker.storage.lifecycle_retention import (
    create_cleanup_preview as _create_cleanup_preview,
)
from raiker.storage.lifecycle_retention import (
    create_retention_policy as _create_retention_policy,
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

_RETENTION_POLICIES: dict[str, StorageLifecycleRetentionPolicy] = {}
_CLEANUP_PREVIEWS: dict[str, StorageLifecycleCleanupPreview] = {}
_APPROVAL_HANDOFFS: dict[str, StorageLifecycleApprovalHandoff] = {}


def create_retention_policy_metadata(**kwargs: Any) -> StorageLifecycleRetentionPolicy:
    policy = _create_retention_policy(**kwargs)
    _RETENTION_POLICIES[policy.policy_id] = policy
    return policy


def list_retention_policies() -> list[StorageLifecycleRetentionPolicy]:
    return sorted(_RETENTION_POLICIES.values(), key=lambda p: p.policy_id)


def create_cleanup_preview_metadata(**kwargs: Any) -> StorageLifecycleCleanupPreview:
    preview = _create_cleanup_preview(**kwargs)
    _CLEANUP_PREVIEWS[preview.preview_id] = preview
    return preview


def list_cleanup_previews() -> list[StorageLifecycleCleanupPreview]:
    return sorted(_CLEANUP_PREVIEWS.values(), key=lambda p: p.preview_id)


def get_cleanup_preview(preview_id: str) -> StorageLifecycleCleanupPreview | None:
    return _CLEANUP_PREVIEWS.get(preview_id)


def create_approval_handoff_metadata(**kwargs: Any) -> StorageLifecycleApprovalHandoff:
    handoff = _create_approval_handoff(**kwargs)
    _APPROVAL_HANDOFFS[handoff.handoff_id] = handoff
    return handoff


def list_approval_handoffs() -> list[StorageLifecycleApprovalHandoff]:
    return sorted(_APPROVAL_HANDOFFS.values(), key=lambda h: h.handoff_id)


def get_approval_handoff(handoff_id: str) -> StorageLifecycleApprovalHandoff | None:
    return _APPROVAL_HANDOFFS.get(handoff_id)


def seed_workspace_retention_cleanup_handoffs(workspace_root: str | Path = ".") -> dict[str, Any]:
    records = seed_workspace_lifecycle_records(workspace_root)
    lifecycle_ids = [record.lifecycle_id for record in records]
    for target in sorted({r.target_capability for r in records}):
        create_retention_policy_metadata(
            lifecycle_target_type=target,
            retention_class="audit_metadata",
            expiry_rule="manual_review_required",
            cleanup_eligible=False,
            reason_summary=f"metadata-only retention planning for {target}",
        )
    expired = sum(1 for r in records if r.status == "expired")
    superseded = sum(1 for r in records if r.status == "superseded")
    preview = create_cleanup_preview_metadata(
        linked_lifecycle_ids=lifecycle_ids,
        expired_candidate_count=expired,
        superseded_candidate_count=superseded,
        summaries=["cleanup preview only; execution denied"],
    )
    handoff = create_approval_handoff_metadata(
        linked_lifecycle_ids=lifecycle_ids,
        target_capability="storage_lifecycle_metadata",
        approval_state="requires_future_policy",
        source_preview_ids=[preview.preview_id],
        summary="approval handoff is planned only; no relay or execution",
    )
    return {"retention_policies": list_retention_policies(), "cleanup_previews": list_cleanup_previews(), "approval_handoffs": list_approval_handoffs(), "latest_cleanup_preview": preview, "latest_approval_handoff": handoff}


def retention_cleanup_handoff_summary(*, workspace_root: str | Path = ".") -> dict[str, Any]:
    seed_workspace_retention_cleanup_handoffs(workspace_root)
    lifecycle = storage_lifecycle_summary(workspace_root=workspace_root)
    previews = list_cleanup_previews()
    return {
        "retention_policy_count": len(list_retention_policies()),
        "cleanup_preview_count": len(previews),
        "approval_handoff_count": len(list_approval_handoffs()),
        "expired_lifecycle_count": lifecycle["counts_by_status"].get("expired", 0),
        "superseded_lifecycle_count": lifecycle["counts_by_status"].get("superseded", 0),
        "metadata_only": True,
        "cleanup_execution_enabled": False,
        "approval_handoff_execution_enabled": False,
        "graph_indexing_enabled": False,
        "semantic_memory_writes_enabled": False,
        "vector_writes_enabled": False,
        "embedding_creation_enabled": False,
        "rollback_execution_enabled": False,
        "plugin_channel_subagent_remote_container_execution_enabled": False,
    }


def render_retention_cleanup_handoff(kind: str, *, workspace_root: str | Path = ".", summary_only: bool = False) -> str:
    seed_workspace_retention_cleanup_handoffs(workspace_root)
    summary = retention_cleanup_handoff_summary(workspace_root=workspace_root)
    lines = [
        f"Storage lifecycle {kind} metadata:",
        "metadata_only: True",
        "execution_enabled: False",
        "No graph indexing, semantic memory writes, embeddings, vectors, rollback, plugins, channels, subagents, remote/container execution.",
    ]
    if summary_only:
        lines.extend(f"{k}: {v}" for k, v in summary.items())
        return "\n".join(lines)
    if kind == "retention":
        lines.extend(f"- {p.policy_id} target={p.lifecycle_target_type} class={p.retention_class} expiry={p.expiry_rule} cleanup_eligible={p.cleanup_eligible}" for p in list_retention_policies()[:20])
    elif kind == "cleanup-preview":
        lines.extend(f"- {p.preview_id} linked={len(p.linked_lifecycle_ids)} expired={p.expired_candidate_count} superseded={p.superseded_candidate_count} can_cleanup_now={p.can_cleanup_now}" for p in list_cleanup_previews()[:20])
    else:
        lines.extend(f"- {h.handoff_id} target={h.target_capability} state={h.approval_state} can_execute_now={h.can_execute_now}" for h in list_approval_handoffs()[:20])
    return "\n".join(lines)
