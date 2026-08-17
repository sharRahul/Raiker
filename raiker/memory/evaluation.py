"""Small, reproducible lexical-memory evaluation harness for CI and owner runs."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import median, quantiles
from time import perf_counter
from typing import Any

from raiker.memory.retrieval import HybridRetrievalWeights, retrieve_hybrid_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    query: str
    expected_memory_ids: tuple[str, ...]
    forbidden_memory_ids: tuple[str, ...] = ()
    scope: str | None = None
    entity_id: str | None = None


def lexical_backend_version(store: SQLiteStore) -> str:
    """The lexical engine a measurement was actually taken on.

    Two runs of the same corpus on FTS4 and FTS5 are not comparable — one has a
    relevance score and the other orders by time — so the engine belongs in the
    stored evaluation row rather than in a constant that outlives its truth.
    """
    return f"sqlite-{store.resolved_text_search_engine()}"


@dataclass(frozen=True)
class RetrievalEvaluation:
    corpus_version: str
    case_count: int
    precision_at_k: float
    recall_at_k: float
    mean_reciprocal_rank: float
    ndcg_at_k: float
    policy_leak_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    token_count: int
    compute_cost_usd: float
    storage_bytes: int
    backend_version: str = "sqlite-fts5"
    scope: str = "mixed"
    workload: str = "retrieval_case_set"
    latency_distribution: dict[str, float | int] | None = None
    strategy: str = "lexical_fts"


@dataclass(frozen=True)
class RetrievalBudget:
    min_precision_at_k: float = 0.0
    min_recall_at_k: float = 0.0
    max_p95_latency_ms: float = float("inf")
    max_compute_cost_usd: float = float("inf")
    max_token_count: int = 2**63 - 1
    max_storage_bytes: int = 2**63 - 1
    max_policy_leaks: int = 0


def evaluate_lexical_retrieval(
    store: SQLiteStore, *, corpus_version: str, cases: tuple[RetrievalCase, ...], top_k: int = 5
) -> RetrievalEvaluation:
    return evaluate_retrieval(
        corpus_version=corpus_version,
        cases=cases,
        retrieve=lambda case: store.search_approved_memory(case.query, scope=case.scope, limit=top_k),
        top_k=top_k,
        # Named from the probe, not from a literal: a measurement recorded
        # against the wrong engine cannot be compared with the next one.
        backend_version=lexical_backend_version(store),
        strategy="lexical_fts",
    )


def evaluate_vector_retrieval(
    store: SQLiteStore, *, corpus_version: str, cases: tuple[RetrievalCase, ...], top_k: int = 5
) -> RetrievalEvaluation:
    return _evaluate_hybrid_strategy(
        store, corpus_version=corpus_version, cases=cases, top_k=top_k,
        weights=HybridRetrievalWeights(lexical=0, vector=1, graph=0),
        strategy="vector", backend_version=LOCAL_EMBEDDING_MODEL,
    )


def evaluate_graph_retrieval(
    store: SQLiteStore, *, corpus_version: str, cases: tuple[RetrievalCase, ...], top_k: int = 5
) -> RetrievalEvaluation:
    return _evaluate_hybrid_strategy(
        store, corpus_version=corpus_version, cases=cases, top_k=top_k,
        weights=HybridRetrievalWeights(lexical=0, vector=0, graph=1),
        strategy="graph", backend_version="memory-entity-graph-v1",
    )


def evaluate_hybrid_retrieval(
    store: SQLiteStore, *, corpus_version: str, cases: tuple[RetrievalCase, ...], top_k: int = 5,
    weights: HybridRetrievalWeights | None = None,
) -> RetrievalEvaluation:
    return _evaluate_hybrid_strategy(
        store, corpus_version=corpus_version, cases=cases, top_k=top_k,
        weights=weights or HybridRetrievalWeights(), strategy="hybrid",
        backend_version=(
            f"{lexical_backend_version(store)}+{LOCAL_EMBEDDING_MODEL}+memory-entity-graph-v1"
        ),
    )


def _evaluate_hybrid_strategy(
    store: SQLiteStore, *, corpus_version: str, cases: tuple[RetrievalCase, ...], top_k: int,
    weights: HybridRetrievalWeights, strategy: str, backend_version: str,
) -> RetrievalEvaluation:
    return evaluate_retrieval(
        corpus_version=corpus_version,
        cases=cases,
        retrieve=lambda case: retrieve_hybrid_memory(
            store=store, query=case.query, scope=case.scope, entity_id=case.entity_id,
            limit=top_k, weights=weights,
        ),
        top_k=top_k,
        backend_version=backend_version,
        strategy=strategy,
    )


def evaluate_retrieval(
    *, corpus_version: str, cases: tuple[RetrievalCase, ...],
    retrieve: Callable[[RetrievalCase], Sequence[Any]], top_k: int = 5,
    backend_version: str, strategy: str, workload: str = "retrieval_case_set",
) -> RetrievalEvaluation:
    if not corpus_version or not cases or top_k < 1:
        raise ValueError("invalid_retrieval_evaluation")
    recalls: list[float] = []
    precisions: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    latencies: list[float] = []
    leaks = 0
    token_count = 0
    storage_bytes = 0
    for case in cases:
        started = perf_counter()
        rows = retrieve(case)
        result_ids = [_field(row, "memory_id") for row in rows]
        latencies.append((perf_counter() - started) * 1000)
        expected = set(case.expected_memory_ids)
        hits = [memory_id for memory_id in result_ids if memory_id in expected]
        precisions.append(len(hits) / len(result_ids) if result_ids else 1.0)
        recalls.append(len(hits) / len(expected) if expected else 1.0)
        reciprocal_ranks.append(next((1 / index for index, memory_id in enumerate(result_ids, 1) if memory_id in expected), 0.0))
        ndcgs.append(sum(1 / (index + 1) for index, memory_id in enumerate(result_ids) if memory_id in expected) / sum(1 / (index + 1) for index in range(min(len(expected), top_k))))
        leaks += len(set(result_ids).intersection(case.forbidden_memory_ids))
        token_count += sum(len(_field(row, "text")) // 4 for row in rows)
        storage_bytes += sum(len(_field(row, "text").encode()) for row in rows)
    p95 = max(latencies) if len(latencies) == 1 else quantiles(latencies, n=20)[18]
    scopes = {case.scope for case in cases}
    report_scope = next(iter(scopes)) if len(scopes) == 1 else None
    return RetrievalEvaluation(
        corpus_version, len(cases), sum(precisions) / len(cases), sum(recalls) / len(cases),
        sum(reciprocal_ranks) / len(cases), sum(ndcgs) / len(cases), leaks, median(latencies), p95,
        token_count, 0.0, storage_bytes, backend_version, report_scope or "mixed",
        workload, {"count": len(latencies), "p50_ms": median(latencies), "p95_ms": p95, "max_ms": max(latencies)}, strategy,
    )


def _field(row: Any, name: str) -> str:
    if isinstance(row, dict):
        return str(row[name])
    try:
        return str(row[name])
    except (KeyError, TypeError):
        return str(getattr(row, name))


def enforce_retrieval_budget(report: RetrievalEvaluation, budget: RetrievalBudget) -> None:
    if report.policy_leak_count > budget.max_policy_leaks:
        raise AssertionError("memory_retrieval_policy_leak")
    if report.precision_at_k < budget.min_precision_at_k:
        raise AssertionError("memory_retrieval_precision_regression")
    if report.recall_at_k < budget.min_recall_at_k:
        raise AssertionError("memory_retrieval_recall_regression")
    if report.p95_latency_ms > budget.max_p95_latency_ms:
        raise AssertionError("memory_retrieval_latency_regression")
    if report.compute_cost_usd > budget.max_compute_cost_usd:
        raise AssertionError("memory_retrieval_cost_regression")
    if report.token_count > budget.max_token_count:
        raise AssertionError("memory_retrieval_token_regression")
    if report.storage_bytes > budget.max_storage_bytes:
        raise AssertionError("memory_retrieval_storage_regression")
