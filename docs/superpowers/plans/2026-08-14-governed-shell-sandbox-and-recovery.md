# Governed Shell, Sandbox, and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver market-parity shell capability with authoritative backend selection, native/container/SSH/Daytona isolation, persistent foreground/background/PTY execution, filtered network escalation, live Build output, durable receipts, and restart recovery.

**Architecture:** A backend-neutral `CommandService` owns the durable command lifecycle and delegates only process mechanics to explicit `CommandBackend` implementations. `ToolBroker` and the approval relay use the same service, while command output is redacted before persistence and exposed to Build through owner-scoped catch-up APIs plus metadata-only stream events. The selected environment is authoritative and an unavailable sandbox never falls back to the host.

**Tech Stack:** Python 3.11 dataclasses, protocols, subprocess/PTY and platform sandbox adapters, FastAPI, SQLCipher/SQLite, Svelte 5 and TypeScript, pytest, Vitest, Playwright, Docker/Podman, OpenSSH, Daytona CLI, GitHub Actions.

## Global Constraints

- Raiker remains owner-authoritative and monitored.
- The default rule is sandboxed execution with no network.
- An unavailable sandbox fails closed and never becomes host execution.
- Local host execution is an explicit owner selection and is labelled **Host access — reduced isolation**.
- Execution environment selection and approval policy are independent layers.
- Selecting an environment grants no capability and changes no decision mode.
- Output is redacted before it is streamed, stored, shown, or returned to the model.
- Filesystem and network boundaries cover descendant processes.
- Stop and timeout terminate the complete command process tree.
- `.raiker` is never readable or writable by a command backend; `.git` is read-only except through separately governed git executors.
- Credentials are absent by default and can enter only through a purpose-bound credential grant.
- Raw terminal input is never stored.
- A backend may return unavailable or refused but may never silently substitute another backend.
- A restart may report an unprovable outcome as `lost`; it must never infer success.
- Provider keys are entered only through the UI and never printed, committed, placed in command arguments, or retained in Playwright state.
- Python tests that need temporary files run with `--basetemp .tmp/pytest-<scope>` on this Windows workspace.

---

## File Structure

### New backend-neutral command package

- `raiker/execution/commands/models.py`: immutable request, state, chunk, receipt, feature, and resolution contracts.
- `raiker/execution/commands/store.py`: owner-scoped persistence facade over `SQLiteStore`.
- `raiker/execution/commands/redactor.py`: provably split-safe byte decoding and multi-pattern/structured streaming redaction.
- `raiker/execution/commands/supervisor_protocol.py`: versioned authenticated frames shared by local and backend-resident supervisors.
- `raiker/execution/commands/runner.py`: local supervisor client, bounded capture, timeout, input, and process-tree termination.
- `raiker/execution/commands/backends/base.py`, `local.py`, `native.py`, `container.py`, `remote.py`: independently reviewable backend adapters.
- `raiker/execution/commands/network.py`: domain grants and proxy control client.
- `raiker/execution/commands/credential_broker.py`: secret detection, typed placeholders, purpose-bound injection, and safe display.
- `raiker/execution/commands/receipts.py`: canonical receipt creation and digest.
- `raiker/execution/commands/evidence.py`: checkpoint, symlink-safe change summary, and bounded diagnostic producers.
- `raiker/execution/commands/service.py`: lifecycle operations and environment resolution.
- `raiker/execution/commands/recovery.py`: startup reconciliation and bounded cleanup.
- `raiker/execution/commands/composition.py`: one workspace-scoped service, recovery, and lease-reaper composition root.
- `raiker/api/routes_commands.py`: owner-facing command history, output, input, stop, lease, and reset APIs.

### New packaged security-boundary artifacts

- `native/Cargo.toml`, `native/raiker-command-protocol/`: shared framed protocol, canonical request digest, redaction automaton, and test vectors.
- `native/raiker-command-supervisor/`: backend-resident process/PTY/log/lease supervisor used by container, SSH, and Daytona backends.
- `native/raiker-command-runner/`: Windows AppContainer/restricted-token, Job Object, ConPTY, ACL, named-pipe, and policy client.
- `native/raiker-windows-policy-service/`: installed least-privileged Windows service that owns the WFP dynamic session and authenticates narrowly scoped policy IPC.
- `native/raiker-egress-proxy/`: authenticated HTTP CONNECT and SOCKS5 CONNECT proxy with DNS/address enforcement and connection audits.
- `containers/command-sandbox/Containerfile`: pinned supervisor/proxy artifacts and non-root read-only command image.
- `scripts/install_windows_runner.ps1`, `scripts/uninstall_windows_runner.ps1`: signature/digest verification, elevation UX, transactional policy-service/AppContainer setup, and rollback.
- `.github/workflows/native-security-boundaries.yml`: Linux/Rust tests, Windows helper build/integration tests, artifact digest, and release packaging checks.

### New web components

- `apps/web/src/lib/components/CommandOutputPane.svelte`: resizable pane, run selection, output, status, input, stop, lease, reset, and receipt controls.
- `apps/web/src/lib/components/CommandActivityRow.svelte`: first-class transcript activity linked to the pane.
- `apps/web/src/lib/commandPresentation.ts`: status, reason, stream, failure-coordinate, and boundary presentation helpers.

### Existing files modified

- `raiker/storage/migrations.py`, `raiker/storage/sqlite.py`: command rows, chunks, grants, receipts, owner-scoped queries, and compare-and-swap transitions.
- `raiker/execution/profiles.py`, `raiker/control/dashboard.py`: authoritative command profile and proven feature/readiness projection.
- `raiker/runtime/executors/tier2_shell.py`, `tier5_network.py`, `containers.py`: adapters into the shared command service.
- `raiker/runtime/executors/__init__.py`: inject the single application-scoped `CommandService` into the default registry.
- `raiker/runtime/executors/tier1_approval.py`, `raiker/tools/broker.py`, `raiker/runtime/orchestrator.py`: shared execution path and metadata-only command lifecycle stream.
- `raiker/models/tool_call_validation.py`, `raiker/contracts/models.py`, `raiker/policy/config.py`, `raiker/runtime/authority/router.py`: typed `run_command`/`process` tools and their unchanged governance.
- `raiker/api/app.py`, `raiker/api/dependencies.py`, `raiker/api/schemas.py`: lifespan composition, router registration, shared service injection, strict request bodies, lease reaping, and shutdown.
- `pyproject.toml`, release/build configuration, and Windows installer metadata: package pinned helper/proxy artifacts and verify protocol/digest compatibility.
- `apps/web/src/lib/api.ts`, `apiTypes.ts`, `views/BuildView.svelte`, `views/ApprovalsView.svelte`, `views/settings/Runtime.svelte`: command API, terminal pane, effective boundary, and approval previews.
- planning, Known Limits, compatibility, security, implementation-status, and live-test documents listed in Task 11.

---

### Task 1: Durable command contracts and owner-scoped storage

**Files:**
- Create: `raiker/execution/commands/__init__.py`
- Create: `raiker/execution/commands/models.py`
- Create: `raiker/execution/commands/store.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Create: `tests/test_command_store.py`

**Interfaces:**
- Produces: `CommandRequest`, `CommandState`, `CommandChunk`, `CommandFeatures`, `CommandReceipt`, `CommandResolution`, `CommandStore.create`, `transition`, `append_chunk`, `list_runs`, `read_output`, atomic `finalize_with_receipt`, and `list_recoverable`.
- Consumes: `SQLiteStore.connect`, `new_id`, `utc_now`, and the existing migration registration path.

- [ ] **Step 1: Write failing contract and state-machine tests**

```python
def request(**overrides: object) -> CommandRequest:
    values = {
        "run_id": "cmd_1", "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a", "session_id": "sess_a",
        "turn_id": "turn_a", "action_id": "act_a", "repository_id": None,
        "workspace_root": Path("C:/workspace"), "cwd": ".",
        "executable_template": "npm test", "argv_template": (),
        "safe_display": "npm test", "credential_bindings": (), "shell": True,
        "interactive": False, "background": False, "timeout_seconds": 30.0,
        "max_output_bytes": 100_000, "environment_profile_id": "container_default",
        "network_policy_id": None,
    }
    values.update(overrides)
    return CommandRequest(**values)


def test_request_requires_exactly_one_command_representation() -> None:
    with pytest.raises(ValueError, match="command_representation_invalid"):
        request(executable_template="npm test", argv_template=("npm", "test"))
    with pytest.raises(ValueError, match="command_representation_invalid"):
        request(executable_template="", argv_template=())


def test_terminal_states_require_atomic_finalization() -> None:
    assert can_transition(CommandState.RUNNING, CommandState.FINALIZING)
    assert can_transition(CommandState.FINALIZING, CommandState.SUCCEEDED)
    assert not can_transition(CommandState.SUCCEEDED, CommandState.FAILED)


@pytest.mark.parametrize("terminal", TERMINAL_COMMAND_STATES)
def test_terminal_transition_requires_receipt_in_same_transaction(store, terminal) -> None:
    store.create_finalizing(request())
    with pytest.raises(ReceiptRequired):
        store.transition("owner_a", "cmd_1", CommandState.FINALIZING, terminal)
    store.finalize_with_receipt("owner_a", "cmd_1", terminal, receipt_for(terminal))
    assert store.receipt_count("cmd_1") == 1
```

- [ ] **Step 2: Run the model tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_store.py -q --basetemp .tmp/pytest-command-store`

Expected: collection fails because `raiker.execution.commands` does not exist.

- [ ] **Step 3: Implement immutable models and transition rules**

```python
class CommandState(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    CONTAINED = "contained"
    LOST = "lost"


TERMINAL_COMMAND_STATES = frozenset({
    CommandState.SUCCEEDED, CommandState.FAILED, CommandState.TIMED_OUT,
    CommandState.CANCELLED, CommandState.CONTAINED, CommandState.LOST,
})


def can_transition(current: CommandState, target: CommandState) -> bool:
    return target in {
        CommandState.QUEUED: {CommandState.STARTING, CommandState.CANCELLED},
        CommandState.STARTING: {CommandState.RUNNING, CommandState.FINALIZING, CommandState.CONTAINED},
        CommandState.RUNNING: {CommandState.FINALIZING},
        CommandState.FINALIZING: TERMINAL_COMMAND_STATES,
    }.get(current, set())
```

`CommandRequest.__post_init__` enforces the mutually exclusive template contract, positive timeout/output limits, relative contained cwd, required identity fields, and safe-display/template digest consistency. Literal registered or pattern-matched secrets fail before `CommandStore.create`; credential references are typed placeholders only.

