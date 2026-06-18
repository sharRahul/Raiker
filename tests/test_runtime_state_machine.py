from __future__ import annotations

import pytest

from raiker.runtime.state_machine import InvalidStateTransition, RuntimeStateMachine


def test_valid_transitions() -> None:
    machine = RuntimeStateMachine()
    for state in [
        "NORMALISED",
        "CLASSIFIED",
        "CONTEXT_READY",
        "PLAN_SKIPPED",
        "RESPONDING",
        "CHECKPOINTING",
        "CLOSED",
    ]:
        machine.transition(state)
    assert machine.state == "CLOSED"


def test_invalid_transition_raises() -> None:
    machine = RuntimeStateMachine()
    with pytest.raises(InvalidStateTransition):
        machine.transition("CLOSED")
