from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from collections import defaultdict, deque
from contextlib import suppress
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import (
    ChannelApprovalResponse,
    ChannelDestinationRequest,
    ChannelEnabledRequest,
    ChannelPausedRequest,
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
    ChannelDeliveryReviewed,
    ChannelDestinationSet,
    ChannelEnabledSet,
    ChannelInboundAccepted,
    ChannelPaired,
    ChannelPausedSet,
    ChannelRoutingSet,
    ChannelSendersSet,
    ChannelTestDelivered,
    ChannelUnpaired,
    ChannelUpdateIgnored,
    InboundRoute,
)
from raiker.channels.adapters import adapter_for
from raiker.channels.revision import CHANNEL_CONFLICT
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


# DEC-14 step 8 — per sender was the only budget, so a channel with many
# allowlisted senders (a group) or many channels at once had no bound at all.
# Two more windows sit behind it: one per channel and one for the host. Each is
# a multiple of the per-sender budget unless set, so raising the sender budget
# for one busy person does not leave the channel's bound below it.
CHANNEL_INBOUND_CHANNEL_FACTOR = 4
CHANNEL_INBOUND_GLOBAL_FACTOR = 10

_channel_hits: dict[str, deque[float]] = defaultdict(deque)
_global_hits: deque[float] = deque()


def _positive_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def channel_inbound_channel_limit() -> int:
    """Messages per channel per minute, every sender together."""
    return _positive_env(
        "RAIKER_CHANNEL_INBOUND_CHANNEL_RATE",
        channel_inbound_limit() * CHANNEL_INBOUND_CHANNEL_FACTOR,
    )


def channel_inbound_global_limit() -> int:
    """Messages per minute across every channel on this host."""
    return _positive_env(
        "RAIKER_CHANNEL_INBOUND_GLOBAL_RATE",
        channel_inbound_limit() * CHANNEL_INBOUND_GLOBAL_FACTOR,
    )


def _inbound_budget_refusal(connector_id: str, sender_id: str) -> str | None:
    """Spend one message from every budget it falls under, or name the one that is spent.

    Checked smallest scope first, and nothing is recorded unless all three have
    room: a message refused by the channel's budget must not also use up the
    sender's, or a flood from others would lock a quiet sender out after it.
    """
    now = time.monotonic()
    cutoff = now - CHANNEL_INBOUND_WINDOW_SECONDS
    if not _within_inbound_budget(connector_id, sender_id, record=False):
        return "rate_limited"
    channel = _channel_hits[connector_id]
    while channel and channel[0] < cutoff:
        channel.popleft()
    if len(channel) >= channel_inbound_channel_limit():
        return "channel_rate_limited"
    while _global_hits and _global_hits[0] < cutoff:
        _global_hits.popleft()
    if len(_global_hits) >= channel_inbound_global_limit():
        return "inbound_rate_limited"
    _within_inbound_budget(connector_id, sender_id)
    channel.append(now)
    _global_hits.append(now)
    return None


def _within_inbound_budget(connector_id: str, sender_id: str, *, record: bool = True) -> bool:
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
    if record:
        hits.append(now)
    return True


#: DEC-14 step 4 — the shape a webhook caller's ``Idempotency-Key`` must have,
#: the same as every other route that takes one.
_EVENT_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


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
    if reason in {CHANNEL_CONFLICT, "channel_test_required"}:
        # §13.2 item 6 — another tab changed this pairing since the page read
        # it. Nothing was written; the page re-reads and the owner decides again.
        # DEC-14 step 3 — the channel's state stands in the way until a test
        # to its destination is delivered.
        raise refusal(status.HTTP_409_CONFLICT, reason)
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
            _service(request).set_channel_enabled(
                auth_data[0].principal_id, pairing_id, body.enabled, body.expected_revision
            )
        ),
    )
    return serialize_dto(answer)


@router.put("/api/channels/pairings/{pairing_id}/paused")
async def set_channel_paused(
    pairing_id: str,
    body: ChannelPausedRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """DEC-14 step 10 — hold a channel: messages are kept, no work starts, nothing is sent."""
    answer = cast(
        ChannelPausedSet,
        _channel_result(
            _service(request).set_channel_paused(
                auth_data[0].principal_id, pairing_id, body.paused, body.expected_revision
            )
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
                auth_data[0].principal_id,
                pairing_id,
                list(body.senders or []),
                body.expected_revision,
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
                expected_revision=body.expected_revision,
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
                auth_data[0].principal_id, pairing_id, body.delivery_url, body.expected_revision
            )
        ),
    )
    return serialize_dto(answer)


