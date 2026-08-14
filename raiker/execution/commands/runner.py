from __future__ import annotations

import contextlib
import os
import queue
import signal
import subprocess
import threading
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, Protocol

from raiker.execution.commands.models import CommandRequest, CommandState
from raiker.execution.commands.redactor import StreamingRedactor


class StreamProcess(Protocol):
    def iter_events(self) -> Iterator[tuple[str, bytes]]: ...
    def wait(self) -> int: ...
    def poll(self) -> int | None: ...
    def terminate_tree(self) -> None: ...
    def write(self, data: bytes) -> None: ...


class CommandSink(Protocol):
    def configure_limit(self, limit: int) -> None: ...
    def record_raw(self, stream: str, byte_count: int) -> None: ...
    def append_safe(self, stream: str, data: bytes) -> None: ...
    def mark_redactions(self, count: int) -> None: ...
    def record_input(self, byte_count: int) -> None: ...
    def complete(self, state: CommandState, returncode: int | None) -> None: ...


class MemoryCommandSink:
    def __init__(self) -> None:
        self.max_output_bytes = 100_000
        self.stdout_bytes = 0
        self.stderr_bytes = 0
        self.stdout_text = ""
        self.stderr_text = ""
        self.truncated = False
        self.redaction_count = 0
        self.input_events: list[dict[str, int]] = []
        self.state: CommandState | None = None
        self.returncode: int | None = None

    @property
    def captured_text(self) -> str:
        return self.stdout_text + self.stderr_text

    def configure_limit(self, limit: int) -> None:
        self.max_output_bytes = limit

    def record_raw(self, stream: str, byte_count: int) -> None:
        if stream == "stderr":
            self.stderr_bytes += byte_count
        else:
            self.stdout_bytes += byte_count

    def append_safe(self, stream: str, data: bytes) -> None:
        captured = len(self.captured_text.encode("utf-8"))
        remaining = max(0, self.max_output_bytes - captured)
        if len(data) > remaining:
            self.truncated = True
        text = data[:remaining].decode("utf-8", errors="replace")
        if stream == "stderr":
            self.stderr_text += text
        else:
            self.stdout_text += text

    def mark_redactions(self, count: int) -> None:
        self.redaction_count += count

    def record_input(self, byte_count: int) -> None:
        self.input_events.append({"byte_count": byte_count})

    def complete(self, state: CommandState, returncode: int | None) -> None:
        self.state = state
        self.returncode = returncode


