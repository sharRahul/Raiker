"""OpenRouter routing preferences — Hermes Agent's ``provider_routing``, governed.

Two preferences an owner can act on: keep requests away from providers that
store prompts (``data_collection: deny``), and what to prefer when several
providers serve a model (``sort``). Live on 2026-10-18 ``deny`` moved
``openai/gpt-4o-mini`` from OpenAI to Azure and made ``openrouter/free`` fail
with 429, which is why nothing is denied by default: the owner chooses it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.vault_key_file import VAULT_KEY_ENV
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.connections import get_model_connection, openrouter_routing, put_model_connection
from raiker.models.contracts import ModelMessage, ModelRequest
from raiker.models.factory import ModelProviderFactory
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.storage.sqlite import SQLiteStore

OPENROUTER = "openrouter-policy-gated"
OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(VAULT_KEY_ENV, Fernet.generate_key().decode())
    ws = tmp_path / "routing"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def auth(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session(OWNER)
    return {"Authorization": f"Bearer {raw}"}


def test_preferences_need_a_saved_connection(client: TestClient, auth: dict[str, str]) -> None:
    resp = client.put(f"/api/models/{OPENROUTER}/routing", json={"data_collection": "deny"}, headers=auth)
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason_code"] == "connection_required"


def test_only_openrouter_takes_routing_preferences(client: TestClient, auth: dict[str, str]) -> None:
    resp = client.put("/api/models/openai-hosted/routing", json={"sort": "price"}, headers=auth)
    assert resp.status_code == 400


def test_only_openrouters_own_values_are_accepted(client: TestClient, auth: dict[str, str]) -> None:
    resp = client.put(f"/api/models/{OPENROUTER}/routing", json={"sort": "cheapest!"}, headers=auth)
    assert resp.status_code == 422


def test_saved_beside_the_key_without_touching_it_and_cleared_by_empty(
    client: TestClient, auth: dict[str, str], workspace: Path
) -> None:
    store = SQLiteStore(workspace)
    put_model_connection(store, OWNER, OPENROUTER, {"api_key": "sk-or-test"})
    resp = client.put(
        f"/api/models/{OPENROUTER}/routing", json={"data_collection": "deny", "sort": "price"}, headers=auth
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data_collection": "deny", "sort": "price"}
    saved = get_model_connection(store, OWNER, OPENROUTER) or {}
    assert saved["api_key"] == "sk-or-test"
    assert openrouter_routing(saved) == {"data_collection": "deny", "sort": "price"}

    view = client.get("/api/models", headers=auth).json()
    card = next(p for p in view["profiles"] if p["profile_id"] == OPENROUTER)
    assert (card["routing_data_collection"], card["routing_sort"]) == ("deny", "price")

    client.put(f"/api/models/{OPENROUTER}/routing", json={"data_collection": "", "sort": ""}, headers=auth)
    assert openrouter_routing(get_model_connection(store, OWNER, OPENROUTER)) == {}


def test_re_pasting_the_key_keeps_the_preferences(workspace: Path) -> None:
    """The key dialog does not show routing; replacing the key must not reset it."""
    store = SQLiteStore(workspace)
    put_model_connection(
        store, OWNER, OPENROUTER, {"api_key": "old", "routing_data_collection": "deny"}
    )
    client = TestClient(create_app(workspace))
    raw, _ = ApiSessionStore(workspace).create_session(OWNER)
    resp = client.put(
        f"/api/models/{OPENROUTER}/connection",
        json={"api_key": "sk-or-new"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert resp.status_code == 200, resp.text
    saved = get_model_connection(store, OWNER, OPENROUTER) or {}
    assert saved["api_key"] == "sk-or-new"
    assert saved["routing_data_collection"] == "deny"


def _chat_body(connection: dict[str, str], provider_profile: str = OPENROUTER) -> dict[str, object]:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"id": "x", "choices": [{"message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]},
        )

    profile = profile_with_model(ModelProfileRegistry.load().resolve_profile_id(provider_profile), "openai/gpt-4o-mini")
    provider = ModelProviderFactory(
        allow_hosted_provider=True,
        allow_policy_gated_provider=True,
        connection=connection,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ).create(profile)
    asyncio.run(
        provider.chat(
            ModelRequest(profile.profile_id, provider.provider, provider.model, [ModelMessage("user", "hi")], stream=False)
        )
    )
    return seen[0]


def test_the_request_carries_the_preferences_as_openrouters_provider_object() -> None:
    body = _chat_body({"api_key": "k", "routing_data_collection": "deny", "routing_sort": "throughput"})
    assert body["provider"] == {"data_collection": "deny", "sort": "throughput"}
    assert body["model"] == "openai/gpt-4o-mini"


def test_no_preference_sends_no_provider_object() -> None:
    assert "provider" not in _chat_body({"api_key": "k"})


def test_a_stray_value_never_reaches_the_request() -> None:
    body = _chat_body({"api_key": "k", "routing_data_collection": "allow-everything", "routing_sort": "x"})
    assert "provider" not in body


def test_other_providers_never_carry_openrouter_routing() -> None:
    body = _chat_body({"api_key": "k", "routing_data_collection": "deny"}, "openai-hosted")
    assert "provider" not in body
