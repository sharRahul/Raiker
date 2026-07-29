from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.contracts.ids import utc_now
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import default_tool_specs, validate_tool_call
from raiker.runtime.connector_ecosystem import (
    ConnectorCatalog,
    ConnectorInvoker,
    ConnectorVault,
    compile_manifest,
)
from raiker.storage.sqlite import SQLiteStore


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


def headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def manifest(method: str = "get") -> dict[str, object]:
    return {
        "openapi": "3.0.0",
        "servers": [{"url": "https://api.github.com"}],
        "paths": {
            "/repos/{owner}": {
                method: {
                    "operationId": f"{method}Repo",
                    "summary": "Repository operation",
                }
            }
        },
    }


def setup_connector(client: TestClient, auth: dict[str, str], method: str) -> None:
    assert client.post("/api/connector-store/github/install", headers=auth).status_code == 200
    assert client.put(
        "/api/connector-store/github/credentials",
        headers=auth,
        json={"values": {"access_token": "secret-token"}},
    ).status_code == 200
    assert client.post(
        "/api/connector-store/github/manifest", headers=auth, json={"manifest": manifest(method)}
    ).status_code == 200
    assert client.put(
        "/api/connector-store/github/enabled?enabled=true", headers=auth
    ).status_code == 200


def test_catalog_contains_every_named_integration() -> None:
    catalog = ConnectorCatalog().list()
    assert len(catalog) == 26
    ids = {item.connector_id for item in catalog}
    assert {"github", "google-drive", "booking", "uber", "ubereats", "olx-india"} <= ids


def test_model_exposes_separate_read_and_write_tools() -> None:
    names = {spec.name for spec in default_tool_specs()}
    assert {"connector_read", "connector_write"} <= names
    read = validate_tool_call(
        ToolCallProposal("call_read", "connector_read", {"connector_id": "github", "operation_id": "getRepo"})
    )
    write = validate_tool_call(
        ToolCallProposal("call_write", "connector_write", {"connector_id": "github", "operation_id": "postRepo"})
    )
    assert read.requires_approval is False
    assert write.requires_approval is True


