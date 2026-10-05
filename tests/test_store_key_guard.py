"""DEC-24 step 6 — a missing or wrong key never makes a new, empty workspace.

Before this, ``ensure_app_key`` treated "no key file" as "first use" whatever
else was in the workspace. A key file that had gone missing beside an existing
database was replaced by a fresh key that could open nothing, written into the
very path the owner needed to restore the original to.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.auth.app_key import app_key_path, ensure_app_key
from raiker.storage.sqlite import SQLiteStore, invalidate_workspace_connections, store_health
from raiker.storage.store_errors import (
    STORE_KEY_MISSING,
    STORE_UNREADABLE,
    AppKeyMissingError,
    StoreUnavailableError,
)


def _workspace_with_data(tmp_path: Path) -> Path:
    SQLiteStore(tmp_path).connect().execute("SELECT 1")
    invalidate_workspace_connections(tmp_path)
    assert (tmp_path / ".raiker" / "raiker.db").stat().st_size > 0
    return tmp_path


def test_first_use_still_mints_a_key(tmp_path: Path) -> None:
    key = ensure_app_key(tmp_path)
    assert key and app_key_path(tmp_path).read_bytes().strip() == key


def test_a_zero_byte_database_is_still_first_use(tmp_path: Path) -> None:
    (tmp_path / ".raiker").mkdir()
    (tmp_path / ".raiker" / "raiker.db").write_bytes(b"")
    assert ensure_app_key(tmp_path)


def test_missing_key_beside_a_database_refuses_and_writes_nothing(tmp_path: Path) -> None:
    ws = _workspace_with_data(tmp_path)
    app_key_path(ws).unlink()
    before = (ws / ".raiker" / "raiker.db").read_bytes()

    with pytest.raises(AppKeyMissingError) as caught:
        ensure_app_key(ws)

    assert caught.value.reason == STORE_KEY_MISSING
    assert "app.key" in caught.value.detail
    assert not app_key_path(ws).exists()
    assert (ws / ".raiker" / "raiker.db").read_bytes() == before


def test_store_health_names_the_missing_key(tmp_path: Path) -> None:
    ws = _workspace_with_data(tmp_path)
    app_key_path(ws).unlink()
    health = store_health(ws)
    assert health["store"] == "unavailable"
    assert health["reason"] == STORE_KEY_MISSING
    assert not app_key_path(ws).exists()


def test_a_key_that_does_not_open_the_database_is_named_and_changes_nothing(
    tmp_path: Path,
) -> None:
    ws = _workspace_with_data(tmp_path)
    db = ws / ".raiker" / "raiker.db"
    before = db.read_bytes()
    # Another key in the right place: the database was made with the first.
    app_key_path(ws).unlink()
    other = tmp_path / "other"
    app_key_path(other).parent.mkdir(parents=True)
    app_key_path(ws).write_bytes(ensure_app_key(other))

    with pytest.raises(StoreUnavailableError) as caught:
        SQLiteStore(ws)

    assert caught.value.reason == STORE_UNREADABLE
    assert db.read_bytes() == before
    assert store_health(ws)["reason"] == STORE_UNREADABLE


def test_the_host_starts_and_every_read_names_the_missing_key(tmp_path: Path) -> None:
    ws = _workspace_with_data(tmp_path)
    app_key_path(ws).unlink()

    client = TestClient(create_app(workspace_root=ws), raise_server_exceptions=False)
    health = client.get("/api/health").json()
    assert health["status"] == "degraded"
    assert health["reason"] == STORE_KEY_MISSING
    assert "Put the original app.key back" in health["detail"]
    assert not app_key_path(ws).exists()
