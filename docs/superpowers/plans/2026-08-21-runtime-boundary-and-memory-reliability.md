# Runtime Boundary and Memory Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close BUG-216 and MEM-06, regression-prove MEM-11/MEM-12, and complete BUG-194's remaining governed-command backends and safeguards without creating parallel authority paths.

**Architecture:** Continue the existing `RuntimePaths`, hybrid-memory, relationship-review, and `CommandService` control planes. Windows extended-length paths are applied once at the internal storage boundary; entity extraction produces owner-scoped review candidates; remote, network, credential, and runner-trust features advertise only measured backend capabilities.

**Tech Stack:** Python 3.11+, SQLite/SQLCipher, FastAPI, Svelte 5/TypeScript, pytest, Vitest/Testing Library, Playwright, Rust/native runner where applicable.

## Global Constraints

- No credential value may be committed, logged, included in commands, or visible in screenshots.
- A selected execution environment is authoritative and must never fall back to host execution.
- Every new production behavior follows RED/GREEN TDD.
- UI copy must state measured behavior and named failures, not configured intent.
- Windows PTY or restart recovery remains unavailable until the AppContainer/ConPTY and named-pipe authorization properties are proven.
- Documentation completion claims require automated and live evidence.

---

### Task 1: Make every Raiker-owned internal path deep-Windows safe

**Files:**
- Create: `raiker/storage/internal_paths.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/storage/sqlcipher_probe.py`
- Modify: `raiker/memory/store.py`
- Modify: `raiker/memory/integrity.py`
- Modify: `raiker/app/host.py`
- Modify: `raiker/app/backup.py`
- Modify: `raiker/app/uninstall.py`
- Modify: `raiker/auth/app_key.py`
- Modify: `raiker/auth/vault_key_file.py`
- Modify: `raiker/execution/container_tools.py`
- Modify: `raiker/execution/commands/backends/native.py`
- Modify: `raiker/execution/commands/backends/container.py`
- Modify: `raiker/execution/commands/supervisor_client.py`
- Modify: `raiker/api/app.py`
- Modify: `raiker/api/routes_models.py`
- Modify: `raiker/runtime/executors/mcp.py`
- Modify: `raiker/runtime/executors/containers.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/control/knowledge_scope.py`
- Modify: `raiker/cli/commands.py`
- Modify: `raiker/events/export.py`
- Modify: `raiker/api/routes_dashboard.py`
- Test: `tests/test_windows_internal_paths.py`
- Test: `tests/test_internal_path_audit.py`
- Test: `tests/test_approval_execution_wiring.py`

**Interfaces:**
- Produces: `internal_io_path(path: str | Path) -> Path`, `display_path(path: str | Path) -> str`.
- Consumes: ordinary absolute workspace paths; workspace-visible paths remain unprefixed.

- [ ] **Step 1: Write Windows path-unit tests and a real deep-workspace regression**

```python
def test_internal_io_path_adds_extended_prefix_only_on_windows(tmp_path: Path) -> None:
    converted = internal_io_path(tmp_path / ".raiker" / "events")
    if sys.platform == "win32":
        assert str(converted).startswith("\\\\?\\")
        assert display_path(converted) == str((tmp_path / ".raiker" / "events").resolve())
    else:
        assert converted == (tmp_path / ".raiker" / "events").resolve()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows MAX_PATH regression")
def test_deep_workspace_bootstraps_and_captures_a_pre_image(tmp_path_factory) -> None:
    root = tmp_path_factory.getbasetemp() / ("deep-" + "a" * 170) / "ws"
    store = SQLiteStore(root)
    writer = EventLogWriter(store)
    # create an approved file mutation through RuntimeAuthority, then assert
    # checkpoint_captured and a readable blob rather than checkpoint_capture_failed
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest --basetemp .tmp/pytest-long-path tests/test_windows_internal_paths.py -q`

Expected on Windows: failure while creating the SQLCipher probe or later `.raiker` writer.

- [ ] **Step 3: Implement the single storage-boundary adapter**

```python
def internal_io_path(path: str | Path) -> Path:
    candidate = Path(path)
    raw_input = str(candidate)
    if not candidate.is_absolute() or _is_malformed_device_path(raw_input):
        raise ValueError("internal_path_must_be_absolute")
    resolved = candidate.resolve()
    if sys.platform != "win32":
        return resolved
    raw = str(resolved)
    if raw.startswith("\\\\?\\"):
        return resolved
    if raw.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + raw[2:])
    return Path("\\\\?\\" + raw)


def display_path(path: str | Path) -> str:
    raw = str(path)
    if raw.startswith("\\\\?\\UNC\\"):
        return "\\\\" + raw[8:]
    return raw[4:] if raw.startswith("\\\\?\\") else raw
```

