# Graph Memory And Codemap Specification

Graph memory lets Raiker understand relationships between files, symbols, tasks, decisions, entities, tools, tests, dependencies, and architectural constraints.

The graph is not a replacement for grep, semantic search, or LSP. It complements them by making relationships queryable.

---

## Graph Goals

Raiker graph memory must support:

1. codebase entity extraction;
2. project architecture mapping;
3. symbol relationship queries;
4. documentation-to-code links;
5. decision-to-file links;
6. task-to-change links;
7. memory provenance;
8. context retrieval;
9. impact analysis;
10. stale graph detection.

---

## Graph Entity Types

| Entity | Examples |
|---|---|
| `file` | `raiker/tools/broker.py` |
| `directory` | `raiker/tools/` |
| `module` | `raiker.tools` |
| `class` | `ToolBroker` |
| `function` | `execute_action` |
| `method` | `PolicyEngine.evaluate` |
| `test` | `test_shell_requires_approval` |
| `contract` | `ToolAction` |
| `event_type` | `policy_decision` |
| `tool` | `read_file` |
| `policy_rule` | `shell_requires_approval` |
| `task` | `RAIKER-0401` |
| `decision` | `ADR-0001` |
| `memory_record` | `mem_01H...` |
| `dependency` | `pytest` |
| `plugin` | `com.example.plugin` |
| `channel` | `tui` |
| `model_profile` | `qwen-local` |

---

## Graph Relationship Types

| Relationship | Meaning |
|---|---|
| `contains` | directory contains file/symbol |
| `imports` | module imports module |
| `calls` | function calls function |
| `defines` | file defines symbol |
| `tests` | test covers symbol/behaviour |
| `implements` | code implements contract/task |
| `documents` | doc explains code/contract |
| `depends_on` | entity depends on entity |
| `emits_event` | code emits event type |
| `requires_policy` | tool/action requires policy |
| `uses_tool` | runtime/agent uses tool |
| `owned_by` | task/decision owner |
| `supersedes` | decision supersedes decision |
| `derived_from` | memory derived from source |
| `related_to` | general relationship |

---

## Graph Node Schema

```json
{
  "schema_version": "1.0",
  "node_id": "node_01H...",
  "type": "function",
  "name": "execute_action",
  "qualified_name": "raiker.tools.broker.ToolBroker.execute_action",
  "source": {
    "path": "raiker/tools/broker.py",
    "line_start": 42,
    "line_end": 118,
    "sha256": "..."
  },
  "metadata": {
    "language": "python",
    "visibility": "public"
  },
  "created_at": "2026-06-17T12:00:00Z",
  "updated_at": "2026-06-17T12:00:00Z"
}
```

---

## Graph Edge Schema

```json
{
  "schema_version": "1.0",
  "edge_id": "edge_01H...",
  "from_node_id": "node_func",
  "to_node_id": "node_policy",
  "relationship": "requires_policy",
  "confidence": 0.92,
  "provenance": {
    "extractor": "static_python_ast",
    "source_event_id": "evt_01H..."
  }
}
```

---

## Codemap Build Pipeline

```text
workspace scan
  -> ignore rules applied
  -> language detection
  -> parse files
  -> extract symbols
  -> extract imports/calls/tests
  -> link docs/contracts/tasks
  -> persist graph snapshot
  -> emit graph_index_created event
```

The graph builder must be incremental where possible.

---

## Graph Context Retrieval

When a task references code, Raiker should ask graph questions such as:

- What files implement this contract?
- What tests cover this function?
- What code emits this event?
- What files depend on this module?
- What docs explain this behaviour?
- What tasks or ADRs are related?
- What would be impacted by editing this file?

Graph results must be merged into the context bundle with provenance.

---

## Graph Query Tool

`graph_query` must be tool-brokered.

Example:

```json
{
  "tool_name": "graph_query",
  "arguments": {
    "query_type": "impact_analysis",
    "entity": "raiker.tools.broker.ToolBroker.execute_action",
    "max_results": 25
  }
}
```

