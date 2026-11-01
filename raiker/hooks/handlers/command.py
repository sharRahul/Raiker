from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from raiker.hooks.contracts import HookHandler, HookInput, HookOutput
from raiker.tools.filesystem import FilesystemSafetyError, resolve_workspace_path

_MAX_OUTPUT_CHARS = 10_000


class CommandHookError(ValueError):
    pass


class CommandHookTimeout(TimeoutError):
    pass


def _resolve_program(workspace_root: str | Path, program: str) -> Path:
    """A command hook runs a workspace-local script, never an arbitrary binary."""
    try:
        resolved = resolve_workspace_path(workspace_root, program)
    except FilesystemSafetyError as exc:
        raise CommandHookError(f"command_outside_workspace:{program}") from exc
    if not resolved.is_file():
        raise CommandHookError(f"command_not_found:{program}")
    return resolved


def run_command(
    handler: HookHandler, hook_input: HookInput, workspace_root: str | Path
) -> HookOutput:
    """Run the hook's script in the native sandbox, the event on its stdin.

    The script runs alone in a throwaway folder with no network: it can read
    the event it is handed and decide, but it cannot read or change the
    project, Raiker's state or anything else on the machine. Where the host's
    boundary is not enforced the hook is refused (``native_sandbox_required``),
    never run on the host; an enforcing hook that cannot run still needs the
    owner's decision.
    """
    from raiker.execution.commands.backends.base import CommandBackendError  # noqa: PLC0415
    from raiker.execution.commands.backends.native import run_sandboxed_program  # noqa: PLC0415

    assert handler.command is not None  # guaranteed by HookHandler validation
    program = _resolve_program(workspace_root, handler.command[0])
    payload = json.dumps(
        {
            "event_name": hook_input.event_name,
            "tool_name": hook_input.tool_name,
            "tool_input": hook_input.tool_input,
            "context": hook_input.context,
        }
    )
    try:
        completed = run_sandboxed_program(
            workspace_root,
            program,
            [*handler.command[1:], *handler.args],
            stdin=payload,
            timeout_seconds=handler.timeout_ms / 1000,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandHookTimeout(f"hook_timeout:{handler.id}") from exc
    except CommandBackendError as exc:
        raise CommandHookError("native_sandbox_required") from exc
    except OSError as exc:
        raise CommandHookError(f"hook_exec_failed:{exc}") from exc
    if completed.returncode == 91 and "raiker_runner_error" in completed.stderr:
        # The boundary itself refused; that is not the hook's verdict.
        raise CommandHookError("native_sandbox_required")
    return _parse_output(completed.stdout, completed.stderr, completed.returncode)


def _parse_output(stdout: str, stderr: str, returncode: int) -> HookOutput:
    text = (stdout or "")[:_MAX_OUTPUT_CHARS]
    decoded = _maybe_json(text)
    if isinstance(decoded, dict) and "decision" in decoded:
        return HookOutput(
            decision=str(decoded.get("decision", "no_decision")),
            decision_reason=_opt_str(decoded.get("decision_reason")),
            additional_context=_opt_str(decoded.get("additional_context")),
            metadata=decoded.get("metadata", {}) if isinstance(decoded.get("metadata"), dict) else {},
        )
    # No structured decision: use the exit-code convention (non-zero blocks the action).
    if returncode != 0:
        reason = (stderr or text or f"exit_{returncode}").strip()[:500]
        return HookOutput(decision="deny", decision_reason=reason)
    return HookOutput(decision="no_decision")


def _maybe_json(text: str) -> Any:
    snippet = text.strip()
    if not snippet:
        return None
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def _opt_str(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None
