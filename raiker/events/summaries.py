"""What a governed event's summary says.

BUG-302. Four events that close a turn — ``response_created``,
``checkpoint_created``, ``turn_closed`` and, when the turn belonged to a task,
``task_completed`` — each carried the first couple of hundred characters of the
answer as their summary. In the Sessions turn inspector that produced four
near-identical rows of the same borrowed sentence in a list whose job is to say
what happened, in order. For a turn that declared a table it was four copies of
the same JSON payload under a rendered table that already said it legibly.

The summary being the *raw record* is correct and is not what changed here: an
audit summary is what the runtime saw, verbatim, and a fence rendered as a table
in the evidence log would be the log editing itself. What was wrong is that four
different events described themselves with one borrowed sentence instead of
saying what each of them did.

So there is one rule, and this module is where it lives:

* **One event carries the answer.** ``response_created`` is the event whose
  subject *is* the answer — the runtime produced this text — so it keeps it,
  verbatim and bounded exactly as before.
* **Every other event says what it did.** A checkpoint says a restore point was
  recorded and at which runtime state. A closed turn says how it settled. A
  completed task says the task completed. None of them borrows the answer.

The facts each sentence is built from stay in the event payload under their own
keys, so nothing that needed the text lost it — the per-task attempt timeline
still reads a completion's outcome, it just reads it from
``outcome_summary`` rather than from a column whose job is to describe the
event.
"""

from __future__ import annotations

#: The one event whose summary is the answer text itself.
#:
#: A frozenset of one, deliberately: the rule this module exists to hold is
#: *how many*, and a set makes that assertable in a test rather than implied by
#: which call site happens to pass the text through.
ANSWER_BEARING_EVENTS = frozenset({"response_created"})

#: How much of the answer ``response_created`` carries. Unchanged — the bound
#: was never the defect.
ANSWER_SUMMARY_MAX_CHARS = 200


def response_created_summary(message: str) -> str:
    """The answer this turn produced, bounded.

    The one place the text is still the summary, because here the text is what
    the event is about.
    """
    return message[:ANSWER_SUMMARY_MAX_CHARS]


def checkpoint_created_summary(runtime_state: str) -> str:
    """What a checkpoint did, rather than what the turn happened to say.

    The runtime state is named because it is the thing a restore would return
    to, and it is the only fact about this event an owner reading the list in
    order actually needs.
    """
    state = runtime_state.strip() or "an unnamed state"
    return f"Recorded a restore point for this turn at {state}."


def turn_closed_summary(status: str) -> str:
    """How the turn settled.

    ``status`` is the runtime's own word — ``completed``, ``failed``,
    ``needs_approval`` and the rest — and it is repeated rather than translated,
    so the sentence and the payload cannot come to mean different things.
    """
    settled = status.strip() or "an unstated status"
    return f"Turn closed as {settled}."


def task_completed_summary(title: str = "") -> str:
    """Which task completed.

    The convention this follows is the one ``raiker.events.otlp`` already
    states: *a summary names the object an action acted on.* The event type
    already says "Task completed", so repeating that adds nothing — the fact a
    reader scanning a list needs is **which** task, and that is the title the
    owner filed it under.

    The task's own outcome text is not lost and is not repeated here: it travels
    on the same event under ``outcome_summary``, which is where the per-task
    attempt timeline reads it.
    """
    named = title.strip()
    return f"Completed the task “{named}”." if named else "Completed an untitled task."