- [ ] **Step 4: Write failing migration, ownership, chunk-order, and compare-and-swap tests**

```python
def test_command_store_is_owner_scoped_and_chunks_are_monotonic(workspace: Path) -> None:
    sqlite = SQLiteStore(workspace)
    store = CommandStore(sqlite)
    store.create(request())
    assert store.transition("owner_a", "cmd_1", CommandState.QUEUED, CommandState.STARTING)
    assert not store.transition("owner_a", "cmd_1", CommandState.QUEUED, CommandState.RUNNING)
    store.append_chunk("owner_a", CommandChunk("cmd_1", 1, "stdout", "one", 3, utc_now()))
    store.append_chunk("owner_a", CommandChunk("cmd_1", 2, "stderr", "two", 3, utc_now()))
    assert [row.sequence for row in store.read_output("owner_a", "cmd_1", after=0)] == [1, 2]
    assert store.list_runs("owner_b", session_id="sess_a") == []
```

- [ ] **Step 5: Run the storage test and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_store.py -q --basetemp .tmp/pytest-command-store`

Expected: failure because the migration and `CommandStore` methods are absent.

- [ ] **Step 6: Add `RAIKER-2030-command-runs` and the persistence facade**

```sql
CREATE TABLE IF NOT EXISTS command_runs (
  run_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  acting_principal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  state TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  backend TEXT NOT NULL DEFAULT '',
  safe_display TEXT NOT NULL,
  template_digest TEXT NOT NULL,
  encrypted_execution_material BLOB NOT NULL,
  isolation_json TEXT NOT NULL DEFAULT '{}',
  encrypted_backend_handle BLOB,
  started_at TEXT,
  completed_at TEXT,
  lease_expires_at TEXT,
  exit_code INTEGER,
  termination_reason TEXT,
  stdout_bytes INTEGER NOT NULL DEFAULT 0,
  stderr_bytes INTEGER NOT NULL DEFAULT 0,
  truncated INTEGER NOT NULL DEFAULT 0,
  redaction_count INTEGER NOT NULL DEFAULT 0,
  receipt_digest TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_command_runs_owner_session
  ON command_runs(owner_principal_id, session_id, created_at DESC);
CREATE TABLE IF NOT EXISTS command_output_chunks (
  owner_principal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  stream TEXT NOT NULL,
  text TEXT NOT NULL,
  start_byte_offset INTEGER NOT NULL,
  end_byte_offset INTEGER NOT NULL,
  byte_count INTEGER NOT NULL,
  emitted_at TEXT NOT NULL,
  PRIMARY KEY (run_id, sequence),
  FOREIGN KEY (run_id) REFERENCES command_runs(run_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS command_network_grants (
  grant_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  run_id TEXT,
  scope_json TEXT NOT NULL,
  decision_id TEXT NOT NULL,
  status TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  uses INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS command_network_attempts (
  attempt_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  grant_id TEXT NOT NULL,
  requested_host TEXT NOT NULL,
  requested_port INTEGER NOT NULL,
  resolved_address_digest TEXT NOT NULL,
  decision TEXT NOT NULL,
  outcome TEXT NOT NULL,
  bytes_sent INTEGER NOT NULL DEFAULT 0,
  bytes_received INTEGER NOT NULL DEFAULT 0,
  opened_at TEXT NOT NULL,
  closed_at TEXT
);
CREATE TABLE IF NOT EXISTS command_receipts (
  run_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES command_runs(run_id) ON DELETE CASCADE
);
```

Encrypt executable templates, typed credential bindings, and supervisor handles with the existing vault envelope; only safe display and digests are queryable. Enforce owner id in every read/update query and use `UPDATE ... WHERE state = ?` for state transitions. Add owner/run indexes and quotas for chunks and connection attempts, immutable receipt insertion, terminal-only retention cleanup, and migration idempotence/rollback tests.

Add failing tests before this implementation for: a registered/pattern-matched secret never appearing in any database column; encrypted material failing closed when the vault is locked; byte offsets remaining gap-free after pagination; cross-owner attempt/receipt isolation; per-run/per-owner quota enforcement; idempotent migration rerun and rollback after an injected DDL failure; and receipt insertion refusing replacement.

- [ ] **Step 7: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_store.py -q --basetemp .tmp/pytest-command-store`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands raiker/storage/migrations.py raiker/storage/sqlite.py tests/test_command_store.py
git commit -m "feat: persist governed command runs"
```

---

### Task 2: Streaming runner, split-safe redaction, PTY, and process-tree stop

**Files:**
- Create: `native/Cargo.toml`
- Create/update: `native/Cargo.lock`
- Create: `native/raiker-command-protocol/Cargo.toml`
- Create: `raiker/execution/commands/redactor.py`
- Create: `raiker/execution/commands/supervisor_protocol.py`
- Create: `raiker/execution/commands/runner.py`
- Modify: `raiker/context/redaction.py`
- Create: `native/raiker-command-protocol/src/lib.rs`
- Create: `native/raiker-command-supervisor/src/main.rs`
- Create: `native/raiker-command-supervisor/Cargo.toml`
- Create: `native/raiker-command-protocol/tests/vectors.rs`
- Create: `tests/test_command_runner.py`
- Create: `tests/test_command_supervisor_protocol.py`

**Interfaces:**
- Consumes: `CommandRequest`, `CommandChunk`, registered/pattern secrets, vault instance key, protocol test vectors.
- Produces: `StreamingRedactor`, authenticated framed `SupervisorClient`, supervisor run identity/log/status/PTY/lease records, `RunningProcess.poll`, `wait`, `write`, `terminate`, and `reattach`.

- [ ] **Step 1: Write failing concurrent-stream, truncation, and split-token tests**

```python
SECRET_PAYLOAD = ("prefix " + LONG_SECRET + " suffix").encode()


@pytest.mark.parametrize("split", range(len(SECRET_PAYLOAD) + 1))
def test_no_secret_prefix_is_emitted_at_any_split(split: int) -> None:
    redactor = StreamingRedactor(registered=(LONG_SECRET,), structured=PEM_RULES)
    emitted = redactor.feed(SECRET_PAYLOAD[:split])
    emitted += redactor.feed(SECRET_PAYLOAD[split:])
    emitted += redactor.finish()
    assert LONG_SECRET.encode() not in emitted
    assert emitted == b"prefix [REDACTED_CREDENTIAL] suffix"


def test_redactor_handles_utf8_boundaries_concurrent_streams_pem_and_truncation() -> None:
    result = adversarial_redaction_matrix(
        registered=("x" * 4097,),
        payloads=(UTF8_SPLITS, PEM_EVERY_SPLIT, INTERLEAVED_STDOUT_STDERR),
        truncate_at=(0, 1, 255, 4096),
    )
    assert result.persisted_secrets == []
    assert result.notified_before_safe == []


@pytest.mark.parametrize("mode", ["default", "locator", "identifier", "digest"])
def test_streaming_redaction_matches_existing_contract_at_every_byte_split(mode) -> None:
    for vector in load_redaction_vectors(mode):
        expected, _ = redact_text(vector.text, **vector.mode_kwargs)
        for split in range(len(vector.encoded) + 1):
            actual = stream_redact(vector.encoded[:split], vector.encoded[split:], mode=mode)
            assert actual.decode("utf-8", errors="replace") == expected


def test_runner_records_total_bytes_after_capture_is_truncated(tmp_path: Path) -> None:
    sink = RecordingSink()
    process = FakeProcess([("stdout", b"1234567890")], returncode=0)
    handle = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(workspace_root=tmp_path, max_output_bytes=5), ["fake"], tmp_path, {}, sink, pty=False
    )
    handle.wait()
    assert sink.stdout_bytes == 10
    assert sink.captured_text == "12345"
    assert sink.truncated is True
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_runner.py -q --basetemp .tmp/pytest-command-runner`

Expected: import failure for `StreamingCommandRunner`.

- [ ] **Step 3: Implement a provably split-safe streaming automaton and shared vectors**

```python
class StreamingRedactor:
    def feed(self, data: bytes) -> bytes:
        text = self.decoder.decode(data, final=False)
        # pending is the exact longest automaton prefix that can still match.
        # Structured rules withhold from start marker through validated end.
        return self.machine.consume(text)

    def finish(self) -> bytes:
        return self.machine.consume(self.decoder.decode(b"", final=True), final=True)
```

Move the current `_PATTERNS` contract into one versioned rule manifest consumed
by `redact_text` and the Python/Rust streaming compilers. Cover private keys;
GitHub/OpenAI/AWS tokens; bearer headers; assignments and spoken credentials;
email/card/account/medical ids; high entropy; registered values; snake/server-
id/path/digest exemptions; every minimum/word/EOF boundary; and callable
replacement branches. Generate common JSON vectors for default, locator,
identifier, and digest modes at every byte split, including secrets longer than
any input chunk, overlaps, invalid/split UTF-8, flush, truncation, and concurrent
stream ordering. Assert exact equivalence to `redact_text`. Nothing reaches a
sink or durable supervisor frame until the machine proves it safe.

- [ ] **Step 4: Write failing timeout, PTY input, and descendant-stop tests**

```python
def test_timeout_terminates_process_tree(tmp_path: Path) -> None:
    process = HangingProcess()
    handle = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(workspace_root=tmp_path, timeout_seconds=0.01), ["fake"], tmp_path, {}, RecordingSink(), pty=False
    )
    assert handle.wait() == CommandState.TIMED_OUT
    assert process.tree_terminated is True


def test_input_requires_a_pty_and_is_not_recorded(tmp_path: Path) -> None:
    handle = runner_with_fake_pty(tmp_path)
    handle.write("owner input\n")
    assert handle.process.stdin_bytes == b"owner input\n"
    assert handle.sink.input_events == [{"byte_count": 12}]
```

- [ ] **Step 5: Implement the authenticated backend-resident supervisor and local adapters**

```python
class SupervisorClient:
    def start(self, request: SupervisorStart) -> SupervisorIdentity: ...
    def attach(self, identity: SupervisorIdentity) -> SupervisorSession: ...
```

Use versioned length-prefixed frames authenticated by a vault-held instance key.
The supervisor durably creates run identity, request digest, process start
identity, append-only redacted log, atomic status/lease, and optional PTY endpoint
before launch; it installs the exit callback before spawning and owns the
process group/Job Object. Reattachment must prove supervisor instance, request
digest, PID/start identity, and authenticated transport. Refuse unsupported
background/PTY/recovery features instead of controlling only a Docker/SSH client.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_runner.py tests/test_command_supervisor_protocol.py -q --basetemp .tmp/pytest-command-runner`

Run: `cargo test --manifest-path native/Cargo.toml -p raiker-command-protocol -p raiker-command-supervisor`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/redactor.py raiker/execution/commands/supervisor_protocol.py raiker/execution/commands/runner.py raiker/context/redaction.py native/Cargo.toml native/Cargo.lock native/raiker-command-protocol native/raiker-command-supervisor tests/test_command_runner.py tests/test_command_supervisor_protocol.py
git commit -m "feat: stream bounded command output"
```

---

### Task 3: Authoritative environment resolution, local strict, and native sandbox drivers

**Files:**
- Modify: `native/Cargo.toml`
- Modify: `native/Cargo.lock`
- Create: `raiker/execution/commands/backends/base.py`
- Create: `raiker/execution/commands/backends/local.py`
- Create: `raiker/execution/commands/backends/native.py`
- Create: `native/raiker-command-runner/Cargo.toml`
- Create: `native/raiker-command-runner/src/main.rs`
- Create: `native/raiker-command-runner/src/token.rs`
- Create: `native/raiker-command-runner/src/job.rs`
- Create: `native/raiker-command-runner/src/pipe.rs`
- Create: `native/raiker-command-runner/src/appcontainer.rs`
- Create: `native/raiker-command-runner/src/policy_client.rs`
- Create: `native/raiker-windows-policy-service/src/main.rs`
- Create: `native/raiker-windows-policy-service/Cargo.toml`
- Create: `native/raiker-windows-policy-service/src/service.rs`
- Create: `native/raiker-windows-policy-service/src/pipe.rs`
- Create: `native/raiker-windows-policy-service/src/wfp.rs`
- Create: `native/raiker-windows-policy-service/src/transaction.rs`
- Create: `scripts/install_windows_runner.ps1`
- Create: `scripts/uninstall_windows_runner.ps1`
- Create: `.github/workflows/native-security-boundaries.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `pyproject.toml`
- Create: `raiker/execution/native_artifacts.py`
- Modify: `raiker/execution/profiles.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/runtime/command_policy.py`
- Create: `tests/test_command_backends.py`
- Create: `tests/test_windows_command_runner.py`
- Create: `tests/test_native_artifact_packaging.py`
- Create: `native/raiker-command-runner/tests/windows_boundary.rs`
- Modify: `tests/test_execution_environments.py`

**Interfaces:**
- Consumes: `CommandRequest`, `StreamingCommandRunner`, selected environment rows, existing strict command validation.
- Produces: `CommandBackend`, `LocalStrictBackend`, `NativeSandboxBackend`, `NativeSandboxDriver`, `resolve_command_environment(store, owner, tool_name)`, and feature/readiness projection.

- [ ] **Step 1: Write failing selected-profile and no-fallback tests**

```python
def test_selected_command_environment_is_authoritative(store: SQLiteStore) -> None:
    store.select_execution_environment("owner_a", "container_a")
    resolution = resolve_command_environment(store, "owner_a", "shell")
    assert resolution.profile.profile_id == "container_a"


def test_unavailable_selected_sandbox_never_calls_local_runner(store: SQLiteStore) -> None:
    local = Mock()
    backend = backend_registry(local=local, container=UnavailableBackend("container_daemon_unreachable"))
    service = command_service(store, backends=backend, selected="container_a")
    result = service.start(request(environment_profile_id="container_a"))
    assert result.reason_code == "container_daemon_unreachable"
    local.start.assert_not_called()
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_backends.py tests/test_execution_environments.py -q --basetemp .tmp/pytest-command-backends`

Expected: resolution does not consult the selected environment.

- [ ] **Step 3: Implement command-specific resolution and honest feature projection**

```python
@dataclass(frozen=True)
class CommandFeatures:
    shell: bool
    background: bool
    pty: bool
    input: bool
    filtered_network: bool
    persistent: bool
    recoverable: bool
    concurrent_runs: bool


def resolve_command_environment(store: SQLiteStore, owner_principal_id: str, tool_name: str) -> CommandResolution:
    profile_id = store.selected_execution_environment(owner_principal_id)
    profile = load_command_profile(store, owner_principal_id, profile_id)
    if profile is None:
        return CommandResolution(None, "selected_environment_unavailable")
    if tool_name not in {"shell", "run_command", "process"}:
        return CommandResolution(None, "selected_environment_tool_unsupported")
    return probe_profile(profile)
```

The Runtime API returns distinct `selected_for_commands`, `assigned_tools`, `features`, `probe_checked_at`, and `availability_reason` fields.

- [ ] **Step 4: Write native driver command and readiness tests**

```python
@pytest.mark.parametrize((platform, marker), [
    ("linux", "bwrap"), ("darwin", "sandbox-exec"), ("win32", "raiker-command-runner.exe"),
])
def test_native_driver_wraps_command_and_denies_network(platform: str, marker: str, tmp_path: Path) -> None:
    driver = native_driver(platform, helper_root=tmp_path)
    command = driver.command(request(workspace_root=tmp_path), ["npm", "test"])
    assert marker in command[0]
    assert driver.policy(request(workspace_root=tmp_path)).network == "none"
    assert ".raiker" in driver.policy(request(workspace_root=tmp_path)).protected_paths


def test_native_probe_proves_protected_paths_descendants_and_network(boundary) -> None:
    proof = boundary.probe_with_descendant()
    assert proof.workspace_write is True
    assert proof.raiker_read is False and proof.raiker_write is False
    assert proof.git_read is True and proof.git_write is False
    assert proof.outside_workspace_write is False
    assert proof.direct_network is False
    assert proof.descendant_survived_stop is False
```

- [ ] **Step 5: Implement native probes and local strict adapter**

```python
class LocalStrictBackend:
    features = CommandFeatures(
        shell=True, background=False, pty=False, input=False,
        filtered_network=False, persistent=False, recoverable=False,
        concurrent_runs=False,
    )

    def start(self, request: CommandRequest) -> CommandHandle:
        if request.shell:
            raise CommandBackendError("local_strict_shell_source_denied")
        validate_command(request.argv_template, workspace_root=request.workspace_root, allowlist=ALLOWED_SHELL_COMMANDS)
        return self.local_supervisor.start(request, list(request.argv_template), sandbox_environment(workspace_root=request.workspace_root))
```

`local_strict` is foreground-only and rejects credential bindings and
filtered-network grants because
it does not isolate commands from the Raiker/user process identity. For every
other backend, readiness either proves distinct per-run principal/PID and
private-process/control/log/PTY/network boundaries, or sets
`concurrent_runs=false`; a second start while a run is alive then fails with
`environment_busy`. Add two-hostile-run tests for each backend that advertises
concurrency, and busy/refusal tests for every serialized backend.

Linux uses `bwrap`; macOS uses a generated Seatbelt profile. Windows builds a
Rust helper whose versioned named pipe rejects remote clients, is ACL-limited to
the owner SID/LocalSystem, and verifies nonce-bound Ed25519-signed requests,
opens/canonicalizes handles before applying ACLs, and inherits only an explicit
supervisor/ConPTY handle list. It creates a per-run AppContainer SID under the
owner/profile prefix, a
low-integrity restricted AppContainer token without network capability in
offline mode (filtered mode adds only the client capability required to reach
the proxy and relies on the scoped WFP deny/permit policy), a
minimum workspace ACL that denies `.raiker` and `.git` writes, and a
kill-on-close Job Object with CPU/memory/process limits. Installer scripts verify
the Authenticode chain/digest and install the `RaikerCommandPolicy` service once
with owner confirmation. The service runs under a least-privileged service SID
and owns the long-lived WFP dynamic session. Its local named pipe is ACL-limited
to LocalSystem and the installing owner SID, rejects remote clients,
impersonates the caller, and verifies owner SID, instance id, nonce replay
window, timestamp/expiry, per-run AppContainer SID, proxy endpoint, grant id,
and runner/proxy digests. Install creates the Ed25519 private key in Raiker's
vault; the elevated installer pins only its public key. Administrator-only HKLM
configuration pins that key, publisher, protocol, runner/proxy digests,
AppContainer prefix, and allowed proxy endpoint;
IPC cannot create arbitrary filters. ALE filters scoped to the AppContainer
deny outbound and permit only that proxy. A crash closes the dynamic session
and all filters; restart opens a clean session but requires Raiker to
re-authenticate active grants before permits return. Readiness proves the
service/session live. Installer/update/uninstall/profile reset roll back
filters, profiles, ACLs, service registration, and configuration. Ordinary
commands do not elevate. Owner-confirmed rotation atomically installs a new
public key using a request signed by the old key; a lost/corrupt key or owner SID
change requires full elevated reset, which removes active filters/profiles before
pinning a replacement.

Every advertised platform runs traversal, symlink/junction, nested-repository,
Windows path/case, descendant, `.raiker` read/write denial, `.git` write denial,
outside-workspace denial, and direct-network probes. Windows CI builds the
runner and policy service, runs protocol/unit tests, installs the service and
test rules, proves a service crash removes filters and restart stays fail-closed
until re-authentication, executes the boundary test, verifies uninstall/rollback,
tests install/rotation/owner change/reset/replay/corrupt-key/uninstall, and
publishes digest-checked artifacts. Any missing signature/digest/service/
session/firewall/probe returns
`native_sandbox_probe_failed`; native mode never degrades to local strict.

Add runner/service crates to the Cargo workspace and lockfile. Release jobs
build the supervisor, Windows runner, and policy service artifacts, record
SHA-256/protocol metadata, include them
as wheel package-data and Windows installer payloads, and
`native_artifacts.py` resolves only a platform artifact whose manifest, digest,
publisher, and protocol match. A clean-install test builds a wheel, installs it
into an empty virtual environment, removes the source checkout from import/PATH
resolution, and proves readiness finds the packaged helper. Missing or tampered
artifacts fail closed.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_backends.py tests/test_execution_environments.py tests/test_command_sandbox.py -q --basetemp .tmp/pytest-command-backends`

Run on Windows: `cargo test --manifest-path native/Cargo.toml -p raiker-command-runner --test windows_boundary`

Expected: all tests pass.

```powershell
git add -- native/Cargo.toml native/Cargo.lock native/raiker-command-runner native/raiker-windows-policy-service scripts/install_windows_runner.ps1 scripts/uninstall_windows_runner.ps1 .github/workflows/native-security-boundaries.yml .github/workflows/release.yml pyproject.toml raiker/execution/native_artifacts.py raiker/execution/commands/backends raiker/execution/profiles.py raiker/control/dashboard.py raiker/runtime/command_policy.py tests/test_command_backends.py tests/test_windows_command_runner.py tests/test_native_artifact_packaging.py tests/test_execution_environments.py
git commit -m "feat: enforce selected command environment"
```

---

### Task 4: Persistent Docker and Podman command sandbox

**Files:**
- Create: `raiker/execution/commands/backends/container.py`
- Create: `raiker/execution/commands/cache_snapshots.py`
- Create: `raiker/execution/commands/credential_delta.py`
- Create: `containers/command-sandbox/Containerfile`
- Modify: `raiker/runtime/executors/containers.py`
- Modify: `raiker/execution/container_tools.py`
- Modify: `raiker/execution/tool_bridge.py`
- Create: `tests/test_persistent_command_container.py`
- Create: `tests/test_command_cache_snapshots.py`
- Create: `tests/test_credential_command_delta.py`
- Modify: `tests/test_container_tool_bridge.py`

**Interfaces:**
- Consumes: `CommandBackend`, `CommandRequest`, `SupervisorClient`, pinned supervisor image digest, validated container profile.
- Produces: `PersistentContainerBackend`, persistent session cache/workspace state, isolated per-run worker names/identities/networks, authenticated supervisor start/attach/reset/recreate/recover operations, and actual container-shell support.

- [ ] **Step 1: Write failing container creation and reuse tests**

```python
def test_session_state_is_reused_but_each_run_has_an_isolated_worker(tmp_path: Path) -> None:
    runtime = RecordingContainerRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path)
    first = backend.start(request(session_id="sess_a"), RecordingSink())
    second = backend.start(request(run_id="cmd_2", session_id="sess_a"), RecordingSink())
    assert runtime.create_calls == 2
    create = runtime.commands[0]
    assert ["--network", "none"] == adjacent(create, "--network")
    assert "--read-only" in create and ["--cap-drop", "ALL"] == adjacent(create, "--cap-drop")
    assert raiker_mask(create).source == runtime.inaccessible_empty_mask_dir
    assert raiker_mask(create).readonly is True
    assert runtime.stat(runtime.inaccessible_empty_mask_dir).mode == 0
    assert git_mount(create).readonly is True
    assert supervisor_digest(create) == EXPECTED_SUPERVISOR_DIGEST
    assert first.backend_handle.container_id != second.backend_handle.container_id
    assert first.backend_handle.cache_base_digest == second.backend_handle.cache_base_digest
    assert first.backend_handle.private_cache_volume != second.backend_handle.private_cache_volume


def test_hostile_concurrent_workers_cannot_cross_run_boundaries(live_backend) -> None:
    victim = live_backend.start(run_with_network_grant())
    attacker = live_backend.start(hostile_inspection_run())
    assert attacker.sibling_processes == []
    assert attacker.signal_victim == "denied"
    assert attacker.read_victim_proc_fds == "denied"
    assert attacker.read_victim_control_or_logs == "denied"
    assert attacker.recovered_credentials == []
    assert attacker.use_victim_proxy_capability == "denied"
    victim.stop()


def test_credential_bound_worker_holds_exclusive_environment_lease(live_backend) -> None:
    victim = live_backend.start(run_with_credential())
    assert live_backend.start(hostile_inspection_run()).reason_code == "credential_environment_busy"
    victim.stop()


@pytest.mark.parametrize("location", ["workspace", "cache", "filename", "xattr", "ads", "symlink", "binary"])
def test_credential_delta_is_quarantined_before_later_worker(location, live_backend) -> None:
    secret = live_backend.register_credential("credential-value-123456789")
    run = live_backend.start(write_credential_to_delta(secret, location))
    result = run.wait()
    assert result.delta_state == "quarantined_secret_detected"
    assert live_backend.start(request(run_id="later")).reason_code == "credential_delta_resolution_required"
    live_backend.discard_delta(run.run_id, owner_decision())
    later = live_backend.start(request(run_id="later"))
    assert secret not in later.read_workspace_and_cache()
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_persistent_command_container.py -q --basetemp .tmp/pytest-command-container`

Expected: `PersistentContainerBackend` is absent.

- [ ] **Step 3: Implement labelled persistent creation and full shell exec**

```python
def command_container_name(owner: str, session: str, profile: str, run_id: str) -> str:
    digest = sha256(f"{owner}\0{session}\0{profile}\0{run_id}".encode()).hexdigest()[:24]
    return f"raiker-cmd-{digest}"


def supervisor_start(profile: ExecutionProfile, request: CommandRequest) -> SupervisorStart:
    return SupervisorStart(
        shell_path=profile.shell_path,
        template=request.executable_template,
        request_digest=request.template_digest,
    )
```

Build the supervisor into a digest-pinned non-root image. Persist session state
as the host workspace plus a committed cache snapshot, but create a separate read-only-root
worker container, non-root uid, PID namespace, supervisor/control mount, and
network namespace for every run. A cache service copies the committed snapshot
into a private per-run volume; no two workers share writable cache state. On
copy-out it accepts bounded directories/regular files only, strips executable,
setuid and setgid bits, rejects symlinks/hard links/sockets/devices/FIFOs, and
atomically publishes a new snapshot after conflict detection. The worker gets
bounded tmpfs, that private cache, and workspace bind; after that mount, over-mount `.git` read-only and
mask `.raiker` with a Raiker-owned empty mode-`000`, unmapped-owner, read-only
bind so listing and all access fail. Reject `.git`/`.raiker`
symlink or reparse targets in preflight. Use no capabilities, no-new-privileges,
CPU/memory/PID/lease labels, and no ambient environment. Supervisor state,
credentials, logs, and proxy capabilities never enter cache. Advertise disk
quota only when proven. A short-lived `exec` may transport a control frame but
never owns lifetime, logs, PTY, or kill.

Credential-bearing workers acquire an exclusive environment lease and receive
private ephemeral workspace and cache snapshots; the real state is read-only.
After exit, scan every changed path/content/name/symlink target/xattr/ADS and
bounded binary string for the exact registered values plus the full pattern
manifest. A match quarantines the complete delta and blocks later workers until
an owner-confirmed discard. A clean delta presents selective file merge; apply
only owner-selected paths after canonical containment and a second byte-for-byte
scan through governed file/checkpoint APIs. Cache merge uses the validated cache
service. The UI warns that the recipient command is in the credential TCB and
can transform, persist, or exfiltrate the value; quarantine is defense-in-depth
for exact/pattern-detectable local persistence, not malicious-recipient DLP. Add both
lease orderings, every location case above, clean selective merge, rescan race,
and later-worker denial tests. Credential-free workers may overlap with separate
kernel/control/network/cache identities; the host workspace remains explicit
shared mutable session state.

- [ ] **Step 4: Write failing reset, recovery, daemon-probe, and no-host-fallback tests**

```python
def test_recreate_removes_state_but_reset_processes_keeps_volume(tmp_path: Path) -> None:
    runtime = RecordingContainerRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path)
    backend.start(request(run_id="worker_a"))
    backend.reset("owner_a", "sess_a", "container_a", recreate=False)
    assert runtime.kill_process_calls == 1 and runtime.remove_calls == 0
    backend.start(request(run_id="worker_b"))
    backend.reset("owner_a", "sess_a", "container_a", recreate=True)
    assert runtime.kill_process_calls == 2 and runtime.remove_volume_calls == 1


