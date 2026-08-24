from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── ReasonCode constants ──────────────────────────────────────────────
# Values match the denial strings returned by RuntimeAuthority so callers
# can branch on them without coupling to prose.

REASON_NOT_RUNTIME_GATE_MANAGER: str = "not_runtime_gate_manager"
REASON_ONLY_GATE_MANAGER_CAN_MANAGE: str = "only_runtime_gate_manager_can_manage_gates"
REASON_ONLY_GATE_MANAGER_CAN_ENABLE: str = "only_runtime_gate_manager_can_enable_gates"
REASON_AI_CANNOT_MANAGE_RUNTIME_GATES: str = "ai_cannot_manage_runtime_gates"
REASON_AI_ENABLE_RUNTIME_GATE: str = "ai_cannot_enable_runtime_gate"
REASON_DISABLED_BY_CAPABILITY_GATE: str = "disabled_by_capability_gate"
REASON_UNKNOWN_CAPABILITY_GATE: str = "unknown_capability_gate"
REASON_UNKNOWN_CAPABILITY: str = "unknown_capability"
REASON_INVALID_TARGET_STATE: str = "invalid_target_state"
REASON_RUNTIME_MODE_NOT_ACTIVATED: str = "runtime_mode_not_activated"
REASON_CAPABILITY_REQUIRES_ACTIVATION_TASK: str = "capability_requires_activation_task"
REASON_UNKNOWN_RUNTIME_MODE: str = "unknown_runtime_mode"
REASON_PRINCIPAL_NOT_ACTIVE: str = "principal_not_active"
REASON_PRINCIPAL_EXPIRED: str = "principal_expired"
REASON_DOMAIN_SCOPE_DENIED: str = "domain_scope_denied"
REASON_CANNOT_ASSIGN_HUMAN_ROLE_TO_AI: str = "cannot_assign_human_role_to_ai"
REASON_AI_CANNOT_APPROVE_OWN_ACTION: str = "ai_cannot_approve_own_action"
REASON_AI_CANNOT_GRANT_ROLES: str = "ai_cannot_grant_roles"
REASON_CRITICAL_REQUIRES_HUMAN: str = "critical_action_requires_human_confirmation"
REASON_DENIED_BY_POLICY: str = "denied_by_policy"
REASON_APPROVAL_REQUIRED: str = "approval_required"
REASON_RISK_ACCEPTANCE_REQUIRED: str = "risk_acceptance_required"


# ── DTOs ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ControlPrincipalRef:
    principal_id: str
    display_name: str
    principal_type: str
    role_ids: tuple[str, ...] = ()
    is_authorized_gate_manager: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "display_name": self.display_name,
            "principal_type": self.principal_type,
            "role_ids": list(self.role_ids),
            "is_authorized_gate_manager": self.is_authorized_gate_manager,
        }


@dataclass(frozen=True)
class CapabilityGateView:
    capability: str
    phase: int
    state: str
    default_state: str
    source: str = "unknown"
    runtime_enabled: bool = False
    allowed_transitions: tuple[str, ...] = ()
    can_current_principal_change: bool = False
    blocked_reason_code: str | None = None
    readiness: dict[str, Any] = field(default_factory=dict)
    # Per-capability decision mode for AI-proposed actions (ask|allow|auto|deny).
    # Included here so a UI can render the whole capability matrix in one read
    # instead of a per-capability fan-out.
    decision_mode: str = "ask"
    # Activation preconditions the UI must collect to enable this capability, so
    # the step-up dialog is driven by real backend requirements rather than a
    # hardcoded client-side list.
    requires_threat_model_ack: bool = False
    requires_human_confirmation: bool = False
    threat_model_ack_recorded: bool = False
    # GEP-04 — what this gate actually decides: `own_gate`, `governed_elsewhere`
    # or `no_path`. A switch beside a running feature that it does not govern is
    # worse than no switch, so the surface says which it is rather than letting
    # the toggle imply an authority it does not have.
    gate_reality: str = "own_gate"
    # For anything other than `own_gate`: the sentence naming what really
    # governs the work, or why nothing runs. Empty for `own_gate`.
    governance_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "phase": self.phase,
            "state": self.state,
            "default_state": self.default_state,
            "source": self.source,
            "runtime_enabled": self.runtime_enabled,
            "allowed_transitions": list(self.allowed_transitions),
            "can_current_principal_change": self.can_current_principal_change,
            "blocked_reason_code": self.blocked_reason_code,
            "readiness": dict(self.readiness),
            "decision_mode": self.decision_mode,
            "requires_threat_model_ack": self.requires_threat_model_ack,
            "requires_human_confirmation": self.requires_human_confirmation,
            "threat_model_ack_recorded": self.threat_model_ack_recorded,
            "gate_reality": self.gate_reality,
            "governance_note": self.governance_note,
        }


@dataclass(frozen=True)
class RuntimeModeView:
    mode_name: str
    status: str
    activated_by: str = ""
    activated_at: str = ""
    reason: str = ""
    allowed_modes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_name": self.mode_name,
            "status": self.status,
            "activated_by": self.activated_by,
            "activated_at": self.activated_at,
            "reason": self.reason,
            "allowed_modes": list(self.allowed_modes),
        }


@dataclass(frozen=True)
class ControlResult:
    ok: bool
    reason_code: str | None = None
    message_key: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason_code": self.reason_code,
            "message_key": self.message_key,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class RuntimeReadinessView:
    mode: RuntimeModeView
    gates: tuple[CapabilityGateView, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.to_dict(),
            "gates": [g.to_dict() for g in self.gates],
            "summary": dict(self.summary),
        }
