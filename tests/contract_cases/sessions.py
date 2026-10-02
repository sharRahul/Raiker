"""Conversations: their organisation, transcript, sources, plan, grants and branches."""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, Seed, first, plain, with_turn


def _session(client: TestClient, h: dict[str, str]) -> str:
    """A conversation with one completed turn in it."""
    with_turn("")(Path("."), client, h)
    return first(client, h, "/api/sessions", "session_id")


def _on_session(suffix: str, body: object = None) -> Seed:
    """``/api/sessions/{id}<suffix>`` on a conversation that has a turn."""

    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        path = f"/api/sessions/{_session(client, h)}{suffix}"
        return path if body is None else (path, body)

    return seed


def _checkpoint(suffix: str, body: object = None) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        _session(client, h)
        path = "/api/checkpoints/" + first(client, h, "/api/checkpoints", "checkpoint_id") + suffix
        return path if body is None else (path, body)

    return seed


def _with_document(client: TestClient, h: dict[str, str]) -> tuple[str, str]:
    """A conversation whose turn carried an uploaded document."""
    upload = client.post(
        "/api/attachments",
        json={
            "filename": "notes.txt",
            "media_type": "text/plain",
            "data_base64": base64.b64encode(b"Quarterly notes: revenue up.").decode(),
        },
        headers=h,
    )
    assert upload.status_code == 200, upload.text
    attachment_id = upload.json()["attachment_id"]
    sent = client.post(
        "/api/prompts",
        json={"text": "Summarise", "attachments": [{"type": "document", "attachment_id": attachment_id}]},
        headers=h,
    )
    assert sent.status_code == 200, sent.text
    return sent.json()["session_id"], attachment_id


def _attachment(suffix: str) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        session_id, attachment_id = _with_document(client, h)
        return f"/api/sessions/{session_id}/attachments/{attachment_id}{suffix}"

    return seed


def _attachments(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    session_id, _attachment_id = _with_document(client, h)
    return f"/api/sessions/{session_id}/attachments"


def _source(ws: Path, client: TestClient, h: dict[str, str]) -> tuple[str, str]:
    """A recorded source on the conversation's turn: (session, turn)."""
    session_id = _session(client, h)
    store = SQLiteStore(ws)
    turn_id = str(store.list_turns(session_id)[0]["turn_id"])
    store.record_turn_sources(
        session_id=session_id,
        turn_id=turn_id,
        principal_id="principal_owner",
        rows=[
            {
                "source_id": "src_1",
                "ordinal": 1,
                "kind": "web",
                "title": "Example",
                "locator": "https://example.com/",
                "tool_name": "web_fetch",
                "detail": "",
                "passage": "Example passage the turn read.",
            }
        ],
    )
    return session_id, turn_id


def _sources(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    session_id, _turn_id = _source(ws, client, h)
    return f"/api/sessions/{session_id}/sources"


def _excerpt(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    session_id, turn_id = _source(ws, client, h)
    return f"/api/sessions/{session_id}/turns/{turn_id}/sources/src_1/excerpt"


def _delete_one(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    session_id = _session(client, h)
    return f"/api/sessions/{session_id}", None, {**h, "X-Session-Delete-Confirm": session_id}


def _delete_bulk(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/sessions/bulk", {"session_ids": [_session(client, h)]}


def _compact(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    session_id = _session(client, h)
    turn_id = str(SQLiteStore(ws).list_turns(session_id)[0]["turn_id"])
    return f"/api/sessions/{session_id}/compact", {"through_turn_id": turn_id}


def _resume(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    task = client.post("/api/tasks", json={"title": "t", "description": "d"}, headers=h).json()
    return f"/api/tasks/{task['task_id']}/resume"


GRANT = {"commands": [["ls"]], "timeout_seconds": 30, "ttl_minutes": 10}

CASES: Cases = {
    ("GET", "/api/sessions/{session_id}"): _on_session(""),
    ("GET", "/api/sessions/{session_id}/export/manifest"): _on_session("/export/manifest"),
    ("PUT", "/api/sessions/{session_id}/pin"): _on_session("/pin", {"pinned": True}),
    ("PUT", "/api/sessions/{session_id}/rename"): _on_session("/rename", {"title": "Renamed"}),
    ("PUT", "/api/sessions/{session_id}/archive"): _on_session("/archive"),
    ("PUT", "/api/sessions/{session_id}/unarchive"): _on_session("/unarchive"),
    ("DELETE", "/api/sessions/bulk"): _delete_bulk,
    ("DELETE", "/api/sessions/{session_id}"): _delete_one,
    ("PUT", "/api/sessions/{session_id}/project"): _on_session("/project", {"project_id": None}),
    ("PUT", "/api/sessions/{session_id}/tags"): _on_session("/tags", {"tags": ["contract"]}),
    ("PUT", "/api/sessions/{session_id}/command-grant"): _on_session("/command-grant", GRANT),
    ("DELETE", "/api/sessions/{session_id}/command-grant"): _on_session("/command-grant"),
    ("GET", "/api/sessions/{session_id}/plan"): _on_session("/plan"),
    ("GET", "/api/sessions/{session_id}/attachments"): _attachments,
    ("GET", "/api/sessions/{session_id}/attachments/{attachment_id}/preview"): _attachment("/preview"),
    ("GET", "/api/sessions/{session_id}/attachments/{attachment_id}/provenance"): _attachment(
        "/provenance"
    ),
    ("GET", "/api/sessions/{session_id}/sources"): _sources,
    ("GET", "/api/sessions/{session_id}/recall"): _on_session("/recall"),
    ("GET", "/api/sessions/{session_id}/turns/{turn_id}/sources/{source_id}/excerpt"): _excerpt,
    ("POST", "/api/sessions/{session_id}/compact"): _compact,
    ("GET", "/api/sessions/{session_id}/branch-origin"): _on_session("/branch-origin"),
    ("GET", "/api/work-in-flight"): plain("/api/work-in-flight"),
    ("POST", "/api/tasks/{task_id}/resume"): _resume,
    ("GET", "/api/checkpoints/{checkpoint_id}/restore-plan"): _checkpoint("/restore-plan"),
    ("POST", "/api/checkpoints/{checkpoint_id}/restore"): _checkpoint("/restore"),
    ("GET", "/api/checkpoints/{checkpoint_id}/branch-plan"): _checkpoint("/branch-plan"),
    ("POST", "/api/checkpoints/{checkpoint_id}/branch"): _checkpoint("/branch", {"title": "Branch"}),
}

