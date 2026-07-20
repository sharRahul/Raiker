"""Per-action posture snapshots (User-Centric Zero Trust, ZT-3).

A posture snapshot records *who was in control, on what session, how strongly
authenticated*, at the moment a governed action is executed. Workstream A / A4
attaches it to `approval_executed` events and uses it to deny an execution whose
approving session was revoked between approval and execution.

This is intentionally a small, metadata-only helper: it captures only what can
be honestly derived from persisted state (never fabricated MFA ages). Workstream
F1 generalizes it to every governed action; A4 seeds it for the relay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore


def _age_seconds(created_at: str | None, *, now: str | None = None) -> int | None:
    if not created_at:
        return None
    try:
        start = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(now or utc_now()).replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return max(0, int((end - start).total_seconds()))


def capture_posture(
    store: SQLiteStore, principal: Principal, session_id: str = ""
) -> dict[str, Any]:
    """Build a metadata-only posture snapshot for *principal* on *session_id*.

    All fields are safe to place in the audit log: identifiers, an interface
    label, booleans, and derived ages — never tokens, secrets, or content.
    """
    session = store.load_api_session(session_id) if session_id else None
    # principal_type may be a PrincipalType enum or a plain string (rows loaded
    # straight from SQLite are not coerced), so normalise to its string value.
    principal_type = getattr(principal.principal_type, "value", str(principal.principal_type))
    return {
        "principal_id": principal.principal_id,
        "principal_type": principal_type,
        "session_id": session_id or None,
        # An API session implies a web/app interface; its absence is the local
        # terminal path, which has no revocable server-side session.
        "interface": "web_api" if session is not None else "local",
        "mfa_enrolled": store.principal_mfa_enrolled(principal.principal_id),
        "session_revoked": bool(session and session.get("revoked")),
        "session_age_seconds": _age_seconds(session.get("created_at")) if session else None,
        "captured_at": utc_now(),
    }


def posture_degraded_reason(posture: dict[str, Any]) -> str | None:
    """Return a `posture_degraded:*` reason code when the snapshot is unsafe.

    Today this fires only when the approving session was revoked between
    approval and execution — the resting state of a revoked session is deny.
    """
    if posture.get("session_revoked"):
        return "posture_degraded:session_revoked"
    return None
