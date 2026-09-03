from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ModelProfile
from raiker.models.contracts import ProviderModelInfo
from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
)
from raiker.models.readiness import (
    ModelReadinessService,
    ModelReadinessState,
    ProviderCatalogueProbe,
)
from raiker.models.router import ModelRouter
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "model-readiness-api"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def owner_token(workspace: Path) -> str:
    token, _session = ApiSessionStore(workspace).create_session("principal_owner")
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_native_default_is_selected_but_not_ready_without_a_check(
    client: TestClient,
    owner_token: str,
    workspace: Path,
) -> None:
    """With Ollama installed, the shipped default is selected and unproven.

    BUG-270 made `configured` mean "names a model that exists here" rather than
    "names a model string", so this — the case where it does exist — states the
    detection that makes the claim true. `ready` is still False: detection finds
    a binary, and only a readiness check finds a model that answers.
    """
    SQLiteStore(workspace).save_local_runtime_presence(
        "ollama", present=True, executable="/usr/local/bin/ollama"
    )
    body = client.get("/api/models", headers=_auth(owner_token)).json()

    ollama = next(
        profile
        for profile in body["profiles"]
        if profile["profile_id"] == "ollama-local-openai-compatible"
    )
    assert ollama["selected"] is True
    assert ollama["configured"] is True
    assert ollama["provider_detected"] is True
    assert ollama["ready"] is False
    assert ollama["readiness_state"] == "not_configured"
    assert body["ready_provider_count"] == 0


def test_undetected_native_default_is_not_configured_and_not_selected(
    client: TestClient,
    owner_token: str,
) -> None:
    """BUG-270 — nothing on this host serves `gemma4:31b-cloud`, so nothing says so."""
    body = client.get("/api/models", headers=_auth(owner_token)).json()

    ollama = next(
        profile
        for profile in body["profiles"]
        if profile["profile_id"] == "ollama-local-openai-compatible"
    )
    assert ollama["selected"] is False
    assert ollama["configured"] is False
    assert ollama["provider_detected"] is False
    assert body["current_profile_id"] is None
    # The four empty llama.cpp slots carry `local-gguf…` model strings and used
    # to be counted the same way, which is the other half of "5 models set up".
    assert body["usable_provider_count"] == 0


def test_check_marks_only_the_exact_catalogue_model_ready(
    client: TestClient,
    owner_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def catalogue(_router: ModelRouter, _profile: object) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id="gemma4:31b-cloud", owned_by="library")]

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", catalogue)
    response = client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "ready"
    assert response.json()["reason_code"] == "model_ready"
    models = client.get("/api/models", headers=_auth(owner_token)).json()
    ollama = next(
        profile
        for profile in models["profiles"]
        if profile["profile_id"] == "ollama-local-openai-compatible"
    )
    assert ollama["ready"] is True
    assert models["ready_provider_count"] == 1
    listing = client.get("/api/model-readiness", headers=_auth(owner_token)).json()
    assert [(item["profile_id"], item["model"]) for item in listing["items"]] == [
        ("ollama-local-openai-compatible", "gemma4:31b-cloud")
    ]


def test_hosted_check_requires_a_bounded_execution_preflight(
    client: TestClient,
    owner_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def catalogue(_router: ModelRouter, profile: ModelProfile) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id=profile.model, owned_by="provider")]

    async def refused(_router: ModelRouter, _profile: ModelProfile) -> None:
        raise ProviderConnectionError("provider_http_error:http_400")

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", catalogue)
    monkeypatch.setattr(ModelRouter, "aprobe_model", refused)

    response = client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={"profile_id": "anthropic-hosted", "model": "claude-opus-4-8"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "unreachable"
    assert response.json()["reason_code"] == "provider_execution_refused"
    assert "credential, access, and billing" in response.json()["remediation"]


def test_check_reports_plain_language_local_model_missing(
    client: TestClient,
    owner_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty_catalogue(_router: ModelRouter, _profile: object) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id="another-model")]

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", empty_catalogue)
    response = client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={"profile_id": "ollama-local-openai-compatible", "model": "missing"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "model_missing"
    assert response.json()["reason_code"] == "local_model_missing"
    assert "Ollama" in response.json()["summary"]
    assert "missing" in response.json()["summary"]


@pytest.mark.parametrize(
    ("error", "state", "reason_code"),
    [
        (
            ProviderAuthenticationError("provider_auth_failed:http_401"),
            "authentication_failed",
            "provider_authentication_failed",
        ),
        (
            ProviderConnectionError("provider_connection_failed"),
            "runtime_stopped",
            "local_runtime_unreachable",
        ),
    ],
)
def test_provider_failures_are_stable_and_redacted(
    client: TestClient,
    owner_token: str,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    state: str,
    reason_code: str,
) -> None:
    async def failed(_router: ModelRouter, _profile: object) -> list[ProviderModelInfo]:
        raise error

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", failed)
    response = client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    assert response.status_code == 200
    assert response.json()["state"] == state
    assert response.json()["reason_code"] == reason_code
    assert "provider_error_unclassified" not in response.text
    assert "http_401" not in response.text


def test_selection_change_invalidates_profile_readiness(
    client: TestClient,
    owner_token: str,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def catalogue(_router: ModelRouter, profile: ModelProfile) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id=profile.model)]

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", catalogue)
    client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    changed = client.put(
        "/api/model-selection",
        headers=_auth(owner_token),
        json={"profile_id": "ollama-local-openai-compatible", "model": "qwen2.5"},
    )

    assert changed.status_code == 200
    rows = SQLiteStore(workspace).list_model_readiness(
        "principal_owner", "ollama-local-openai-compatible"
    )
    assert len(rows) == 1
    assert rows[0].state is ModelReadinessState.STALE
    assert rows[0].reason_code == "model_selection_changed"


def test_connection_change_invalidates_profile_readiness(
    client: TestClient,
    owner_token: str,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def catalogue(_router: ModelRouter, profile: ModelProfile) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id=profile.model)]

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", catalogue)
    client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    changed = client.put(
        "/api/models/ollama-local-openai-compatible/connection",
        headers=_auth(owner_token),
        json={"endpoint": "http://127.0.0.1:11435/v1"},
    )

    assert changed.status_code == 200, changed.text
    service = ModelReadinessService(
        SQLiteStore(workspace),
        probe=ProviderCatalogueProbe(SQLiteStore(workspace)),
    )
    readiness = service.current_selected(
        "principal_owner",
        "ollama-local-openai-compatible",
        "gemma4:31b-cloud",
    )
    assert readiness.state is ModelReadinessState.NOT_CONFIGURED
    old_rows = SQLiteStore(workspace).list_model_readiness(
        "principal_owner", "ollama-local-openai-compatible"
    )
    assert old_rows[0].state is ModelReadinessState.STALE
    assert old_rows[0].reason_code == "connection_changed"


def test_readiness_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/model-readiness").status_code == 401
    assert (
        client.post(
            "/api/model-readiness/check",
            json={"profile_id": "ollama-local-openai-compatible", "model": "x"},
        ).status_code
        == 401
    )
