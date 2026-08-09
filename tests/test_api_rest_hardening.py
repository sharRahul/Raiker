from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _headers(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {raw}"}


# ── Security headers ──


def test_security_headers_present(workspace: Path) -> None:
    client = TestClient(create_app(workspace))
    resp = client.get("/api/events", headers=_headers(workspace))
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"
    # HSTS must NOT be emitted by default (loopback / non-TLS).
    assert "strict-transport-security" not in resp.headers


def test_hsts_emitted_when_enabled(workspace: Path) -> None:
    client = TestClient(create_app(workspace, hsts=True))
    resp = client.get("/api/events", headers=_headers(workspace))
    assert "strict-transport-security" in resp.headers


# ── Rate limiting ──


def test_rate_limit_returns_429(workspace: Path) -> None:
    client = TestClient(create_app(workspace, rate_limit_per_minute=3))
    headers = _headers(workspace)
    statuses = [client.get("/api/events", headers=headers).status_code for _ in range(5)]
    assert 429 in statuses
    assert statuses.count(200) == 3


# ── Body size limit ──


def test_oversized_body_rejected(workspace: Path) -> None:
    client = TestClient(create_app(workspace, max_body_bytes=50))
    resp = client.post(
        "/api/prompts",
        content=b"x" * 200,
        headers={**_headers(workspace), "content-type": "application/json"},
    )
    assert resp.status_code == 413
    assert resp.json()["reason_code"] == "request_body_too_large"


# ── Phase 8 gate: same session accepts a CLI turn and a REST prompt ──


def test_same_session_accepts_cli_and_rest_prompt(
    workspace: Path, mark_model_ready
) -> None:
    import asyncio

    from raiker.contracts.ids import new_id
    from raiker.contracts.models import (
        ClientMetadata,
        PromptEnvelope,
        PromptOptions,
        PromptPayload,
        UserMetadata,
    )
    from raiker.gateway.agent_gateway import AgentGateway

    session_id = new_id("sess_")
    mark_model_ready(workspace, "local_user")
    mark_model_ready(workspace, "principal_owner")
    # A CLI-origin turn lands in the session first.
    cli_env = PromptEnvelope(
        request_id=new_id("req_"),
        session_id=session_id,
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="cli", name="raiker", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="hello from cli", metadata={"entry_command": "cli"}),
        options=PromptOptions(),
    )
    asyncio.run(AgentGateway(workspace).submit_prompt_async(cli_env))

    # A REST-origin prompt into the SAME session via the API.
    client = TestClient(create_app(workspace))
    resp = client.post(
        "/api/prompts",
        json={"text": "hello from rest", "session_id": session_id, "client_type": "rest"},
        headers=_headers(workspace),
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == session_id

    # Both origins are recorded under one session's event log (client origin
    # lives in the JSONL payload, read back via EventViewer).
    from raiker.events.query import EventViewer

    viewer = EventViewer(SQLiteStore(workspace))
    clients: set[str] = set()
    for row in viewer.list_events(session_id=session_id, limit=500):
        event = viewer.read_event_payload(row["event_id"]) or {}
        inner = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        client_block = inner.get("client") if isinstance(inner, dict) else None
        if isinstance(client_block, dict) and client_block.get("type"):
            clients.add(str(client_block["type"]))
    assert "cli" in clients
    assert "rest" in clients
