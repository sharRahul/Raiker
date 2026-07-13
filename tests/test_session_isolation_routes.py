from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
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
    pid = store.get_account_by_username(username)["principal_id"]
    return str(store.get_principal(pid)["delegated_by_user_id"])


def test_sessions_isolated_between_accounts(ctx) -> None:  # type: ignore[no-untyped-def]
    client, ws = ctx
    tok_a = _register(client, "alice")
    tok_b = _register(client, "bob")
    store = SQLiteStore(ws)
    store.create_session("s_alice", str(ws), user_id=_user_id(store, "alice"))
    store.create_session("s_bob", str(ws), user_id=_user_id(store, "bob"))

    a_ids = {s["session_id"] for s in client.get("/api/sessions", headers=_h(tok_a)).json()}
    assert "s_alice" in a_ids
    assert "s_bob" not in a_ids

    # alice cannot open bob's session
    assert client.get("/api/sessions/s_bob", headers=_h(tok_a)).status_code == 404
    # bob can open his own
    assert client.get("/api/sessions/s_bob", headers=_h(tok_b)).status_code == 200
