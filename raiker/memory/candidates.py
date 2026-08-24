from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

# The capability that decides whether a turn may propose a durable memory write
# at all. `memory_forget_execution` governs removal and is reported alongside it,
# because "can this agent change my memory?" is one question to an owner.
MEMORY_WRITE_CAPABILITY = "memory_write_execution"
MEMORY_FORGET_CAPABILITY = "memory_forget_execution"


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
    source_session_id: str | None = None
    source_turn_id: str | None = None
    source_role: str | None = None
    extractor_version: str | None = None


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


# The one shared admission read (GEP-01). Imported inside the functions because
# `raiker.runtime.authority` pulls the executor registry, which reaches back into
# this module through the context gatherer.
def _gate_enabled(store: SQLiteStore, principal_id: str | None, capability: str) -> bool:
    from raiker.runtime.authority.admission import capability_admission

    return capability_admission(store, principal_id, capability).gate_enabled


def _decision_mode(store: SQLiteStore, principal_id: str | None, capability: str) -> str:
    from raiker.runtime.authority.admission import capability_admission

    return capability_admission(store, principal_id, capability).decision_mode.value


def governed_memory_status(
    candidates: list[dict[str, object]],
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """What the memory capability *actually* allows right now (BUG-71).

    This used to return ``durable_writes_enabled: False`` and
    ``mode: read_only_review`` as literals. The runtime has real, broker-governed
    ``memory_write`` / ``memory_forget`` executors behind the
    ``memory_write_execution`` and ``memory_forget_execution`` gates, so the
    literal was a claim about the product rather than a reading of it: an owner
    could enable the capability, set it to Allow, and be told by the agent that
    memory is read-only.

    Called without a store it still answers conservatively — nothing to read
    means nothing can be asserted as enabled — but every in-runtime caller now
    passes the store and the acting principal, so the answer is the gate state
    and decision mode the next write would actually meet.
    """
    if store is None:
        return {
            "durable_writes_enabled": False,
            "candidate_count": len(candidates),
            "mode": "read_only_review",
            "write_gate_enabled": False,
            "forget_gate_enabled": False,
            "write_decision_mode": "unknown",
            "forget_decision_mode": "unknown",
        }
    write_enabled = _gate_enabled(store, principal_id, MEMORY_WRITE_CAPABILITY)
    forget_enabled = _gate_enabled(store, principal_id, MEMORY_FORGET_CAPABILITY)
    write_mode = _decision_mode(store, principal_id, MEMORY_WRITE_CAPABILITY)
    forget_mode = _decision_mode(store, principal_id, MEMORY_FORGET_CAPABILITY)
    # `deny` is the one mode under which the gate being on changes nothing: the
    # write is refused before it reaches an executor. Every other mode still
    # reaches a decision (ask/auto park it for the owner; allow runs it), so the
    # honest answer to "can a turn write memory" is yes.
    durable = write_enabled and write_mode != "deny"
    if durable:
        mode = "governed_write" if write_mode == "allow" else "governed_write_review"
    elif write_enabled:
        mode = "denied_by_decision_mode"
    else:
        mode = "read_only_review"
    return {
        "durable_writes_enabled": durable,
        "candidate_count": len(candidates),
        "mode": mode,
        "write_gate_enabled": write_enabled,
        "forget_gate_enabled": forget_enabled,
        "write_decision_mode": write_mode,
        "forget_decision_mode": forget_mode,
    }
