from __future__ import annotations

from enum import StrEnum

from raiker.runtime.authority.models import RiskLevelValue


class DecisionMode(StrEnum):
    """Per-capability decision mode layered on top of the capability gate.

    The gate still governs *whether* a capability is enabled at all (default
    disabled, fail-closed). Once enabled, the decision mode governs *how* an
    AI-proposed action on that capability is treated:

    - ``ask`` (default): the action requires human approval before it runs.
    - ``deny``: the action is always blocked.
    - ``allow``: the action runs without prompting — but the critical-risk
      human-confirmation floor and every PolicyEngine hard-deny still apply.
    - ``auto`` ("let Raiker decide"): a deterministic, auditable choice keyed off
      the action's risk level — low runs, medium/high ask, critical stays on the
      human-confirmation floor. No opaque model call participates in the trust
      decision.
    """

    ASK = "ask"
    DENY = "deny"
    ALWAYS_ALLOW = "allow"
    AUTO = "auto"


DEFAULT_DECISION_MODE = DecisionMode.ASK

# Modes that let an action run more freely than the fail-closed default require a
# real executor behind the capability. ``ask``/``deny`` are always selectable
# (they only ever tighten behavior); ``allow``/``auto`` may only be set on
# capabilities that can actually execute, so a sensitive/no-executor domain can
# never be relaxed into acting.
PERMISSIVE_MODES = frozenset({DecisionMode.ALWAYS_ALLOW, DecisionMode.AUTO})


def parse_decision_mode(value: str) -> DecisionMode | None:
    # Backward-compatible config/database alias from the earlier internal name.
    aliases = {"always_allow": DecisionMode.ALWAYS_ALLOW.value}
    try:
        return DecisionMode(aliases.get(value, value))
    except ValueError:
        return None


def auto_requires_approval(risk_level: str) -> bool:
    """Deterministic ``auto`` policy: only low-risk actions run unprompted.

    Critical is handled by the router's standing human-confirmation floor before
    this is consulted, so it is treated as "approval required" here for safety.
    """
    return risk_level != RiskLevelValue.LOW