Validate the caller supplied an absolute drive/UNC path before `resolve()`;
never make a relative input valid by resolving it against process cwd. Accept
an already-valid `\\?\` drive or `\\?\UNC\` path idempotently, reject other
device namespaces and malformed/mixed prefixes, and preserve display
round-tripping. Tests cover relative paths, extended drive paths, UNC paths,
already-extended UNC paths, malformed device paths, and
`display_path(internal_io_path(path))`.

Use the adapter in every `RuntimePaths` internal directory property and migrate
the audited Raiker-owned writers listed above. `test_internal_path_audit.py`
scans Python source for literal `.raiker` joins and permits only an explicit
allowlist of deny checks, docs, migrations, user-authored hook paths, and calls
inside `internal_paths.py`; a new internal writer fails the test. An actual
reader/writer may not be allowlisted merely because another task later changes
its file. The initial inventory explicitly covers both container-workspace
implementations, dashboard memory/artifact paths, knowledge-scope generated
roots, CLI event/checkpoint rendering, and audit-export paths in addition to the
files above. Store/export `display_path(...)` when a path crosses a metadata,
CLI, receipt, or UI boundary, while retaining an internal I/O path for later
reads such as export download.

- [ ] **Step 4: Run GREEN and the affected storage/checkpoint suites**

Run: `python -m pytest --basetemp .tmp/pytest-long-path tests/test_windows_internal_paths.py tests/test_internal_path_audit.py tests/test_approval_execution_wiring.py tests/test_checkpoint_restore.py tests/test_storage_sqlite.py -q`

- [ ] **Step 5: Commit**

```powershell
git add -- raiker/storage/internal_paths.py raiker/storage/sqlite.py raiker/storage/sqlcipher_probe.py raiker/memory/store.py raiker/memory/integrity.py raiker/app/host.py raiker/app/backup.py raiker/app/uninstall.py raiker/auth/app_key.py raiker/auth/vault_key_file.py raiker/execution/container_tools.py raiker/execution/commands/backends/native.py raiker/execution/commands/backends/container.py raiker/execution/commands/supervisor_client.py raiker/api/app.py raiker/api/routes_models.py raiker/api/routes_dashboard.py raiker/runtime/executors/mcp.py raiker/runtime/executors/containers.py raiker/control/dashboard.py raiker/control/knowledge_scope.py raiker/cli/commands.py raiker/events/export.py tests/test_windows_internal_paths.py tests/test_internal_path_audit.py tests/test_approval_execution_wiring.py
git commit -m "fix: support deep Windows runtime paths"
```

---

### Task 2: Surface checkpoint capture health on receipts and Diagnostics

**Files:**
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/approvals/execution.py`
- Modify: `raiker/api/routes_approvals.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.test.ts`
- Modify: `apps/web/src/lib/views/DiagnosticsView.svelte`
- Modify: `apps/web/src/lib/views/DiagnosticsView.test.ts`
- Test: `tests/test_checkpoint_restore.py`
- Test: `tests/test_api_web_read_models.py`

**Interfaces:**
- Produces: capture outcome `{ok, reason_code, display_path, checked_at}` in execution artifacts and `readiness.checkpoint_capture`.
- Consumes: the existing best-effort pre-image capture; approved writes still execute.

- [ ] **Step 1: Write failing backend tests**

```python
def test_snapshot_failure_is_returned_on_the_execution_receipt_and_health(tmp_path, monkeypatch):
    authority = seeded_authority(tmp_path)
    monkeypatch.setattr(authority.capture_service, "snapshot_pre_image", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    result = execute_approved_write(authority)
    assert result.artifacts["checkpoint_capture"]["ok"] is False
    assert result.artifacts["checkpoint_capture"]["stage"] == "snapshot"
    assert result.artifacts["checkpoint_capture"]["reason_code"] == "checkpoint_snapshot_os_error"
    health = SQLiteStore(tmp_path).get_checkpoint_capture_health()
    assert health["ok"] == 0
    assert "boom" not in json.dumps(health)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest --basetemp .tmp/pytest-checkpoint-health tests/test_checkpoint_restore.py tests/test_api_web_read_models.py -q`

- [ ] **Step 3: Return and persist a safe structured outcome**

Replace `_snapshot_pre_image -> Any|None` with a structured result that first
records whether the capability is eligible, then distinguishes
`snapshot_ready` from `snapshot_failed`. `_commit_pre_image` returns
`committed|commit_failed`. Map exception classes to stable reason codes, upsert
health for failures at either stage, and merge the result into executor
artifacts before `action_executed`. `ApprovalExecutionBridge` preserves it;
`routes_approvals.py` explicitly includes `checkpoint_capture` in the execution
receipt whitelist. Never persist exception text or file content.

- [ ] **Step 4: Write and satisfy Diagnostics UI tests**

```typescript
it("names a non-reversible write and its repair", async () => {
  stubFetch({ "GET /api/diagnostics": diagnostics({ readiness: {
    checkpoint_capture: { ok: false, reason_code: "checkpoint_capture_path_unreachable", checked_at: "2026-08-21T00:00:00Z", remediation: "Shorten the workspace path or enable Windows long paths." },
  } }) });
  render(DiagnosticsView);
  expect(await screen.findByText(/checkpoint capture/i)).toBeInTheDocument();
  expect(screen.getByText(/not reversible/i)).toBeInTheDocument();
});
```

Render boolean and structured readiness entries; show the stable reason and
remediation without raw paths.

