"""Deletions recorded outside the database, so a restore cannot undo them (DEC-24 step 5).

A backup is a snapshot. Restoring one brings back everything the snapshot held,
including a memory the owner forgot or a conversation they deleted *after* the
backup was taken. §13.2 item 5 is explicit that a restore must not quietly
re-create erased content, and DEC-24 step 5 asks for deletion tombstones to be
applied after a restore and before the switch.

The tombstones cannot live in the database — the database is the thing being
replaced, and on the lock screen it is the thing that will not open. So each
deletion is also appended here, to ``.raiker/deletions.jsonl``, beside the
database and outside every backup:

* **Content-free.** A line holds the kind, the object's id, its owner's
  principal id and the time. No text, title or memory content is ever written,
  so the journal is not a second copy of what was erased.
* **Append-only and best-effort.** A deletion that has already happened in the
  database is not undone because its journal line could not be written; the
  line is what lets a *later restore* honour it.
* **Reapplied by time.** A restore replays the lines newer than the backup's
  ``created_at`` into the restored copy, through the same store methods the
  deletion used, with journaling off so the replay does not journal itself.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.storage.internal_paths import internal_io_path

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

JOURNAL = "deletions.jsonl"

#: A memory excluded by Forget: its row is marked forgotten and its Markdown
#: export becomes a content-free tombstone.
MEMORY_FORGET = "memory_forget"
#: A memory deleted permanently: its row, index entries and export are removed.
MEMORY_PURGE = "memory_purge"
#: A conversation deleted with its turns, sources and transcript.
SESSION_DELETE = "session_delete"

KINDS = (MEMORY_FORGET, MEMORY_PURGE, SESSION_DELETE)


def journal_path(workspace_root: str | Path) -> Path:
    return internal_io_path(Path(workspace_root).resolve() / ".raiker" / JOURNAL)


def record_deletion(
    workspace_root: str | Path, kind: str, object_id: str, owner_principal_id: str | None = None
) -> None:
    """Append one deletion. Never raises: the deletion itself has already happened."""
    if kind not in KINDS or not object_id:
        return
    line = json.dumps(
        {"kind": kind, "id": object_id, "owner": owner_principal_id or "", "at": utc_now()},
        separators=(",", ":"),
    )
    with contextlib.suppress(OSError):
        path = journal_path(workspace_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())


@dataclass(frozen=True)
class Deletion:
    kind: str
    object_id: str
    owner: str
    at: str


def read_deletions(workspace_root: str | Path, *, after: str = "") -> list[Deletion]:
    """Every journalled deletion at or after ``after`` (an ISO timestamp), oldest first.

    A line that does not parse is skipped rather than failing the restore it
    serves: one torn write at the end of the file must not cost every other line.
    """
    path = journal_path(workspace_root)
    if not path.is_file():
        return []
    found: list[Deletion] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            data: dict[str, Any] = json.loads(raw)
            entry = Deletion(str(data["kind"]), str(data["id"]), str(data.get("owner", "")), str(data["at"]))
        except (ValueError, KeyError, TypeError):
            continue
        # At or after: a deletion in the same instant as the backup may or may
        # not be in it, and replaying one that is changes nothing.
        if entry.kind in KINDS and entry.object_id and entry.at >= after:
            found.append(entry)
    return found


def reapply_deletions(store: SQLiteStore, deletions: list[Deletion]) -> dict[str, int]:
    """Apply journalled deletions to a restored store. Returns how many of each applied.

    Each kind goes through the store method the original deletion used, so the
    restored copy ends in the state the running workspace was in — and an entry
    whose object the backup never held is simply nothing to do.
    """
    from raiker.memory.store import tombstone_memory_file

    applied = dict.fromkeys(KINDS, 0)
    for entry in deletions:
        if entry.kind == SESSION_DELETE:
            if store.delete_session(entry.object_id, journal=False):
                applied[SESSION_DELETE] += 1
        elif entry.kind == MEMORY_FORGET:
            changed = store.mark_approved_memory_forgotten(
                entry.object_id, deleted_at=entry.at, updated_at=entry.at, journal=False
            )
            store.deactivate_memory_projections(entry.object_id)
            tombstone_memory_file(store.paths.workspace_root, entry.object_id, deleted_at=entry.at)
            if changed:
                applied[MEMORY_FORGET] += 1
        elif entry.kind == MEMORY_PURGE:
            existed = (
                store._row(  # noqa: SLF001 — one existence read, no method of its own
                    "SELECT 1 FROM approved_memory WHERE memory_id = ?", (entry.object_id,)
                )
                is not None
            )
            store.deactivate_memory_projections(entry.object_id)
            store.delete_approved_memory(entry.object_id, journal=False)
            with contextlib.suppress(OSError):
                internal_io_path(
                    Path(store.paths.workspace_root) / ".raiker" / "memory" / f"{entry.object_id}.md"
                ).unlink(missing_ok=True)
            if existed:
                applied[MEMORY_PURGE] += 1
    return applied