def test_vault_is_fail_closed_and_ciphertext_is_not_plaintext(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(workspace)
    vault = ConnectorVault(store)
    vault.put("principal_owner", "github", {"access_token": "top-secret"})
    with store.connect() as connection:
        encrypted = bytes(
            connection.execute("SELECT encrypted_payload FROM connector_credentials").fetchone()[0]
        )
    assert b"top-secret" not in encrypted
    assert vault.get("principal_owner", "github") == {"access_token": "top-secret"}
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY")
    with pytest.raises(ValueError, match="connector_vault_key_unset"):
        vault.get("principal_owner", "github")


def test_invoker_rechecks_session_enablement_at_execution(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    with pytest.raises(ValueError, match="connector_not_enabled"):
        ConnectorInvoker(store)._require_enabled("principal_owner", "github")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO connector_installations
               (principal_id, connector_id, enabled, auth_status, installed_at, updated_at)
               VALUES ('principal_owner', 'github', 1, 'connected', 'now', 'now')"""
        )
    ConnectorInvoker(store)._require_enabled("principal_owner", "github")


def test_manifest_compilation_is_bounded_and_under_200ms() -> None:
    started = time.perf_counter()
    compiled = compile_manifest(manifest("post"))
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert compiled["operations"][0]["requires_confirmation"] is True
    assert elapsed_ms < 200


def test_manifest_compiles_bounded_operation_scoped_compensation() -> None:
    raw = manifest("post")
    paths = cast(dict[str, Any], raw["paths"])
    paths["/items/{id}"] = {
        "delete": {"operationId": "delete_item"}
    }
    operation = cast(dict[str, Any], next(iter(paths.values()))["post"])
    operation["x-raiker-compensation"] = {
        "operationId": "delete_item",
        "argumentMap": {"path.id": "response.id"},
        "deadlineSeconds": 600,
    }
    compiled = compile_manifest(raw)
    created = next(item for item in compiled["operations"] if item["method"] == "POST")
    assert created["compensation"] == {
        "operation_id": "delete_item",
        "argument_map": {"path.id": "response.id"},
        "deadline_seconds": 600,
    }


def test_enabled_connector_is_in_model_context_without_credentials(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO connector_installations
               (principal_id, connector_id, enabled, auth_status, installed_at, updated_at)
               VALUES ('principal_owner', 'github', 1, 'connected', 'now', 'now')"""
        )
    bundle = ContextGatherer().gather(
        workspace_root=workspace,
        session_id="sess_context",
        turn_id="turn_context",
        prompt_text="Use my repository",
    )
    item = next(item for item in bundle.items if item.source.source_type == "connector_status")
    assert "github: enabled, invocation=idle" in item.content
    assert "token" not in item.content.lower()


def test_store_install_auth_enable_and_uninstall(client: TestClient) -> None:
    auth = headers(client)
    listing = client.get("/api/connector-store", headers=auth)
    assert listing.status_code == 200
    assert listing.json()["count"] == 26
    setup_connector(client, auth, "get")
    connected = next(
        item for item in client.get("/api/connector-store", headers=auth).json()["connectors"]
        if item["connector_id"] == "github"
    )
    assert connected["installed"] is True
    assert connected["enabled"] is True
    assert connected["auth_status"] == "connected"
    assert "secret-token" not in json.dumps(connected)
    assert client.delete("/api/connector-store/github", headers=auth).status_code == 200


def test_get_executes_but_write_waits_for_approval_then_executes_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = headers(client)
    setup_connector(client, auth, "post")
    invoke = AsyncMock(
        return_value={
            "connector_id": "github",
            "operation_id": "postRepo",
            "method": "POST",
            "status_code": 200,
            "data": {"ok": True},
        }
    )
    monkeypatch.setattr(
        "raiker.runtime.connector_ecosystem.ConnectorInvoker.invoke", invoke
    )
    proposed = client.post(
        "/api/connector-store/github/actions",
        headers=auth,
        json={"operation_id": "postRepo", "arguments": {"path": {"owner": "acme"}}},
    )
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "approval_required"
    assert proposed.json()["executes_action"] is False
    invoke.assert_not_awaited()
    approval_id = proposed.json()["approval_id"]
    approved = client.post(
        f"/api/approvals/{approval_id}/resolve",
        headers=auth,
        json={"approve": True, "reason": "confirmed"},
    )
    assert approved.status_code == 200
    assert approved.json()["executes_action"] is True
    invoke.assert_awaited_once()
    repeated = client.post(
        f"/api/approvals/{approval_id}/resolve",
        headers=auth,
        json={"approve": True, "reason": "again"},
    )
    assert repeated.status_code == 409
    invoke.assert_awaited_once()


def test_connector_write_approval_appears_in_owning_principals_inbox(
    client: TestClient, workspace: Path
) -> None:
    """A connector-store write has no chat session, but must remain reviewable."""
    auth = headers(client)
    setup_connector(client, auth, "post")
    proposed = client.post(
        "/api/connector-store/github/actions",
        headers=auth,
        json={"operation_id": "postRepo", "arguments": {"path": {"owner": "acme"}}},
    )

    assert proposed.status_code == 200
    inbox = client.get("/api/approvals?status_filter=pending", headers=auth)

    assert inbox.status_code == 200
    assert [item["approval_id"] for item in inbox.json()] == [proposed.json()["approval_id"]]
    detail = client.get(f"/api/approvals/{proposed.json()['approval_id']}", headers=auth)
    assert detail.status_code == 200

    with SQLiteStore(workspace).connect() as connection:
        connection.execute(
            """INSERT INTO principals
               (principal_id, principal_type, display_name, role_ids, domain_scopes,
                max_runtime_mode, created_at, is_active)
               VALUES (?, 'human', ?, '[]', '[]', 'development_preview', ?, 1)""",
            ("principal_other", "Other", utc_now()),
        )
    other_token, _ = ApiSessionStore(workspace).create_session("principal_other")
    other_auth = {"Authorization": f"Bearer {other_token}"}
    other_inbox = client.get("/api/approvals?status_filter=pending", headers=other_auth)

    assert other_inbox.status_code == 200
    assert other_inbox.json() == []
    assert client.get(f"/api/approvals/{proposed.json()['approval_id']}", headers=other_auth).status_code == 404
