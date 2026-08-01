from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    proposed_edit_snapshot,
    proposed_patch_snapshot,
    proposed_write_snapshot,
    read_file,
    stat_path,
)
from raiker.tools.git import run_git
from raiker.tools.mcp_tools import is_mcp_tool, mcp_call
from raiker.tools.memory_tools import (
    memory_get,
    memory_list,
    memory_search,
)
from raiker.tools.search import glob, grep
from raiker.tools.vector_tools import vector_get

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal


@dataclass(frozen=True)
class ToolExecutionContext:
    """Trusted turn identity supplied by the broker, never by a model tool call."""

    session_id: str
    principal_id: str
    turn_id: str

# Tools whose arguments/results are scrubbed to metadata before entering event
# payloads or the stored tool-action record. The advisor question/answer flow
# only between the models (that is the tool's purpose); the audit trail records
# lengths and profile metadata, never the text.
# Tools whose *arguments* are scrubbed to lengths before entering events (the
# argument text is itself sensitive prompt content — the advisor question).
_METADATA_ONLY_TOOLS = frozenset({"consult_advisor"})


def _drops_argument_values(tool_name: str) -> bool:
    """True when a tool's *argument values* must not enter an event payload.

    A projected MCP tool's arguments are opaque values the model composes for an
    outside program — they can carry anything the conversation contained, and
    unlike a connector's repo/number they name nothing governance-relevant. The
    MCP session log already records their *shape* rather than their value; the
    broker events do the same (BUG-12).
    """
    return tool_name in _METADATA_ONLY_TOOLS or is_mcp_tool(tool_name)
# Tools whose *result content* is dropped from events. The advisor answer and the
# fetched GitHub body are untrusted content that flows only to the calling model;
# the audit trail keeps metadata (lengths, ids), never the content itself.
# The connector tools' arguments (repo / resource / number / message_id /
# calendar_id / event_id / channel) are governance-relevant non-secret
# identifiers and are kept verbatim (redacted) for the audit trail; only the
# fetched *content* is dropped from events.
_CONTENT_RESULT_TOOLS = frozenset(
    {
        "consult_advisor", "github_read", "gmail_read", "gcal_read", "slack_read",
        "connector_read", "run_command",
    }
)
_CONTENT_RESULT_FIELDS = ("answer", "content")


