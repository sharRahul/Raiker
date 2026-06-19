from __future__ import annotations

import json

import pytest

from raiker.review.lifecycle import record_from_proposal
from raiker.review.models import (
    PROPOSAL_LIFECYCLE_STATUSES,
    PROPOSAL_RISK_LEVELS,
    ProposalLifecycleRecord,
    ReviewActionProposal,
)


def _proposal(finding_id: str = "missing-tests") -> ReviewActionProposal:
    return ReviewActionProposal(
        proposal_id="rap_abcdef0123456789",
        finding_id=finding_id,
        title="Add or update focused tests for changed source behavior",
        action_type="test_addition_proposal",
        risk_level="medium",
        requires_approval=True,
        would_modify_files=True,
        files=["raiker/example.py"],
        summary="Add or update focused tests for the changed behavior.",
        rationale="Source changed without tests.",
        safety_notes=["Proposal only.", "No files were modified."],
    )


def test_record_from_proposal_default_status_is_proposed() -> None:
    record = record_from_proposal(_proposal(), review_id="rev_123")
    assert record.status == "proposed"
    assert record.proposal_id == "rap_abcdef0123456789"
    assert record.review_id == "rev_123"
    assert record.finding_id == "missing-tests"
    assert record.action_type == "test_addition_proposal"
    assert record.risk_level == "medium"
    assert record.requires_approval is True
    assert record.would_modify_files is True
    assert record.files == ["raiker/example.py"]
    assert record.source == "review_propose_fixes_save"


def test_record_keeps_rap_prefix() -> None:
    record = record_from_proposal(_proposal(), review_id="rev_1")
    assert record.proposal_id.startswith("rap_")


@pytest.mark.parametrize("status", sorted(PROPOSAL_LIFECYCLE_STATUSES))
def test_allowed_statuses_accepted(status: str) -> None:
    proposal = _proposal()
    record = ProposalLifecycleRecord(
        proposal_id=proposal.proposal_id,
        review_id="rev_1",
        finding_id=proposal.finding_id,
        title=proposal.title,
        action_type=proposal.action_type,
        risk_level=proposal.risk_level,
        requires_approval=proposal.requires_approval,
        would_modify_files=proposal.would_modify_files,
        status=status,
        files=proposal.files,
        summary=proposal.summary,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        source="review_propose_fixes_save",
    )
    assert record.status == status


def test_invalid_status_rejected() -> None:
    proposal = _proposal()
    with pytest.raises(ValueError):
        ProposalLifecycleRecord(
            proposal_id=proposal.proposal_id,
            review_id="rev_1",
            finding_id=proposal.finding_id,
            title=proposal.title,
            action_type=proposal.action_type,
            risk_level=proposal.risk_level,
            requires_approval=proposal.requires_approval,
            would_modify_files=proposal.would_modify_files,
            status="approved",
            files=proposal.files,
            summary=proposal.summary,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            source="review_propose_fixes_save",
        )


def test_execution_status_rejected() -> None:
    proposal = _proposal()
    for bad in ("approved_for_execution", "ready_to_apply", "execute"):
        with pytest.raises(ValueError):
            ProposalLifecycleRecord(
                proposal_id=proposal.proposal_id,
                review_id="rev_1",
                finding_id=proposal.finding_id,
                title=proposal.title,
                action_type=proposal.action_type,
                risk_level=proposal.risk_level,
                requires_approval=proposal.requires_approval,
                would_modify_files=proposal.would_modify_files,
                status=bad,
                files=proposal.files,
                summary=proposal.summary,
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                source="review_propose_fixes_save",
            )


def test_invalid_proposal_id_prefix_rejected() -> None:
    with pytest.raises(ValueError):
        ProposalLifecycleRecord(
            proposal_id="bad_prefix",
            review_id="rev_1",
            finding_id="missing-tests",
            title="t",
            action_type="test_addition_proposal",
            risk_level="medium",
            requires_approval=True,
            would_modify_files=True,
            status="proposed",
            files=[],
            summary="s",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            source="review_propose_fixes_save",
        )


def test_record_serializes_to_json_safe_dict() -> None:
    record = record_from_proposal(_proposal(), review_id="rev_1")
    payload = record.to_dict()
    serialised = json.dumps(payload, sort_keys=True)
    assert payload["proposal_id"] == "rap_abcdef0123456789"
    assert json.loads(serialised) == payload


def test_record_has_no_raw_diff_or_content_fields() -> None:
    record = record_from_proposal(_proposal(), review_id="rev_1")
    payload = record.to_dict()
    for forbidden in ("diff", "diff_text", "file_contents", "content", "patch", "raw", "secret"):
        assert forbidden not in payload
    blob = json.dumps(payload).lower()
    for forbidden in ("diff --git", "patch body", "raw tool output", "chain-of-thought"):
        assert forbidden not in blob


def test_record_risk_levels_match_proposal_enum() -> None:
    assert {"low", "medium", "high"} == PROPOSAL_RISK_LEVELS


def test_lifecycle_statuses_match_allowed_set() -> None:
    assert {
        "proposed",
        "acknowledged",
        "deferred",
        "rejected",
        "superseded",
    } == PROPOSAL_LIFECYCLE_STATUSES
