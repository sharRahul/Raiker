from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from raiker.runtime.identity.contracts import (
    IDENTITY_SCHEMA_VERSION,
    MachineIdentityClaims,
    MachineIdentityError,
    VerifiedMachineIdentity,
    b64url_decode,
    token_fingerprint,
)
from raiker.storage.sqlite import SQLiteStore


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MachineIdentityError("machine_identity_malformed") from exc
    if parsed.tzinfo is None:
        raise MachineIdentityError("machine_identity_malformed")
    return parsed.astimezone(UTC)


def _same(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


class MachineIdentityVerifier:
    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = store

    def verify(
        self,
        token: str,
        *,
        expected_owner_principal_id: str,
        expected_session_id: str,
        expected_turn_id: str,
        expected_audience: str,
        now: datetime | None = None,
    ) -> VerifiedMachineIdentity:
        if not isinstance(token, str) or token.count(".") != 1:
            raise MachineIdentityError("machine_identity_malformed")
        encoded_payload, encoded_signature = token.split(".")
        payload = b64url_decode(encoded_payload)
        signature = b64url_decode(encoded_signature)
        try:
            raw = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MachineIdentityError("machine_identity_malformed") from exc
        if not isinstance(raw, dict):
            raise MachineIdentityError("machine_identity_malformed")
        claims = MachineIdentityClaims.from_mapping(raw)
        key = self.store.get_machine_issuer_key(claims.key_id)
        if key is None:
            raise MachineIdentityError("machine_identity_unknown_key")
        try:
            Ed25519PublicKey.from_public_bytes(bytes(key["public_key"])).verify(
                signature, payload
            )
        except (InvalidSignature, ValueError) as exc:
            raise MachineIdentityError("machine_identity_invalid_signature") from exc

        if claims.version != IDENTITY_SCHEMA_VERSION:
            raise MachineIdentityError("machine_identity_malformed")
        workspace_id = str(key["workspace_id"])
        if not _same(claims.workspace_id, workspace_id) or not _same(
            claims.issuer, f"raiker-workspace:{workspace_id}"
        ):
            raise MachineIdentityError("machine_identity_workspace_mismatch")
        if not _same(claims.audience, expected_audience):
            raise MachineIdentityError("machine_identity_wrong_audience")
        if not _same(claims.owner_principal_id, expected_owner_principal_id):
            raise MachineIdentityError("machine_identity_delegation_mismatch")
        if not _same(claims.session_id, expected_session_id):
            raise MachineIdentityError("machine_identity_session_mismatch")
        if not _same(claims.turn_id, expected_turn_id):
            raise MachineIdentityError("machine_identity_turn_mismatch")
        current = (now or datetime.now(UTC)).astimezone(UTC)
        if current < _parse_timestamp(claims.issued_at):
            raise MachineIdentityError("machine_identity_malformed")
        if current > _parse_timestamp(claims.expires_at):
            raise MachineIdentityError("machine_identity_expired")

        principal = self.store.get_principal(claims.principal_id)
        identity = self.store.get_turn_machine_identity(claims.principal_id)
        if principal is None or identity is None:
            raise MachineIdentityError("machine_identity_principal_mismatch")
        if str(principal.get("principal_type")) != "ai_agent":
            raise MachineIdentityError("machine_identity_principal_mismatch")
        if not bool(principal.get("is_active")) or not bool(identity.get("is_active")):
            raise MachineIdentityError("machine_identity_inactive_principal")
        for field, expected in (
            ("owner_principal_id", claims.owner_principal_id),
            ("workspace_id", claims.workspace_id),
            ("session_id", claims.session_id),
            ("turn_id", claims.turn_id),
            ("subject", claims.subject),
            ("key_id", claims.key_id),
            ("token_id", claims.token_id),
        ):
            if not _same(str(identity.get(field, "")), expected):
                raise MachineIdentityError("machine_identity_principal_mismatch")
        return VerifiedMachineIdentity(
            claims=claims,
            token_fingerprint=token_fingerprint(token),
        )
