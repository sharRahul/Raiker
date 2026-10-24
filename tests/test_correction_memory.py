"""Corrections become memory (Quiet UI 06, QUI-F20).

The owner's correction is filed as a proposal and nothing more: it becomes a
memory only through the human-only decision Memory › Suggestions uses, which
also refuses secret-like text. A correction for a conversation the owner does
not have is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


# Built at run time so the repository's own secret scan does not read it as a key.
_FAKE_KEY = "sk-ant-" + "api03-" + "Q" * 36


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _session(client: TestClient, h: dict[str, str]) -> str:
    """A conversation this owner has, made directly: no model is needed for it."""
    workspace = Path(client.app.state.workspace_root)  # type: ignore[attr-defined]
    store = SQLiteStore(workspace)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    store.create_session("sess_correction", str(workspace), title="Reply to Anna", user_id=store.principal_user_id(principal))
    return "sess_correction"


def test_a_correction_is_a_proposal_until_the_owner_decides(client: TestClient) -> None:
    h = _headers(client)
    session_id = _session(client, h)
    proposed = client.post(
        "/api/memory/proposals",
        json={"text": "  Anna prefers   short replies. ", "session_id": session_id},
        headers=h,
    )
    assert proposed.status_code == 200, proposed.text
    body = proposed.json()
    assert body["text"] == "Anna prefers short replies."
    pending = client.get("/api/memory/proposals", headers=h).json()
    assert [row["candidate_id"] for row in pending] == [body["candidate_id"]]
    assert client.get("/api/memory", headers=h).json() == []
    decided = client.post(
        f"/api/memory/proposals/{body['candidate_id']}/decision",
        json={"decision": "approved", "expected_decision": "deferred"},
        headers=h,
    )
    assert decided.status_code == 200, decided.text
    texts = [row["text"] for row in client.get("/api/memory", headers=h).json()]
    assert texts == ["Anna prefers short replies."]


def test_a_secret_like_correction_is_never_remembered(client: TestClient) -> None:
    h = _headers(client)
    session_id = _session(client, h)
    body = client.post(
        "/api/memory/proposals",
        json={"text": f"my api key is {_FAKE_KEY}", "session_id": session_id},
        headers=h,
    ).json()
    decided = client.post(
        f"/api/memory/proposals/{body['candidate_id']}/decision",
        json={"decision": "approved", "expected_decision": "deferred"},
        headers=h,
    )
    assert decided.status_code == 403
    assert decided.json()["detail"]["reason_code"] == "secret_like_memory_blocked"


def test_a_correction_needs_a_conversation_and_words(client: TestClient) -> None:
    h = _headers(client)
    session_id = _session(client, h)
    missing = client.post("/api/memory/proposals", json={"text": "Use tabs.", "session_id": "sess_nope"}, headers=h)
    assert missing.status_code == 404
    empty = client.post("/api/memory/proposals", json={"text": "   ", "session_id": session_id}, headers=h)
    assert empty.status_code == 422
