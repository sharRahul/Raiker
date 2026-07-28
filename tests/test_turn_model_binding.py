"""Per-turn model binding: an explicit envelope profile choice is honoured,
test-harness profiles and placeholder models fall back to the persisted
selection, and nothing ever silently defaults to a test provider."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import ModelMessage, ModelResponse, ReasoningOptions
from raiker.models.exceptions import ProviderPolicyError
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState
from raiker.runtime.turn_suspension import serialize_messages


def _gateway(tmp_path: Path) -> AgentGateway:
    return AgentGateway(tmp_path)


def _select_anthropic(gateway: AgentGateway, model: str = "claude-opus-4-8") -> None:
    gateway.store.save_model_session_state(
        ModelSessionState(
            session_id=TERMINAL_MODEL_SESSION_ID,
            profile_id="anthropic-hosted",
            model=model,
        )
    )


class TestPromptOptionsDefault:
    def test_model_profile_defaults_to_operator_selection_not_mock(self) -> None:
        assert PromptOptions().model_profile == ""

    def test_per_turn_model_defaults_to_profile_model(self) -> None:
        assert PromptOptions().model == ""

    def test_reasoning_effort_defaults_to_absent(self) -> None:
        assert PromptOptions().reasoning_effort is None


class TestResolveProfileForTurn:
    def test_hosted_placeholder_requires_concrete_selection(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        assert gateway._resolve_profile_for_turn("anthropic-hosted") is None
        _select_anthropic(gateway)
        resolved = gateway._resolve_profile_for_turn("anthropic-hosted")
        assert resolved == ("anthropic", "claude-opus-4-8")

    def test_rejects_unknown_profile(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        assert gateway._resolve_profile_for_turn("no-such-profile") is None

    def test_rejects_placeholder_model_without_selection(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        assert gateway._resolve_profile_for_turn("ollama-local-openai-compatible") is None

    def test_placeholder_model_resolves_via_persisted_selection(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        gateway.store.save_model_session_state(
            ModelSessionState(
                session_id=TERMINAL_MODEL_SESSION_ID,
                profile_id="ollama-local-openai-compatible",
                model="qwen2.5",
            )
        )
        resolved = gateway._resolve_profile_for_turn("ollama-local-openai-compatible")
        assert resolved == ("ollama", "qwen2.5")

    def test_explicit_per_turn_model_wins(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        resolved = gateway._resolve_profile_for_turn(
            "ollama-local-openai-compatible", "qwen2.5"
        )
        assert resolved == ("ollama", "qwen2.5")
        # The concrete choice is registered so the router can resolve it.
        assert gateway.model_registry.find("ollama", "qwen2.5")

    def test_explicit_per_turn_model_overrides_persisted_selection(
        self, tmp_path: Path
    ) -> None:
        gateway = _gateway(tmp_path)
        _select_anthropic(gateway)
        resolved = gateway._resolve_profile_for_turn(
            "anthropic-hosted", "claude-haiku-4-5-20251001"
        )
        assert resolved == ("anthropic", "claude-haiku-4-5-20251001")
        assert gateway.model_registry.find("anthropic", "claude-haiku-4-5-20251001")

    def test_per_turn_model_registration_is_idempotent(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        gateway._resolve_profile_for_turn("ollama-local-openai-compatible", "qwen2.5")
        gateway._resolve_profile_for_turn("ollama-local-openai-compatible", "qwen2.5")
        assert len(gateway.model_registry.find("ollama", "qwen2.5")) == 1

    def test_placeholder_per_turn_model_rejected(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        assert (
            gateway._resolve_profile_for_turn("ollama-local-openai-compatible", "<model>")
            is None
        )


class TestContextModelProfileItem:
    def test_context_reports_the_persisted_selection_not_the_native_default(
        self, tmp_path: Path
    ) -> None:
        from raiker.context.gatherer import ContextGatherer

        gateway = _gateway(tmp_path)  # creates the workspace store
        _select_anthropic(gateway)
        item = ContextGatherer()._model_profile(tmp_path)
        assert item is not None
        assert "profile_id: anthropic-hosted" in item.content
        assert "provider: anthropic" in item.content

    def test_context_falls_back_to_native_default_without_selection(
        self, tmp_path: Path
    ) -> None:
        from raiker.context.gatherer import ContextGatherer

        _gateway(tmp_path)
        item = ContextGatherer()._model_profile(tmp_path)
        assert item is not None
        assert "provider: llama.cpp" in item.content


class TestOrchestratorTurnProvider:
    def test_explicit_choice_wins_and_fallback_is_persisted_selection(
        self, tmp_path: Path
    ) -> None:
        gateway = _gateway(tmp_path)
        runtime = gateway.runtime
        from raiker.contracts.ids import new_id
        from raiker.contracts.models import (
            ClientMetadata,
            PromptEnvelope,
            PromptPayload,
            UserMetadata,
        )

        def envelope(profile: str) -> PromptEnvelope:
            return PromptEnvelope(
                request_id=new_id("req_"),
                session_id=new_id("sess_"),
                turn_id=new_id("turn_"),
                client=ClientMetadata(type="rest", name="test", version="0"),
                user=UserMetadata(),
                prompt=PromptPayload(text="hi"),
                options=PromptOptions(model_profile=profile),
            )

        _select_anthropic(gateway)
        assert runtime._turn_provider(envelope("anthropic-hosted")) == (
            "anthropic",
            "claude-opus-4-8",
        )
        # Unresolvable profile choice: honest fallback to the persisted
        # selection, never a fabricated turn.
        assert runtime._turn_provider(envelope("missing-profile")) == runtime.default_provider
        # No explicit choice: the operator's selection binds the turn.
        assert runtime._turn_provider(envelope("")) == runtime.default_provider


class TestTurnReasoningEffort:
    def _envelope(self, *, profile: str, model: str, effort: str | None) -> PromptEnvelope:
        return PromptEnvelope(
            request_id="req_effort",
            session_id="sess_effort",
            turn_id="turn_effort",
            client=ClientMetadata(type="rest", name="test", version="0"),
            user=UserMetadata(),
            prompt=PromptPayload(text="hi"),
            options=PromptOptions(model_profile=profile, model=model, reasoning_effort=effort),
        )

    def test_rejects_effort_for_profile_that_does_not_declare_it(self, tmp_path: Path) -> None:
        runtime = _gateway(tmp_path).runtime

        with pytest.raises(ProviderPolicyError, match="reasoning_effort_not_supported"):
            runtime._turn_reasoning(  # noqa: SLF001
                self._envelope(profile="ollama-local-openai-compatible", model="qwen2.5", effort="high"),
                "ollama",
                "qwen2.5",
            )

    def test_rejects_undeclared_reasoning_effort_value(self, tmp_path: Path) -> None:
        runtime = _gateway(tmp_path).runtime

        with pytest.raises(ProviderPolicyError, match="reasoning_effort_not_allowed"):
            runtime._turn_reasoning(  # noqa: SLF001
                self._envelope(profile="openai-hosted", model="gpt-4o", effort="extreme"),
                "openai",
                "gpt-4o",
            )

    def test_valid_effort_reaches_router_for_that_turn(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runtime = _gateway(tmp_path).runtime
        seen: list[ReasoningOptions | None] = []

        async def chat_stub(*_args: object, reasoning: ReasoningOptions | None = None, **_kwargs: object) -> ModelResponse:
            seen.append(reasoning)
            return ModelResponse(text="ok", finish_reason="stop")

        monkeypatch.setattr(runtime.model_router, "achat", chat_stub)

        response = asyncio.run(
            runtime._acall_model(  # noqa: SLF001
                self._envelope(profile="openai-hosted", model="gpt-4o", effort="high"),
                [ModelMessage(role="user", content="hi")],
            )
        )

        assert response.text == "ok"
        assert seen == [ReasoningOptions(enabled=True, effort="high")]

    def test_absent_effort_keeps_legacy_router_call_shape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runtime = _gateway(tmp_path).runtime

        async def legacy_chat(
            _provider: str,
            _model: str,
            _messages: list[ModelMessage],
            _tools: object,
        ) -> ModelResponse:
            return ModelResponse(text="legacy router called", finish_reason="stop")

        monkeypatch.setattr(runtime.model_router, "achat", legacy_chat)

        response = asyncio.run(
            runtime._acall_model(  # noqa: SLF001
                self._envelope(profile="openai-hosted", model="gpt-4o", effort=None),
                [ModelMessage(role="user", content="hi")],
            )
        )

        assert response.text == "legacy router called"

    def test_unresolved_explicit_profile_with_effort_never_falls_back_to_a_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runtime = _gateway(tmp_path).runtime
        called = False

        async def chat_stub(*_args: object, **_kwargs: object) -> ModelResponse:
            nonlocal called
            called = True
            return ModelResponse(text="must not run", finish_reason="stop")

        monkeypatch.setattr(runtime.model_router, "achat", chat_stub)

        with pytest.raises(ProviderPolicyError, match="reasoning_effort_profile_unresolved"):
            asyncio.run(
                runtime._acall_model(  # noqa: SLF001
                    self._envelope(profile="missing-profile", model="missing-model", effort="high"),
                    [ModelMessage(role="user", content="hi")],
                )
            )
        assert called is False

    def test_manual_approval_resume_preserves_reasoning_effort(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        approval_id = "appr_effort"
        gateway.store.insert_suspended_turn(
            {
                "approval_id": approval_id,
                "session_id": "sess_effort",
                "turn_id": "turn_effort",
                "request_id": "req_effort",
                "principal_id": gateway.tool_broker.principal_id,
                "action_id": "act_effort",
                "tool_name": "write_file",
                "call_id": "call_effort",
                "prompt_text": "write the file",
                "messages_json": serialize_messages([ModelMessage(role="user", content="write the file")]),
                "options_json": json.dumps(
                    {
                        "planning_mode": "auto",
                        "approval_mode": "manual",
                        "model_profile": "openai-hosted",
                        "model": "gpt-4o",
                        "reasoning_effort": "high",
                        "max_tool_calls": 10,
                    }
                ),
                "client_json": json.dumps({"type": "web_ui", "name": "test", "version": "1"}),
                "tool_calls_made": 1,
            }
        )
        assert gateway.store.record_suspended_turn_outcome(approval_id, json.dumps({"status": "success"}))

        restored, _messages, _calls = gateway._restore_suspended_turn(approval_id)  # noqa: SLF001

        assert restored.options.approval_mode == "manual"
        assert restored.options.reasoning_effort == "high"
