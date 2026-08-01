"""Start Raiker in the background the way each platform already starts things.

BUG-40. The distribution design is explicit that *native service managers are
preferred over a custom daemon manager*, and names one per platform. That
preference is not a style choice: a supervisor Raiker wrote itself would have to
re-solve start-at-login, restart-on-failure, per-user isolation and log capture —
four problems the operating system has already solved and the owner already
knows how to inspect.

So this module writes one definition file per platform and hands activation to
that platform's own tool:

============  ===========================================  ================================
Platform      Mechanism                                    Activated with
============  ===========================================  ================================
macOS         ``launchd`` LaunchAgent (per-user)            ``launchctl bootstrap gui/<uid>``
Linux         ``systemd --user`` unit                       ``systemctl --user enable --now``
Windows       per-user Startup folder entry                 the shell, at sign-in
============  ===========================================  ================================

The Windows choice deserves its reason. The design asks for "per-user
background/startup registration for a desktop host", and both the ``Run``
registry value and the Startup folder satisfy it. The Startup folder is used
because it makes install, inspect and uninstall the same three operations as the
other two platforms — write a file, read a file, delete a file — with nothing
hiding in a registry hive that an uninstall could miss. The Windows *service*
path in the design belongs to the explicitly-configured shared host, which is a
separate, administrator-initiated decision and not what ``raiker-app`` does.

Everything is per-user. Nothing here writes outside the invoking user's own home
directory, asks for elevation, or registers a system-wide daemon; a shared host
remains the deliberate, separately-reviewed configuration the design describes.
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

APP_LABEL = "com.raiker.host"
UNIT_NAME = "raiker.service"
WINDOWS_ENTRY = "Raiker.cmd"


@dataclass(frozen=True)
class ServicePlan:
    """What registering the background host on this platform would do.

    Held as data rather than performed inline so the same description can be
    shown to the owner before anything is written, checked in a test on a
    platform it does not target, and executed — three uses, one source.
    """

    supported: bool
    mechanism: str
    label: str
    path: Path | None
    contents: str
    activate: list[list[str]]
    deactivate: list[list[str]]
    note: str

    def described_activation(self) -> str:
        """The activation commands as the owner would type them."""
        return "; ".join(shlex.join(command) for command in self.activate)


@dataclass(frozen=True)
class ServiceRegistration:
    """Whether the background host is registered, and what registered it."""

    supported: bool
    registered: bool
    mechanism: str
    label: str
    path: str | None
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "supported": self.supported,
            "registered": self.registered,
            "mechanism": self.mechanism,
            "label": self.label,
            "path": self.path,
            "note": self.note,
        }


def detect_os(system: str | None = None) -> str:
    """``windows``, ``macos``, ``linux``, or ``posix`` for anything else."""
    name = (system or platform.system()).lower()
    if name.startswith("win"):
        return "windows"
    if name == "darwin":
        return "macos"
    if name == "linux":
        return "linux"
    return "posix"


def launch_command(workspace: Path, port: int) -> list[str]:
    """How the service manager should start Raiker.

    The installed console script is preferred because it survives a virtualenv
    being activated differently at login; ``python -m`` is the fallback for a
    checkout that was never installed. ``--no-browser`` is not optional: a
    background service that opens a browser window at sign-in is a background
    service nobody keeps enabled.
    """
    executable = shutil.which("raiker-app")
    base = [executable] if executable else [sys.executable, "-m", "apps.api.launcher"]
    return [*base, "--no-browser", "--workspace", str(workspace), "--port", str(port)]


def service_plan(
    workspace: str | Path,
    *,
    port: int,
    os_name: str | None = None,
    home: Path | None = None,
) -> ServicePlan:
    """The registration this platform would receive. Never touches the disk."""
    name = os_name or detect_os()
    root = Path(home) if home is not None else Path.home()
    target = Path(workspace).resolve()
    command = launch_command(target, port)
    if name == "macos":
        return _macos_plan(root, command)
    if name == "linux":
        return _linux_plan(root, command, target)
    if name == "windows":
        return _windows_plan(root, command)
    return ServicePlan(
        supported=False,
        mechanism="none",
        label=APP_LABEL,
        path=None,
        contents="",
        activate=[],
        deactivate=[],
        note=(
            "This platform has no service manager Raiker knows how to register "
            "with. Start it with `raiker-app`, or add it to whatever supervisor "
            "you already use."
        ),
    )


def _macos_plan(home: Path, command: list[str]) -> ServicePlan:
    path = home / "Library" / "LaunchAgents" / f"{APP_LABEL}.plist"
    arguments = "\n".join(f"      <string>{escape(part)}</string>" for part in command)
    logs = home / "Library" / "Logs" / "Raiker"
    contents = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>{APP_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{arguments}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
      <key>SuccessfulExit</key>
      <false/>
    </dict>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>{escape(str(logs / "host.log"))}</string>
    <key>StandardErrorPath</key>
    <string>{escape(str(logs / "host.error.log"))}</string>
  </dict>
</plist>
"""
    domain = f"gui/{os.getuid()}" if hasattr(os, "getuid") else "gui/501"
    return ServicePlan(
        supported=True,
        mechanism="launchd LaunchAgent (per-user)",
        label=APP_LABEL,
        path=path,
        contents=contents,
        # `bootstrap`/`bootout` are the modern launchctl verbs; `kickstart` makes
        # the agent start now rather than at the next sign-in.
        activate=[
            ["launchctl", "bootstrap", domain, str(path)],
            ["launchctl", "kickstart", "-k", f"{domain}/{APP_LABEL}"],
        ],
        deactivate=[["launchctl", "bootout", f"{domain}/{APP_LABEL}"]],
        note=(
            "A LaunchAgent runs as you, only while you are signed in, and is "
            "restarted by launchd if it exits unexpectedly."
        ),
    )


