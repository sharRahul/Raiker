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
- `raiker/execution/commands/runner.py`: bounded concurrent stdout/stderr capture, redaction, timeout, input, and process-tree termination.
- `raiker/execution/commands/backends.py`: `CommandBackend` protocol plus local, native, container, SSH, and Daytona adapters.
- `raiker/execution/commands/network.py`: domain grants and isolated proxy topology/policy.
- `raiker/execution/commands/receipts.py`: canonical receipt creation and digest.
- `raiker/execution/commands/service.py`: lifecycle operations and environment resolution.
- `raiker/execution/commands/recovery.py`: startup reconciliation and bounded cleanup.
- `raiker/api/routes_commands.py`: owner-facing command history, output, input, stop, lease, and reset APIs.

### New web components

- `apps/web/src/lib/components/CommandOutputPane.svelte`: resizable pane, run selection, output, status, input, stop, lease, reset, and receipt controls.
- `apps/web/src/lib/components/CommandActivityRow.svelte`: first-class transcript activity linked to the pane.
- `apps/web/src/lib/commandPresentation.ts`: status, reason, stream, failure-coordinate, and boundary presentation helpers.

### Existing files modified

- `raiker/storage/migrations.py`, `raiker/storage/sqlite.py`: command rows, chunks, grants, receipts, owner-scoped queries, and compare-and-swap transitions.
- `raiker/execution/profiles.py`, `raiker/control/dashboard.py`: authoritative command profile and proven feature/readiness projection.
- `raiker/runtime/executors/tier2_shell.py`, `tier5_network.py`, `containers.py`: adapters into the shared command service.
- `raiker/runtime/executors/tier1_approval.py`, `raiker/tools/broker.py`, `raiker/runtime/orchestrator.py`: shared execution path and metadata-only command lifecycle stream.
- `raiker/models/tool_call_validation.py`, `raiker/contracts/models.py`, `raiker/policy/config.py`, `raiker/runtime/authority/router.py`: typed `run_command`/`process` tools and their unchanged governance.
- `raiker/api/app.py`, `raiker/api/schemas.py`: router registration and strict request bodies.
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
- Produces: `CommandRequest`, `CommandState`, `CommandChunk`, `CommandFeatures`, `CommandReceipt`, `CommandResolution`, `CommandStore.create`, `transition`, `append_chunk`, `list_runs`, `read_output`, `put_receipt`, and `list_recoverable`.
- Consumes: `SQLiteStore.connect`, `new_id`, `utc_now`, and the existing migration registration path.

- [ ] **Step 1: Write failing contract and state-machine tests**

```python
def request(**overrides: object) -> CommandRequest:
    values = {
        "run_id": "cmd_1", "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a", "session_id": "sess_a",
        "turn_id": "turn_a", "action_id": "act_a", "repository_id": None,
        "workspace_root": Path("C:/workspace"), "cwd": ".",
        "command": "npm test", "argv": (), "shell": True,
        "interactive": False, "background": False, "timeout_seconds": 30.0,
        "max_output_bytes": 100_000, "environment_profile_id": "container_default",
        "network_policy_id": None,
    }
    values.update(overrides)
    return CommandRequest(**values)


def test_request_requires_exactly_one_command_representation() -> None:
    with pytest.raises(ValueError, match="command_representation_invalid"):
        request(command="npm test", argv=("npm", "test"))
    with pytest.raises(ValueError, match="command_representation_invalid"):
        request(command="", argv=())


def test_terminal_states_cannot_transition_again() -> None:
    assert can_transition(CommandState.RUNNING, CommandState.SUCCEEDED)
    assert not can_transition(CommandState.SUCCEEDED, CommandState.FAILED)
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
        CommandState.STARTING: {CommandState.RUNNING, CommandState.FAILED, CommandState.CONTAINED},
        CommandState.RUNNING: TERMINAL_COMMAND_STATES,
    }.get(current, set())
```