def test_daemon_probe_requires_a_runnable_approved_image(tmp_path: Path) -> None:
    probe = probe_container_profile(profile(), runner=daemon_without_image)
    assert probe.available is False
    assert probe.reason_code == "container_image_unavailable:container_a"


def test_reattach_after_raiker_restart_keeps_run_identity(container_backend) -> None:
    run = container_backend.start(background_request())
    restarted = container_backend.new_client_after_raiker_restart()
    attached = restarted.attach(run.encrypted_handle)
    assert attached.run_identity == run.run_identity
    assert attached.log(after=0).sequence > 0
    attached.kill("owner_stop")
    assert attached.descendants_alive() is False
```

- [ ] **Step 5: Implement probe, reset, recreate, and labelled recovery**

Only reuse or remove containers whose Raiker labels, supervisor instance id,
image digest, request digest, and workspace bounds match the durable encrypted
handle. A name match without proof is `container_identity_mismatch` and is never
touched. Add a live service-process restart test, an expired-lease reaper test,
and a deliberately corrupted supervisor identity test that produces `lost`.
Add live `.raiker` tests for listing, reads, writes, `..` traversal, symlink and
junction access, plus the two-hostile-worker test above. Prove workers cannot
signal/inspect each other, read sibling descriptors/control/logs/credentials,
or use the other worker's network capability. Reset-processes removes every
worker but retains cache/workspace; recreate also removes cache state.

- [ ] **Step 6: Complete the generic bridge's shell claim**

`CONTAINER_PROFILE_TOOLS`, `CONTAINER_SAFE_TOOLS`, and Runtime `supported_tools` must agree. The command sandbox uses `PersistentContainerBackend`; read-only ephemeral bridge tools keep the JSON protocol. Delete the misleading path that advertises `shell` to the read-only bridge without an executor.

- [ ] **Step 7: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_persistent_command_container.py tests/test_command_cache_snapshots.py tests/test_credential_command_delta.py tests/test_container_tool_bridge.py tests/test_execution_profiles.py tests/test_execution_environments.py -q --basetemp .tmp/pytest-command-container`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/backends/container.py raiker/execution/commands/cache_snapshots.py raiker/execution/commands/credential_delta.py containers/command-sandbox/Containerfile raiker/runtime/executors/containers.py raiker/execution/container_tools.py raiker/execution/tool_bridge.py tests/test_persistent_command_container.py tests/test_command_cache_snapshots.py tests/test_credential_command_delta.py tests/test_container_tool_bridge.py
git commit -m "feat: add persistent command sandbox"
```

---

### Task 5: Filtered command-network grants and isolated proxy topology

**Files:**
- Modify: `native/Cargo.toml`
- Modify: `native/Cargo.lock`
- Create: `native/raiker-egress-proxy/Cargo.toml`
- Create: `raiker/execution/commands/network.py`
- Create: `native/raiker-egress-proxy/src/main.rs`
- Create: `native/raiker-egress-proxy/src/http_connect.rs`
- Create: `native/raiker-egress-proxy/src/socks5.rs`
- Create: `native/raiker-egress-proxy/src/policy.rs`
- Modify: `raiker/execution/commands/backends/container.py`
- Modify: `raiker/execution/commands/backends/native.py`
- Modify: `containers/command-sandbox/Containerfile`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/release.yml`
- Modify: `raiker/execution/native_artifacts.py`
- Modify: `raiker/api/schemas.py`
- Create: `tests/test_command_network.py`
- Create: `native/raiker-egress-proxy/tests/egress_boundary.rs`
- Modify: `tests/test_native_artifact_packaging.py`

