"""Each work surface remembers the model the owner chose for it.

Raiker already had two scopes: one global default, and a model captured on an
individual task. Neither answers "Chat should use the small local model and
Build should use the big one" — the per-turn picker forgot the choice on every
reload, so both surfaces fell back to the same global default.

A surface default is a *preference*, not an authority: it only decides what the
picker starts on. The turn still carries an explicit profile and model, and the
readiness gate still judges that exact pair, so nothing here can put work on a
model that was never proven.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner

# Imported rather than restated: MODEL-02's whole failure was that this list
# lived in one module and the product model lived in another, so `design` was
# missing from the first for as long as nobody compared them.
from raiker.models.decision import SURFACES
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "surface-models"
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


def test_each_surface_keeps_its_own_default(workspace: Path) -> None:
    store = SQLiteStore(workspace)

    store.save_surface_model_default(
        "principal_owner", "chat", "ollama-local-openai-compatible", "gemma4:31b-cloud"
    )
    store.save_surface_model_default(
        "principal_owner", "build", "anthropic-hosted", "claude-haiku-4-5-20251001"
    )

    assert store.load_surface_model_default("principal_owner", "chat") == (
        "ollama-local-openai-compatible",
        "gemma4:31b-cloud",
    )
    assert store.load_surface_model_default("principal_owner", "build") == (
        "anthropic-hosted",
        "claude-haiku-4-5-20251001",
    )
    # An unset surface has no opinion; the caller falls back to the global model.
    assert store.load_surface_model_default("principal_owner", "tasks") is None


def test_a_default_is_replaced_not_accumulated(workspace: Path) -> None:
    store = SQLiteStore(workspace)

    store.save_surface_model_default("principal_owner", "chat", "a-profile", "a-model")
    store.save_surface_model_default("principal_owner", "chat", "b-profile", "b-model")

    assert store.load_surface_model_default("principal_owner", "chat") == (
        "b-profile",
        "b-model",
    )
    assert list(store.list_surface_model_defaults("principal_owner")) == [
        ("chat", "b-profile", "b-model")
    ]


def test_clearing_a_default_returns_the_surface_to_the_global_model(
    workspace: Path,
) -> None:
    store = SQLiteStore(workspace)
    store.save_surface_model_default("principal_owner", "chat", "a-profile", "a-model")

    store.clear_surface_model_default("principal_owner", "chat")

    assert store.load_surface_model_default("principal_owner", "chat") is None


def test_defaults_are_owner_scoped(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    store.save_surface_model_default("principal_owner", "chat", "a-profile", "a-model")

    assert store.load_surface_model_default("principal_other", "chat") is None


def test_api_round_trips_every_surface(client: TestClient, owner_token: str) -> None:
    empty = client.get("/api/surface-models", headers=_auth(owner_token))
    assert empty.status_code == 200
    assert empty.json() == {"surfaces": {}}

    saved = client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={
            "surface": "build",
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )
    assert saved.status_code == 200

    body = client.get("/api/surface-models", headers=_auth(owner_token)).json()
    assert body["surfaces"]["build"] == {
        "profile_id": "ollama-local-openai-compatible",
        "model": "gemma4:31b-cloud",
    }


def test_api_rejects_a_surface_raiker_does_not_have(
    client: TestClient, owner_token: str
) -> None:
    response = client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={
            "surface": "not-a-surface",
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "unknown_surface"


def test_api_rejects_a_profile_that_does_not_exist(
    client: TestClient, owner_token: str
) -> None:
    response = client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={"surface": "chat", "profile_id": "nope", "model": "x"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"].startswith("unknown_profile")


def test_api_clears_a_default_with_an_empty_profile(
    client: TestClient, owner_token: str
) -> None:
    client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={
            "surface": "chat",
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    cleared = client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={"surface": "chat", "profile_id": "", "model": ""},
    )

    assert cleared.status_code == 200
    assert client.get("/api/surface-models", headers=_auth(owner_token)).json() == {
        "surfaces": {}
    }


def test_design_is_one_of_the_surfaces_that_may_hold_a_default() -> None:
    """MODEL-02 — the product model is Chat | Build | Design.

    Two of the three had explicit surface state and the third silently borrowed
    the global default, so an owner who put Chat on a small local model had
    their image prompts follow it there. The list is asserted whole rather than
    only for the entry that was missing: the point is that it matches the Work
    modes, and a future surface added to one place and not the other is the
    same defect again.
    """
    assert SURFACES == ("chat", "build", "design", "tasks", "schedule")


def test_design_round_trips_through_the_api(client: TestClient, owner_token: str) -> None:
    saved = client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={
            "surface": "design",
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )
    assert saved.status_code == 200

    body = client.get("/api/surface-models", headers=_auth(owner_token)).json()
    assert body["surfaces"]["design"] == {
        "profile_id": "ollama-local-openai-compatible",
        "model": "gemma4:31b-cloud",
    }

    # And it is genuinely its own scope, not an alias for the global one: Chat
    # keeps no opinion while Design holds one.
    assert "chat" not in body["surfaces"]

    cleared = client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={"surface": "design", "profile_id": "", "model": ""},
    )
    assert cleared.status_code == 200
    assert client.get("/api/surface-models", headers=_auth(owner_token)).json() == {
        "surfaces": {}
    }


def test_a_surface_default_never_grants_readiness(
    client: TestClient, owner_token: str
) -> None:
    """A preference decides where the picker starts, never whether work may run."""
    client.put(
        "/api/surface-models",
        headers=_auth(owner_token),
        json={
            "surface": "chat",
            "profile_id": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    refused = client.post(
        "/api/prompts",
        headers=_auth(owner_token),
        json={
            "text": "hello",
            "model_profile": "ollama-local-openai-compatible",
            "model": "gemma4:31b-cloud",
        },
    )

    assert refused.status_code == 409
    assert refused.json()["detail"]["reason_code"] == "model_not_ready"
