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

BUG-40 adds the rest of an application's life around that start, as
subcommands — ``raiker-app`` with no arguments still means "start Raiker":

* ``raiker-app status`` — running, paused, needs attention, or stopped, and what
  background work is in flight.
* ``raiker-app pause`` / ``resume`` — stop and restart the starting of new
  background work, without stopping the host.
* ``raiker-app quit`` — stop the host, reporting waiting work first.
* ``raiker-app service install|status|uninstall`` — register the host to start in
  the background with the platform's own service manager.
* ``raiker-app uninstall`` — state exactly what removal takes and what it keeps,
  with a per-instance retain / export / erase choice.

What is deliberately *not* here, because it cannot be honestly built from a
source checkout: signed installers (``.dmg``/``.pkg``, ``.msi``, AppImage,
``.deb``) and the signed-update channel with atomic migration and rollback. Both
need code-signing identities and per-OS release runners, and both are tracked as
their own work rather than faked with an unsigned artifact.
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

from raiker.app.host import HostControl

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


def _add_common(parser: argparse.ArgumentParser) -> None:
    """The two options every subcommand needs to talk about the same host."""
    parser.add_argument(
        "--workspace",
        default=None,
        help="Where Raiker keeps its data (default: this platform's application-data directory).",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Preferred port (default: {DEFAULT_PORT})."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="raiker-app",
        description=(
            "Start Raiker as a desktop application: platform-appropriate data "
            "directory, a free loopback port, and your default browser. "
            "Subcommands control the background host and its removal."
        ),
    )
    _add_common(parser)
    parser.add_argument(
        "--no-browser", action="store_true", help="Start the host without opening a browser."
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print the detected platform and data directory, then exit.",
    )
    # `required=False` keeps the bare `raiker-app` — the thing a desktop icon
    # runs — meaning exactly what it meant before: start Raiker.
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", help="Report whether the host is running, paused, or stopped.")
    _add_common(status)

    pause = sub.add_parser("pause", help="Stop starting new background work.")
    _add_common(pause)
    pause.add_argument("--reason", default=None, help="Why, recorded alongside the pause.")

    resume = sub.add_parser("resume", help="Start scheduled background work again.")
    _add_common(resume)

    quit_parser = sub.add_parser("quit", help="Stop the host, reporting waiting work first.")
    _add_common(quit_parser)
    quit_parser.add_argument(
        "--force", action="store_true", help="Stop even when background work is in flight."
    )

    service = sub.add_parser(
        "service", help="Register the host to start in the background with this platform."
    )
    _add_common(service)
    service.add_argument("action", choices=("install", "status", "uninstall"))
    service.add_argument(
        "--no-activate",
        action="store_true",
        help="Write the definition without asking the service manager to load it now.",
    )

    remove = sub.add_parser("uninstall", help="State what removing Raiker takes, and take it.")
    _add_common(remove)
    remove.add_argument(
        "--data",
        choices=("keep", "export", "erase"),
        default="keep",
        help="What to do with each local instance (default: keep).",
    )
    remove.add_argument("--export-to", default=None, help="Where to copy instances before removal.")
    remove.add_argument(
        "--yes", action="store_true", help="Carry out the plan instead of only printing it."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "command", None):
        return _run_command(args)

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

    # BUG-40 — claim the workspace for this process, so `raiker-app status` in
    # another terminal, the in-app Host control, and the service manager are all
    # talking about the same host. Cleared on the way out whatever the reason,
    # including a crash-free quit, so a stale record never reports "running".
    control = HostControl(workspace)
    control.record_start(pid=os.getpid(), port=port)
    try:
        uvicorn.run(app, host=LOOPBACK, port=port)
    finally:
        control.clear()
    # Set by the Host control's Restart action: a status the platform's service
    # manager is configured to restart on, rather than a clean exit it would
    # (correctly) leave stopped.
    exit_code = getattr(app.state, "exit_code", 0)
    return int(exit_code) if isinstance(exit_code, int) else 0


# ── the lifecycle subcommands ────────────────────────────────────────────


def _resolved_workspace(args: argparse.Namespace) -> Path:
    return Path(args.workspace).expanduser() if args.workspace else default_workspace()


