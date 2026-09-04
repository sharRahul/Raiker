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
    QUOTA_EXHAUSTED = "quota_exhausted"
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


#: The reason code `current()` synthesises when a stored READY observation has
#: simply outlived its window. It is deliberately distinct from the reason codes
#: `invalidate_model_readiness` writes — `runtime_changed`,
#: `readiness_invalidated`, and the rest — because the two mean different things
#: and only one of them is safe to resolve without the owner:
#:
#: * **expired** — nothing changed; nobody has looked recently. Re-looking is
#:   exactly what the owner would do, so Raiker does it (BUG-238).
#: * **invalidated** — something changed *under* the model: a connection, an
#:   endpoint, a credential, a pulled model. The previous observation does not
#:   describe reality any more, and the owner asked for that check by changing
#:   the thing. It keeps its explicit re-check.
READINESS_EXPIRED_REASON = "readiness_expired"


def _has_merely_expired(readiness: ModelReadiness) -> bool:
    """True when this observation aged out and nothing else is known to be wrong.

    `STALE` carries two different meanings, and only this one may be resolved
    without the owner. See :data:`READINESS_EXPIRED_REASON`.
    """
    return (
        readiness.state is ModelReadinessState.STALE
        and readiness.reason_code == READINESS_EXPIRED_REASON
    )


def _nothing_has_been_measured(readiness: ModelReadiness, connected: frozenset[str]) -> bool:
    """True when nobody has ever checked this model on a provider already connected.

    Never-checked is otherwise the same kind of state as merely-expired: nothing
    is known to be wrong, and the only thing between the owner and their turn is
    a look nobody has taken. Refusing there asked the owner to press **Test** on
    a provider they had just connected and a model they had just selected — the
    complaint BUG-238 removed for expiry, arriving instead on first use.

    The limit is the one the original invariant exists for: Raiker must never
    quietly reach a provider the owner never configured. So this covers only
    profiles with a saved connection, and a profile still carrying the
    ``<model>`` placeholder is excluded because there is no exact model to look
    at.
    """
    return (
        readiness.state is ModelReadinessState.NOT_CONFIGURED
        and readiness.key.profile_id in connected
        and bool(readiness.key.model)
        and "<" not in readiness.key.model
    )


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


# BUG-83 — the observation window used to be a hard-coded five minutes with no
# way to move it and nothing to re-check in the background, so a long editing
# session traded a stale-ready window for a spurious-stale interruption. The TTL
# is now the owner's, bounded so neither end can be set to something dishonest:
# under a minute is a check on every keystroke, over two hours is not a check.
DEFAULT_READINESS_TTL_MINUTES = 5
MIN_READINESS_TTL_MINUTES = 1
MAX_READINESS_TTL_MINUTES = 120


def readiness_ttl_minutes(store: Any, owner_principal_id: str) -> int:
    """The owner's readiness TTL in minutes, clamped, defaulting when unset.

    Read from the same per-account settings blob the UI writes
    (``settings.models.readiness_ttl_minutes``). A missing, malformed or
    out-of-range value resolves to the default rather than failing: a preference
    that cannot be read must never be the reason a turn cannot start.
    """
    try:
        row = store.get_user_settings(owner_principal_id)
    except Exception:  # noqa: BLE001 — an unreadable preference is the default
        return DEFAULT_READINESS_TTL_MINUTES
    if not row:
        return DEFAULT_READINESS_TTL_MINUTES
    import json

    try:
        settings = json.loads(row["settings_json"])
        # The settings blob carries both shapes — the flat dotted keys the
        # settings sections write and the nested objects a few older readers
        # use — so both are accepted rather than one silently winning.
        raw = settings.get("models.readiness_ttl_minutes")
        if raw is None:
            raw = (settings.get("models") or {}).get("readiness_ttl_minutes")
        if raw is None:
            return DEFAULT_READINESS_TTL_MINUTES
        value = int(raw)
    except (KeyError, TypeError, ValueError, AttributeError):
        return DEFAULT_READINESS_TTL_MINUTES
    return max(MIN_READINESS_TTL_MINUTES, min(MAX_READINESS_TTL_MINUTES, value))


