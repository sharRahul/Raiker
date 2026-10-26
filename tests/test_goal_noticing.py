"""Goals noticed in conversation (Quiet UI 06, QUI-F03).

An aim that comes up in two conversations is offered as a goal once; *Not now*
is remembered as the aim, so the same aim worded differently is not offered
again; an aim that already has a goal is not offered; one conversation, a
routine's own conversation, and another account's conversations offer nothing.
Nothing here creates a goal.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.goals import noticing
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _store(client: TestClient) -> SQLiteStore:
    return SQLiteStore(Path(client.app.state.workspace_root))  # type: ignore[attr-defined]


def _chat(client: TestClient, h: dict[str, str], session_id: str, prompt: str, *, origin: str = "chat") -> None:
    store = _store(client)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    store.create_session(session_id, str(store.paths.workspace_root), title=prompt[:40], user_id=store.principal_user_id(principal))
    if origin != "chat":
        store._execute("UPDATE sessions SET origin = ? WHERE session_id = ?", (origin, session_id))
    store.insert_turn(session_id, f"turn_{session_id}", prompt)
    store.complete_turn(f"turn_{session_id}", "completed", "Done.")


def _suggestion(client: TestClient, h: dict[str, str], session_id: str) -> dict[str, object] | None:
    response = client.get(f"/api/goals/suggestion?session_id={session_id}", headers=h)
    assert response.status_code == 200, response.text
    suggestion: dict[str, object] | None = response.json()["suggestion"]
    return suggestion


def test_the_same_aim_in_two_conversations_is_offered_once(client: TestClient) -> None:
    h = _headers(client)
    _chat(client, h, "sess_a", "Find a marathon training plan for the Berlin marathon in September")
    assert _suggestion(client, h, "sess_a") is None  # one conversation is not a pattern
    _chat(client, h, "sess_b", "Adjust my Berlin marathon training plan, my long runs feel too short")
    offered = _suggestion(client, h, "sess_b")
    assert offered is not None
    assert {"berlin", "marathon", "training"} <= set(str(word) for word in offered["keywords"])  # type: ignore[attr-defined]
    assert offered["session_ids"] == ["sess_a"]
    assert str(offered["objective"]).startswith("Adjust my Berlin marathon")
    assert client.get("/api/goals", headers=h).json()["goals"] == []  # nothing was created

    dismissed = client.post("/api/goals/suggestion/dismiss", json={"keywords": offered["keywords"]}, headers=h)
    assert dismissed.status_code == 200, dismissed.text
    assert _suggestion(client, h, "sess_b") is None
    # The same aim, worded again in a third conversation, is still the dismissed aim.
    _chat(client, h, "sess_c", "Marathon training for Berlin: what pace for my long runs?")
    assert _suggestion(client, h, "sess_c") is None


def test_unrelated_requests_and_routines_offer_nothing(client: TestClient) -> None:
    h = _headers(client)
    _chat(client, h, "sess_a", "Draft a polite reply to the landlord about the broken boiler")
    _chat(client, h, "sess_b", "Compare three laptops for photo editing under two thousand euros")
    assert _suggestion(client, h, "sess_b") is None
    _chat(client, h, "sess_task", "Compare three laptops for photo editing under two thousand euros", origin="task")
    assert _suggestion(client, h, "sess_task") is None
    assert _suggestion(client, h, "sess_b") is None  # a routine's conversation is not a second chat


def test_an_aim_with_a_goal_is_not_offered(client: TestClient) -> None:
    h = _headers(client)
    _chat(client, h, "sess_a", "Plan the garden renovation budget and the contractor schedule")
    _chat(client, h, "sess_b", "Update the garden renovation budget, the contractor schedule slipped")
    assert _suggestion(client, h, "sess_b") is not None
    created = client.post(
        "/api/goals",
        json={
            "title": "Garden renovation",
            "objective": "Plan the garden renovation budget and the contractor schedule",
            "criteria": [{"text": "A budget", "validator": "owner_confirms"}],
            "steps": [{"title": "Budget", "instruction": "Draft the budget.", "criteria": [0]}],
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    assert _suggestion(client, h, "sess_b") is None


def test_keywords_ignore_short_and_filler_words() -> None:
    assert noticing.keywords("Please help me with the Berlin marathon plan") == frozenset({"berlin", "marathon", "plan"})
    assert noticing.same_aim(frozenset({"a", "b", "c", "d"}), frozenset({"a", "b", "c"}))
    assert not noticing.same_aim(frozenset({"a", "b"}), frozenset({"a", "b"}))
