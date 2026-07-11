from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from raiker.contracts.models import ModelProfile
from raiker.models.contracts import ModelCapabilities
from raiker.models.endpoint_policy import (
    EndpointPolicy,
    enforce_model_egress,
    validate_endpoint_policy,
)
from raiker.models.exceptions import ProviderConfigurationError, ProviderPolicyError
from raiker.models.providers.anthropic_messages import AsyncAnthropicMessagesProvider
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.providers.test_provider import DeterministicTestProvider


def capabilities_from_profile(profile: ModelProfile) -> ModelCapabilities:
    raw = profile.raw
    return ModelCapabilities(
        supports_streaming=bool(raw.get("supports_streaming", False)),
        supports_embeddings=bool(raw.get("supports_embeddings", False)),
        supports_tool_calls=bool(raw.get("supports_tool_calls", False)),
        supports_vision=bool(raw.get("supports_vision", False)),
        supports_json_schema=bool(raw.get("supports_json_schema", False)),
        supports_reasoning=bool(raw.get("supports_reasoning", False)),
        supports_reasoning_effort=bool(raw.get("supports_reasoning_effort", False)),
        supports_reasoning_budget_tokens=bool(raw.get("supports_reasoning_budget_tokens", False)),
        supports_reasoning_summary=bool(raw.get("supports_reasoning_summary", False)),
        reasoning_effort_values=tuple(str(v) for v in raw.get("reasoning_effort_values", [])),
        reasoning_modes=tuple(str(v) for v in raw.get("reasoning_modes", [])),
        reasoning_trace_visible=bool(raw.get("reasoning_trace_visible", False)),
    )


@dataclass(frozen=True)
class ProviderRuntimePolicy:
    allow_test_provider: bool = False
    allow_policy_gated_provider: bool = False
    allow_hosted_provider: bool = False
    allow_private_network_provider: bool = False
    require_api_key_for_hosted: bool = True
    test_mode: bool = False


