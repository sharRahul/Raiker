from __future__ import annotations

from dataclasses import dataclass, field


class InvalidStateTransition(ValueError):
    pass


RUNTIME_STATES = {
    "RECEIVED",
    "NORMALISED",
    "CLASSIFIED",
    "CONTEXT_READY",
    "PLAN_READY",
    "PLAN_SKIPPED",
    "POLICY_REVIEWED",
    "EXECUTING",
    "WAITING_FOR_APPROVAL",
    "DENIED",
    "OBSERVING",
    "VERIFYING",
    "RESPONDING",
    "CHECKPOINTING",
    "CLOSED",
    "FAILED",
    "CANCELLED",
    "PAUSED",
    "WAITING_FOR_USER",
}

VALID_TRANSITIONS = {
    "RECEIVED": {"NORMALISED"},
    "NORMALISED": {"CLASSIFIED"},
    "CLASSIFIED": {"CONTEXT_READY"},
    "CONTEXT_READY": {"PLAN_READY", "PLAN_SKIPPED"},
    "PLAN_READY": {"POLICY_REVIEWED"},
    "PLAN_SKIPPED": {"POLICY_REVIEWED", "RESPONDING"},
    "POLICY_REVIEWED": {"EXECUTING", "WAITING_FOR_APPROVAL", "DENIED", "RESPONDING"},
    "EXECUTING": {"OBSERVING"},
    "WAITING_FOR_APPROVAL": {"RESPONDING"},
    "DENIED": {"RESPONDING"},
    "OBSERVING": {"VERIFYING"},
    "VERIFYING": {"RESPONDING"},
    "RESPONDING": {"CHECKPOINTING", "CLOSED"},
    "CHECKPOINTING": {"CLOSED"},
    "CLOSED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
    "PAUSED": {"RECEIVED", "CANCELLED"},
    "WAITING_FOR_USER": {"RECEIVED", "CANCELLED"},
}


@dataclass
class RuntimeStateMachine:
    state: str = "RECEIVED"
    history: list[str] = field(default_factory=lambda: ["RECEIVED"])

    def transition(self, new_state: str) -> None:
        if new_state not in RUNTIME_STATES:
            raise InvalidStateTransition(f"unknown_state:{new_state}")
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise InvalidStateTransition(f"invalid_transition:{self.state}->{new_state}")
        self.state = new_state
        self.history.append(new_state)
