import json
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.entities import create_entity, relate_entities
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text


def test_hybrid_retrieval_deduplicates_governed_lexical_vector_and_graph_hits(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Sarah is married to Mark.", workspace_root=tmp_path, scope="project:family", store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    vector_id = new_id("vec_")
    store.insert_vector_record(VectorRecord(vector_id, VectorIndex.compute_content_hash(memory.text), memory.text, LOCAL_EMBEDDING_MODEL, 384, memory.scope, memory.sensitivity, utc_now(), json.dumps(embed_text(memory.text, 384))))
    store.link_memory_projection(memory.memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL)
    sarah = create_entity(store=store, name="Sarah", entity_type="person")
    mark = create_entity(store=store, name="Mark", entity_type="person")
    relate_entities(store=store, subject_entity_id=sarah, predicate="married_to", object_entity_id=mark, evidence_memory_id=memory.memory_id, confidence=0.9)
    result = retrieve_hybrid_memory(store=store, query="Sarah married", scope="project:family", entity_id=sarah)
    assert len(result) == 1
    assert result[0].memory_id == memory.memory_id
    assert result[0].sources == ("graph", "lexical", "vector")