def _run_command(args: argparse.Namespace) -> int:
    workspace = _resolved_workspace(args)
    if args.command == "status":
        return _command_status(workspace, args.port)
    if args.command == "pause":
        HostControl(workspace).pause(args.reason)
        print("[raiker] Paused. No new background work will start until you resume.")
        return _command_status(workspace, args.port)
    if args.command == "resume":
        HostControl(workspace).resume()
        print("[raiker] Resumed. Scheduled work starts again from the next tick.")
        return _command_status(workspace, args.port)
    if args.command == "quit":
        return _command_quit(workspace, force=args.force)
    if args.command == "service":
        return _command_service(workspace, args.port, args.action, activate=not args.no_activate)
    return _command_uninstall(workspace, args)


def _command_status(workspace: Path, port: int) -> int:
    from raiker.app.service import registration

    status = HostControl(workspace).status()
    service = registration(workspace, port=port)
    print(f"[raiker] {status.state} — {status.detail}")
    print(f"[raiker] workspace: {workspace}")
    if status.pid is not None:
        print(f"[raiker] process {status.pid} on port {status.port}, since {status.started_at}")
    for item in status.waiting:
        print(f"[raiker]   · {item.label} — {item.detail}")
    if service.supported:
        state = "registered" if service.registered else "not registered"
        print(f"[raiker] background start: {state} ({service.mechanism})")
    else:
        print(f"[raiker] background start: {service.note}")
    return 0


def _command_quit(workspace: Path, *, force: bool) -> int:
    """Stop the host, stating what that interrupts before it happens."""
    control = HostControl(workspace)
    status = control.status()
    if status.state == "stopped":
        print("[raiker] No Raiker host is running for this workspace.")
        return 0
    if status.waiting and not force:
        print("[raiker] Not stopping — this would interrupt work in progress:")
        for item in status.waiting:
            print(f"[raiker]   · {item.label}")
            print(f"[raiker]     {item.detail}")
        print("[raiker] Run `raiker-app quit --force` if that is what you want.")
        return 1
    if not control.request_quit():
        print("[raiker] Could not signal the host. It may have already stopped.", file=sys.stderr)
        return 2
    print(f"[raiker] Asked process {status.pid} to stop at its next safe boundary.")
    return 0


def _command_service(workspace: Path, port: int, action: str, *, activate: bool) -> int:
    from raiker.app.service import install, registration, service_plan, uninstall

    plan = service_plan(workspace, port=port)
    if not plan.supported:
        print(f"[raiker] {plan.note}", file=sys.stderr)
        return 2
    if action == "status":
        current = registration(workspace, port=port)
        print(f"[raiker] {plan.mechanism}: {'registered' if current.registered else 'not registered'}")
        print(f"[raiker] definition: {plan.path}")
        print(f"[raiker] {plan.note}")
        return 0
    result = install(plan, activate=activate) if action == "install" else uninstall(plan)
    print(f"[raiker] {result.message}")
    for command in result.ran:
        print(f"[raiker]   ran: {command}")
    for failure in result.failed:
        print(f"[raiker]   could not: {failure}", file=sys.stderr)
    if action == "install":
        print(f"[raiker] {plan.note}")
    return 0 if result.ok else 2


def _command_uninstall(workspace: Path, args: argparse.Namespace) -> int:
    from raiker.app.uninstall import apply_uninstall, plan_uninstall

    try:
        plan = plan_uninstall(
            workspace,
            disposition=args.data,
            export_to=args.export_to,
            port=args.port,
        )
    except ValueError as error:
        message = {
            "export_requires_a_destination": "Pass --export-to with --data export.",
        }.get(str(error), str(error))
        print(f"[raiker] {message}", file=sys.stderr)
        return 2

    print("[raiker] Uninstalling Raiker would:")
    for line in plan.describe():
        print(f"[raiker]   {line}")
    if not args.yes:
        print("[raiker] Nothing has been changed. Re-run with --yes to carry this out.")
        return 0
    if plan.removes_data:
        print("[raiker] Removing instance data. This cannot be undone.")
    for line in apply_uninstall(plan, workspace, port=args.port):
        print(f"[raiker]   {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
