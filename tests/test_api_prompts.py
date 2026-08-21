from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.routes_prompts import _build_envelope
from raiker.api.schemas import PromptRequest
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import AgentResponse, ContractValidationError, PromptEnvelope
from raiker.contracts.streaming import FINAL, StreamEvent
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/session", json={"as_principal": None})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_prompt_without_approval_mode_uses_account_preference(workspace: Path) -> None:
    SQLiteStore(workspace).put_user_settings(
        "principal_owner", '{"composer":{"approval_mode":"auto"}}', utc_now()
    )

    envelope = _build_envelope(PromptRequest(text="hello"), "principal_owner", workspace)

    assert envelope.options.approval_mode == "auto"


def test_prompt_without_approval_mode_defaults_to_manual(workspace: Path) -> None:
    envelope = _build_envelope(PromptRequest(text="hello"), "principal_owner", workspace)

    assert envelope.options.approval_mode == "manual"


def test_prompt_preserves_optional_reasoning_effort_for_the_turn(workspace: Path) -> None:
    envelope = _build_envelope(
        PromptRequest(
            text="hello", model_profile="openai-hosted", model="gpt-4o", reasoning_effort="high"
        ),
        "principal_owner",
        workspace,
    )

    assert envelope.options.reasoning_effort == "high"


def test_prompt_without_reasoning_effort_remains_backward_compatible(workspace: Path) -> None:
    envelope = _build_envelope(PromptRequest(text="hello"), "principal_owner", workspace)

    assert envelope.options.reasoning_effort is None


def test_prompt_input_provenance_defaults_to_typed_and_preserves_dictation(
    workspace: Path,
) -> None:
    typed = _build_envelope(PromptRequest(text="hello"), "principal_owner", workspace)
    dictated = _build_envelope(
        PromptRequest(text="hello", input_mode="dictated"), "principal_owner", workspace
    )

    assert typed.prompt.metadata["input_mode"] == "typed"
    assert dictated.prompt.metadata["input_mode"] == "dictated"
    assert set(dictated.prompt.metadata) == {"entry_command", "input_mode", "surface"}


def test_prompt_surface_defaults_to_chat_and_is_validated(workspace: Path) -> None:
    default = _build_envelope(PromptRequest(text="hello"), "principal_owner", workspace)
    build = _build_envelope(
        PromptRequest(text="hello", surface="build"), "principal_owner", workspace
    )

    # An external REST client that has never heard of the field gets the
    # conservative surface, not the coding one.
    assert default.prompt.metadata["surface"] == "chat"
    assert build.prompt.metadata["surface"] == "build"


def test_prompt_surface_never_changes_what_a_turn_may_do(workspace: Path) -> None:
    chat = _build_envelope(
        PromptRequest(text="hello", capability_modes={"shell_execution": "ask"}),
        "principal_owner",
        workspace,
    )
    build = _build_envelope(
        PromptRequest(
            text="hello", surface="build", capability_modes={"shell_execution": "ask"}
        ),
        "principal_owner",
        workspace,
    )

    # The surface selects an operating protocol and nothing else: every field
    # that decides authority is identical on both.
    assert chat.options.capability_modes == build.options.capability_modes
    assert chat.options.approval_mode == build.options.approval_mode
    assert chat.options.planning_mode == build.options.planning_mode
    assert chat.options.max_tool_calls == build.options.max_tool_calls


