# SPDX-License-Identifier: Apache-2.0
"""DEC-13 step 3 — which memories are worth the owner's review first, and why.

"Calculate review priority from retention, sensitivity, use, verification,
conflict, provenance and pin — not from one opaque score." Memory said which
records were expiring or stale, one policy at a time; nothing ordered the whole
set by what most needed a look, or said why a record was in that order.

Each factor is a named reason with a fixed weight, and the priority is their
sum, so the order is explainable by listing the reasons. Age raises a record's
place in the list and never removes it. A pin lowers the priority by one —
the owner has looked at it — but is not an exemption: a pinned record that is
expiring is still said to be expiring.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

#: Reason code → weight. Retention first (a record about to stop being recalled
#: is the most time-bound), then sensitivity, verification and provenance,
#: conflict, and use.
REVIEW_WEIGHTS: dict[str, int] = {
    # retention
    "expired": 5,
    "expires_soon": 4,
    # sensitivity
    "personal": 3,
    "unclassified": 1,
    # verification and provenance
    "written_by_agent": 2,
    "low_confidence": 2,
    # conflict
    "replaces_another": 1,
    # use
    "stale": 2,
    "never_recalled": 1,
}

#: Sources that mean the owner wrote or accepted the words themselves.
OWNER_SOURCES = frozenset(
    {"user", "owner", "manual", "human", "human_correction", "human_approved_proposal", "user_import"}
)

EXPIRES_SOON = timedelta(days=14)
STALE_AFTER = timedelta(days=90)
NEVER_RECALLED_AFTER = timedelta(days=30)
LOW_CONFIDENCE = 0.6


def _at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def review_reasons(
    memory: dict[str, Any], *, now: datetime | None = None
) -> tuple[int, tuple[str, ...]]:
    """``(priority, reasons)`` for one record; ``(0, ())`` for an archived one.

    ``memory`` carries the fields of ``MemoryControlView``: ``expires_at``,
    ``archived_at``, ``sensitivity``, ``source``, ``created_at``,
    ``updated_at``, ``confidence``, ``supersedes_memory_id``, ``last_used_at``,
    ``recall_turn_count`` and ``pinned``.
    """
    if memory.get("archived_at"):
        return 0, ()
    moment = now or datetime.now(UTC)
    reasons: list[str] = []
    expires = _at(memory.get("expires_at"))
    if expires is not None and expires <= moment:
        reasons.append("expired")
    elif expires is not None and expires - moment <= EXPIRES_SOON:
        reasons.append("expires_soon")
    sensitivity = str(memory.get("sensitivity") or "")
    if sensitivity == "personal":
        reasons.append("personal")
    elif sensitivity in {"", "unknown"}:
        reasons.append("unclassified")
    created = _at(memory.get("created_at"))
    updated = _at(memory.get("updated_at"))
    edited = created is not None and updated is not None and updated > created
    if str(memory.get("source") or "") not in OWNER_SOURCES and not edited:
        reasons.append("written_by_agent")
    try:
        confidence = float(memory.get("confidence"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        confidence = 1.0
    if confidence < LOW_CONFIDENCE:
        reasons.append("low_confidence")
    if memory.get("supersedes_memory_id"):
        reasons.append("replaces_another")
    touched = [at for at in (created, updated, _at(memory.get("last_used_at"))) if at is not None]
    if touched and max(touched) < moment - STALE_AFTER:
        reasons.append("stale")
    elif (
        int(memory.get("recall_turn_count") or 0) == 0
        and not memory.get("last_used_at")
        and created is not None
        and created < moment - NEVER_RECALLED_AFTER
    ):
        reasons.append("never_recalled")
    priority = sum(REVIEW_WEIGHTS[reason] for reason in reasons)
    if reasons and memory.get("pinned"):
        priority = max(1, priority - 1)
    return priority, tuple(reasons)


__all__ = ["REVIEW_WEIGHTS", "review_reasons"]
