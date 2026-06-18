from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from raiker.graph.governance import GRAPH_RUNTIME_DISABLED_REASON
from raiker.graph.planner import GraphCodemapIndexPlan
from raiker.memory.policy import MemorySensitivity
from raiker.memory.review import MemoryReviewItem

POLICY_DECISION_PREVIEW_ONLY = "denied_or_preview_only"
GRAPH_INDEXING_DISABLED_REASON = "graph_runtime_indexing_disabled"
SEMANTIC_VECTOR_WRITES_DISABLED_REASON = "semantic_vector_writes_disabled"
SECRET_REDACTION = "[REDACTED]"

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\bbearer\s+[a-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\b(password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s:@]+:[^\s@]+@[^\s]+"),
    re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"),
)


def redact_secret_like_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(SECRET_REDACTION, redacted)
    return redacted


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{prefix}{hashlib.sha256(encoded).hexdigest()[:24]}"


@dataclass(frozen=True)
class ApprovalPreview:
    preview_id: str
    action_type: str
    target_capability: str
    title: str
    summary: str
    risk_level: str
    requested_by: str
    created_at: str
    requires_user_approval: bool
    can_execute_now: bool
    execution_enabled: bool
    reasons: list[str]
    policy_decision: str
    expected_events: list[str]
    reversible: bool
    affected_paths: list[str]
    affected_records: list[str]
    safety_notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "preview_id": self.preview_id,
            "action_type": self.action_type,
            "target_capability": self.target_capability,
            "title": self.title,
            "summary": self.summary,
            "risk_level": self.risk_level,
            "requested_by": self.requested_by,
            "created_at": self.created_at,
            "requires_user_approval": self.requires_user_approval,
            "can_execute_now": self.can_execute_now,
            "execution_enabled": self.execution_enabled,
            "reasons": self.reasons,
            "policy_decision": self.policy_decision,
            "expected_events": self.expected_events,
            "reversible": self.reversible,
            "affected_paths": self.affected_paths,
            "affected_records": self.affected_records,
            "safety_notes": self.safety_notes,
        }


def create_graph_indexing_approval_preview(
    plan: GraphCodemapIndexPlan, *, requested_by: str = "local_user"
) -> ApprovalPreview:
    unsafe = [
        str(item.get("reason"))
        for item in plan.excluded_paths
        if str(item.get("reason")) in {"outside_workspace_root", "symlink_escape"}
    ]
    reasons = [
        GRAPH_INDEXING_DISABLED_REASON,
        GRAPH_RUNTIME_DISABLED_REASON,
        "preview_creation_does_not_write_graph_indexes",
    ]
    if not plan.can_index:
        reasons.append("graph_plan_cannot_index")
    if unsafe:
        reasons.append("unsafe_graph_plan_denied")
    return ApprovalPreview(
        preview_id=_stable_id(
            "aprev_graph_",
            {
                "plan_id": plan.plan_id,
                "paths": plan.included_paths,
                "excluded": plan.excluded_paths,
            },
        ),
        action_type="graph_indexing_preview",
        target_capability="graph_codemap_indexing",
        title="Graph/codemap indexing approval preview",
        summary=f"Preview only: {len(plan.included_paths)} paths would be considered by a future graph indexer; no index records are written.",
        risk_level="high" if unsafe else "medium",
        requested_by=requested_by,
        created_at=plan.created_at,
        requires_user_approval=True,
        can_execute_now=False,
        execution_enabled=False,
        reasons=reasons,
        policy_decision=POLICY_DECISION_PREVIEW_ONLY,
        expected_events=[
            "phase3.approval.preview.created",
            "phase3.graph.approval_preview.created",
            "phase3.approval.preview.execution_denied",
        ],
        reversible=False,
        affected_paths=list(plan.included_paths),
        affected_records=[],
        safety_notes=[
            "Graph/codemap runtime indexing remains disabled.",
            "Preview creation does not start background indexers, watchers, or daemons.",
        ],
    )


def create_semantic_memory_write_approval_preview(
    item: MemoryReviewItem, *, requested_by: str = "local_user"
) -> ApprovalPreview:
    secret_like = item.sensitivity in {
        MemorySensitivity.SECRET_LIKE.value,
        MemorySensitivity.CREDENTIAL_LIKE.value,
    }
    summary_text = redact_secret_like_text(item.proposed_text)
    reasons = [
        SEMANTIC_VECTOR_WRITES_DISABLED_REASON,
        "phase3_semantic_vector_writes_disabled",
        "preview_creation_does_not_write_semantic_memory",
        "no_embeddings_created",
        "no_vectors_created",
    ]
    if secret_like:
        reasons.append("secret_or_credential_like_candidate_blocked")
    return ApprovalPreview(
        preview_id=_stable_id(
            "aprev_memory_",
            {
                "candidate_id": item.candidate_id,
                "sensitivity": item.sensitivity,
                "decision": item.decision,
            },
        ),
        action_type="semantic_memory_write_preview",
        target_capability="semantic_memory_writes",
        title="Semantic memory write approval preview",
        summary=f"Preview only: candidate {item.candidate_id} ({item.sensitivity}) would need approval; proposed_text={summary_text}",
        risk_level="high"
        if secret_like
        else ("medium" if item.sensitivity in {"personal", "unknown"} else "low"),
        requested_by=requested_by,
        created_at=item.created_at,
        requires_user_approval=True,
        can_execute_now=False,
        execution_enabled=False,
        reasons=reasons,
        policy_decision=POLICY_DECISION_PREVIEW_ONLY,
        expected_events=[
            "phase3.approval.preview.created",
            "phase3.memory.approval_preview.created",
            "phase3.approval.preview.execution_denied",
        ],
        reversible=False,
        affected_paths=[],
        affected_records=[item.candidate_id],
        safety_notes=[
            "Semantic/vector memory writes remain disabled.",
            "Preview creation does not create embeddings or vectors.",
        ],
    )


def render_approval_preview(preview: ApprovalPreview) -> str:
    data = preview.to_dict()
    lines = ["Approval preview:"]
    for key in sorted(data):
        value = data[key]
        if isinstance(value, list):
            rendered = ",".join(str(item) for item in value) if value else "none"
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)
