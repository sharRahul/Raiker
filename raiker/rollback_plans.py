from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from raiker.approval_previews import ApprovalPreview
from raiker.contracts.views import View


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{prefix}{hashlib.sha256(encoded).hexdigest()[:24]}"


@dataclass(frozen=True)
class RollbackPlan(View):
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


def create_graph_rollback_plan(preview: ApprovalPreview) -> RollbackPlan:
    return RollbackPlan(
        rollback_plan_id=_stable_id(
            "rb_graph_", {"preview_id": preview.preview_id, "target": preview.target_capability}
        ),
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
            "Legacy rollback preview only: graph indexing runtime is governed separately.",
        ],
        can_execute_rollback_now=False,
        rollback_execution_enabled=False,
        reasons=["rollback_preview_only", "graph_runtime_indexing_disabled"],
        created_at=preview.created_at,
    )


def create_memory_rollback_plan(preview: ApprovalPreview) -> RollbackPlan:
    return RollbackPlan(
        rollback_plan_id=_stable_id(
            "rb_memory_", {"preview_id": preview.preview_id, "target": preview.target_capability}
        ),
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
            "Legacy rollback preview only: semantic/vector runtimes are governed separately.",
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
