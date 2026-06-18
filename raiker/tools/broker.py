from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ClientMetadata, PolicyDecision, ToolAction, ToolResult
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import (
    FilesystemSafetyError,
    diff_files,
    list_directory,
    proposed_write_snapshot,
    read_file,
    stat_path,
)
from raiker.tools.git import run_git
from raiker.tools.search import glob, grep


class ToolBroker:
    def __init__(
        self,
        *,
        workspace_root: str | Path,
        policy_engine: PolicyEngine,
        store: SQLiteStore | None = None,
        writer: EventLogWriter | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.policy_engine = policy_engine
        self.store = store
        self.writer = writer
        self.executors: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "read_file": lambda args: read_file(self.workspace_root, str(args.get("path", "."))),
            "list_directory": lambda args: list_directory(self.workspace_root, str(args.get("path", "."))),
            "glob": lambda args: glob(
                self.workspace_root,
                str(args.get("pattern", "*")),
                max_results=int(args.get("max_results", 100)),
            ),
            "grep": lambda args: grep(
                self.workspace_root,
                str(args.get("query", "")),
                str(args.get("path", ".")),
                include=str(args.get("include", "*")),
                max_results=int(args.get("max_results", 100)),
            ),
            "stat_path": lambda args: stat_path(self.workspace_root, str(args.get("path", "."))),
            "diff_files": lambda args: diff_files(self.workspace_root, str(args.get("before_path", ".")), str(args.get("after_path", "."))),
            "git_status": lambda args: run_git(self.workspace_root, "status", ["--short"]),
            "git_diff": lambda args: run_git(self.workspace_root, "diff", list(args.get("args", []))),
            "git_log": lambda args: run_git(self.workspace_root, "log", ["--oneline", "-n", str(args.get("limit", 10))]),
            "write_file": lambda args: proposed_write_snapshot(self.workspace_root, str(args.get("path", ".")), str(args.get("text", ""))),
            "edit_file": lambda args: proposed_write_snapshot(self.workspace_root, str(args.get("path", ".")), str(args.get("text", ""))),
            "apply_patch": lambda args: {"status": "proposal", "patch": str(args.get("patch", "")), "requires_approval": True},
        }

    def _event(
        self,
        *,
        session_id: str,
        turn_id: str | None,
        event_type: str,
        actor: str,
        payload: dict[str, object],
        client: ClientMetadata | None,
    ) -> None:
        if self.writer is not None:
            self.writer.append(
                make_event(
                    session_id=session_id,
                    turn_id=turn_id,
                    event_type=event_type,
                    actor=actor,
                    payload=payload,
                    client=client,
                )
            )

    def execute(
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None = None,
    ) -> tuple[ToolResult, PolicyDecision]:
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="action_proposed",
            actor="tool_broker",
            payload={"action": action.to_dict(), "risk_level": action.risk_level},
            client=client,
        )
        if self.store is not None:
            self.store.insert_tool_action(action, session_id, turn_id, "proposed")
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="action_validated",
            actor="tool_broker",
            payload={"action_id": action.action_id, "tool_name": action.tool_name, "validation_status": "ok"},
            client=client,
        )
        decision = self.policy_engine.review(action)
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="policy_decision",
            actor="policy_engine",
            payload=decision.to_dict(),
            client=client,
        )
        if self.store is not None:
            self.store.insert_policy_decision(decision)
        now = utc_now()
        if decision.decision == "deny":
            if self.store is not None:
                self.store.insert_tool_action(action, session_id, turn_id, "denied")
            return (
                ToolResult(
                    action_id=action.action_id,
                    tool_name=action.tool_name,
                    status="denied",
                    output=None,
                    error={"type": "policy_denied", "reasons": decision.reasons},
                    started_at=now,
                    completed_at=utc_now(),
                ),
                decision,
            )
        if decision.decision == "needs_approval":
            approval_id = new_id("appr_")
            self._event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="approval_requested",
                actor="tool_broker",
                payload={
                    "approval_id": approval_id,
                    "action_id": action.action_id,
                    "tool_name": action.tool_name,
                    "arguments_preview": action.arguments,
                    "risk_level": "high",
                    "policy_reasons": decision.reasons,
                    "expected_effect": "Records an action-bound approval request and does not execute until resolved.",
                },
                client=client,
            )
            if self.store is not None:
                self.store.insert_approval(approval_id, action.action_id)
                self.store.insert_tool_action(action, session_id, turn_id, "approval_required")
            return (
                ToolResult(
                    action_id=action.action_id,
                    tool_name=action.tool_name,
                    status="approval_required",
                    output={"approval_id": approval_id, "reasons": decision.reasons},
                    error=None,
                    started_at=now,
                    completed_at=utc_now(),
                ),
                decision,
            )
        executor = self.executors.get(action.tool_name)
        if executor is None:
            failed = ToolResult(
                action_id=action.action_id,
                tool_name=action.tool_name,
                status="failed",
                output=None,
                error={"type": "unknown_tool"},
                started_at=now,
                completed_at=utc_now(),
            )
            self._event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="tool_failed",
                actor="tool_broker",
                payload=failed.to_dict(),
                client=client,
            )
            return failed, decision
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_started",
            actor="tool_broker",
            payload={"action_id": action.action_id, "tool_name": action.tool_name},
            client=client,
        )
        try:
            raw = executor(action.arguments)
            status = "success" if raw.get("status") == "success" else "failed"
            result = ToolResult(
                action_id=action.action_id,
                tool_name=action.tool_name,
                status=status,
                output=raw if status == "success" else None,
                error=None if status == "success" else raw.get("error", {"type": "tool_failed"}),
                started_at=now,
                completed_at=utc_now(),
            )
        except FilesystemSafetyError as exc:
            result = ToolResult(
                action_id=action.action_id,
                tool_name=action.tool_name,
                status="failed",
                output=None,
                error={"type": str(exc)},
                started_at=now,
                completed_at=utc_now(),
            )
        if self.store is not None:
            self.store.insert_tool_action(action, session_id, turn_id, result.status)
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_completed" if result.status == "success" else "tool_failed",
            actor="tool_broker",
            payload=result.to_dict(),
            client=client,
        )
        return result, decision
