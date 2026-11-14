"""BUG-354 — the workspace key is rotated in place, and nothing is lost."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pyotp
import pytest
from cryptography.fernet import Fernet, InvalidToken
from fastapi.testclient import TestClient
from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.api.app import create_app
from raiker.auth.app_key import app_fernet, app_key_path, next_key_path, retired_keys
from raiker.storage.backup import list_backups, restore_backup, verify_backup
from raiker.storage.key_rotation import (
    KeyRotationError,
    fingerprint_of,
    finish_interrupted_rotation,
    rotate_workspace_key,
)
from raiker.storage.sqlite import SQLiteStore, invalidate_workspace_connections

USER = "owner"
PASSWORD = "correct horse battery staple 42"


def _opens(db: Path, key: bytes) -> bool:
    connection = sqlite3.connect(str(db))
    try:
        connection.execute(f"PRAGMA key = \"x'{hashlib.sha256(key).hexdigest()}'\"")
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except sqlite3.DatabaseError:
        return False
    finally:
        connection.close()


@pytest.fixture()
def workspace(tmp_path: Path) -> tuple[Path, TestClient, dict[str, str], pyotp.TOTP]:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    secret = client.post("/api/auth/mfa/enroll", headers=headers).json()["secret"]
    totp = pyotp.TOTP(secret)
    assert client.post("/api/auth/mfa/activate", json={"code": totp.now()}, headers=headers).status_code == 200
    return tmp_path, client, headers, totp


def test_rotation_rekeys_reseals_and_keeps_old_backups_usable(workspace) -> None:  # type: ignore[no-untyped-def]
    root, _client, _headers, totp = workspace
    store = SQLiteStore(root)
    db = store.db_path
    old = app_key_path(root).read_bytes().strip()
    sealed_before = app_fernet(root).encrypt(b"probe")

    result = rotate_workspace_key(store)

    new = app_key_path(root).read_bytes().strip()
    assert new != old
    assert result.old_fingerprint == fingerprint_of(old)
    assert result.new_fingerprint == fingerprint_of(new)
    assert result.resealed >= 1  # the MFA seed at least
    assert _opens(db, new) and not _opens(db, old)
    assert not next_key_path(root).exists()
    assert old in retired_keys(root)
    # A token sealed before the rotation still opens (MultiFernet), and new ones use the new key.
    assert app_fernet(root).decrypt(sealed_before) == b"probe"
    assert Fernet(new).decrypt(app_fernet(root).encrypt(b"x")) == b"x"

    # The MFA seed was re-sealed under the new key alone: sign-in with a code still works.
    invalidate_workspace_connections(root)
    fresh = TestClient(create_app(root))
    login = fresh.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()
    verify = fresh.post("/api/auth/mfa/verify", json={"ticket": login["ticket"], "code": totp.now()})
    assert verify.status_code == 200, verify.text
    seeds = SQLiteStore(root)._rows("SELECT mfa_secret_encrypted FROM account_credentials WHERE mfa_secret_encrypted IS NOT NULL")
    for (seed,) in seeds:
        Fernet(new).decrypt(bytes(seed) if not isinstance(seed, str) else seed.encode())
        with pytest.raises(InvalidToken):
            Fernet(old).decrypt(bytes(seed) if not isinstance(seed, str) else seed.encode())

    # The pre-rotation backup needs the retired key, verifies with it, and restores as a copy.
    assert result.backup_id in result.backups_on_retired_key
    assert verify_backup(root, result.backup_id).state == "verified"
    restored = restore_backup(root, result.backup_id)
    assert _opens(Path(restored.path) / ".raiker" / "raiker.db", old)
    assert any(record.backup_id == result.backup_id for record in list_backups(root))


def test_an_interrupted_rotation_is_finished_by_whichever_key_opens(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).status_code == 200
    store = SQLiteStore(tmp_path)
    store.connect()
    # Crash before the re-key: the staged key is discarded.
    next_key_path(tmp_path).write_bytes(Fernet.generate_key())
    invalidate_workspace_connections(tmp_path)
    assert finish_interrupted_rotation(tmp_path) == "undone"
    assert not next_key_path(tmp_path).exists()

    # Crash after the re-key: the staged key is promoted.
    old = app_key_path(tmp_path).read_bytes().strip()
    new = Fernet.generate_key()
    next_key_path(tmp_path).write_bytes(new)
    connection = sqlite3.connect(str(store.db_path))
    connection.execute(f"PRAGMA key = \"x'{hashlib.sha256(old).hexdigest()}'\"")
    connection.execute("PRAGMA journal_mode = DELETE")
    connection.execute(f"PRAGMA rekey = \"x'{hashlib.sha256(new).hexdigest()}'\"")
    connection.close()
    assert finish_interrupted_rotation(tmp_path) == "completed"
    assert app_key_path(tmp_path).read_bytes().strip() == new
    assert old in retired_keys(tmp_path)


def test_rotation_refuses_while_a_project_move_is_signed_with_the_old_key(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).status_code == 200
    area = tmp_path / ".raiker" / "project-migrations"
    area.mkdir(parents=True, exist_ok=True)
    (area / "pending.json").write_text("{}")
    old = app_key_path(tmp_path).read_bytes()
    with pytest.raises(KeyRotationError) as refused:
        rotate_workspace_key(SQLiteStore(tmp_path))
    assert refused.value.reason == "key_rotation_project_move_pending"
    assert app_key_path(tmp_path).read_bytes() == old
