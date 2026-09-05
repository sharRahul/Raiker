"""One adapter per channel type, resolved from a table.

The reference webhook and Telegram were an ``if channel_type == "telegram"``
inside :class:`ExternalChannelExecutor`. That works for two and stops working at
three, which is the point at which every messaging product has had to answer the
same question.

**The shape here is borrowed from Hermes Agent** (MIT, © 2025 Nous Research),
which runs twenty-two platforms off one gateway: a table keyed by platform, each
entry owning its own wire format, and the gateway owning everything that is not
wire format. What is *not* borrowed is the size of it — Hermes's
``BasePlatformAdapter`` is four thousand lines of streaming edits, typing
bubbles, TTS, media caches and inline keyboards, because Hermes is a chat client
you talk to. A Raiker channel is a governed relay whose default routing is
``record_only``. Importing that surface would be importing a different product's
problem.

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


class ChannelAdapter(Protocol):
    channel_type: str

    def outbound(
        self, *, connector_id: str, pairing: dict[str, Any], arguments: dict[str, Any],
        text: str, delivered_at: str,
    ) -> OutboundRequest | AdapterRefusal: ...

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage | None:
        """``None`` for a payload that is not a message and never will be."""
        ...


# ── Telegram ──────────────────────────────────────────────────────────────────

TELEGRAM_HOST = "api.telegram.org"


class TelegramAdapter:
    channel_type = "telegram"

    def outbound(
        self, *, connector_id: str, pairing: dict[str, Any], arguments: dict[str, Any],
        text: str, delivered_at: str,
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
            signed=False,
        )

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
        return InboundMessage(sender_id=sender_id, text=text)


# ── The reference webhook ─────────────────────────────────────────────────────


class WebhookAdapter:
    """Raiker's own shape, signed by Raiker because the receiver is the owner's."""

    channel_type = "webhooks"

    def outbound(
        self, *, connector_id: str, pairing: dict[str, Any], arguments: dict[str, Any],
        text: str, delivered_at: str,
    ) -> OutboundRequest | AdapterRefusal:
        from raiker.runtime.executors.channels import sign_delivery

        url = str(arguments.get("url", "")).strip()
        if not url:
            return AdapterRefusal(
                "missing_argument:connector_id_or_url",
                "Channel delivery denied: connector_id and url required.",
            )
        body = json.dumps(
            {"text": text, "connector_id": connector_id, "delivered_at": delivered_at},
            sort_keys=True,
        ).encode("utf-8")
        signature, signed = sign_delivery(body)
        headers = {"X-Raiker-Delivered-At": delivered_at}
        if signed:
            headers["X-Raiker-Signature"] = signature
        return OutboundRequest(url=url, body=body, headers=headers, signed=signed)

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


def adapter_channel_types() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))
