"""UX-TASK-05 — every task status sits in one published phase, served with the task.

The web module ``web/src/lib/taskPhase.ts`` decides which controls each phase
offers; these cases keep the server's phases and the client's in step, and keep
a new status from arriving without one.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import TASK_STATUSES
from raiker.control.dashboard import DashboardService
from raiker.tasks.lifecycle import STATUS_PHASES, TASK_PHASES, task_phase

TASK_PHASE_TS = Path("web/src/lib/taskPhase.ts")


def test_every_status_has_a_published_phase() -> None:
    assert set(STATUS_PHASES) == TASK_STATUSES
    assert set(STATUS_PHASES.values()) <= set(TASK_PHASES)


def test_queued_work_is_told_apart_by_its_schedule() -> None:
    now = datetime(2026, 10, 3, 12, tzinfo=UTC)
    assert task_phase("queued", None, now) == "not_started"
    assert task_phase("queued", "2026-10-04T09:00:00Z", now) == "scheduled"
    assert task_phase("queued", "2026-10-03T11:00:00Z", now) == "queued"
    assert task_phase("cancelled", None, now) == "stopped"
    assert task_phase("a_status_from_the_future", None, now) == "waiting"


def test_the_client_names_the_same_phases_and_statuses() -> None:
    source = TASK_PHASE_TS.read_text(encoding="utf-8")
    phases = re.search(r"export const TASK_PHASES = \[(.*?)\] as const;", source, re.S)
    assert phases is not None
    assert re.findall(r'"([a-z_]+)"', phases.group(1)) == list(TASK_PHASES)
    table = re.search(r"const STATUS_PHASES: Record<string, TaskPhase> = \{(.*?)\};", source, re.S)
    assert table is not None
    assert dict(re.findall(r"^\s*([a-z_]+): \"([a-z_]+)\",", table.group(1), re.M)) == STATUS_PHASES


def test_the_task_view_carries_its_phase(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    service = DashboardService(tmp_path)
    view = service.create_task(
        title="Later",
        objective="Do it later",
        user_id=None,
        principal_id="principal_owner",
        scheduled_at="2099-01-01T09:00:00Z",
    )
    assert view.phase == "scheduled"
