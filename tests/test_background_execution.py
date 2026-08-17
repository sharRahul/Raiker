"""BUG-194 — background execution, observation, and a terminal a run can be typed into.

The entry said each of these is a *component*, not a flag, and that shipping the
flag alone would be worse than refusing: an orphan process holding a sandbox
grant nothing reclaims, or an agent that starts work it cannot poll. Both halves
are therefore under test together —

* the **lease**, which is what makes an unsupervised run reclaimable rather than
  orphaned, and the reconciliation that acts on a lapsed one;
* the **observation surface** (`poll`, `log`, `wait`, `kill`, `input`), which is
  what makes a started run something an agent can finish reasoning about.

Restart reattachment is deliberately *not* claimed here and stays open: a
restarted Raiker still reconciles an in-flight run to `lost` with an honest
receipt, which is a different outcome from the one this change adds.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import utc_now
from raiker.execution.commands.models import (
    TERMINAL_COMMAND_STATES,
    CommandState,
    StoredCommandRun,
)
from raiker.execution.commands.runner import pty_supported
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.execution.profiles import ProfileProbe

OWNER = "owner_bg"

#: A long-running command built only from the governed allowlist. `sort` reads
#: stdin to EOF before producing anything, so on a pipe that is never closed it
#: blocks indefinitely — which is what a background test needs — and on a
#: terminal it produces *reordered* output, which is what distinguishes "the
#: program read my input" from "the terminal echoed it back".
_BLOCKS_ON_STDIN = ["sort"]


def _service(tmp_path: Path) -> CommandService:
    return CommandService(
        tmp_path,
        profile_probe=lambda profile: ProfileProbe(profile, True, None, utc_now()),
    )


def _start(service: CommandService, argv: list[str], **overrides: object) -> StoredCommandRun:
    call: dict[str, object] = {
        "owner_principal_id": OWNER,
        "acting_principal_id": "agent_bg",
        "session_id": "sess_bg",
        "turn_id": "turn_bg",
        "action_id": "act_bg",
        "authority_kind": "session_command_grant",
        "authority_id": "grant_bg",
        "command": "",
        "argv": argv,
        "timeout_seconds": 30.0,
    }
    call.update(overrides)
    return service.start(**call)  # type: ignore[arg-type]


def _await_state(
    service: CommandService, run_id: str, *, seconds: float = 20.0
) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status = service.poll(OWNER, run_id)
        if not status["running"]:
            return status
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} never reached a terminal state")


def test_a_background_run_returns_immediately_and_is_pollable_to_completion(
    tmp_path: Path,
) -> None:
    """The whole point: the turn does not wait, and the run is still observable.

    Two runs, because the two halves need different evidence. A command that
    blocks proves `start` really returned early — a fast one would have finished
    before the assertion and proved nothing. A command that exits proves the
    unwaited-for run still lands in a terminal state with a receipt.
    """
    service = _service(tmp_path)
    blocking = _start(service, _BLOCKS_ON_STDIN, background=True)
    try:
        assert blocking.state is CommandState.RUNNING
        first = service.poll(OWNER, blocking.run_id)
        assert first["running"] is True
        assert first["supervised"] is True
        assert first["lease_expires_at"], "a background run must hold a lease"
        service.stop(OWNER, blocking.run_id)

        quick = _start(service, ["echo", "started"], background=True)
        final = _await_state(service, quick.run_id)
        assert final["state"] == CommandState.SUCCEEDED.value
        assert final["exit_code"] == 0
        assert final["receipt_digest"], "a terminal run always carries a receipt"
    finally:
        service.shutdown()


def test_the_log_is_readable_in_pages_and_resumes_where_it_stopped(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = _start(
        service,
        ["echo", "alpha beta"],
        background=True,
    )
    try:
        _await_state(service, run.run_id)
        page = service.read_log(OWNER, run.run_id, after=0)
        assert "alpha" in "".join(chunk["text"] for chunk in page["chunks"])
        # Resuming from the last sequence returns nothing new rather than
        # repeating the page, which is what makes polling a long run cheap.
        resumed = service.read_log(
            OWNER, run.run_id, after=page["next_after"]
        )
        assert resumed["chunks"] == []
        assert resumed["next_after"] == page["next_after"]
    finally:
        service.shutdown()


def test_wait_blocks_until_the_run_finishes_and_a_short_wait_says_so(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = _start(
        service,
        _BLOCKS_ON_STDIN,
        background=True,
    )
    run_id = run.run_id
    try:
        # A timeout is not an error. The run is genuinely still going, and the
        # caller learns that from `state` rather than from an exception it would
        # have to tell apart from a real failure.
        early = service.wait(OWNER, run_id, timeout_seconds=1.0)
        assert early["running"] is True
        assert early["state"] == CommandState.RUNNING.value

        service.stop(OWNER, run_id)
        finished = service.wait(OWNER, run_id, timeout_seconds=20.0)
        assert finished["running"] is False
        assert finished["state"] == CommandState.CANCELLED.value
    finally:
        service.shutdown()


def test_killing_a_background_run_produces_a_cancelled_receipt(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = _start(
        service,
        _BLOCKS_ON_STDIN,
        background=True,
    )
    try:
        service.stop(OWNER, run.run_id)
        final = _await_state(service, run.run_id)
        assert final["state"] == CommandState.CANCELLED.value
        receipt = service.store.get_receipt(OWNER, run.run_id)
        assert receipt is not None and receipt.state is CommandState.CANCELLED
    finally:
        service.shutdown()


def test_a_lapsed_lease_is_reclaimed_with_an_honest_receipt_not_left_running(
    tmp_path: Path,
) -> None:
    """The safeguard that makes background execution offerable at all.

    The lease is backdated to simulate a supervisor that stopped renewing — a
    crashed worker, a wedged backend. The run must be terminated and finalised
    with a receipt that *names* the reason, never quietly marked succeeded.
    """
    service = _service(tmp_path)
    run = _start(
        service,
        _BLOCKS_ON_STDIN,
        background=True,
    )
    run_id = run.run_id
    try:
        service.store.renew_lease(OWNER, run_id, "2000-01-01T00:00:00Z")
        assert [item.run_id for item in service.store.list_expired_leases(OWNER)] == [run_id]

        assert service.reconcile_leases(OWNER) == [run_id]

        reclaimed = service.store.load(OWNER, run_id)
        assert reclaimed is not None
        assert reclaimed.state in TERMINAL_COMMAND_STATES
        receipt = service.store.get_receipt(OWNER, run_id)
        assert receipt is not None
        assert receipt.termination_reason == "command_background_lease_expired"
        # And it is genuinely gone, not merely marked.
        assert service.reconcile_leases(OWNER) == []
    finally:
        service.shutdown()


def test_a_foreground_run_holds_no_lease_and_is_never_swept(tmp_path: Path) -> None:
    """`lease_expires_at IS NULL` must not read as "expired"."""
    service = _service(tmp_path)
    run = _start(service, _BLOCKS_ON_STDIN)
    try:
        assert service.poll(OWNER, run.run_id)["lease_expires_at"] is None
        assert service.store.list_expired_leases(OWNER) == []
        assert service.reconcile_leases(OWNER) == []
    finally:
        service.shutdown()


def test_polling_an_unknown_run_is_a_named_refusal(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(CommandServiceError, match="command_run_not_found"):
        service.poll(OWNER, "cmd_does_not_exist")
    # And one owner cannot reach another's run even holding its id.
    run = _start(service, ["echo", "hello"], background=True)
    try:
        with pytest.raises(CommandServiceError, match="command_run_not_found"):
            service.poll("owner_someone_else", run.run_id)
    finally:
        service.shutdown()


@pytest.mark.skipif(not pty_supported(), reason="this platform has no pseudo-terminal")
def test_an_interactive_run_gets_a_real_terminal_and_can_be_typed_into(
    tmp_path: Path,
) -> None:
    """PTY plus raw input, proven by the program *reading* what was written.

    A terminal echoes what is typed, so finding the input in the output would
    prove only that the bytes reached the terminal. `sort` emits its input
    *reordered* after EOF, and ^D is EOF only because the child really has a
    terminal in canonical mode — so the assertion is that the last `alpha`
    precedes the last `beta`, which the echo alone (typed beta first) cannot
    produce.
    """
    service = _service(tmp_path)
    run = _start(
        service,
        _BLOCKS_ON_STDIN,
        background=True,
        interactive=True,
    )
    run_id = run.run_id
    try:
        service.send_input(OWNER, run_id, "beta\nalpha\n\x04")
        final = _await_state(service, run_id)
        assert final["state"] == CommandState.SUCCEEDED.value
        text = "".join(
            chunk["text"] for chunk in service.read_log(OWNER, run_id, after=0)["chunks"]
        )
        assert "alpha" in text and "beta" in text
        assert text.rindex("alpha") < text.rindex("beta"), (
            "sort must have read the input and reordered it; the terminal echo "
            f"alone would leave beta first: {text!r}"
        )
    finally:
        service.shutdown()


@pytest.mark.skipif(not pty_supported(), reason="this platform has no pseudo-terminal")
def test_input_to_a_run_without_a_terminal_is_refused_rather_than_written_to_a_pipe(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    run = _start(
        service,
        _BLOCKS_ON_STDIN,
        background=True,
    )
    try:
        with pytest.raises(CommandServiceError, match="command_input_requires_pty"):
            service.send_input(OWNER, run.run_id, "hello\n")
    finally:
        service.shutdown()
