"""BUG-40 — the lifecycle around ``raiker-app``: state, service, uninstall.

The three obligations from ``docs/architecture/DESKTOP_DISTRIBUTION_DESIGN.md`` that these
tests hold to: the host reports a state an owner can act on, background start is
registered with the *platform's own* manager rather than a Raiker daemon, and an
uninstall states what it takes before it takes it.

The per-platform definitions are asserted on every platform. That is the point:
a launchd plist generated on a Linux CI runner is exactly the artifact that would
be written on macOS, and a test that only ran on macOS would never notice it
break.
"""

from __future__ import annotations

import asyncio
import json
import plistlib
from pathlib import Path

import pytest

from raiker.app import host as host_module
from raiker.app.host import HostControl, process_is_alive
from raiker.app.service import (
    APP_LABEL,
    UNIT_NAME,
    WINDOWS_ENTRY,
    install,
    registration,
    service_plan,
    uninstall,
)
from raiker.app.uninstall import (
    apply_uninstall,
    directory_bytes,
    human_bytes,
    plan_uninstall,
    secure_erase,
)
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

# ── host state ───────────────────────────────────────────────────────────


def test_a_workspace_with_no_host_reports_stopped(tmp_path: Path) -> None:
    status = HostControl(tmp_path).status()
    assert status.state == "stopped"
    assert status.pid is None
    assert "No Raiker host is running" in status.detail


def test_a_recorded_live_host_reports_running(tmp_path: Path) -> None:
    control = HostControl(tmp_path)
    control.record_start(pid=_this_process(), port=8765)
    status = control.status()
    assert status.state == "running"
    assert status.port == 8765


def test_a_record_whose_process_is_gone_is_not_reported_as_running(tmp_path: Path) -> None:
    """A crashed host must not send the owner to a URL nothing is listening on."""
    control = HostControl(tmp_path)
    control.record_start(pid=_dead_pid(), port=8765)
    assert control.status().state == "stopped"


def test_an_unreadable_record_is_treated_as_no_host(tmp_path: Path) -> None:
    control = HostControl(tmp_path)
    control.state_dir.mkdir(parents=True, exist_ok=True)
    control.record_path.write_text("{ not json", encoding="utf-8")
    assert control.status().state == "stopped"


def test_pause_and_resume_round_trip(tmp_path: Path) -> None:
    control = HostControl(tmp_path)
    control.record_start(pid=_this_process(), port=8765)

    state = control.pause("stepping away")
    assert state.paused and state.reason == "stepping away"
    assert control.is_paused()
    status = control.status()
    assert status.state == "paused"
    assert status.detail == "New background work is not being started."

    control.resume()
    assert not control.is_paused()
    assert control.status().state == "running"


def test_a_run_waiting_on_an_approval_makes_the_host_need_attention(tmp_path: Path) -> None:
    """A tray reading "running" while every routine is blocked is a lie."""
    store = SQLiteStore(tmp_path)
    store.create_session("sess_inbox_principal_owner", str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id="sess_inbox_principal_owner", title="Nightly review", objective="Review",
    )
    store.update_task_status(task.task_id, "waiting_for_approval")

    control = HostControl(tmp_path)
    control.record_start(pid=_this_process(), port=8765)
    status = control.status()
    assert status.state == "needs attention"
    assert [item.kind for item in status.waiting] == ["blocked_task"]


def test_quitting_names_the_running_work_it_would_interrupt(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_inbox_principal_owner", str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id="sess_inbox_principal_owner", title="Long build", objective="Build",
    )
    store.update_task_status(task.task_id, "running")

    waiting = HostControl(tmp_path).waiting_work()
    assert [item.kind for item in waiting] == ["running_task"]
    assert waiting[0].label == "1 background run in flight"
    assert "safe boundary" in waiting[0].detail


def test_a_workspace_without_a_database_has_nothing_waiting(tmp_path: Path) -> None:
    assert HostControl(tmp_path).waiting_work() == []


def test_a_dead_pid_is_not_alive_and_a_live_one_is() -> None:
    assert process_is_alive(_this_process())
    assert not process_is_alive(_dead_pid())
    assert not process_is_alive(0)
    # A hand-edited or corrupted record must answer "not running", not raise.
    assert not process_is_alive(2**63)


