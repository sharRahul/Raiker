# Phase 3 Build Plan — Local Rich Workspace and Extensibility Foundations

Phase 3 expands Raiker's local workspace clients and extension planning while preserving equal primary interfaces. Runtime execution stays gated until contracts, policy, storage, events, and tests are present.

## Dependency Graph

```text
RAIKER-3001 phase gates and capability registry
  -> RAIKER-3101 desktop/web/dashboard contract parity
  -> RAIKER-3201 plugin manifest validation boundary
  -> RAIKER-3301 graph/codemap planning schema
  -> RAIKER-3401 semantic memory planning schema
  -> RAIKER-3501 local rich workspace UX acceptance tests
```

## Tasks

| Task ID | Scope | Contracts/events/storage | Policy | Tests | Acceptance criteria |
|---|---|---|---|---|---|
| RAIKER-3001 | Disabled/listable Phase 3 capability gates | Capability names only | Execution denied | Gate tests | Phase 3 capabilities are discoverable and cannot execute. |
| RAIKER-3101 | Desktop, web, dashboard action parity plan | UIActionEnvelope reuse | No interface bypass | Contract parity tests | No client has privileged runtime access. |
| RAIKER-3201 | Plugin manifest validation boundary | Manifest validation result events | No plugin code execution | Invalid/valid manifest tests | Manifests can be checked without executing plugin code. |
| RAIKER-3301 | Graph/codemap planning | Planned graph node/edge schemas | No runtime indexing | Schema tests | Codemap indexing remains disabled until policy is complete. |
| RAIKER-3401 | Semantic memory planning | Memory candidate/read-only status | No durable memory writes | Memory gate tests | Candidates can be reviewed; no embedding/vector writes happen. |
| RAIKER-3501 | Rich workspace UX validation | Shared gateway contracts | Equal-interface invariant | Integration tests | Desktop/web/dashboard foundations use shared boundaries. |

## Implemented safe foundation in this pass

- `raiker.phase_gates` lists Phase 3 capabilities as disabled and raises before execution.
- Tests prove representative Phase 3 capabilities are listable and non-executable.

## Gated until later Phase 3 work

Desktop UI, web UI, dashboard runtime, plugin execution, graph/codemap indexing, and semantic memory writes remain disabled until their task-specific policy, storage, events, and acceptance tests exist.

## 2026-06-18 implementation update

The current implementation completes the Phase 3 safe foundation layer without activating runtime features prematurely:

- plugin manifests can be validated for required fields and permission-prefix safety without importing or executing plugin code;
- graph/codemap node and edge plans can be inspected and validated for dangling edges while runtime indexing remains disabled;
- semantic memory status is exposed as disabled-by-default, with candidate counts available for workspace inspection;
- `/capabilities` and `/semantic-memory` provide terminal inspection parity through the existing CLI command surface.

These foundations intentionally stop before desktop/web/mobile runtimes, plugin execution, graph indexing, embeddings, or durable semantic writes. Those features still require task-specific policy, storage, event, lifecycle, and acceptance-test work before activation.

## Phase 3 rollout slice A — implemented verified

This slice starts the real Phase 3 rollout without marking full Phase 3 complete.

Implemented:

- RAIKER-3101 now has a shared read-only workspace inspection service for terminal, desktop, web, and dashboard clients. The service returns runtime status, events, checkpoints, tasks, approvals, model profiles, channel connectors, capability gates, semantic-memory status, execution profiles, and plugin registration plan summaries through one contract path.
- RAIKER-3201 now has plugin policy evaluation and registration planning after manifest validation. Plans can be `planned`, `pending_approval`, or `denied`, but `execution_enabled` remains `false`.
- Phase 3 capability state tracking now represents disabled, planned, readiness gates, read-only enablement, policy-gated enablement, and runtime enablement. Runtime enablement cannot be reached from disabled/planned without readiness gates.
- Read-only terminal inspection commands were added for `/workspace`, `/clients`, `/plugins`, and `/plugin-plan <manifest_path>`.

Still disabled:

- plugin code execution;
- graph/codemap runtime indexing;
- semantic/vector memory writes;
- external channel activation;
- subagents and multi-agent teams;
- remote/container execution;
- desktop app packaging and web/dashboard server runtime.

Evidence:

- `tests/test_phase_3_capability_states.py`
- `tests/test_phase_3_workspace_inspection.py`
- `tests/test_phase_3_equal_workspace_clients.py`
- `tests/test_phase_3_plugin_policy.py`
- `tests/test_phase_3_terminal_commands.py`

