# Implementation Status

> Current truth (2026-06-21): current launchable UI is the plain local terminal client only. Rich/native TUI is Phase 8 deferred work. Desktop/Web/Dashboard/Mobile/IDE/Voice/Browser Extension/REST/API clients are Phase 8 deferred, specified but not implemented. Phase 3 is complete only for safe foundation/readiness slices A-P; Phase 4 memory MVP is implemented; Phase 5-7 remain metadata/readiness/contract surfaces unless code and tests explicitly prove runtime behavior. Runtime execution remains disabled for plugin execution, graph indexing, semantic/vector writes, embeddings, approval execution/relay, cleanup/rollback execution, external channels/notifications, remote/container/cloud/process/shell/network execution.


Security architecture status and deferred-control gates are summarized in [`docs/SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md).

This document is the implementation control ledger for Raiker. It converts the existing phase blueprint into a builder-proof status view so a local or cloud coding agent can tell what is specified, what is implemented, what is intentionally disabled, and what must not be built yet.

A feature marked as specified is not automatically implemented. A feature marked as phase-scheduled is not permission to invent behaviour in code. A feature may only be marked `implemented_verified` when the implementation maps to documented task IDs, required tests exist, and validation has passed for the current change set.

## Canonical Backend Capability Statuses

The backend foundation uses these current-status labels when the simpler phase ledger terms would be ambiguous:

- `implemented_read_only`
- `implemented_policy_gated`
- `implemented_approval_required`
- `metadata_only`
- `readiness_only`
- `dry_run_only`
- `contract_only`
- `disabled_deferred`
- `test_only`

Current high-signal truth:

- Approval resolution is `metadata_only`: `/approve` and `/deny` do not execute actions.
- Approval resolution is metadata-only.
- CLI durable memory mutation is `implemented_approval_required`: requests are brokered and approval-required by default.
- Governed durable memory writes are `implemented_policy_gated`: they require provenance, retention, approval_state, confidence, trust_score, and event logging on the governed path.
- Semantic/vector writes, graph indexing, plugin execution, channel runtime, and remote execution remain `disabled_deferred`.
- **Runtime Authority / Action Router** (`raiker/runtime/authority/`) is `implemented_policy_gated` — governs all mutation actions through capability gates, policy engine, risk classification, approval/risk acceptance, and event logging.
- **AI-executable role model** is `implemented_policy_gated` — defines `assistant`, `automation`, `operator`, `developer` roles with per-role permissions, denied capabilities, and self-approval/self-grant restrictions.
- **Human-only role protection** is `implemented_policy_gated` — `owner`, `admin`, `approver`, `security_admin`, `finance_approver`, `medical_decision_maker`, `runtime_gate_manager` cannot be assigned to AI principals.
- **Domain scopes** are `implemented_policy_gated` — 16 domain scopes enforced at the authority level.
- **Risk acceptance model** is `implemented_policy_gated` — risk acceptance records with required fields, expiry, one-time/reusable, and event logging.
- **Capability registry** is `implemented_policy_gated` — expanded to 47 capabilities covering all domain runtimes, all default-disabled.
- **Event redaction** is `implemented_policy_gated` — extended with bank/card/medical ID patterns.
- **Runtime enablement validator** is `implemented_verified` — `scripts/validate_runtime_enablement_readiness.py`.

### Enforcement status

- Runtime readiness decision: `runtime_enablement_candidate`.
- strict non-allow blocking: enforced — `_govern_admin_mutation` blocks on all non-allow decisions (`deny`, `needs_approval`, `needs_risk_acceptance`, `needs_human_confirmation`, `disabled_by_capability_gate`).
- role revoke governed: enforced — routes through `_govern_admin_mutation` / RuntimeAuthority before mutation.
- capability gate per action: enforced — `RuntimeAuthority.check_capability_gate()` checks the relevant gate for each governed action and returns `disabled_by_capability_gate` when the gate is disabled.
- risk acceptance enforcement: enforced — one-time risk acceptances are consumed (deleted) on use; expired, mismatched, or missing acceptances block execution; critical-risk always requires human confirmation.
- **Validator depth**: `scripts/validate_runtime_enablement_readiness.py` now detects direct store mutation patterns in CLI handlers without governance, and validates documentation markers across all 8 required docs.
- Approval resolution remains `metadata_only` — does not execute approved actions.
- No UI/API client implements RuntimeAuthority as the sole authority path (no UI/API clients exist yet).

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

## Known Documentation/Code Gaps (Review 2026-06-19)

A repository review (`docs/GAP_AND_TODO_ANALYSIS.md`) verified the following gaps
where documentation runs ahead of code. These are recorded here so the ledger stays trustworthy;
none of them change the validator-required Phase 1/2/3 markers below.

| Area | Documented as | Verified code reality | Honest status |
|---|---|---|---|
| Hooks | Full lifecycle spec (`docs/HOOKS_SPEC.md`) | `raiker/hooks/` implements `builtin`+`command` handlers, scoped config, decision authority, and dispatch wired through the broker/gateway; `http`/`mcp_tool`/`prompt`/`agent` deferred | `implemented_verified` (core); remaining handler types `specified_not_implemented` |
| Local model providers | llama.cpp native default through async OpenAI-compatible adapter; Ollama/LM Studio/vLLM/generic/OpenRouter profile-compatible and policy-gated; deterministic test-only | `raiker/models/providers/openai_compatible.py` uses `httpx.AsyncClient`; production gateway selects llama.cpp and never falls back to deterministic; OpenRouter/private/hosted profiles require explicit policy | `implemented_verified` (async adapter + policy gates) |
| Local provider health-check | Phase 2 `implemented_verified` | `raiker/models/health.py` probes the llama.cpp `/health` endpoint over HTTP | accurate |
| Model-driven tool calls | "gather→act→verify" loop | `raiker/runtime/orchestrator.py` runs a bounded model-driven loop; model tool calls validated by `raiker/models/tool_call_validation.py` (OWASP LLM05) | `implemented_verified` |
| Verifier / verification step | "verify results" loop phase | `raiker/verification/` + `raiker/runtime/verifier.py` run deterministic safety/result-shape checks (tool-call schema, denied/approval non-execution, read result shape, mutation gating); integrated into the runtime loop | `implemented_verified` (deterministic safety/result-shape verification; not a semantic-correctness proof) |
| Context gathering | repository understanding feeding the model | `raiker/context/` builds a bounded `ContextBundle` of safe Phase 1/2 local metadata with provenance, trust level, sensitivity, redaction, and budgeting; the fixed `sources=["current_prompt"]` stub is removed from the runtime path | `implemented_verified` (Phase 1/2-safe bounded local-metadata context; not full repository intelligence) |
| Code review workflow | implied by "coding platform" | no review module present | `specified_not_implemented` (remains a separate follow-up; not required by Phase 1/2 acceptance) |

These do not activate or disable any runtime capability; they correct the *claimed* maturity only.
Close them via named phase tasks with tests before marking any `implemented_verified`.

### Phase 1/2 runtime maturity update (context gathering + verifier)

The two long-standing Phase 1/2 runtime stubs are now closed:

- **Context gathering** is now `implemented_verified` for Phase 1/2-safe bounded local-metadata
  context. `raiker/context/` produces a deterministic `ContextBundle` from safe sources only
  (current prompt, workspace summary, recent events, tasks, checkpoints, approvals, memory
  status/candidates, model profile, capability status). Every item carries source type, trust
  level, provenance, sensitivity, and redaction metadata; the bundle is budgeted by item count
  and characters; secrets/tokens/emails/private keys are redacted with deterministic
  placeholders. The runtime no longer records the fixed `sources=["current_prompt"]` stub.
  This is bounded metadata/local-summary context only, not full repository intelligence, and it
  does not enable semantic search, vector memory, graph runtime, plugin execution, external
  channels, or remote/container/cloud execution.
- **Verifier** is now `implemented_verified` for deterministic safety/result-shape verification.
  `raiker/verification/` checks tool-call schemas (unknown/invalid calls fail and are not
  executed), confirms denied actions did not execute, confirms approval-required actions stopped
  before execution with an approval record, validates safe read-tool result shape, and confirms
  mutation proposals stay approval-gated. Verifier output never exposes hidden reasoning,
  chain-of-thought, scratchpads, or system prompts. This is safety/result-shape verification, not
  a semantic-correctness proof.
- **Code review workflow** is now delivered as the Phase 2.5 local code-review workflow MVP
  (`implemented_verified` for CLI-only, read-only, bounded local diff review using deterministic
  rule-based findings and metadata-only events). See the Phase 2.5 status section below.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_1_2_context_gatherer.py`, `tests/test_phase_1_2_verifier.py`,
`tests/test_phase_1_2_runtime_gather_act_verify.py`.

---

## Phase 2.5 Local Code-Review Workflow Status

Phase 2.5 local code-review workflow MVP: `implemented_verified` for CLI-only, read-only, bounded
local diff review using deterministic rule-based findings and metadata-only events.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `raiker/review/` review engine (models, workflow, classifier, diff parser, render) | `phase_2_5` | `implemented_verified` | `raiker/review/` | `tests/test_phase_2_5_code_review_workflow.py` |
| `/review` CLI command surface (`--summary`, `--staged`, `--path`, `--json`, `--limit`, `--severity`) | `phase_2_5` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_2_5_code_review_cli.py` |
| Deterministic rule-based findings + metadata-only review events | `phase_2_5` | `implemented_verified` | `raiker/review/classifier.py`, `raiker/review/workflow.py` | `tests/test_phase_2_5_code_review_safety.py` |

Scope and boundaries:

- Review collects local Git status/diff through the existing policy-mediated `ToolBroker`/
  `PolicyEngine` git wrappers and the Phase 1/2-safe context gatherer. It does not call
  `subprocess`, shell, process, or network directly from `raiker/review/`.
- Review is read-only: it never mutates files, stages/unstages the Git index, commits, runs tests,
  applies fixes, or starts watchers/workers/daemons.
- Raw diffs, file contents, and secrets are never placed into findings or event payloads; secret-like
  content is redacted before findings/events.
- This MVP is deterministic/rule-based local CLI review only. It is **not** model-assisted review,
  GitHub PR review automation, a web/dashboard review UI, an IDE review UI, external-channel review
  delivery, plugin-based review, or semantic/graph review intelligence. Those remain deferred.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_2_5_code_review_workflow.py`, `tests/test_phase_2_5_code_review_cli.py`,
`tests/test_phase_2_5_code_review_safety.py`.

Phase 2.5 review hardening: `implemented_verified` for filtered-summary consistency and
metadata-only untracked-file detection.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `--severity`/`--limit` summary rebuilt from filtered findings | `phase_2_5` | `implemented_verified` | `raiker/review/render.py`, `raiker/cli/commands.py` | `tests/test_phase_2_5_code_review_hardening.py` |
| Metadata-only untracked-file detection in `/review` | `phase_2_5` | `implemented_verified` | `raiker/review/workflow.py` | `tests/test_phase_2_5_code_review_hardening.py` |

Hardening details:
- `rebuild_review_result_with_findings()` rebuilds `ReviewSummary.findings_count`,
  `severity_counts`, `categories`, and `event_metadata` from filtered findings.
- Filtering order is severity threshold first, limit second, summary rebuild third.
- `_collect_untracked_files()` uses `git_status` through `ToolBroker`/`PolicyEngine`.
- Untracked files are detected as metadata only; their contents are not read or leaked.
- Event payloads include safe `untracked_count` but not file contents or raw diffs.

Scope and boundaries (same as MVP — no expansion):
- Review collects local Git status/diff through the existing policy-mediated `ToolBroker`/
  `PolicyEngine` git wrappers and the Phase 1/2-safe context gatherer. It does not call
  `subprocess`, shell, process, or network directly from `raiker/review/`.
- Review is read-only: it never mutates files, stages/unstages the Git index, commits, runs tests,
  applies fixes, or starts watchers/workers/daemons.
- Raw diffs, file contents, and secrets are never placed into findings or event payloads; secret-like
  content is redacted before findings/events.
- This hardening is deterministic/rule-based local CLI review only. It is **not** model-assisted
  review, GitHub PR review automation, a web/dashboard review UI, an IDE review UI, external-channel
  review delivery, plugin-based review, or semantic/graph review intelligence. Those remain deferred.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_2_5_code_review_hardening.py`, `tests/test_phase_2_5_code_review_cli.py`,
`tests/test_phase_2_5_code_review_workflow.py`, `tests/test_phase_2_5_code_review_safety.py`.

---

## Phase 2.6 Review-to-Action Proposal Workflow Status

Phase 2.6 review-to-action proposal workflow: `implemented_verified` for local CLI-only proposal
generation from deterministic review findings.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `ReviewActionProposal` model + deterministic `generate_action_proposals()` | `phase_2_6` | `implemented_verified` | `raiker/review/models.py`, `raiker/review/proposals.py` | `tests/test_phase_2_6_review_action_proposals.py` |
| `/review --propose-fixes` / `--proposals-only` CLI surface | `phase_2_6` | `implemented_verified` | `raiker/cli/commands.py`, `raiker/review/render.py` | `tests/test_phase_2_6_review_action_proposal_cli.py` |
| Proposal text/JSON rendering + metadata-only `review_proposals_created` event | `phase_2_6` | `implemented_verified` | `raiker/review/render.py`, `raiker/review/workflow.py` | `tests/test_phase_2_6_review_action_proposal_safety.py` |

Scope and boundaries:

- Phase 2.6 is proposal-only. No fixes are applied. No files are modified. No tests are run.
  No shell/process/network execution is used. No GitHub PR automation is implemented. No
  UI/API/IDE/dashboard/mobile surface is implemented. No model-assisted/semantic review is
  implemented. No Phase 3/4 runtime capability is enabled.
- Proposals are generated in memory from the (filtered) review findings and returned in
  `ReviewResult.action_proposals`. `--severity`/`--limit` filtering applies before proposal
  generation so proposals align with visible findings.
- No proposal contains raw diff, raw file contents, raw secrets, prompt text, private
  reasoning, chain-of-thought, or raw tool output.
- Every proposal that could change files has `requires_approval=True` and
  `would_modify_files=True`; info-only/no-action proposals have both false.
- `raiker/review/` (including `raiker/review/proposals.py`) does not import `subprocess`,
  `socket`, `requests`, `httpx`, `urllib`, or `asyncio`.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_2_6_review_action_proposals.py`,
`tests/test_phase_2_6_review_action_proposal_cli.py`,
`tests/test_phase_2_6_review_action_proposal_safety.py`,
`tests/test_pre_phase_3_readiness.py`.

Pre-Phase-3 readiness audit: `docs/IMPLEMENTATION_STATUS.md` records that Phase 1, Phase 2,
Phase 2.5, and Phase 2.6 are complete and that it is safe to start Phase 3 planning next. It does
not mark Phase 3 runtime activation complete; Phase 4 remains blocked.

---

## Phase 3 Slice A Proposal Lifecycle Foundation Status

Phase 3 Slice A proposal lifecycle foundation: implemented_verified for local metadata-only
proposal lifecycle tracking of review action proposals.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `ProposalLifecycleRecord` model + `ProposalLifecycleStore` | `phase_3_slice_a` | `implemented_verified` | `raiker/review/lifecycle.py`, `raiker/review/models.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_models.py`, `tests/test_phase_3_slice_a_proposal_lifecycle_storage.py` |
| `/review --propose-fixes --save-proposals` persists proposals | `phase_3_slice_a` | `implemented_verified` | `raiker/cli/commands.py`, `raiker/review/lifecycle.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_cli.py` |
| `/proposals` and `/proposal <proposal_id>` CLI surfaces | `phase_3_slice_a` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_cli.py` |
| Metadata-only proposal lifecycle events | `phase_3_slice_a` | `implemented_verified` | `raiker/review/lifecycle.py`, `raiker/contracts/models.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_safety.py` |

Scope and boundaries:

- Phase 3 Slice A is metadata-only; proposal-only; no proposal execution; no auto-fix; no patch
  application; no file mutation; no staging/unstaging; no test execution; no GitHub PR automation;
  no UI/API/IDE/dashboard/mobile; no approval execution; no Phase 4.
- `approval_execution_enabled` remains false. All disabled runtime flags remain false:
  plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.
- Lifecycle statuses are planning labels only: `proposed`, `acknowledged`, `deferred`,
  `rejected`, `superseded`. No status implies execution approval (`approved`,
  `approved_for_execution`, `ready_to_apply`, `execute` are deliberately excluded).
- No raw diff, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw
  tool output, or patch content is stored in records or event payloads.
- `raiker/review/` (including `raiker/review/lifecycle.py`) does not import `subprocess`,
  `socket`, `requests`, `httpx`, `urllib`, or `asyncio`. Lifecycle operations never mutate files,
  stages/unstages the Git index, commits, runs tests, applies fixes, or executes
  shell/process/network calls.
- This slice does not implement Phase 3 runtime execution, Phase 4, or any disabled runtime
  capability.

Evidence: `tests/test_phase_3_slice_a_proposal_lifecycle_models.py`,
`tests/test_phase_3_slice_a_proposal_lifecycle_storage.py`,
`tests/test_phase_3_slice_a_proposal_lifecycle_cli.py`,
`tests/test_phase_3_slice_a_proposal_lifecycle_safety.py`,
`tests/test_phase_3_slice_a_docs_truthfulness.py`.

Spec: `docs/IMPLEMENTATION_STATUS.md`.

## Phase 3 Slice B Approval Planning Preview Status

Phase 3 Slice B approval planning preview: `implemented_verified` for metadata-only approval
planning previews derived from saved proposal lifecycle records.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `ProposalApprovalPreview` model + `approval_preview_from_lifecycle_record()` | `phase_3_slice_b` | `implemented_verified` | `raiker/review/models.py`, `raiker/review/approval_preview.py` | `tests/test_phase_3_slice_b_approval_preview_models.py` |
| `ProposalApprovalPreviewStore` + `proposal_approval_previews` table | `phase_3_slice_b` | `implemented_verified` | `raiker/review/approval_preview.py`, `raiker/storage/migrations.py` | `tests/test_phase_3_slice_b_approval_preview_storage.py` |
| `/proposal <proposal_id> --approval-preview` CLI surface | `phase_3_slice_b` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_3_slice_b_approval_preview_cli.py` |
| `/approval-previews` and `/approval-preview <preview_id>` CLI surfaces | `phase_3_slice_b` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_3_slice_b_approval_preview_cli.py` |
| Metadata-only approval preview events | `phase_3_slice_b` | `implemented_verified` | `raiker/review/approval_preview.py`, `raiker/contracts/models.py` | `tests/test_phase_3_slice_b_approval_preview_safety.py` |

Scope and boundaries:

- Phase 3 Slice B is preview-only; no approval execution; no proposal execution; no auto-fix; no
  patch application; no file mutation; no staging/unstaging; no test execution; no GitHub PR
  automation; no UI/API/IDE/dashboard/mobile; no Phase 4.
- `approval_execution_enabled` remains false. `runtime_execution_enabled` remains false. All
  disabled runtime flags remain false: plugin_execution_enabled, graph_indexing_enabled,
  semantic_memory_writes_enabled, vector_writes_enabled, embedding_creation_enabled,
  approval_execution_enabled, approval_relay_runtime_enabled, cleanup_execution_enabled,
  rollback_execution_enabled, external_channels_enabled, notifications_enabled,
  remote_execution_enabled, container_execution_enabled, cloud_execution_enabled,
  process_execution_enabled, shell_execution_enabled, network_execution_enabled,
  runtime_execution_enabled.
- Preview statuses are planning labels only: `preview_created`, `needs_human_review`, `blocked`,
  `ready_for_planning`, `superseded`. No status implies execution approval.
- No raw diff, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw
  tool output, or patch content is stored in preview records or event payloads.
- `raiker/review/approval_preview.py` does not import `subprocess`, `socket`, `requests`, `httpx`,
  `urllib`, or `asyncio`. Preview operations never mutate files, stage/unstage the Git index,
  commit, run tests, apply fixes, or execute shell/process/network calls.

Evidence: `tests/test_phase_3_slice_b_approval_preview_models.py`,
`tests/test_phase_3_slice_b_approval_preview_storage.py`,
`tests/test_phase_3_slice_b_approval_preview_cli.py`,
`tests/test_phase_3_slice_b_approval_preview_safety.py`,
`tests/test_phase_3_slice_b_docs_truthfulness.py`.

Spec: `docs/IMPLEMENTATION_STATUS.md`.

### Local validation baseline (2026-06-19)

After Phase 3 Slice B approval planning preview:

| Check | Result |
|---|---|
| ruff | All checks passed |
| mypy | Success, 209 source files |
| pytest | TBD |
| validate_phase_status.py | passed |
| validate_repo_truthfulness.py | passed |

If dependency metadata tests fail after dependency changes, branch switching, or local environment
rebuilds, refresh local editable-install metadata with:

```bash
python -m pip install -e .
```

Do not commit generated metadata/cache files including `*.egg-info/`, `build/`, `dist/`,
`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, or virtual environments.

---

## Phase 7 Desktop, Web, Plugins Runtime, Graph Index, Semantic Memory, IDE Status

Phase 7 activates the runtime features deferred from Phase 3 (safe foundation/readiness slices A-P only were implemented). All execution remains policy-gated and approval-required.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-7001 Desktop app session model | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7101 Web API session model | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7201 Dashboard data parity | `specified_not_implemented` | — | Dashboard widgets require UI framework. |
| RAIKER-7301 Mobile apps | `specified_not_implemented` | — | Mobile apps require native build toolchain. |
| RAIKER-7401 Plugin runtime execution | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7501 Graph/codemap runtime indexing | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7601 Semantic/vector memory writes | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7701 IDE extension session model | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |

All execution remains policy-gated. No runtime is activated without explicit policy, approval, and audit.

---

## Phase 1 MVP Status

Post-restore audit note: the long-form Phase 1 build plan is restored and remains the detailed scope source for implemented/verified Phase 1 behavior. Later Slice G/H lifecycle metadata does not change Phase 1 runtime scope.

PR #6 added the initial Phase 1 MVP runtime core.
PR #8 reconciled documentation and version baseline.
PR #11 removed generated Python bytecode artifacts and strengthened .gitignore.

**Validation status (2026-06-17):** The full validation set was run on the `phase-1-runtime-core-validation-baseline` branch. All validation commands pass, event sequences are verified, and security invariants hold. The Phase 1 final acceptance criteria are met. See the validation PR for exact command outputs and artifact inspection results.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---:|---:|---|---|
| Python package scaffold | `phase_1_required` | `implemented_verified` | `docs/foundation/09_IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md` | import/package smoke |
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
|---|---|---:|---|
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
| Hosted model billing controls | Phase 5 | Budget records implemented; hosted providers remain policy-gated disabled. |
| Managed policies | Phase 5 | Implemented: managed deny wins over user/project/plugin allow. |
| Org/home-lab roles | Phase 5 | Implemented: users, roles, grants, session binding. |
| Audit export | Phase 5 | Implemented: export manifests, redaction, hash-chain integrity. |
| Plugin marketplace | Phase 5 | Implemented: checksum/signature verification, install records. |
| Hosted routines | Phase 5 | Implemented: metadata-only routine records; no execution. |
| Retention/backup | Phase 5 | Implemented: retention policies, legal hold, backup manifests. |

---

## Phase 2 Rich Local Workspace Status

Post-restore audit note: the long-form Phase 2 build plan is restored and remains the detailed scope source for implemented/verified Phase 2 behavior. Later Slice G/H lifecycle metadata depends on Phase 2 concepts but does not expand Phase 2 runtime authority.

PR #12 established the Phase 2 build plan, CI baseline, task manager, event viewer, checkpoint timeline, and inspection commands. This table tracks all Phase 2 capabilities.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---|---|---|---|
| Phase 2 build plan and status ledger | `phase_2_required` | `implemented_verified` | `docs/foundation/09_IMPLEMENTATION_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md` | doc consistency |
| CI baseline | `phase_2_required` | `implemented_verified` | `.github/workflows/ci.yml`, `docs/VERIFICATION_PLAN.md` | workflow syntax |
| Task record contract and storage helpers | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_task_manager.py` |
| Background task manager service | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | `tests/test_phase_2_task_manager.py` |
| Task lifecycle events and event indexing | `phase_2_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | task event tests |
| Event viewer query service | `phase_2_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_event_viewer.py` |
| Checkpoint timeline listing | `phase_2_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_checkpoint_timeline.py` |
| /status terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /tasks terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /events terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /checkpoints terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| Side-question child-turn contract | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | side-question contract tests |
| Read-only side-question runtime | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | side-question runtime tests |
| Interrupt/steer action contracts | `phase_2_required` | `implemented_verified` | `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` | interrupt contract tests |
| Safe-boundary interrupt handling | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | interrupt runtime tests |
| Approval inbox service | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | approval inbox tests |
| Approval terminal commands | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | terminal approval tests |
| Checkpoint restore/fork planning | `phase_2_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` | restore/fork tests |
| stat_path and diff_files tools | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | stat/diff tests |
| write_file/edit_file/apply_patch | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | file mutation approval tests |
| git status/diff/log wrappers | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | git wrapper tests |
| Local provider health-check | `phase_2_required` | `implemented_verified` | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | health check tests |
| Memory candidate listing | `phase_2_required` | `implemented_verified` | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` | memory candidate tests |
| Phase 2 integration validation | `phase_2_required` | `implemented_verified` | `docs/VERIFICATION_PLAN.md` | integration smoke tests |

---

## Phase 3 and Phase 4 Planning Status

Detailed Phase 3 and Phase 4 plans are now recorded in `docs/IMPLEMENTATION_STATUS.md` and `docs/IMPLEMENTATION_STATUS.md`. Safe foundations now include disabled/listable capability gates, plugin manifest validation without code execution, graph/codemap planning schemas, semantic-memory disabled status reporting, remote/container execution profiles, subagent planning, external-channel activation status, and terminal inspection commands. Tests prove these foundations are discoverable and remain non-executable until policy, storage, approval, and lifecycle controls are complete.

| Phase | Implemented foundation | Runtime state | Evidence |
|---|---|---|---|
| Phase 3 | Capability gates, `/capabilities`, plugin manifest validation, graph/codemap planning, semantic-memory status, `/semantic-memory` | Disabled/non-executing | `tests/test_phase_3_phase_4_implementation.py` |
| Phase 4 | Capability gates, `/execution-profiles`, remote/container execution planning, subagent planning, external-channel activation status | Disabled/non-executing | `tests/test_phase_3_phase_4_implementation.py` |

## Validation Evidence (2026-06-18)

**Local validation** was performed on `main` (no fixes needed — all checks passed):

| Aspect | Detail |
|---|---|
| **Date/time** | 2026-06-18 07:51 UTC |
| **OS** | Windows (PowerShell) |
| **Python version** | 3.13.5 |
| **Virtual environment** | `.venv` |
| **Commands run** | `ruff check .`, `mypy raiker apps tests`, `pytest`, `scripts/validate_phase_status.py`, `raiker --help`, `raiker --prompt "Hello Raiker"`, comprehensive smoke script |
| **Test result** | 93/93 passed |
| **Ruff** | All checks passed |
| **Mypy** | No issues (87 files) |
| **Phase status validation** | Passed |
| **Fixes made** | None — all checks passed on first run |
| **Phase 3 runtime disabled** | plugin_execution, graph_codemap_indexing, semantic_memory_writes all confirmed disabled |
| **Phase 4 runtime disabled** | external_channels, subagents, multi_agent_teams, remote_execution, container_execution all confirmed disabled |
| **Assessments** | Phase 1 and Phase 2 remain `implemented_verified`. Phase 3/4 safe foundations are correct, discoverable, tested, and non-executing. No runtime features were activated.|

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

## Phase 3 rollout slice A status — 2026-06-18

Phase 3 is **not complete**. The first rollout slice is `implemented_verified` after adding read-only workspace contract parity and plugin policy/registration planning.

| Slice | Status | Evidence |
|---|---:|---|
| RAIKER-3101 desktop/web/dashboard contract parity foundation | `implemented_verified` | `raiker/workspace/inspection.py`, `tests/test_phase_3_workspace_inspection.py`, `tests/test_phase_3_equal_workspace_clients.py` |
| RAIKER-3201 plugin execution policy boundary without execution | `implemented_verified` | `raiker/plugins/policy.py`, `raiker/plugins/registry.py`, `tests/test_phase_3_plugin_policy.py` |
| Phase 3 capability state model | `implemented_verified` | `raiker/phase_gates.py`, `tests/test_phase_3_capability_states.py` |
| Read-only CLI inspection commands | `implemented_verified` | `/workspace`, `/clients`, `/plugins`, `/plugin-plan <manifest_path>`, `tests/test_phase_3_terminal_commands.py` |

Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain non-executing.

## Temporary CI Pause — GitHub Actions quota exhausted

- GitHub Actions are temporarily paused or unavailable due run-limit/quota exhaustion.
- Local validation is mandatory while Actions are paused; use `docs/LOCAL_VALIDATION_GATE.md` as the source of truth for required commands and evidence.
- Full CI must be re-enabled before future release tagging or when quota becomes available.
- This is not a waiver of validation requirements.

## Phase 3 rollout slice B status — 2026-06-18

Phase 3 is **not complete**. Slice B adds the RAIKER-3501 read-only rich workspace view/API foundation while preserving all disabled runtime gates.

| Slice | Status | Evidence |
|---|---:|---|
| RAIKER-3501 read-only rich workspace view/API foundation | `implemented_verified` after local validation evidence is recorded | `raiker/workspace/views.py`, `tests/test_phase_3_workspace_views.py` |
| `/workspace-view` read-only CLI summary | `implemented_verified` after local validation evidence is recorded | `raiker/cli/commands.py`, `tests/test_phase_3_workspace_views.py` |

The view layer consumes the shared workspace inspection contract and renders deterministic text, JSON-safe, dashboard, client capability, and plugin plan summaries. It does not execute tools, create approvals, call models, write memory, execute plugin code, activate channels, start remote/container execution, or expose secret-like values.

Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain non-executing.

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

| `/workspace-view` safe terminal snapshot command | `implemented_verified` | `raiker/cli/commands.py`, `tests/test_phase_3_workspace_views.py` |

## 2026-06-18 Phase 3 Slice E — approval-preview UX/contracts

Status: `implemented_verified` locally for the Slice E contract surface only; full Phase 3 is not complete.

Slice E adds preview-only approval contracts for future graph/codemap indexing and semantic memory writes. The implementation exposes deterministic preview rendering, redaction of secret-like memory text, CLI preview commands, and workspace inspection summary fields.

Safety status:

- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- Previews are not approvals to execute; approving for later does not write memory or run indexing.
- No embeddings, vectors, background indexers, watchers, daemons, plugins, channels, remote execution, or container execution are activated.
- GitHub Actions remain paused due quota exhaustion; local validation evidence is mandatory and full CI must be re-enabled later when quota is available.

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

## Phase 3 Slice H lifecycle retention status

Slice H is `implemented_verified` locally for metadata-only retention policies, cleanup previews, approval-handoff planning, read-only summaries, and SQLite metadata tables. Full Phase 3 is still incomplete. Keep detailed contract and safety requirements in `docs/IMPLEMENTATION_STATUS.md`; this document records only the status summary. Slice H does not execute cleanup, graph/codemap indexing, semantic/vector memory writes, embeddings, rollback, plugins, channels, subagents, approval relay, or remote/container/cloud execution.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/IMPLEMENTATION_STATUS.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Phase 3 Slice J — Graph/Codemap Indexing Readiness Metadata

Slice J is `implemented_verified` for metadata-only readiness surfaces: deterministic contract, registry create/list/get/summary, read-only CLI, optional SQLite metadata table, workspace inspection/view fields, docs, and tests.

Slice J did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked. Graph/codemap runtime indexing, graph writes, workers, schedulers, file watchers, daemons, and runtime jobs remain disabled.


## Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only
- Adds deterministic metadata-only semantic memory readiness contracts, registry, optional SQLite metadata table, CLI, and workspace surfaces.
- Semantic memory writes, vector writes, embeddings, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled.
- Reserved Slice K metadata-only events: `phase3.semantic_memory_readiness.metadata_created`, `phase3.semantic_memory_readiness.summary_viewed`, `phase3.semantic_memory_readiness.exported`. No runtime memory write events are enabled.
- Slice K did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice L — Approval Preview Persistence Readiness — Metadata Only

Slice L is implemented as metadata-only readiness for future durable approval preview persistence. It adds `/approval-readiness [--summary|--json]`, deterministic `appr_` readiness contracts, optional `phase3_approval_preview_persistence_readiness` SQLite metadata storage, and workspace inspection/view fields. Approval execution, approval relay runtime, durable approval queues, approval workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice L did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.


## Phase 3 Slice M — Storage Cleanup Execution Readiness — Metadata Only

Implemented deterministic metadata-only readiness contracts, registry, optional SQLite metadata table, CLI surface, and workspace summaries for storage cleanup execution readiness. Cleanup execution, deletion, purge, tombstone, rollback, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice M did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice O — External Channels/Notifications Readiness — Metadata Only

Implemented metadata-only readiness contracts, registry operations, optional SQLite persistence, read-only `/channel-readiness` CLI output, and workspace summary fields for future external channels and notifications. No external channels, notifications, push notifications, share links, webhook dispatch, relay runtime, hosted channels/routines, workers, schedulers, watchers, daemons, or runtime execution are enabled. Slice O did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice P — Remote/Container/Cloud Execution Readiness — Metadata Only

Added metadata-only readiness contracts, registry operations, optional SQLite persistence, read-only `/remote-readiness` CLI output, and workspace summary fields for future remote/container/cloud execution. No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, or runtime execution are enabled.

## Phase 5 Governed Enterprise Status

Phase 5 adds managed governance, org roles, audit export, plugin marketplace, hosted routines, budget controls, retention, and backup. All runtime execution remains disabled.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-5001 Managed policy model | `implemented_verified` | `raiker/policy/engine.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_5_managed_policy.py` |
| RAIKER-5101 Org/home-lab roles | `implemented_verified` | `raiker/cli/commands.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_5_org_roles.py` |
| RAIKER-5201 Audit export and event integrity | `implemented_verified` | `raiker/events/export.py`, `raiker/events/integrity.py`, `raiker/cli/commands.py` | `tests/test_phase_5_audit_export.py` |
| RAIKER-5301 Plugin marketplace and signed trust | `implemented_verified` | `raiker/plugins/verify.py`, `raiker/plugins/policy.py`, `raiker/plugins/registry.py` | `tests/test_phase_5_plugin_marketplace.py` |
| RAIKER-5401 Hosted routines | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_5_hosted_budget_retention.py` |
| RAIKER-5501 Budget records | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_5_hosted_budget_retention.py` |
| RAIKER-5601 Retention and backup | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_5_hosted_budget_retention.py` |

All runtime execution remains disabled.

## Phase 6 Channels, Subagents, Remote Execution Status

Phase 6 adds external channel profiles, approval relay, subagent contracts, multi-agent team ledgers, remote execution profiles, and execution budgets. All execution remains disabled by default.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-6001 External channel connectors | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6101 Channel approval relay | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6201 Subagent contracts | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6301 Multi-agent teams | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6401 Remote/container execution | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6501 Execution budget | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |

Disabled runtime flags remain false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled, vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled, approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled, external_channels_enabled, notifications_enabled, remote_execution_enabled, container_execution_enabled, cloud_execution_enabled, process_execution_enabled, shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

## Phase 3 Completion Status

All Phase 3 slices A through P are implemented, tested, and documented. Phase 3 is now marked `implemented_verified` (this ledger is the canonical completion record; the former standalone `PHASE_3_COMPLETION_AUDIT.md` has been folded in here). **Phase 3 can be marked complete.** All runtime execution remains disabled. Phase 4 memory MVP is implemented. Remaining Phase 4 capabilities (external channels, subagents, multi-agent teams, remote/container/cloud execution) stay blocked: **Phase 4 remains blocked.**

### Current launchable UI & runtime truth

The current launchable UI is a local terminal client: a plain local terminal client only; Rich/native TUI is Phase 8 deferred. Previously this section referred to a Textual shell on an
interactive TTY, with a plain line-oriented CLI shell as the fallback (`RAIKER_TUI=plain`,
`--prompt`, or non-interactive stdin). Both route through the Agent Gateway, ToolBroker, and
PolicyEngine and add no runtime authority of their own. Desktop/Web/Dashboard/Mobile apps, IDE
extension, Voice, Browser Extension, and REST/API remain specified/deferred, not implemented as
launchable apps. Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P;
runtime execution remains disabled. Phase 4 memory MVP is implemented.

Runtime execution remains disabled.

### Phase 3 Slice A & B consolidated safety markers

These single-line markers are the canonical safety guarantees for the proposal-lifecycle (Slice A) and approval-planning-preview (Slice B) surfaces. They are intentionally unwrapped so tooling can assert them verbatim:

- Phase 3 Slice A proposal lifecycle foundation: implemented_verified. It is metadata-only and proposal-only with no proposal execution, no auto-fix, no patch application, no file mutation, no staging/unstaging, no test execution, no GitHub PR automation, no UI/API/IDE/dashboard/mobile, no approval execution, and no Phase 4; disabled runtime flags remain false.
- Phase 3 Slice B approval planning preview: implemented_verified. It is preview-only with no approval execution, no proposal execution, no auto-fix, no patch application, no file mutation, no staging/unstaging, no test execution, no GitHub PR automation, no UI/API/IDE/dashboard/mobile, and no Phase 4; disabled runtime flags remain false.

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter is hosted and requires egress plus budget policy; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled by default. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.


## Async model runtime status (verified)

Status labels used by Raiker are `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Raiker now uses the real `httpx` package (`httpx.AsyncClient`) for async OpenAI-compatible provider transport. The repository-local `httpx.py` shim was removed and must not be restored. The OpenAI SDK and Pydantic are not used by this runtime.

Dependency decision: `httpx` is required and used. `fastapi` is deferred because this change does not implement a Raiker API/server surface. `langchain` is deferred because no governed adapter is implemented and it must not bypass Raiker tool, policy, approval, or event contracts. `llama-index` is deferred because no governed retrieval/indexing adapter is implemented and it must not bypass Raiker memory or provenance policy.

llama.cpp, Ollama, LM Studio, vLLM, generic OpenAI-compatible endpoints, and OpenRouter are represented through Raiker-owned async model-provider contracts. llama.cpp is the local-first native profile via the async OpenAI-compatible path. OpenRouter is hosted and policy-gated: it requires explicit hosted policy, egress and budget policy metadata, HTTPS, and a non-empty API key environment variable.

The deterministic provider is `test_only`; production gateways and normal CLI runtime do not fall back to it. If no real provider is configured or usable, runtime fails safely with a `no_real_model_provider_available`/provider-policy style error instead of silently switching to a mock or hosted backend. No silent local-to-hosted fallback is implemented. Provider support is offline-tested with `httpx.MockTransport`; real provider validation requires an operator-provided server or API key and was not performed here.

UI model selection is session-scoped and persisted in the workspace SQLite store. `/model use` writes the selected profile, `/model current` reads it, `/models` marks it, and reasoning controls are capability-gated. Private chain-of-thought is never exposed; any reasoning summary must be labeled as a summary, not raw reasoning. Model events use safe metadata only and must not include prompts, completions, stream chunks, Authorization headers, API keys, file contents, or tool outputs.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Plain terminal client | Line-oriented terminal client with `/help`, `/commands`, slash-command routing, and prompt submission. Rich/native TUI is Phase 8 deferred. | Yes | No direct tool authority; prompts route through gateway/broker/policy. | Implement richer clients only in Phase 8. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |



Disabled runtime flags remain false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled, vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled, approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled, external_channels_enabled, notifications_enabled, remote_execution_enabled, container_execution_enabled, cloud_execution_enabled, process_execution_enabled, shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.


## Plain terminal client (implemented); Rich/native TUI deferred

Plain terminal client is `implemented_verified`: `raiker`, `raiker --prompt`, and `RAIKER_TUI=plain` route slash commands through `handle_slash_command()` and normal prompts through `submit_terminal_prompt()`. Rich/native TUI is Phase 8 deferred; the active Textual implementation and tests have been removed. All disabled runtime flags remain false.

---

## Phase 9 Advanced Memory & Graph Status

Phase 9 adds advanced memory and graph features: vector index, AST-based symbol extraction and dependency discovery, project-level graph extraction, and procedural-memory-to-skill-candidate conversion. All execution remains policy-gated and disabled by default.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-9001 Vector index (upsert, search, chunk, flush) | `implemented_verified` | `raiker/vector/__init__.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| RAIKER-9101 Graph indexer (AST symbol extraction, import deps) | `implemented_verified` | `raiker/graph/indexer.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| RAIKER-9201 Project graph extractor (module map, dep graph, skill suggestions) | `implemented_verified` | `raiker/graph/project_graph.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| RAIKER-9301 Skill candidate store (propose, review, generate) | `implemented_verified` | `raiker/skills/__init__.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| CLI commands (`/vector-index`, `/symbol-graph`, `/project-graph`, `/skill-candidates`) | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_9_advanced_memory_graph.py` |

All features are in-memory runtime modules with SQLite persistence for records. No external vector DB or LLM calls are required. All disabled runtime flags remain false.
