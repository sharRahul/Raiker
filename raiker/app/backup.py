from __future__ import annotations

import json
import os
import secrets
import zipfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class BackupResult:
    path: Path
    created_at: str


def _backup_key(workspace_root: Path) -> bytes:
    key_path = workspace_root / ".raiker" / "keys" / "backup.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        temporary = key_path.with_suffix(f".{secrets.token_hex(4)}.tmp")
        temporary.write_bytes(Fernet.generate_key())
        with suppress_os_error():
            os.chmod(temporary, 0o600)
        temporary.replace(key_path)
    return key_path.read_bytes().strip()


class suppress_os_error:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return isinstance(exc, OSError)


def create_local_backup(workspace_root: str | Path, target: str | Path) -> BackupResult:
    root = Path(workspace_root).resolve()
    destination = Path(target).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    probe = destination / f".raiker-write-{secrets.token_hex(4)}"
    probe.write_bytes(b"ok")
    probe.unlink()

    store = SQLiteStore(root)
    store.connect().commit()
    created_at = utc_now()
    stamp = created_at.replace(":", "-")
    final_path = destination / f"raiker-backup-{stamp}.zip"
    temporary = final_path.with_suffix(".tmp")
    manifest = Fernet(_backup_key(root)).encrypt(
        json.dumps({"schema": 1, "created_at": created_at, "kind": "local-recovery"}).encode()
    )
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(store.db_path, "raiker.db")
            archive.writestr("manifest.enc", manifest)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise OSError("backup_verification_failed")
        temporary.replace(final_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return BackupResult(path=final_path, created_at=created_at)
