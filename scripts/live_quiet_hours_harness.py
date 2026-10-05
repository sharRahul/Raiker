# SPDX-License-Identifier: Apache-2.0
"""Set up the states the 2026-10-05 (third) live round drives through the product.

The round proves quiet hours (DEC-21a), the routine doctor and run limit
(DEC-12 steps 6 and 8) and damaged search indexes on the attention list
(BUG-322, DEC-24 step 6). Some starting states take a night or a broken disk to
reach on their own: notices written during an interval that has since ended, a
security notice raised by a monitor, a vector the disk mangled. This files each
one through the product's own store — ``insert_notification`` decides every
notice's presentation by the owner's saved policy, exactly as a real notice is
decided — and everything that then decides an outcome is the running host's.

    python scripts/live_quiet_hours_harness.py <workspace> notice <kind> [<minutes ago>]
    python scripts/live_quiet_hours_harness.py <workspace> held
    python scripts/live_quiet_hours_harness.py <workspace> damage-vectors
    python scripts/live_quiet_hours_harness.py <workspace> routine
    python scripts/live_quiet_hours_harness.py <workspace> show-notices
    python scripts/live_quiet_hours_harness.py <workspace> memories

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.events.writer import EventLogWriter
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex

TITLES = {
    "capability_contained": ("Web access contained", "Raiker stopped web access after repeated refusals."),
    "task_finished": ("Background task finished", "“Weekly dependency digest” completed."),
    "task_paused": ("A routine was paused", "“Morning digest” did not complete 3 times in a row."),
    "approval_pending": ("Approval needed", "Raiker is waiting for your approval to run 'write_file'."),
    "mcp_tools_held": ("An MCP server changed its tools", "Two tools are held for your review."),
}


def _owner(store: SQLiteStore) -> str:
    owner = store.original_account_principal_id()
    if not owner:
        raise SystemExit("No owner account in this workspace yet; sign in first.")
    return owner


def notice(store: SQLiteStore, kind: str, minutes_ago: int) -> dict[str, object]:
    """One notice of ``kind``, written as if raised ``minutes_ago`` minutes ago."""
    title, body = TITLES.get(kind, ("Notice", "A notice."))
    moment = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    notification_id = store.insert_notification(
        principal_id=_owner(store), kind=kind, title=title, body=body,
        subject_id="apr_resolved_live" if kind == "approval_pending" else None, now=moment,
    )
    return _row(store, notification_id)


def held(store: SQLiteStore) -> dict[str, object]:
    """Three notices written two hours ago, inside a quiet interval that has ended.

    One of them is about an approval that is no longer pending, which the
    end-of-interval summary must leave out.
    """
    rows = [
        notice(store, "task_paused", 120),
        notice(store, "task_finished", 119),
        notice(store, "approval_pending", 118),
    ]
    return {"notices": rows}


def damage_vectors(store: SQLiteStore, workspace: Path) -> dict[str, object]:
    """Two approved memories whose stored vectors a damaged disk has mangled."""
    governance = MemoryGovernance("evt", "sess", None, "live", 1, 1, "until_forget", "approved", "live")
    owner = _owner(store)
    damaged: list[str] = []
    for text, embedding in (
        ("The release train leaves on Thursdays.", "[0.1, 0.2,"),
        ("Staging is rebuilt every Monday.", json.dumps([0.5, 0.25])),
    ):
        memory = write_memory(
            text, workspace_root=workspace, scope="global", store=store, governance=governance,
            owner_principal_id=owner,
        )
        vector_id = new_id("vec_")
        store.insert_vector_record(
            VectorRecord(
                vector_id, VectorIndex.compute_content_hash(memory.text), memory.text,
                LOCAL_EMBEDDING_MODEL, 384, memory.scope, memory.sensitivity, utc_now(), embedding,
                owner_principal_id=owner,
            )
        )
        store.link_memory_projection(memory.memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL)
        damaged.append(vector_id)
    return {"damaged_vectors": store.damaged_vector_ids(), "written": damaged}


def routine(store: SQLiteStore, workspace: Path) -> dict[str, object]:
    """A daily routine whose next run is tomorrow at 09:00 UTC."""
    session_id = f"sess_inbox_{_owner(store)}"
    if store.load_session(session_id) is None:
        store.create_session(session_id, str(workspace))
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Morning dependency digest",
        objective="List the dependencies with new releases.",
        scheduled_at=tomorrow.isoformat().replace("+00:00", "Z"), recurrence="daily",
    )
    return {"task_id": task.task_id}


def _row(store: SQLiteStore, notification_id: str) -> dict[str, object]:
    for row in store.list_notifications(_owner(store), limit=200):
        if row["notification_id"] == notification_id:
            return {
                key: row[key]
                for key in ("notification_id", "kind", "in_app_presentation", "desktop_presentation", "quiet_until")
            }
    return {}


def show_notices(store: SQLiteStore) -> dict[str, object]:
    return {
        "notices": [
            {key: row[key] for key in ("kind", "read", "in_app_presentation", "summarised_at")}
            for row in store.list_notifications(_owner(store), limit=50)
        ]
    }


def memories(store: SQLiteStore) -> dict[str, object]:
    """The texts of the active approved memories, and which still lack a vector."""
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT text FROM approved_memory WHERE deleted_at IS NULL AND archived_at IS NULL"
        ).fetchall()
    missing = store.list_memories_missing_embedding(LOCAL_EMBEDDING_MODEL)
    return {"texts": [str(row["text"]) for row in rows], "waiting_to_be_indexed": len(missing)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("command", choices=["notice", "held", "damage-vectors", "routine", "show-notices", "memories"])
    parser.add_argument("kind", nargs="?", default="task_finished")
    parser.add_argument("minutes_ago", nargs="?", type=int, default=0)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    store = SQLiteStore(workspace)
    if args.command == "notice":
        result = notice(store, args.kind, args.minutes_ago)
    elif args.command == "held":
        result = held(store)
    elif args.command == "damage-vectors":
        result = damage_vectors(store, workspace)
    elif args.command == "routine":
        result = routine(store, workspace)
    elif args.command == "memories":
        result = memories(store)
    else:
        result = show_notices(store)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
