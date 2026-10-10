"""Backups of the encrypted store, and restoring one somewhere new (DEC-24 step 5).

A workspace had no backup Raiker made itself. The lock screen's own advice for
a damaged database — "restore the database from a backup" — pointed at
something only an owner who had copied files by hand could have. DEC-17 step 8
asks for a backup before an irreversible migration; DEC-24 step 5 for a
consistent snapshot, a manifest, integrity verification, no plaintext staging,
and restore into a *new* location.

What this is, exactly:

* **A consistent, encrypted snapshot.** SQLCipher's ``sqlcipher_export`` writes
  the live database into a new file keyed with the same workspace key, inside
  one read transaction. Nothing is ever written in plaintext, and the copy is
  opened and checked before it is called a backup.
* **The memory files beside it.** Approved memories are also kept as Markdown
  under ``.raiker/memory``; they are copied with the database.
* **The files the database points at.** A checkpoint row names the
  content-addressed pre-images under ``.raiker/checkpoints``, and a knowledge
  upload names its file under ``.raiker/artifacts``; a restored database whose
  rows point at nothing would offer restores and sources it cannot deliver
  (DEC-24 step 5, "referenced blobs"). Both trees are copied, and the manifest
  records each one's file count, size and a digest over every file, which
  verification recomputes. They are copied as the workspace keeps them —
  only the database is encrypted. The event log and attached folders are
  **not** included, and the manifest says so rather than implying a whole
  workspace.
* **Key custody, stated.** The backup opens with this workspace's
  ``.raiker/app.key`` and nothing else. The manifest records a fingerprint of
  that key so a restore can say which key it needs; the key itself is never
  written into a backup.
* **Restore never replaces the running workspace.** It writes a verified copy
  into ``.raiker/restores/<backup id>/`` as a workspace of its own, with a copy
  of the key it needs, and says how to open it. Switching to it is the owner's
  act, taken with Raiker stopped.
* **Referenced files are added back, never replaced.** Either restore copies a
  checkpoint or upload file only where none of that name exists: checkpoint
  objects are named by their own hash, so an existing one is the same bytes,
  and an upload already there is newer than the backup.
* **Except from the lock screen** (BUG-323). When the database will not open —
  this key does not open it, or a newer Raiker shaped it — there is no running
  workspace to protect, and :func:`restore_in_place` is the way back: verify
  the backup, move the unopenable database and its memory files aside into
  ``.raiker/quarantine/<time>/`` (nothing is deleted), and switch the verified
  copy in with one rename.
* **Deletions are honoured.** Either restore replays the deletions recorded
  after the backup was taken (``raiker.storage.deletion_journal``), so a
  memory forgotten or a conversation deleted since does not come back.
* **Each backup says which builds can open it.** The manifest records the
  schema generation (DEC-17 step 8); a backup a newer Raiker made is listed and
  refused here rather than opened as a downgrade.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.auth.app_key import app_key_path, ensure_app_key
from raiker.contracts.ids import new_id, utc_now
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.migrations import SCHEMA_GENERATION

MANIFEST = "manifest.json"
DATABASE = "raiker.db"
MEMORY_DIR = "memory"

#: Pre-migration backups kept; older ones are removed when a new one is taken.
#: Owner backups are kept until the owner removes them.
PRE_MIGRATION_KEEP = 3

#: The file trees under ``.raiker/`` the database's rows point at, copied with it.
FILE_TREES = ("checkpoints", "artifacts")

#: What a backup holds and does not, said in the manifest and on the page.
INCLUDED = ("database", "memory_files", *FILE_TREES)
NOT_INCLUDED = ("event_log", "attached_folders")

#: Tables counted into the manifest, so a restored copy can be compared.
COUNTED_TABLES = ("sessions", "turns", "tasks", "approved_memory", "projects", "notifications")


class BackupError(RuntimeError):
    """A backup could not be made, read or restored. ``reason`` is a stable code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


def backups_dir(workspace_root: Path) -> Path:
    return internal_io_path(Path(workspace_root).resolve() / ".raiker" / "backups")


def restores_dir(workspace_root: Path) -> Path:
    return internal_io_path(Path(workspace_root).resolve() / ".raiker" / "restores")


def quarantine_dir(workspace_root: Path) -> Path:
    return internal_io_path(Path(workspace_root).resolve() / ".raiker" / "quarantine")


