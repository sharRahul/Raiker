# Checkpointing And Rewind Specification

Raiker checkpoints provide local recovery, rewind, resume, fork, and auditability for agent work.

Checkpoints are not a replacement for Git, backups, or source control. They are a local agent-runtime safety mechanism.

> **Code status, 2026-08-23. This document is the design target; two of its five
> verbs are not reachable by an owner.**
>
> - **Capture — implemented and automatic.** A pre-image is written before every
>   approved mutation (`raiker/checkpoints/capture.py`), and the gateway records a
>   turn checkpoint (`checkpoint_created`). Deep Windows paths were made
>   reversible in FIXED-240.
> - **Fork — implemented.** A conversation forks from a checkpoint through
>   `POST /api/checkpoints/{id}/branch`, with a lineage band naming the source
>   conversation (FIXED-227). `/checkpoints fork` runs directly because a fork
>   mutates no workspace file.
> - **Restore — executor built, surface absent.** `CheckpointRestoreExecutor`
>   (`raiker/runtime/executors/tier1_checkpoint.py`) recomputes the plan from the
>   capture manifest at execution time, refuses any path outside the workspace,
>   and captures its own pre-image so a restore would itself be reversible. It is
>   registered and covered by `tests/test_checkpoint_restore.py`. **No route,
>   terminal command or model tool proposes a restore.** `/checkpoints restore`
>   and the Checkpoints view both compute a preflight and perform nothing, and
>   `checkpoint_restore_execution` is not in `EXECUTABLE_ON_APPROVAL`, so an
>   approval would not relay one either.
> - **The restore events below are specified, not emitted.**
>   `checkpoint_restore_requested`, `checkpoint_restore_approved`,
>   `checkpoint_restored`, `checkpoint_restore_failed` and
>   `checkpoint_restore_planned` are all declared in `EVENT_TYPES` and none has a
>   call site. The restore path emits nothing today because nothing reaches it.
> - **The rich TUI in §"Rich TUI" is not built.** The launchable clients are the
>   plain terminal client and the web dashboard.
>
> Closing the restore gap is the highest-priority, lowest-effort item in
> [the backlog](REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).

---

## Checkpoint Goals

Raiker checkpoints must support:

1. restoring session state;
2. restoring task state;
3. restoring file-edit snapshots where configured;
4. comparing before/after changes;
5. forking from a previous state;
6. summarising a checkpoint;
7. cleaning up old snapshots;
8. linking checkpoints to event logs;
9. audit and provenance;
10. safe TUI rewind UX.

---

## Checkpoint Types

| Type | Purpose |
|---|---|
| `turn_checkpoint` | Created after each completed turn. |
| `tool_checkpoint` | Created before risky file/tool action. |
| `file_snapshot` | Captures file content before edit/write/delete. |
| `task_checkpoint` | Captures background task state. |
| `session_checkpoint` | Captures session-level state. |
| `manual_checkpoint` | User-requested checkpoint. |
| `fork_checkpoint` | Created when user forks from previous state. |

---

## Checkpoint Lifecycle

```text
checkpoint_requested
  -> collect runtime state
  -> collect task state
  -> collect changed-file metadata
  -> snapshot files if required
  -> write checkpoint manifest
  -> emit checkpoint_created event
```

Restore lifecycle:

```text
restore_requested
  -> validate checkpoint
  -> show restore plan
  -> request approval if files will change
  -> pause active tasks
  -> restore state/files
  -> emit checkpoint_restored event
  -> resume or stop as requested
```

Fork lifecycle:

```text
fork_requested
  -> validate checkpoint
  -> create new session or worktree if configured
  -> copy checkpoint state
  -> emit session_forked event
```

---

## Checkpoint Manifest Schema

```json
{
  "schema_version": "1.0",
  "checkpoint_id": "ckpt_01H...",
  "checkpoint_type": "turn_checkpoint",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "task_id": null,
  "created_at": "2026-06-17T12:00:00Z",
  "created_by": "checkpoint_service",
  "summary": "Listed project files and answered user.",
  "last_event_id": "evt_01H...",
  "runtime_state": "CLOSED",
  "files": [
    {
      "path": "README.md",
      "snapshot_id": "snap_01H...",
      "sha256_before": "...",
      "sha256_after": "...",
      "change_type": "modified"
    }
  ],
  "artifacts": [],
  "memory_candidates": [],
  "restore_policy": {
    "can_restore_state": true,
    "can_restore_files": true,
    "requires_approval": true
  }
}
```

---

## File Snapshot Rules

Create file snapshots before write file, edit file, delete file, apply patch, bulk refactor, generated file overwrite, and package/config file mutation.

Do not snapshot large files above configured size unless allowed, binary files unless explicitly enabled, secrets unless secure storage/redaction is configured, or ignored directories such as `.git`, `node_modules`, virtualenvs, and caches.

---

## Restore Modes

| Mode | Behaviour |
|---|---|
| `state_only` | Restore runtime/session/task state only. |
| `files_only` | Restore file snapshots only. |
| `state_and_files` | Restore both. |
| `fork_only` | Create new branch/session without touching current state. |
| `summarise_only` | Show summary and diff only. |

---

## Rewind UX Requirements

Rich TUI must show checkpoint timeline, checkpoint summary, files changed, event range, risk warning, diff preview, restore mode choices, approval requirement, and rollback outcome.

User must be able to inspect checkpoint, compare checkpoints, restore, fork, export, delete/clean up, and ask side questions about checkpoints without stopping active work.

---

## Session Resume

Resume must load session metadata, load latest checkpoint, load event log pointer, reconstruct task list, mark interrupted tasks as recoverable/failed/paused, ask user before resuming risky pending actions, and never auto-run local commands or network actions after resume without fresh approval.

---

## Session Fork

Fork creates a new session lineage:

```json
{
  "new_session_id": "sess_new",
  "parent_session_id": "sess_old",
  "forked_from_checkpoint_id": "ckpt_01H...",
  "reason": "Try an alternate implementation approach"
}
```

Phase 2 implements session-only fork. Phase 3 implements optional Git branch/worktree fork according to the execution profile and worktree isolation rules.

---

## Cleanup And Retention

Checkpoint retention policy must support max checkpoints per session, max storage size, max age, keep manual checkpoints, keep checkpoints linked to unresolved tasks, and secure deletion for sensitive snapshots where available.

---

## Checkpoint Events

Required events:

- `checkpoint_requested`
- `checkpoint_created`
- `checkpoint_failed`
- `checkpoint_inspected`
- `checkpoint_compare_requested`
- `checkpoint_restore_requested`
- `checkpoint_restore_approved`
- `checkpoint_restored`
- `checkpoint_restore_failed`
- `checkpoint_fork_requested`
- `session_forked`
- `checkpoint_deleted`
- `checkpoint_cleanup_completed`

---

## Checkpoint Security Requirements

- Snapshots may contain sensitive data.
- Snapshot storage path must be local and access-controlled where possible.
- Secrets must be redacted or snapshot skipped according to policy.
- Restore must show diff before file mutation.
- Restore must require approval if files change.
- Checkpoints must not be sent to remote model providers unless explicitly allowed.

---

## Testing Requirements

Tests must prove:

- checkpoint manifest writes correctly;
- latest checkpoint can be loaded;
- file snapshot captures before-edit content;
- restore requires approval for file changes;
- state-only restore does not change files;
- fork creates new session lineage;
- local command/network pending actions do not auto-run after resume;
- cleanup preserves manual checkpoints;
- Git branch/worktree fork is unavailable until Phase 3 execution profile is configured.
