from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.contracts.views import View

# The reasons a control action is refused are `AuthorityReason`, in
# `raiker/runtime/authority/reason_codes.py` (OPT-18).


# ── DTOs ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ControlPrincipalRef(View):
    principal_id: str
    display_name: str
    principal_type: str
    role_ids: tuple[str, ...] = ()
    is_authorized_gate_manager: bool = False


@dataclass(frozen=True)
class CapabilityGateView(View):
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
    # BUG-239 — how this capability's *enforcing* path reads a gate table with
    # nothing persisted in it: `off`, `shipped_default_unscoped`, or
    # `shipped_default`. Read from `CAPABILITY_UNSET_RESOLUTION`, so the page
    # describing a gate and the path enforcing it quote the same table.
    unset_resolution: str = "off"
    # What that path would answer *right now* for this principal. On a fresh
    # account these two disagree for `web_fetch`: `state` is the fail-closed
    # per-principal reading and this is the shipped default the tool actually
    # gets. A page that shows only the first says Off about a capability that
    # would run, which is the defect FIXED-279 closed for the model's context
    # bundle and left standing on the screen the owner decides from.
    enforced_enabled: bool = False
    # BUG-293 — the two columns DEC-16 step 8 asked for that had no home. Read
    # from `CAPABILITY_AUTHORITY`, so the page answering *what would this cost
    # if it ran without me* and the test proving it will not are the same row.
    # Empty for a capability with no real executor: there is no cost to state
    # for something that cannot run, and a filled cell is always a claim
    # somebody wrote.
    side_effect: str = ""
    ungoverned_consequence: str = ""
    authority_requirement: str = ""
    #: BUG-308 — for a capability that runs code, where that code runs on *this*
    #: machine: inside the native sandbox, or with the host's network. Measured,
    #: never assumed; empty for every capability that runs no code.
    network_boundary: str = ""


@dataclass(frozen=True)
class RuntimeModeView(View):
    mode_name: str
    status: str
    activated_by: str = ""
    activated_at: str = ""
    reason: str = ""
    allowed_modes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlResult(View):
    ok: bool
    reason_code: str | None = None
    message_key: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeReadinessView(View):
    mode: RuntimeModeView
    gates: tuple[CapabilityGateView, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)
