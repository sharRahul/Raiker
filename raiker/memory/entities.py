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
