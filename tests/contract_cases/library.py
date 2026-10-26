"""The Library and its pinned blocks (QUI-F15)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases

_ANSWER = (
    "Numbers.\n\n```raiker:figures\n"
    + json.dumps({"caption": "Q3", "items": [{"label": "Revenue", "value": 1, "unit": "$"}], "source": "Q3 report"})
    + "\n```"
)


def _conversation(ws: Path, client: TestClient, h: dict[str, str]) -> tuple[str, str]:
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(ws)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    store.create_session("sess_contract_lib", str(ws), title="Library", user_id=store.principal_user_id(principal))
    store.insert_turn("sess_contract_lib", "turn_contract_lib", "Numbers?")
    store.complete_turn("turn_contract_lib", "completed", _ANSWER)
    return "sess_contract_lib", "turn_contract_lib"


def _pin_body(ws: Path, client: TestClient, h: dict[str, str]) -> dict[str, object]:
    session_id, turn_id = _conversation(ws, client, h)
    return {"session_id": session_id, "turn_id": turn_id, "part_index": 1}


def _pinned(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    response = client.post("/api/library/pins", json=_pin_body(ws, client, h), headers=h)
    assert response.status_code == 201, response.text
    return str(response.json()["pin_id"])


def _library(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _pinned(ws, client, h)
    return "/api/library"


def _session_pins(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _pinned(ws, client, h)
    return "/api/library/pins?session_id=sess_contract_lib"


def _pin(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/library/pins", _pin_body(ws, client, h)


def _unpin(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/library/pins/{_pinned(ws, client, h)}"


def _move(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/library/pins/{_pinned(ws, client, h)}/project", {"project_id": None}


CASES: Cases = {
    ("PUT", "/api/library/pins/{pin_id}/project"): _move,
    ("GET", "/api/library"): _library,
    ("GET", "/api/library/pins"): _session_pins,
    ("POST", "/api/library/pins"): _pin,
    ("DELETE", "/api/library/pins/{pin_id}"): _unpin,
}
