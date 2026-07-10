"""HTTP API coverage for the user-owned model fallback sequence.

`PUT /api/model-fallback` persists the ordered list of profile ids the runtime
tries when the selected provider is unavailable; `GET /api/models` reflects it.
Writes are human gate-manager only, unknown/test profiles fail closed, and the
list is de-duplicated. Setting a sequence never enables a provider — each
candidate is still gated by provider policy at turn time.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "api_model_fallback"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    app: FastAPI = create_app(workspace)
    return TestClient(app)


@pytest.fixture
def owner_token(workspace: Path) -> str:
    raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
    return raw


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestSetAndRead:
    def test_default_sequence_is_empty(self, client: TestClient, owner_token: str) -> None:
        resp = client.get("/api/models", headers=_auth(owner_token))
        assert resp.status_code == 200
        assert resp.json()["fallback_sequence"] == []

    def test_owner_sets_sequence_and_models_reflects_it(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.put(
            "/api/model-fallback",
            json={"profile_ids": ["anthropic-hosted", "raiker-local-llama-cpp"]},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["fallback_sequence"] == [
            "anthropic-hosted",
            "raiker-local-llama-cpp",
        ]
        read = client.get("/api/models", headers=_auth(owner_token))
        assert read.json()["fallback_sequence"] == [
            "anthropic-hosted",
            "raiker-local-llama-cpp",
        ]

    def test_sequence_is_deduplicated(self, client: TestClient, owner_token: str) -> None:
        resp = client.put(
            "/api/model-fallback",
            json={"profile_ids": ["raiker-local-llama-cpp", "raiker-local-llama-cpp"]},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["fallback_sequence"] == ["raiker-local-llama-cpp"]

    def test_empty_sequence_clears(self, client: TestClient, owner_token: str) -> None:
        client.put(
            "/api/model-fallback",
            json={"profile_ids": ["anthropic-hosted"]},
            headers=_auth(owner_token),
        )
        resp = client.put(
            "/api/model-fallback", json={"profile_ids": []}, headers=_auth(owner_token)
        )
        assert resp.status_code == 200
        assert resp.json()["fallback_sequence"] == []


class TestFailClosed:
    def test_unknown_profile_rejected(self, client: TestClient, owner_token: str) -> None:
        resp = client.put(
            "/api/model-fallback",
            json={"profile_ids": ["no-such-profile"]},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "unknown_profile:no-such-profile"

    def test_test_profile_rejected(self, client: TestClient, owner_token: str) -> None:
        resp = client.put(
            "/api/model-fallback",
            json={"profile_ids": ["mock-test"]},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "test_profile_not_allowed:mock-test"

    def test_write_requires_auth(self, client: TestClient) -> None:
        resp = client.put(
            "/api/model-fallback", json={"profile_ids": ["raiker-local-llama-cpp"]}
        )
        assert resp.status_code == 401

    def test_unknown_fields_rejected(self, client: TestClient, owner_token: str) -> None:
        resp = client.put(
            "/api/model-fallback",
            json={"profile_ids": ["raiker-local-llama-cpp"], "smuggled": True},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422
