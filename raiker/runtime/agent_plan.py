"""The agent's plan for the work in front of it (B6).

Build ran a genuine agentic loop with nothing tracking what it intended to do
next. A long change therefore had no visible spine and no recovery point: a
failure at step six left neither the model nor the owner with a statement of
what the remaining steps were.

This is that statement, and deliberately nothing more:

* **Ordered steps, one status each.** ``pending`` → ``in_progress`` →
  ``completed``, with ``blocked`` for a step that cannot proceed. At most one
  step may be ``in_progress`` at a time, so "what is happening right now" always
  has exactly one answer.
* **Session-scoped, not turn-scoped.** The plan is written by ``update_plan``
  during a turn and outlives it, so it survives an approval parking the turn, a
  failed step, and a browser reload. It is re-injected into the next turn's
  context, which is what makes it a recovery point rather than a progress bar.
* **Not a task.** ``raiker/tasks`` stores work the owner scheduled, with its own
  lifecycle, notifications, and interrupts. A plan grants no authority, runs
  nothing, and schedules nothing — every step it names still reaches the broker,
  the policy engine, and the approval path exactly as if the plan did not exist.

Validation is fail-closed: a malformed plan is refused with a machine-readable
reason and the previously stored plan is left untouched, because a half-written
spine is worse than the one that was already there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

# The four states a step may be in. `blocked` exists so a step that cannot
# proceed is *said* rather than silently left pending.
PLAN_STATUSES: tuple[str, ...] = ("pending", "in_progress", "completed", "blocked")
ACTIVE_STATUS = "in_progress"

# Bounds. A plan is a spine, not a document: it is re-sent to the model on every
# turn of the conversation, so an unbounded one would quietly eat the context
# budget it exists to protect.
MAX_PLAN_STEPS = 20
MAX_TITLE_CHARS = 200
MAX_NOTE_CHARS = 280


class PlanValidationError(ValueError):
    """Raised when a proposed plan is malformed. Fail-closed by design."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PlanStep:
    """One ordered step. ``note`` is optional and short — a blocker, usually."""

    title: str
    status: str
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {"title": self.title, "status": self.status}
        if self.note:
            payload["note"] = self.note
        return payload


def normalize_steps(raw: object) -> list[PlanStep]:
    """Validate an untrusted, model-proposed plan into ordered steps.

    Every rejection names itself, so the model gets a correctable error instead
    of a silent no-op and the owner gets a reason in the transcript.
    """
    if not isinstance(raw, list):
        raise PlanValidationError("plan_steps_not_a_list")
    if not raw:
        raise PlanValidationError("plan_steps_empty")
    if len(raw) > MAX_PLAN_STEPS:
        raise PlanValidationError(f"plan_too_many_steps:{len(raw)}>{MAX_PLAN_STEPS}")
    steps: list[PlanStep] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise PlanValidationError(f"plan_step_not_an_object:{index}")
        title = str(entry.get("title", "")).strip()
        if not title:
            raise PlanValidationError(f"plan_step_missing_title:{index}")
        if len(title) > MAX_TITLE_CHARS:
            raise PlanValidationError(f"plan_step_title_too_long:{index}")
        status = str(entry.get("status", "pending")).strip() or "pending"
        if status not in PLAN_STATUSES:
            raise PlanValidationError(f"plan_step_invalid_status:{index}:{status}")
        note = str(entry.get("note", "")).strip()
        if len(note) > MAX_NOTE_CHARS:
            raise PlanValidationError(f"plan_step_note_too_long:{index}")
        steps.append(PlanStep(title=title, status=status, note=note))
    active = [step for step in steps if step.status == ACTIVE_STATUS]
    if len(active) > 1:
        raise PlanValidationError(f"plan_multiple_steps_in_progress:{len(active)}")
    return steps


def plan_summary(steps: list[PlanStep]) -> dict[str, Any]:
    """Counts and the current step — the metadata form safe for an event payload."""
    counts = {status: sum(1 for step in steps if step.status == status) for status in PLAN_STATUSES}
    current = next((step.title for step in steps if step.status == ACTIVE_STATUS), "")
    return {
        "total": len(steps),
        "completed": counts["completed"],
        "in_progress": counts["in_progress"],
        "pending": counts["pending"],
        "blocked": counts["blocked"],
        "current_step": current,
    }


def save_plan(
    store: SQLiteStore,
    *,
    session_id: str,
    principal_id: str,
    turn_id: str,
    steps: list[PlanStep],
) -> dict[str, Any]:
    """Persist *steps* as this conversation's plan and return the stored view."""
    payload = [step.to_dict() for step in steps]
    updated_at = store.save_agent_plan(
        session_id=session_id,
        principal_id=principal_id,
        turn_id=turn_id,
        steps_json=json.dumps(payload),
    )
    return {
        "session_id": session_id,
        "turn_id": turn_id,
        "steps": payload,
        "updated_at": updated_at,
        **plan_summary(steps),
    }


def load_plan(
    store: SQLiteStore, session_id: str, principal_id: str
) -> dict[str, Any] | None:
    """This conversation's stored plan, or None when it never wrote one.

    A stored row that no longer parses is treated as absent rather than raised:
    a corrupt plan must not be able to stop a turn that would otherwise run.
    """
    row = store.load_agent_plan(session_id, principal_id)
    if row is None:
        return None
    try:
        steps = normalize_steps(json.loads(str(row["steps_json"])))
    except (PlanValidationError, ValueError, TypeError):
        return None
    return {
        "session_id": session_id,
        "turn_id": str(row.get("turn_id", "")),
        "steps": [step.to_dict() for step in steps],
        "created_at": str(row.get("created_at", "")),
        "updated_at": str(row.get("updated_at", "")),
        **plan_summary(steps),
    }


_STATUS_MARK = {
    "completed": "[x]",
    "in_progress": "[>]",
    "blocked": "[!]",
    "pending": "[ ]",
}


def plan_context_message(plan: dict[str, Any]) -> str:
    """The plan as one system message, so a resumed turn starts with its spine.

    This is Raiker's own record of what the model itself wrote, not workspace
    data, so it is stated as the model's plan rather than wrapped in untrusted
    framing — but it still grants nothing: it is a list of intentions, and every
    step it names is governed when it is actually attempted.
    """
    lines = [
        f"{index + 1}. {_STATUS_MARK.get(str(step.get('status')), '[ ]')} {step.get('title')}"
        + (f" — {step['note']}" if step.get("note") else "")
        for index, step in enumerate(plan.get("steps", []))
    ]
    return (
        "Your current plan for this conversation (you wrote it with `update_plan`). "
        "Keep it accurate: mark a step in_progress when you start it and completed "
        "when it is genuinely done, and call `update_plan` again whenever the plan "
        "changes.\n" + "\n".join(lines)
    )


__all__ = [
    "ACTIVE_STATUS",
    "MAX_PLAN_STEPS",
    "PLAN_STATUSES",
    "PlanStep",
    "PlanValidationError",
    "load_plan",
    "normalize_steps",
    "plan_context_message",
    "plan_summary",
    "save_plan",
]
