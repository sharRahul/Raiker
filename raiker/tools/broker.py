from __future__ import annotations

import contextlib
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ClientMetadata, PolicyDecision, ToolAction, ToolResult
from raiker.contracts.streaming import TOOL, StreamEvent
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.execution.container_tools import ContainerToolExecutor
from raiker.execution.profiles import (
    ExecutionProfile,
    ProfileResolution,
    execution_profiles_from_rows,
    list_execution_profiles,
    resolve_tool_profile,
)
from raiker.hooks.contracts import HookInput, HookOutcome
from raiker.hooks.dispatcher import HookDispatcher
from raiker.memory.capture import capture_tool_observation
from raiker.memory.governance import GovernedMemoryService
from raiker.policy.engine import PolicyEngine
from raiker.runtime.identity.contracts import (
    IDENTITY_AUDIENCE,
    MachineIdentityError,
)
from raiker.runtime.identity.lifecycle import TrustedTurnIdentity
from raiker.runtime.identity.verifier import MachineIdentityVerifier
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.advisor_tools import consult_advisor
from raiker.tools.codemap_tools import code_map_references, code_map_search
from raiker.tools.connector_tools import (
    connector_read,
    gcal_read,
    github_read,
    gmail_read,
    slack_read,
)
from raiker.tools.conversation_tools import conversation_search
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
from raiker.tools.git import (
    proposed_branch_snapshot,
    proposed_commit_snapshot,
    proposed_push_snapshot,
    repository_label,
    resolve_repository_root,
    run_git,
    selected_repository_subpath,
)
from raiker.tools.graph_tools import knowledge_graph
from raiker.tools.mcp_tools import is_mcp_tool, mcp_call
from raiker.tools.memory_tools import (
    memory_get,
    memory_list,
    memory_search,
)
from raiker.tools.presentation import tool_row
from raiker.tools.search import glob, grep
from raiker.tools.skill_tools import skill_load
from raiker.tools.vector_tools import vector_get
from raiker.tools.web_tools import web_fetch, web_search

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal


@dataclass(frozen=True)
class ToolExecutionContext:
    """Trusted turn identity supplied by the broker, never by a model tool call."""

    session_id: str
    turn_id: str
    acting_principal_id: str
    owner_principal_id: str
    verified_identity: TrustedTurnIdentity

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
#: The ceiling a background run may occupy (BUG-194). Deliberately a hard cap
#: rather than "until it finishes": a run with no deadline is a run whose lease
#: renews forever, and the reclaim path would never fire. Two hours is long
#: enough for a real build or test suite and short enough that a wedged one is
#: reaped the same working day.
_BACKGROUND_TIMEOUT_SECONDS = 7200.0

