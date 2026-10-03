# SPDX-License-Identifier: Apache-2.0
"""Pairing and routing a channel, and what the inbound receivers answer."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.control.views.extensions import ChannelRoutingMode


class ChannelPaired(TypedDict):
    """Paired is not enabled: that is a second decision."""

    ok: bool
    pairing_id: str
    enabled: bool


class ChannelEnabledSet(TypedDict):
    ok: bool
    pairing_id: str
    enabled: bool


class ChannelSendersSet(TypedDict):
    ok: bool
    pairing_id: str
    sender_count: int


class ChannelRoutingSet(TypedDict):
    ok: bool
    pairing_id: str
    routing_mode: ChannelRoutingMode


class ChannelUnpaired(TypedDict):
    ok: bool
    pairing_id: str
    removed: bool


class ChannelTestDelivered(TypedDict):
    """One governed test delivery: sizes and status, never the text sent."""

    ok: bool
    delivered: bool
    connector_id: str
    channel_type: str
    sent_bytes: int
    status: int
    signed: bool


class InboundRoute(TypedDict):
    """What the stored route did with an inbound message; message fields grant nothing."""

    routed: bool
    routing_mode: str
    reason_code: NotRequired[str]
    action: NotRequired[Literal["stop", "steer"]]
    session_id: NotRequired[str]
    turn_id: NotRequired[str]
    status: NotRequired[str]
    reply: NotRequired[str]


class ChannelInboundAccepted(InboundRoute):
    """An inbound message recorded; quarantined unless the route carried it somewhere."""

    ok: bool
    channel_message_id: str
    trust_level: Literal["owner", "untrusted"]
    quarantined: bool


class ChannelDestinationSet(TypedDict):
    """A webhook channel's destination bound or cleared — whether, never where."""

    ok: bool
    pairing_id: str
    has_destination: bool


class ChannelUpdateIgnored(TypedDict):
    """A transport update that is not a message: acknowledged so it is not retried."""

    ok: bool
    ignored: str


class ApprovalRelayAnswered(TypedDict):
    ok: bool
    relay_id: str
    approval_id: str
    status: str
    resumable: bool
