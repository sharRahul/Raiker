from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from raiker.approval_previews import ApprovalPreview


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}{hashlib.sha256(encoded).hexdigest()[:24]}"


@dataclass(frozen=True)
class RollbackPlan:
    rollback_plan_id: str
    target_capability: str
    source_preview_id: str
    action_type: str
    affected_paths: list[str]
    affected_records: list[str]
    reversible: bool
    rollback_available: bool
    rollback_steps: list[str]
    safety_notes: list[str]
    can_execute_rollback_now: bool
    rollback_execution_enabled: bool
    reasons: list[str]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "rollback_plan_id": self.rollback_plan_id,
            "target_capability": self.target_capability,
            "source_preview_id": self.source_preview_id,
            "action_type": self.action_type,
            "affected_paths": self.affected_paths,
            "affected_records": self.affected_records,
            "reversible": self.reversible,
            "rollback_available": self.rollback_available,
            "rollback_steps": self.rollback_steps,
            "safety_notes": self.safety_notes,
            "can_execute_rollback_now": self.can_execute_rollback_now,
            "rollback_execution_enabled": self.rollback_execution_enabled,
            "reasons": self.reasons,
            "created_at": self.created_at,
        }


def create_graph_rollback_plan(preview: ApprovalPreview) -> RollbackPlan:
    return RollbackPlan(
        rollback_plan_id=_stable_id("rb_graph_", {"preview_id": preview.preview_id, "target": preview.target_capability}),
        target_capability="graph_codemap_indexing",
        source_preview_id=preview.preview_id,
        action_type="graph_index_rollback_preview",
        affected_paths=sorted(preview.affected_paths),
        affected_records=[],
        reversible=True,
        rollback_available=True,
        rollback_steps=[
            "Identify graph index records produced by the approved preview id.",
            "Remove or tombstone only those future graph index records after policy approval.",
            "Emit audit events for rollback planning and any future rollback execution.",
        ],
        safety_notes=[
            "Preview only: no graph data is created or deleted.",
            "Graph/codemap runtime indexing remains disabled.",
        ],
        can_execute_rollback_now=False,
        rollback_execution_enabled=False,
        reasons=["rollback_preview_only", "graph_runtime_indexing_disabled"],
        created_at=preview.created_at,
    )


def create_memory_rollback_plan(preview: ApprovalPreview) -> RollbackPlan:
    return RollbackPlan(
        rollback_plan_id=_stable_id("rb_memory_", {"preview_id": preview.preview_id, "target": preview.target_capability}),
        target_capability="semantic_memory_writes",
        source_preview_id=preview.preview_id,
        action_type="semantic_memory_rollback_preview",
        affected_paths=[],
        affected_records=sorted(preview.affected_records),
        reversible=True,
        rollback_available=True,
        rollback_steps=[
            "Find semantic memory records associated with the approved preview id.",
            "Tombstone future memory records rather than exposing deleted sensitive text.",
            "Remove associated vector references only after policy approval and audit recording.",
        ],
        safety_notes=[
            "Preview only: no semantic memory records, embeddings, or vectors are created or deleted.",
            "Semantic/vector memory writes remain disabled.",
        ],
        can_execute_rollback_now=False,
        rollback_execution_enabled=False,
        reasons=["rollback_preview_only", "semantic_vector_writes_disabled"],
        created_at=preview.created_at,
    )


def render_rollback_plan(plan: RollbackPlan) -> str:
    lines = ["Rollback plan preview:"]
    for key, value in sorted(plan.to_dict().items()):
        if isinstance(value, list):
            rendered = ",".join(str(item) for item in value) if value else "none"
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)
