> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

# Local Validation Gate while hosted CI quota is unreliable

> Current truth (2026-06-21): the launchable local UIs are the plain local terminal client and the local web dashboard (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only; read-only governed views + governed prompt/turn/approval/runtime-mutation flows where approval resolution is metadata-only; adds no authority of its own). Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST/API clients are Phase 8 deferred, specified but not implemented. Phase 3 is complete only for safe foundation/readiness slices A-P; Phase 4 memory MVP is implemented; Phase 5-7 remain metadata/readiness/contract surfaces unless code and tests explicitly prove runtime behavior. Runtime execution remains disabled for plugin execution, graph indexing, semantic/vector writes, embeddings, approval execution/relay, cleanup/rollback execution, external channels/notifications, remote/container/cloud/process/shell/network execution.


## Reason

CI triggers are configured, but hosted CI may stay red or unavailable because the Actions run limit/quota is exhausted.

During this period:

- Hosted GitHub CI is not the sole source of truth while quota prevents reliable hosted runs.
- Local validation evidence is required while quota prevents reliable hosted runs.
- Developers must run the full validation set locally before merge or main push.
- The validation evidence must be copied into the PR body or `docs/IMPLEMENTATION_STATUS.md`.

Security documentation changes must also keep [`docs/SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md) linked and truthfully separated between implemented, metadata/readiness, specified/deferred, and missing controls.

This is a temporary infrastructure pause only. It is not a waiver of validation requirements, phase status rules, or runtime safety gates.

## Required local validation commands

Run the full set from a clean virtual environment before merge or any main push:

```bash
python -m ruff check .
python -m mypy .
python -m pytest
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/validate_runtime_enablement_readiness.py
python scripts/validate_local_single_user_runtime.py
python scripts/validate_documentation_truthfulness.py
python -m compileall raiker
raiker --workspace . --prompt "status"
raiker --workspace . --prompt "/status"
raiker --workspace . --prompt "/capabilities"
raiker --workspace . --prompt "/memory-readiness"
raiker --workspace . --prompt "/plugin-readiness"
raiker --workspace . --prompt "/cleanup-readiness"
```

## Local web dashboard validation (apps/web + raiker-web)

The local web dashboard is a launchable surface (single-user, `127.0.0.1` only). Run the frontend
gate from `apps/web` before merge:

```bash
npm --prefix apps/web ci            # or: npm --prefix apps/web install
npm --prefix apps/web run lint
npm --prefix apps/web run check     # svelte-check / tsc
npm --prefix apps/web run test      # vitest (component, a11y, contract, security-regression UI guards)
npm --prefix apps/web run build
```

Backend routes the dashboard depends on are covered by `pytest` (`tests/test_api_*.py`,
`tests/test_security_regression_ui.py`, `tests/test_api_contract_schemas.py`). To smoke the running
server locally (loopback only — never expose it):

```bash
raiker-web --workspace . --host 127.0.0.1 --port 8765   # serves the governed local API
# then, in another shell, mint a token and read a governed view:
curl -s -XPOST 127.0.0.1:8765/api/auth/session -H 'content-type: application/json' -d '{}'
curl -s 127.0.0.1:8765/api/diagnostics -H "authorization: Bearer <token>"
# serve the built SPA for a full UI smoke (read-only views, prompt stream, approvals, security settings):
npm --prefix apps/web run preview
```

Web dashboard truths to keep honest during smoke: read views render real backend state only;
approval resolution is metadata-only (`executes_action=false`); disabled/deferred and sensitive-domain
capabilities are not enableable; runtime mutations go through step-up auth and the governed
`RuntimeAuthority`; the STOP switch cancels at the next safe boundary and is human-only.

For Phase 3 rollout branches, also run manual or scripted smoke coverage for:

```text
/help
/status
/capabilities
/semantic-memory
/execution-profiles
/workspace
/clients
/plugins
/plugin-plan
/graph-status
/graph-plan
/memory-review
/memory-review --summary
/approval-previews
/graph-approval-preview
/memory-approval-preview --summary
/approval-audit
/approval-audit --summary
/rollback-plan
/graph-rollback-plan
/memory-rollback-plan
/storage-lifecycle
/storage-lifecycle --summary
/storage-lifecycle --graph
/storage-lifecycle --memory
/doctor
/proposal <known_proposal_id> --approval-preview
/approval-previews --json
/approval-previews --status needs_human_review
/approval-previews --limit 1
/approval-preview <known_preview_id>
/approval-preview <known_preview_id> --json
```

## Phase 3 Slice G validation additions

For any branch that changes storage lifecycle metadata, lifecycle registry behavior, lifecycle workspace summaries, storage migrations, lifecycle CLI rendering, graph/memory/audit/rollback conversions, or related docs, validation evidence must include:

```bash
python -m pytest tests/test_phase_3_storage_lifecycle.py
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python scripts/validate_phase_status.py
```

Required Slice G smoke assertions:

- `/storage-lifecycle` renders read-only lifecycle metadata.
- `/storage-lifecycle --summary` renders aggregate counts and disabled runtime write flags.
- `/storage-lifecycle --graph` states graph/codemap runtime indexing remains disabled.
- `/storage-lifecycle --memory` states semantic/vector writes and embeddings remain disabled.
- SQLite migrations create only metadata lifecycle tables and lifecycle metadata event tables.
- No graph node/edge tables are introduced by Slice G.
- No vector/embedding tables are introduced by Slice G.
- Lifecycle expire/supersede operations are metadata status changes only.
- Workspace inspection and workspace views include lifecycle summaries without activating runtime writes.

## Required evidence format

Record this evidence in the PR body or `docs/IMPLEMENTATION_STATUS.md`:

1. Branch and commit tested
2. OS
3. Python version
4. Virtual environment
5. Commands run
6. Test result totals
7. CLI smoke results
8. Confirmation that the following remain disabled:
   - plugin execution
   - graph/codemap runtime indexing
   - graph node/edge writes
   - semantic/vector memory writes
   - embedding generation/storage
   - rollback execution
   - external channels
   - subagents
   - multi-agent teams
   - remote execution
   - container execution
   - hosted routines and marketplace installs
9. Files changed
10. Commit SHA
11. Remaining risks
12. Statement that CI triggers are configured, hosted CI may be red/unavailable due quota, local validation evidence is required, and `phase-status.yml` remains manual if still true

## Documentation alignment validation

When updating documentation to reflect backend changes (e.g., Runtime Authority, AI roles, domain scopes, risk acceptance model, expanded capability gates, strict enforcement), validate that:

- Runtime readiness is stated as `runtime_enablement_candidate`, not `production_ready_runtime`.
- Strict enforcement status is documented (strict non-allow blocking, /role revoke governed, capability gate per action enforced, risk acceptance enforced before execution).
- Runtime mode activation is stated as `controlled_runtime_mode_activation_implemented`, not production-enabled.
- No document claims production runtime enablement, approval execution relay enabled, or broad runtime execution active.
- Admin mutation governance (`_govern_admin_mutation`) is referenced where CLI commands describe their authority path.
- The AI-executable roles and human-only role protections are documented consistently across all docs.
- Controlled runtime mode activation states that human `runtime_gate_manager` can activate `local_single_user_runtime` and enable `admin_mutation`/`role_mutation`; AI cannot activate runtime modes or capability gates.

Run `python scripts/validate_runtime_enablement_readiness.py` after any authority-related changes.

## Re-enable requirement

Keep `pull_request` and `push` triggers for CI configured. If `phase-status.yml` remains `workflow_dispatch`-only, keep that manual status explicit. Hosted CI must be made reliable again before future release tagging when Actions quota is available.

## Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/IMPLEMENTATION_STATUS.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/IMPLEMENTATION_STATUS.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Plain terminal shell/status rendering only; Rich/native TUI panels are Phase 8 deferred. | Plain-only | None. | Build panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Launchable local web dashboard: `apps/web` Svelte SPA over the `raiker-web` loopback API. Read-only governed views + governed prompt/turn/approval/runtime-mutation flows (approval resolution metadata-only); single-user, `127.0.0.1` only. | Yes | No direct tool authority; routes through gateway/RuntimeAuthority/broker exactly as the CLI. | Keep API-contract + frontend test parity; broader client surfaces stay deferred. |
| Dashboard | Read-only governed views are part of the local web dashboard above (capabilities, runtime mode, models, diagnostics). Standalone native/mobile dashboards remain Phase 8 deferred. | Yes (web) | None beyond the governed API. | Implement standalone dashboard apps after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |

---

## Editable install metadata refresh

If dependency metadata tests fail after dependency changes, branch switching, or local environment
rebuilds, refresh local editable-install metadata:

```bash
python -m pip install -e .
```

Do not commit generated metadata/cache files, including `*.egg-info/`, `build/`, `dist/`,
`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, or virtual environments.

## Phase 3 Slice B validation additions

For any branch that changes approval planning preview behavior, storage, CLI, events, or related
docs, validation evidence must include:

```bash
python -m pytest tests/test_phase_3_slice_b_approval_preview_models.py tests/test_phase_3_slice_b_approval_preview_storage.py tests/test_phase_3_slice_b_approval_preview_cli.py tests/test_phase_3_slice_b_approval_preview_safety.py tests/test_phase_3_slice_b_docs_truthfulness.py
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python scripts/validate_phase_status.py
```

Required Slice B smoke assertions:

- `/proposal <proposal_id> --approval-preview` renders an approval planning preview.
- `/approval-previews --json` returns parseable JSON.
- `/approval-preview <preview_id>` shows one preview.
- Approval preview records are metadata-only; no raw diff, file contents, or secrets.
- `approval_execution_enabled: False`, `runtime_execution_enabled: False`.
- All disabled runtime flags remain false.

## Latest confirmed local green baseline (2026-06-19)

After Phase 3 Slice B approval planning preview:

| Check | Result |
|---|---|
| ruff | All checks passed |
| mypy | Success, 209 source files |
| pytest | TBD |
| validate_phase_status.py | passed |
| validate_repo_truthfulness.py | passed |



## Raiker TUI smoke

Run the Raiker TUI smoke commands locally (hosted Actions may stay red/unavailable):

```text
python -m pytest tests/test_phase_3_slice_q1_rich_tui_command_access.py
raiker --prompt "Hello Raiker"
raiker --prompt "/help"
RAIKER_TUI=plain raiker --prompt "/help"
```

The opt-in real-provider integration test (`Phase 8 real-provider UI integration tests (deferred)`) is skipped without the required env vars. `approval_execution_enabled: False` and `runtime_execution_enabled: False` remain unchanged; all disabled runtime flags remain false.
