"""Move Raiker to another machine (RU-17).

A backup (``raiker.storage.backup``) opens only with the workspace key of the
machine that made it, so it cannot carry Raiker to a new computer. A *move
file* can:

* **Sealed with a passphrase the owner chooses.** The whole file is one
  AES-256-GCM ciphertext under a key derived from the passphrase with scrypt.
  The header (format tag and salt) is the authenticated data, so a file that
  was cut, altered or opened with the wrong passphrase is refused as one
  answer: ``move_passphrase_or_file_wrong``. Nothing in it is readable
  without the passphrase.
* **What it carries.** A verified snapshot of the encrypted database (account,
  conversations, memory, notes, tasks, personas, settings kept in the store),
  the memory files, checkpoint and upload files, and the settings kept as
  files: user instructions, command policies, the sandbox and egress choices
  and hooks. The workspace key goes inside the sealed file, because the
  database and the tokens in it were sealed with it.
* **What it never carries.** Provider and connector keys: they are sealed by
  this machine's vault key, which is not exported, so the import removes them
  and the owner enters them again. Local model files, the event log, attached
  folders and anything about this machine (host registration, instances,
  remote-access pairing) stay behind.
* **Import only into a workspace with no account.** First run's *I have a
  backup* is the one place it is offered; a workspace someone already uses is
  refused (``move_workspace_in_use``), so an import never merges or replaces
  someone's data.
* **Re-keyed on arrival.** The new machine keeps its own key: the database is
  exported into a file under that key and every token sealed with the old key
  is re-sealed (the key-rotation path). The empty database it replaces is
  moved to ``.raiker/quarantine/``, not deleted.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.auth.app_key import ensure_app_key
from raiker.contracts.ids import utc_now
from raiker.storage.backup import (
    DATABASE,
    FILE_TREES,
    MEMORY_DIR,
    BackupError,
    backups_dir,
    create_backup,
    quarantine_dir,
)
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.migrations import SCHEMA_GENERATION

#: Format tag; the trailing byte is the format version.
MAGIC = b"RAIKERMOVE\x01"
SALT_BYTES = 16
NONCE_BYTES = 12
#: scrypt cost: about 32 MiB and a fraction of a second, per OWASP's floor.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
MIN_PASSPHRASE = 12
#: The largest move file read back. Larger workspaces move their uploads by hand.
MAX_BYTES = 512 * 1024 * 1024

#: Settings kept as files under ``.raiker/``, carried with the database.
SETTING_PATHS = (
    "user-instructions",
    "command-policies",
    "command-sandbox.json",
    "command-egress.json",
    "hooks.json",
)
CARRIED = ("database", "memory_files", *FILE_TREES, "settings_files")
LEFT_BEHIND = ("provider_keys", "connector_keys", "local_models", "event_log", "attached_folders", "machine_setup")

_KEY_MEMBER = "workspace.key"
_MANIFEST_MEMBER = "move.json"


class MoveError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


@dataclass(frozen=True)
class MoveExport:
    path: Path
    created_at: str
    size_bytes: int
    counts: dict[str, int]


@dataclass(frozen=True)
class MoveImport:
    created_at: str
    counts: dict[str, int]
    keys_removed: int
    quarantine: str


def _derive(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P).derive(passphrase.encode("utf-8"))


def seal(payload: bytes, passphrase: str) -> bytes:
    if len(passphrase) < MIN_PASSPHRASE:
        raise MoveError("move_passphrase_short", f"Use at least {MIN_PASSPHRASE} characters.")
    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    header = MAGIC + salt
    return header + nonce + AESGCM(_derive(passphrase, salt)).encrypt(nonce, payload, header)


def unseal(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(MAGIC[:-1]):
        raise MoveError("move_not_a_move_file", "This is not a Raiker move file.")
    if not blob.startswith(MAGIC):
        raise MoveError("move_format_newer", "A newer Raiker made this file.")
    header_end = len(MAGIC) + SALT_BYTES
    if len(blob) < header_end + NONCE_BYTES + 16:
        raise MoveError("move_passphrase_or_file_wrong")
    header = blob[:header_end]
    nonce = blob[header_end : header_end + NONCE_BYTES]
    try:
        return AESGCM(_derive(passphrase, header[len(MAGIC) :])).decrypt(
            nonce, blob[header_end + NONCE_BYTES :], header
        )
    except InvalidTag as exc:
        raise MoveError(
            "move_passphrase_or_file_wrong", "The passphrase is wrong or the file was changed."
        ) from exc


def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: str) -> None:
    if source.is_file():
        archive.write(source, prefix)
        return
    if not source.is_dir():
        return
    for path in sorted(source.rglob("*")):
        if path.is_file() and not path.is_symlink():
            archive.write(path, f"{prefix}/{path.relative_to(source).as_posix()}")


def export_move(connection: Any, workspace_root: Path, destination: Path, passphrase: str) -> MoveExport:
    """Write a passphrase-sealed move file into the folder ``destination``."""
    if len(passphrase) < MIN_PASSPHRASE:
        raise MoveError("move_passphrase_short", f"Use at least {MIN_PASSPHRASE} characters.")
    root = Path(workspace_root).resolve()
    folder = Path(destination).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    try:
        snapshot = create_backup(connection, root, reason="move")
    except BackupError as exc:
        raise MoveError(exc.reason, str(exc)) from exc
    source = backups_dir(root) / snapshot.backup_id
    created_at = utc_now()
    runtime = internal_io_path(root / ".raiker")
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                _MANIFEST_MEMBER,
                json.dumps(
                    {
                        "format": 1,
                        "created_at": created_at,
                        "schema_generation": snapshot.schema_generation,
                        "counts": snapshot.counts,
                        "database_sha256": snapshot.sha256,
                        "carried": list(CARRIED),
                        "left_behind": list(LEFT_BEHIND),
                    }
                ),
            )
            archive.writestr(_KEY_MEMBER, ensure_app_key(root))
            archive.write(source / DATABASE, DATABASE)
            _add_tree(archive, source / MEMORY_DIR, MEMORY_DIR)
            for name in FILE_TREES:
                _add_tree(archive, source / name, name)
            for name in SETTING_PATHS:
                _add_tree(archive, runtime / name, f"settings/{name}")
    finally:
        # The snapshot was only a consistent read for this file; it is not an
        # owner backup and is not left in the list.
        shutil.rmtree(source, ignore_errors=True)
    sealed = seal(buffer.getvalue(), passphrase)
    stamp = created_at.replace(":", "-").split(".")[0]
    final = folder / f"raiker-move-{stamp}.raikermove"
    temporary = final.with_suffix(f".{secrets.token_hex(4)}.tmp")
    try:
        temporary.write_bytes(sealed)
        if unseal(temporary.read_bytes(), passphrase)[:2] != b"PK":
            raise MoveError("move_verification_failed")
        temporary.replace(final)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return MoveExport(path=final, created_at=created_at, size_bytes=len(sealed), counts=dict(snapshot.counts))


def _safe_member(name: str) -> bool:
    parts = Path(name).parts
    return bool(parts) and not Path(name).is_absolute() and ".." not in parts and ":" not in name


def _hex(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def _rekey(source: Path, source_key: bytes, target: Path, target_key: bytes) -> dict[str, int]:
    """Copy ``source`` into a new database under ``target_key``; re-seal tokens; drop vault keys."""
    from raiker.storage.backup import COUNTED_TABLES
    from raiker.storage.key_rotation import _reseal

    connection = sqlite3.connect(str(source))
    try:
        connection.execute(f"PRAGMA key = \"x'{_hex(source_key)}'\"")
        try:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        except sqlite3.DatabaseError as exc:
            raise MoveError("move_database_unreadable", str(exc)[:200]) from exc
        if integrity != "ok":
            raise MoveError("move_database_damaged", integrity[:200])
        generation = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if generation > SCHEMA_GENERATION:
            raise MoveError("move_schema_newer", "A newer Raiker made this file. Update Raiker here first.")
        _reseal(connection, source_key, target_key)
        removed = 0
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "connector_credentials" in tables:
            removed = int(connection.execute("SELECT count(*) FROM connector_credentials").fetchone()[0])
            connection.execute("DELETE FROM connector_credentials")
        connection.commit()
        connection.execute(f"ATTACH DATABASE ? AS moved KEY \"x'{_hex(target_key)}'\"", (str(target),))
        try:
            connection.execute("SELECT sqlcipher_export('moved')")
            connection.execute(f"PRAGMA moved.user_version = {generation}")
        finally:
            connection.execute("DETACH DATABASE moved")
        counts: dict[str, int] = {}
        for table in COUNTED_TABLES:
            if table in tables:
                counts[table] = int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
        counts["keys_removed"] = removed
        return counts
    finally:
        connection.close()


def _pages_into(source: Path, source_key: bytes, target: Path, target_key: bytes) -> None:
    """Copy every page of ``source`` into ``target`` through the backup API."""
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.execute(f"PRAGMA key = \"x'{_hex(source_key)}'\"")
        dst.execute(f"PRAGMA key = \"x'{_hex(target_key)}'\"")
        dst.execute("PRAGMA busy_timeout = 15000")
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def workspace_has_account(workspace_root: Path) -> bool:
    from raiker.auth.accounts import AccountService

    try:
        return bool(AccountService(Path(workspace_root))._store.list_accounts())  # noqa: SLF001
    except Exception:  # an unreadable store is not an empty one
        return True


def import_move(workspace_root: Path, blob: bytes, passphrase: str) -> MoveImport:
    """Open a move file into this workspace, which must have no account yet."""
    from raiker.storage.sqlite import invalidate_workspace_connections

    root = Path(workspace_root).resolve()
    if len(blob) > MAX_BYTES:
        raise MoveError("move_file_too_large")
    if workspace_has_account(root):
        raise MoveError("move_workspace_in_use", "This Raiker already has an account; a move file opens only on first run.")
    payload = unseal(blob, passphrase)
    runtime = internal_io_path(root / ".raiker")
    staging = runtime / f"moving-{secrets.token_hex(4)}"
    staging.mkdir(parents=True)
    try:
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise MoveError("move_passphrase_or_file_wrong") from exc
        with archive:
            names = archive.namelist()
            if not all(_safe_member(name) for name in names) or DATABASE not in names or _KEY_MEMBER not in names:
                raise MoveError("move_file_incomplete")
            manifest = json.loads(archive.read(_MANIFEST_MEMBER))
            if int(manifest.get("format", 0)) != 1:
                raise MoveError("move_format_newer")
            old_key = archive.read(_KEY_MEMBER).strip()
            archive.extract(DATABASE, staging / "in")
            if hashlib.sha256((staging / "in" / DATABASE).read_bytes()).hexdigest() != manifest.get("database_sha256"):
                raise MoveError("move_file_incomplete", "The database inside does not match its manifest.")
            for name in names:
                if name.startswith((f"{MEMORY_DIR}/", "settings/", *(f"{tree}/" for tree in FILE_TREES))):
                    archive.extract(name, staging / "files")
        new_key = ensure_app_key(root)
        rekeyed = staging / DATABASE
        counts = _rekey(staging / "in" / DATABASE, old_key, rekeyed, new_key)
        keys_removed = counts.pop("keys_removed", 0)
        if workspace_has_account(root):  # someone registered while this ran
            raise MoveError("move_workspace_in_use")
        invalidate_workspace_connections(root)
        held = quarantine_dir(root) / ("before-move-" + utc_now().replace(":", "").replace("-", "").split(".")[0])
        held.mkdir(parents=True, exist_ok=True)
        # The database is copied *into* the open file with SQLite's backup
        # API, page by page under its lock, rather than swapped: on Windows a
        # worker's connection holds the file and it cannot be moved. The empty
        # database is copied out to the quarantine first, the same way.
        live_db = runtime / DATABASE
        _pages_into(live_db, new_key, held / DATABASE, new_key)
        moved: list[tuple[Path, Path]] = []
        try:
            for name in (MEMORY_DIR, *SETTING_PATHS):
                current = runtime / name
                if current.exists():
                    shutil.move(str(current), str(held / name))
                    moved.append((held / name, current))
            _pages_into(rekeyed, new_key, live_db, new_key)
            files = staging / "files"
            if (files / MEMORY_DIR).is_dir():
                shutil.copytree(files / MEMORY_DIR, runtime / MEMORY_DIR)
            for tree in FILE_TREES:
                if (files / tree).is_dir():
                    shutil.copytree(files / tree, runtime / tree, dirs_exist_ok=True)
            settings = files / "settings"
            if settings.is_dir():
                for entry in settings.iterdir():
                    if entry.name in SETTING_PATHS:
                        if entry.is_dir():
                            shutil.copytree(entry, runtime / entry.name)
                        else:
                            shutil.copy2(entry, runtime / entry.name)
        except BaseException:
            _pages_into(held / DATABASE, new_key, live_db, new_key)
            for kept, original in reversed(moved):
                if original.is_dir():
                    shutil.rmtree(original, ignore_errors=True)
                else:
                    original.unlink(missing_ok=True)
                shutil.move(str(kept), str(original))
            invalidate_workspace_connections(root)
            raise
        invalidate_workspace_connections(root)
        (held / "why.json").write_text(
            json.dumps({"replaced_by_move_file_from": manifest.get("created_at"), "at": utc_now()}, indent=2),
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return MoveImport(
        created_at=str(manifest.get("created_at", "")),
        counts=counts,
        keys_removed=keys_removed,
        quarantine=".raiker/quarantine/" + held.name,
    )
