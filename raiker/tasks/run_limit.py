"""How long one run of a routine may take (DEC-12 step 6).

A routine with no bound could hold the scheduler's attention — and a provider's
meter — for as long as its turn kept going. Each run now has a limit. At the
limit the run is asked to stop at its next safe boundary through the same
control an owner's Stop uses, so a tool call in flight finishes and is recorded
rather than being cut off; if the turn has not stopped after a short grace, the
wait is abandoned. Either way the run is recorded as stopped by its limit, and
it counts as a cycle that did not complete, so a routine that always overruns
is paused by FIXED-757's rule rather than overrunning every morning.
"""

from __future__ import annotations

#: A routine created without its own limit. An hour is long enough for a
#: real multi-step Build cycle and short enough that a stuck one is noticed the
#: same morning; the owner sets a different limit per routine.
DEFAULT_MAX_RUN_MINUTES = 60

#: The bounds an owner's own limit must sit within: at least a minute, at most
#: twelve hours.
MIN_RUN_MINUTES = 1
MAX_RUN_MINUTES = 720

#: How long after the stop is requested the scheduler keeps waiting for the
#: turn to reach its boundary before abandoning the wait.
STOP_GRACE_SECONDS = 120.0

#: What the run's history says when the limit ended it.
STOP_REASON = "run_time_limit"


def effective_minutes(stored: int | None) -> int:
    """The limit a run is held to: the routine's own, or the default."""
    if stored is None:
        return DEFAULT_MAX_RUN_MINUTES
    return max(MIN_RUN_MINUTES, min(MAX_RUN_MINUTES, int(stored)))


def stopped_message(minutes: int) -> str:
    return (
        f"This run reached its {minutes}-minute limit and was stopped at a safe boundary. "
        "Anything it finished before then is kept. Raise the limit in the routine's details "
        "if it needs longer."
    )
