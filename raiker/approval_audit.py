from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from raiker.approval_previews import ApprovalPreview, redact_secret_like_text
from raiker.contracts.views import View
from raiker.rollback_plans import RollbackPlan

DECISION_STATES = {
    "preview_created",
    "approval_requested",
    "approved_for_later",
    "denied",
    "expired",
    "superseded",
    "execution_blocked",
}


@dataclass(frozen=True)
class ApprovalAuditRecord(View):
    audit_id: str
    preview_id: str
    action_type: str
    target_capability: str
    decision: str
    decision_status: str
    requested_by: str
    reviewer: str | None
    created_at: str
    decided_at: str | None
    risk_level: str
    policy_decision: str
    reasons: list[str]
    safety_notes: list[str]
    expected_events: list[str]
    can_execute_now: bool
    execution_enabled: bool
    reversible: bool
    rollback_plan_id: str | None
    redacted_summary: str


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{prefix}{hashlib.sha256(encoded).hexdigest()[:24]}"


def create_approval_audit_record(
    preview: ApprovalPreview,
    *,
    decision: str = "preview_created",
    reviewer: str | None = None,
    decided_at: str | None = None,
    rollback_plan: RollbackPlan | None = None,
) -> ApprovalAuditRecord:
    if decision not in DECISION_STATES:
        raise ValueError(f"invalid_approval_audit_decision:{decision}")
    execution_blocked = preview.target_capability in {
        "graph_codemap_indexing",
        "semantic_memory_writes",
    }
    status = (
        "execution_blocked" if execution_blocked and decision == "approved_for_later" else decision
    )
    return ApprovalAuditRecord(
        audit_id=_stable_id(
            "audit_", {"preview_id": preview.preview_id, "decision": decision, "reviewer": reviewer}
        ),
        preview_id=preview.preview_id,
        action_type=preview.action_type,
        target_capability=preview.target_capability,
        decision=decision,
        decision_status=status,
        requested_by=preview.requested_by,
        reviewer=reviewer,
        created_at=preview.created_at,
        decided_at=decided_at,
        risk_level=preview.risk_level,
        policy_decision=preview.policy_decision,
        reasons=sorted({*preview.reasons, "audit_preview_only_no_execution"}),
        safety_notes=[redact_secret_like_text(note) for note in preview.safety_notes],
        expected_events=[*preview.expected_events, "phase3.approval.audit.recorded"],
        can_execute_now=False,
        execution_enabled=False,
        reversible=rollback_plan is not None,
        rollback_plan_id=rollback_plan.rollback_plan_id if rollback_plan else None,
        redacted_summary=redact_secret_like_text(preview.summary),
    )


def render_approval_audit_record(record: ApprovalAuditRecord) -> str:
    lines = ["Approval audit record preview:"]
    for key, value in sorted(record.to_dict().items()):
        if isinstance(value, list):
            rendered = ",".join(str(item) for item in value) if value else "none"
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)
