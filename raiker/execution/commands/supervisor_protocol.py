from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: The instance key travels between Raiker and the native supervisor as
#: lowercase hex, because an environment block carries text and a raw 32-byte
#: value would be mangled by any encoding on the way. Both sides decode to raw
#: bytes **before** keying. Leaving that unstated is how one implementation ends
#: up keying on 64 ASCII characters while the other keys on 32 bytes, and
#: nothing authenticates — which no protocol vector catches, because vectors fix
#: the key.
INSTANCE_KEY_BYTES = 32


def instance_key_from_hex(value: str) -> bytes:
    key = bytes.fromhex(value.strip())
    if len(key) < INSTANCE_KEY_BYTES:
        raise ValueError("supervisor_instance_key_too_short")
    return key


def instance_key_to_hex(key: bytes) -> str:
    if len(key) < INSTANCE_KEY_BYTES:
        raise ValueError("supervisor_instance_key_too_short")
    return key.hex()


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
        self._seen_nonces: dict[str, int] = {}

    @staticmethod
    def _canonical(value: dict[str, Any]) -> bytes:
        """The exact bytes both implementations authenticate.

        ``ensure_ascii`` is the whole point of this method existing. Python's
        default escapes every non-ASCII code point (``café`` becomes
        ``caf\\u00e9``); Rust's ``serde_json`` emits raw UTF-8. Keyed over
        different bytes, the two MACs disagree on any frame carrying non-ASCII
        program output — that is, on real command output — and every such frame
        fails authentication. Floats are refused rather than serialised because
        their shortest round-trip representation is not identical across the two
        languages, so a payload that authenticated once might not authenticate
        twice.
        """
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def _reject_floats(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, float):
            raise ValueError("supervisor_frame_float_unsupported")
        if isinstance(value, dict):
            for item in value.values():
                SupervisorCodec._reject_floats(item)
        elif isinstance(value, list | tuple):
            for item in value:
                SupervisorCodec._reject_floats(item)

    def encode(self, kind: str, payload: dict[str, Any]) -> bytes:
        if not kind or not isinstance(payload, dict):
            raise ValueError("supervisor_frame_invalid")
        self._reject_floats(payload)
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
        # A frame older than the skew window is already refused above, so a
        # nonce older than that window can never be replayed successfully and
        # does not need remembering. Without this the set grows for as long as
        # the process lives, which for a long-running supervisor connection is
        # an unbounded allocation driven by the peer.
        horizon = int(self._clock()) - self._max_clock_skew_seconds
        self._seen_nonces = {
            seen: seen_at for seen, seen_at in self._seen_nonces.items() if seen_at >= horizon
        }
        if nonce in self._seen_nonces:
            raise ReplayRejected("supervisor_frame_replayed")
        self._seen_nonces[nonce] = issued_at
        return SupervisorFrame(version, kind, nonce, issued_at, payload)
