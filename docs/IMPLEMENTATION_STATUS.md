# Implementation Status

This document is the implementation control ledger for Raiker. It converts the existing phase blueprint into a builder-proof status view so a local or cloud coding agent can tell what is specified, what is implemented, what is intentionally disabled, and what must not be built yet.

A feature marked as specified is not automatically implemented. A feature marked as phase-scheduled is not permission to invent behaviour in code. A feature may only be marked `implemented_verified` when the implementation maps to documented task IDs, required tests exist, and validation has passed for the current change set.

---

## Status Vocabulary

| Status | Meaning | Builder action |
|---|---|---|
| `specified_not_implemented` | The behaviour is documented, but code is not present yet. | Implement only through a named task and tests. |
| `phase_1_required` | Required for the Phase 1 MVP. | Build in Phase 1 task order. |
| `phase_scheduled_disabled` | Contract/profile/storage boundary may exist, but runtime wiring is disabled until a later phase. | Preserve contracts and registries; do not activate. |
| `implemented_unverified` | Code exists, but current acceptance validation is missing, incomplete, or not yet recorded for the active change set. | Run/repair tests before marking complete. |
| `implemented_verified` | Code and tests satisfy the acceptance criteria for the active change set. | Keep stable; regressions must fail CI. |
| `blocked_by_spec_gap` | Required behaviour is not detailed enough to implement safely. | Update docs before code. |
| `out_of_scope` | Deliberately not a Raiker goal. | Do not implement unless the non-goal is changed through ADR. |

---

## Phase 1 MVP Status

PR #6 added the initial Phase 1 MVP runtime core.
PR #8 reconciled documentation and version baseline.

**Validation status (2026-06-17):** The full validation set was run on the `phase-1-runtime-core-validation-baseline` branch. All validation commands pass, event sequences are verified, and security invariants hold. The Phase 1 final acceptance criteria are met. See the validation PR for exact command outputs and artifact inspection results.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---:|---:|---|---|
| Python package scaffold | `phase_1_required` | `implemented_verified` | `docs/PHASE_1_MVP_BUILD_PLAN.md`, `docs/ARCHITECTURE.md` | import/package smoke |
| Global `raiker` command | `phase_1_required` | `implemented_verified` | `README.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_scaffold.py`, terminal smoke |
| Equal-interface metadata | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/FEATURE_COVERAGE_MATRIX.md` | `tests/test_equal_interface_invariant.py` or equivalent invariant coverage |
| PromptEnvelope contract | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | `tests/test_contracts.py` |
| AgentEvent contract | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/EVENT_CATALOG.md` | `tests/test_event_log.py` |
| SQLite bootstrap | `phase_1_required` | `implemented_verified` | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_storage_sqlite.py` |
| Append-only JSONL event writer | `phase_1_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_event_log.py` |
| Static policy engine | `phase_1_required` | `implemented_verified` | `docs/SECURITY_AND_POLICY.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | `tests/test_policy_engine.py` |
| Tool broker skeleton | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | `tests/test_tool_broker.py` |
| `read_file` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | path safety tests |
| `list_directory` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | stable sorted output tests |
| `glob` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | bounded result tests |
| `grep` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | text-only and bounded output tests |
| Local action proposal | `phase_1_required` | `implemented_verified` | `docs/SECURITY_AND_POLICY.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | approval-required tests |
| Mock model provider | `phase_1_required` | `implemented_verified` | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | deterministic output tests |
| Model profile registry | `phase_1_required` | `implemented_verified` | `config/model-profiles.json`, `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | registry load tests |
| Channel connector registry | `phase_1_required` | `implemented_verified` | `config/channel-connectors.json`, `docs/CHANNELS_SPEC.md` | disabled/listable tests |
| Runtime state machine | `phase_1_required` | `implemented_verified` | `docs/RUNTIME_STATE_MACHINE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` | transition tests |
| Agent gateway | `phase_1_required` | `implemented_verified` | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` | gateway validation tests |
| Session manager | `phase_1_required` | `implemented_verified` | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | create/load tests |
| Checkpoint stub | `phase_1_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | write/read stub tests |
| Terminal client MVP | `phase_1_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` | terminal smoke tests |

---

## Phase-Scheduled Disabled Capabilities

The following capabilities may have config profiles, schemas, or storage boundaries in Phase 1, but must not be wired into active behaviour until their phase task explicitly allows it.

| Capability | First active phase | Required Phase 1 behaviour |
|---|---:|---|
| Desktop UI | Phase 3 | Preserve equal-interface contracts only. |
| Web UI and dashboard | Phase 3 | Preserve action parity and storage metrics contracts only. |
| Apple mobile app | Phase 3 | Connector profile may be disabled/listable; no active transport. |
| Android mobile app | Phase 3 | Connector profile may be disabled/listable; no active transport. |
| Plugin execution | Phase 3 | Validate/describe manifest shape only; no plugin code execution. |
| Semantic/vector memory writes | Phase 3 | Preserve storage metadata boundaries; no active embedding writes. |
| Graph/codemap runtime indexing | Phase 3 | Preserve schema/spec only; no runtime indexing. |
| External channels | Phase 4 | Profiles disabled unless explicitly paired in later phase. |
| Subagents and multi-agent teams | Phase 4 | Contracts/spec only; no spawning. |
| Remote/container execution | Phase 4 | Execution profiles disabled; no command routing. |
| Hosted model billing controls | Phase 5 | Hosted providers disabled until policy and budgets exist. |

---

## Status Update Rule

A builder may change a row to `implemented_verified` only when all of these are true:

1. The implementation maps to a Phase 1 task ID or later phase task ID.
2. The implementation follows the canonical docs listed in this file.
3. Required tests exist and pass for the active change set.
4. Validation output is included in the PR.
5. Event names, storage tables, contracts, and policy decisions match the specs.
6. The equal primary-interface invariant remains intact.

If any of these are false, the correct status is `implemented_unverified` or `blocked_by_spec_gap`.

---

## Documentation Gap Handling

When a builder finds conflicting or incomplete documentation, it must stop the implementation task and create a documentation update first. The documentation update must identify:

- affected feature;
- build phase;
- conflicting files;
- chosen canonical behaviour;
- contracts affected;
- storage affected;
- events emitted;
- policy/security impact;
- tests required.

Undocumented behaviour is not approved Raiker behaviour.
