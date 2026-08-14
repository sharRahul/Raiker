from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class SupervisorProtocolError(RuntimeError):
    pass


class AuthenticationFailed(SupervisorProtocolError):
    pass


class ReplayRejected(SupervisorProtocolError):
    pass


class FrameTooLarge(SupervisorProtocolError):
    pass


@dataclass(frozen=True)
class SupervisorFrame:
    version: int
    kind: str
    nonce: str
    issued_at: int
    payload: dict[str, Any]


class SupervisorCodec:
    VERSION = 1

    def __init__(
        self,
        instance_key: bytes,
        *,
        max_frame_bytes: int = 1_048_576,
        nonce_factory: Callable[[], str] | None = None,
        clock: Callable[[], float] | None = None,
        max_clock_skew_seconds: int = 300,
    ) -> None:
        if len(instance_key) < 32:
            raise ValueError("supervisor_instance_key_too_short")
        self._key = instance_key
        self._max_frame_bytes = max_frame_bytes
        self._nonce_factory = nonce_factory or (lambda: secrets.token_hex(16))
        self._clock = clock or time.time
        self._max_clock_skew_seconds = max_clock_skew_seconds
        self._seen_nonces: set[str] = set()

    @staticmethod
    def _canonical(value: dict[str, Any]) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    def encode(self, kind: str, payload: dict[str, Any]) -> bytes:
        if not kind or not isinstance(payload, dict):
            raise ValueError("supervisor_frame_invalid")
        authenticated = {
            "issued_at": int(self._clock()),
            "kind": kind,
            "nonce": self._nonce_factory(),
            "payload": payload,
            "version": self.VERSION,
        }
        authenticated["mac"] = hmac.new(
            self._key, self._canonical(authenticated), hashlib.sha256
        ).hexdigest()
        body = self._canonical(authenticated)
        if len(body) > self._max_frame_bytes:
            raise FrameTooLarge("supervisor_frame_too_large")
        return len(body).to_bytes(4, "big") + body

    def decode(self, frame: bytes) -> SupervisorFrame:
        if len(frame) < 4:
            raise ValueError("supervisor_frame_length_invalid")
        size = int.from_bytes(frame[:4], "big")
        if size > self._max_frame_bytes:
            raise FrameTooLarge("supervisor_frame_too_large")
        if size != len(frame) - 4:
            raise ValueError("supervisor_frame_length_invalid")
        try:
            value = json.loads(frame[4:])
            supplied_mac = str(value.pop("mac"))
            expected_mac = hmac.new(
                self._key, self._canonical(value), hashlib.sha256
            ).hexdigest()
        except Exception as exc:
            raise AuthenticationFailed("supervisor_frame_authentication_failed") from exc
        if not hmac.compare_digest(supplied_mac, expected_mac):
            raise AuthenticationFailed("supervisor_frame_authentication_failed")
        try:
            version = int(value["version"])
            kind = str(value["kind"])
            nonce = str(value["nonce"])
            issued_at = int(value["issued_at"])
            payload = dict(value["payload"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationFailed("supervisor_frame_contract_invalid") from exc
        if version != self.VERSION:
            raise AuthenticationFailed("supervisor_frame_version_unsupported")
        if abs(int(self._clock()) - issued_at) > self._max_clock_skew_seconds:
            raise AuthenticationFailed("supervisor_frame_expired")
        if nonce in self._seen_nonces:
            raise ReplayRejected("supervisor_frame_replayed")
        self._seen_nonces.add(nonce)
        return SupervisorFrame(version, kind, nonce, issued_at, payload)
