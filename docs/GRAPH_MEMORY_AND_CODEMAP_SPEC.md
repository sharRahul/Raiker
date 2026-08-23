# Graph Memory And Codemap Specification

Graph memory lets Raiker understand relationships between files, symbols, tasks, decisions, entities, tools, tests, dependencies, and architectural constraints.

The graph is not a replacement for grep, semantic search, or LSP. It complements them by making relationships queryable.

## What is implemented today

This specification describes two things that have since been built to different
depths, and the difference matters when reading it.

**The codemap is shipped** (GAP-BUILD B9 / FIXED-113). `raiker/graph/codemap.py`
scans one repository and records files, symbols and `imports` edges;
`raiker/graph/codemap_service.py` governs it under the `code_map_indexing`
capability; the rows live in `code_map_files`, `code_map_symbols`,
`code_map_edges` and `code_map_indexes`. It is built on repository connect, on
selecting a never-indexed repository, and on the owner's **Rebuild index**
control, and it is refreshed incrementally for the paths an approved write
touched. The model reaches it through `code_map_search`, and the turn bundle
carries the ranked slices as untrusted context. It emits `code_map_indexed` and
`code_map_refreshed` rather than the `graph_index_created` named below.

**The durable governed graph store is not.** The node/edge schema, the entity and
relationship taxonomies, provenance, approval previews, rollback plans and
lifecycle retention below describe the Phase-3 subsystem behind the separate
`graph_codemap_indexing` capability, which remains a dry-run planner
(`raiker/graph/planner.py`). The codemap deliberately does **not** claim that
name: it is a derived cache that can be deleted and rebuilt, not a governed
record store, and one capability must not mean both.

The codemap implements a subset of what follows — `file`, `directory`, `module`,
`class`, `function`, `method` and `component` entities, and `contains`, `defines`
and `imports` relationships. `calls`, `tests`, `implements`, `documents`,
`emits_event`, `requires_policy`, `uses_tool`, `owned_by`, `supersedes` and
`derived_from` are still specification.

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

- GitHub Actions **run on every pull request and push to `main`** (`.github/workflows/`); the claim that they were paused for quota was true in an earlier phase and is not true now. See [`VERIFICATION_PLAN.md`](VERIFICATION_PLAN.md).
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

### Additional Improvements Needed

Here are concrete structural, technical, and governance improvements for the Raiker Graph Memory and Codemap Specification.

## Architectural Edge Cases

* Missing Node Deletion Logic: Staleness detection covers modification but lacks explicit removal logic for deleted files or dead code. Add a purge_stale_nodes sub-pipeline step.
* Lack of Graph Version Partitioning: Changes to schemas or AST extractors will break existing database entries. Introduce a migration strategy or strict data-store namespacing for schema_version mismatches.
* Unbounded Memory Overhead: Complex codebases create millions of fine-grained symbol dependencies (calls, contains). Enforce strict limits on maximum nested call-graph depths stored per function.

## Schema Improvements

* Missing Error and Truncation Metadata: The source object inside the node schema assumes flawless parsing. Add optional parsing_error: string and is_truncated: boolean flags for huge or partially corrupted files.
* Missing Edge Weighting: The current schema uses generic confidence scores. Add a frequency metric for calls relations to distinguish rare error handling branches from critical path hot loops.

## Governance and Security Tightening

* Ambiguous "Dry-Run" Validation: Phases 3 C through G reference dry-runs that report failure blocks (can_index: false) alongside active real executors. Explicitly document the runtime interaction matrix detailing exactly where real executors override legacy surfaces.
* Data Leaks via Metadata: Structural graphs can reconstruct patent-sensitive application workflows via symbol names even without full code visibility. Mandate local data hashing or pseudonymization configurations for exportable graphs.

Here are additional technical and functional gaps in the current specification that should be addressed before finalizing the implementation plan.
## Core Graph Mechanics & Multi-Language Complexity

* Polyglot Cross-Language Boundaries: Codebases often cross language barriers (e.g., Python calling a Rust extension, or TypeScript calling a Go microservice). The pipeline lacks cross-language linkers, which will break dependency mapping across multi-language repositories.
* Lack of Multi-Reference Resolution: The defines and contains relationships assume static assignments. They do not handle dynamic runtime mutations, conditional imports, or multiple definitions found in polymorphism, inheritance, and interface overloading.
* Implicit Graph Traversal Limits: Recursive queries like impact_analysis or dependency_path are prone to infinite cycles or severe performance degradation on large codebases. The spec needs to define maximum step limits and circular dependency protection loops.

