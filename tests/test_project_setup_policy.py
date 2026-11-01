"""Project setup in a task copy: the commands it needs, and what it leaves out.

A copy is set up with the project's own tools (a virtualenv and pip, npm,
Cargo). Those commands are allowed exactly, and the folders they fill are the
task's environment: never copied from the project, never in the change set.
"""

from pathlib import Path

import pytest

from raiker.execution.workspaces import create_task_workspace, diff_workspace
from raiker.runtime.command_policy import ALLOWED_SHELL_COMMANDS, CommandRejected, validate_command


def _decide(argv: list[str], tmp_path: Path) -> str:
    try:
        validate_command(argv, workspace_root=tmp_path, allowlist=ALLOWED_SHELL_COMMANDS)
    except CommandRejected as refused:
        return refused.reason_code
    return "ok"


@pytest.mark.parametrize(
    "argv",
    [
        ["python", "-m", "venv", ".venv"],
        ["python", "-mvenv", ".venv"],
        [".venv/bin/python", "-m", "pip", "install", "-r", "requirements.txt"],
        ["python", "-I", "-m", "pytest", "-c", "setup.cfg"],
        ["python", "-W", "error", "-m", "unittest"],
        ["python", "check.py", "-c", "config"],
        ["npm", "ci"],
        ["cargo", "build", "--release"],
        ["cargo", "test"],
    ],
)
def test_setting_up_and_testing_a_project_is_allowed(argv: list[str], tmp_path: Path) -> None:
    assert _decide(argv, tmp_path) == "ok"


@pytest.mark.parametrize(
    ("argv", "reason"),
    [
        (["python", "-c", "x"], "command_flag_denied:python -c"),
        (["python", "-cimport os"], "command_flag_denied:python -c"),
        (["python", "-Ic", "x"], "command_flag_denied:python -c"),
        (["python", "-Werror", "-c", "x"], "command_flag_denied:python -c"),
        (["python", "-m", "http.server"], "command_module_denied:python -m http.server"),
        (["python", "-mhttp.server"], "command_module_denied:python -m http.server"),
        (["cargo", "install", "ripgrep"], "command_subcommand_denied:cargo install"),
        (["cargo", "+nightly", "build"], "command_subcommand_denied:cargo +nightly"),
        (["cargo", "build", "--config", "x=1"], "command_flag_denied:cargo --config"),
    ],
)
def test_other_code_and_other_cargo_commands_are_refused(
    argv: list[str], reason: str, tmp_path: Path
) -> None:
    assert _decide(argv, tmp_path) == reason


def test_a_toolchains_folders_are_neither_copied_nor_promoted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "app.py").write_text("print('app')\n", encoding="utf-8")
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / ".venv" / "bin" / "python").write_text("venv", encoding="utf-8")
    (project / "web" / "node_modules" / "left-pad").mkdir(parents=True)
    (project / "web" / "node_modules" / "left-pad" / "index.js").write_text("x", encoding="utf-8")
    (project / "crate").mkdir()
    (project / "crate" / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    (project / "crate" / "target" / "debug").mkdir(parents=True)
    (project / "crate" / "target" / "debug" / "bin").write_text("x", encoding="utf-8")
    (project / "docs" / "target").mkdir(parents=True)
    (project / "docs" / "target" / "page.md").write_text("kept", encoding="utf-8")

    workspace = create_task_workspace(project, tmp_path / "copies", "setup")
    assert set(workspace.manifest) == {"src/app.py", "crate/Cargo.toml", "docs/target/page.md"}

    # Setting the copy up fills the same folders, and home caches at its top.
    (workspace.root / ".venv" / "lib").mkdir(parents=True)
    (workspace.root / ".venv" / "lib" / "site.py").write_text("x", encoding="utf-8")
    (workspace.root / "web" / "node_modules" / "react").mkdir(parents=True)
    (workspace.root / "web" / "node_modules" / "react" / "index.js").write_text("x", encoding="utf-8")
    (workspace.root / ".cache" / "pip").mkdir(parents=True)
    (workspace.root / ".cache" / "pip" / "wheel").write_text("x", encoding="utf-8")
    (workspace.root / "src" / "__pycache__").mkdir()
    (workspace.root / "src" / "__pycache__" / "app.pyc").write_text("x", encoding="utf-8")
    (workspace.root / "src" / "new.py").write_text("print('new')\n", encoding="utf-8")

    diff = diff_workspace(workspace)
    assert diff.created == ("src/new.py",)
    assert not diff.modified and not diff.deleted and not diff.rejected


def test_a_real_copy_gets_its_own_virtualenv_and_promotes_none_of_it(tmp_path: Path) -> None:
    """Real boundary: `python -m venv` and the venv's pip run in the copy."""
    import sys
    import time

    from raiker.contracts.ids import utc_now
    from raiker.execution.commands.backends.native import (
        NativeSandboxDriver,
        task_workspace_registry,
    )
    from raiker.execution.commands.service import CommandService
    from raiker.execution.profiles import ProfileProbe

    project = tmp_path / "project"
    (project / ".raiker").mkdir(parents=True)
    (project / "app.py").write_text("print('app')\n", encoding="utf-8")
    if not NativeSandboxDriver(project).probe().available:
        pytest.skip("no enforced native boundary on this host")
    service = CommandService(
        project, profile_probe=lambda profile: ProfileProbe(profile, True, None, utc_now())
    )
    owner, session = "owner_setup", "sess_setup"

    def run(argv: list[str]) -> dict[str, object]:
        started = service.start(
            owner_principal_id=owner, acting_principal_id="agent_setup", session_id=session,
            turn_id="turn_setup", action_id=f"act_{len(argv)}_{time.monotonic_ns()}",
            authority_kind="session_command_grant", authority_id="grant_setup",
            command="", argv=argv, timeout_seconds=120.0,
        )
        deadline = time.monotonic() + 150
        while service.poll(owner, started.run_id)["running"]:
            assert time.monotonic() < deadline, "the run never finished"
            time.sleep(0.1)
        return service.poll(owner, started.run_id)

    interpreter = "python" if sys.platform == "win32" else "python3"
    venv_python = ".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python"
    try:
        made = run([interpreter, "-m", "venv", ".venv"])
        assert made["state"] == "succeeded", made
        pip = run([venv_python, "-m", "pip", "--version"])
        assert pip["state"] == "succeeded", pip
        [(_, copy)] = task_workspace_registry(project).session_copies(owner, session)
        assert (copy.root / venv_python).exists()
        assert not (project / ".venv").exists()
        diff = diff_workspace(copy)
        assert not diff.created and not diff.modified and not diff.deleted
    finally:
        service.shutdown()
