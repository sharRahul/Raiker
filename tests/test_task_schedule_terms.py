"""UX-TASK-02 — a schedule is read in its owner's zone, ends, and says what a missed slot does.

Before this, every cadence was a fixed number of seconds from the slot before,
stored and stepped in UTC. "Daily at 09:00" in London became 10:00 the morning
after the clocks went back. These cases pin the three decisions the release
review asks for — zone, bounds and missed-run policy — and the two DST cases the
Tasks guide promises: a skipped local hour runs at the old offset, a repeated
one runs once.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.schedule import (
    DEFAULT_MISSED_RUN_POLICY,
    TASK_REPEATING,
    first_slot,
    format_instant,
    next_occurrence,
    parse_instant,
    schedule_terms,
)
from raiker.tasks.scheduler import MISSED_RUN_SKIPPED, TaskScheduler

OWNER = "principal_owner"


def _walk(anchor: str, recurrence: str, zone: str | None, count: int) -> list[str]:
    slots: list[str] = []
    after = parse_instant(anchor) - timedelta(seconds=1)
    for _ in range(count):
        after = next_occurrence(anchor, recurrence, zone, after)
        slots.append(format_instant(after))
    return slots


class TestCalendarCadences:
    def test_daily_keeps_the_local_time_across_the_autumn_change(self) -> None:
        # 09:00 in London is 08:00Z in summer and 09:00Z in winter.
        slots = _walk("2026-10-23T08:00:00Z", "daily", "Europe/London", 4)
        assert slots == [
            "2026-10-23T08:00:00Z",
            "2026-10-24T08:00:00Z",
            "2026-10-25T09:00:00Z",
            "2026-10-26T09:00:00Z",
        ]

    def test_daily_keeps_the_local_time_across_the_spring_change(self) -> None:
        slots = _walk("2026-03-27T09:00:00Z", "daily", "Europe/London", 3)
        assert slots == ["2026-03-27T09:00:00Z", "2026-03-28T09:00:00Z", "2026-03-29T08:00:00Z"]

    def test_a_local_time_the_clocks_skip_runs_at_the_old_offset_that_day_only(self) -> None:
        # 01:30 does not exist in London on 29 March 2026; it runs at 01:30Z
        # (02:30 BST) and is back to 01:30 local the next day.
        slots = _walk("2026-03-28T01:30:00Z", "daily", "Europe/London", 3)
        assert slots == ["2026-03-28T01:30:00Z", "2026-03-29T01:30:00Z", "2026-03-30T00:30:00Z"]

    def test_a_local_time_the_clocks_repeat_runs_once(self) -> None:
        # 01:30 happens twice in London on 25 October 2026; the first is 00:30Z.
        slots = _walk("2026-10-24T00:30:00Z", "daily", "Europe/London", 3)
        assert slots == ["2026-10-24T00:30:00Z", "2026-10-25T00:30:00Z", "2026-10-26T01:30:00Z"]

    def test_weekly_counts_from_the_anchor_not_from_the_slot_before(self) -> None:
        slots = _walk("2026-10-21T08:00:00Z", "weekly", "Europe/London", 3)
        assert slots == ["2026-10-21T08:00:00Z", "2026-10-28T09:00:00Z", "2026-11-04T09:00:00Z"]

    def test_weekdays_skip_the_weekend(self) -> None:
        # Friday 2 October 2026, then Monday and Tuesday.
        slots = _walk("2026-10-02T07:00:00Z", "weekdays", "Europe/Paris", 3)
        assert slots == ["2026-10-02T07:00:00Z", "2026-10-05T07:00:00Z", "2026-10-06T07:00:00Z"]

    def test_a_weekday_schedule_anchored_on_a_saturday_first_runs_on_monday(self) -> None:
        first = first_slot("2026-10-03T07:00:00Z", "weekdays", "Europe/Paris")
        assert format_instant(first) == "2026-10-05T07:00:00Z"

    def test_interval_cadences_stay_absolute(self) -> None:
        slots = _walk("2026-10-24T23:00:00Z", "hourly", "Europe/London", 3)
        assert slots == ["2026-10-24T23:00:00Z", "2026-10-25T00:00:00Z", "2026-10-25T01:00:00Z"]

    def test_a_schedule_with_no_zone_behaves_as_it_always_did(self) -> None:
        slots = _walk("2026-10-24T08:00:00Z", "daily", None, 3)
        assert slots == ["2026-10-24T08:00:00Z", "2026-10-25T08:00:00Z", "2026-10-26T08:00:00Z"]

    def test_elapsed_slots_are_skipped_not_owed(self) -> None:
        later = parse_instant("2027-01-01T12:00:00Z")
        slot = next_occurrence("2026-10-01T08:00:00Z", "weekly", "Europe/London", later)
        assert slot > later
        assert slot - later <= timedelta(days=7)

    def test_weekdays_is_a_repeating_cadence(self) -> None:
        assert "weekdays" in TASK_REPEATING


class TestTermsValidation:
    def test_an_end_on_a_task_that_does_not_repeat_is_refused(self) -> None:
        with pytest.raises(ValueError, match="schedule_terms_need_a_repeating_task"):
            schedule_terms(
                recurrence=None,
                scheduled_at="2026-10-05T07:00:00Z",
                timezone=None,
                run_until="2026-10-30T00:00:00Z",
                missed_runs=None,
            )

    def test_an_unknown_zone_is_refused(self) -> None:
        with pytest.raises(ValueError, match="invalid_timezone:Mars/Olympus"):
            schedule_terms(
                recurrence="daily",
                scheduled_at="2026-10-05T07:00:00Z",
                timezone="Mars/Olympus",
                run_until=None,
                missed_runs=None,
            )

    def test_an_end_before_the_first_run_is_refused(self) -> None:
        with pytest.raises(ValueError, match="schedule_ends_before_first_run"):
            schedule_terms(
                recurrence="weekdays",
                scheduled_at="2026-10-03T07:00:00Z",
                timezone="Europe/Paris",
                run_until="2026-10-04T23:00:00Z",
                missed_runs=None,
            )

    def test_a_repeating_schedule_records_its_policy_even_when_not_chosen(self) -> None:
        terms = schedule_terms(
            recurrence="daily",
            scheduled_at="2026-10-05T07:00:00Z",
            timezone="Europe/Paris",
            run_until=None,
            missed_runs=None,
        )
        assert terms.missed_run_policy == DEFAULT_MISSED_RUN_POLICY
        assert terms.anchor == "2026-10-05T07:00:00Z"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _routine(store: SQLiteStore, **terms: str | None) -> str:
    session_id = f"sess_inbox_{OWNER}"
    store.create_session(session_id, str(store.paths.workspace_root))
    scheduled_at = terms.pop("scheduled_at", None) or "2020-01-01T09:00:00Z"
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id,
        title="Morning brief",
        objective="Summarise the morning",
        scheduled_at=scheduled_at,
        recurrence=terms.pop("recurrence", None) or "daily",
        schedule_anchor=scheduled_at,
        **terms,  # type: ignore[arg-type]
    )
    return task.task_id


def _completed(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []

    async def completed(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append(1)
        return SimpleNamespace(status="completed", message="Brief written.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    return calls


class TestTheSchedulerHonoursTheTerms:
    def test_a_missed_slot_is_skipped_when_the_routine_says_so(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = SQLiteStore(workspace)
        task_id = _routine(store, schedule_timezone="Europe/London", missed_run_policy="skip")
        calls = _completed(monkeypatch)
        assert asyncio.run(TaskScheduler(workspace).run_due()) == 1
        assert calls == [], "a skipped slot runs no turn"
        saved = store.load_task(task_id)
        assert saved is not None and saved.status == "queued"
        assert saved.summary == MISSED_RUN_SKIPPED
        assert saved.scheduled_at is not None
        assert parse_instant(saved.scheduled_at) > datetime.now(UTC)
        # The next slot is still 09:00 London.
        local = parse_instant(saved.scheduled_at).astimezone(ZoneInfo("Europe/London"))
        assert (local.hour, local.minute) == (9, 0)
        detail = DashboardService(workspace).get_task_detail(task_id, user_id=None)
        assert detail is not None
        assert [attempt.outcome for attempt in detail.attempts][-1] == "skipped"

    def test_a_missed_slot_runs_once_by_default(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = SQLiteStore(workspace)
        task_id = _routine(store, schedule_timezone="Europe/London")
        calls = _completed(monkeypatch)
        assert asyncio.run(TaskScheduler(workspace).run_due()) == 1
        assert calls == [1]
        saved = store.load_task(task_id)
        assert saved is not None and saved.status == "queued"
        assert saved.summary == "Brief written."

    def test_a_routine_past_its_end_finishes_instead_of_re_arming(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = SQLiteStore(workspace)
        task_id = _routine(
            store,
            scheduled_at=format_instant(datetime.now(UTC) - timedelta(minutes=1)),
            schedule_timezone="UTC",
            schedule_until=format_instant(datetime.now(UTC) + timedelta(hours=1)),
        )
        calls = _completed(monkeypatch)
        assert asyncio.run(TaskScheduler(workspace).run_due()) == 1
        assert calls == [1]
        saved = store.load_task(task_id)
        assert saved is not None
        assert saved.status == "completed"
        assert saved.summary == "Brief written. That was its last scheduled run."


class TestCreation:
    def test_the_dashboard_stores_and_serves_the_terms(self, workspace: Path) -> None:
        view = DashboardService(workspace).create_task(
            title="Stand-up notes",
            objective="Draft my stand-up notes",
            user_id=None,
            principal_id=OWNER,
            scheduled_at="2026-10-03T07:00:00Z",
            recurrence="weekdays",
            timezone="Europe/Paris",
            run_until="2026-12-31T22:59:59Z",
            missed_runs="skip",
        )
        assert view.recurrence == "weekdays"
        # Anchored on a Saturday, so the first run the scheduler claims is Monday.
        assert view.scheduled_at == "2026-10-05T07:00:00Z"
        assert view.schedule_timezone == "Europe/Paris"
        assert view.schedule_until == "2026-12-31T22:59:59Z"
        assert view.missed_run_policy == "skip"

    def test_the_route_refuses_terms_on_a_one_off(self, workspace: Path) -> None:
        from fastapi.testclient import TestClient

        from raiker.api.app import create_app

        client = TestClient(create_app(workspace))
        token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
        response = client.post(
            "/api/tasks",
            json={
                "title": "Once",
                "description": "",
                "scheduled_at": "2026-10-05T07:00:00Z",
                "missed_runs": "skip",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason_code"] == "schedule_terms_need_a_repeating_task"
