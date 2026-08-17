"""BUG-194 — Raiker's half of the supervisor channel.

`SupervisedProcess` is deliberately shaped like `RunningProcess`: `poll`,
`wait`, `write`, `terminate`. The service does not have two lifecycles to
reason about — it has one, and one of the two things that can be behind it
survives a restart.

The reattachment story is the whole point, so it is worth stating exactly what
is trusted. A stored handle carries a socket path and an instance key, both
encrypted at rest in `command_runs.encrypted_backend_handle`. Reattaching means
*authenticating* to whatever answers on that socket: a supervisor that returns a
frame this key verifies is Raiker's supervisor, and one that does not is
refused. That is the difference between this and a pid file — a pid can be
reused by a stranger, an HMAC over a fresh nonce cannot be produced by one.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.execution.commands.models import CommandState
from raiker.execution.commands.runner import CommandSink
from raiker.execution.commands.supervisor import (
    KEY_ENVIRONMENT_NAME,
    supervisor_supported,
)
from raiker.execution.commands.supervisor_protocol import (
    INSTANCE_KEY_BYTES,
    SupervisorCodec,
    SupervisorProtocolError,
    instance_key_from_hex,
    instance_key_to_hex,
)

__all__ = [
    "SupervisedProcess",
    "SupervisorHandle",
    "SupervisorUnavailable",
    "attach",
    "spawn_supervised",
    "supervisor_supported",
]

#: How often Raiker asks the supervisor what happened. A background run is
#: watched, not streamed byte-by-byte: a quarter second is far below anything a
#: person perceives and far above anything that costs.
POLL_INTERVAL_SECONDS = 0.25

#: Where a run's journal lives: inside `.raiker`, which the sandbox denies to
#: every governed command. The journal is the run's *output*, so it belongs with
#: the rest of the runtime's governed state and inside the workspace the owner
#: backs up.
SUPERVISOR_DIRECTORY = Path(".raiker") / "command-supervisors"

#: A `AF_UNIX` address is a fixed-size field in a kernel structure — 108 bytes
#: on Linux, 104 on macOS — and it is the *path string* that has to fit, not the
#: file. A workspace nested deeply enough would therefore make the socket
#: unbindable while every other part of the run worked, which is exactly the
#: class of failure BUG-216 records elsewhere in this repository. So the control
#: endpoint does not live beside the journal: it lives in a short, per-workspace
#: directory under the platform's runtime area, 0700, with the socket itself
#: 0600. The security argument does not rest on where the file is — the channel
#: is authenticated, and a caller without the run's instance key cannot produce
#: a frame it accepts — so moving it costs nothing and buys a bound that holds.
_MAX_UNIX_SOCKET_PATH = 100


def socket_directory(workspace_root: Path) -> Path:
    """A short, per-workspace, owner-only directory for control sockets."""
    import hashlib
    import tempfile

    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    digest = hashlib.sha256(str(workspace_root).encode()).hexdigest()[:10]
    return Path(base) / f"raiker-cmd-{digest}"

_STATES = {
    "succeeded": CommandState.SUCCEEDED,
    "failed": CommandState.FAILED,
    "timed_out": CommandState.TIMED_OUT,
    "cancelled": CommandState.CANCELLED,
}


class SupervisorUnavailable(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class SupervisorHandle:
    """The restart-safe handle. Stored encrypted; never logged."""

    socket_path: str
    journal_path: str
    instance_key_hex: str
    pty: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "unix_supervisor",
            "socket_path": self.socket_path,
            "journal_path": self.journal_path,
            "instance_key": self.instance_key_hex,
            "pty": self.pty,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SupervisorHandle:
        if str(value.get("kind")) != "unix_supervisor":
            raise SupervisorUnavailable("command_supervisor_handle_unsupported")
        try:
            return cls(
                socket_path=str(value["socket_path"]),
                journal_path=str(value["journal_path"]),
                instance_key_hex=str(value["instance_key"]),
                pty=bool(value.get("pty", False)),
            )
        except KeyError as exc:
            raise SupervisorUnavailable("command_supervisor_handle_invalid") from exc


class _Channel:
    """One authenticated request/response over the run's socket.

    A fresh connection per call rather than a held one, because the interesting
    case is precisely the one where the holder went away: a channel that only
    works while it is open would make reattachment depend on the thing
    reattachment exists to survive.
    """

    def __init__(self, socket_path: str, instance_key: bytes) -> None:
        self._socket_path = socket_path
        self._key = instance_key

    def call(self, kind: str, payload: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
        codec = SupervisorCodec(self._key)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(timeout)
                connection.connect(self._socket_path)
                connection.sendall(codec.encode(kind, payload))
                frame = _read_frame(connection)
        except (OSError, ValueError) as exc:
            raise SupervisorUnavailable("command_supervisor_unreachable") from exc
        try:
            response = codec.decode(frame)
        except SupervisorProtocolError as exc:
            raise SupervisorUnavailable("command_supervisor_authentication_failed") from exc
        if response.kind == "refused":
            raise SupervisorUnavailable(str(response.payload.get("reason", "command_supervisor_refused")))
        return dict(response.payload)


def _read_frame(connection: socket.socket) -> bytes:
    header = _read_exactly(connection, 4)
    size = int.from_bytes(header, "big")
    if size <= 0 or size > 8_388_608:
        raise ValueError("supervisor_frame_length_invalid")
    return header + _read_exactly(connection, size)


def _read_exactly(connection: socket.socket, count: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < count:
        chunk = connection.recv(count - len(buffer))
        if not chunk:
            raise ValueError("supervisor_frame_truncated")
        buffer.extend(chunk)
    return bytes(buffer)


class SupervisedProcess:
    """A background run watched through its supervisor.

    Shaped like `RunningProcess` on purpose. `after` is the sequence of the last
    journal record already delivered to the sink, which is what makes a reattach
    resume rather than replay: a restarted Raiker passes the sequence its store
    already holds and receives only what it missed.
    """

    def __init__(
        self,
        handle: SupervisorHandle,
        sink: CommandSink,
        *,
        max_output_bytes: int,
        after: int = 0,
        reattached: bool = False,
    ) -> None:
        self.handle = handle
        self.pty = handle.pty
        self.reattached = reattached
        self._channel = _Channel(handle.socket_path, instance_key_from_hex(handle.instance_key_hex))
        self._sink = sink
        self._cursor = after
        self._state: CommandState | None = None
        self._done = threading.Event()
        self._lock = threading.Lock()
        sink.configure_limit(max_output_bytes)
        self._worker = threading.Thread(target=self._pump, name="supervised-pump", daemon=True)
        self._worker.start()

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._cursor

    def _drain(self) -> dict[str, Any]:
        status = self._channel.call("read", {"after": self._cursor, "limit": 500})
        for chunk in status.get("chunks", []):
            stream = str(chunk.get("stream", "stdout"))
            raw = int(chunk.get("raw", 0))
            if raw:
                self._sink.record_raw(stream, raw)
            text = str(chunk.get("text", ""))
            if text:
                # Already redacted, in the supervisor, before it reached the
                # journal. Re-running the redactor here would be a second
                # opinion about bytes the first one already cleared.
                self._sink.append_safe(stream, text.encode("utf-8"))
            with self._lock:
                self._cursor = max(self._cursor, int(chunk.get("seq", self._cursor)))
        return status

    def _pump(self) -> None:
        try:
            while True:
                status = self._drain()
                if not bool(status.get("running", True)):
                    # One more drain: the child's last write and its exit are
                    # two events, and reading the status first can see the
                    # second before the first has been journalled.
                    status = self._drain()
                    self._sink.mark_redactions(int(status.get("redactions", 0)))
                    state = _STATES.get(str(status.get("state", "failed")), CommandState.FAILED)
                    with self._lock:
                        self._state = state
                    self._sink.complete(state, status.get("returncode"))
                    with contextlib.suppress(SupervisorUnavailable):
                        self._channel.call("release", {})
                    return
                if self._done.wait(POLL_INTERVAL_SECONDS):
                    return
        except SupervisorUnavailable:
            # The supervisor went away mid-run. That is a lost run, and the
            # service's own recovery path is what says so — reporting a
            # fabricated exit code here would be worse than saying nothing.
            with self._lock:
                self._state = None
        finally:
            self._done.set()

    def poll(self) -> CommandState | None:
        return self._state if self._done.is_set() else None

    def wait(self, timeout: float | None = None) -> CommandState:
        if not self._done.wait(timeout):
            raise TimeoutError("command_wait_timeout")
        if self._state is None:
            raise SupervisorUnavailable("command_supervisor_unreachable")
        return self._state

    def write(self, value: str | bytes) -> None:
        if not self.pty:
            raise RuntimeError("command_input_requires_pty")
        data = value if isinstance(value, str) else value.decode("utf-8", "replace")
        result = self._channel.call("input", {"data": data})
        self._sink.record_input(int(result.get("byte_count", 0)))

    def terminate(self) -> None:
        with contextlib.suppress(SupervisorUnavailable):
            self._channel.call("kill", {})

    def release(self) -> None:
        """Tell the supervisor nobody is coming back for this run.

        The linger window exists so a *restarting* Raiker can still collect an
        outcome. A Raiker that is shutting down deliberately is not restarting
        from the supervisor's point of view yet, so it says so and the process
        goes away now rather than holding for the full window.
        """
        self._done.set()
        with contextlib.suppress(SupervisorUnavailable):
            self._channel.call("release", {})


def spawn_supervised(
    *,
    workspace_root: Path,
    run_id: str,
    argv: list[str],
    cwd: Path,
    environment: dict[str, str],
    sink: CommandSink,
    deadline_seconds: float,
    max_output_bytes: int,
    pty: bool = False,
    registered_secrets: tuple[str, ...] = (),
) -> SupervisedProcess:
    """Start a detached supervisor and hand back a handle onto its child."""
    if not supervisor_supported():
        raise SupervisorUnavailable("command_supervisor_platform_unsupported")
    import hashlib

    directory = workspace_root / SUPERVISOR_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        directory.chmod(0o700)
    endpoints = socket_directory(workspace_root)
    endpoints.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        endpoints.chmod(0o700)
    socket_path = endpoints / f"{hashlib.sha256(run_id.encode()).hexdigest()[:16]}.sock"
    if len(str(socket_path)) > _MAX_UNIX_SOCKET_PATH:
        # Refused by name rather than attempted and mis-diagnosed later as a
        # supervisor that would not start.
        raise SupervisorUnavailable("command_supervisor_socket_path_too_long")
    journal_path = directory / f"{run_id}.journal"
    key = secrets.token_bytes(INSTANCE_KEY_BYTES)
    handle = SupervisorHandle(
        socket_path=str(socket_path),
        journal_path=str(journal_path),
        instance_key_hex=instance_key_to_hex(key),
        pty=pty,
    )
    specification = SupervisorCodec(key).encode(
        "start",
        {
            "argv": list(argv),
            "cwd": str(cwd),
            "env": dict(environment),
            "deadline_seconds": int(max(1, round(deadline_seconds))),
            "max_output_bytes": int(max_output_bytes),
            "pty": bool(pty),
            "secrets": list(registered_secrets),
        },
    )
    child_environment = dict(os.environ)
    child_environment[KEY_ENVIRONMENT_NAME] = handle.instance_key_hex
    try:
        process = subprocess.Popen(  # noqa: S603 - argv is this interpreter and this package
            [sys.executable, "-m", "raiker.execution.commands.supervisor",
             "--socket", str(socket_path), "--journal", str(journal_path)],
            cwd=str(workspace_root),
            env=child_environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # The whole point: its own session, so a signal to Raiker's process
            # group is not a signal to the run, and a restart of Raiker leaves
            # it standing.
            start_new_session=True,
        )
    except OSError as exc:
        raise SupervisorUnavailable("command_supervisor_launch_failed") from exc
    assert process.stdin is not None
    try:
        process.stdin.write(specification)
        process.stdin.close()
    except OSError as exc:
        with contextlib.suppress(Exception):
            process.kill()
        raise SupervisorUnavailable("command_supervisor_launch_failed") from exc
    _await_socket(socket_path, process)
    return SupervisedProcess(handle, sink, max_output_bytes=max_output_bytes)


def _await_socket(socket_path: Path, process: subprocess.Popen[bytes], *, timeout: float = 10.0) -> None:
    """Wait for the supervisor to be reachable, or say why it never was."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if socket_path.exists():
            return
        if process.poll() is not None:
            raise SupervisorUnavailable("command_supervisor_launch_failed")
        time.sleep(0.02)
    with contextlib.suppress(Exception):
        process.kill()
    raise SupervisorUnavailable("command_supervisor_launch_timeout")


def attach(
    handle: SupervisorHandle,
    sink: CommandSink,
    *,
    max_output_bytes: int,
    after: int = 0,
) -> SupervisedProcess:
    """Reattach to a run this runtime started before it restarted.

    Authenticates first and refuses on failure: a socket that cannot answer a
    frame keyed on the stored instance key is not this run's supervisor, and
    treating it as one is exactly the mistake a pid file makes.
    """
    if not supervisor_supported():
        raise SupervisorUnavailable("command_supervisor_platform_unsupported")
    channel = _Channel(handle.socket_path, instance_key_from_hex(handle.instance_key_hex))
    channel.call("poll", {})
    return SupervisedProcess(
        handle, sink, max_output_bytes=max_output_bytes, after=after, reattached=True
    )
