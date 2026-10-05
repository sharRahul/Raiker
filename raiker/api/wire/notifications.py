# SPDX-License-Identifier: Apache-2.0
"""When notices may interrupt the owner (DEC-21a), and what quiet hours held."""

from __future__ import annotations

from typing_extensions import TypedDict

from raiker.control.views.security import (
    InterruptCategory,
    NotificationDelivery,
    NotificationView,
    QuietHoursState,
)

__all__ = [
    "HeldNotificationsAcknowledged",
    "InterruptCategory",
    "NotificationDelivery",
    "QuietHoursState",
    "TestNoticeSent",
]


class HeldNotificationsAcknowledged(TypedDict):
    acknowledged: int


class TestNoticeSent(TypedDict):
    """A test notice, written through the same policy as a real one."""

    notification: NotificationView