def _linux_plan(home: Path, command: list[str], workspace: Path) -> ServicePlan:
    path = home / ".config" / "systemd" / "user" / UNIT_NAME
    contents = f"""[Unit]
Description=Raiker governed agent host
Documentation=https://github.com/sharRahul/Raiker
After=network.target

[Service]
Type=simple
ExecStart={shlex.join(command)}
WorkingDirectory={workspace}
Restart=on-failure
RestartSec=5
# The exit status the host uses for "the owner pressed Restart" (see
# raiker/api/routes_host.py). Without this, a deliberate restart would read as a
# clean exit and systemd would leave the host stopped.
RestartForceExitStatus=75
# The host is loopback-only and owns nothing outside its own workspace; these
# keep a service manager restart from being a privilege escalation path.
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
"""
    return ServicePlan(
        supported=True,
        mechanism="systemd --user",
        label=UNIT_NAME,
        path=path,
        contents=contents,
        activate=[
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", "--now", UNIT_NAME],
        ],
        deactivate=[
            ["systemctl", "--user", "disable", "--now", UNIT_NAME],
            ["systemctl", "--user", "daemon-reload"],
        ],
        note=(
            "A --user unit runs as you and stops when you sign out unless "
            "lingering is enabled (`loginctl enable-linger`)."
        ),
    )


def _windows_plan(home: Path, command: list[str]) -> ServicePlan:
    path = (
        home
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / WINDOWS_ENTRY
    )
    quoted = " ".join(f'"{part}"' if " " in part else part for part in command)
    contents = f"@echo off\r\nstart \"Raiker\" /b {quoted}\r\n"
    return ServicePlan(
        supported=True,
        mechanism="Windows per-user startup",
        label=WINDOWS_ENTRY,
        path=path,
        contents=contents,
        # The shell reads the Startup folder at sign-in; there is no separate
        # activation step, and removing the file is the whole uninstall.
        activate=[],
        deactivate=[],
        note=(
            "Starts when you sign in to Windows, as you. A shared host is a "
            "Windows service and a separate, administrator-made decision."
        ),
    )


def registration(
    workspace: str | Path,
    *,
    port: int,
    os_name: str | None = None,
    home: Path | None = None,
) -> ServiceRegistration:
    """Whether the background host is currently registered on this platform."""
    plan = service_plan(workspace, port=port, os_name=os_name, home=home)
    registered = bool(plan.path is not None and plan.path.is_file())
    return ServiceRegistration(
        supported=plan.supported,
        registered=registered,
        mechanism=plan.mechanism,
        label=plan.label,
        path=str(plan.path) if plan.path is not None else None,
        note=plan.note,
    )


@dataclass(frozen=True)
class ServiceActionResult:
    """What an install or uninstall actually did, including what it could not."""

    ok: bool
    written: str | None
    ran: list[str]
    failed: list[str]
    message: str


def install(plan: ServicePlan, *, activate: bool = True) -> ServiceActionResult:
    """Write the definition and ask the platform to load it.

    A failed activation is reported, not raised, and never rolls the file back:
    the definition on disk is correct and useful on its own (it takes effect at
    the next sign-in), and a headless session where ``launchctl`` or
    ``systemctl`` cannot reach its manager is a normal thing to be in — not a
    reason to leave the owner with nothing.
    """
    if not plan.supported or plan.path is None:
        return ServiceActionResult(False, None, [], [], plan.note)
    plan.path.parent.mkdir(parents=True, exist_ok=True)
    plan.path.write_text(plan.contents, encoding="utf-8")
    ran, failed = ([], []) if not activate else _run_all(plan.activate)
    message = (
        f"Registered with {plan.mechanism}."
        if not failed
        else (
            f"Wrote {plan.path}, but the service manager did not accept it "
            f"({'; '.join(failed)}). It will still start at your next sign-in."
        )
    )
    return ServiceActionResult(True, str(plan.path), ran, failed, message)


def uninstall(plan: ServicePlan) -> ServiceActionResult:
    """Unload the definition and delete it. Idempotent by construction."""
    if not plan.supported or plan.path is None:
        return ServiceActionResult(False, None, [], [], plan.note)
    ran, failed = _run_all(plan.deactivate)
    existed = plan.path.is_file()
    plan.path.unlink(missing_ok=True)
    message = (
        f"Removed the {plan.mechanism} registration."
        if existed
        else "There was no background registration to remove."
    )
    return ServiceActionResult(True, str(plan.path) if existed else None, ran, failed, message)


def _run_all(commands: list[list[str]]) -> tuple[list[str], list[str]]:
    """Run each command, collecting what worked and what did not. Never raises."""
    ran: list[str] = []
    failed: list[str] = []
    for command in commands:
        printed = shlex.join(command)
        if shutil.which(command[0]) is None:
            failed.append(f"{command[0]} is not installed")
            continue
        try:
            result = subprocess.run(  # noqa: S603
                command, capture_output=True, text=True, timeout=30, check=False
            )
        except (OSError, subprocess.SubprocessError) as error:
            failed.append(f"{printed}: {type(error).__name__}")
            continue
        if result.returncode == 0:
            ran.append(printed)
        else:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            failed.append(f"{printed}: {detail[0] if detail else f'exit {result.returncode}'}")
    return ran, failed
