"""GCR-05 — a governed execution must not run on the ASGI event loop.

Raiker's tool execution is synchronous by design and ends, for a model-backed
capability, in a provider call. Three routes used to perform that execution
*inline* inside an `async def`: generating an image, building the memory
embedding index, and resolving an approval that executes on resolution.

Inline meant the request's own event loop — the one serving every other request
on this host — was blocked for the length of the call. The symptom was not an
error anywhere; it was a server that stopped answering while one owner waited
for a picture.

`raiker.runtime.async_bridge` counts the calls that arrive with a loop already
running, because that is exactly the condition these routes used to create. Each
test below replaces the synchronous work the route performs with work that
crosses the same bridge, drives the route, and asserts the counter never moved.

The counter is the mechanism rather than a timing measurement on purpose. A
"did the loop stay responsive" assertion is a race; this is a fact about which
thread the call was made from.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.service import ControlResult, RuntimeControlService
from raiker.runtime.async_bridge import (
    blocked_loop_calls,
    reset_blocked_loop_calls,
    run_coro,
)


def _crosses_the_bridge() -> None:
    """Do what a model-backed executor does: leave sync code for a provider."""

    async def provider_call() -> str:
        await asyncio.sleep(0)
        return "answered"

    assert run_coro(provider_call()) == "answered"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "loop"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture()
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_generating_an_image_does_not_block_the_event_loop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def generate_image(self: Any, *args: Any, **kwargs: Any) -> ControlResult:
        _crosses_the_bridge()
        return ControlResult(ok=True, data={"generation_id": "img_1"})

    monkeypatch.setattr(RuntimeControlService, "generate_image", generate_image)
    headers = _headers(client)
    reset_blocked_loop_calls()

    response = client.post(
        "/api/images",
        headers=headers,
        json={
            "profile_id": "openai-hosted",
            "prompt": "a maple leaf",
            "size": "1024x1024",
            "model": "gpt-image-1",
        },
    )

    assert response.status_code == 200, response.text
    assert blocked_loop_calls() == 0


def test_building_the_embedding_index_does_not_block_the_event_loop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def build_index(self: Any, *args: Any, **kwargs: Any) -> ControlResult:
        _crosses_the_bridge()
        return ControlResult(ok=True, data={"indexed_count": 0})

    monkeypatch.setattr(RuntimeControlService, "build_memory_embedding_index", build_index)
    headers = _headers(client)
    reset_blocked_loop_calls()

    response = client.post(
        "/api/memory/embedding-index",
        headers=headers,
        json={"provider": "openai", "model": "text-embedding-3-small"},
    )

    assert response.status_code == 200, response.text
    assert blocked_loop_calls() == 0


def test_the_guard_would_catch_the_hop_being_removed() -> None:
    """Proved, not assumed.

    A counter that never moves is indistinguishable from a counter nothing
    reads, so this does what the routes used to do — synchronous work, on the
    loop — and shows the guard notices.
    """
    reset_blocked_loop_calls()

    async def inline() -> None:
        _crosses_the_bridge()

    asyncio.run(inline())
    assert blocked_loop_calls() == 1


def test_the_bridge_is_free_when_there_is_no_loop_to_block() -> None:
    reset_blocked_loop_calls()
    _crosses_the_bridge()
    assert blocked_loop_calls() == 0