def test_windows_liveness_probe_never_signals_the_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_module, "_IS_WINDOWS", True)
    monkeypatch.setattr(host_module, "_windows_process_is_alive", lambda pid: pid == 42)
    monkeypatch.setattr(
        host_module.os,
        "kill",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Windows probe sent a signal")),
    )

    assert process_is_alive(42)
    assert not process_is_alive(43)


# ── pause really stops new background work ───────────────────────────────


def test_a_paused_host_does_not_claim_due_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.tasks.scheduler import TaskScheduler

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Review", objective="Review now",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    async def never(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("a paused host must not start new work")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", never)
    HostControl(tmp_path).pause()
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 0
    # And the task is still there to run, not consumed or failed.
    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status not in ("failed", "completed")


def test_resuming_lets_due_work_start_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.tasks.scheduler import TaskScheduler

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Review", objective="Review now",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    async def completed(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(status="completed", message="Done.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    control = HostControl(tmp_path)
    control.pause()
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 0
    control.resume()
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1


# ── service registration, per platform ───────────────────────────────────


def test_macos_registers_a_launchagent_that_parses_as_a_plist(tmp_path: Path) -> None:
    plan = service_plan(tmp_path, port=8765, os_name="macos", home=tmp_path / "home")
    assert plan.supported
    assert plan.path == tmp_path / "home" / "Library" / "LaunchAgents" / f"{APP_LABEL}.plist"

    parsed = plistlib.loads(plan.contents.encode("utf-8"))
    assert parsed["Label"] == APP_LABEL
    assert parsed["RunAtLoad"] is True
    # A background service that opens a browser at every sign-in is a background
    # service nobody keeps enabled.
    assert "--no-browser" in parsed["ProgramArguments"]
    assert str(tmp_path.resolve()) in parsed["ProgramArguments"]
    assert parsed["ProcessType"] == "Background"
    # launchd's own verbs, not a Raiker supervisor.
    assert plan.activate[0][0] == "launchctl"
    assert plan.deactivate[0][:2] == ["launchctl", "bootout"]


def test_linux_registers_a_user_unit_that_restarts_on_the_restart_status(tmp_path: Path) -> None:
    plan = service_plan(tmp_path, port=9000, os_name="linux", home=tmp_path / "home")
    assert plan.path == tmp_path / "home" / ".config" / "systemd" / "user" / UNIT_NAME
    assert "[Install]\nWantedBy=default.target" in plan.contents
    assert "--no-browser" in plan.contents and "--port 9000" in plan.contents
    # The Restart action exits 75; without this the manager would treat a
    # deliberate restart as a clean exit and leave the host stopped.
    assert "RestartForceExitStatus=75" in plan.contents
    assert plan.activate[-1] == ["systemctl", "--user", "enable", "--now", UNIT_NAME]


def test_windows_registers_a_per_user_startup_entry(tmp_path: Path) -> None:
    plan = service_plan(tmp_path, port=8765, os_name="windows", home=tmp_path / "home")
    assert plan.path is not None and plan.path.name == WINDOWS_ENTRY
    assert plan.path.parent.name == "Startup"
    assert plan.contents.startswith("@echo off")
    assert "--no-browser" in plan.contents
    # The shell reads the Startup folder at sign-in; there is nothing to run.
    assert plan.activate == [] and plan.deactivate == []


def test_an_unknown_platform_says_so_instead_of_inventing_a_daemon(tmp_path: Path) -> None:
    plan = service_plan(tmp_path, port=8765, os_name="posix", home=tmp_path / "home")
    assert not plan.supported
    assert plan.path is None
    assert "no service manager" in plan.note


def test_install_writes_the_definition_and_uninstall_removes_it(tmp_path: Path) -> None:
    home = tmp_path / "home"
    plan = service_plan(tmp_path, port=8765, os_name="windows", home=home)
    assert registration(tmp_path, port=8765, os_name="windows", home=home).registered is False

    result = install(plan, activate=False)
    assert result.ok and plan.path is not None and plan.path.is_file()
    assert registration(tmp_path, port=8765, os_name="windows", home=home).registered is True

    removed = uninstall(plan)
    assert removed.ok and not plan.path.exists()
    assert registration(tmp_path, port=8765, os_name="windows", home=home).registered is False


