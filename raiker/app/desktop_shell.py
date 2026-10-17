"""Find and open Raiker's desktop window (DESK-11).

Raiker's default experience is its own desktop window, an Electron shell in
``desktop/`` that shows the local host in a native window with a menu,
shortcuts and notifications. The host is unchanged: the window is one more
client of the same loopback service, and closing it stops nothing.

This module answers one question — *how do I open that window on this
install?* — so the launcher, the tray's **Open Raiker** and the tests share one
answer:

1. ``RAIKER_DESKTOP_SHELL``, when set, names the executable to run. It is the
   override for a development build and for anyone who keeps the shell
   somewhere else.
2. A packaged application carries the host inside the shell
   (``resources/host/Raiker``), so the shell's own executable is found relative
   to the frozen host.
3. A source checkout runs Electron from ``desktop/node_modules`` against
   ``desktop/dist/main.js``, which ``npm --prefix desktop ci`` and
   ``npm --prefix desktop run build`` produce.

When none of those exists the answer is ``None`` and the caller falls back to
the browser, saying why — a missing window is never a failed start.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SHELL_ENV = "RAIKER_DESKTOP_SHELL"
URL_FLAG = "--raiker-url"


@dataclass(frozen=True)
class ShellCommand:
    """The argv that opens the desktop window, and where it was found."""

    argv: tuple[str, ...]
    source: str


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _electron_binary(desktop_dir: Path, platform: str) -> Path:
    dist = desktop_dir / "node_modules" / "electron" / "dist"
    if platform == "win32":
        return dist / "electron.exe"
    if platform == "darwin":
        return dist / "Electron.app" / "Contents" / "MacOS" / "Electron"
    return dist / "electron"


def _packaged_shell(executable: Path, platform: str) -> Path | None:
    """The shell executable that carries this frozen host, if it is one.

    ``electron-builder.yml`` places the host at ``resources/host/`` beside the
    shell: ``Raiker.app/Contents/Resources/host`` on macOS, and
    ``<install>/resources/host`` on Windows and Linux.
    """
    host_dir = executable.parent
    if host_dir.name != "host":
        return None
    resources = host_dir.parent
    if platform == "darwin":
        candidate = resources.parent / "MacOS" / "Raiker"
    else:
        candidate = resources.parent / ("Raiker.exe" if platform == "win32" else "raiker")
    return candidate if candidate.is_file() else None


def find_shell(
    url: str,
    *,
    environ: dict[str, str] | None = None,
    platform: str = sys.platform,
    frozen_executable: Path | None = None,
    repository_root: Path | None = None,
) -> ShellCommand | None:
    """The command that opens *url* in the desktop window, or ``None``."""
    env = os.environ if environ is None else environ
    explicit = env.get(SHELL_ENV, "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return ShellCommand((str(path), URL_FLAG, url), SHELL_ENV) if path.is_file() else None

    if frozen_executable is None and getattr(sys, "frozen", False):
        frozen_executable = Path(sys.executable)
    if frozen_executable is not None:
        shell = _packaged_shell(frozen_executable.resolve(), platform)
        return ShellCommand((str(shell), URL_FLAG, url), "packaged") if shell is not None else None

    desktop_dir = (repository_root or _repository_root()) / "desktop"
    electron = _electron_binary(desktop_dir, platform)
    if electron.is_file() and (desktop_dir / "dist" / "main.js").is_file():
        return ShellCommand((str(electron), str(desktop_dir), URL_FLAG, url), "source checkout")
    return None


def unavailable_reason(*, environ: dict[str, str] | None = None) -> str:
    """Why :func:`find_shell` found nothing, in words an owner can act on."""
    env = os.environ if environ is None else environ
    if env.get(SHELL_ENV, "").strip():
        return f"{SHELL_ENV} does not name a file"
    if getattr(sys, "frozen", False):
        return "this build does not include the desktop window"
    return "the desktop window is not built (npm --prefix desktop ci && npm --prefix desktop run build)"


def launch(command: ShellCommand) -> bool:
    """Start the window detached from this process. False if it could not start.

    Detached so the window outlives a terminal that started it and the host
    outlives the window: they are two programs that talk over loopback HTTP.
    """
    options: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        options["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        options["start_new_session"] = True
    try:
        subprocess.Popen(list(command.argv), **options)  # type: ignore[call-overload]  # noqa: S603
    except OSError:
        return False
    return True
