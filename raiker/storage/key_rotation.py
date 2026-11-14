"""BUG-354 — rotate the workspace key in place.

``.raiker/app.key`` is the one secret a workspace has: SHA-256 of it is the
SQLCipher key of ``raiker.db``, and Fernet under it seals Raiker's own at-rest
secrets (MFA seeds, the machine issuer's private seed, command material). An
owner who believes it was copied off the machine could, before this, only
export memories into a new workspace.

Rotation, in order, failing closed at every step:

1. **Refuse while something depends on the old key mid-flight**: a project
   move holds HMAC reservations signed with it.
2. **Take a verified backup** (reason ``pre_key_rotation``) with the old key.
3. **Write the new key beside the old one** as ``app.key.next`` (0600,
   exclusive). From here an interruption is recoverable: whichever key opens
   the database is the live one (:func:`finish_interrupted_rotation`).
4. **Re-key the database** with ``PRAGMA rekey`` on a dedicated connection,
   after every cached connection is taken out of use.
5. **Re-verify** with a fresh connection under the new key (``quick_check``).
6. **Re-seal every Fernet token** the old key made, in one transaction.
7. **Retire the old key** to ``.raiker/retired-keys/<fingerprint>.key`` and
   move ``app.key.next`` into place with one ``os.replace``.

Backups made before the rotation keep needing the old key. It is kept in
``retired-keys`` so they stay verifiable and restorable as a separate copy;
the owner can discard it, after which those backups cannot be opened.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.auth.app_key import (
    app_key_path,
    ensure_app_key,
    next_key_path,
    retired_key_path,
    retired_keys_dir,
)
from raiker.auth.secure_io import atomic_write_private
from raiker.storage.internal_paths import internal_io_path

#: The prefix every Fernet token has (version byte 0x80, base64url).
_FERNET_PREFIX = "gAAAAA"


class KeyRotationError(Exception):
    """A refusal or failure, named for the owner. The old key stays in force."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class KeyRotationResult:
    old_fingerprint: str
    new_fingerprint: str
    backup_id: str
    resealed: int
    #: Backups that now need the retired key, by id.
    backups_on_retired_key: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_fingerprint": self.old_fingerprint,
            "new_fingerprint": self.new_fingerprint,
            "backup_id": self.backup_id,
            "resealed": self.resealed,
            "backups_on_retired_key": list(self.backups_on_retired_key),
        }


def _hex(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def fingerprint_of(key: bytes) -> str:
    """The same one-way label backups record (``backup.key_fingerprint``)."""
    return hashlib.sha256(("raiker-backup-key:" + _hex(key)).encode()).hexdigest()[:16]


def _database(root: Path) -> Path:
    return internal_io_path(root / ".raiker" / "raiker.db")


def _opens_with(database: Path, key: bytes) -> bool:
    connection = sqlite3.connect(str(database))
    try:
        connection.execute(f"PRAGMA key = \"x'{_hex(key)}'\"")
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except sqlite3.DatabaseError:
        return False
    finally:
        connection.close()


def _pending_project_moves(root: Path) -> bool:
    area = internal_io_path(root / ".raiker" / "project-migrations")
    with contextlib.suppress(OSError):
        if area.is_dir():
            return any(path.suffix == ".json" for path in area.iterdir())
    return False


def _reseal(connection: Any, old: bytes, new: bytes) -> int:
    """Re-encrypt every Fernet token sealed by ``old`` under ``new``; how many."""
    rotator = MultiFernet([Fernet(new), Fernet(old)])
    old_only = Fernet(old)
    tables = [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND (sql IS NULL OR upper(sql) NOT LIKE 'CREATE VIRTUAL%')"
        ).fetchall()
    ]
    changed = 0
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        columns = [str(row[1]) for row in connection.execute(f"PRAGMA table_info({quoted})").fetchall()]
        for column in columns:
            col = '"' + column.replace('"', '""') + '"'
            try:
                rows = connection.execute(
                    f"SELECT DISTINCT {col} FROM {quoted} "
                    f"WHERE CAST(substr({col}, 1, 6) AS TEXT) = ?",
                    (_FERNET_PREFIX,),
                ).fetchall()
            except sqlite3.DatabaseError:
                continue
            for (value,) in rows:
                token = value.encode() if isinstance(value, str) else bytes(value)
                try:
                    old_only.decrypt(token)
                except InvalidToken:
                    continue  # not ours, or already under the new key
                fresh = rotator.rotate(token)
                replacement: Any = fresh.decode() if isinstance(value, str) else fresh
                connection.execute(f"UPDATE {quoted} SET {col} = ? WHERE {col} = ?", (replacement, value))
                changed += 1
    return changed


def _promote(root: Path, old: bytes, new_path: Path) -> None:
    """Retire ``old`` and make the staged key the live one (one ``os.replace``)."""
    retired = retired_key_path(root, fingerprint_of(old))
    retired_keys_dir(root).mkdir(parents=True, exist_ok=True)
    if not retired.exists():
        atomic_write_private(retired, old, exclusive=True)
    os.replace(new_path, app_key_path(root))


