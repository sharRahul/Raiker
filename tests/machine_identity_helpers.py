from __future__ import annotations

from typing import Any

from raiker.contracts.models import PolicyDecision, ToolAction, ToolResult
from raiker.runtime.identity.lifecycle import (
    TrustedTurnIdentity,
    TurnMachineIdentityLifecycle,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class IdentityBoundTestBroker(ToolBroker):
    """Direct-broker test harness that models the production turn issuer."""

    def execute(  # type: ignore[override]
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
        machine_identity: TrustedTurnIdentity | None = None,
        **kwargs: Any,
    ) -> tuple[ToolResult, PolicyDecision]:
        store = self.store or SQLiteStore(self.workspace_root)
        owner = self.owner_scope or self.principal_id
        effective_turn_id = turn_id or "turn_test"
        identity = machine_identity or TurnMachineIdentityLifecycle(
            self.workspace_root, store, self.writer
        ).start(
            owner_principal_id=owner,
            session_id=session_id,
            turn_id=effective_turn_id,
            role_ids=("assistant",),
        )
        return super().execute(
            action,
            session_id=session_id,
            turn_id=effective_turn_id,
            machine_identity=identity,
            **kwargs,
        )