Add an approval receipt test where a successful write with failed snapshot
shows **Change completed — not reversible**, its stable reason, and the repair
link. The success notice must not call it reversible.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest --basetemp .tmp/pytest-checkpoint-health tests/test_checkpoint_restore.py tests/test_api_web_read_models.py -q`

Run: `npm --prefix apps/web run test -- DiagnosticsView.test.ts ApprovalsView.test.ts`

```powershell
git add -- raiker/runtime/authority/router.py raiker/approvals/execution.py raiker/api/routes_approvals.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/control/dashboard.py apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/ApprovalsView.svelte apps/web/src/lib/views/ApprovalsView.test.ts apps/web/src/lib/views/DiagnosticsView.svelte apps/web/src/lib/views/DiagnosticsView.test.ts tests/test_checkpoint_restore.py tests/test_api_web_read_models.py
git commit -m "fix: surface checkpoint capture failures"
```

---

### Task 3: Regression-prove MEM-11 and MEM-12 before graph changes

**Files:**
- Verify: `raiker/tools/memory_tools.py`
- Verify: `raiker/memory/retrieval.py`
- Verify: `raiker/storage/sqlite.py`
- Verify: `tests/test_model_facing_memory_graph.py`

**Interfaces:**
- Consumes/produces: no new interface; protects unified hybrid lookup and query-resolved graph anchors.

- [ ] **Step 1: Run the existing regression suite**

Run: `python -m pytest --basetemp .tmp/pytest-memory-regression tests/test_model_facing_memory_graph.py -q`

Expected: all tests pass, including identical runtime/tool ordering and graph-only query-anchor recall.

- [ ] **Step 2: Add a regression only if a closure property is missing**

The added test must name the exact production mutation that would make it fail,
then be verified by temporarily reverting that mutation before restoring it.

---

### Task 4: Add owner-scoped, idempotent entity relationship extraction

**Files:**
- Create: `raiker/memory/entity_extraction.py`
- Modify: `raiker/memory/entities.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/gateway/agent_gateway.py`
- Modify: `raiker/sessions/manager.py`
- Test: `tests/test_memory_entity_extraction.py`
- Test: `tests/test_memory_controls.py`
- Test: `tests/test_turn_memory_proposals.py`

**Interfaces:**
- Produces: `extract_relationship_candidates(text: str) -> tuple[ExtractedRelationship, ...]`, `propose_memory_relationships(store, memory_id, owner_principal_id) -> ExtractionSummary`.
- Consumes: active approved memory owned by the caller.

Version 1 predicates are exactly `is_a`, `married_to`, `works_on`, `uses`,
`prefers`, `located_in`, and `part_of`. Each has an anchored parser template,
canonical direction, maximum subject/object length, and fixed confidence.

- [ ] **Step 1: Write failing extractor, idempotency, evidence, and owner-isolation tests**

```python
def test_explicit_relation_proposes_review_but_does_not_populate_graph(store, memory):
    summary = propose_memory_relationships(store, memory.memory_id, OWNER)
    assert summary.proposed == 1
    candidate = store.list_memory_relationship_candidates(OWNER)[0]
    assert (candidate["subject_name"], candidate["predicate"], candidate["object_name"]) == ("Sarah", "married_to", "Mark")
    assert store.match_memory_entities("Sarah") == []


def test_backfill_is_idempotent_and_cross_owner_candidates_are_invisible(store):
    propose_memory_relationships(store, OWNER_MEMORY, OWNER)
    propose_memory_relationships(store, OWNER_MEMORY, OWNER)
    assert len(store.list_memory_relationship_candidates(OWNER)) == 1
    assert store.list_memory_relationship_candidates(OTHER) == []


def test_legacy_duplicate_migration_keeps_oldest_and_backfills_owner(legacy_store):
    migrated = reopen_with_current_schema(legacy_store)
    rows = migrated.list_memory_relationship_candidates(OWNER)
    assert len(rows) == 1
    assert rows[0]["owner_principal_id"] == OWNER


def test_concurrent_approval_creates_one_edge_and_loser_mutates_nothing(store):
    outcomes = decide_concurrently(store, CANDIDATE, OWNER)
    assert sorted(outcomes) == ["approved", "stale_memory_relationship_candidate"]
    assert count_edges(store, evidence_memory_id=MEMORY) == 1
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest --basetemp .tmp/pytest-entity-extraction tests/test_memory_entity_extraction.py tests/test_memory_controls.py -q`

- [ ] **Step 3: Add the owner/version/uniqueness migration and conservative extractor**

The migration adds nullable owner/version/normalized fields, backfills owner
from `approved_memory`, deterministically keeps the oldest duplicate, validates
no unresolved owner, rebuilds the table with required fields, then creates a
unique index over owner, evidence, normalized triple, and version. Patterns are
anchored, bounded, reject secret sensitivity, and emit at most five candidates
per source.

- [ ] **Step 4: Wire extraction after approval/import and add an owner-started backfill service**

Call proposal creation after `write_memory` succeeds in
`decide_memory_proposal` and memory import. In
`AgentGateway._finalize_turn`, after the `turn_closed` event and
`SessionManager.close_turn` have durably stored a `completed` turn, scan bounded
user and assistant text into role-specific deferred memory proposals with
owner, session, turn, event, and extractor-version provenance. Failed, stopped,
cancelled, and approval-parked turns create none; replay is idempotent and
cross-owner isolated. Apply the existing sensitivity classifier before storing
a proposal, and create no entity candidate until that memory is approved.
Extraction failure records a safe count/reason but never rolls back approved
memory. Backfill lists only the caller's active approved memories.

Implement `resolve_memory_relationship_candidate_atomic(...)` as one store
transaction: select candidate and evidence by owner, compare expected decision,
upsert both entities, insert the edge, resolve the candidate, and commit. Any
error rolls back. Remove production use of the existing multi-transaction
helper. Add rollback, concurrency, cross-owner lookup, and cross-owner anchor
tests.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest --basetemp .tmp/pytest-entity-extraction tests/test_memory_entity_extraction.py tests/test_memory_controls.py tests/test_turn_memory_proposals.py tests/test_model_facing_memory_graph.py -q`

```powershell
git add -- raiker/memory/entity_extraction.py raiker/memory/entities.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/control/dashboard.py raiker/gateway/agent_gateway.py raiker/sessions/manager.py tests/test_memory_entity_extraction.py tests/test_memory_controls.py tests/test_turn_memory_proposals.py
git commit -m "feat: propose evidence-bound memory entities"
```

---

### Task 5: Add entity review, Knowledge Map projection, provenance, and rejection

