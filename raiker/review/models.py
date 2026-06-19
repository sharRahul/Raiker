from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Allowed enumerations for deterministic, contract-safe review models.
REVIEW_MODES = frozenset({"unstaged", "staged", "path", "clean"})
SEVERITIES = ("info", "low", "medium", "high")
SEVERITY_SET = frozenset(SEVERITIES)
SEVERITY_RANK = {severity: rank for rank, severity in enumerate(SEVERITIES)}
CATEGORIES = frozenset(
    {
        "correctness",
        "security",
        "tests",
        "docs",
        "maintainability",
        "scope",
        "style",
        "performance",
    }
)
CONFIDENCES = frozenset({"low", "medium", "high"})

# Phase 2.6 review-to-action proposal enumerations. Proposals are safe, in-memory
# descriptions of what *could* be done; they never apply fixes or mutate files.
PROPOSAL_ACTION_TYPES = frozenset(
    {
        "manual_patch_proposal",
        "test_addition_proposal",
        "docs_update_proposal",
        "scope_reduction_proposal",
        "secret_removal_proposal",
        "runtime_safety_refactor_proposal",
        "review_scope_adjustment_proposal",
        "no_action_required",
    }
)
PROPOSAL_RISK_LEVELS = frozenset({"low", "medium", "high"})

# Phase 3 Slice A proposal lifecycle statuses. None of these imply execution
# approval; ``approved``/``approved_for_execution``/``ready_to_apply``/``execute``
# are deliberately excluded and must never be added.
PROPOSAL_LIFECYCLE_STATUSES = frozenset(
    {
        "proposed",
        "acknowledged",
        "deferred",
        "rejected",
        "superseded",
    }
)


class ReviewModelError(ValueError):
    """Raised when a review model is constructed with an invalid enumeration value."""


@dataclass(frozen=True)
class ReviewScope:
    mode: str
    workspace_root: str
    path_filter: str | None
    staged: bool
    max_files: int
    max_diff_chars: int

    def __post_init__(self) -> None:
        if self.mode not in REVIEW_MODES:
            raise ReviewModelError(f"invalid_review_mode:{self.mode}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "workspace_root": self.workspace_root,
            "path_filter": self.path_filter,
            "staged": self.staged,
            "max_files": self.max_files,
            "max_diff_chars": self.max_diff_chars,
        }


@dataclass(frozen=True)
class ReviewInput:
    """In-memory input bundle for the reviewer.

    ``diff_text`` is the already-redacted, bounded diff. It is never serialised into a
    :class:`ReviewResult` or any event payload; it exists only to feed deterministic rule
    evaluation during a single review call.
    """

    scope: ReviewScope
    files: list[str] = field(default_factory=list)
    diff_text: str = ""
    context_summary: str = ""
    source_types: list[str] = field(default_factory=list)
    truncated: bool = False
    redaction_applied: bool = False


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    severity: str
    category: str
    title: str
    description: str
    evidence: str
    recommendation: str
    confidence: str
    file_path: str | None = None
    line: int | None = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_SET:
            raise ReviewModelError(f"invalid_severity:{self.severity}")
        if self.category not in CATEGORIES:
            raise ReviewModelError(f"invalid_category:{self.category}")
        if self.confidence not in CONFIDENCES:
            raise ReviewModelError(f"invalid_confidence:{self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "category": self.category,
            "file_path": self.file_path,
            "line": self.line,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ReviewActionProposal:
    """A safe, in-memory proposed action derived from a review finding.

    Proposals are proposal-only. They never apply fixes, mutate files, run tests, or
    execute shell/process/network calls. ``would_modify_files`` describes what an
    approval-gated future action *would* do, not anything this proposal does.
    """

    proposal_id: str
    finding_id: str
    title: str
    action_type: str
    risk_level: str
    requires_approval: bool
    would_modify_files: bool
    files: list[str]
    summary: str
    rationale: str
    safety_notes: list[str]

    def __post_init__(self) -> None:
        if self.action_type not in PROPOSAL_ACTION_TYPES:
            raise ReviewModelError(f"invalid_action_type:{self.action_type}")
        if self.risk_level not in PROPOSAL_RISK_LEVELS:
            raise ReviewModelError(f"invalid_risk_level:{self.risk_level}")
        if self.would_modify_files and not self.requires_approval:
            raise ReviewModelError("would_modify_files requires requires_approval")
        if not self.proposal_id.startswith("rap_"):
            raise ReviewModelError("proposal_id must use rap_ prefix")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "finding_id": self.finding_id,
            "title": self.title,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "would_modify_files": self.would_modify_files,
            "files": list(self.files),
            "summary": self.summary,
            "rationale": self.rationale,
            "safety_notes": list(self.safety_notes),
        }


@dataclass(frozen=True)
class ProposalLifecycleRecord:
    """Metadata-only lifecycle record for a saved review action proposal.

    This is proposal-only and metadata-only. It never contains raw diff, raw file
    contents, secrets, prompt text, private reasoning, chain-of-thought, raw tool
    output, or patch content. It never executes, applies, mutates files, or stages
    changes. Status is a planning label only; no status implies execution approval.
    """

    proposal_id: str
    review_id: str
    finding_id: str
    title: str
    action_type: str
    risk_level: str
    requires_approval: bool
    would_modify_files: bool
    status: str
    files: list[str]
    summary: str
    created_at: str
    updated_at: str
    source: str

    def __post_init__(self) -> None:
        if self.action_type not in PROPOSAL_ACTION_TYPES:
            raise ReviewModelError(f"invalid_action_type:{self.action_type}")
        if self.risk_level not in PROPOSAL_RISK_LEVELS:
            raise ReviewModelError(f"invalid_risk_level:{self.risk_level}")
        if self.status not in PROPOSAL_LIFECYCLE_STATUSES:
            raise ReviewModelError(f"invalid_lifecycle_status:{self.status}")
        if self.would_modify_files and not self.requires_approval:
            raise ReviewModelError("would_modify_files requires requires_approval")
        if not self.proposal_id.startswith("rap_"):
            raise ReviewModelError("proposal_id must use rap_ prefix")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "review_id": self.review_id,
            "finding_id": self.finding_id,
            "title": self.title,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "would_modify_files": self.would_modify_files,
            "status": self.status,
            "files": list(self.files),
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
        }


@dataclass(frozen=True)
class ReviewSummary:
    files_reviewed: int
    findings_count: int
    severity_counts: dict[str, int]
    categories: dict[str, int]
    truncated: bool
    redaction_applied: bool
    proposal_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_reviewed": self.files_reviewed,
            "findings_count": self.findings_count,
            "severity_counts": dict(self.severity_counts),
            "categories": dict(self.categories),
            "truncated": self.truncated,
            "redaction_applied": self.redaction_applied,
            "proposal_count": self.proposal_count,
        }


@dataclass(frozen=True)
class ReviewResult:
    review_id: str
    scope: ReviewScope
    summary: ReviewSummary
    findings: list[ReviewFinding] = field(default_factory=list)
    action_proposals: list[ReviewActionProposal] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    event_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "scope": self.scope.to_dict(),
            "summary": self.summary.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "action_proposals": [proposal.to_dict() for proposal in self.action_proposals],
            "safety_notes": list(self.safety_notes),
            "event_metadata": dict(self.event_metadata),
        }
