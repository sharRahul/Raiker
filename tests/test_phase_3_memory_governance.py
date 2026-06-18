from __future__ import annotations

from raiker.cli.commands import handle_slash_command
from raiker.memory.policy import classify_memory_sensitivity
from raiker.memory.review import MemoryReviewQueue
from raiker.phase_gates import get_capability_gate
from raiker.workspace.inspection import inspect_workspace


def test_semantic_vector_writes_remain_disabled(tmp_path) -> None:  # type: ignore[no-untyped-def]
    queue = MemoryReviewQueue(tmp_path)
    summary = queue.export_summary()
    assert get_capability_gate("semantic_memory_writes").runtime_enabled is False
    assert summary["semantic_writes_enabled"] is False
    assert summary["embedding_records_written"] == 0
    assert summary["vector_records_written"] == 0


def test_memory_candidates_can_be_listed_and_reviewed_without_writes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    queue = MemoryReviewQueue(tmp_path)
    item = queue.add_candidate("Raiker project prefers local-first docs")
    assert item.can_write_semantic_memory is False
    approved = queue.mark(item.candidate_id, "approved_for_later")
    assert approved.decision == "approved_for_later"
    summary = queue.export_summary()
    assert summary["approved_for_later_count"] == 1
    assert summary["semantic_writes_enabled"] is False
    assert summary["embedding_records_written"] == 0
    assert summary["vector_records_written"] == 0


def test_secret_like_candidates_are_denied_or_blocked(tmp_path) -> None:  # type: ignore[no-untyped-def]
    item = MemoryReviewQueue(tmp_path).add_candidate("api_key = 'sk_test_1234567890abcdef1234567890'")
    assert item.sensitivity in {"secret_like", "credential_like"}
    assert item.decision == "denied"
    assert item.can_write_semantic_memory is False


def test_classification_is_deterministic_and_local() -> None:
    text = "password=supersecretvalue123456"
    assert classify_memory_sensitivity(text) == classify_memory_sensitivity(text)
    assert classify_memory_sensitivity("public documentation note").value == "public"
    assert classify_memory_sensitivity("").value == "unknown"


def test_memory_review_cli_is_read_only_and_workspace_summary_includes_governance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    MemoryReviewQueue(tmp_path).add_candidate("project decision needs review")
    before = inspect_workspace("terminal", workspace_root=tmp_path)
    output = handle_slash_command("/memory-review", workspace_root=tmp_path)
    summary = handle_slash_command("/memory-review --summary", workspace_root=tmp_path)
    after = inspect_workspace("terminal", workspace_root=tmp_path)
    assert "Memory review queue:" in output
    assert "Memory review summary:" in summary
    assert after["semantic_memory"]["semantic_writes_enabled"] is False
    assert after["semantic_memory"]["candidate_count"] == 1
    assert after["semantic_memory"]["memory_governance_mode"] == "review_queue_only_no_semantic_writes"
    assert before["semantic_memory"]["candidate_count"] == after["semantic_memory"]["candidate_count"]
