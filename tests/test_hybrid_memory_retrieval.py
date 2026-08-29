import json
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.entities import create_entity, relate_entities
from raiker.memory.retrieval import HybridRetrievalWeights, retrieve_hybrid_memory
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
    assert result[0].source_event_id == memory.source_event_id
    assert result[0].scope == memory.scope
    assert result[0].sensitivity == memory.sensitivity
    assert result[0].confidence == memory.confidence
    assert result[0].retention == memory.retention
    assert result[0].trust_label == "untrusted_memory_data"
    assert dict(result[0].score_breakdown)["lexical"] == 3.0
    assert {source for source, _ in result[0].score_breakdown} == {"graph", "lexical", "vector"}


def test_hybrid_retrieval_rejects_negative_weights() -> None:
    try:
        HybridRetrievalWeights(vector=-1)
    except ValueError as error:
        assert str(error) == "invalid_hybrid_retrieval_weights"
    else:
        raise AssertionError("negative weights must fail closed")


def test_a_question_recalls_the_memory_that_answers_it(tmp_path: Path) -> None:
    """BUG-243 — a question is not a filter.

    The full-text join is an AND, so every indexable word in the query had to
    appear in the stored sentence. "Where do my nightly backups go?" therefore
    found nothing against a memory that says exactly where they go, because the
    memory does not contain the word "where". Ambient recall fired for keyword
    queries and almost never for a sentence, which is the shape of a memory
    system that looks present and is not.
    """
    store = SQLiteStore(tmp_path)
    governance = MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test")
    answer = write_memory(
        "My nightly backups go to the encrypted NAS in the garage.",
        workspace_root=tmp_path, store=store, governance=governance,
    )

    found = retrieve_hybrid_memory(store=store, query="Where do my nightly backups go?")
    assert [m.memory_id for m in found] == [answer.memory_id]

    # Precision is not traded for it: the join stays an AND over the words that
    # carry meaning, so an unrelated question still recalls nothing.
    assert retrieve_hybrid_memory(store=store, query="What is the weather?") == []

    # And a query that is only function words still searches for them literally,
    # rather than silently becoming a search for nothing.
    assert [m.memory_id for m in retrieve_hybrid_memory(store=store, query="the")] == [
        answer.memory_id
    ]