`CommandRequest.__post_init__` enforces the mutually exclusive command/argv contract, positive timeout/output limits, relative contained cwd, and required identity fields.

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
  request_json TEXT NOT NULL,
  command_digest TEXT NOT NULL,
  isolation_json TEXT NOT NULL DEFAULT '{}',
  backend_handle TEXT,
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
  run_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  stream TEXT NOT NULL,
  text TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS command_receipts (
  run_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES command_runs(run_id) ON DELETE CASCADE
);
```

Persist request JSON without credentials or raw environment values. Enforce owner id in every read/update query and use `UPDATE ... WHERE state = ?` for state transitions.

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
- Create: `raiker/execution/commands/runner.py`
- Modify: `raiker/context/redaction.py`
- Create: `tests/test_command_runner.py`

**Interfaces:**
- Consumes: `CommandRequest`, `CommandChunk`, `CommandState`, `redact_text`.
- Produces: `StreamingCommandRunner.start(request, command, cwd, env, sink, pty) -> RunningProcess`, `RunningProcess.poll`, `wait`, `write`, and `terminate`.

- [ ] **Step 1: Write failing concurrent-stream, truncation, and split-token tests**

```python
def test_runner_redacts_token_split_across_reads_and_preserves_stream_order(tmp_path: Path) -> None:
    sink = RecordingSink()
    process = FakeProcess([
        ("stdout", b"prefix sk-proj-abc"),
        ("stdout", b"defghijklmnop suffix"),
        ("stderr", b"warning\n"),
    ], returncode=0)
    result = StreamingCommandRunner(process_factory=lambda *_a, **_k: process).start(
        request(workspace_root=tmp_path), ["fake"], tmp_path, {}, sink, pty=False
    ).wait()
    assert result == CommandState.SUCCEEDED
    joined = "".join(chunk.text for chunk in sink.chunks)
    assert "sk-proj" not in joined
    assert "[REDACTED]" in joined
    assert [chunk.sequence for chunk in sink.chunks] == list(range(1, len(sink.chunks) + 1))


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

- [ ] **Step 3: Implement bounded concurrent capture with carry-over redaction**

```python
class StreamingRedactor:
    def __init__(self, carry: int = 256) -> None:
        self._carry = carry
        self._pending = ""

    def feed(self, text: str, *, final: bool = False) -> tuple[str, int]:
        merged = self._pending + text
        cut = len(merged) if final else max(0, len(merged) - self._carry)
        visible, self._pending = merged[:cut], merged[cut:]
        redacted, changed = redact_text(visible)
        return redacted, int(changed)
```

Read stdout/stderr on separate worker threads, serialize chunks through one sequence allocator, stop persisting content after the cap while continuing to drain pipes, and never block the child because output was truncated.

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

- [ ] **Step 5: Implement platform process groups and PTY adapters**

```python
def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        _terminate_windows_job(process.pid)
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
```

Use a Windows Job Object for all child processes, a new POSIX session/process group on Unix, stdlib `pty` on Unix, and the packaged Windows runner's ConPTY channel on Windows. Refuse `interactive=true` with `pty_unavailable` when the selected adapter did not prove PTY readiness.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_runner.py -q --basetemp .tmp/pytest-command-runner`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/runner.py raiker/context/redaction.py tests/test_command_runner.py
git commit -m "feat: stream bounded command output"
```

---

### Task 3: Authoritative environment resolution, local strict, and native sandbox drivers

**Files:**
- Create: `raiker/execution/commands/backends.py`
- Modify: `raiker/execution/profiles.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/runtime/command_policy.py`
- Create: `tests/test_command_backends.py`
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
```

- [ ] **Step 5: Implement native probes and local strict adapter**

```python
class LocalStrictBackend:
    features = CommandFeatures(True, True, False, False, False, False, False)

    def start(self, request: CommandRequest, sink: CommandEventSink) -> CommandHandle:
        if request.shell:
            raise CommandBackendError("local_strict_shell_source_denied")
        validate_command(request.argv, workspace_root=request.workspace_root, allowlist=ALLOWED_SHELL_COMMANDS)
        return self.runner.start(request, list(request.argv), request.workspace_root / request.cwd, sandbox_environment(workspace_root=request.workspace_root), sink, pty=False)
```

Linux uses `bwrap`; macOS uses a generated Seatbelt profile; Windows uses the packaged restricted-token/Job Object/firewall helper. Each readiness probe runs a harmless child that proves workspace write, protected-path denial, and network denial. A failed proof returns `native_sandbox_probe_failed`.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_backends.py tests/test_execution_environments.py tests/test_command_sandbox.py -q --basetemp .tmp/pytest-command-backends`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/backends.py raiker/execution/profiles.py raiker/control/dashboard.py raiker/runtime/command_policy.py tests/test_command_backends.py tests/test_execution_environments.py
git commit -m "feat: enforce selected command environment"
```

---

### Task 4: Persistent Docker and Podman command sandbox

