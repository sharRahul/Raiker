"""A new app on the same disk workspace must not become a first-run account.

Exercises app shutdown/startup plus the real encrypted store. This catches
startup reseeding/resetting owner state and loss of account-scoped controls.
No live model or external service is needed to persist conversation records.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.contracts.ids import utc_now
from raiker.memory.candidates import governed_memory_status
from raiker.models.session_state import ModelSessionState
from raiker.storage.sqlite import SQLiteStore


@pytest.mark.parametrize(
    ("gate", "mode", "enabled"),
    [("disabled", "ask", False), ("enabled_runtime", "allow", True)],
)
def test_same_workspace_restart_preserves_owner_state(
    tmp_path: Path, gate: str, mode: str, enabled: bool
) -> None:
    with TestClient(create_app(tmp_path)) as first:
        registration = first.post(
            "/api/auth/register", json={"username": "restart-owner", "password": "restart-test-pass"}
        )
        assert registration.status_code == 200, registration.text
        owner = registration.json()["principal_id"]
        headers = {"Authorization": f"Bearer {registration.json()['token']}"}
        cookies = dict(first.cookies)
        setup = first.put(
            "/api/setup", headers=headers,
            json={"status": "complete", "stage": "finish", "privacy_mode": "local_first",
                  "selected_profile_id": "ollama-local", "selected_model": "restart-model"},
        )
        assert setup.status_code == 200, setup.text
        settings = first.put(
            "/api/settings", headers=headers, json={"settings": {"personalisation": {"theme": "dark"}}}
        )
        assert settings.status_code == 200, settings.text
        store = SQLiteStore(tmp_path)
        record = {"capability": "memory_write_execution", "state": gate,
                  "decision_mode": mode, "created_at": utc_now(), "updated_at": utc_now()}
        store.upsert_principal_capability_gate_state(owner, record)
        store.upsert_principal_capability_decision_mode(owner, record)
        store.save_configured_model(owner, "ollama-local", "restart-model")
        store.save_principal_model_state(
            owner, ModelSessionState("session-restart", "ollama-local", "restart-model")
        )
        owner_user_id = store.principal_user_id(owner)
        assert owner_user_id is not None
        store.create_session("session-restart", str(tmp_path), user_id=owner_user_id)
        store.insert_turn("session-restart", "turn-restart", "Remember our restart conversation")
        store.complete_turn("turn-restart", "completed", "The saved conversation is still here.")

    # Entering a second lifespan constructs fresh app services after the first
    # lifespan has invalidated workspace connections, rather than reusing an app.
    with TestClient(create_app(tmp_path)) as restarted:
        restarted.cookies.update(cookies)
        who = restarted.get("/api/auth/whoami")
        assert who.status_code == 200, who.text
        assert who.json()["principal_id"] == owner
        login = restarted.post(
            "/api/auth/login", json={"username": "restart-owner", "password": "restart-test-pass"}
        )
        assert login.status_code == 200, login.text
        assert login.json()["principal_id"] == owner
        assert restarted.get("/api/setup").json()["status"] == "complete"
        assert restarted.get("/api/settings").json()["settings"]["personalisation"]["theme"] == "dark"
        conversation = restarted.get("/api/sessions/session-restart")
        assert conversation.status_code == 200, conversation.text
        assert "Remember our restart conversation" in conversation.text
        assert "The saved conversation is still here." in conversation.text
        recovered = SQLiteStore(tmp_path)
        status = governed_memory_status([], store=recovered, principal_id=owner)
        assert status["write_gate_enabled"] is enabled
        assert status["durable_writes_enabled"] is enabled
        assert status["write_decision_mode"] == mode
        assert recovered.list_configured_models(owner) == [("ollama-local", "restart-model")]
        selected = recovered.load_principal_model_state(owner)
        assert selected is not None
        assert (selected.profile_id, selected.model) == ("ollama-local", "restart-model")
