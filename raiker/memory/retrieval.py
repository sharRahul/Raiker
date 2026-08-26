"""Bounded hybrid retrieval over already-governed durable-memory projections."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from raiker.storage.sqlite import SQLiteStore
from raiker.vector import VectorIndex
from raiker.vector.backends import EmbeddingBackend, resolve_embedding_backend


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
    #: MEM-03 — which embedding space the vector leg searched, and whether that
    #: space can relate two texts that share no token. Carried on the result
    #: because "recalled by similarity" means something different in a learned
    #: space than in a hashing one, and the reader has to be able to tell.
    vector_backend: str = ""
    vector_backend_semantic: bool = False
    #: MEM-11 — read from the row this result was already built from, so the
    #: model-facing tool can answer "when, and filed under what" without a
    #: second query per hit. The lexical-only tool this replaced returned them
    #: and they are worth keeping: a memory's age is how a reader decides
    #: whether it has been superseded in spirit if not in the record.
    created_at: str = ""
    tags: tuple[str, ...] = ()
    source: str = ""


@dataclass(frozen=True)
class HybridRetrievalWeights:
    lexical: float = 3.0
    vector: float = 1.0
    graph: float = 1.0

    def __post_init__(self) -> None:
        if min(self.lexical, self.vector, self.graph) < 0:
            raise ValueError("invalid_hybrid_retrieval_weights")


#: How many entities one query may anchor a graph traversal on. Bounded because
#: each anchor is a separate neighborhood query, and because a query that names
#: five entities is asking a broad question the lexical leg answers better.
_MAX_GRAPH_ANCHORS = 3

#: Embeds a query in a named space. Injected rather than imported so the
#: egress-gated path stays where the capability check is — this module never
#: performs a provider call on its own.
QueryEmbedder = Callable[[EmbeddingBackend, str], list[float] | None]


def default_query_embedder() -> QueryEmbedder | None:
    """No context-free embedder exists; production callers supply governance context."""
    return None


def _embed_query(
    backend: EmbeddingBackend, query: str, embedder: QueryEmbedder | None = None
) -> list[float] | None:
    """The query, in *backend*'s space — or nothing at all.

    Returning ``None`` drops the vector leg for this search. That is deliberate
    and is the whole point of MEM-03: when the stored vectors are semantic and
    no governed embedder is available to match them, the alternative is to embed
    the query with the hashing fallback and compare two unrelated spaces. A
    missing leg is a smaller lie than a meaningless one.
    """
    resolved = embedder or default_query_embedder()
    if resolved is not None:
        return resolved(backend, query)
    if backend.semantic:
        return None
    return backend.embed(query)


def _tags_of(row: Any) -> tuple[str, ...]:
    """Tags as a tuple, or empty. A malformed `tags_json` is not a failed search."""
    try:
        parsed = json.loads(str(row["tags_json"] or "[]"))
    except (TypeError, ValueError):
        return ()
    return tuple(str(tag) for tag in parsed) if isinstance(parsed, list) else ()


def retrieve_hybrid_memory(
    *, store: SQLiteStore, query: str, scope: str | None = None, entity_id: str | None = None,
    limit: int = 10, weights: HybridRetrievalWeights | None = None,
    owner_principal_id: str | None = None,
    embedding_backend: EmbeddingBackend | None = None,
    query_embedder: QueryEmbedder | None = None,
) -> list[HybridMemoryResult]:
    if not query.strip() or limit < 1:
        return []
    weights = weights or HybridRetrievalWeights()
    # MEM-03 — the vector leg searches exactly one embedding space, and the query
    # is embedded in that same space. Mixing two spaces produces cosines between
    # coordinates that mean different things, which is not a weaker signal but a
    # meaningless one.
    backend = embedding_backend or resolve_embedding_backend(
        store, owner_principal_id=owner_principal_id
    )
    candidates: dict[str, tuple[float, set[str], dict[str, float]]] = {}
    for row in store.search_approved_memory(query, scope=scope, limit=limit, owner_principal_id=owner_principal_id):
        candidates[str(row["memory_id"])] = (weights.lexical, {"lexical"}, {"lexical": weights.lexical})
    index = VectorIndex(backend.dimensions)
    for row in store.list_active_memory_vector_embeddings(
        backend.model_label, scope=scope, owner_principal_id=owner_principal_id
    ):
        try:
            vector = json.loads(str(row["embedding"]))
        except (TypeError, ValueError):
            continue
        if isinstance(vector, list) and len(vector) == backend.dimensions:
            index.upsert(str(row["vector_id"]), vector, {"memory_id": str(row["memory_id"])})
    query_vector = _embed_query(backend, query, query_embedder)
    for hit in ([] if query_vector is None else index.search(query_vector, top_k=limit)):
        # `search` returns the top *k* by similarity with no floor, so on a small
        # or unrelated corpus it returns every memory in scope, including the ones
        # that share no token with the query at all. Admitting those puts
        # unrelated owner memories into the model's context as "recalled", and a
        # negative similarity would subtract from a genuine lexical hit. Only a
        # positive similarity is evidence of anything.
        if float(hit["score"]) <= 0.0:
            continue
        memory_id = str(hit["metadata"]["memory_id"])
        score, sources, breakdown = candidates.get(memory_id, (0.0, set(), {}))
        contribution = float(hit["score"]) * weights.vector
        candidates[memory_id] = (
            score + contribution,
            sources | {"vector"},
            {**breakdown, "vector": contribution},
        )
    # MEM-12 — the graph leg now has an anchor on an ordinary turn.
    #
    # It was gated on an `entity_id` the caller had to already know, and the
    # context gatherer — the only production caller — never passed one. So the
    # third leg of "hybrid" retrieval never ran outside the evaluation harness,
    # and the shortfall was invisible: two legs still answer, just without the
    # one that relates a memory to a memory.
    #
    # An explicit `entity_id` still wins, because a caller that names one is
    # asking about that entity rather than about the words in the query.
    # Otherwise the anchors are resolved from the query itself, which is what
    # makes the leg reachable from Chat, Build and ambient recall alike.
    anchors = (
        [entity_id]
        if entity_id
        else [
            str(row["entity_id"])
            for row in store.match_memory_entities(
                query,
                limit=_MAX_GRAPH_ANCHORS,
                owner_principal_id=owner_principal_id,
            )
        ]
    )
    for anchor in anchors:
        for row in store.list_memory_entity_neighborhood(
            anchor, scope=scope, owner_principal_id=owner_principal_id
        ):
            memory_id = str(row["evidence_memory_id"])
            score, sources, breakdown = candidates.get(memory_id, (0.0, set(), {}))
            contribution = float(row["confidence"]) * weights.graph
            # `max`, not `+`: two anchors that both reach the same memory are
            # two paths to one fact, not two facts. Summing would let a densely
            # connected entity outrank an exact lexical hit on nothing more than
            # how many edges happen to point at it.
            existing = breakdown.get("graph", 0.0)
            if contribution <= existing:
                continue
            candidates[memory_id] = (
                score - existing + contribution,
                sources | {"graph"},
                {**breakdown, "graph": contribution},
            )
    results: list[HybridMemoryResult] = []
    for memory_id, (score, sources, breakdown) in candidates.items():
        memory_row = store.get_active_approved_memory(memory_id, owner_principal_id=owner_principal_id)
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
                    vector_backend=backend.model_label,
                    vector_backend_semantic=backend.semantic,
                    created_at=str(memory_row["created_at"] or ""),
                    tags=_tags_of(memory_row),
                    source=str(memory_row["source"] or ""),
                )
            )
    return sorted(results, key=lambda item: (-item.score, item.memory_id))[:limit]
