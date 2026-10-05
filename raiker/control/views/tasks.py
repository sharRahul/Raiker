"""Tasks and the detail a task row opens."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from typing_extensions import TypedDict

from raiker.contracts.views import View
from raiker.control.views.approvals import ApprovalView
from raiker.tasks.history import TaskAttemptView
from raiker.tasks.schedule import TASK_REPEATING

# Cadences a task/schedule may carry. `background` runs one governed cycle now;
# the recurring cadences re-arm after every cycle so a standing agent keeps
# working until the owner stops it. An unknown cadence is refused rather than
# silently stored as a one-shot, which would make a "keep going" schedule stop
# after its first run.
TASK_RECURRENCES = frozenset({"background", *TASK_REPEATING})


# Task states in which the stored summary *is* the outcome — what the run ended
# on, or what it is parked against. In those states `current_step` is the step
# the run last reached, which is not what the owner needs to be told (BUG-09).
TASK_OUTCOME_STATES = frozenset({"completed", "failed", "cancelled", "waiting_for_approval"})


class PathAttachment(TypedDict):
    """A workspace path a task reads."""

    type: Literal["path"]
    path: str


class UploadAttachment(TypedDict):
    """An image or document uploaded through ``POST /api/attachments``."""

    type: Literal["image", "document"]
    attachment_id: str


@dataclass(frozen=True)
class TaskView(View):
    task_id: str
    session_id: str
    status: str
    title: str
    objective: str
    current_step: str | None
    progress_percent: int | None
    created_at: str
    updated_at: str
    completed_at: str | None
    summary: str | None
    priority: str | None = None
    scheduled_at: str | None = None
    recurrence: str | None = None
    reminder_at: str | None = None
    parent_task_id: str | None = None
    # Project-scoped schedules: the organizing project this task was created
    # under, or None when it was created outside every project.
    project_id: str | None = None
    model_profile: str | None = None
    model: str | None = None
    # Backlog #23 — the working method this task's cycles run under: `chat` or
    # `build`. A delegating parent chooses it per child, so one brief can put
    # the reading half in Chat and the change-and-test half in Build.
    surface: str = "chat"
    # C11 — this task's own conversation, or None for a task created before
    # threads existed. The card links to it, and every cycle runs in it, so
    # "what did the overnight run find?" opens a transcript the owner can reply
    # in rather than a status line they can only read.
    thread_session_id: str | None = None
    # How many turns that thread holds. It is the difference between a link
    # worth pressing and one that opens an empty page, so the card can say so
    # instead of the owner discovering it.
    thread_turns: int = 0
    attachments: list[PathAttachment | UploadAttachment] = field(default_factory=list)
    # UX-TASK-02 — the schedule's own terms, so a card can say "weekdays at
    # 09:00 Europe/London, until 31 Dec, skips missed runs" rather than a cadence
    # and a UTC instant. Empty on a task created before they existed.
    schedule_timezone: str | None = None
    schedule_until: str | None = None
    missed_run_policy: str | None = None
    # DEC-12 step 5 — whether the owner was told it ended, separate from
    # whether it worked: `delivered`, `failed`, or null when nothing was owed.
    delivery_state: str | None = None
    delivery_detail: str | None = None
    # DEC-12 step 6 — the longest one run may take, in minutes: the routine's
    # own limit or the default. Never absent, because no run is unbounded.
    max_run_minutes: int = 60
    # UX-TASK-05 — the published lifecycle phase (`raiker/tasks/lifecycle.py`),
    # served rather than re-derived so every surface offers the same actions
    # for the same task.
    phase: str = "queued"


@dataclass(frozen=True)
class TaskDetailView(View):
    """One task at its own address, with the attempts behind its status.

    BUG-299 / UX-TASK-04. The board says what a task *is* doing; this says what
    it *has* done — every cycle in order, the decision each waited on, the
    continuation that followed and the conversation it produced. It exists
    because two shipped changes promised it: a deduplicated Home row that links
    to "the canonical Tasks detail", and a stop control that can honestly report
    ``outcome_unknown`` and tell the owner to refresh to see the run's state.

    Nothing here is stored separately. The attempts are derived from the
    governed events the task's own lifecycle already writes, so this view can
    never disagree with the audit log — it *is* the audit log, grouped.
    """

    task: TaskView
    attempts: list[TaskAttemptView]
    #: Decisions still open on this task's session. A parked attempt names the
    #: one it is waiting on when the runtime recorded which; this is the queue
    #: the owner can actually act in.
    approvals: list[ApprovalView] = field(default_factory=list)
    #: True when the attempt list was cut off by the read bound, so the page
    #: says "showing the most recent" rather than implying a complete history.
    truncated: bool = False


def _task_detail(task: TaskView) -> str | None:
    """What a live view should say about a task: its outcome, else its step."""
    if task.status in TASK_OUTCOME_STATES:
        return task.summary or task.current_step
    return task.current_step
