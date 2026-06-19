from __future__ import annotations

from pathlib import Path

import pytest

from raiker.review.lifecycle import (
    ProposalLifecycleError,
    ProposalLifecycleStore,
    record_from_proposal,
)
from raiker.review.models import ReviewActionProposal
from raiker.storage.sqlite import SQLiteStore


def _proposal(proposal_id: str = "rap_aaaa000000000001") -> ReviewActionProposal:
    return ReviewActionProposal(
        proposal_id=proposal_id,
        finding_id="missing-tests",
        title="Add or update focused tests",
        action_type="test_addition_proposal",
        risk_level="medium",
        requires_approval=True,
        would_modify_files=True,
        files=["raiker/example.py"],
        summary="Add tests.",
        rationale="Source changed without tests.",
        safety_notes=["Proposal only.", "No files were modified."],
    )


def _store(tmp_path: Path) -> ProposalLifecycleStore:
    return ProposalLifecycleStore(SQLiteStore(tmp_path))


def test_save_proposals_persists_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    saved = store.save_proposals([_proposal()], review_id="rev_1")
    assert len(saved) == 1
    assert saved[0].status == "proposed"
    loaded = store.get_record("rap_aaaa000000000001")
    assert loaded is not None
    assert loaded.finding_id == "missing-tests"
    assert loaded.action_type == "test_addition_proposal"


def test_save_empty_proposals_creates_no_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    saved = store.save_proposals([], review_id="rev_1")
    assert saved == []
    assert store.list_records() == []


def test_save_proposals_preserves_existing_status(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    store.mark_status("rap_aaaa000000000001", new_status="deferred")
    store.save_proposals([_proposal()], review_id="rev_2")
    loaded = store.get_record("rap_aaaa000000000001")
    assert loaded is not None
    assert loaded.status == "deferred"
    assert loaded.review_id == "rev_2"


def test_list_records_newest_first(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_proposals(
        [_proposal("rap_aaaa000000000001")], review_id="rev_1"
    )
    store.save_proposals(
        [_proposal("rap_bbbb000000000002")], review_id="rev_2"
    )
    records = store.list_records()
    assert [r.proposal_id for r in records] == [
        "rap_bbbb000000000002",
        "rap_aaaa000000000001",
    ]


def test_list_records_status_filter(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_proposals(
        [_proposal("rap_aaaa000000000001")], review_id="rev_1"
    )
    store.save_proposals(
        [_proposal("rap_bbbb000000000002")], review_id="rev_2"
    )
    store.mark_status("rap_aaaa000000000001", new_status="deferred")
    records = store.list_records(status="deferred")
    assert len(records) == 1
    assert records[0].proposal_id == "rap_aaaa000000000001"


def test_list_records_limit(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for n in range(5):
        store.save_proposals(
            [_proposal(f"rap_aaaa00000000000{n}")], review_id=f"rev_{n}"
        )
    assert len(store.list_records(limit=2)) == 2


def test_list_records_invalid_status_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ProposalLifecycleError):
        store.list_records(status="approved")


def test_mark_status_updates_metadata_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    before = store.get_record("rap_aaaa000000000001")
    assert before is not None
    original_created = before.created_at
    updated = store.mark_status("rap_aaaa000000000001", new_status="acknowledged")
    assert updated.status == "acknowledged"
    assert updated.created_at == original_created
    assert updated.updated_at >= before.updated_at


def test_mark_status_unknown_proposal_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ProposalLifecycleError):
        store.mark_status("rap_unknown0000000000", new_status="deferred")


def test_mark_status_invalid_status_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    with pytest.raises(ProposalLifecycleError):
        store.mark_status("rap_aaaa000000000001", new_status="approved")


def test_get_record_returns_none_for_unknown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_record("rap_unknown0000000000") is None


def test_record_from_proposal_carries_files(tmp_path: Path) -> None:
    proposal = _proposal()
    proposal = ReviewActionProposal(
        proposal_id=proposal.proposal_id,
        finding_id=proposal.finding_id,
        title=proposal.title,
        action_type=proposal.action_type,
        risk_level=proposal.risk_level,
        requires_approval=proposal.requires_approval,
        would_modify_files=proposal.would_modify_files,
        files=["a/b.py", "c/d.py"],
        summary=proposal.summary,
        rationale=proposal.rationale,
        safety_notes=proposal.safety_notes,
    )
    record = record_from_proposal(proposal, review_id="rev_1")
    assert record.files == ["a/b.py", "c/d.py"]
