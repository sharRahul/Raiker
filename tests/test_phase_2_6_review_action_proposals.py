from __future__ import annotations

from raiker.review.models import ReviewFinding
from raiker.review.proposals import (
    generate_action_proposals,
    proposal_risk_counts,
)


def _finding(finding_id: str, severity: str = "medium", file_path: str | None = None) -> ReviewFinding:
    return ReviewFinding(
        finding_id=finding_id,
        severity=severity,
        category="tests",
        title="title",
        description="desc",
        evidence="evidence",
        recommendation="rec",
        confidence="medium",
        file_path=file_path,
    )


def test_missing_tests_finding_creates_test_addition_proposal() -> None:
    proposals = generate_action_proposals([_finding("missing-tests")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "test_addition_proposal"
    assert p.risk_level == "medium"
    assert p.requires_approval is True
    assert p.would_modify_files is True
    assert p.finding_id == "missing-tests"


def test_secret_finding_creates_secret_removal_proposal_and_no_raw_secret() -> None:
    proposals = generate_action_proposals([_finding("secret-introduced", severity="high")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "secret_removal_proposal"
    assert p.risk_level == "high"
    assert p.requires_approval is True
    assert p.would_modify_files is True
    blob = p.summary + p.rationale + p.title + " ".join(p.safety_notes)
    assert "hunter2" not in blob
    assert "password" not in blob.lower()


def test_scope_expansion_finding_creates_scope_reduction_proposal() -> None:
    proposals = generate_action_proposals([_finding("scope-expansion", severity="high")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "scope_reduction_proposal"
    assert p.risk_level == "high"
    assert p.requires_approval is True
    assert p.would_modify_files is True


def test_unsafe_runtime_finding_creates_runtime_safety_proposal() -> None:
    proposals = generate_action_proposals([_finding("unsafe-runtime", severity="high")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "runtime_safety_refactor_proposal"
    assert p.risk_level == "high"
    assert p.requires_approval is True
    assert p.would_modify_files is True


def test_docs_only_finding_creates_no_action_proposal() -> None:
    proposals = generate_action_proposals([_finding("docs-only", severity="info")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "no_action_required"
    assert p.risk_level == "low"
    assert p.requires_approval is False
    assert p.would_modify_files is False


def test_test_only_finding_creates_no_action_proposal() -> None:
    proposals = generate_action_proposals([_finding("test-only", severity="info")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "no_action_required"
    assert p.requires_approval is False
    assert p.would_modify_files is False


def test_truncated_finding_creates_review_scope_proposal() -> None:
    proposals = generate_action_proposals([_finding("review-truncated", severity="info")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "review_scope_adjustment_proposal"
    assert p.risk_level == "low"
    assert p.requires_approval is False
    assert p.would_modify_files is False


def test_untracked_files_finding_creates_review_scope_proposal() -> None:
    proposals = generate_action_proposals([_finding("untracked-files", severity="info")])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action_type == "review_scope_adjustment_proposal"
    assert p.requires_approval is False
    assert p.would_modify_files is False


def test_unknown_finding_creates_no_proposal() -> None:
    proposals = generate_action_proposals([_finding("not-a-known-finding")])
    assert proposals == []


def test_proposal_ids_are_stable_and_prefixed() -> None:
    proposals_a = generate_action_proposals([_finding("missing-tests")])
    proposals_b = generate_action_proposals([_finding("missing-tests")])
    assert proposals_a[0].proposal_id == proposals_b[0].proposal_id
    assert proposals_a[0].proposal_id.startswith("rap_")


def test_proposal_files_reflect_finding_path() -> None:
    proposals = generate_action_proposals(
        [_finding("missing-tests", file_path="raiker/example.py")]
    )
    assert proposals[0].files == ["raiker/example.py"]
    proposals_none = generate_action_proposals([_finding("missing-tests")])
    assert proposals_none[0].files == []


def test_proposal_risk_counts() -> None:
    proposals = generate_action_proposals(
        [
            _finding("missing-tests", severity="medium"),
            _finding("secret-introduced", severity="high"),
            _finding("docs-only", severity="info"),
        ]
    )
    counts = proposal_risk_counts(proposals)
    assert counts == {"low": 1, "medium": 1, "high": 1}


def test_proposal_order_follows_finding_order() -> None:
    findings = [
        _finding("secret-introduced", severity="high"),
        _finding("missing-tests", severity="medium"),
        _finding("docs-only", severity="info"),
    ]
    proposals = generate_action_proposals(findings)
    assert [p.finding_id for p in proposals] == [
        "secret-introduced",
        "missing-tests",
        "docs-only",
    ]


def test_proposals_carry_safety_notes() -> None:
    proposals = generate_action_proposals([_finding("missing-tests")])
    notes = proposals[0].safety_notes
    assert "Proposal only." in notes
    assert "No files were modified." in notes
    assert "No shell/network/process execution was used." in notes


def test_proposal_does_not_claim_fix_applied() -> None:
    findings = [
        _finding("missing-tests"),
        _finding("secret-introduced", severity="high"),
        _finding("docs-only", severity="info"),
    ]
    proposals = generate_action_proposals(findings)
    for p in proposals:
        blob = (p.title + p.summary + p.rationale).lower()
        assert "applied" not in blob
        assert "fixed" not in blob
        assert "has been fixed" not in blob