class _PopenProcess:
    def __init__(
        self,
        argv: Sequence[str],
        cwd: Path,
        env: dict[str, str],
        *,
        pty: bool,
    ) -> None:
        if pty:
            raise RuntimeError("command_pty_backend_unavailable")
        creationflags = (
            int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
        )
        self._process = subprocess.Popen(  # noqa: S603 - argv is a validated command contract
            list(argv),
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        self.pty = False

    def iter_events(self) -> Iterator[tuple[str, bytes]]:
        events: queue.Queue[tuple[str, bytes | None]] = queue.Queue()

        def read(stream: str, pipe: Any) -> None:
            try:
                while True:
                    data = pipe.read(4096)
                    if not data:
                        break
                    events.put((stream, data))
            finally:
                events.put((stream, None))

        assert self._process.stdout is not None and self._process.stderr is not None
        readers = [
            threading.Thread(target=read, args=("stdout", self._process.stdout), daemon=True),
            threading.Thread(target=read, args=("stderr", self._process.stderr), daemon=True),
        ]
        for reader in readers:
            reader.start()
        closed = 0
        while closed < len(readers):
            stream, data = events.get()
            if data is None:
                closed += 1
            else:
                yield stream, data

    def wait(self) -> int:
        return self._process.wait()

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate_tree(self) -> None:
        if self._process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(  # noqa: S603,S607 - fixed OS process-tree utility
                ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(  # type: ignore[attr-defined]  # Unix-only branch
                    self._process.pid,
                    signal.SIGKILL,  # type: ignore[attr-defined]  # Unix-only branch
                )

    def write(self, data: bytes) -> None:
        if self._process.stdin is None:
            raise RuntimeError("command_input_unavailable")
        self._process.stdin.write(data)
        self._process.stdin.flush()


class RunningProcess:
    def __init__(
        self,
        process: StreamProcess,
        request: CommandRequest,
        sink: CommandSink,
        *,
        pty: bool,
        registered_secrets: tuple[str, ...],
    ) -> None:
        self.process = process
        self.request = request
        self.sink = sink
        self.pty = pty
        self._registered_secrets = registered_secrets
        self._done = threading.Event()
        self._state: CommandState | None = None
        self._forced_state: CommandState | None = None
        self._lock = threading.Lock()
        sink.configure_limit(request.max_output_bytes)
        self._worker = threading.Thread(target=self._pump, daemon=True)
        self._worker.start()
        self._timer = threading.Timer(request.timeout_seconds, self._timeout)
        self._timer.daemon = True
        self._timer.start()

    def _pump(self) -> None:
        redactor = StreamingRedactor(registered=self._registered_secrets)
        active_stream: str | None = None
        returncode: int | None = None
        try:
            for stream, data in self.process.iter_events():
                selected = stream if stream in {"stdout", "stderr", "system"} else "system"
                self.sink.record_raw(selected, len(data))
                if active_stream is not None and selected != active_stream:
                    # stdout/stderr are one visual transcript. A visible,
                    # non-whitespace boundary prevents two independently benign
                    # fragments from reconstructing a canonical or registered
                    # credential when a client concatenates ordered chunks.
                    boundary = f"\n[stream:{selected}]\n".encode()
                    safe = redactor.feed(boundary)
                    if safe:
                        self.sink.append_safe("system", safe)
                active_stream = selected
                safe = redactor.feed(data)
                if safe:
                    self.sink.append_safe(selected, safe)
            returncode = self.process.wait()
            safe = redactor.finish()
            if safe:
                self.sink.append_safe(active_stream or "system", safe)
            self.sink.mark_redactions(redactor.redaction_count)
            with self._lock:
                state = self._forced_state or (
                    CommandState.SUCCEEDED if returncode == 0 else CommandState.FAILED
                )
                self._state = state
            self.sink.complete(state, returncode)
        finally:
            self._done.set()

    def _timeout(self) -> None:
        if self._done.is_set():
            return
        with self._lock:
            if self._forced_state is None:
                self._forced_state = CommandState.TIMED_OUT
        self.process.terminate_tree()

    def poll(self) -> CommandState | None:
        return self._state if self._done.is_set() else None

    def wait(self, timeout: float | None = None) -> CommandState:
        if not self._done.wait(timeout):
            raise TimeoutError("command_wait_timeout")
        self._timer.cancel()
        assert self._state is not None
        return self._state

    def write(self, value: str | bytes) -> None:
        if not self.pty:
            raise RuntimeError("command_input_requires_pty")
        data = value.encode() if isinstance(value, str) else value
        self.process.write(data)
        self.sink.record_input(len(data))

    def terminate(self) -> None:
        if self._done.is_set():
            return
        with self._lock:
            if self._forced_state is None:
                self._forced_state = CommandState.CANCELLED
        self.process.terminate_tree()


class StreamingCommandRunner:
    def __init__(
        self,
        *,
        process_factory: Callable[..., StreamProcess] | None = None,
        registered_secrets: Sequence[str] = (),
    ) -> None:
        self._process_factory = process_factory or _PopenProcess
        self._registered_secrets = tuple(registered_secrets)

    def start(
        self,
        request: CommandRequest,
        argv: Sequence[str],
        cwd: Path,
        env: dict[str, str],
        sink: CommandSink,
        *,
        pty: bool,
    ) -> RunningProcess:
        process = self._process_factory(argv, cwd, env, pty=pty)
        if pty and not bool(getattr(process, "pty", False)):
            raise RuntimeError("command_pty_backend_unavailable")
        return RunningProcess(
            process,
            request,
            sink,
            pty=pty,
            registered_secrets=self._registered_secrets,
        )
