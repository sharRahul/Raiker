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
#: A Git credential the owner removed or disconnected (ADD-27 GH-16): the id is
#: the vault entry it was kept under, or the credential record's id.
GIT_CREDENTIAL_FORGET = "git_credential_forget"
#: Every Git grant the owner withdrew: the id is the owner, and the grants made
#: at or before the line's time are revoked again after a restore.
GIT_GRANT_REVOKE = "git_grant_revoke"
#: A repository delegation the owner revoked (ADD-27 GH-50).
DELEGATION_REVOKE = "repository_delegation_revoke"
#: A project the owner deleted (BUG-324), with the conversations and tasks
#: filed in it. A database backup cannot bring back a managed folder's bytes
#: either way; the replay keeps the rows gone.
PROJECT_DELETE = "project_delete"
#: A Design picture removed for good from Recently deleted (BUG-324).
IMAGE_PURGE = "image_purge"
#: A managed file the owner removed from a project's or the owner's files (BUG-324).
MANAGED_FILE_RETIRE = "managed_file_retire"

KINDS = (
    MEMORY_FORGET, MEMORY_PURGE, SESSION_DELETE,
    GIT_CREDENTIAL_FORGET, GIT_GRANT_REVOKE, DELEGATION_REVOKE,
    PROJECT_DELETE, IMAGE_PURGE, MANAGED_FILE_RETIRE,
)


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
        elif entry.kind == GIT_CREDENTIAL_FORGET:
            # Authority the owner took back is not handed back by a snapshot:
            # the vault entry, the record that named it and every grant on it go.
            with store.connect() as connection:
                removed = connection.execute(
                    "DELETE FROM connector_credentials WHERE principal_id = ? AND connector_id = ?",
                    (entry.owner, entry.object_id),
                ).rowcount
                removed += connection.execute(
                    """DELETE FROM git_credentials
                       WHERE principal_id = ? AND (credential_id = ? OR secret_ref = ?)""",
                    (entry.owner, entry.object_id, entry.object_id),
                ).rowcount
            store.revoke_git_credential_grants(entry.owner)
            if removed:
                applied[GIT_CREDENTIAL_FORGET] += 1
        elif entry.kind == GIT_GRANT_REVOKE:
            revoked_grants = store._execute(  # noqa: SLF001 — a bounded revocation with no method of its own
                """UPDATE git_credential_grants SET status = 'revoked', revoked_at = ?
                   WHERE owner_principal_id = ? AND status = 'active' AND granted_at <= ?""",
                (entry.at, entry.object_id, entry.at),
            )
            if revoked_grants:
                applied[GIT_GRANT_REVOKE] += 1
        elif entry.kind == DELEGATION_REVOKE:
            revoked_delegations = store._execute(  # noqa: SLF001 — a bounded revocation with no method of its own
                """UPDATE repository_delegations SET revoked_at = ?
                   WHERE (delegation_id = ? OR parent_delegation_id = ?) AND revoked_at IS NULL""",
                (entry.at, entry.object_id, entry.object_id),
            )
            if revoked_delegations:
                applied[DELEGATION_REVOKE] += 1
        elif entry.kind == PROJECT_DELETE:
            if store.delete_project_with_orphanage(entry.object_id, journal=False):
                applied[PROJECT_DELETE] += 1
        elif entry.kind == IMAGE_PURGE:
            # Removing for good is only ever the second step, so a picture the
            # backup still held as live is put away first, then removed.
            store.set_image_generation_deleted(
                entry.object_id, owner_principal_id=entry.owner, deleted=True
            )
            if store.purge_image_generation(
                entry.object_id, owner_principal_id=entry.owner, journal=False
            ):
                applied[IMAGE_PURGE] += 1
        elif entry.kind == MANAGED_FILE_RETIRE:
            store.retire_managed_file_chunks(entry.object_id, entry.owner)
            if store.retire_managed_file(entry.object_id, entry.owner):
                applied[MANAGED_FILE_RETIRE] += 1
    return applied
