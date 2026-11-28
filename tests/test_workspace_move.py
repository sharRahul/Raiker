"""RU-17 — moving Raiker to another machine with a passphrase-sealed file."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.auth.accounts import AccountService
from raiker.auth.app_key import app_fernet, ensure_app_key
from raiker.auth.vault_key_file import ensure_vault_key
from raiker.runtime.connector_ecosystem import ConnectorVault
from raiker.storage.move import MoveError, export_move, import_move, seal, unseal
from raiker.storage.sqlite import SQLiteStore

PASS = "correct horse battery"


def _old_machine(root: Path) -> tuple[SQLiteStore, str, bytes]:
    store = SQLiteStore(root)
    user = AccountService(root).register("owner", "a long password here")
    store.create_session("sess_moved", str(root))
    ensure_vault_key(root)
    ConnectorVault(store).put(user, "model:anthropic", {"api_key": "sk-secret-value"})
    token = app_fernet(root).encrypt(b"sealed with the old key")
    (root / ".raiker" / "hooks.json").write_text('{"hooks": []}', encoding="utf-8")
    return store, user, token


def test_seal_refuses_a_wrong_passphrase_and_a_changed_byte() -> None:
    blob = seal(b"payload", PASS)
    assert unseal(blob, PASS) == b"payload"
    with pytest.raises(MoveError) as wrong:
        unseal(blob, PASS + "x")
    assert wrong.value.reason == "move_passphrase_or_file_wrong"
    changed = bytearray(blob)
    changed[-1] ^= 1
    with pytest.raises(MoveError):
        unseal(bytes(changed), PASS)
    with pytest.raises(MoveError) as short:
        seal(b"x", "short")
    assert short.value.reason == "move_passphrase_short"


def test_a_move_carries_the_account_and_data_and_asks_for_keys_again(tmp_path: Path) -> None:
    old, new, out = tmp_path / "old", tmp_path / "new", tmp_path / "out"
    store, _user, _token = _old_machine(old)
    exported = export_move(store.connect(), old, out, PASS)
    raw = exported.path.read_bytes()
    assert b"sess_moved" not in raw and b"sk-secret" not in raw
    assert not list((old / ".raiker" / "backups").glob("*/raiker.db")), "the snapshot is not left as a backup"

    SQLiteStore(new).create_session("sess_blank", str(new))  # a fresh install has an empty store
    new_key = ensure_app_key(new)
    # A worker's open connection holds the file on Windows; the import must
    # not need to move it (found in the live run).
    from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

    holder = sqlite3.connect(str(new / ".raiker" / "raiker.db"))
    try:
        result = import_move(new, raw, PASS)
    finally:
        holder.close()
    assert result.keys_removed == 1
    assert result.counts["sessions"] >= 1
    assert ensure_app_key(new) == new_key, "the new machine keeps its own key"
    moved = SQLiteStore(new)
    assert AccountService(new)._store.list_accounts()  # noqa: SLF001
    assert moved.connect().execute("SELECT count(*) FROM sessions WHERE session_id='sess_moved'").fetchone()[0] == 1
    assert moved.connect().execute("SELECT count(*) FROM connector_credentials").fetchone()[0] == 0
    assert (new / ".raiker" / "hooks.json").read_text(encoding="utf-8") == '{"hooks": []}'
    assert list((new / ".raiker" / "quarantine").glob("before-move-*/raiker.db"))


def test_an_import_refuses_a_workspace_with_an_account(tmp_path: Path) -> None:
    old, new = tmp_path / "old", tmp_path / "new"
    store, _user, _token = _old_machine(old)
    raw = export_move(store.connect(), old, tmp_path / "out", PASS).path.read_bytes()
    AccountService(new).register("someone", "another long password")
    with pytest.raises(MoveError) as refused:
        import_move(new, raw, PASS)
    assert refused.value.reason == "move_workspace_in_use"


def test_a_wrong_passphrase_changes_nothing(tmp_path: Path) -> None:
    old, new = tmp_path / "old", tmp_path / "new"
    store, _user, _token = _old_machine(old)
    raw = export_move(store.connect(), old, tmp_path / "out", PASS).path.read_bytes()
    SQLiteStore(new).create_session("sess_blank", str(new))
    with pytest.raises(MoveError):
        import_move(new, raw, "not the passphrase at all")
    assert SQLiteStore(new).connect().execute("SELECT count(*) FROM sessions WHERE session_id='sess_blank'").fetchone()[0] == 1


def test_the_routes_export_with_step_up_and_import_only_on_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app
    from raiker.api.sessions import ApiSessionStore

    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    old, new = tmp_path / "old", tmp_path / "new"
    client = TestClient(create_app(old))
    token = client.post("/api/auth/register", json={"username": "alice", "password": "right-pass-123"}).json()["token"]
    plain_session = {"Authorization": f"Bearer {token}"}
    refused = client.post("/api/move/export", json={"passphrase": PASS}, headers=plain_session)
    assert refused.status_code == 403 and refused.json()["detail"]["reason_code"] == "move_requires_step_up"
    principal = AccountService(old)._store.list_accounts()[0]["principal_id"]  # noqa: SLF001
    elevated, _ = ApiSessionStore(old).create_session(principal, scope="elevated", expires_in_seconds=60)
    made = client.post("/api/move/export", json={"passphrase": PASS}, headers={"Authorization": f"Bearer {elevated}"})
    assert made.status_code == 200, made.text
    assert "raikermove" in made.headers["content-disposition"]

    fresh = TestClient(create_app(new))
    assert fresh.get("/api/move/status").json()["can_import"] is True
    wrong_type = fresh.post("/api/move/import", content=made.content, headers={"x-raiker-move-passphrase": PASS})
    assert wrong_type.status_code == 415
    opened = fresh.post(
        "/api/move/import",
        content=made.content,
        headers={"content-type": "application/octet-stream", "x-raiker-move-passphrase": PASS},
    )
    assert opened.status_code == 200, opened.text
    assert fresh.get("/api/move/status").json()["can_import"] is False
    signed_in = fresh.post("/api/auth/login", json={"username": "alice", "password": "right-pass-123"})
    assert signed_in.status_code == 200
    again = fresh.post(
        "/api/move/import",
        content=made.content,
        headers={"content-type": "application/octet-stream", "x-raiker-move-passphrase": PASS},
    )
    assert again.status_code == 409
