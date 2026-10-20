"""MEM-EVAL-06 — the recall corpus, scored through the real context assembly."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.memory.recall_evaluation import (
    MEMORY_RECALL_EVAL_V2,
    evaluate_recall_corpus,
    seed_recall_eval_v2,
)
from raiker.storage.sqlite import SQLiteStore


def test_recall_corpus_scores_precision_provenance_and_unsafe_recall(
    tmp_path: Path, seed_account: Any
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bootstrap_owner("bootstrap", "Bootstrap", workspace_root=workspace)
    owner, _ = seed_account(workspace, "owner")
    stranger, _ = seed_account(workspace, "stranger")
    store = SQLiteStore(workspace)

    cases = seed_recall_eval_v2(store=store, workspace_root=workspace, owner=owner, stranger=stranger)
    report = evaluate_recall_corpus(store=store, workspace_root=workspace, owner=owner, cases=cases)

    by_case = {result.case_id: result for result in report.cases}
    assert report.corpus_version == MEMORY_RECALL_EVAL_V2
    assert report.case_count == len(cases) == 9
    assert report.unsafe_recall_rate == 0.0, [r for r in report.cases if r.unsafe]
    assert report.provenance_completeness == 1.0
    assert report.precision == 1.0, [r for r in report.cases if r.precision < 1.0]
    for result in report.cases:
        assert "forbidden_recalled" not in result.notes
        assert "contradiction_misordered" not in result.notes
    for case_id in ("preference-recall", "stale-fact-correction", "contradictory-memories",
                    "prompt-injection-content", "owner-isolation", "project-isolation"):
        assert "expected_not_recalled" not in by_case[case_id].notes, by_case[case_id]
    assert by_case["incognito"].recalled == ()
    # The budget case keeps the bundle bounded: not every bulk record fits.
    assert 0 < len(by_case["retrieval-budget-truncation"].recalled) < 12 + 6
    # The evaluation leaves the owner's Incognito as it found it.
    assert store.is_memory_incognito(owner) is False
