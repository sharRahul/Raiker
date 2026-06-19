from __future__ import annotations

import hashlib
import json
from pathlib import Path

from raiker.context.gatherer import ContextGatherer
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.review.classifier import generate_findings
from raiker.review.diff_parser import parse_unified_diff
from raiker.review.models import (
    SEVERITIES as _SEVERITIES,
)
from raiker.review.models import (
    ReviewFinding,
    ReviewInput,
    ReviewResult,
    ReviewScope,
    ReviewSummary,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker
from raiker.tools.filesystem import FilesystemSafetyError, resolve_workspace_path

_SAFETY_NOTES_CLEAN = (
    "No files were modified.",
    "No shell/network/process execution was used.",
)
_SAFETY_NOTES_REVIEW = (
    "No files were modified.",
    "No shell/network/process execution was used.",
    "Review used bounded local context only.",
)


class ReviewError(ValueError):
    """Base error for the code-review workflow."""


class ReviewPathError(ReviewError):
    """Raised when a requested review path escapes the workspace."""


def _review_client() -> ClientMetadata:
    return ClientMetadata(type="cli", name="raiker-review", version="0.0.0")


class CodeReviewWorkflow:
    """Deterministic, read-only, local code-review workflow.

    Git status/diff are collected through the policy-mediated :class:`ToolBroker`. The broker
    is created without an event writer so raw diff output is never logged; only metadata-only
    review events are emitted. The workflow never mutates files, the index, or runs
    shell/process/network calls directly.
    """

    def __init__(self, *, emit_events: bool = True) -> None:
        self.emit_events = emit_events

    def review(
        self,
        *,
        workspace_root: str | Path,
        staged: bool = False,
        path: str | None = None,
        summary_only: bool = False,
        max_files: int = 20,
        max_diff_chars: int = 20000,
    ) -> ReviewResult:
        root = Path(workspace_root).resolve()
        path_filter = self._resolve_path_filter(root, path)

        store = SQLiteStore(root) if self.emit_events else None
        writer = EventLogWriter(store) if store is not None else None
        session_id = new_id("sess_")

        mode_base = "path" if path_filter is not None else ("staged" if staged else "unstaged")
        try:
            diff_text, staged_present = self._collect_diff(
                root, path_filter=path_filter, staged=staged, mode_base=mode_base
            )
            bounded_diff, truncated = self._bound_diff(diff_text, max_diff_chars)
            parsed = parse_unified_diff(bounded_diff)
            files = parsed.files
            if len(files) > max_files:
                files = files[:max_files]
                truncated = True
            redacted_diff, redaction_applied = redact_text(bounded_diff)
            untracked_files: list[str] = []
            if not staged:
                untracked_broker = ToolBroker(
                    workspace_root=root,
                    policy_engine=PolicyEngine(StaticPolicyConfig(root)),
                )
                untracked_files = self._collect_untracked_files(
                    untracked_broker, path_filter=path_filter
                )
            mode = mode_base if (files or untracked_files) else "clean"
            scope = ReviewScope(
                mode=mode,
                workspace_root=str(root),
                path_filter=path_filter,
                staged=staged,
                max_files=max_files,
                max_diff_chars=max_diff_chars,
            )
            review_id = _compute_review_id(scope, files, redacted_diff)
            self._emit(writer, session_id, "review_started", {"review_id": review_id, "mode": mode})

            context_summary = self._context_summary(root, session_id)
            review_input = ReviewInput(
                scope=scope,
                files=files,
                diff_text=redacted_diff,
                context_summary=context_summary,
                source_types=["git_diff", "context_gatherer"],
                truncated=truncated,
                redaction_applied=redaction_applied,
            )
            findings = generate_findings(review_input)
            if untracked_files:
                findings.append(ReviewFinding(
                    finding_id="untracked-files",
                    severity="info",
                    category="maintainability",
                    title="Untracked files present",
                    description="Untracked files exist and are not included in normal git diff review.",
                    evidence=f"{len(untracked_files)} untracked file(s) detected.",
                    recommendation="Stage the files or review a specific path after adding it to the index.",
                    confidence="high",
                ))
            summary = self._build_summary(
                files_reviewed=len(files),
                findings=findings,
                truncated=truncated,
                redaction_applied=redaction_applied,
            )
            event_payload = {
                "review_id": review_id,
                "mode": mode,
                "files_reviewed": len(files),
                "findings_count": len(findings),
                "severity_counts": dict(summary.severity_counts),
                "truncated": truncated,
                "redaction_applied": redaction_applied,
                "untracked_count": len(untracked_files),
            }
            self._emit(writer, session_id, "review_completed", dict(event_payload))
            result_metadata = dict(event_payload)
            result_metadata["categories"] = dict(summary.categories)
            result_metadata["staged_changes_present"] = staged_present
            result_metadata["untracked_files"] = untracked_files
            return ReviewResult(
                review_id=review_id,
                scope=scope,
                summary=summary,
                findings=findings,
                safety_notes=list(_SAFETY_NOTES_CLEAN if not files else _SAFETY_NOTES_REVIEW),
                event_metadata=result_metadata,
            )
        except ReviewPathError:
            raise
        except Exception as exc:
            self._emit(
                writer,
                session_id,
                "review_failed",
                {"mode": mode_base, "error_class": type(exc).__name__},
            )
            raise

    # --- internals ---------------------------------------------------------------

    def _resolve_path_filter(self, root: Path, path: str | None) -> str | None:
        if path is None:
            return None
        try:
            resolved = resolve_workspace_path(root, path)
        except FilesystemSafetyError as exc:
            raise ReviewPathError("path_outside_workspace") from exc
        if resolved == root:
            return "."
        return resolved.relative_to(root).as_posix()

    def _collect_diff(
        self,
        root: Path,
        *,
        path_filter: str | None,
        staged: bool,
        mode_base: str,
    ) -> tuple[str, bool]:
        broker = ToolBroker(
            workspace_root=root,
            policy_engine=PolicyEngine(StaticPolicyConfig(root)),
        )
        diff = self._git_diff(broker, path_filter=path_filter, cached=staged)
        staged_present = False
        if mode_base == "unstaged" and not diff.strip():
            staged_diff = self._git_diff(broker, path_filter=path_filter, cached=True)
            if staged_diff.strip():
                staged_present = True
            diff = ""  # default mode does not auto-review staged changes
        return diff, staged_present

    def _git_diff(self, broker: ToolBroker, *, path_filter: str | None, cached: bool) -> str:
        args: list[str] = []
        if cached:
            args.append("--cached")
        if path_filter is not None and path_filter != ".":
            args.extend(["--", path_filter])
        action = ToolAction(
            action_id=new_id("act_"),
            tool_name="git_diff",
            arguments={"args": args},
            risk_level="low",
            requires_approval=False,
            proposed_by="code_review_workflow",
        )
        result, _decision = broker.execute(
            action,
            session_id=new_id("sess_"),
            turn_id=new_id("turn_"),
            client=_review_client(),
        )
        if result.status == "success" and isinstance(result.output, dict):
            return str(result.output.get("output", ""))
        return ""

    def _collect_untracked_files(
        self, broker: ToolBroker, *, path_filter: str | None
    ) -> list[str]:
        action = ToolAction(
            action_id=new_id("act_"),
            tool_name="git_status",
            arguments={},
            risk_level="low",
            requires_approval=False,
            proposed_by="code_review_workflow",
        )
        result, _decision = broker.execute(
            action,
            session_id=new_id("sess_"),
            turn_id=new_id("turn_"),
            client=_review_client(),
        )
        if result.status != "success" or not isinstance(result.output, dict):
            return []
        output = str(result.output.get("output", ""))
        untracked: list[str] = []
        for line in output.splitlines():
            line = line.rstrip("\n")
            if line.startswith("?? "):
                rel = line[3:].strip()
                if rel:
                    untracked.append(rel)
        if path_filter is not None and path_filter != ".":
            stripped = path_filter.rstrip("/")
            untracked = [
                p
                for p in untracked
                if p == stripped
                or p.startswith(stripped + "/")
                or stripped.startswith(p.rstrip("/") + "/")
                or stripped == p.rstrip("/")
            ]
        return untracked[:20]

    def _context_summary(self, root: Path, session_id: str) -> str:
        try:
            bundle = ContextGatherer().gather(
                workspace_root=root,
                session_id=session_id,
                turn_id=new_id("turn_"),
                prompt_text="local code review",
                max_items=10,
                max_chars=4000,
            )
            return bundle.summary
        except Exception:
            return "context_gather_unavailable"

    def _bound_diff(self, diff_text: str, max_diff_chars: int) -> tuple[str, bool]:
        if len(diff_text) > max_diff_chars:
            return diff_text[:max_diff_chars], True
        return diff_text, False

    def _build_summary(
        self,
        *,
        files_reviewed: int,
        findings: list[ReviewFinding],
        truncated: bool,
        redaction_applied: bool,
    ) -> ReviewSummary:
        severity_counts = {severity: 0 for severity in _SEVERITIES}
        categories: dict[str, int] = {}
        for finding in findings:
            severity_counts[finding.severity] += 1
            categories[finding.category] = categories.get(finding.category, 0) + 1
        return ReviewSummary(
            files_reviewed=files_reviewed,
            findings_count=len(findings),
            severity_counts=severity_counts,
            categories=dict(sorted(categories.items())),
            truncated=truncated,
            redaction_applied=redaction_applied,
        )

    def _emit(
        self,
        writer: EventLogWriter | None,
        session_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        if writer is None:
            return
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type=event_type,
                actor="code_review",
                payload=payload,
                client=_review_client(),
            )
        )


def _compute_review_id(scope: ReviewScope, files: list[str], diff_text: str) -> str:
    payload = json.dumps(
        {
            "mode": scope.mode,
            "staged": scope.staged,
            "path_filter": scope.path_filter,
            "files": files,
            "diff": diff_text,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"rev_{digest}"
