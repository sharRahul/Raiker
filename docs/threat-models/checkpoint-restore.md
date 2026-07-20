# Threat Model — Checkpoint Restore & Rewind (Workstream B)

> Status marker: B1 (pre-image capture) is implemented and integrated into the
> broker/relay mutation path. B2 (restore executor), B3 (fork), and B4
> (zero-trust escalation) are planned; this document is written to cover the
> whole workstream and is extended slice-by-slice. Sections marked **(B1)** are
> live today; sections marked **(planned)** describe the intended B2–B4 design
> and are not yet enforced in code.

Per-capability threat model for making Raiker checkpoints restorable. The safety
net is built bottom-up: B1 records the *pre-image* of every workspace-file
mutation so that a later restore (B2) can put a file back byte-for-byte, and so
that a restore — itself a mutation — is reversible in turn.

## What this capability is

### B1 — pre-image capture (live)

`raiker/checkpoints/capture.py::CheckpointCaptureService` records, for every
workspace-file mutation routed through `RuntimeAuthority.route_action()` — the
single chokepoint shared by direct broker writes and the Workstream A approval
relay — the pre-mutation state of the target file:

1. **Before** the file-mutating executor runs, `snapshot_pre_image` reads the
   target file's current bytes (resolving the path against the workspace root).
2. **After** the executor reports success, `commit` writes those bytes into a
   content-addressed blob store under `.raiker/checkpoints/objects/<aa>/<sha256>`
   (deduplicated, atomic temp-file + rename), and inserts a metadata-only row
   into the `checkpoint_capture_manifest` table mapping the mutation
   (`session_id`, `turn_id`, `action_id`, `capability`, `principal_id`,
   `workspace_path`) to the pre-image's content-address, size, and status.
3. A `checkpoint_captured` event is appended to the hash-chained log carrying
   **only metadata** — content-address, size, status, path — never file content.

`capture_status` is one of `captured` (pre-image blob stored — restorable),
`absent` (the file did not exist; a restore reverses the mutation by deleting
it), or `oversize` (the file exceeded the size cap and was not snapshot — the
row records this honestly so a later restore knows the file is not restorable
rather than silently corrupting it).

Only the two file-mutating Tier-1 capabilities — `file_write_execution` and
`patch_apply_execution` — are capture-eligible. Non-file mutations (memory,
shell, network, …) are not pre-image-captured (there is no workspace file to
snapshot).

### B2–B4 (planned)

`checkpoint_restore` will be an approval-required governed action (a mutation
itself) that dry-run-previews a metadata-only diff, then restores only files
recorded in a manifest, refusing any path outside the workspace, and writing its
own pre-image first. `plan_fork` will seed a new session from a checkpoint's
state summary with no file mutation. Restore is medium risk (auto-mode asks); a
restore touching files modified by a *different* principal since the checkpoint
escalates to high risk (B4), and — per F6(c) — a restore that would overwrite a
different principal's changes is a **critical** action routed to the human floor.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Governed entry only (B1) | Capture piggybacks on `route_action()`; it runs only where a mutation was already allowed to execute. It grants nothing and adds no new authority surface. |
| Never breaks the mutation (B1) | Capture is best-effort and fully isolated in `try/except` (`_snapshot_pre_image` / `_commit_pre_image`). A capture failure records a metadata-only `checkpoint_capture_failed` event and returns; it never fails, blocks, or alters the real mutation. |
| Workspace-scoped (B1) | The target path is resolved with `resolve_workspace_path`; a path that escapes the workspace root is not eligible for capture (and the executor that produced it would itself refuse it). Capture never reads or writes outside the workspace. |
| Content-addressed & tamper-evident (B1) | A blob's name **is** the SHA-256 of its bytes, so a stored pre-image can be re-verified against its address and identical pre-images deduplicate to one object. |
| Size-capped (B1) | Files larger than `MAX_PRE_IMAGE_BYTES` (8 MiB) are not snapshot; the manifest records `oversize` rather than pretending the file is restorable, bounding blob-store growth and read cost. |
| Metadata-only audit (B1) | Neither the manifest table nor the event log ever stores file content — only content-address, size, status, and path. File bytes live solely in the workspace-scoped blob store. |
| Only-on-success capture (B1) | The manifest row is written only after the executor reports `ok`, so a failed/blocked mutation (which changed nothing) leaves no spurious pre-image. |
| Append-only audit unaffected (scope) | Capture and (planned) restore never rewind the event log; the hash-chained history is append-only and is never rewritten. |

## Residual risks / non-goals

- **Oversize files are not restorable.** Above the cap, no pre-image exists; a
  future restore must surface this from the `oversize` status rather than
  attempt a partial restore. Recorded honestly, not silently dropped.
- **Blob-store growth.** Pre-images accumulate under
  `.raiker/checkpoints/objects/`. Garbage-collection of blobs no longer
  referenced by any live checkpoint is a later slice; today the store only
  grows (bounded per-object by the size cap).
- **Out of scope (workstream non-goals).** Restoring state outside the workspace
  (global config, SQLite history), rewinding the append-only event log, and
  cross-machine restore are explicitly not covered.
