from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PhaseSpan:
    name: str
    state: str
    started_at: str
    ended_at: str | None = None
    duration_ms: float | None = None
    event_count: int = 0


@dataclass
class ToolCallSpan:
    tool_name: str
    started_at: str
    ended_at: str | None = None
    duration_ms: float | None = None
    status: str = "unknown"
    tool_call_id: str = ""


@dataclass
class ModelCallSpan:
    model: str
    started_at: str
    ended_at: str | None = None
    duration_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class TurnTrace:
    session_id: str
    turn_id: str
    status: str
    prompt_preview: str | None = None
    total_duration_ms: float = 0.0
    phases: list[PhaseSpan] = field(default_factory=list)
    tool_calls: list[ToolCallSpan] = field(default_factory=list)
    model_calls: list[ModelCallSpan] = field(default_factory=list)
    error: str | None = None