**Files:**
- Modify: `raiker/execution/commands/backends.py`
- Modify: `raiker/runtime/executors/containers.py`
- Modify: `raiker/execution/container_tools.py`
- Modify: `raiker/execution/tool_bridge.py`
- Create: `tests/test_persistent_command_container.py`
- Modify: `tests/test_container_tool_bridge.py`

**Interfaces:**
- Consumes: `CommandBackend`, `CommandRequest`, `StreamingCommandRunner`, validated container profile.
- Produces: `PersistentContainerBackend`, deterministic labelled container names, start/exec/reset/recreate/recover operations, and actual container-shell support.

- [ ] **Step 1: Write failing container creation and reuse tests**

```python
def test_container_is_hardened_and_reused_for_one_session(tmp_path: Path) -> None:
    runtime = RecordingContainerRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path)
    first = backend.start(request(session_id="sess_a"), RecordingSink())
    second = backend.start(request(run_id="cmd_2", session_id="sess_a"), RecordingSink())
    assert runtime.create_calls == 1
    create = runtime.commands[0]
    assert ["--network", "none"] == adjacent(create, "--network")
    assert "--read-only" in create and ["--cap-drop", "ALL"] == adjacent(create, "--cap-drop")
    assert all(".raiker" not in value or "readonly" in value for value in mount_values(create))
    assert first.backend_handle.container_id == second.backend_handle.container_id
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_persistent_command_container.py -q --basetemp .tmp/pytest-command-container`

Expected: `PersistentContainerBackend` is absent.

- [ ] **Step 3: Implement labelled persistent creation and full shell exec**

```python
def command_container_name(owner: str, session: str, profile: str) -> str:
    digest = sha256(f"{owner}\0{session}\0{profile}".encode()).hexdigest()[:24]
    return f"raiker-cmd-{digest}"


def shell_exec(profile: ExecutionProfile, request: CommandRequest) -> list[str]:
    assert profile.runtime in {"docker", "podman"}
    assert profile.shell_path and profile.shell_path.startswith("/")
    return [profile.runtime, "exec", "--interactive", profile.container_name,
            profile.shell_path, "-lc", request.command]
```

Create a read-only-root container with bounded tmpfs, `/sandbox-home`, `/workspace`, protected `.git`/`.raiker`, non-root uid, no capabilities, no-new-privileges, CPU/memory/PID/disk/lease labels, and no ambient environment. Run commands with `exec`; do not reapply the host basename/interpreter restriction inside the sandbox.

- [ ] **Step 4: Write failing reset, recovery, daemon-probe, and no-host-fallback tests**

```python
def test_recreate_removes_state_but_reset_processes_keeps_volume(tmp_path: Path) -> None:
    runtime = RecordingContainerRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path)
    backend.reset("owner_a", "sess_a", "container_a", recreate=False)
    assert runtime.kill_process_calls == 1 and runtime.remove_calls == 0
    backend.reset("owner_a", "sess_a", "container_a", recreate=True)
    assert runtime.remove_calls == 1 and runtime.remove_volume_calls == 1


def test_daemon_probe_requires_a_runnable_approved_image(tmp_path: Path) -> None:
    probe = probe_container_profile(profile(), runner=daemon_without_image)
    assert probe.available is False
    assert probe.reason_code == "container_image_unavailable:container_a"
```

- [ ] **Step 5: Implement probe, reset, recreate, and labelled recovery**

Only reuse or remove containers whose Raiker labels match the owner/session/profile hashes in the durable row. A name match without labels is `container_identity_mismatch` and is never touched.

- [ ] **Step 6: Complete the generic bridge's shell claim**

`CONTAINER_PROFILE_TOOLS`, `CONTAINER_SAFE_TOOLS`, and Runtime `supported_tools` must agree. The command sandbox uses `PersistentContainerBackend`; read-only ephemeral bridge tools keep the JSON protocol. Delete the misleading path that advertises `shell` to the read-only bridge without an executor.

- [ ] **Step 7: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_persistent_command_container.py tests/test_container_tool_bridge.py tests/test_execution_profiles.py tests/test_execution_environments.py -q --basetemp .tmp/pytest-command-container`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/backends.py raiker/runtime/executors/containers.py raiker/execution/container_tools.py raiker/execution/tool_bridge.py tests/test_persistent_command_container.py tests/test_container_tool_bridge.py
git commit -m "feat: add persistent command sandbox"
```

---

### Task 5: Filtered command-network grants and isolated proxy topology

