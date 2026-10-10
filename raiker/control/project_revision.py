"""Revisions for what an owner configures on a project (§13.2 item 6).

Projects can be open in two tabs. The context editor saved whatever its
textarea held, so a tab opened before the instructions were rewritten saved the
old text back over the new; a move from a stale tree undid a move made
elsewhere. Each change now carries the revision the page read and is refused
with ``project_conflict`` when it no longer matches.

Two revisions, because they change for different reasons: the *context* (what
every chat filed here is given) and the *placement* (name, parent, archived).
Activity counts and timestamps are in neither — they move on their own.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

PROJECT_CONFLICT = "project_conflict"


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def context_revision(context: Mapping[str, Any]) -> str:
    return _digest(
        {
            "instructions": context.get("instructions") or "",
            "attachment_ids": list(context.get("attachment_ids") or []),
            "memory_mode": context.get("memory_mode") or "inherit",
            "memory_enabled": bool(context.get("memory_enabled")),
        }
    )


def placement_revision(row: Mapping[str, Any]) -> str:
    return _digest(
        {
            "name": row.get("name") or "",
            "parent_id": row.get("parent_id"),
            "is_archived": bool(row.get("is_archived")),
        }
    )
