from __future__ import annotations

from pathlib import Path
from typing import cast

from raiker.approval_audit import ApprovalAuditRecord, create_approval_audit_record
from raiker.approval_preview_registry import (
    create_fresh_graph_preview_for_workspace,
    create_fresh_memory_preview_for_workspace,
)
from raiker.memory.review import MemoryReviewQueue
from raiker.rollback_plans import create_graph_rollback_plan, create_memory_rollback_plan


class ApprovalAuditRegistry:
    """In-memory preview-only audit registry; it never executes approved actions."""

    def __init__(self) -> None:
        self._records: dict[str, ApprovalAuditRecord] = {}

    def add(self, record: ApprovalAuditRecord) -> ApprovalAuditRecord:
        self._records[record.audit_id] = record
        return record

    def list_records(self) -> list[ApprovalAuditRecord]:
        return [self._records[key] for key in sorted(self._records)]


def create_workspace_audit_records(workspace_root: str | Path = ".") -> list[ApprovalAuditRecord]:
    records: list[ApprovalAuditRecord] = []
    graph_preview = create_fresh_graph_preview_for_workspace(workspace_root)
    records.append(create_approval_audit_record(graph_preview, rollback_plan=create_graph_rollback_plan(graph_preview)))
    memory_preview = create_fresh_memory_preview_for_workspace(workspace_root)
    if memory_preview is not None:
        decision = "denied" if "secret_or_credential_like_candidate_blocked" in memory_preview.reasons else "approval_requested"
        records.append(create_approval_audit_record(memory_preview, decision=decision, rollback_plan=create_memory_rollback_plan(memory_preview)))
    return records


def approval_audit_summary(*, workspace_root: str | Path = ".") -> dict[str, object]:
    records = create_workspace_audit_records(workspace_root)
    queue_summary = MemoryReviewQueue(workspace_root).export_summary()
    approved = cast(int, queue_summary["approved_for_later_count"])
    denied = sum(1 for record in records if record.decision == "denied")
    blocked = sum(1 for record in records if record.decision_status == "execution_blocked")
    return {
        "audit_preview_available": True,
        "audit_record_count": len(records),
        "denied_count": denied,
        "approved_for_later_count": approved,
        "execution_blocked_count": blocked,
        "execution_enabled": False,
    }