**Files:**
- Create: `raiker/execution/commands/network.py`
- Modify: `raiker/execution/commands/backends.py`
- Modify: `raiker/api/schemas.py`
- Create: `tests/test_command_network.py`

**Interfaces:**
- Consumes: command grant rows, public-address checks from `raiker.runtime.web_policy`, backend network adapters.
- Produces: `CommandNetworkScope`, `CommandNetworkBroker.authorize`, `revoke`, `proxy_decision`, private container network/sidecar plan, and `command_network_approval_required`.

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
```

- [ ] **Step 5: Implement native proxy policy and container sidecar topology**

Native drivers deny direct sockets and expose only the proxy transport. Container filtered mode creates one `--internal` command network and a proxy sidecar attached to both that network and an egress network. Removing/revoking the grant tears down the sidecar route before the durable status becomes revoked.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_network.py tests/test_web_fetch_policy.py -q --basetemp .tmp/pytest-command-network`

Expected: all tests pass and existing web policy remains unchanged.

```powershell
git add -- raiker/execution/commands/network.py raiker/execution/commands/backends.py raiker/api/schemas.py tests/test_command_network.py
git commit -m "feat: govern sandbox network grants"
```

---

### Task 6: Command lifecycle service, receipts, and restart recovery

**Files:**
- Create: `raiker/execution/commands/service.py`
- Create: `raiker/execution/commands/receipts.py`
- Create: `raiker/execution/commands/recovery.py`
- Create: `tests/test_command_service.py`
- Create: `tests/test_command_recovery.py`

**Interfaces:**
- Consumes: `CommandStore`, `CommandBackend`, `CommandNetworkBroker`, `CommandRequest`, `StreamingCommandRunner`.
- Produces: `CommandService.start`, `poll`, `wait`, `log`, `write`, `stop`, `renew_lease`, `reset_environment`; `canonical_receipt`; `CommandRecovery.reconcile`.

- [ ] **Step 1: Write failing lifecycle and foreground/background stop tests**

```python
def test_service_persists_before_start_and_finalizes_once(store: CommandStore) -> None:
    backend = RecordingBackend(final=CommandState.SUCCEEDED, exit_code=0)
    service = CommandService(store, {"container": backend})
    run = service.start(request(background=False))
    assert backend.observed_states_at_start == [CommandState.STARTING]
    assert service.wait("owner_a", run.run_id).state == CommandState.SUCCEEDED
    assert store.load("owner_a", run.run_id).receipt_digest is not None


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
        handle = resolution.backend.start(request, self._sink(request))
        self._handles[request.run_id] = handle
        self.store.mark_running(request.owner_principal_id, request.run_id, handle.backend_handle)
        return self.store.load_required(request.owner_principal_id, request.run_id)
```

The service owns all state transitions, per-owner handle lookup, background lease expiry, and re-governed input/stop/reset calls. Backend callbacks never update SQL directly.

- [ ] **Step 4: Write failing canonical receipt and recovery tests**

```python
def test_receipt_digest_changes_if_evidence_changes() -> None:
    first = canonical_receipt(receipt_input(exit_code=0))
    second = canonical_receipt(receipt_input(exit_code=1))
    assert first.digest != second.digest
    assert first.payload["command"]["display"] == "npm test"
    assert "environment" not in json.dumps(first.payload).lower()


def test_recovery_marks_unprovable_run_lost(store: CommandStore) -> None:
    store.create_running(request(), backend_handle="opaque")
    recovered = CommandRecovery(store, backends={"container": UnknownHandleBackend()}).reconcile()
    assert recovered[0].state == CommandState.LOST
    assert recovered[0].termination_reason == "recovery_identity_unproven"
```

- [ ] **Step 5: Implement canonical receipts and bounded recovery**

Receipt payload contains request identity, effective boundary, approval/grant ids, terminal outcome, byte/redaction/truncation counts, changed-file summary, recognised test status, checkpoints, and timestamps. Serialize with sorted keys and compact separators before SHA-256.

Recovery resumes only when backend labels/handle identity match. Expired Raiker-owned resources are stopped only after path and label validation. Unknown outcomes become `lost`.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_service.py tests/test_command_recovery.py -q --basetemp .tmp/pytest-command-service`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/service.py raiker/execution/commands/receipts.py raiker/execution/commands/recovery.py tests/test_command_service.py tests/test_command_recovery.py
git commit -m "feat: manage command lifecycle and recovery"
```

---

### Task 7: SSH and Daytona lifecycle parity

