"""Bounded hybrid retrieval over already-governed durable-memory projections."""
from __future__ import annotations

import json
from dataclasses import dataclass

from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text


@dataclass(frozen=True)
class HybridMemoryResult:
    memory_id: str
    text: str
    score: float
    sources: tuple[str, ...]


def retrieve_hybrid_memory(
    *, store: SQLiteStore, query: str, scope: str | None = None, entity_id: str | None = None,
    limit: int = 10,
) -> list[HybridMemoryResult]:
    if not query.strip() or limit < 1:
        return []
    candidates: dict[str, tuple[float, set[str]]] = {}
    for row in store.search_approved_memory(query, scope=scope, limit=limit):
        candidates[str(row["memory_id"])] = (3.0, {"lexical"})
    index = VectorIndex(384)
    for row in store.list_active_memory_vector_embeddings(LOCAL_EMBEDDING_MODEL, scope=scope):
        try:
            vector = json.loads(str(row["embedding"]))
        except (TypeError, ValueError):
            continue
        if isinstance(vector, list) and len(vector) == 384:
            index.upsert(str(row["vector_id"]), vector, {"memory_id": str(row["memory_id"])})
    for hit in index.search(embed_text(query, 384), top_k=limit):
        memory_id = str(hit["metadata"]["memory_id"])
        score, sources = candidates.get(memory_id, (0.0, set()))
        candidates[memory_id] = (score + float(hit["score"]), sources | {"vector"})
    if entity_id:
        for row in store.list_memory_entity_neighborhood(entity_id, scope=scope):
            memory_id = str(row["evidence_memory_id"])
            score, sources = candidates.get(memory_id, (0.0, set()))
            candidates[memory_id] = (score + float(row["confidence"]), sources | {"graph"})
    results: list[HybridMemoryResult] = []
    for memory_id, (score, sources) in candidates.items():
        memory_row = store.get_active_approved_memory(memory_id)
        if memory_row is not None:
            results.append(HybridMemoryResult(memory_id, str(memory_row["text"]), score, tuple(sorted(sources))))
    return sorted(results, key=lambda item: (-item.score, item.memory_id))[:limit]
