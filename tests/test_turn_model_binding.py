"""Per-turn model binding: an explicit envelope profile choice is honoured,
test-harness profiles and placeholder models fall back to the persisted
selection, and nothing ever silently defaults to a test provider."""

from __future__ import annotations

from pathlib import Path

from raiker.contracts.models import PromptOptions
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState


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
