from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Protocol

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    AgentResponse,
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import ProviderModelInfo
from raiker.models.router import ModelRouter
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "readiness-guards"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def owner_token(workspace: Path) -> str:
    token, _session = ApiSessionStore(workspace).create_session("principal_owner")
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


MODEL = {
    "model_profile": "ollama-local-openai-compatible",
    "model": "gemma4:31b-cloud",
}


class MarkModelReady(Protocol):
    def __call__(
        self,
        workspace: Path,
        principal_id: str = "principal_owner",
        profile_id: str = "ollama-local-openai-compatible",
        model: str = "gemma4:31b-cloud",
    ) -> None: ...


def test_unready_chat_creates_no_session_turn_or_event(
    client: TestClient,
    owner_token: str,
    workspace: Path,
) -> None:
    store = SQLiteStore(workspace)
    before = (len(store.list_sessions()), store.count_events())

    response = client.post(
        "/api/prompts",
        headers=_auth(owner_token),
        json={"text": "hello", **MODEL},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "reason_code": "model_not_ready",
        "readiness": {
            "state": "not_configured",
            "summary": "No readiness check exists for this exact model.",
            "reason_code": "model_not_checked",
            "remediation": "Set up or check this model before sending.",
        },
    }
    assert (len(store.list_sessions()), store.count_events()) == before


def test_unready_build_stream_emits_one_final_refusal_and_creates_no_work(
    client: TestClient,
    owner_token: str,
    workspace: Path,
) -> None:
    store = SQLiteStore(workspace)
    before = (len(store.list_sessions()), store.count_events(), store.count_tasks())

    response = client.post(
        "/api/prompts/stream",
        headers=_auth(owner_token),
        json={"text": "build a page", **MODEL},
    )

    assert response.status_code == 200
    frames = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 1
    assert frames[0]["kind"] == "final"
    assert frames[0]["event_type"] == "model_not_ready"
    assert frames[0]["payload"]["reason_code"] == "model_not_ready"
    assert frames[0]["payload"]["readiness"]["state"] == "not_configured"
    assert (len(store.list_sessions()), store.count_events(), store.count_tasks()) == before


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"scheduled_at": "2030-01-01T00:00:00Z"},
        {"recurrence": "background"},
    ],
)
def test_unready_task_schedule_and_background_create_no_task(
    client: TestClient,
    owner_token: str,
    workspace: Path,
    extra: dict[str, Any],
) -> None:
    store = SQLiteStore(workspace)
    before = store.count_tasks()

    response = client.post(
        "/api/tasks",
        headers=_auth(owner_token),
        json={"title": "Run", "description": "Do work", **MODEL, **extra},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "model_not_ready"
    assert store.count_tasks() == before


def test_ready_exact_model_reaches_gateway(
    client: TestClient,
    owner_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def catalogue(_router: ModelRouter, _profile: object) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id="gemma4:31b-cloud")]

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", catalogue)
    checked = client.post(
        "/api/model-readiness/check",
        headers=_auth(owner_token),
        json={
            "profile_id": MODEL["model_profile"],
            "model": MODEL["model"],
        },
    )
    assert checked.json()["state"] == "ready"

    class AnsweringGateway:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def submit_prompt_async(self, envelope: Any) -> AgentResponse:
            return AgentResponse(
                request_id=envelope.request_id,
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                status="completed",
                message="ready path",
            )

    monkeypatch.setattr("raiker.api.routes_prompts.AgentGateway", AnsweringGateway)
    response = client.post(
        "/api/prompts",
        headers=_auth(owner_token),
        json={"text": "hello", **MODEL},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "ready path"


def test_gateway_rechecks_readiness_before_creating_a_turn(
    workspace: Path,
    mark_model_ready: MarkModelReady,
) -> None:
    mark_model_ready(workspace)
    gateway = AgentGateway(workspace, principal_id="principal_owner")
    gateway.store.invalidate_model_readiness(
        "principal_owner",
        "ollama-local-openai-compatible",
        reason_code="runtime_changed",
    )
    before = len(gateway.store.list_sessions())
    envelope = PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="dashboard", name="scheduler", version="1"),
        user=UserMetadata(id="principal_owner"),
        prompt=PromptPayload(text="scheduled work"),
        options=PromptOptions(
            model_profile=MODEL["model_profile"],
            model=MODEL["model"],
        ),
    )

    response = asyncio.run(gateway.submit_prompt_async(envelope))

    assert response.status == "failed"
    assert response.message == "This model connection must be checked again."
    assert len(gateway.store.list_sessions()) == before
