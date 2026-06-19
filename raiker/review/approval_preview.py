from __future__ import annotations

import json
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.contracts.models import ClientMetadata
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.review.models import (
    APPROVAL_PREVIEW_STATUSES,
    PROPOSAL_ACTION_TYPES,
    ProposalApprovalPreview,
    ProposalLifecycleRecord,
)
from raiker.storage.sqlite import SQLiteStore

_PREVIEW_SOURCE = "proposal_approval_preview"


def _preview_client() -> ClientMetadata:
    return ClientMetadata(type="cli", name="raiker-approval-preview", version="0.0.0")


def _preview_id(proposal_id: str) -> str:
    return f"apv_{proposal_id.removeprefix('rap_')}"


def _human_decision(action_type: str) -> str:
    decisions = {
        "secret_removal_proposal": (
            "Confirm the secret-like material has been removed from the intended change, "
            "rotate any exposed credential outside Raiker, and decide whether a future "
            "patch plan should be created."
        ),
        "test_addition_proposal": (
            "Confirm the changed behavior needs additional tests and decide whether a "
            "future patch plan should be created for focused test coverage."
        ),
        "scope_reduction_proposal": (
            "Confirm the deferred runtime capability should remain disabled and decide "
            "whether a future patch plan should remove or revise the scope-expanding change."
        ),
        "runtime_safety_refactor_proposal": (
            "Confirm direct runtime activation must be replaced with a policy-gated design "
            "before any future implementation planning."
        ),
        "review_scope_adjustment_proposal": (
            "Confirm whether the review scope should be narrowed or expanded before "
            "further planning."
        ),
        "no_action_required": (
            "Confirm no implementation action is required beyond human acknowledgement."
        ),
        "manual_patch_proposal": (
            "Confirm the manual patch is still needed and decide whether a future patch "
            "plan should be created."
        ),
        "docs_update_proposal": (
            "Confirm the documentation needs updating and decide whether a future patch "
            "plan should be created."
        ),
    }
    return decisions.get(action_type, "Review the proposal manually and decide on next steps.")


def _safety_checks(record: ProposalLifecycleRecord) -> list[str]:
    checks = [
        "Confirm no raw secrets are present.",
        "Confirm the proposed action is still relevant.",
        "Confirm the action remains within the current phase scope.",
        "Confirm no disabled runtime flag would be enabled.",
        "Confirm any future change would require a separate approved implementation step.",
    ]
    if record.would_modify_files:
        checks.append("Identify exact files before any future patch planning.")
        checks.append("Confirm tests/docs that would need updating.")
        checks.append("Confirm the change can be reviewed before application.")
    if record.risk_level == "high":
        checks.append("Require explicit human review before any future implementation plan.")
    if record.action_type == "secret_removal_proposal":
        checks.append("Confirm credential rotation is handled outside Raiker.")
    if record.action_type in ("scope_reduction_proposal", "runtime_safety_refactor_proposal"):
        checks.append(
            "Confirm proposal does not enable shell/process/network/plugin/graph/semantic/"
            "vector/external/remote execution."
        )
    return checks


def _blocking_conditions(record: ProposalLifecycleRecord) -> list[str]:
    conditions: list[str] = []
    if record.status == "rejected":
        conditions.append("Proposal was rejected; no further planning until re-proposed.")
    if record.status == "superseded":
        conditions.append("Proposal was superseded by another proposal.")
    if record.action_type not in PROPOSAL_ACTION_TYPES:
        conditions.append("Unknown action type; cannot plan.")
    if record.risk_level == "high":
        conditions.append("High-risk proposal requires explicit human review before future implementation planning.")
    if record.would_modify_files and not record.files:
        conditions.append("Proposal would modify files but no files are specified.")
    if record.status == "proposed":
        conditions.append("Proposal is only proposed; acknowledge, defer, or plan before detailed planning.")
    return conditions


def _preview_status(record: ProposalLifecycleRecord) -> str:
    if record.status in ("rejected", "superseded"):
        return "blocked"
    if record.risk_level == "high" and record.status == "proposed":
        return "needs_human_review"
    if record.action_type == "no_action_required" and record.risk_level in ("low", "medium"):
        return "ready_for_planning"
    return "preview_created"


