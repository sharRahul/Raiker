"""Start a live round on a genuinely empty workspace, or refuse to start one.

BUG-266. A round was reset by stopping ``raiker-web`` and running ``rm -rf`` on
its workspace. On Windows the SQLCipher file handle outlives the HTTP response
that reported the shutdown, so the removal silently failed and the next run
signed in against the *previous* round's account — reporting a first run that was
not one. Every ``FIXED_ITEMS`` entry proved on a "fresh" workspace inherits that
doubt, which is why this is a defect in the harness and not an operator error.

Three things have to be true, in this order, and each is checked rather than
assumed:

1. Nothing is listening on the round's port. The HTTP response is not the
   evidence — a host can answer and still hold the store open for a moment
   afterwards, which is exactly the window that made the failure invisible.
2. The workspace directory is gone. Removal is retried briefly, because a
   lagging handle is normal and a first failure is not proof of a stuck one.
3. It is gone *after* the removal returned, read back from the filesystem.

Any of the three failing exits non-zero with the reason. A reset that cannot
complete must stop the round rather than hand it the previous one's data.

    python scripts/reset_live_workspace.py /tmp/raiker-manual-test --port 8765
"""

from __future__ import annotations

import argparse
import shutil
import socket
import sys
import time
from pathlib import Path

#: How long to wait for a host to let go of its port, in seconds. Generous
#: because the cost of waiting is a few seconds and the cost of not waiting is a
#: round of evidence about the wrong state.
PORT_RELEASE_TIMEOUT = 30.0

#: How long to keep retrying the removal itself. Windows releases a lagging
#: SQLCipher handle in well under a second; anything past this is stuck, not slow.
REMOVAL_TIMEOUT = 15.0


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    """Whether anything accepts a connection there right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0


def wait_for_port_release(port: int, *, timeout: float = PORT_RELEASE_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_is_open(port):
            return True
        time.sleep(0.25)
    return not port_is_open(port)


def remove_workspace(workspace: Path, *, timeout: float = REMOVAL_TIMEOUT) -> str | None:
    """Remove the directory and read back that it is gone. Returns why not, or ``None``.

    ``shutil.rmtree`` raising is only one of the two ways this fails. The other —
    the one BUG-266 was — is a removal that reports nothing and leaves the
    directory in place, so the answer comes from the filesystem afterwards rather
    than from the absence of an exception.
    """
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while True:
        if not workspace.exists():
            return None
        try:
            shutil.rmtree(workspace)
        except OSError as error:
            last_error = error
        if not workspace.exists():
            return None
        if time.monotonic() >= deadline:
            break
        time.sleep(0.25)
    if last_error is not None:
        return f"{workspace} could not be removed: {last_error}"
    return f"{workspace} still exists after removal reported no error"


def reset(
    workspace: Path, port: int | None, *, timeout: float = PORT_RELEASE_TIMEOUT
) -> str | None:
    """Do the reset, or say why the round must not start. ``None`` means ready."""
    if port is not None and not wait_for_port_release(port, timeout=timeout):
        return (
            f"something is still listening on 127.0.0.1:{port}. "
            "Stop raiker-web and wait for the process to exit before resetting."
        )
    failure = remove_workspace(workspace)
    if failure is not None:
        return failure
    workspace.mkdir(parents=True, exist_ok=True)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, help="the round's workspace directory")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="the port the host was bound to; the reset waits for it to be free",
    )
    args = parser.parse_args(argv)
    failure = reset(args.workspace.expanduser(), args.port)
    if failure is not None:
        print(f"live workspace reset failed: {failure}", file=sys.stderr)
        return 1
    print(f"live workspace ready: {args.workspace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
