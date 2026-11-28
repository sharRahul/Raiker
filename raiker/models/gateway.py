"""In-process model execution controls; never stores prompts or billing rows."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar
from uuid import uuid4

from raiker.models.attempts import is_transport_failure
from raiker.models.contracts import ModelStreamEvent, summarize_model_usage
from raiker.models.exceptions import ModelProviderError, provider_error_code

T = TypeVar("T")
_LOG = logging.getLogger("raiker.models.gateway")
_SAFE_ERROR_CODES = frozenset({
    "provider_auth_failed", "provider_timeout", "provider_rate_limited",
    "provider_quota_exhausted", "provider_workspace_required", "provider_workspace_invalid",
    "provider_model_refused", "model_not_found", "provider_connection_failed",
    "provider_misconfigured", "provider_policy_denied", "model_dial_refused",
    "provider_invalid_response", "provider_stream_failed", "provider_cancelled",
    "provider_capability_unsupported", "provider_unavailable", "tool_calls_unsupported",
    "provider_circuit_open", "provider_error_unclassified",
})


class GatewayCircuitOpenError(ModelProviderError):
    """The connection is cooling down or has a recovery request in flight."""

    def __init__(self) -> None:
        super().__init__("provider_circuit_open")


@dataclass(frozen=True)
class GatewayTarget:
    owner_scope: str
    profile_id: str
    model: str
    connection_id: str


@dataclass(frozen=True)
class GatewayRecord:
    request_id: str
    profile_id: str
    model: str
    kind: str
    outcome: str
    duration_ms: float
    error_code: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    attempt: int = 1
    session_id: str | None = None
    turn_id: str | None = None


@dataclass
class _Circuit:
    failures: int = 0
    open_until: float = 0.0
    probe: bool = False
    generation: int = 0
    active: int = 0


class AIGateway:
    """Thread-safe, bounded circuit state shared across loops; no network retries.

    Authorize a provider before calling this service. Only transport failures
    trip its circuit; permanent errors and cancellation never count as outages.
    A circuit belongs to an owner, profile, model and exact resolved connection.
    Keys are process-keyed digests so retained state contains no credentials.
    """

    def __init__(self, *, failure_threshold: int = 3, cooldown_seconds: float = 30.0,
                 max_targets: int = 1024, max_records: int = 256,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if failure_threshold < 1 or cooldown_seconds <= 0 or max_targets < 1 or max_records < 1:
            raise ValueError("invalid_gateway_limits")
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_targets = max_targets
        self.clock = clock
        self._secret = secrets.token_bytes(32)
        self._lock = threading.Lock()
        self._circuits: OrderedDict[str, _Circuit] = OrderedDict()
        self._records: deque[GatewayRecord] = deque(maxlen=max_records)

    def _key(self, target: GatewayTarget) -> str:
        value = json.dumps([target.owner_scope, target.profile_id, target.model, target.connection_id])
        return hmac.new(self._secret, value.encode(), hashlib.sha256).hexdigest()

    def _enter(self, target: GatewayTarget) -> tuple[_Circuit, int]:
        key = self._key(target)
        with self._lock:
            state = self._circuits.get(key)
            if state is None:
                if len(self._circuits) >= self.max_targets:
                    # Never evict an active request or a cooling connection: doing
                    # so admits duplicate probes or silently defeats containment.
                    evict = next((k for k, s in self._circuits.items()
                                  if not s.active and not s.probe and s.open_until <= self.clock()), None)
                    if evict is None:
                        raise GatewayCircuitOpenError()
                    del self._circuits[evict]
                state = _Circuit()
                self._circuits[key] = state
            self._circuits.move_to_end(key)
            if state.open_until:
                if self.clock() < state.open_until or state.probe:
                    raise GatewayCircuitOpenError()
                state.probe = True
            state.active += 1
            return state, state.generation

    def _leave(self, lease: tuple[_Circuit, int], outcome: str, error_code: str) -> None:
        state, generation = lease
        with self._lock:
            state.active -= 1
            if generation != state.generation:
                return
            state.probe = False
            if outcome == "cancelled":
                return
            if outcome == "failed" and is_transport_failure(error_code):
                state.failures += 1
                if state.failures >= self.failure_threshold:
                    state.open_until = self.clock() + self.cooldown_seconds
                    state.generation += 1
            else:
                # A classified permanent refusal proves the service responded.
                state.failures = 0
                state.open_until = 0.0

    def _record(self, target: GatewayTarget, kind: str, request_id: str, start: float,
                outcome: str, error_code: str, usage: Any, attempt: int,
                session_id: str | None, turn_id: str | None) -> None:
        category = error_code.split(":", 1)[0]
        category = category if category in _SAFE_ERROR_CODES else ("provider_error_unclassified" if category else "")
        record = GatewayRecord(request_id, target.profile_id, target.model, kind, outcome,
                               max(0.0, (self.clock() - start) * 1000), category,
                               summarize_model_usage(usage), attempt, session_id, turn_id)
        with self._lock:
            self._records.append(record)
        # The record contains metadata only. Never attach provider exceptions,
        # resolved endpoints, connection identifiers, prompts or response text.
        _LOG.info(
            "model gateway: request_id=%s profile=%s model=%s kind=%s attempt=%s "
            "outcome=%s duration_ms=%.2f reason=%s usage=%s session=%s turn=%s",
            record.request_id, record.profile_id, record.model, record.kind, record.attempt,
            record.outcome, record.duration_ms, record.error_code, record.usage,
            record.session_id, record.turn_id,
        )

    def recent(self) -> list[GatewayRecord]:
        with self._lock:
            return list(self._records)

    async def call(self, target: GatewayTarget, kind: str, operation: Callable[[], Awaitable[T]],
                   *, request_id: str | None = None, attempt: int = 1,
                   session_id: str | None = None, turn_id: str | None = None) -> T:
        start, request_id = self.clock(), request_id or uuid4().hex
        outcome, code, usage = "cancelled", "", None
        lease = None
        try:
            lease = self._enter(target)
            result = await operation()
            usage = getattr(result, "usage", None)
            outcome = "completed"
            return result
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except Exception as exc:
            outcome = "blocked" if isinstance(exc, GatewayCircuitOpenError) else "failed"
            code = provider_error_code(exc)
            raise
        finally:
            if lease is not None:
                self._leave(lease, outcome, code)
            self._record(target, kind, request_id, start, outcome, code, usage, attempt, session_id, turn_id)

    async def stream(self, target: GatewayTarget,
                     operation: Callable[[], AsyncIterator[ModelStreamEvent]], *,
                     request_id: str | None = None, attempt: int = 1,
                     session_id: str | None = None, turn_id: str | None = None) -> AsyncGenerator[ModelStreamEvent, None]:
        start, request_id = self.clock(), request_id or uuid4().hex
        outcome, code, usage = "cancelled", "", None
        lease = None
        stream = None
        try:
            lease = self._enter(target)
            stream = operation()
            async for event in stream:
                if isinstance(event.metadata.get("usage"), dict):
                    usage = event.metadata["usage"]
                yield event
            outcome = "completed"
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except Exception as exc:
            outcome = "blocked" if isinstance(exc, GatewayCircuitOpenError) else "failed"
            code = provider_error_code(exc)
            raise
        finally:
            try:
                if stream is not None and hasattr(stream, "aclose"):
                    await stream.aclose()
            finally:
                if lease is not None:
                    self._leave(lease, outcome, code)
                self._record(target, "stream", request_id, start, outcome, code, usage, attempt, session_id, turn_id)


# Process lifetime only. Restarting clears cooldowns and the bounded diagnostic ring.
model_gateway = AIGateway()
