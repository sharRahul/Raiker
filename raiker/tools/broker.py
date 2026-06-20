from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ClientMetadata, PolicyDecision, ToolAction, ToolResult
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HookInput, HookOutcome
from raiker.hooks.dispatcher import HookDispatcher
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
from raiker.tools.memory_tools import memory_forget, memory_get, memory_list, memory_search, memory_write
from raiker.tools.search import glob, grep


class ToolBroker:
    def __init__(
        self,
        *,
        workspace_root: str | Path,
        policy_engine: PolicyEngine,
        store: SQLiteStore | None = None,
        writer: EventLogWriter | None = None,
        hook_dispatcher: HookDispatcher | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.policy_engine = policy_engine
        self.store = store
        self.writer = writer
        self.hook_dispatcher = hook_dispatcher
        self.executors: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "read_file": lambda args: read_file(self.workspace_root, str(args.get("path", "."))),
            "list_directory": lambda args: list_directory(
                self.workspace_root, str(args.get("path", "."))
            ),
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
            "diff_files": lambda args: diff_files(
                self.workspace_root,
                str(args.get("before_path", ".")),
                str(args.get("after_path", ".")),
            ),
            "git_status": lambda args: run_git(self.workspace_root, "status", ["--short"]),
            "git_diff": lambda args: run_git(
                self.workspace_root, "diff", list(args.get("args", []))
            ),
            "git_log": lambda args: run_git(
                self.workspace_root, "log", ["--oneline", "-n", str(args.get("limit", 10))]
            ),
            "write_file": lambda args: proposed_write_snapshot(
                self.workspace_root, str(args.get("path", ".")), str(args.get("text", ""))
            ),
            "edit_file": lambda args: proposed_write_snapshot(
                self.workspace_root, str(args.get("path", ".")), str(args.get("text", ""))
            ),
            "apply_patch": lambda args: {
                "status": "proposal",
                "patch": str(args.get("patch", "")),
                "requires_approval": True,
            },
            "memory_write": lambda args: memory_write(
                self.workspace_root,
                str(args.get("text", "")),
                scope=str(args.get("scope", "project")),
                tags=tuple(args.get("tags", [])),
                source=str(args.get("source", "agent")),
            ),
            "memory_search": lambda args: memory_search(
                self.workspace_root,
                str(args.get("query", "")),
                scope=args.get("scope"),
                max_results=int(args.get("max_results", 20)),
            ),
            "memory_forget": lambda args: memory_forget(
                self.workspace_root,
                str(args.get("memory_id", "")),
            ),
            "memory_list": lambda args: memory_list(
                self.workspace_root,
                scope=args.get("scope"),
                limit=int(args.get("limit", 50)),
            ),
            "memory_get": lambda args: memory_get(
                self.workspace_root,
                str(args.get("memory_id", "")),
            ),
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

    def _approval_preview(self, action: ToolAction) -> dict[str, Any] | None:
        if action.tool_name in {"write_file", "edit_file"}:
            try:
                return proposed_write_snapshot(
                    self.workspace_root,
                    str(action.arguments.get("path", ".")),
                    str(action.arguments.get("text", "")),
                )
            except FilesystemSafetyError as exc:
                return {"status": "failed", "error": {"type": str(exc)}}
        if action.tool_name == "apply_patch":
            return {
                "status": "proposal",
                "patch": str(action.arguments.get("patch", "")),
                "requires_approval": True,
            }
        return None

    def _pre_tool_use(
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
    ) -> HookOutcome | None:
        if self.hook_dispatcher is None or not self.hook_dispatcher.is_active():
            return None
        return self.hook_dispatcher.dispatch(
            HookInput(
                event_name="PreToolUse",
                tool_name=action.tool_name,
                tool_input=action.arguments,
                context={"risk_level": action.risk_level, "policy_state": "pending"},
            ),
            session_id=session_id,
            turn_id=turn_id,
            client=client,
        )

    def _notify_hook(
        self,
        event_name: str,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
        context: dict[str, Any] | None = None,
    ) -> None:
        if self.hook_dispatcher is None or not self.hook_dispatcher.is_active():
            return
        self.hook_dispatcher.dispatch(
            HookInput(
                event_name=event_name,
                tool_name=action.tool_name,
                tool_input=action.arguments,
                context=context or {},
            ),
            session_id=session_id,
            turn_id=turn_id,
            client=client,
        )

    def _hook_deny_decision(self, action: ToolAction, reasons: list[str]) -> PolicyDecision:
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="deny",
            reasons=["hook_denied", *reasons],
            requires_user_approval=False,
            risk_level="blocked",
            timestamp=utc_now(),
        )

    def _hook_ask_decision(self, action: ToolAction, base: PolicyDecision) -> PolicyDecision:
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="needs_approval",
            reasons=["hook_requested_approval", *base.reasons],
            requires_user_approval=True,
            risk_level="high",
            timestamp=utc_now(),
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
            payload={
                "action_id": action.action_id,
                "tool_name": action.tool_name,
                "validation_status": "ok",
            },
            client=client,
        )
        hook_outcome = self._pre_tool_use(
            action, session_id=session_id, turn_id=turn_id, client=client
        )
        if hook_outcome is not None and hook_outcome.decision == "deny":
            decision = self._hook_deny_decision(action, hook_outcome.reasons)
        else:
            decision = self.policy_engine.review(action)
            if (
                hook_outcome is not None
                and hook_outcome.decision == "ask"
                and decision.decision == "allow"
            ):
                decision = self._hook_ask_decision(action, decision)
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
            self._notify_hook(
                "PermissionDenied",
                action,
                session_id=session_id,
                turn_id=turn_id,
                client=client,
                context={"reasons": decision.reasons},
            )
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
            proposal_preview = self._approval_preview(action)
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
                    "proposal_preview": proposal_preview,
                    "risk_level": "high",
                    "policy_reasons": decision.reasons,
                    "expected_effect": "Records an action-bound approval request and does not execute until resolved.",
                },
                client=client,
            )
            if self.store is not None:
                self.store.insert_approval(approval_id, action.action_id)
                self.store.insert_tool_action(action, session_id, turn_id, "approval_required")
            self._notify_hook(
                "PermissionRequest",
                action,
                session_id=session_id,
                turn_id=turn_id,
                client=client,
                context={"approval_id": approval_id, "reasons": decision.reasons},
            )
            return (
                ToolResult(
                    action_id=action.action_id,
                    tool_name=action.tool_name,
                    status="approval_required",
                    output={
                        "approval_id": approval_id,
                        "reasons": decision.reasons,
                        "proposal_preview": proposal_preview,
                    },
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
        self._notify_hook(
            "PostToolUse" if result.status == "success" else "PostToolUseFailure",
            action,
            session_id=session_id,
            turn_id=turn_id,
            client=client,
            context={"status": result.status},
        )
        return result, decision
