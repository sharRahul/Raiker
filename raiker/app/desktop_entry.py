"""The icon you click to open Raiker.

:mod:`raiker.app.service` registers the host to *start at sign-in*. That is a
different thing from a launcher, and Raiker had only the first: after installing
from a checkout there was nothing in the applications menu, nothing in the Start
Menu, nothing in Spotlight. The only way in was a terminal, which is a strange
thing to require of a product whose whole surface is a browser page.

So this module writes one launcher entry per platform and nothing else:

============  =========================================  ==========================
Platform      Entry                                      Where
============  =========================================  ==========================
Linux         freedesktop ``.desktop`` file               ``~/.local/share/applications``
macOS         minimal ``.app`` bundle                     ``~/Applications``
Windows       Start Menu ``.cmd``, plus a ``.lnk``        ``…/Start Menu/Programs``
============  =========================================  ==========================

It follows :mod:`~raiker.app.service` exactly, and for the same reasons: the
plan is a value that can be printed, shown and asserted without touching the
disk; everything is per-user, so nothing here writes outside the invoking user's
home or asks for elevation; and a failed activation is reported rather than
raised, because a file that is correct on disk is useful even when the desktop
environment did not pick it up this second.

The entry runs ``raiker-app``, which starts the host if it is not running and
opens the dashboard in the default browser either way — so one icon is the whole
answer to "how do I open this", whether or not the background service is
registered.
"""

from __future__ import annotations

import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from raiker.app.service import ServiceActionResult, detect_os, run_all

APP_NAME = "Raiker"
LINUX_ENTRY = "raiker.desktop"
MACOS_BUNDLE = "Raiker.app"
WINDOWS_ENTRY = "Raiker.cmd"
WINDOWS_SHORTCUT = "Raiker.lnk"
COMMENT = "Open the Raiker governed agent dashboard"


@dataclass(frozen=True)
class DesktopEntryPlan:
    """What adding a launcher on this platform would do.

    ``files`` rather than one path because a macOS ``.app`` is a directory with a
    plist and an executable in it. Everything else writes exactly one entry, and
    a single-entry mapping is a smaller idea than two code paths.
    """

    supported: bool
    mechanism: str
    label: str
    #: Destination path → contents. Written in iteration order.
    files: dict[Path, str]
    #: Paths that must be made executable after writing.
    executable: tuple[Path, ...]
    #: Directories removed wholesale on uninstall (the macOS bundle).
    directories: tuple[Path, ...]
    activate: list[list[str]]
    note: str

    @property
    def path(self) -> Path | None:
        """The entry an owner would point at, for a one-line report."""
        if self.directories:
            return self.directories[0]
        return next(iter(self.files), None)

    def described_activation(self) -> str:
        return "; ".join(shlex.join(command) for command in self.activate)


@dataclass(frozen=True)
class DesktopEntryStatus:
    """Whether a launcher is currently installed, and what kind."""

    supported: bool
    installed: bool
    mechanism: str
    label: str
    path: str | None
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "supported": self.supported,
            "installed": self.installed,
            "mechanism": self.mechanism,
            "label": self.label,
            "path": self.path,
            "note": self.note,
        }


def launch_command(workspace: Path | None = None) -> list[str]:
    """How the launcher should start Raiker.

    No ``--no-browser`` here, and no ``--port``: unlike the background service,
    opening the browser *is* the point, and letting the launcher pick a free port
    is what stops a second entry from colliding with a host that is already up.

    The workspace is named only when the caller asks for a specific one. A bare
    ``raiker-app`` uses the platform's own data directory, which is the right
    default for an icon someone clicks a year from now, long after whichever
    directory they happened to install from has moved.
    """
    executable = shutil.which("raiker-app")
    base = [executable] if executable else [sys.executable, "-m", "apps.api.launcher"]
    return [*base, *(["--workspace", str(workspace)] if workspace is not None else [])]


def entry_plan(
    *,
    workspace: str | Path | None = None,
    os_name: str | None = None,
    home: Path | None = None,
    icon: Path | None = None,
) -> DesktopEntryPlan:
    """The launcher this platform would receive. Never touches the disk."""
    name = os_name or detect_os()
    root = Path(home) if home is not None else Path.home()
    target = Path(workspace).resolve() if workspace is not None else None
    command = launch_command(target)
    if icon is None:
        from raiker.assets import icon_path

        icon = icon_path()
    if name == "linux":
        return _linux_plan(root, command, icon)
    if name == "macos":
        return _macos_plan(root, command, icon)
    if name == "windows":
        return _windows_plan(root, command, icon)
    return DesktopEntryPlan(
        supported=False,
        mechanism="none",
        label=APP_NAME,
        files={},
        executable=(),
        directories=(),
        activate=[],
        note=(
            "This platform has no application menu Raiker knows how to add to. "
            "Start it with `raiker-app`."
        ),
    )


