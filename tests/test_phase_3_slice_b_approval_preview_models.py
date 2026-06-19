from __future__ import annotations

import json

import pytest

from raiker.review.approval_preview import approval_preview_from_lifecycle_record
from raiker.review.models import (
    APPROVAL_PREVIEW_STATUSES,
    PROPOSAL_ACTION_TYPES,
    ProposalApprovalPreview,
    ProposalLifecycleRecord,
    ReviewModelError,
)


def _lifecycle_record(
    proposal_id: str = "rap_abcdef0123456789",
    finding_id: str = "missing-tests",
    action_type: str = "test_addition_proposal",
    risk_level: str = "medium",
    status: str = "proposed",
    requires_approval: bool = True,
    would_modify_files: bool = True,
    files: list[str] | None = None,
) -> ProposalLifecycleRecord:
    return ProposalLifecycleRecord(
        proposal_id=proposal_id,
        review_id="rev_123",
        finding_id=finding_id,
        title="Test proposal",
        action_type=action_type,
        risk_level=risk_level,
        requires_approval=requires_approval,
        would_modify_files=would_modify_files,
        status=status,
        files=files or ["raiker/example.py"],
        summary="Test summary",
        created_at="2026-06-19T00:00:00Z",
        updated_at="2026-06-19T00:00:00Z",
        source="review_propose_fixes_save",
    )


def test_preview_created_from_lifecycle_record() -> None:
    record = _lifecycle_record()
    preview = approval_preview_from_lifecycle_record(
        record, created_at="2026-06-19T00:00:00Z"
    )
    assert preview.preview_id.startswith("apv_")
    assert preview.proposal_id == "rap_abcdef0123456789"
    assert preview.review_id == "rev_123"
    assert preview.finding_id == "missing-tests"
    assert preview.action_type == "test_addition_proposal"
    assert preview.risk_level == "medium"
    assert preview.requires_approval is True
    assert preview.would_modify_files is True
    assert preview.files == ["raiker/example.py"]
    assert preview.status == "preview_created"
    assert preview.created_at == "2026-06-19T00:00:00Z"
    assert preview.source == "proposal_approval_preview"


def test_preview_id_apv_prefix() -> None:
    record = _lifecycle_record(proposal_id="rap_aaaa000000000001")
    preview = approval_preview_from_lifecycle_record(record)
    assert preview.preview_id == "apv_aaaa000000000001"
    assert preview.preview_id.startswith("apv_")


def test_proposal_id_keeps_rap_prefix() -> None:
    record = _lifecycle_record(proposal_id="rap_bbbb000000000002")
    preview = approval_preview_from_lifecycle_record(record)
    assert preview.proposal_id.startswith("rap_")


@pytest.mark.parametrize("status", sorted(APPROVAL_PREVIEW_STATUSES))
def test_allowed_preview_statuses_accepted(status: str) -> None:
    preview = ProposalApprovalPreview(
        preview_id="apv_0000000000000001",
        proposal_id="rap_0000000000000001",
        review_id="rev_1",
        finding_id="finding_1",
        proposal_status="proposed",
        action_type="no_action_required",
        risk_level="low",
        requires_approval=False,
        would_modify_files=False,
        files=[],
        required_human_decision="Confirm no action required.",
        required_safety_checks=[],
        blocking_conditions=[],
        recommended_next_action="No action needed.",
        status=status,
        created_at="2026-06-19T00:00:00Z",
        source="test",
    )
    assert preview.status == status


def test_execution_approval_statuses_rejected() -> None:
    for bad in ("approved", "approved_for_execution", "ready_to_apply", "execute", "executed", "applied", "merged", "ready_to_execute"):
        with pytest.raises(ReviewModelError):
            ProposalApprovalPreview(
                preview_id="apv_0000000000000001",
                proposal_id="rap_0000000000000001",
                review_id="rev_1",
                finding_id="finding_1",
                proposal_status="proposed",
                action_type="no_action_required",
                risk_level="low",
                requires_approval=False,
                would_modify_files=False,
                files=[],
                required_human_decision="Confirm no action required.",
                required_safety_checks=[],
                blocking_conditions=[],
                recommended_next_action="No action needed.",
                status=bad,
                created_at="2026-06-19T00:00:00Z",
                source="test",
            )


def test_human_decision_is_deterministic_per_action_type() -> None:
    for action_type in PROPOSAL_ACTION_TYPES:
        record = _lifecycle_record(action_type=action_type)
        preview = approval_preview_from_lifecycle_record(record)
        assert preview.required_human_decision
        assert len(preview.required_human_decision) > 10


def test_safety_checks_include_disabled_runtime_check() -> None:
    record = _lifecycle_record()
    preview = approval_preview_from_lifecycle_record(record)
    checks = "\n".join(preview.required_safety_checks)
    assert "Confirm no disabled runtime flag would be enabled." in checks
    assert "Confirm any future change would require a separate approved implementation step." in checks


def test_safety_checks_include_would_modify_files_checks() -> None:
    record = _lifecycle_record(would_modify_files=True)
    preview = approval_preview_from_lifecycle_record(record)
    checks = "\n".join(preview.required_safety_checks)
    assert "Identify exact files before any future patch planning." in checks


