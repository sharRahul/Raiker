# SPDX-License-Identifier: Apache-2.0
"""Set up the states the 2026-10-05 (fifth) live round drives through the product.

The round proves restoring a locked workspace from the lock screen (BUG-323,
DEC-24 steps 5–6), refusing a database a newer Raiker shaped (DEC-17 step 8),
and what a model turn is told about language and place (DEC-21 General). Some
starting states need a damaged file or a newer build; this makes each with the
product's own store code, with ``raiker-web`` stopped, and everything that then
decides an outcome is the running host's.

    python scripts/live_recovery_harness.py <workspace> damage
    python scripts/live_recovery_harness.py <workspace> newer
    python scripts/live_recovery_harness.py <workspace> environment
    python scripts/live_recovery_harness.py <workspace> sessions
    python scripts/live_recovery_harness.py <workspace> quarantine
    python scripts/live_recovery_harness.py <workspace> due <task_id>

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from raiker.storage.migrations import SCHEMA_GENERATION
from raiker.storage.sqlite import SQLiteStore


def damage(workspace: Path) -> dict[str, object]:
    """Overwrite the database's first pages, the way a failed disk write does."""
    database = workspace / ".raiker" / "raiker.db"
    data = bytearray(database.read_bytes())
    data[16:8192] = os.urandom(8176)
    database.write_bytes(bytes(data))
    return {"damaged": str(database.name), "bytes": len(data)}


def newer(workspace: Path) -> dict[str, object]:
    """Stamp the database as shaped by a build five generations newer than this one."""
    connection = SQLiteStore(workspace).connect()
    connection.execute(f"PRAGMA user_version = {SCHEMA_GENERATION + 5}")
    connection.commit()
    return {"schema_generation": SCHEMA_GENERATION + 5, "this_build": SCHEMA_GENERATION}


def environment(workspace: Path) -> dict[str, object]:
    """The newest turn's ``environment_context`` event: what the model was told."""
    events = sorted((workspace / ".raiker" / "events").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    for path in reversed(events):
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            record = json.loads(line)
            if record.get("event_type") == "environment_context":
                return {"session": path.stem, "payload": record.get("payload", {})}
    return {"session": None, "payload": {}}


def sessions(workspace: Path) -> dict[str, object]:
    store = SQLiteStore(workspace)
    rows = store._rows("SELECT session_id, title FROM sessions")  # noqa: SLF001
    return {"sessions": [dict(row) for row in rows]}


def quarantine(workspace: Path) -> dict[str, object]:
    base = workspace / ".raiker" / "quarantine"
    held = sorted(p.name for p in base.iterdir()) if base.is_dir() else []
    notes = [json.loads((base / name / "why.json").read_text()) for name in held if (base / name / "why.json").is_file()]
    return {"held": held, "notes": notes}


def due(workspace: Path, task_id: str) -> dict[str, object]:
    """Make one routine's next slot a minute ago, so the host's next pass runs it."""
    from datetime import UTC, datetime, timedelta

    when = (datetime.now(UTC) - timedelta(minutes=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        changed = connection.execute(
            "UPDATE tasks SET scheduled_at = ?, status = 'queued' WHERE task_id = ?", (when, task_id)
        ).rowcount
    return {"task_id": task_id, "scheduled_at": when, "changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("action", choices=["damage", "newer", "environment", "sessions", "quarantine", "due"])
    parser.add_argument("target", nargs="?", default="")
    args = parser.parse_args()
    if args.action == "due":
        print(json.dumps(due(args.workspace.resolve(), args.target)))
        return
    actions = {
        "damage": damage,
        "newer": newer,
        "environment": environment,
        "sessions": sessions,
        "quarantine": quarantine,
    }
    print(json.dumps(actions[args.action](args.workspace.resolve())))


if __name__ == "__main__":
    main()
