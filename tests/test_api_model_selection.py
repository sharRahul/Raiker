"""HTTP API coverage for provider model listing and model selection.

`GET /api/models/{profile_id}/provider-models` lists the models a provider
serves on explicit user demand — provider policy (gates, egress allowlist,
API key) is enforced before any network contact and failures return an honest
empty list. `PUT /api/model-selection` persists the operator's selection the
same way the CLI `/model use` does: human gate-manager only, unknown/test
profiles fail closed, placeholder profiles require a concrete model, and the
provider factory validates policy before anything is saved. `GET /api/models`
reflects the selection (`current_profile_id` + `current_model`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.vault_key_file import write_vault_key
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "api_model_selection"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    app: FastAPI = create_app(workspace)
    return TestClient(app)


@pytest.fixture
def owner_token(workspace: Path) -> str:
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return raw


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestProviderModelListing:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/models/raiker-local-llama-cpp/provider-models")
        assert resp.status_code == 401

    def test_unknown_profile_is_404(self, client: TestClient, owner_token: str) -> None:
        resp = client.get(
            "/api/models/no-such-profile/provider-models", headers=_auth(owner_token)
        )
        assert resp.status_code == 404

    def test_unreachable_local_provider_returns_empty_honestly(
        self, client: TestClient, owner_token: str
    ) -> None:
        # No llama.cpp server is running in the test environment: the listing
        # must say so rather than fabricate model names.
        resp = client.get(
            "/api/models/raiker-local-llama-cpp/provider-models", headers=_auth(owner_token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "unavailable"
        assert body["models"] == []

    def test_hosted_provider_is_policy_denied_before_any_network(
        self, client: TestClient, owner_token: str
    ) -> None:
        # The hosted gate is disabled by default: the provider factory denies the
        # listing before a connection is even attempted.
        resp = client.get(
            "/api/models/anthropic-hosted/provider-models", headers=_auth(owner_token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "policy_denied"
        assert body["models"] == []
        assert body["reason_code"]


class TestSetModelSelection:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.put(
            "/api/model-selection", json={"profile_id": "raiker-local-llama-cpp"}
        )
        assert resp.status_code == 401

    def test_unknown_profile_fails_closed(self, client: TestClient, owner_token: str) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "no-such-profile"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "unknown_profile:no-such-profile"

    def test_placeholder_profile_requires_concrete_model(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "ollama-local-openai-compatible"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        assert (
            resp.json()["detail"]["reason_code"]
            == "model_required_for_profile:ollama-local-openai-compatible"
        )

    def test_hosted_provider_fails_closed_when_gate_disabled(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "anthropic-hosted"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"]

    def test_unknown_fields_rejected(self, client: TestClient, owner_token: str) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "raiker-local-llama-cpp", "smuggled": True},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422

    def test_select_local_profile_and_models_reflects_it(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "raiker-local-llama-cpp"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "ok": True,
            "profile_id": "raiker-local-llama-cpp",
            "model": "local-gguf",
        }
        read = client.get("/api/models", headers=_auth(owner_token)).json()
        assert read["current_profile_id"] == "raiker-local-llama-cpp"
        assert read["current_model"] == "local-gguf"
        selected = [p for p in read["profiles"] if p["selected"]]
        assert [p["profile_id"] for p in selected] == ["raiker-local-llama-cpp"]

    def test_select_placeholder_profile_with_explicit_model(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "ollama-local-openai-compatible", "model": "qwen2.5"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["model"] == "qwen2.5"
        read = client.get("/api/models", headers=_auth(owner_token)).json()
        assert read["current_profile_id"] == "ollama-local-openai-compatible"
        assert read["current_model"] == "qwen2.5"
        # The selected card shows the concrete model the runtime will bind,
        # not the profile's placeholder.
        selected = next(p for p in read["profiles"] if p["selected"])
        assert selected["model"] == "qwen2.5"

    def test_placeholder_model_string_rejected(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.put(
            "/api/model-selection",
            json={"profile_id": "ollama-local-openai-compatible", "model": "<model>"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"].startswith("model_required_for_profile")


def test_model_connection_is_encrypted_and_principal_scoped(
    client: TestClient, workspace: Path, owner_token: str
) -> None:
    write_vault_key(workspace, Fernet.generate_key().decode())
    response = client.put(
        "/api/models/generic-openai-compatible/connection",
        headers=_auth(owner_token),
        json={"endpoint": "http://127.0.0.1:9000/v1", "api_key": "instance-secret"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "connection_configured": True}
    profiles = client.get("/api/models", headers=_auth(owner_token)).json()["profiles"]
    generic = next(item for item in profiles if item["profile_id"] == "generic-openai-compatible")
    assert generic["connection_configured"] is True
    with SQLiteStore(workspace).connect() as connection:
        row = connection.execute(
            "SELECT encrypted_payload FROM connector_credentials WHERE principal_id=? AND connector_id=?",
            ("principal_owner", "model:generic-openai-compatible"),
        ).fetchone()
    assert row is not None and b"instance-secret" not in bytes(row["encrypted_payload"])