**Files:**
- Modify: `raiker/execution/commands/backends.py`
- Modify: `raiker/runtime/executors/tier5_network.py`
- Modify: `tests/test_execution_environments.py`
- Create: `tests/test_remote_command_backends.py`

**Interfaces:**
- Consumes: `CommandBackend`, `CommandService`, current SSH/Daytona profile and cost helpers.
- Produces: `SshCommandBackend`, `DaytonaCommandBackend` with proven feature flags and shared start/poll/wait/log/kill behavior.

- [ ] **Step 1: Write failing remote lifecycle and feature-honesty tests**

```python
def test_ssh_backend_binds_host_key_cwd_and_exact_argv(tmp_path: Path) -> None:
    backend, calls = ssh_backend(tmp_path, features={"pty": False})
    backend.start(request(shell=False, command="", argv=("pytest", "-q")), RecordingSink())
    command = calls[0]
    assert "StrictHostKeyChecking=yes" in command
    assert command[-2:] == ["pytest", "-q"]
    assert backend.features.pty is False


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
    def start(self, request: CommandRequest, sink: CommandEventSink) -> CommandHandle:
        profile = self._profiles.require_ssh(request.owner_principal_id, request.environment_profile_id)
        command = self._bound_command(profile, request)
        return self.runner.start(request, command, request.workspace_root, self._credential_env(profile), sink, pty=request.interactive)
```

Daytona retains pre/post provider spend snapshots and reservations; SSH retains strict host-key and identity-file binding. API feature flags are false unless probe commands prove remote PTY/input/background/kill support.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/test_remote_command_backends.py tests/test_execution_environments.py -q --basetemp .tmp/pytest-remote-command`

Expected: all tests pass.

```powershell
git add -- raiker/execution/commands/backends.py raiker/runtime/executors/tier5_network.py tests/test_remote_command_backends.py tests/test_execution_environments.py
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
    assert [call.request.command for call in command_service.start_calls] == ["npm test", "npm test"]


def test_grant_cannot_widen_backend_network_or_interactivity(broker) -> None:
    result, _ = broker.execute(run_command_action(
        "npm test", profile_id="local_native", network_domains=["example.com"], interactive=True
    ), session_id="sess_a", turn_id="turn_a")
    assert result.error == {"type": "command_grant_scope_mismatch"}
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
    optional_args=("background", "interactive", "timeout_seconds", "notify_on_complete", "network_domains"),
)
ToolSpec(
    name="process",
    description="List, poll, wait, read logs, write input, or stop an owned command run.",
    required_args=("operation",),
    optional_args=("run_id", "after", "input", "timeout_seconds"),
)
```

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

Do not include command strings or output in lifecycle events. The model tool result receives bounded redacted output for foreground completion, or run id/state/receipt link for background execution.

- [ ] **Step 5: Verify approval re-governance, queued calls, stop, and provider-valid tool replies**

Run: `.venv\Scripts\python.exe -m pytest tests/test_command_tool_integration.py tests/test_approval_relay_general.py tests/test_batched_approval_queue.py tests/test_runtime_interrupts.py -q --basetemp .tmp/pytest-command-tools`

Expected: all tests pass.

- [ ] **Step 6: Commit runtime integration**

```powershell
git add -- raiker/runtime/executors/tier2_shell.py raiker/runtime/executors/tier1_approval.py raiker/tools/broker.py raiker/models/tool_call_validation.py raiker/contracts/models.py raiker/policy/config.py raiker/runtime/authority/router.py raiker/runtime/orchestrator.py tests/test_approval_relay_general.py tests/test_tool_broker.py tests/test_command_tool_integration.py
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
- Produces: command list/detail/output/input/stop/lease and environment-reset endpoints.

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