def _key_hex(workspace_root: Path) -> str:
    return hashlib.sha256(ensure_app_key(Path(workspace_root))).hexdigest()


def key_fingerprint(workspace_root: Path) -> str:
    """A short, one-way label for the key a backup needs. Not the key."""
    return hashlib.sha256(("raiker-backup-key:" + _key_hex(workspace_root)).encode()).hexdigest()[:16]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_summary(path: Path) -> dict[str, Any]:
    """``{files, bytes, sha256}`` of every file under ``path``, by relative name.

    The digest covers each file's name and content hash in a fixed order, so a
    file changed, added or removed after the backup was made is detected.
    """
    digest = hashlib.sha256()
    files = 0
    size = 0
    if path.is_dir():
        for entry in sorted(p for p in path.rglob("*") if p.is_file() and not p.is_symlink()):
            relative = entry.relative_to(path).as_posix()
            digest.update(relative.encode("utf-8") + b"\0" + _sha256(entry).encode("ascii") + b"\n")
            files += 1
            size += entry.stat().st_size
    return {"files": files, "bytes": size, "sha256": digest.hexdigest()}


def _copy_tree(source: Path, destination: Path) -> None:
    """Copy regular files only — a link inside a workspace tree is not followed."""
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink() or not entry.is_file():
            continue
        target = destination / entry.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)


def _add_missing(source: Path, destination: Path) -> int:
    """Copy into ``destination`` only the files it does not already have."""
    added = 0
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink() or not entry.is_file():
            continue
        target = destination / entry.relative_to(source)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)
        added += 1
    return added


def _open_copy(path: Path, key_hex: str) -> Any:
    connection = sqlite3.connect(str(path))
    connection.execute(f"PRAGMA key = \"x'{key_hex}'\"")
    return connection


def _inspect(path: Path, key_hex: str) -> tuple[str, list[str], dict[str, int], int]:
    """``(integrity, migration ids, counts, schema generation)`` read from an encrypted copy."""
    connection = _open_copy(path, key_hex)
    try:
        try:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        except sqlite3.DatabaseError as exc:
            raise BackupError("backup_unreadable", "The workspace key does not open this backup.") from exc
        migrations = sorted(
            str(row[0]) for row in connection.execute("SELECT migration_id FROM migrations")
        )
        counts: dict[str, int] = {}
        for table in COUNTED_TABLES:
            try:
                counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.DatabaseError:
                counts[table] = -1
        generation = int(connection.execute("PRAGMA user_version").fetchone()[0])
        return integrity, migrations, counts, generation
    finally:
        connection.close()


@dataclass(frozen=True)
class BackupRecord:
    backup_id: str
    reason: str
    created_at: str
    size_bytes: int
    sha256: str
    schema_migrations: int
    latest_migration: str
    counts: dict[str, int]
    key_fingerprint: str
    included: tuple[str, ...]
    not_included: tuple[str, ...]
    #: ``verified`` (checksum and integrity check passed when last read),
    #: ``damaged`` or ``unreadable``.
    state: str = "verified"
    verified_at: str | None = None
    detail: str = ""
    #: DEC-17 step 8 — ``PRAGMA user_version`` of the copy; 0 for a backup made
    #: before generations were written, which every current build can open.
    schema_generation: int = 0
    #: DEC-24 step 5 — each copied file tree's ``{files, bytes, sha256}``; empty
    #: for a backup made before trees were copied.
    trees: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)

    @property
    def opens_here(self) -> bool:
        """Whether this build can open it without a downgrade."""
        return self.schema_generation <= SCHEMA_GENERATION

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "reason": self.reason,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "schema_migrations": self.schema_migrations,
            "latest_migration": self.latest_migration,
            "counts": dict(self.counts),
            "key_fingerprint": self.key_fingerprint,
            "included": list(self.included),
            "not_included": list(self.not_included),
            "state": self.state,
            "verified_at": self.verified_at,
            "detail": self.detail,
            "schema_generation": self.schema_generation,
            "opens_here": self.opens_here,
            "trees": {name: dict(summary) for name, summary in self.trees.items()},
        }

    @classmethod
    def from_manifest(cls, data: dict[str, Any]) -> BackupRecord:
        return cls(
            backup_id=str(data["backup_id"]),
            reason=str(data.get("reason", "owner")),
            created_at=str(data.get("created_at", "")),
            size_bytes=int(data.get("size_bytes", 0)),
            sha256=str(data.get("sha256", "")),
            schema_migrations=int(data.get("schema_migrations", 0)),
            latest_migration=str(data.get("latest_migration", "")),
            counts={str(k): int(v) for k, v in dict(data.get("counts", {})).items()},
            key_fingerprint=str(data.get("key_fingerprint", "")),
            included=tuple(data.get("included", INCLUDED)),
            not_included=tuple(data.get("not_included", NOT_INCLUDED)),
            state=str(data.get("state", "verified")),
            verified_at=data.get("verified_at"),
            detail=str(data.get("detail", "")),
            schema_generation=int(data.get("schema_generation", 0) or 0),
            trees={
                str(name): {
                    "files": int(summary.get("files", 0)),
                    "bytes": int(summary.get("bytes", 0)),
                    "sha256": str(summary.get("sha256", "")),
                }
                for name, summary in dict(data.get("trees", {})).items()
                if isinstance(summary, dict)
            },
        )


