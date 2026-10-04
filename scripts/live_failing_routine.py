# SPDX-License-Identifier: Apache-2.0
"""Drive a routine through failed cycles on a live workspace, for a live round.

DEC-12 step 6 pauses a routine after three cycles in a row that did not
complete. A real routine runs once a day at best, so a round cannot wait for
three slots. This harness files a real daily routine through ``TaskManager`` —
the same call the API makes — and, between the host's own ticks, moves its
next slot to the past so the running host claims it. Everything that decides
the outcome is the product's: the host tick, the governed turn (which fails on a
workspace with no model chosen), the failure count, the pause and the notice.

    python scripts/live_failing_routine.py /tmp/raiker-live create
    python scripts/live_failing_routine.py /tmp/raiker-live due <task_id>
    python scripts/live_failing_routine.py /tmp/raiker-live show <task_id>

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

PAST_SLOT = "2020-01-01T09:00:00Z"


def _owner(store: SQLiteStore) -> str:
    for account in store.list_accounts():
        principal = getattr(account, "principal_id", None) or (
            account.get("principal_id") if isinstance(account, dict) else None
        )
        if principal:
            return str(principal)
    raise SystemExit("No owner account in this workspace yet; sign in first.")


def create(store: SQLiteStore, workspace: Path) -> dict[str, object]:
    session_id = f"sess_inbox_{_owner(store)}"
    if store.load_session(session_id) is None:
        store.create_session(session_id, str(workspace))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id,
        title="Morning inbox digest",
        objective="Summarise what arrived overnight in three lines.",
        scheduled_at=PAST_SLOT,
        recurrence="daily",
    )
    return {"task_id": task.task_id}


def due(store: SQLiteStore, task_id: str) -> dict[str, object]:
    """Move an armed routine's next slot to the past; refuse anything else."""
    with store.connect() as connection:
        moved = connection.execute(
            "UPDATE tasks SET scheduled_at = ? WHERE task_id = ? AND status = 'queued'",
            (PAST_SLOT, task_id),
        ).rowcount
    return {"moved": moved == 1, **show(store, task_id)}


def show(store: SQLiteStore, task_id: str) -> dict[str, object]:
    task = store.load_task(task_id)
    if task is None:
        raise SystemExit(f"No task {task_id}.")
    return {
        "status": task.status,
        "failed_cycles": task.failed_cycles,
        "scheduled_at": task.scheduled_at,
        "summary": task.summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("command", choices=("create", "due", "show"))
    parser.add_argument("task_id", nargs="?")
    args = parser.parse_args()
    store = SQLiteStore(args.workspace)
    if args.command == "create":
        print(json.dumps(create(store, args.workspace)))
    elif not args.task_id:
        raise SystemExit("A task id is required.")
    elif args.command == "due":
        print(json.dumps(due(store, args.task_id)))
    else:
        print(json.dumps(show(store, args.task_id)))


if __name__ == "__main__":
    main()