Return 404 for cross-owner resources, 409 with stable reason codes for invalid lifecycle operations, and only redacted chunks/receipts.

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
- Create: `apps/web/src/lib/commandPresentation.ts`
- Create: `apps/web/src/lib/components/CommandOutputPane.test.ts`
- Create: `apps/web/src/lib/components/CommandActivityRow.test.ts`
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
```

- [ ] **Step 2: Run and verify RED**

Run: `npm --prefix apps/web run test -- CommandOutputPane.test.ts CommandActivityRow.test.ts commandPresentation.test.ts`

Expected: component/module imports fail.

- [ ] **Step 3: Add exact API types and client methods**

```typescript
export type CommandState = "queued" | "starting" | "running" | "succeeded" | "failed" | "timed_out" | "cancelled" | "contained" | "lost";
export interface CommandRunView {
  run_id: string; session_id: string; turn_id: string; state: CommandState;
  backend: "local_strict" | "native_sandbox" | "container" | "ssh" | "daytona";
  profile_id: string; command_display: string; cwd: string;
  background: boolean; interactive: boolean; network: string[];
  started_at: string | null; completed_at: string | null; lease_expires_at: string | null;
  exit_code: number | null; stdout_bytes: number; stderr_bytes: number;
  truncated: boolean; redaction_count: number; receipt_digest: string | null;
}
export interface CommandOutputChunk { run_id: string; sequence: number; stream: "stdout" | "stderr"; text: string; byte_count: number; emitted_at: string; }
```

- [ ] **Step 4: Implement the pane and transcript row**

Use semantic buttons, labelled output regions, `aria-live="polite"` for state changes but not every output byte, keyboard-reachable resize controls, per-stream filters, output catch-up by sequence, and responsive drawer behavior below 768 px. `failureCoordinate(text)` recognises bounded `path:line[:column]` forms and calls the existing source inspector.

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
```

Runtime cards show real probe time, features, persistence, protected paths, filtered network, and **Host access — reduced isolation**. Unsupported features are disabled with exact remediation.

- [ ] **Step 6: Run web tests, Svelte checks, and commit**

Run: `npm --prefix apps/web run test -- CommandOutputPane.test.ts CommandActivityRow.test.ts commandPresentation.test.ts BuildView.test.ts ApprovalsView.test.ts Runtime.test.ts`

Run: `npm --prefix apps/web run check`

Expected: tests and checks pass.

```powershell
git add -- apps/web/src/lib/components/CommandOutputPane.svelte apps/web/src/lib/components/CommandActivityRow.svelte apps/web/src/lib/commandPresentation.ts apps/web/src/lib/components/CommandOutputPane.test.ts apps/web/src/lib/components/CommandActivityRow.test.ts apps/web/src/lib/commandPresentation.test.ts apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/BuildView.svelte apps/web/src/lib/views/BuildView.test.ts apps/web/src/lib/views/ApprovalsView.svelte apps/web/src/lib/views/ApprovalsView.test.ts apps/web/src/lib/views/settings/Runtime.svelte apps/web/src/lib/views/settings/Runtime.test.ts
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

Verify each provider separately with a Build prompt that causes a sandboxed foreground command and receipt. Then verify one background dev server, output polling, stop, reload recovery, PTY input, timeout, truncation, failed-test navigation, filtered-domain approval/retry, no-fallback refusal, reset, and recreate.

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

- [ ] **Step 3: Repeat and inspect the critical live scenarios**

Repeat four-provider foreground execution, background/PTY, network escalation, stop/timeout/truncation, failure navigation, reload recovery, no-fallback refusal, and reset/recreate. Review the final screenshots rather than relying on DOM assertions alone.

- [ ] **Step 4: Obtain an independent whole-change review**

Package `git log --oneline`, `git diff --stat`, and `git diff -U10` from the pre-implementation base to `HEAD`. Give the reviewer the specification, this plan, test evidence, live evidence, and deferred issues. Resolve every Critical/Important finding through a tested fix and scoped re-review before proceeding.

- [ ] **Step 5: Inspect scope and commit intentional final changes**

Run: `git diff --check`

Run: `git status --short`

Run: `git diff --stat origin/main...HEAD`

Do not add the user's untracked `debug.log`. Commit only intentional remaining changes with a specific message.

- [ ] **Step 6: Push main and identify the pushed SHA**

Run: `git push origin main`

Run: `git rev-parse HEAD`

Expected: `origin/main` advances to the printed SHA.

- [ ] **Step 7: Monitor every GitHub Actions workflow for the pushed SHA**

Run: `gh run list --commit <FINAL_SHA> --json databaseId,name,status,conclusion,url,workflowName`

For each incomplete run, run `gh run watch <RUN_ID> --exit-status`. For a failure, inspect `gh run view <RUN_ID> --log-failed`, reproduce locally, add a failing regression test, fix it, rerun the affected full gate, commit, push, and monitor the new SHA. Repeat until every workflow concludes `success`.

- [ ] **Step 8: Produce the evidence-backed final summary**

Report the five closed items, effective backend/control set, automated test results, provider/model live results, screenshot paths, commits, final pushed SHA, workflow URLs/conclusions, and every unresolved issue added to `TO_BE_FIXED.md`.
