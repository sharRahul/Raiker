# Local Validation Gate while GitHub Actions are paused

## Reason

GitHub Actions are temporarily paused because the Actions run limit/quota is exhausted.

During this period:

- GitHub CI is not the source of truth.
- No PR or branch should be considered validated unless local validation evidence is recorded.
- Developers must run the full validation set locally before merge or main push.
- The validation evidence must be copied into the PR body or `docs/IMPLEMENTATION_STATUS.md`.

This is a temporary infrastructure pause only. It is not a waiver of validation requirements, phase status rules, or runtime safety gates.

## Required local validation commands

Run the full set from a clean virtual environment before merge or any main push:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
raiker --help
raiker --prompt "Hello Raiker"
```

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
12. Statement that GitHub Actions are paused due quota and must be re-enabled later

## Re-enable requirement

Restore `pull_request` and `push` triggers for the CI and Phase Status Validation workflows when Actions quota is available again. Full CI must be re-enabled before future release tagging.

## Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.
