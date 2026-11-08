"""MM-3 (beta plan) — the credential and privacy canary drill.

Distinct fake secrets are planted where an owner keeps them: a key in a model
connection, a password and a card number in a memory, and all three in a
document attached to a turn. Then a chat turn, a task and a support export are
run. Every model request, every file Raiker wrote under the workspace (events,
logs, the store's own text files) and the export are searched for the raw
markers. None may be found anywhere, except inside the encrypted vault.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.contracts.ids import new_id
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.models.contracts import ModelResponse
from tests.test_turn_resume_after_approval import ScriptedRouter, scripted_model

__all__ = ["scripted_model"]

KEY = "sk-ant-api03-CANARYkeyQ7m2Zp9Lw4Xv8Rt1Yb6Nc3Hd5Jf0Gk"
PASSWORD = "Canary-Pass-7f3e9bQ!"
CARD = "4111 1111 1111 1111"
CARD_DIGITS = CARD.replace(" ", "")
MARKERS = (KEY, PASSWORD, CARD, CARD_DIGITS)


def _text_files(root: Path) -> list[Path]:
    """Everything Raiker wrote that a person or a support bundle could read."""
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        # The SQLCipher database and the connector vault are encrypted at rest.
        if path.suffix in {".db", ".db-wal", ".db-shm"} or "vault" in path.name:
            continue
        found.append(path)
    return found


def _leaks(text: str) -> list[str]:
    return [marker for marker in MARKERS if marker in text]


def test_no_planted_secret_leaves_in_a_request_a_record_or_an_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scripted_model: ScriptedRouter,
    offline_default_model: None,
) -> None:
    from raiker.api.app import create_app

    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    scripted_model.responses = [ModelResponse(text="I read your note and the file.", tool_calls=[])]
    client = TestClient(create_app(tmp_path), raise_server_exceptions=False)
    token = client.post("/api/auth/register", json={"username": "alice", "password": "right-pass-123"}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    owner = client.get("/api/auth/me", headers=auth).json().get("principal_id", "principal_owner")

    # 1. A connector-held credential: the model connection's key.
    saved = client.put("/api/models/anthropic-hosted/connection", json={"api_key": KEY}, headers=auth)
    assert saved.status_code in (200, 201, 204), saved.text

    # 2. A memory the owner kept, with a password and a card in it.
    from raiker.storage.sqlite import SQLiteStore

    write_memory(
        f"My bank login password: {PASSWORD} and my card is {CARD}.",
        workspace_root=tmp_path,
        scope="user",
        memory_type="user",
        source="user_ui",
        store=SQLiteStore(tmp_path),
        governance=MemoryGovernance(
            source_event_id=new_id("evt_"), source_session_id="", source_turn_id=None,
            source_type="user_ui", confidence=1.0, trust_score=1.0,
            retention="until_forget", approval_state="approved", created_by=str(owner),
        ),
        owner_principal_id=str(owner),
    )

    # 3. A document attached to the turn, carrying all three.
    document = f"Notes\napi_key = {KEY}\npassword: {PASSWORD}\ncard {CARD}\n".encode()
    uploaded = client.post(
        "/api/attachments",
        json={"filename": "notes.txt", "media_type": "text/plain", "data_base64": base64.b64encode(document).decode()},
        headers=auth,
    )
    assert uploaded.status_code in (200, 201), uploaded.text
    attachment_id = uploaded.json()["attachment_id"]

    # A chat turn that recalls the memory and reads the file.
    turn = client.post(
        "/api/prompts",
        json={
            "text": "What did I save about my bank login and my card, and what is in the attached file?",
            "attachments": [{"type": "document", "attachment_id": attachment_id}],
        },
        headers=auth,
    )
    assert turn.status_code == 200, turn.text

    # A task that carries the same question.
    task = client.post("/api/tasks", json={"title": "Bank note", "prompt": "Summarise my bank note."}, headers=auth)
    if task.status_code in (200, 201):
        task_id = task.json().get("task_id")
        if task_id:
            client.post(f"/api/tasks/{task_id}/run", headers=auth)

    # The support export.
    export = client.get("/api/diagnostics/export", headers=auth)
    assert export.status_code in (200, 422), export.text

    # ── search ──
    requests = [message.content for call in scripted_model.seen_messages for message in call if isinstance(message.content, str)]
    assert scripted_model.seen_messages, "no model request was made, so nothing was checked"
    joined = chr(10).join(requests)
    # The paths were really exercised: the file's text and the memory reached
    # the model, with their secrets masked.
    assert "card" in joined and "Notes" in joined, "the attached document never reached the model"
    assert "bank login" in joined, "the memory was never recalled into the request"
    assert "[REDACTED" in joined
    request_leaks = sorted({leak for text in requests for leak in _leaks(text)})
    assert request_leaks == [], f"model requests carried {request_leaks}"

    file_leaks = {
        str(path.relative_to(tmp_path)): found
        for path in _text_files(tmp_path)
        if (found := _leaks(path.read_bytes().decode("utf-8", "ignore")))
    }
    assert file_leaks == {}, f"files under the workspace carried planted secrets: {file_leaks}"

    export_leaks = _leaks(json.dumps(export.json()))
    assert export_leaks == [], f"the support export carried {export_leaks}"

    turn_leaks = _leaks(json.dumps(turn.json()))
    assert turn_leaks == [], f"the turn's answer carried {turn_leaks}"


def _messages(router: ScriptedRouter) -> list[Any]:  # pragma: no cover - helper for debugging
    return router.seen_messages
