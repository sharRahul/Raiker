from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from raiker.contracts.models import ModelProfile
from raiker.models.contracts import ModelCapabilities
from raiker.models.endpoint_policy import EndpointPolicy, validate_endpoint_policy
from raiker.models.exceptions import ProviderConfigurationError, ProviderPolicyError
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.providers.test_provider import DeterministicTestProvider


def capabilities_from_profile(profile: ModelProfile) -> ModelCapabilities:
    raw = profile.raw
    return ModelCapabilities(
        supports_streaming=bool(raw.get("supports_streaming", False)),
        supports_embeddings=bool(raw.get("supports_embeddings", False)),
        supports_tool_calls=bool(raw.get("supports_tool_calls", False)),
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
class ModelProviderFactory:
    allow_test_provider: bool = False
    client: httpx.AsyncClient | None = None

    def create(self, profile: ModelProfile) -> Any:
        provider = profile.provider.replace("_", "-").lower()
        raw = profile.raw
        is_test = provider in {"mock", "test", "deterministic-test"} or bool(raw.get("test_only"))
        if is_test:
            if not (self.allow_test_provider or os.environ.get("RAIKER_TEST_MODE") == "1"):
                raise ProviderPolicyError("deterministic_test_provider_requires_test_mode")
            return DeterministicTestProvider(provider="test", model=profile.model, profile_id=profile.profile_id)
        aliases = {"llama-cpp", "llama.cpp", "llama-cpp-server", "ollama", "lm-studio", "vllm", "openai-compatible", "openrouter"}
        if provider not in aliases:
            raise ProviderConfigurationError(f"unknown_provider:{profile.provider}")
        endpoint = str(raw.get("endpoint") or raw.get("base_url") or "")
        if not endpoint:
            raise ProviderConfigurationError("missing_endpoint")
        policy = EndpointPolicy(
            local_only=profile.local_only,
            requires_network=profile.requires_network,
            requires_egress_policy=bool(raw.get("requires_egress_policy", False)),
            requires_budget_policy=bool(raw.get("requires_budget_policy", False)),
            provider=provider,
            allow_remote_http=bool(raw.get("allow_remote_http", False)),
        )
        validate_endpoint_policy(endpoint, policy)
        if provider == "openrouter" and raw.get("default_state") == "enabled":
            raise ProviderPolicyError("openrouter_must_not_be_enabled_by_default")
        headers: dict[str, str] = {}
        api_key_env = raw.get("api_key_env")
        if isinstance(api_key_env, str) and os.environ.get(api_key_env):
            headers["Authorization"] = f"Bearer {os.environ[api_key_env]}"
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
