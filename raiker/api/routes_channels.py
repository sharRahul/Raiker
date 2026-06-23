from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from raiker.api.schemas import InboundChannelMessage
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# Inbound channel receiver (Phase 4 slice 4 / Phase 8 gate). Inbound traffic is
# authenticated by an owner-set channel secret (NOT the owner bearer token) and
# is ALWAYS labelled untrusted + quarantined: it records a message and emits a
# governed event, and never executes anything or grants any authority.


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _enabled_pairing(store: SQLiteStore, connector_id: str) -> dict[str, Any] | None:
    for pairing in store.list_channel_pairings(enabled_only=True):
        if pairing.get("connector_id") == connector_id:
            return pairing
    return None


@router.post("/api/channels/{connector_id}/inbound")
async def receive_inbound(
    connector_id: str,
    body: InboundChannelMessage,
    request: Request,
    x_raiker_channel_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    secret = os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
    if not secret:
        # Fail closed: no inbound until the owner configures a channel secret.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ok": False, "reason_code": "channel_inbound_disabled"},
        )
    if not x_raiker_channel_secret or not hmac.compare_digest(x_raiker_channel_secret, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "reason_code": "invalid_channel_secret"},
        )

    store = SQLiteStore(_ws(request))
    writer = EventLogWriter(store)
    pairing = _enabled_pairing(store, connector_id)
    if pairing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "channel_not_paired_or_disabled"},
        )

    try:
        allowlist = set(json.loads(pairing.get("sender_allowlist_json") or "[]"))
    except (json.JSONDecodeError, TypeError):
        allowlist = set()

    channel_message_id = new_id("chn_")
    channel_type = str(pairing.get("channel_type", "webhooks"))
    preview, _ = redact_text(body.text[:200])

    if body.sender_id not in allowlist:
        writer.append(make_event(
            session_id="channels",
            turn_id=None,
            event_type="channel_message_rejected",
            actor="channel_receiver",
            payload={
                "connector_id": connector_id,
                "channel_type": channel_type,
                "sender_id": body.sender_id,
                "trust_level": "untrusted",
                "reason": "sender_not_allowlisted",
            },
        ))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "ok": False,
                "reason_code": "sender_not_allowlisted",
                "trust_level": "untrusted",
                "quarantined": True,
            },
        )

    # Allowlisted sender: still untrusted + quarantined; instructions are inert.
    writer.append(make_event(
        session_id="channels",
        turn_id=None,
        event_type="channel_message_received",
        actor="channel_receiver",
        payload={
            "channel_message_id": channel_message_id,
            "connector_id": connector_id,
            "channel_type": channel_type,
            "sender_id": body.sender_id,
            "trust_level": "untrusted",
            "quarantined": True,
            "instructions_inert": True,
            "preview": preview,
        },
    ))
    return {
        "ok": True,
        "channel_message_id": channel_message_id,
        "trust_level": "untrusted",
        "quarantined": True,
    }
