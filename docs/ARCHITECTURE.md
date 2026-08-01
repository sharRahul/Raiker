# Architecture

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is a local-first runtime with two clients: the terminal client and the
loopback web dashboard. Both call the same gateway; neither receives direct
tool authority.

## Governed action flow

`client → gateway → policy → RuntimeAuthority → executor → audit/event store`

The gateway resolves the principal and records request context. Policy classifies
the requested action. RuntimeAuthority checks that the agent runtime is
accepting executions, then the capability gate, decision mode, approval state,
and executor availability before any action can run. There is one runtime —
`raiker_runtime` — and its only runtime-level state is `active` or `disabled`;
the historical mode names (`development_preview`, the single-user modes,
`multi_user_local_runtime`, `hosted_or_networked_runtime`) are still accepted
wherever a mode name is read and every one of them resolves to it. `checkpoint_created` and `turn_closed` are gateway finalisation events, not
runtime states. Strict non-allow blocking, role revoke governed, and capability
gate per action are enforced.

## Current Backend Capability Matrix

| Area | Current posture |
|---|---|
| Terminal and web dashboard | Implemented local clients; no direct authority |
| Local model profiles | Supported through governed provider contracts |
| Integrated executors | Governed per capability and decision mode |
| Approval resolution | Executes an approved file mutation through the governed relay (re-governed at execution time, checkpointed); metadata-only for every other capability |
| Remote/cloud and sensitive domains | Disabled and fail-closed |

Owner bootstrap creates a persisted principal and a human `runtime_gate_manager`.
The runtime state and capability gate state are durable. No `/sessions` command is
currently implemented; sessions: deferred; no `/sessions` command is currently
implemented. Session records are exposed through the documented
commands and local API.

See [implementation status](IMPLEMENTATION_STATUS.md) for the current capability
ledger and [security architecture](SECURITY_ARCHITECTURE.md) for trust boundaries.

Approval resolution executes an approved local file mutation through the governed relay and is metadata-only for every other capability. Strict non-allow blocking, role revoke governed, and capability gate per action are enforced. sessions: deferred; no `/sessions` command is currently implemented.
