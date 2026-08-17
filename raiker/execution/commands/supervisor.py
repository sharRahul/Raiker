"""BUG-194 — the supervisor a background run lives in, so a restart can find it.

Before this, a background command was an ordinary child of the Raiker process.
That is the right shape for a foreground run and the wrong one for a background
one: when Raiker went away the pipes died with it, the reader thread went with
them, and the durable row could only be reconciled to ``lost``. The entry called
the missing piece "a detached supervisor with an authenticated control channel"
and declined to fake it with a pid file, which was right — **a bare pid cannot
tell "still running" from "pid reused"**, so a runtime that reattached by pid
would eventually reattach to a stranger.

This is that supervisor. It is a module of the Raiker package rather than a
second binary, which is what makes it packaged by construction: anywhere Raiker
runs, `python -m raiker.execution.commands.supervisor` runs.

**What it holds.** One child process, in its own session so the whole tree can
be signalled; the deadline that bounds it; the redactor every byte passes
through before anything is written down; and a journal on disk that is the
run's output.

**How it is reached.** A `AF_UNIX` socket in the workspace, mode 0600 inside a
0700 directory, speaking the same authenticated frames
`raiker.execution.commands.supervisor_protocol` already defines and already has
cross-language vectors for. The instance key never touches the command line and
never touches the disk in the clear: it arrives in the environment, and Raiker
keeps its copy inside `command_runs.encrypted_backend_handle`. Reattachment is
therefore an authentication, not a pid lookup — a socket that answers a frame
Raiker's key authenticates *is* Raiker's supervisor.

**Why it may outlive Raiker, when nothing else may.** The rule that a governed
command must not outlive the runtime that governs it exists so a command cannot
escape its governance. Here the governance travels with the command: the
supervisor holds the deadline itself and enforces it with no help, kills the
whole process group when it expires, and exits on its own after a bounded
linger if nobody ever comes back. A run in this supervisor is bounded by the
same two-hour ceiling it had before; what changed is who is holding the clock.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

from raiker.execution.commands.redactor import StreamingRedactor
from raiker.execution.commands.supervisor_protocol import (
    SupervisorCodec,
    SupervisorProtocolError,
    instance_key_from_hex,
)

#: How long the supervisor keeps answering after its child has exited, so a
#: Raiker that was restarting can still collect the outcome. After this it
#: exits and the run reconciles to `lost` — which is the honest answer, because
#: by then nothing holds the exit status.
#:
#: Fifteen minutes rather than an hour: a restart takes seconds, and the cost of
#: the window is a process per uncollected run held for its whole length. A
#: Raiker that has been down for a quarter of an hour is not restarting, it is
#: off, and `lost` is the true thing to say about its runs.
LINGER_SECONDS_AFTER_EXIT = 900.0

#: The environment variable carrying the instance key, as lowercase hex. Never
#: an argument: `ps` shows arguments to every user on the machine.
KEY_ENVIRONMENT_NAME = "RAIKER_COMMAND_SUPERVISOR_KEY"

#: Accept queue depth. One client (Raiker) at a time is the whole design; the
#: backlog only stops a reattach racing a poll from being refused outright.
_BACKLOG = 8


def supervisor_supported() -> bool:
    """Whether this platform can host a detached, reattachable supervisor.

    POSIX can: `AF_UNIX` gives a filesystem-addressed channel whose permissions
    are the workspace's, and `setsid` detaches the supervisor from Raiker's
    session so a restart of Raiker is not a signal to the run. Windows is
    refused here rather than served by a weaker thing under the same name — a
    named pipe is reachable by name from any session on the machine, so the
    channel's authorisation story is different enough that it needs its own
    design and its own proof, and claiming it from this code would be claiming
    something nobody measured.
    """
    return os.name != "nt" and hasattr(socket, "AF_UNIX")


class _Journal:
    """The run's output, on disk, already redacted.

    Append-only and read by offset, which is what makes a reattach cheap: the
    reader passes the last sequence it saw and gets only what is new. The
    redaction happens *before* a byte reaches this file, so the journal is
    never a copy of anything the redactor would have removed.
    """

    def __init__(self, path: Path, *, max_text_bytes: int) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sequence = 0
        #: The same ceiling the store-side sink enforces, applied here too. The
        #: journal is on disk and the child chooses how much it writes, so
        #: without this a command that prints without stopping fills the disk —
        #: which the in-process runner never risked, because nothing between the
        #: pipe and the capped sink ever wrote the stream down.
        self._max_text_bytes = max(1, max_text_bytes)
        self._text_bytes = 0
        self.truncated = False

    def append(self, stream: str, text: str, raw_bytes: int) -> None:
        with self._lock:
            remaining = max(0, self._max_text_bytes - self._text_bytes)
            encoded = text.encode("utf-8")
            if len(encoded) > remaining:
                # Past the ceiling the text stops and the counting does not: the
                # raw total stays true so the receipt reports what the command
                # really produced, not what was kept.
                self.truncated = True
                text = encoded[:remaining].decode("utf-8", "ignore")
            self._text_bytes += len(text.encode("utf-8"))
            self._sequence += 1
            record = {
                "seq": self._sequence,
                "stream": stream,
                "text": text,
                "raw": raw_bytes,
            }
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def read_after(self, after: int, limit: int, max_bytes: int = 262_144) -> list[dict[str, Any]]:
        """A page of records after `after`, bounded by count **and** by size.

        The byte bound is not belt-and-braces. A frame larger than the codec's
        ceiling cannot be encoded, and the failure would present to the client
        as an unreachable supervisor — so a chatty command would look exactly
        like a crashed one. Returning a shorter page is always safe: the caller
        passes the last sequence it saw and comes back for the rest.
        """
        if not self.path.exists():
            return []
        selected: list[dict[str, Any]] = []
        size = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if int(record.get("seq", 0)) <= after:
                    continue
                if selected and size + len(line) > max_bytes:
                    break
                selected.append(record)
                size += len(line)
                if len(selected) >= limit:
                    break
        return selected

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence


class CommandSupervisor:
    """One child, one socket, one deadline."""

    def __init__(
        self,
        *,
        socket_path: Path,
        journal_path: Path,
        codec: SupervisorCodec,
        argv: list[str],
        cwd: Path,
        environment: dict[str, str],
        deadline_seconds: float,
        pty: bool,
        max_output_bytes: int = 100_000,
        registered_secrets: tuple[str, ...] = (),
    ) -> None:
        self.socket_path = socket_path
        self.journal = _Journal(journal_path, max_text_bytes=max_output_bytes)
        self.codec = codec
        self.argv = argv
        self.cwd = cwd
        self.environment = environment
        self.deadline_seconds = deadline_seconds
        self.pty = pty
        self._registered_secrets = registered_secrets
        self._process: Any = None
        self._state = "running"
        self._returncode: int | None = None
        self._redactions = 0
        self._finished = threading.Event()
        self._released = threading.Event()
        self._lock = threading.Lock()

    # ── the child ────────────────────────────────────────────────────────────

    def _spawn(self) -> None:
        from raiker.execution.commands.runner import default_process_factory

        self._process = default_process_factory(
            self.argv, self.cwd, self.environment, pty=self.pty
        )

    def _pump(self) -> None:
        redactor = StreamingRedactor(registered=self._registered_secrets)
        active: str | None = None
        # Raw bytes the redactor is still holding back while it decides. They
        # are carried to the next record it releases rather than journalled on
        # their own, so **every journal record produces exactly one stored
        # chunk**. That one-to-one relation is what makes a reattach resumable:
        # the sequence the store already holds is the sequence to ask for next,
        # with no side table mapping one numbering onto the other.
        pending_raw = 0
        try:
            for stream, data in self._process.iter_events():
                selected = stream if stream in {"stdout", "stderr", "system"} else "system"
                if active is not None and selected != active:
                    boundary = redactor.feed(f"\n[stream:{selected}]\n".encode())
                    if boundary:
                        self.journal.append("system", boundary.decode("utf-8", "replace"), 0)
                active = selected
                pending_raw += len(data)
                safe = redactor.feed(data)
                if safe:
                    self.journal.append(selected, safe.decode("utf-8", "replace"), pending_raw)
                    pending_raw = 0
            returncode = self._process.wait()
            tail = redactor.finish()
            if tail or pending_raw:
                self.journal.append(
                    active or "system",
                    tail.decode("utf-8", "replace") if tail else "",
                    pending_raw,
                )
            with self._lock:
                self._redactions = redactor.redaction_count
                if self._state == "running":
                    self._state = "succeeded" if returncode == 0 else "failed"
                self._returncode = returncode
        except Exception:  # noqa: BLE001 — a pump that died still has to finalise
            with self._lock:
                if self._state == "running":
                    self._state = "failed"
        finally:
            self._finished.set()

    def _deadline(self) -> None:
        if self._finished.wait(self.deadline_seconds):
            return
        with self._lock:
            if self._state == "running":
                self._state = "timed_out"
        with contextlib.suppress(Exception):
            self._process.terminate_tree()

    # ── the channel ──────────────────────────────────────────────────────────

    def _status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "returncode": self._returncode,
                "running": not self._finished.is_set(),
                "sequence": self.journal.sequence,
                "redactions": self._redactions,
                "truncated": self.journal.truncated,
                "pty": self.pty,
                "pid": int(getattr(self._process, "pid", 0) or 0),
            }

    def _handle(self, kind: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if kind == "poll":
            return "status", self._status()
        if kind == "read":
            after = int(payload.get("after", 0))
            limit = max(1, min(int(payload.get("limit", 500)), 2000))
            chunks = self.journal.read_after(after, limit)
            return "output", {"chunks": chunks, **self._status()}
        if kind == "input":
            if not self.pty:
                return "refused", {"reason": "command_input_requires_pty"}
            data = str(payload.get("data", ""))
            try:
                self._process.write(data.encode("utf-8"))
            except Exception:  # noqa: BLE001 — the reason travels, the supervisor lives
                return "refused", {"reason": "command_input_unavailable"}
            return "accepted", {"byte_count": len(data.encode("utf-8"))}
        if kind == "kill":
            with self._lock:
                if self._state == "running":
                    self._state = "cancelled"
            with contextlib.suppress(Exception):
                self._process.terminate_tree()
            return "accepted", {"killed": True}
        if kind == "release":
            self._released.set()
            return "accepted", {"released": True}
        return "refused", {"reason": "supervisor_frame_kind_unsupported"}

    def _serve(self, server: socket.socket) -> None:
        while not self._released.is_set():
            try:
                connection, _ = server.accept()
            except OSError:
                return
            with contextlib.suppress(Exception), connection:
                connection.settimeout(30.0)
                frame = _read_frame(connection)
                request = self.codec.decode(frame)
                kind, payload = self._handle(request.kind, request.payload)
                connection.sendall(self.codec.encode(kind, payload))

    def run(self) -> int:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            self.socket_path.parent.chmod(0o700)
        with contextlib.suppress(FileNotFoundError):
            self.socket_path.unlink()
        server.bind(str(self.socket_path))
        with contextlib.suppress(OSError):
            self.socket_path.chmod(0o600)
        server.listen(_BACKLOG)
        try:
            self._spawn()
        except Exception:  # noqa: BLE001 — a launch failure is a status, not a crash
            with self._lock:
                self._state = "failed"
            self._finished.set()
        else:
            threading.Thread(target=self._pump, name="supervisor-pump", daemon=True).start()
            threading.Thread(target=self._deadline, name="supervisor-deadline", daemon=True).start()
        threading.Thread(target=self._serve, args=(server,), name="supervisor-serve", daemon=True).start()
        self._finished.wait()
        # Linger so a Raiker that was restarting can still collect the outcome,
        # but not forever: after this nothing holds the exit status and `lost`
        # becomes the true answer rather than a shrug.
        deadline = time.monotonic() + LINGER_SECONDS_AFTER_EXIT
        while not self._released.is_set() and time.monotonic() < deadline:
            time.sleep(0.25)
        with contextlib.suppress(OSError):
            server.close()
        with contextlib.suppress(FileNotFoundError):
            self.socket_path.unlink()
        return 0


def _read_frame(connection: socket.socket) -> bytes:
    header = _read_exactly(connection, 4)
    size = int.from_bytes(header, "big")
    if size <= 0 or size > 8_388_608:
        raise SupervisorProtocolError("supervisor_frame_length_invalid")
    return header + _read_exactly(connection, size)


def _read_exactly(connection: socket.socket, count: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < count:
        chunk = connection.recv(count - len(buffer))
        if not chunk:
            raise SupervisorProtocolError("supervisor_frame_truncated")
        buffer.extend(chunk)
    return bytes(buffer)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raiker-command-supervisor")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--journal", required=True)
    arguments = parser.parse_args(argv)
    key_hex = os.environ.get(KEY_ENVIRONMENT_NAME, "")
    if not key_hex:
        return 2
    codec = SupervisorCodec(instance_key_from_hex(key_hex))
    # The specification arrives on stdin as one authenticated frame. Not as
    # arguments: `ps` shows those to every user on the machine, and the argv of
    # a governed command is the command.
    try:
        specification = codec.decode(_read_stdin_frame()).payload
    except (SupervisorProtocolError, ValueError):
        return 3
    supervisor = CommandSupervisor(
        socket_path=Path(str(arguments.socket)),
        journal_path=Path(str(arguments.journal)),
        codec=codec,
        argv=[str(item) for item in specification.get("argv", [])],
        cwd=Path(str(specification.get("cwd", "."))),
        environment={str(k): str(v) for k, v in dict(specification.get("env", {})).items()},
        deadline_seconds=float(int(specification.get("deadline_seconds", 3600))),
        pty=bool(specification.get("pty", False)),
        max_output_bytes=int(specification.get("max_output_bytes", 100_000)),
        registered_secrets=tuple(str(item) for item in specification.get("secrets", [])),
    )
    return supervisor.run()


def _read_stdin_frame() -> bytes:
    stream = sys.stdin.buffer
    header = stream.read(4)
    if len(header) != 4:
        raise SupervisorProtocolError("supervisor_frame_truncated")
    size = int.from_bytes(header, "big")
    body = stream.read(size)
    if len(body) != size:
        raise SupervisorProtocolError("supervisor_frame_truncated")
    return header + body


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
