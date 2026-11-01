"""Workspace command hooks cannot bypass the native process boundary."""

import subprocess
import sys
from pathlib import Path

import pytest

from raiker.hooks.contracts import HookHandler, HookInput
from raiker.hooks.handlers.command import CommandHookError, run_command


def test_command_hook_does_not_start_host_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "hook"
    script.write_text("untrusted hook")
    launches: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        launches.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    handler = HookHandler(id="test", type="command", command=["hook"])
    with pytest.raises(CommandHookError, match="native_sandbox_required"):
        run_command(handler, HookInput(event_name="PreToolUse"), tmp_path)
    # Only the boundary's own probe may start; the hook never runs on the host.
    assert all(Path(argv[0]).stem == "raiker-command-runner" for argv in launches)
    assert not any(str(script) in argv for argv in launches)


def _real_boundary(workspace: Path) -> bool:
    from raiker.execution.commands.backends.native import NativeSandboxDriver

    return NativeSandboxDriver(workspace).probe().available


DENY = '{"decision":"deny","decision_reason":"sandboxed"}'
LEAK = '{"decision":"allow","decision_reason":"leaked"}'


def test_a_hook_runs_in_the_sandbox_and_cannot_see_the_project(tmp_path: Path) -> None:
    """Real boundary: the hook decides from its event; the project is out of reach."""
    workspace = tmp_path / "ws"
    (workspace / ".raiker").mkdir(parents=True)
    if not _real_boundary(workspace):
        pytest.skip("no enforced native boundary on this host")
    secret = workspace / "secret.txt"
    secret.write_text("project secret", encoding="utf-8")
    if sys.platform == "win32":
        script = workspace / "hook.cmd"
        script.write_text(
            f'@echo off\r\nif exist "{secret}" (echo {LEAK}) else (echo {DENY})\r\n',
            encoding="utf-8",
        )
    else:
        script = workspace / "hook.sh"
        script.write_text(
            f"#!/bin/sh\nread -r event\nif [ -e '{secret}' ]; then echo '{LEAK}'; else echo '{DENY}'; fi\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
    output = run_command(
        HookHandler(id="real", type="command", command=[script.name], timeout_ms=30_000),
        HookInput(event_name="PreToolUse", tool_name="write_file"),
        workspace,
    )
    assert (output.decision, output.decision_reason) == ("deny", "sandboxed")
