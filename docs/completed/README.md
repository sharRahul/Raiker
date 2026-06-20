# Completed / Superseded Documents

This directory contains documents that are no longer active source-of-truth. They are preserved for traceability.

Active source-of-truth documents remain under `docs/`. When a document here is referenced by an active doc, the active doc points to `docs/completed/<filename>`.

## Completed Phase 3 slice / phase deliverables

| Moved filename | Original purpose | Why moved | Replacement / current source-of-truth | Date moved |
|---|---|---|---|---|
| `PHASE_1_MVP_BUILD_PLAN.md` | Phase 1 build scope, task order, acceptance criteria. | Phase 1 is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 1 status table); `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` for living contracts. | 2026-06-20 |
| `PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md` | Phase 2 task decomposition and acceptance criteria. | Phase 2 is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 2 status table). | 2026-06-20 |
| `PHASE_3_BUILD_PLAN.md` | Phase 3 local rich workspace, extensibility foundation, governance, approval-preview plan. | Phase 3 slices A-P are `implemented_verified` per `docs/PHASE_3_COMPLETION_AUDIT.md`. | `docs/PHASE_3_COMPLETION_AUDIT.md`; `docs/IMPLEMENTATION_STATUS.md`. | 2026-06-20 |
| `PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SPEC.md` | Phase 3 Slice A proposal lifecycle foundation spec. | Slice A is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice A status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_SPEC.md` | Phase 3 Slice B approval planning preview spec. | Slice B is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice B status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md` | Phase 3 Slice G storage lifecycle preparation spec. | Slice G is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice G status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md` | Phase 3 Slice H lifecycle retention spec. | Slice H is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice H status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md` | Phase 3 Slice I lifecycle evidence bundle / policy simulation spec. | Slice I is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice I status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_J_GRAPH_CODEMAP_READINESS_SPEC.md` | Phase 3 Slice J graph/codemap indexing readiness metadata spec. | Slice J is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice J status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_K_SEMANTIC_MEMORY_READINESS_SPEC.md` | Phase 3 Slice K semantic memory write readiness metadata spec. | Slice K is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice K status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_L_APPROVAL_PREVIEW_PERSISTENCE_READINESS_SPEC.md` | Phase 3 Slice L approval preview persistence readiness metadata spec. | Slice L is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice L status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_M_STORAGE_CLEANUP_EXECUTION_READINESS_SPEC.md` | Phase 3 Slice M storage cleanup execution readiness metadata spec. | Slice M is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice M status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_N_PLUGIN_SERVER_STARTUP_READINESS_SPEC.md` | Phase 3 Slice N plugin/server startup readiness metadata spec. | Slice N is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice N status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_O_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_SPEC.md` | Phase 3 Slice O external channels/notifications readiness metadata spec. | Slice O is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice O status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_P_REMOTE_CONTAINER_CLOUD_READINESS_SPEC.md` | Phase 3 Slice P remote/container/cloud execution readiness metadata spec. | Slice P is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice P status); `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_3_SLICE_Q1_RICH_TUI_DEFAULT_ACCESS_SHELL_SPEC.md` | Phase 3 Slice Q1 documented default Rich TUI access shell spec. | Slice Q1 default access shell is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice Q1 status); `docs/UI_UX_DESIGN_SPEC.md` for the living TUI spec. | 2026-06-20 |

## Superseded point-in-time audits / handoffs

| Moved filename | Original purpose | Why moved | Replacement / current source-of-truth | Date moved |
|---|---|---|---|---|
| `PRE_PHASE_3_READINESS_AUDIT.md` | Audit confirming Phase 1, 2, 2.5, 2.6 complete before Phase 3 start. | Phase 3 is now complete; superseded by the Phase 3 completion audit. | `docs/PHASE_3_COMPLETION_AUDIT.md`; `docs/IMPLEMENTATION_STATUS.md`. | 2026-06-20 |
| `PHASE_1_2_ACCEPTANCE_HARDENING_AUDIT.md` | Point-in-time acceptance hardening audit for Phase 1 and Phase 2. | Phase 1 and 2 remain `implemented_verified`; status tracked in the ledger. | `docs/IMPLEMENTATION_STATUS.md`. | 2026-06-20 |
| `PHASE_3_READINESS_PATTERN_CONSOLIDATION_AUDIT.md` | Audit of repeated Phase 3 readiness patterns across Slices J-O before Slice P. | All slices J-P are implemented; superseded by the completion audit. | `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-20 |
| `PHASE_1_TO_5_SLICE_G_ALIGNMENT.md` | Note explaining how Phase 3 Slice G affects every phase. | Slice G is `implemented_verified`. | `docs/IMPLEMENTATION_STATUS.md` (Phase 3 Slice G status). | 2026-06-20 |
| `SLICE_G_CODING_AGENT_HANDOFF.md` | Coding-agent handoff note after Phase 3 Slice G. | Slice G is `implemented_verified`; later slices complete. | `docs/PHASE_3_COMPLETION_AUDIT.md`; `docs/IMPLEMENTATION_STATUS.md`. | 2026-06-20 |
| `PHASE_3_NEXT_SLICE_DEFINITION_AUDIT.md` | Audit of Phase 3 slice status before Slice J definition. | All Phase 3 slices A-P are implemented and documented. | `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-18 |
| `PHASE_3_NEXT_SLICE_SELECTION_PROPOSAL.md` | Proposed next Phase 3 slices J-O with scope definitions. | Slices J-O are implemented and documented individually. | `docs/PHASE_3_SLICE_J_*` through `docs/PHASE_3_SLICE_P_*` specs (now in this directory), `docs/PHASE_3_COMPLETION_AUDIT.md`. | 2026-06-18 |

## Legacy / superseded foundational documents (numbered series)

These pre-date the named Raiker documents and are retained for traceability only. They are **not** active source-of-truth and are not referenced by the current builder reading order or documentation map. Some use the former project name "Local Sovereign Agent" and one prescribes a `/core/...` directory layout that does not match the actual `raiker/` package.

| Moved filename | Original purpose | Why moved | Replacement / current source-of-truth | Date moved |
|---|---|---|---|---|
| `01_PRD.md` | Original product requirements document. | Superseded by `README.md` and `docs/FEATURE_COVERAGE_MATRIX.md`. | `README.md`; `docs/FEATURE_COVERAGE_MATRIX.md`. | 2026-06-20 |
| `02_SPEC.md` | Original technical spec (uses "Local Sovereign Agent" name). | Superseded by the named spec docs. | `docs/ARCHITECTURE.md`; `docs/CONTRACTS.md`; `docs/API_AND_CONTRACT_SCHEMAS.md`. | 2026-06-20 |
| `03_ARCHITECTURE.md` | Original nested-boundary architecture description. | Superseded by `docs/ARCHITECTURE.md` and `docs/NESTED_BOUNDARIES_ARCHITECTURE.md`. | `docs/ARCHITECTURE.md`; `docs/NESTED_BOUNDARIES_ARCHITECTURE.md`. | 2026-06-20 |
| `04_ROADMAP.md` | Original phase 0-5 roadmap. | Superseded by `docs/ROADMAP_PHASE_2_TO_PHASE_5.md` and the phase build plans. | `docs/ROADMAP_PHASE_2_TO_PHASE_5.md`; `docs/PHASE_4_BUILD_PLAN.md`; `docs/PHASE_5_BUILD_PLAN.md`. | 2026-06-20 |
| `05_MASTER_BUILD_PROMPT.md` | Master build prompt (uses "Local Sovereign Agent" name). | Superseded by `docs/LOCAL_LLM_BUILDER_GUIDE.md`. | `docs/LOCAL_LLM_BUILDER_GUIDE.md`. | 2026-06-20 |
| `06_SECURITY_MODEL.md` | Original security model. | Superseded by `docs/SECURITY_AND_POLICY.md` and `docs/THREAT_MODEL.md`. | `docs/SECURITY_AND_POLICY.md`; `docs/THREAT_MODEL.md`. | 2026-06-20 |
| `07_PROMPT_FILES.md` | Prompt pack (uses "Local Sovereign Agent" name). | Superseded by `docs/LOCAL_LLM_BUILDER_GUIDE.md`. | `docs/LOCAL_LLM_BUILDER_GUIDE.md`. | 2026-06-20 |
| `08_ACCEPTANCE_TESTS.md` | Original acceptance test groups A-D. | Superseded by `docs/ACCEPTANCE_TESTS_BY_PHASE.md`. | `docs/ACCEPTANCE_TESTS_BY_PHASE.md`. | 2026-06-20 |
| `09_IMPLEMENTATION_PLAN.md` | Original Phase 1 task decomposition. | Superseded by the phase build plans (now in this directory) and `docs/BUILD_ORDER.md`. | `docs/completed/PHASE_1_MVP_BUILD_PLAN.md`; `docs/BUILD_ORDER.md`. | 2026-06-20 |
| `10_AGENT_CONTRACTS.md` | Original language-neutral contracts. | Superseded by `docs/CONTRACTS.md` and `docs/API_AND_CONTRACT_SCHEMAS.md`. | `docs/CONTRACTS.md`; `docs/API_AND_CONTRACT_SCHEMAS.md`. | 2026-06-20 |
| `11_DIRECTORY_STRUCTURE.md` | Original directory scaffold (prescribes `/core/...` layout). | Does not match the actual `raiker/` package layout; superseded by `docs/ARCHITECTURE.md` and the real `raiker/` tree. | `docs/ARCHITECTURE.md`; the `raiker/` package itself. | 2026-06-20 |
| `12_ADR_TEMPLATE.md` | Original ADR template. | Duplicates `docs/ADR_TEMPLATE.md` (the richer current template). | `docs/ADR_TEMPLATE.md`. | 2026-06-20 |
