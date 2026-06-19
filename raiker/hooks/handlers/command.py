from __future__ import annotations

import json
import os
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


def _minimal_env() -> dict[str, str]:
    # Command hooks run with a minimal environment so they cannot read process secrets.
    return {"PATH": os.environ.get("PATH", ""), "RAIKER_HOOK": "1"}


def _resolve_program(workspace_root: str | Path, program: str) -> Path:
    """Resolve a command-hook program to a real file inside the workspace.

    Command hooks may only run workspace-local scripts (e.g. ``.raiker/hooks/check.sh``). This
    blocks a hook config from invoking arbitrary system binaries and keeps the subprocess path
    inside the workspace boundary, reusing the filesystem path-safety helper.
    """

    try:
        resolved = resolve_workspace_path(workspace_root, program)
    except FilesystemSafetyError as exc:
        raise CommandHookError(f"command_outside_workspace:{program}") from exc
    if not resolved.exists() or not resolved.is_file():
        raise CommandHookError(f"command_not_found:{program}")
    return resolved


def run_command(
    handler: HookHandler, hook_input: HookInput, workspace_root: str | Path
) -> HookOutput:
    assert handler.command is not None  # guaranteed by HookHandler validation
    program = _resolve_program(workspace_root, handler.command[0])
    argv = [str(program), *handler.command[1:], *handler.args]
    payload = json.dumps(
        {
            "event_name": hook_input.event_name,
            "tool_name": hook_input.tool_name,
            "tool_input": hook_input.tool_input,
            "context": hook_input.context,
        }
    )
    try:
        completed = subprocess.run(
            argv,
            cwd=str(workspace_root),
            input=payload,
            capture_output=True,
            text=True,
            shell=False,
            env=_minimal_env(),
            timeout=handler.timeout_ms / 1000,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandHookTimeout(f"hook_timeout:{handler.id}") from exc
    except OSError as exc:
        raise CommandHookError(f"hook_exec_failed:{exc}") from exc
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
