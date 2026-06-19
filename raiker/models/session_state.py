from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSessionState:
    session_id: str
    profile_id: str
    reasoning_enabled: bool = False
    reasoning_effort: str | None = None
    reasoning_mode: str | None = None
    reasoning_budget_tokens: int | None = None