**Interfaces:**
- Consumes: command grant/attempt rows, vault instance key, public-address checks from `raiker.runtime.web_policy`, backend route/firewall adapters.
- Produces: `CommandNetworkScope`, `CommandNetworkBroker.authorize`, `revoke`, authenticated proxy control/data protocol, HTTP CONNECT/SOCKS5 CONNECT listeners, immutable attempt audit, private container network/sidecar lifecycle, and `command_network_approval_required`.

- [ ] **Step 1: Write failing scope, address, expiry, and revocation tests**

```python
def test_network_scope_matches_only_named_public_domain_and_port() -> None:
    scope = CommandNetworkScope(("registry.npmjs.org",), (443,))
    assert scope.allows("registry.npmjs.org", 443, [ip_address("104.16.0.1")])
    assert not scope.allows("evil.example", 443, [ip_address("104.16.0.1")])
    assert not scope.allows("registry.npmjs.org", 443, [ip_address("127.0.0.1")])


def test_revoked_grant_stops_authorizing_immediately(store: CommandStore) -> None:
    broker = CommandNetworkBroker(store)
    grant = broker.grant("owner_a", "sess_a", "cmd_1", ["registry.npmjs.org"], [443], "decision_1", expires_in=60)
    assert broker.authorize(grant.grant_id, "registry.npmjs.org", 443).allowed
    broker.revoke("owner_a", grant.grant_id)
    assert broker.authorize(grant.grant_id, "registry.npmjs.org", 443).reason_code == "command_network_grant_revoked"
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_network.py -q --basetemp .tmp/pytest-command-network`