def create_backup(connection: Any, workspace_root: Path, *, reason: str = "owner") -> BackupRecord:
    """Snapshot the open store through ``connection`` and verify the copy.

    ``connection`` must be a keyed connection to the workspace database with no
    transaction open: ``ATTACH`` is refused inside one. On any failure the
    partial copy is removed, so a backup that exists is one that was checked.
    """
    root = Path(workspace_root).resolve()
    key_hex = _key_hex(root)
    backup_id = new_id("bkp_")
    target = backups_dir(root) / backup_id
    target.mkdir(parents=True, exist_ok=False)
    database = target / DATABASE
    try:
        connection.commit()
        connection.execute(f"ATTACH DATABASE ? AS raiker_backup KEY \"x'{key_hex}'\"", (str(database),))
        try:
            connection.execute("SELECT sqlcipher_export('raiker_backup')")
            # The export copies schema and rows, not the header's user_version,
            # which is the schema generation a restore checks (DEC-17 step 8).
            generation = int(connection.execute("PRAGMA main.user_version").fetchone()[0])
            connection.execute(f"PRAGMA raiker_backup.user_version = {generation}")
        finally:
            connection.execute("DETACH DATABASE raiker_backup")
        memory = internal_io_path(root / ".raiker" / "memory")
        if memory.is_dir():
            shutil.copytree(memory, target / MEMORY_DIR)
        trees: dict[str, dict[str, Any]] = {}
        for name in FILE_TREES:
            live = internal_io_path(root / ".raiker" / name)
            if live.is_dir():
                _copy_tree(live, target / name)
            trees[name] = _tree_summary(target / name)
        integrity, migrations, counts, generation = _inspect(database, key_hex)
        if integrity != "ok":
            raise BackupError("backup_damaged", f"The new copy failed its integrity check: {integrity[:200]}")
        record = BackupRecord(
            backup_id=backup_id,
            reason=reason,
            created_at=utc_now(),
            size_bytes=database.stat().st_size,
            sha256=_sha256(database),
            schema_migrations=len(migrations),
            latest_migration=migrations[-1] if migrations else "",
            counts=counts,
            key_fingerprint=key_fingerprint(root),
            included=INCLUDED,
            not_included=NOT_INCLUDED,
            verified_at=utc_now(),
            schema_generation=generation,
            trees=trees,
        )
        (target / MANIFEST).write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    if reason == "pre_migration":
        _prune(root, reason="pre_migration", keep=PRE_MIGRATION_KEEP)
    return record


def _prune(root: Path, *, reason: str, keep: int) -> None:
    matching = [record for record in list_backups(root) if record.reason == reason]
    for stale in matching[keep:]:
        shutil.rmtree(backups_dir(root) / stale.backup_id, ignore_errors=True)


def list_backups(workspace_root: Path) -> list[BackupRecord]:
    """Every backup with a readable manifest, newest first."""
    base = backups_dir(Path(workspace_root))
    if not base.is_dir():
        return []
    records: list[BackupRecord] = []
    for entry in base.iterdir():
        manifest = entry / MANIFEST
        if not manifest.is_file():
            continue
        try:
            records.append(BackupRecord.from_manifest(json.loads(manifest.read_text(encoding="utf-8"))))
        except (ValueError, KeyError, TypeError):
            continue
    return sorted(records, key=lambda record: (record.created_at, record.backup_id), reverse=True)


