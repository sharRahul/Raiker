"""Bringing the catalogue level with a folder Raiker does not own.

An imported file changes only when the owner replaces it, so the catalogue is
authoritative by construction. An attached folder is the opposite: it is edited
by whatever the owner uses, and the catalogue is a claim about a past that may
already be wrong. This pass is what makes that claim honest again — and it is
the floor the watcher only makes prompt, so recall is never left stale with
nothing to notice.

Two rules hold throughout, and both are about ownership rather than caution:

* Nothing here writes into the folder. Not a marker, not a cache, not a
  temporary file.
* Nothing here deletes from it. Retiring a revision drops the projection only;
  the bytes belong to the owner (see ``ManagedFileService.owns_bytes``).
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.control.project_roots import resolve_project_root
from raiker.knowledge.extractors import MAX_EXTRACTION_BYTES, resolve_extractable_media_type
from raiker.knowledge.files import ManagedFileError
from raiker.knowledge.indexing import ManagedFileIndexer

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: Directories skipped in every attached root. Fixed and stated rather than read
#: from `.gitignore`: a scan that quietly honoured a file in the tree would make
#: what Raiker can recall depend on a file the owner may not have written, and
#: half-parsing gitignore semantics is worse than not parsing them at all.
IGNORED_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".raiker",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "target",
        ".mypy_cache",
        ".pytest_cache",
    }
)

#: A tree the owner points at can be arbitrarily large. This is the ceiling on
#: one pass, so a folder with a million files degrades to "partially indexed"
#: rather than to a scan that never finishes.
MAX_FILES_PER_PASS = 5_000


@dataclass(frozen=True)
class ReconcileReport:
    """What one pass found, in the terms the interface has to state."""

    indexed: int
    updated: int
    retired: int
    skipped: int
    scanned_at: str
    truncated: bool = False


def reconcile_attached_root(
    workspace_root: str | Path,
    store: SQLiteStore,
    project: Mapping[str, Any] | None,
    owner_principal_id: str,
) -> ReconcileReport:
    """Bring the catalogue level with what is on disk, reading only.

    The folder belongs to the owner, so this pass never writes into it. Its
    whole job is to decide, per file, whether the database is behind.
    """
    root = resolve_project_root(
        project, store.list_brain_source_grants(owner_principal_id), workspace_root
    )
    if project is None or root.path is None or root.missing or root.kind != "attached":
        return ReconcileReport(0, 0, 0, 0, utc_now())
    project_id = str(project["project_id"])
    indexer = ManagedFileIndexer(workspace_root, store)
    known = {
        str(row["relative_path"]): row
        for row in store.list_managed_files(
            owner_principal_id, scope_kind="project", project_id=project_id
        )
    }
    seen: set[str] = set()
    indexed = updated = retired = skipped = 0
    truncated = False

    for count, path in enumerate(_walk(root.path)):
        if count >= MAX_FILES_PER_PASS:
            truncated = True
            break
        relative = path.relative_to(root.path).as_posix()
        seen.add(relative)
        media_type = resolve_extractable_media_type(relative, "")
        if media_type is None:
            skipped += 1
            continue
        try:
            stat = path.stat()
        except OSError:
            # Vanished or unreadable between the walk and the stat. It is not a
            # failure of the pass; the next one will see whatever is true then.
            skipped += 1
            continue
        if stat.st_size > MAX_EXTRACTION_BYTES:
            skipped += 1
            continue
        row = known.get(relative)
        if row is not None and _unchanged(row, stat.st_size, stat.st_mtime_ns):
            continue
        if row is not None:
            # A changed revision retires the old one before publishing the new,
            # so recall can never quote a passage the file no longer contains.
            _retire(indexer, str(row["file_id"]), owner_principal_id)
            updated += 1
        else:
            indexed += 1
        if not _catalogue(
            store, project_id, relative, media_type, stat, owner_principal_id, indexer
        ):
            skipped += 1

    for relative, row in known.items():
        if relative not in seen and not truncated:
            # The file is gone from a folder Raiker does not own; its
            # projections must go with it or recall quotes bytes that vanished.
            _retire(indexer, str(row["file_id"]), owner_principal_id)
            retired += 1

    return ReconcileReport(indexed, updated, retired, skipped, utc_now(), truncated)


def _unchanged(row: Mapping[str, Any], size_bytes: int, mtime_ns: int) -> bool:
    """Whether the catalogue is already level with these bytes.

    Size *and* mtime, because either alone is routinely wrong: an edit that
    keeps the length is common, and a checkout restores an mtime without
    restoring the content.
    """
    stored = row["source_mtime_ns"]
    return (
        stored is not None
        and int(row["size_bytes"]) == size_bytes
        and int(stored) == mtime_ns
    )


def _catalogue(
    store: SQLiteStore,
    project_id: str,
    relative: str,
    media_type: str,
    stat: Any,
    owner_principal_id: str,
    indexer: ManagedFileIndexer,
) -> bool:
    file_id = f"mfile_{secrets.token_hex(16)}"
    registered = store.register_discovered_file(
        file_id=file_id,
        owner_principal_id=owner_principal_id,
        scope_kind="project",
        project_id=project_id,
        relative_path=relative,
        media_type=media_type,
        # The hash identifies a revision for the chunk projection. It is read
        # from the file rather than computed over an imported copy, because
        # there is no copy.
        content_hash=_hash_of(stat, relative),
        size_bytes=int(stat.st_size),
        source_mtime_ns=int(stat.st_mtime_ns),
    )
    if not registered:
        return False
    try:
        indexer.index(file_id, owner_principal_id)
    except ManagedFileError:
        # The row stands with whatever index state the failure left; the file is
        # still listed, still browsable, and simply does not answer recall.
        return False
    return True


def _hash_of(stat: Any, relative: str) -> str:
    """A revision identity for bytes Raiker never copied.

    Derived from path, size and mtime rather than content: the content hash of
    a managed file exists to prove an import landed intact, and there was no
    import here. What the projection needs is only that a *different* revision
    gets a different identity, which this gives without reading the file twice.
    """
    seed = f"{relative}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _retire(indexer: ManagedFileIndexer, file_id: str, owner_principal_id: str) -> None:
    # Already retired, or the row went while the pass was running. Either way
    # the projection is gone, which is the outcome retiring is for.
    with suppress(ManagedFileError):
        indexer.retire(file_id, owner_principal_id)


def _walk(root: Path) -> Iterator[Path]:
    """Every ordinary file under *root*, skipping ignored and linked directories.

    Symlinks are not followed in either direction. A link out of the root would
    put a file outside the boundary into the project's index under a name that
    claims it is inside.
    """
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name in IGNORED_DIRECTORY_NAMES:
                continue
            yield from _walk(entry)
        elif entry.is_file():
            yield entry
