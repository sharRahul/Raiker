from pathlib import Path

from raiker.memory.evaluation import RetrievalCase, evaluate_lexical_retrieval
from raiker.memory.store import MemoryGovernance, set_memory_archived, write_memory
from raiker.storage.sqlite import SQLiteStore


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