**Files:**
- Modify: `raiker/api/routes_memory.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/MemoryView.svelte`
- Modify: `apps/web/src/lib/views/MemoryView.test.ts`
- Modify: `apps/web/src/lib/views/BrainView.svelte`
- Modify: `apps/web/src/lib/views/BrainView.test.ts`
- Test: `tests/test_api_memory_controls.py`
- Test: `tests/test_brain_view.py`

**Interfaces:**
- Produces: `GET /api/memory/entity-proposals`, `POST /api/memory/entity-proposals/{id}/decision`, `POST /api/memory/entity-proposals/scan`, `POST /api/memory/entity-relationships/{id}/reject`, and entity/evidence nodes in `GET /api/brain`.
- Consumes: Task 4 owner-scoped candidate services.

- [ ] **Step 1: Write failing API tests for list, approve, deny, stale, and cross-owner cases**

```python
def test_relationship_decision_is_owner_scoped_and_stale_safe(client, owner_headers, other_headers):
    candidate_id = seed_relationship_candidate()
    assert client.get("/api/memory/entity-proposals", headers=other_headers).json() == []
    approved = client.post(f"/api/memory/entity-proposals/{candidate_id}/decision", headers=owner_headers, json={"decision": "approved", "expected_decision": "needs_user_review"})
    assert approved.status_code == 200
    assert client.post(f"/api/memory/entity-proposals/{candidate_id}/decision", headers=owner_headers, json={"decision": "denied", "expected_decision": "needs_user_review"}).status_code == 409


def test_rejecting_an_approved_edge_removes_it_from_retrieval(client, owner_headers):
    relationship_id = seed_approved_relationship()
    assert graph_only_recall("Sarah", OWNER)
    assert client.post(f"/api/memory/entity-relationships/{relationship_id}/reject", headers=owner_headers, json={"reason": "Incorrect relationship", "expected_active": True}).status_code == 200
    assert graph_only_recall("Sarah", OWNER) == []
```

- [ ] **Step 2: Run RED, implement strict routes, run GREEN**

Run: `python -m pytest --basetemp .tmp/pytest-memory-api tests/test_api_memory_controls.py -q`

- [ ] **Step 3: Write failing Memory UI tests**

```typescript
it("shows inferred links as pending evidence, never as facts", async () => {
  render(MemoryView);
  expect(await screen.findByRole("heading", { name: /entity links pending review/i })).toBeInTheDocument();
  expect(screen.getByText(/Sarah.*married to.*Mark/i)).toBeInTheDocument();
  expect(screen.getByText(/evidence: Sarah is married to Mark/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /approve link/i })).toBeInTheDocument();
});
```

- [ ] **Step 4: Implement responsive, accessible review and scan controls**

Keep pending relationships visually distinct from approved memories. Disable
decision buttons while pending, preserve errors in an alert, announce scan
counts, and refresh memories/candidates after success.

`DashboardService.brain_view` adds caller-owned entity nodes, active relation
edges, and `evidenced_by` edges to already-rendered memory nodes. Brain DTOs
carry `relationship_id`, `evidence_memory_id`, and `owner_can_reject` only for
relationship edges. The Knowledge Map inspector shows the evidence memory and
an owner-only **Reject link** action with reason and stale-active check. Rejected
edges disappear after refresh. Tests prove another owner cannot see an entity
label, edge, evidence link, or rejection endpoint.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest --basetemp .tmp/pytest-memory-api tests/test_api_memory_controls.py tests/test_brain_view.py -q`

Run: `npm --prefix apps/web run test -- MemoryView.test.ts BrainView.test.ts`

Run: `npm --prefix apps/web run check`

```powershell
git add -- raiker/api/routes_memory.py raiker/api/routes_dashboard.py raiker/control/dashboard.py apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/MemoryView.svelte apps/web/src/lib/views/MemoryView.test.ts apps/web/src/lib/views/BrainView.svelte apps/web/src/lib/views/BrainView.test.ts tests/test_api_memory_controls.py tests/test_brain_view.py
git commit -m "feat: review memory entity links"
```

---

### Task 6: Bring SSH and Daytona into the governed command lifecycle

**Files:**
- Create: `raiker/execution/commands/backends/remote.py`
- Create: `raiker/execution/commands/remote_envelope.py`
- Create: `raiker/execution/commands/remote_supervisor.py`
- Create: `raiker/execution/commands/known_hosts.py`
- Modify: `pyproject.toml`
- Modify: `raiker/app/release.py`
- Modify: package/release workflows under `.github/workflows/`
- Modify: `raiker/execution/commands/backends/__init__.py`
- Modify: `raiker/execution/commands/service.py`
- Modify: `raiker/execution/profiles.py`
- Modify: `raiker/runtime/executors/tier5_network.py`
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/approvals/execution.py`
- Modify: `raiker/api/routes_commands.py`
- Modify: `raiker/api/routes_approvals.py`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.test.ts`
- Modify: `apps/web/src/lib/views/settings/Runtime.svelte`
- Modify: `apps/web/src/lib/views/settings/Runtime.test.ts`
- Test: `tests/test_remote_command_backends.py`
- Test: `tests/test_execution_environments.py`
- Test: `tests/test_remote_supervisor_packaging.py`
- Test: `tests/test_remote_supervisor_install.py`
- Test: `tests/test_api_commands.py`

**Interfaces:**
- Produces: foreground-only `SshCommandBackend` and `DaytonaCommandBackend`, canonical length-prefixed `RemoteCommandEnvelope`, and owner-scoped host-key pin records. Features are `shell=False, background=False, pty=False, restart_recovery=False, credential_delivery=False`.
- Consumes: owner-selected remote profile, existing strict validation/cost services, `_StoreSink` redaction/output lifecycle.

- [ ] **Step 1: Write RED tests for selection, streaming receipt, strict host keys, cost ceiling, and no fallback**

```python
def test_selected_ssh_runs_through_command_service_without_host_fallback(service, fake_ssh):
    run = service.start(**request(argv=["git", "status"]))
    assert run.backend == "ssh"
    assert service.wait(OWNER, run.run_id)["state"] == "succeeded"
    assert fake_ssh.argv[-1] == "raiker-command-supervisor"
    assert decode_frame(fake_ssh.stdin).argv == ("git", "status")


