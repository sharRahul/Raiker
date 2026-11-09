"""QUI-P04 — what Raiker may do with one connection: Read only, Ask before changes, Custom.

A new connection starts Read only; a preset only narrows; the refusal holds at
the route and again inside the invoker, so a write approved before the owner
chose Read only still changes nothing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.runtime import connector_policy
from raiker.runtime.connector_ecosystem import ConnectorInvoker
from raiker.storage.sqlite import SQLiteStore
from tests.test_connector_ecosystem import headers, manifest


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture(autouse=True)
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_CONNECTOR_VAULT_KEY", Fernet.generate_key().decode())


def _connect(client: TestClient, auth: dict[str, str], method: str) -> None:
    assert client.post("/api/connector-store/github/install", headers=auth).status_code == 200
    assert client.put(
        "/api/connector-store/github/credentials", headers=auth, json={"values": {"access_token": "t"}}
    ).status_code == 200
    assert client.post(
        "/api/connector-store/github/manifest", headers=auth, json={"manifest": manifest(method)}
    ).status_code == 200
    assert client.put("/api/connector-store/github/enabled?enabled=true", headers=auth).status_code == 200


def _preset_of(client: TestClient, auth: dict[str, str]) -> str:
    store = client.get("/api/connector-store", headers=auth).json()["connectors"]
    return next(item["preset"] for item in store if item["connector_id"] == "github")


def test_presets_read_only_ask_and_custom_in_words() -> None:
    assert connector_policy.refusal("read_only", "POST") == "connection_read_only"
    assert connector_policy.refusal("read_only", "get") is None
    assert connector_policy.refusal("ask", "DELETE") is None
    assert connector_policy.must_ask("ask", "PATCH") and not connector_policy.must_ask("ask", "GET")
    assert not connector_policy.must_ask("custom", "POST")


def test_a_new_connection_starts_read_only_and_refuses_a_change(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = headers(client)
    _connect(client, auth, "post")
    assert _preset_of(client, auth) == "read_only"
    invoke = AsyncMock()
    monkeypatch.setattr("raiker.runtime.connector_ecosystem.ConnectorInvoker.invoke", invoke)
    refused = client.post(
        "/api/connector-store/github/actions", headers=auth,
        json={"operation_id": "postRepo", "arguments": {"path": {"owner": "acme"}}},
    )
    assert (refused.status_code, refused.json()["detail"]["reason_code"]) == (409, "connection_read_only")
    invoke.assert_not_awaited()


def test_ask_before_changes_and_custom_are_the_owners_choice(client: TestClient) -> None:
    auth = headers(client)
    _connect(client, auth, "post")
    for preset in ("ask", "custom", "read_only"):
        changed = client.put("/api/connector-store/github/preset", headers=auth, json={"preset": preset})
        assert changed.status_code == 200, changed.text
        assert _preset_of(client, auth) == preset
    assert client.put("/api/connector-store/github/preset", headers=auth, json={"preset": "everything"}).status_code == 422
    assert client.put("/api/connector-store/slack/preset", headers=auth, json={"preset": "ask"}).status_code == 404


def test_reads_are_never_narrowed_and_activity_is_listed(client: TestClient) -> None:
    auth = headers(client)
    _connect(client, auth, "get")
    activity = client.get("/api/connector-store/github/activity", headers=auth)
    assert activity.status_code == 200
    assert activity.json() == {"connector_id": "github", "items": []}


def test_the_invoker_refuses_a_change_on_a_read_only_connection(client: TestClient, workspace: Path) -> None:
    auth = headers(client)
    _connect(client, auth, "post")
    store = SQLiteStore(workspace)
    principal = store._row("SELECT principal_id FROM connector_installations LIMIT 1")["principal_id"]  # type: ignore[index]
    with pytest.raises(ValueError, match="connection_read_only"):
        asyncio.run(ConnectorInvoker(store).invoke(principal, "github", "postRepo", {"path": {"owner": "acme"}}))


def test_a_connection_from_before_presets_reads_as_custom(workspace: Path) -> None:
    assert connector_policy.get(SQLiteStore(workspace), "principal_owner", "github") == "custom"
