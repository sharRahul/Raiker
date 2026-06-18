# Phase 3 Next Slice Selection Proposal

Status: `planning_only`

This proposal is a maintainer-facing recommendation for selecting the next named Phase 3 slice after PR #35. It does not define or implement Slice J, does not start Phase 4, and does not enable any runtime execution path.

## Current baseline after PR #35

- Current merged baseline includes PR #35 merge commit `6341d6547cbdb657ba12a8ad6b5cf84bcbaec5c7`.
- `docs/PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md` exists and states that Phase 3 remains incomplete, Phase 4 must not start as a substitute for Phase 3, and no named `Slice J` definition was found.
- `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md` exists and owns the Slice I lifecycle evidence/export/policy-simulation contract.
- `README.md` references the planning-only next-slice audit.
- No named `Slice J` implementation or Slice J spec is defined in this repository at the time of this proposal.

## Selection constraints

The next Phase 3 slice must be explicitly named by maintainers before implementation begins. Unless maintainers add a narrower, source-backed authorization, candidates must remain metadata-only, read-only, preview-only, simulation-only, or planning-only.

Phase 3 remains incomplete. Phase 4 must not start as a substitute for unfinished Phase 3 work.

## Candidate next slices

### Candidate 1 — Phase 3 Slice J: Lifecycle Readiness Decision Records

1. **Purpose:** Add metadata-only readiness decision records that summarize Slice G/H/I lifecycle evidence, retention, cleanup-preview, approval-handoff, and policy-simulation outputs into a maintainer-reviewable decision package.
2. **Why it follows Slice I:** Slice I already exports evidence bundles and policy simulations; the safest continuation is a planning/readiness layer that records whether a lifecycle area is still blocked, needs more policy, or is ready for a future separately authorized implementation slice.
3. **Source references:** `docs/PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md`, `docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md`, `docs/PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md`, `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`, `docs/PHASE_3_BUILD_PLAN.md`, `docs/EVENT_CATALOG.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`, and `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`.
4. **Type:** Metadata-only, read-only, planning-only, and simulation-adjacent. Runtime execution is not enabled.
5. **Required contracts/models:** A deterministic `StorageLifecycleReadinessDecision` or similarly named contract with redacted canonical JSON, linked evidence bundle IDs, linked simulation IDs, target capability, decision state (`blocked`, `needs_policy`, `ready_for_future_slice_review`), maintainer notes summary, and disabled execution flags.
6. **Required registry/service changes:** In-memory and SQLite-backed metadata create/list/get helpers only; deterministic sorting; not-found behavior; no workers, queues, schedulers, or jobs.
7. **Required CLI/API surfaces:** Read-only commands such as `/storage-lifecycle-readiness`, `/storage-lifecycle-readiness --summary`, `/storage-lifecycle-readiness --json`, and `/storage-lifecycle-readiness <decision_id>` if maintainers approve that surface.
8. **Required SQLite metadata-only tables:** At most `phase3_storage_lifecycle_readiness_decisions` and `phase3_storage_lifecycle_readiness_events`. These must be idempotent metadata tables only.
9. **Required workspace inspection/view fields:** Counts, latest decision IDs, target capability counts, decision-state counts, and explicit `execution_enabled=false` / `runtime_writes_enabled=false` fields.
10. **Required docs/catalog/event catalog updates:** Update the Phase 3 build plan, storage lifecycle specs, Slice I references, command spec, storage spec, event catalog, implementation status, validation gate, verification plan, acceptance-test matrix, tool/plugin catalog, and README status links.
11. **Required tests:** Deterministic IDs, redaction before ID generation and serialization, stable list ordering, CLI usage and filters, JSON safety, allowed SQLite table presence, forbidden runtime table absence, workspace summary fields, and disabled-runtime flags.
12. **Explicit forbidden runtime boundaries:** No cleanup execution, graph/codemap indexing, graph writes, semantic/vector writes, embedding creation/storage, rollback execution, plugin execution, server startup, monitors, external channels, approval relay, subagents, teams, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, share links, schedulers, workers, queues, or runtime jobs.
13. **Risks:** Naming a state such as `ready_for_future_slice_review` could be misread as approval to execute. Mitigate with explicit field names, denied execution flags, documentation, and tests that prove no runtime path is reachable.
14. **Acceptance criteria:** Maintainers approve the slice name and states; all records are metadata-only; no runtime-capability state transitions reach execution; docs and catalogs agree; validation commands pass; tests prove forbidden runtime boundaries remain disabled.

### Candidate 2 — Phase 3 Slice J: Durable Approval-Preview Persistence Governance

