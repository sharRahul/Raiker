from pathlib import Path

from raiker.memory.entities import create_entity, relate_entities
from raiker.memory.store import MemoryGovernance, set_memory_archived, write_memory
from raiker.storage.sqlite import SQLiteStore


def test_entity_relationship_requires_active_evidence_and_hides_archived_evidence(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Sarah is married to Mark.", workspace_root=tmp_path, scope="project:family", store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    sarah = create_entity(store=store, name="Sarah", entity_type="person")
    mark = create_entity(store=store, name="Mark", entity_type="person")
    relationship_id = relate_entities(
        store=store, subject_entity_id=sarah, predicate="married_to", object_entity_id=mark,
        evidence_memory_id=memory.memory_id, confidence=0.9,
    )
    assert store.list_memory_entity_neighborhood(sarah, "project:family")[0]["relationship_id"] == relationship_id
    set_memory_archived(memory.memory_id, archived=True, workspace_root=tmp_path, store=store)
    assert store.list_memory_entity_neighborhood(sarah, "project:family") == []
