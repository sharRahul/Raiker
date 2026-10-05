from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import (
    ChannelApprovalResponse,
    ChannelDestinationRequest,
    ChannelEnabledRequest,
    ChannelRoutingRequest,
    ChannelSendersRequest,
    ChannelTestDeliveryRequest,
    InboundChannelMessage,
    PairChannelRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.api.wire.channels import (
    ApprovalRelayAnswered,
    ChannelDestinationSet,
    ChannelEnabledSet,
    ChannelInboundAccepted,
    ChannelPaired,
    ChannelRoutingSet,
    ChannelSendersSet,
    ChannelTestDelivered,
    ChannelUnpaired,
    ChannelUpdateIgnored,
    InboundRoute,
)
from raiker.channels.adapters import adapter_for
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
)
from raiker.control.views.extensions import ChannelsView
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
from raiker.runtime.identity.presentation import owner_user_metadata
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# Inbound channel receiver (Phase 4 slice 4 / Phase 8 gate). Inbound traffic is
# authenticated by an owner-set channel secret (NOT the owner bearer token).
# Content remains structurally untrusted; only an owner-stored route may place
# it in a governed turn, and doing so never increases that turn's authority.


def _enabled_pairing(store: SQLiteStore, connector_id: str) -> dict[str, Any] | None:
    for pairing in store.list_channel_pairings(enabled_only=True):
        if pairing.get("connector_id") == connector_id:
            return pairing
    return None


# ── Inbound rate limit (BUG-225) ─────────────────────────────────────────────
#
# An allowlisted sender was unbounded. Allowlisting says *who* may speak; it says
# nothing about *how often*, and the two are different questions — a compromised
# or merely broken allowlisted client could fill the event log as fast as it
# could post, and every message is written to durable storage before anything
# else looks at it.
#
# Fixed window, in memory, per (connector, sender) — the same shape and the same
# trade-off as `RateLimitMiddleware`: process-local, reset by a restart, and a
# denial-of-service guardrail rather than an auth boundary. The allowlist is
# still the gate; this is the budget behind it.
#
# A refusal is *recorded*, not silent: a sender that hits the limit produces a
# `channel_message_rejected` event with `reason: rate_limited`, so a channel that
# stops working is answerable from Observability rather than by guesswork.

CHANNEL_INBOUND_WINDOW_SECONDS = 60.0
CHANNEL_INBOUND_DEFAULT_MAX = 60

_inbound_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def channel_inbound_limit() -> int:
    """Messages per sender per minute. ``RAIKER_CHANNEL_INBOUND_RATE`` overrides.

    A non-numeric or non-positive override falls back to the default rather than
    disabling the limit: "0" is far more likely to be a mistake than a request to
    accept an unbounded stream, and this is the one setting where guessing
    generously is the wrong way to be wrong.
    """
    raw = os.environ.get("RAIKER_CHANNEL_INBOUND_RATE", "").strip()
    try:
        value = int(raw)
    except ValueError:
        return CHANNEL_INBOUND_DEFAULT_MAX
    return value if value > 0 else CHANNEL_INBOUND_DEFAULT_MAX


def _within_inbound_budget(connector_id: str, sender_id: str) -> bool:
    """Record this message against the sender's budget; False when it is spent."""
    limit = channel_inbound_limit()
    now = time.monotonic()
    cutoff = now - CHANNEL_INBOUND_WINDOW_SECONDS
    # Aged out and swept *before* this sender's bucket is fetched. Doing it after
    # is subtly wrong and silently disables the limit: a `defaultdict` creates the
    # bucket empty on access, so a sweep that drops empty buckets drops the one
    # about to be appended to, and every message then looks like the first.
    for key, seen in list(_inbound_hits.items()):
        while seen and seen[0] < cutoff:
            seen.popleft()
        if not seen:
            del _inbound_hits[key]
    hits = _inbound_hits[(connector_id, sender_id)]
    if len(hits) >= limit:
        return False
    hits.append(now)
    return True


