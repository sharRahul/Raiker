from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

IDENTITY_AUDIENCE = "tool_broker"
IDENTITY_SCHEMA_VERSION = 1


class MachineIdentityError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class MachineIdentityClaims:
    version: int
    issuer: str
    key_id: str
    subject: str
    principal_id: str
    principal_type: str
    owner_principal_id: str
    workspace_id: str
    session_id: str
    turn_id: str
    role_ids: tuple[str, ...]
    audience: str
    issued_at: str
    expires_at: str
    token_id: str

    def canonical_bytes(self) -> bytes:
        payload = asdict(self)
        payload["role_ids"] = list(self.role_ids)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> MachineIdentityClaims:
        required = {field.name for field in cls.__dataclass_fields__.values()}
        if set(raw) != required or not isinstance(raw.get("role_ids"), list):
            raise MachineIdentityError("machine_identity_malformed")
        try:
            return cls(
                version=int(raw["version"]),
                issuer=str(raw["issuer"]),
                key_id=str(raw["key_id"]),
                subject=str(raw["subject"]),
                principal_id=str(raw["principal_id"]),
                principal_type=str(raw["principal_type"]),
                owner_principal_id=str(raw["owner_principal_id"]),
                workspace_id=str(raw["workspace_id"]),
                session_id=str(raw["session_id"]),
                turn_id=str(raw["turn_id"]),
                role_ids=tuple(str(item) for item in raw["role_ids"]),
                audience=str(raw["audience"]),
                issued_at=str(raw["issued_at"]),
                expires_at=str(raw["expires_at"]),
                token_id=str(raw["token_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MachineIdentityError("machine_identity_malformed") from exc


@dataclass(frozen=True)
class MachineAttestation:
    token: str
    claims: MachineIdentityClaims


@dataclass(frozen=True)
class VerifiedMachineIdentity:
    claims: MachineIdentityClaims
    token_fingerprint: str


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    if not value or any(character.isspace() for character in value):
        raise MachineIdentityError("machine_identity_malformed")
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, TypeError) as exc:
        raise MachineIdentityError("machine_identity_malformed") from exc


def token_fingerprint(token: str) -> str:
    return sha256(token.encode("ascii")).hexdigest()