Expected: network broker imports fail.

- [ ] **Step 3: Implement exact domain/port scopes and public-address guard**

```python
@dataclass(frozen=True)
class CommandNetworkScope:
    domains: tuple[str, ...]
    ports: tuple[int, ...]

    def allows(self, host: str, port: int, addresses: Sequence[IPv4Address | IPv6Address]) -> bool:
        return (
            port in self.ports
            and any(host_matches(host, rule) for rule in self.domains)
            and bool(addresses)
            and all(address.is_global for address in addresses)
        )
```

Store only scope, decision, expiry, status, use count, host/port, byte counts, and outcome. Never store request/response bodies.

- [ ] **Step 4: Write failing isolated-network and redirect/rebinding tests**

```python
def test_container_has_only_internal_proxy_network() -> None:
    plan = container_proxy_plan("cmd_1", scope())
    assert plan.command_network.internal is True
    assert plan.command_network.members == ("command", "proxy")
    assert plan.proxy_network.members == ("proxy",)
    assert plan.command_has_direct_egress is False


def test_proxy_rechecks_each_resolution_and_redirect() -> None:
    resolver = iter([["104.16.0.1"], ["127.0.0.1"]])
    broker = proxy_with_resolver(lambda _host: next(resolver))
    assert broker.connect("registry.npmjs.org", 443).allowed
    assert broker.redirect("registry.npmjs.org", 443).reason_code == "command_network_private_address_denied"


def test_direct_socket_fails_but_capability_bound_proxy_succeeds(live_sandbox) -> None:
    assert live_sandbox.direct_connect("registry.npmjs.org", 443).denied
    capability = live_sandbox.grant_once("registry.npmjs.org", 443)
    assert live_sandbox.http_connect(capability, "registry.npmjs.org", 443).ok
    assert live_sandbox.http_connect("wrong", "registry.npmjs.org", 443).unauthorized


def test_capability_is_bound_to_worker_network_identity(proxy, two_workers) -> None:
    victim, attacker = two_workers
    capability = proxy.grant(victim.identity, "registry.npmjs.org", 443)
    assert proxy.connect(victim.identity, capability, "registry.npmjs.org", 443).ok
    assert proxy.connect(attacker.identity, capability, "registry.npmjs.org", 443).unauthorized


def test_revoke_closes_active_connection_before_marking_revoked(proxy, store) -> None:
    connection = proxy.connect(active_grant())
    proxy.revoke(active_grant().grant_id)
    assert connection.closed
    assert proxy.route_exists(active_grant().grant_id) is False
    assert store.network_grant(active_grant().grant_id).status == "revoked"
```

- [ ] **Step 5: Implement native proxy policy and container sidecar topology**

Implement a packaged Rust proxy with a versioned authenticated control socket
and separate HTTP CONNECT and SOCKS5 CONNECT listeners. Each per-run worker has
a separate internal network and proxy sidecar. Each connection must present a
random per-run capability bound to the runtime-proven worker network identity
and active grant; reject wrong-worker reuse, UDP, BIND,
raw IP destinations, unauthenticated clients, and unsupported methods. Resolve
DNS inside the proxy for every connection, pin public answers, guard CNAME and
rebinding to private/loopback/link-local/multicast/reserved/metadata space, and
re-authorize proxy-observed redirects. Persist an immutable attempt row with
host/port, resolved-address digest, decision/outcome/timestamps/byte counts only.

Native drivers deny direct sockets and expose only the proxy endpoint through
their sandbox/firewall policy. Container filtered mode creates one `--internal`
command network and a proxy sidecar attached to it and a separate egress
network. Revoke ordering is: stop accepts, close active connections, remove
route/firewall permit, then durable revoked state. Startup recovery repeats
cleanup idempotently. Tests cover teardown races, expired grants, DNS changes,
redirects, wrong capabilities, direct socket denial, and sidecar crash/recovery.

Add the proxy crate to the Cargo workspace/lockfile. Release builds package the
proxy in platform wheel data and copy the exact digest-matching supervisor and
proxy into `containers/command-sandbox/Containerfile`; the built image records
both protocol versions/digests in labels checked by readiness. Extend the clean-
wheel and clean-image smoke tests to remove source-tree artifacts, start from the
installed package/image only, prove both artifacts resolve, and fail closed for
missing or tampered bytes.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_network.py tests/test_web_fetch_policy.py -q --basetemp .tmp/pytest-command-network`

Run: `cargo test --manifest-path native/Cargo.toml -p raiker-egress-proxy`

Expected: all tests pass and existing web policy remains unchanged.

```powershell
git add -- native/Cargo.toml native/Cargo.lock native/raiker-egress-proxy raiker/execution/commands/network.py raiker/execution/commands/backends containers/command-sandbox/Containerfile pyproject.toml .github/workflows/release.yml raiker/execution/native_artifacts.py raiker/api/schemas.py tests/test_command_network.py tests/test_native_artifact_packaging.py
git commit -m "feat: govern sandbox network grants"
```

---

### Task 6: Command lifecycle service, receipts, and restart recovery

**Files:**
- Create: `raiker/execution/commands/service.py`
- Create: `raiker/execution/commands/receipts.py`
- Create: `raiker/execution/commands/evidence.py`
- Create: `raiker/execution/commands/recovery.py`
- Create: `raiker/execution/commands/composition.py`
- Modify: `raiker/runtime/executors/__init__.py`
- Modify: `raiker/api/app.py`
- Modify: `raiker/api/dependencies.py`
- Create: `tests/test_command_service.py`
- Create: `tests/test_command_recovery.py`
- Create: `tests/test_command_lifespan.py`
- Create: `tests/test_command_evidence.py`

**Interfaces:**
- Consumes: `CommandStore`, `CommandBackend`, `CommandNetworkBroker`, `CommandRequest`, `SupervisorClient`, vault/checkpoint services, FastAPI lifespan.
- Produces: one workspace-scoped `CommandService`; `start`, `poll`, `wait`, `log`, `write`, `stop`, `renew_lease`, `reset_environment`; atomic `canonical_receipt` finalization; checkpoint/change/diagnostic evidence; `CommandRecovery.reconcile`; lease reaper and bounded shutdown.

- [ ] **Step 1: Write failing lifecycle and foreground/background stop tests**

```python
def test_service_persists_before_start_and_finalizes_once(store: CommandStore) -> None:
    backend = RecordingBackend(final=CommandState.SUCCEEDED, exit_code=0)
    service = CommandService(store, {"container": backend})
    run = service.start(request(background=False))
    assert backend.observed_states_at_start == [CommandState.STARTING]
    assert service.wait("owner_a", run.run_id).state == CommandState.SUCCEEDED
    assert store.load("owner_a", run.run_id).receipt_digest is not None


def test_immediate_exit_and_receipt_commit_are_atomic(store: CommandStore) -> None:
    service = service_with_immediate_exit_backend(store)
    run = service.start(request())
    assert service.wait("owner_a", run.run_id).state == CommandState.SUCCEEDED
    assert store.receipt_count(run.run_id) == 1


def test_receipt_failure_never_publishes_success(store: CommandStore) -> None:
    store.fail_next_receipt_transaction()
    service = service_with_success_backend(store)
    run = service.start(request())
    assert service.wait("owner_a", run.run_id).state == CommandState.FINALIZING
    assert store.receipt_count(run.run_id) == 0
    service.retry_finalization(run.run_id)
    assert store.load("owner_a", run.run_id).state == CommandState.SUCCEEDED
    assert store.receipt_count(run.run_id) == 1


def test_turn_stop_kills_foreground_but_not_explicit_background_run(store: CommandStore) -> None:
    service = service_with_running_backend(store)
    foreground = service.start(request(run_id="fg", background=False))
    background = service.start(request(run_id="bg", background=True))
    service.stop_turn("owner_a", "turn_a", "owner requested stop")
    assert service.poll("owner_a", foreground.run_id).state == CommandState.CANCELLED
    assert service.poll("owner_a", background.run_id).state == CommandState.RUNNING
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_service.py -q --basetemp .tmp/pytest-command-service`

Expected: `CommandService` is absent.

- [ ] **Step 3: Implement lifecycle operations and lease enforcement**

```python
class CommandService:
    def start(self, request: CommandRequest) -> CommandRun:
        resolution = self.resolve(request)
        if resolution.backend is None:
            return self.store.contain_before_start(request, resolution.reason_code or "backend_unavailable")
        self.store.create(request)
        self.store.transition(request.owner_principal_id, request.run_id, CommandState.QUEUED, CommandState.STARTING)
        subscription = self._completion_subscription(request)
        handle = resolution.backend.start(request, subscription.supervisor)
        self._handles[request.run_id] = handle
        self.store.mark_running_unless_finalizing(
            request.owner_principal_id, request.run_id,
            self.vault.encrypt(handle.recovery_identity),
        )
        return self.store.load_required(request.owner_principal_id, request.run_id)