def test_uninstalling_a_registration_that_is_not_there_is_not_an_error(tmp_path: Path) -> None:
    plan = service_plan(tmp_path, port=8765, os_name="windows", home=tmp_path / "home")
    result = uninstall(plan)
    assert result.ok
    assert result.message == "There was no background registration to remove."


def test_a_failed_activation_keeps_the_definition_and_says_what_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A headless session is a normal place to be, not a reason to leave nothing."""
    from raiker.app import service as service_module

    home = tmp_path / "home"
    plan = service_plan(tmp_path, port=8765, os_name="linux", home=home)
    monkeypatch.setattr(service_module.shutil, "which", lambda _name: None)

    result = install(plan)
    assert result.ok and plan.path is not None and plan.path.is_file()
    assert result.failed and "systemctl is not installed" in result.failed[0]
    assert "will still start at your next sign-in" in result.message


# ── uninstall ────────────────────────────────────────────────────────────


def _seed_instance(root: Path, name: str) -> Path:
    path = root / ".raiker" / "instances" / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "raiker.db").write_bytes(b"x" * 2048)
    return path


def test_the_plan_states_what_is_removed_and_what_is_kept_without_touching_anything(
    tmp_path: Path,
) -> None:
    (tmp_path / ".raiker").mkdir(parents=True)
    (tmp_path / ".raiker" / "raiker.db").write_bytes(b"y" * 4096)
    instance = _seed_instance(tmp_path, "work")

    plan = plan_uninstall(tmp_path, os_name="windows", home=tmp_path / "home")
    lines = "\n".join(plan.describe())

    assert not plan.removes_data
    assert "Kept: This device's Raiker data" in lines
    assert "Instance “work”" in lines
    # The two things "uninstall" would otherwise be assumed to have taken.
    assert "never deletes a copy it does not hold" in lines
    assert "pip uninstall raiker" in lines
    # Nothing has happened yet — that is the whole contract of a plan.
    assert instance.is_dir() and (tmp_path / ".raiker" / "raiker.db").is_file()


def test_export_requires_a_destination(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="export_requires_a_destination"):
        plan_uninstall(tmp_path, disposition="export")


def test_an_unknown_disposition_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown_disposition:shred"):
        plan_uninstall(tmp_path, disposition="shred")


def test_keeping_data_removes_the_registration_and_nothing_else(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "keep.txt").write_text("mine", encoding="utf-8")
    install(service_plan(workspace, port=8765, os_name="windows", home=home), activate=False)

    plan = plan_uninstall(workspace, disposition="keep", os_name="windows", home=home)
    assert plan.service_registered
    done = "\n".join(apply_uninstall(plan, workspace, os_name="windows", home=home))

    assert "Removed the Windows per-user startup registration." in done
    assert (workspace / "keep.txt").read_text(encoding="utf-8") == "mine"


def test_exporting_copies_the_instance_out_before_removing_it(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "notes.md").write_text("still encrypted at rest", encoding="utf-8")
    destination = tmp_path / "backup"

    plan = plan_uninstall(
        workspace,
        disposition="export",
        export_to=destination,
        os_name="windows",
        home=tmp_path / "home",
    )
    apply_uninstall(plan, workspace, os_name="windows", home=tmp_path / "home")

    exported = destination / "This device's Raiker data" / "notes.md"
    assert exported.read_text(encoding="utf-8") == "still encrypted at rest"
    assert not workspace.exists()


def test_a_nested_instance_is_removed_before_the_workspace_that_holds_it(tmp_path: Path) -> None:
    """Deepest-first, or the child's removal is a no-op that still claims success."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _seed_instance(workspace, "work")

    plan = plan_uninstall(
        workspace, disposition="erase", os_name="windows", home=tmp_path / "home"
    )
    done = apply_uninstall(plan, workspace, os_name="windows", home=tmp_path / "home")

    assert "instances/work" in done[0].replace("\\", "/")
    assert not workspace.exists()


def test_erase_overwrites_before_removing(tmp_path: Path) -> None:
    root = tmp_path / "erase-me"
    (root / "nested").mkdir(parents=True)
    secret = root / "nested" / "secret.txt"
    secret.write_text("the passphrase", encoding="utf-8")

    assert secure_erase(root) == 1
    assert not root.exists()


