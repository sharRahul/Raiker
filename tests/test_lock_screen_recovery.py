"""BUG-323, DEC-24 steps 5–6 and DEC-17 step 8 — getting back into a workspace that will not open.

Four things, each held here:

* a database a newer Raiker shaped is refused, named, and left unchanged
  (``store_schema_newer``), and every backup says which builds can open it;
* a deletion is journalled outside the database, and a restore replays the ones
  made after its backup, so a forgotten memory or a deleted conversation does
  not come back;
* the lock screen can list the workspace's backups and restore one in place:
  the database that would not open is moved into quarantine, never deleted,
  and the verified copy is switched in with one rename;
* those two routes answer only while the store will not open, only to this
  machine and only to a same-origin JSON request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.contracts.ids import new_id
from raiker.memory.store import (
    MemoryForgetGovernance,
    MemoryGovernance,
    forget_memory,
    write_memory,
)
from raiker.storage.backup import (
    BackupError,
    backups_dir,
    create_backup,
    list_backups,
    restore_backup,
    restore_in_place,
    verify_backup,
)
from raiker.storage.deletion_journal import journal_path, read_deletions
from raiker.storage.migrations import SCHEMA_GENERATION
from raiker.storage.sqlite import SQLiteStore, invalidate_workspace_connections, store_health
from raiker.storage.store_errors import STORE_SCHEMA_NEWER, StoreUnavailableError


def _has_session(store: SQLiteStore, session_id: str) -> bool:
    return store._row("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)) is not None  # noqa: SLF001


def _governance() -> MemoryGovernance:
    return MemoryGovernance(
        source_event_id=new_id("evt_"),
        source_session_id="",
        source_turn_id=None,
        source_type="user_ui",
        confidence=1.0,
        trust_score=1.0,
        retention="until_forget",
        approval_state="approved",
        created_by="principal_owner",
    )


def _forget(root: Path, store: SQLiteStore, memory_id: str) -> None:
    assert forget_memory(
        memory_id,
        workspace_root=root,
        store=store,
        governance=MemoryForgetGovernance(
            source_event_id=new_id("evt_"),
            source_session_id="",
            source_turn_id=None,
            source_type="user_ui",
            deleted_by="principal_owner",
        ),
        owner_principal_id="principal_owner",
    )


def _damage(root: Path) -> None:
    invalidate_workspace_connections(root)
    database = root / ".raiker" / "raiker.db"
    data = bytearray(database.read_bytes())
    data[16:4096] = os.urandom(4080)
    database.write_bytes(bytes(data))


def _make_newer(root: Path) -> None:
    connection = SQLiteStore(root).connect()
    connection.execute(f"PRAGMA user_version = {SCHEMA_GENERATION + 5}")
    connection.commit()
    invalidate_workspace_connections(root)


# ── DEC-17 step 8 ────────────────────────────────────────────────────────────


def test_every_bootstrap_writes_this_builds_generation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    assert store.connect().execute("PRAGMA user_version").fetchone()[0] == SCHEMA_GENERATION


def test_a_database_a_newer_raiker_shaped_is_refused_and_unchanged(tmp_path: Path) -> None:
    SQLiteStore(tmp_path).create_session("sess_newer", str(tmp_path))
    _make_newer(tmp_path)
    before = (tmp_path / ".raiker" / "raiker.db").read_bytes()
    with pytest.raises(StoreUnavailableError) as refused:
        SQLiteStore(tmp_path)
    assert refused.value.reason == STORE_SCHEMA_NEWER
    assert str(SCHEMA_GENERATION) in refused.value.detail
    # Nothing written: no migration, no snapshot, no header change.
    assert (tmp_path / ".raiker" / "raiker.db").read_bytes() == before
    assert list_backups(tmp_path) == []
    assert store_health(tmp_path)["reason"] == STORE_SCHEMA_NEWER


def test_a_backup_records_its_generation_and_a_newer_one_is_not_restored(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    assert record.schema_generation == SCHEMA_GENERATION and record.opens_here
    manifest = backups_dir(tmp_path) / record.backup_id / "manifest.json"
    data = json.loads(manifest.read_text())
    data["schema_generation"] = SCHEMA_GENERATION + 1
    manifest.write_text(json.dumps(data))
    checked = verify_backup(tmp_path, record.backup_id)
    assert checked.state == "newer" and not checked.opens_here
    with pytest.raises(BackupError):
        restore_backup(tmp_path, record.backup_id)


# ── DEC-24 step 5: the deletion journal ─────────────────────────────────────


def test_deletions_are_journalled_without_content(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_gone", str(tmp_path))
    memory = write_memory(
        "The vault code is 1234.",
        workspace_root=tmp_path,
        store=store,
        governance=_governance(),
        owner_principal_id="principal_owner",
    )
    _forget(tmp_path, store, memory.memory_id)
    assert store.delete_session("sess_gone")
    kinds = [(entry.kind, entry.object_id) for entry in read_deletions(tmp_path)]
    assert ("memory_forget", memory.memory_id) in kinds
    assert ("session_delete", "sess_gone") in kinds
    assert "1234" not in journal_path(tmp_path).read_text()


def test_a_restore_to_a_new_folder_does_not_bring_back_what_was_deleted_since(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_gone", str(tmp_path))
    memory = write_memory(
        "Remember the blue door.",
        workspace_root=tmp_path,
        store=store,
        governance=_governance(),
        owner_principal_id="principal_owner",
    )
    record = create_backup(store.connect(), tmp_path)
    _forget(tmp_path, store, memory.memory_id)
    assert store.delete_session("sess_gone")

    restored = restore_backup(tmp_path, record.backup_id)
    assert restored.deletions_applied["memory_forget"] == 1
    assert restored.deletions_applied["session_delete"] == 1
    copy = SQLiteStore(restored.path)
    assert not _has_session(copy, "sess_gone")
    row = copy._row(  # noqa: SLF001
        "SELECT approval_state, deleted_at FROM approved_memory WHERE memory_id = ?", (memory.memory_id,)
    )
    assert row is not None and row["approval_state"] == "forgotten" and row["deleted_at"]
    export = Path(restored.path) / ".raiker" / "memory" / f"{memory.memory_id}.md"
    assert "blue door" not in export.read_text()
    # The replay is not itself journalled into the copy.
    assert not journal_path(restored.path).exists()


def test_a_purge_since_the_backup_is_purged_from_the_restore(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Delete me for good.",
        workspace_root=tmp_path,
        store=store,
        governance=_governance(),
        owner_principal_id="principal_owner",
    )
    record = create_backup(store.connect(), tmp_path)
    store.delete_approved_memory(memory.memory_id)
    restored = restore_backup(tmp_path, record.backup_id)
    assert restored.deletions_applied["memory_purge"] == 1
    copy = SQLiteStore(restored.path)
    assert copy._row("SELECT 1 FROM approved_memory WHERE memory_id = ?", (memory.memory_id,)) is None  # noqa: SLF001


# ── BUG-323 / DEC-24 step 6: restoring in place ─────────────────────────────


def test_restore_in_place_quarantines_the_damaged_database_and_switches_the_copy_in(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_kept", str(tmp_path))
    record = create_backup(store.connect(), tmp_path)
    store.create_session("sess_deleted_later", str(tmp_path))
    assert store.delete_session("sess_deleted_later")
    _damage(tmp_path)
    damaged = (tmp_path / ".raiker" / "raiker.db").read_bytes()
    assert store_health(tmp_path)["reason"] == "store_unreadable"

    result = restore_in_place(tmp_path, record.backup_id)
    assert store_health(tmp_path)["store"] == "ok"
    reopened = SQLiteStore(tmp_path)
    assert _has_session(reopened, "sess_kept")
    # The damaged file is kept, byte for byte, with a note of why.
    held = Path(result.quarantine)
    assert (held / "raiker.db").read_bytes() == damaged
    assert json.loads((held / "why.json").read_text())["restored_from"] == record.backup_id
    assert not (tmp_path / ".raiker" / "raiker.db.restoring").exists()


def test_a_backup_that_does_not_verify_leaves_the_workspace_as_it_was(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    record = create_backup(store.connect(), tmp_path)
    copy = backups_dir(tmp_path) / record.backup_id / "raiker.db"
    data = bytearray(copy.read_bytes())
    data[len(data) // 2] ^= 0xFF
    copy.write_bytes(bytes(data))
    _damage(tmp_path)
    before = (tmp_path / ".raiker" / "raiker.db").read_bytes()
    with pytest.raises(BackupError):
        restore_in_place(tmp_path, record.backup_id)
    assert (tmp_path / ".raiker" / "raiker.db").read_bytes() == before
    assert not (tmp_path / ".raiker" / "quarantine").exists()


# ── The lock screen's two routes ────────────────────────────────────────────


def _client(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    from raiker.api.app import create_app

    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    client = TestClient(create_app(root))
    token = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()["token"]
    made = client.post("/api/backups", headers={"Authorization": f"Bearer {token}"})
    assert made.status_code == 200, made.text
    return client, str(made.json()["backup_id"])


def test_the_routes_say_nothing_while_the_store_opens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, backup_id = _client(tmp_path, monkeypatch)
    listing = client.get("/api/recovery/backups")
    assert listing.status_code == 409
    assert listing.json()["detail"]["reason_code"] == "recovery_not_needed"
    restore = client.post("/api/recovery/restore", json={"backup_id": backup_id})
    assert restore.status_code == 409


def test_the_lock_screen_lists_and_restores_a_damaged_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, backup_id = _client(tmp_path, monkeypatch)
    _damage(tmp_path)
    assert client.get("/api/health").json()["reason"] == "store_unreadable"
    listing = client.get("/api/recovery/backups")
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["reason"] == "store_unreadable"
    assert body["schema_generation"] == SCHEMA_GENERATION
    row = body["backups"][0]
    assert row["backup_id"] == backup_id and row["opens_here"] is True
    assert row["key_fingerprint"] == body["key_fingerprint"]

    restored = client.post("/api/recovery/restore", json={"backup_id": backup_id})
    assert restored.status_code == 200, restored.text
    answer = restored.json()
    assert answer["quarantine"].startswith(".raiker/quarantine/")
    assert str(tmp_path) not in json.dumps(answer)
    assert client.get("/api/health").json()["store"] == "ok"
    # And the owner can sign in again.
    login = client.post("/api/auth/login", json={"username": "alice", "password": "right-pass-123"})
    assert login.status_code == 200, login.text


def test_a_newer_schema_is_offered_the_backups_this_build_can_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, backup_id = _client(tmp_path, monkeypatch)
    _make_newer(tmp_path)
    body = client.get("/api/recovery/backups").json()
    assert body["reason"] == STORE_SCHEMA_NEWER
    assert body["backups"][0]["opens_here"] is True
    assert client.post("/api/recovery/restore", json={"backup_id": backup_id}).status_code == 200
    assert client.get("/api/health").json()["store"] == "ok"


def test_a_restore_must_be_same_origin_json_from_this_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, backup_id = _client(tmp_path, monkeypatch)
    _damage(tmp_path)
    as_form = client.post(
        "/api/recovery/restore",
        content=json.dumps({"backup_id": backup_id}),
        headers={"Content-Type": "text/plain"},
    )
    # Refused before any handler runs: a body that is not JSON is not parsed.
    assert as_form.status_code in (415, 422)
    cross = client.post(
        "/api/recovery/restore",
        json={"backup_id": backup_id},
        headers={"Origin": "https://elsewhere.example"},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["reason_code"] == "recovery_cross_origin"
    client.app.state.loopback_only = False  # type: ignore[attr-defined]
    exposed = client.get("/api/recovery/backups")
    assert exposed.status_code == 403
    assert exposed.json()["detail"]["reason_code"] == "recovery_loopback_only"
    # Still damaged: none of those changed anything.
    assert client.get("/api/health").json()["reason"] == "store_unreadable"


# ── Damage found past the key check (the fifth 2026-10-05 live round) ──────


def test_damage_past_the_first_page_is_unreadable_not_a_generic_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first page that still reads, and a later page that does not."""
    from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

    from raiker.storage.stores.migration_runner import MigrationRunner

    SQLiteStore(tmp_path)
    invalidate_workspace_connections(tmp_path)

    def malformed(_self: object) -> None:
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(MigrationRunner, "_bootstrap", malformed)
    assert store_health(tmp_path)["reason"] == "store_unreadable"


def test_a_memory_error_is_the_files_when_a_scratch_store_opens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLCipher reports a page it cannot decrypt as out-of-memory under memory security."""
    from raiker.storage.stores.migration_runner import MigrationRunner

    SQLiteStore(tmp_path)
    invalidate_workspace_connections(tmp_path)

    def out_of_memory(_self: object) -> None:
        raise MemoryError

    monkeypatch.setattr(MigrationRunner, "_bootstrap", out_of_memory)
    assert store_health(tmp_path)["reason"] == "store_unreadable"
    # And when even a scratch store will not open, it really is the machine.
    monkeypatch.setattr("raiker.storage.sqlite._scratch_store_opens", lambda: False)
    assert store_health(tmp_path)["reason"] == "store_memory_lock_unavailable"
