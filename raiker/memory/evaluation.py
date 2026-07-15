"""Small, reproducible lexical-memory evaluation harness for CI and owner runs."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import quantiles
from time import perf_counter

from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    query: str
    expected_memory_ids: tuple[str, ...]
    forbidden_memory_ids: tuple[str, ...] = ()
    scope: str | None = None


@dataclass(frozen=True)
class RetrievalEvaluation:
    corpus_version: str
    case_count: int
    recall_at_k: float
    mean_reciprocal_rank: float
    ndcg_at_k: float
    policy_leak_count: int
    p95_latency_ms: float


def evaluate_lexical_retrieval(
    store: SQLiteStore, *, corpus_version: str, cases: tuple[RetrievalCase, ...], top_k: int = 5
) -> RetrievalEvaluation:
    if not corpus_version or not cases or top_k < 1:
        raise ValueError("invalid_retrieval_evaluation")
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    latencies: list[float] = []
    leaks = 0
    for case in cases:
        started = perf_counter()
        result_ids = [str(row["memory_id"]) for row in store.search_approved_memory(case.query, scope=case.scope, limit=top_k)]
        latencies.append((perf_counter() - started) * 1000)
        expected = set(case.expected_memory_ids)
        hits = [memory_id for memory_id in result_ids if memory_id in expected]
        recalls.append(len(hits) / len(expected) if expected else 1.0)
        reciprocal_ranks.append(next((1 / index for index, memory_id in enumerate(result_ids, 1) if memory_id in expected), 0.0))
        ndcgs.append(sum(1 / (index + 1) for index, memory_id in enumerate(result_ids) if memory_id in expected) / sum(1 / (index + 1) for index in range(min(len(expected), top_k))))
        leaks += len(set(result_ids).intersection(case.forbidden_memory_ids))
    p95 = max(latencies) if len(latencies) == 1 else quantiles(latencies, n=20)[18]
    return RetrievalEvaluation(corpus_version, len(cases), sum(recalls) / len(cases), sum(reciprocal_ranks) / len(cases), sum(ndcgs) / len(cases), leaks, p95)
