"""DEC-24 step 5 and DEC-17 step 8 — backups Raiker makes itself, and restoring one.

The lock screen told an owner with a damaged database to "restore the database
from a backup", and Raiker made none. Now: a consistent snapshot through
SQLCipher's own export, encrypted from the first byte; a manifest with a
checksum, the schema it was taken at and what it does and does not hold; a
verification that re-reads all three; a restore that writes a verified copy as
a workspace of its own and never touches the running one; and a snapshot taken
automatically before a database is migrated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.storage.backup import (
    NOT_INCLUDED,
    PRE_MIGRATION_KEEP,
    BackupError,
    backups_dir,
    create_backup,
    list_backups,
    restore_backup,
    verify_backup,
)
from raiker.storage.sqlite import SQLiteStore


def _store_with_data(root: Path) -> SQLiteStore:
    store = SQLiteStore(root)
    store.create_session("sess_backup", str(root))
    return store


def test_a_backup_is_encrypted_verified_and_says_what_it_holds(tmp_path: Path) -> None:
    store = _store_with_data(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    assert record.state == "verified"
    assert record.counts["sessions"] >= 1
    assert record.schema_migrations > 100
    assert set(NOT_INCLUDED) == set(record.not_included)
    database = backups_dir(tmp_path) / record.backup_id / "raiker.db"
    # Encrypted: no SQLite header and none of the stored text in the clear.
    raw = database.read_bytes()
    assert not raw.startswith(b"SQLite format 3")
    assert b"sess_backup" not in raw
    # The key is never written into a backup.
    assert not (backups_dir(tmp_path) / record.backup_id / "app.key").exists()
    assert [item.backup_id for item in list_backups(tmp_path)] == [record.backup_id]


def test_verification_notices_a_changed_file(tmp_path: Path) -> None:
    store = _store_with_data(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    database = backups_dir(tmp_path) / record.backup_id / "raiker.db"
    data = bytearray(database.read_bytes())
    data[len(data) // 2] ^= 0xFF
    database.write_bytes(bytes(data))
    checked = verify_backup(tmp_path, record.backup_id)
    assert checked.state == "damaged"
    assert "checksum" in checked.detail
    # The answer is written back, so the list says what was last measured.
    assert list_backups(tmp_path)[0].state == "damaged"


def test_a_backup_made_with_another_key_is_unreadable_not_damaged(tmp_path: Path) -> None:
    store = _store_with_data(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    manifest = backups_dir(tmp_path) / record.backup_id / "manifest.json"
    data = json.loads(manifest.read_text())
    data["key_fingerprint"] = "0" * 16
    manifest.write_text(json.dumps(data))
    assert verify_backup(tmp_path, record.backup_id).state == "unreadable"


def test_restore_writes_a_separate_verified_workspace(tmp_path: Path) -> None:
    store = _store_with_data(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    store.create_session("sess_after_backup", str(tmp_path))
    restored = restore_backup(tmp_path, record.backup_id)
    target = Path(restored.path)
    assert target != tmp_path and (target / ".raiker" / "raiker.db").is_file()
    assert restored.counts["sessions"] == record.counts["sessions"]
    # The running workspace is untouched by a restore.
    assert store.load_session("sess_after_backup") is not None
    # The restored copy opens as a workspace of its own and holds what was backed up.
    reopened = SQLiteStore(target)
    assert reopened.load_session("sess_backup") is not None
    assert reopened.load_session("sess_after_backup") is None
    with pytest.raises(BackupError) as exists:
        restore_backup(tmp_path, record.backup_id)
    assert exists.value.reason == "restore_exists"


def test_a_backup_that_does_not_verify_is_not_restored(tmp_path: Path) -> None:
    store = _store_with_data(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    (backups_dir(tmp_path) / record.backup_id / "raiker.db").write_bytes(b"not a database")
    with pytest.raises(BackupError) as refused:
        restore_backup(tmp_path, record.backup_id)
    assert refused.value.reason == "backup_not_verified"


@pytest.mark.parametrize("backup_id", ["../escape", "bkp_../../x", "nope"])
def test_an_id_that_is_not_a_backup_reaches_nothing(tmp_path: Path, backup_id: str) -> None:
    SQLiteStore(tmp_path)
    with pytest.raises(BackupError) as refused:
        verify_backup(tmp_path, backup_id)
    assert refused.value.reason == "unknown_backup"


def test_a_pending_migration_takes_a_snapshot_first_and_keeps_three(tmp_path: Path) -> None:
    store = _store_with_data(tmp_path)
    assert list_backups(tmp_path) == []  # an up-to-date workspace takes none
    for _ in range(PRE_MIGRATION_KEEP + 1):
        with store.connect() as connection:
            connection.execute(
                "DELETE FROM migrations WHERE migration_id = 'RAIKER-2091-task-run-limit'"
            )
        SQLiteStore(tmp_path)
    taken = [record for record in list_backups(tmp_path) if record.reason == "pre_migration"]
    assert len(taken) == PRE_MIGRATION_KEEP
    assert all(record.state == "verified" for record in taken)


def test_a_fresh_workspace_takes_no_pre_migration_snapshot(tmp_path: Path) -> None:
    SQLiteStore(tmp_path)
    assert list_backups(tmp_path) == []


def test_the_routes_need_an_owner_and_say_what_they_did(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    client = TestClient(create_app(tmp_path))
    token = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    made = client.post("/api/backups", headers=headers)
    assert made.status_code == 200 and made.json()["state"] == "verified"
    listing = client.get("/api/backups", headers=headers).json()
    assert listing["backups"][0]["key_fingerprint"] == listing["key_fingerprint"]
    backup_id = made.json()["backup_id"]
    assert client.post(f"/api/backups/{backup_id}/verify", headers=headers).json()["state"] == "verified"
    restored = client.post(f"/api/backups/{backup_id}/restore", headers=headers).json()
    assert "--workspace" in restored["command"]
    # The owner's own folder, not `[REDACTED_SECRET]`: a backup id inside a path
    # reads as a token to the secret redactor.
    assert restored["path"].endswith(f".raiker/restores/{backup_id}")
    assert "REDACTED" not in restored["command"]
    assert client.post(f"/api/backups/{backup_id}/restore", headers=headers).status_code == 409
    assert client.delete(f"/api/backups/{backup_id}", headers=headers).status_code == 200
    assert client.post("/api/backups/bkp_missing/verify", headers=headers).status_code == 404