def _provider_label(provider: str) -> str:
    return {
        "ollama": "Ollama",
        "lm-studio": "LM Studio",
        "llama.cpp": "llama.cpp",
        "anthropic": "Anthropic",
        "openrouter": "OpenRouter",
        "openai": "OpenAI",
        "chatgpt-codex": "ChatGPT subscription",
        "gemini": "Gemini",
        "huggingface": "Hugging Face",
        "ollama-cloud": "Ollama Cloud",
        "mlx": "MLX",
        "openai-compatible": "OpenAI-compatible",
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
    """Exact-model catalogue probe plus a bounded hosted execution preflight."""

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

    def _workspace_required(
        self, key: ModelReadinessKey, label: str, provider: str
    ) -> ModelReadiness:
        """BUG-272 — the key is valid and names no workspace.

        Its own answer for the same reason quota has one: the repair is neither
        a network fix nor a new key. An identity-linked key is the wrong *shape*
        of credential for a request that does not carry a workspace, and telling
        the owner to rotate it would send them round the same loop.
        """
        return self._result(
            key,
            ModelReadinessState.AUTHENTICATION_FAILED,
            f"{label} needs a workspace named alongside this kind of key.",
            "provider_workspace_required",
            f"This key is identity-linked. Use a standard {label} API key from the "
            "provider's console, or one scoped to a single workspace, then check again.",
            provider=provider,
        )

    def _quota_exhausted(
        self, key: ModelReadinessKey, label: str, provider: str
    ) -> ModelReadiness:
        """One answer for both probe stages: reachable, authorised, unpayable.

        Kept separate from `unreachable` and `authentication_failed` because the
        repair is neither a network fix nor a new key — the account needs credit
        or a higher quota, and saying so is the whole point of an exact state.
        """
        return self._result(
            key,
            ModelReadinessState.QUOTA_EXHAUSTED,
            f"{label} accepted the credential but the account has no credit or quota left.",
            "provider_quota_exhausted",
            f"Add credit or raise the quota on your {label} account, then check again.",
            provider=provider,
        )

    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        from raiker.models.connections import get_model_connection
        from raiker.models.exceptions import (
            ProviderAuthenticationError,
            ProviderConfigurationError,
            ProviderConnectionError,
            ProviderModelNotFoundError,
            ProviderPolicyError,
            ProviderQuotaExhaustedError,
            ProviderRateLimitError,
            ProviderResponseValidationError,
            ProviderTimeoutError,
            ProviderUnsupportedCapabilityError,
            ProviderWorkspaceRequiredError,
        )
        from raiker.models.policy_state import provider_runtime_policy_from_gates
        from raiker.models.registry import ModelProfileRegistry, profile_with_model
        from raiker.models.router import ModelRouter

        registry = ModelProfileRegistry.load()
        profile = registry.resolve_profile_id(key.profile_id)
        label = _provider_label(profile.provider)
        connection = get_model_connection(self.store, key.owner_principal_id, key.profile_id)
        router = ModelRouter(
            registry,
            runtime_policy=provider_runtime_policy_from_gates(self.store, key.owner_principal_id),
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
        except ProviderWorkspaceRequiredError:
            return self._workspace_required(key, label, profile.provider)
        except ProviderQuotaExhaustedError:
            return self._quota_exhausted(key, label, profile.provider)
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
        if not profile.local_only:
            try:
                await router.aprobe_model(effective)
            except ProviderAuthenticationError:
                return self._result(
                    key,
                    ModelReadinessState.AUTHENTICATION_FAILED,
                    f"{label} rejected the saved credential during execution.",
                    "provider_authentication_failed",
                    "Update the provider credential and check again.",
                    provider=profile.provider,
                )
            except ProviderWorkspaceRequiredError:
                return self._workspace_required(key, label, profile.provider)
            except ProviderQuotaExhaustedError:
                return self._quota_exhausted(key, label, profile.provider)
            except ProviderModelNotFoundError:
                return self._result(
                    key,
                    ModelReadinessState.MODEL_MISSING,
                    f"{label} lists {key.model}, but cannot execute it.",
                    "provider_model_missing",
                    "Choose a currently executable model, then check again.",
                    provider=profile.provider,
                )
            except ProviderRateLimitError:
                return self._result(
                    key,
                    ModelReadinessState.UNREACHABLE,
                    f"{label} temporarily refused the execution check.",
                    "provider_rate_limited",
                    "Wait briefly, then check again.",
                    provider=profile.provider,
                )
            except (ProviderConnectionError, ProviderTimeoutError):
                return self._result(
                    key,
                    ModelReadinessState.UNREACHABLE,
                    f"{label} cannot execute {key.model} with the current account.",
                    "provider_execution_refused",
                    "Review the provider credential, access, and billing, then check again.",
                    provider=profile.provider,
                )
            except ProviderUnsupportedCapabilityError:
                return self._result(
                    key,
                    ModelReadinessState.UNSUPPORTED,
                    f"{label} does not support an execution readiness check.",
                    "provider_execution_probe_unsupported",
                    "Choose a provider that supports chat completions.",
                    provider=profile.provider,
                )
            except ProviderResponseValidationError:
                return self._result(
                    key,
                    ModelReadinessState.UNREACHABLE,
                    f"{label} returned an invalid execution response.",
                    "provider_execution_invalid",
                    "Check the endpoint and model compatibility.",
                    provider=profile.provider,
                )
            except Exception:  # noqa: BLE001 - public result remains classified
                return self._result(
                    key,
                    ModelReadinessState.UNREACHABLE,
                    f"{label} could not complete the execution check.",
                    "provider_execution_probe_failed",
                    "Check the provider account and try again.",
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
        ttl: timedelta | None = None,
    ) -> None:
        self.store = store
        self.probe = probe
        self.clock = clock
        # ``None`` means "ask the owner's settings at check time" (BUG-83). An
        # explicit value stays fixed, which is what tests and one-off callers
        # want; the running product takes the owner's.
        self._fixed_ttl = ttl

    def ttl_for(self, owner_principal_id: str) -> timedelta:
        """This owner's observation window."""
        if self._fixed_ttl is not None:
            return self._fixed_ttl
        return timedelta(minutes=readiness_ttl_minutes(self.store, owner_principal_id))

    @property
    def ttl(self) -> timedelta:
        """The default window, for callers that have no owner in hand."""
        return self._fixed_ttl or timedelta(minutes=DEFAULT_READINESS_TTL_MINUTES)

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
            expires_at=(now + self.ttl_for(owner_principal_id)).isoformat(),
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
                    reason_code=READINESS_EXPIRED_REASON,
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

    def _configured_model(self, owner_principal_id: str, profile_id: str) -> str | None:
        """The owner's most recent pinned model for one profile, if any."""
        try:
            pairs = self.store.list_configured_models(owner_principal_id)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — an unreadable pin resolves nothing
            return None
        for candidate_profile, candidate_model in reversed(list(pairs or [])):
            if candidate_profile == profile_id and candidate_model:
                return str(candidate_model)
        return None

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
            if not effective_model or "<" in effective_model:
                # Hosted profiles ship a `<model>` placeholder, and the single
                # session state only ever names the currently selected profile.
                # The owner's pinned choice for any *other* profile lives in the
                # configured-model table, which is what makes a fallback entry
                # resolvable at all.
                pinned = self._configured_model(owner_principal_id, profile.profile_id)
                if pinned:
                    effective_model = pinned
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

    def _fallback_profile_ids(self, owner_principal_id: str) -> list[str]:
        """The owner's ordered fallback profile ids, or none if unreadable."""
        from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID

        try:
            # Owner-scoped first, terminal only when the owner has none. A
            # credential-backed owner and a CLI-bootstrapped one write to
            # different rows, and a sequence the owner saved is theirs either
            # way — keying off the presence of an account row would silently
            # ignore one of them.
            stored = self.store.load_principal_model_fallback_sequence(  # type: ignore[attr-defined]
                owner_principal_id
            ) or self.store.load_model_fallback_sequence(  # type: ignore[attr-defined]
                TERMINAL_MODEL_SESSION_ID
            )
        except Exception:  # noqa: BLE001 — an unreadable sequence adds no candidate
            return []
        return [str(entry) for entry in stored or []]

    def resolve_chain(
        self,
        owner_principal_id: str,
        profile_id: str | None,
        model: str | None,
    ) -> list[ModelReadiness]:
        """Readiness for every model this turn could actually run, in order.

        ``RuntimeOrchestrator._provider_chain`` builds exactly this list — the
        resolved primary followed by the owner's fallback sequence — and tries
        each entry in turn. Judging readiness on the primary alone therefore
        answers a question the runtime never asks.
        """
        resolved_profile, resolved_model = self.resolve_request_target(
            owner_principal_id,
            profile_id,
            model,
        )
        chain = [
            self.current_selected(owner_principal_id, resolved_profile, resolved_model)
        ]
        seen = {(resolved_profile, resolved_model)}
        for candidate_id in self._fallback_profile_ids(owner_principal_id):
            try:
                candidate_profile, candidate_model = self.resolve_request_target(
                    owner_principal_id, candidate_id, None
                )
            except (KeyError, ValueError, StopIteration):
                continue
            # An unresolved `<model>` placeholder is not a runnable candidate;
            # the orchestrator drops it from the chain for the same reason.
            if not candidate_model or "<" in candidate_model:
                continue
            if (candidate_profile, candidate_model) in seen:
                continue
            seen.add((candidate_profile, candidate_model))
            chain.append(
                self.current_selected(
                    owner_principal_id, candidate_profile, candidate_model
                )
            )
        return chain

    def require_ready(
        self,
        owner_principal_id: str,
        profile_id: str | None,
        model: str | None,
    ) -> ModelReadiness:
        """Admit the turn when any model the runtime would try is ready.

        The primary keeps priority, so a ready primary is always the answer it
        returns. A refusal reports the primary's reason: that is the model the
        owner chose, and it is the one whose repair they came to perform.

        This is the *pure read*: it never reaches a provider. Callers that can
        await should use :meth:`require_ready_async`, which re-takes an
        observation that has merely aged out instead of refusing on it.
        """
        chain = self.resolve_chain(owner_principal_id, profile_id, model)
        for readiness in chain:
            if readiness.ready:
                return readiness
        raise ModelNotReady(chain[0])

    async def require_ready_async(
        self,
        owner_principal_id: str,
        profile_id: str | None,
        model: str | None,
    ) -> ModelReadiness:
        """The same admission, re-checking a model whose observation aged out.

        BUG-238. A readiness observation has a TTL so that no turn runs on a
        claim older than the owner's window. It was also, wrongly, the thing
        that decided whether the model was *set up at all*: once the window
        passed, `state` became ``stale``, ``ready`` became false, and the
        product asked the owner to **set up a model they had already set up** —
        after every restart, and after any five idle minutes.

        Staleness is not unavailability. It means "this worked, and nobody has
        looked recently", and the honest response is to look — which is exactly
        what the owner was being asked to do by hand. So a `stale` entry is
        re-checked here, against the real provider, and only a check that
        *fails* refuses the turn.

        A model nobody has *ever* checked gets the same answer, but only on a
        provider the owner has already connected: Raiker looks once rather than
        refusing the first turn on a connection they just made. A provider with
        no saved connection is still never reached on Raiker's own initiative.

        The TTL keeps its whole meaning: a turn still never runs on an
        observation older than the window, because a stale one is replaced by a
        fresh observation before the turn is admitted. Every other refusal —
        authentication, quota, a missing model, a policy block — is a real
        answer about the model and is returned unchanged, because those are the
        cases where the owner does have something to fix.
        """
        chain = self.resolve_chain(owner_principal_id, profile_id, model)
        for readiness in chain:
            if readiness.ready:
                return readiness

        from raiker.models.policy_state import owner_configured_providers

        connected = owner_configured_providers(self.store, owner_principal_id)
        refreshed_primary: ModelReadiness | None = None
        for readiness in chain:
            if not (
                _has_merely_expired(readiness)
                or _nothing_has_been_measured(readiness, connected)
            ):
                continue
            try:
                rechecked = await self.check(
                    readiness.key.owner_principal_id,
                    readiness.key.profile_id,
                    readiness.key.model,
                    readiness.key.endpoint_fingerprint,
                )
            except Exception:  # noqa: BLE001 - a failed re-check refuses, never raises past here
                continue
            if rechecked.ready:
                return rechecked
            if refreshed_primary is None and readiness is chain[0]:
                # The primary is the model the owner chose, so its *fresh*
                # answer is the one to report — "the key was rejected" is worth
                # far more than "the last check expired".
                refreshed_primary = rechecked
        raise ModelNotReady(refreshed_primary or chain[0])