def finish_interrupted_rotation(workspace_root: str | Path) -> str | None:
    """Complete or undo a rotation a crash left half done; what happened, or ``None``.

    The database decides: if it opens with ``app.key.next`` the re-key
    happened, so the tokens are re-sealed (idempotently) and the new key
    promoted; if it still opens with ``app.key`` it did not, and the staged key
    is removed. Neither opening leaves both files untouched for the owner.
    """
    root = Path(workspace_root).resolve()
    staged = next_key_path(root)
    if not staged.exists():
        return None
    database = _database(root)
    current_path = app_key_path(root)
    new = staged.read_bytes().strip()
    old = current_path.read_bytes().strip() if current_path.exists() else b""
    if not database.exists() or (old and _opens_with(database, old)):
        staged.unlink(missing_ok=True)
        return "undone"
    if not _opens_with(database, new):
        return None
    if old:
        connection = sqlite3.connect(str(database))
        try:
            connection.execute(f"PRAGMA key = \"x'{_hex(new)}'\"")
            with connection:
                _reseal(connection, old, new)
        finally:
            connection.close()
        _promote(root, old, staged)
    else:
        os.replace(staged, current_path)
    return "completed"


def rotate_workspace_key(store: Any) -> KeyRotationResult:
    """Rotate this workspace's key; raises :class:`KeyRotationError` and changes nothing on refusal."""
    from raiker.storage.backup import BackupError, create_backup, list_backups
    from raiker.storage.sqlite import invalidate_workspace_connections

    root = Path(store.paths.workspace_root).resolve()
    if next_key_path(root).exists():
        finish_interrupted_rotation(root)
    if _pending_project_moves(root):
        raise KeyRotationError(
            "key_rotation_project_move_pending",
            "A project folder move is still in progress, and it is signed with the current key. "
            "Finish or cancel the move in Work › Projects, then rotate the key.",
        )
    old = ensure_app_key(root)
    try:
        backup = create_backup(store.connect(), root, reason="pre_key_rotation")
    except BackupError as exc:
        raise KeyRotationError(
            "key_rotation_backup_failed",
            f"Raiker could not take the verified backup it makes first, so the key was not changed: {exc}",
        ) from exc
    new = Fernet.generate_key()
    staged = next_key_path(root)
    if not atomic_write_private(staged, new, exclusive=True):
        raise KeyRotationError(
            "key_rotation_in_progress", "Another key rotation is already in progress. Try again in a minute."
        )
    database = _database(root)
    invalidate_workspace_connections(root)
    connection = sqlite3.connect(str(database), timeout=30.0)
    try:
        connection.execute(f"PRAGMA key = \"x'{_hex(old)}'\"")
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        # SQLCipher re-keys a WAL database in place, with other connections
        # still open (they are retired above and fail closed on the old key).
        # The checkpoint folds the log in first so the re-key writes every page.
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        connection.execute(f"PRAGMA rekey = \"x'{_hex(new)}'\"")
    except sqlite3.DatabaseError as exc:
        connection.close()
        if not _opens_with(database, new):
            staged.unlink(missing_ok=True)
        else:
            finish_interrupted_rotation(root)
        raise KeyRotationError(
            "key_rotation_rekey_failed",
            "The database could not be re-keyed, so the current key stays in force. "
            f"Nothing was lost; the backup {backup.backup_id} was taken first.",
        ) from exc
    connection.close()
    check = sqlite3.connect(str(database))
    try:
        check.execute(f"PRAGMA key = \"x'{_hex(new)}'\"")
        verdict = str(check.execute("PRAGMA quick_check").fetchone()[0])
        if verdict != "ok":
            raise KeyRotationError(
                "key_rotation_verify_failed",
                f"The re-keyed database failed its check ({verdict[:120]}). Restore backup {backup.backup_id}.",
            )
        with check:
            resealed = _reseal(check, old, new)
    finally:
        check.close()
    _promote(root, old, staged)
    invalidate_workspace_connections(root)
    old_fp = fingerprint_of(old)
    on_retired = tuple(
        record.backup_id for record in list_backups(root) if record.key_fingerprint == old_fp
    )
    return KeyRotationResult(
        old_fingerprint=old_fp,
        new_fingerprint=fingerprint_of(new),
        backup_id=backup.backup_id,
        resealed=resealed,
        backups_on_retired_key=on_retired,
    )


def retired_fingerprints(workspace_root: str | Path) -> list[str]:
    """The fingerprints of retired keys this workspace still keeps, sorted."""
    directory = retired_keys_dir(Path(workspace_root).resolve())
    with contextlib.suppress(OSError):
        if directory.is_dir():
            return sorted(path.stem for path in directory.iterdir() if path.suffix == ".key")
    return []


def discard_retired_key(workspace_root: str | Path, fingerprint: str) -> bool:
    """Delete one retired key; backups that needed it can no longer be opened."""
    if len(fingerprint) != 16 or any(char not in "0123456789abcdef" for char in fingerprint):
        return False
    path = retired_key_path(Path(workspace_root).resolve(), fingerprint)
    if not path.exists():
        return False
    path.unlink()
    return True