_CONTENT_RESULT_TOOLS = frozenset(
    {
        "consult_advisor", "github_read", "gmail_read", "gcal_read", "slack_read",
        "connector_read", "run_command",
        # BUG-194 — a background run's log is the same program output
        # `run_command` returns, arriving one page at a time. It gets the same
        # treatment: metadata into the audit trail, content only to the model.
        "background_run",
        # B12/C7 — a fetched page and a search result set are outside content the
        # agent read on the owner's behalf. They flow to the calling model as
        # untrusted data; the audit trail keeps the URL, the query and the sizes.
        "web_fetch", "web_search",
        # B7 — a subagent's digest is workspace content it read on the parent's
        # behalf. It flows to the calling model and nowhere else; the audit
        # trail keeps the contract, the steps, and the tools used.
        "spawn_subagent",
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
        # BUG-206 slice A — the live half of a tool call. `self.writer` makes a
        # call readable *afterwards*, on the Audit log; without a sink the same
        # facts never reach the turn that is running, which is why a tool-using
        # conversation looked exactly like one that used no tools. The runtime
        # owns this list for the length of a streamed turn and drains it beside
        # its own lifecycle events (see `RuntimeOrchestrator._sink`); when it is
        # None — a non-streamed turn, the terminal client, a direct caller — the
        # broker behaves exactly as it did before.
        self.stream_sink: list[StreamEvent] | None = None
        self.command_service = CommandService.for_workspace(self.workspace_root)
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
            "git_status": lambda args: run_git(self.git_root(), "status", ["--short"]),
            "git_diff": lambda args: run_git(
                self.git_root(), "diff", list(args.get("args", []))
            ),
            "git_log": lambda args: run_git(
                self.git_root(), "log", ["--oneline", "-n", str(args.get("limit", 10))]
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
            "knowledge_graph": lambda args: knowledge_graph(
                self.workspace_root,
                str(args.get("action", "")),
                query=str(args.get("query", "")),
                entity_id=str(args.get("entity_id", "")),
                locator=str(args.get("locator", "")),
                session_id=str(args.get("session_id", "")),
                scope=args.get("scope"),
                max_results=int(args.get("max_results", 50)),
                owner_principal_id=self.owner_scope,
            ),
            "memory_search": lambda args: memory_search(
                self.workspace_root,
                str(args.get("query", "")),
                scope=args.get("scope"),
                entity_id=str(args["entity_id"]) if args.get("entity_id") else None,
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
            "skill_load": lambda args: skill_load(
                self.workspace_root,
                str(args.get("name", "")),
                file=str(args["file"]) if args.get("file") else None,
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
            "web_fetch": lambda args: web_fetch(
                self.workspace_root,
                str(args.get("url", "")),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "web_search": lambda args: web_search(
                self.workspace_root,
                str(args.get("query", "")),
                args.get("max_results", 5),
                store=self.store,
                principal_id=self.principal_id,
            ),
            "code_map_search": lambda args: code_map_search(
                self.workspace_root,
                str(args.get("query", "")),
                args.get("max_results", 10),
                store=self.store,
                principal_id=self.principal_id,
            ),
            # RAIKER-2020 — recall of the owner's own past conversations. Scoped
            # to the owner's user, bounded, and read-only: it returns transcript
            # text the owner already owns, so it opens nothing `get_session`
            # would not already have shown them.
            "conversation_search": lambda args: conversation_search(
                self.workspace_root,
                str(args.get("query", "")),
                max_results=args.get("max_results", 10),
                session_id=str(args["session_id"]) if args.get("session_id") else None,
                after=str(args["after"]) if args.get("after") else None,
                before=str(args["before"]) if args.get("before") else None,
                store=self.store,
                user_id=(
                    self.store.principal_user_id(self.owner_scope or self.principal_id)
                    if self.store
                    else None
                ),
            ),
            "code_map_references": lambda args: code_map_references(
                self.workspace_root,
                str(args.get("name", "")),
                args.get("max_results", 25),
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
            "background_run": self._background_run,
            "update_plan": self._update_plan,
            "spawn_subagent": self._spawn_subagent,
        }

    def _update_plan(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        """Record this conversation's plan (B6).

        Owner-scoped and fail-closed: a malformed plan is refused with a named
        reason and the stored plan is left exactly as it was, because replacing
        a good spine with half of one is worse than refusing.
        """
        from raiker.runtime.agent_plan import (
            PlanValidationError,
            normalize_steps,
            save_plan,
        )

        if self.store is None:
            return {"status": "failed", "error": {"type": "plan_store_unavailable"}}
        owner = context.owner_principal_id
        try:
            steps = normalize_steps(args.get("steps"))
        except PlanValidationError as exc:
            return {"status": "failed", "error": {"type": exc.reason}}
        plan = save_plan(
            self.store,
            session_id=context.session_id,
            principal_id=owner,
            turn_id=context.turn_id,
            steps=steps,
        )
        return {"status": "success", "plan": plan}

    def _spawn_subagent(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        """Run one bounded, read-only subagent for the model (B7).

        The subagent's own steps are re-brokered individually, so nothing here
        widens authority; what this adds is the *digest*, which keeps a wide
        search out of the parent turn's context.
        """
        from raiker.tools.subagent_tools import spawn_subagent

        if self.store is None:
            return {"status": "failed", "error": {"type": "subagent_store_unavailable"}}
        return spawn_subagent(
            self.workspace_root,
            args,
            store=self.store,
            principal_id=context.acting_principal_id,
            owner_principal_id=context.owner_principal_id,
            parent_identity=context.verified_identity,
            session_id=context.session_id,
            turn_id=context.turn_id,
        )

    def _run_command(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        import shlex

        from raiker.runtime.executors.sandbox import (
            ALLOWED_SHELL_COMMANDS,
            SandboxError,
            check_command_allowlist,
        )

        if self.store is None:
            return {"status": "denied", "error": {"type": "command_grant_required"}}
        grant = self.store.load_session_command_grant(
            session_id=context.session_id, principal_id=context.owner_principal_id
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
            grant_identity = hashlib.sha256(
                json.dumps(
                    {
                        "session_id": context.session_id,
                        "principal_id": context.owner_principal_id,
                        "commands": grant.get("commands", []),
                        "expires_at": grant.get("expires_at"),
                        "created_at": grant.get("created_at"),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            invocation: dict[str, Any] = dict(
                owner_principal_id=context.owner_principal_id,
                acting_principal_id=context.acting_principal_id,
                session_id=context.session_id,
                turn_id=context.turn_id,
                action_id=new_id("act_"),
                authority_kind="session_command_grant",
                authority_id=grant_identity,
                command=str(args.get("command", "")),
                argv=command,
                max_output_bytes=100_000,
            )
            if bool(args.get("background")):
                # BUG-194 — the same grant, the same allowlist, the same argv
                # policy. What differs is only that the turn does not wait: the
                # deadline becomes the background ceiling rather than the grant's
                # foreground one, and the run is observed through `process`.
                run = self.command_service.start(
                    **invocation,
                    timeout_seconds=_BACKGROUND_TIMEOUT_SECONDS,
                    background=True,
                )
                return {
                    "status": "success",
                    "run_id": run.run_id,
                    "state": run.state.value,
                    "background": True,
                    "next": "Use background_run with this run_id to poll, log, wait or kill.",
                }
            result = self.command_service.run_foreground(
                **invocation, timeout_seconds=float(grant["timeout_seconds"])
            )
        except (SandboxError, CommandServiceError) as exc:
            reason = exc.reason_code if isinstance(exc, CommandServiceError) else str(exc)
            return {"status": "failed", "error": {"type": reason}}
        return {"status": "success", **result}

    def _background_run(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        """Observe and control what `run_command` started in the background.

        Owner-scoped throughout: every call reads the durable run row through the
        owner's principal, so one session cannot poll, read or kill another
        owner's run even holding its id. The tool grants nothing — a run it can
        see is one the grant that started it already authorised.
        """
        action = str(args.get("action", "")).strip()
        if action not in {"list", "poll", "log", "wait", "kill", "input"}:
            return {"status": "denied", "error": {"type": "background_run_action_invalid"}}
        service = self.command_service
        owner = context.owner_principal_id
        # Every entry point reconciles first. A lapsed lease means the run's
        # supervisor is gone, and reporting it as "running" would be the exact
        # orphan this design exists to prevent.
        with contextlib.suppress(Exception):
            service.reconcile_leases(owner)
        if action == "list":
            runs = service.store.list_runs(owner, session_id=context.session_id, limit=25)
            return {
                "status": "success",
                "runs": [
                    {
                        "run_id": run.run_id,
                        "state": run.state.value,
                        "command": run.safe_display,
                        "exit_code": run.exit_code,
                        "started_at": run.started_at,
                    }
                    for run in runs
                ],
            }
        run_id = str(args.get("run_id", "")).strip()
        if not run_id:
            return {"status": "denied", "error": {"type": "background_run_id_required"}}
        try:
            if action == "poll":
                return {"status": "success", **service.poll(owner, run_id)}
            if action == "log":
                after = max(0, int(args.get("after") or 0))
                return {"status": "success", **service.read_log(owner, run_id, after=after)}
            if action == "wait":
                requested = float(args.get("timeout_seconds") or 30.0)
                timeout = min(300.0, max(1.0, requested))
                return {"status": "success", **service.wait(
                    owner, run_id, timeout_seconds=timeout
                )}
            if action == "input":
                data = args.get("input")
                if not isinstance(data, str) or not data:
                    return {"status": "denied", "error": {"type": "background_run_input_required"}}
                return {"status": "success", **service.send_input(owner, run_id, data)}
            run = service.stop(owner, run_id)
            return {"status": "success", "run_id": run.run_id, "state": run.state.value}
        except CommandServiceError as exc:
            return {"status": "failed", "error": {"type": exc.reason_code}}
        except (TypeError, ValueError):
            return {"status": "denied", "error": {"type": "background_run_argument_invalid"}}

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
            principal_id=context.owner_principal_id,
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
        # `objective` is a required contract field. This path and the approval
        # relay's `TaskManagementExecutor` are the two ways a model-proposed task
        # is created, so they must agree on what a title-only proposal means:
        # a task to do what its title says.
        objective = str(args.get("description", "")).strip() or title
        try:
            task = service.create_task(
                title=title,
                objective=objective,
                user_id=self.store.principal_user_id(context.owner_principal_id) if self.store else None,
                principal_id=context.acting_principal_id,
                scheduled_at=str(args["scheduled_at"]) if args.get("scheduled_at") else None,
                reminder_at=str(args["reminder_at"]) if args.get("reminder_at") else None,
                recurrence=str(args["recurrence"]) if args.get("recurrence") else None,
                project_id=str(args["project_id"]) if args.get("project_id") else None,
                start_immediately=False,
            )
        except ValueError as exc:
            return {"status": "failed", "error": {"type": str(exc)}}
        return {
            "status": "success",
            "receipt": {"kind": "task", "title": task.title, "href": "#/tasks", "label": "Review in Tasks"},
            "task_id": task.task_id,
        }

    def _execution_profiles(self) -> list[ExecutionProfile]:
        profiles = list_execution_profiles()
        if self.store is None:
            return profiles
        rows = self.store.list_remote_execution_profiles(
            enabled_only=True,
            owner_principal_id=self.owner_scope or self.principal_id,
        )
        profiles.extend(execution_profiles_from_rows(rows))
        return profiles

    def _execution_profile(self, tool_name: str) -> ProfileResolution:
        return resolve_tool_profile(tool_name, self._execution_profiles())

    def _assign_session_project(self, args: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        from raiker.control.dashboard import DashboardService

        project_id = str(args.get("project_id", "")).strip()
        if not project_id:
            return {"status": "failed", "error": {"type": "project_id_required"}}
        service = DashboardService(self.workspace_root)
        result = service.set_session_project(
            context.session_id, project_id, context.owner_principal_id
        )
        if not result.ok:
            return {"status": "failed", "error": {"type": result.reason_code}}
        project = self.store.load_project(
            project_id, user_id=self.store.principal_user_id(context.owner_principal_id)
        ) if self.store else None
        return {
            "status": "success",
            "receipt": {"kind": "project_assignment", "title": str(project.get("name")) if project else project_id, "href": "#/projects", "label": "Review in Projects"},
            "session_id": context.session_id,
        }

    # ── BUG-66: the repository the git tools work in ─────────────────────────

    def git_root(self) -> Path:
        """The repository the owner selected in Build, or the workspace root.

        Resolved per call rather than cached, because the owner can change the
        selection between turns and a cached answer would quietly commit into
        the repository they stopped working in.
        """
        return resolve_repository_root(
            self.workspace_root,
            # `code_repos` rows are keyed on the principal the API wrote them
            # under, which is the acting principal itself; `owner_scope` narrows
            # to it only once that principal names a real account.
            selected_repository_subpath(self.store, self.owner_scope or self.principal_id),
        )

    def _with_repository(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Name the repository a git proposal was computed against.

        A workspace can hold more than one, so the approval has to say which one
        the change lands in — otherwise the owner is approving a commit whose
        destination is an assumption.
        """
        snapshot["repository"] = repository_label(self.workspace_root, self.git_root())
        return snapshot

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
    ) -> str:
        """Append one event and return its id, or ``""`` when there is no log.

        The id is what MEM-04's observations point back at: an observation whose
        `source_event_id` names a real event can be opened at the moment it came
        from, and one that names nothing is a claim nobody can check.
        """
        if self.writer is None:
            return ""
        event = make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type=event_type,
            actor=actor,
            payload=payload,
            client=client,
        )
        self.writer.append(event)
        return event.event_id

    def _stream_tool(
        self,
        action: ToolAction,
        event_type: str,
        *,
        status: str,
        reason: str = "",
    ) -> None:
        """Put one tool call on the live stream (BUG-206 slices A and B).

        Emitted beside — never instead of — the durable event, and carrying
        strictly less: the family, the owner-language label, and the one short
        action phrase `raiker.tools.presentation` decided is safe to say. No
        arguments, no result, no output. The durable log stays the full record;
        this is the summary the owner watches arrive.
        """
        if self.stream_sink is None:
            return
        payload: dict[str, object] = {
            "action_id": action.action_id,
            **tool_row(action.tool_name, action.arguments).to_payload(),
            "status": status,
        }
        if reason:
            payload["reason"] = reason
        self.stream_sink.append(
            StreamEvent(kind=TOOL, event_type=event_type, payload=payload)
        )

    @staticmethod
    def _failure_reason(result: ToolResult) -> str:
        """The named reason a call failed, as the row will show it."""
        error = result.error if isinstance(result.error, dict) else {}
        reason = error.get("type")
        if isinstance(reason, str) and reason:
            return reason
        reasons = error.get("reasons")
        if isinstance(reasons, list) and reasons and isinstance(reasons[0], str):
            return reasons[0]
        return ""

    def _capture_observation(
        self,
        action: ToolAction,
        result: ToolResult,
        *,
        source_event_id: str,
        session_id: str,
        turn_id: str | None,
        owner_principal_id: str,
    ) -> None:
        """MEM-04 — one eidetic observation per governed tool result.

        Best-effort by construction. An observation is a record *about* the
        work; a tool call that succeeded must not be reported as failed because
        the bookkeeping for it did not land. What a failure costs is one row,
        and the tool result the model receives is untouched either way.
        """
        if self.store is None or not source_event_id or not owner_principal_id:
            return
        try:
            capture_tool_observation(
                self.store,
                tool_name=action.tool_name,
                arguments=action.arguments,
                output=result.output,
                source_event_id=source_event_id,
                session_id=session_id,
                turn_id=turn_id or "",
                owner_principal_id=owner_principal_id,
            )
        except Exception:  # noqa: BLE001 — see the docstring; never fails the call
            self._event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="eidetic_observation_skipped",
                actor="tool_broker",
                payload={
                    "action_id": action.action_id,
                    "tool_name": action.tool_name,
                    "reason": "eidetic_capture_failed",
                },
                client=None,
            )

    def _stream_tool_result(self, action: ToolAction, result: ToolResult) -> None:
        """The settled half of a row, from the result the broker just produced."""
        if result.status == "success":
            self._stream_tool(action, "tool_completed", status="success")
            return
        self._stream_tool(
            action,
            "tool_failed",
            status="denied" if result.status == "denied" else "failed",
            reason=self._failure_reason(result),
        )

    def _unperformable_proposal(
        self,
        action: ToolAction,
        preview: dict[str, Any],
        decision: Any,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
        sanitized_action: ToolAction,
        now: str,
    ) -> tuple[ToolResult, Any]:
        """Answer a proposal the runtime already knows it cannot honour.

        The refusal the snapshot computed is returned verbatim, so the model gets
        the same machine-readable reason an execution would have produced and no
        approval row is created for a decision that has no effect either way.
        """
        failed = ToolResult(
            action_id=action.action_id,
            tool_name=action.tool_name,
            status="failed",
            output=None,
            error=preview.get("error", {"type": "proposal_unperformable"}),
            started_at=now,
            completed_at=utc_now(),
        )
        if self.store is not None:
            self.store.insert_tool_action(sanitized_action, session_id, turn_id, failed.status)
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_failed",
            actor="tool_broker",
            payload=self._event_safe_result_payload(failed),
            client=client,
        )
        # A proposal the runtime already knows it cannot honour never reaches
        # `tool_started`, so its row is opened and settled by this one event.
        self._stream_tool_result(action, failed)
        self._notify_hook(
            "PostToolUse",
            action,
            session_id=session_id,
            turn_id=turn_id,
            client=client,
            context={"status": failed.status},
        )
        return failed, decision

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
        if action.tool_name == "git_branch":
            return self._with_repository(
                proposed_branch_snapshot(
                    self.git_root(),
                    str(action.arguments.get("name", "")),
                    str(action.arguments["base"]) if action.arguments.get("base") else None,
                )
            )
        if action.tool_name == "git_commit":
            return self._with_repository(
                proposed_commit_snapshot(
                    self.git_root(),
                    str(action.arguments.get("message", "")),
                    action.arguments.get("paths"),
                )
            )
        if action.tool_name == "git_push":
            return self._with_repository(
                proposed_push_snapshot(
                    self.git_root(),
                    str(action.arguments["remote"]) if action.arguments.get("remote") else None,
                    str(action.arguments["branch"]) if action.arguments.get("branch") else None,
                )
            )
        if action.tool_name == "apply_patch":
            try:
                return proposed_patch_snapshot(
                    self.workspace_root,
                    str(action.arguments["path"]) if action.arguments.get("path") else None,
                    str(action.arguments.get("patch", "")),
                )
            except FilesystemSafetyError as exc:
                return {"status": "failed", "error": {"type": str(exc)}}
        # BUG-71 — a memory decision is a decision about *text*. The owner has to
        # read the exact sentence that would be kept (or the record that would
        # go) before approving, so the preview carries it rather than only the
        # tool's name.
        if action.tool_name == "memory_write":
            text = str(action.arguments.get("text", "")).strip()
            if not text:
                return {"status": "failed", "error": {"type": "empty_text"}}
            from raiker.memory.policy import (
                MemorySensitivity,
                classify_memory_sensitivity,
            )

            sensitivity = classify_memory_sensitivity(text)
            if sensitivity in {
                MemorySensitivity.CREDENTIAL_LIKE,
                MemorySensitivity.SECRET_LIKE,
            }:
                # Refused before the owner is asked: approving a credential into
                # durable storage is not a decision Raiker offers.
                return {
                    "status": "failed",
                    "error": {
                        "type": "secret_or_credential_like_memory_blocked",
                        "sensitivity": sensitivity.value,
                    },
                }
            return {
                "status": "success",
                "text": str(self._redact_value(text)),
                "scope": str(action.arguments.get("scope", "project")),
                "memory_type": str(action.arguments.get("memory_type", "project")),
                "sensitivity": sensitivity.value,
            }
        if action.tool_name == "memory_forget":
            memory_id = str(action.arguments.get("memory_id", "")).strip()
            if not memory_id:
                return {"status": "failed", "error": {"type": "missing_memory_id"}}
            from raiker.memory.store import get_memory

            try:
                existing = get_memory(
                    memory_id,
                    workspace_root=self.workspace_root,
                    owner_principal_id=self.owner_scope or self.principal_id,
                )
            except Exception:  # noqa: BLE001 — an unreadable record is "not found"
                existing = None
            if existing is None:
                return {"status": "failed", "error": {"type": "memory_not_found"}}
            return {
                "status": "success",
                "memory_id": memory_id,
                "text": str(self._redact_value(existing.text)),
                "scope": existing.scope,
            }
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
                if action.tool_name == "shell":
                    return "Approving executes this exact bounded shell command once."
                # BUG-62 — neither planning mutation has a path, and describing
                # one as a write to "the proposed path" was how this sentence
                # would have started lying the moment they became executable.
                if action.tool_name == "create_task":
                    return (
                        "Creates one task in Tasks. It will wait until you run or "
                        "schedule it."
                    )
                if action.tool_name == "assign_session_project":
                    return "Approving moves this conversation into the named project, once."
                # BUG-71 — memory writes nothing to the filesystem, so the file
                # sentence below would have named a path that does not exist.
                if action.tool_name == "memory_write":
                    scope = str(action.arguments.get("scope", "project"))
                    return (
                        f"Approving stores this exact text as a durable {scope} memory, "
                        "once. You can remove it later from Memory."
                    )
                if action.tool_name == "memory_forget":
                    return "Approving deletes this exact memory record, once."
                # B11 — none of the three writes a path, and the file sentence
                # below would have named one that does not exist. Each says the
                # thing it actually changes.
                if action.tool_name == "git_branch":
                    name = str(self._redact_value(str(action.arguments.get("name", ""))))
                    return (
                        f"Approving creates the branch “{name}” and checks it out, once."
                        if name
                        else "Approving creates and checks out this branch, once."
                    )
                if action.tool_name == "git_commit":
                    return (
                        "Approving records this exact change set as one commit on the "
                        "current branch, once."
                    )
                # BUG-67 — a push is the one git write that leaves the machine,
                # so the sentence says where it goes rather than what it records.
                if action.tool_name == "git_push":
                    snapshot = self._approval_preview(action) or {}
                    if snapshot.get("status") == "success":
                        return (
                            f"Approving sends {snapshot['commit_count']} commit(s) on "
                            f"{snapshot['branch']} to {snapshot['remote']} "
                            f"({snapshot['host']}) with your own credential, once."
                        )
                    return (
                        "Approving sends this branch to the named remote with your own "
                        "credential, once."
                    )
                if action.tool_name == "github_write":
                    repo = str(self._redact_value(str(action.arguments.get("repo", ""))))
                    operation = str(action.arguments.get("operation", ""))
                    noun = (
                        "pull request"
                        if operation == "create_pull_request"
                        else "comment" if operation == "create_comment" else "write"
                    )
                    return (
                        f"Approving sends this exact {noun} to {repo} on GitHub, once."
                        if repo
                        else f"Approving sends this exact GitHub {noun}, once."
                    )
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

    @staticmethod
    def _turn_capability_mode(
        action: ToolAction, turn_capability_modes: Mapping[str, str] | None
    ) -> str | None:
        """The posture this *turn* set for the capability behind ``action``.

        Returns None when the turn named no posture for it, which is the common
        case: a turn-scoped map covers only the capabilities the surface's mode
        is about, and everything else keeps the owner's standing decision mode
        untouched.
        """
        if not turn_capability_modes:
            return None
        from raiker.runtime.authority.router import CAPABILITY_GATE_MAP

        capability = CAPABILITY_GATE_MAP.get(action.tool_name)
        if capability is None:
            return None
        mode = turn_capability_modes.get(capability)
        # Only the two tightening modes are honoured here. The envelope already
        # rejects anything else; this is the second, independent refusal so a
        # caller that reaches the broker directly cannot loosen a turn either.
        return mode if mode in {"ask", "deny"} else None

    def _turn_posture_deny_decision(
        self, action: ToolAction, base: PolicyDecision
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="deny",
            # Named distinctly from `denied_by_decision_mode` so an audit reader
            # can tell "the owner denied this capability" from "this turn was
            # running in a mode that writes nothing".
            reasons=["denied_by_turn_posture", *base.reasons],
            requires_user_approval=False,
            risk_level="blocked",
            timestamp=utc_now(),
        )

    def _turn_posture_ask_decision(
        self, action: ToolAction, base: PolicyDecision
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="needs_approval",
            reasons=["turn_posture_requires_approval", *base.reasons],
            requires_user_approval=True,
            risk_level="high",
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
        if self.store is None:
            return None
        raw_principal = self.store.get_principal(action.proposed_by)
        if raw_principal is None:
            return None
        from raiker.runtime.authority.models import Principal

        principal = Principal(**raw_principal)

        preview = self._approval_preview(action) if approval_mode == "auto" else None
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_started",
            actor="tool_broker",
            payload={"action_id": action.action_id, "tool_name": action.tool_name},
            client=client,
        )
        self._stream_tool(action, "tool_started", status="running")
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
            # This path is reached only after the broker has proved the action is
            # ordinary and the owner selected auto/skip for this turn.
            decision_mode_override="always_allow",
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
            self._stream_tool_result(action, failed)
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
        self._stream_tool_result(action, result)
        self._notify_hook(
            "PostToolUse",
            action,
            session_id=session_id,
            turn_id=turn_id,
            client=client,
            context={"status": result.status, "approval_mode": approval_mode},
        )
        return result, executed_decision

    def _identity_refusal(
        self,
        action: ToolAction,
        *,
        reason_code: str,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
        now: str,
    ) -> tuple[ToolResult, PolicyDecision]:
        decision = PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="deny",
            reasons=[reason_code],
            requires_user_approval=False,
            risk_level=action.risk_level,
            timestamp=now,
        )
        result = ToolResult(
            action_id=action.action_id,
            tool_name=action.tool_name,
            status="denied",
            output=None,
            error={"type": reason_code},
            started_at=now,
            completed_at=utc_now(),
        )
        self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="machine_identity_refused",
            actor="tool_broker",
            payload={
                "action_id": action.action_id,
                "tool_name": action.tool_name,
                "reason_code": reason_code,
            },
            client=client,
        )
        return result, decision

    def execute(
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
        machine_identity: TrustedTurnIdentity | None = None,
        client: ClientMetadata | None = None,
        approval_mode: str = "manual",
        turn_capability_modes: Mapping[str, str] | None = None,
    ) -> tuple[ToolResult, PolicyDecision]:
        now = utc_now()
        if machine_identity is None:
            return self._identity_refusal(
                action,
                reason_code="machine_identity_missing",
                session_id=session_id,
                turn_id=turn_id,
                client=client,
                now=now,
            )
        identity_store = self.store or SQLiteStore(self.workspace_root)
        expected_owner = self.owner_scope or self.principal_id
        try:
            verified = MachineIdentityVerifier(
                self.workspace_root, identity_store
            ).verify(
                machine_identity.token,
                expected_owner_principal_id=expected_owner,
                expected_session_id=session_id,
                expected_turn_id=turn_id or "",
                expected_audience=IDENTITY_AUDIENCE,
            )
        except MachineIdentityError as exc:
            return self._identity_refusal(
                action,
                reason_code=exc.reason_code,
                session_id=session_id,
                turn_id=turn_id,
                client=client,
                now=now,
            )
        action = ToolAction(
            action_id=action.action_id,
            tool_name=action.tool_name,
            arguments=action.arguments,
            risk_level=action.risk_level,
            requires_approval=action.requires_approval,
            proposed_by=verified.claims.principal_id,
        )
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
            self.store.insert_tool_action(
                sanitized_action,
                session_id,
                turn_id,
                "proposed",
                owner_principal_id=verified.claims.owner_principal_id,
                machine_subject=verified.claims.subject,
                machine_token_id=verified.claims.token_id,
                machine_key_id=verified.claims.key_id,
                machine_issued_at=verified.claims.issued_at,
                machine_expires_at=verified.claims.expires_at,
            )
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
        # BUG-70 — the turn's own posture, applied after policy and only ever in
        # the tightening direction. This is what Build's Plan and Edit chips now
        # do instead of rewriting four standing permissions: Plan denies the
        # write capabilities for *this turn*, Edit forces each one to a decision,
        # and neither touches what the owner set in Permissions.
        turn_mode = self._turn_capability_mode(action, turn_capability_modes)
        if turn_mode == "deny" and decision.decision != "deny":
            decision = self._turn_posture_deny_decision(action, decision)
        elif turn_mode == "ask":
            if decision.decision == "allow":
                decision = self._turn_posture_ask_decision(action, decision)
            # An `ask` the owner set for this turn is a request to *see* the
            # decision, so the unattended approval modes must not swallow it —
            # including when policy had already routed the call to approval.
            approval_mode = "manual"
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
            # BUG-67 — a proposal whose own precondition check already failed is
            # not a decision, it is a refusal. Raising an approval for it asks
            # the owner to weigh an action the runtime has already established it
            # will not perform, and only tells them after they approved. The
            # named reason goes back to the model instead, which is what lets it
            # correct the call rather than wait on a person.
            if isinstance(proposal_preview, dict) and proposal_preview.get("status") == "failed":
                return self._unperformable_proposal(
                    action,
                    proposal_preview,
                    decision,
                    session_id=session_id,
                    turn_id=turn_id,
                    client=client,
                    sanitized_action=sanitized_action,
                    now=now,
                )
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
                        # B11 — the repository's own history, which no file-level
                        # checkpoint rewinds.
                        "repository": action.tool_name in {"git_branch", "git_commit", "git_push", "github_write"},
                        "memory": action.tool_name in {"memory_write", "memory_forget"},
                        "network": action.tool_name in {"shell", "remote_execute", "cloud_execute", "connector_write", "github_write", "git_push"},
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
        self._stream_tool(action, "tool_started", status="running")
        context_executor = self.context_executors.get(action.tool_name)
        raw: dict[str, Any]
        profile_resolution = self._execution_profile(action.tool_name)
        if profile_resolution.reason_code is not None:
            raw = {
                "status": "failed",
                "error": {"type": profile_resolution.reason_code},
            }
        elif (
            profile_resolution.profile is not None
            and profile_resolution.profile.kind == "container"
        ):
            raw = ContainerToolExecutor(
                self.workspace_root, profile_resolution.profile
            ).execute(action.tool_name, action.arguments, action.action_id)
        elif executor is None and context_executor is None and is_mcp_tool(action.tool_name):
            raw = self._mcp_call(action)
        elif executor is None and context_executor is None:
            if action.tool_name == "memory_write":
                raw = self.memory_service.write_from_action(
                    action,
                    decision,
                    session_id=session_id,
                    turn_id=turn_id,
                    client=client,
                    owner_principal_id=verified.claims.owner_principal_id,
                )
            elif action.tool_name == "memory_forget":
                raw = self.memory_service.forget_from_action(
                    action,
                    decision,
                    session_id=session_id,
                    turn_id=turn_id,
                    client=client,
                    owner_principal_id=verified.claims.owner_principal_id,
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
                self._stream_tool_result(action, failed)
                return failed, decision
        else:
            try:
                if context_executor is not None:
                    raw = context_executor(
                        action.arguments,
                        ToolExecutionContext(
                            session_id=session_id,
                            turn_id=turn_id or "",
                            acting_principal_id=verified.claims.principal_id,
                            owner_principal_id=verified.claims.owner_principal_id,
                            verified_identity=machine_identity,
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
        result_event_id = self._event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="tool_completed" if result.status == "success" else "tool_failed",
            actor="tool_broker",
            payload=self._event_safe_result_payload(result),
            client=client,
        )
        if result.status == "success":
            self._capture_observation(
                action,
                result,
                source_event_id=result_event_id,
                session_id=session_id,
                turn_id=turn_id,
                owner_principal_id=verified.claims.owner_principal_id,
            )
        self._stream_tool_result(action, result)
        self._notify_hook(
            "PostToolUse" if result.status == "success" else "PostToolUseFailure",
            action,
            session_id=session_id,
            turn_id=turn_id,
            client=client,
            context={"status": result.status},
        )
        return result, decision
