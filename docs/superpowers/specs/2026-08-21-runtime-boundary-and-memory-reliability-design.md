# Runtime Boundary and Memory Reliability Continuation Design

## Goal

Finish the partially built work behind BUG-194, BUG-216, MEM-06, MEM-11, and
MEM-12 without creating a second execution or memory path. The result must make
deep Windows workspaces reversible, make the memory graph populate only through
owner review, preserve the already-fixed unified recall behavior, and complete
the remaining governed-command backends and safeguards through the command
control plane designed in
the governed shell, sandbox, environment and recovery control set — recorded
in [`../../REFERENCE_PLATFORM_COMPATIBILITY.md`](../../REFERENCE_PLATFORM_COMPATIBILITY.md#governed-shell-sandbox-environment-and-recovery-control-set) and
[`../../plans/TO_BE_FIXED.md`](../../plans/TO_BE_FIXED.md) → BUG-194. (The
2026-08-14 design note this line used to link was never committed to this
repository.)

## Priority and Scope

Work proceeds by impact divided by effort, while completing partial slices
before starting unrelated features:

1. BUG-216: high severity and contained. Fix all Raiker-owned internal paths on
   Windows and surface non-reversible writes.
2. MEM-11/MEM-12: high severity but recorded fixed. Re-run their shared
   regression suite before changing memory behavior.
3. MEM-06: medium severity and the binding constraint on the graph leg. Add a
   conservative extractor, owner-scoped review, and UI.
4. BUG-194: low recorded severity but strategically important. Reuse the
   existing SSH/Daytona executors inside the command lifecycle, then add
   filtered egress, credential delivery/delta quarantine, and runner signature
   proof in dependency order.

Windows ConPTY inside AppContainer and Windows restart reattachment remain a
separate native-security spike unless implementation can prove the required
handle and named-pipe authorization properties. They must continue to fail by
name; an unsandboxed approximation is not acceptable.

## Audited Starting Point

- The local command backend supports foreground/background execution, durable
  output, owner-scoped observation, leases, POSIX PTY/input, and POSIX restart
  reattachment. Persistent containers and reset controls are also built.
- Bounded SSH and Daytona approval executors already execute commands, enforce
  strict host-key or cost policy, and read only credential references. They do
  not implement the `CommandBackend` lifecycle, so selecting those environments
  for `run_command` still fails `*_command_supervisor_unavailable`.
- Filtered network and credential delta quarantine have contracts but no
  executable backend path.
- The runner records and compares SHA-256, but does not prove a trusted signer.
- MEM-11 and MEM-12 route model-facing lookup through hybrid retrieval and
  resolve graph anchors from query text. Their regression test passes.
- The graph tables, relationship-review primitives, and evidence-aware
  traversal exist. No production caller proposes relationship candidates, and
  the candidate table is not owner-scoped.
- BUG-216 reproduces on Windows. At greater depth than the original report the
  first failure is the SQLCipher probe directory; event locks and checkpoint
  objects are later instances of the same missing internal-path boundary.

## Options Considered

### A. Continue the existing control planes (recommended)

Add one Windows internal-path adapter, one evidence-bound entity extraction
service, and SSH/Daytona command-backend adapters. Extend the existing command
and memory review surfaces. This has the smallest authority surface and makes
old and new behavior converge.

### B. Patch each failing call site and retain parallel remote executors

This is initially faster, but another `.raiker` writer will fail at the next
path depth and remote commands will continue to have two receipt, output, and
recovery models. It does not close either root cause.

### C. Replace the existing command and memory implementations

A new generic workflow engine could cover every desired feature, but would
discard tested policy, audit, redaction, review, and recovery behavior. The
scope and regression risk are unjustified.

Option A is selected.

## BUG-216 Architecture

Create a small storage-path module with two operations:

- `internal_io_path(path: Path) -> Path` returns a Windows extended-length
  absolute path (`\\?\...`, including UNC handling) for Raiker-owned internal
  I/O and an unchanged path elsewhere.
- `display_path(path: Path) -> str` removes only that transport prefix for UI,
  events, and exported metadata.

`RuntimePaths` keeps `workspace_root` as the ordinary resolved path and exposes
its `.raiker` directories through `internal_io_path`. A repository-wide audit
also migrates Raiker-owned writers which currently bypass `RuntimePaths`:
memory records/integrity, host/instance state, backup keys, authentication key
files, command supervisor/policy/mask/cache areas, container workspaces, model
caches, MCP server state, and brain-source legacy migration. A regression test
maintains an explicit allowlist for `.raiker` literals that are checks, deny
rules, documentation, or intentionally owner-authored hook paths; any new
Raiker-owned writer must use the adapter. Workspace file paths remain ordinary
paths because they are user-visible and separately governed.

Checkpoint capture models `ineligible`, `snapshot_ready`, `snapshot_failed`,
`committed`, and `commit_failed` separately. Eligibility is evaluated before
the guarded snapshot, so a read/stat failure can never collapse to the same
`None` as an unrelated capability. A failed snapshot or commit still does not
cancel an already-approved write, but its reason code and safe display path are
added to the execution artifacts, passed through `ApprovalExecutionBridge`,
whitelisted by the approval API, and shown on the approval receipt as **Change
completed — not reversible**. A durable
checkpoint-health record stores the last success/failure and appears as a
Diagnostics readiness object with state, reason, checked time, and remediation;
the UI must not reduce it to a boolean or claim reversibility after failure.

## MEM-06 Architecture

Add a deterministic, conservative `EntityRelationshipExtractor`. Version 1
recognizes exactly `is_a`, `married_to`, `works_on`, `uses`, `prefers`,
`located_in`, and `part_of`, with anchored templates and canonical inverse-free
direction. It emits a candidate only when both bounded entity spans occur in
the evidence. It never calls a provider, never promotes an edge, rejects
secret-like text, emits at most five candidates per source, normalizes names,
and assigns a rule-specific confidence. Text it cannot parse produces no
candidate rather than a guessed one.

Extraction runs after a memory becomes approved or is imported. Existing
approved memories can be scanned through an owner-started, idempotent backfill.
Completed conversation turns are also scanned, but do not create a graph edge
directly. The production hook is `AgentGateway._finalize_turn`, after the
`turn_closed` event and `SessionManager.close_turn` have durably stored a
`completed` turn. It reads the bounded user prompt and persisted assistant
summary plus their session, turn, event, role, and owner provenance, then
creates a deferred memory proposal. Failed, stopped, `needs_approval`, and
cancelled turns are excluded. Replaying finalization is idempotent by
owner/turn/role/extractor-version. Only after the owner approves that durable
memory does the ordinary relationship candidate get created. This reuses the
existing sensitivity and memory review boundary and ensures every edge still
has active approved memory as evidence.

Every relationship candidate carries the approved memory ID, owner principal
ID, extractor version, normalized triple, and timestamps. Migration adds
nullable columns, backfills owner from the evidence memory, deterministically
keeps the oldest duplicate, validates no owner remains null, rebuilds the table
with required columns, then adds the uniqueness constraint. A legacy-duplicate
migration test proves the sequence.

Memory APIs list only the caller's relationship candidates and accept
stale-safe `approved` or `denied` decisions. One SQLite transaction selects the
owner-scoped candidate and active owner-scoped evidence, compare-and-swaps the
expected decision, upserts both entities, inserts the evidence-bound edge, and
resolves the candidate. Any error rolls back all mutations. Denial uses the
same owner-scoped compare-and-swap and creates no graph data. The transaction is
the only production relationship-resolution entry point.

Approved edges remain reviewable. An owner-scoped rejection transaction marks
the edge inactive, records reviewer/reason/time, and removes it from hybrid
retrieval immediately; it does not delete the evidence memory or shared entity
labels. Archive, purge, expiry, and search-disable behavior continues to hide
evidence through the existing neighborhood query.

The Memory page gains an **Entity links pending review** section. Each card
shows the proposed subject, relation, object, confidence, and the exact approved
memory that evidences it, with Approve and Reject controls. A **Scan approved
memories** action reports scanned, proposed, skipped, and already-present
counts. `DashboardService.brain_view` adds owner-visible entity nodes, active
relationship edges, and an `evidenced_by` connection to the approved memory.
The Knowledge Map inspector shows that provenance and an owner-only **Reject
link** action. It never displays unreviewed candidates as facts. Multi-owner
tests prove entity-name anchoring and graph projection reveal only edges whose
evidence belongs to the caller.

## BUG-194 Continuation Architecture

SSH and Daytona become `CommandBackend` adapters selected by the existing
environment resolver. They do not concatenate a remote shell command. Readiness
requires a packaged `raiker-command-supervisor` on the remote target with a
pinned version, release-manifest digest, and protocol. It is shipped as a
console entry point and signed release artifact. Installation or update is the
named `install_remote_command_supervisor` capability, never a readiness side
effect. Its immutable approval payload binds owner, profile, destination and
host fingerprint, artifact/protocol/version/digest, fixed remote staging/final
paths, bootstrap version, and expiry. After approval, the normal
`ApprovalExecutionBridge` revalidates the current signed artifact and target
fingerprint, uploads the exact bytes through SFTP or the Daytona file API, and
invokes only a fixed bootstrap command. Artifact or target TOCTOU mismatch,
failed upload/bootstrap, and uncertain outcome fail closed with a safe receipt.
Manual install remains supported. A package smoke test executes it outside the source tree;
readiness stays false until the fixed-path probe returns the expected
version/protocol/digest. The remote host or Daytona sandbox is a recipient TCB:
its self-reported digest establishes compatibility and identity, not independent
attestation. The local client runs a fixed remote program name and sends a
length-prefixed canonical command envelope over stdin; adversarial argv is
decoded as data by the supervisor and passed to `execve`, never parsed by a
shell. SSH profiles pin a dedicated owner-scoped known-host record and
fingerprint under `.raiker`; key rotation is a separate owner-confirmed action.
`StrictHostKeyChecking=yes` and a profile-specific `UserKnownHostsFile` are both
mandatory.

The SSH identity and Daytona API key are backend-transport credentials, not
credentials delivered to the command. They are resolved after authority checks,
bound to owner/profile/destination/expiry, used only by the local transport,
and added to redaction before the client launches. They never enter the remote
envelope. Command credential bindings remain refused until delta quarantine is
complete. The adapters reuse Daytona budget reservation/reconciliation, the
durable output/state/receipt lifecycle, and no-fallback routing. They initially
advertise foreground execution only; PTY, background, persistence, and restart
recovery require the remote supervisor's authenticated durable mode.

Filtered egress is initially a container-only backend capability, not a command
flag. Raiker creates a per-session Docker/Podman `--internal` network. The
command container connects only to that network; a digest-pinned
`raiker-command-egress-proxy` sidecar connects to it and a separate outbound
network. A run-scoped HMAC capability binds owner, profile, run, normalized IDNA
host/port set, resolved public address set, monotonic nonce, and expiry. The
proxy accepts authenticated HTTP/HTTPS CONNECT only, resolves and pins addresses
itself, rejects IP literals and private/link-local/loopback/reserved/multicast
answers, rechecks every connection, and logs only host/port/verdict/digest. The
command container receives only the proxy endpoint and run capability. The
proxy maintains a run-to-live-socket registry. An authenticated local control
channel marks the run revoking, refuses new CONNECTs, closes every socket for
that run, confirms the live count is zero, and only then marks it revoked. A
shared session network remains available to unrelated active grants; it is
removed only when no permitted run remains.

Platform integration tests create a real internal network and demonstrate an
allowed proxy request succeeds while direct TCP and direct DNS to the same
destination fail before, during, and after revocation. Native Windows/Linux
backends keep `filtered_network=false` until their WFP/netns enforcement gets an
equivalent design and proof.

Credential delivery is paired with delta quarantine and builds on the existing
`credential_delta.py`, store tables, and partial container blocking hooks. A
credentialed command never executes inside the standing persistent container.
For Docker/Podman runtimes which pass the integration probe, Raiker takes an
exclusive session lease, pauses and commits the standing container to a
temporary content-addressed image, copies the private cache volume and a writable
workspace tree that explicitly excludes both `.raiker` and `.git`, plus a
separate read-only `.git` snapshot, into Raiker-owned per-run staging roots.
That snapshot is the sole mount at `/workspace/.git`. Raiker records baseline
manifests, resumes the standing boundary, and starts a disposable clone with
only the staged workspace and cache writable.
The original workspace, cache, and standing container are not writable or
mounted into that run. Purpose-bound bindings are resolved after authorization,
delivered through a protected 0600 tmpfs file or inherited descriptor (never
argv or persistent environment), included in streaming redaction, and removed
before finalization. The disposable container layer is always discarded;
only staged workspace and cache changes can be considered for merge. Unsupported
runtimes or platforms report `credential_copy_on_write_unavailable`.

The delta manifest compares each allowed root against its baseline and models
creates, regular-file changes, directories, and deletes explicitly. Symlinks,
hardlinks, special files, mount crossings, unsafe modes, unreadable entries,
case/unicode collisions, scan limits, or changes outside the two allowed roots
force quarantine and discard-only. Deletes are not inferred from container
whiteouts; they are computed from the two bounded manifests. A merge uses
nofollow path traversal, rechecks every destination baseline immediately before
mutation, refuses concurrent conflicts, stages replacements on the same volume,
and applies owner-selected paths atomically where the host permits. File modes
are reduced to the approved safe executable/non-executable set. No container
filesystem, `.git`, `.raiker`, mount, link, owner, device, or ACL mutation is
mergeable. Only safe metadata and digests enter SQLite.

The resolution state machine is `scanning -> clean|quarantined -> resolving ->
merged|discarded|cleanup_failed`. A fresh owner decision compare-and-swaps
`clean` to `resolving`; the service takes a second snapshot/scan and verifies
the baseline plus delta digest immediately before a path-by-path governed merge.
Matched, changed, or uncertain deltas can only be discarded. A crash in
`resolving` is recovered by reconciliation; new credentialed work on the
profile remains blocked. Receipts contain digests and counts, never values.

Runner trust extends the existing `native_artifacts.py` manifest/digest checks
instead of creating another verifier. On Windows, the verified manifest's exact
file is additionally checked through `WinVerifyTrust`: trusted chain, pinned
leaf SPKI/publisher, RFC-3161 timestamp within certificate validity, no
revocation failure, and no catalog/path substitution. On POSIX, full publisher
authenticity is available only through a root-owned launcher outside the
writable installation (for example `/usr/libexec/raiker/raiker-runner-launcher`)
that verifies the signed canonical manifest with a root-owned key under
`/etc/raiker/trust.d/`, validates ownership/mode, and launches the exact digest.
An ordinary user installation can report only `package_relative_integrity`:
its package key plus digest detects accidental mismatch but is not a publisher
trust anchor and must not satisfy BUG-194 authenticity. The manifest pins
protocol and minimum version; downgrade fails closed. Development builds report
`developer_unverified` and cannot advertise a production native boundary. The
container supervisor and egress proxy are addressed by signed release-manifest
image digests, never placeholder constants.

## Reference Compatibility and Meaningful Improvement Test

The comparison is against the combined control set, not any single product.
Current primary documentation shows Codex and Claude emphasize sandbox and
approval boundaries; OpenClaw combines explicit host selection, canonical
execution-plan binding, approvals, PTY, and background tasks; Hermes exposes
local, container, SSH, Modal, and Daytona terminal environments; DeepSeek
Harness exposes replaceable tools, sessions, sandboxes, storage, loops,
scheduling, UI, persistent bash, plans, goals, subagents, and workflows;
ChatGPT Work/agent adds long-running multi-step work, apps/actions, and
workspace governance.

Each proposed addition is categorically meaningful:

| Addition | Meaningful improvement beyond the combined references? | Reason |
|---|---|---|
| Deep-path-safe internal I/O plus visible non-reversibility | **Conditionally yes** | If the implementation and source audit confirm it, this converts a silent safety-promise failure into durable, actionable evidence. |
| Evidence-bound, owner-reviewed entity extraction | **Conditionally yes** | If owner isolation, atomic review, provenance, and rejection are proven, this supplies graph recall without treating parser inference as fact. |
| One lifecycle for local, container, SSH, and Daytona | **Conditionally yes** | Remote execution is parity; common authority binding, redaction, receipts, no-fallback behavior, and honest feature probes would be the differentiator. |
| Filtered egress with active revocation and bypass proof | **Conditionally yes** | This is beyond only if platform integration evidence proves bypass denial and active revocation, not merely proxy configuration. |
| Credential delivery paired with two-pass delta quarantine | **Conditionally yes** | This is meaningful if the overlay, failure-closed scan, second scan, and recovery state machine are proven. |
| Publisher-verified runner | **Conditionally yes** | This closes replacement of both runner and expected digest only if the trust anchor and platform signature checks are outside the writable install surface. |
| Windows PTY/reattachment without a proven sandbox transport | **No** | An unsandboxed approximation would add convenience but reduce the claimed control boundary, so it is explicitly rejected. |

## Error Handling and Honest States

- Internal-path conversion validates absoluteness before resolution, accepts
  valid extended drive/UNC paths idempotently, and rejects malformed or other
  device namespaces.
- Snapshot and commit failures use stable reason codes and safe paths; exceptions
  and secret values never reach receipts.
- Extraction is idempotent and returns counts; a malformed sentence is a skip,
  not an error. Candidate approval/rejection and approved-edge rejection are
  owner-scoped, transactional, and stale-safe.
- Remote/backend readiness is feature-specific. Unknown execution outcomes are
  `lost`, never success. Unavailable security proof never triggers host fallback.
- Egress revocation and credential cleanup are sagas with durable intermediate
  states and retryable cleanup; new credentialed work is blocked while cleanup
  is unresolved.

## Verification

Use RED/GREEN tests for every behavior, including an actual deep Windows
workspace, long-path event/checkpoint/probe I/O, receipt/Diagnostics rendering,
multi-owner relationship isolation, duplicate extraction, inactive evidence,
MEM-11/MEM-12 consistency, remote no-fallback, host-key and cost refusal,
egress bypass/revocation, credential redaction/quarantine, and runner tamper.

Live Playwright testing uses the UI to configure Anthropic, OpenRouter, OpenAI,
and Ollama; credentials are never placed in source, commands, screenshots, or
logs. Verify Chat and Build turns, memory review/backfill/graph traversal,
Diagnostics, command environment selection and receipts, reload recovery, and
responsive layouts. Inspect screenshots at 375, 768, 1024, and 1440 pixels.

Before completion run Python tests, Ruff, mypy, web unit tests, lint, Svelte
check, production build, applicable native checks, repository truth validators,
and `git diff --check`. Push `main`, then monitor every GitHub Actions workflow
for the pushed SHA until green.
