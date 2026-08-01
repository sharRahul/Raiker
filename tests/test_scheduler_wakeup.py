"""BUG-39 — a granted approval continues its scheduled run without waiting.

The old behaviour was correct but slow: the continuation happened on the host's
own 15-second sweep, so a decision granted just after a sweep left the task card
reading *waiting for approval* for most of the interval. These tests pin the two
halves of the fix — the signal itself, and the fact that resolving an approval
for a scheduled run raises it — plus the boundaries that keep it honest: a Chat
approval does not wake the scheduler, and a host with no worker listening is
never harmed by the nudge.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from raiker.api.routes_approvals import _nudge_scheduler
from raiker.tasks.wakeup import SchedulerWakeup


class _FakeState:
    def __init__(self, wakeup: object | None) -> None:
        if wakeup is not None:
            self.scheduler_wakeup = wakeup


class _FakeApp:
    def __init__(self, wakeup: object | None) -> None:
        self.state = _FakeState(wakeup)


class _FakeRequest:
    def __init__(self, wakeup: object | None) -> None:
        self.app = _FakeApp(wakeup)


class _RecordingWakeup:
    def __init__(self) -> None:
        self.requests = 0

    def request(self) -> None:
        self.requests += 1


# ── the signal ───────────────────────────────────────────────────────────


def test_a_nudge_before_anyone_waits_is_not_lost() -> None:
    """A decision that lands during startup must still be seen.

    The event is created before the loop exists, so `request` has to set it
    directly when nothing has waited yet; the first wait then returns at once
    instead of sitting out a full interval for a decision already made.
    """
    wakeup = SchedulerWakeup()
    wakeup.request()

    async def scenario() -> bool:
        return await wakeup.wait(timeout=5)

    assert asyncio.run(scenario()) is True


def test_waiting_returns_false_when_nothing_nudges() -> None:
    """The timeout path is the recovery path and must report itself as one."""

    async def scenario() -> bool:
        return await SchedulerWakeup().wait(timeout=0.01)

    assert asyncio.run(scenario()) is False


def test_a_nudge_wakes_a_waiter_immediately() -> None:
    async def scenario() -> tuple[bool, float]:
        wakeup = SchedulerWakeup()
        loop = asyncio.get_running_loop()
        waiter = asyncio.create_task(wakeup.wait(timeout=30))
        await asyncio.sleep(0)  # let the waiter bind the loop
        started = loop.time()
        wakeup.request()
        return await waiter, loop.time() - started

    nudged, elapsed = asyncio.run(scenario())
    assert nudged is True
    # The point of the fix: not "eventually", but "now".
    assert elapsed < 1.0


def test_a_nudge_is_consumed_so_the_next_wait_blocks_again() -> None:
    """One decision must not wake the worker forever."""

    async def scenario() -> tuple[bool, bool]:
        wakeup = SchedulerWakeup()
        wakeup.request()
        first = await wakeup.wait(timeout=5)
        second = await wakeup.wait(timeout=0.01)
        return first, second

    assert asyncio.run(scenario()) == (True, False)


def test_a_nudge_from_another_thread_reaches_the_loop() -> None:
    """Not every caller is on the host loop; a worker thread must still signal."""

    async def scenario() -> bool:
        wakeup = SchedulerWakeup()
        waiter = asyncio.create_task(wakeup.wait(timeout=30))
        await asyncio.sleep(0)
        await asyncio.to_thread(wakeup.request)
        return await waiter

    assert asyncio.run(scenario()) is True


# ── the resolve path ─────────────────────────────────────────────────────


def test_resolving_a_scheduled_run_approval_wakes_the_scheduler() -> None:
    wakeup = _RecordingWakeup()
    _nudge_scheduler(_FakeRequest(wakeup), "sess_inbox_principal_owner")  # type: ignore[arg-type]
    assert wakeup.requests == 1


def test_resolving_a_chat_approval_leaves_the_scheduler_alone() -> None:
    """A Chat tab continues its own turn; waking the sweep would be pure noise."""
    wakeup = _RecordingWakeup()
    _nudge_scheduler(_FakeRequest(wakeup), "sess_chat_1")  # type: ignore[arg-type]
    assert wakeup.requests == 0


def test_a_host_without_a_scheduler_is_unharmed_by_the_nudge() -> None:
    """Embedded and test hosts never start a worker; resolving must still work."""
    _nudge_scheduler(_FakeRequest(None), "sess_inbox_principal_owner")  # type: ignore[arg-type]


def test_the_created_app_exposes_a_wakeup_for_the_resolve_path(tmp_path: Path) -> None:
    from raiker.api.app import create_app

    app = create_app(tmp_path)
    assert isinstance(app.state.scheduler_wakeup, SchedulerWakeup)


# ── end to end through the API ───────────────────────────────────────────


@pytest.mark.parametrize("session_prefix", ["sess_inbox_", "sess_chat_"])
def test_resolve_records_the_outcome_and_nudges_only_for_scheduled_work(
    tmp_path: Path, session_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorded outcome is unchanged; only the extra signal is new.

    Driven through ``_record_resume_outcome`` rather than a full HTTP round trip
    because that function is where both effects meet: it is the one place that
    knows a parked turn exists *and* which session it belongs to.
    """
    from raiker.api import routes_approvals

    class _Store:
        def __init__(self, session_id: str) -> None:
            self.session_id = session_id
            self.recorded: list[str] = []

        def load_suspended_turn(self, _approval_id: str) -> dict[str, object]:
            return {
                "status": "suspended",
                "session_id": self.session_id,
                "turn_id": "turn_1",
            }

        def record_suspended_turn_outcome(self, _approval_id: str, outcome: str) -> bool:
            self.recorded.append(outcome)
            return True

    wakeup = _RecordingWakeup()
    store = _Store(f"{session_prefix}principal_owner")
    monkeypatch.setattr(routes_approvals, "_nudge_scheduler", routes_approvals._nudge_scheduler)

    result = routes_approvals._record_resume_outcome(
        _FakeRequest(wakeup),  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        "apr_1",
        {"status": "approved"},
    )

    assert result == {
        "resumable": True,
        "session_id": store.session_id,
        "turn_id": "turn_1",
    }
    assert json.loads(store.recorded[0]) == {"status": "approved"}
    assert wakeup.requests == (1 if session_prefix == "sess_inbox_" else 0)
