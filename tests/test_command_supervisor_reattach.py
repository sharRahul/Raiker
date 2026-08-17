"""BUG-194 — a background run survives the restart of the runtime that started it.

The claim under test is not "a supervisor exists". It is the one the entry
called for: **restart, and the run is still there.** So the restart is real —
the service that started the run has its in-memory state dropped and a second
service is built against the same workspace, which is all a restarted Raiker
has — and the assertions are that the output the first service never saw still
arrives exactly once, and that the receipt says `succeeded` rather than `lost`.

The two refusals matter as much as the success. A socket that is gone, and a
socket that answers a frame the stored key does not authenticate, both end in
the same honest `lost` this file's predecessor already produced. That second one
is the case a pid file cannot tell apart from the real thing, which is why the
entry declined to build reattachment on one.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import utc_now
from raiker.execution.commands.models import TERMINAL_COMMAND_STATES, CommandState
from raiker.execution.commands.runner import MemoryCommandSink
from raiker.execution.commands.service import CommandService
from raiker.execution.commands.supervisor_client import (
    SupervisedProcess,
    SupervisorHandle,
    SupervisorUnavailable,
    supervisor_supported,
)
from raiker.execution.profiles import ProfileProbe

pytestmark = pytest.mark.skipif(
    not supervisor_supported(),
    reason="the detached supervisor is a POSIX capability and Windows says so by name",
)

OWNER = "owner_supervisor"


def _service(tmp_path: Path) -> CommandService:
    return CommandService(
        tmp_path,
        profile_probe=lambda profile: ProfileProbe(profile, True, None, utc_now()),
    )


def _start(service: CommandService, argv: list[str], *, timeout: float = 60.0) -> str:
    return service.start(
        owner_principal_id=OWNER,
        acting_principal_id="agent_supervisor",
        session_id="sess_supervisor",
        turn_id="turn_supervisor",
        action_id="act_supervisor",
        authority_kind="session_command_grant",
        authority_id="grant_supervisor",
        command="",
        argv=argv,
        background=True,
        timeout_seconds=timeout,
    ).run_id


def _await(predicate: Any, *, seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _release(handle: SupervisorHandle) -> None:
    """Stop a supervisor a test deliberately orphaned.

    A test that simulates a crashed or unreachable Raiker leaves a supervisor
    holding its linger window open, which is correct behaviour and a leaked
    process for the rest of the suite. Releasing it here keeps the scenario
    honest and the machine clean.
    """
    with contextlib.suppress(Exception):
        process = SupervisedProcess(handle, MemoryCommandSink(), max_output_bytes=1_000)
        process.terminate()
        process.release()


def _text(service: CommandService, run_id: str) -> str:
    return "".join(chunk["text"] for chunk in service.read_log(OWNER, run_id)["chunks"])


def _fifo(tmp_path: Path, name: str = "pipe") -> Path:
    """A named pipe inside the workspace, so an allowlisted `cat` can be the run.

    The governed allowlist refuses interpreters and refuses `python -c`, which
    is the invariant working — a background test must not be the one thing that
    gets to run arbitrary source. A FIFO gives the same control with none of
    that: the test decides exactly when the run produces output and exactly when
    it ends, using a program the policy already permits.
    """
    path = tmp_path / name
    os.mkfifo(path)
    return path


class _Writer:
    """The other end of the FIFO, opened off the test thread.

    Opening a FIFO for writing blocks until a reader opens it, and the reader
    here is the governed run — so this has to happen off the thread that is
    about to assert on the run.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: Any = None
        self._ready = threading.Event()
        threading.Thread(target=self._open, daemon=True).start()

    def _open(self) -> None:
        self._handle = self._path.open("w", encoding="utf-8")
        self._ready.set()

    def write(self, line: str) -> None:
        assert self._ready.wait(20.0), "the governed run never opened the pipe"
        self._handle.write(line)
        self._handle.flush()

    def close(self) -> None:
        if self._ready.wait(20.0) and self._handle is not None:
            self._handle.close()


def test_a_background_run_is_started_in_a_detached_supervisor(tmp_path: Path) -> None:
    service = _service(tmp_path)
    fifo = _fifo(tmp_path)
    writer = _Writer(fifo)
    try:
        run_id = _start(service, ["cat", "pipe"])
        stored = service.store.load_backend_handle(OWNER, run_id)
        assert stored is not None
        assert stored["kind"] == "unix_supervisor"
        # The instance key is what makes reattachment an authentication rather
        # than a pid lookup. It is stored, and it is stored encrypted — reading
        # it back needs the app key, which is why this goes through the store.
        assert len(str(stored["instance_key"])) >= 64
        writer.write("from the supervisor\n")
        writer.close()
        assert _await(lambda: not service.poll(OWNER, run_id)["running"])
        assert service.poll(OWNER, run_id)["state"] == CommandState.SUCCEEDED.value
        assert "from the supervisor" in _text(service, run_id)
    finally:
        writer.close()
        service.shutdown()