def test_unready_remote_backend_never_calls_local(service, local_spy):
    with pytest.raises(CommandServiceError, match="ssh_profile_not_ready"):
        service.start(**request(argv=["git", "status"]))
    local_spy.assert_not_called()


@pytest.mark.parametrize("value", ["a; rm -rf x", "$(touch x)", "a b", "'\"`$\\", "line\nbreak"])
def test_remote_argv_is_data_not_shell_source(value, supervisor):
    frame = encode_remote_envelope(argv=("printf", "%s", value))
    assert supervisor.decode(frame).argv[-1] == value
    assert supervisor.exec_argv(frame) == ["printf", "%s", value]


def test_profile_pins_its_own_known_host_and_rotation_needs_owner_decision(service):
    profile = configured_ssh_profile(host_key_sha256=PIN)
    argv = service.build_transport(profile)
    assert "UserKnownHostsFile=" in " ".join(argv)
    assert service.rotate_host_key(profile, new_pin=OTHER_PIN, decision_id="") == "owner_decision_required"
```

- [ ] **Step 2: Implement a non-shell remote envelope and pinned transport**

Readiness runs only a fixed `raiker-command-supervisor --probe` command and
verifies its protocol/version/signed release digest. Execution invokes that
fixed program and sends a bounded versioned length-prefixed canonical JSON frame
over stdin. The supervisor rejects unknown fields, digest mismatch, oversized
frames, shell mode, and absolute/traversing cwd, then uses direct process argv.

Add `raiker-command-supervisor` to `[project.scripts]` and include its exact
artifact in the signed release manifest. Define
`install_remote_command_supervisor` as an executable-on-approval capability.
The proposed action's canonical immutable payload binds owner, profile,
destination/host fingerprint, artifact/protocol/version/digest, fixed staging
and final paths, bootstrap version, and expiry. `ApprovalExecutionBridge`
revalidates all bindings after approval, then the executor uploads the exact
locally verified bytes through SFTP or the Daytona file API and invokes only a
fixed literal bootstrap command; no user-supplied shell source is accepted.
Readiness probes are read-only and may never install or update. The approval
receipt contains only artifact, protocol, destination, and resulting probe
digests plus stable outcome codes. A supported manual-install path remains available.
Package smoke installs into a clean environment and invokes the supervisor from
outside the checkout. Readiness is false until the fixed remote path reports the
expected version, protocol, and manifest digest. Document the remote recipient
as a TCB: a self-reported digest is compatibility evidence, not attestation.

RED tests prove no upload without an approved action, artifact/target TOCTOU
mismatch refusal, expired approval refusal, failed upload, failed or uncertain
bootstrap, secret-free receipts, and readiness becoming true only after a
successful install followed by a separate read-only probe.

SSH requires profile-specific `UserKnownHostsFile`, `StrictHostKeyChecking=yes`,
an owner-pinned SHA-256 host fingerprint, and an owner-confirmed rotation route;
the global known-host file is never trusted for a governed profile.

- [ ] **Step 3: Reuse backend-transport credentials without creating command credential delivery**

Resolve the SSH identity/Daytona API key only after authority and profile checks,
bind it to owner/profile/destination/expiry, add it to redaction before launch,
and pass it only to the local transport process. It never enters the remote
envelope. `CommandRequest.credential_bindings` remains refused until Task 8.
The legacy approval capabilities delegate into the same validators so behavior
cannot drift.

- [ ] **Step 4: Make probes report foreground remote capability only after executable/profile checks**

The Runtime card states **Foreground command execution** and explicitly lists
PTY, background, persistence, and restart recovery as unavailable with
`remote_command_supervisor_unavailable`.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest --basetemp .tmp/pytest-remote tests/test_remote_command_backends.py tests/test_execution_environments.py tests/test_remote_supervisor_packaging.py tests/test_remote_supervisor_install.py tests/test_api_commands.py tests/test_command_service.py -q`

Run: `npm --prefix apps/web run test -- Runtime.test.ts ApprovalsView.test.ts`

```powershell
git add -- pyproject.toml raiker/app/release.py .github/workflows raiker/execution/commands/backends/remote.py raiker/execution/commands/remote_envelope.py raiker/execution/commands/remote_supervisor.py raiker/execution/commands/known_hosts.py raiker/execution/commands/backends/__init__.py raiker/execution/commands/service.py raiker/execution/profiles.py raiker/runtime/executors/tier5_network.py raiker/runtime/authority/router.py raiker/approvals/execution.py raiker/api/routes_commands.py raiker/api/routes_approvals.py apps/web/src/lib/views/ApprovalsView.svelte apps/web/src/lib/views/ApprovalsView.test.ts apps/web/src/lib/views/settings/Runtime.svelte apps/web/src/lib/views/settings/Runtime.test.ts tests/test_remote_command_backends.py tests/test_execution_environments.py tests/test_remote_supervisor_packaging.py tests/test_remote_supervisor_install.py tests/test_api_commands.py
git commit -m "feat: govern remote command backends"
```

---

### Task 7: Add measured filtered egress to the container backend

