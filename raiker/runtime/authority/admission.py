"""One capability admission check, shared by every path that needs one.

**Why this exists (GEP-01).** Eight modules used to carry their own copy of the
capability-gate lookup — a local ``_ENABLED_GATE_STATES`` constant, a local
"is this principal account-scoped" test, and a local decision-mode read. None of
them was wrong. Eight independent copies of a governance check is simply the
precondition for drift, and this repository has already produced one instance of
exactly that pattern in its two egress implementations.

Two drifts were live in the eight copies when this module replaced them:

* **Scope.** ``RuntimeAuthority`` resolves the control scope with
  ``store.account_scope``, which maps a delegated AI-agent principal onto the
  owner account that delegated it. The eight used ``store.get_account(pid) is
  not None``, which does not — so the same capability could read the owner's
  gate at chokepoint B and the workspace-wide gate inside the tool. No shipped
  path passed an AI-agent principal to any of the eight, so the drift was latent
  rather than live; it is closed here by construction.
* **Failure.** Some copies caught a broken store read and reported "off";
  others let it raise. Every admission here fails closed with a named reason.

**What this module is not.** It is not a second chokepoint. It answers exactly
the question the eight already asked — *may this capability run for this
principal at all, and under what decision mode* — and it answers it once. The
checks that belong to :meth:`RuntimeAuthority.route_action` (self-approval,
domain scope, the critical floor, the audit event) stay there; a caller that
needs those routes an action instead of calling this.

**The runtime status is reported, never enforced here.** Whether "stop the agent
runtime" should also stop a read that leaves the machine is
`GEP-02 <../../../docs/plans/GOVERNANCE_ENTRY_PATHS.md>`_ — an owner decision
that no document has answered. :attr:`CapabilityAdmission.runtime_active` makes
the answer available to every call site at no cost, and nothing consults it yet,
so this module records the question rather than silently deciding it.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from raiker.runtime.authority.decision_modes import (
    DEFAULT_DECISION_MODE,
    DecisionMode,
    parse_decision_mode,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The gate states that mean "this capability may run". Anything else — including
#: a gate with no persisted row at all — is off. This is the one copy.
ENABLED_GATE_STATES = frozenset({
    "enabled_read_only",
    "enabled_policy_gated",
    "enabled_runtime",
})

#: The reason a caller reports when the gate itself is off. Named exactly as
#: ``RuntimeAuthority.check_capability_gate`` names it, so an owner meets one
#: reason code wherever the refusal happens.
REASON_GATE_DISABLED = "disabled_by_capability_gate"

#: The reason a caller reports when the gate is on and the owner's decision mode
#: for it is ``deny``.
REASON_DENIED_BY_MODE = "denied_by_decision_mode"

# ── What "nothing persisted" means ──────────────────────────────────────────
# Three answers were live in the eight call sites this module replaced, and the
# difference is visible to an owner: on a fresh account `web_fetch` was on and
# `code_map_indexing` was off, from the same empty table. The fork is named here
# rather than decided, because deciding it silently would either loosen seven
# paths or tighten one.

#: Nothing persisted is nothing decided, and nothing decided is not consent.
#: What seven of the eight original call sites did.
UNSET_OFF = "off"
#: Fall back to the shipped gate table only for a caller with no account — what
#: :meth:`RuntimeAuthority.check_capability_gate` does, and what the code map
#: deliberately matched.
UNSET_SHIPPED_DEFAULT_UNSCOPED = "shipped_default_unscoped"
#: Fall back to the shipped gate table for any caller. RAIKER-2021: an owner who
#: turns a capability off writes a row, and that row wins; an empty table on a
#: fresh install is not a refusal.
UNSET_SHIPPED_DEFAULT = "shipped_default"

UNSET_RESOLUTIONS = frozenset({
    UNSET_OFF,
    UNSET_SHIPPED_DEFAULT_UNSCOPED,
    UNSET_SHIPPED_DEFAULT,
})

#: Which resolution each capability's *enforcing* path uses. Anything absent is
#: :data:`UNSET_OFF`.
#:
#: This is a table rather than an argument at each call site because the fork was
#: not only between enforcing paths — it was between an enforcing path and the
#: surfaces that *describe* it. The context bundle told the model
#: ``web_fetch: disabled`` on a fresh install while `WebAccessService` fetched
#: happily, because the two resolved an empty gate table differently. Reading the
#: rule from one place is what makes the description and the behaviour the same
#: fact.
CAPABILITY_UNSET_RESOLUTION: dict[str, str] = {
    # RAIKER-2021 — an owner who turns web access off writes a row; an empty
    # table on a fresh install is not a refusal.
    "web_fetch": UNSET_SHIPPED_DEFAULT,
    # The code map matches `RuntimeAuthority.check_capability_gate`: an account
    # with nothing persisted has not said yes yet; only a caller with no account
    # falls back to the shipped table.
    "code_map_indexing": UNSET_SHIPPED_DEFAULT_UNSCOPED,
    # Delegation, for the same reason and by the same precedent. It is the
    # posture `RUNTIME_EXECUTORS_SPEC.md` documents for every integrated
    # capability: the web dashboard's per-principal controls are fail-closed
    # until the owner turns a gate on, and the single-user terminal client — a
    # principal with no account row — gets the shipped default.
    "subagents": UNSET_SHIPPED_DEFAULT_UNSCOPED,
}


def unset_resolution_for(capability: str) -> str:
    """How *capability* resolves a gate table with nothing persisted in it."""
    return CAPABILITY_UNSET_RESOLUTION.get(capability, UNSET_OFF)


@dataclass(frozen=True)
class CapabilityAdmission:
    """Everything a non-routing call site needs to decide whether to proceed."""

    capability: str
    #: The owner account the gate was read under, or ``None`` when the lookup was
    #: workspace-wide. Resolved with ``store.account_scope`` — the same
    #: resolution :class:`RuntimeAuthority` uses.
    control_scope: str | None
    #: The persisted gate state, or ``""`` when nothing is persisted.
    state: str
    #: The owner's decision mode for this capability (``ask`` when unset).
    decision_mode: DecisionMode
    #: Whether the agent runtime is accepting executions. Reported, not enforced
    #: — see the module docstring and GEP-02.
    runtime_active: bool

    @property
    def gate_enabled(self) -> bool:
        return self.state in ENABLED_GATE_STATES

    @property
    def denied_by_mode(self) -> bool:
        return self.gate_enabled and self.decision_mode == DecisionMode.DENY

    @property
    def admitted(self) -> bool:
        """True only when the gate is on and the owner has not set ``deny``."""
        return self.gate_enabled and not self.denied_by_mode

    @property
    def refusal(self) -> str | None:
        """The reason code to report, or ``None`` when the capability may run."""
        if not self.gate_enabled:
            return REASON_GATE_DISABLED
        if self.denied_by_mode:
            return REASON_DENIED_BY_MODE
        return None


def _control_scope(store: SQLiteStore, principal_id: str | None) -> str | None:
    try:
        return store.account_scope(principal_id)
    except Exception:  # noqa: BLE001 — an unreadable principal is not an account
        return None


def _read_gate(
    store: SQLiteStore, control_scope: str | None, capability: str
) -> tuple[Mapping[str, Any] | None, bool]:
    """``(row, readable)``. A failed read is **not** the same as an empty table.

    Collapsing the two is a fail-open: `web_fetch` resolves an empty table to
    the shipped default (enabled), so a storage error that reported "nothing
    persisted" would have turned a broken read into an enabled capability. The
    second element is what keeps the fallback out of the error path.
    """
    try:
        record = (
            store.get_principal_capability_gate_state(control_scope, capability)
            if control_scope is not None
            else store.get_capability_gate_state(capability)
        )
    except Exception:  # noqa: BLE001 — an unreadable gate reports "off", never "on"
        return None, False
    return (record or None), True


def _gate_record(
    store: SQLiteStore, control_scope: str | None, capability: str
) -> Mapping[str, Any] | None:
    return _read_gate(store, control_scope, capability)[0]


def _shipped_default_state(capability: str) -> str:
    """The state the shipped gate table declares for *capability*, or ``""``."""
    from raiker.phase_gates import default_capability_gates

    try:
        gate = default_capability_gates().get(capability)
    except Exception:  # noqa: BLE001 — an unreadable default table is not an enable
        return ""
    return gate.state.value if gate is not None else ""


def _gate_state(
    store: SQLiteStore,
    control_scope: str | None,
    capability: str,
    *,
    unset: str,
) -> str:
    record, readable = _read_gate(store, control_scope, capability)
    if record is not None:
        return str(record.get("state", ""))
    if not readable:
        # A broken read is off, whatever the shipped table says. This is the one
        # place the three unset resolutions do not differ.
        return ""
    if unset == UNSET_SHIPPED_DEFAULT:
        return _shipped_default_state(capability)
    if unset == UNSET_SHIPPED_DEFAULT_UNSCOPED and control_scope is None:
        return _shipped_default_state(capability)
    return ""


def _decision_mode(
    store: SQLiteStore, control_scope: str | None, capability: str
) -> DecisionMode:
    try:
        persisted = (
            store.get_principal_capability_decision_mode(control_scope, capability)
            if control_scope is not None
            else store.get_capability_decision_mode(capability)
        )
    except Exception:  # noqa: BLE001 — an unreadable mode falls back to the safe default
        persisted = None
    mode = parse_decision_mode(persisted) if persisted else None
    return mode or DEFAULT_DECISION_MODE


def _runtime_active(store: SQLiteStore, control_scope: str | None) -> bool:
    """Whether the one runtime is accepting executions.

    No stored row means active: Raiker runs one runtime, and a fresh install has
    nothing to activate before its gates mean what they say. This mirrors
    ``RuntimeAuthority.get_runtime_mode`` rather than re-deciding it.
    """
    from raiker.runtime.authority.models import RUNTIME_STATUS_ACTIVE

    try:
        stored = (
            store.get_principal_runtime_mode(control_scope)
            if control_scope is not None
            else store.get_latest_runtime_mode()
        )
    except Exception:  # noqa: BLE001 — an unreadable runtime row is not a stop
        return True
    if stored is None:
        return True
    return str(stored.get("status", RUNTIME_STATUS_ACTIVE)) == RUNTIME_STATUS_ACTIVE


def capability_admission(
    store: SQLiteStore,
    principal_id: str | None,
    capability: str,
    *,
    unset: str | None = None,
) -> CapabilityAdmission:
    """Read one capability's gate state, decision mode and runtime status.

    The single lookup every non-routing governed path performs. It reads; it
    never writes, never emits an event and never decides on the caller's behalf
    — the caller reports :attr:`CapabilityAdmission.refusal` in whatever shape
    its own contract uses.

    ``unset`` names which of the three "nothing persisted" resolutions to use.
    Left as ``None`` — which every caller should do — it is read from
    :data:`CAPABILITY_UNSET_RESOLUTION`, so a capability resolves the same way
    wherever it is asked about. The three exist rather than one because unifying
    them would either loosen seven paths or tighten one, and that is an
    owner-visible change rather than a refactor.
    """
    if unset is None:
        unset = unset_resolution_for(capability)
    if unset not in UNSET_RESOLUTIONS:
        raise ValueError(f"capability_admission_unset_invalid:{unset}")
    control_scope = _control_scope(store, principal_id)
    return CapabilityAdmission(
        capability=capability,
        control_scope=control_scope,
        state=_gate_state(store, control_scope, capability, unset=unset),
        decision_mode=_decision_mode(store, control_scope, capability),
        runtime_active=_runtime_active(store, control_scope),
    )


def gate_enabled(
    store: SQLiteStore, principal_id: str | None, capability: str, *, unset: str | None = None
) -> bool:
    """Shorthand for the commonest question: is this capability's gate on?"""
    return capability_admission(store, principal_id, capability, unset=unset).gate_enabled


def capability_gate_record(
    store: SQLiteStore, principal_id: str | None, capability: str
) -> Mapping[str, Any] | None:
    """The persisted gate row itself, read under the shared control scope.

    For the one caller that needs more than the state: distinguishing *the owner
    turned this off* from *nobody has decided yet* requires the row's ``source``,
    and inventing a second scope resolution to get at it is the drift this module
    exists to prevent.
    """
    return _gate_record(store, _control_scope(store, principal_id), capability)
