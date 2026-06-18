# Build Order

This document defines the dependency-safe order for implementing Raiker. It complements `docs/PHASE_1_MVP_BUILD_PLAN.md` by making the build sequence explicit enough that a builder agent does not implement UI, tools, memory, plugins, channels, or storage lifecycles before the contracts and safety rails exist.

Phase order controls implementation sequencing only. It does not create an interface hierarchy.

---

## Required Reading Order

Every implementation task must start with this sequence:

```text
README.md
  -> docs/IMPLEMENTATION_STATUS.md
  -> docs/FEATURE_COVERAGE_MATRIX.md
  -> docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/BUILD_ORDER.md
  -> docs/ARCHITECTURE.md
  -> docs/CONTRACTS.md
  -> docs/API_AND_CONTRACT_SCHEMAS.md
  -> docs/EVENT_CATALOG.md
  -> docs/RUNTIME_STATE_MACHINE.md
  -> docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md
  -> docs/SECURITY_AND_POLICY.md
  -> docs/THREAT_MODEL.md
  -> docs/NON_GOALS_AND_BOUNDARIES.md
  -> docs/PHASE_1_MVP_BUILD_PLAN.md
  -> docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md
  -> docs/PHASE_3_BUILD_PLAN.md
  -> docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md
  -> docs/PHASE_1_TO_5_SLICE_G_ALIGNMENT.md
  -> docs/SLICE_G_CODING_AGENT_HANDOFF.md
  -> docs/PHASE_4_BUILD_PLAN.md
  -> docs/PHASE_5_BUILD_PLAN.md
  -> docs/RUNTIME_ORCHESTRATION_SPEC.md
  -> docs/TOOLS_AND_PERMISSIONS_SPEC.md
  -> docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md
  -> docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md
  -> docs/MODEL_PROVIDER_CONTRACT.md
  -> docs/CHANNELS_SPEC.md
  -> docs/UI_UX_DESIGN_SPEC.md
  -> docs/MEMORY_AND_CONTEXT_STRATEGY.md
  -> docs/MEMORY_GOVERNANCE_RULES.md
  -> docs/PLUGIN_SYSTEM_SPEC.md
  -> docs/PLUGIN_MANIFEST_SCHEMA.md
  -> docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md
  -> docs/ACCEPTANCE_TESTS_BY_PHASE.md
  -> docs/REFERENCE_REQUIREMENTS_MATRIX.md
  -> docs/VERIFICATION_PLAN.md
  -> docs/LOCAL_VALIDATION_GATE.md
  -> config/model-profiles.json
  -> config/channel-connectors.json
```

A builder must not skip the status, schema, event, runtime state, storage, security, threat-model, non-goals, acceptance-test, verification, or registry docs because they are the controls that keep the implementation deterministic.

---

## Phase 1 Dependency Graph

```text
RAIKER-0001 scaffold
  -> RAIKER-0002 dev tooling
    -> RAIKER-0101 contracts
      -> RAIKER-0102 IDs/timestamps
        -> RAIKER-0201 SQLite bootstrap
        -> RAIKER-0202 JSONL event writer
        -> RAIKER-0203 built-in registries
          -> RAIKER-0301 static policy config
            -> RAIKER-0302 policy engine
              -> RAIKER-0401 tool broker routing
                -> RAIKER-0402 read_file
                -> RAIKER-0403 list_directory
                -> RAIKER-0404 glob/grep
                -> RAIKER-0405 approval-gated local action placeholder
          -> RAIKER-0501 mock model provider
            -> RAIKER-0502 model router interface
            -> RAIKER-0503 terminal launch profile resolution
          -> RAIKER-0601 runtime states
            -> RAIKER-0602 classifier/planner
            -> RAIKER-0603 verification stub
              -> RAIKER-0701 agent gateway
                -> RAIKER-0702 session manager
                -> RAIKER-0703 checkpoint service
                  -> RAIKER-0801 global raiker launch
                  -> RAIKER-0802 terminal prompt path
                  -> RAIKER-0803 terminal approval behaviour
                  -> RAIKER-0804 terminal registry panels
                    -> RAIKER-0901 end-to-end smoke tests
                    -> RAIKER-0902 documentation/validation report
```

---

## Non-Negotiable Sequencing Rules

1. Contracts before runtime.
2. Event envelope before event writer.
3. SQLite bootstrap before event indexing.
4. Policy engine before tool execution.
5. Tool broker before any filesystem/search/local-command action.
6. Mock model provider before model routing tests.
7. Runtime state machine before terminal prompt orchestration.
8. Agent gateway before any client-specific prompt path.
9. Checkpoint stub before terminal end-to-end completion criteria.
10. Equal-interface metadata before first terminal-specific implementation.
11. Lifecycle metadata contracts before lifecycle metadata storage.
12. Lifecycle metadata storage before lifecycle summaries.
13. Lifecycle summaries before any future lifecycle approval handoff.
14. Lifecycle approval handoff before any future runtime graph/memory/rollback execution work.

If a builder needs to violate this order for bootstrap reasons, it must document the temporary exception in the PR and add a follow-up task that restores the canonical order.

---

## Phase 1 Build Slices