@dataclass(frozen=True)
class ModelProviderFactory:
    allow_test_provider: bool = False
    allow_policy_gated_provider: bool = False
    allow_hosted_provider: bool = False
    allow_private_network_provider: bool = False
    require_api_key_for_hosted: bool = True
    test_mode: bool = False
    client: httpx.AsyncClient | None = None

    def __init__(self, allow_test_provider: bool = False, client: httpx.AsyncClient | None = None, policy: ProviderRuntimePolicy | None = None, **kwargs: Any) -> None:
        object.__setattr__(self, "client", client)
        if policy is None:
            policy = ProviderRuntimePolicy(allow_test_provider=allow_test_provider, **kwargs)
        object.__setattr__(self, "allow_test_provider", policy.allow_test_provider)
        object.__setattr__(self, "allow_policy_gated_provider", policy.allow_policy_gated_provider)
        object.__setattr__(self, "allow_hosted_provider", policy.allow_hosted_provider)
        object.__setattr__(self, "allow_private_network_provider", policy.allow_private_network_provider)
        object.__setattr__(self, "require_api_key_for_hosted", policy.require_api_key_for_hosted)
        object.__setattr__(self, "test_mode", policy.test_mode)

    def create(self, profile: ModelProfile, *, require_model: bool = True) -> Any:
        provider = profile.provider.replace("_", "-").lower()
        raw = profile.raw
        is_test = provider in {"mock", "test", "deterministic-test"} or bool(raw.get("test_only"))
        if is_test:
            if not (self.allow_test_provider or self.test_mode or os.environ.get("RAIKER_TEST_MODE") == "1"):
                raise ProviderPolicyError("deterministic_test_provider_requires_test_mode")
            return DeterministicTestProvider(provider="test", model=profile.model, profile_id=profile.profile_id)
        aliases = {
            "llama-cpp", "llama.cpp", "llama-cpp-server", "ollama", "lm-studio", "vllm",
            "openai-compatible", "openrouter",
            # Hosted providers: OpenAI + Gemini speak the OpenAI-compatible
            # protocol; Anthropic uses the native Messages API adapter.
            "openai", "gemini", "anthropic",
        }
        if provider not in aliases:
            raise ProviderConfigurationError(f"unknown_provider:{profile.provider}")
        state = str(raw.get("default_state", ""))
        if state == "enabled_for_tests_only" and not (self.allow_test_provider or self.test_mode or os.environ.get("RAIKER_TEST_MODE") == "1"):
            raise ProviderPolicyError("test_only_profile_requires_test_mode")
        if state == "disabled_until_policy_approved" and not self.allow_policy_gated_provider:
            raise ProviderPolicyError("provider_requires_explicit_policy_approval")
        model_name = str(profile.model or "")
        if require_model and (not model_name or "<" in model_name or ">" in model_name):
            raise ProviderConfigurationError("model_name_not_configured")
        endpoint = str(raw.get("endpoint") or raw.get("base_url") or "")
        if not endpoint or "<" in endpoint:
            raise ProviderConfigurationError("missing_endpoint")
        policy = EndpointPolicy(
            local_only=profile.local_only,
            requires_network=profile.requires_network,
            requires_egress_policy=bool(raw.get("requires_egress_policy", False)),
            requires_budget_policy=bool(raw.get("requires_budget_policy", False)),
            provider=provider,
            allow_remote_http=bool(raw.get("allow_remote_http", False)),
        )
        endpoint_kind = validate_endpoint_policy(endpoint, policy)
        if endpoint_kind == "private_network" and not self.allow_private_network_provider:
            raise ProviderPolicyError("private_network_provider_requires_explicit_policy")
        if endpoint_kind == "remote_hosted" and not self.allow_hosted_provider:
            raise ProviderPolicyError("hosted_provider_requires_explicit_policy")
        # Off-machine endpoints must also be on the owner egress allowlist —
        # fail closed even when the capability gate / runtime policy allows them.
        enforce_model_egress(endpoint, kind=endpoint_kind)
        if provider == "openrouter" and raw.get("default_state") == "enabled":
            raise ProviderPolicyError("openrouter_must_not_be_enabled_by_default")
        headers: dict[str, str] = {}
        api_key_env = raw.get("api_key_env")
        if provider == "openrouter":
            if not (raw.get("requires_network") and raw.get("requires_egress_policy") and raw.get("requires_budget_policy")):
                raise ProviderPolicyError("openrouter_requires_hosted_egress_budget_policy")
            if urlparse(endpoint).scheme != "https":
                raise ProviderPolicyError("openrouter_requires_https")
            if not isinstance(api_key_env, str) or not os.environ.get(api_key_env):
                raise ProviderConfigurationError("openrouter_api_key_missing")
        if (
            endpoint_kind == "remote_hosted"
            and self.require_api_key_for_hosted
            and (not isinstance(api_key_env, str) or not os.environ.get(api_key_env))
        ):
            raise ProviderConfigurationError("hosted_api_key_missing")
        api_key = os.environ.get(api_key_env, "") if isinstance(api_key_env, str) else ""
        if provider == "anthropic":
            if api_key:
                headers["x-api-key"] = api_key
            return AsyncAnthropicMessagesProvider(
                profile_id=profile.profile_id,
                provider=profile.provider,
                model=str(raw.get("served_model_name", profile.model)),
                endpoint=endpoint,
                capabilities=capabilities_from_profile(profile),
                timeout=float(raw.get("timeout_seconds", 120.0)),
                max_tokens=int(raw.get("max_tokens", 1024)),
                models_path=str(raw.get("models_path", "/v1/models")),
                chat_path=str(raw.get("chat_path", "/v1/messages")),
                extra_headers=headers,
                client=self.client,
            )
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        raw_extra = raw.get("extra_headers")
        extra: dict[Any, Any] = raw_extra if isinstance(raw_extra, dict) else {}
        for key, value in extra.items():
            if isinstance(key, str) and isinstance(value, str):
                headers[key] = value
        return AsyncOpenAICompatibleProvider(
            profile_id=profile.profile_id,
            provider=profile.provider,
            model=str(raw.get("served_model_name", profile.model)),
            endpoint=endpoint,
            capabilities=capabilities_from_profile(profile),
            timeout=float(raw.get("timeout_seconds", 120.0)),
            temperature=float(raw.get("temperature", 0.2)),
            max_tokens=int(raw.get("max_tokens", 1024)),
            tool_call_mode=str(raw.get("tool_call_mode", "text_json")),
            health_path=str(raw.get("health_path", "/health")),
            models_path=str(raw.get("models_path", "/v1/models")),
            chat_path=str(raw.get("chat_path", "/v1/chat/completions")),
            embeddings_path=str(raw.get("embeddings_path", "/v1/embeddings")),
            extra_headers=headers,
            client=self.client,
        )
