from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit


class ModelReadinessState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CHECKING = "checking"
    READY = "ready"
    RUNTIME_MISSING = "runtime_missing"
    RUNTIME_STOPPED = "runtime_stopped"
    MODEL_MISSING = "model_missing"
    POLICY_BLOCKED = "policy_blocked"
    AUTHENTICATION_FAILED = "authentication_failed"
    UNREACHABLE = "unreachable"
    UNSUPPORTED = "unsupported"
    STALE = "stale"


@dataclass(frozen=True)
class ModelReadinessKey:
    owner_principal_id: str
    profile_id: str
    model: str
    endpoint_fingerprint: str


@dataclass(frozen=True)
class ModelReadiness:
    key: ModelReadinessKey
    state: ModelReadinessState
    checked_at: str | None
    expires_at: str | None
    summary: str
    reason_code: str
    remediation: str
    evidence: dict[str, object]

    @property
    def ready(self) -> bool:
        return self.state is ModelReadinessState.READY

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_principal_id": self.key.owner_principal_id,
            "profile_id": self.key.profile_id,
            "model": self.key.model,
            "endpoint_fingerprint": self.key.endpoint_fingerprint,
            "state": self.state.value,
            "checked_at": self.checked_at,
            "expires_at": self.expires_at,
            "summary": self.summary,
            "reason_code": self.reason_code,
            "remediation": self.remediation,
            "evidence": self.evidence,
            "ready": self.ready,
        }

    def public_status(self) -> dict[str, str]:
        return {
            "state": self.state.value,
            "summary": self.summary,
            "reason_code": self.reason_code,
            "remediation": self.remediation,
        }


class ModelNotReady(RuntimeError):
    def __init__(self, readiness: ModelReadiness) -> None:
        super().__init__("model_not_ready")
        self.readiness = readiness

    def detail(self) -> dict[str, object]:
        return {
            "reason_code": "model_not_ready",
            "readiness": self.readiness.public_status(),
        }


class ModelProbe(Protocol):
    async def check(self, key: ModelReadinessKey) -> ModelReadiness: ...


class ModelReadinessStore(Protocol):
    def save_model_readiness(self, readiness: ModelReadiness) -> None: ...

    def load_model_readiness(self, key: ModelReadinessKey) -> ModelReadiness | None: ...

    def invalidate_model_readiness(
        self,
        owner_principal_id: str,
        profile_id: str,
        *,
        reason_code: str = "readiness_invalidated",
    ) -> int: ...

    def list_model_readiness(
        self,
        owner_principal_id: str,
        profile_id: str | None = None,
    ) -> list[ModelReadiness]: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _provider_label(provider: str) -> str:
    return {
        "ollama": "Ollama",
        "lm-studio": "LM Studio",
        "llama.cpp": "llama.cpp",
        "anthropic": "Anthropic",
        "openrouter": "OpenRouter",
        "openai": "OpenAI",
        "gemini": "Gemini",
        "huggingface": "Hugging Face",
    }.get(provider, provider.replace("-", " ").title())


def _effective_endpoint(profile: Any, connection: dict[str, str] | None) -> str:
    if connection and connection.get("endpoint", "").strip():
        return connection["endpoint"].strip()
    endpoint_env = profile.raw.get("endpoint_env")
    if isinstance(endpoint_env, str) and endpoint_env:
        configured = os.environ.get(endpoint_env, "").strip()
        if configured:
            return configured
    return str(profile.raw.get("endpoint") or profile.raw.get("base_url") or "").strip()


def _endpoint_fingerprint(provider: str, endpoint: str) -> str:
    parsed = urlsplit(endpoint.strip())
    # Userinfo and fragments are never endpoint identity and must not survive in
    # evidence. Host case and a trailing slash are semantically irrelevant.
    host = (parsed.hostname or "").casefold()
    if parsed.port:
        host = f"{host}:{parsed.port}"
    normalized = urlunsplit(
        (parsed.scheme.casefold(), host, parsed.path.rstrip("/"), parsed.query, "")
    )
    return hashlib.sha256(f"{provider.casefold()}\0{normalized}".encode()).hexdigest()


