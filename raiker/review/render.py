from __future__ import annotations

import json

from raiker.review.models import SEVERITIES, ReviewResult


def render_json(result: ReviewResult) -> str:
    """Render a JSON-safe, secret-free representation of the review result."""

    return json.dumps(result.to_dict(), sort_keys=True, indent=2)


def render_text(result: ReviewResult, *, summary_only: bool = False) -> str:
    scope = result.scope
    summary = result.summary

    if summary.files_reviewed == 0:
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
