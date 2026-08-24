# Threat Model — Remote / Cloud Execution (Phase 4, slice 6: deliberately fail-closed)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. Runtime execution remains
> disabled/deferred. Approval resolution is metadata-only.

Per the **sandboxed-first** Phase 4 decision, the off-machine command-execution
capabilities stay **fail-closed (no executor)**:

- `remote_execution_cap` (SSH/VPS remote command execution)
- `cloud_execution_cap` (cloud-provider execution)

> Update (Phase 4 slice 7): `hosted_model_runtime` and
> `private_network_model_runtime` completed the per-integration opt-in below
> and were promoted to real governed executors — see
> [`hosted-models.md`](hosted-models.md). Remote/cloud **command execution**
> remains fail-closed as documented here.

These are **not** in `REAL_EXECUTOR_CAPABILITIES`; their executors return
`not_implemented:<capability>` (`raiker/runtime/executors/tier5_network.py`),
the executor registry refuses to register them, and activation is blocked with
`activation_blocked:no_executor`. This is intentional, not an omission: each
crosses the machine boundary and carries credential-handling, egress, and
blast-radius risk that demands its own integration + threat model + tests.

## What a future per-integration opt-in MUST satisfy

Promoting any of these to a real executor (the documented process in
`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`) requires, per capability:

1. A real integration that injects credentials from an owner secret store
   (never from model/action args), over TLS, to an **owner-allowlisted**
   destination only.
2. An egress/destination allowlist that is empty by default (fail closed), plus
   per-call resource/time/budget bounds.
3. Metadata-only events (no command output, secrets, or destinations leaked).
4. A dedicated threat model documenting escape/lateral-movement risks and
   mitigations, plus a recorded `threat_model_acks` entry.
5. Acceptance tests for executes-when-governed **and** fails-closed-when-disabled.
6. Removal from the validator's `must_not_have_default_executor` set and from
   the guard test's `_SENSITIVE` tuple, in lockstep with the above.

Until all of that lands for a given capability, it remains fail-closed and
disabled/fail-closed by design, and AI principals can never run or enable it.
