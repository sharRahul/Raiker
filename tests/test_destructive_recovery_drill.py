"""MM-4 (beta plan) — the destructive recovery drill, against a real workspace.

Each scenario starts from a workspace with an owner, a conversation's worth of
data and one verified backup, then breaks it the way a disk, a crash or a
person does:

* the database truncated to half its size;
* one byte flipped deep inside the file, past the header page;
* the key file removed;
* the disk filling up in the middle of a write.

What must hold every time: Raiker does not quietly create a new, empty
workspace in place of the damaged one. Either it still opens with the owner's
data, or it refuses, names why, and offers the newest backup it verified.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.storage.sqlite import invalidate_workspace_connections

USER = {"username": "alice", "password": "right-pass-123"}


def _workspace(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str, str]:
    from raiker.api.app import create_app

    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    # As the owner's browser sees it: a server error is a response, not a
    # traceback in the test.
    client = TestClient(create_app(root), raise_server_exceptions=False)
    token = client.post("/api/auth/register", json=USER).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/projects", json={"name": "Kept across damage"}, headers=auth)
    assert project.status_code in (200, 201), project.text
    made = client.post("/api/backups", headers=auth)
    assert made.status_code == 200, made.text
    return client, str(made.json()["backup_id"]), token


def _database(root: Path) -> Path:
    return root / ".raiker" / "raiker.db"


def _assert_refuses_and_offers(client: TestClient, backup_id: str) -> None:
    """Unhealthy, named, and the newest verified backup on offer."""
    health = client.get("/api/health").json()
    assert health.get("store") != "ok", health
    assert health.get("reason"), health
    listing = client.get("/api/recovery/backups")
    assert listing.status_code == 200, listing.text
    rows = listing.json()["backups"]
    assert rows and rows[0]["backup_id"] == backup_id, rows


def _assert_restores_the_owner(client: TestClient, backup_id: str) -> None:
    restored = client.post("/api/recovery/restore", json={"backup_id": backup_id})
    assert restored.status_code == 200, restored.text
    assert client.get("/api/health").json()["store"] == "ok"
    login = client.post("/api/auth/login", json=USER)
    assert login.status_code == 200, login.text
    projects = client.get("/api/projects", headers={"Authorization": f"Bearer {login.json()['token']}"}).json()
    names = [p["name"] for p in (projects.get("projects", projects) if isinstance(projects, dict) else projects)]
    assert "Kept across damage" in names, projects


def _never_silently_empty(root: Path, client: TestClient) -> None:
    """No fresh owner registration may be on offer for a damaged workspace."""
    status = client.get("/api/auth/status")
    if status.status_code == 200:
        body = status.json()
        assert body.get("registration_open") is not True and body.get("needs_registration") is not True, body


def test_a_truncated_database_is_refused_and_the_newest_backup_offered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, backup_id, _ = _workspace(tmp_path, monkeypatch)
    invalidate_workspace_connections(tmp_path)
    database = _database(tmp_path)
    data = database.read_bytes()
    database.write_bytes(data[: len(data) // 2])
    _assert_refuses_and_offers(client, backup_id)
    _never_silently_empty(tmp_path, client)
    _assert_restores_the_owner(client, backup_id)
    # The damaged file was kept, not deleted.
    assert any((tmp_path / ".raiker" / "quarantine").rglob("raiker.db*"))


def test_a_byte_flipped_deep_in_the_file_is_refused_not_read_as_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, backup_id, token = _workspace(tmp_path, monkeypatch)
    invalidate_workspace_connections(tmp_path)
    database = _database(tmp_path)
    data = bytearray(database.read_bytes())
    # Past the first page, so the header still decrypts and only a page the
    # owner's data lives on is damaged. Every page from the second on is hit
    # once, so whichever page holds the projects table is among them.
    for offset in range(4096 + 100, len(data), 4096):
        data[offset] ^= 0xFF
    database.write_bytes(bytes(data))
    health = client.get("/api/health").json()
    if health.get("store") == "ok":
        # The header page still opens. Reading the damaged pages must then
        # fail loudly, never answer as though the workspace were empty.
        answer = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
        assert answer.status_code >= 400, answer.text
        assert client.get("/api/health").json().get("store") != "ok"
    _assert_refuses_and_offers(client, backup_id)
    _never_silently_empty(tmp_path, client)
    _assert_restores_the_owner(client, backup_id)


def test_a_missing_key_file_is_refused_and_no_new_key_is_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _backup_id, _ = _workspace(tmp_path, monkeypatch)
    invalidate_workspace_connections(tmp_path)
    keys = [p for p in (tmp_path / ".raiker").rglob("*") if p.is_file() and "key" in p.name.lower()]
    assert keys, "the workspace keeps its database key in a file"
    database_before = _database(tmp_path).read_bytes()
    for key in keys:
        key.unlink()
    health = client.get("/api/health").json()
    assert health.get("store") != "ok", health
    assert health.get("reason"), health
    _never_silently_empty(tmp_path, client)
    # The encrypted database was not replaced by a new, empty one under a new key.
    assert _database(tmp_path).read_bytes() == database_before


def test_a_full_disk_mid_write_fails_the_write_and_keeps_the_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _backup_id, token = _workspace(tmp_path, monkeypatch)
    auth = {"Authorization": f"Bearer {token}"}
    from raiker.storage.sqlite import SQLiteStore

    # SQLite's own disk-full path: every connection opened from here on may not
    # grow the file past its current size, so the next write that needs a new
    # page fails with SQLITE_FULL ("database or disk is full"), exactly as on a
    # full disk.
    real_open = SQLiteStore._open_keyed

    def capped(self: SQLiteStore) -> object:
        connection = real_open(self)
        pages = connection.execute("PRAGMA page_count").fetchone()[0]
        connection.execute(f"PRAGMA max_page_count = {int(pages)}")
        return connection

    monkeypatch.setattr(SQLiteStore, "_open_keyed", capped)
    invalidate_workspace_connections(tmp_path)

    created: list[str] = []
    refused = None
    for index in range(3000):
        name = f"Filling the disk {index:04d}"
        answer = client.post("/api/projects", json={"name": name}, headers=auth)
        if answer.status_code >= 400:
            refused = (name, answer)
            break
        created.append(name)
    assert refused is not None, "the capped database never filled"
    assert refused[1].status_code == 507, refused[1].text
    assert refused[1].json()["reason_code"] == "storage_full"

    # Room again, as when the owner frees disk space: the workspace opens with
    # everything that was written, and nothing half-written.
    monkeypatch.setattr(SQLiteStore, "_open_keyed", real_open)
    invalidate_workspace_connections(tmp_path)
    assert client.get("/api/health").json()["store"] == "ok"
    projects = client.get("/api/projects", headers=auth).json()
    rows = projects.get("projects", projects) if isinstance(projects, dict) else projects
    names = [p["name"] for p in rows]
    assert "Kept across damage" in names
    assert all(name in names for name in created)
    assert refused[0] not in names
