"""Run-scoped authenticated capabilities for the command egress proxy."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class EgressTokenClaims:
    owner_principal_id: str
    profile_id: str
    run_id: str
    grant_digest: str
    nonce: str
    expires_at: int

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.owner_principal_id,
                self.profile_id,
                self.run_id,
                self.grant_digest,
                self.nonce,
            )
        ) or self.expires_at <= 0:
            raise ValueError("egress_token_claims_invalid")

    def payload(self) -> bytes:
        return json.dumps(
            {
                "expires_at": self.expires_at,
                "grant_digest": self.grant_digest,
                "nonce": self.nonce,
                "owner_principal_id": self.owner_principal_id,
                "profile_id": self.profile_id,
                "run_id": self.run_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


class EgressTokenAuthority:
    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("egress_token_key_too_short")
        self._key = key
        self._used: set[str] = set()
        self._lock = Lock()

    def issue(self, claims: EgressTokenClaims) -> str:
        payload = claims.payload()
        signature = hmac.new(self._key, payload, hashlib.sha256).digest()
        return ".".join(
            base64.urlsafe_b64encode(value).decode().rstrip("=")
            for value in (payload, signature)
        )

    def consume(
        self,
        token: str,
        *,
        owner_principal_id: str,
        profile_id: str,
        run_id: str,
        now: int | None = None,
    ) -> EgressTokenClaims:
        claims = self.verify(
            token,
            owner_principal_id=owner_principal_id,
            profile_id=profile_id,
            run_id=run_id,
            now=now,
        )
        token_digest = hashlib.sha256(token.encode()).hexdigest()
        with self._lock:
            if token_digest in self._used:
                raise ValueError("egress_token_replayed")
            self._used.add(token_digest)
        return claims

    def verify(
        self,
        token: str,
        *,
        owner_principal_id: str,
        profile_id: str,
        run_id: str,
        now: int | None = None,
    ) -> EgressTokenClaims:
        """Verify a scoped data-plane token without consuming the grant.

        A proxy credential is reused by standard HTTP clients when they open a
        second CONNECT tunnel.  The signed nonce still prevents substitution;
        one-shot control-plane operations use :meth:`consume` for replay
        rejection.
        """
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
            payload = _decode(encoded_payload)
            signature = _decode(encoded_signature)
            value = json.loads(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("egress_token_invalid") from exc
        expected = hmac.new(self._key, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("egress_token_invalid")
        claims = EgressTokenClaims(
            owner_principal_id=str(value.get("owner_principal_id", "")),
            profile_id=str(value.get("profile_id", "")),
            run_id=str(value.get("run_id", "")),
            grant_digest=str(value.get("grant_digest", "")),
            nonce=str(value.get("nonce", "")),
            expires_at=int(value.get("expires_at", 0)),
        )
        if (
            claims.owner_principal_id != owner_principal_id
            or claims.profile_id != profile_id
            or claims.run_id != run_id
        ):
            raise ValueError("egress_token_scope_mismatch")
        if claims.expires_at <= (int(time.time()) if now is None else now):
            raise ValueError("egress_token_expired")
        return claims


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
