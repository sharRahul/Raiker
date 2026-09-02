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
from raiker.models.providers.codex_app_server import AsyncCodexAppServerProvider
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider


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
    allow_policy_gated_provider: bool = False
    allow_hosted_provider: bool = False
    allow_private_network_provider: bool = False
    require_api_key_for_hosted: bool = True


@dataclass(frozen=True)
class ModelProviderFactory:
    allow_policy_gated_provider: bool = False
    allow_hosted_provider: bool = False
    allow_private_network_provider: bool = False
    require_api_key_for_hosted: bool = True
    client: httpx.AsyncClient | None = None
    connection: dict[str, str] | None = None

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        policy: ProviderRuntimePolicy | None = None,
        connection: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        object.__setattr__(self, "client", client)
        object.__setattr__(self, "connection", connection)
        if policy is None:
            policy = ProviderRuntimePolicy(**kwargs)
        object.__setattr__(self, "allow_policy_gated_provider", policy.allow_policy_gated_provider)
        object.__setattr__(self, "allow_hosted_provider", policy.allow_hosted_provider)
        object.__setattr__(
            self, "allow_private_network_provider", policy.allow_private_network_provider
        )
        object.__setattr__(self, "require_api_key_for_hosted", policy.require_api_key_for_hosted)

    def _configured_endpoint(self, raw: dict[str, Any]) -> str:
        if self.connection and self.connection.get("endpoint", "").strip():
            return self.connection["endpoint"].strip()
        endpoint_env = raw.get("endpoint_env")
        if isinstance(endpoint_env, str) and endpoint_env:
            configured = os.environ.get(endpoint_env, "").strip()
            if configured:
                return configured
        return str(raw.get("endpoint") or raw.get("base_url") or "").strip()

    def create(self, profile: ModelProfile, *, require_model: bool = True) -> Any:
        provider = profile.provider.replace("_", "-").lower()
        raw = profile.raw
        # Raiker ships no built-in test/mock model provider. Any profile that
        # still claims to be one is rejected fail-closed rather than served.
        if provider in {"mock", "test"} or bool(raw.get("test_only")):
            raise ProviderPolicyError("test_provider_not_available")
        aliases = {
            "llama-cpp",
            "llama.cpp",
            "llama-cpp-server",
            "mlx",
            "ollama",
            "ollama-cloud",
            "lm-studio",
            "lm-studio-remote",
            "vllm",
            "openai-compatible",
            "openrouter",
            "huggingface",
            # Hosted providers: OpenAI, Gemini, Ollama Cloud and Hugging Face
            # speak the OpenAI-compatible protocol; Anthropic uses its native
            # Messages API adapter.
            "openai",
            "gemini",
            "anthropic",
            "chatgpt-codex",
        }
        if provider not in aliases:
            raise ProviderConfigurationError(f"unknown_provider:{profile.provider}")
        state = str(raw.get("default_state", ""))
        if state == "enabled_for_tests_only":
            raise ProviderPolicyError("test_only_profile_not_runnable")
        if state == "disabled_until_policy_approved" and not self.allow_policy_gated_provider:
            raise ProviderPolicyError("provider_requires_explicit_policy_approval")
        model_name = str(profile.model or "")
        if require_model and (not model_name or "<" in model_name or ">" in model_name):
            raise ProviderConfigurationError("model_name_not_configured")
        endpoint = self._configured_endpoint(raw)
        if not endpoint or "<" in endpoint:
            endpoint_env = raw.get("endpoint_env")
            if isinstance(endpoint_env, str) and endpoint_env:
                raise ProviderConfigurationError(f"missing_endpoint_env:{endpoint_env}")
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
        # Egress for a provider the owner has configured.
        #
        # Raiker is owner-authoritative and monitored, not prevention-by-
        # restriction (docs/architecture/HANDOFF.md, "Security posture"). Saving a credential
        # for a provider is a deliberate, authenticated act; making the owner
        # then discover a *separate* environment allowlist before the host they
        # just chose can be reached is exactly the wall that posture rejects.
        #
        # So a configured connection authorises this profile's own resolved
        # endpoint — and only that endpoint, never a blanket opening. The
        # environment allowlist stays available for pre-authorising hosts ahead
        # of configuration, and an unconfigured profile still falls back to it
        # and fails closed without one. Every request remains policy-checked,
        # audited, and stoppable.
        configured_allowlist: frozenset[str] | None = None
        if self.connection:
            saved_host = urlparse(str(self.connection.get("endpoint", ""))).hostname
            effective_host = urlparse(endpoint).hostname
            hosts = {host.lower() for host in (saved_host, effective_host) if host}
            configured_allowlist = frozenset(hosts) if hosts else None
        enforce_model_egress(
            endpoint, kind=endpoint_kind, configured_allowlist=configured_allowlist
        )
        if provider == "openrouter" and raw.get("default_state") == "enabled":
            raise ProviderPolicyError("openrouter_must_not_be_enabled_by_default")
        headers: dict[str, str] = {}
        api_key_env = raw.get("api_key_env")
        if provider == "openrouter":
            if not (
                raw.get("requires_network")
                and raw.get("requires_egress_policy")
                and raw.get("requires_budget_policy")
            ):
                raise ProviderPolicyError("openrouter_requires_hosted_egress_budget_policy")
            if urlparse(endpoint).scheme != "https":
                raise ProviderPolicyError("openrouter_requires_https")
            if not (
                (self.connection or {}).get("api_key", "").strip()
                or (isinstance(api_key_env, str) and os.environ.get(api_key_env))
            ):
                raise ProviderConfigurationError("openrouter_api_key_missing")
        api_key = (
            (self.connection or {}).get("api_key", "").strip()
            or (os.environ.get(api_key_env, "") if isinstance(api_key_env, str) else "")
        )
        if bool(raw.get("requires_api_key", False)) and not api_key:
            key_name = api_key_env if isinstance(api_key_env, str) else "api_key_env"
            raise ProviderConfigurationError(f"provider_api_key_missing:{key_name}")
        if (
            endpoint_kind == "remote_hosted"
            and self.require_api_key_for_hosted
            and not api_key
            and provider != "chatgpt-codex"
        ):
            raise ProviderConfigurationError("hosted_api_key_missing")
        if provider == "chatgpt-codex":
            return AsyncCodexAppServerProvider(
                profile_id=profile.profile_id,
                model=str(raw.get("served_model_name", profile.model)),
                capabilities=capabilities_from_profile(profile),
            )
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
