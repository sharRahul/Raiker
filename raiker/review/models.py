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
class ReviewSummary:
    files_reviewed: int
    findings_count: int
    severity_counts: dict[str, int]
    categories: dict[str, int]
    truncated: bool
    redaction_applied: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_reviewed": self.files_reviewed,
            "findings_count": self.findings_count,
            "severity_counts": dict(self.severity_counts),
            "categories": dict(self.categories),
            "truncated": self.truncated,
            "redaction_applied": self.redaction_applied,
        }


@dataclass(frozen=True)
class ReviewResult:
    review_id: str
    scope: ReviewScope
    summary: ReviewSummary
    findings: list[ReviewFinding] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    event_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "scope": self.scope.to_dict(),
            "summary": self.summary.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "safety_notes": list(self.safety_notes),
            "event_metadata": dict(self.event_metadata),
        }
