"""One published lifecycle for a goal (PA-D01, UX state contract).

Goal states are their own vocabulary, separate from task phases and runtime
states: a goal is *waiting* when one of its steps is parked on a decision, and
that is not the task's status renamed. The server decides which actions a state
permits and serves them with the goal, so no surface re-derives them and a
label never authorises anything.

* **draft** — intake and criteria recorded; no permission to run.
* **ready** — the owner accepted the plan under a pinned execution profile.
* **running** — at least one step is in flight.
* **waiting** — a named dependency blocks progress: a decision, an answer,
  delegated work, a paused step or the execution profile.
* **paused** — the owner paused, the budget ran out or the profile changed;
  continuing rechecks scope.
* **completed** — every mandatory criterion has evidence.
* **partial** — some criteria have evidence and a mandatory one does not.
* **failed** — no criterion has evidence and nothing is left to run.
* **stopped** — Stop reached the steps; what had finished is kept.
* **archived** — hidden settled work; it grants nothing and never reactivates.
"""

from __future__ import annotations

GOAL_STATES = (
    "draft", "ready", "running", "waiting", "paused",
    "completed", "partial", "failed", "stopped", "archived",
)

#: States the coordinator advances on each pass.
ACTIVE_STATES = frozenset({"running", "waiting"})
SETTLED_STATES = frozenset({"completed", "partial", "failed", "stopped"})

#: The actions each state offers. ``confirm`` is the owner recording evidence
#: for one criterion; it is allowed wherever evidence can still change the
#: outcome, including ``partial``.
ALLOWED_ACTIONS: dict[str, tuple[str, ...]] = {
    "draft": ("edit", "accept", "archive"),
    "ready": ("start", "confirm", "stop"),
    "running": ("pause", "confirm", "stop"),
    "waiting": ("pause", "confirm", "stop"),
    "paused": ("resume", "confirm", "stop"),
    "completed": ("archive",),
    "partial": ("confirm", "archive"),
    "failed": ("archive",),
    "stopped": ("archive",),
    "archived": (),
}

#: Why a goal waits or pauses, in the words a surface shows. The reason code is
#: kept alongside for the technical view.
REASONS: dict[str, str] = {
    "needs_decision": "A step is waiting for your decision",
    "needs_answer": "A step is waiting for your answer",
    "waiting_on_delegated_work": "A step is waiting on work it delegated",
    "step_paused": "A step is paused",
    "profile_blocks_model": "The execution profile does not allow the model this work would use",
    "no_execution_profile": "No execution profile is chosen in Settings",
    "budget_exhausted": "The goal's budget is used up",
    "owner_paused": "You paused this goal",
    "profile_changed": "The execution profile changed since this goal was accepted",
    "steps_blocked": "A step could not start because a step it depends on did not finish",
}

#: Step states. A step holds at most one task; ``blocked`` means a dependency
#: settled without finishing, so this step will never start.
STEP_STATES = ("pending", "running", "waiting", "done", "failed", "stopped", "blocked")
STEP_SETTLED = frozenset({"done", "failed", "stopped", "blocked"})

#: Criterion validators. ``steps_finish`` is deterministic — every step linked to
#: the criterion finished — and is named as that, not as a judgement that the
#: result is good. ``owner_confirms`` is the owner's own check of the result.
VALIDATORS = ("steps_finish", "owner_confirms")

#: Task status → the step state it means, and the waiting reason if it waits.
TASK_TO_STEP: dict[str, tuple[str, str]] = {
    "queued": ("running", ""),
    "running": ("running", ""),
    "continuing": ("running", ""),
    "cancelling": ("running", ""),
    "waiting_for_approval": ("waiting", "needs_decision"),
    "waiting_for_user_answer": ("waiting", "needs_answer"),
    "waiting_for_children": ("waiting", "waiting_on_delegated_work"),
    "paused": ("waiting", "step_paused"),
    "completed": ("done", ""),
    "failed": ("failed", ""),
    "cancelled": ("stopped", ""),
}


def allowed_actions(status: str) -> list[str]:
    return list(ALLOWED_ACTIONS.get(status, ()))


def step_from_task(task_status: str | None) -> tuple[str, str]:
    """The step state a linked task's status means. A missing task is failed, never done."""
    if task_status is None:
        return "failed", "task_missing"
    # An unknown status reads as waiting — never as finished.
    return TASK_TO_STEP.get(task_status, ("waiting", "step_paused"))