@router.delete("/api/channels/pairings/{pairing_id}")
async def unpair_channel(
    pairing_id: str,
    request: Request,
    expected_revision: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    answer = cast(
        ChannelUnpaired,
        _channel_result(
            _service(request).unpair_channel(
                auth_data[0].principal_id, pairing_id, expected_revision
            )
        ),
    )
    return serialize_dto(answer)


@router.post("/api/channels/deliveries/{receipt_id}/reviewed")
async def mark_channel_delivery_reviewed(
    receipt_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """DEC-14 step 7 — take a failed or unknown delivery off the review list.

    Nothing is sent: a delivery that may already have arrived is the owner's to
    follow up, not Raiker's to repeat.
    """
    result = _service(request).mark_channel_delivery_reviewed(
        auth_data[0].principal_id, receipt_id
    )
    if not result.ok:
        raise refusal(status.HTTP_404_NOT_FOUND, result.reason_code)
    answer = cast(ChannelDeliveryReviewed, {"ok": True, **result.data})
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


#: DEC-14 step 5 — how far a signed message's timestamp may be from this
#: host's clock, either way, before it is refused as a replay or a forgery.
INBOUND_SIGNATURE_WINDOW_SECONDS = 300
_SIGNATURE = re.compile(r"^sha256=[0-9a-f]{64}$")


def inbound_signature_required() -> bool:
    """The owner asked for every webhook message to be signed."""
    return os.environ.get("RAIKER_CHANNEL_INBOUND_REQUIRE_SIGNATURE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _verify_inbound_signature(timestamp: str | None, signature: str, raw: bytes) -> str:
    """DEC-14 step 5 — verify a signed webhook message; return its replay key.

    ``X-Raiker-Signature: sha256=<hex>`` is HMAC-SHA256 over
    ``<X-Raiker-Timestamp>.<raw body>`` keyed by the inbound secret, which a
    signed sender never has to put on the wire. The timestamp must be within
    five minutes of this host's clock, and the signature is then claimed once
    like a provider event id, so the same signed message sent again is a
    repeat, never a second message.
    """
    secret = os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
    if not secret:
        raise refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "channel_inbound_disabled")
    if not _SIGNATURE.fullmatch(signature) or not (timestamp or "").isdigit():
        raise refusal(status.HTTP_401_UNAUTHORIZED, "channel_signature_invalid")
    expected = hmac.new(
        secret.encode("utf-8"), f"{timestamp}.".encode() + raw, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, f"sha256={expected}"):
        raise refusal(status.HTTP_401_UNAUTHORIZED, "channel_signature_invalid")
    if abs(time.time() - int(timestamp or "0")) > INBOUND_SIGNATURE_WINDOW_SECONDS:
        raise refusal(status.HTTP_401_UNAUTHORIZED, "channel_signature_expired")
    return f"sig:{expected[:48]}"


async def _signed_bytes(request: Request) -> bytes:
    """The exact bytes a signature covers — the body as it arrived, already
    read and bounded by the ingress limit before the JSON was parsed."""
    return await request.body()


@router.post("/api/channels/{connector_id}/inbound")
async def receive_inbound(
    connector_id: str,
    body: InboundChannelMessage,
    request: Request,
    x_raiker_channel_secret: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    x_raiker_timestamp: str | None = Header(default=None),
    x_raiker_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    """One message on the reference webhook.

    DEC-14 step 4 — a caller that may re-send sends ``Idempotency-Key``; a
    repeat of a message already accepted under it is answered with the first
    message's receipt and runs nothing.

    DEC-14 step 5 — a caller may sign instead of presenting the secret:
    ``X-Raiker-Timestamp`` and ``X-Raiker-Signature``, verified before routing,
    within five minutes, once. With
    ``RAIKER_CHANNEL_INBOUND_REQUIRE_SIGNATURE`` set, an unsigned message is
    refused.
    """
    event_key: str | None = None
    if x_raiker_signature is not None:
        event_key = _verify_inbound_signature(
            x_raiker_timestamp, x_raiker_signature, await _signed_bytes(request)
        )
    elif inbound_signature_required():
        if not os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip():
            raise refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "channel_inbound_disabled")
        raise refusal(status.HTTP_401_UNAUTHORIZED, "channel_signature_required")
    else:
        _require_channel_secret(x_raiker_channel_secret)
    if idempotency_key is not None:
        if not _EVENT_KEY.fullmatch(idempotency_key):
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "idempotency_key_invalid")
        event_key = f"key:{idempotency_key}"
    return serialize_dto(await _handle_inbound(
        connector_id,
        sender_id=body.sender_id,
        text=body.text,
        request=request,
        event_key=event_key,
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
        event_key=parsed.event_id,
        sender_label=parsed.sender_label,
    ))



async def _handle_inbound(
    connector_id: str,
    *,
    sender_id: str,
    text: str,
    request: Request,
    conversation_scope: str = "endpoint",
    event_key: str | None = None,
    sender_label: str | None = None,
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

    if sender_label:
        # DEC-14 step 3 — an allowed sender's own name for themselves, so
        # Messaging can show it beside the id. Never used to decide anything.
        with suppress(Exception):
            store.record_channel_sender_label(
                str(pairing.get("pairing_id") or ""), sender_id, sender_label
            )

    # DEC-14 step 4 — claimed once the sender is known to be allowed and
    # before anything spends a budget, so a provider re-sending an update it
    # got no answer for is neither a second turn nor a second hit on the rate
    # limit or the loop guard. A refusal below gives the claim back: a message
    # that was refused was not accepted, and the provider's retry is a fresh try.
    if event_key is not None:
        first = store.claim_channel_inbound_event(connector_id, event_key, channel_message_id)
        if first is not None:
            return _duplicate_answer(
                store, writer, pairing, first,
                connector_id=connector_id,
                channel_type=channel_type,
                is_owner=is_owner,
            )

    def _release_event() -> None:
        if event_key is not None:
            store.release_channel_inbound_event(connector_id, event_key, channel_message_id)

    spent = _inbound_budget_refusal(connector_id, sender_id)
    if spent is not None:
        _release_event()
        _receipt(
            {"failed_at": utc_now()},
            role="owner" if is_owner else "allowed",
            reason=spent,
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
                "reason": spent,
                "limit_per_minute": {
                    "rate_limited": channel_inbound_limit,
                    "channel_rate_limited": channel_inbound_channel_limit,
                    "inbound_rate_limited": channel_inbound_global_limit,
                }[spent](),
            },
        ))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "ok": False,
                "reason_code": spent,
                "trust_level": "untrusted",
                "quarantined": True,
            },
        )

    loop = _loop_reason(connector_id, sender_id, text)
    if loop is not None:
        _release_event()
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

    if bool(pairing.get("paused")):
        # DEC-14 step 10 — the owner has contained this channel. The message is
        # kept as evidence (its receipt and a redacted preview), but no route
        # runs: no turn starts, no interrupt lands, nothing is replied. It is
        # answered as accepted, so a sender's retry logic does not resend what
        # was already recorded.
        _receipt(
            {"accepted_at": utc_now()},
            role="owner" if is_owner else "allowed",
            reason="channel_paused",
        )
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
                "held": "channel_paused",
            },
        ))
        held = cast(ChannelInboundAccepted, {
            "ok": True,
            "channel_message_id": channel_message_id,
            "trust_level": "owner" if is_owner else "untrusted",
            "quarantined": True,
            "routed": False,
            "routing_mode": str(pairing.get("routing_mode") or "record_only"),
            "reason_code": "channel_paused",
        })
        return held

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


