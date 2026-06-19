from __future__ import annotations

import json
from dataclasses import replace

from raiker.review.models import SEVERITIES, ReviewFinding, ReviewResult, ReviewSummary


def rebuild_review_result_with_findings(
    result: ReviewResult, findings: list[ReviewFinding]
) -> ReviewResult:
    severity_counts: dict[str, int] = {s: 0 for s in SEVERITIES}
    categories: dict[str, int] = {}
    for finding in findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        categories[finding.category] = categories.get(finding.category, 0) + 1
    summary = ReviewSummary(
        files_reviewed=result.summary.files_reviewed,
        findings_count=len(findings),
        severity_counts=severity_counts,
        categories=dict(sorted(categories.items())),
        truncated=result.summary.truncated,
        redaction_applied=result.summary.redaction_applied,
    )
    event_metadata = dict(result.event_metadata)
    event_metadata["findings_count"] = len(findings)
    event_metadata["severity_counts"] = severity_counts
    event_metadata["categories"] = dict(sorted(categories.items()))
    return replace(
        result,
        findings=findings,
        summary=summary,
        event_metadata=event_metadata,
    )


def render_json(result: ReviewResult) -> str:
    """Render a JSON-safe, secret-free representation of the review result."""

    return json.dumps(result.to_dict(), sort_keys=True, indent=2)


def render_text(result: ReviewResult, *, summary_only: bool = False) -> str:
    scope = result.scope
    summary = result.summary

    if summary.files_reviewed == 0 and not result.findings:
        return _render_empty(result)

    lines = [
        "Code review summary",
        "Scope:",
        f"- Mode: {_mode_label(scope.mode, scope.staged)}",
        f"- Files reviewed: {summary.files_reviewed}",
        f"- Findings: {summary.findings_count}",
        "Severity:",
        f"- High: {summary.severity_counts.get('high', 0)}",
        f"- Medium: {summary.severity_counts.get('medium', 0)}",
        f"- Low: {summary.severity_counts.get('low', 0)}",
        f"- Info: {summary.severity_counts.get('info', 0)}",
    ]

    if result.findings:
        lines.append("Findings:")
        for index, finding in enumerate(result.findings, start=1):
            if summary_only:
                lines.append(
                    f"{index}. [{finding.severity}] {finding.category}: {finding.title}"
                )
                continue
            lines.append(
                f"{index}. [{finding.severity}] {finding.category}: {finding.title}"
            )
            lines.append(f"   File: {finding.file_path or '-'}")
            lines.append(f"   Line: {finding.line if finding.line is not None else '-'}")
            lines.append(f"   Evidence: {finding.evidence}")
            lines.append(f"   Recommendation: {finding.recommendation}")

    lines.append("Safety:")
    lines.extend(f"- {note}" for note in result.safety_notes)
    return "\n".join(lines)


def _render_empty(result: ReviewResult) -> str:
    scope = result.scope
    if result.event_metadata.get("staged_changes_present"):
        headline = "No unstaged changes found. Staged changes exist; run /review --staged to review them."
    elif scope.path_filter is not None:
        headline = f"No matching changes found under path: {scope.path_filter}"
    elif scope.staged:
        headline = "No staged changes found."
    else:
        headline = "No local changes found."
    lines = ["Code review summary", headline, "Safety:"]
    lines.extend(f"- {note}" for note in result.safety_notes)
    return "\n".join(lines)


def _mode_label(mode: str, staged: bool) -> str:
    if mode == "unstaged":
        return "unstaged changes"
    if mode == "staged":
        return "staged changes"
    if mode == "path":
        return "staged changes (path filtered)" if staged else "path filtered changes"
    return "clean"


# Re-exported for callers that want the canonical severity ordering.
__all__ = ["render_json", "render_text", "SEVERITIES"]
