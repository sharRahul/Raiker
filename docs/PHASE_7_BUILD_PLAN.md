# Phase 7 Build Plan — Desktop, Web, Mobile, Plugins Runtime, Graph/Codemap, Semantic Memory

Phase 7 activates the runtime features deferred from Phase 3 (safe foundation/readiness slices A-P only were implemented). This includes Desktop UI, Web UI, Dashboard, Mobile apps, plugin runtime execution, graph/codemap runtime indexing, and semantic/vector memory writes.

Phase 7 builds on all prior phases' governance, policy, approval, storage, and validation foundations.

---

## Dependency Graph

```text
RAIKER-7001 Desktop UI application shell
  -> RAIKER-7101 Web UI and REST API server
  -> RAIKER-7201 Dashboard widgets and data parity
  -> RAIKER-7301 Mobile apps (Apple + Android)
  -> RAIKER-7401 Plugin runtime execution
  -> RAIKER-7501 Graph/codemap runtime indexing
  -> RAIKER-7601 Semantic/vector memory writes
  -> RAIKER-7701 IDE extension
```

---

## Tasks

| Task ID | Scope | Contracts/events/storage | Policy | Tests | Acceptance criteria |
|---|---|---|---|---|---|
| RAIKER-7001 | Desktop UI application shell | Desktop app events, session binding | Gateway-only client access | Desktop smoke tests | Desktop app launches, connects to gateway, renders workspace. |
| RAIKER-7101 | Web UI and REST API | Web events, REST contracts, auth | CSRF, CORS, session auth | Web/API tests | Web client and REST API use same gateway; auth required for remote. |
| RAIKER-7201 | Dashboard widgets | Widget events, data contracts | Read-only by default | Dashboard tests | Dashboard shows tasks, approvals, memory, graph, storage, execution, channels, models, security. |
| RAIKER-7301 | Mobile apps | Mobile events, push contracts | Stale-state rejection | Mobile tests | Mobile app submits prompts, approvals, and checkpoints; stale state cannot approve. |
| RAIKER-7401 | Plugin runtime execution | Plugin execution events, job records | Trust + permission + approval | Plugin execution tests | Plugin code executes only after manifest validation, trust review, permission diff, and approval. |
| RAIKER-7501 | Graph/codemap runtime indexing | Graph node/edge events, index records | Policy-gated; no destructive writes | Graph indexing tests | Graph indexes workspace code; queries return symbol/test/dependency data. |
| RAIKER-7601 | Semantic/vector memory writes | Embedding events, vector records | Sensitivity filters; approval required | Semantic memory tests | Semantic memory writes are approved, sensitive-filtered, and auditable. |
| RAIKER-7701 | IDE extension | Extension transport, auth contracts | Gateway-only; no direct tool authority | IDE extension tests | IDE extension connects to gateway; all actions route through policy. |

---

## Storage requirements

Allowed Phase 7 storage categories:

- desktop/web/mobile session state;
- REST API tokens and auth sessions;
- plugin execution jobs and results;
- graph/codemap nodes, edges, and indexes;
- vector/embedding records;
- IDE extension state.

---

## Validation requirements

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
```

Phase 7 tests must prove:

- Desktop/Web/Mobile/IDE clients call gateway only;
- plugin execution requires trust, permission diff, and approval;
- graph indexing produces queryable symbol/test/dependency data;
- semantic memory writes respect sensitivity filters;
- stale mobile state cannot approve actions;
- all enabled interfaces share the same gateway, policy, events, and session state.

---

## Completion rule

Phase 7 is not complete until all runtime features from Phase 3 of the full blueprint are implemented, tested, and documented. All execution must remain policy-gated and approval-required.
