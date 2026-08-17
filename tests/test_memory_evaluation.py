from pathlib import Path

import pytest

from raiker.memory.evaluation import (
    RetrievalBudget,
    RetrievalCase,
    enforce_retrieval_budget,
    evaluate_graph_retrieval,
    evaluate_hybrid_retrieval,
    evaluate_lexical_retrieval,
    evaluate_vector_retrieval,
    lexical_backend_version,
)
from raiker.memory.store import (
    MemoryGovernance,
    correct_memory,
    list_memory,
    set_memory_archived,
    write_memory,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL


def _write(store: SQLiteStore, workspace: Path, text: str, scope: str) -> str:
    return write_memory(
        text, workspace_root=workspace, scope=scope, store=store,
        governance=MemoryGovernance("evt_eval", "sess_eval", None, "test", 1, 1, "until_forget", "approved", "test"),
    ).memory_id


def test_evaluation_reports_quality_latency_and_policy_leaks(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    expected = _write(store, tmp_path, "Raiker uses an archive-first memory lifecycle.", "project:alpha")
    forbidden = _write(store, tmp_path, "Raiker uses an archive-first memory lifecycle.", "project:beta")
    set_memory_archived(forbidden, archived=True, workspace_root=tmp_path, store=store)
    report = evaluate_lexical_retrieval(
        store, corpus_version="memory-eval-v1", cases=(
            RetrievalCase("scope-and-archive", "archive-first lifecycle", (expected,), (forbidden,), "project:alpha"),
        ),
    )
    assert report.corpus_version == "memory-eval-v1"
    assert report.recall_at_k == report.mean_reciprocal_rank == report.ndcg_at_k == 1.0
    assert report.policy_leak_count == 0
    assert report.p95_latency_ms >= 0
    assert report.precision_at_k == 1.0
    evaluation_id = store.create_memory_evaluation_run(report)
    assert evaluation_id.startswith("mev_")
    with store.connect() as connection:
        row = connection.execute(
            "SELECT policy_leak_count, backend_version, scope, workload, latency_distribution_json "
            "FROM memory_evaluation_runs WHERE evaluation_id = ?", (evaluation_id,)
        ).fetchone()
    assert row["policy_leak_count"] == 0
    assert row["backend_version"] == lexical_backend_version(store)
    assert row["scope"] == "project:alpha"
    assert row["workload"] == "retrieval_case_set"
    assert '"p95_ms"' in row["latency_distribution_json"]


def test_all_retrieval_strategies_report_aggregate_context(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "A durable scoped retrieval result.", "project:alpha")
    cases = (RetrievalCase("strategy", "durable retrieval", (memory_id,), scope="project:alpha"),)
    reports = (
        evaluate_lexical_retrieval(store, corpus_version="memory-eval-v1", cases=cases),
        evaluate_vector_retrieval(store, corpus_version="memory-eval-v1", cases=cases),
        evaluate_graph_retrieval(store, corpus_version="memory-eval-v1", cases=cases),
        evaluate_hybrid_retrieval(store, corpus_version="memory-eval-v1", cases=cases),
    )
    lexical = lexical_backend_version(store)
    assert {report.backend_version for report in reports} == {
        lexical, LOCAL_EMBEDDING_MODEL, "memory-entity-graph-v1",
        f"{lexical}+{LOCAL_EMBEDDING_MODEL}+memory-entity-graph-v1",
    }
    for report in reports:
        assert report.scope == "project:alpha"
        assert report.workload == "retrieval_case_set"
        assert report.latency_distribution is not None
        assert report.latency_distribution["count"] == 1
    evaluation_id = store.create_memory_evaluation_run(reports[1])
    with store.connect() as connection:
        assert connection.execute(
            "SELECT strategy FROM memory_evaluation_runs WHERE evaluation_id = ?", (evaluation_id,)
        ).fetchone()["strategy"] == "vector"


def test_correction_supersedes_old_fact_and_removes_it_from_retrieval(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    original = _write(store, tmp_path, "The preferred editor is Vim.", "project:alpha")
    replacement = correct_memory(
        original, "The preferred editor is VS Code.", workspace_root=tmp_path, store=store,
        remembered_reason="The user updated their preference.",
        governance=MemoryGovernance("evt_correct", "sess", None, "human", 1, 1, "until_forget", "approved", "human"),
    )
    assert replacement is not None and replacement.supersedes_memory_id == original
    assert store.search_approved_memory("Vim", scope="project:alpha") == []
    assert [row["memory_id"] for row in store.search_approved_memory("VS Code", scope="project:alpha")] == [replacement.memory_id]
    assert [entry.memory_id for entry in list_memory(workspace_root=tmp_path, store=store)] == [replacement.memory_id]


def test_evaluation_budget_rejects_policy_leaks(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "Scoped result.", "project:alpha")
    report = evaluate_lexical_retrieval(
        store, corpus_version="memory-eval-v1", cases=(
            RetrievalCase("leak", "Scoped", (memory_id,), (memory_id,), "project:alpha"),
        ),
    )
    with pytest.raises(AssertionError, match="policy_leak"):
        enforce_retrieval_budget(report, RetrievalBudget())


def test_evaluation_budget_rejects_token_and_storage_regressions(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "A durable scoped retrieval result.", "project:alpha")
    report = evaluate_lexical_retrieval(
        store,
        corpus_version="memory-eval-v1",
        cases=(RetrievalCase("budget", "durable retrieval", (memory_id,), scope="project:alpha"),),
    )
    with pytest.raises(AssertionError, match="token_regression"):
        enforce_retrieval_budget(report, RetrievalBudget(max_token_count=0))
    with pytest.raises(AssertionError, match="storage_regression"):
        enforce_retrieval_budget(report, RetrievalBudget(max_storage_bytes=0))


def test_secret_like_durable_memory_is_not_retrievable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "api_key=abcdefghijklmnop", "project:alpha")
    assert store.get_active_approved_memory(memory_id) is None
    assert store.search_approved_memory("api key", scope="project:alpha") == []
