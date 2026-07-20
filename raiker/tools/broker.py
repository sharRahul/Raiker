from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ClientMetadata, PolicyDecision, ToolAction, ToolResult
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HookInput, HookOutcome
from raiker.hooks.dispatcher import HookDispatcher
from raiker.memory.governance import GovernedMemoryService
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.advisor_tools import consult_advisor
from raiker.tools.connector_tools import (
    connector_read,
    gcal_read,
    github_read,
    gmail_read,
    slack_read,
)
from raiker.tools.filesystem import (
    FilesystemSafetyError,
    diff_files,
    list_directory,
    proposed_write_snapshot,
    read_file,
    stat_path,
)
from raiker.tools.git import run_git
from raiker.tools.memory_tools import (
    memory_get,
    memory_list,
    memory_search,
)
from raiker.tools.search import glob, grep
from raiker.tools.vector_tools import vector_get

# Tools whose arguments/results are scrubbed to metadata before entering event
# payloads or the stored tool-action record. The advisor question/answer flow
# only between the models (that is the tool's purpose); the audit trail records
# lengths and profile metadata, never the text.
# Tools whose *arguments* are scrubbed to lengths before entering events (the
# argument text is itself sensitive prompt content — the advisor question).
_METADATA_ONLY_TOOLS = frozenset({"consult_advisor"})
# Tools whose *result content* is dropped from events. The advisor answer and the
# fetched GitHub body are untrusted content that flows only to the calling model;
# the audit trail keeps metadata (lengths, ids), never the content itself.
# The connector tools' arguments (repo / resource / number / message_id /
# calendar_id / event_id / channel) are governance-relevant non-secret
# identifiers and are kept verbatim (redacted) for the audit trail; only the
# fetched *content* is dropped from events.
_CONTENT_RESULT_TOOLS = frozenset(
    {"consult_advisor", "github_read", "gmail_read", "gcal_read", "slack_read", "connector_read"}
)
_CONTENT_RESULT_FIELDS = ("answer", "content")


