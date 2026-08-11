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

Approval resolution is `metadata_only` except for approved local file mutations
(`file_write_execution`, `patch_apply_execution`) and configured SSH/Daytona
commands (`remote_execution_cap`, `cloud_execution_cap`). Those bounded actions
execute once through the governed relay and are re-governed at execution time;
file mutations are additionally checkpointed so they stay reversible.
Approval remains metadata-only for every other capability.
CLI durable memory mutation is `implemented_approval_required`.

Per-turn machine identity is `implemented_verified`. Every ordinary, resumed,
scheduled, plugin-relay, CLI-agentic, and child-agent tool call reaches the
broker with a short-lived Ed25519-signed identity. Verification precedes policy,
credential resolution, approvals, hooks, and execution. Owner resource scope is
carried separately from the machine actor; the API and dashboard expose the
literal event actor, contextual turn identity, machine proposer, and human
authorizer without exposing bearer material. Terminal and exceptional paths
deactivate their identities; a parked approval keeps its identity active until
resume. Approval rows snapshot the verified key and validity metadata so later
key rotation cannot rewrite historical attribution.

Daytona execution additionally reserves cumulative owner/profile budget in an
append-only ledger before launch. Provider actuals reconcile reservations when
available; an unavailable billing adapter is explicit and retains the estimate.
Scheduled task turns carry the same validated attachments as Chat and Build.

Integrated real executors (including graph indexing, semantic/vector runtimes,
plugin slices, channels, container, scheduled routines, model providers,
SSH/Daytona command execution, and local email/calendar/reminder stores) are
governed per action. Sensitive finance/investment/medical/pregnancy/CCTV/
home-security/hardware domains remain `disabled_deferred` and fail closed.

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
`cloud_execution_enabled`,
`process_execution_enabled`, `shell_execution_enabled`,
`network_execution_enabled`, and `runtime_execution_enabled`.

`container_execution_enabled` is no longer a fixed false compatibility flag.
It is derived from the owner account's container gate plus a valid persisted
profile whose Docker/Podman runtime and operator-allowlisted image are available.
Profiled safe filesystem/search tools execute through the container bridge with
a read-only repository and one action-scoped writable output directory; an
unavailable profile never falls back to native host execution.

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
| Slice P | The historical Phase 3 readiness record remains metadata-only. Current SSH, Daytona, and bounded container profiles have real executors and stay unavailable until an owner configures and selects one; other remote/cloud types remain fail-closed. |

Strict non-allow blocking, role revoke governed, and capability gate per action are enforced. This document distinguishes metadata-only, dry-run-only, contract-only, readiness-only, implemented-read-only, and test-only surfaces from executable capabilities.


## Universal model readiness and acquisition

Universal model readiness is `implemented_verified`: a fresh selection grants
no send authority until exact, fresh evidence exists, and the shared gate is
used by Workbench, Chat, Build, Tasks, and Schedule. Approved-root GGUF indexing,
managed llama.cpp deployment, Ollama pulls, and immutable Hugging Face GGUF
downloads are implemented. Optional Safetensors conversion is
`implemented_policy_gated` by explicit owner confirmation and the isolated
container boundary.

The gate judges the resolved chain — the selected model followed by the owner's
fallback sequence — and an exhausted account is its own state
(`quota_exhausted`), separate from an unreachable provider and a rejected
credential. The advisor model carries its own readiness observation and chip
(FIXED-158), and the observation window is an owner setting — 1 to 120 minutes,
five by default — re-confirmed opportunistically in the background while a work
surface is open, with the invalidation hooks still authoritative over the timer
(FIXED-169).