def test_a_run_survives_the_restart_of_the_runtime_that_started_it(tmp_path: Path) -> None:
    first = _service(tmp_path)
    fifo = _fifo(tmp_path)
    writer = _Writer(fifo)
    run_id = _start(first, ["cat", "pipe"])
    writer.write("before the restart\n")
    assert _await(lambda: "before the restart" in _text(first, run_id))

    # The restart. Nothing the first service held survives; the workspace does,
    # which is all a restarted Raiker has to work from.
    first._lease_stop.set()  # noqa: SLF001 - a shutdown stops leases, not children
    first._active.clear()  # noqa: SLF001 - the point is that in-memory state is gone
    second = _service(tmp_path)
    second.recover_owner(OWNER)
    try:
        state = second.poll(OWNER, run_id)
        assert state["state"] != CommandState.LOST.value
        assert state["supervised"] is True
        assert state["reattached"] is True
        # The half of the run the first service never saw.
        writer.write("after the restart\n")
        writer.close()
        assert _await(lambda: not second.poll(OWNER, run_id)["running"])
        assert second.poll(OWNER, run_id)["state"] == CommandState.SUCCEEDED.value
        text = _text(second, run_id)
        # Exactly once each: the reattach resumed from the sequence the store
        # already held rather than replaying the journal from the beginning.
        assert text.count("before the restart") == 1
        assert text.count("after the restart") == 1
        receipt = second.store.get_receipt(OWNER, run_id)
        assert receipt is not None and receipt.state is CommandState.SUCCEEDED
        # The handle is a key to a channel that no longer exists.
        assert second.store.load_backend_handle(OWNER, run_id) is None
    finally:
        writer.close()
        second.shutdown()


def test_a_run_whose_supervisor_is_gone_is_still_honestly_lost(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _fifo(tmp_path)
    # No writer: `cat` blocks on the pipe, so the run is genuinely in flight.
    run_id = _start(service, ["cat", "pipe"])
    stored = service.store.load_backend_handle(OWNER, run_id)
    assert stored is not None
    handle = SupervisorHandle.from_dict(stored)
    service._lease_stop.set()  # noqa: SLF001
    service._active.clear()  # noqa: SLF001
    # A supervisor that is no longer answering is exactly the case where "lost"
    # is the true answer, and it must stay the answer.
    Path(handle.socket_path).unlink(missing_ok=True)
    restarted = _service(tmp_path)
    try:
        restarted.recover_owner(OWNER)
        run = restarted.store.load(OWNER, run_id)
        assert run is not None
        assert run.state is CommandState.LOST
        assert run.termination_reason == "command_backend_handle_unavailable_after_restart"
    finally:
        restarted.shutdown()
        service.shutdown()
        _release(handle)


def test_reattachment_refuses_a_socket_it_cannot_authenticate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _fifo(tmp_path)
    run_id = _start(service, ["cat", "pipe"])
    stored = service.store.load_backend_handle(OWNER, run_id)
    assert stored is not None
    forged = dict(stored)
    forged["instance_key"] = "aa" * 32
    service.store.record_backend_handle(OWNER, run_id, forged)
    service._lease_stop.set()  # noqa: SLF001
    service._active.clear()  # noqa: SLF001
    restarted = _service(tmp_path)
    try:
        run = restarted.store.load(OWNER, run_id)
        assert run is not None
        assert restarted.reattach(run) is None
        restarted.recover_owner(OWNER)
        recovered = restarted.store.load(OWNER, run_id)
        assert recovered is not None and recovered.state in TERMINAL_COMMAND_STATES
    finally:
        restarted.shutdown()
        service.shutdown()
        _release(SupervisorHandle.from_dict(stored))


def test_a_handle_shape_this_runtime_does_not_know_is_refused() -> None:
    with pytest.raises(SupervisorUnavailable, match="unsupported"):
        SupervisorHandle.from_dict({"kind": "named_pipe", "socket_path": "x"})


def test_the_journal_is_bounded_in_size_and_in_page(tmp_path: Path) -> None:
    """Two bounds, and neither is belt-and-braces.

    The journal is on disk and the child decides how much it writes, so without
    a ceiling a command that prints without stopping fills the disk — a risk the
    in-process runner never had, because nothing between the pipe and the capped
    sink ever wrote the stream down. And a page larger than the codec's frame
    ceiling cannot be encoded at all, so an over-large read would reach the
    client as an *unreachable supervisor* — a chatty command indistinguishable
    from a crashed one.
    """
    from raiker.execution.commands.supervisor import _Journal

    journal = _Journal(tmp_path / "j.journal", max_text_bytes=64)
    journal.append("stdout", "a" * 40, 40)
    journal.append("stdout", "b" * 40, 40)
    assert journal.truncated is True

    records = journal.read_after(0, 500)
    kept = "".join(str(record["text"]) for record in records)
    assert len(kept.encode()) == 64
    # The raw total stays true: the receipt reports what the command really
    # produced, not what was kept.
    assert sum(int(record["raw"]) for record in records) == 80

    wide = _Journal(tmp_path / "w.journal", max_text_bytes=1_000_000)
    for _ in range(40):
        wide.append("stdout", "c" * 10_000, 10_000)
    page = wide.read_after(0, 500, max_bytes=50_000)
    assert 0 < len(page) < 40
    # Short pages are always safe: the caller comes back for the rest with the
    # last sequence it saw.
    assert wide.read_after(int(page[-1]["seq"]), 500, max_bytes=50_000)
