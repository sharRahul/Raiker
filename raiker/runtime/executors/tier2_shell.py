from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class ShellExecutor:
    capability = "shell_execution"

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        command_service: CommandService | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._commands = command_service or CommandService.for_workspace(self._workspace_root)

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        command: list[str] = list(action.arguments.get("command", []))
        if not command:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:command",
                summary="Shell execution denied: no command provided.",
            )
        timeout = float(action.arguments.get("timeout", 30))
        max_output = int(action.arguments.get("max_output_bytes", 100_000))
        if not action.authority_kind or not action.authority_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="command_authority_missing",
                summary="Shell execution denied: no approval or grant authority was bound.",
            )
        try:
            result = self._commands.run_foreground(
                owner_principal_id=principal.principal_id,
                acting_principal_id=principal.principal_id,
                session_id=action.origin_session_id or action.session_id,
                turn_id=action.turn_id or "turn_unavailable",
                action_id=action.action_id,
                authority_kind=action.authority_kind,
                authority_id=action.authority_id,
                command=" ".join(command),
                argv=command,
                timeout_seconds=timeout,
                max_output_bytes=max_output,
            )
        except CommandServiceError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=exc.reason_code,
                summary="Shell execution blocked by governed command lifecycle.",
            )
        return ExecutionResult(
            ok=result["returncode"] == 0,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if result["returncode"] == 0 else f"exit_code:{result['returncode']}",
            summary=f"Shell command exit {result['returncode']} ({result['stdout_bytes']}b out, {result['stderr_bytes']}b err).",
            artifacts={
                "returncode": result["returncode"],
                "stdout_bytes": result["stdout_bytes"],
                "stderr_bytes": result["stderr_bytes"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "run_id": result["run_id"],
                "receipt_digest": result["receipt_digest"],
                "truncated": result["truncated"],
            },
        )


class ProcessExecutor:
    capability = "process_execution"

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        command_service: CommandService | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._commands = command_service or CommandService.for_workspace(self._workspace_root)

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        executable = str(action.arguments.get("executable", "")).strip()
        args: list[str] = list(action.arguments.get("args", []))
        if not executable:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:executable",
                summary="Process execution denied: no executable provided.",
            )
        timeout = float(action.arguments.get("timeout", 60))
        max_output = int(action.arguments.get("max_output_bytes", 200_000))
        command = [executable, *args]
        if not action.authority_kind or not action.authority_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="command_authority_missing",
                summary="Process execution denied: no approval or grant authority was bound.",
            )
        try:
            result = self._commands.run_foreground(
                owner_principal_id=principal.principal_id,
                acting_principal_id=principal.principal_id,
                session_id=action.origin_session_id or action.session_id,
                turn_id=action.turn_id or "turn_unavailable",
                action_id=action.action_id,
                authority_kind=action.authority_kind,
                authority_id=action.authority_id,
                command=" ".join(command),
                argv=command,
                timeout_seconds=timeout,
                max_output_bytes=max_output,
            )
        except CommandServiceError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=exc.reason_code,
                summary="Process execution blocked by governed command lifecycle.",
            )
        return ExecutionResult(
            ok=result["returncode"] == 0,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if result["returncode"] == 0 else f"exit_code:{result['returncode']}",
            summary=f"Process exit {result['returncode']} ({result['stdout_bytes']}b out, {result['stderr_bytes']}b err).",
            artifacts={
                "returncode": result["returncode"],
                "stdout_bytes": result["stdout_bytes"],
                "stderr_bytes": result["stderr_bytes"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "run_id": result["run_id"],
                "receipt_digest": result["receipt_digest"],
                "truncated": result["truncated"],
            },
        )