**Files:**
- Create: `raiker/execution/commands/egress_policy.py`
- Create: `raiker/execution/commands/egress_tokens.py`
- Create: `raiker/execution/commands/egress_proxy.py`
- Create: `containers/command-egress-proxy/Containerfile`
- Modify: `raiker/execution/commands/backends/container.py`
- Modify: `raiker/execution/commands/service.py`
- Modify: `raiker/execution/commands/store.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/api/routes_commands.py`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.test.ts`
- Modify: `apps/web/src/lib/views/settings/Runtime.svelte`
- Modify: `apps/web/src/lib/views/settings/Runtime.test.ts`
- Test: `tests/test_command_egress_policy.py`
- Test: `tests/test_command_egress_proxy.py`
- Test: `tests/integration/test_container_egress_boundary.py`

**Interfaces:**
- Produces: run-scoped `EgressGrant`, HMAC capability, container internal-network lifecycle, proxy verdict log, and measured `filtered_network`.
- Consumes: owner-approved host/port policy, persistent container identity, signed proxy image digest.

- [ ] **Step 1: Write RED policy/token tests**

Test IDNA normalization, exact/wildcard boundary matching, port binding, nonce
replay, expiry, cross-run/owner/profile token use, IP literals, DNS rebinding,
and private/link-local/loopback/reserved/multicast answers. Token claims are
canonical JSON authenticated by an instance key and contain no provider secret.

- [ ] **Step 2: Add durable grants and fail-closed lifecycle**

Migrate `command_egress_grants` and `command_egress_verdicts`. Grant states are
`pending -> active -> revoking -> revoked|cleanup_failed`; starts require
`active`, and `revoking|cleanup_failed` blocks new networked work on that
profile. Store host, port, address-set digest, verdict, checked time, and grant
digest only.

- [ ] **Step 3: Implement the digest-pinned proxy sidecar and internal network**

Create a per-session runtime `--internal` network. Connect the command
container only to it. Connect a digest-pinned proxy sidecar to that network and
a separate outbound network. The proxy accepts authenticated HTTP and HTTPS
CONNECT, resolves/pins public addresses itself, and revalidates every
connection. It records every live socket against the authenticated run ID. An
authenticated local control channel atomically marks that run revoking, refuses
new CONNECTs, closes every live socket for only that run, verifies the count is
zero, and then marks it revoked. The shared internal network and other runs stay
up; disconnect/remove the network only when no active grant remains.

- [ ] **Step 4: Prove bypass denial in a real container integration test**

With Docker or Podman, assert an allowed HTTPS request through the proxy
succeeds while direct TCP and direct DNS to the same external destination fail.
Revoke the grant while an established long-lived stream is active and another
run on the shared network remains permitted. Assert the first stream is closed,
new proxy and direct attempts for that run fail, and the unrelated grant still
works. This integration test is required before the probe returns
`filtered_network=true`; absence of a runtime skips the test locally but the
container-boundary workflow must run it.

- [ ] **Step 5: Add approval/Runtime UI and commit**

Show exact normalized domains/ports, expiry, active/revoking/cleanup state, and
measured bypass proof. Native and remote cards keep filtered network absent.

Run: `python -m pytest --basetemp .tmp/pytest-egress tests/test_command_egress_policy.py tests/test_command_egress_proxy.py tests/integration/test_container_egress_boundary.py -q`

Run: `npm --prefix apps/web run test -- ApprovalsView.test.ts Runtime.test.ts`

The web tests include 375 px responsive layout, keyboard-accessible controls,
named status regions, and no secret/token/raw-address rendering assertions.

```powershell
git add -- raiker/execution/commands/egress_policy.py raiker/execution/commands/egress_tokens.py raiker/execution/commands/egress_proxy.py containers/command-egress-proxy/Containerfile raiker/execution/commands/backends/container.py raiker/execution/commands/service.py raiker/execution/commands/store.py raiker/storage/migrations.py raiker/api/routes_commands.py apps/web/src/lib/views/ApprovalsView.svelte apps/web/src/lib/views/ApprovalsView.test.ts apps/web/src/lib/views/settings/Runtime.svelte apps/web/src/lib/views/settings/Runtime.test.ts tests/test_command_egress_policy.py tests/test_command_egress_proxy.py tests/integration/test_container_egress_boundary.py
git commit -m "feat: enforce container domain egress"
```

---

### Task 8: Complete credential delivery and two-pass delta quarantine

**Files:**
- Modify: `raiker/execution/commands/credential_delta.py`
- Create: `raiker/execution/commands/credential_overlay.py`
- Modify: `raiker/execution/commands/backends/container.py`
- Modify: `raiker/execution/commands/models.py`
- Modify: `raiker/execution/commands/service.py`
- Modify: `raiker/execution/commands/store.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/api/routes_commands.py`
- Modify: `apps/web/src/lib/components/CommandOutputPane.svelte`
- Modify: `apps/web/src/lib/components/CommandOutputPane.test.ts`
- Create: `apps/web/src/lib/components/CredentialDeltaReview.svelte`
- Create: `apps/web/src/lib/components/CredentialDeltaReview.test.ts`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.test.ts`
- Test: `tests/test_credential_command_delta.py`
- Test: `tests/test_credential_overlay.py`
- Test: `tests/test_api_commands.py`
- Test: `tests/integration/test_container_credential_copy_on_write.py`

**Interfaces:**
- Produces: per-run overlay baseline, protected delivery file/descriptor, failure-closed scan, resolution/recovery state machine, immutable delta receipt.
- Consumes: existing delta scanner/store tables, vault binding, redactor, partial container block/discard hooks.

- [ ] **Step 1: Audit existing partial behavior and write RED gap tests**

