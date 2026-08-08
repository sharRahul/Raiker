from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.identity.contracts import MachineIdentityClaims
from raiker.runtime.identity.issuer import WorkspaceIdentityIssuer
from raiker.storage.sqlite import SQLiteStore

DEFAULT_TURN_IDENTITY_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class TrustedTurnIdentity:
    token: str
    claims: MachineIdentityClaims


class TurnMachineIdentityLifecycle:
    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore | None = None,
        writer: EventLogWriter | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = store or SQLiteStore(self.workspace_root)
        self.writer = writer or EventLogWriter(self.store)
        self.issuer = WorkspaceIdentityIssuer(self.workspace_root, self.store)

    def start(
        self,
        *,
        owner_principal_id: str,
        session_id: str,
        turn_id: str,
        role_ids: tuple[str, ...],
        principal_id: str | None = None,
        parent_principal_id: str | None = None,
    ) -> TrustedTurnIdentity:
        issued = self.issuer.mint(
            owner_principal_id=owner_principal_id,
            session_id=session_id,
            turn_id=turn_id,
            role_ids=role_ids,
            ttl_seconds=DEFAULT_TURN_IDENTITY_TTL_SECONDS,
            principal_id=principal_id,
            parent_principal_id=parent_principal_id,
        )
        self._event("machine_identity_issued", issued.claims, parent_principal_id)
        return TrustedTurnIdentity(token=issued.token, claims=issued.claims)

    def rotate(
        self,
        *,
        owner_principal_id: str,
        session_id: str,
        turn_id: str,
        principal_id: str,
        role_ids: tuple[str, ...],
    ) -> TrustedTurnIdentity:
        issued = self.issuer.mint(
            owner_principal_id=owner_principal_id,
            session_id=session_id,
            turn_id=turn_id,
            role_ids=role_ids,
            ttl_seconds=DEFAULT_TURN_IDENTITY_TTL_SECONDS,
            principal_id=principal_id,
        )
        self._event("machine_identity_rotated", issued.claims)
        return TrustedTurnIdentity(token=issued.token, claims=issued.claims)

    def finish(self, identity: TrustedTurnIdentity) -> None:
        principal_id = identity.claims.principal_id
        self.store.deactivate_turn_machine_identity(principal_id)
        self.store.deactivate_principal(principal_id)
        self._event("machine_identity_deactivated", identity.claims)

    def _event(
        self,
        event_type: str,
        claims: MachineIdentityClaims,
        parent_principal_id: str | None = None,
    ) -> None:
        self.writer.append(
            make_event(
                session_id=claims.session_id,
                turn_id=claims.turn_id,
                event_type=event_type,
                actor="machine_identity_issuer",
                payload={
                    "principal_id": claims.principal_id,
                    "principal_type": claims.principal_type,
                    "subject": claims.subject,
                    "key_id": claims.key_id,
                    "token_id": claims.token_id,
                    "audience": claims.audience,
                    "issued_at": claims.issued_at,
                    "expires_at": claims.expires_at,
                    **(
                        {"parent_principal_id": parent_principal_id}
                        if parent_principal_id else {}
                    ),
                },
            )
        )
