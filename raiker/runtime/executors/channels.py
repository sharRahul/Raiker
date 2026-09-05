from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import TYPE_CHECKING

from raiker.channels.adapters import AdapterRefusal, adapter_for
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


def sign_delivery(body: bytes) -> tuple[str, bool]:
    """``(signature, signed)`` for one outbound body.

    The webhook connector profile declares transport ``signed_http_callback`` and
    auth ``signed_message_reference``. Until this existed, the executor POSTed an
    unsigned body — so a receiver had no way to tell a Raiker delivery from
    anything else that could reach the URL, and the profile's declaration was
    documentation rather than a fact.

    HMAC-SHA256 over the exact bytes sent, keyed by ``RAIKER_CHANNEL_OUTBOUND_SECRET``.
    The secret is read at delivery and never stored, logged or returned.

    **Unset means unsigned, not refused**, and that is deliberate: the owner
    controls both ends of a webhook they configured, and hard-blocking their own
    destination is prevention-by-restriction. The delivery says so in its summary
    and its artifacts, so an unsigned delivery is a visible state rather than a
    silent one, and a receiver that requires a signature simply rejects it.
    """
    secret = os.environ.get("RAIKER_CHANNEL_OUTBOUND_SECRET", "").strip()
    if not secret:
        return "", False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}", True


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
        text = str(action.arguments.get("text", ""))
        if not connector_id:
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

        channel_type = str(pairing.get("channel_type") or "webhooks")
        delivered_at = utc_now()

        # One adapter per channel type, resolved from a table rather than an
        # `if` chain here. What an adapter owns is the wire format and nothing
        # else: the gate, the egress allowlist, the pairing, the sender
        # allowlist and the audit event are all above this line and apply
        # identically whichever one answers.
        adapter = adapter_for(channel_type)
        if adapter is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"channel_transport_unsupported:{channel_type}",
                summary=f"Channel delivery denied: no wire format for '{channel_type}'.",
            )
        built = adapter.outbound(
            connector_id=connector_id,
            pairing=pairing,
            arguments=action.arguments,
            text=text,
            delivered_at=delivered_at,
        )
        if isinstance(built, AdapterRefusal):
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=built.reason_code, summary=built.summary,
            )
        url, body, headers, signed = built.url, built.body, built.headers, built.signed

        try:
            result = post_url(
                url, body, egress_allowlist=channel_egress_allowlist(), headers=headers
            )
        except SandboxError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=str(exc),
                summary="Channel delivery blocked (egress/transport).",
            )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=(
                f"Delivered to '{connector_id}' ({result['sent_bytes']}b)"
                # The adapter already said whether Raiker signs this transport;
                # asking it beats naming a platform here.
                + (", signed." if signed else ".")
            ),
            # Metadata only — never the message text, the target URL, or the
            # signature itself. For Telegram the URL matters twice over: it
            # carries the bot token.
            artifacts={
                "connector_id": connector_id,
                "channel_type": channel_type,
                "sent_bytes": result["sent_bytes"],
                "status": result["status"],
                "signed": signed,
            },
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
        if not bool(pairing.get("approval_relay_enabled")) or not str(
            pairing.get("owner_sender_id") or ""
        ):
            return ExecutionResult(
                ok=False,
                capability=self.capability,
                action_id=action.action_id,
                reason_code="channel_approval_relay_not_enabled",
                summary="Approval relay denied: bind the owner sender and enable relay first.",
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
