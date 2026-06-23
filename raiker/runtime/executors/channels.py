from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ApprovalRelayRecord
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, channel_egress_allowlist, post_url
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

# Reference channel: a single, bounded outbound connector (webhook transport).
# Outbound delivery is constrained by an owner-controlled egress allowlist; the
# relay is metadata-only (it queues a pending approval relay, it never resolves
# an approval). Inbound traffic is handled separately and always labelled
# untrusted (see raiker/api/routes_channels.py). This is the one reference
# transport for Phase 4 slice 4; other transports remain gated/fail-closed.


def _enabled_pairing(store: SQLiteStore, connector_id: str) -> dict | None:
    for pairing in store.list_channel_pairings(enabled_only=True):
        if pairing.get("connector_id") == connector_id:
            return pairing
    return None


class ExternalChannelExecutor:
    """Real executor for ``external_channel_runtime`` — bounded outbound webhook delivery."""

    capability = "external_channel_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        connector_id = str(action.arguments.get("connector_id", "")).strip()
        url = str(action.arguments.get("url", "")).strip()
        text = str(action.arguments.get("text", ""))
        if not connector_id or not url:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:connector_id_or_url",
                summary="Channel delivery denied: connector_id and url required.",
            )
        pairing = _enabled_pairing(self._store, connector_id)
        if pairing is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="channel_not_paired_or_disabled",
                summary="Channel delivery denied: connector is not paired/enabled.",
            )
        body = json.dumps({"text": text, "connector_id": connector_id}).encode("utf-8")
        try:
            result = post_url(url, body, egress_allowlist=channel_egress_allowlist())
        except SandboxError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=str(exc),
                summary="Channel delivery blocked (egress/transport).",
            )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Delivered to '{connector_id}' ({result['sent_bytes']}b).",
            # Metadata only — never the message text or the target URL.
            artifacts={"connector_id": connector_id, "sent_bytes": result["sent_bytes"], "status": result["status"]},
        )


class ChannelApprovalRelayExecutor:
    """Real executor for ``channel_approval_relay`` — metadata-only pending relay.

    Records a *pending* approval relay for a paired channel. It never resolves
    an approval (resolution stays metadata-only / owner-only), matching Raiker's
    "approval resolution is metadata-only" posture.
    """

    capability = "channel_approval_relay"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        connector_id = str(action.arguments.get("connector_id", "")).strip()
        relayed_action_id = str(action.arguments.get("relayed_action_id", "")).strip()
        if not connector_id or not relayed_action_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:connector_id_or_relayed_action_id",
                summary="Approval relay denied: connector_id and relayed_action_id required.",
            )
        pairing = _enabled_pairing(self._store, connector_id)
        if pairing is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="channel_not_paired_or_disabled",
                summary="Approval relay denied: connector is not paired/enabled.",
            )
        relay = ApprovalRelayRecord(
            relay_id=new_id("chr_"),
            pairing_id=str(pairing["pairing_id"]),
            action_id=relayed_action_id,
            status="pending",
            requested_at=utc_now(),
            resolved_at=None,
            resolved_by=None,
        )
        self._store.insert_approval_relay(relay)
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Approval relay queued (pending). Resolution remains metadata-only/owner-only.",
            artifacts={"relay_id": relay.relay_id, "connector_id": connector_id, "status": "pending"},
        )
