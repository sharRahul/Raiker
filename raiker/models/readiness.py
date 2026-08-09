from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol


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


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