def _linux_plan(home: Path, command: list[str], icon: Path | None) -> DesktopEntryPlan:
    path = home / ".local" / "share" / "applications" / LINUX_ENTRY
    # `Exec` takes a command line, not an argv list, and a path with a space in
    # it is ordinary on a desktop. `shlex.join` quotes it correctly; the `%` that
    # freedesktop reserves for field codes has to be escaped as `%%`.
    exec_line = shlex.join(command).replace("%", "%%")
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={APP_NAME}",
        f"Comment={COMMENT}",
        f"Exec={exec_line}",
        "Terminal=false",
        "Categories=Development;Utility;",
        "Keywords=agent;assistant;ai;",
        # One window per launch would be wrong: Raiker is a browser page, and the
        # second click should reach the host that is already running.
        "SingleMainWindow=true",
        "StartupNotify=false",
    ]
    if icon is not None:
        lines.insert(5, f"Icon={icon}")
    contents = "\n".join(lines) + "\n"
    return DesktopEntryPlan(
        supported=True,
        mechanism="freedesktop application entry",
        label=LINUX_ENTRY,
        files={path: contents},
        # A `.desktop` file that is not executable is refused by some desktops
        # and silently shown-but-inert by others.
        executable=(path,),
        directories=(),
        # Not fatal if missing: most desktops watch the directory, and the entry
        # appears at the next login regardless.
        activate=[["update-desktop-database", str(path.parent)]],
        note=(
            "Appears in your applications menu. Written under your own home "
            "directory; nothing system-wide is touched."
        ),
    )


def _macos_plan(home: Path, command: list[str], icon: Path | None) -> DesktopEntryPlan:
    bundle = home / "Applications" / MACOS_BUNDLE
    runner = bundle / "Contents" / "MacOS" / "Raiker"
    plist = bundle / "Contents" / "Info.plist"
    resources = bundle / "Contents" / "Resources"
    icon_line = (
        "    <key>CFBundleIconFile</key>\n    <string>raiker-icon.png</string>\n"
        if icon is not None
        else ""
    )
    plist_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.raiker.launcher</string>
    <key>CFBundleExecutable</key>
    <string>Raiker</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1</string>
{icon_line}    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <!-- No dock icon and no menu bar for the launcher itself: what the owner
         wants is the browser page, and the tray is where the host lives. -->
    <key>LSUIElement</key>
    <true/>
  </dict>
</plist>
"""
    runner_body = f"""#!/bin/sh