def _duplicate_answer(
    store: SQLiteStore,
    writer: EventLogWriter,
    pairing: dict[str, Any],
    first_receipt_id: str,
    *,
    connector_id: str,
    channel_type: str,
    is_owner: bool,
) -> ChannelInboundAccepted:
    """A repeat of an accepted event: the first receipt, and nothing run.

    Answered 200 so the provider stops re-sending. The audit log says a repeat
    arrived and which message it repeated; the receipt ledger is not given a
    second row for a message that happened once.
    """
    first = store.load_channel_receipt(first_receipt_id) or {}
    writer.append(make_event(
        session_id="channels",
        turn_id=None,
        event_type="channel_message_rejected",
        actor="channel_receiver",
        payload={
            "connector_id": connector_id,
            "channel_type": channel_type,
            "trust_level": "owner" if is_owner else "untrusted",
            "reason": "duplicate_event",
            "channel_message_id": first_receipt_id,
        },
    ))
    answer = cast(ChannelInboundAccepted, {
        "ok": True,
        "channel_message_id": first_receipt_id,
        "trust_level": "owner" if is_owner else "untrusted",
        "quarantined": True,
        "routed": False,
        "routing_mode": str(pairing.get("routing_mode") or "record_only"),
        "reason_code": "duplicate_event",
    })
    session_id = first.get("session_id")
    if session_id:
        answer["session_id"] = str(session_id)
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
    if bool(pairing.get("paused")):
        # DEC-14 step 10 — a paused channel decides nothing on the owner's behalf.
        raise refusal(409, "channel_paused")
    owner_sender = str(pairing.get("owner_sender_id") or "")
    if not owner_sender or not hmac.compare_digest(body.sender_id, owner_sender):
        raise refusal(403, "channel_owner_sender_required")
    spent = _inbound_budget_refusal(connector_id, body.sender_id)
    if spent is not None:
        raise refusal(status.HTTP_429_TOO_MANY_REQUESTS, spent)
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
            from raiker.storage.stores.conversations import SteerQueueFull

            try:
                store.queue_turn_steer(target, principal_id, text=text[:4000])
            except SteerQueueFull:
                answer_full: InboundRoute = {
                    "routed": False,
                    "routing_mode": mode,
                    "reason_code": "steer_queue_full",
                }
                return answer_full
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