1. **Purpose:** Define governance and metadata persistence for approval-preview records without adding approval relay or execution.
2. **Why it follows Slice I:** Slice E/F introduced approval previews, audits, and rollback planning; Slice G/H/I added lifecycle evidence and export support that could justify durable preview governance as a narrow planning continuation.
3. **Source references:** `docs/PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md`, `docs/PHASE_3_BUILD_PLAN.md`, `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/EVENT_CATALOG.md`, `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`, and approval-preview tests.
4. **Type:** Metadata-only and preview-only. Not runtime-enabled.
5. **Required contracts/models:** Durable approval-preview metadata envelope, retention metadata, redacted summary, linked audit/rollback/lifecycle IDs, and disabled approval-relay flags.
6. **Required registry/service changes:** Metadata persistence/list/get only; no resolver, relay, action executor, or queue.
7. **Required CLI/API surfaces:** `/approval-previews --persisted`, `/approval-preview <id> --json`, or equivalent if maintainers approve.
8. **Required SQLite metadata-only tables:** A narrow approval-preview metadata table only if maintainers authorize it; no approval relay or execution table.
9. **Required workspace inspection/view fields:** Persisted preview counts, latest preview ID, and `approval_relay_enabled=false`.
10. **Required docs/catalog/event catalog updates:** Approval-preview, approval-audit, command, storage, event, implementation-status, and tool-catalog updates.
11. **Required tests:** Persistence redaction, deterministic IDs, read-only lookup, CLI rendering, allowed/forbidden tables, and disabled relay/execution assertions.
12. **Explicit forbidden runtime boundaries:** No approval relay, action execution, graph indexing, semantic writes, rollback execution, plugin execution, channels, subagents, or remote/container/cloud execution.
13. **Risks:** Higher confusion risk because approval records are close to executable approval semantics.
14. **Acceptance criteria:** Persisted previews remain inert metadata; existing approval resolution semantics are not expanded; all disabled-runtime tests pass.

### Candidate 3 — Phase 3 Slice J: Graph/Codemap Activation Readiness Audit

1. **Purpose:** Create a readiness audit for future graph/codemap indexing without starting an indexer or writing graph records.
2. **Why it follows Slice I:** Slice I evidence can be used to audit whether graph lifecycle and rollback evidence exists before any future indexing implementation.
3. **Source references:** `docs/PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md`, `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/PHASE_3_BUILD_PLAN.md`, `docs/EVENT_CATALOG.md`, and graph governance tests.
4. **Type:** Read-only, planning-only, and readiness-only. Not runtime-enabled.
5. **Required contracts/models:** Graph readiness audit record with dry-run plan ID, lifecycle evidence links, blocked reasons, and disabled indexing/write flags.
6. **Required registry/service changes:** Metadata-only audit store/list/get helpers.
7. **Required CLI/API surfaces:** `/graph-readiness-audit`, `/graph-readiness-audit --summary`, and JSON rendering if approved.
8. **Required SQLite metadata-only tables:** Optional graph readiness audit metadata table; no graph node/edge tables.
9. **Required workspace inspection/view fields:** Graph readiness count, latest audit ID, and explicit indexing/write disabled fields.
10. **Required docs/catalog/event catalog updates:** Graph/codemap spec, command spec, storage spec, event catalog, build plan, validation docs, and tool catalog.
11. **Required tests:** Dry-run-only behavior, no graph writes, no indexer startup, deterministic audit IDs, and disabled runtime assertions.
12. **Explicit forbidden runtime boundaries:** No graph/codemap indexing jobs, graph node/edge writes, background indexers, watchers, daemons, schedulers, queues, or workers.
13. **Risks:** More likely than Candidate 1 to be mistaken for permission to implement indexing.
14. **Acceptance criteria:** Every audit result states `can_index_now=false`; no graph storage or runtime capability is added.

### Candidate 4 — Phase 3 Slice J: Semantic Memory Write Readiness Audit

1. **Purpose:** Audit whether semantic memory write prerequisites are documented and evidenced while keeping vector and embedding paths disabled.
2. **Why it follows Slice I:** Slice I evidence can inform future memory write readiness, while Slice D remains review-queue-only.
3. **Source references:** `docs/PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md`, `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/API_AND_CONTRACT_SCHEMAS.md`, and semantic-memory tests.
4. **Type:** Read-only, planning-only, and readiness-only. Not runtime-enabled.
5. **Required contracts/models:** Semantic readiness audit record with candidate counts, policy gaps, lifecycle evidence links, and disabled vector/embedding/write flags.
6. **Required registry/service changes:** Metadata-only audit list/get helpers.
7. **Required CLI/API surfaces:** `/memory-readiness-audit`, `/memory-readiness-audit --summary`, and JSON rendering if approved.
8. **Required SQLite metadata-only tables:** Optional readiness audit metadata table; no vector, embedding, or durable semantic-memory write table.
9. **Required workspace inspection/view fields:** Memory readiness count, latest audit ID, and explicit write/vector/embedding disabled fields.
10. **Required docs/catalog/event catalog updates:** Memory governance docs, command spec, storage spec, event catalog, build plan, validation docs, and tool catalog.
11. **Required tests:** No vector writes, no embeddings, deterministic audit records, redaction, CLI rendering, and disabled runtime assertions.
12. **Explicit forbidden runtime boundaries:** No semantic writes, vector writes, embeddings, vector indexes, embedding storage, or background workers.
13. **Risks:** Any wording around readiness can be confused with write authorization.
14. **Acceptance criteria:** Audit output states writes remain disabled and all tests prove no vector/embedding path exists.

