from __future__ import annotations

import hmac
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    ChannelApprovalResponse,
    ChannelEnabledRequest,
    ChannelRoutingRequest,
    ChannelSendersRequest,
    ChannelTestDeliveryRequest,
    InboundChannelMessage,
    PairChannelRequest,
)
from raiker.api.sessions import ApiSession
from raiker.channels.adapters import adapter_for
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# Inbound channel receiver (Phase 4 slice 4 / Phase 8 gate). Inbound traffic is
# authenticated by an owner-set channel secret (NOT the owner bearer token).
# Content remains structurally untrusted; only an owner-stored route may place
# it in a governed turn, and doing so never increases that turn's authority.


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


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


@router.put("/api/channels/pairings/{pairing_id}/routing")
async def set_channel_routing(
    pairing_id: str,
    body: ChannelRoutingRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _channel_result(
        _service(request).set_channel_routing(
            auth_data[0].principal_id,
            pairing_id,
            routing_mode=body.routing_mode,
            target_session_id=body.target_session_id,
            owner_sender_id=body.owner_sender_id,
            approval_relay_enabled=body.approval_relay_enabled,
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


def _require_channel_secret(presented: str | None) -> None:
    """The shared inbound secret, checked the same way for every transport.

    Fail closed: no inbound at all until the owner sets one. Telegram presents
    it in its own header (`X-Telegram-Bot-Api-Secret-Token`, which Telegram
    echoes verbatim from the value given at `setWebhook`), so the check lives
    here rather than in either route.
    """
    secret = os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ok": False, "reason_code": "channel_inbound_disabled"},
        )
    if not presented or not hmac.compare_digest(presented, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "reason_code": "invalid_channel_secret"},
        )


@router.post("/api/channels/{connector_id}/inbound")
async def receive_inbound(
    connector_id: str,
    body: InboundChannelMessage,
    request: Request,
    x_raiker_channel_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_channel_secret(x_raiker_channel_secret)
    return await _handle_inbound(
        connector_id, sender_id=body.sender_id, text=body.text, request=request
    )


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
        return {"ok": True, "ignored": "unsupported_update"}
    return await _handle_inbound(
        connector_id, sender_id=parsed.sender_id, text=parsed.text, request=request
    )



async def _handle_inbound(
    connector_id: str,
    *,
    sender_id: str,
    text: str,
    request: Request,
) -> dict[str, Any]:
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
    preview, _ = redact_text(text[:200])

    if sender_id not in allowlist:
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

    # Allowlisted sender, within budget: content stays structurally untrusted.
    # The stored owner route — never a field in this request — decides whether
    # anything else happens.
    owner_sender_id = str(pairing.get("owner_sender_id") or "")
    is_owner = bool(owner_sender_id and hmac.compare_digest(sender_id, owner_sender_id))
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
    return {
        "ok": True,
        "channel_message_id": channel_message_id,
        "trust_level": "owner" if is_owner else "untrusted",
        "quarantined": not bool(routed.get("routed")),
        **routed,
    }


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
        raise HTTPException(status_code=503, detail={"ok": False, "reason_code": "channel_inbound_disabled"})
    if not x_raiker_channel_secret or not hmac.compare_digest(x_raiker_channel_secret, secret):
        raise HTTPException(status_code=401, detail={"ok": False, "reason_code": "invalid_channel_secret"})
    store = SQLiteStore(_ws(request))
    pairing = _enabled_pairing(store, connector_id)
    if pairing is None or not bool(pairing.get("approval_relay_enabled")):
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": "channel_approval_relay_not_enabled"})
    owner_sender = str(pairing.get("owner_sender_id") or "")
    if not owner_sender or not hmac.compare_digest(body.sender_id, owner_sender):
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": "channel_owner_sender_required"})
    if not _within_inbound_budget(connector_id, body.sender_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"ok": False, "reason_code": "rate_limited"},
        )
    relay = store.get_approval_relay(body.relay_id)
    if (
        relay is None
        or str(relay.get("pairing_id")) != str(pairing.get("pairing_id"))
        or str(relay.get("action_id")) != body.action_id
        or str(relay.get("status")) != "pending"
    ):
        raise HTTPException(status_code=409, detail={"ok": False, "reason_code": "channel_approval_relay_mismatch"})

    from raiker.approvals import ApprovalInbox
    from raiker.approvals.execution import ApprovalExecutionBridge, executable_capability
    from raiker.cli.principal_resolver import resolve_local_principal
    from raiker.runtime.turn_suspension import approval_outcome

    principal_id = str(pairing.get("paired_by") or "")
    principal, _ = resolve_local_principal(_ws(request), principal_id)
    if principal is None:
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": "principal_not_resolved"})
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
        raise HTTPException(status_code=404, detail={"ok": False, "reason_code": "approval_not_found"})
    approval_id = str(approval.get("approval_id") or "")
    if bool(approval.get("critical")):
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": "critical_approval_requires_local_step_up"})
    with store.connect() as connection:
        connector_intent = connection.execute(
            "SELECT 1 FROM connector_write_intents WHERE approval_id = ?", (approval_id,)
        ).fetchone()
    if connector_intent is not None:
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": "connector_write_requires_local_approval"})

    writer = EventLogWriter(store)
    relay_status = "approved" if body.approve else "denied"
    # Claim the single-use relay before resolving or executing the action. Two
    # concurrent responses can both read "pending", but only one can win this
    # compare-and-set and cross the execution boundary.
    if not store.resolve_approval_relay(
        body.relay_id, status=relay_status, resolved_by=principal_id
    ):
        raise HTTPException(status_code=409, detail={"ok": False, "reason_code": "channel_approval_relay_already_resolved"})
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
            execution = bridge.execute(
                approval,
                principal,
                session_id="channel_approval",
                reason=(body.reason or "approved over paired owner channel")[:500],
            )
            if not execution.ok:
                raise HTTPException(status_code=409, detail={"ok": False, "reason_code": execution.reason_code})
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
    return {
        "ok": True,
        "relay_id": body.relay_id,
        "approval_id": approval_id,
        "status": "executed" if executed else relay_status,
        "resumable": suspended is not None,
    }


async def _route_inbound_message(
    request: Request,
    store: SQLiteStore,
    pairing: dict[str, Any],
    *,
    channel_message_id: str,
    sender_id: str,
    text: str,
    is_owner: bool,
) -> dict[str, Any]:
    """Apply only the route stored on the pairing; message fields grant nothing."""
    mode = str(pairing.get("routing_mode") or "record_only")
    if mode == "record_only":
        return {"routed": False, "routing_mode": mode}
    principal_id = str(pairing.get("paired_by") or "")
    target = str(pairing.get("target_session_id") or "") or None
    if mode in {"new_turn", "interrupt"} and not is_owner:
        return {
            "routed": False,
            "routing_mode": mode,
            "reason_code": "channel_owner_sender_required",
        }
    if mode == "interrupt":
        if target is None:
            return {"routed": False, "routing_mode": mode, "reason_code": "channel_target_session_required"}
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
        return {"routed": True, "routing_mode": mode, "action": action, "session_id": target}

    if mode not in {"new_turn", "side_question"}:
        return {"routed": False, "routing_mode": mode, "reason_code": "channel_routing_mode_unsupported"}
    if mode == "side_question" and target is None:
        return {"routed": False, "routing_mode": mode, "reason_code": "channel_target_session_required"}

    from raiker.gateway.agent_gateway import AgentGateway

    session_id = target or new_id("sess_")
    channel_type = str(pairing.get("channel_type") or "webhooks")
    envelope = PromptEnvelope(
        request_id=new_id("req_"),
        session_id=session_id,
        turn_id=new_id("turn_"),
        client=ClientMetadata(type=channel_type, name=f"raiker-{channel_type}", version="1.0"),
        user=UserMetadata(id=principal_id),
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
    return {
        "routed": True,
        "routing_mode": mode,
        "session_id": session_id,
        "turn_id": envelope.turn_id,
        "status": response.status,
        "reply": response.message,
    }