Query types:

- `find_symbol`
- `find_tests`
- `impact_analysis`
- `dependency_path`
- `docs_for_symbol`
- `events_emitted_by_file`
- `contracts_implemented_by_file`
- `tasks_related_to_file`
- `memory_related_to_entity`

---

## Staleness Detection

Graph nodes/edges must track source file hashes. If files change, affected graph entries become stale until re-indexed.

Events:

- `graph_index_started`
- `graph_index_created`
- `graph_index_failed`
- `graph_node_stale`
- `graph_query_started`
- `graph_query_completed`

---

## Security Requirements

- Graph content may expose sensitive code structure.
- Graph export requires approval.
- Graph indexing must respect ignore rules and secret policies.
- Graph must not treat untrusted docs as instructions.
- Graph memory cannot override policy.

---

## Testing Requirements

Tests must prove:

- symbols are extracted from a small fixture;
- imports/calls are represented;
- tests link to functions;
- stale detection works when file hash changes;
- graph query is brokered and policy-reviewed;
- ignored files are not indexed;
- graph context includes provenance.

## Phase 3 Slice C/D governance update (local validation required)

Current runtime posture update: graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding now have real governed executors; broader graph query/planning automation, learned semantics, external sync, and no-executor extensions remain deferred/fail-closed.

Safety status for this slice:

- GitHub Actions remain paused due quota exhaustion; do not claim GitHub CI passed while paused.
- Local validation evidence remains mandatory under `docs/LOCAL_VALIDATION_GATE.md`.
- Plugin execution slices are integrated governed executors; broader plugin extensions remain deferred/fail-closed.
- Graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding are integrated governed executors; broader graph/memory extensions remain deferred/fail-closed.
- The reference external channel runtime, subagent/team executors, and local container executor are integrated and governed.
- Remote/cloud command execution remains no-executor/fail-closed.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.

## Phase 3 Slice E Graph Approval Preview

Graph/codemap approval previews wrap dry-run `GraphCodemapIndexPlan` output to show what a future indexer would need approval to process. They are not executable approvals.

Rules:

- `target_capability` is `graph_codemap_indexing`.
- `can_execute_now` is `false`.
- `execution_enabled` is `false`.
- `policy_decision` is `denied_or_preview_only`.
- `graph_runtime_indexing_disabled` is included in reasons.
- Unsafe graph plans, including symlink escapes or outside-workspace paths, produce denied high-risk previews.
- Preview creation writes no graph indexes and starts no background indexers, watchers, or daemons.

Full graph indexing remains disabled and full Phase 3 is not complete.

## Phase 3 Slice F — Approval Audit and Rollback Planning

Slice F adds preview-only approval audit and rollback planning contracts for future graph indexing and semantic memory writes. Full Phase 3 is not complete.

Safety invariants for this slice:

- Approval audit records do not execute actions.
- Rollback plans do not execute rollback.
- Legacy preview surfaces do not execute graph writes; the current graph indexing runtime is a separate governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic memory and vector embedding/search runtimes are separate governed real executors.
- Plugin slices, the reference external channel, subagent/team executors, local container runtime, and owner-configured SSH/Daytona command execution are governed real executors; other remote/cloud providers remain no-executor/fail-closed.
- GitHub Actions remain paused due quota exhaustion; local/cloud validation evidence is mandatory.
- CI must be re-enabled later when quota is available and must not be claimed as passed while Actions are paused.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

## Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Legacy lifecycle/preview surfaces do not write graph data directly; current graph indexing is a governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic/vector runtimes are governed real executors.
- Rollback execution remains disabled.
- Plugin slices, the reference external channel, subagent/team executors, local container runtime, and owner-configured SSH/Daytona command execution are governed real executors; other remote/cloud providers remain no-executor/fail-closed.
- GitHub Actions remain paused due quota/run-limit exhaustion; local/cloud validation evidence is mandatory and GitHub CI must be re-enabled later when quota is available.
