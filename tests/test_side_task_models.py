"""Hermes Agent's auxiliary models: a separate model per side task, with fallback.

Summarising tries the owner's chain and then the turn's own model, so
compaction cannot become impossible because a side model is down. Vision
describes an image the turn's model cannot see; only image-capable models may
be in that chain, and with none the image stays withheld.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.vault_key_file import VAULT_KEY_ENV
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models import side_tasks
from raiker.models.contracts import ModelImage, ModelResponse
from raiker.models.exceptions import ProviderConnectionError
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(VAULT_KEY_ENV, Fernet.generate_key().decode())
    ws = tmp_path / "side"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def test_chains_are_validated_and_stored_per_task(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    stored = side_tasks.save(store, OWNER, "summarise", [("openai-hosted", "gpt-4o-mini"), ("openai-hosted", "gpt-4o-mini")])
    assert stored == [("openai-hosted", "gpt-4o-mini")]  # de-duplicated
    with pytest.raises(side_tasks.SideTaskError, match="side_task_model_required"):
        side_tasks.save(store, OWNER, "summarise", [("openai-hosted", "<model>")])
    with pytest.raises(side_tasks.SideTaskError, match="side_task_profile_unknown"):
        side_tasks.save(store, OWNER, "summarise", [("no-such-profile", "m")])
    with pytest.raises(side_tasks.SideTaskError, match="side_task_chain_too_long"):
        side_tasks.save(store, OWNER, "summarise", [("openai-hosted", f"m{i}") for i in range(4)])
    # Vision only takes models that accept images.
    with pytest.raises(side_tasks.SideTaskError, match="side_task_model_lacks_vision"):
        side_tasks.save(store, OWNER, "vision", [("deepseek-hosted", "deepseek-chat")])
    side_tasks.save(store, OWNER, "vision", [("gemini-hosted-openai-compatible", "gemini-2.5-flash")])
    assert side_tasks.load(store, OWNER) == {
        "summarise": [("openai-hosted", "gpt-4o-mini")],
        "vision": [("gemini-hosted-openai-compatible", "gemini-2.5-flash")],
    }


def test_summarising_falls_back_to_the_turns_model_and_vision_never_does(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    side_tasks.save(store, OWNER, "summarise", [("openai-hosted", "gpt-4o-mini")])
    assert side_tasks.candidates(store, OWNER, "summarise", main=("ollama", "gemma3:1b")) == [
        ("openai", "gpt-4o-mini"),
        ("ollama", "gemma3:1b"),
    ]
    assert side_tasks.candidates(store, OWNER, "vision", main=("ollama", "gemma3:1b")) == []


def test_compaction_moves_down_the_chain_when_a_side_model_fails(workspace: Path) -> None:
    from raiker.runtime.conversation_compaction import ContextBudgetPlan, ConversationCompactor

    store = SQLiteStore(workspace)
    side_tasks.save(store, OWNER, "summarise", [("openai-hosted", "gpt-4o-mini")])
    calls: list[tuple[str, str]] = []

    class _Router:
        async def achat(self, provider: str, model: str, *_args: Any, **_kwargs: Any) -> ModelResponse:
            calls.append((provider, model))
            if provider == "openai":
                raise ProviderConnectionError("provider_connection_failed")
            return ModelResponse(text="A short summary of the earlier conversation.")

    plan = ContextBudgetPlan(
        should_compact=True,
        estimated_tokens=10_000,
        capacity_tokens=8_000,
        threshold_tokens=7_200,
        compact_through_turn_id="turn_1",
        eligible_turns=({"prompt_text": "hello", "summary": "hi"},),
    )
    outcome = asyncio.run(
        ConversationCompactor(store, _Router()).run(
            owner_principal_id=OWNER,
            session_id="sess_1",
            turn_id=None,
            provider="ollama",
            model="gemma3:1b",
            capacity_tokens=8_000,
            plan=plan,
            active=None,
        )
    )
    assert calls == [("openai", "gpt-4o-mini"), ("ollama", "gemma3:1b")]
    assert outcome.record is not None
    assert (outcome.record.provider, outcome.record.model) == ("ollama", "gemma3:1b")


def test_an_image_the_turn_cannot_see_is_described_by_the_vision_chain(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    side_tasks.save(store, OWNER, "vision", [("gemini-hosted-openai-compatible", "gemini-2.5-flash")])
    events: list[tuple[str, dict[str, Any]]] = []
    seen: list[Any] = []

    class _Router:
        async def achat(self, provider: str, model: str, messages: list[Any], *_a: Any, **_k: Any) -> ModelResponse:
            seen.append((provider, model, messages[-1].images))
            return ModelResponse(text="A red square on a white background.")

    fake = SimpleNamespace(
        tool_broker=SimpleNamespace(store=store),
        workspace_root=workspace,
        model_router=_Router(),
        _event=lambda _envelope, kind, payload: events.append((kind, payload)),
    )
    envelope = SimpleNamespace(user=SimpleNamespace(id=OWNER))
    image = ModelImage(media_type="image/png", base64_data="aGVsbG8=")
    described = asyncio.run(RuntimeOrchestrator._describe_images(fake, envelope, [("att_1", image)]))  # type: ignore[arg-type]
    assert len(described) == 1
    assert "described by gemini-2.5-flash" in described[0]
    assert "untrusted content" in described[0]
    assert "A red square" in described[0]
    assert seen[0][0] == "gemini" and seen[0][2] == (image,)
    assert events == [("attachment_image_described", {"attachment_id": "att_1", "provider": "gemini", "model": "gemini-2.5-flash"})]


def test_with_no_vision_chain_nothing_is_described(workspace: Path) -> None:
    fake = SimpleNamespace(
        tool_broker=SimpleNamespace(store=SQLiteStore(workspace)),
        workspace_root=workspace,
        model_router=None,
        _event=lambda *_a: None,
    )
    envelope = SimpleNamespace(user=SimpleNamespace(id=OWNER))
    image = ModelImage(media_type="image/png", base64_data="aGVsbG8=")
    assert asyncio.run(RuntimeOrchestrator._describe_images(fake, envelope, [("att_1", image)])) == []  # type: ignore[arg-type]


def test_the_route_stores_a_chain_and_the_models_view_returns_it(workspace: Path) -> None:
    client = TestClient(create_app(workspace))
    raw, _ = ApiSessionStore(workspace).create_session(OWNER)
    auth = {"Authorization": f"Bearer {raw}"}
    resp = client.put(
        "/api/model-side-tasks",
        json={"task": "summarise", "chain": [{"profile_id": "openai-hosted", "model": "gpt-4o-mini"}]},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["chain"] == [{"profile_id": "openai-hosted", "model": "gpt-4o-mini"}]
    view = client.get("/api/models", headers=auth).json()
    assert view["side_tasks"]["summarise"] == [{"profile_id": "openai-hosted", "model": "gpt-4o-mini"}]
    refused = client.put(
        "/api/model-side-tasks",
        json={"task": "vision", "chain": [{"profile_id": "deepseek-hosted", "model": "deepseek-chat"}]},
        headers=auth,
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["reason_code"] == "side_task_model_lacks_vision"
