"""Approvals and the detail an approval card opens."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from raiker.contracts.views import View
from raiker.control.views.security import IdentityView


@dataclass(frozen=True)
class ApprovalView(View):
    approval_id: str
    action_id: str
    status: str
    tool_name: str
    capability: str
    risk_level: str
    session_id: str
    turn_id: str | None
    created_at: str
    age_seconds: int | None
    requires_approval: bool
    # The browser displays this server-reported snapshot; the resolve endpoint
    # re-checks the TTL before recording any decision.
    expires_at: str | None
    is_expired: bool
    proposed_by: IdentityView
    approved_by: IdentityView | None
    machine_identity: IdentityView | None
    # Resolving an approval records a decision; it never executes the action.
    executes_action: bool = False
    # Critical approvals use the elevated, human-only RuntimeAuthority lifecycle.
    critical: bool = False
    resolved_by: str | None = None
    # ADD-02 — where this decision sits in the batch of tool calls the turn
    # proposed. 1 of 1 for an ordinary single-call approval; "2 of 3" tells the
    # owner two more decisions are queued behind this one on the same turn.
    queue_position: int = 1
    queue_total: int = 1


#: How an approval card renders what it is asking about.
PreviewKind = Literal[
    "file_diff", "patch", "git_change", "connector_request", "checkpoint_restore", "arguments"
]


@dataclass(frozen=True)
class ApprovalDetailView(View):
    approval: ApprovalView
    # Redacted, metadata-only preview of the proposed action's arguments.
    arguments: dict[str, Any]
    # Unified diff for file-mutation proposals (write_file/edit_file); None otherwise.
    diff: str | None
    diff_path: str | None
    # Tells the UI how to render the preview.
    preview_kind: PreviewKind
    metadata_only_notice: str = (
        "Approval resolution is metadata-only. Recording a decision does NOT execute the action."
    )
    # Server-computed: does pressing Approve actually perform this action? True
    # for a connector write intent and — once the relay and the target capability
    # are both enabled — for a file mutation. The owner is told which of the two
    # kinds of decision they are making before they make it.
    executes_on_approval: bool = False
    execution_evidence: dict[str, Any] = field(default_factory=dict)
