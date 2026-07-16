from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth import passwords
from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def ctx(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    client = TestClient(create_app(tmp_path))
    return client, tmp_path


def _register(client: TestClient, user: str) -> str:
    return client.post(
        "/api/auth/register", json={"username": user, "password": "right-pass-123"}
    ).json()["token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_id(store: SQLiteStore, username: str) -> str:
    account = store.get_account_by_username(username)
    assert account is not None
    principal = store.get_principal(str(account["principal_id"]))
    assert principal is not None
    return str(principal["delegated_by_user_id"])


def _seed_legacy_account(store: SQLiteStore, username: str) -> tuple[str, str]:
    now = utc_now()
    user_id = f"user_{username}"
    principal_id = f"principal_{username}"
    store.insert_user(User(user_id, username, None, True, now, now))
    store.insert_principal(
        principal_id=principal_id,
        principal_type="human",
        display_name=username,
        delegated_by_user_id=user_id,
        role_ids=(),
        is_active=True,
    )
    password_hash, hash_algo = passwords.hash_password("right-pass-123")
    store.upsert_account(principal_id, username, password_hash, hash_algo, now, now)
    token, _ = ApiSessionStore(store.paths.workspace_root).create_session(principal_id)
    return token, user_id


def test_sessions_isolated_between_accounts(ctx) -> None:  # type: ignore[no-untyped-def]
    client, ws = ctx
    tok_a = _register(client, "alice")
    store = SQLiteStore(ws)
    tok_b, bob_user_id = _seed_legacy_account(store, "bob")
    store.create_session("s_alice", str(ws), user_id=_user_id(store, "alice"))
    store.create_session("s_bob", str(ws), user_id=bob_user_id)

    a_ids = {s["session_id"] for s in client.get("/api/sessions", headers=_h(tok_a)).json()}
    assert "s_alice" in a_ids
    assert "s_bob" not in a_ids

    # alice cannot open bob's session
    assert client.get("/api/sessions/s_bob", headers=_h(tok_a)).status_code == 404
    # bob can open his own
    assert client.get("/api/sessions/s_bob", headers=_h(tok_b)).status_code == 200


def test_prompt_rejects_foreign_session_before_turn_creation(ctx) -> None:  # type: ignore[no-untyped-def]
    client, ws = ctx
    tok_a = _register(client, "alice")
    store = SQLiteStore(ws)
    tok_b, bob_user_id = _seed_legacy_account(store, "bob")
    store.create_session("s_bob", str(ws), user_id=bob_user_id)

    response = client.post("/api/prompts", json={"text": "hello", "session_id": "s_bob"}, headers=_h(tok_a))
    assert response.status_code == 404
    assert store.list_turns("s_bob") == []
    assert client.get("/api/sessions/s_bob", headers=_h(tok_b)).status_code == 200