## Phase 3 rollout slice B — RAIKER-3501 read-only rich workspace view/API foundation

Slice B continues Phase 3 without marking full Phase 3 complete. It adds a read-only view layer over the existing shared workspace inspection contract for future terminal, desktop, web, and dashboard clients.

Implemented scope:

- deterministic text workspace summary;
- JSON-safe workspace summary;
- dashboard summary;
- client capability summary;
- plugin plan summary;
- `/workspace-view` CLI command for deterministic read-only terminal inspection.

Safety boundaries:

- views consume the shared inspection output instead of bypassing policy, storage, or event boundaries;
- views do not execute tools;
- views do not create approvals;
- views do not call models;
- views do not write semantic/vector memory;
- views do not execute plugin code;
- views do not activate external channels;
- views do not start remote/container execution;
- views redact secret-like keys before returning summaries.

GitHub Actions are temporarily paused only due quota exhaustion. Local validation evidence from `docs/LOCAL_VALIDATION_GATE.md` is required while Actions are paused. Unsafe runtime capabilities remain disabled.

## Phase 3 Slice C/D governance update (local validation required)

Full Phase 3 is not complete. Slice C adds graph/codemap governance and dry-run planning only: graph/codemap runtime indexing remains disabled, no background indexer is started, and no durable graph nodes or edges are written. Slice D adds semantic memory governance and a review queue only: semantic/vector memory writes remain disabled, no embeddings are created, and no vector records are written.

Safety status for this slice:

- GitHub Actions remain paused due quota exhaustion; do not claim GitHub CI passed while paused.
- Local validation evidence remains mandatory under `docs/LOCAL_VALIDATION_GATE.md`.
- Plugin execution remains disabled.
- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- External channels remain disabled.
- Subagents and multi-agent teams remain disabled.
- Remote/container execution remains disabled.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.

## Phase 3 rollout slice E — policy-gated approval preview UX

Slice E continues the graph and semantic-memory governance rollout by adding approval-preview contracts and CLI/workspace affordances before any runtime write path can be activated.

Implemented scope:

- `ApprovalPreview` contract for preview-only approval surfaces.
- Graph indexing approval previews over dry-run `GraphCodemapIndexPlan` values.
- Semantic memory write approval previews over `MemoryReviewItem` values.
- In-memory/non-persistent preview helpers and deterministic rendering.
- CLI commands: `/approval-previews`, `/graph-approval-preview`, `/memory-approval-preview [--summary]`, and `/approval-preview <preview_id>`.
- Workspace inspection/view `approval_preview_summary`.

Still disabled:

- graph/codemap runtime indexing;
- semantic/vector memory writes;
- embeddings and vector creation;
- plugin execution;
- external channel activation;
- subagents, multi-agent teams, remote execution, and container execution.

Full Phase 3 is not complete. GitHub Actions remain paused due quota exhaustion, so local validation is mandatory until full CI is re-enabled when quota is available.

## Phase 3 Slice F — Approval Audit and Rollback Planning

Slice F adds preview-only approval audit and rollback planning contracts for future graph indexing and semantic memory writes. Full Phase 3 is not complete.

Safety invariants for this slice:

- Approval audit records do not execute actions.
- Rollback plans do not execute rollback.
- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled; no embeddings or vectors are created.
- Plugin execution, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.
- GitHub Actions remain paused due quota exhaustion; local/cloud validation evidence is mandatory.
- CI must be re-enabled later when quota is available and must not be claimed as passed while Actions are paused.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

## Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Graph indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- Rollback execution remains disabled.
- Plugin execution, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.
- GitHub Actions remain paused due quota/run-limit exhaustion; local/cloud validation evidence is mandatory and GitHub CI must be re-enabled later when quota is available.

## Phase 3 Slice H lifecycle retention update

Slice H adds metadata-only lifecycle retention policies, cleanup previews, expiry/supersede counts, and approval-handoff planning. The read-only commands are `/storage-lifecycle-retention`, `/storage-lifecycle-retention --summary`, `/storage-lifecycle-cleanup-preview`, `/storage-lifecycle-cleanup-preview --summary`, `/storage-lifecycle-handoff`, and `/storage-lifecycle-handoff --summary`. Slice H does not execute cleanup, graph/codemap indexing, semantic/vector memory writes, embeddings, rollback, plugins, channels, subagents, or remote/container/cloud execution.
