from __future__ import annotations

import json

from raiker.contracts.models import VectorRecord
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import ApproximateVectorIndex, MemoryVectorIndexCache


def test_small_corpora_keep_exact_vector_ranking() -> None:
    index = ApproximateVectorIndex(2)
    index.upsert("near", [1.0, 0.0])
    index.upsert("far", [0.0, 1.0])

    assert [item["vector_id"] for item in index.search([1.0, 0.0], top_k=1)] == ["near"]


def test_large_corpus_uses_a_matching_lsh_bucket_then_exactly_reranks() -> None:
    index = ApproximateVectorIndex(4)
    for number in range(600):
        # Deterministic, non-zero vectors whose exact match is unambiguous.
        index.upsert(f"other-{number}", [0.0, 1.0, float(number % 7), -1.0])
    index.upsert("exact", [1.0, 0.0, 0.0, 0.0])

    first = index.search([1.0, 0.0, 0.0, 0.0], top_k=1)[0]
    assert first["vector_id"] == "exact"
    assert first["score"] == 1.0


def test_cache_reloads_only_after_the_durable_revision_changes() -> None:
    cache = MemoryVectorIndexCache()
    loads = 0

    def load() -> list[dict[str, object]]:
        nonlocal loads
        loads += 1
        return [{"vector_id": "v1", "vector": [1.0, 0.0], "metadata": {"memory_id": "m1"}}]

    first = cache.search(revision=1, dimensions=2, query_vector=[1.0, 0.0], top_k=1, load=load)
    second = cache.search(revision=1, dimensions=2, query_vector=[1.0, 0.0], top_k=1, load=load)
    changed = cache.search(revision=2, dimensions=2, query_vector=[1.0, 0.0], top_k=1, load=load)

    assert [item["vector_id"] for item in first] == ["v1"]
    assert [item["vector_id"] for item in second] == ["v1"]
    assert [item["vector_id"] for item in changed] == ["v1"]
    assert loads == 2


def test_database_revision_advances_when_a_vector_changes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    before = store.active_memory_vector_revision()
    store.insert_vector_record(
        VectorRecord(
            vector_id="vector-cache-revision",
            content_hash="hash",
            content_preview="",
            embedding_model="test-model",
            dimensions=2,
            scope="global",
            sensitivity="normal",
            embedding=json.dumps([1.0, 0.0]),
            created_at="2026-08-28T00:00:00Z",
            owner_principal_id="owner",
        )
    )

    assert store.active_memory_vector_revision() > before
