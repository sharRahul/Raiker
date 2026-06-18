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