```

Install completion subscription before launch. A callback asks the service to
compare-and-swap `starting|running -> finalizing`; it never writes SQL directly.
One transaction inserts an immutable canonical receipt and changes finalizing
to the selected terminal state. Retry uses the same digest and cannot duplicate
the receipt. If intended receipt construction exhausts its retry budget, one
transaction writes a minimal immutable containment receipt describing the
evidence failure and transitions to `contained`. If storage cannot write that
receipt, the run remains non-terminal `finalizing` and success stays withheld.
Owner discard is a separately authorized transaction that first writes an
immutable `discarded` containment receipt. Add deterministic race
tests for immediate exit, natural exit versus timeout/stop, database failure,
and retry.

The service owns state transitions, owner/run handle lookup, background lease
expiry, and re-governed input/stop/reset. Every lifecycle action rechecks the
current owner session and original unrevoked grant; reset requires a fresh owner
decision. Command creation is not exposed as a direct API.

- [ ] **Step 4: Write failing canonical receipt and recovery tests**

```python
def test_receipt_digest_changes_if_evidence_changes() -> None:
    first = canonical_receipt(receipt_input(exit_code=0))
    second = canonical_receipt(receipt_input(exit_code=1))
    assert first.digest != second.digest
    assert first.payload["command"]["display"] == "npm test"
    serialized = json.dumps(first.payload)
    assert first.payload["environment"]["backend"] == "container"
    assert "RAW_SECRET_VALUE" not in serialized


def test_recovery_marks_unprovable_run_lost(store: CommandStore) -> None:
    store.create_running(request(), encrypted_backend_handle=vault.encrypt("opaque"))
    recovered = CommandRecovery(store, backends={"container": UnknownHandleBackend()}).reconcile()
    assert recovered[0].state == CommandState.LOST
    assert recovered[0].termination_reason == "recovery_identity_unproven"
```

- [ ] **Step 5: Implement canonical receipts and bounded recovery**

Before mutation, use the existing checkpoint service to record repository id and
a bounded workspace manifest. After exit, compare canonical workspace paths
without following symlinks/junctions and record only relative paths, state, and
bounded hashes. Parse already-redacted output through bounded pytest/compiler/
test-runner diagnostic parsers without interpreting terminal escapes. Receipt
payload contains safe display/template digest, request identity, effective
boundary, approval/grant ids, outcome, byte/redaction/truncation counts, these
evidence fields, and timestamps. Serialize with sorted keys and compact
separators before SHA-256. Evidence failure is explicit and cannot read outside
the selected workspace.

`build_command_composition` creates one service and injects that exact instance
into the default executor registry, ToolBroker, approval relay, routes, and
orchestrator. FastAPI lifespan starts reconciliation and the periodic lease
reaper; profile change invokes scoped cleanup; bounded shutdown stops foreground
and non-persistent supervisors. Recovery resumes only when authenticated
supervisor instance/request/PID-start identity, labels, and workspace bounds
match. Unknown outcomes become `lost` only in the same transaction that writes
their immutable recovery receipt; otherwise they remain `finalizing`.

Add an integration fixture that starts a real loopback Raiker process and live
container background command, kills/restarts Raiker, then proves identical run
id, ordered log catch-up, PTY input when enabled, lease expiry, and kill. Corrupt
identity and prove `lost`. Also assert both approval and standing-grant paths
resolve the same injected service object and durable lifecycle.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_service.py tests/test_command_recovery.py tests/test_command_lifespan.py tests/test_command_evidence.py -q --basetemp .tmp/pytest-command-service`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/service.py raiker/execution/commands/receipts.py raiker/execution/commands/evidence.py raiker/execution/commands/recovery.py raiker/execution/commands/composition.py raiker/runtime/executors/__init__.py raiker/api/app.py raiker/api/dependencies.py tests/test_command_service.py tests/test_command_recovery.py tests/test_command_lifespan.py tests/test_command_evidence.py
git commit -m "feat: manage command lifecycle and recovery"
```

---

### Task 7: SSH and Daytona lifecycle parity

**Files:**
- Create: `raiker/execution/commands/backends/remote.py`
- Modify: `raiker/runtime/executors/tier5_network.py`
- Modify: `tests/test_execution_environments.py`
- Create: `tests/test_remote_command_backends.py`

**Interfaces:**
- Consumes: `CommandBackend`, `CommandService`, current SSH/Daytona profile and cost helpers.
- Produces: `SshCommandBackend`, `DaytonaCommandBackend` with authenticated framed supervisor transport, proven feature flags, and shared start/poll/wait/log/kill/reattach behavior.

- [ ] **Step 1: Write failing remote lifecycle and feature-honesty tests**

```python
def test_ssh_backend_binds_host_key_cwd_and_exact_argv(tmp_path: Path) -> None:
    backend, transport = ssh_backend(tmp_path, features={"pty": False})
    backend.start(request(shell=False, executable_template="", argv_template=("pytest", "-q")))
    frame = transport.decoded_start_frame()
    assert transport.strict_host_key_checking is True
    assert frame.cwd == "." and frame.argv == ("pytest", "-q")
    assert transport.used_ad_hoc_shell_string is False
    assert backend.features.pty is False


def test_remote_without_verified_supervisor_is_foreground_only(tmp_path: Path) -> None:
    backend = ssh_backend_without_supervisor(tmp_path)
    assert backend.features.background is False
    assert backend.features.pty is False
    assert backend.features.recoverable is False
    assert backend.start(background_request()).reason_code == "remote_supervisor_required"


def test_daytona_cost_reservation_survives_background_run(store: CommandStore) -> None:
    backend = daytona_backend(store, actual_cost=1.25)
    handle = backend.start(request(background=True), RecordingSink())
    assert handle.poll() == CommandState.RUNNING
    handle.wait()
    assert store.cloud_cost("owner_a", "daytona_a").actual_cost == Decimal("1.25")
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_remote_command_backends.py -q --basetemp .tmp/pytest-remote-command`

Expected: remote executors do not implement `CommandBackend`.

- [ ] **Step 3: Adapt SSH and Daytona without duplicating lifecycle state**

```python
class SshCommandBackend:
    def start(self, request: CommandRequest) -> CommandHandle:
        profile = self._profiles.require_ssh(request.owner_principal_id, request.environment_profile_id)
        supervisor = self._verified_supervisor_transport(profile)
        return supervisor.start(self._framed_request(profile, request))
```

Daytona retains pre/post provider spend snapshots and reservations; SSH retains
strict host-key and protected credential-reference binding. Install or verify
the approved supervisor version/digest before advertising capabilities. Exact
cwd/argv/template travels only in the framed protocol, never an interpolated
remote shell string. API flags for PTY/input/background/kill/lease/recovery and
filtered network remain false unless a live authenticated supervisor/policy
probe proves them. Add real restart/reattach/kill tests where configured; all
other remote fixtures must prove honest feature refusal.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_remote_command_backends.py tests/test_execution_environments.py -q --basetemp .tmp/pytest-remote-command`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/backends/remote.py raiker/runtime/executors/tier5_network.py tests/test_remote_command_backends.py tests/test_execution_environments.py
git commit -m "feat: unify remote command backends"
```

---

### Task 8: Broker, approval relay, tool schema, and orchestrator integration

**Files:**
- Modify: `raiker/runtime/executors/tier2_shell.py`
- Modify: `raiker/runtime/executors/tier1_approval.py`
- Modify: `raiker/tools/broker.py`
- Modify: `raiker/models/tool_call_validation.py`
- Modify: `raiker/contracts/models.py`
- Modify: `raiker/policy/config.py`
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/runtime/orchestrator.py`
- Create: `raiker/execution/commands/credential_broker.py`
- Modify: `tests/test_approval_relay_general.py`
- Modify: `tests/test_tool_broker.py`
- Create: `tests/test_command_tool_integration.py`

**Interfaces:**
- Consumes: `CommandService` lifecycle operations.
- Produces: approval-gated `shell`, standing-grant `run_command`, and model-visible `process` actions through one service; metadata-only stream events.

- [ ] **Step 1: Write failing shared-path and grant-scope tests**

```python
def test_approved_shell_and_granted_run_command_use_same_service(broker, relay, command_service) -> None:
    relay.resolve(approved_shell_action("npm test"))
    broker.execute(granted_run_command_action("npm test"), session_id="sess_a", turn_id="turn_a")
    assert [call.request.safe_display for call in command_service.start_calls] == ["npm test", "npm test"]


def test_selected_profile_is_not_a_model_overridable_field(broker) -> None:
    result, _ = broker.execute(run_command_action(
        "npm test", profile_id="local_native", network_domains=["example.com"], interactive=True
    ), session_id="sess_a", turn_id="turn_a")
    assert result.error == {"type": "unknown_tool_argument", "argument": "profile_id"}


@pytest.mark.parametrize("surface", ["database", "approval", "event", "tool_result", "api"])
def test_secret_bearing_command_is_rejected_before_every_surface(surface, harness) -> None:
    secret = harness.register_secret("token-value-123456789")
    result = harness.propose_command(f"tool --token {secret}")
    assert result.reason_code == "command_secret_literal_denied"
    assert secret not in harness.serialized(surface)
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_tool_integration.py tests/test_approval_relay_general.py tests/test_tool_broker.py -q --basetemp .tmp/pytest-command-tools`

Expected: current paths invoke different runners and `process` is unknown.

- [ ] **Step 3: Define exact tool contracts**

```python
ToolSpec(
    name="run_command",
    description="Run a governed command in the owner-selected environment.",
    required_args=("command",),
    optional_args=("background", "interactive", "timeout_seconds", "notify_on_complete", "network_domains", "credential_bindings"),
)
ToolSpec(
    name="process",
    description="List, poll, wait, read logs, write input, or stop an owned command run.",
    required_args=("operation",),
    optional_args=("run_id", "after", "input", "timeout_seconds"),
)
```

