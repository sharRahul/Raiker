"""A task's attempts, read back from the events its own lifecycle already wrote.

BUG-299 / UX-TASK-04. A task had a status and a current step, and nothing else.
When [FIXED-533] gave one run one Stop, Resume and Run-now meaning across Home,
Tasks and Build, it also gained an honest third settlement — ``outcome_unknown``
— whose remedy is *"refresh to see the run's current state"*. There was nowhere
to refresh **to**: no per-task address, no attempt list, no record of the
approval a cycle parked on or the continuation that followed it.

Everything needed to answer that was already being written. ``TaskManager``
appends a governed event for every transition a task makes, and ``events_index``
carries ``task_id`` on each of them, so the history is a **read** rather than a
new store. This module is the reading: it turns one task's ordered events into
the attempts a person would describe if they were narrating the task out loud.

**An attempt is a run, not a status.** It opens when a cycle starts
(``task_started``) or when a granted approval is replayed into a parked one
(``task_resume_started``), and it closes on the first event that settles it —
completed, failed, parked on a decision, cancelled, waiting on delegated work,
or, for a routine, the cycle landing while the task itself stays armed. Events
that belong to no run — the filing, an owner pressing *Run now*, a parked task
being stopped — are kept in their own segment rather than being folded into a
neighbouring run, because attributing an owner's act to a cycle that had already
ended would be the same class of untruth this record exists to remove.

Nothing here reads a payload the runtime did not write itself, and nothing here
infers an outcome that was not recorded: a run whose settlement never arrived is
reported as ``in_progress``, which is the honest answer and is exactly the state
``outcome_unknown`` asked for somewhere to look.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: An attempt begins here, and what kind of attempt it is.
#:
#: ``task_resume_started`` is a *continuation* rather than a fresh run: it
#: replays a decision into the turn that parked, so calling it attempt two of a
#: task would tell an owner the work was done twice.
ATTEMPT_START_EVENTS: dict[str, str] = {
    "task_started": "run",
    "task_resume_started": "continuation",
}

#: An attempt ends here, and the outcome the event settles it with.
#:
#: ``task_resume_blocked`` settles the continuation it belongs to without
#: settling the *task*: the run is still parked, and the card still offers the
#: retry. ``task_cycle_landed`` carries its own outcome in the payload, because
#: a routine's cycle can succeed or fail while the task stays armed either way.
ATTEMPT_END_EVENTS: dict[str, str] = {
    "task_completed": "completed",
    "task_failed": "failed",
    "task_blocked": "waiting_for_approval",
    "task_resume_blocked": "waiting_for_approval",
    "task_cancelled": "cancelled",
    "task_waiting_for_children": "waiting_for_children",
    "task_cycle_landed": "",
}

#: What each recorded transition says, in the owner's words rather than the
#: runtime's. The payload key is read only when the runtime wrote it; a missing
#: one falls back to the sentence rather than to an empty line, so no row in
#: this timeline is ever blank.
_DETAIL_KEYS: tuple[str, ...] = ("reason", "summary", "current_step", "detail")

_FALLBACK_DETAIL: dict[str, str] = {
    "task_created": "Filed.",
    "task_run_requested": "You asked for this to run now.",
    "task_started": "This cycle started.",
    "task_progress": "Progress recorded.",
    "task_paused": "Paused.",
    "task_resume_started": "A granted approval is being replayed into this run.",
    "task_resume_blocked": "The continuation could not proceed.",
    "task_blocked": "Waiting for a decision.",
    "task_waiting_for_children": "Waiting on delegated work.",
    "task_cycle_landed": "This cycle landed.",
    "task_completed": "Completed.",
    "task_failed": "Did not complete.",
    "task_cancelled": "Stopped.",
}


@dataclass(frozen=True)
class TaskEventView:
    """One recorded transition, as the timeline draws it."""

    event_id: str
    event_type: str
    timestamp: str
    actor: str
    detail: str
    #: The governed turn this transition belongs to, when it had one. It is what
    #: makes the row a link: the owner opens the exchange rather than reading a
    #: sentence about it.
    turn_id: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskAttemptView:
    """One run of a task, from where it started to how it settled."""

    #: 1-based across runs and continuations; ``0`` for a segment that is not a
    #: run at all, so "attempt 1" always means the first time work was tried.
    index: int
    #: ``run``, ``continuation`` or ``record``.
    kind: str
    started_at: str
    ended_at: str | None
    #: ``completed``, ``failed``, ``waiting_for_approval``, ``cancelled``,
    #: ``waiting_for_children``, ``in_progress`` or ``recorded``.
    outcome: str
    #: The stated reason the settling event carried. Never a bare code.
    summary: str
    #: The decision this attempt waited on, when the runtime recorded which.
    approval_id: str | None
    events: list[TaskEventView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def event_detail(event_type: str, payload: dict[str, Any]) -> str:
    """The sentence one recorded transition shows.

    Prefers what the runtime stated over anything derived: a failure's reason, a
    completion's summary, a progress step. A transition the runtime recorded
    without words still gets a sentence rather than an empty row.
    """
    for key in _DETAIL_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if event_type == "task_progress":
        percent = payload.get("progress_percent")
        if isinstance(percent, int):
            return f"{percent}% through its objective."
    if event_type == "task_waiting_for_children":
        outstanding = payload.get("unfinished_children")
        if isinstance(outstanding, int):
            plural = "task" if outstanding == 1 else "tasks"
            return f"Its own run finished. Waiting on {outstanding} delegated {plural}."
    return _FALLBACK_DETAIL.get(event_type, "Recorded.")


def _approval_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("approval_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _settled_outcome(event_type: str, payload: dict[str, Any]) -> str:
    """How an ending event settles the attempt it closes."""
    mapped = ATTEMPT_END_EVENTS[event_type]
    if mapped:
        return mapped
    # `task_cycle_landed` — a routine's cycle, whose outcome is the cycle's and
    # not the task's. The payload states it; an unrecognised one is reported as
    # recorded rather than guessed into a success or a failure.
    stated = payload.get("outcome")
    return stated if stated in {"completed", "failed", "waiting_for_approval"} else "recorded"


class _Segment:
    """One attempt under construction. Internal to :func:`derive_attempts`."""

    __slots__ = ("approval_id", "closed", "ended_at", "events", "index", "kind", "outcome", "started_at", "summary")

    def __init__(self, *, index: int, kind: str, started_at: str) -> None:
        self.index = index
        self.kind = kind
        self.started_at = started_at
        self.ended_at: str | None = None
        self.outcome = "in_progress" if kind in ("run", "continuation") else "recorded"
        self.summary = ""
        self.approval_id: str | None = None
        self.events: list[TaskEventView] = []
        self.closed = False

    def view(self) -> TaskAttemptView:
        return TaskAttemptView(
            index=self.index,
            kind=self.kind,
            started_at=self.started_at,
            ended_at=self.ended_at,
            outcome=self.outcome,
            summary=self.summary or (self.events[-1].detail if self.events else ""),
            approval_id=self.approval_id,
            events=list(self.events),
        )


def derive_attempts(events: list[dict[str, Any]]) -> list[TaskAttemptView]:
    """Group one task's events, oldest first, into the attempts they describe.

    ``events`` is a list of mappings with ``event_id``, ``event_type``,
    ``timestamp`` and ``actor``, an optional ``turn_id`` and ``session_id``, and
    a ``payload`` mapping. Events the caller could not read a payload for are
    still placed — the row says what transition happened even when the line it
    was written on could not be read back.
    """
    segments: list[_Segment] = []
    current: _Segment | None = None
    attempt_index = 0

    for event in events:
        event_type = str(event.get("event_type", ""))
        payload = event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        timestamp = str(event.get("timestamp", ""))

        if event_type in ATTEMPT_START_EVENTS:
            attempt_index += 1
            current = _Segment(
                index=attempt_index,
                kind=ATTEMPT_START_EVENTS[event_type],
                started_at=timestamp,
            )
            segments.append(current)
        elif current is None or current.closed:
            current = _Segment(index=0, kind="record", started_at=timestamp)
            segments.append(current)

        current.events.append(
            TaskEventView(
                event_id=str(event.get("event_id", "")),
                event_type=event_type,
                timestamp=timestamp,
                actor=str(event.get("actor", "")),
                detail=event_detail(event_type, payload),
                turn_id=event.get("turn_id") or None,
                session_id=event.get("session_id") or None,
            )
        )
        found = _approval_id(payload)
        if found is not None:
            current.approval_id = found

        if event_type in ATTEMPT_END_EVENTS:
            current.outcome = _settled_outcome(event_type, payload)
            current.ended_at = timestamp
            current.summary = current.events[-1].detail
            current.closed = True

    return [segment.view() for segment in segments]
