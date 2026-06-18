# Phase 2 Rich Local Workspace Build Plan

This plan decomposes Raiker Phase 2 into small implementation tasks suitable for local or cloud builder models.

The Phase 2 objective:

```text
Build a rich local workspace on top of the Phase 1 runtime core, adding task management, event inspection, checkpoint timeline, status/approval UX, side questions, interrupt/steer controls, local model provider discovery, governed memory views, and inspection commands — without making the terminal/TUI the privileged or canonical interface.
```

All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. Phase 2 may expand the terminal/TUI first, but no code, contract, event, policy rule, storage table, or runtime path may describe the terminal client as the only primary human interface or grant it a private bypass path.

---

## Phase 2 Status Vocabulary

| Status | Meaning | Builder action |
|---|---|---|
| `phase_2_required` | Required for the Phase 2 scope. | Build in Phase 2 task order. |
| `specified_not_implemented` | The behaviour is documented, but code is not present yet. | Implement only through a named task and tests. |
| `implemented_verified` | Code and tests satisfy the acceptance criteria for the active change set. | Keep stable; regressions must fail CI. |
| `blocked_by_spec_gap` | Required behaviour is not detailed enough to implement safely. | Update docs before code. |

---

## Phase 2 Alignment Rules

### Phase Scheduling Rule
Phase 3+ features (Desktop UI, Web UI, Dashboard, mobile apps, plugins, graph/codemap, vector memory writes, external channel wiring, remote execution, subagents) must remain disabled. Phase 2 does not wire those features into active behaviour.

### Equal Primary Interface Rule
All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. Phase 2 may expand the terminal/TUI first, but it must not become the privileged or canonical interface.

### Version Rule
Version remains `0.0.0` until all Phase 1 and Phase 2 patch increments (`0.0.1` through `0.0.99`) are consumed.

### CI Gate Rule
Every implementation PR must pass CI before merging. See `.github/workflows/ci.yml`.

---

## Phase 2 Task IDs

| Task ID | Title | Slice |
|---|---|---|
| RAIKER-1001 | Phase 2 status ledger and build-plan setup | Foundation |
| RAIKER-1002 | CI baseline and validation gate | Foundation |
| RAIKER-1101 | Task record contract and storage helpers | Task management |
| RAIKER-1102 | Background task manager service | Task management |
| RAIKER-1103 | Task lifecycle events and event indexing | Task management |
| RAIKER-1201 | Side-question child-turn contract | Side questions |
| RAIKER-1202 | Read-only side-question runtime path | Side questions |
| RAIKER-1301 | Interrupt, pause, cancel, and steer action contracts | Interrupt/steer |
| RAIKER-1302 | Safe-boundary interrupt handling | Interrupt/steer |
| RAIKER-1401 | Approval inbox query/list/resolve service | Approvals |
| RAIKER-1402 | Approval slash commands and action-bound approval resolution | Approvals |
| RAIKER-1501 | Checkpoint timeline listing | Checkpoints |
| RAIKER-1502 | Checkpoint restore/fork planning path, restore disabled until approved | Checkpoints |
| RAIKER-1601 | Event viewer query service | Event viewer |
| RAIKER-1602 | /events terminal command | Event viewer |
| RAIKER-1701 | /status and /tasks terminal commands | Terminal commands |
| RAIKER-1801 | stat_path and diff_files tools | File tools |
| RAIKER-1802 | write_file/edit_file/apply_patch proposal path with snapshot and approval | File tools |
| RAIKER-1901 | git status/diff/log wrappers with policy | Git wrappers |
| RAIKER-2001 | Local provider health-check abstraction | Model providers |
| RAIKER-2002 | Ollama profile detection, disabled unless provider is available | Model providers |
| RAIKER-2101 | Memory candidate listing and governed memory status view | Memory |
| RAIKER-2201 | Phase 2 integration validation and status update | Validation |

---

## Phase 2 Dependency Graph

```text
RAIKER-1001 Phase 2 plan
  -> RAIKER-1002 CI baseline
    -> RAIKER-1101 task contract and storage
      -> RAIKER-1102 task manager
        -> RAIKER-1103 task events and indexing
    -> RAIKER-1601 event query service
```

---

## Phase 3 Slice G impact on Phase 2

Phase 3 Slice G does not expand Phase 2 runtime scope. Phase 2 memory candidate listing, event viewer, task manager, approval inbox, checkpoint timeline, and file mutation proposal paths remain the only active Phase 2 local workspace features.

Slice G depends on Phase 2 concepts but does not retroactively change them:

- Task/event inspection informs lifecycle views, but lifecycle status changes are metadata-only.
- Approval inbox concepts inform future lifecycle approval handoff, but Slice G records are not executable approvals.
- Checkpoint and rollback planning concepts inform lifecycle summaries, but rollback execution remains disabled.
- Memory candidate listing informs semantic-memory lifecycle metadata, but semantic/vector writes and embeddings remain disabled.
- SQLite migrations may create metadata tables, but no Phase 2 storage path may write graph nodes, graph edges, vectors, embeddings, or durable semantic-memory records.

Phase 2 builders touching lifecycle-adjacent code must read `docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md` first and must preserve all disabled runtime gates.
