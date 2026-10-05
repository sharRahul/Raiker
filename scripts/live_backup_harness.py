# SPDX-License-Identifier: Apache-2.0
"""Set up the states the 2026-10-05 (fourth) live round drives through the product.

The round proves backups and restore (DEC-24 step 5), the snapshot taken before
an upgrade (DEC-17 step 8), notice deduplication and the record's account of
what happened to a notice (DEC-21), the scheduler's queue (DEC-24 step 1) and
settings conflicts (13.2 #6). Some starting states need an upgrade, a disk that
changes a file, or a monitor that trips on every pass; this files each through
the product's own store and backup code, and everything that then decides an
outcome is the running host's.

    python scripts/live_backup_harness.py <workspace> upgrade
    python scripts/live_backup_harness.py <workspace> tamper <backup_id>
    python scripts/live_backup_harness.py <workspace> restored <path>
    python scripts/live_backup_harness.py <workspace> repeat <times>
    python scripts/live_backup_harness.py <workspace> due

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.events.writer import EventLogWriter
from raiker.storage.backup import backups_dir, list_backups
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

#: The newest migration in this build, removed and re-applied to stand in for
#: an upgrade: the runner sees one migration this database has not had.
LATEST = "RAIKER-2093-task-tool-limit"


def _owner(store: SQLiteStore) -> str:
    owner = store.original_account_principal_id()
    if not owner:
        raise SystemExit("No owner account in this workspace yet; sign in first.")
    return owner


def upgrade(workspace: Path) -> dict[str, object]:
    """Make the database one migration behind, then open it as an upgraded build would."""
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        connection.execute("DELETE FROM migrations WHERE migration_id = ?", (LATEST,))
    SQLiteStore(workspace)
    taken = [record.to_dict() for record in list_backups(workspace) if record.reason == "pre_migration"]
    return {"pre_migration_backups": len(taken), "newest": taken[0] if taken else None}


def tamper(workspace: Path, backup_id: str) -> dict[str, object]:
    """Change one byte of a backup's database, the way a failing disk does."""
    database = backups_dir(workspace) / backup_id / "raiker.db"
    data = bytearray(database.read_bytes())
    data[len(data) // 2] ^= 0xFF
    database.write_bytes(bytes(data))
    return {"tampered": backup_id}


def restored(path: str) -> dict[str, object]:
    """Open a restored copy as its own workspace and count what it holds."""
    store = SQLiteStore(Path(path))
    with store.connect() as connection:
        sessions = int(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
        owners = int(connection.execute("SELECT COUNT(*) FROM principals").fetchone()[0])
    return {"sessions": sessions, "principals": owners}


def repeat(store: SQLiteStore, times: int) -> dict[str, object]:
    """One monitor finding raised ``times`` times in a row, as a tripping monitor does."""
    ids = {
        store.insert_notification(
            principal_id=_owner(store),
            kind="security_alert",
            title="Security finding",
            body="Web access was refused three times by the egress policy.",
            subject_id="web_fetch",
        )
        for _ in range(times)
    }
    rows = [row for row in store.list_notifications(_owner(store), limit=50) if row["notification_id"] in ids]
    return {"distinct": len(ids), "repeat_count": [row["repeat_count"] for row in rows]}


def due(store: SQLiteStore, workspace: Path) -> dict[str, object]:
    """A scheduled task due twenty minutes ago."""
    session_id = f"sess_inbox_{_owner(store)}"
    if store.load_session(session_id) is None:
        store.create_session(session_id, str(workspace))
    when = (datetime.now(UTC) - timedelta(minutes=20)).replace(microsecond=0)
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Overnight report", objective="Summarise yesterday.",
        scheduled_at=when.isoformat().replace("+00:00", "Z"),
    )
    return {"task_id": task.task_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("command", choices=["upgrade", "tamper", "restored", "repeat", "due"])
    parser.add_argument("value", nargs="?", default="")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if args.command == "upgrade":
        result = upgrade(workspace)
    elif args.command == "tamper":
        result = tamper(workspace, args.value)
    elif args.command == "restored":
        result = restored(args.value)
    elif args.command == "repeat":
        result = repeat(SQLiteStore(workspace), int(args.value or 3))
    else:
        result = due(SQLiteStore(workspace), workspace)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
