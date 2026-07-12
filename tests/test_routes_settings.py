from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _token(client: TestClient, user: str, pw: str = "right-pass-123") -> str:
    return client.post("/api/auth/register", json={"username": user, "password": pw}).json()["token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_settings_roundtrip(client: TestClient) -> None:
    token = _token(client, "alice")
    empty = client.get("/api/settings", headers=_h(token))
    assert empty.status_code == 200
    assert empty.json()["settings"] == {}
    assert empty.json()["status"]["vault"] == "missing"
    put = client.put(
        "/api/settings", json={"settings": {"personalisation": {"theme": "dark"}}}, headers=_h(token)
    )
    assert put.status_code == 200
    got = client.get("/api/settings", headers=_h(token)).json()
    assert got["settings"]["personalisation"]["theme"] == "dark"


def test_settings_isolated_per_account(client: TestClient) -> None:
    tok_a = _token(client, "alice")
    tok_b = _token(client, "bob")
    client.put("/api/settings", json={"settings": {"secret": "alice-only"}}, headers=_h(tok_a))
    # bob sees his own (empty) settings, not alice's
    assert client.get("/api/settings", headers=_h(tok_b)).json()["settings"] == {}


def test_settings_requires_auth(client: TestClient) -> None:
    assert client.get("/api/settings").status_code == 401