def _recommended_action(record: ProposalLifecycleRecord, status: str) -> str:
    if status == "blocked":
        return "No action available; the proposal must be unblocked before any planning."
    if status == "needs_human_review":
        return "Review the proposal manually and keep it in planning until a separate implementation scope is approved."
    if status == "ready_for_planning":
        return "Low risk; can be included in future planning scope without additional review gates."
    return "Keep the proposal in planning status until a future implementation scope is approved."


def approval_preview_from_lifecycle_record(
    record: ProposalLifecycleRecord,
    *,
    created_at: str | None = None,
) -> ProposalApprovalPreview:
    """Generate a deterministic metadata-only approval planning preview from a lifecycle record."""

    now = created_at or utc_now()
    status = _preview_status(record)
    return ProposalApprovalPreview(
        preview_id=_preview_id(record.proposal_id),
        proposal_id=record.proposal_id,
        review_id=record.review_id,
        finding_id=record.finding_id,
        proposal_status=record.status,
        action_type=record.action_type,
        risk_level=record.risk_level,
        requires_approval=record.requires_approval,
        would_modify_files=record.would_modify_files,
        files=list(record.files),
        required_human_decision=_human_decision(record.action_type),
        required_safety_checks=_safety_checks(record),
        blocking_conditions=_blocking_conditions(record),
        recommended_next_action=_recommended_action(record, status),
        status=status,
        created_at=now,
        source=_PREVIEW_SOURCE,
    )


def render_preview_text(preview: ProposalApprovalPreview) -> str:
    lines = [
        f"Approval planning preview: {preview.preview_id}",
        f"Proposal: {preview.proposal_id}",
        f"Status: {preview.status}",
        f"Risk: {preview.risk_level}",
        f"Action type: {preview.action_type}",
        f"Would modify files: {'true' if preview.would_modify_files else 'false'}",
    ]
    if preview.files:
        lines.append(f"Files: {', '.join(preview.files)}")
    lines.extend([
        "",
        "Required human decision:",
        preview.required_human_decision,
        "",
        "Required safety checks:",
    ])
    for check in preview.required_safety_checks:
        lines.append(f"- {check}")
    if preview.blocking_conditions:
        lines.extend(["", "Blocking conditions:"])
        for condition in preview.blocking_conditions:
            lines.append(f"- {condition}")
    lines.extend([
        "",
        "Recommended next action:",
        preview.recommended_next_action,
        "",
        "Safety:",
        "- Preview only.",
        "- No approval was executed.",
        "- No proposal was executed.",
        "- No files were modified.",
    ])
    return "\n".join(lines)


def render_previews_text(previews: list[ProposalApprovalPreview]) -> str:
    if not previews:
        return "No approval planning previews found."
    lines = ["Approval planning previews:"]
    for index, preview in enumerate(previews, start=1):
        lines.append(
            f"{index}. {preview.preview_id} [{preview.status}] "
            f"proposal={preview.proposal_id} risk={preview.risk_level} "
            f"action={preview.action_type}"
        )
    lines.append("Safety: preview-only. No approval was executed. No files were modified.")
    return "\n".join(lines)


def preview_to_json(preview: ProposalApprovalPreview) -> str:
    return json.dumps(preview.to_dict(), sort_keys=True, indent=2)


def previews_to_json(previews: list[ProposalApprovalPreview]) -> str:
    return json.dumps([p.to_dict() for p in previews], sort_keys=True, indent=2)