class ToolBroker:
    def __init__(
        self,
        *,
        workspace_root: str | Path,
        policy_engine: PolicyEngine,
        store: SQLiteStore | None = None,
        writer: EventLogWriter | None = None,
        hook_dispatcher: HookDispatcher | None = None,
        principal_id: str = "local_user",
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.policy_engine = policy_engine
        self.store = store
        self.writer = writer
        self.hook_dispatcher = hook_dispatcher
        self.principal_id = principal_id
        self.memory_service = GovernedMemoryService(
            self.workspace_root,
            store=store or SQLiteStore(self.workspace_root),
            writer=writer,
        )
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
            "memory_search": lambda args: memory_search(
                self.workspace_root,
                str(args.get("query", "")),
                scope=args.get("scope"),
                max_results=int(args.get("max_results", 20)),
                owner_principal_id=self.owner_scope,
            ),
            "memory_list": lambda args: memory_list(
                self.workspace_root,
                scope=args.get("scope"),
                limit=int(args.get("limit", 50)),
                owner_principal_id=self.owner_scope,
            ),
            "memory_get": lambda args: memory_get(
                self.workspace_root,
                str(args.get("memory_id", "")),
                owner_principal_id=self.owner_scope,
            ),
            "vector_get": lambda args: vector_get(
                self.workspace_root,
                str(args.get("vector_id", "")),
                owner_principal_id=self.owner_scope,
            ),
            "consult_advisor": lambda args: consult_advisor(
                self.workspace_root,
                str(args.get("question", "")),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "github_read": lambda args: github_read(
                self.workspace_root,
                str(args.get("resource", "")),
                str(args.get("repo", "")),
                args.get("number", ""),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "gmail_read": lambda args: gmail_read(
                self.workspace_root,
                str(args.get("resource", "")),
                str(args.get("message_id", "")),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "gcal_read": lambda args: gcal_read(
                self.workspace_root,
                str(args.get("resource", "")),
                str(args.get("calendar_id", "")),
                str(args.get("event_id", "")),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "slack_read": lambda args: slack_read(
                self.workspace_root,
                str(args.get("resource", "")),
                str(args.get("channel", "")),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "connector_read": lambda args: connector_read(
                self.workspace_root,
                self.principal_id,
                str(args.get("connector_id", "")),
                str(args.get("operation_id", "")),
                args.get("arguments") if isinstance(args.get("arguments"), dict) else {},
                store=self.store,
            ),
        }

    @property
    def owner_scope(self) -> str | None:
        """The acting principal id, but only when it names a real account.

        ``principal_id`` identifies *who acted* and is always recorded as-is for
        attribution. It only narrows an owner-scoped **read** when it belongs to
        an account: the default ``local_user`` is not a principal, so scoping a
        read on it matches no rows and hides the caller's own data. Resolved per
        call because an account can be created after the broker is built.
        """
        store = self.store or SQLiteStore(self.workspace_root)
        return store.account_scope(self.principal_id)

    @staticmethod
    def _redact_value(value: Any) -> Any:
        if isinstance(value, str):
            redacted, _ = redact_text(value)
            return redacted
        if isinstance(value, list):
            return [ToolBroker._redact_value(item) for item in value]
        if isinstance(value, tuple):
            return [ToolBroker._redact_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): ToolBroker._redact_value(item) for key, item in value.items()}
        return value

    @classmethod
    def _event_safe_arguments(cls, action: ToolAction) -> dict[str, Any]:
        """Arguments as they may appear in events / stored records.

        Metadata-only tools replace their content-bearing arguments with
        lengths; everything else is secret-redacted verbatim.
        """
        if action.tool_name in _METADATA_ONLY_TOOLS:
            return {
                f"{key}_length": len(str(value))
                for key, value in action.arguments.items()
            }
        return cls._redact_value(action.arguments)

    @classmethod
    def _event_safe_result_payload(cls, result: ToolResult) -> dict[str, Any]:
        """Result payload for events: metadata-only tools drop content fields."""
        payload = result.to_dict()
        if result.tool_name in _CONTENT_RESULT_TOOLS and isinstance(payload.get("output"), dict):
            output = dict(payload["output"])
            for field in _CONTENT_RESULT_FIELDS:
                output.pop(field, None)
            output["content_redacted"] = True
            payload["output"] = output
        return payload

    @classmethod
    def _sanitized_action_payload(cls, action: ToolAction) -> dict[str, Any]:
        payload = action.to_dict()
        payload["arguments"] = cls._event_safe_arguments(action)
        return payload

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
        sanitized_action = ToolAction(
            action_id=action.action_id,
            tool_name=action.tool_name,
            arguments=self._event_safe_arguments(action),
            risk_level=action.risk_level,
            requires_approval=action.requires_approval,
            proposed_by=action.proposed_by,
        )
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="action_proposed",
            actor="tool_broker",
            payload={"action": self._sanitized_action_payload(action), "risk_level": action.risk_level},
            client=client,
        )
        if self.store is not None:
            self.store.insert_tool_action(sanitized_action, session_id, turn_id, "proposed")
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
                self.store.insert_tool_action(sanitized_action, session_id, turn_id, "denied")
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
            connector_write = action.tool_name == "connector_write"
            expected_effect = (
                "Approving executes this exact connector mutation once."
                if connector_write
                else "Records an action-bound approval request only. Approval resolution is metadata-only and does not execute the action."
            )
            self._event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="approval_requested",
                actor="tool_broker",
                payload={
                    "approval_id": approval_id,
                    "action_id": action.action_id,
                    "tool_name": action.tool_name,
                    "arguments_preview": self._event_safe_arguments(action),
                    "proposal_preview": proposal_preview,
                    "risk_level": "high",
                    "policy_reasons": decision.reasons,
                    "expected_effect": expected_effect,
                    "state_changes": {
                        "files": action.tool_name in {"write_file", "edit_file", "apply_patch"},
                        "memory": action.tool_name in {"memory_write", "memory_forget"},
                        "network": action.tool_name in {"shell", "connector_write"},
                        "shell": action.tool_name == "shell",
                        "provider": False,
                        "export": False,
                        "plugin": False,
                        "graph": False,
                        "channel": False,
                        "remote": False,
                    },
                },
                client=client,
            )
            if self.store is not None:
                self.store.insert_approval(approval_id, action)
                self.store.insert_tool_action(
                    sanitized_action, session_id, turn_id, "approval_required"
                )
                # D2 — async approval notification. Parking a turn for approval
                # never blocks silently: the owner gets a dashboard notification
                # (and an optional OS-level push) so they can approve from any
                # surface. Best-effort and metadata-only; a delivery failure never
                # affects the parked approval.
                try:
                    from raiker.notify import notify_approval_pending

                    notify_approval_pending(
                        self.store,
                        acting_principal_id=self.principal_id,
                        approval_id=approval_id,
                        tool_name=action.tool_name,
                        risk_level=action.risk_level,
                    )
                except Exception:
                    pass
                if action.tool_name == "connector_write":
                    connector_id = action.arguments.get("connector_id")
                    operation_id = action.arguments.get("operation_id")
                    arguments = action.arguments.get("arguments", {})
                    if (
                        isinstance(connector_id, str)
                        and isinstance(operation_id, str)
                        and isinstance(arguments, dict)
                    ):
                        from raiker.runtime.connector_ecosystem import ConnectorInvoker

                        try:
                            operation, _base = ConnectorInvoker(self.store)._operation(
                                connector_id, operation_id
                            )
                        except ValueError:
                            operation = {}
                        if operation.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
                            with self.store.connect() as connection:
                                connection.execute(
                                """INSERT INTO connector_write_intents
                                   (intent_id, approval_id, principal_id, connector_id,
                                    operation_id, arguments_json, status, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?, 'pending_approval', ?)""",
                                    (
                                    new_id("cwi_"),
                                    approval_id,
                                    self.principal_id,
                                    connector_id,
                                    operation_id,
                                    json.dumps(arguments, sort_keys=True),
                                        utc_now(),
                                    ),
                                )
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
                        "action_id": action.action_id,
                        "tool_name": action.tool_name,
                        "exact_arguments": self._event_safe_arguments(action),
                        "risk_level": "high",
                        "reasons": decision.reasons,
                        "proposal_preview": proposal_preview,
                        "expected_effect": expected_effect,
                    },
                    error=None,
                    started_at=now,
                    completed_at=utc_now(),
                ),
                decision,
            )
        executor = self.executors.get(action.tool_name)
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_started",
            actor="tool_broker",
            payload={"action_id": action.action_id, "tool_name": action.tool_name},
            client=client,
        )
        if executor is None:
            if action.tool_name == "memory_write":
                raw = self.memory_service.write_from_action(
                    action,
                    decision,
                    session_id=session_id,
                    turn_id=turn_id,
                    client=client,
                    owner_principal_id=self.owner_scope,
                )
            elif action.tool_name == "memory_forget":
                raw = self.memory_service.forget_from_action(
                    action,
                    decision,
                    session_id=session_id,
                    turn_id=turn_id,
                    client=client,
                    owner_principal_id=self.owner_scope,
                )
            else:
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
        else:
            try:
                raw = executor(action.arguments)
            except FilesystemSafetyError as exc:
                raw = {"status": "failed", "error": {"type": str(exc)}}
        status = "success" if raw.get("status") == "success" else ("denied" if raw.get("status") == "denied" else "failed")
        result = ToolResult(
            action_id=action.action_id,
            tool_name=action.tool_name,
            status=status,
            output=raw if status == "success" else None,
            error=None if status == "success" else raw.get("error", {"type": "tool_failed"}),
            started_at=now,
            completed_at=utc_now(),
        )
        if self.store is not None:
            self.store.insert_tool_action(sanitized_action, session_id, turn_id, result.status)
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_completed" if result.status == "success" else "tool_failed",
            actor="tool_broker",
            payload=self._event_safe_result_payload(result),
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
