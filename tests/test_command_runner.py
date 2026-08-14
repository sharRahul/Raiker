from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from raiker.execution.commands import CommandRequest, CommandState
from raiker.execution.commands.redactor import StreamingRedactor
from raiker.execution.commands.runner import (
    MemoryCommandSink,
    StreamingCommandRunner,
)

LONG_SECRET = "credential-" + ("x" * 4097)
SECRET_PAYLOAD = ("prefix " + LONG_SECRET + " suffix").encode()


def request(workspace_root: Path, **overrides: object) -> CommandRequest:
    values: dict[str, object] = {
        "run_id": "cmd_runner",
        "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a",
        "session_id": "sess_a",
        "turn_id": "turn_a",
        "action_id": "act_a",
        "repository_id": None,
        "workspace_root": workspace_root,
        "cwd": ".",
        "executable_template": "python task.py",
        "argv_template": (),
        "safe_display": "python task.py",
        "credential_bindings": (),
        "shell": True,
        "interactive": False,
        "background": False,
        "timeout_seconds": 30.0,
        "max_output_bytes": 100_000,
        "environment_profile_id": "local_strict",
        "network_policy_id": None,
    }
    values.update(overrides)
    return CommandRequest(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("split", (0, 1, 7, 8, 256, 4096, len(SECRET_PAYLOAD)))
def test_no_secret_prefix_is_emitted_at_any_split(split: int) -> None:
    redactor = StreamingRedactor(registered=(LONG_SECRET,))
    emitted = redactor.feed(SECRET_PAYLOAD[:split])
    emitted += redactor.feed(SECRET_PAYLOAD[split:])
    emitted += redactor.finish()
    assert LONG_SECRET.encode() not in emitted
    assert emitted == b"prefix [REDACTED_CREDENTIAL] suffix"


def test_redactor_handles_utf8_and_private_key_boundaries() -> None:
    payload = (
        "before ☃ -----BEGIN PRIVATE KEY-----\nabc123\n"
        "-----END PRIVATE KEY----- after"
    ).encode()
    for split in range(len(payload) + 1):
        redactor = StreamingRedactor()
        emitted = redactor.feed(payload[:split]) + redactor.feed(payload[split:]) + redactor.finish()
        assert emitted.decode() == "before ☃ [REDACTED_PRIVATE_KEY] after"


class FakeProcess:
    def __init__(
        self,
        events: list[tuple[str, bytes]],
        *,
        returncode: int = 0,
        hang: bool = False,
        pty: bool = False,
    ) -> None:
        self.events = events
        self.returncode = returncode
        self.hang = hang
        self.pty = pty
        self.tree_terminated = False
        self.stdin_bytes = b""

    def iter_events(self):  # type: ignore[no-untyped-def]
        yield from self.events
        while self.hang and not self.tree_terminated:
            time.sleep(0.005)

    def wait(self) -> int:
        return self.returncode

    def poll(self) -> int | None:
        return None if self.hang and not self.tree_terminated else self.returncode

    def terminate_tree(self) -> None:
        self.tree_terminated = True
        self.returncode = -1

    def write(self, data: bytes) -> None:
        self.stdin_bytes += data


def test_runner_records_total_bytes_after_capture_is_truncated(tmp_path: Path) -> None:
    sink = MemoryCommandSink()
    process = FakeProcess([("stdout", b"abcdefghij")])
    handle = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(tmp_path, max_output_bytes=5), ["fake"], tmp_path, {}, sink, pty=False
    )
    assert handle.wait() is CommandState.SUCCEEDED
    assert sink.stdout_bytes == 10
    assert sink.captured_text == "abcde"
    assert sink.truncated is True


def test_split_registered_secret_never_reaches_sink(tmp_path: Path) -> None:
    sink = MemoryCommandSink()
    process = FakeProcess(
        [("stdout", SECRET_PAYLOAD[:2000]), ("stdout", SECRET_PAYLOAD[2000:])]
    )
    handle = StreamingCommandRunner(
        process_factory=lambda *_a, **_k: process,
        registered_secrets=(LONG_SECRET,),
    ).start(request(tmp_path), ["fake"], tmp_path, {}, sink, pty=False)
    assert handle.wait() is CommandState.SUCCEEDED
    assert LONG_SECRET not in sink.captured_text
    assert sink.captured_text == "prefix [REDACTED_CREDENTIAL] suffix"
    assert sink.redaction_count == 1


def test_timeout_terminates_process_tree(tmp_path: Path) -> None:
    process = FakeProcess([], hang=True)
    handle = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(tmp_path, timeout_seconds=0.01), ["fake"], tmp_path, {}, MemoryCommandSink(), pty=False
    )
    assert handle.wait() is CommandState.TIMED_OUT
    assert process.tree_terminated is True


def test_input_requires_a_pty_and_is_not_recorded(tmp_path: Path) -> None:
    process = FakeProcess([], pty=True)
    sink = MemoryCommandSink()
    handle = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(tmp_path, interactive=True), ["fake"], tmp_path, {}, sink, pty=True
    )
    handle.write("owner input\n")
    assert process.stdin_bytes == b"owner input\n"
    assert sink.input_events == [{"byte_count": 12}]
    assert "owner input" not in sink.captured_text

    non_pty = StreamingCommandRunner(
        process_factory=lambda *_a, **_k: FakeProcess([])
    ).start(request(tmp_path), ["fake"], tmp_path, {}, MemoryCommandSink(), pty=False)
    with pytest.raises(RuntimeError, match="command_input_requires_pty"):
        non_pty.write("no")


def test_real_process_streams_stdout_and_stderr(tmp_path: Path) -> None:
    sink = MemoryCommandSink()
    script = "import sys; print('out', flush=True); print('err', file=sys.stderr, flush=True)"
    handle = StreamingCommandRunner().start(
        request(tmp_path, executable_template="python stream", safe_display="python stream"),
        [sys.executable, "-c", script],
        tmp_path,
        {},
        sink,
        pty=False,
    )
    assert handle.wait() is CommandState.SUCCEEDED
    assert "out" in sink.stdout_text
    assert "err" in sink.stderr_text


def test_terminate_is_idempotent(tmp_path: Path) -> None:
    process = FakeProcess([], hang=True)
    handle = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(tmp_path), ["fake"], tmp_path, {}, MemoryCommandSink(), pty=False
    )
    handle.terminate()
    handle.terminate()
    assert handle.wait() is CommandState.CANCELLED
    assert process.tree_terminated is True
