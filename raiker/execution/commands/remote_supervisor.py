"""Small remote-side direct-argv command supervisor."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from raiker.execution.commands.remote_envelope import PROTOCOL_VERSION, read_remote_envelope

SUPERVISOR_VERSION = "1.0.0"


def supervisor_artifact_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def probe_document() -> dict[str, object]:
    return {
        "available": True,
        "artifact_digest": supervisor_artifact_digest(),
        "features": {
            "background": False,
            "credential_delivery": False,
            "filtered_network": False,
            "pty": False,
            "restart_recovery": False,
            "shell": False,
        },
        "protocol": PROTOCOL_VERSION,
        "version": SUPERVISOR_VERSION,
    }


def execute_from_stream() -> int:
    envelope = read_remote_envelope(sys.stdin.buffer)
    root = Path(os.environ.get("RAIKER_REMOTE_WORKSPACE", ".")).resolve()
    cwd = (root / envelope.cwd).resolve()
    try:
        cwd.relative_to(root)
    except ValueError:
        return 125
    if not cwd.is_dir():
        return 125
    process = subprocess.Popen(  # noqa: S603 - validated direct argv, never shell source
        list(envelope.argv),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
        start_new_session=os.name != "nt",
    )
    try:
        return process.wait(timeout=envelope.timeout_seconds)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)  # type: ignore[attr-defined]
        else:
            process.kill()
        process.wait()
        return 124


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raiker-command-supervisor")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args(argv)
    if args.probe:
        print(json.dumps(probe_document(), sort_keys=True, separators=(",", ":")))
        return 0
    try:
        return execute_from_stream()
    except (OSError, ValueError):
        return 125


if __name__ == "__main__":  # pragma: no cover - console script boundary
    raise SystemExit(main())