def test_gateway_revalidates_and_audits_only_safe_input_provenance(workspace: Path) -> None:
    envelope = _build_envelope(
        PromptRequest(text="spoken secret stays only in the prompt", input_mode="mixed"),
        "principal_owner",
        workspace,
    )
    AgentGateway(workspace)._prepare_turn(envelope)
    events = [
        json.loads(line)
        for line in EventLogWriter(SQLiteStore(workspace))
        .path_for_session(envelope.session_id)
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    received = next(event for event in events if event["event_type"] == "prompt_received")

    assert received["payload"]["client_type"] == "web_ui"
    assert received["payload"]["prompt_length"] == len(envelope.prompt.text)
    assert received["payload"]["input_mode"] == "mixed"
    assert received["payload"]["surface"] == "chat"
    assert set(received["payload"]) == {
        "client",
        "client_type",
        "prompt_length",
        "input_mode",
        "surface",
    }
    assert "spoken secret" not in json.dumps(received)

    envelope.prompt.metadata["input_mode"] = "continuous-listening"
    with pytest.raises(ContractValidationError, match="invalid_input_mode"):
        AgentGateway(workspace)._prepare_turn(envelope)


def test_gateway_refuses_an_unknown_prompt_surface(workspace: Path) -> None:
    envelope = _build_envelope(PromptRequest(text="hello"), "principal_owner", workspace)
    envelope.prompt.metadata["surface"] = "voice"

    # Guessing here would put the Build operating protocol on a Chat turn (or the
    # reverse) with nothing in the audit trail saying so.
    with pytest.raises(ContractValidationError, match="invalid_prompt_surface"):
        AgentGateway(workspace)._prepare_turn(envelope)


class TestPrompts:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.post("/api/prompts", json={"text": "hi"}).status_code == 401

    def test_prompt_routes_use_account_approval_mode_when_omitted(
        self,
        workspace: Path,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        mark_model_ready: Callable[..., None],
    ) -> None:
        mark_model_ready(workspace)
        SQLiteStore(workspace).put_user_settings(
            "principal_owner", '{"composer":{"approval_mode":"auto"}}', utc_now()
        )
        captured: list[PromptEnvelope] = []

        def response_for(envelope: PromptEnvelope) -> AgentResponse:
            return AgentResponse(
                request_id=envelope.request_id,
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                status="completed",
                message="stubbed",
            )

        async def submit_stub(_gateway, envelope: PromptEnvelope) -> AgentResponse:  # type: ignore[no-untyped-def]
            captured.append(envelope)
            return response_for(envelope)

        async def stream_stub(_gateway, envelope: PromptEnvelope):  # type: ignore[no-untyped-def]
            captured.append(envelope)
            yield StreamEvent(kind=FINAL, response=response_for(envelope))

        monkeypatch.setattr(
            "raiker.api.routes_prompts.AgentGateway.submit_prompt_async", submit_stub
        )
        monkeypatch.setattr("raiker.api.routes_prompts.AgentGateway.astream_prompt", stream_stub)
        token = _token(client)

        prompt = client.post("/api/prompts", json={"text": "hello"}, headers=_headers(token))
        stream = client.post("/api/prompts/stream", json={"text": "hello"}, headers=_headers(token))

        assert prompt.status_code == 200
        assert stream.status_code == 200
        assert [envelope.options.approval_mode for envelope in captured] == ["auto", "auto"]

    def test_prompt_runs_a_governed_turn(
        self, workspace: Path, client: TestClient, mark_model_ready: Callable[..., None]
    ) -> None:
        mark_model_ready(workspace)
        token = _token(client)
        resp = client.post("/api/prompts", json={"text": "hello"}, headers=_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in {"completed", "failed", "needs_approval", "denied"}
        # The full governed turn lifecycle is recorded in the durable event log.
        events = SQLiteStore(workspace).list_event_index(session_id=body["session_id"], limit=200)
        types = {e["event_type"] for e in events}
        assert "prompt_received" in types
        assert "turn_closed" in types

    def test_invalid_prompt_returns_failed(self, client: TestClient) -> None:
        token = _token(client)
        resp = client.post("/api/prompts", json={"text": ""}, headers=_headers(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_invalid_input_provenance_is_rejected_at_the_http_boundary(
        self, client: TestClient
    ) -> None:
        token = _token(client)
        response = client.post(
            "/api/prompts",
            json={"text": "hello", "input_mode": "continuous-listening"},
            headers=_headers(token),
        )

        assert response.status_code == 422

    def test_stream_emits_sse_with_final(self, client: TestClient) -> None:
        token = _token(client)
        resp = client.post("/api/prompts/stream", json={"text": "hello"}, headers=_headers(token))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "data:" in resp.text
        assert '"kind": "final"' in resp.text


class TestInterrupts:
    def test_stop_cancels_active_tasks_at_safe_boundary(
        self, workspace: Path, client: TestClient
    ) -> None:
        store = SQLiteStore(workspace)
        store.create_session("sess_i", str(workspace))
        manager = TaskManager(store, EventLogWriter(store))
        task = manager.create_task(session_id="sess_i", title="demo", objective="do x")
        token = _token(client)

        resp = client.post(
            "/api/interrupts",
            json={"session_id": "sess_i", "all": True, "action_type": "cancel", "reason": "stop"},
            headers=_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["safe_boundary"] is True
        assert any(
            a["task_id"] == task.task_id and a["result"] == "cancelled" for a in body["applied"]
        )

        assert store.load_task(task.task_id).status == "cancelled"  # type: ignore[union-attr]
        types = {e["event_type"] for e in store.list_event_index(session_id="sess_i", limit=200)}
        assert {"interrupt_received", "safe_boundary_reached", "task_cancelled"} <= types

    def test_ai_principal_cannot_interrupt(self, workspace: Path, client: TestClient) -> None:
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
            )
        raw, _ = ApiSessionStore(workspace).create_session("principal_ai")
        resp = client.post(
            "/api/interrupts",
            json={"session_id": "sess_i", "all": True},
            headers=_headers(raw),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "human_principal_required"