# ── Loop guard (DEC-14 step 9) ───────────────────────────────────────────────
#
# Telegram marks another bot's message and it is never routed (UX-MSG-05). The
# generic webhook has no such flag: whatever is on the other end — a person, a
# script, another assistant — reaches Raiker as a sender id and a string, and
# the reply goes back to it. Two automated parties pointed at each other answer
# each other until the rate limit, sixty times a minute, and every answer is a
# model call. So the guard reads lineage rather than a flag:
#
# * an inbound message that *is* one of Raiker's own recent replies on this
#   connector is an echo — the other side fed the answer back in;
# * the same message from the same sender a third time inside the window is a
#   repeat, which is what a stuck automation sends and a person rarely does.
#
# Fingerprints only (a hash of the normalised text), process-local and windowed
# like the budget above. Both refusals are recorded with their reason, so a
# channel that went quiet is answerable from its receipts.

CHANNEL_LOOP_WINDOW_SECONDS = 600.0
CHANNEL_LOOP_REPEAT_LIMIT = 3

_recent_replies: dict[str, deque[tuple[float, str]]] = defaultdict(deque)
_recent_inbound: dict[tuple[str, str], deque[tuple[float, str]]] = defaultdict(deque)


def _fingerprint(text: str) -> str:
    normalised = " ".join(text.split()).casefold()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _prune(seen: deque[tuple[float, str]], cutoff: float) -> None:
    while seen and seen[0][0] < cutoff:
        seen.popleft()


def _loop_reason(connector_id: str, sender_id: str, text: str) -> str | None:
    """``loop_echo``, ``loop_repeated`` or None — and records this message."""
    now = time.monotonic()
    cutoff = now - CHANNEL_LOOP_WINDOW_SECONDS
    mark = _fingerprint(text)
    replies = _recent_replies[connector_id]
    _prune(replies, cutoff)
    if any(seen == mark for _at, seen in replies):
        return "loop_echo"
    inbound = _recent_inbound[(connector_id, sender_id)]
    _prune(inbound, cutoff)
    inbound.append((now, mark))
    if sum(1 for _at, seen in inbound if seen == mark) >= CHANNEL_LOOP_REPEAT_LIMIT:
        return "loop_repeated"
    return None


def _remember_reply(connector_id: str, reply: str) -> None:
    if reply.strip():
        _recent_replies[connector_id].append((time.monotonic(), _fingerprint(reply)))


# ── Owner surface (BUG-225) ──────────────────────────────────────────────────
#
# The transport existed and had no way in. These routes are the way in, and they
# are deliberately thin: every one delegates to the control service, which is
# human-only and owner-scoped, and the test delivery goes through the governed
# `external_channel_runtime` capability rather than posting the webhook itself.


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
        or reason
        in {
            "channel_already_paired",
            "sender_allowlist_required",
            "channel_destination_invalid",
            "channel_destination_not_configurable",
        }
    ):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_403_FORBIDDEN
    raise refusal(code, reason)


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
    answer: ChannelsView = _service(request).list_channels(auth_data[0].principal_id)
    return serialize_dto(answer)


