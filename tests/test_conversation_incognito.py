"""RU-11: an owner can withhold memory from one saved conversation."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.goals.store import session_memory_withheld
from raiker.storage.sqlite import SQLiteStore


def test_conversation_incognito_is_durable_isolated_and_does_not_release_profile_withholding(
    tmp_path: Path, seed_account: Any,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bootstrap_owner("bootstrap", "Bootstrap", workspace_root=workspace)
    owner, token = seed_account(workspace, "owner")
    _, other_token = seed_account(workspace, "other")
    headers = {"Authorization": f"Bearer {token}"}
    client = TestClient(create_app(workspace))
    response = client.post("/api/sessions/incognito", headers=headers)
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]
    store = SQLiteStore(workspace)
    assert session_memory_withheld(store, session_id) == "incognito"
    disclosure = ContextGatherer._memory_disclosure(store, owner, session_id)
    assert disclosure["incognito"] is True
    assert disclosure["effective_mode"] == "off"
    assert client.get(f"/api/sessions/{session_id}", headers=headers).json()["session"]["incognito"] is True
    url = f"/api/sessions/{session_id}/incognito"
    denied = client.put(url, json={"incognito": False}, headers={"Authorization": f"Bearer {other_token}"})
    assert denied.status_code == 403
    assert session_memory_withheld(store, session_id) == "incognito"
    assert client.put(url, json={"incognito": False, "extra": True}, headers=headers).status_code == 422
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO session_memory_withholds (session_id, owner_principal_id, reason, created_at) VALUES (?, ?, ?, ?)",
            (session_id, owner, "execution_profile", "2026-11-27T00:00:00Z"),
        )
    assert client.put(url, json={"incognito": False}, headers=headers).status_code == 200
    assert session_memory_withheld(store, session_id) == "execution_profile"
    saved = store.load_session(session_id)
    assert saved is not None and saved["incognito"] == 0
    ordinary = "ordinary"
    store.create_session(ordinary, str(workspace), user_id=saved["user_id"])
    assert session_memory_withheld(store, ordinary) == ""
    assert not store.is_memory_incognito(owner)
