from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from raiker.auth.app_key import app_fernet
from raiker.runtime.identity.contracts import (
    IDENTITY_AUDIENCE,
    IDENTITY_SCHEMA_VERSION,
    MachineAttestation,
    MachineIdentityClaims,
    MachineIdentityError,
    b64url_encode,
)
from raiker.storage.sqlite import SQLiteStore


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class WorkspaceIdentityIssuer:
    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = store

    def _issuer_key(self) -> dict[str, Any]:
        existing = self.store.get_active_machine_issuer_key()
        if existing is not None:
            return existing
        private_key = Ed25519PrivateKey.generate()
        private_seed = private_key.private_bytes_raw()
        return self.store.create_machine_issuer_key_if_absent(
            workspace_id=f"ws_{uuid4().hex}",
            key_id=f"mkey_{uuid4().hex}",
            public_key=private_key.public_key().public_bytes_raw(),
            private_key_encrypted=app_fernet(self.workspace_root).encrypt(private_seed),
        )

    def mint(
        self,
        *,
        owner_principal_id: str,
        session_id: str,
        turn_id: str,
        role_ids: tuple[str, ...],
        ttl_seconds: int,
        now: datetime | None = None,
        principal_id: str | None = None,
        parent_principal_id: str | None = None,
    ) -> MachineAttestation:
        owner = self.store.get_principal(owner_principal_id)
        if owner is None and owner_principal_id == "local_user":
            # Embedded/terminal compatibility: older local-only entry points
            # use this well-known owner without an account bootstrap. They still
            # receive a signed per-turn machine identity; this creates the
            # delegation anchor, not an authentication bypass for remote APIs.
            self.store.insert_principal(
                principal_id="local_user",
                principal_type="human",
                display_name="Local workspace owner",
                is_active=True,
            )
            owner = self.store.get_principal(owner_principal_id)
        if owner is None or not bool(owner.get("is_active")):
            raise MachineIdentityError("machine_identity_delegation_mismatch")
        if ttl_seconds <= 0:
            raise MachineIdentityError("machine_identity_malformed")
        key = self._issuer_key()
        issued = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
        expires = issued + timedelta(seconds=ttl_seconds)
        machine_principal_id = principal_id or f"principal_turn_agent_{uuid4().hex}"
        workspace_id = str(key["workspace_id"])
        key_id = str(key["key_id"])
        token_id = f"mti_{uuid4().hex}"
        subject = f"spiffe://raiker/{workspace_id}/agent/turn/{turn_id}"
        claims = MachineIdentityClaims(
            version=IDENTITY_SCHEMA_VERSION,
            issuer=f"raiker-workspace:{workspace_id}",
            key_id=key_id,
            subject=subject,
            principal_id=machine_principal_id,
            principal_type="ai_agent",
            owner_principal_id=owner_principal_id,
            workspace_id=workspace_id,
            session_id=session_id,
            turn_id=turn_id,
            role_ids=tuple(role_ids),
            audience=IDENTITY_AUDIENCE,
            issued_at=_timestamp(issued),
            expires_at=_timestamp(expires),
            token_id=token_id,
        )
        encrypted_seed = bytes(key["private_key_encrypted"])
        private_seed = app_fernet(self.workspace_root).decrypt(encrypted_seed)
        signature = Ed25519PrivateKey.from_private_bytes(private_seed).sign(
            claims.canonical_bytes()
        )
        token = f"{b64url_encode(claims.canonical_bytes())}.{b64url_encode(signature)}"

        existing_principal = self.store.get_principal(machine_principal_id)
        if existing_principal is None:
            self.store.insert_principal(
                principal_id=machine_principal_id,
                principal_type="ai_agent",
                display_name=f"Raiker agent · {turn_id}",
                delegated_by_user_id=(
                    str(owner["delegated_by_user_id"])
                    if owner.get("delegated_by_user_id") else None
                ),
                session_id=session_id,
                role_ids=tuple(role_ids),
                expires_at=claims.expires_at,
                is_active=True,
            )
            self.store.insert_turn_machine_identity(
                {
                    **claims.__dict__,
                    "parent_principal_id": parent_principal_id,
                }
            )
        else:
            identity = self.store.get_turn_machine_identity(machine_principal_id)
            if identity is None or any(
                str(identity[field]) != expected
                for field, expected in (
                    ("owner_principal_id", owner_principal_id),
                    ("session_id", session_id),
                    ("turn_id", turn_id),
                    ("subject", subject),
                )
            ):
                raise MachineIdentityError("machine_identity_principal_mismatch")
            self.store.rotate_turn_machine_identity(
                machine_principal_id,
                token_id=token_id,
                issued_at=claims.issued_at,
                expires_at=claims.expires_at,
            )
            self.store.reactivate_machine_principal(
                machine_principal_id, expires_at=claims.expires_at
            )
        return MachineAttestation(token=token, claims=claims)