def _locate(workspace_root: Path, backup_id: str) -> Path:
    if not backup_id.startswith("bkp_") or "/" in backup_id or "\\" in backup_id or ".." in backup_id:
        raise BackupError("unknown_backup")
    target = backups_dir(Path(workspace_root)) / backup_id
    if not (target / MANIFEST).is_file():
        raise BackupError("unknown_backup")
    return target


def verify_backup(workspace_root: Path, backup_id: str) -> BackupRecord:
    """Re-read a backup: its checksum, whether this key opens it, its integrity.

    The answer is written back to the manifest, so the list says what was last
    measured and when.
    """
    root = Path(workspace_root).resolve()
    target = _locate(root, backup_id)
    record = BackupRecord.from_manifest(json.loads((target / MANIFEST).read_text(encoding="utf-8")))
    database = target / DATABASE
    state, detail = "verified", ""
    if not database.is_file():
        state, detail = "damaged", "The database file is missing from this backup."
    elif _sha256(database) != record.sha256:
        state, detail = "damaged", "The database file no longer matches the checksum taken when it was made."
    elif record.key_fingerprint != key_fingerprint(root):
        state, detail = "unreadable", "This backup was made with another workspace key."
    else:
        try:
            integrity, _migrations, _counts, _generation = _inspect(database, _key_hex(root))
        except BackupError as exc:
            state, detail = "unreadable", str(exc)
        else:
            if integrity != "ok":
                state, detail = "damaged", f"It failed its integrity check: {integrity[:200]}"
    if state == "verified":
        for name, summary in record.trees.items():
            if _tree_summary(target / name)["sha256"] != summary.get("sha256"):
                label = "checkpoint files" if name == "checkpoints" else "uploaded files"
                state, detail = "damaged", (
                    f"The {label} copied into this backup no longer match what was copied."
                )
                break
    if state == "verified" and not record.opens_here:
        state, detail = "newer", (
            f"A newer Raiker made this backup (schema {record.schema_generation}; this build "
            f"understands up to {SCHEMA_GENERATION}). Restore it with that Raiker."
        )
    checked = BackupRecord(**{**record.__dict__, "state": state, "verified_at": utc_now(), "detail": detail})
    (target / MANIFEST).write_text(json.dumps(checked.to_dict(), indent=2), encoding="utf-8")
    return checked


def delete_backup(workspace_root: Path, backup_id: str) -> None:
    shutil.rmtree(_locate(Path(workspace_root), backup_id))


@dataclass(frozen=True)
class RestoredWorkspace:
    backup_id: str
    path: str
    counts: dict[str, int]
    command: str
    #: Deletions recorded after the backup and applied to the copy, by kind.
    deletions_applied: dict[str, int]


def _reapply_after(workspace_root: Path, journal_root: Path, created_at: str) -> dict[str, int]:
    """Open the restored store at ``workspace_root`` and replay ``journal_root``'s later deletions."""
    from raiker.storage.deletion_journal import read_deletions, reapply_deletions
    from raiker.storage.sqlite import SQLiteStore, invalidate_workspace_connections

    deletions = read_deletions(journal_root, after=created_at)
    store = SQLiteStore(workspace_root)
    try:
        return reapply_deletions(store, deletions)
    finally:
        invalidate_workspace_connections(workspace_root)


def restore_backup(workspace_root: Path, backup_id: str) -> RestoredWorkspace:
    """Write a verified copy of a backup as a workspace of its own.

    Never touches the running workspace. Refuses a backup that does not verify,
    and a restore that already exists rather than writing over it.
    """
    root = Path(workspace_root).resolve()
    checked = verify_backup(root, backup_id)
    if checked.state != "verified":
        raise BackupError("backup_not_verified", checked.detail)
    destination = restores_dir(root) / backup_id
    if destination.exists():
        raise BackupError("restore_exists", f"A restore of this backup is already at {destination}.")
    runtime = destination / ".raiker"
    runtime.mkdir(parents=True)
    try:
        source = backups_dir(root) / backup_id
        shutil.copy2(source / DATABASE, runtime / DATABASE)
        if (source / MEMORY_DIR).is_dir():
            shutil.copytree(source / MEMORY_DIR, runtime / MEMORY_DIR)
        for name in FILE_TREES:
            if (source / name).is_dir():
                _copy_tree(source / name, runtime / name)
        shutil.copy2(app_key_path(root), runtime / "app.key")
        integrity, _migrations, _counts, _generation = _inspect(runtime / DATABASE, _key_hex(root))
        if integrity != "ok":
            raise BackupError("restore_damaged", integrity[:200])
        # DEC-24 step 5 — the running workspace's later deletions, applied to
        # the copy before anyone opens it.
        applied = _reapply_after(destination, root, checked.created_at)
        _integrity, _migrations, counts, _generation = _inspect(runtime / DATABASE, _key_hex(root))
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return RestoredWorkspace(
        backup_id=backup_id,
        path=str(destination),
        counts=counts,
        command=f'raiker-web --workspace "{destination}" --port 8766',
        deletions_applied=applied,
    )


