from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from raiker.approval_audit import ApprovalAuditRecord
from raiker.approval_previews import ApprovalPreview, redact_secret_like_text
from raiker.contracts.ids import utc_now
from raiker.rollback_plans import RollbackPlan

REDACTED = "[REDACTED]"
ALLOWED_RECORD_TYPES = {
    "graph_index_plan_metadata",
    "semantic_memory_review_metadata",
    "approval_preview_metadata",
    "approval_audit_metadata",
    "rollback_plan_metadata",
}
ALLOWED_STATUSES = {
    "planned",
    "preview_only",
    "pending_approval",
    "denied",
    "approved_for_later",
    "expired",
    "superseded",
    "runtime_blocked",
}
SECRET_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "passwd",
    "pwd",
    "api_key",
    "apikey",
    "credential",
    "private_key",
    "proposed_text",
    "raw_text",
    "memory_text",
)


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{prefix}{hashlib.sha256(encoded).hexdigest()[:24]}"


def _secret_key(key: object) -> bool:
    return isinstance(key, str) and any(marker in key.lower() for marker in SECRET_KEY_MARKERS)


def redact_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): (REDACTED if _secret_key(k) else redact_metadata(v))
            for k, v in sorted(value.items(), key=lambda i: str(i[0]))
        }
    if isinstance(value, str):
        return redact_secret_like_text(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_metadata(v) for v in value]
    json.dumps(value, sort_keys=True, default=str)
    return value


def json_safe_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    safe = redact_metadata(value)
    if not isinstance(safe, dict):
        raise TypeError("metadata_must_be_object")
    json.dumps(safe, sort_keys=True)
    return safe


@dataclass(frozen=True)
class StorageLifecycleRecord:
    lifecycle_id: str
    target_capability: str
    record_type: str
    source_preview_id: str | None
    source_audit_id: str | None
    rollback_plan_id: str | None
    status: str
    created_at: str
    updated_at: str
    retention_policy: str
    redaction_policy: str
    can_write_runtime_data: bool
    runtime_writes_enabled: bool
    reasons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "lifecycle_id": self.lifecycle_id,
            "target_capability": self.target_capability,
            "record_type": self.record_type,
            "source_preview_id": self.source_preview_id,
            "source_audit_id": self.source_audit_id,
            "rollback_plan_id": self.rollback_plan_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retention_policy": self.retention_policy,
            "redaction_policy": self.redaction_policy,
            "can_write_runtime_data": self.can_write_runtime_data,
            "runtime_writes_enabled": self.runtime_writes_enabled,
            "reasons": self.reasons,
            "metadata": self.metadata,
        }


def create_storage_lifecycle_record(
    *,
    target_capability: str,
    record_type: str,
    status: str = "preview_only",
    source_preview_id: str | None = None,
    source_audit_id: str | None = None,
    rollback_plan_id: str | None = None,
    reasons: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    created_at: str | None = None,
) -> StorageLifecycleRecord:
    if record_type not in ALLOWED_RECORD_TYPES:
        raise ValueError(f"invalid_lifecycle_record_type:{record_type}")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid_lifecycle_status:{status}")
    safe_metadata = json_safe_metadata(dict(metadata or {}))
    safe_reasons = [redact_secret_like_text(reason) for reason in sorted(set(reasons or []))]
    timestamp = created_at or utc_now()
    identity = {
        "target_capability": target_capability,
        "record_type": record_type,
        "source_preview_id": source_preview_id,
        "source_audit_id": source_audit_id,
        "rollback_plan_id": rollback_plan_id,
        "status": status,
        "reasons": safe_reasons,
        "metadata": safe_metadata,
    }
    return StorageLifecycleRecord(
        lifecycle_id=_stable_id("slc_", identity),
        target_capability=target_capability,
        record_type=record_type,
        source_preview_id=source_preview_id,
        source_audit_id=source_audit_id,
        rollback_plan_id=rollback_plan_id,
        status=status,
        created_at=timestamp,
        updated_at=timestamp,
        retention_policy="metadata_only_until_phase3_runtime_storage_policy",
        redaction_policy="secret_like_values_redacted_no_raw_memory_text",
        can_write_runtime_data=False,
        runtime_writes_enabled=False,
        reasons=sorted(
            {*safe_reasons, "storage_lifecycle_metadata_only", "runtime_writes_disabled"}
        ),
        metadata=safe_metadata,
    )


def lifecycle_from_approval_preview(preview: ApprovalPreview) -> StorageLifecycleRecord:
    return create_storage_lifecycle_record(
        target_capability=preview.target_capability,
        record_type="approval_preview_metadata",
        status="runtime_blocked",
        source_preview_id=preview.preview_id,
        reasons=preview.reasons,
        metadata={
            "action_type": preview.action_type,
            "title": preview.title,
            "redacted_summary": preview.summary,
            "risk_level": preview.risk_level,
            "can_execute_now": preview.can_execute_now,
            "execution_enabled": preview.execution_enabled,
            "affected_path_count": len(preview.affected_paths),
            "affected_record_count": len(preview.affected_records),
        },
        created_at=preview.created_at,
    )


def lifecycle_from_approval_audit(record: ApprovalAuditRecord) -> StorageLifecycleRecord:
    return create_storage_lifecycle_record(
        target_capability=record.target_capability,
        record_type="approval_audit_metadata",
        status="runtime_blocked",
        source_preview_id=record.preview_id,
        source_audit_id=record.audit_id,
        rollback_plan_id=record.rollback_plan_id,
        reasons=record.reasons,
        metadata={
            "action_type": record.action_type,
            "decision": record.decision,
            "decision_status": record.decision_status,
            "risk_level": record.risk_level,
            "redacted_summary": record.redacted_summary,
            "execution_enabled": record.execution_enabled,
        },
        created_at=record.created_at,
    )


def lifecycle_from_rollback_plan(plan: RollbackPlan) -> StorageLifecycleRecord:
    return create_storage_lifecycle_record(
        target_capability=plan.target_capability,
        record_type="rollback_plan_metadata",
        status="preview_only",
        source_preview_id=plan.source_preview_id,
        rollback_plan_id=plan.rollback_plan_id,
        reasons=plan.reasons,
        metadata={
            "action_type": plan.action_type,
            "reversible": plan.reversible,
            "rollback_available": plan.rollback_available,
            "rollback_step_count": len(plan.rollback_steps),
            "rollback_execution_enabled": plan.rollback_execution_enabled,
        },
        created_at=plan.created_at,
    )
