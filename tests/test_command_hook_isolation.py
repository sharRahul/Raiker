"""Workspace command hooks cannot bypass the native process boundary."""

import subprocess
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
    assert not launches