class ProposalApprovalPreviewStore:
    """Metadata-only SQLite persistence for approval planning previews.

    This store never executes approvals, executes proposals, applies patches,
    modifies files, stages/unstages, runs tests, or calls shell/process/network.
    """

    def __init__(self, store: SQLiteStore, *, emit_events: bool = True) -> None:
        self.store = store
        self.emit_events = emit_events
        self._writer = EventLogWriter(store) if emit_events else None
        self._session_id = "approval-preview"

    def create_from_record(self, record: ProposalLifecycleRecord) -> ProposalApprovalPreview:
        """Generate and persist an approval planning preview from a lifecycle record."""

        preview = approval_preview_from_lifecycle_record(record)
        self.save_preview(preview)
        return preview

    def save_preview(self, preview: ProposalApprovalPreview) -> ProposalApprovalPreview:
        """Persist or update a preview row (upsert by preview_id)."""
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO proposal_approval_previews
                (preview_id, proposal_id, review_id, finding_id, proposal_status,
                 action_type, risk_level, requires_approval, would_modify_files,
                 files_json, required_human_decision, required_safety_checks_json,
                 blocking_conditions_json, recommended_next_action, status,
                 created_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preview.preview_id,
                    preview.proposal_id,
                    preview.review_id,
                    preview.finding_id,
                    preview.proposal_status,
                    preview.action_type,
                    preview.risk_level,
                    int(preview.requires_approval),
                    int(preview.would_modify_files),
                    json.dumps(preview.files),
                    preview.required_human_decision,
                    json.dumps(preview.required_safety_checks),
                    json.dumps(preview.blocking_conditions),
                    preview.recommended_next_action,
                    preview.status,
                    preview.created_at,
                    preview.source,
                ),
            )
        self._emit(
            "proposal_approval_preview_created",
            {
                "preview_id": preview.preview_id,
                "proposal_id": preview.proposal_id,
                "proposal_status": preview.proposal_status,
                "action_type": preview.action_type,
                "risk_level": preview.risk_level,
                "requires_approval": preview.requires_approval,
                "would_modify_files": preview.would_modify_files,
                "status": preview.status,
                "blocking_condition_count": len(preview.blocking_conditions),
                "safety_check_count": len(preview.required_safety_checks),
            },
        )
        return preview

    def list_previews(
        self, *, status: str | None = None, limit: int = 20
    ) -> list[ProposalApprovalPreview]:
        """List previews newest-first with optional status filter and limit."""

        query = "SELECT * FROM proposal_approval_previews"
        params: list[Any] = []
        if status is not None:
            if status not in APPROVAL_PREVIEW_STATUSES:
                raise ValueError(f"invalid_approval_preview_status:{status}")
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(str(limit))
        with self.store.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        previews = [_row_to_preview(dict(row)) for row in rows]
        self._emit(
            "proposal_approval_preview_listed",
            {
                "status_filter": status,
                "limit": limit,
                "result_count": len(previews),
            },
        )
        return previews

    def get_preview(self, preview_id: str) -> ProposalApprovalPreview | None:
        """Load one preview by preview_id."""

        if not preview_id.startswith("apv_"):
            return None
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proposal_approval_previews WHERE preview_id = ?",
                (preview_id,),
            ).fetchone()
        if row is None:
            return None
        preview = _row_to_preview(dict(row))
        self._emit(
            "proposal_approval_preview_viewed",
            {"preview_id": preview.preview_id, "status": preview.status},
        )
        return preview

    def _emit(self, event_type: str, payload: dict[str, object]) -> None:
        if self._writer is None:
            return
        self._writer.append(
            make_event(
                session_id=self._session_id,
                turn_id=None,
                event_type=event_type,
                actor="approval_preview",
                payload=payload,
                client=_preview_client(),
            )
        )


def _row_to_preview(row: dict[str, Any]) -> ProposalApprovalPreview:
    return ProposalApprovalPreview(
        preview_id=str(row["preview_id"]),
        proposal_id=str(row["proposal_id"]),
        review_id=str(row["review_id"]),
        finding_id=str(row["finding_id"]),
        proposal_status=str(row["proposal_status"]),
        action_type=str(row["action_type"]),
        risk_level=str(row["risk_level"]),
        requires_approval=bool(row["requires_approval"]),
        would_modify_files=bool(row["would_modify_files"]),
        files=json.loads(str(row["files_json"])),
        required_human_decision=str(row["required_human_decision"]),
        required_safety_checks=json.loads(str(row["required_safety_checks_json"])),
        blocking_conditions=json.loads(str(row["blocking_conditions_json"])),
        recommended_next_action=str(row["recommended_next_action"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        source=str(row["source"]),
    )


__all__ = [
    "ProposalApprovalPreviewStore",
    "approval_preview_from_lifecycle_record",
    "preview_to_json",
    "previews_to_json",
    "render_preview_text",
    "render_previews_text",
]