def test_sizes_are_reported_in_units_an_owner_can_act_on(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"0" * 1536)
    assert directory_bytes(tmp_path) == 1536
    assert human_bytes(512) == "512 B"
    assert human_bytes(1536) == "1.5 KB"
    assert human_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_measuring_a_directory_that_is_not_there_is_zero_not_an_error(tmp_path: Path) -> None:
    assert directory_bytes(tmp_path / "nope") == 0


# ── the CLI surface ──────────────────────────────────────────────────────


def test_status_reports_the_state_and_whether_it_starts_on_its_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    assert main(["status", "--workspace", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "stopped" in out
    assert "background start:" in out


def test_pause_and_resume_are_visible_to_the_next_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    assert main(["pause", "--workspace", str(tmp_path), "--reason", "lunch"]) == 0
    assert HostControl(tmp_path).pause_state().reason == "lunch"
    assert main(["resume", "--workspace", str(tmp_path)]) == 0
    assert not HostControl(tmp_path).is_paused()


def test_quit_refuses_while_work_is_in_flight_and_says_what(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    store = SQLiteStore(tmp_path)
    store.create_session("sess_inbox_principal_owner", str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id="sess_inbox_principal_owner", title="Long build", objective="Build",
    )
    store.update_task_status(task.task_id, "running")
    HostControl(tmp_path).record_start(pid=_this_process(), port=8765)

    assert main(["quit", "--workspace", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "Not stopping" in out
    assert "1 background run in flight" in out
    assert "--force" in out


def test_quit_on_a_stopped_host_is_a_no_op(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    assert main(["quit", "--workspace", str(tmp_path)]) == 0
    assert "No Raiker host is running" in capsys.readouterr().out


def test_uninstall_prints_the_plan_and_changes_nothing_without_yes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    (tmp_path / "data.bin").write_bytes(b"z" * 128)
    assert main(["uninstall", "--workspace", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Uninstalling Raiker would:" in out
    assert "Nothing has been changed" in out
    assert (tmp_path / "data.bin").is_file()


def test_uninstall_export_without_a_destination_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    assert main(["uninstall", "--workspace", str(tmp_path), "--data", "export"]) == 2
    assert "Pass --export-to" in capsys.readouterr().err


def test_service_status_names_the_platform_mechanism(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.api.launcher import main

    isolated_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: isolated_home))
    assert main(["service", "status", "--workspace", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "not registered" in out
    assert "definition:" in out


def test_running_raiker_app_with_no_command_still_means_start(tmp_path: Path) -> None:
    """The desktop icon runs `raiker-app`; adding subcommands must not change it."""
    from apps.api.launcher import build_parser

    args = build_parser().parse_args([])
    assert getattr(args, "command", None) is None
    assert args.port == 8765


def test_common_options_work_before_or_after_a_subcommand(tmp_path: Path) -> None:
    """A subparser must not erase a workspace already parsed by the root."""
    from apps.api.launcher import build_parser

    before = build_parser().parse_args(
        ["--workspace", str(tmp_path), "--port", "8877", "service", "install"]
    )
    after = build_parser().parse_args(
        ["service", "install", "--workspace", str(tmp_path), "--port", "8877"]
    )

    assert before.workspace == after.workspace == str(tmp_path)
    assert before.port == after.port == 8877


# ── helpers ──────────────────────────────────────────────────────────────


def _this_process() -> int:
    import os

    return os.getpid()


def _dead_pid() -> int:
    """A pid that is almost certainly not in use.

    Chosen above the usual `pid_max` rather than by spawning and reaping a
    process, which would race with pid reuse on a busy machine.
    """
    return 4_194_303


def test_the_host_record_is_written_atomically(tmp_path: Path) -> None:
    """A half-written state file is a control that lies after a restart."""
    control = HostControl(tmp_path)
    control.record_start(pid=_this_process(), port=8765)
    saved = json.loads(control.record_path.read_text(encoding="utf-8"))
    assert set(saved) == {"pid", "port", "started_at"}
    assert not list(control.state_dir.glob("*.tmp"))
