"""``raiker-app`` — start Raiker the way the operating system expects.

Raiker already ran on Windows, macOS and Linux; what it did not do was *behave*
like an application on any of them. Starting it meant knowing to run
``raiker-web``, knowing that state lands in the current working directory,
knowing which port to keep free, and knowing to open a browser at the right URL.
That is a service, and asking a person to operate a service is asking them to
hold the operating system's job in their head.

This is the single entry point that closes that gap. It detects the platform and
does the right thing for it, and there is exactly one of it — no per-OS script to
keep in step, and nothing here that only works on the author's machine:

* **State lives where the platform says it should.** ``%LOCALAPPDATA%\\Raiker`` on
  Windows, ``~/Library/Application Support/Raiker`` on macOS, and
  ``$XDG_DATA_HOME/raiker`` (falling back to ``~/.local/share/raiker``) on Linux
  and anything else POSIX. An explicit ``--workspace`` always wins, and
  ``RAIKER_HOME`` overrides the default for people who keep their data elsewhere.
* **An already-running Raiker is joined, not fought.** If the port answers as a
  Raiker host, the launcher opens the browser at it and exits successfully
  rather than failing on a bind conflict or, worse, starting a second host over
  the same workspace.
* **The port is found, not assumed.** 8765 is tried first so the URL stays
  familiar; if it is taken by something that is not Raiker, the next free port is
  used and printed.
* **The browser is opened through the platform's own opener** — ``start`` on
  Windows, ``open`` on macOS, ``xdg-open`` on Linux — falling back to Python's
  ``webbrowser``. A headless machine simply prints the URL rather than failing.

Everything about *how Raiker runs* is unchanged: this binds loopback, serves the
same app, and cannot widen exposure. Reaching Raiker from another machine is
still the deliberate ``raiker-web --allow-public`` path with its own token
requirement, and this launcher deliberately offers no flag for it.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

APP_NAME = "Raiker"
DEFAULT_PORT = 8765
# How many ports past the default to try before giving up. Small on purpose: if
# a dozen consecutive ports are taken, something is wrong that a wider scan
# would only hide.
PORT_SCAN_RANGE = 12
LOOPBACK = "127.0.0.1"


def detect_os() -> str:
    """``windows``, ``macos``, ``linux``, or ``posix`` for anything else.

    Anything unrecognised is treated as POSIX rather than refused: a BSD or an
    illumos box has a home directory and a loopback interface, which is all this
    launcher actually needs.
    """
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    return "posix"


def default_workspace(os_name: str | None = None) -> Path:
    """Where this platform expects an application to keep its data.

    ``RAIKER_HOME`` overrides everything: someone who keeps their data on an
    encrypted volume should not have to move the whole platform convention to
    get it.
    """
    override = os.environ.get("RAIKER_HOME", "").strip()
    if override:
        return Path(override).expanduser()

    name = os_name or detect_os()
    if name == "windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / APP_NAME
    if name == "macos":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / APP_NAME.lower()


def port_is_free(port: int, host: str = LOOPBACK) -> bool:
    """Can this process bind that port right now?

    Asked by binding rather than by connecting: a port with nothing listening
    can still be unbindable, and a launcher that discovers that at ``uvicorn.run``
    has already printed a URL it cannot honour.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def raiker_is_running(port: int, host: str = LOOPBACK, timeout: float = 1.0) -> bool:
    """Is the thing on this port a Raiker host?

    ``/api/health`` is the only unauthenticated read Raiker exposes and returns
    nothing but ``{"status": "ok"}``, so this identifies a Raiker without
    touching anything in the workspace. Any failure — refused, timed out,
    something else answering — is "not Raiker", which is the fail-safe answer:
    the launcher then looks for a free port instead of handing the owner a URL
    belonging to someone else's server.
    """
    try:
        with urlopen(f"http://{host}:{port}/api/health", timeout=timeout) as response:  # noqa: S310
            if response.status != 200:
                return False
            return b'"ok"' in response.read(256)
    except (URLError, OSError, ValueError):
        return False


