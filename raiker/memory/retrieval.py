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
    source_event_id: str
    scope: str
    sensitivity: str
    confidence: float
    retention: str
    trust_label: str = "untrusted_memory_data"
    score_breakdown: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class HybridRetrievalWeights:
    lexical: float = 3.0
    vector: float = 1.0
    graph: float = 1.0

    def __post_init__(self) -> None:
        if min(self.lexical, self.vector, self.graph) < 0:
            raise ValueError("invalid_hybrid_retrieval_weights")


def retrieve_hybrid_memory(
    *, store: SQLiteStore, query: str, scope: str | None = None, entity_id: str | None = None,
    limit: int = 10, weights: HybridRetrievalWeights | None = None,
) -> list[HybridMemoryResult]:
    if not query.strip() or limit < 1:
        return []
    weights = weights or HybridRetrievalWeights()
    candidates: dict[str, tuple[float, set[str], dict[str, float]]] = {}
    for row in store.search_approved_memory(query, scope=scope, limit=limit):
        candidates[str(row["memory_id"])] = (weights.lexical, {"lexical"}, {"lexical": weights.lexical})
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
        score, sources, breakdown = candidates.get(memory_id, (0.0, set(), {}))
        contribution = float(hit["score"]) * weights.vector
        candidates[memory_id] = (
            score + contribution,
            sources | {"vector"},
            {**breakdown, "vector": contribution},
        )
    if entity_id:
        for row in store.list_memory_entity_neighborhood(entity_id, scope=scope):
            memory_id = str(row["evidence_memory_id"])
            score, sources, breakdown = candidates.get(memory_id, (0.0, set(), {}))
            contribution = float(row["confidence"]) * weights.graph
            candidates[memory_id] = (
                score + contribution,
                sources | {"graph"},
                {**breakdown, "graph": contribution},
            )
    results: list[HybridMemoryResult] = []
    for memory_id, (score, sources, breakdown) in candidates.items():
        memory_row = store.get_active_approved_memory(memory_id)
        if memory_row is not None:
            results.append(
                HybridMemoryResult(
                    memory_id,
                    str(memory_row["text"]),
                    score,
                    tuple(sorted(sources)),
                    str(memory_row["source_event_id"]),
                    str(memory_row["scope"]),
                    str(memory_row["sensitivity"]),
                    float(memory_row["confidence"]),
                    str(memory_row["retention"]),
                    score_breakdown=tuple(sorted(breakdown.items())),
                )
            )
    return sorted(results, key=lambda item: (-item.score, item.memory_id))[:limit]