## Context Optimization & LLM Integration

* Token Window Overflow Controls: The graph context retrieval process states that results must be merged into the context bundle. It does not provide any ranking or token-trimming mechanism when the extracted subgraph exceeds the LLM's prompt window limits.
* Graph-to-Text Serialisation Format: The spec does not dictate how the retrieved graph data turns into prompt context. Stating whether the agent reads raw JSON, a Markdown tree, or Cypher queries is critical for predictable LLM reasoning.

## Phase 3 Safety & State Machine Gaps

* Race Conditions During Indexing: Since incremental builds are planned, changes made to files during an active scan will corrupt the graph state. The spec requires a file-locking or snapshot-isolation strategy during pipeline executions.
* Vague Rollback Mechanics: Phase 3 Slice F mentions preview-only rollback planning contracts but omits concrete execution rules. It lacks clarity on how the graph reverts to a healthy snapshot if an incremental index run fails mid-way.

If you want to dive deeper, let me know if we should:

* Outline the cross-language mapping logic
* Create the token-window truncation rules for context injection
* Detail the state machine for transaction safety during indexing

To ensure Raiker can scale its graph memory efficiently over a 30-100 year horizon without breaking down or slowing down, we need to optimize how relationships are stored, grouped, and pruned. A direct graph of millions of fine-grained edges (e.g., every single function call) will eventually cause severe performance degradation and hit context-window bottlenecks.
Here is how we can refactor the relationships and communication strategy for multi-year long-term retention:

## 1. Multi-Tier Memory Decay (Temporal Tiering)
Not all relationships retain equal value over a decade. Implement a three-tiered retention strategy based on age and access frequency:

* Hot Tier (Epimemory): Keeps granular, short-lived edges (calls, extracts, tasks) for active development (0–90 days).
* Warm Tier (Semantic Memory): Collapses old granular edges into architectural generalizations (module_depends_on, implements_contract) after 90 days.
* Cold Tier (Core History/ADRs): Archives high-level historical relationships (supersedes, decision_to_module, architectural_intent) permanently. This ensures 10-year retention of why things were done, without cluttering the graph with how a function was structured in 2026.

## 2. Introduce Structural Edge Aggregation
Instead of storing thousands of individual calls edges between functions in two separate modules, the graph builder should dynamically roll them up into an aggregated weight metric:

* Aggregated Relationship: { "from": "module_a", "to": "module_b", "relationship": "depends_on", "weight": 245, "first_seen": "2026-01-01", "last_active": "2036-01-01" }
* Benefit: Reduces communication and traversal latency across subgraphs by up to 90%, allowing the agent to quickly scan architectural pathways before dipping into granular nodes.

## 3. Add Contextual Clustering and "Anchors"
To prevent historical data fragmentation over a decade, introduce a new relationship type called anchored_to.

* Concept: Connect long-term entities (like a Core Architecture Decision or a Core Data Model) to immutable business rules rather than volatile files or line numbers.
* Example: If a file is refactored, renamed, or split over 10 years, the relationship to the original design intent remains intact because it is anchored to a persistent functional domain id rather than a file path.

## 4. Implement Relationship Hash-Chaining for Evolution Tracking
When code changes over a 10-year span, relationships naturally break (the "stale graph" problem).

* Introduce a mutated_into relationship.
* When a class or function is deprecated or heavily refactored, do not simply delete its historical relationships. Point the old node to the new node using a lineage edge (node_A -> mutated_into -> node_B). This allows Raiker to trace the structural evolution of a module across historical Git commits over a decade.

## 5. Vector-Optimized Relationship Queries
For fast agent communication, stop relying solely on exhaustive graph traversals (like depth-first search) which stall out on deep 10-year history trees.

* Map every relationship type into a semantic vector space.
* When the agent asks a cross-cutting question ("How has our authentication philosophy changed over the last decade?"), it can use vector-similarity search to immediately land on the relevant neighborhood of edges without needing to compute the entire dependency path.



