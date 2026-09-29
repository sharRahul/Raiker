from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.contracts.views import View

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

# Phase 3 Slice B approval planning preview statuses. These are preview/planning
# labels only and never imply execution approval.
APPROVAL_PREVIEW_STATUSES = frozenset(
    {
        "preview_created",
        "needs_human_review",
        "blocked",
        "ready_for_planning",
        "superseded",
    }
)


class ReviewModelError(ValueError):
    """Raised when a review model is constructed with an invalid enumeration value."""


@dataclass(frozen=True)
class ReviewScope(View):
    mode: str
    workspace_root: str
    path_filter: str | None
    staged: bool
    max_files: int
    max_diff_chars: int

    def __post_init__(self) -> None:
        if self.mode not in REVIEW_MODES:
            raise ReviewModelError(f"invalid_review_mode:{self.mode}")


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
class ReviewFinding(View):
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


@dataclass(frozen=True)
class ReviewActionProposal(View):
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


@dataclass(frozen=True)
class ProposalLifecycleRecord(View):
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


@dataclass(frozen=True)
class ProposalApprovalPreview(View):
    """Metadata-only approval planning preview derived from a saved proposal lifecycle record.

    This is a preview/planning record only. It never approves execution, executes
    proposals, applies patches, modifies files, stages/unstages, runs tests, or
    calls shell/process/network. ``ready_for_planning`` does not imply execution
    approval. ``requires_approval`` does not mean approval has been granted.
    """

    preview_id: str
    proposal_id: str
    review_id: str
    finding_id: str
    proposal_status: str
    action_type: str
    risk_level: str
    requires_approval: bool
    would_modify_files: bool
    files: list[str]
    required_human_decision: str
    required_safety_checks: list[str]
    blocking_conditions: list[str]
    recommended_next_action: str
    status: str
    created_at: str
    source: str

    def __post_init__(self) -> None:
        if not self.preview_id.startswith("apv_"):
            raise ReviewModelError("preview_id must use apv_ prefix")
        if not self.proposal_id.startswith("rap_"):
            raise ReviewModelError("proposal_id must use rap_ prefix")
        if self.status not in APPROVAL_PREVIEW_STATUSES:
            raise ReviewModelError(f"invalid_approval_preview_status:{self.status}")


@dataclass(frozen=True)
class ReviewSummary(View):
    files_reviewed: int
    findings_count: int
    severity_counts: dict[str, int]
    categories: dict[str, int]
    truncated: bool
    redaction_applied: bool
    proposal_count: int = 0


@dataclass(frozen=True)
class ReviewResult(View):
    review_id: str
    scope: ReviewScope
    summary: ReviewSummary
    findings: list[ReviewFinding] = field(default_factory=list)
    action_proposals: list[ReviewActionProposal] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    event_metadata: dict[str, Any] = field(default_factory=dict)
