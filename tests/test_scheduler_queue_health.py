"""DEC-24 step 1 — the scheduler's queue depth and age, read from the record.

The background-pass record said whether the scheduler's pass had run, not
whether it was keeping up. Due work no pass has claimed, and how long the oldest
has waited, is the measurement that says so.
"""

from __future__ import annotations

from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


def test_due_unclaimed_work_is_counted_with_its_age(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    manager = TaskManager(store, EventLogWriter(store))
    assert store.scheduler_queue("2026-10-05T12:00:00Z") == {"due": 0, "oldest_due_at": None}
    manager.create_task(session_id=session_id, title="Old", objective="x", scheduled_at="2020-01-01T09:00:00Z")
    manager.create_task(session_id=session_id, title="Later", objective="x", scheduled_at="2999-01-01T09:00:00Z")
    queue = store.scheduler_queue("2026-10-05T12:00:00Z")
    assert queue == {"due": 1, "oldest_due_at": "2020-01-01T09:00:00Z"}
    diagnostics = DashboardService(tmp_path).get_diagnostics("principal_owner")
    assert diagnostics.scheduler_queue["due"] == 1
    assert (diagnostics.scheduler_queue["oldest_wait_seconds"] or 0) > 86_400
    assert diagnostics.scheduler_queue["host_paused"] is False
