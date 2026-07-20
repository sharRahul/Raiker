"""Scoped standing approval grants (User-Centric Zero Trust, ZT-5 / F3).

A standing grant is the actual "frictionless" mechanism: instead of answering an
identical approval prompt over and over, a human answers a *class* of prompt once
by creating a scoped, expiry-bound grant. A later AI-proposed action whose shape
matches an active grant — same action type, in-scope, at or below the grant's
risk ceiling — runs without a fresh prompt. Every use is logged with the grant id.

The grant model is one shape shared by Workstreams A/C/E:
``(principal, action shape, scope pattern, risk ceiling, expires_at)``.

Invariants enforced here (never relaxed):

* **Human-created only.** ``granted_by`` must be a human principal — an AI can
  never mint or broaden its own grant. (Creating a grant is itself a critical,
  human-decided action per F6 criterion (d).)
* **Sub-critical ceiling.** ``risk_ceiling`` is strictly below ``critical`` by
  construction, so no grant can ever pre-authorize a critical action. Critical
  actions are floored to a live human decision regardless of any grant.
* **Mandatory expiry.** Every grant has an ``expires_at`` (default 7 days). There
  is no permanent "always allow" grant; an expired grant matches nothing.
* **Narrowing only, revocable, listed.** A grant can only narrow from the human
  decision that created it; it is always listed in Security Settings and can be
  revoked at any time (revocation is immediate — the resting state is deny).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue

# Risk ordering used to compare an action's risk against a grant's ceiling. The
# critical tier is intentionally *absent* — a grant can never cover it.
_RISK_ORDER: dict[str, int] = {
    RiskLevelValue.LOW: 0,
    RiskLevelValue.MEDIUM: 1,
    RiskLevelValue.HIGH: 2,
}

# Grants may only be created with a ceiling in this set — strictly below critical.
GRANTABLE_RISK_CEILINGS: frozenset[str] = frozenset(_RISK_ORDER)

DEFAULT_GRANT_TTL_DAYS = 7


@dataclass(frozen=True)
class StandingGrant:
    grant_id: str
    principal_id: str
    granted_by: str
    action_type: str
    tool_name: str
    scope_pattern: str
    risk_ceiling: str
    reason: str
    created_at: str
    expires_at: str
    revoked: bool = False
    revoked_at: str | None = None
    revoked_by: str | None = None
    use_count: int = 0
    last_used_at: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> StandingGrant:
        return cls(
            grant_id=str(row["grant_id"]),
            principal_id=str(row["principal_id"]),
            granted_by=str(row["granted_by"]),
            action_type=str(row["action_type"]),
            tool_name=str(row.get("tool_name", "")),
            scope_pattern=str(row.get("scope_pattern", "*")),
            risk_ceiling=str(row["risk_ceiling"]),
            reason=str(row.get("reason", "")),
            created_at=str(row["created_at"]),
            expires_at=str(row["expires_at"]),
            revoked=bool(row.get("revoked")),
            revoked_at=row.get("revoked_at"),
            revoked_by=row.get("revoked_by"),
            use_count=int(row.get("use_count", 0)),
            last_used_at=row.get("last_used_at"),
        )


def _risk_rank(risk_level: str) -> int | None:
    return _RISK_ORDER.get(risk_level)


def is_expired(grant_row: dict[str, Any], *, now: str | None = None) -> bool:
    expires_at = str(grant_row.get("expires_at", ""))
    if not expires_at:
        return True
    return (now or utc_now()) > expires_at


def grant_covers(
    grant_row: dict[str, Any],
    *,
    action_type: str,
    tool_name: str,
    scope: str,
    risk_level: str,
    now: str | None = None,
) -> bool:
    """True when an active grant covers this exact action shape.

    A grant covers an action when it is not revoked, not expired, the action
    types match, the grant's tool_name matches (empty = any tool for that action
    type), the action's scope matches the grant's glob pattern, and the action's
    risk is at or below the grant's ceiling. A critical action never has a rank
    in ``_RISK_ORDER`` and so is never covered — the fail-closed default.
    """
    if bool(grant_row.get("revoked")):
        return False
    if is_expired(grant_row, now=now):
        return False
    if str(grant_row.get("action_type")) != action_type:
        return False
    grant_tool = str(grant_row.get("tool_name", ""))
    if grant_tool and grant_tool != tool_name:
        return False
    action_rank = _risk_rank(risk_level)
    ceiling_rank = _risk_rank(str(grant_row.get("risk_ceiling", "")))
    if action_rank is None or ceiling_rank is None or action_rank > ceiling_rank:
        return False
    pattern = str(grant_row.get("scope_pattern", "*")) or "*"
    return fnmatch.fnmatch(scope or "", pattern)


class GrantValidationError(ValueError):
    """Raised when a grant creation request violates a grant invariant."""


def build_grant_record(
    *,
    principal_id: str,
    granted_by: Principal,
    action_type: str,
    tool_name: str = "",
    scope_pattern: str = "*",
    risk_ceiling: str,
    reason: str = "",
    ttl_days: float = DEFAULT_GRANT_TTL_DAYS,
) -> dict[str, Any]:
    """Validate the invariants and build a grant row ready to persist.

    Raises :class:`GrantValidationError` with a stable reason code when any
    invariant is violated, so an invalid grant is never written.
    """
    if granted_by.principal_type != PrincipalType.HUMAN:
        raise GrantValidationError("only_human_may_create_grant")
    if not action_type:
        raise GrantValidationError("grant_action_type_required")
    if risk_ceiling == RiskLevelValue.CRITICAL:
        raise GrantValidationError("grant_ceiling_cannot_be_critical")
    if risk_ceiling not in GRANTABLE_RISK_CEILINGS:
        raise GrantValidationError(f"invalid_grant_risk_ceiling:{risk_ceiling}")
    if ttl_days <= 0:
        raise GrantValidationError("grant_ttl_must_be_positive")
    created = datetime.now(UTC).replace(microsecond=0)
    created_at = created.isoformat().replace("+00:00", "Z")
    expires_at = (created + timedelta(days=ttl_days)).isoformat().replace("+00:00", "Z")
    return {
        "grant_id": new_id("grn_"),
        "principal_id": principal_id,
        "granted_by": granted_by.principal_id,
        "action_type": action_type,
        "tool_name": tool_name,
        "scope_pattern": scope_pattern or "*",
        "risk_ceiling": risk_ceiling,
        "reason": reason,
        "created_at": created_at,
        "expires_at": expires_at,
    }
