"""ADR-0005 — composer personas."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases

_BODY = {
    "name": "Copywriter",
    "description": "Warm, short copy.",
    "instructions": "Write in short, warm sentences.",
    "tool_ceiling": ["web"],
}


def _made(client: TestClient, h: dict[str, str]) -> str:
    response = client.post("/api/personas", json=_BODY, headers=h)
    assert response.status_code == 201, response.text
    return str(response.json()["persona_id"])


def _list(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _made(client, h)
    return "/api/personas"


def _create(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/personas", _BODY


def _update(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/personas/{_made(client, h)}", {**_BODY, "tool_ceiling": None}


def _delete(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/personas/{_made(client, h)}"


CASES: Cases = {
    ("GET", "/api/personas"): _list,
    ("POST", "/api/personas"): _create,
    ("PUT", "/api/personas/{persona_id}"): _update,
    ("DELETE", "/api/personas/{persona_id}"): _delete,
}
