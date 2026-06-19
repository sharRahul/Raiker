from __future__ import annotations

import hashlib

from raiker.review.models import ReviewActionProposal, ReviewFinding

# Deterministic proposal-only action generation from review findings.
#
# This module is proposal-only. It never applies fixes, mutates files, runs tests,
# stages/unstages the Git index, commits, or executes shell/process/network calls.
# It does not import subprocess/socket/requests/httpx/urllib/asyncio.

_PROPOSAL_SAFETY_NOTES = (
    "Proposal only.",
    "No files were modified.",
    "No shell/network/process execution was used.",
)

# Static proposal templates keyed by finding id. Each template is a safe, public
# description with no raw diff, file content, secret, or private reasoning.
_PROPOSAL_TEMPLATES: dict[str, dict[str, object]] = {
    "missing-tests": {
        "title": "Add or update focused tests for changed source behavior",
        "action_type": "test_addition_proposal",
        "risk_level": "medium",
        "requires_approval": True,
        "would_modify_files": True,
        "summary": (
            "Add or update focused tests for the source behavior changed in this review scope."
        ),
        "rationale": (
            "Source files changed without matching test changes; tests should cover the new behavior."
        ),
    },
    "secret-introduced": {
        "title": "Remove secret-like material from the change",
        "action_type": "secret_removal_proposal",
        "risk_level": "high",
        "requires_approval": True,
        "would_modify_files": True,
        "summary": (
            "Remove the secret-like addition from the diff and rotate the exposed credential "
            "outside Raiker."
        ),
        "rationale": (
            "A secret-like value was detected in the change; it must be removed and rotated."
        ),
    },
    "scope-expansion": {
        "title": "Keep deferred runtime capability disabled",
        "action_type": "scope_reduction_proposal",
        "risk_level": "high",
        "requires_approval": True,
        "would_modify_files": True,
        "summary": (
            "Remove or revert Phase 3/4 runtime activation claims or enabled flags from this change."
        ),
        "rationale": (
            "The change appears to enable a deferred runtime capability; keep it disabled."
        ),
    },
    "unsafe-runtime": {
        "title": "Replace unsafe runtime activation with policy-gated design",
        "action_type": "runtime_safety_refactor_proposal",
        "risk_level": "high",
        "requires_approval": True,
        "would_modify_files": True,
        "summary": (
            "Remove direct shell/process/network/background activation and route any future "
            "capability through explicit policy-gated design."
        ),
        "rationale": (
            "Direct runtime activation was detected; route it through brokered, policy-gated wrappers."
        ),
    },
    "docs-only": {
        "title": "No code action required for documentation-only change",
        "action_type": "no_action_required",
        "risk_level": "low",
        "requires_approval": False,
        "would_modify_files": False,
        "summary": "Documentation-only change detected; no code fix is proposed.",
        "rationale": "All changed files are documentation; no code behavior is affected.",
    },
    "test-only": {
        "title": "Verify tests match intended behavior",
        "action_type": "no_action_required",
        "risk_level": "low",
        "requires_approval": False,
        "would_modify_files": False,
        "summary": "Test-only change detected; confirm it targets the intended behavior.",
        "rationale": "Only test files changed; confirm coverage of intended behavior.",
    },
    "review-truncated": {
        "title": "Narrow review scope or increase bounds",
        "action_type": "review_scope_adjustment_proposal",
        "risk_level": "low",
        "requires_approval": False,
        "would_modify_files": False,
        "summary": (
            "Review context was truncated; run a narrower path review or raise bounds before "
            "relying on the result."
        ),
        "rationale": "The diff or file set exceeded review bounds and was truncated.",
    },
    "untracked-files": {
        "title": "Stage or track files before content review",
        "action_type": "review_scope_adjustment_proposal",
        "risk_level": "low",
        "requires_approval": False,
        "would_modify_files": False,
        "summary": (
            "Untracked files were detected metadata-only; stage or track them before content review."
        ),
        "rationale": "Untracked files are not included in normal git diff review.",
    },
}


def _proposal_id(finding_id: str, action_type: str) -> str:
    digest = hashlib.sha1(f"{finding_id}:{action_type}".encode()).hexdigest()[:16]
    return f"rap_{digest}"


def _proposal_files(finding: ReviewFinding) -> list[str]:
    if finding.file_path is None:
        return []
    return [finding.file_path]


def _build_proposal(finding: ReviewFinding, template: dict[str, object]) -> ReviewActionProposal:
    action_type = str(template["action_type"])
    return ReviewActionProposal(
        proposal_id=_proposal_id(finding.finding_id, action_type),
        finding_id=finding.finding_id,
        title=str(template["title"]),
        action_type=action_type,
        risk_level=str(template["risk_level"]),
        requires_approval=bool(template["requires_approval"]),
        would_modify_files=bool(template["would_modify_files"]),
        files=_proposal_files(finding),
        summary=str(template["summary"]),
        rationale=str(template["rationale"]),
        safety_notes=list(_PROPOSAL_SAFETY_NOTES),
    )


def generate_action_proposals(findings: list[ReviewFinding]) -> list[ReviewActionProposal]:
    """Produce deterministic, proposal-only action proposals from review findings.

    Returns one proposal per known finding id, in finding order. Unknown finding ids
    produce no proposal. No proposal contains raw diff, raw file contents, secrets,
    or private reasoning. This function never mutates files or executes anything.
    """

    proposals: list[ReviewActionProposal] = []
    for finding in findings:
        template = _PROPOSAL_TEMPLATES.get(finding.finding_id)
        if template is None:
            continue
        proposals.append(_build_proposal(finding, template))
    return proposals


def proposal_risk_counts(proposals: list[ReviewActionProposal]) -> dict[str, int]:
    counts = {"low": 0, "medium": 0, "high": 0}
    for proposal in proposals:
        counts[proposal.risk_level] = counts.get(proposal.risk_level, 0) + 1
    return counts


__all__ = [
    "generate_action_proposals",
    "proposal_risk_counts",
]
