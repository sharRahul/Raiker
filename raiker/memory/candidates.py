from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.ids import new_id, utc_now


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    source_event_id: str
    memory_type: str
    scope: str
    text: str
    sensitivity: str
    confidence: float
    decision: str
    created_at: str


def create_deferred_candidate(
    source_event_id: str, text: str, scope: str = "project"
) -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id=new_id("memcand_"),
        source_event_id=source_event_id,
        memory_type="project",
        scope=scope,
        text=text,
        sensitivity="normal",
        confidence=0.5,
        decision="deferred",
        created_at=utc_now(),
    )


def governed_memory_status(candidates: list[dict[str, object]]) -> dict[str, object]:
    return {
        "durable_writes_enabled": False,
        "candidate_count": len(candidates),
        "mode": "read_only_review",
    }
