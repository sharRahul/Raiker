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
executes a supported action.
