# Implementation status

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

## Canonical Backend Capability Statuses

| Status | Meaning |
|---|---|
| `implemented_verified` | Implemented and covered by repository validation |
| `implemented_policy_gated` | Has a real executor but remains governed per action |
| `implemented_approval_required` | Requires an explicit human approval path |
| `implemented_read_only` | Reads current state without a mutation |
| `metadata_only` | Records, previews, or reads state without execution |
| `readiness_only` | Reports blockers and availability without activation |
| `dry_run_only` | Produces a non-executing preview |
| `contract_only` | Defines an interface without an executable implementation |
| `test_only` | Reserved for offline test support |
| `disabled_deferred` | No usable executor; fails closed |

Approval resolution is `metadata_only` for every capability except an approved
local **file mutation** (`file_write_execution`, `patch_apply_execution`), which
is executed once through the governed approval execution relay — re-governed at
execution time and checkpointed so it stays reversible.
CLI durable memory mutation is `implemented_approval_required`.

Integrated real executors (including graph indexing, semantic/vector runtimes, plugin execution slices, channel runtime, container, scheduled routines, model-provider runtime, and local email/calendar/reminder stores) are `implemented_policy_gated`/governed per action; remote/cloud command execution and sensitive finance/investment/medical/pregnancy/CCTV/home-security/hardware domains remain `disabled_deferred` and fail closed.

Phase 4 memory MVP is implemented. The launchable interfaces are the local
terminal client and loopback web dashboard. Owner bootstrap creates the owner
principal, every request resolves an acting-principal, and a human
`runtime_gate_manager` governs capability changes and stopping or starting the
single agent runtime.

Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced. Disabled runtime flags remain false where no executor exists:
`plugin_execution_enabled`, `graph_indexing_enabled`,
`semantic_memory_writes_enabled`, `vector_writes_enabled`,
`embedding_creation_enabled`, `approval_execution_enabled`,
`approval_relay_runtime_enabled`, `cleanup_execution_enabled`,
`rollback_execution_enabled`, `external_channels_enabled`,
`notifications_enabled`, `remote_execution_enabled`,
`container_execution_enabled`, `cloud_execution_enabled`,
`process_execution_enabled`, `shell_execution_enabled`,
`network_execution_enabled`, and `runtime_execution_enabled`.

The dashboard's Build workspace is a client of these controls and adds no
authority of its own. Its Plan/Edit/Auto composer modes set the existing
per-capability decision modes (`deny`/`ask`/`auto`) on
`file_write_execution`, `patch_apply_execution`, `shell_execution`, and
`process_execution` — a human `runtime_gate_manager` operation, refused
otherwise — so the mode shown is the posture the runtime enforces. Repository
references are `implemented_read_only` bookkeeping: a local folder must resolve
inside the workspace or it fails closed, a GitHub `owner/repo` coordinate is
recorded without any network call, and GitHub content still reaches a turn only
through the brokered `github_read` tool under the `connector_github_runtime`
gate. Scheduled agents are ordinary tasks with a cadence; each cycle is one
discrete governed turn. See [the Build workspace](BUILD_WORKSPACE_SPEC.md).

See [feature coverage](FEATURE_COVERAGE_MATRIX.md) for a concise area-by-area
view and [open gaps](GAP_AND_TODO_ANALYSIS.md) for deferred work.

## Readiness compatibility ledger

Phase 3 is complete for the following metadata and readiness slices. Phase 4 remains blocked for autonomous expansion without a supported executor and governance path; the bounded Phase 4 memory MVP is implemented.

| Slice | Current meaning |
|---|---|
| Phase 3 Slice K | Semantic-memory readiness is metadata-only: `semantic_memory_readiness_metadata_only: True`; `semantic_memory_ready_for_writes: False`. |
| Slice L | Approval preview persistence is metadata-only; it records an inspectable preview and executes nothing. Its `approval_execution_enabled` / `approval_relay_runtime_enabled` flags scope to **this preview-persistence surface** (durable approval queues, workers, schedulers, watchers, daemons — all still deferred). They are not a statement about the Approvals inbox, where an approved file mutation is executed once through the governed relay. |
| Slice M | Storage cleanup reports readiness and produces cleanup previews. Cleanup execution remains governed and fail-closed where no executor is available. |
| Slice N | Plugin server startup readiness reports plugin capability and blockers; plugins do not become an authority bypass. |
| Slice O | External channels and notifications expose metadata readiness only; runtime dispatch events are introduced only with a governed executor. |
| Slice P | Remote, container, and cloud readiness records metadata only. These execution domains remain disabled and fail-closed. |

Strict non-allow blocking, role revoke governed, and capability gate per action are enforced. This document distinguishes metadata-only, dry-run-only, contract-only, readiness-only, implemented-read-only, and test-only surfaces from executable capabilities.
