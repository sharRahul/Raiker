from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    ChannelEnabledRequest,
    ChannelSendersRequest,
    ChannelTestDeliveryRequest,
    InboundChannelMessage,
    PairChannelRequest,
)
from raiker.api.sessions import ApiSession
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
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


# ── Owner surface (BUG-225) ──────────────────────────────────────────────────
#
# The transport existed and had no way in. These routes are the way in, and they
# are deliberately thin: every one delegates to the control service, which is
# human-only and owner-scoped, and the test delivery goes through the governed
# `external_channel_runtime` capability rather than posting the webhook itself.


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _service(request: Request) -> Any:
    from raiker.control.dashboard import DashboardService

    return DashboardService(_ws(request))


def _channel_result(result: Any) -> dict[str, Any]:
    """Map a ControlResult onto a response, keeping the governed reason.

    422 for something the owner typed, 403 for a gate or an authority refusal —
    the same split the MCP routes use, so one reason code has one remedy wherever
    it is met.
    """
    if result.ok:
        return {"ok": True, **result.data}
    reason = result.reason_code or ""
    if (
        reason.startswith("unknown_connector")
        or reason.startswith("unknown_channel_pairing")
        or reason in {"channel_already_paired", "sender_allowlist_required"}
    ):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_403_FORBIDDEN
    raise HTTPException(status_code=code, detail={"ok": False, "reason_code": reason})


@router.get("/api/channels")
async def list_channels(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Every connector profile and what is actually true of it right now.

    Read-only. Reports linked, enabled, sender count, the capability gate, the
    egress allowlist and the inbound secret as separate facts, because each has a
    different remedy and collapsing them into one "ready" flag is what made this
    surface unable to say anything useful in the first place.
    """
    return _service(request).list_channels(auth_data[0].principal_id)


@router.post("/api/channels/pairings")
async def pair_channel(
    body: PairChannelRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Pair a connector. Paired is **not** enabled — that is a second decision."""
    return _channel_result(
        _service(request).pair_channel(
            auth_data[0].principal_id,
            body.connector_id,
            body.display_name or "",
            list(body.senders or []),
        )
    )


@router.put("/api/channels/pairings/{pairing_id}/enabled")
async def set_channel_enabled(
    pairing_id: str,
    body: ChannelEnabledRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _channel_result(
        _service(request).set_channel_enabled(auth_data[0].principal_id, pairing_id, body.enabled)
    )


@router.put("/api/channels/pairings/{pairing_id}/senders")
async def set_channel_senders(
    pairing_id: str,
    body: ChannelSendersRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Replace the sender allowlist. This is what the inbound receiver enforces."""
    return _channel_result(
        _service(request).set_channel_senders(
            auth_data[0].principal_id, pairing_id, list(body.senders or [])
        )
    )


@router.delete("/api/channels/pairings/{pairing_id}")
async def unpair_channel(
    pairing_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _channel_result(
        _service(request).unpair_channel(auth_data[0].principal_id, pairing_id)
    )


@router.post("/api/channels/deliver-test")
async def deliver_channel_test(
    body: ChannelTestDeliveryRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Send one test delivery through the governed outbound path.

    Not a shortcut: this builds a governed action and routes it through the
    runtime authority, so a closed `external_channel_runtime` gate refuses it
    with `disabled_by_capability_gate` and an unallowlisted host refuses it at
    the egress boundary — exactly as a real delivery would.
    """
    return _channel_result(
        _service(request).deliver_channel_test(
            auth_data[0].principal_id, body.connector_id, body.url, body.text
        )
    )


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