@router.post("/api/channels/pairings")
async def pair_channel(
    body: PairChannelRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Pair a connector. Paired is **not** enabled — that is a second decision."""
    answer = cast(
        ChannelPaired,
        _channel_result(
            _service(request).pair_channel(
                auth_data[0].principal_id,
                body.connector_id,
                body.display_name or "",
                list(body.senders or []),
            )
        ),
    )
    return serialize_dto(answer)


@router.put("/api/channels/pairings/{pairing_id}/enabled")
async def set_channel_enabled(
    pairing_id: str,
    body: ChannelEnabledRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    answer = cast(
        ChannelEnabledSet,
        _channel_result(
            _service(request).set_channel_enabled(auth_data[0].principal_id, pairing_id, body.enabled)
        ),
    )
    return serialize_dto(answer)


@router.put("/api/channels/pairings/{pairing_id}/senders")
async def set_channel_senders(
    pairing_id: str,
    body: ChannelSendersRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Replace the sender allowlist. This is what the inbound receiver enforces."""
    answer = cast(
        ChannelSendersSet,
        _channel_result(
            _service(request).set_channel_senders(
                auth_data[0].principal_id, pairing_id, list(body.senders or [])
            )
        ),
    )
    return serialize_dto(answer)


@router.put("/api/channels/pairings/{pairing_id}/routing")
async def set_channel_routing(
    pairing_id: str,
    body: ChannelRoutingRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    answer = cast(
        ChannelRoutingSet,
        _channel_result(
            _service(request).set_channel_routing(
                auth_data[0].principal_id,
                pairing_id,
                routing_mode=body.routing_mode,
                target_session_id=body.target_session_id,
                owner_sender_id=body.owner_sender_id,
                approval_relay_enabled=body.approval_relay_enabled,
            )
        ),
    )
    return serialize_dto(answer)


@router.put("/api/channels/pairings/{pairing_id}/destination")
async def set_channel_destination(
    pairing_id: str,
    body: ChannelDestinationRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """UX-MSG-04 — bind where a webhook channel delivers. Telegram has no URL."""
    answer = cast(
        ChannelDestinationSet,
        _channel_result(
            _service(request).set_channel_destination(
                auth_data[0].principal_id, pairing_id, body.delivery_url
            )
        ),
    )
    return serialize_dto(answer)


@router.delete("/api/channels/pairings/{pairing_id}")
async def unpair_channel(
    pairing_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    answer = cast(
        ChannelUnpaired,
        _channel_result(
            _service(request).unpair_channel(auth_data[0].principal_id, pairing_id)
        ),
    )
    return serialize_dto(answer)


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
    the egress boundary — exactly as a real delivery would. It names no
    destination: it goes where the channel delivers (UX-MSG-04).
    """
    answer = cast(
        ChannelTestDelivered,
        _channel_result(
            _service(request).deliver_channel_test(
                auth_data[0].principal_id, body.connector_id, body.text
            )
        ),
    )
    return serialize_dto(answer)


def _require_channel_secret(presented: str | None) -> None:
    """The shared inbound secret, checked the same way for every transport.

    Fail closed: no inbound at all until the owner sets one. Telegram presents
    it in its own header (`X-Telegram-Bot-Api-Secret-Token`, which Telegram
    echoes verbatim from the value given at `setWebhook`), so the check lives
    here rather than in either route.
    """
    secret = os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
    if not secret:
        raise refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "channel_inbound_disabled")
    if not presented or not hmac.compare_digest(presented, secret):
        raise refusal(status.HTTP_401_UNAUTHORIZED, "invalid_channel_secret")


@router.post("/api/channels/{connector_id}/inbound")
async def receive_inbound(
    connector_id: str,
    body: InboundChannelMessage,
    request: Request,
    x_raiker_channel_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_channel_secret(x_raiker_channel_secret)
    return serialize_dto(await _handle_inbound(
        connector_id, sender_id=body.sender_id, text=body.text, request=request
    ))


@router.post("/api/channels/{connector_id}/telegram")
async def receive_telegram(
    connector_id: str,
    update: dict[str, Any],
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Telegram's own update shape, translated at the edge.

    Everything after the translation is the path every channel already takes —
    pairing lookup, sender allowlist, per-sender budget, redacted preview,
    audit event, and the stored owner route. Telegram gets no shortcut: a
    sender it does not recognise is refused here exactly as one arriving on the
    generic webhook is, and the text stays structurally untrusted either way.

    A non-message update (an edit is accepted; a poll answer, a reaction, a
    join) is acknowledged and dropped rather than refused — Telegram retries
    anything it does not get a 2xx for, and retrying a `chat_member` update
    forever helps nobody.
    """
    _require_channel_secret(x_telegram_bot_api_secret_token)
    adapter = adapter_for("telegram")
    parsed = adapter.parse_inbound(update) if adapter is not None else None
    if parsed is None:
        answer: ChannelUpdateIgnored = {"ok": True, "ignored": "unsupported_update"}
        return serialize_dto(answer)
    if parsed.from_bot:
        # UX-MSG-05 — another bot is never a party to a route. Acknowledged so
        # Telegram does not retry it, and recorded so a quiet channel is
        # answerable, but never routed: two automated parties answering each
        # other is the loop the messaging contract names.
        EventLogWriter(SQLiteStore(_ws(request))).append(make_event(
            session_id="channels",
            turn_id=None,
            event_type="channel_message_rejected",
            actor="channel_receiver",
            payload={
                "connector_id": connector_id,
                "channel_type": "telegram",
                "trust_level": "untrusted",
                "reason": "bot_sender",
            },
        ))
        ignored: ChannelUpdateIgnored = {"ok": True, "ignored": "bot_sender"}
        return serialize_dto(ignored)
    return serialize_dto(await _handle_inbound(
        connector_id,
        sender_id=parsed.sender_id,
        text=parsed.text,
        request=request,
        conversation_scope=parsed.conversation_scope,
    ))



async def _handle_inbound(
    connector_id: str,
    *,
    sender_id: str,
    text: str,
    request: Request,
    conversation_scope: str = "endpoint",
) -> ChannelInboundAccepted:
    store = SQLiteStore(_ws(request))
    writer = EventLogWriter(store)
    pairing = _enabled_pairing(store, connector_id)
    if pairing is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "channel_not_paired_or_disabled")
    received_at = utc_now()

    try:
        allowlist = set(json.loads(pairing.get("sender_allowlist_json") or "[]"))
    except (json.JSONDecodeError, TypeError):
        allowlist = set()

    channel_message_id = new_id("chn_")
    channel_type = str(pairing.get("channel_type", "webhooks"))
    preview, _ = redact_text(text[:200])
    owner_sender_id = str(pairing.get("owner_sender_id") or "")
    is_owner = bool(owner_sender_id and hmac.compare_digest(sender_id, owner_sender_id))

    def _receipt(stages: dict[str, str], *, role: str, reason: str | None = None) -> None:
        # UX-MSG-06 — the receipt holds the sender's role, never the id.
        store.insert_channel_receipt(
            receipt_id=channel_message_id,
            connector_id=connector_id,
            pairing_id=str(pairing.get("pairing_id") or "") or None,
            direction="inbound",
            kind="message",
            sender_role=role,
            conversation_scope=conversation_scope,
            routing_mode=str(pairing.get("routing_mode") or "record_only"),
            stages={"received_at": received_at, **stages},
            reason_code=reason,
        )

    if sender_id not in allowlist:
        _receipt({"failed_at": utc_now()}, role="not_allowed", reason="sender_not_allowlisted")
        writer.append(make_event(
            session_id="channels",
            turn_id=None,
            event_type="channel_message_rejected",
            actor="channel_receiver",
            payload={
                "connector_id": connector_id,
                "channel_type": channel_type,
                "sender_id": sender_id,
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

    if not _within_inbound_budget(connector_id, sender_id):
        _receipt(
            {"failed_at": utc_now()},
            role="owner" if is_owner else "allowed",
            reason="rate_limited",
        )
        writer.append(make_event(
            session_id="channels",
            turn_id=None,
            event_type="channel_message_rejected",
            actor="channel_receiver",
            payload={
                "connector_id": connector_id,
                "channel_type": channel_type,
                "sender_id": sender_id,
                "trust_level": "untrusted",
                "reason": "rate_limited",
                "limit_per_minute": channel_inbound_limit(),
            },
        ))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "ok": False,
                "reason_code": "rate_limited",
                "trust_level": "untrusted",
                "quarantined": True,
            },
        )

    loop = _loop_reason(connector_id, sender_id, text)
    if loop is not None:
        _receipt(
            {"failed_at": utc_now()},
            role="owner" if is_owner else "allowed",
            reason=loop,
        )
        writer.append(make_event(
            session_id="channels",
            turn_id=None,
            event_type="channel_message_rejected",
            actor="channel_receiver",
            payload={
                "connector_id": connector_id,
                "channel_type": channel_type,
                "sender_id": sender_id,
                "trust_level": "untrusted",
                "reason": loop,
            },
        ))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "ok": False,
                "reason_code": loop,
                "trust_level": "untrusted",
                "quarantined": True,
            },
        )

    # Allowlisted sender, within budget: content stays structurally untrusted.
    # The stored owner route — never a field in this request — decides whether
    # anything else happens.
    _receipt({"accepted_at": utc_now()}, role="owner" if is_owner else "allowed")
    writer.append(make_event(
        session_id="channels",
        turn_id=None,
        event_type="channel_message_received",
        actor="channel_receiver",
        payload={
            "channel_message_id": channel_message_id,
            "connector_id": connector_id,
            "channel_type": channel_type,
            "sender_id": sender_id,
            "trust_level": "owner" if is_owner else "untrusted",
            "quarantined": True,
            "instructions_inert": True,
            "preview": preview,
            "conversation_scope": conversation_scope,
        },
    ))
    routed = await _route_inbound_message(
        request,
        store,
        pairing,
        channel_message_id=channel_message_id,
        sender_id=sender_id,
        text=text,
        is_owner=is_owner,
    )
    _settle_receipt(store, channel_message_id, routed, channel_type=channel_type)
    _remember_reply(connector_id, str(routed.get("reply") or ""))
    answer = cast(ChannelInboundAccepted, {
        "ok": True,
        "channel_message_id": channel_message_id,
        "trust_level": "owner" if is_owner else "untrusted",
        "quarantined": not bool(routed.get("routed")),
        **routed,
    })
    return answer


def _settle_receipt(
    store: SQLiteStore, receipt_id: str, routed: InboundRoute, *, channel_type: str
) -> None:
    """UX-MSG-06 — what became of an accepted message, stage by stage.

    *Queued* is the route handing it to work; *processed* is that work
    finishing; a failed turn is *failed*, not processed. The reply is its own
    fact: the generic webhook returns it in the response to the caller, which
    is a delivery; Telegram gets nothing back over the channel, so its receipt
    says processed and no more — a finished turn is not a delivered reply.
    """
    now = utc_now()
    if not routed.get("routed"):
        reason = routed.get("reason_code")
        if reason:
            store.advance_channel_receipt(
                receipt_id, stages={"failed_at": now}, reason_code=str(reason)
            )
        return
    stages: dict[str, str] = {"queued_at": now}
    status_value = str(routed.get("status") or "")
    if routed.get("action") in {"stop", "steer"}:
        stages["processed_at"] = now
    elif status_value in {"error", "failed", "refused", "stopped", "cancelled", "resume_failed"}:
        stages["failed_at"] = now
    elif any(word in status_value for word in ("approval", "suspend", "waiting")):
        # Paused for the owner: queued, and not yet processed.
        pass
    elif status_value:
        stages["processed_at"] = now
        if routed.get("reply") and channel_type != "telegram":
            stages["reply_queued_at"] = now
            stages["delivered_at"] = now
    store.advance_channel_receipt(
        receipt_id,
        stages=stages,
        session_id=str(routed.get("session_id") or "") or None,
        # FIXED-720 — the turn's own status ("failed", "stopped") is not a
        # reason an owner can act on; its conversation holds the reason, and
        # the receipt links there.
        reason_code=f"turn_{status_value}" if "failed_at" in stages else None,
    )


@router.post("/api/channels/{connector_id}/approval-response")
async def receive_approval_response(
    connector_id: str,
    body: ChannelApprovalResponse,
    request: Request,
    x_raiker_channel_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Resolve one relayed approval through the paired owner identity.

    The exact relay and action ids are mandatory, the relay is single-use, and
    critical approvals and connector writes remain local-only.  This is the
    anti-phishing boundary: a generic "approve" message has no meaning here.
    """
    secret = os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
    if not secret:
        raise refusal(503, "channel_inbound_disabled")
    if not x_raiker_channel_secret or not hmac.compare_digest(x_raiker_channel_secret, secret):
        raise refusal(401, "invalid_channel_secret")
    store = SQLiteStore(_ws(request))
    pairing = _enabled_pairing(store, connector_id)
    if pairing is None or not bool(pairing.get("approval_relay_enabled")):
        raise refusal(403, "channel_approval_relay_not_enabled")
    owner_sender = str(pairing.get("owner_sender_id") or "")
    if not owner_sender or not hmac.compare_digest(body.sender_id, owner_sender):
        raise refusal(403, "channel_owner_sender_required")
    if not _within_inbound_budget(connector_id, body.sender_id):
        raise refusal(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    relay = store.get_approval_relay(body.relay_id)
    if (
        relay is None
        or str(relay.get("pairing_id")) != str(pairing.get("pairing_id"))
        or str(relay.get("action_id")) != body.action_id
        or str(relay.get("status")) != "pending"
    ):
        raise refusal(409, "channel_approval_relay_mismatch")

    from raiker.approvals import ApprovalInbox
    from raiker.approvals.execution import ApprovalExecutionBridge, executable_capability
    from raiker.cli.principal_resolver import resolve_local_principal
    from raiker.runtime.turn_suspension import approval_outcome

    principal_id = str(pairing.get("paired_by") or "")
    principal, _ = resolve_local_principal(_ws(request), principal_id)
    if principal is None:
        raise refusal(403, "principal_not_resolved")
    user_id = store.principal_user_id(principal_id)
    # A relay is bound to the immutable tool-action id, while resolution APIs
    # load the richer joined row by approval id. Resolve the indirection first;
    # never accept an approval id in the action-id field.
    with store.connect() as connection:
        approval_ref = connection.execute(
            "SELECT approval_id FROM approvals WHERE action_id = ?", (body.action_id,)
        ).fetchone()
    approval = (
        store.load_approval(str(approval_ref["approval_id"]), user_id=user_id)
        if approval_ref is not None
        else None
    )
    if approval is None or str(approval.get("action_id")) != body.action_id:
        raise refusal(404, "approval_not_found")
    approval_id = str(approval.get("approval_id") or "")
    if bool(approval.get("critical")):
        raise refusal(403, "critical_approval_requires_local_step_up")
    with store.connect() as connection:
        connector_intent = connection.execute(
            "SELECT 1 FROM connector_write_intents WHERE approval_id = ?", (approval_id,)
        ).fetchone()
    if connector_intent is not None:
        raise refusal(403, "connector_write_requires_local_approval")

    writer = EventLogWriter(store)
    relay_status = "approved" if body.approve else "denied"
    # Claim the single-use relay before resolving or executing the action. Two
    # concurrent responses can both read "pending", but only one can win this
    # compare-and-set and cross the execution boundary.
    if not store.resolve_approval_relay(
        body.relay_id, status=relay_status, resolved_by=principal_id
    ):
        raise refusal(409, "channel_approval_relay_already_resolved")
    capability = executable_capability(str(approval.get("tool_name") or "")) or str(
        approval.get("tool_name") or ""
    )
    executed = False
    artifacts: dict[str, Any] = {}
    if body.approve:
        bridge = ApprovalExecutionBridge(store, writer)
        if bridge.executes_on_resolution(
            str(approval.get("tool_name") or ""), principal_id, critical=False
        ):
            # GCR-05 — off the loop, for the same reason the inbox route is:
            # resolving an approval here executes the action it approved.
            execution = await asyncio.to_thread(
                lambda: bridge.execute(
                    approval,
                    principal,
                    session_id="channel_approval",
                    reason=(body.reason or "approved over paired owner channel")[:500],
                )
            )
            if not execution.ok:
                raise refusal(409, execution.reason_code)
            executed = True
            capability = execution.capability
            artifacts = dict(execution.artifacts)
            from raiker.api.routes_prompts import _record_generated_file_attachments_for_turn

            _record_generated_file_attachments_for_turn(
                _ws(request),
                session_id=str(approval.get("session_id") or ""),
                turn_id=str(approval.get("turn_id") or ""),
                principal_id=principal_id,
            )
        else:
            ApprovalInbox(store, writer).resolve(
                approval_id,
                approve=True,
                resolved_by=principal_id,
                reason=(body.reason or "approved over paired owner channel")[:500],
                user_id=user_id,
            )
    else:
        ApprovalInbox(store, writer).resolve(
            approval_id,
            approve=False,
            resolved_by=principal_id,
            reason=(body.reason or "denied over paired owner channel")[:500],
            user_id=user_id,
        )
    suspended = store.load_suspended_turn(approval_id, principal_id=principal_id)
    if suspended is not None and str(suspended.get("status")) == "suspended":
        store.record_suspended_turn_outcome(
            approval_id,
            json.dumps(
                approval_outcome(
                    approved=body.approve,
                    executed=executed,
                    capability=capability,
                    artifacts=artifacts,
                ),
                sort_keys=True,
            ),
        )
    writer.append(make_event(
        session_id=str(approval.get("session_id") or "channels"),
        turn_id=approval.get("turn_id"),
        event_type="approval_relay_approved" if body.approve else "approval_relay_denied",
        actor="channel_approval_relay",
        payload={"relay_id": body.relay_id, "approval_id": approval_id, "executed": executed},
    ))
    answer: ApprovalRelayAnswered = {
        "ok": True,
        "relay_id": body.relay_id,
        "approval_id": approval_id,
        "status": "executed" if executed else relay_status,
        "resumable": suspended is not None,
    }
    return serialize_dto(answer)


async def _route_inbound_message(
    request: Request,
    store: SQLiteStore,
    pairing: dict[str, Any],
    *,
    channel_message_id: str,
    sender_id: str,
    text: str,
    is_owner: bool,
) -> InboundRoute:
    """Apply only the route stored on the pairing; message fields grant nothing."""
    mode = str(pairing.get("routing_mode") or "record_only")
    if mode == "record_only":
        answer_0: InboundRoute = {"routed": False, "routing_mode": mode}
        return answer_0
    principal_id = str(pairing.get("paired_by") or "")
    target = str(pairing.get("target_session_id") or "") or None
    if mode in {"new_turn", "interrupt"} and not is_owner:
        answer_1: InboundRoute = {
            "routed": False,
            "routing_mode": mode,
            "reason_code": "channel_owner_sender_required",
        }
        return answer_1
    if mode == "interrupt":
        if target is None:
            answer_2: InboundRoute = {"routed": False, "routing_mode": mode, "reason_code": "channel_target_session_required"}
            return answer_2
        action: Literal["stop", "steer"]
        if text.strip().lower() in {"stop", "cancel", "pause"}:
            store.request_turn_stop(target, principal_id, reason="owner requested stop over paired channel")
            action = "stop"
        else:
            store.queue_turn_steer(target, principal_id, text=text[:4000])
            action = "steer"
        EventLogWriter(store).append(make_event(
            session_id=target,
            turn_id=None,
            event_type="channel_message_routed",
            actor="channel_router",
            payload={"channel_message_id": channel_message_id, "routing_mode": mode, "action": action},
        ))
        answer_3: InboundRoute = {"routed": True, "routing_mode": mode, "action": action, "session_id": target}
        return answer_3

    if mode not in {"new_turn", "side_question"}:
        answer_4: InboundRoute = {"routed": False, "routing_mode": mode, "reason_code": "channel_routing_mode_unsupported"}
        return answer_4
    if mode == "side_question" and target is None:
        answer_5: InboundRoute = {"routed": False, "routing_mode": mode, "reason_code": "channel_target_session_required"}
        return answer_5

    from raiker.gateway.agent_gateway import AgentGateway

    session_id = target or new_id("sess_")
    channel_type = str(pairing.get("channel_type") or "webhooks")
    envelope = PromptEnvelope(
        request_id=new_id("req_"),
        session_id=session_id,
        turn_id=new_id("turn_"),
        client=ClientMetadata(type=channel_type, name=f"raiker-{channel_type}", version="1.0"),
        # RR-IDENTITY-01 — resolved from the *paired owner's* principal, never
        # from anything the channel message carries: a name a sender can set is
        # a name a sender can borrow.
        user=owner_user_metadata(store, principal_id),
        prompt=PromptPayload(
            text=text[:16000] or "(empty channel message)",
            metadata={
                "entry_command": channel_type,
                "surface": "chat",
                "input_mode": "typed",
                "channel_message": {
                    "id": channel_message_id,
                    "connector_id": str(pairing.get("connector_id") or ""),
                    "sender_id": sender_id,
                    "trust_level": "owner" if is_owner else "untrusted",
                    "routing_mode": mode,
                },
            },
        ),
        # A side question observes; it cannot turn an allowlisted external
        # sender into the owner of the active task.  Owner new turns use the
        # owner's ordinary standing controls and still pass every gate.
        options=PromptOptions(max_tool_calls=0 if mode == "side_question" else 12),
    )
    response = await AgentGateway(_ws(request), principal_id=principal_id).submit_prompt_async(envelope)
    EventLogWriter(store).append(make_event(
        session_id=session_id,
        turn_id=envelope.turn_id,
        event_type="channel_message_routed",
        actor="channel_router",
        payload={
            "channel_message_id": channel_message_id,
            "routing_mode": mode,
            "status": response.status,
            "tool_budget": envelope.options.max_tool_calls,
        },
    ))
    answer_6: InboundRoute = {
        "routed": True,
        "routing_mode": mode,
        "session_id": session_id,
        "turn_id": envelope.turn_id,
        "status": response.status,
        "reply": response.message,
    }
    return answer_6
