"""Detached, signed-update handoff for a running Raiker host.

The web host must never replace the tree it is executing from.  This small
process is started by an owner-confirmed Settings action, waits for that host to
exit cleanly, then performs the same signed release check and atomic install as
``raiker-app update --apply`` before launching Raiker again.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from raiker.app.installation import detect_installation, read_channel_config
from raiker.app.updater import check_for_update, download_and_apply


def wait_for_exit(pid: int, *, poll_seconds: float = 0.2) -> None:
    """Wait for the named parent without trusting a pid file or arbitrary path."""
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            # A parent we cannot inspect is still alive from this user's point
            # of view. Retrying is safer than changing files under it.
            pass
        time.sleep(poll_seconds)


def apply_after_host_exit(
    workspace: str | Path,
    *,
    parent_pid: int,
    restart_command: list[str],
) -> int:
    """Wait, re-check, verify/install, then restart; failures leave it stopped."""
    root = Path(workspace)
    wait_for_exit(parent_pid)
    installation = detect_installation()
    status = check_for_update(root, installation=installation)
    if status.state != "available" or status.available is None:
        return 2
    channel = read_channel_config(root)
    if channel is None:
        return 2
    try:
        download_and_apply(
            root,
            status=status,
            config=channel,
            install_root=installation.install_root,
        )
    except Exception:  # the installer has already retained/rolled back safely
        return 2
    try:
        subprocess.Popen(  # noqa: S603 - command is built by this module
            [*restart_command, "--workspace", str(root)],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return 2
    return 0


def launcher_command() -> list[str]:
    """The installed launcher, without shell interpolation or user input."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "apps.api.launcher"]


def start_update_handoff(workspace: str | Path, *, parent_pid: int) -> None:
    """Start the updater independently of the web host's process group."""
    command = [
        sys.executable,
        "-m",
        "raiker.app.update_handoff",
        "--workspace",
        str(Path(workspace)),
        "--parent-pid",
        str(parent_pid),
    ]
    kwargs: dict[str, object] = {
        "cwd": str(Path(workspace)),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if platform.system().lower().startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)  # noqa: S603 - fixed local Python module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raiker-update-handoff")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--parent-pid", required=True, type=int)
    args = parser.parse_args(argv)
    return apply_after_host_exit(
        args.workspace,
        parent_pid=args.parent_pid,
        restart_command=launcher_command(),
    )


if __name__ == "__main__":  # pragma: no cover - exercised by the detached process
    raise SystemExit(main())