Keep the existing scanner and immutable receipt tests. Add unreadable/special
file, symlink/hardlink/mount crossing, case/unicode collision, unsafe mode,
delete, scan-limit, baseline drift, concurrent destination change, changed
second scan, crash in `resolving`, cleanup failure/retry, cross-owner decision,
secret-free API, and blocked-next-run tests. Name each existing hook that
becomes wired; do not create a second `credential_delta.py`.

- [ ] **Step 2: Add a disposable overlay and purpose-bound delivery**

For a measured Docker/Podman Linux-container runtime, take an exclusive session
lease, pause and commit the standing container to a temporary content-addressed
image, copy the private cache volume and a writable workspace tree that excludes
both `.raiker` and `.git`, plus a separate read-only `.git` snapshot into
Raiker-owned per-run staging roots. Mount that snapshot as the sole
`/workspace/.git`; record both baseline manifests and resume the standing
boundary. On any
snapshot failure, resume it, clean temporary material, and fail closed.
Start a disposable clone in which only those two staging roots are writable;
the original workspace, cache, and standing container are never writable or
mounted. Resolve credentials only after authority, compile all values into
streaming redaction, and deliver by a 0600 tmpfs file or inherited descriptor.
Never use argv or persistent environment. Remove delivery material before final
scan and always discard the disposable container layer. A platform/runtime that
cannot pass this real copy-on-write probe advertises
`credential_copy_on_write_unavailable` and refuses credential bindings.

- [ ] **Step 3: Implement failure-closed scan and compare-and-swap resolution**

Every uncertain condition produces `quarantined`. State transitions are
`scanning -> clean|quarantined -> resolving -> merged|discarded|cleanup_failed`.
A fresh owner decision CASes clean to resolving, then a second snapshot/scan
must match baseline and delta before path-by-path governed merge. Quarantined or
changed deltas can only discard. Reconciliation retries cleanup and blocks new
credentialed work until terminal.

Only staged workspace and private-cache creates, regular-file changes,
directories, and explicit manifest deletes are merge candidates. Symlinks,
hardlinks, special files, mount crossings, unsafe modes, unreadable entries,
case/unicode collisions, or any change outside those roots are discard-only.
Never merge container-layer, `.git`, `.raiker`, device, owner, ACL, link, or
mount mutations. Use nofollow traversal, compare each live destination with its
baseline immediately before mutation, refuse concurrent conflicts, stage
replacement bytes on the destination volume, and apply only owner-selected
paths. Normalize file mode to an approved executable/non-executable set.

The real Docker/Podman integration asserts the writable staging tree contains
no duplicate `.git`, the sole `/workspace/.git` mount is read-only, writes under
it fail, and `.git` paths never appear in a delta manifest or merge selection.

- [ ] **Step 4: Add review UI and verify**

Show recipient-TCB warning, safe path/count metadata, both scan digests/states,
and merge/discard controls. Never render matched bytes, values, or raw overlay
paths.

Run: `python -m pytest --basetemp .tmp/pytest-command-credentials tests/test_credential_command_delta.py tests/test_credential_overlay.py tests/test_api_commands.py tests/integration/test_container_credential_copy_on_write.py -q`

Run: `npm --prefix apps/web run test -- CredentialDeltaReview.test.ts CommandOutputPane.test.ts ApprovalsView.test.ts`

```powershell
git add -- raiker/execution/commands/credential_delta.py raiker/execution/commands/credential_overlay.py raiker/execution/commands/backends/container.py raiker/execution/commands/models.py raiker/execution/commands/service.py raiker/execution/commands/store.py raiker/storage/migrations.py raiker/api/routes_commands.py apps/web/src/lib/components/CommandOutputPane.svelte apps/web/src/lib/components/CommandOutputPane.test.ts apps/web/src/lib/components/CredentialDeltaReview.svelte apps/web/src/lib/components/CredentialDeltaReview.test.ts apps/web/src/lib/views/ApprovalsView.svelte apps/web/src/lib/views/ApprovalsView.test.ts tests/test_credential_command_delta.py tests/test_credential_overlay.py tests/test_api_commands.py tests/integration/test_container_credential_copy_on_write.py
git commit -m "feat: quarantine credentialed command deltas"
```

---

### Task 9: Verify runner publisher authenticity and remove placeholder digests

**Files:**
- Modify: `raiker/execution/native_artifacts.py`
- Create: `raiker/execution/windows_authenticode.py`
- Modify: `raiker/execution/commands/backends/native.py`
- Modify: `raiker/execution/commands/backends/container.py`
- Modify: `raiker/app/release.py`
- Create: `native/raiker-runner-launcher/`
- Modify: POSIX installer/package assets under `packaging/`
- Modify: native/package workflows under `.github/workflows/`
- Modify: `apps/web/src/lib/views/settings/Runtime.svelte`
- Modify: `apps/web/src/lib/views/settings/Runtime.test.ts`
- Test: `tests/test_native_artifact_packaging.py`
- Test: `tests/test_windows_authenticode.py`
- Test: `tests/test_runner_trust_integration.py`

**Interfaces:**
- Produces: signed canonical native manifest verification, Windows Authenticode/SPKI/timestamp verdict, signed image-digest pins, explicit development posture.
- Consumes: compiled release public key and existing signed update/release manifest primitives.

- [ ] **Step 1: Write RED tamper/trust-anchor tests**

Cover modified artifact and manifest, wrong release key, writable/missing POSIX
launcher or trust root, package-relative-only posture, wrong publisher/leaf
SPKI, untrusted chain, missing/invalid RFC-3161 timestamp, post-expiry unsigned
binary, revoked/unavailable revocation result, protocol/version downgrade,
catalog/path substitution, placeholder image digest, and development-unverified
posture.

- [ ] **Step 2: Extend the existing verifier**