def choose_port(preferred: int, host: str = LOOPBACK) -> tuple[int, bool]:
    """``(port, already_running)`` for this launch.

    Three outcomes, in order: the preferred port is free and is used; a Raiker
    is already answering there and is joined; something else holds it and the
    next free port is taken.
    """
    if port_is_free(preferred, host):
        return preferred, False
    if raiker_is_running(preferred, host):
        return preferred, True
    for candidate in range(preferred + 1, preferred + 1 + PORT_SCAN_RANGE):
        if port_is_free(candidate, host):
            return candidate, False
    raise OSError(
        f"No free port between {preferred} and {preferred + PORT_SCAN_RANGE} on {host}."
    )


def open_browser(url: str, os_name: str | None = None) -> bool:
    """Open *url* the way this platform opens things. False if nothing could.

    The platform opener is preferred over Python's ``webbrowser`` because it
    honours the user's actual default browser in cases ``webbrowser`` does not
    (a Windows default set through Settings, a macOS default set through a
    non-Apple browser's own preferences). ``webbrowser`` is the fallback, and a
    headless machine failing both is not an error — the caller prints the URL.
    """
    name = os_name or detect_os()
    try:
        if name == "windows":
            os.startfile(url)  # type: ignore[attr-defined]  # noqa: S606  # Windows-only
            return True
        opener = "open" if name == "macos" else "xdg-open"
        if shutil.which(opener) is not None:
            subprocess.Popen(  # noqa: S603
                [opener, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    except OSError:
        pass
    try:
        return bool(webbrowser.open(url, new=1))
    except Exception:  # noqa: BLE001
        return False


def _resolve_ui_dir() -> Path | None:
    """The built web app, if this install has one."""
    from apps.api.main import _resolve_ui_dir as resolve

    candidate = resolve(None)
    if candidate.is_dir() and (candidate / "index.html").is_file():
        return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="raiker-app",
        description=(
            "Start Raiker as a desktop application: platform-appropriate data "
            "directory, a free loopback port, and your default browser."
        ),
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Where Raiker keeps its data (default: this platform's application-data directory).",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Preferred port (default: {DEFAULT_PORT})."
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Start the host without opening a browser."
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print the detected platform and data directory, then exit.",
    )
    args = parser.parse_args(argv)

    os_name = detect_os()
    workspace = Path(args.workspace).expanduser() if args.workspace else default_workspace(os_name)

    if args.print_paths:
        print(f"platform: {os_name}")
        print(f"workspace: {workspace}")
        return 0

    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"[raiker] Cannot use {workspace}: {error}", file=sys.stderr)
        print("[raiker] Pass --workspace, or set RAIKER_HOME to a writable directory.", file=sys.stderr)
        return 2

    try:
        port, already_running = choose_port(args.port)
    except OSError as error:
        print(f"[raiker] {error}", file=sys.stderr)
        return 2

    url = f"http://{LOOPBACK}:{port}/"

    if already_running:
        # Joining is the right answer, not an error: two hosts over one
        # encrypted workspace is a data-integrity problem, and the person who
        # double-clicked the icon wants the app, not a second copy of it.
        print(f"[raiker] Raiker is already running at {url} — opening it.")
        if not args.no_browser and not open_browser(url, os_name):
            print(f"[raiker] Could not open a browser. Go to {url}")
        return 0

    ui_dir = _resolve_ui_dir()
    if ui_dir is None:
        print(
            "[raiker] No built web app found, so this will serve the API only. "
            "Build it first: npm --prefix apps/web run build",
        )

    from raiker.api.app import create_app

    print(f"[raiker] {os_name} · data in {workspace}")
    print(f"[raiker] Starting on {url} (loopback only)")

    app = create_app(workspace, ui_dir=ui_dir)

    if not args.no_browser:
        # After the server has had a moment to bind, so the first request is not
        # a connection refused the owner has to reload past.
        threading.Timer(1.2, lambda: open_browser(url, os_name)).start()

    import uvicorn

    uvicorn.run(app, host=LOOPBACK, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
