from __future__ import annotations

from pathlib import Path

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


def test_settings_isolated_per_account(client: TestClient, tmp_path: Path, seed_account) -> None:  # type: ignore[no-untyped-def]
    # One credential-backed account registers per instance, so the second
    # account is seeded directly. Settings stay per-principal because a legacy
    # or recovered-from principal can still own rows in this database.
    tok_a = _token(client, "alice")
    _, tok_b = seed_account(tmp_path, "bob")
    client.put("/api/settings", json={"settings": {"secret": "alice-only"}}, headers=_h(tok_a))
    # bob sees his own (empty) settings, not alice's
    assert client.get("/api/settings", headers=_h(tok_b)).json()["settings"] == {}


def test_settings_requires_auth(client: TestClient) -> None:
    assert client.get("/api/settings").status_code == 401


def test_speech_language_is_owner_scoped_and_constrained(client: TestClient) -> None:
    token = _token(client, "alice")
    saved = client.put(
        "/api/settings",
        json={"settings": {"general.speech_language": "fr"}},
        headers=_h(token),
    )
    assert saved.status_code == 200

    rejected = client.put(
        "/api/settings",
        json={"settings": {"general.speech_language": "unbounded"}},
        headers=_h(token),
    )

    assert rejected.status_code == 422
    assert client.get("/api/settings", headers=_h(token)).json()["settings"] == {
        "general.speech_language": "fr"
    }

    wrong_type = client.put(
        "/api/settings",
        json={"settings": {"general.speech_language": ["en"]}},
        headers=_h(token),
    )
    assert wrong_type.status_code == 422


def test_composer_approval_mode_defaults_to_manual(client: TestClient) -> None:
    token = _token(client, "alice")

    response = client.get("/api/settings/composer-approval-mode", headers=_h(token))

    assert response.status_code == 200
    assert response.json() == {"approval_mode": "manual"}


def test_composer_approval_mode_normalizes_and_preserves_unrelated_settings(client: TestClient) -> None:
    token = _token(client, "alice")
    client.put(
        "/api/settings",
        json={"settings": {"personalisation": {"theme": "dark"}, "other": True}},
        headers=_h(token),
    )

    response = client.put(
        "/api/settings/composer-approval-mode",
        json={"approval_mode": "allow_safe_only"},
        headers=_h(token),
    )

    assert response.status_code == 200
    assert response.json() == {"approval_mode": "auto"}
    settings = client.get("/api/settings", headers=_h(token)).json()["settings"]
    assert settings == {
        "personalisation": {"theme": "dark"},
        "other": True,
        "composer": {"approval_mode": "auto"},
    }


def test_composer_approval_mode_isolated_per_account(client: TestClient, tmp_path: Path, seed_account) -> None:  # type: ignore[no-untyped-def]
    token_alice = _token(client, "alice")
    _, token_bob = seed_account(tmp_path, "bob")
    client.put(
        "/api/settings/composer-approval-mode",
        json={"approval_mode": "skip"},
        headers=_h(token_alice),
    )

    response = client.get("/api/settings/composer-approval-mode", headers=_h(token_bob))

    assert response.status_code == 200
    assert response.json() == {"approval_mode": "manual"}


def test_composer_approval_mode_rejects_unknown_value(client: TestClient) -> None:
    token = _token(client, "alice")

    response = client.put(
        "/api/settings/composer-approval-mode",
        json={"approval_mode": "unbounded"},
        headers=_h(token),
    )

    assert response.status_code == 422