Verify digest/protocol/minimum version from the canonical artifact manifest. On
Windows call `WinVerifyTrust` for the exact resolved file and require the pinned
leaf SPKI, publisher, trusted chain, RFC-3161 time within certificate validity,
and a successful revocation policy. On POSIX, advertise publisher authenticity
only when a root-owned, non-group/other-writable launcher outside the writable
installation verifies the signed manifest using a root-owned key under
`/etc/raiker/trust.d/`, checks ownership/mode, and launches the exact digest.
An ordinary user install reports `package_relative_integrity`; a package-local
key and verifier must never be labelled publisher-verified.

- [ ] **Step 3: Sign and pin container helper image digests in release output**

Replace `EXPECTED_SUPERVISOR_DIGEST` placeholders with values read from the
verified release manifest. The proxy and supervisor image digests are required
entries; missing or mutable tags fail readiness.

- [ ] **Step 4: Add platform integration workflow and UI**

The Windows workflow signs a fixture with the test publisher, verifies it,
tamper-copies it, and proves refusal. Package smoke installs without the source
tree. The POSIX package workflow installs the launcher/key with root ownership,
proves writable/missing/replaced anchors refuse, and separately proves an
ordinary wheel reports only package-relative integrity. Runtime shows
`Publisher verified`, `Package-relative integrity only`, `Developer build —
unverified`, or a named refusal and never marks a weaker posture
production-isolated.

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest --basetemp .tmp/pytest-runner-trust tests/test_native_artifact_packaging.py tests/test_windows_authenticode.py tests/test_runner_trust_integration.py -q`

Run: `npm --prefix apps/web run test -- Runtime.test.ts`

```powershell
git add -- raiker/execution/native_artifacts.py raiker/execution/windows_authenticode.py raiker/execution/commands/backends/native.py raiker/execution/commands/backends/container.py raiker/app/release.py native/raiker-runner-launcher packaging .github/workflows apps/web/src/lib/views/settings/Runtime.svelte apps/web/src/lib/views/settings/Runtime.test.ts tests/test_native_artifact_packaging.py tests/test_windows_authenticode.py tests/test_runner_trust_integration.py
git commit -m "feat: verify command runner publishers"
```

---

### Task 10: Documentation, four-provider live test, final verification, push, and CI

**Files:**
- Modify: `docs/REFERENCE_PLATFORM_COMPATIBILITY.md`
- Modify: `docs/plans/TO_BE_FIXED.md`
- Modify: `docs/plans/MEMORY_RELIABILITY_PLAN.md`
- Modify: `docs/plans/FIXED_ITEMS.md`
- Modify: `docs/plans/GAP_BUILD_CHAT.md`
- Modify: `docs/plans/TO_BE_ADDED.md`
- Modify: `README.md`
- Modify if needed: `docs/guide/`
- Create reviewed screenshots under: `docs/plans/screenshots/working/`

**Interfaces:**
- Consumes: fresh automated/live evidence.
- Produces: honest closure/gap records, compatibility decisions, final pushed SHA, green workflow evidence.

- [ ] **Step 1: Update compatibility and backlog truth before claims**

For every reference-platform row, record `at parity`, `beyond`, `partial`, or
`absent`, cite current primary sources, and include the categorical meaningful-
improvement decision from the design. A `beyond` decision requires both local
evidence and a primary source establishing the compared reference behavior; do
not infer undocumented absence. Where a source does not establish a reference
control, write `not established by cited source` rather than `absent`. Move only
proven items to `FIXED_ITEMS`.
Remove stale README Known Limits and keep genuine platform limits.

- [ ] **Step 2: Load the Playwright skill and start a clean loopback host**

Confirm no listener remains on port 8765. Start Raiker with test data isolated
from source. Configure Anthropic, OpenRouter, OpenAI, and Ollama through the UI;
do not place keys in a command or environment shown by the transcript.

- [ ] **Step 3: Run live provider and feature scenarios**

For each provider, send one Chat and one Build turn and verify the exact model
readiness plus response. Verify deep-path checkpoint health, a write receipt,
entity scan/review/graph-only recall, SSH/Daytona refusal or execution according
to real configured readiness, filtered egress allow/deny/revoke, credential
delta quarantine, command reload recovery, and honest unsupported Windows
features. Use Rahul / `Ithink@10` only in the local test UI.

- [ ] **Step 4: Capture and inspect responsive screenshots**

Capture 375, 768, 1024, and 1440 pixel views of Memory review, Diagnostics,
Runtime environments, command receipt/output, and approval/delta review. Inspect
for secret leakage, clipping, horizontal overflow, focus/labels, status copy,
and backend truth.

- [ ] **Step 5: Run all local quality gates**

Run: `python -m ruff check .`

Run: `python -m mypy raiker apps tests`

Run: `python -m pytest -q --basetemp .tmp/pytest-full`

Run: `npm run lint`

Run: `npm run check`

Run: `npm run test`

Run: `npm run build`

Run applicable native format, lint, test, package, signature, and tamper gates.

- [ ] **Step 6: Review scope and commit documentation/evidence**

Run: `git diff --check`

Run: `git status --short`

Commit only reviewed documentation and screenshots; no runtime data, API keys,
temporary files, or provider responses containing private content.

- [ ] **Step 7: Push and monitor every workflow for the pushed SHA**

Run: `git push origin main`

Run: `git rev-parse HEAD`

Run: `gh run list --commit <FINAL_SHA> --json databaseId,name,status,conclusion,url,workflowName`

Watch each run. For a failure, inspect its failed log, reproduce locally, add a
failing regression, fix, rerun the affected full gate, commit, push, and monitor
the new SHA. Repeat until every required workflow succeeds.
