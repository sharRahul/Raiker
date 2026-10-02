# SPDX-License-Identifier: Apache-2.0
"""What deciding, answering, replacing and resuming an approval answers with."""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

from raiker.control.views.security import CheckpointCaptureHealth, IdentityView


class ResumeHandle(TypedDict):
    """Whether a turn was parked on this decision, and where it continues (B2).

    The ids and the ADD-02 batch counters are present only when it was.
    """

    resumable: bool
    session_id: NotRequired[str]
    turn_id: NotRequired[str]
    queue_position: NotRequired[int]
    queue_total: NotRequired[int]
    queued_calls: NotRequired[int]


class ResumableTurn(TypedDict):
    """A parked turn another tab may continue: ids and the decision, never the conversation."""

    approval_id: str
    session_id: str
    turn_id: str
    tool_name: str
    outcome_status: str
    created_at: str
    queue_position: int
    queue_total: int


class ResumableTurns(TypedDict):
    session_id: str | None
    turns: list[ResumableTurn]


class OwnerQuestionAnswered(TypedDict):
    approval_id: str
    status: Literal["answered"]
    answered: int
    resume: ResumeHandle


class ApprovalReplaced(TypedDict):
    """BUG-271 — the proposal denied, and the reviewer's own edit raised in its place.

    The resume handle's keys sit beside these, not under them.
    """

    ok: bool
    approval_id: str
    status: Literal["denied"]
    replacement_approval_id: str
    action_id: str
    executes_action: bool
    resumable: bool
    session_id: NotRequired[str]
    turn_id: NotRequired[str]
    queue_position: NotRequired[int]
    queue_total: NotRequired[int]
    queued_calls: NotRequired[int]


class ExecutionReceipt(TypedDict):
    """BUG-62 — where an executed action's result now lives."""

    kind: str
    title: str
    href: str
    label: str


class ExecutionSummary(TypedDict):
    """What the relay reports of an approved action it carried out.

    Only the keys the executor produced are present; a file write has a path
    and nothing else, a command has its exit code and output.
    """

    capability: str
    path: str | None
    returncode: NotRequired[int | None]
    stdout_bytes: NotRequired[int]
    stderr_bytes: NotRequired[int]
    stdout: NotRequired[str]
    stderr: NotRequired[str]
    truncated: NotRequired[bool]
    output_redacted: NotRequired[bool]
    receipt: NotRequired[ExecutionReceipt]
    summary: NotRequired[str]
    checkpoint_capture: NotRequired[CheckpointCaptureHealth]


class ApprovalResolved(TypedDict):
    """A decision, who proposed and decided it, and what it set in motion.

    ``execution`` is present when approving carried the action out through
    the relay, ``connector_result`` when it ran a connector write intent.
    """

    approval_id: str
    action_id: str
    status: str
    executes_action: bool
    reason: str
    proposed_by: IdentityView | None
    approved_by: IdentityView | None
    machine_identity: IdentityView | None
    execution: NotRequired[ExecutionSummary]
    connector_result: NotRequired[dict[str, Any]]
    resume: ResumeHandle


class CriticalApprovalResolved(TypedDict):
    approval_id: str
    status: str
    decision: str
    message: str
    executes_action: bool
