"""Small, reproducible lexical-memory evaluation harness for CI and owner runs."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median, quantiles
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
        rows = store.search_approved_memory(case.query, scope=case.scope, limit=top_k)
        result_ids = [str(row["memory_id"]) for row in rows]
        latencies.append((perf_counter() - started) * 1000)
        expected = set(case.expected_memory_ids)
        hits = [memory_id for memory_id in result_ids if memory_id in expected]
        precisions.append(len(hits) / len(result_ids) if result_ids else 1.0)
        recalls.append(len(hits) / len(expected) if expected else 1.0)
        reciprocal_ranks.append(next((1 / index for index, memory_id in enumerate(result_ids, 1) if memory_id in expected), 0.0))
        ndcgs.append(sum(1 / (index + 1) for index, memory_id in enumerate(result_ids) if memory_id in expected) / sum(1 / (index + 1) for index in range(min(len(expected), top_k))))
        leaks += len(set(result_ids).intersection(case.forbidden_memory_ids))
        token_count += sum(len(str(row["text"])) // 4 for row in rows)
        storage_bytes += sum(len(str(row["text"]).encode()) for row in rows)
    p95 = max(latencies) if len(latencies) == 1 else quantiles(latencies, n=20)[18]
    return RetrievalEvaluation(
        corpus_version, len(cases), sum(precisions) / len(cases), sum(recalls) / len(cases),
        sum(reciprocal_ranks) / len(cases), sum(ndcgs) / len(cases), leaks, median(latencies), p95,
        token_count, 0.0, storage_bytes,
    )


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
