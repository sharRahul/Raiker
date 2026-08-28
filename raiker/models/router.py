from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
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
    ProviderConfigurationError,
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


_VALID_CACHE_TTLS = {"5m", "1h"}


def _cache_ttl(profile: ModelProfile) -> str | None:
    """Read the profile cache TTL, normalized to a supported value or None."""
    value = str(profile.raw.get("prompt_cache_ttl", "") or "").strip()
    return value if value in _VALID_CACHE_TTLS else None


class ModelRouter:
    def __init__(
        self,
        registry: ModelProfileRegistry,
        writer: EventLogWriter | None = None,
        *,
        runtime_policy: ProviderRuntimePolicy | None = None,
        connection_resolver: Callable[[str], dict[str, str] | None] | None = None,
    ) -> None:
        self.registry = registry
        self.writer = writer
        if runtime_policy is None and writer is not None:
            from raiker.models.policy_state import provider_runtime_policy_from_gates

            runtime_policy = provider_runtime_policy_from_gates(writer.store)
        self.runtime_policy = runtime_policy or ProviderRuntimePolicy()
        self.connection_resolver = connection_resolver
        self.active_profile_id: str | None = None
        self.reasoning: ReasoningOptions | None = None

    def _factory(self, profile: ModelProfile) -> ModelProviderFactory:
        connection = (
            self.connection_resolver(profile.profile_id) if self.connection_resolver else None
        )
        return ModelProviderFactory(policy=self.runtime_policy, connection=connection)

    def _profile(self, provider: str, model: str) -> ModelProfile:
        return self.registry.resolve(provider, model)

    def _request(
        self,
        profile: ModelProfile,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None,
        *,
        stream: bool,
        reasoning: ReasoningOptions | None = None,
        response_schema: dict[str, object] | None = None,
        response_schema_name: str = "raiker_response",
        max_tokens: int | None = None,
    ) -> ModelRequest:
        return ModelRequest(
            profile.profile_id,
            provider,
            model,
            messages,
            tools,
            temperature=float(profile.raw.get("temperature", 0.2)),
            max_tokens=(
                max_tokens if max_tokens is not None else int(profile.raw.get("max_tokens", 1024))
            ),
            stream=stream,
            tool_call_mode=str(profile.raw.get("tool_call_mode", "text_json")),
            reasoning=reasoning if reasoning is not None else self.reasoning,
            cache_ttl=_cache_ttl(profile),
            response_schema=response_schema,
            response_schema_name=response_schema_name,
        )

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
        *,
        reasoning: ReasoningOptions | None = None,
        response_schema: dict[str, object] | None = None,
        response_schema_name: str = "raiker_response",
        max_tokens: int | None = None,
    ) -> ModelResponse:
        profile = self._profile(provider, model)
        model_provider = self._factory(profile).create(profile)
        request = self._request(
            profile,
            model_provider.provider,
            model_provider.model,
            messages,
            tools,
            stream=False,
            reasoning=reasoning,
            response_schema=response_schema,
            response_schema_name=response_schema_name,
            max_tokens=max_tokens,
        )
        try:
            return await model_provider.chat(request)
        finally:
            await model_provider.aclose()

    async def aprobe_model(self, profile: ModelProfile) -> None:
        """Run the smallest real completion that proves a hosted model can execute.

        Catalogue membership alone does not prove billing/access is usable. This
        preflight is only called by an explicit owner readiness check and asks for
        one output token with no tools, cache write, reasoning, or response schema.
        """
        model_provider = self._factory(profile).create(profile)
        request = ModelRequest(
            profile.profile_id,
            model_provider.provider,
            model_provider.model,
            [ModelMessage("user", ".")],
            max_tokens=1,
            stream=False,
        )
        try:
            await model_provider.chat(request)
        finally:
            await model_provider.aclose()

    async def astream(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
        *,
        reasoning: ReasoningOptions | None = None,
        response_schema: dict[str, object] | None = None,
        response_schema_name: str = "raiker_response",
    ) -> AsyncIterator[ModelStreamEvent]:
        profile = self._profile(provider, model)
        model_provider = self._factory(profile).create(profile)
        request = self._request(
            profile,
            model_provider.provider,
            model_provider.model,
            messages,
            tools,
            stream=True,
            reasoning=reasoning,
            response_schema=response_schema,
            response_schema_name=response_schema_name,
        )
        try:
            async for event in model_provider.stream_chat(request):
                yield event
        finally:
            await model_provider.aclose()

    async def aembed(self, provider: str, model: str, text: str) -> EmbeddingResponse:
        profile = self._profile(provider, model)
        model_provider = self._factory(profile).create(profile)
        embedding_model = str(profile.raw.get("embedding_model") or model_provider.model)
        if "<" in embedding_model or ">" in embedding_model:
            embedding_model = model_provider.model
        if not embedding_model:
            await model_provider.aclose()
            raise ProviderConfigurationError("embedding_model_not_configured")
        try:
            return await model_provider.embed(
                EmbeddingRequest(profile.profile_id, model_provider.provider, embedding_model, text)
            )
        finally:
            await model_provider.aclose()

    async def alist_models_for_profile(self, profile: ModelProfile) -> list[ProviderModelInfo]:
        """List models at a profile endpoint without requiring a concrete chat model."""
        model_provider = self._factory(profile).create(profile, require_model=False)
        try:
            return await model_provider.list_models()
        finally:
            await model_provider.aclose()

    async def ahealth(self, provider: str, model: str) -> ProviderHealth:
        profile = self._profile(provider, model)
        model_provider = self._factory(profile).create(profile)
        try:
            return await model_provider.health()
        finally:
            await model_provider.aclose()

    async def alist_models(self, provider: str, model: str) -> list[ProviderModelInfo]:
        profile = self._profile(provider, model)
        model_provider = self._factory(profile).create(profile)
        try:
            return await model_provider.list_models()
        finally:
            await model_provider.aclose()

    def supports_vision(self, provider: str, model: str) -> bool:
        """Whether the resolved profile declares image input support, fail-closed."""
        try:
            return capabilities_from_profile(self._profile(provider, model)).supports_vision
        except (RegistryError, ValueError):
            return False

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.achat(provider, model, messages, tools))
        raise RuntimeError("use achat inside an active event loop")

    def generate(
        self,
        provider: str,
        model: str,
        prompt: str,
        context: dict[str, object] | None = None,
    ) -> str:
        return self.chat(provider, model, [ModelMessage(role="user", content=prompt)]).text

    def default_provider(self, *, health_timeout: float = 1.0) -> tuple[str, str]:
        for profile in self.registry.list_profiles():
            if profile.raw.get("is_native_default"):
                return profile.provider, profile.model
        raise RegistryError("no_real_model_provider_available")

    def select_profile(self, profile_id: str) -> ModelProfile:
        profile = self.registry.resolve_profile_id(profile_id)
        self._factory(profile).create(profile)
        self.active_profile_id = profile.profile_id
        return profile

    def set_reasoning(self, value: str) -> str:
        profile = (
            self.registry.resolve_profile_id(self.active_profile_id)
            if self.active_profile_id
            else self.registry.list_profiles()[0]
        )
        capabilities = capabilities_from_profile(profile)
        if value == "off":
            self.reasoning = ReasoningOptions(enabled=False)
            return "Reasoning controls disabled."
        if not capabilities.supports_reasoning:
            raise ProviderPolicyError("reasoning_not_supported")
        if value in capabilities.reasoning_effort_values and capabilities.supports_reasoning_effort:
            self.reasoning = ReasoningOptions(enabled=True, effort=value)
            return f"Reasoning effort set to {value}."
        if value in capabilities.reasoning_modes:
            self.reasoning = ReasoningOptions(enabled=True)
            return f"Reasoning mode set to {value}."
        raise ProviderPolicyError("reasoning_setting_rejected")

    def launch(
        self,
        provider: str,
        model: str,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata,
    ) -> ModelLaunchResult:
        if self.writer is not None:
            self.writer.append(
                make_event(
                    session_id=session_id,
                    turn_id=turn_id,
                    event_type="model_launch_requested",
                    actor="model_router",
                    payload={"provider": provider, "model": model},
                    client=client,
                )
            )
        try:
            profile = self.registry.resolve(provider, model)
            ModelProviderFactory(policy=self.runtime_policy).create(profile)
        except (RegistryError, ModelProviderError) as exc:
            if self.writer is not None:
                self.writer.append(
                    make_event(
                        session_id=session_id,
                        turn_id=turn_id,
                        event_type="model_launch_failed",
                        actor="model_router",
                        payload={
                            "provider": provider,
                            "model": model,
                            "error_class": type(exc).__name__,
                        },
                        client=client,
                    )
                )
            return ModelLaunchResult("failed", None, str(exc))
        if self.writer is not None:
            self.writer.append(
                make_event(
                    session_id=session_id,
                    turn_id=turn_id,
                    event_type="model_launch_completed",
                    actor="model_router",
                    payload={
                        "profile_id": profile.profile_id,
                        "provider": profile.provider,
                        "model": profile.model,
                    },
                    client=client,
                )
            )
        return ModelLaunchResult(
            "completed", profile, f"Resolved model profile {profile.profile_id}"
        )
