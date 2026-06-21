# Workstream C — Governed Activation Path (Remove the In-Code Denylist)

> Goal: make every capability *mechanically flippable* by an authorized principal
> — but only through a per-capability `ActivationRequirement` gate that proves the
> capability is genuinely ready (policy + storage + events + executor + tests +
> threat-model). This replaces the blanket hard-coded refusal that currently
> rejects ~30 capabilities for everyone, including the owner.

Depends on: nothing structurally, but pairs with Workstream D (an activation
requirement is only *satisfiable* once D registers the executor). Do C's framework
first; flip each capability as its D executor lands.

---

## C.0 Current reality — the blocker

`raiker/runtime/authority/router.py`, `request_capability_transition()`, lines
**314–324** hard-refuse this set regardless of principal, role, or runtime mode:

```
shell_execution, process_execution, network_execution, web_fetch,
email_runtime, calendar_runtime, finance_runtime, investment_runtime,
medical_runtime, pregnancy_baby_runtime, cctv_runtime, home_security_runtime,
hardware_operator_runtime, plugin_execution_cap, plugin_install,
external_channel_runtime, channel_approval_relay, remote_execution_cap,
container_execution_cap, cloud_execution_cap, approval_execution_relay,
scheduled_routines, graph_indexing_runtime, semantic_memory_runtime,
vector_embedding_runtime, hosted_model_runtime, private_network_model_runtime
```

→ returns `"Capability remains disabled: {cap} requires a future explicit
activation task."`

So a UI flip is **categorically impossible** for these today. This is the
no-silent-runtime principle, but implemented as a static wall. Workstream C turns
the static wall into a **data-driven, satisfiable requirement check**.

Also note `raiker/phase_gates.py::transition_capability()` already enforces a
*readiness ladder* (`policy_ready/contract_ready/storage_ready/event_ready/
test_ready` and `ENABLED_POLICY_GATED` before `ENABLED_RUNTIME`). C builds on this
rather than replacing it.

---

## C.1 Target architecture

New module: `raiker/runtime/authority/activation.py`.

```python
@dataclass(frozen=True)
class ActivationRequirement:
    capability: str
    risk_tier: str                 # see 07_CAPABILITY_REGISTRY_AND_RISK_TIERS.md
    requires_runtime_mode: tuple[str, ...]   # e.g. ("local_single_user_runtime",)
    requires_executor: bool        # must have a registered executor (Workstream D)
    requires_policy_rules: bool
    requires_storage: bool
    requires_events: bool
    requires_threat_model_ack: bool
    requires_human_confirmation_to_enable: bool   # critical tiers
    notes: str = ""

ACTIVATION_REQUIREMENTS: dict[str, ActivationRequirement]  # one entry per capability
```

A capability transition to an enabled state is allowed iff:

1. Principal passes `_check_human_runtime_gate_manager` (unchanged).
2. The capability has an `ActivationRequirement`.
3. The target runtime mode is active and is in `requires_runtime_mode`.
4. Each `requires_*` is satisfied:
   - `requires_executor` → `ExecutorRegistry.has(capability)` is True (Workstream D).
   - `requires_policy_rules` → policy engine has rules for the capability's actions.
   - `requires_storage` / `requires_events` → migrations/event types present.
   - `requires_threat_model_ack` → a recorded, signed threat-model ack exists
     (`threat_model_acks` table: capability, acked_by, acked_at, doc_ref).
5. If `requires_human_confirmation_to_enable`, the acting principal must be HUMAN
   and supply an explicit confirmation token (mirrors the critical-action rule in
   `route_action`).

If any check fails, return a **specific reason code** (e.g.
`activation_blocked:no_executor`, `activation_blocked:no_threat_model_ack`,
`activation_blocked:runtime_mode_not_active`) — never the old generic string, and
never a silent allow.

### Change to `request_capability_transition()`

Replace lines 314–324 with a call into `evaluate_activation_requirement(capability,
target_state, principal, confirmation_token)`. Default `ActivationRequirement`
entries leave every capability **unsatisfiable until its D executor + acks land**,
so behaviour is unchanged at rest (still effectively disabled) but becomes
*satisfiable per capability* as the program progresses.

---

## C.2 Task breakdown

| Task ID | Title | Files | Acceptance |
|---|---|---|---|
| RAIKER-C001 | `ActivationRequirement` model + registry | `raiker/runtime/authority/activation.py` | One entry per capability in `ALL_CAPABILITIES`; all default to unsatisfiable (no executor yet); tests assert coverage of every capability. |
| RAIKER-C002 | `threat_model_acks` storage | `raiker/storage/sqlite.py` + migration | Insert/query signed acks; owner/`security_admin` only. |
| RAIKER-C003 | `evaluate_activation_requirement()` | `raiker/runtime/authority/activation.py`, `router.py` | Implements the 5-step check; returns specific reason codes. |
| RAIKER-C004 | Wire into `request_capability_transition()` | `raiker/runtime/authority/router.py` (replace 314–324) | Denylist gone; transitions governed by requirements; existing "stays disabled" tests still pass (because requirements unsatisfied). |
| RAIKER-C005 | Confirmation-token flow for critical tiers | `router.py`, `activation.py` | Critical capabilities require HUMAN principal + explicit confirmation; AI refused; tested. |
| RAIKER-C006 | Activation tests | `tests/test_capability_activation.py` | For a fixture capability with a stub executor + acks: flip succeeds (HUMAN owner), fails for AI, fails without ack, fails without runtime mode, reverses cleanly. |

---

## C.3 Safety gates (must hold)

- Removing the denylist must **not** make any real capability enabled by default.
  The requirement registry must leave every capability unsatisfiable until its
  executor + threat-model ack exist. Add a test that, on a fresh workspace, **no**
  capability can reach `enabled_runtime`.
- AI principals can never satisfy an activation requirement.
- Every activation/deactivation emits an audit event (capability, principal,
  target state, reason/ack ref).
- `validate_runtime_enablement_readiness.py` must be **extended** to assert: (a) no
  generic "requires a future explicit activation task" bypass remains, and (b)
  every `ALL_CAPABILITIES` member has an `ActivationRequirement`.

## C.4 Validation

Full §5 gate. The truthfulness validator and runtime-enablement validator must be
updated in this workstream to understand the new requirement model and must pass.
</content>
