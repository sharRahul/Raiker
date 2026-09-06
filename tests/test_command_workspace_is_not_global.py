"""GCR-06 — the workspace a command is validated against is the caller's to state.

`check_command_allowlist` used to read a module global that `run_command`
assigned immediately before calling it, and that the tool broker never assigned
at all. Two commands validating at once — two mounted instances, or one instance
with a background run in flight — read whichever root was written last, so a
path could be accepted for being inside a workspace it would never run in.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from raiker.runtime.command_policy import ALLOWED_SHELL_COMMANDS
from raiker.runtime.executors import sandbox
from raiker.runtime.executors.sandbox import SandboxError, check_command_allowlist


def test_the_module_global_is_gone() -> None:
    """The defect was the global itself, so its absence is the fix."""
    assert not hasattr(sandbox, "_COMMAND_WORKSPACE")
    assert not hasattr(sandbox, "set_command_workspace")
    assert not hasattr(sandbox, "_command_workspace")


def test_a_path_inside_the_stated_workspace_is_accepted(tmp_path: Path) -> None:
    inside = tmp_path / "notes.txt"
    inside.write_text("hello", encoding="utf-8")
    check_command_allowlist(
        ["cat", str(inside)], ALLOWED_SHELL_COMMANDS, workspace_root=tmp_path
    )


def test_a_path_outside_the_stated_workspace_is_refused(tmp_path: Path) -> None:
    other = tmp_path / "other"
    workspace = tmp_path / "workspace"
    other.mkdir()
    workspace.mkdir()
    (other / "secret.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(SandboxError):
        check_command_allowlist(
            ["cat", str(other / "secret.txt")],
            ALLOWED_SHELL_COMMANDS,
            workspace_root=workspace,
        )


def test_two_workspaces_validated_at_once_do_not_borrow_each_others_root(
    tmp_path: Path,
) -> None:
    """The race, run: each thread must be judged against its own workspace.

    With the global, the two `set_command_workspace` calls interleaved with the
    two validations, and a file inside workspace A could be accepted while the
    global held workspace B — or refused while it held A. Stating the root at
    the call site makes the outcome depend on nothing but the arguments.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a.txt").write_text("a", encoding="utf-8")
    (second / "b.txt").write_text("b", encoding="utf-8")

    verdicts: dict[str, list[bool]] = {"own": [], "other": []}
    lock = threading.Lock()
    start = threading.Barrier(2)

    def judge(root: Path, own: Path, other: Path) -> None:
        start.wait(timeout=10)
        for _ in range(60):
            own_ok = True
            other_ok = True
            try:
                check_command_allowlist(
                    ["cat", str(own)], ALLOWED_SHELL_COMMANDS, workspace_root=root
                )
            except SandboxError:
                own_ok = False
            try:
                check_command_allowlist(
                    ["cat", str(other)], ALLOWED_SHELL_COMMANDS, workspace_root=root
                )
            except SandboxError:
                other_ok = False
            with lock:
                verdicts["own"].append(own_ok)
                verdicts["other"].append(other_ok)

    threads = [
        threading.Thread(
            target=judge, args=(first, first / "a.txt", second / "b.txt")
        ),
        threading.Thread(
            target=judge, args=(second, second / "b.txt", first / "a.txt")
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    # Every path inside its own workspace was accepted, every path in the other
    # one refused, on every interleaving.
    assert verdicts["own"] and all(verdicts["own"])
    assert verdicts["other"] and not any(verdicts["other"])


def test_run_command_validates_against_its_own_cwd(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(SandboxError):
        sandbox.run_command(
            ["cat", str(outside / "secret.txt")],
            allowlist=ALLOWED_SHELL_COMMANDS,
            cwd=workspace,
        )


def test_no_workspace_still_means_the_process_directory(tmp_path: Path) -> None:
    """`None` keeps its old meaning, now as a stated choice rather than a default."""
    with pytest.raises(SandboxError):
        check_command_allowlist(
            ["cat", str(tmp_path / "elsewhere.txt")],
            ALLOWED_SHELL_COMMANDS,
            workspace_root=None,
        )


def test_the_workspace_argument_is_required(tmp_path: Path) -> None:
    """A caller cannot forget it and silently inherit somebody else's root."""
    with pytest.raises(TypeError):
        check_command_allowlist(["cat", "x"], ALLOWED_SHELL_COMMANDS)  # type: ignore[call-arg]