def test_blocking_conditions_for_rejected() -> None:
    record = _lifecycle_record(status="rejected")
    preview = approval_preview_from_lifecycle_record(record)
    assert any("rejected" in c.lower() for c in preview.blocking_conditions)


def test_blocking_conditions_for_superseded() -> None:
    record = _lifecycle_record(status="superseded")
    preview = approval_preview_from_lifecycle_record(record)
    assert any("superseded" in c.lower() for c in preview.blocking_conditions)


def test_high_risk_proposed_becomes_needs_human_review() -> None:
    record = _lifecycle_record(action_type="secret_removal_proposal", risk_level="high", status="proposed")
    preview = approval_preview_from_lifecycle_record(record)
    assert preview.status == "needs_human_review"


def test_rejected_becomes_blocked() -> None:
    record = _lifecycle_record(status="rejected")
    preview = approval_preview_from_lifecycle_record(record)
    assert preview.status == "blocked"


def test_superseded_becomes_blocked() -> None:
    record = _lifecycle_record(status="superseded")
    preview = approval_preview_from_lifecycle_record(record)
    assert preview.status == "blocked"


def test_preview_dict_no_raw_content() -> None:
    record = _lifecycle_record()
    preview = approval_preview_from_lifecycle_record(record)
    payload = preview.to_dict()
    forbidden = ("diff", "diff_text", "file_contents", "content", "patch", "raw", "secret", "reasoning", "chain_of_thought")
    for key in payload:
        for term in forbidden:
            assert term not in key
    blob = json.dumps(payload)
    for term in ("diff --git", "patch body", "raw tool output", "chain-of-thought"):
        assert term not in blob


def test_ready_for_planning_does_not_imply_execution() -> None:
    record = _lifecycle_record(action_type="no_action_required", risk_level="low")
    preview = approval_preview_from_lifecycle_record(record)
    assert preview.status == "ready_for_planning"
    assert "approval" not in preview.recommended_next_action.lower() or "planning" in preview.recommended_next_action.lower()


def test_invalid_preview_id_prefix_rejected() -> None:
    with pytest.raises(ReviewModelError):
        ProposalApprovalPreview(
            preview_id="bad_prefix",
            proposal_id="rap_0000000000000001",
            review_id="rev_1",
            finding_id="finding_1",
            proposal_status="proposed",
            action_type="no_action_required",
            risk_level="low",
            requires_approval=False,
            would_modify_files=False,
            files=[],
            required_human_decision="Confirm no action required.",
            required_safety_checks=[],
            blocking_conditions=[],
            recommended_next_action="No action needed.",
            status="preview_created",
            created_at="2026-06-19T00:00:00Z",
            source="test",
        )


def test_invalid_proposal_id_prefix_rejected() -> None:
    with pytest.raises(ReviewModelError):
        ProposalApprovalPreview(
            preview_id="apv_0000000000000001",
            proposal_id="bad_prefix",
            review_id="rev_1",
            finding_id="finding_1",
            proposal_status="proposed",
            action_type="no_action_required",
            risk_level="low",
            requires_approval=False,
            would_modify_files=False,
            files=[],
            required_human_decision="Confirm no action required.",
            required_safety_checks=[],
            blocking_conditions=[],
            recommended_next_action="No action needed.",
            status="preview_created",
            created_at="2026-06-19T00:00:00Z",
            source="test",
        )


def test_required_human_decision_for_secret_removal() -> None:
    record = _lifecycle_record(action_type="secret_removal_proposal")
    preview = approval_preview_from_lifecycle_record(record)
    assert "secret" in preview.required_human_decision.lower()
    assert "rotate" in preview.required_human_decision.lower()


def test_required_human_decision_for_no_action_required() -> None:
    record = _lifecycle_record(action_type="no_action_required")
    preview = approval_preview_from_lifecycle_record(record)
    assert "no implementation action" in preview.required_human_decision.lower()


def test_blocking_conditions_for_high_risk_proposed() -> None:
    record = _lifecycle_record(action_type="secret_removal_proposal", risk_level="high", status="proposed")
    preview = approval_preview_from_lifecycle_record(record)
    assert any("high-risk" in c.lower() for c in preview.blocking_conditions)


def test_safety_check_for_high_risk() -> None:
    record = _lifecycle_record(action_type="secret_removal_proposal", risk_level="high")
    preview = approval_preview_from_lifecycle_record(record)
    checks = "\n".join(preview.required_safety_checks)
    assert "Require explicit human review" in checks


def test_safety_check_for_secrets() -> None:
    record = _lifecycle_record(action_type="secret_removal_proposal")
    preview = approval_preview_from_lifecycle_record(record)
    checks = "\n".join(preview.required_safety_checks)
    assert "credential rotation" in checks


def test_safety_check_for_scope_runtime() -> None:
    for action_type in ("scope_reduction_proposal", "runtime_safety_refactor_proposal"):
        record = _lifecycle_record(action_type=action_type)
        preview = approval_preview_from_lifecycle_record(record)
        checks = "\n".join(preview.required_safety_checks)
        assert "shell/process/network/plugin/graph/semantic" in checks