| Slice | Task IDs | Output | Must not do |
|---|---|---|---|
| Foundation | RAIKER-0001 to RAIKER-0002 | Package, tests, dev tooling | No runtime behaviour. |
| Contracts | RAIKER-0101 to RAIKER-0102 | Versioned schemas and ID helpers | No tool execution. |
| Storage/events | RAIKER-0201 to RAIKER-0203 | SQLite, JSONL, registries | No active channels or hosted providers. |
| Policy | RAIKER-0301 to RAIKER-0302 | Static allow/deny/needs_approval decisions | No command execution. |
| Tools | RAIKER-0401 to RAIKER-0405 | Brokered read/list/glob/grep plus approval placeholder | No direct file access from runtime. |
| Models | RAIKER-0501 to RAIKER-0503 | Mock provider and profile resolution | No network or hosted provider calls. |
| Runtime | RAIKER-0601 to RAIKER-0603 | Deterministic state machine and verifier stub | No parallel agent teams. |
| Gateway/session/checkpoint | RAIKER-0701 to RAIKER-0703 | Shared gateway and checkpoint stub | No client bypass path. |
| Terminal MVP | RAIKER-0801 to RAIKER-0804 | First terminal client through gateway | No terminal-only architecture. |
| Validation | RAIKER-0901 to RAIKER-0902 | Smoke tests and report | No unverified completion claim. |

---

## Phase 2 Dependency Graph

```text
RAIKER-1001 Phase 2 plan
  -> RAIKER-1002 CI baseline
    -> RAIKER-1101 task contract + storage
      -> RAIKER-1102 task manager
        -> RAIKER-1103 task events
    -> RAIKER-1601 event query service
      -> RAIKER-1602 /events command
    -> RAIKER-1701 /status and /tasks
    -> RAIKER-1501 checkpoint timeline
  -> RAIKER-1201 side-question contract
    -> RAIKER-1202 side-question runtime
  -> RAIKER-1301 interrupt/steer contracts
    -> RAIKER-1302 safe-boundary handling
  -> RAIKER-1401 approval inbox
    -> RAIKER-1402 approval commands
  -> RAIKER-1502 checkpoint restore/fork
  -> RAIKER-1801 stat_path/diff_files
    -> RAIKER-1802 write/edit/patch with snapshots
  -> RAIKER-1901 git wrappers
  -> RAIKER-2001 provider health check
    -> RAIKER-2002 Ollama detection
  -> RAIKER-2101 memory candidate listing
    -> RAIKER-2201 integration validation
```

---

## Phase 2 Build Slices

| Slice | Task IDs | Output | Must not do |
|---|---|---|---|
| Foundation | RAIKER-1001 to RAIKER-1002 | CI, status ledger, build plan | No runtime behaviour change. |
| Task management | RAIKER-1101 to RAIKER-1103 | Task storage, manager, events | No tool execution. |
| Event viewer | RAIKER-1601 to RAIKER-1602 | Event query service and /events | No event log mutation. |
| Terminal inspection | RAIKER-1701, RAIKER-1501 | /status, /tasks, /checkpoints | No restore/fork execution. |
| Side questions | RAIKER-1201 to RAIKER-1202 | Child-turn contract and runtime | No active task mutation. |
| Interrupt/steer | RAIKER-1301 to RAIKER-1302 | Interrupt contracts and safe-boundary | No silent cancellation. |
| Approvals | RAIKER-1401 to RAIKER-1402 | Approval inbox and commands | No auto-approval. |
| File tools | RAIKER-1801 to RAIKER-1802 | stat_path, diff_files, write/patch proposal | No unrestricted file mutation. |
| Git wrappers | RAIKER-1901 | Git status/diff/log with policy | No git push/merge without approval. |
| Model providers | RAIKER-2001 to RAIKER-2002 | Health check, Ollama detection | No hosted model calls. |
| Memory | RAIKER-2101 | Memory candidate listing | No durable memory writes. |
| Validation | RAIKER-2201 | Integration tests and status update | No unverified completion claim. |

---

## Phase 3 Storage Lifecycle Build Order

Slice G is the current deepest Phase 3 storage lifecycle preparation slice. Future agents must follow this sequence:

```text
Slice C graph/codemap dry-run planning
  -> Slice D semantic-memory review queue
    -> Slice E approval preview contracts
      -> Slice F approval audit + rollback planning
        -> Slice G storage lifecycle metadata
          -> Slice H metadata-only retention/cleanup-preview/approval-handoff planning
```

Slice G may create and inspect metadata records only. It must not be used as a trigger for graph indexing, semantic/vector memory writes, embeddings, rollback execution, plugin execution, channels, subagents, or remote/container/cloud execution.

---

## Builder Stop Conditions

A builder must stop and update documentation before coding if:

- a contract field is missing or ambiguous;
- an event name is not in `docs/EVENT_CATALOG.md`;
- a state transition is not allowed by `docs/RUNTIME_STATE_MACHINE.md`;
- a storage table or column is missing from the storage spec;
- a tool lacks policy, failure modes, or output limits;
- an approval flow is not action-bound;
- a lifecycle metadata record would imply runtime execution;
- a later-phase feature would need active runtime wiring;
- a client would bypass the Agent Gateway;
- a change would make terminal/TUI canonical over another enabled primary interface.

---

## PR Completion Gate

Every implementation PR must include:

```markdown
## Task IDs
- RAIKER-....

## Build order position
- Slice: ...
- Depends on: ...

## Contracts/events/storage/policy affected
- Contracts: ...
- Events: ...
- Storage: ...
- Policy: ...

## Validation
- [ ] python -m pytest
- [ ] python -m ruff check .
- [ ] python -m mypy raiker apps tests
- [ ] python scripts/validate_phase_status.py
- [ ] raiker smoke test, if terminal path affected

## Invariants
- [ ] No client bypasses Agent Gateway
- [ ] No tool executes without policy decision
- [ ] Equal primary-interface invariant preserved
- [ ] Phase-scheduled features remain disabled unless this task explicitly enables them
- [ ] Slice G lifecycle metadata remains metadata-only unless a later approved task explicitly changes that with docs, tests, policy, rollback, and CI evidence
```

## Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.
