# Contracts

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker contracts use explicit fields, stable identifiers, and safe failure
states. Unknown capabilities, principals, or action shapes are rejected.

## Principal resolution contract

Every request resolves a persisted, active principal. Human-only roles cannot
be assigned to AI principals. The resolved principal, interface, and session
metadata are included in governance and audit context.

## Runtime mode activation contract

Only a human `runtime_gate_manager` may activate or disable a runtime mode. The
transition is governed, persisted, and audited; AI principals cannot perform it.

## Capability gate transition contract

A capability gate transition requires the applicable principal, runtime mode,
policy constraints, and a real executor where execution is claimed. Invalid
transitions fail closed.

## Approval contract

An approval records an immutable proposed action and an expiry. Resolving the
record is metadata-only unless the separately governed relay revalidates and
executes a supported action — the twelve capabilities in `EXECUTABLE_ON_APPROVAL`
(`raiker/approvals/execution.py`). The relay re-checks its own gate, the target
capability's gate, policy and posture at execution time; either gate being off
returns the approval to metadata-only, and the surface says which before the
owner decides.

A **critical** approval never reaches the relay. It keeps the human-only,
step-up-verified lifecycle in `RuntimeAuthority.resolve_critical_approval`.

## Proposed personal-goal contracts

The [target contracts](PERSONAL_AUTONOMOUS_AGENT_SPEC.md#proposed-durable-contracts)
define logical Goal, Goal step, Delegation envelope, Standing intent, Personal
context reference, Effect receipt and Outcome assessment records. PAA-01/02/08
must supply concrete versioned schemas, owner-scoped migrations and concurrency
checks before implementation. Reuse task/session/action/approval IDs by reference.
Envelope scope intersects current authority and never replaces policy or grants
human roles. Keep unknown external effects distinct from confirmed results.
These proposed records are not classes implemented by the current runtime.
