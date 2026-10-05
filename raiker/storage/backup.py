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
  under ``.raiker/memory``; they are copied with the database. Checkpoints,
  artifacts, the event log and attached folders are **not** included, and the
  manifest says so rather than implying a whole workspace.
* **Key custody, stated.** The backup opens with this workspace's
  ``.raiker/app.key`` and nothing else. The manifest records a fingerprint of
  that key so a restore can say which key it needs; the key itself is never
  written into a backup.
* **Restore never replaces the running workspace.** It writes a verified copy
  into ``.raiker/restores/<backup id>/`` as a workspace of its own, with a copy
  of the key it needs, and says how to open it. Switching to it is the owner's
  act, taken with Raiker stopped.
"""

from __future__ import annotations

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

MANIFEST = "manifest.json"
DATABASE = "raiker.db"
MEMORY_DIR = "memory"

#: Pre-migration backups kept; older ones are removed when a new one is taken.
#: Owner backups are kept until the owner removes them.
PRE_MIGRATION_KEEP = 3

#: What a backup holds and does not, said in the manifest and on the page.
INCLUDED = ("database", "memory_files")
NOT_INCLUDED = ("checkpoints", "artifacts", "event_log", "attached_folders")

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


def _open_copy(path: Path, key_hex: str) -> Any:
    connection = sqlite3.connect(str(path))
    connection.execute(f"PRAGMA key = \"x'{key_hex}'\"")
    return connection


def _inspect(path: Path, key_hex: str) -> tuple[str, list[str], dict[str, int]]:
    """``(integrity, migration ids, counts)`` read from an encrypted copy."""
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
        return integrity, migrations, counts
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
        finally:
            connection.execute("DETACH DATABASE raiker_backup")
        memory = internal_io_path(root / ".raiker" / "memory")
        if memory.is_dir():
            shutil.copytree(memory, target / MEMORY_DIR)
        integrity, migrations, counts = _inspect(database, key_hex)
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
            integrity, _migrations, _counts = _inspect(database, _key_hex(root))
        except BackupError as exc:
            state, detail = "unreadable", str(exc)
        else:
            if integrity != "ok":
                state, detail = "damaged", f"It failed its integrity check: {integrity[:200]}"
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
        shutil.copy2(app_key_path(root), runtime / "app.key")
        integrity, _migrations, counts = _inspect(runtime / DATABASE, _key_hex(root))
        if integrity != "ok":
            raise BackupError("restore_damaged", integrity[:200])
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return RestoredWorkspace(
        backup_id=backup_id,
        path=str(destination),
        counts=counts,
        command=f'raiker-web --workspace "{destination}" --port 8766',
    )
