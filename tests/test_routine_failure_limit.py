"""DEC-12 step 6 — a routine that keeps failing is paused and the owner told.

A routine re-arms whatever one cycle did, so one whose every cycle failed used
to fail every morning for as long as nobody looked. Now:

* a cycle that completes starts the count again, so an occasional failure never
  stops a working routine;
* at :data:`ROUTINE_FAILURE_LIMIT` failures in a row the routine is *paused* —
  not failed, not retried — with its last reason, a ``task_paused`` event and
  one notice to the owner;
* the owner's Continue runs it once now, with the count reset, and its schedule
  carries on from there.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import ROUTINE_FAILURE_LIMIT, TaskScheduler

_OWNER = "principal_owner"


@pytest.fixture()
def routine(tmp_path: Path) -> tuple[SQLiteStore, str]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = f"sess_inbox_{_OWNER}"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id,
        title="Morning digest",
        objective="Summarise the inbox",
        scheduled_at="2020-01-01T09:00:00Z",
        recurrence="daily",
    )
    return store, task.task_id


def _cycle(
    tmp_path: Path, store: SQLiteStore, task_id: str, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """Make the routine due now and run exactly one cycle that ends in ``status``."""

    async def answer(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status=status, message=f"The provider said no ({status}).")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", answer)
    with store.connect() as connection:
        connection.execute(
            "UPDATE tasks SET scheduled_at = '2020-01-01T09:00:00Z' WHERE task_id = ? "
            "AND status = 'queued'",
            (task_id,),
        )
    asyncio.run(TaskScheduler(tmp_path).run_due())


def _paused_notices(store: SQLiteStore) -> list[dict[str, object]]:
    return [n for n in store.list_notifications(_OWNER) if n["kind"] == "task_paused"]


def test_the_limit_is_more_than_one(routine: tuple[SQLiteStore, str]) -> None:
    assert ROUTINE_FAILURE_LIMIT == 3


def test_failures_below_the_limit_keep_the_routine_armed(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    for _ in range(ROUTINE_FAILURE_LIMIT - 1):
        _cycle(tmp_path, store, task_id, monkeypatch, "failed")
    task = store.load_task(task_id)
    assert task is not None
    assert task.status == "queued"
    assert task.failed_cycles == ROUTINE_FAILURE_LIMIT - 1
    assert _paused_notices(store) == []


def test_a_completed_cycle_starts_the_count_again(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    for status in ("failed", "failed", "completed", "failed", "failed"):
        _cycle(tmp_path, store, task_id, monkeypatch, status)
    task = store.load_task(task_id)
    assert task is not None
    assert task.status == "queued"
    assert task.failed_cycles == 2


def test_at_the_limit_the_routine_is_paused_with_its_reason_and_the_owner_told(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    for _ in range(ROUTINE_FAILURE_LIMIT):
        _cycle(tmp_path, store, task_id, monkeypatch, "failed")

    task = store.load_task(task_id)
    assert task is not None
    assert task.status == "paused"
    assert task.summary is not None
    assert task.summary.startswith("Paused after 3 runs in a row did not complete.")
    assert "The provider said no (failed)." in task.summary
    assert task.recurrence == "daily"  # its terms are kept, not cleared

    types = [row["event_type"] for row in store.list_event_index(task_id=task_id, limit=100)]
    assert types.count("task_paused") == 1
    assert types.count("task_cycle_landed") == ROUTINE_FAILURE_LIMIT
    assert "task_failed" not in types  # paused, not failed

    notices = _paused_notices(store)
    assert len(notices) == 1
    assert notices[0]["subject_id"] == task_id
    assert "did not complete 3 times in a row" in str(notices[0]["body"])

    # A paused routine is not claimed by the next tick.
    asyncio.run(TaskScheduler(tmp_path).run_due())
    again = store.load_task(task_id)
    assert again is not None and again.status == "paused"


def test_continue_runs_it_once_now_and_puts_it_back_on_its_schedule(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    for _ in range(ROUTINE_FAILURE_LIMIT):
        _cycle(tmp_path, store, task_id, monkeypatch, "failed")

    answer = asyncio.run(TaskScheduler(tmp_path).resume_task(task_id, _OWNER))
    assert answer["ok"] is True
    assert answer["task_status"] == "queued"
    resumed = store.load_task(task_id)
    assert resumed is not None and resumed.failed_cycles == 0

    # A second press has nothing left to resume.
    second = asyncio.run(TaskScheduler(tmp_path).resume_task(task_id, _OWNER))
    assert second["ok"] is False

    async def completed(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status="completed", message="Digest sent.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1
    settled = store.load_task(task_id)
    assert settled is not None
    assert settled.status == "queued"  # armed for its next slot
    assert settled.scheduled_at is not None and settled.scheduled_at > "2026-01-01"


def test_another_owner_cannot_continue_it(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    for _ in range(ROUTINE_FAILURE_LIMIT):
        _cycle(tmp_path, store, task_id, monkeypatch, "failed")
    answer = asyncio.run(TaskScheduler(tmp_path).resume_task(task_id, "principal_other"))
    assert answer == {"ok": False, "reason_code": "task_not_found"}
