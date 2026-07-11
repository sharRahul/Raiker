from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from raiker.contracts.models import ClientMetadata, ModelProfile
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderModelInfo,
    ReasoningOptions,
    ToolSpec,
)
from raiker.models.exceptions import (
    ModelProviderError,
    ProviderPolicyError,
)
from raiker.models.factory import (
    ModelProviderFactory,
    ProviderRuntimePolicy,
    capabilities_from_profile,
)
from raiker.models.health import ProviderHealth
from raiker.models.registry import ModelProfileRegistry, RegistryError


@dataclass(frozen=True)
class ModelLaunchResult:
    status: str
    profile: ModelProfile | None
    message: str


# Accepted prompt-cache TTL breakpoints. Anything else (including the common
# unset/empty case) means "no caching" and is normalised to None.
_VALID_CACHE_TTLS = {"5m", "1h"}


def _cache_ttl(profile: ModelProfile) -> str | None:
    """Read the profile's ``prompt_cache_ttl`` config, validated to {"5m","1h"} or None."""
    value = str(profile.raw.get("prompt_cache_ttl", "") or "").strip()
    return value if value in _VALID_CACHE_TTLS else None


class ModelRouter:
    def __init__(self, registry: ModelProfileRegistry, writer: EventLogWriter | None = None, *, allow_test_provider: bool = False, runtime_policy: ProviderRuntimePolicy | None = None) -> None:
        self.registry = registry
        self.writer = writer
        self.allow_test_provider = allow_test_provider
        self.runtime_policy = runtime_policy or ProviderRuntimePolicy(allow_test_provider=allow_test_provider)
        self.active_profile_id: str | None = None
        self.reasoning: ReasoningOptions | None = None

    def _factory(self) -> ModelProviderFactory:
        return ModelProviderFactory(policy=self.runtime_policy)

    def _profile(self, provider: str, model: str) -> ModelProfile:
        return self.registry.resolve(provider, model)

    async def achat(self, provider: str, model: str, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec] | None = None) -> ModelResponse:
        profile = self._profile(provider, model)
        p = self._factory().create(profile)
        request = ModelRequest(profile.profile_id, p.provider, p.model, messages, tools, temperature=float(profile.raw.get("temperature", 0.2)), max_tokens=int(profile.raw.get("max_tokens", 1024)), tool_call_mode=str(profile.raw.get("tool_call_mode", "text_json")), reasoning=self.reasoning, cache_ttl=_cache_ttl(profile))
        try:
            return await p.chat(request)
        finally:
            await p.aclose()

    async def astream(self, provider: str, model: str, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec] | None = None) -> AsyncIterator[ModelStreamEvent]:
        profile = self._profile(provider, model)
        p = self._factory().create(profile)
        request = ModelRequest(profile.profile_id, p.provider, p.model, messages, tools, stream=True, reasoning=self.reasoning, cache_ttl=_cache_ttl(profile))
        try:
            async for event in p.stream_chat(request):
                yield event
        finally:
            await p.aclose()

    async def aembed(self, provider: str, model: str, text: str) -> EmbeddingResponse:
        profile = self._profile(provider, model)
        p = self._factory().create(profile)
        try:
            return await p.embed(EmbeddingRequest(profile.profile_id, p.provider, p.model, text))
        finally:
            await p.aclose()

    async def alist_models_for_profile(self, profile: ModelProfile) -> list[ProviderModelInfo]:
        """List models served by ``profile``'s endpoint without requiring a concrete model name.

        Used to auto-detect the served model for profiles that ship a placeholder model
        (e.g. Ollama / LM Studio). Endpoint and provider policy are still enforced.
        """
        p = self._factory().create(profile, require_model=False)
        try:
            return await p.list_models()
        finally:
            await p.aclose()

    async def ahealth(self, provider: str, model: str) -> ProviderHealth:
        profile = self._profile(provider, model)
        p = self._factory().create(profile)
        try:
            return await p.health()
        finally:
            await p.aclose()

    async def alist_models(self, provider: str, model: str) -> list[ProviderModelInfo]:
        profile = self._profile(provider, model)
        p = self._factory().create(profile)
        try:
            return await p.list_models()
        finally:
            await p.aclose()

    def supports_vision(self, provider: str, model: str) -> bool:
        """Whether the resolved profile declares image (vision) input support.

        Fails closed: an unresolvable profile means no vision — the caller must
        withhold image content rather than guess.
        """
        try:
            return capabilities_from_profile(self._profile(provider, model)).supports_vision
        except (RegistryError, ValueError):
            return False

    def chat(self, provider: str, model: str, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec] | None = None) -> ModelResponse:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.achat(provider, model, messages, tools))
        raise RuntimeError("use achat inside an active event loop")

    def generate(self, provider: str, model: str, prompt: str, context: dict[str, object] | None = None) -> str:
        return self.chat(provider, model, [ModelMessage(role="user", content=prompt)]).text

    def default_provider(self, *, health_timeout: float = 1.0) -> tuple[str, str]:
        for profile in self.registry.list_profiles():
            if profile.provider == "llama.cpp":
                return profile.provider, profile.model
        raise RegistryError("no_real_model_provider_available")

    def select_profile(self, profile_id: str) -> ModelProfile:
        profile = self.registry.resolve_profile_id(profile_id)
        self._factory().create(profile)
        self.active_profile_id = profile.profile_id
        return profile

    def set_reasoning(self, value: str) -> str:
        profile = self.registry.resolve_profile_id(self.active_profile_id) if self.active_profile_id else self.registry.list_profiles()[0]
        caps = capabilities_from_profile(profile)
        if value == "off":
            self.reasoning = ReasoningOptions(enabled=False)
            return "Reasoning controls disabled."
        if not caps.supports_reasoning:
            raise ProviderPolicyError("reasoning_not_supported")
        if value in caps.reasoning_effort_values and caps.supports_reasoning_effort:
            self.reasoning = ReasoningOptions(enabled=True, effort=value)
            return f"Reasoning effort set to {value}."
        if value in caps.reasoning_modes:
            self.reasoning = ReasoningOptions(enabled=value != "off", summary=None)
            return f"Reasoning mode set to {value}."
        raise ProviderPolicyError("reasoning_setting_rejected")

    def launch(self, provider: str, model: str, *, session_id: str, turn_id: str | None, client: ClientMetadata) -> ModelLaunchResult:
        if self.writer is not None:
            self.writer.append(make_event(session_id=session_id, turn_id=turn_id, event_type="model_launch_requested", actor="model_router", payload={"provider": provider, "model": model}, client=client))
        try:
            profile = self.registry.resolve(provider, model)
            policy = ProviderRuntimePolicy(allow_test_provider=self.allow_test_provider or client.type == "test_harness")
            ModelProviderFactory(policy=policy).create(profile)
        except (RegistryError, ModelProviderError) as exc:
            if self.writer is not None:
                self.writer.append(make_event(session_id=session_id, turn_id=turn_id, event_type="model_launch_failed", actor="model_router", payload={"provider": provider, "model": model, "error_class": type(exc).__name__}, client=client))
            return ModelLaunchResult("failed", None, str(exc))
        if self.writer is not None:
            self.writer.append(make_event(session_id=session_id, turn_id=turn_id, event_type="model_launch_completed", actor="model_router", payload={"profile_id": profile.profile_id, "provider": profile.provider, "model": profile.model}, client=client))
        return ModelLaunchResult("completed", profile, f"Resolved model profile {profile.profile_id}")
