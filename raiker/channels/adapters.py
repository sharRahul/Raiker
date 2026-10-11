"""One adapter per channel type, resolved from a table.

The reference webhook and Telegram were an ``if channel_type == "telegram"``
inside :class:`ExternalChannelExecutor`. That works for two and stops working at
three, which is the point at which every messaging product has had to answer the
same question.

The answer is a table keyed by channel type: each entry owns its own wire format,
and the executor owns everything that is not wire format. What an adapter
deliberately does *not* grow is the surface of a chat client — streaming message
edits, typing indicators, media caches, inline keyboards. A Raiker channel is a
governed relay whose default routing is ``record_only`` and whose content is
untrusted by definition; every one of those features would need its own
governance answer before it could ship, and none of them is what a relay is for.

So an adapter here answers exactly two questions, and nothing else:

* **outbound** — what URL and body does one message become for this platform?
* **inbound** — what did this platform's webhook payload actually say?

Everything that decides whether a message is *allowed* — the capability gate,
the egress allowlist, the pairing, the sender allowlist, the per-sender budget,
the redaction, the audit event, the owner's stored routing choice — lives
outside and applies identically to every adapter. An adapter cannot widen any of
it, which is why adding one is a small, reviewable thing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from typing_extensions import TypedDict


@dataclass(frozen=True)
class OutboundRequest:
    """One delivery, ready for the transport."""

    url: str
    body: bytes
    headers: dict[str, str]
    #: Whether Raiker signs the body itself. False when the provider
    #: authenticates the request some other way (Telegram: a token in the URL),
    #: so an unsigned delivery there is correct rather than a missing control.
    signed: bool = False


@dataclass(frozen=True)
class AdapterRefusal:
    """The adapter cannot build a delivery, and says why in audit vocabulary."""

    reason_code: str
    summary: str


@dataclass(frozen=True)
class InboundMessage:
    """What a webhook payload turned out to be saying."""

    sender_id: str
    text: str
    #: UX-MSG-05 — where the message was said: ``direct`` for a one-to-one
    #: chat, ``group`` for a group or channel, ``endpoint`` for a transport
    #: that has no notion of either (the reference webhook).
    conversation_scope: str = "endpoint"
    #: Authored by another bot. Never routed: two automated parties answering
    #: each other is the loop the messaging contract names.
    from_bot: bool = False
    #: DEC-14 step 4 — the provider's own id for this delivery, when it has
    #: one. A re-send of the same update carries the same id, which is how the
    #: receiver tells a retry from a second message.
    event_id: str | None = None
    #: DEC-14 step 3 — what the sender calls themselves on the channel, when
    #: the transport says. Set by the sender, so it is a label to show beside
    #: the id, never something to authorise by.
    sender_label: str | None = None


class ChannelCapabilities(TypedDict):
    """DEC-14 step 1 — what one channel type can carry, declared by its adapter.

    Declared rather than discovered so the Messaging page can say what a channel
    will and will not do before it is set up, and so the executor can refuse a
    reply the platform would reject instead of finding out from a failed send.
    Every rich feature is ``False`` on purpose: a Raiker channel is a governed
    text relay, and each of those would need its own governance answer before it
    could ship (see the module docstring).
    """

    #: Where a message can come from: one-to-one chats, group chats, and threads
    #: inside either.
    direct_messages: bool
    group_chats: bool
    threads: bool
    #: Rich features this build does not carry on this channel.
    streaming: bool
    media: bool
    reactions: bool
    edits_and_deletes: bool
    buttons: bool
    typing_indicator: bool
    #: The longest reply, in characters, this channel accepts. A longer one is
    #: refused with this number rather than cut short or sent to fail.
    max_text_chars: int
    #: How the channel authenticates, in words.
    authentication: str


class ChannelAdapter(Protocol):
    channel_type: str
    capabilities: ChannelCapabilities

    def outbound(
        self, *, connector_id: str, pairing: dict[str, Any], arguments: dict[str, Any],
        text: str, delivered_at: str, delivery_id: str,
    ) -> OutboundRequest | AdapterRefusal: ...

    def provider_message_id(self, response_body: bytes) -> str | None:
        """DEC-14 step 7 — the platform's own id for a delivered message, or ``None``.

        Read from the response and kept on the receipt; nothing else of the
        response is kept.
        """
        ...

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage | None:
        """``None`` for a payload that is not a message and never will be."""
        ...


# ── Telegram ──────────────────────────────────────────────────────────────────

TELEGRAM_HOST = "api.telegram.org"


#: Telegram's own limit on one ``sendMessage`` text.
TELEGRAM_MAX_TEXT_CHARS = 4096


class TelegramAdapter:
    channel_type = "telegram"
    capabilities: ChannelCapabilities = {
        "direct_messages": True,
        "group_chats": True,
        "threads": False,
        "streaming": False,
        "media": False,
        "reactions": False,
        "edits_and_deletes": False,
        "buttons": False,
        "typing_indicator": False,
        "max_text_chars": TELEGRAM_MAX_TEXT_CHARS,
        "authentication": "A bot token held in this host's environment",
    }

    def outbound(
        self, *, connector_id: str, pairing: dict[str, Any], arguments: dict[str, Any],
        text: str, delivered_at: str, delivery_id: str,
    ) -> OutboundRequest | AdapterRefusal:
        token = os.environ.get("RAIKER_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            return AdapterRefusal(
                "telegram_bot_token_missing",
                "Telegram delivery refused: RAIKER_TELEGRAM_BOT_TOKEN is unset in the "
                "host environment.",
            )
        chat_id = str(
            arguments.get("chat_id") or pairing.get("owner_sender_id") or ""
        ).strip()
        if not chat_id:
            return AdapterRefusal(
                "telegram_chat_id_missing",
                "Telegram delivery refused: no chat_id given and the pairing has no "
                "bound owner sender.",
            )
        # Built here, never taken from the action: an action argument is a thing a
        # model can propose, and a proposed URL plus an owner's bot token is a
        # credential-exfiltration primitive. The token also sits in the *path*,
        # which is why `post_url` reports only scheme and host on a bad URL.
        return OutboundRequest(
            url=f"https://{TELEGRAM_HOST}/bot{token}/sendMessage",
            body=json.dumps({"chat_id": chat_id, "text": text}, sort_keys=True).encode(
                "utf-8"
            ),
            headers={"X-Raiker-Delivered-At": delivered_at},
            # Telegram authenticates the token in the URL rather than a body HMAC,
            # so there is nothing for Raiker to sign and no control missing.
            # Its Bot API takes no idempotency key, which is why a delivery the
            # host stopped mid-send is reviewed rather than sent again.
            signed=False,
        )

    def provider_message_id(self, response_body: bytes) -> str | None:
        """``{"ok": true, "result": {"message_id": 123}}`` → ``"123"``."""
        result = _json_object(response_body).get("result")
        return _clean_provider_id(result.get("message_id")) if isinstance(result, dict) else None

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage | None:
        message = payload.get("message") or payload.get("edited_message") or {}
        if not isinstance(message, dict):
            return None
        sender = message.get("from")
        sender_id = (
            str(sender.get("id"))
            if isinstance(sender, dict) and sender.get("id") is not None
            else ""
        )
        text = message.get("text")
        if not sender_id or not isinstance(text, str) or not text.strip():
            return None
        chat = message.get("chat")
        chat_type = str(chat.get("type") or "") if isinstance(chat, dict) else ""
        return InboundMessage(
            sender_id=sender_id,
            text=text,
            conversation_scope="direct" if chat_type == "private" else "group",
            from_bot=bool(isinstance(sender, dict) and sender.get("is_bot")),
            event_id=_telegram_event_id(payload),
            sender_label=_telegram_sender_label(sender),
        )


def _telegram_sender_label(sender: object) -> str | None:
    """``@username`` when the sender has one, else their first and last name."""
    if not isinstance(sender, dict):
        return None
    username = sender.get("username")
    if isinstance(username, str) and username.strip():
        return f"@{username.strip()}"
    names = [
        str(sender.get(part)).strip()
        for part in ("first_name", "last_name")
        if isinstance(sender.get(part), str) and str(sender.get(part)).strip()
    ]
    return " ".join(names) or None


#: The longest provider message id kept, and the characters it may hold. An id
#: is the platform's reference, not content; anything else is not kept.
_PROVIDER_ID_MAX = 128
_PROVIDER_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:"
)


def _clean_provider_id(value: object) -> str | None:
    """A provider id as text, or ``None`` when it is not a plain short id."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not text or len(text) > _PROVIDER_ID_MAX or not set(text) <= _PROVIDER_ID_CHARS:
        return None
    return text


