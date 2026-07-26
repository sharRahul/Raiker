# API and contract schemas

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

`raiker-web` is a local loopback API. It is a client of the same governed
backend as the terminal; it adds no direct tool authority.

## Core API areas

| Area | Purpose |
|---|---|
| Authentication | Creates a local, in-memory session token for a human principal |
| Prompts and turns | Submits a governed turn and returns safe response metadata |
| Models | Lists profiles and exposes governed selection/readiness |
| Runtime control | Reads or changes runtime mode and capability gates through RuntimeAuthority |
| Audit views | Reads sessions, events, checkpoints, approvals, and diagnostics |

A persisted principal is resolved for each authenticated request. The durable
`runtime_mode_state` and `capability_gate_state` records are the source of
runtime-control state. `/runtime-readiness` reports blockers and available
governance controls.

Requests that propose a mutation are subject to policy, decision mode, and
approval requirements. Approval resolution remains metadata-only unless a
supported action enters its separately governed execution path.

See [contracts](CONTRACTS.md) and [commands](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md).
