from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandlerDecision:
    scope: str
    decision: str
    has_authority: bool
    reason: str | None = None


def combine(decisions: list[HandlerDecision]) -> str:
    """Aggregate handler decisions. Hooks may only make an action stricter.

    Precedence: a managed deny wins; otherwise any authoritative deny wins; otherwise any
    authoritative ask wins; otherwise no decision. A handler without decision authority is
    advisory only and cannot deny or ask.
    """

    authoritative = [d for d in decisions if d.has_authority]
    if any(d.scope == "managed" and d.decision == "deny" for d in authoritative):
        return "deny"
    if any(d.decision == "deny" for d in authoritative):
        return "deny"
    if any(d.decision == "ask" for d in authoritative):
        return "ask"
    return "no_decision"
