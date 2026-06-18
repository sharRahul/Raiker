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


## Phase 3 rollout slice B — workspace view/API foundation

Status: `implemented_verified` for the safe read-only view layer only. This slice fixes CI compatibility for Python 3.11, keeps Python 3.13 compatibility where possible, and adds deterministic workspace rendering for future terminal, desktop, web, and dashboard clients through the shared workspace inspection contract.

Implemented scope:

- `raiker/workspace/views.py` renders JSON-safe workspace, text/terminal, dashboard summary, client capability summary, and plugin plan summary views.
- `/workspace-view` renders a stable read-only terminal snapshot from `inspect_workspace(...)`.
- Acceptance tests prove equivalent read-only data for terminal, desktop, web, and dashboard clients and prove view rendering does not mutate tasks, approvals, memory candidates, plugin state, channel state, or execution gates.

Out of scope and still disabled: full desktop/web/dashboard runtime, web server, privileged UI path, plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution. Full Phase 3 is not complete.