# Opens Raiker. The host is started if it is not already running.
exec {shlex.join(command)}
"""
    files: dict[Path, str] = {plist: plist_body, runner: runner_body}
    return DesktopEntryPlan(
        supported=True,
        mechanism="Applications bundle (per-user)",
        label=MACOS_BUNDLE,
        files=files,
        executable=(runner,),
        directories=(bundle,),
        # Tells Launch Services the bundle exists now rather than at the next
        # scan, so it is searchable from Spotlight immediately.
        activate=[
            [
                "/System/Library/Frameworks/CoreServices.framework/Frameworks"
                "/LaunchServices.framework/Support/lsregister",
                "-f",
                str(bundle),
            ]
        ],
        note=(
            f"Appears in ~/Applications and Spotlight. The icon is copied into "
            f"{resources.name}/ so the bundle does not depend on the checkout."
        ),
    )


def _windows_plan(home: Path, command: list[str], icon: Path | None) -> DesktopEntryPlan:
    programs = (
        home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    )
    script = programs / WINDOWS_ENTRY
    shortcut = programs / WINDOWS_SHORTCUT
    quoted = " ".join(f'"{part}"' if " " in part else part for part in command)
    contents = f'@echo off\r\nstart "Raiker" /b {quoted}\r\n'
    # The `.cmd` is the thing that works with no help. The `.lnk` is what makes
    # it look like an application: a real icon, and a window style that does not
    # flash a console. PowerShell is how you write one without adding a COM
    # dependency, and if it is unavailable the `.cmd` is still in the Start Menu.
    icon_line = f"$s.IconLocation = '{icon}';" if icon is not None else ""
    powershell = (
        "$w = New-Object -ComObject WScript.Shell; "
        f"$s = $w.CreateShortcut('{shortcut}'); "
        f"$s.TargetPath = '{script}'; "
        f"$s.WorkingDirectory = '{script.parent}'; "
        f"$s.Description = '{COMMENT}'; "
        "$s.WindowStyle = 7; "
        f"{icon_line} "
        "$s.Save()"
    )
    return DesktopEntryPlan(
        supported=True,
        mechanism="Start Menu entry",
        label=WINDOWS_ENTRY,
        files={script: contents},
        executable=(),
        directories=(),
        activate=[["powershell", "-NoProfile", "-NonInteractive", "-Command", powershell]],
        note=(
            "Appears in the Start Menu under your own account. If the shortcut "
            "could not be written, the .cmd beside it still launches Raiker."
        ),
    )


def status(
    *,
    workspace: str | Path | None = None,
    os_name: str | None = None,
    home: Path | None = None,
) -> DesktopEntryStatus:
    """Whether a launcher is installed on this platform right now."""
    plan = entry_plan(workspace=workspace, os_name=os_name, home=home)
    target = plan.path
    installed = bool(
        target is not None and (target.is_dir() if plan.directories else target.is_file())
    )
    return DesktopEntryStatus(
        supported=plan.supported,
        installed=installed,
        mechanism=plan.mechanism,
        label=plan.label,
        path=str(target) if target is not None else None,
        note=plan.note,
    )


def install(plan: DesktopEntryPlan, *, activate: bool = True) -> ServiceActionResult:
    """Write the entry and ask the desktop to notice it.

    Reuses :class:`~raiker.app.service.ServiceActionResult` deliberately: an
    owner reading `raiker-app desktop install` and `raiker-app service install`
    should not have to learn two shapes of answer for two commands that do the
    same kind of thing.
    """
    if not plan.supported or not plan.files:
        return ServiceActionResult(False, None, [], [], plan.note)
    for path, contents in plan.files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    for path in plan.executable:
        path.chmod(0o755)
    _copy_icon(plan)
    ran, failed = ([], []) if not activate else run_all(plan.activate)
    written = str(plan.path)
    message = (
        f"Added the {plan.mechanism}."
        if not failed
        else (
            f"Wrote {written}, but the desktop did not pick it up yet "
            f"({'; '.join(failed)}). It appears at your next sign-in."
        )
    )
    return ServiceActionResult(True, written, ran, failed, message)


def _copy_icon(plan: DesktopEntryPlan) -> None:
    """Put the icon inside a macOS bundle, which cannot reference one outside it.

    Linux and Windows point at the installed file by path, so there is nothing to
    copy; a bundle that referenced a path in a checkout would show a blank icon
    the day that checkout moved.
    """
    if not plan.directories:
        return
    from raiker.assets import ICON_FILENAME, icon_path

    source = icon_path()
    if source is None:
        return
    resources = plan.directories[0] / "Contents" / "Resources"
    resources.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, resources / ICON_FILENAME)


def uninstall(plan: DesktopEntryPlan) -> ServiceActionResult:
    """Remove the entry. Idempotent by construction."""
    if not plan.supported:
        return ServiceActionResult(False, None, [], [], plan.note)
    removed: list[str] = []
    for directory in plan.directories:
        if directory.is_dir():
            shutil.rmtree(directory, ignore_errors=True)
            removed.append(str(directory))
    for path in plan.files:
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    # The Windows shortcut is created by the activation step rather than written
    # as a file, so it is not in `files` and has to be named here or it would
    # survive an uninstall — a Start Menu icon pointing at a launcher that is
    # gone is worse than no icon.
    for extra in _companions(plan):
        if extra.is_file():
            extra.unlink()
            removed.append(str(extra))
    # `ran` stays empty: it means "commands that were run", and the CLI prints it
    # as `ran:`. What was removed is a path, and it belongs in the message.
    message = (
        f"Removed the {plan.mechanism} ({', '.join(removed)})."
        if removed
        else "There was no launcher to remove."
    )
    return ServiceActionResult(True, removed[0] if removed else None, [], [], message)


def _companions(plan: DesktopEntryPlan) -> tuple[Path, ...]:
    """Files an activation step creates that no `files` entry names."""
    for path in plan.files:
        if path.name == WINDOWS_ENTRY:
            return (path.with_name(WINDOWS_SHORTCUT),)
    return ()
