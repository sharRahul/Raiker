from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from raiker.cli.commands import (
    build_prompt_envelope,
    handle_model_command,
    handle_reasoning_command,
    render_models_async,
)
from raiker.contracts.models import AgentResponse
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import ModelMessage, ModelResponse
from raiker.models.exceptions import ProviderConnectionError
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter
from raiker.models.session_state import ModelSessionState
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


def _event_payloads(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (root / ".raiker" / "events").glob("*.jsonl"):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return rows


class RecordingRouter:
    async def achat(
        self, provider: str, model: str, messages: list[ModelMessage], tools: object = None
    ) -> ModelResponse:
        self.called = (provider, model, messages, tools)
        return ModelResponse(text="async ok")


class FailingRouter:
    async def achat(
        self, provider: str, model: str, messages: list[ModelMessage], tools: object = None
    ) -> ModelResponse:
        raise ProviderConnectionError("provider_unreachable")


def _runtime(tmp_path: Path, router: object) -> RuntimeOrchestrator:
    store = SQLiteStore(tmp_path)
    return RuntimeOrchestrator(
        workspace_root=tmp_path,
        writer=EventLogWriter(store),
        tool_broker=ToolBroker(
            workspace_root=tmp_path,
            policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
            store=store,
            writer=EventLogWriter(store),
        ),
        model_router=router,  # type: ignore[arg-type]
        default_provider=("llama.cpp", "local-gguf"),
    )


def test_orchestrator_ahandle_awaits_router_and_redacts_events(tmp_path: Path) -> None:
    router = RecordingRouter()
    envelope = build_prompt_envelope("RAW_PROMPT_SECRET", session_id="sess_async")
    response = asyncio.run(_runtime(tmp_path, router).ahandle(envelope))
    assert response.message == "async ok"
    assert router.called[0:2] == ("llama.cpp", "local-gguf")
    model_events = [
        e for e in _event_payloads(tmp_path) if e["event_type"].startswith("model_request_")
    ]
    assert {e["event_type"] for e in model_events} >= {
        "model_request_started",
        "model_request_completed",
    }
    assert "RAW_PROMPT_SECRET" not in json.dumps(model_events)
    assert "async ok" not in json.dumps(model_events)


def test_orchestrator_handle_refuses_active_loop(tmp_path: Path) -> None:
    async def main() -> None:
        with pytest.raises(RuntimeError, match="use ahandle"):
            _runtime(tmp_path, RecordingRouter()).handle(build_prompt_envelope("hi"))

    asyncio.run(main())


def test_provider_failure_emits_failed_event_without_prompt(tmp_path: Path) -> None:
    envelope = build_prompt_envelope("RAW_PROMPT_SECRET", session_id="sess_fail")
    response = asyncio.run(_runtime(tmp_path, FailingRouter()).ahandle(envelope))
    assert response.status == "failed"
    # The provider's own reason code survives to the user-facing message: a
    # failed turn says *why* it failed rather than collapsing every cause into
    # one generic "connection failed".
    assert response.message == "model_unavailable: provider_unreachable"
    events = _event_payloads(tmp_path)
    model_events = [e for e in events if e["event_type"].startswith("model_request_")]
    assert any(e["event_type"] == "model_request_failed" for e in model_events)
    forbidden = [
        "RAW_PROMPT_SECRET",
        "RAW_COMPLETION_SECRET",
        "RAW_REASONING_SECRET",
        "Authorization",
        "API_KEY",
        "OPENROUTER_API_KEY",
        "Bearer",
    ]
    serialized = json.dumps(model_events)
    assert all(token not in serialized for token in forbidden)


def test_gateway_async_and_sync_loop_policy(tmp_path: Path) -> None:
    gateway = AgentGateway(tmp_path)
    gateway.runtime.ahandle = lambda envelope: asyncio.sleep(  # type: ignore[method-assign]
        0,
        result=AgentResponse(
            envelope.request_id,
            envelope.session_id,
            envelope.turn_id,
            "completed",
            "ok",
            client=envelope.client,
        ),
    )
    envelope = build_prompt_envelope("hello")
    response = asyncio.run(gateway.submit_prompt_async(envelope))
    assert isinstance(response, AgentResponse)
    assert gateway.default_provider == ("ollama", "gemma4:31b-cloud")

    async def active() -> None:
        with pytest.raises(RuntimeError, match="submit_prompt_async"):
            gateway.submit_prompt(envelope)

    asyncio.run(active())


def test_models_live_listing_and_policy_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ModelProfileRegistry.load()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": [{"id": "local-gguf"}, {"id": "qwen2.5-coder"}]})

    router = ModelRouter(registry)

    def factory(profile: object | None = None) -> ModelProviderFactory:
        return ModelProviderFactory(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    router._factory = factory  # type: ignore[method-assign]
    out = asyncio.run(render_models_async(workspace_root=tmp_path, router=router))
    assert "ollama-local-openai-compatible (selected)" in out
    assert "status: available" in out and "qwen2.5-coder" in out
    assert seen[0] == "http://127.0.0.1:11434/v1/models"
    assert seen[1:] == [
        "http://127.0.0.1:11434/api/ps",
        "http://127.0.0.1:11434/api/show",
        "http://127.0.0.1:11434/api/show",
    ]

    SQLiteStore(tmp_path).save_model_session_state(
        ModelSessionState(session_id="terminal-local", profile_id="openrouter-policy-gated")
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "SHOULD_NOT_PRINT")
    denied = asyncio.run(render_models_async(workspace_root=tmp_path))
    assert "status: policy_denied" in denied
    assert "SHOULD_NOT_PRINT" not in denied and "Authorization" not in denied


def test_models_unavailable(tmp_path: Path) -> None:
    registry = ModelProfileRegistry.load()
    router = ModelRouter(registry)

    class BadFactory:
        def create(self, profile: object) -> object:
            raise ProviderConnectionError("boom")

    def bad_factory(profile: object | None = None) -> BadFactory:
        return BadFactory()

    router._factory = bad_factory  # type: ignore[method-assign, assignment]
    out = asyncio.run(render_models_async(workspace_root=tmp_path, router=router))
    assert "status: unavailable" in out
    assert "reason: provider_unreachable" in out


def test_cli_model_and_reasoning_events_are_safe(tmp_path: Path) -> None:
    assert "Selected model profile" in handle_model_command(
        "/model use raiker-local-llama-cpp", workspace_root=tmp_path
    )
    handle_model_command("/model capabilities", workspace_root=tmp_path)
    handle_model_command("/model health", workspace_root=tmp_path)
    assert "rejected" in handle_reasoning_command(
        "/reasoning set RAW_REASONING_SECRET", workspace_root=tmp_path
    )
    assert "disabled" in handle_reasoning_command("/reasoning off", workspace_root=tmp_path)
    types = [e["event_type"] for e in _event_payloads(tmp_path)]
    assert "model_profile_selected" in types
    assert "model_capabilities_inspected" in types
    assert "model_health_check_started" in types and "model_health_check_completed" in types
    assert "reasoning_setting_rejected" in types and "reasoning_setting_changed" in types
    data = json.dumps(_event_payloads(tmp_path))
    for token in [
        "RAW_PROMPT_SECRET",
        "RAW_COMPLETION_SECRET",
        "RAW_REASONING_SECRET",
        "Authorization",
        "API_KEY",
        "OPENROUTER_API_KEY",
        "Bearer",
    ]:
        assert token not in data


def test_provider_policy_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    r = ModelProfileRegistry.load()
    assert ModelRouter(r).default_provider() == ("ollama", "gemma4:31b-cloud")
    for profile_id in ["lm-studio-local-openai-compatible", "openrouter-policy-gated"]:
        with pytest.raises(Exception) as excinfo:
            ModelProviderFactory(
                policy=ProviderRuntimePolicy(
                    allow_policy_gated_provider=True,
                    allow_private_network_provider=True,
                    allow_hosted_provider=True,
                )
            ).create(r.resolve_profile_id(profile_id))
        assert "model_name_not_configured" in str(excinfo.value)
        assert "SECRET" not in str(excinfo.value)
