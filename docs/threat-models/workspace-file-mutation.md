# Threat model — workspace file mutation (`file_write_execution`, `patch_apply_execution`)

These two capabilities are what Build's premise rests on: **approving a file
change really writes it**. Both are in
[`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py). They are the
original members of that set, and the repository-wide analysis in
[`../THREAT_MODEL.md`](../architecture/THREAT_MODEL.md#tier-1-executors-approval_execution_relay-file_write_execution-patch_apply_execution)
covers the relay they share; this page is the per-capability document the
step-up acknowledgement points at.

## What the capabilities do

`raiker/runtime/executors/tier1_files.py`:

- **`file_write_execution`** — behind `write_file`, `edit_file` and
  `create_document`. Resolves the path through
  `resolve_writable_workspace_path` and writes UTF-8 text.
- **`patch_apply_execution`** — behind `apply_patch`. Applies **one unified diff**
  as **one approval and one reversible change set**, which may cover several
  files including creates and deletes.

## Containment, exactly

`raiker/tools/filesystem.py`:

- Every mutating path goes through `resolve_writable_workspace_path`, never
  through the read-only resolver, so confinement and the protected-directory
  refusal cannot drift apart.
- The path is resolved (`resolve(strict=False)`, which follows symlinks) and must
  be `relative_to` the resolved workspace root, or the call fails with
  `outside_workspace`.
- The workspace root itself and anything under `PROTECTED_WORKSPACE_DIRS` —
  **`.raiker` and `.git`** — fail with `protected_workspace_path`. The agent
  cannot write the encrypted store or rewrite git history.

## Checkpoint capture, exactly

`raiker/checkpoints/capture.py` snapshots the pre-image **before** the write, into
a content-addressed blob store. Three outcomes are recorded, and the difference
between them matters:

| `capture_status` | Meaning |
|---|---|
| `captured` | Pre-image blob stored; the change is restorable |
| `absent` | The file did not exist; a restore means delete |
| `oversize` | The file exceeded `MAX_PRE_IMAGE_BYTES` (8 MiB); **not restorable** |

Blobs are content-addressed by SHA-256 and deduplicated, and the address is
**re-verified on read** — a blob whose bytes no longer hash to its name is not
returned.

`CAPTURE_PATH_ARG` names exactly these two capabilities. Other relayed mutations
are not pre-image-captured: a `git_commit` is git history rather than a file the
checkpoint store holds a pre-image of, and the approval notice says so instead of
promising a rewind it cannot give.

## Patch matching, exactly

- Matching tries the **exact text first**; when that finds nothing, the same
  search runs again ignoring **trailing whitespace and indentation style**, and
  the file keeps its own indentation rather than adopting the quote's.
- **Uniqueness does not relax.** An edit requires exactly one match; a relaxed
  search that hits two places is refused, so the tolerance can never land an edit
  somewhere it was not meant to.
- Interior spacing is text, not formatting: `a + b` and `a+b` remain a mismatch.
- A section that edits or deletes must name a text file that already exists
  inside the workspace; one that creates must name a path that does not; a patch
  naming the same file twice is rejected before anything is written.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| Writing outside the workspace, including via `..` or an absolute path | `resolve_workspace_path` → `outside_workspace` | `filesystem.py` |
| Writing the encrypted store or git internals | `PROTECTED_WORKSPACE_DIRS` → `protected_workspace_path` | `filesystem.py` |
| A symlink inside the workspace pointing out of it | The path is fully resolved *before* the containment check, so the link's target is what is tested | `filesystem.py` |
| The diff changing between review and execution | Arguments-hash check against the immutable intent snapshot | `tier1_approval.py` |
| One approval writing twice | Atomic `pending → executing → executed` claim | `store.claim_approval_for_execution` |
| Execution after the approving session was revoked | Posture check → `posture_degraded` | `raiker/runtime/authority/posture.py` |
| A partially applied patch leaving the tree inconsistent | There is no partial application — one bad hunk fails the whole proposal | `raiker/tools/filesystem.py` |
| A half-written pre-image blob | Blobs are written to a temporary name and `replace`d atomically | `capture.py` |
| A stale code map sending the next turn to a moved line | The map is refreshed for the touched paths at this one point, best-effort and strictly after the write | `tier1_approval.py` |
| The approval saying more than the write will do | The notice is derived from what the server will actually do — both gates are consulted, and either being off returns the approval to metadata-only *before* the owner decides | `raiker/control/dashboard.py` |

## Residual risk, stated plainly

- **A file over 8 MiB is written but not restorable.** Capture records
  `oversize` rather than failing the write. Capture is complete in the sense that
  every eligible mutation is attempted; it is not complete in the sense that
  every mutation can be undone.
- **There is no rewind.** `CheckpointRestoreExecutor` is implemented, registered
  and tested and captures its own pre-image, but no route, terminal command or
  model tool proposes a restore. `/checkpoints restore` and the Checkpoints view
  compute a preflight and perform nothing. Recovery is git, or asking the agent
  to reverse the edit. See [`checkpoint-restore.md`](checkpoint-restore.md) and
  [Known limits](../architecture/KNOWN_LIMITS.md).
- **Text only.** The write path encodes UTF-8; there is no binary write tool, and
  `read_file` refuses a file containing a NUL byte.
- **A batch containing three edits is three decisions.** Parallel execution
  applies only to validated read-only calls; the moment one call in a batch needs
  a decision the whole batch is walked serially and pauses there.

## Evidence

- `raiker/runtime/executors/tier1_files.py`, `raiker/tools/filesystem.py`,
  `raiker/checkpoints/capture.py`
- [`../THREAT_MODEL.md`](../architecture/THREAT_MODEL.md), [`approval-execution-relay.md`](approval-execution-relay.md)
- [`../BUILD_WORKSPACE_SPEC.md`](../architecture/BUILD_WORKSPACE_SPEC.md)