def _json_object(response_body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _telegram_event_id(payload: dict[str, Any]) -> str | None:
    """``update_id`` — Telegram's sequence number for one update, retries included."""
    update_id = payload.get("update_id")
    if isinstance(update_id, int) and not isinstance(update_id, bool):
        return f"update:{update_id}"
    return None


# ── The reference webhook ─────────────────────────────────────────────────────


#: The longest reply Raiker sends to an owner's webhook. The receiver is the
#: owner's own, so this is Raiker's bound rather than a platform's: one delivery
#: stays a message, not a document.
WEBHOOK_MAX_TEXT_CHARS = 32_000


class WebhookAdapter:
    """Raiker's own shape, signed by Raiker because the receiver is the owner's."""

    channel_type = "webhooks"
    capabilities: ChannelCapabilities = {
        "direct_messages": False,
        "group_chats": False,
        "threads": False,
        "streaming": False,
        "media": False,
        "reactions": False,
        "edits_and_deletes": False,
        "buttons": False,
        "typing_indicator": False,
        "max_text_chars": WEBHOOK_MAX_TEXT_CHARS,
        "authentication": "An HMAC signature on each delivery, when the outbound secret is set",
    }

    def outbound(
        self, *, connector_id: str, pairing: dict[str, Any], arguments: dict[str, Any],
        text: str, delivered_at: str, delivery_id: str,
    ) -> OutboundRequest | AdapterRefusal:
        from raiker.runtime.executors.channels import sign_delivery

        # UX-MSG-04 — the destination is part of the pairing, set by the owner
        # out of band, and never an argument. A delivery that could name its own
        # URL tested whatever was typed into a form rather than the channel, and
        # is the same exfiltration shape the Telegram comment above refuses.
        url = str(pairing.get("delivery_url") or "").strip()
        if not url:
            return AdapterRefusal(
                "channel_destination_missing",
                "Channel delivery denied: this channel has no delivery destination.",
            )
        body = json.dumps(
            {
                "text": text, "connector_id": connector_id, "delivered_at": delivered_at,
                "delivery_id": delivery_id,
            },
            sort_keys=True,
        ).encode("utf-8")
        signature, signed = sign_delivery(body)
        # DEC-12 step 4 — the delivery's receipt id is its idempotency key, so a
        # receiver that deduplicates can tell a second copy of one delivery from
        # a second message. Raiker never sends one again on its own; the key is
        # for a copy the network or a deliberate resend produces.
        headers = {"X-Raiker-Delivered-At": delivered_at, "Idempotency-Key": delivery_id}
        if signed:
            headers["X-Raiker-Signature"] = signature
        return OutboundRequest(url=url, body=body, headers=headers, signed=signed)

    def provider_message_id(self, response_body: bytes) -> str | None:
        """The owner's receiver may answer ``{"id": …}`` or ``{"message_id": …}``."""
        parsed = _json_object(response_body)
        return _clean_provider_id(parsed.get("message_id", parsed.get("id")))

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage | None:
        sender_id = str(payload.get("sender_id") or "").strip()
        text = payload.get("text")
        if not sender_id or not isinstance(text, str):
            return None
        return InboundMessage(sender_id=sender_id, text=text)


_ADAPTERS: dict[str, ChannelAdapter] = {
    a.channel_type: a for a in (TelegramAdapter(), WebhookAdapter())
}


def adapter_for(channel_type: str) -> ChannelAdapter | None:
    """The adapter for a channel type, or ``None`` if this build has no wire
    format for it — which is a refusal with a name, not a hopeful attempt."""
    return _ADAPTERS.get(channel_type)


def channel_capabilities(channel_type: str) -> ChannelCapabilities | None:
    """What a channel type can carry, or ``None`` when this build has no adapter for it."""
    adapter = _ADAPTERS.get(channel_type)
    return dict(adapter.capabilities) if adapter is not None else None  # type: ignore[return-value]


def adapter_channel_types() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))
