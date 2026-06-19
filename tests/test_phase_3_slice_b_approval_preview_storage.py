from __future__ import annotations

from pathlib import Path

import pytest

from raiker.review.approval_preview import (
    ProposalApprovalPreviewStore,
    approval_preview_from_lifecycle_record,
)
from raiker.review.models import (
    ProposalLifecycleRecord,
)
from raiker.storage.sqlite import SQLiteStore


def _lifecycle_record(
    proposal_id: str = "rap_aaaa000000000001",
    action_type: str = "test_addition_proposal",
    risk_level: str = "medium",
    status: str = "proposed",
) -> ProposalLifecycleRecord:
    return ProposalLifecycleRecord(
        proposal_id=proposal_id,
        review_id="rev_1",
        finding_id="missing-tests",
        title="Test proposal",
        action_type=action_type,
        risk_level=risk_level,
        requires_approval=True,
        would_modify_files=True,
        status=status,
        files=["raiker/example.py"],
        summary="Test summary",
        created_at="2026-06-19T00:00:00Z",
        updated_at="2026-06-19T00:00:00Z",
        source="review_propose_fixes_save",
    )


def _store(tmp_path: Path) -> ProposalApprovalPreviewStore:
    return ProposalApprovalPreviewStore(SQLiteStore(tmp_path))


def test_preview_persists_in_sqlite(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _lifecycle_record()
    preview = approval_preview_from_lifecycle_record(record, created_at="2026-06-19T00:00:00Z")
    stored = store.save_preview(preview)
    assert stored.preview_id == preview.preview_id


def test_preview_loads_by_id(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _lifecycle_record()
    preview = approval_preview_from_lifecycle_record(record, created_at="2026-06-19T00:00:00Z")
    store.save_preview(preview)
    loaded = store.get_preview(preview.preview_id)
    assert loaded is not None
    assert loaded.proposal_id == record.proposal_id
    assert loaded.action_type == record.action_type


def test_list_previews_newest_first(tmp_path: Path) -> None:
    store = _store(tmp_path)
    rec1 = _lifecycle_record(proposal_id="rap_aaaa000000000001")
    rec2 = _lifecycle_record(proposal_id="rap_bbbb000000000002")
    p1 = approval_preview_from_lifecycle_record(rec1, created_at="2026-06-19T00:00:00Z")
    p2 = approval_preview_from_lifecycle_record(rec2, created_at="2026-06-19T01:00:00Z")
    store.save_preview(p1)
    store.save_preview(p2)
    previews = store.list_previews()
    assert [p.preview_id for p in previews] == ["apv_bbbb000000000002", "apv_aaaa000000000001"]


def test_list_previews_status_filter(tmp_path: Path) -> None:
    store = _store(tmp_path)
    rec_noop = _lifecycle_record(proposal_id="rap_aaaa000000000001", action_type="no_action_required", risk_level="low")
    rec_high = _lifecycle_record(proposal_id="rap_bbbb000000000002", action_type="secret_removal_proposal", risk_level="high")
    store.save_preview(approval_preview_from_lifecycle_record(rec_noop, created_at="2026-06-19T00:00:00Z"))
    store.save_preview(approval_preview_from_lifecycle_record(rec_high, created_at="2026-06-19T00:00:00Z"))
    previews = store.list_previews(status="ready_for_planning")
    assert len(previews) == 1
    assert previews[0].proposal_id == "rap_aaaa000000000001"


def test_list_previews_limit(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for n in range(5):
        rec = _lifecycle_record(proposal_id=f"rap_aaaa00000000000{n}")
        store.save_preview(approval_preview_from_lifecycle_record(rec, created_at=f"2026-06-19T00:0{n}:00Z"))
    assert len(store.list_previews(limit=2)) == 2


def test_create_from_record_persists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _lifecycle_record()
    preview = store.create_from_record(record)
    assert preview.preview_id == "apv_aaaa000000000001"
    loaded = store.get_preview(preview.preview_id)
    assert loaded is not None
    assert loaded.status == preview.status


def test_re_generating_same_proposal_is_deterministic(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _lifecycle_record()
    p1 = store.create_from_record(record)
    p2 = store.create_from_record(record)
    assert p1.preview_id == p2.preview_id
    assert p1.proposal_id == p2.proposal_id
    assert p1.review_id == p2.review_id


def test_stored_row_contains_metadata_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _lifecycle_record()
    store.create_from_record(record)
    with SQLiteStore(tmp_path).connect() as connection:
        row = dict(connection.execute(
            "SELECT * FROM proposal_approval_previews WHERE preview_id = ?",
            ("apv_aaaa000000000001",),
        ).fetchone())
    forbidden_fields = {"diff", "diff_text", "file_contents", "patch", "secret", "reasoning"}
    for field in row:
        assert field not in forbidden_fields


def test_no_raw_diff_file_content_fields_in_table(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _lifecycle_record()
    store.create_from_record(record)
    with SQLiteStore(tmp_path).connect() as connection:
        cols = [d[1] for d in connection.execute("PRAGMA table_info(proposal_approval_previews)").fetchall()]
    forbidden = {"diff", "diff_text", "file_contents", "content", "patch", "secret", "reasoning", "chain"}
    for col in cols:
        for term in forbidden:
            assert term not in col


def test_migration_creates_indexes(tmp_path: Path) -> None:
    s = SQLiteStore(tmp_path)
    with s.connect() as connection:
        indexes = [str(d["name"]) for d in connection.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
    assert "idx_approval_preview_proposal_id" in indexes
    assert "idx_approval_preview_status" in indexes
    assert "idx_approval_preview_created" in indexes


def test_existing_proposal_records_remain_intact(tmp_path: Path) -> None:
    from raiker.review.lifecycle import ProposalLifecycleStore
    from raiker.review.models import ReviewActionProposal

    lifecycle_store = ProposalLifecycleStore(SQLiteStore(tmp_path))
    proposal = ReviewActionProposal(
        proposal_id="rap_cccc000000000003",
        finding_id="missing-tests",
        title="Test",
        action_type="test_addition_proposal",
        risk_level="medium",
        requires_approval=True,
        would_modify_files=True,
        files=["test.py"],
        summary="Test",
        rationale="Test",
        safety_notes=["Safety note."],
    )
    lifecycle_store.save_proposals([proposal], review_id="rev_1")
    preview_store = _store(tmp_path)
    record = _lifecycle_record(proposal_id="rap_cccc000000000003")
    preview_store.create_from_record(record)
    loaded = lifecycle_store.get_record("rap_cccc000000000003")
    assert loaded is not None
    assert loaded.status == "proposed"


def test_invalid_status_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.list_previews(status="approved")


def test_get_preview_unknown_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_preview("apv_unknown0000000000") is None


def test_get_preview_invalid_prefix_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_preview("bad_prefix") is None


def test_files_json_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    files = ["a/b.py", "c/d.py"]
    record = ProposalLifecycleRecord(
        proposal_id="rap_dddd000000000004",
        review_id="rev_1",
        finding_id="missing-tests",
        title="Test",
        action_type="test_addition_proposal",
        risk_level="medium",
        requires_approval=True,
        would_modify_files=True,
        status="proposed",
        files=files,
        summary="Test",
        created_at="2026-06-19T00:00:00Z",
        updated_at="2026-06-19T00:00:00Z",
        source="test",
    )
    store.create_from_record(record)
    loaded = store.get_preview("apv_dddd000000000004")
    assert loaded is not None
    assert loaded.files == files