class ProviderCatalogueProbe:
    """Non-billable exact-model probe through the provider catalogue endpoint."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def resolve_key(
        self,
        owner_principal_id: str,
        profile_id: str,
        model: str,
    ) -> ModelReadinessKey:
        from raiker.models.connections import get_model_connection
        from raiker.models.registry import ModelProfileRegistry

        profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
        connection = get_model_connection(self.store, owner_principal_id, profile_id)
        endpoint = _effective_endpoint(profile, connection)
        return ModelReadinessKey(
            owner_principal_id=owner_principal_id,
            profile_id=profile_id,
            model=model.strip(),
            endpoint_fingerprint=_endpoint_fingerprint(profile.provider, endpoint),
        )

    def _result(
        self,
        key: ModelReadinessKey,
        state: ModelReadinessState,
        summary: str,
        reason_code: str,
        remediation: str,
        *,
        provider: str,
    ) -> ModelReadiness:
        return ModelReadiness(
            key=key,
            state=state,
            checked_at=None,
            expires_at=None,
            summary=summary,
            reason_code=reason_code,
            remediation=remediation,
            evidence={"provider": provider},
        )

    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        from raiker.models.connections import get_model_connection
        from raiker.models.exceptions import (
            ProviderAuthenticationError,
            ProviderConfigurationError,
            ProviderConnectionError,
            ProviderModelNotFoundError,
            ProviderPolicyError,
            ProviderRateLimitError,
            ProviderResponseValidationError,
            ProviderTimeoutError,
            ProviderUnsupportedCapabilityError,
        )
        from raiker.models.policy_state import provider_runtime_policy_from_gates
        from raiker.models.registry import ModelProfileRegistry, profile_with_model
        from raiker.models.router import ModelRouter

        registry = ModelProfileRegistry.load()
        profile = registry.resolve_profile_id(key.profile_id)
        label = _provider_label(profile.provider)
        connection = get_model_connection(
            self.store, key.owner_principal_id, key.profile_id
        )
        router = ModelRouter(
            registry,
            runtime_policy=provider_runtime_policy_from_gates(
                self.store, key.owner_principal_id
            ),
            connection_resolver=lambda profile_id: (
                connection if profile_id == key.profile_id else None
            ),
        )
        effective = profile_with_model(profile, key.model)
        try:
            models = await router.alist_models_for_profile(effective)
        except ProviderAuthenticationError:
            return self._result(
                key,
                ModelReadinessState.AUTHENTICATION_FAILED,
                f"{label} rejected the saved credential.",
                "provider_authentication_failed",
                "Update the provider credential and check again.",
                provider=profile.provider,
            )
        except ProviderPolicyError:
            return self._result(
                key,
                ModelReadinessState.POLICY_BLOCKED,
                f"{label} is blocked by the current model policy.",
                "provider_policy_blocked",
                "Review the provider policy and check again.",
                provider=profile.provider,
            )
        except ProviderConfigurationError:
            state = (
                ModelReadinessState.RUNTIME_MISSING
                if profile.local_only
                else ModelReadinessState.NOT_CONFIGURED
            )
            return self._result(
                key,
                state,
                f"{label} is not fully configured.",
                "local_runtime_missing" if profile.local_only else "provider_not_configured",
                f"Set up {label} and check again.",
                provider=profile.provider,
            )
        except ProviderModelNotFoundError:
            return self._result(
                key,
                ModelReadinessState.MODEL_MISSING,
                f"{label} cannot find {key.model}.",
                "local_model_missing" if profile.local_only else "provider_model_missing",
                f"Install or select {key.model}, then check again.",
                provider=profile.provider,
            )
        except ProviderUnsupportedCapabilityError:
            return self._result(
                key,
                ModelReadinessState.UNSUPPORTED,
                f"{label} does not support model catalogue checks.",
                "model_catalogue_unsupported",
                "Choose a supported provider runtime.",
                provider=profile.provider,
            )
        except (ProviderConnectionError, ProviderTimeoutError):
            return self._result(
                key,
                (
                    ModelReadinessState.RUNTIME_STOPPED
                    if profile.local_only
                    else ModelReadinessState.UNREACHABLE
                ),
                f"{label} is not reachable.",
                "local_runtime_unreachable" if profile.local_only else "provider_unreachable",
                f"Start or reconnect {label}, then check again.",
                provider=profile.provider,
            )
        except ProviderRateLimitError:
            return self._result(
                key,
                ModelReadinessState.UNREACHABLE,
                f"{label} temporarily refused the catalogue check.",
                "provider_rate_limited",
                "Wait briefly, then check again.",
                provider=profile.provider,
            )
        except ProviderResponseValidationError:
            return self._result(
                key,
                ModelReadinessState.UNREACHABLE,
                f"{label} returned an invalid model catalogue.",
                "provider_catalogue_invalid",
                "Check the endpoint and runtime version.",
                provider=profile.provider,
            )
        except Exception:  # noqa: BLE001 - API output is deliberately classified
            return self._result(
                key,
                ModelReadinessState.UNREACHABLE,
                f"{label} could not complete the model check.",
                "provider_probe_failed",
                "Check the provider connection and try again.",
                provider=profile.provider,
            )
        if not any(item.id == key.model for item in models):
            return self._result(
                key,
                ModelReadinessState.MODEL_MISSING,
                f"{label} is reachable, but {key.model} is not available.",
                "local_model_missing" if profile.local_only else "provider_model_missing",
                f"Install or select {key.model}, then check again.",
                provider=profile.provider,
            )
        return self._result(
            key,
            ModelReadinessState.READY,
            f"{label} can reach {key.model}.",
            "model_ready",
            "",
            provider=profile.provider,
        )


class ModelReadinessService:
    def __init__(
        self,
        store: ModelReadinessStore,
        *,
        probe: ModelProbe,
        clock: Callable[[], datetime] = _utc_now,
        ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self.store = store
        self.probe = probe
        self.clock = clock
        self.ttl = ttl

    @staticmethod
    def key(
        owner_principal_id: str,
        profile_id: str,
        model: str,
        endpoint_fingerprint: str,
    ) -> ModelReadinessKey:
        return ModelReadinessKey(
            owner_principal_id=owner_principal_id,
            profile_id=profile_id,
            model=model,
            endpoint_fingerprint=endpoint_fingerprint,
        )

    @staticmethod
    def _not_configured(key: ModelReadinessKey) -> ModelReadiness:
        return ModelReadiness(
            key=key,
            state=ModelReadinessState.NOT_CONFIGURED,
            checked_at=None,
            expires_at=None,
            summary="No readiness check exists for this exact model.",
            reason_code="model_not_checked",
            remediation="Set up or check this model before sending.",
            evidence={},
        )

    async def check(
        self,
        owner_principal_id: str,
        profile_id: str,
        model: str,
        endpoint_fingerprint: str,
    ) -> ModelReadiness:
        key = self.key(owner_principal_id, profile_id, model, endpoint_fingerprint)
        observed = await self.probe.check(key)
        now = self.clock().astimezone(UTC)
        readiness = replace(
            observed,
            key=key,
            checked_at=now.isoformat(),
            expires_at=(now + self.ttl).isoformat(),
        )
        self.store.save_model_readiness(readiness)
        return readiness

    def current(
        self,
        owner_principal_id: str,
        profile_id: str,
        model: str,
        endpoint_fingerprint: str,
    ) -> ModelReadiness:
        key = self.key(owner_principal_id, profile_id, model, endpoint_fingerprint)
        readiness = self.store.load_model_readiness(key)
        if readiness is None:
            return self._not_configured(key)
        if readiness.state is ModelReadinessState.READY and readiness.expires_at:
            expires_at = datetime.fromisoformat(readiness.expires_at)
            if expires_at <= self.clock().astimezone(UTC):
                return replace(
                    readiness,
                    state=ModelReadinessState.STALE,
                    summary="The last model check has expired.",
                    reason_code="readiness_expired",
                    remediation="Check this model again before sending.",
                )
        return readiness

    def invalidate_profile(
        self,
        owner_principal_id: str,
        profile_id: str,
        *,
        reason_code: str = "readiness_invalidated",
    ) -> int:
        return self.store.invalidate_model_readiness(
            owner_principal_id,
            profile_id,
            reason_code=reason_code,
        )

    def _selected_key(
        self,
        owner_principal_id: str,
        profile_id: str,
        model: str,
    ) -> ModelReadinessKey:
        resolver = getattr(self.probe, "resolve_key", None)
        if resolver is None:
            raise TypeError("model_probe_cannot_resolve_endpoint")
        return resolver(owner_principal_id, profile_id, model)

    async def check_selected(
        self,
        owner_principal_id: str,
        profile_id: str,
        model: str,
    ) -> ModelReadiness:
        key = self._selected_key(owner_principal_id, profile_id, model)
        return await self.check(
            key.owner_principal_id,
            key.profile_id,
            key.model,
            key.endpoint_fingerprint,
        )

    def current_selected(
        self,
        owner_principal_id: str,
        profile_id: str,
        model: str,
    ) -> ModelReadiness:
        key = self._selected_key(owner_principal_id, profile_id, model)
        return self.current(
            key.owner_principal_id,
            key.profile_id,
            key.model,
            key.endpoint_fingerprint,
        )

    def resolve_request_target(
        self,
        owner_principal_id: str,
        profile_id: str | None,
        model: str | None,
    ) -> tuple[str, str]:
        from raiker.models.registry import ModelProfileRegistry
        from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID

        registry = ModelProfileRegistry.load()
        state = (
            self.store.load_principal_model_state(owner_principal_id)  # type: ignore[attr-defined]
            if self.store.get_account(owner_principal_id) is not None  # type: ignore[attr-defined]
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)  # type: ignore[attr-defined]
        )
        requested_profile = (profile_id or "").strip()
        if requested_profile:
            profile = registry.resolve_profile_id(requested_profile)
            effective_model = profile.model
            if state is not None and state.profile_id == profile.profile_id and state.model:
                effective_model = state.model
            if model and model.strip():
                effective_model = model.strip()
            return profile.profile_id, effective_model

        if state is not None:
            profile = registry.resolve_profile_id(state.profile_id)
            effective_model = state.model or profile.model
            if effective_model and "<" not in effective_model:
                return profile.profile_id, effective_model

        native = next(
            profile
            for profile in registry.list_profiles()
            if bool(profile.raw.get("is_native_default"))
        )
        return native.profile_id, native.model

    def require_ready(
        self,
        owner_principal_id: str,
        profile_id: str | None,
        model: str | None,
    ) -> ModelReadiness:
        resolved_profile, resolved_model = self.resolve_request_target(
            owner_principal_id,
            profile_id,
            model,
        )
        readiness = self.current_selected(
            owner_principal_id,
            resolved_profile,
            resolved_model,
        )
        if not readiness.ready:
            raise ModelNotReady(readiness)
        return readiness
