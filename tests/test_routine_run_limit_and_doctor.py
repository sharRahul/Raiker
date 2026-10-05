"""DEC-12 steps 6 and 8 — a run is bounded, and a routine can be asked if it will run.

Step 6: one run of a routine had no time limit. It now has one — the routine's
own or the default — and at the limit the turn is asked to stop at its next
safe boundary through the same control as the owner's Stop; the run is
recorded as stopped by its limit and counts as a cycle that did not complete.

Step 8: a routine failed at 03:00 for reasons already true at 17:00. The doctor
asks the same questions before the run, from records only.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks import scheduler as scheduler_module
from raiker.tasks.doctor import routine_doctor
from raiker.tasks.manager import TaskManager
from raiker.tasks.run_limit import DEFAULT_MAX_RUN_MINUTES, effective_minutes, stopped_message
from raiker.tasks.scheduler import TaskScheduler

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


def test_no_run_is_unbounded() -> None:
    assert effective_minutes(None) == DEFAULT_MAX_RUN_MINUTES
    assert effective_minutes(5) == 5
    assert effective_minutes(0) == 1
    assert effective_minutes(10_000) == 720


def test_a_run_inside_its_limit_returns_its_answer(tmp_path: Path, routine: tuple[SQLiteStore, str]) -> None:
    store, _task_id = routine

    async def quick() -> SimpleNamespace:
        return SimpleNamespace(status="completed", message="done")

    response, overran = asyncio.run(
        TaskScheduler(tmp_path)._within_limit(  # noqa: SLF001 - the bound itself is under test
            quick(), seconds=5, session_id="sess_x", principal_id=_OWNER  # type: ignore[arg-type]
        )
    )
    assert not overran and response is not None and response.message == "done"


def test_an_overrun_asks_the_turn_to_stop_at_a_safe_boundary(
    tmp_path: Path, routine: tuple[SQLiteStore, str]
) -> None:
    store, _task_id = routine
    store.create_session("sess_run", str(tmp_path))
    stopped = asyncio.Event()

    async def slow() -> SimpleNamespace:
        # A turn that notices its stop control at the next boundary.
        for _ in range(200):
            await asyncio.sleep(0.01)
            with store.connect() as connection:
                row = connection.execute(
                    "SELECT stop_requested, stop_reason FROM turn_controls WHERE session_id = 'sess_run'"
                ).fetchone()
            if row is not None and row["stop_requested"]:
                assert row["stop_reason"] == "run_time_limit"
                stopped.set()
                return SimpleNamespace(status="stopped", message="Stopped.")
        return SimpleNamespace(status="completed", message="never stopped")

    response, overran = asyncio.run(
        TaskScheduler(tmp_path)._within_limit(  # noqa: SLF001
            slow(), seconds=0.05, session_id="sess_run", principal_id=_OWNER, grace_seconds=5  # type: ignore[arg-type]
        )
    )
    assert overran and response is None
    assert stopped.is_set()


def test_a_turn_that_never_reaches_a_boundary_is_abandoned_after_the_grace(
    tmp_path: Path, routine: tuple[SQLiteStore, str]
) -> None:
    async def stuck() -> SimpleNamespace:
        await asyncio.sleep(60)
        return SimpleNamespace(status="completed", message="late")

    started = datetime.now(UTC)
    _response, overran = asyncio.run(
        TaskScheduler(tmp_path)._within_limit(  # noqa: SLF001
            stuck(), seconds=0.05, session_id="sess_y", principal_id=_OWNER, grace_seconds=0.05  # type: ignore[arg-type]
        )
    )
    assert overran
    assert (datetime.now(UTC) - started).total_seconds() < 5


def test_the_scheduler_records_a_run_its_limit_ended(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    store.set_task_run_limit(task_id, 1)

    async def endless(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(60)
        return SimpleNamespace(status="completed", message="late")

    original = TaskScheduler._within_limit

    async def fast_limit(self: TaskScheduler, submission: object, **kwargs: object) -> object:
        assert kwargs["seconds"] == 60  # the routine's own one-minute limit
        return await original(self, submission, **{**kwargs, "seconds": 0.05, "grace_seconds": 0.05})  # type: ignore[arg-type]

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", endless)
    monkeypatch.setattr(scheduler_module.TaskScheduler, "_within_limit", fast_limit)
    asyncio.run(TaskScheduler(tmp_path).run_due())
    task = store.load_task(task_id)
    assert task is not None
    assert task.failed_cycles == 1
    assert task.summary is not None and task.summary.endswith(stopped_message(1))
    # A routine keeps its slot: one overrun is not the end of it.
    assert task.status == "queued"


def test_the_doctor_reads_records_and_names_what_would_stop_a_run(
    tmp_path: Path, routine: tuple[SQLiteStore, str]
) -> None:
    store, task_id = routine
    task = store.load_task(task_id)
    assert task is not None
    report = routine_doctor(store, task, owner_principal_id=_OWNER, workspace_root=tmp_path)
    checks = {check["key"]: check for check in report["checks"]}
    assert set(checks) == {"scheduler", "schedule", "clock", "model", "delivery", "limits"}
    # No host has ticked in a test workspace: unknown, never ok.
    assert checks["scheduler"]["state"] == "unknown"
    assert checks["limits"]["detail"].startswith(f"Each run is stopped after {DEFAULT_MAX_RUN_MINUTES} minutes")
    assert report["state"] in {"unknown", "blocked", "warn"}

    store.record_background_pass("scheduled_tasks")
    with store.connect() as connection:
        connection.execute("UPDATE tasks SET status = 'paused', failed_cycles = 3 WHERE task_id = ?", (task_id,))
    paused = store.load_task(task_id)
    assert paused is not None
    report = routine_doctor(store, paused, owner_principal_id=_OWNER, workspace_root=tmp_path)
    checks = {check["key"]: check for check in report["checks"]}
    assert checks["scheduler"]["state"] == "ok"
    assert checks["schedule"]["state"] == "blocked"
    assert "Continue it in Tasks" in checks["schedule"]["detail"]
    assert report["state"] == "blocked"


def test_the_doctor_says_when_quiet_hours_will_hold_the_notice(
    tmp_path: Path, routine: tuple[SQLiteStore, str]
) -> None:
    import json

    store, task_id = routine
    store.put_user_settings(
        _OWNER,
        json.dumps({
            "notification.quiet_hours.enabled": True,
            "notification.quiet_hours.start": "08:00",
            "notification.quiet_hours.end": "10:00",
            "notification.quiet_hours.timezone": "UTC",
        }),
        "2026-10-05T00:00:00Z",
    )
    task = store.load_task(task_id)
    assert task is not None
    report = routine_doctor(store, task, owner_principal_id=_OWNER, workspace_root=tmp_path)
    delivery = next(check for check in report["checks"] if check["key"] == "delivery")
    assert "falls in your quiet hours (08:00–10:00)" in delivery["detail"]


def test_the_doctor_says_no_model_rather_than_a_placeholder(
    tmp_path: Path, routine: tuple[SQLiteStore, str]
) -> None:
    store, task_id = routine
    task = store.load_task(task_id)
    assert task is not None
    report = routine_doctor(store, task, owner_principal_id=_OWNER, workspace_root=tmp_path)
    model = next(check for check in report["checks"] if check["key"] == "model")
    assert "<" not in model["detail"]
    assert model["state"] == "blocked"
    assert model["detail"].startswith("No model is chosen")


def test_a_routine_tool_limit_reaches_the_turn_and_the_doctor(
    tmp_path: Path, routine: tuple[SQLiteStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, task_id = routine
    seen: list[int] = []

    async def capture(_self: object, envelope: object) -> SimpleNamespace:
        seen.append(envelope.options.max_tool_calls)  # type: ignore[attr-defined]
        return SimpleNamespace(status="completed", message="done")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", capture)
    asyncio.run(TaskScheduler(tmp_path).run_due())
    from raiker.contracts.models import DEFAULT_MAX_TOOL_CALLS

    assert seen == [DEFAULT_MAX_TOOL_CALLS]  # no limit of its own: the runaway guard
    store.set_task_tool_limit(task_id, 25)
    with store.connect() as connection:
        connection.execute(
            "UPDATE tasks SET scheduled_at = '2020-01-01T09:00:00Z', status = 'queued' WHERE task_id = ?",
            (task_id,),
        )
    asyncio.run(TaskScheduler(tmp_path).run_due())
    assert seen[-1] == 25
    task = store.load_task(task_id)
    assert task is not None
    limits = next(
        check for check in routine_doctor(store, task, owner_principal_id=_OWNER, workspace_root=tmp_path)["checks"]
        if check["key"] == "limits"
    )
    assert "or 25 tool calls" in limits["detail"]