`profile_id` is deliberately absent: resolution reads the owner-selected
environment after approval and refuses if it changed. Add an optional typed
`credential_bindings` collection containing only vault reference, purpose, and
delivery target. `CommandCredentialBroker` scans literal command/argv with both
registered values and bounded secret patterns before any durable proposal;
secret-bearing literals are rejected. At supervisor launch it resolves a
purpose-bound grant and delivers memory-only material via stdin, inherited
descriptor/handle, protected ephemeral file, or an explicitly approved process
environment. It creates the safe display and template digest. Tests search raw
database pages, approval/event JSON, API/tool results, receipt, and rendered UI
fixtures for registered and pattern secrets.

Validation accepts only operations `list|poll|wait|log|write|kill`, boolean background/interactive flags, 1–1800 second timeout, at most 20 public-domain patterns, and bounded input/output offsets.

- [ ] **Step 4: Route both tools through `CommandService` and emit metadata-only lifecycle events**

```python
def _emit_command_event(self, envelope: PromptEnvelope, event_type: str, run: CommandRun) -> None:
    self._event(envelope, event_type, {
        "run_id": run.run_id, "state": run.state.value,
        "profile_id": run.profile_id, "backend": run.backend,
        "interactive": run.interactive, "background": run.background,
    })
```

Do not include executable templates, raw command strings, credential values, or
output in lifecycle events. Use safe display only where a command label is
necessary. The model tool result receives bounded redacted output for foreground
completion, or run id/state/receipt link for background execution. Input, stop,
lease, and reset recheck current session/original grant; revoked authority fails
closed and reset always obtains a new owner decision.

- [ ] **Step 5: Verify approval re-governance, queued calls, stop, and provider-valid tool replies**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_tool_integration.py tests/test_approval_relay_general.py tests/test_batched_approval_queue.py tests/test_runtime_interrupts.py -q --basetemp .tmp/pytest-command-tools`

Expected: all tests pass.

- [ ] **Step 6: Commit runtime integration**

```powershell
git add -- raiker/execution/commands/credential_broker.py raiker/runtime/executors/tier2_shell.py raiker/runtime/executors/tier1_approval.py raiker/tools/broker.py raiker/models/tool_call_validation.py raiker/contracts/models.py raiker/policy/config.py raiker/runtime/authority/router.py raiker/runtime/orchestrator.py tests/test_approval_relay_general.py tests/test_tool_broker.py tests/test_command_tool_integration.py
git commit -m "feat: unify governed command tools"
```

---

### Task 9: Strict command APIs and owner-scoped catch-up output

**Files:**
- Create: `raiker/api/routes_commands.py`
- Modify: `raiker/api/app.py`
- Modify: `raiker/api/schemas.py`
- Create: `tests/test_api_commands.py`

**Interfaces:**
- Consumes: `CommandService`, current authenticated owner session dependency.
- Produces: command list/detail/output/input/stop/lease, credential-delta merge/discard, and environment-reset endpoints.

- [ ] **Step 1: Write failing auth, ownership, pagination, and mutation tests**

```python
def test_output_catchup_is_owner_scoped_and_sequence_bounded(client: TestClient, seeded_commands) -> None:
    owner = auth_headers(client, "owner_a")
    other = auth_headers(client, "owner_b")
    assert client.get("/api/command-runs/cmd_a/output?after=1", headers=owner).json()[0]["sequence"] == 2
    assert client.get("/api/command-runs/cmd_a/output", headers=other).status_code == 404


def test_input_rejects_unknown_fields_and_noninteractive_run(client: TestClient, owner_headers) -> None:
    response = client.post("/api/command-runs/cmd_a/input", headers=owner_headers, json={"input": "x", "profile_id": "evil"})
    assert response.status_code == 422
    response = client.post("/api/command-runs/cmd_a/input", headers=owner_headers, json={"input": "x"})
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "command_not_interactive"


@pytest.mark.parametrize("operation", ["input", "stop", "lease"])
def test_lifecycle_control_rejects_revoked_session_or_grant(client, seeded_run, operation) -> None:
    headers = revoked_auth_headers(client, seeded_run.owner)
    response = post_lifecycle(client, seeded_run.run_id, operation, headers)
    assert response.status_code in {401, 403, 409}


def test_reset_requires_fresh_owner_decision(client, owner_headers) -> None:
    response = client.post("/api/execution-environments/container_a/reset", headers=owner_headers, json={"mode": "recreate"})
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "owner_decision_required"


def test_quarantined_delta_cannot_merge_and_discard_requires_owner_decision(client, owner_headers) -> None:
    assert client.post("/api/command-runs/cmd_a/delta/merge", headers=owner_headers, json={"paths": ["safe.txt"]}).status_code == 409
    response = client.post("/api/command-runs/cmd_a/delta/discard", headers=owner_headers, json={})
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "owner_decision_required"
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api_commands.py -q --basetemp .tmp/pytest-api-commands`

Expected: all routes return 404.

- [ ] **Step 3: Implement strict schemas and router**

```python
class CommandInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field(min_length=1, max_length=16_384)


@router.get("/api/command-runs/{run_id}/output")
def command_output(run_id: str, after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500), auth_data=Depends(require_session), request: Request = None):
    return command_service(request).log(auth_data[0].principal_id, run_id, after=after, limit=limit)
```

There is no command-create endpoint. Return 404 for cross-owner resources, 409
with stable reason codes for invalid lifecycle operations, and only redacted
chunks/safe receipts. Recheck current session and original grant for input,
stop, and lease; require a fresh owner decision for reset. Apply per-owner/run
rate limits to list/output polling, input bytes, stop, lease renewal, and reset,
with bounded pagination and retry metadata.
Delta merge accepts only paths from a clean reviewed manifest, rechecks owner
decision and canonical containment, and invokes the second scan immediately
before governed apply. Quarantined deltas cannot merge. Discard requires an
owner decision and records the delta digest without secret content.

- [ ] **Step 4: Run API and redaction tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api_commands.py tests/test_api_redaction.py -q --basetemp .tmp/pytest-api-commands`

Expected: all tests pass.

```powershell
git add -- raiker/api/routes_commands.py raiker/api/app.py raiker/api/schemas.py tests/test_api_commands.py
git commit -m "feat: expose governed command controls"
```

---

### Task 10: Build terminal pane, command activity, approval preview, and Runtime controls

**Files:**
- Create: `apps/web/src/lib/components/CommandOutputPane.svelte`
- Create: `apps/web/src/lib/components/CommandActivityRow.svelte`
- Create: `apps/web/src/lib/components/CredentialDeltaReview.svelte`
- Create: `apps/web/src/lib/commandPresentation.ts`
- Create: `apps/web/src/lib/components/CommandOutputPane.test.ts`
- Create: `apps/web/src/lib/components/CommandActivityRow.test.ts`
- Create: `apps/web/src/lib/components/CredentialDeltaReview.test.ts`
- Create: `apps/web/src/lib/commandPresentation.test.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/BuildView.svelte`
- Modify: `apps/web/src/lib/views/BuildView.test.ts`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.test.ts`
- Modify: `apps/web/src/lib/views/settings/Runtime.svelte`
- Modify: `apps/web/src/lib/views/settings/Runtime.test.ts`

**Interfaces:**
- Consumes: command APIs, command lifecycle stream metadata, execution-environment feature/readiness fields.
- Produces: resizable durable output pane, first-class activity rows, input/stop/lease/reset/receipt controls, failure navigation, and honest backend/approval copy.

- [ ] **Step 1: Write failing presentation and component tests**

```typescript
it("restores output after reload and appends only later chunks", async () => {
  api.commandRuns.mockResolvedValue([runningCommand({ run_id: "cmd_1" })]);
  api.commandOutput.mockResolvedValue([
    chunk({ sequence: 1, stream: "stdout", text: "ready\n" }),
  ]);
  render(CommandOutputPane, { sessionId: "sess_a" });
  expect(await screen.findByText("ready")).toBeInTheDocument();
  window.dispatchEvent(new CustomEvent("raiker:command-output", { detail: { run_id: "cmd_1" } }));
  await waitFor(() => expect(api.commandOutput).toHaveBeenLastCalledWith("cmd_1", 1));
});


it("shows the effective boundary and only valid controls", async () => {
  render(CommandOutputPane, { sessionId: "sess_a", initialRuns: [runningCommand({ interactive: false, backend: "container" })] });
  expect(screen.getByText(/container.*no network/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /stop process/i })).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /send input/i })).not.toBeInTheDocument();
});


it("quarantines a secret-bearing delta and offers discard only", async () => {
  render(CredentialDeltaReview, { delta: quarantinedDelta({ matched_paths: 2 }) });
  expect(screen.getByText(/2 files quarantined/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /merge/i })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /discard credentialed changes/i })).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("credential-value-123456789");
});


