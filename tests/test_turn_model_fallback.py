"""User-owned model fallback sequence.

When the bound model provider is unavailable (no network, timeout, non-responsive
host, or a policy denial), the turn walks the user-owned ordered fallback
sequence and tries the next candidate — typically a local backend. Each candidate
is still resolved and gated through the model router, so fallback never bypasses
provider policy. When every candidate fails the turn fails closed, exactly as a
single-provider turn does today.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.events.query import EventViewer
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import ModelResponse
from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderPolicyError,
    ProviderRateLimitError,
)
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState


def _gateway(tmp_path: Path) -> AgentGateway:
    return AgentGateway(tmp_path)


def _select_anthropic(gw: AgentGateway, model: str = "claude-opus-4-8") -> None:
    gw.store.save_model_session_state(
        ModelSessionState(
            session_id=TERMINAL_MODEL_SESSION_ID,
            profile_id="anthropic-hosted",
            model=model,
        )
    )


def _envelope() -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="rest", name="test", version="0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="hi"),
        options=PromptOptions(model_profile=""),
    )


class TestStoreRoundTrip:
    def test_empty_by_default(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        assert gw.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID) == []

    def test_save_and_load_ordered(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        gw.store.save_model_fallback_sequence(
            TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted", "raiker-local-llama-cpp"]
        )
        assert gw.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID) == [
            "anthropic-hosted",
            "raiker-local-llama-cpp",
        ]

    def test_save_empty_clears(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted"])
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, [])
        assert gw.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID) == []


class TestResolveFallbackChain:
    def test_resolves_concrete_profiles_in_order(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        _select_anthropic(gw)
        gw.store.save_model_fallback_sequence(
            TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted", "raiker-local-llama-cpp"]
        )
        assert gw._resolve_fallback_chain() == [
            ("anthropic", "claude-opus-4-8"),
            ("llama.cpp", "local-gguf"),
        ]

    def test_drops_test_and_unresolved_placeholder(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        gw.store.save_model_fallback_sequence(
            TERMINAL_MODEL_SESSION_ID,
            ["missing-profile", "ollama-local-openai-compatible", "raiker-local-llama-cpp"],
        )
        # The unknown profile and the placeholder-<model> ollama profile (no
        # persisted concrete model) drop out; only the concrete local backend remains.
        assert gw._resolve_fallback_chain() == [("llama.cpp", "local-gguf")]

    def test_deduplicates(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        gw.store.save_model_fallback_sequence(
            TERMINAL_MODEL_SESSION_ID, ["raiker-local-llama-cpp", "raiker-local-llama-cpp"]
        )
        assert gw._resolve_fallback_chain() == [("llama.cpp", "local-gguf")]


class TestProviderChain:
    def test_primary_then_fallback_deduped(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        _select_anthropic(gw)
        # Primary is the native llama.cpp default; fallback lists it again + anthropic.
        gw.store.save_model_fallback_sequence(
            TERMINAL_MODEL_SESSION_ID, ["raiker-local-llama-cpp", "anthropic-hosted"]
        )
        chain = gw.runtime._provider_chain(_envelope())
        assert chain[0] == ("llama.cpp", "local-gguf")
        assert chain == [("llama.cpp", "local-gguf"), ("anthropic", "claude-opus-4-8")]


class TestFallbackEngagement:
    def test_fallback_engages_when_primary_fails(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        _select_anthropic(gw)
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted"])

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            if provider == "llama.cpp":
                raise ProviderConnectionError("connection refused")
            return ModelResponse(text=f"hello from {provider}", finish_reason="stop")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.finish_reason == "stop"
        assert response.text == "hello from anthropic"

    def test_emits_fallback_event(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        _select_anthropic(gw)
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted"])
        env = _envelope()

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            if provider == "llama.cpp":
                raise ProviderConnectionError("down")
            return ModelResponse(text="ok", finish_reason="stop")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        asyncio.run(gw.runtime._acall_model(env, []))
        events = gw.store.list_event_index(turn_id=env.turn_id, limit=100)
        engaged = [e for e in events if e["event_type"] == "model_fallback_engaged"]
        assert len(engaged) == 1

    def test_policy_denied_fallback_is_skipped(self, tmp_path: Path) -> None:
        """A hosted fallback that policy denies is skipped, not fatal — the next
        (local) candidate is tried. Fallback never opens a denied provider."""
        gw = _gateway(tmp_path)
        gw.store.save_model_session_state(
            ModelSessionState(
                session_id=TERMINAL_MODEL_SESSION_ID,
                profile_id="ollama-local-openai-compatible",
                model="qwen2.5",
            )
        )
        gw.default_provider = ("openai", "gpt-4o-mini")
        gw.runtime.default_provider = ("openai", "gpt-4o-mini")
        gw.store.save_model_fallback_sequence(
            TERMINAL_MODEL_SESSION_ID, ["ollama-local-openai-compatible"]
        )

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            if provider == "openai":
                raise ProviderPolicyError("hosted_model_runtime_disabled")
            return ModelResponse(text="from local", finish_reason="stop")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.text == "from local"

    def test_all_providers_fail_closed(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted"])

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderConnectionError("everything is down")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.finish_reason == "error"
        assert response.text == "model_unavailable: provider_connection_failed"

    def test_no_fallback_configured_still_fails_closed(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderConnectionError("down")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.finish_reason == "error"


class TestFailureReasonIsSpecific:
    """A failed turn must say *why* it failed, not just that it failed.

    The provider layer already classifies its failures precisely. Collapsing all
    of them into "provider_connection_failed" sends the owner to debug their
    network when the real cause is an invalid credential — the exact confusion a
    live run against a rejected API key produced.
    """

    def test_authentication_failure_is_not_reported_as_a_connection_failure(
        self, tmp_path: Path
    ) -> None:
        gw = _gateway(tmp_path)

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderAuthenticationError("provider_auth_failed:http_401")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.finish_reason == "error"
        assert response.text == "model_unavailable: provider_auth_failed:http_401"
        assert "connection" not in response.text

    def test_missing_model_names_the_model_not_the_network(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderModelNotFoundError("model_not_found:local-gguf")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.text == "model_unavailable: model_not_found:local-gguf"

    def test_rate_limit_is_reported_as_a_rate_limit(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderRateLimitError("provider_rate_limited")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.text == "model_unavailable: provider_rate_limited"

    def test_prose_message_falls_back_to_the_class_code(self, tmp_path: Path) -> None:
        # A provider that raises prose rather than a code must not have that
        # prose promoted into an event payload as if it were one.
        gw = _gateway(tmp_path)

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderConnectionError("the socket went away, sorry")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.text == "model_unavailable: provider_connection_failed"

    def test_last_providers_reason_survives_the_fallback_chain(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        _select_anthropic(gw)
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, ["anthropic-hosted"])

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            if provider == "llama.cpp":
                raise ProviderConnectionError("provider_connection_failed")
            raise ProviderAuthenticationError("provider_auth_failed:http_401")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        response = asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert response.text == "model_unavailable: provider_auth_failed:http_401"

    def test_the_event_payload_carries_the_same_specific_code(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        env = _envelope()

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            raise ProviderAuthenticationError("provider_auth_failed:http_401")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        asyncio.run(gw.runtime._acall_model(env, []))

        viewer = EventViewer(gw.store)
        failures = viewer.list_events(
            session_id=env.session_id, event_type="model_request_failed"
        )
        assert failures, "no model_request_failed event was recorded"
        record = viewer.read_event_payload(str(failures[-1]["event_id"]))
        assert record is not None
        payload = record.get("payload", record)
        assert payload["safe_error_code"] == "provider_auth_failed:http_401"
        assert payload["error_class"] == "ProviderAuthenticationError"
