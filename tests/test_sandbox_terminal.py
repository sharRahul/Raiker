"""A sandboxed command with a terminal, through the real boundary.

Runs where this host's native sandbox is enforced (CI's Linux and Windows
jobs set it up; elsewhere it is skipped): an interactive run is started, sees
a terminal, prompts, and answers what is typed into it. On Windows the
sandbox account's runner builds the pseudo-console as the account; on Linux
and macOS the terminal is the one Raiker opened.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROGRAM = (
    "import os; print('tty', os.isatty(0), os.isatty(1), flush=True); "
    "print('got', input('name? '), flush=True)"
)


def test_an_interactive_run_has_a_terminal_and_answers_what_is_typed(tmp_path: Path) -> None:
    from raiker.contracts.ids import utc_now
    from raiker.execution.commands.backends.native import NativeSandboxDriver
    from raiker.execution.commands.service import CommandService
    from raiker.execution.profiles import ProfileProbe

    project = tmp_path / "project"
    (project / ".raiker").mkdir(parents=True)
    (project / "prompt.py").write_text(PROGRAM + "\n", encoding="utf-8")
    proof = NativeSandboxDriver(project).probe()
    if not proof.available or not proof.features.pty:
        pytest.skip("no enforced native boundary with terminals on this host")
    service = CommandService(
        project, profile_probe=lambda profile: ProfileProbe(profile, True, None, utc_now())
    )
    owner = "owner_terminal"
    interpreter = "python" if sys.platform == "win32" else "python3"
    try:
        started = service.start(
            owner_principal_id=owner, acting_principal_id="agent_terminal",
            session_id="sess_terminal", turn_id="turn_terminal", action_id="act_terminal",
            authority_kind="session_command_grant", authority_id="grant_terminal",
            command="", argv=[interpreter, "prompt.py"], timeout_seconds=60.0,
            interactive=True,
        )

        def output() -> str:
            chunks = service.store.read_output(owner, started.run_id, after=0)
            return "".join(str(getattr(chunk, "text", "")) for chunk in chunks)

        deadline = time.monotonic() + 60
        # The prompt itself has no newline, so the output redactor may hold it
        # back until more arrives; the first line says the program is waiting.
        while "tty " not in output():
            assert time.monotonic() < deadline, output()
            time.sleep(0.1)
        # A console takes Enter as a carriage return; a POSIX terminal maps it.
        service.send_input(owner, started.run_id, "raiker-typed\r")
        while service.poll(owner, started.run_id)["running"]:
            assert time.monotonic() < deadline, output()
            time.sleep(0.1)
        text = output()
        assert "tty True True" in text, text
        assert "got raiker-typed" in text, text
    finally:
        service.shutdown()