@dataclass(frozen=True)
class InPlaceRestore:
    backup_id: str
    #: Where the database that would not open, and its memory files, now are.
    quarantine: str
    counts: dict[str, int]
    deletions_applied: dict[str, int]


def restore_in_place(workspace_root: Path, backup_id: str) -> InPlaceRestore:
    """BUG-323 — put a verified backup in place of a database that will not open.

    Only for the lock screen's case, which the caller checks: there is no
    running workspace to protect, because nothing can open this one. In order:

    1. verify the backup (checksum, this key, integrity) and that this build can
       open it without a downgrade;
    2. stage the verified copy beside the database, not over it;
    3. move the current database (with any ``-wal``/``-shm``) and the memory
       files into ``.raiker/quarantine/<time>/`` — kept, never deleted;
    4. switch the staged copy in with one ``os.replace``, so the workspace holds
       either the old file or the whole new one, never part of either;
    5. replay the deletions recorded after the backup, then re-check integrity.

    Any failure after step 3 moves the quarantined files back.
    """
    import os

    from raiker.storage.sqlite import invalidate_workspace_connections

    root = Path(workspace_root).resolve()
    checked = verify_backup(root, backup_id)
    if checked.state != "verified":
        raise BackupError("backup_not_verified", checked.detail)
    runtime = internal_io_path(root / ".raiker")
    live_db = runtime / DATABASE
    source = backups_dir(root) / backup_id
    staged = runtime / f"{DATABASE}.restoring"
    shutil.copy2(source / DATABASE, staged)
    if _sha256(staged) != checked.sha256:
        staged.unlink(missing_ok=True)
        raise BackupError("restore_damaged", "The staged copy does not match the backup's checksum.")
    invalidate_workspace_connections(root)
    stamp = utc_now().replace(":", "").replace("-", "").split(".")[0]
    # Named for when, not for which backup: why.json says which. A backup id
    # inside a path reads as a token to the response redactor (FIXED-799).
    held = quarantine_dir(root) / stamp
    suffix = 1
    while held.exists():
        suffix += 1
        held = quarantine_dir(root) / f"{stamp}-{suffix}"
    held.mkdir(parents=True, exist_ok=False)
    moved: list[tuple[Path, Path]] = []
    try:
        for name in (DATABASE, f"{DATABASE}-wal", f"{DATABASE}-shm", MEMORY_DIR):
            current = runtime / name
            if current.exists():
                shutil.move(str(current), str(held / name))
                moved.append((held / name, current))
        os.replace(staged, live_db)
        if (source / MEMORY_DIR).is_dir():
            shutil.copytree(source / MEMORY_DIR, runtime / MEMORY_DIR)
        # The trees were never unreadable, so they are not quarantined: what the
        # backup has and the workspace lost is added back, and nothing is replaced.
        for name in FILE_TREES:
            if (source / name).is_dir():
                _add_missing(source / name, runtime / name)
        applied = _reapply_after(root, root, checked.created_at)
        integrity, _migrations, counts, _generation = _inspect(live_db, _key_hex(root))
        if integrity != "ok":
            raise BackupError("restore_damaged", integrity[:200])
    except BaseException:
        invalidate_workspace_connections(root)
        live_db.unlink(missing_ok=True)
        shutil.rmtree(runtime / MEMORY_DIR, ignore_errors=True)
        for kept, original in reversed(moved):
            shutil.move(str(kept), str(original))
        staged.unlink(missing_ok=True)
        raise
    (held / "why.json").write_text(
        json.dumps(
            {"restored_from": backup_id, "at": utc_now(), "moved": [kept.name for kept, _ in moved]},
            indent=2,
        ),
        encoding="utf-8",
    )
    return InPlaceRestore(
        backup_id=backup_id, quarantine=str(held), counts=counts, deletions_applied=applied
    )