def _drops_result_content(tool_name: str) -> bool:
    """True when a tool's *content* must never enter an event payload.

    Projected MCP tools (``mcp__<server>__<tool>``) join the connector family:
    what an owner-registered server returned flows to the calling model as
    untrusted data, while the audit trail keeps metadata only (BUG-12).
    """
    return tool_name in _CONTENT_RESULT_TOOLS or is_mcp_tool(tool_name)


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
            "edit_file": lambda args: proposed_edit_snapshot(
                self.workspace_root,
                str(args.get("path", ".")),
                str(args.get("old_text", "")),
                str(args.get("new_text", "")),
            ),
            "apply_patch": lambda args: proposed_patch_snapshot(
                self.workspace_root, str(args["path"]) if args.get("path") else None, str(args.get("patch", ""))
            ),
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
        self.context_executors: dict[
            str, Callable[[dict[str, Any], ToolExecutionContext], dict[str, Any]]
        ] = {
            "create_task": self._create_task,
            "assign_session_project": self._assign_session_project,
            "create_document": self._create_document,
            "run_command": self._run_command,
        }

    def _run_command(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        import shlex

        from raiker.runtime.executors.containers import run_isolated_workspace_command
        from raiker.runtime.executors.sandbox import (
            ALLOWED_SHELL_COMMANDS,
            SandboxError,
            check_command_allowlist,
        )

        if self.store is None:
            return {"status": "denied", "error": {"type": "command_grant_required"}}
        grant = self.store.load_session_command_grant(
            session_id=context.session_id, principal_id=context.principal_id
        )
        if grant is None:
            return {
                "status": "denied",
                "error": {"type": "command_grant_required", "fallback_tool": "shell"},
            }
        try:
            command = shlex.split(str(args.get("command", "")), posix=True)
        except ValueError:
            return {"status": "denied", "error": {"type": "invalid_command"}}
        prefixes = grant.get("commands", [])
        authorised = any(
            command[: len(prefix)] == prefix
            for prefix in prefixes
            if isinstance(prefix, list) and prefix
        )
        if not authorised:
            return {
                "status": "denied",
                "error": {"type": "command_not_authorised", "fallback_tool": "shell"},
            }
        try:
            check_command_allowlist(command, ALLOWED_SHELL_COMMANDS)
            result = run_isolated_workspace_command(
                command,
                workspace_root=self.workspace_root,
                timeout=float(grant["timeout_seconds"]),
                max_output_bytes=100_000,
            )
        except SandboxError as exc:
            return {"status": "failed", "error": {"type": str(exc)}}
        return {"status": "success", **result}

    def _create_document(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        from raiker.runtime.document_generation import generate_document

        if self.store is None:
            return {"status": "failed", "error": {"type": "document_store_unavailable"}}
        return generate_document(
            self.workspace_root, self.store,
            path=str(args.get("path", "")), text=str(args.get("text", "")),
            session_id=context.session_id, turn_id=context.turn_id,
            principal_id=context.principal_id,
        )

    def _mcp_call(self, action: ToolAction) -> dict[str, Any]:
        """Run one projected MCP tool call (BUG-12).

        The broker has already applied hooks, the policy engine, and the
        approval flow by the time this runs; the MCP service adds the capability
        gate, the decision mode, containment, and the advertised-tool check.
        """
        nested = action.arguments.get("arguments")
        return mcp_call(
            self.workspace_root,
            action.tool_name,
            nested if isinstance(nested, dict) else {},
            store=self.store,
            principal_id=self.principal_id,
        )

    def _create_task(self, args: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        from raiker.control.dashboard import DashboardService

        title = str(args.get("title", "")).strip()
        if not title:
            return {"status": "failed", "error": {"type": "task_title_required"}}
        service = DashboardService(self.workspace_root)
        task = service.create_task(
            title=title,
            objective=str(args.get("description", "")).strip(),
            user_id=self.store.principal_user_id(context.principal_id) if self.store else None,
            principal_id=context.principal_id,
            scheduled_at=str(args["scheduled_at"]) if args.get("scheduled_at") else None,
            reminder_at=str(args["reminder_at"]) if args.get("reminder_at") else None,
            recurrence=str(args["recurrence"]) if args.get("recurrence") else None,
            project_id=str(args["project_id"]) if args.get("project_id") else None,
        )
        return {
            "status": "success",
            "receipt": {"kind": "task", "title": task.title, "href": "#/tasks", "label": "Review in Tasks"},
            "task_id": task.task_id,
        }

    def _assign_session_project(self, args: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        from raiker.control.dashboard import DashboardService

        project_id = str(args.get("project_id", "")).strip()
        if not project_id:
            return {"status": "failed", "error": {"type": "project_id_required"}}
        service = DashboardService(self.workspace_root)
        result = service.set_session_project(context.session_id, project_id, context.principal_id)
        if not result.ok:
            return {"status": "failed", "error": {"type": result.reason_code}}
        project = self.store.load_project(
            project_id, user_id=self.store.principal_user_id(context.principal_id)
        ) if self.store else None
        return {
            "status": "success",
            "receipt": {"kind": "project_assignment", "title": str(project.get("name")) if project else project_id, "href": "#/projects", "label": "Review in Projects"},
            "session_id": context.session_id,
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
        if _drops_argument_values(action.tool_name):
            return {
                f"{key}_length": len(str(value))
                for key, value in action.arguments.items()
            }
        return cls._redact_value(action.arguments)

    @classmethod
    def _event_safe_result_payload(cls, result: ToolResult) -> dict[str, Any]:
        """Result payload for events: metadata-only tools drop content fields."""
        payload = result.to_dict()
        if _drops_result_content(result.tool_name) and isinstance(payload.get("output"), dict):
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
        if action.tool_name in {"write_file", "create_document"}:
            if action.tool_name == "create_document" and not str(
                action.arguments.get("path", "")
            ).lower().endswith((".md", ".markdown")):
                return {"status": "failed", "error": {"type": "document_path_must_be_markdown"}}
            try:
                return proposed_write_snapshot(
                    self.workspace_root,
                    str(action.arguments.get("path", ".")),
                    str(action.arguments.get("text", "")),
                )
            except FilesystemSafetyError as exc:
                return {"status": "failed", "error": {"type": str(exc)}}
        if action.tool_name == "edit_file":
            try:
                return proposed_edit_snapshot(
                    self.workspace_root,
                    str(action.arguments.get("path", ".")),
                    str(action.arguments.get("old_text", "")),
                    str(action.arguments.get("new_text", "")),
                )
            except FilesystemSafetyError as exc:
                return {"status": "failed", "error": {"type": str(exc)}}
        if action.tool_name == "apply_patch":
            try:
                return proposed_patch_snapshot(
                    self.workspace_root,
                    str(action.arguments["path"]) if action.arguments.get("path") else None,
                    str(action.arguments.get("patch", "")),
                )
            except FilesystemSafetyError as exc:
                return {"status": "failed", "error": {"type": str(exc)}}
        return None

    def _expected_effect(self, action: ToolAction, connector_write: bool) -> str:
        """What approving this proposal will actually do, stated at proposal time.

        BUG-06: this sentence used to say "metadata-only … does not execute the
        action" for every non-connector tool, which stopped being true for file
        mutations once approval resolution was wired to the execution relay. It
        is now derived from the same check the resolve endpoint makes, so the
        model and the transcript are told the truth in both configurations.
        """
        if connector_write:
            return "Approving executes this exact connector mutation once."
        if self.store is not None:
            from raiker.approvals.execution import ApprovalExecutionBridge

            if ApprovalExecutionBridge(self.store).executes_on_resolution(
                action.tool_name, self.principal_id
            ):
                # The sentence is stored in events and returned to the client, so
                # the model-supplied path is scrubbed by credential shape first —
                # the same treatment every other argument gets on the way out.
                raw_path = str(action.arguments.get("path", ""))
                path = str(self._redact_value(raw_path)) or "the proposed path"
                return f"Approving writes this exact change to {path}, once."
        return (
            "Records an action-bound approval request only. Approval resolution is "
            "metadata-only and does not execute the action."
        )

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

    @staticmethod
    def _is_ordinary_approval_decision(action: ToolAction, decision: PolicyDecision) -> bool:
        """Whether a composer mode may replace this *UI* approval pause.

        This deliberately recognises only the exact ordinary Action-Bound
        approval pair emitted by :class:`PolicyEngine`. Hook requests, managed
        policy, unknown reasons, and every deny stay outside this narrow path.
        Critical actions are also excluded before the runtime authority is ever
        asked to execute them.
        """
        if decision.decision != "needs_approval" or action.risk_level == "critical":
            return False
        from raiker.runtime.authority.critical import classify_critical

        return (
            classify_critical(action.tool_name, action.tool_name, action.arguments) is None
            and decision.reasons
            == [
                f"{action.tool_name}_requires_approval",
                "phase2_action_bound_approval_required",
            ]
        )

    def _approval_mode_principal(self) -> Principal | None:
        """Return the human owner represented by the composer setting.

        Selecting Auto or Skip is an explicit, persisted owner decision. It is
        therefore represented as human pre-authorisation at the governed
        executor boundary, rather than by weakening an AI principal or a gate.
        An unrecognised stored non-human principal fails closed to the normal
        approval workflow.
        """
        from raiker.runtime.authority.models import Principal, PrincipalType

        if self.store is None:
            return None
        raw = self.store.get_principal(self.principal_id)
        if raw is not None:
            principal = Principal(**raw)
            return principal if principal.principal_type == PrincipalType.HUMAN else None
        return Principal(
            principal_id=self.principal_id,
            principal_type=PrincipalType.HUMAN,
            display_name="Local approval owner",
        )

    def _execute_preapproved_action(
        self,
        action: ToolAction,
        decision: PolicyDecision,
        *,
        approval_mode: str,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
        sanitized_action: ToolAction,
        now: str,
    ) -> tuple[ToolResult, PolicyDecision] | None:
        """Execute an ordinary action through the full runtime authority.

        No UI approval record is created, but the action still crosses all
        capability gates, critical classification, policy review, checkpoints,
        path/hunk validation, and executor transaction boundaries. Returning
        ``None`` intentionally falls back to the normal paused workflow.
        """
        if approval_mode not in {"auto", "skip"} or not self._is_ordinary_approval_decision(action, decision):
            return None
        principal = self._approval_mode_principal()
        if principal is None or self.store is None:
            return None

        preview = self._approval_preview(action) if approval_mode == "auto" else None
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_started",
            actor="tool_broker",
            payload={"action_id": action.action_id, "tool_name": action.tool_name},
            client=client,
        )
        from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
        from raiker.runtime.executors import build_default_executor_registry

        authority = RuntimeAuthority(
            self.store,
            self.writer or EventLogWriter(self.store),
            executor_registry=build_default_executor_registry(self.workspace_root, self.store),
        )
        governed = GovernedAction(
            action_id=action.action_id,
            principal_id=principal.principal_id,
            action_type=action.tool_name,
            tool_or_service_name=action.tool_name,
            arguments=action.arguments,
            risk_level=action.risk_level,
            session_id=session_id,
            turn_id=turn_id,
        )
        governed_result = authority.route_action(governed, principal)
        if governed_result.decision != "allow" or governed_result.error is not None:
            blocked_decision = PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="deny",
                reasons=["runtime_protection_preserved", governed_result.message or "execution_denied"],
                requires_user_approval=False,
                risk_level="blocked",
                timestamp=utc_now(),
            )
            failed = ToolResult(
                action_id=action.action_id,
                tool_name=action.tool_name,
                status="denied",
                output=None,
                error={"type": "runtime_execution_denied", "reason": governed_result.message},
                started_at=now,
                completed_at=utc_now(),
            )
            if self.store is not None:
                self.store.insert_tool_action(sanitized_action, session_id, turn_id, "denied")
                self.store.insert_policy_decision(blocked_decision)
            self._event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="tool_failed",
                actor="tool_broker",
                payload=self._event_safe_result_payload(failed),
                client=client,
            )
            return failed, blocked_decision

        executed_decision = PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="allow",
            reasons=[*decision.reasons, f"approval_mode:{approval_mode}"],
            requires_user_approval=False,
            risk_level=decision.risk_level,
            timestamp=utc_now(),
        )
        result = ToolResult(
            action_id=action.action_id,
            tool_name=action.tool_name,
            status="success",
            output={"status": "success", "executed": True, "approval_mode": approval_mode},
            error=None,
            started_at=now,
            completed_at=utc_now(),
        )
        if self.store is not None:
            self.store.insert_tool_action(sanitized_action, session_id, turn_id, result.status)
            self.store.insert_policy_decision(executed_decision)
        event_type = "approval_auto_executed" if approval_mode == "auto" else "approval_preview_skipped"
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type=event_type,
            actor="tool_broker",
            payload={
                "action_id": action.action_id,
                "tool_name": action.tool_name,
                "approval_mode": approval_mode,
                "policy_reasons": decision.reasons,
                **({"proposal_preview": preview} if approval_mode == "auto" else {}),
            },
            client=client,
        )
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_completed",
            actor="tool_broker",
            payload=self._event_safe_result_payload(result),
            client=client,
        )
        self._notify_hook(
            "PostToolUse",
            action,
            session_id=session_id,
            turn_id=turn_id,
            client=client,
            context={"status": result.status, "approval_mode": approval_mode},
        )
        return result, executed_decision

    def execute(
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None = None,
        approval_mode: str = "manual",
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
            preapproved = self._execute_preapproved_action(
                action,
                decision,
                approval_mode=approval_mode,
                session_id=session_id,
                turn_id=turn_id,
                client=client,
                sanitized_action=sanitized_action,
                now=now,
            )
            if preapproved is not None:
                return preapproved
            approval_id = new_id("appr_")
            proposal_preview = self._approval_preview(action)
            connector_write = action.tool_name == "connector_write"
            expected_effect = self._expected_effect(action, connector_write)
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
                        "files": action.tool_name in {"write_file", "create_document", "edit_file", "apply_patch"},
                        "memory": action.tool_name in {"memory_write", "memory_forget"},
                        "network": action.tool_name in {"shell", "remote_execute", "cloud_execute", "connector_write"},
                        "shell": action.tool_name in {"shell", "remote_execute", "cloud_execute"},
                        "provider": False,
                        "export": False,
                        "plugin": False,
                        "graph": False,
                        "channel": False,
                        "remote": action.tool_name in {"remote_execute", "cloud_execute"},
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
        context_executor = self.context_executors.get(action.tool_name)
        if executor is None and context_executor is None and is_mcp_tool(action.tool_name):
            raw = self._mcp_call(action)
        elif executor is None and context_executor is None:
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
                if context_executor is not None:
                    raw = context_executor(
                        action.arguments,
                        ToolExecutionContext(
                            session_id=session_id, principal_id=self.principal_id,
                            turn_id=turn_id or "",
                        ),
                    )
                else:
                    assert executor is not None
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
