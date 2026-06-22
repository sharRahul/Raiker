from __future__ import annotations

from dataclasses import dataclass

# Fixed key for the local terminal client's current model selection.
TERMINAL_MODEL_SESSION_ID = "terminal-local"


@dataclass(frozen=True)
class ModelSessionState:
    session_id: str
    profile_id: str
    model: str | None = None
    reasoning_enabled: bool = False
    reasoning_effort: str | None = None
    reasoning_mode: str | None = None
    reasoning_budget_tokens: int | None = None
