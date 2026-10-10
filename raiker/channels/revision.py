"""The revision of one channel pairing's configuration (§13.2 item 6).

Messaging can be open in two tabs. Without a revision, a tab still showing an
old sender allowlist saved it back over a newer one — re-admitting a sender the
owner had just removed, or re-enabling a channel they had just switched off —
and nothing said anything was overwritten.

The revision is a digest of the fields an owner decides about a pairing. A page
sends the one it read; a change made against a different one is refused with
``channel_conflict`` and nothing is written. Test results and receipts are not
part of it: they change on their own and are not the owner's configuration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

#: The owner-decided columns. A new owner-decided column belongs here too.
CONFIGURATION_FIELDS = (
    "enabled",
    "paused",
    "sender_allowlist_json",
    "routing_mode",
    "target_session_id",
    "owner_sender_id",
    "approval_relay_enabled",
    "delivery_url",
    "display_name",
)

CHANNEL_CONFLICT = "channel_conflict"


def pairing_revision(row: Mapping[str, Any]) -> str:
    """A short digest of what the owner has configured on this pairing."""
    payload = {field: row.get(field) for field in CONFIGURATION_FIELDS}
    for flag in ("enabled", "paused", "approval_relay_enabled"):
        payload[flag] = bool(payload[flag])
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def is_stale(row: Mapping[str, Any], expected_revision: str | None) -> bool:
    """Whether a change sent against ``expected_revision`` would overwrite a newer one.

    ``None`` is an older client that sent no revision; it behaves as before.
    """
    return expected_revision is not None and pairing_revision(row) != expected_revision
