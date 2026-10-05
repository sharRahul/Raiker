# SPDX-License-Identifier: Apache-2.0
"""Set up the states a readiness live round drives through the product.

The 2026-10-05 (second) round proves decisions whose starting states take days
or a broken disk to reach on their own: a delegated task tree mid-run, a
background task whose notice could not be delivered, a text index SQLite
reports as damaged, and a webhook channel paired to an allowed sender. This
files each one through the product's own services — ``TaskManager``,
``DashboardService``, the store — and everything that then decides an outcome
(the interrupt route, the notifier, the integrity check, the loop guard) is the
running host's.

    python scripts/live_readiness_harness.py <workspace> delegation
    python scripts/live_readiness_harness.py <workspace> show <task_id>
    python scripts/live_readiness_harness.py <workspace> undelivered
    python scripts/live_readiness_harness.py <workspace> damage-index
    python scripts/live_readiness_harness.py <workspace> pair-webhook

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

WEBHOOKS = "channel.webhooks"


def _owner(store: SQLiteStore) -> str:
    for account in store.list_accounts():
        principal = account.get("principal_id") if isinstance(account, dict) else None
        if principal:
            return str(principal)
    raise SystemExit("No owner account in this workspace yet; sign in first.")


def _inbox(store: SQLiteStore, workspace: Path) -> str:
    session_id = f"sess_inbox_{_owner(store)}"
    if store.load_session(session_id) is None:
        store.create_session(session_id, str(workspace))
    return session_id


def delegation(store: SQLiteStore, workspace: Path) -> dict[str, object]:
    """A running parent with a running child and a queued grandchild."""
    session_id = _inbox(store, workspace)
    manager = TaskManager(store, EventLogWriter(store))
    parent = manager.create_task(
        session_id=session_id, title="Release notes review",
        objective="Split the release notes into sections and check each.",
    )
    child = manager.create_task(
        session_id=session_id, title="Check the API section",
        objective="Read the API section.", parent_task_id=parent.task_id,
    )
    grandchild = manager.create_task(
        session_id=session_id, title="Check the API examples",
        objective="Run the examples.", parent_task_id=child.task_id,
    )
    store.update_task_status(parent.task_id, "running")
    store.update_task_status(child.task_id, "running")
    return {"parent": parent.task_id, "child": child.task_id, "grandchild": grandchild.task_id}


def show(store: SQLiteStore, task_id: str) -> dict[str, object]:
    task = store.load_task(task_id)
    if task is None:
        raise SystemExit(f"No task {task_id}.")
    return {
        "status": task.status,
        "summary": task.summary,
        "delivery_state": task.delivery_state,
        "delivery_detail": task.delivery_detail,
    }


def undelivered(store: SQLiteStore, workspace: Path) -> dict[str, object]:
    """A scheduled task that completes while the desktop notice command fails."""
    session_id = _inbox(store, workspace)
    manager = TaskManager(store, EventLogWriter(store))
    task = manager.create_task(
        session_id=session_id, title="Weekly dependency digest",
        objective="List the dependencies with new releases.",
        scheduled_at="2026-10-05T06:00:00Z",
    )
    # The owner's configured desktop notice command, failing as a broken one
    # does. The notice in Raiker is still written.
    os.environ["RAIKER_OS_NOTIFY_CMD"] = "false"
    manager.complete_task(task.task_id, "Two dependencies have new releases.")
    return {"task_id": task.task_id, **show(store, task.task_id)}


def damage_index(store: SQLiteStore) -> dict[str, object]:
    """Lose the conversation index's segments, the way a damaged disk does."""
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO conversation_fts (turn_id, session_id, role, text) "
            "VALUES ('turn_live_damage', 'sess_live_damage', 'user', 'segment to lose')"
        )
    with store.connect() as connection:
        connection.execute("DELETE FROM conversation_fts_data WHERE id NOT IN (1, 10)")
    return {"damaged": store.damaged_text_indexes()}


def pair_webhook(workspace: Path, store: SQLiteStore) -> dict[str, object]:
    """A generic webhook channel, on, with ``ops`` as its one allowed sender."""
    owner = _owner(store)
    service = DashboardService(workspace)
    paired = service.pair_channel(owner, WEBHOOKS, "Ops webhook", ["ops"])
    if not paired.ok:
        raise SystemExit(f"pairing refused: {paired.reason_code}")
    pairing_id = str((paired.data or {})["pairing_id"])
    enabled = service.set_channel_enabled(owner, pairing_id, True)
    if not enabled.ok:
        raise SystemExit(f"enable refused: {enabled.reason_code}")
    return {"pairing_id": pairing_id, "connector_id": WEBHOOKS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "command", choices=["delegation", "show", "undelivered", "damage-index", "pair-webhook"]
    )
    parser.add_argument("task_id", nargs="?", default="")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    store = SQLiteStore(workspace)
    if args.command == "delegation":
        result = delegation(store, workspace)
    elif args.command == "show":
        result = show(store, args.task_id)
    elif args.command == "undelivered":
        result = undelivered(store, workspace)
    elif args.command == "damage-index":
        result = damage_index(store)
    else:
        result = pair_webhook(workspace, store)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
