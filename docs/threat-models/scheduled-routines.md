# Threat Model — Scheduled Routines (Phase 4, slice 2)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capability is now
> integrated and governed/default-ask; it was historically disabled/deferred
> before its executor landed. Approval resolution is metadata-only.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`scheduled_routines` may join `REAL_EXECUTOR_CAPABILITIES`.

## What the executor does

`raiker/runtime/executors/scheduled.py::ScheduledRoutinesExecutor` defines and
runs **local, on-demand** routines. A routine bundles an interval with a bounded
read-only subagent spec. Operations: `define`, `run_due`, `run`.

**There is no background daemon, thread, or watcher.** Routines execute only
when the owner (or an external trigger) calls `run_due`/`run`; `run_due` runs
the routines whose `next_run` has passed.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| No background execution | On-demand only; nothing runs without an explicit governed `run_due`/`run` action. |
| Read-only work | A routine's payload is run via the bounded `SubagentExecutor`; mutating/egress tools fail closed (`subagent_tool_not_allowed`). |
| Minimum interval | `interval_seconds >= 60`, else `interval_too_small`. |
| Per-tick bound | At most `MAX_ROUTINES_PER_TICK` (50) routines run per `run_due`. |
| Valid payload | The payload must parse as a bounded subagent spec, else `invalid_payload`. |
| No fabricated success | Malformed ops/payloads and failed routines return `ok=False` with a reason. |
| AI principals | Capability gate + `route_action` block non-human principals from running or enabling the gate. |

## Activation requirements

Default gate state is **DISABLED**. Enabling requires a HUMAN
`runtime_gate_manager`, the `local_single_user_runtime` mode, the registered
executor, a `threat_model_acks` row referencing this document, and a human
confirmation token. AI principals can never flip the gate.

## Residual risks & non-goals

- Routines inherit the subagent read-only boundary, so a routine cannot mutate
  state, reach the network, or spawn processes.
- Out of scope: cron-style background scheduling, mutating routines, hosted
  routines, and routines that drive networked/remote work. Those remain gated.
