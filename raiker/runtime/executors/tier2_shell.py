from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import ALLOWED_SHELL_COMMANDS, SandboxError, run_command

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class ShellExecutor:
    capability = "shell_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

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
        try:
            result = run_command(
                command,
                timeout=timeout,
                max_output_bytes=max_output,
                allowlist=ALLOWED_SHELL_COMMANDS,
                cwd=self._workspace_root,
            )
        except SandboxError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=str(exc),
                summary="Shell execution blocked by sandbox.",
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
                "truncated": result["truncated"],
            },
        )


class ProcessExecutor:
    capability = "process_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

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
        try:
            result = run_command(
                command,
                timeout=timeout,
                max_output_bytes=max_output,
                allowlist=ALLOWED_SHELL_COMMANDS,
                cwd=self._workspace_root,
            )
        except SandboxError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=str(exc),
                summary="Process execution blocked by sandbox.",
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
                "truncated": result["truncated"],
            },
        )