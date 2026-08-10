"""Identity binding for delegated subagent results (BUG-78).

Raiker already issues and verifies a signed per-turn machine identity
(:mod:`raiker.runtime.identity`), and a spawned subagent already runs under its
own child identity. Delegation was the one governed hand-off that did not use
it: the subagent's findings re-entered the parent turn as a source with nothing
tying them to the spawn that produced them, and the parent performed no
verification step before treating them as material.

The gap is narrower than the networked case OWASP ASI07 addresses — delegation
is in-process, so forging a result already requires local code execution — but
it is real in the audit trail: with several spawns in one turn, nothing could
prove *which* spawn produced a given result.

This module closes it. At delegation the runner mints a spawn-scoped attestation
signed by the workspace issuer key, binding the subagent id, its child
principal, the owner, the session and turn, and a digest of the result the
parent is about to read. The parent verifies that attestation before the result
becomes a turn source, and the binding is recorded on the hash-chained event so
the delegation is provable after the fact.

A completed spawn is deliberately *not* required to still be active: the runner
deactivates the child identity as it finishes, and refusing a result because its
spawn has ended would refuse every result. What must still hold is that the
identity row exists and agrees with the attestation on every field.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.runtime.identity.contracts import (
    MachineIdentityError,
    b64url_decode,
    b64url_encode,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

__all__ = [
    "DelegationClaims",
    "DelegationError",
    "result_digest",
    "sign_delegation",
    "verify_delegation",
]

DELEGATION_AUDIENCE = "turn_sources"
DELEGATION_SCHEMA_VERSION = 1


class DelegationError(ValueError):
    """A delegated result could not be bound to the spawn that produced it."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class DelegationClaims:
    """What one delegation asserts. Metadata and a digest — never the findings."""

    version: int
    subagent_id: str
    spawn_principal_id: str
    parent_principal_id: str
    owner_principal_id: str
    session_id: str
    turn_id: str
    spawn_turn_id: str
    subject: str
    audience: str
    result_digest: str
    issued_at: str

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> DelegationClaims:
        required = {field for field in cls.__dataclass_fields__}
        if set(raw) != required:
            raise DelegationError("delegation_attestation_malformed")
        try:
            return cls(
                version=int(raw["version"]),
                subagent_id=str(raw["subagent_id"]),
                spawn_principal_id=str(raw["spawn_principal_id"]),
                parent_principal_id=str(raw["parent_principal_id"]),
                owner_principal_id=str(raw["owner_principal_id"]),
                session_id=str(raw["session_id"]),
                turn_id=str(raw["turn_id"]),
                spawn_turn_id=str(raw["spawn_turn_id"]),
                subject=str(raw["subject"]),
                audience=str(raw["audience"]),
                result_digest=str(raw["result_digest"]),
                issued_at=str(raw["issued_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DelegationError("delegation_attestation_malformed") from exc


def result_digest(content: str) -> str:
    """A stable digest of the findings the parent will read.

    The digest is what binds the attestation to *this* result rather than to the
    spawn in general, so a result swapped between two spawns in the same turn
    fails verification instead of being silently consumed.
    """
    return sha256(content.encode("utf-8")).hexdigest()


def _issuer_key(store: SQLiteStore) -> dict[str, Any]:
    key = store.get_active_machine_issuer_key()
    if key is None:
        raise DelegationError("delegation_issuer_key_missing")
    return key


def sign_delegation(
    workspace_root: str | Path,
    store: SQLiteStore,
    *,
    subagent_id: str,
    spawn_principal_id: str,
    parent_principal_id: str,
    owner_principal_id: str,
    session_id: str,
    turn_id: str,
    spawn_turn_id: str,
    subject: str,
    content: str,
) -> str:
    """Mint the attestation token binding *content* to this spawn."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from raiker.auth.app_key import app_fernet

    key = _issuer_key(store)
    claims = DelegationClaims(
        version=DELEGATION_SCHEMA_VERSION,
        subagent_id=subagent_id,
        spawn_principal_id=spawn_principal_id,
        parent_principal_id=parent_principal_id,
        owner_principal_id=owner_principal_id,
        session_id=session_id,
        turn_id=turn_id,
        spawn_turn_id=spawn_turn_id,
        subject=subject,
        audience=DELEGATION_AUDIENCE,
        result_digest=result_digest(content),
        issued_at=utc_now(),
    )
    seed = app_fernet(Path(workspace_root).resolve()).decrypt(bytes(key["private_key_encrypted"]))
    signature = Ed25519PrivateKey.from_private_bytes(seed).sign(claims.canonical_bytes())
    return f"{b64url_encode(claims.canonical_bytes())}.{b64url_encode(signature)}"


def verify_delegation(
    store: SQLiteStore,
    token: str,
    *,
    expected_owner_principal_id: str,
    expected_session_id: str,
    expected_turn_id: str,
    expected_content: str,
) -> DelegationClaims:
    """Verify one delegated result, or raise :class:`DelegationError`.

    Fail-closed at every step: a malformed token, an unknown issuer key, a bad
    signature, a mismatched owner/session/turn, a digest that does not cover the
    content the parent is holding, or a spawn identity that does not exist or
    disagrees with the attestation all refuse the result.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if not isinstance(token, str) or token.count(".") != 1:
        raise DelegationError("delegation_attestation_malformed")
    encoded_payload, encoded_signature = token.split(".")
    try:
        payload = b64url_decode(encoded_payload)
        signature = b64url_decode(encoded_signature)
    except MachineIdentityError as exc:
        raise DelegationError("delegation_attestation_malformed") from exc
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DelegationError("delegation_attestation_malformed") from exc
    if not isinstance(raw, dict):
        raise DelegationError("delegation_attestation_malformed")
    claims = DelegationClaims.from_mapping(raw)
    if claims.version != DELEGATION_SCHEMA_VERSION:
        raise DelegationError("delegation_attestation_malformed")
    if claims.audience != DELEGATION_AUDIENCE:
        raise DelegationError("delegation_wrong_audience")

    key = _issuer_key(store)
    try:
        Ed25519PublicKey.from_public_bytes(bytes(key["public_key"])).verify(signature, payload)
    except (InvalidSignature, ValueError) as exc:
        raise DelegationError("delegation_invalid_signature") from exc

    if claims.owner_principal_id != expected_owner_principal_id:
        raise DelegationError("delegation_owner_mismatch")
    if claims.session_id != expected_session_id:
        raise DelegationError("delegation_session_mismatch")
    if claims.turn_id != expected_turn_id:
        raise DelegationError("delegation_turn_mismatch")
    if claims.result_digest != result_digest(expected_content):
        raise DelegationError("delegation_result_mismatch")

    identity = store.get_turn_machine_identity(claims.spawn_principal_id)
    if identity is None:
        raise DelegationError("delegation_spawn_unknown")
    for field, expected in (
        ("owner_principal_id", claims.owner_principal_id),
        ("session_id", claims.session_id),
        ("turn_id", claims.spawn_turn_id),
        ("subject", claims.subject),
    ):
        if str(identity.get(field, "")) != expected:
            raise DelegationError("delegation_spawn_mismatch")
    return claims
