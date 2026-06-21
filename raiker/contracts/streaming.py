"""UI-facing streaming event contract.

The runtime and gateway already emit a durable JSONL event log. ``StreamEvent`` is the
*in-memory* channel used to surface a turn incrementally to a client (the plain terminal client or future Phase 8 UI clients,
and any future streaming client) — token-level text deltas, lifecycle transitions, tool
activity, and the final response — without changing the durable event log or granting any
new authority. Tool execution still flows through the broker, policy, and approvals; this
contract only describes what a client may observe in real time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from raiker.contracts.models import AgentResponse

# StreamEvent kinds.
LIFECYCLE = "lifecycle"  # a runtime state/event transition (event_type + payload)
TEXT_DELTA = "text_delta"  # an incremental chunk of model answer text
TOOL = "tool"  # tool proposal/decision/result activity
FINAL = "final"  # terminal event; carries the complete AgentResponse
ERROR = "error"  # a safe error surfaced to the client

STREAM_KINDS = (LIFECYCLE, TEXT_DELTA, TOOL, FINAL, ERROR)


@dataclass(frozen=True)
class StreamEvent:
    """One incremental, client-observable event for a single turn."""

    kind: str
    text: str = ""
    event_type: str = ""
    payload: dict[str, object] = field(default_factory=dict)
    response: AgentResponse | None = None

    def __post_init__(self) -> None:
        if self.kind not in STREAM_KINDS:
            raise ValueError(f"invalid_stream_kind:{self.kind}")
