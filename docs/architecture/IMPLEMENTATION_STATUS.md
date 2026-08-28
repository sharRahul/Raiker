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

Approval resolution executes approved local file mutations, and eleven other
capabilities besides. The complete set is `EXECUTABLE_ON_APPROVAL`
(`raiker/approvals/execution.py`): local file
mutations (`file_write_execution`, `patch_apply_execution`), bounded local
`shell` commands (`shell_execution`), the git write path
(`git_write_execution`), the push (`git_push_execution`), a GitHub write
(`connector_github_runtime`), durable memory writes and forgets
(`memory_write_execution`, `memory_forget_execution`), the two local planning
rows (`task_management_runtime`, `project_assignment_runtime`), and
owner-selected SSH and Daytona commands (`remote_execution_cap`,
`cloud_execution_cap`). Each is relayed once and re-governed at execution time
against its own gate, the relay's `approval_execution_relay` gate, policy and
posture; disabling either gate returns those approvals to metadata-only.

`process` and `network` are **not** relayed: an approved `process` or `network`
action records the decision and executes nothing. Shell execution and
standing-grant `run_command` converge on the same durable `CommandService`; the
runtime stores the authority identity and selected environment, redacts output
before persistence, and requires an immutable receipt for every terminal state.
File mutations are additionally checkpointed so they stay reversible. SSH and
Daytona execute only through an owner-configured, owner-selected profile with a
pinned host key and a cumulative cost ceiling; without one they fail closed, and
a profile record alone is not enough. Approval resolution remains metadata-only
for every other capability.
CLI durable memory mutation is `implemented_approval_required`.

**Checkpoint restore is a known gap.** `CheckpointRestoreExecutor`
(`raiker/runtime/executors/tier1_checkpoint.py`) is implemented, registered and
tested, and it captures its own pre-image so a restore is itself reversible —
but **no route, terminal command or model tool proposes a restore**. The CLI's
`/checkpoints restore` and the web Checkpoints view both compute a *preflight*
and perform nothing. Capture is automatic and complete; rewind is not reachable
by an owner. Tracked in
[Reference platform compatibility §5](REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort).

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
plugin slices, channels, container read tools, governed local commands,
scheduled routines, model providers, and local email/calendar/reminder stores) are
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

**The MCP client negotiates protocol revision `2026-07-28`, and implements a
subset of it.** `MCP_PROTOCOL_VERSION` (`raiker/runtime/executors/mcp.py`) offers
the [current revision](https://modelcontextprotocol.io/specification/versioning)
and accepts `2025-06-18`, `2025-03-26` and `2024-11-05` when a server answers
with one, refusing any revision Raiker does not implement rather than continuing
on a framing it cannot trust; **Extensions → MCP** states the revision each
server negotiated. The bounded session — `initialize`, `tools/list`,
`tools/call` — is `implemented_policy_gated`. What the specification added since
`2024-11-05` remains **not implemented**: streamable-HTTP session semantics,
structured tool output, resource links, elicitation, the mandatory
`server/discover` RPC, and MCP Apps. The `http` transport Raiker does offer is
its own bounded client, not the spec's streamable transport.

**There is exactly one implementation of "reach the network".** The model's
`web_fetch` and `web_search` tools go through `WebAccessService`
(`raiker/runtime/web_access.py`), which is where the blocklist, the address
guard, per-hop redirect re-governance and address pinning live — and the
capability-level `WebFetchExecutor` (`raiker/runtime/executors/tier2_web.py`)
now delegates to that same service. `NetworkExecutor`, the `network_execution`
capability and `sandbox.fetch_url` — whose only control was a hard-coded
four-host netloc glob — were deleted, so no registered executor reaches the
network with a weaker guard than the one an owner is told about.

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
| Slice O | The historical Phase 3 readiness flag `external_channels_enabled` stays `False`; it scopes that readiness record, not the channel surface. Channels have governed outbound delivery plus inbound owner-secret authentication, sender allowlisting, a 60-per-minute per-sender bound, and owner-stored `record_only`, `new_turn`, tool-free `side_question`, or target-bound `interrupt` routing. Approval response is separately disabled, exact, single-use, owner-bound, and refuses critical or connector-write approvals (FIXED-298). |
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
