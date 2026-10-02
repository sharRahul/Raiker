# SPDX-License-Identifier: Apache-2.0
"""Conversations: their organisation, transcript, sources, plan, grants and branches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.contracts.views import View
from raiker.control.views.sessions import SessionView, TurnView


class ParkedApproval(TypedDict):
    """An unresolved approval a parked turn is waiting on (BUG-34) — metadata only."""

    approval_id: str
    turn_id: str
    tool_name: str
    created_at: str


@dataclass(frozen=True)
class SessionDetail(View):
    """One conversation's transcript, with the approvals its parked turns wait on."""

    session: SessionView
    turns: tuple[TurnView, ...]
    parked_approvals: list[ParkedApproval] = field(default_factory=list)


class SessionPinned(TypedDict):
    ok: bool
    session_id: str
    pinned: bool


class SessionRenamed(TypedDict):
    ok: bool
    session_id: str
    title: str


class SessionArchived(TypedDict):
    ok: bool
    session_id: str
    archived: bool


class SessionDeleted(TypedDict):
    ok: bool
    session_id: str


class SessionsDeleted(TypedDict):
    ok: bool
    session_ids: list[str]


class SessionProjectSet(TypedDict):
    ok: bool
    session_id: str
    project_id: str | None


class SessionTagsSet(TypedDict):
    ok: bool
    session_id: str
    tags: list[str]


class CommandGrant(TypedDict):
    """Owner-defined, expiry-bound command prefixes for one conversation."""

    session_id: str
    commands: list[list[str]]
    expires_at: str
    revocable: bool


class CommandGrantRevoked(TypedDict):
    session_id: str
    revoked: bool


class WorkInFlight(TypedDict):
    """What the stop switch would reach. ``commands`` is null when it could not be read."""

    tasks: int
    turns: int
    commands: int | None
    turn_sessions: list[str]


class ConversationBranchOrigin(TypedDict):
    """Where a branched conversation came from; the source is null for a root one."""

    session_id: str
    source_session_id: str | None
    source_title: str | None
    forked_from_checkpoint_id: str | None
    summary: str
    created_at: str


class ConversationCompaction(TypedDict):
    """A compaction, or why there was nothing to compact (``compacted: false``)."""

    session_id: str
    compacted: bool
    reason_code: NotRequired[str]
    through_turn_id: NotRequired[str | None]
    source_turn_count: NotRequired[int]
    estimated_summary_tokens: NotRequired[int]
    provider: NotRequired[str]
    model: NotRequired[str]
    created_at: NotRequired[str]


class RestoreRequested(TypedDict):
    """The approval a checkpoint restore raised (BUG-230); nothing has been restored."""

    status: Literal["approval_required"]
    approval_id: str
    action_id: str
    checkpoint_id: str
    critical: bool
    executes_action: bool
    restore_content_count: int
    delete_count: int
    skip_count: int



class SessionAttachment(TypedDict):
    """One file a conversation carries — metadata only, so a reload can redraw its chip."""

    attachment_id: str
    turn_id: str
    kind: str
    filename: str
    media_type: str
    byte_size: int
    previewable: bool
    source: Literal["uploaded", "generated"]
    created_at: str


class SessionAttachments(TypedDict):
    session_id: str
    files: list[SessionAttachment]


class SourceAnchorView(TypedDict):
    """One exchange a cited search returned."""

    session_id: str
    turn_id: str
    title: str
    created_at: str
    origin: str


class SourceExcerptView(TypedDict):
    """One resolved source passage, or the stated reason there is not one."""

    status: Literal[
        "resolved",
        "no_provenance",
        "source_deleted",
        "source_changed",
        "unsupported_source",
        "not_authorized",
    ]
    kind: str
    title: str
    excerpt: str
    highlight_start: int
    highlight_length: int
    session_id: str
    turn_id: str
    attachment_id: str
    truncated: bool
    resolution_method: Literal[
        "stored_coordinates",
        "matching_text",
        "answer_quote",
        "recorded_passage",
        "whole_source",
        "",
    ]
    anchors: NotRequired[list[SourceAnchorView]]


class AttachmentProvenance(SourceExcerptView):
    """Which exchange produced a generated file, and the passage that asked for it (BUG-27)."""

    ok: bool
    filename: str


class TurnSourceView(TypedDict):
    """What one turn read: a label and a locator, never the passage itself (C6)."""

    source_id: str
    ordinal: int
    kind: str
    title: str
    locator: str
    tool_name: str
    detail: str
    attachment_id: str
    turn_id: str
    openable: bool


class TurnSources(TypedDict):
    session_id: str
    sources: list[TurnSourceView]


class TurnSourceExcerpt(TurnSourceView, SourceExcerptView):
    """One cited source, opened at the passage the turn used (C4)."""

    ok: bool


class RecalledMemory(TypedDict):
    """An approved memory a turn of this conversation was given, as Raiker knows it now."""

    memory_id: str
    turn_id: str
    text: str
    scope: str
    pinned: bool


class SessionRecall(TypedDict):
    ok: bool
    session_id: str
    memories: list[RecalledMemory]


class AgentPlanStep(TypedDict):
    title: str
    status: Literal["pending", "in_progress", "completed", "blocked"]
    note: NotRequired[str]


class AgentPlan(TypedDict):
    """The agent's standing plan for one conversation (B6); only ``steps`` when there is none."""

    session_id: str
    steps: list[AgentPlanStep]
    turn_id: NotRequired[str]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    total: NotRequired[int]
    completed: NotRequired[int]
    in_progress: NotRequired[int]
    pending: NotRequired[int]
    blocked: NotRequired[int]
    current_step: NotRequired[str]


class RestorePlanFile(TypedDict):
    workspace_path: str
    op: str
    pre_image_sha256: str | None
    pre_image_size: int
    current_sha256: str | None
    current_size: int
    changed: bool
    changed_by_other_principal: bool


class RestorePlan(TypedDict):
    """What restoring to a checkpoint would rewrite, delete or skip — computed, not performed."""

    status: Literal["restore_plan"]
    checkpoint_id: str
    session_id: str
    checkpoint_created_at: str
    can_execute: bool
    requires_approval: bool
    files: list[RestorePlanFile]
    restore_content_count: int
    delete_count: int
    skip_count: int
    changed_count: int
    touches_other_principal: bool


class ConversationBranchPlan(TypedDict):
    """What branching from a checkpoint would seed (C14), without doing it."""

    status: Literal["fork_plan"]
    checkpoint_id: str
    source_session_id: str
    summary: str
    memory_candidate_count: int
    can_execute: bool
    requires_approval: bool


class ConversationBranch(TypedDict):
    """A second conversation, seeded from a checkpoint; the first is untouched (C14)."""

    status: Literal["forked"]
    checkpoint_id: str
    source_session_id: str
    session_id: str
    title: str
    summary: str
    memory_candidate_count: int
    seed_manifest_path: str
