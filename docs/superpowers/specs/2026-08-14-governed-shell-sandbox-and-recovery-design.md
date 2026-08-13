# Governed Shell, Sandbox, and Recovery Design

## Goal

Complete the five highest-priority shipped or partly shipped execution items as
one end-to-end Build capability:

- GAP-BUILD B1's remaining shell execution path;
- GAP-BUILD B5's command feedback channel;
- ADD-01's container execution boundary;
- GAP-BUILD B20's sandboxed execution environment; and
- GAP-BUILD B15's terminal and output surface.

The result must reach current coding-agent parity for command execution while
going beyond the reference products in governance, auditability, environment
choice, and recovery. A Build turn must be able to start a command, observe its
output while it runs, continue other work, provide input when an interactive
program requests it, stop it, recover its evidence after a reload or host
restart, and prove which technical boundary actually contained it.

## Reference Control Set

The design was reviewed on 2026-08-14 against the current shell and sandbox
controls documented for:

- [Codex sandboxing and approvals](https://openai.com/index/running-codex-safely/):
  an OS-enforced filesystem/network boundary, workspace write roots, explicit
  approval outside the boundary, configurable network policy, and command/test
  evidence;
- [Claude Code sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing):
  filesystem and network isolation, configurable paths and domains, and an
  approval when a command needs to cross the sandbox boundary;
- [Claude Cowork containment](https://www.anthropic.com/engineering/how-we-contain-claude):
  a local VM boundary with only owner-selected folders mounted and credentials
  kept outside the guest;
- [OpenClaw sandboxing](https://github.com/openclaw/openclaw/blob/main/docs/gateway/sandboxing.md):
  independently selected sandbox mode, scope, backend, workspace access, and
  elevated execution path;
- [OpenClaw exec approvals](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec-approvals.md):
  host selection, allowlist/ask policy, exact execution context, and executable
  binding; and
- [Hermes terminal tools](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/tools.md):
  local, Docker, SSH, Singularity, Modal, and Daytona backends; persistent
  container sessions; PTY input; and background process start, poll, wait,
  logs, write, and kill.

No single reference product owns the complete control set. Codex and Claude
Code establish the local sandbox and approval bar; Claude Cowork establishes
the strongest desktop containment bar; Hermes establishes the terminal
mechanics and backend-choice bar; OpenClaw establishes explicit separation of
sandbox placement from exec approval. Raiker must meet the combined bar rather
than selecting the easiest comparison.

## Scope Selection and Order

The items are handled in dependency order, with already shipped and partly
shipped work completed before new surface work:

1. Verify B1's approval relay and make the selected environment authoritative.
2. Complete B5 by putting both approval-gated `shell` and standing-grant
   `run_command` through the same command lifecycle and evidence contract.
3. Complete ADD-01's advertised shell support in the container bridge.
4. Complete B20 with real sandbox backends, persistence, network control, and
   fail-closed routing.
5. Complete B15 with first-class live output, background-process, PTY, stop,
   failure-navigation, receipt, and recovery controls in Build.

The first four are existing or partly completed claims. B15 begins only after
their common backend contract is proven.

## Audited Starting Point

The repository already has valuable pieces, but they do not form the capability
the product copy implies:

- `ApprovalExecutionRelay` executes an approved `shell` action once and returns
  bounded, redacted stdout/stderr evidence.
- `ShellExecutor` calls `run_command` on the host. It is constrained by a parsed
  argv policy and constructed environment, but it is not an OS sandbox or a
  container boundary.
- the standing-grant `run_command` tool invokes
  `run_isolated_workspace_command`, which uses a no-network Docker container;
  it is a separate path from approval-gated `shell`;
- `ExecutionProfile` includes `shell` in `CONTAINER_PROFILE_TOOLS`, while
  `CONTAINER_SAFE_TOOLS` excludes it and the Runtime API removes it from the
  owner-selectable tool list. A profile can therefore describe support that the
  bridge cannot deliver;
- `ToolBroker._execution_profile` resolves enabled per-tool assignments but
  does not consult `selected_execution_environment`. The Build environment
  badge can consequently name a selection that is not the command's actual
  executor;
- container readiness checks only for a CLI executable, not a reachable daemon
  or a runnable approved image;
- the Build transcript keeps tool activity inside the governance disclosure and
  has no command output pane, background-process controls, PTY input, or
  durable command history; and
- command output reaches the model after completion but no owner-facing stream
  is produced while it runs.

This design does not mark any of those claims complete until automated and live
evidence proves the same path from model proposal through UI recovery.

## Security and Product Posture

Raiker remains owner-authoritative and monitored. The owner may deliberately
select a strict local host backend, a native OS sandbox, a local container, SSH,
or Daytona. Raiker does not pretend those boundaries are equivalent: every
command and receipt names the effective backend and isolation posture.

The default rule is sandboxed execution with no network. An unavailable
sandbox fails closed and never becomes host execution. Local host execution is
an explicit owner selection, retains exact-command approval or a bounded
standing grant, and is labelled **Host access — reduced isolation** wherever it
can be selected or observed.

The following invariants apply to every backend:

- execution environment selection and approval policy are independent layers;
- selecting an environment grants no capability and changes no decision mode;
- every command is bound to the exact owner, machine principal, session, turn,
  repository, working directory, backend, command, environment digest, and
  approval/grant used;
- a backend may return unavailable or refused but may never silently substitute
  another backend;
- credentials are absent by default and can enter only through a purpose-bound
  credential broker grant;
- output is redacted before it is streamed, stored, shown, or returned to the
  model;
- filesystem and network boundaries cover descendant processes, not just the
  first executable;
- stop and timeout terminate the complete command process tree;
- `.raiker` is never writable or readable by a command backend, and `.git` is
  read-only except through the separately governed git executors;
- a background or interactive process cannot outlive its lease without an
  explicit renewal; and
- a backend that advertises recovery keeps supervision and redacted output in
  the backend boundary so a Raiker restart can reattach to the same run; a
  backend without that proof advertises recovery, PTY, and background support
  as unavailable and never misreports an unknown outcome as success.

## Architecture

### Command control plane

A new `raiker.execution.commands` package owns the backend-neutral lifecycle.
It is deliberately separate from the shell parser, container command builder,
approval relay, and web API.

The package exposes these stable interfaces:

```python
@dataclass(frozen=True)
class CommandRequest:
    run_id: str
    owner_principal_id: str
    acting_principal_id: str
    session_id: str
    turn_id: str
    action_id: str
    repository_id: str | None
    workspace_root: Path
    cwd: str
    executable_template: str
    argv_template: tuple[str, ...]
    safe_display: str
    credential_bindings: tuple[CredentialBinding, ...]
    shell: bool
    interactive: bool
    background: bool
    timeout_seconds: float
    max_output_bytes: int
    environment_profile_id: str
    network_policy_id: str | None


class CommandBackend(Protocol):
    def start(
        self,
        request: CommandRequest,
        supervisor: SupervisorClient,
    ) -> CommandHandle: ...


class CommandHandle(Protocol):
    def poll(self) -> CommandState: ...
    def wait(self, timeout: float | None = None) -> CommandState: ...
    def write(self, data: str) -> None: ...
    def terminate(self, reason: str) -> None: ...
    def reattach(self, run_identity: str) -> None: ...
```

`CommandService` validates the request, resolves exactly one selected backend,
creates the durable run before starting a process, streams redacted chunks into
the sink, enforces leases and budgets, finalises the receipt, and exposes
start/poll/wait/log/write/kill/reset operations to tools and APIs.

Exactly one command template is executable. `shell=false` requires a non-empty
`argv_template` and an empty `executable_template`; `shell=true` requires a
non-empty `executable_template` and an empty `argv_template`. Persisted
templates contain typed credential placeholders, never credential material.
`safe_display` is independently generated from that template, has all
placeholders visibly redacted, and is stored with a digest of the canonical
template. The broker rejects registered secrets and bounded secret patterns in
literal command text before any request, approval, event, or receipt is stored.
This prevents both a reviewed display/execution mismatch and credential leakage
through durable command text.

The existing approval relay and `ToolBroker` call `CommandService`; neither
invokes `subprocess` or a container runtime directly after this change.

### Protocol trust and compromise boundaries

| Component | Trusted for | Must not receive / compromise behavior |
| --- | --- | --- |
| Raiker service | Owner/session/grant decisions, vault resolution, durable evidence | A command never shares its process identity; service loss withholds new authority and recovery re-proves identity. |
| Per-run supervisor | One run's process tree, PTY, lease, redaction, bounded logs | Has no vault/database/provider key and cannot address another supervisor; compromise contains to that worker/run boundary. |
| Egress proxy sidecar | One worker identity plus one run capability/grant | Has no payload persistence/provider key and rejects replay from any sibling worker/network. |
| Container runtime / native policy service | Kernel boundary construction and cleanup | Treated as privileged host TCB; digest/protocol/readiness mismatch makes the backend unavailable. |
| SSH/Daytona host | Remote worker isolation and supervisor transport | Is a separately disclosed trust boundary; unsupported per-run isolation serializes the environment or disables background/concurrency/network credentials. |

Supervisor and proxy frames include protocol version, instance/run identity,
monotonic nonce, request digest, expiry, and message authentication. Replays,
unknown fields, downgrade versions, cross-run identities, and expired frames are
refused and audited without their payload.

### Backend-resident supervisor protocol

Recoverable execution is provided by a packaged `raiker-command-supervisor`,
not by keeping a `docker exec`, `ssh`, or Daytona client pipe alive. Each
persistent container includes it. SSH and Daytona readiness installs or proves
an owner-approved version and digest before advertising background, PTY, input,
lease, or recovery support. The Windows native helper embeds the same protocol.

The supervisor uses a versioned, length-prefixed authenticated protocol over a
local Unix socket/named pipe or the authenticated SSH/Daytona transport. Before
launch it durably creates a run directory owned by the sandbox identity with:

- a random run identity bound to request digest and supervisor instance id;
- PID/process-group or Job Object identity plus process start time;
- append-only **redacted** stdout/stderr frames with sequence and byte offset;
- atomic status, lease deadline, exit record, and truncation metadata; and
- a PTY/input endpoint when the backend proved that feature.

The supervisor installs its exit callback and durable identity before launching
the child. It owns process-tree kill and lease expiry. Raiker may reattach only
after the supervisor proves the same request digest, instance id, process start
identity, and authenticated channel; otherwise the run becomes `lost`. Raw
output is never written by the supervisor: the broker supplies a compiled
streaming redaction program and purpose-bound credential values over the secure
channel, they remain memory-only, and the child receives credentials only by
the approved delivery target (`stdin`, inherited descriptor/handle, protected
ephemeral file, or explicitly approved process environment). Credential values
never appear in protocol metadata, argv, environment snapshots, logs, or
receipts.

Any backend that permits overlapping runs must prove a distinct kernel process
identity and protected process view per run: a worker PID/user namespace or
cgroup/security principal, private `/proc`, private supervisor/control/log/PTY
endpoints, and network authority bound to that identity. Windows native uses a
per-run AppContainer profile/SID. A remote host may use an equivalent transient
unit/container. If a backend cannot prove this, `concurrent_runs=false`; while
one run is alive the next start fails with `environment_busy`, and the backend
cannot lend credentials or filtered-network authority to an overlapping run.
`local_strict` is explicitly reduced isolation and never accepts credential or
filtered-network grants.

### Authoritative environment resolution

`resolve_command_environment` consumes the owner-selected environment and the
requested tool. The selected profile controls `shell`, `run_command`, and
`process` execution. Read-only repository tools retain explicit per-tool
profile assignments until migrated, but the API distinguishes **Selected for
commands** from **Assigned tools** so the two concepts cannot be confused.

Resolution returns one of:

- an available `local_strict`, `native_sandbox`, `container`, `ssh`, or
  `daytona` backend;
- a named refusal such as `selected_environment_unavailable`,
  `selected_environment_tool_unsupported`, or
  `container_daemon_unreachable`; or
- an approval boundary for an explicitly requested host escape.

The resolver never scans for another backend after a refusal. Tests assert that
the host runner was not called for every unavailable-sandbox case.

### Local strict backend

The existing parsed argv policy becomes the `local_strict` backend. It remains
useful for owners who deliberately prefer a dependency-free local path, and for
small commands on hosts where no sandbox is installed.

It accepts one executable plus argv, refuses shell metacharacters,
interpreters, command chaining, substitution, expansion, unsafe per-binary
flags, paths outside the workspace, `.raiker`, and `.git`. It launches with the
constructed child environment, bounded output/time, and a process-tree handle.
It is never the automatic fallback from any sandbox.

### Native OS sandbox backend

The native backend uses an explicit driver per operating system:

- Linux: `bwrap` with a read-only host root, writable selected workspace,
  protected `.git`/`.raiker`, new PID and network namespaces, `/proc`, and
  bounded temporary files;
- macOS: `sandbox-exec`/Seatbelt when available, using a generated profile that
  permits process execution and selected-workspace reads/writes while denying
  other writes and network by default; and
- Windows: a packaged Raiker command-runner helper using a restricted token,
  Job Object, explicit workspace ACL allowlist, and Windows Firewall identity
  for offline/online execution. Setup may require one elevated owner action;
  ordinary runs do not.

The Windows helper is a dedicated Rust workspace under
`native/raiker-command-runner`. Its versioned named-pipe protocol uses an ACL
limited to the interactive owner SID and LocalSystem, rejects remote pipe
clients, authenticates each request with a vault-held instance key, validates
all canonical paths after handle-open, and inherits only an explicit
supervisor/PTY handle list. It creates a per-run AppContainer SID under the
owner/profile prefix, applies a
low-integrity restricted AppContainer token with administrative capabilities
removed (and no network capability in offline mode), grants that SID the minimum workspace ACL while explicitly
denying `.raiker` and write access to `.git`, and uses a kill-on-close Job Object
with CPU/memory/process limits plus ConPTY when requested. The signed release
artifact is installed beside the Python package by the Windows installer; its
Authenticode chain, SHA-256 digest, and protocol version are checked before use.

Offline mode is the default. Online filtered mode is enabled only after the
owner elevates once to install the signed `RaikerCommandPolicy` Windows service.
The service runs as a least-privileged service SID, owns the long-lived Windows
Filtering Platform (WFP) dynamic session, and installs ALE filters scoped to an
approved per-run AppContainer SID. The
filtered token receives only the client network capability required to reach the
proxy; WFP blocks all outbound transports, then permits only the authenticated Raiker proxy
endpoint. Filter ids and session identity are recorded; closing the dynamic
session removes them.

The service exposes a local named pipe restricted to LocalSystem and the
installing owner SID, rejects remote clients, impersonates the caller to verify
that SID, and authenticates a nonce-bound request with the vault-held Raiker
instance key. Its HKLM configuration is administrator-writable only and pins
the Authenticode publisher, runner/proxy digests, protocol version, allowed
AppContainer profile prefix, and proxy loopback endpoint; the protocol cannot
request arbitrary filters or destinations. On boot or service restart it opens
a new dynamic session but does not restore a permit until non-elevated Raiker
re-authenticates an active run/grant. A crash removes all dynamic filters and
commands fail closed until readiness proves the service/session and required
filters live. Installer, update, reset, and uninstall are transactional and
remove profiles, ACL projections, filters, service registration, and pinned
configuration on rollback. Readiness executes a
real low-integrity child and proves Job membership, workspace write, outside-
workspace denial, `.raiker` read/write denial, `.git` write denial, descendant
network denial, and complete process-tree termination. Windows packaging and CI
build/test the helper; if installation, signature/digest, firewall state, or
any probe is unavailable, `native_sandbox` is unavailable rather than emulated.

Driver readiness checks a real harmless probe, not only the presence of a
binary. If a platform driver cannot prove descendant filesystem and network
containment, the backend is shown as unavailable rather than downgraded to the
strict host policy.

### Persistent container backend

Docker and Podman represent one owner/session/environment as labelled persistent
state, not one shared process container. The state consists of the selected host
workspace bind, a per-session `/sandbox-home` cache volume, an immutable image
digest, and a small Raiker-side coordinator record. Every run gets a separate
worker container, PID namespace, non-root uid, supervisor instance, IPC mount,
and network namespace. A foreground run and a background run may therefore
coexist without a shared uid, `/proc`, signal boundary, control socket, PTY, log,
credential descriptor, or proxy capability. The cache/workspace persist across
workers; worker containers persist only while their run/lease needs them and
are reattached after a Raiker restart. Reset processes removes workers but keeps
session state; recreate also removes the cache volume.

The `/sandbox-home` volume is owned by the session identity and mounted into a
worker only for the duration of that run. To prevent hostile concurrent workers
from using it as a cross-run control channel, executable files, sockets, device
nodes, FIFOs, and hard links are refused at the volume boundary; supervisor
state, credentials, logs, and capabilities never enter it. Worker isolation is
proven with a two-run hostile test that attempts sibling process discovery and
signals, `/proc` and descriptor reads, control/log/socket access, credential
recovery, and reuse of the other run's proxy grant.

Credential-bearing workers acquire an exclusive environment lease: no sibling
worker may overlap them, and they cannot start while another worker is alive.
This closes the remaining shared-workspace/cache exfiltration path in which a
credentialed process could intentionally deposit its loan for a sibling. The
approval preview states this serialization. Credential-free workers may overlap
because their process, control, PTY, and network authority remain per-run;
shared workspace/cache writes remain an explicit collaboration property of the
session, not a process-authority channel.

The container has:

- no network unless a filtered network grant is active;
- a read-only root filesystem plus size-bounded tmpfs mounts;
- all capabilities dropped and `no-new-privileges`;
- CPU, memory, PID, output, and wall-clock bounds; a disk bound is advertised
  only when the selected runtime/storage driver proves a project quota, while
  tmpfs size bounds are always reported separately;
- a non-root user;
- the selected repository mounted read/write at `/workspace` for Build work;
- `.git` over-mounted read-only and `.raiker` masked by a Raiker-owned empty
  read-only bind whose empty source is mode `000` and owned by an unmapped host
  identity, after the workspace mount. Preflight refuses a `.git` or
  `.raiker` symlink/reparse-point target, and readiness proves `.raiker` cannot
  be listed, read, written, traversed, or reached through a link/junction;
- no host home, Docker socket, provider key, vault key, or ambient credential;
  and
- labels containing only hashed owner/session/profile ids for recovery and
  cleanup.

Commands are submitted to the supervisor inside that run's worker container,
using the profile's absolute shell path and `-lc`. A short-lived `docker exec`
may carry the authenticated control frame, but is never the process supervisor;
disconnecting it cannot orphan control or logs. Full shell syntax is permitted
there because the technical boundary, not a basename heuristic, contains the
command. The safe shell display and canonical template digest are shown in
approval and bound into the receipt.

Reset supports two choices: **Reset processes** stops live jobs but keeps the
session filesystem; **Recreate sandbox** destroys processes and writable state.
Both are explicit, audited, and confirm their scope before execution.

### SSH and Daytona backends

The existing bounded SSH and Daytona adapters implement the same command
lifecycle rather than returning metadata through a separate path. Exact argv is
never serialized into an ad-hoc remote shell string. The authenticated
transport starts or connects to the verified supervisor and sends a framed
request containing cwd, argv/shell template, limits, and request digest. Each
backend must prove start, poll, wait, bounded logs, and process-tree kill.
`write`, PTY, background, lease, and restart recovery are advertised only when
the remote supervisor proves them during readiness; without that supervisor the
backend is foreground-only and recovery is unavailable.

SSH binds host, user, host key, canonical cwd, command digest, and credential
reference. Daytona binds sandbox id, provider snapshot, budget reservation, and
actual-cost reconciliation. Neither backend leaks its credential into a
receipt, log, model result, or process argument.

### Background processes and PTY

The model-visible `run_command` tool gains typed options:

```json
{
  "command": "npm run dev",
  "background": true,
  "interactive": false,
  "timeout_seconds": 180,
  "notify_on_complete": true
}
```

A new `process` tool supports `list`, `poll`, `wait`, `log`, `write`, and
`kill`. Every operation is owner/session scoped and re-governed against the
original grant plus the current session; revoked authority fails closed. `write` is
accepted only for an interactive run; it is byte-bounded and records only the
actor, timestamp, and byte count. Raw input is never stored. A PTY is allocated only when
`interactive=true`, the backend reports PTY support, and the exact request was
approved or covered by a standing grant.

Background runs receive a lease. The default lease is the shorter of the
request timeout and 30 minutes; the owner may renew it from Build. A stopped
turn does not automatically kill an explicitly backgrounded run, but the UI
states that choice and offers **Stop process**. Foreground commands are killed
when the turn is stopped.

### Network broker and domain escalation

Sandbox networking starts disabled. A command may request one or more domain
patterns through the existing approval system. The approval preview names the
domains, ports, profile, command, expiry, and whether the grant is once or for
this session.

For native and container backends, outbound traffic uses a packaged
`raiker-egress-proxy` outside the command environment. It is a real runtime
artifact built into the command image and Python release, with an authenticated
control socket and separate data listeners for HTTP CONNECT and SOCKS5 CONNECT.
Each worker has a distinct internal network and proxy sidecar. The proxy binds
authorization to the worker network identity plus a random per-run capability;
neither value is visible to another run. The proxy maps both to an active grant
and never accepts an unauthenticated or wrong-worker host/port request. It does not support UDP, SOCKS BIND,
arbitrary listening, or raw IP destinations. A container with a filtered grant joins one
private `--internal` network shared only with a proxy sidecar; only the proxy
sidecar joins a second egress-capable network. The command container therefore
has no direct external route even when an application ignores proxy environment
variables. Native drivers expose the proxy through their platform sandbox
policy and deny direct sockets. The proxy:

- accepts only DNS names and ports covered by the active grant;
- resolves DNS itself for every connection, pins approved public addresses for
  that connection, and rejects CNAME/address changes to private, loopback,
  link-local, multicast, reserved, or metadata ranges;
- re-authorizes the destination of every proxy-observed HTTP redirect; callers
  that follow redirects themselves must make a newly authorized connection;
- records host, port, byte counts, decision id, and outcome, never payloads;
- has no general host environment or provider credentials; and
- revokes a grant immediately when the owner stops the run or withdraws it.

A denied domain produces `command_network_approval_required` with the exact
host and a route to the decision. Approval resumes the same command only when
the backend can safely retry; otherwise the receipt says the original process
ended and a new run is required. No command receives unrestricted network as a
side effect of enabling web search or a connector.

SSH and Daytona enforce the same grant contract through their configured remote
policy adapters. If a remote environment cannot prove filtered egress, it is
labelled **Remote network policy not enforced** and cannot be selected for an
allowlisted-network command. Revocation first closes listeners and active
connections, then removes the sandbox route/firewall permit, and only then
marks the grant revoked; recovery repeats this teardown idempotently for
expired grants.

### Durable data model

Migration `RAIKER-2030-command-runs` adds owner-scoped tables:

- `command_runs`: immutable request identity plus mutable state, timestamps,
  backend, profile, canonical template digest, safe display, cwd,
  approval/grant ids, isolation posture, encrypted supervisor-handle reference,
  lease, exit code, termination reason, byte counts, truncation, redaction count,
  and receipt digest; executable templates and credential bindings are stored
  separately as vault-encrypted material and erased on terminal retention;
- `command_output_chunks`: monotonically numbered, redacted stdout/stderr
  chunks with byte offsets and timestamps, bounded per run;
- `command_network_grants`: domain/port scope, run/session binding, decision,
  expiry, revocation, and use count;
- `command_network_attempts`: immutable connection-attempt rows with run/grant,
  requested DNS host/port, resolved-address digest, decision/outcome, open and
  close timestamps, and byte counts, never payloads; and
- `command_receipts`: canonical JSON evidence plus digest and checkpoint ids.

Raw unredacted output and terminal input are never stored. Sensitive handles
and executable material use the existing vault envelope mechanism and are never
returned by list/detail APIs. Chunk and attempt tables have owner/run indexes,
per-run and per-owner quotas, bounded retention, and oldest-first deletion only
after receipt finalization. Migrations are transactional, idempotent, and
rollback-tested. Receipt insertions are immutable. Owner id is part of every
primary lookup; a session id alone never grants access.

Run states are:

`queued -> starting -> running -> finalizing -> {succeeded, failed, timed_out,
cancelled, contained, lost}`.

Only `running` accepts input or kill. The supervisor callback is registered
before launch, and immediate exit may compare-and-swap `starting` directly to
`finalizing`. One database transaction inserts the canonical immutable receipt
and changes `finalizing` to its terminal state. A receipt failure leaves the run
non-terminal in `finalizing`; bounded retry either writes the intended receipt
or atomically writes a minimal immutable containment receipt describing the
evidence failure and transitions to `contained`. If storage cannot write even
that containment receipt, the run remains `finalizing`, the UI says **Evidence
not durable — success withheld**, and recovery keeps retrying. Owner discard is
a separately authorized transaction that writes an immutable `discarded`
containment receipt before terminal transition. Every transition is
compare-and-swap so timeout, owner stop, natural exit, and recovery cannot
finalise the run differently.

### Streaming and event model

The supervisor reads stdout and stderr concurrently as bytes, incrementally
decodes UTF-8, and passes characters through a compiled streaming redactor. A
single versioned rule manifest is the source for every existing
`raiker.context.redaction._PATTERNS` behavior: private keys; GitHub/OpenAI/AWS
tokens; bearer headers; credential assignments and spoken credentials;
email/card/account/medical identifiers; high-entropy fallback; registered exact
secrets; the snake/server-id/path/digest exceptions; case/word boundaries; and
callable replacement semantics. Python and Rust compile that manifest into
equivalent DFA/transducer states. Variable-length token/assignment/email/high-
entropy rules withhold the current lexical candidate until its terminating
boundary, PEM rules withhold through the validated end marker, and registered
secrets use a multi-pattern prefix automaton. Nothing is emitted until no rule
can still match it. There is no arbitrary fixed carry length. Shared conformance
vectors compare streaming output with `redact_text` for default, locator,
identifier, and digest modes at every byte split, minimum lengths, word
boundaries, EOF, invalid UTF-8, truncation, overlaps, and callable branches. The
redactor emits only safe UTF-8 chunks, which are durably written before client
notification. A per-run byte budget stops further capture without blocking the
child; the receipt records truncation and total observed bytes.

The API exposes no direct create endpoint; all command creation passes through
the approval relay or standing-grant `run_command` tool so governance cannot be
bypassed. The selected environment is resolved from owner state and is not an
accepted model/API field. The read/control API exposes:

- `GET /api/command-runs?session_id=...` for scoped history;
- `GET /api/command-runs/{run_id}` for state and receipt;
- `GET /api/command-runs/{run_id}/output?after=<sequence>` for bounded catch-up;
- `POST /api/command-runs/{run_id}/input`;
- `POST /api/command-runs/{run_id}/stop`;
- `POST /api/command-runs/{run_id}/lease`; and
- `POST /api/execution-environments/{profile_id}/reset`.

The existing turn stream emits metadata-only `command_started`,
`command_state_changed`, `command_output_available`, and `command_completed`
events. Build uses the output endpoint for content so lifecycle streaming never
puts command output into the general event payload.

### Execution receipts and recovery

Every terminal run finishes with a receipt containing:

- redacted safe command display and canonical template digest;
- effective backend, profile, sandbox mode, workspace/cwd, and network grant;
- proposer, approver/grant, resolver, session, turn, action, and timestamps;
- exit/cancel/timeout/lost state;
- stdout/stderr byte counts, truncation, and redaction counts;
- changed-file summary calculated against a pre-run checkpoint without treating
  it as an approval to keep those changes;
- tests or diagnostics recognised from the command and their exit status;
- checkpoint ids that predated governed mutations; and
- a digest over the canonical receipt.

The receipt is linked from the transcript, Approvals, Observability, and the
Build output pane. It can be exported without output content, or with the
already-redacted bounded content at the owner's choice.

Before a mutating run, the existing checkpoint service records the repository
identity and bounded workspace manifest. After finalization, a symlink-safe
workspace walker compares canonical paths and records only relative changed
paths, status, and bounded hashes; it never follows links/junctions or reads
outside the selected workspace. A registry of bounded diagnostic parsers
recognizes pytest, compiler, and common test-runner records from already-
redacted output without evaluating terminal control sequences. These producers
feed canonical receipt serialization and have independent failure fields.

One application/workspace-scoped `CommandService` is created in the FastAPI
composition root and injected into the executor registry, `ToolBroker`, approval
relay, command routes, orchestrator, lease reaper, and recovery coordinator.
FastAPI lifespan starts reconciliation and the periodic lease task, and bounded
shutdown stops foreground runs plus non-persistent session supervisors while
preserving explicitly configured recoverable sandboxes. Profile change runs the
same scoped cleanup transaction.

On application start, `CommandRecovery` inspects durable non-terminal runs and
backend labels/handles:

- if the process/container is still provably the same run, monitoring resumes;
- if the process ended and its backend supplies an exit record, the run is
  finalised from that record;
- if identity cannot be proven, the run becomes `lost`, never `failed` or
  `succeeded`, with a recovery action; and
- expired Raiker-owned containers and processes are stopped only after their
  labels and workspace bounds match the durable record.

An integration test kills and restarts the Raiker service while a supervised
container command is active, then proves the same run id, ordered log catch-up,
PTY input where enabled, lease expiry, and process-tree kill. A second test
invalidates supervisor identity and proves the run becomes `lost` without a
success/failure inference.

### Build terminal and output surface

Build gains a resizable bottom pane that is consistent with the existing visual
system and works at 375, 768, 1024, and 1440 px.

The pane contains:

- a run list with running/succeeded/failed/timed-out/cancelled/lost status;
- live interleaved stdout/stderr with separate accessible labels and optional
  stream filtering;
- command, cwd, backend, sandbox, network, duration, exit code, byte count,
  truncation, and redaction badges;
- **Send input** only for an interactive run;
- **Stop process**, **Renew lease**, **Reset processes**, and **Recreate
  sandbox** controls with exact consequences;
- **Jump to first failure**, using recognised `path:line[:column]` coordinates
  to open the existing source inspector;
- **Copy redacted output** and **Open execution receipt**; and
- an honest empty/unavailable state that links to Settings -> Runtime.

Tool activity is also promoted into first-class transcript rows. A command row
opens the same run in the bottom pane; the full governance trail stays in its
existing disclosure. Reloading Build reconstructs the pane from durable runs
and chunks before subscribing for new events.

### Settings and approval surfaces

Settings -> Runtime distinguishes:

- command backend selection;
- native/container/SSH/Daytona readiness from a real probe;
- persistence and resource ceilings;
- workspace read/write and protected-path posture;
- PTY, background, input, filtered-network, and recovery support; and
- the exact remediation for an unavailable capability.

Approvals show the redacted safe command display, cwd, backend, isolation posture, requested
network domains, interactive/background flags, timeout, and affected workspace.
The owner may approve once or create a narrowly scoped session grant. A grant
can constrain command prefix, backend, cwd, network domains, interactivity,
maximum duration, and expiry. Revocation terminates runs whose continued
authority depends on that grant.

Approvals and UI surfaces receive only `safe_display`; literal input is scanned
for registered and pattern-matched secrets before an approval record exists.
Commands that need a credential must choose a named broker reference and an
allowed delivery target. The preview names the reference and target (for
example, **OpenAI credential via protected descriptor**) but never the value.
Input, stop, lease renewal, and environment reset each require the current owner
session plus an unrevoked lifecycle grant. Reset additionally requires an
owner-confirmed decision because it destroys processes or writable state.

## Error Handling

All expected failures have stable reason codes and owner-facing remediation:

- backend/driver/daemon/image unavailable;
- selected environment unsupported or changed since approval;
- workspace/cwd outside the selected repository;
- protected path exposure;
- PTY/input/background unsupported by the backend;
- command, output, process, disk, or time budget exceeded;
- network domain withheld, revoked, or denied by the address guard;
- credential grant missing or expired;
- process launch, stream decode, cleanup, or receipt finalisation failure;
- recovery identity mismatch; and
- concurrent stop/timeout/exit conflict.

An execution failure never tears down the agent loop. The tool result and Build
surface state the failure, its boundary, and the safe next action. A receipt
write failure prevents a success claim: the run stays non-terminal
`finalizing` until the intended receipt or a minimal containment/discard receipt
can be written atomically with the terminal transition.

## Testing and Verification

Implementation follows test-driven development with workspace-local pytest temp
directories on Windows.

### Automated backend tests

- authoritative selected-environment routing and no-fallback assertions;
- full-shell container execution, protected mounts, no ambient environment,
  no network, resource limits, persistent reuse, reset, and cleanup;
- Linux/macOS/Windows native driver command/policy construction plus platform
  integration tests where the runner is available;
- foreground/background state transitions, concurrent stdout/stderr, split-
  token redaction at every boundary, registered secrets longer than any input
  chunk, PEM/multiline regions, UTF-8 byte splits, concurrent streams, final
  flush and truncation, plus timeout, input, PTY, lease renewal, and process-tree
  kill;
- SSH/Daytona lifecycle parity and capability-advertisement honesty;
- proxy domain/port matching, public-address guard, redirect/rebinding defense,
  authenticated CONNECT/SOCKS transport, direct-socket denial, grant
  expiry/revocation ordering, cleanup recovery, and immutable byte-count-only
  connection audit;
- callback-before-launch, immediate-exit, exit/stop/timeout races, atomic
  receipt finalization, idempotent retry, and real service restart recovery;
- traversal, symlink/junction, nested-repository, Windows case/path, `.raiker`
  read/write denial, `.git` write denial, and descendant boundary tests; and
- canonical receipt digest, pre-run checkpoint, symlink-safe changed-file and
  bounded diagnostic summaries.

### Automated API and web tests

- owner/session isolation on every command endpoint;
- rejected secret-bearing command text never reaches database, approval,
  event, API, or rendered UI fixtures;
- approval and standing-grant scope cannot be widened by request fields;
- catch-up output pagination cannot skip, duplicate, or reveal unredacted data;
- Build pane live updates, reload recovery, status/filter/input/stop/reset flows,
  keyboard and screen-reader behavior, failure navigation, and responsive
  layouts; and
- Settings and Approvals state the effective boundary and never imply a
  backend feature that readiness did not prove.

### Live verification

With the Raiker service stopped before the run, start a fresh loopback instance
and configure providers only through the UI. Verify Anthropic, OpenRouter,
OpenAI, and Ollama `gemma4:31b-cloud` separately. For each provider, run a Build
turn that executes a sandboxed foreground command and observes its receipt.

Across the complete matrix, also verify:

- a persistent background dev server: start, poll, log, input where supported,
  stop, recover after a browser reload, then survive a real Raiker service
  restart with identical run identity and controls;
- an interactive PTY command;
- a blocked network domain followed by an allow-once decision and retry;
- timeout, output truncation, cancellation, and a deliberate test failure with
  jump-to-source;
- unavailable Docker/Podman/native/remote states with no host fallback;
- reset and recreate behavior; and
- direct external sockets fail while the approved proxy domain succeeds and a
  revoked grant closes the active route; and
- screenshots at 375, 768, 1024, and 1440 px with no secrets, clipping, or
  inaccessible controls.

Provider keys must never enter source files, shell command lines, logs,
screenshots, or committed Playwright state.

## Documentation and Compatibility Mapping

Update the source documents without erasing their evidence:

- GAP-BUILD B1, B5, B15, and B20 state the verified delivered scope and link to
  tests/live evidence;
- ADD-01 distinguishes read-only ephemeral tool containers from persistent
  command sandboxes;
- README Known Limits removes the stale shell split and honestly retains any
  backend-specific limitation;
- `docs/REFERENCE_PLATFORM_COMPATIBILITY.md` receives a dedicated shell,
  sandbox, process, and recovery control set with separate status for every
  reference capability; and
- any issue discovered and not fixed in this run is added to
  `docs/plans/TO_BE_FIXED.md` in its existing Observed/Reproduce/Root
  cause/Required fix/Required UI outcome format.

The compatibility table may mark a row at parity or beyond only when the live
test proves the UI and effective backend, not from an interface or unit test
alone.

## Acceptance Criteria

The work is complete only when all of the following are true:

1. The selected command environment is the environment that executes, and an
   unavailable sandbox never reaches the host runner.
2. Approval-gated and standing-grant commands share one lifecycle, output,
   redaction, receipt, and recovery implementation.
3. Container mode supports full shell commands, persistent session state,
   foreground/background execution, bounded logs, input/PTY where advertised,
   kill, reset, and filtered network grants.
4. Native, local strict, container, SSH, and Daytona backends advertise only
   features proven by readiness and use the same owner-facing contract.
5. Build streams command state and redacted output, recovers it after reload,
   navigates to failures, and exposes stop/input/lease/reset/receipt controls.
6. Every run has an owner-scoped, digest-bound receipt and an honest terminal
   state, including `lost` when recovery cannot prove the outcome.
7. The four requested providers each complete a live Build command scenario
   from credentials entered through the UI.
8. Responsive Playwright screenshots are reviewed and contain no credential or
   private output.
9. Focused and full Python/web quality gates pass.
10. Changes are committed and pushed to `origin/main`, and every GitHub Actions
    workflow for the pushed SHA concludes successfully.

## Explicit Non-Goals

- Containerising the Raiker service, provider client, database, or approval
  authority with the command.
- Giving a command the host Docker/Podman socket.
- Sending provider credentials into a general shell environment.
- Treating a container as equivalent to ADD-12's future micro-VM boundary.
- Inventing rollback for arbitrary shell side effects outside the selected
  workspace; those effects must be prevented by the boundary or described in
  the receipt.
- Claiming that a remote backend enforces local filesystem or network policy
  unless its readiness probe proves the remote enforcement adapter.
