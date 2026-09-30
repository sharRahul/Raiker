"""The reasons the authority router refuses, named once.

OPT-18. These strings were literals in ``router.py``, a second list of
``REASON_*`` constants in ``control/dtos.py`` that callers and tests branched on,
and a third, hand-kept table of owner-facing copy in the web client. They are
one :class:`~enum.StrEnum` now: a member *is* its wire string, so a response
body, a log line and a comparison all read the same value, and
``tests/test_reason_code_catalogue.py`` fails when the web client's copy names a
code this catalogue does not have, or a code here has no copy for the owner.

A reason that carries a subject — the capability, the scope, the mode — is
spelled ``<reason>:<subject>``; :func:`scoped` builds it, and the web client
reads the part before the colon.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["AuthorityReason", "SCOPED_REASONS", "scoped"]


class AuthorityReason(StrEnum):
    # Principal state.
    PRINCIPAL_NOT_ACTIVE = "principal_not_active"
    PRINCIPAL_EXPIRED = "principal_expired"
    DOMAIN_SCOPE_DENIED = "domain_scope_denied"
    CANNOT_ASSIGN_HUMAN_ROLE_TO_AI = "cannot_assign_human_role_to_ai"
    # What an AI principal may never do for itself.
    AI_CANNOT_APPROVE_OWN_ACTION = "ai_cannot_approve_own_action"
    AI_CANNOT_GRANT_ROLES = "ai_cannot_grant_roles"
    AI_CANNOT_MANAGE_RUNTIME_GATES = "ai_cannot_manage_runtime_gates"
    AI_CANNOT_ENABLE_RUNTIME_GATE = "ai_cannot_enable_runtime_gate"
    # Who may change gates.
    ONLY_RUNTIME_GATE_MANAGER_CAN_MANAGE_GATES = "only_runtime_gate_manager_can_manage_gates"
    ONLY_RUNTIME_GATE_MANAGER_CAN_ENABLE_GATES = "only_runtime_gate_manager_can_enable_gates"
    # Capabilities, modes and transitions.
    DISABLED_BY_CAPABILITY_GATE = "disabled_by_capability_gate"
    UNKNOWN_CAPABILITY_GATE = "unknown_capability_gate"
    UNKNOWN_CAPABILITY = "unknown_capability"
    INVALID_TARGET_STATE = "invalid_target_state"
    INVALID_DECISION_MODE = "invalid_decision_mode"
    DECISION_MODE_REQUIRES_EXECUTOR = "decision_mode_requires_executor"
    UNKNOWN_RUNTIME_MODE = "unknown_runtime_mode"
    # Standing grants.
    GRANT_TARGET_IS_CRITICAL = "grant_target_is_critical"
    ONLY_HUMAN_MAY_REVOKE_GRANT = "only_human_may_revoke_grant"
    GRANT_NOT_FOUND_OR_ALREADY_REVOKED = "grant_not_found_or_already_revoked"
    # Routing outcomes.
    CRITICAL_ACTION_REQUIRES_HUMAN_CONFIRMATION = "critical_action_requires_human_confirmation"
    DENIED_BY_POLICY = "denied_by_policy"
    APPROVAL_REQUIRED = "approval_required"
    RISK_ACCEPTANCE_REQUIRED = "risk_acceptance_required"


#: The reasons that are always sent with a subject after the colon.
SCOPED_REASONS = frozenset(
    {
        AuthorityReason.DOMAIN_SCOPE_DENIED,
        AuthorityReason.CANNOT_ASSIGN_HUMAN_ROLE_TO_AI,
        AuthorityReason.UNKNOWN_CAPABILITY,
        AuthorityReason.INVALID_TARGET_STATE,
        AuthorityReason.INVALID_DECISION_MODE,
        AuthorityReason.DECISION_MODE_REQUIRES_EXECUTOR,
        AuthorityReason.UNKNOWN_RUNTIME_MODE,
    }
)


def scoped(reason: AuthorityReason, subject: object) -> str:
    """``<reason>:<subject>`` — the wire spelling of a reason about one thing."""
    return f"{reason}:{subject}"