it("renders terminal content as text and never exposes secret-bearing fields", async () => {
  const secret = "token-value-123456789";
  render(CommandOutputPane, { initialRuns: [runningCommand({ command_display: "tool --token [REDACTED]" })] });
  await emitOutput({ text: `<img src=x onerror=alert(1)> ${secret}`.replace(secret, "[REDACTED]") });
  expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
  expect(document.body.textContent).not.toContain(secret);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `npm --prefix apps/web run test -- CommandOutputPane.test.ts CommandActivityRow.test.ts commandPresentation.test.ts`

Expected: component/module imports fail.

- [ ] **Step 3: Add exact API types and client methods**

```typescript
export type CommandState = "queued" | "starting" | "running" | "finalizing" | "succeeded" | "failed" | "timed_out" | "cancelled" | "contained" | "lost";
export interface CommandRunView {
  run_id: string; session_id: string; turn_id: string; state: CommandState;
  backend: "local_strict" | "native_sandbox" | "container" | "ssh" | "daytona";
  profile_id: string; safe_display: string; template_digest: string; cwd: string;
  background: boolean; interactive: boolean; network: string[];
  started_at: string | null; completed_at: string | null; lease_expires_at: string | null;
  exit_code: number | null; stdout_bytes: number; stderr_bytes: number;
  truncated: boolean; redaction_count: number; receipt_digest: string | null;
}
export interface CommandOutputChunk { run_id: string; sequence: number; stream: "stdout" | "stderr"; text: string; byte_count: number; emitted_at: string; }
```

- [ ] **Step 4: Implement the pane and transcript row**

Use semantic buttons, labelled output regions, `aria-live="polite"` for state
changes but not every output byte, keyboard-reachable resize controls,
per-stream filters, output catch-up by sequence, and responsive drawer behavior
below 768 px. Render all output/safe display with Svelte text interpolation,
never `{@html}` or an HTML sink. `failureCoordinate(text)` recognises bounded
`path:line[:column]` forms and calls the existing source inspector only after
canonical workspace containment.
Credentialed completion shows the TCB warning and delta state. A clean delta
offers per-path selection, second-scan status, **Merge selected**, and **Discard**;
a secret match shows only counts/reason code, no matched path bytes or value,
and offers discard only. While resolution is pending, Build explains why new
commands are blocked.

- [ ] **Step 5: Write and satisfy Build, Approval, and Runtime integration tests**

```typescript
it("opens a command activity row in the shared output pane", async () => {
  render(BuildView);
  await emitLifecycle("command_started", { run_id: "cmd_1", state: "running", backend: "container" });
  await user.click(await screen.findByRole("button", { name: /npm test.*running/i }));
  expect(screen.getByRole("region", { name: /command output/i })).toHaveAttribute("data-run-id", "cmd_1");
});


it("approval names command boundary and requested domains", async () => {
  render(ApprovalsView);
  expect(await screen.findByText(/container.*persistent.*no host fallback/i)).toBeInTheDocument();
  expect(screen.getByText("registry.npmjs.org:443")).toBeInTheDocument();
});


it("warns that a general command receiving a credential is in its TCB", async () => {
  render(ApprovalsView, { approval: credentialedCommandApproval() });
  expect(screen.getByText(/can transform, persist, or exfiltrate this credential/i)).toBeInTheDocument();
});
```

Runtime cards show real probe time, features, persistence, protected paths, filtered network, and **Host access — reduced isolation**. Unsupported features are disabled with exact remediation.

- [ ] **Step 6: Run web tests, Svelte checks, and commit**

Run: `npm --prefix apps/web run test -- CommandOutputPane.test.ts CommandActivityRow.test.ts CredentialDeltaReview.test.ts commandPresentation.test.ts BuildView.test.ts ApprovalsView.test.ts Runtime.test.ts`

Run: `npm --prefix apps/web run check`

Expected: tests and checks pass.

```powershell
git add -- apps/web/src/lib/components/CommandOutputPane.svelte apps/web/src/lib/components/CommandActivityRow.svelte apps/web/src/lib/components/CredentialDeltaReview.svelte apps/web/src/lib/commandPresentation.ts apps/web/src/lib/components/CommandOutputPane.test.ts apps/web/src/lib/components/CommandActivityRow.test.ts apps/web/src/lib/components/CredentialDeltaReview.test.ts apps/web/src/lib/commandPresentation.test.ts apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/BuildView.svelte apps/web/src/lib/views/BuildView.test.ts apps/web/src/lib/views/ApprovalsView.svelte apps/web/src/lib/views/ApprovalsView.test.ts apps/web/src/lib/views/settings/Runtime.svelte apps/web/src/lib/views/settings/Runtime.test.ts
git commit -m "feat: add Build command workbench"
```

---

### Task 11: Documentation, compatibility mapping, and live provider evidence

**Files:**
- Modify: `docs/plans/GAP_BUILD_CHAT.md`
- Modify: `docs/plans/TO_BE_ADDED.md`
- Modify if unresolved issue exists: `docs/plans/TO_BE_FIXED.md`
- Modify: `README.md`
- Modify: `docs/REFERENCE_PLATFORM_COMPATIBILITY.md`
- Modify: `docs/SECURITY_AND_POLICY.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/WEB_APP_LIVE_TEST.md`
- Create screenshots under: `docs/plans/screenshots/working/`

**Interfaces:**
- Consumes: completed shell behavior and Playwright evidence.
- Produces: honest closure status for B1/B5/B15/B20/ADD-01 and a dedicated market comparison control set.

- [ ] **Step 1: Add the compatibility control set before changing completion claims**

Add rows for: technical boundary vs approval policy; authoritative environment selection; no-fallback behavior; workspace/protected-path isolation; descendant network enforcement; exact once/session grants; foreground output; background start/poll/wait/log/input/kill; PTY; persistent sandbox/reset; native/container/SSH/Daytona backends; filtered domain escalation; secret-free environment; durable output catch-up; execution receipts; failure navigation; process-tree stop; restart recovery; and `lost` outcome honesty.

Each row uses `✅ at parity or beyond`, `🟡 partial`, or `❌ absent` only from automated plus live evidence and cites the official sources listed in the design specification.

- [ ] **Step 2: Start a fresh loopback service without putting keys in commands**

Stop any Raiker process first. Use the application's credential UI for Anthropic, OpenRouter, OpenAI, and Ollama. Runtime-only non-secret sandbox configuration may be set in the launch environment. Start `raiker-web` on loopback and keep the process id for cleanup.

- [ ] **Step 3: Use the Playwright skill for the live matrix**

Verify each provider separately with a Build prompt that causes a sandboxed
foreground command and receipt. Then verify one background dev server, output
polling, stop, browser reload recovery, PTY input, timeout, truncation,
failed-test navigation, filtered-domain approval/retry, no-fallback refusal,
reset, and recreate. While the background process is active, terminate and
restart the Raiker service (not the container), reconnect through the UI, and
prove identical run id, ordered catch-up, input/stop control, and lease expiry.
Repeat with invalidated supervisor identity and prove the honest `lost` path.
Use an approved domain to prove the proxy succeeds while an unproxied direct
socket from the same sandbox fails, then revoke the grant and prove the active
route closes.

Capture reviewed screenshots at 375, 768, 1024, and 1440 px after secrets are no longer visible. Inspect every screenshot for correct backend/status, accessible controls, clipping, and private data.

- [ ] **Step 4: Fix every discovered product issue through RED/GREEN or record it**

For an in-scope defect, add a failing automated test, run it to prove RED, implement the minimum correction, rerun to GREEN, and repeat the live step. If an external dependency prevents an in-scope fix after safe alternatives are exhausted, add a `TO_BE_FIXED.md` entry using Observed, Reproduce, Root cause, Required fix, and Required user-interface outcome.

- [ ] **Step 5: Update closure and Known Limits wording**

B1/B5/B15/B20 and ADD-01 name exact tests, effective backends, screenshots, and retained limitations. README Known Limits removes the stale split between approval shell and command-grant containers. `WEB_APP_LIVE_TEST.md` records provider/model names and outcomes but no key, token, secret path, or unredacted command output.

- [ ] **Step 6: Commit documentation and evidence**

```powershell
git add -- docs/plans/GAP_BUILD_CHAT.md docs/plans/TO_BE_ADDED.md docs/plans/TO_BE_FIXED.md README.md docs/REFERENCE_PLATFORM_COMPATIBILITY.md docs/SECURITY_AND_POLICY.md docs/IMPLEMENTATION_STATUS.md docs/WEB_APP_LIVE_TEST.md docs/plans/screenshots/working
git commit -m "docs: verify governed shell parity"
```

---

### Task 12: Full verification, final review, push, and green workflows

**Files:**
- Verify: every changed source, test, documentation, screenshot, and workflow-relevant file.

**Interfaces:**
- Consumes: Tasks 1–11.
- Produces: fresh verification evidence, independent code review, pushed `origin/main`, and green GitHub Actions for the final SHA.

- [ ] **Step 1: Run the complete Python quality gate with workspace temp paths**

Run: `.venv\Scripts\python.exe -m ruff check .`

Run: `.venv\Scripts\python.exe -m mypy raiker apps tests`

Run: `.venv\Scripts\python.exe -m pytest -q --basetemp .tmp/pytest-full`

Expected: all commands exit zero.

- [ ] **Step 2: Run the complete web quality gate**

Run: `npm run lint`

Run: `npm run check`

Run: `npm run test`

Run: `npm run build`

Expected: all commands exit zero.

- [ ] **Step 3: Run native security-boundary and package gates**

Run: `cargo fmt --manifest-path native/Cargo.toml --check`

Run: `cargo clippy --manifest-path native/Cargo.toml --workspace --all-targets -- -D warnings`

Run: `cargo test --manifest-path native/Cargo.toml --workspace`

Run the Windows installer/firewall rollback integration in the Windows workflow
and build the pinned command image twice, verifying supervisor/proxy protocol
versions and artifact digests. Expected: all gates exit zero and the runtime
refuses a tampered helper or image.

Build the wheel and native artifacts from a clean checkout, install the wheel in
a fresh environment with the source tree absent from import/PATH, build the
command image only from release artifacts, and run readiness for supervisor,
runner, Windows service where applicable, and proxy. This clean-install smoke is
a required job in `native-security-boundaries.yml`.

- [ ] **Step 4: Repeat and inspect the critical live scenarios**

Repeat four-provider foreground execution, background/PTY, network escalation,
stop/timeout/truncation, failure navigation, browser reload, real Raiker service
restart and same-run reattachment, invalid-identity `lost`, direct-socket denial,
approved-proxy success/revocation, no-fallback refusal, and reset/recreate.
Review final screenshots rather than relying on DOM assertions alone.

- [ ] **Step 5: Obtain an independent whole-change review**

Package `git log --oneline`, `git diff --stat`, and `git diff -U10` from the pre-implementation base to `HEAD`. Give the reviewer the specification, this plan, test evidence, live evidence, and deferred issues. Resolve every Critical/Important finding through a tested fix and scoped re-review before proceeding.

- [ ] **Step 6: Inspect scope and commit intentional final changes**

Run: `git diff --check`

Run: `git status --short`

Run: `git diff --stat origin/main...HEAD`

Do not add the user's untracked `debug.log`. Commit only intentional remaining changes with a specific message.

- [ ] **Step 7: Push main and identify the pushed SHA**

Run: `git push origin main`

Run: `git rev-parse HEAD`

Expected: `origin/main` advances to the printed SHA.

- [ ] **Step 8: Monitor every GitHub Actions workflow for the pushed SHA**

Run: `gh run list --commit <FINAL_SHA> --json databaseId,name,status,conclusion,url,workflowName`

For each incomplete run, run `gh run watch <RUN_ID> --exit-status`. For a failure, inspect `gh run view <RUN_ID> --log-failed`, reproduce locally, add a failing regression test, fix it, rerun the affected full gate, commit, push, and monitor the new SHA. Repeat until every workflow concludes `success`.

- [ ] **Step 9: Produce the evidence-backed final summary**

Report the five closed items, effective backend/control set, automated test results, provider/model live results, screenshot paths, commits, final pushed SHA, workflow URLs/conclusions, and every unresolved issue added to `TO_BE_FIXED.md`.
