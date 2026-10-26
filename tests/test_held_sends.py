"""Undo windows (Quiet UI 06, QUI-F19).

An approved connector write is held before it is sent. Undo inside the window,
or Stop on its conversation, takes it back and nothing is sent; once the window
has closed the send happens once and Undo answers that there is nothing held.
The resumed turn is told it was not sent, so the model does not claim it was.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.runtime import held_sends
from raiker.runtime.turn_suspension import SEND_UNDONE, approval_outcome
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


_MANIFEST = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.github.com"}],
    "paths": {"/repos/{owner}": {"post": {"operationId": "postRepo", "summary": "Send"}}},
}


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _proposed(client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, AsyncMock]:
    assert client.post("/api/connector-store/github/install", headers=auth).status_code == 200
    client.put("/api/connector-store/github/credentials", headers=auth, json={"values": {"access_token": "t"}})
    client.post("/api/connector-store/github/manifest", headers=auth, json={"manifest": _MANIFEST})
    client.put("/api/connector-store/github/enabled?enabled=true", headers=auth)
    invoke = AsyncMock(return_value={"connector_id": "github", "operation_id": "postRepo", "method": "POST", "status_code": 200, "data": {}})
    monkeypatch.setattr("raiker.runtime.connector_ecosystem.ConnectorInvoker.invoke", invoke)
    proposed = client.post(
        "/api/connector-store/github/actions", headers=auth, json={"operation_id": "postRepo", "arguments": {}}
    )
    assert proposed.status_code == 200, proposed.text
    return str(proposed.json()["approval_id"]), invoke


def _intent_status(workspace: Path, approval_id: str) -> str:
    row = SQLiteStore(workspace)._row("SELECT status FROM connector_write_intents WHERE approval_id = ?", (approval_id,))
    assert row is not None
    return str(row["status"])


def test_after_the_window_the_send_happens_once_and_undo_is_too_late(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = _auth(client)
    approval_id, invoke = _proposed(client, auth, monkeypatch)
    resolved = client.post(f"/api/approvals/{approval_id}/resolve", headers=auth, json={"approve": True, "reason": "ok"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "executed"
    invoke.assert_awaited_once()
    assert _intent_status(workspace, approval_id) == "executed"
    late = client.post(f"/api/approvals/{approval_id}/undo-send", headers=auth)
    assert late.status_code == 409
    assert "send_not_held" in late.text


def test_undo_inside_the_window_sends_nothing(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("raiker.runtime.held_sends.HOLD_SECONDS", 3.0)
    auth = _auth(client)
    approval_id, invoke = _proposed(client, auth, monkeypatch)
    answers: dict[str, object] = {}

    def approve() -> None:
        answers["resolve"] = client.post(
            f"/api/approvals/{approval_id}/resolve", headers=auth, json={"approve": True, "reason": "ok"}
        )

    worker = threading.Thread(target=approve)
    worker.start()
    deadline = time.monotonic() + 2.5
    while _intent_status(workspace, approval_id) != "held" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _intent_status(workspace, approval_id) == "held"
    undone = client.post(f"/api/approvals/{approval_id}/undo-send", headers=auth)
    assert undone.status_code == 200, undone.text
    worker.join(timeout=10)
    resolved = answers["resolve"]
    assert resolved.status_code == 200, resolved.text  # type: ignore[attr-defined]
    body = resolved.json()  # type: ignore[attr-defined]
    assert body["status"] == "undone"
    assert body["executes_action"] is False
    assert body["not_executed_reason"] == SEND_UNDONE
    invoke.assert_not_awaited()
    assert _intent_status(workspace, approval_id) == "undone"


def test_stop_on_the_conversation_takes_back_a_held_send(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    principal = str(store._row("SELECT principal_id FROM instance_account_guard")["principal_id"])  # type: ignore[index]
    store._execute(
        "INSERT INTO tool_actions (action_id, session_id, tool_name, arguments_json, risk_level, status, proposed_at) "
        "VALUES ('act_hold', 'sess_hold', 'connector_write', '{}', 'high', 'approval_required', '2026-10-26T00:00:00Z')"
    )
    store._execute(
        "INSERT INTO approvals (approval_id, action_id, status, created_at) VALUES ('appr_hold', 'act_hold', 'approved', '2026-10-26T00:00:00Z')"
    )
    store._execute(
        "INSERT INTO connector_write_intents (intent_id, approval_id, principal_id, connector_id, operation_id, arguments_json, status, created_at) "
        "VALUES ('cwi_hold', 'appr_hold', ?, 'github', 'postRepo', '{}', 'pending_approval', '2026-10-26T00:00:00Z')",
        (principal,),
    )
    assert held_sends.hold(store, "cwi_hold", seconds=5) is not None
    store.request_turn_stop("sess_hold", principal, reason="owner pressed Stop")
    assert _intent_status(workspace, "appr_hold") == "undone"
    assert asyncio.run(held_sends.wait_for_release(store, "cwi_hold", seconds=0.1)) is False


def test_a_consumed_intent_cannot_be_held_again(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    assert held_sends.hold(store, "cwi_missing") is None


def test_the_resumed_turn_is_told_nothing_was_sent() -> None:
    outcome = approval_outcome(approved=True, executed=False, capability="connector_write", reason_code=SEND_UNDONE)
    assert outcome["executed"] is False
    assert "nothing was sent" in str(outcome["note"])