### Candidate 5 — Phase 3 Slice J: Workspace/Client Parity Gap Audit

1. **Purpose:** Audit terminal, desktop, web, dashboard, IDE, and mobile documentation for read-only workspace inspection/view parity gaps without building clients.
2. **Why it follows Slice I:** Slice I added workspace summary fields for evidence/simulation counts, so a parity audit can ensure future clients expose them consistently.
3. **Source references:** `docs/PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md`, `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/IMPLEMENTATION_STATUS.md`, and workspace view code/tests.
4. **Type:** Documentation/planning-only or read-only metadata if maintainers authorize a tiny report contract. Not runtime-enabled.
5. **Required contracts/models:** Optional parity gap report with client, field, status, missing-doc/code reference, and disabled runtime fields.
6. **Required registry/service changes:** Prefer none; if implemented, read-only generated report only.
7. **Required CLI/API surfaces:** Prefer none; optional `/workspace-parity-audit --summary` if maintainers authorize.
8. **Required SQLite metadata-only tables:** None recommended.
9. **Required workspace inspection/view fields:** None required unless a report contract is implemented.
10. **Required docs/catalog/event catalog updates:** UI/UX, command spec, implementation status, README, and validation docs.
11. **Required tests:** Documentation-link validation or snapshot tests if a report is implemented.
12. **Explicit forbidden runtime boundaries:** No client servers, external channels, push notifications, share links, plugin startup, or execution.
13. **Risks:** Safe but less directly connected to lifecycle evidence and may not advance core Phase 3 readiness as much as Candidate 1.
14. **Acceptance criteria:** Parity gaps are documented and no client/runtime surface is activated.

## Ranking by implementation safety

- **Recommended next candidate:** Phase 3 Slice J: Lifecycle Readiness Decision Records.
- **Alternative candidates:** Durable Approval-Preview Persistence Governance; Workspace/Client Parity Gap Audit; Graph/Codemap Activation Readiness Audit; Semantic Memory Write Readiness Audit.
- **Candidates rejected for now:** Runtime graph/codemap indexing, semantic/vector memory writes, cleanup execution, rollback execution, plugin/MCP/LSP server startup readiness that includes startup behavior, external-channel activation, subagents/teams, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, share links, schedulers, workers, queues, and runtime job systems.
- **Why rejected:** Existing docs do not authorize these runtime activations; Phase 3 remains incomplete; Phase 4 must not start; and these capabilities would breach the disabled-runtime boundaries preserved by Slice G/H/I and the next-slice definition audit.

## Why the recommended slice is safest

Lifecycle Readiness Decision Records are the safest next step because they continue directly from Slice G/H/I metadata, retention, cleanup-preview, handoff, evidence, export, and simulation work without selecting a runtime target such as graph indexing or semantic writes. The slice would produce maintainer-reviewable decision metadata, not execution authority.

## Scope boundaries

Allowed scope for the recommended slice:

- deterministic metadata-only decision records;
- read-only/list/get/render behavior;
- redacted summaries and canonical JSON IDs;
- links to existing lifecycle, retention, cleanup-preview, approval-handoff, evidence, and policy-simulation records;
- CLI/API/workspace inspection fields only if they remain read-only;
- SQLite metadata-only tables only if maintainers approve them;
- docs, catalogs, events, and tests that preserve disabled runtime boundaries.

## Forbidden runtime boundaries

The next slice must not enable cleanup execution, graph/codemap indexing, graph writes, semantic memory writes, vector writes, embedding writes, rollback execution, plugin execution, MCP/LSP/plugin server startup, monitor daemons, external channels, approval relay, subagents, teams, remote execution, container execution, cloud execution, hosted routines, marketplace installs, push notifications, share links, schedulers, workers, queues, or runtime job systems.

## Required maintainer decision

Before implementation starts, maintainers must decide:

1. whether the next named slice is `Phase 3 Slice J: Lifecycle Readiness Decision Records` or another candidate;
2. whether the slice is documentation-only or includes metadata-only contracts, registry/service helpers, CLI/API surfaces, workspace fields, and SQLite metadata tables;
3. the exact allowed decision states and whether any state may use the word `ready`;
4. the exact SQLite metadata-only table names, if any;
5. the required validation and acceptance-test set.

## Acceptance criteria for starting implementation

Implementation may start only after maintainers approve a named slice definition that includes:

- source documents authorizing the scope;
- explicit type classification as metadata-only/read-only/preview-only/simulation-only/planning-only;
- required contracts/models;
- allowed registry/service, CLI/API, SQLite, and workspace inspection changes;
- event/catalog/doc updates;
- tests and validation commands;
- forbidden runtime boundaries;
- statement that Phase 3 remains incomplete;
- statement that Phase 4 must not start.
