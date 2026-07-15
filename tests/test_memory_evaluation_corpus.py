from pathlib import Path

from raiker.memory.evaluation import (
    RetrievalBudget,
    enforce_retrieval_budget,
    evaluate_lexical_retrieval,
)
from raiker.memory.evaluation_corpus import MEMORY_EVAL_V1, seed_memory_eval_v1
from raiker.storage.sqlite import SQLiteStore


def test_versioned_evaluation_corpus_enforces_scope_archive_and_supersession(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    report = evaluate_lexical_retrieval(
        store, corpus_version=MEMORY_EVAL_V1, cases=seed_memory_eval_v1(store=store, workspace_root=tmp_path)
    )
    enforce_retrieval_budget(report, RetrievalBudget(min_precision_at_k=1, min_recall_at_k=1))
    assert report.policy_leak_count == 0
