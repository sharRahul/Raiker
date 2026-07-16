from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore


@pytest.fixture()
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _register(client: TestClient, user: str = "alice") -> str:
    return client.post(
        "/api/auth/register", json={"username": user, "password": "right-pass-123"}
    ).json()["token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_and_revoke_device_sessions(client: TestClient, tmp_path) -> None:  # type: ignore[no-untyped-def]
    token = _register(client)
    # a second device session
    pid = ApiSessionStore(tmp_path).list_sessions()[0]["principal_id"]
    other_tok, other = ApiSessionStore(tmp_path).create_session(pid, scope="control")
    listing = client.get("/api/auth/sessions", headers=_h(token)).json()
    ids = {r["session_id"]: r for r in listing}
    assert len(ids) >= 2
    assert any(r["current"] for r in listing)
    # revoke the other session
    resp = client.post(f"/api/auth/sessions/{other.session_id}/revoke", headers=_h(token))
    assert resp.status_code == 200
    assert client.get("/api/sessions", headers=_h(other_tok)).status_code == 401


def test_cannot_revoke_another_accounts_session(client: TestClient, tmp_path, seed_account) -> None:  # type: ignore[no-untyped-def]
    # Registration accepts one account per instance, so bob is seeded directly.
    # A second principal is still reachable here (CLI bootstrap, or the
    # deactivated owner a recovery leaves behind), so `owns_session` still has
    # to hold.
    tok_a = _register(client, "alice")
    _, bob_token = seed_account(tmp_path, "bob")
    bob_session = ApiSessionStore(tmp_path).get_by_token(bob_token)
    assert bob_session is not None
    # alice cannot revoke bob's real session ...
    assert (
        client.post(f"/api/auth/sessions/{bob_session.session_id}/revoke", headers=_h(tok_a)).status_code
        == 404
    )
    assert client.get("/api/sessions", headers=_h(bob_token)).status_code == 200
    # ... nor a made-up one
    assert client.post("/api/auth/sessions/api_ses_bogus/revoke", headers=_h(tok_a)).status_code == 404


def test_delete_account_requires_elevation_and_purges(client: TestClient) -> None:
    token = _register(client)
    # plain session cannot delete
    assert client.delete("/api/account", headers=_h(token)).status_code == 403
    elevated = client.post(
        "/api/auth/elevate", json={"password": "right-pass-123"}, headers=_h(token)
    ).json()["token"]
    assert client.delete("/api/account", headers=_h(elevated)).status_code == 200
    # account is gone: cannot log in
    assert (
        client.post("/api/auth/login", json={"username": "alice", "password": "right-pass-123"}).status_code
        == 401
    )
