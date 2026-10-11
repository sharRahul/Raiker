"""DEC-22 step 3 — "Retry creates a new attempt linked to its source."

Retry re-sent the same words as a new turn and nothing recorded that the two
were one request asked twice: a reopened conversation showed two unrelated
turns, and the earlier attempt's tools looked like a separate decision. A Retry
now names the turn it asks again; the server checks the source is a turn of the
same conversation before anything is written, records the link, and every read
of the conversation carries it. The source turn is not changed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.sessions.manager import SessionManager
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _conversation(workspace: Path, session_id: str, *turns: str) -> None:
    store = SQLiteStore(workspace)
    owner = store.get_principal("principal_owner") or {}
    SessionManager(store, workspace).create_session(
        session_id=session_id, user_id=str(owner.get("delegated_by_user_id") or "")
    )
    for turn_id in turns:
        store.insert_turn(session_id, turn_id, "Summarise the build log")
        store.complete_turn(turn_id, "completed", "done")


def test_a_retry_is_linked_to_its_source_and_the_source_is_unchanged(workspace: Path) -> None:
    _conversation(workspace, "sess_a", "turn_first", "turn_again")
    store = SQLiteStore(workspace)

    assert store.record_turn_retry(
        turn_id="turn_again", retry_of_turn_id="turn_first", session_id="sess_a"
    )

    turns = {row["turn_id"]: row for row in store.list_turns("sess_a")}
    assert turns["turn_again"]["retry_of_turn_id"] == "turn_first"
    assert turns["turn_first"]["retry_of_turn_id"] is None
    assert turns["turn_first"]["status"] == "completed"


def test_a_source_in_another_conversation_is_not_linked(workspace: Path) -> None:
    _conversation(workspace, "sess_a", "turn_first")
    _conversation(workspace, "sess_b", "turn_other")
    store = SQLiteStore(workspace)

    assert not store.record_turn_retry(
        turn_id="turn_new", retry_of_turn_id="turn_other", session_id="sess_a"
    )
    assert not store.record_turn_retry(
        turn_id="turn_new", retry_of_turn_id="turn_missing", session_id="sess_a"
    )


def test_the_conversation_read_carries_the_link(workspace: Path) -> None:
    _conversation(workspace, "sess_a", "turn_first", "turn_again")
    SQLiteStore(workspace).record_turn_retry(
        turn_id="turn_again", retry_of_turn_id="turn_first", session_id="sess_a"
    )
    client = TestClient(create_app(workspace))

    detail = client.get("/api/sessions/sess_a", headers=_headers(client))

    assert detail.status_code == 200, detail.text
    turns = {turn["turn_id"]: turn for turn in detail.json()["turns"]}
    assert turns["turn_again"]["retry_of_turn_id"] == "turn_first"
    assert turns["turn_first"]["retry_of_turn_id"] is None


@pytest.mark.parametrize("session_id", [None, "sess_b"])
def test_a_retry_naming_a_turn_outside_its_conversation_is_refused_before_anything_runs(
    workspace: Path, session_id: str | None
) -> None:
    _conversation(workspace, "sess_a", "turn_first")
    _conversation(workspace, "sess_b", "turn_other")
    client = TestClient(create_app(workspace))
    body: dict[str, object] = {"text": "again", "retry_of_turn_id": "turn_first"}
    if session_id:
        body["session_id"] = session_id

    answer = client.post("/api/prompts", json=body, headers=_headers(client))

    assert answer.status_code == 422
    assert answer.json()["detail"]["reason_code"] == "retry_source_not_in_session"
    assert len(SQLiteStore(workspace).list_turns("sess_b")) == 1
