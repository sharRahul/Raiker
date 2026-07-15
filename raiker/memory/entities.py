"""Evidence-bound entity graph helpers for governed durable memory."""
from __future__ import annotations

from raiker.contracts.ids import new_id
from raiker.storage.sqlite import SQLiteStore


def create_entity(*, store: SQLiteStore, name: str, entity_type: str) -> str:
    entity_id = new_id("ent_")
    store.upsert_memory_entity(entity_id, name, entity_type)
    with store.connect() as connection:
        row = connection.execute(
            "SELECT entity_id FROM memory_entities WHERE normalized_name = ? AND entity_type = ?",
            (" ".join(name.casefold().split()), entity_type.strip()),
        ).fetchone()
    return str(row["entity_id"])


def relate_entities(
    *, store: SQLiteStore, subject_entity_id: str, predicate: str, object_entity_id: str,
    evidence_memory_id: str, confidence: float,
) -> str:
    relationship_id = new_id("rel_")
    store.link_memory_entities(
        relationship_id, subject_entity_id, predicate, object_entity_id, evidence_memory_id, confidence
    )
    return relationship_id


def propose_entity_relationship(
    *, store: SQLiteStore, subject_name: str, subject_type: str, predicate: str,
    object_name: str, object_type: str, evidence_memory_id: str, confidence: float,
) -> str:
    """Queue an inferred relationship; it cannot mutate the graph by itself."""
    candidate_id = new_id("memcand_")
    store.create_memory_relationship_candidate(
        candidate_id, subject_name=subject_name, subject_type=subject_type, predicate=predicate,
        object_name=object_name, object_type=object_type, evidence_memory_id=evidence_memory_id,
        confidence=confidence,
    )
    return candidate_id


def resolve_entity_relationship_proposal(
    *, store: SQLiteStore, candidate_id: str, decision: str, reviewer_id: str,
) -> str | None:
    """Apply a reviewed proposal only after an explicit human approval."""
    candidate = store.get_memory_relationship_candidate(candidate_id)
    if candidate is None or str(candidate["decision"]) != "needs_user_review":
        return None
    if decision == "denied":
        return "" if store.resolve_memory_relationship_candidate(
            candidate_id, decision=decision, resolved_by=reviewer_id
        ) else None
    if decision != "approved":
        raise ValueError("invalid_memory_relationship_resolution")
    if store.get_active_approved_memory(str(candidate["evidence_memory_id"])) is None:
        raise ValueError("memory_relationship_evidence_not_active")
    subject_id = create_entity(
        store=store, name=str(candidate["subject_name"]), entity_type=str(candidate["subject_type"])
    )
    object_id = create_entity(
        store=store, name=str(candidate["object_name"]), entity_type=str(candidate["object_type"])
    )
    relationship_id = relate_entities(
        store=store, subject_entity_id=subject_id, predicate=str(candidate["predicate"]),
        object_entity_id=object_id, evidence_memory_id=str(candidate["evidence_memory_id"]),
        confidence=float(candidate["confidence"]),
    )
    if not store.resolve_memory_relationship_candidate(candidate_id, decision=decision, resolved_by=reviewer_id):
        raise RuntimeError("memory_relationship_resolution_race")
    return relationship_id
