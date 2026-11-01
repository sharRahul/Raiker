# Native sandbox migration: initial findings

Status: **incomplete and not release-ready**. This is not yet the required
comprehensive execution-boundary audit. Docker and Podman are no longer invoked
anywhere in Raiker (see *Docker and Podman removal* below); the command service
requires the native backend; and native execution stays unavailable until
disposable task workspaces exist. Release blockers are tracked in
`docs/plans/TO_BE_FIXED.md`.

Baseline: `4d7c14dc9161160e10c417a2f3b5b824c1a646fd` on `origin/main`.

## Known execution paths and blockers

| Path | Current role and evidence | Required work and verification |
| --- | --- | --- |
| `raiker/execution/commands/service.py`, `code_placement.py` | The service routes local-profile commands to the native backend and refuses other non-native profiles. The native backend refuses unavailable boundaries and unsupported background/interactive modes. The earlier router placement logic still describes host execution and needs consolidation. | Verify the native boundary itself, remove contradictory routing and profiles, and test stale approvals and all entry points. `tests/test_native_command_required.py` covers service placement and unavailable-probe refusal, not OS enforcement. |
| `raiker/execution/commands/backends/container.py`, `raiker/execution/container_tools.py`, `profiles.py` | **Removed.** The `container` profile kind no longer exists. Stored container rows are inert history: the selection resolves to `container_environment_retired`, tools assigned to an enabled retired row are refused (`retired_container_tools`), and Settings lists the row as *retired* so the owner can remove it. | Covered by `tests/test_command_backends.py`, `tests/test_execution_environments.py`, `tests/test_execution_profiles.py`, `tests/test_tool_broker.py`. |
| `raiker/runtime/executors/containers.py`, `tier4_plugins.py` | **Removed:** `container_execution_cap`, `plugin_sandboxed_runtime_cap`, `plugin_sandbox_image_pull_cap` and their executors. The remaining plugin runtime runs the entrypoint in the native sandbox (`sandbox.run_command` → `sandboxed_program.run_bounded`). | Covered by `tests/test_plugin_sandbox.py` (real boundary) and `tests/test_phase_4_plugin_runtime.py`. |
| `raiker/runtime/executors/mcp.py`, `sandbox.py`, `raiker/hooks/handlers/command.py` | Local MCP stdio, the plugin launcher and command hooks run in the native sandbox, each holding only its own folder with no network, or refuse with `native_sandbox_required`. Other subprocess sites and their callers remain to be audited. | Trace all callers, distinguish trusted infrastructure from agent-controlled execution, and enforce the broker where required. |
| `native/raiker-command-runner/src/boundary_unix.rs` | Bubblewrap installs seccomp; two denied syscalls were measured with control arms in WSL2. Seatbelt uses a narrower runtime and workspace read allowlist, unverified on macOS. | Validate Seatbelt enforcement and toolchain access, additional seccomp restrictions, and resource controls on supported systems. |
| `native/raiker-command-runner/src/boundary_windows.rs` | Existing Windows boundary requires detailed security and lifecycle review. | Verify AppContainer, ACL cleanup, job limits, process descendants and network denial on supported Windows versions with adversarial control-arm tests. |
| `raiker/models/conversion.py` | **Docker runner removed.** `NativeConversionRunner` runs an owner-installed llama.cpp (`RAIKER_LLAMA_CPP_DIR`) in the native sandbox on Linux: model and toolchain mounted read-only, writes only to a scratch folder, results moved to the output afterwards, provenance names the converter and quantizer by content. Without a toolchain, or off Linux, it refuses by name. | Package llama.cpp with Raiker; Windows and macOS read-only staging. `tests/test_model_conversion_isolation.py` runs a stand-in toolchain through the real boundary. |
| `raiker/tools/git.py`, `raiker/control/build_worktrees.py`, `raiker/github/local_methods.py` | Git and worktree operations run on the host as trusted infrastructure: Raiker builds every argv, and hooks, fsmonitor and filter drivers are neutralised (see the audit below). | Git tools read the real repository; `git_status` and `git_diff` add the session copy's not-yet-applied edits (`task_copy`), so the agent sees its own work. Commits and branches still act on the project, after the owner applies the copy. |
| `raiker/app/`, `desktop/src/`, `scripts/` | Launch, update, packaging, setup and test infrastructure; each site is classified in the audit below. | Done: a release refuses a commit unless every platform's native-runner enforcement tests passed on it, and every download is signed keylessly with the repository's GitHub identity and verified before the draft (FIXED-1282). Apple, Authenticode and Linux package identities remain owner secrets, applied when configured. |
| `.github/workflows/ci.yml`, `scripts/scan_containers.py`, `scripts/scan_images.py`, `containers/**` | **Removed** with the product dependency: the container definition check, the grype image scan, its exception file and both Containerfiles. The native runner job runs on `ubuntu-24.04`, `windows-2025`, `macos-15` and `macos-15-intel`. | Add release-evidence gates that fail packaging when a platform's enforcement tests have not passed. |

## Every place Raiker starts a process (audit, 2026-11-01)

Found by searching the Python package for `subprocess.run`, `Popen`,
`check_output`, `call`, `os.system`, `os.exec*`, `os.spawn*` and
`asyncio.create_subprocess_*`, the desktop shell for `child_process`, and the
runner for `Command::new`. Each site is classified by **who chooses what
runs**. Agent-reachable code (the model, a task's files, a server or plugin
the owner allowed) must cross the native boundary; trusted infrastructure runs
programs Raiker or the owner chose, with arguments Raiker builds.

| Site | What it starts | Who chooses it | Boundary |
| --- | --- | --- | --- |
| `execution/commands/backends/native.py`, `runner.py` (`StreamingCommandRunner`) | `raiker-command-runner`, which starts the agent's command | Agent argv, validated by `command_policy` | **Native sandbox** (task copy, no network unless downloads are on) |
| `execution/commands/supervisor_client.py` | Raiker's own detached supervisor (`python -m raiker.execution.commands.supervisor`), which starts the runner | Raiker | Supervisor is trusted; the command inside it is **native sandbox** |
| `execution/commands/sandboxed_program.py` | The runner, for a local MCP server or a plugin entrypoint | Owner-allowed server or plugin | **Native sandbox** (its own folder only, no network) |
| `execution/commands/backends/native.py` `run_sandboxed_program` | The runner, for a command hook | Hook script in the project | **Native sandbox** (the script alone, no network) |
| `models/conversion.py` `NativeConversionRunner` | The runner, for llama.cpp's converter and quantizer | Owner-installed toolchain | **Native sandbox** (model read-only, Linux only) |
| `execution/commands/runner.py` (tree stop) | `taskkill` / process-group signals | Raiker, fixed argv | Trusted (stops a sandboxed run) |
| `execution/commands/backends/remote.py`, `remote_supervisor.py` | `ssh` to an owner-added host; the remote supervisor there | Owner-configured host; agent argv validated | **Remote host's boundary**, not this machine's; the owner chose the host |
| `tools/git.py` | `git` | Raiker builds every argv | Trusted, hardened: hooks path, fsmonitor and every filter driver neutralised; task copies hold no `.git`, so agent code cannot configure one |
| `github/local_methods.py` | `gh auth token`, `git credential fill` | Raiker, fixed argv, owner-selected | Trusted (reads the owner's own credential, only when selected) |
| `models/slot_runtime.py` | `llama-server` / MLX servers on loopback | Owner-installed runtime and model | Trusted owner infrastructure; never handed agent input as code |
| `models/codex_app_server.py` | The owner's Codex CLI app server | Owner-installed | Trusted owner infrastructure (stdio JSON-RPC) |
| `notify/approval_notifier.py` | The owner's notification command | Owner configuration; arguments are redacted metadata | Trusted owner configuration; agents edit task copies, never Raiker's settings |
| `storage/sqlcipher_probe.py` | Raiker's own interpreter, probing SQLCipher | Raiker, fixed argv | Trusted |
| `execution/windows_authenticode.py` | PowerShell `Get-AuthenticodeSignature` | Raiker, fixed argv | Trusted (verifies a downloaded file) |
| `app/launcher.py`, `service.py`, `desktop_shell.py`, `desktop_update.py`, `update_handoff.py`, `system_check.py` | The Raiker host, the OS service manager, the desktop window, a verified installer, system queries | Raiker, fixed argv | Trusted infrastructure (installation and lifecycle) |
| `app/desktop_build.py`, `desktop_smoke.py`, `scripts/` | Build and test tooling | Developer | Not shipped behaviour |
| `desktop/src/host.ts`, `setup.ts` | The Raiker host and its system check | The desktop shell, fixed argv | Trusted infrastructure |
| `native/raiker-command-runner` (`Command::new`) | `bwrap`, `sandbox-exec`, `systemd-run --scope`, `CreateProcessWithLogonW`, the probe's own self-test child, `icacls`/PowerShell during account setup | The runner | The boundary itself |

No site runs model-chosen or project-supplied code on the host. The remaining
work is not a missing boundary but a narrower one: Git operations read the
real repository (trusted, hardened), and the local model servers run on the
host as owner infrastructure.

## Ordered checklist

- [ ] Complete the repository-wide inventory and trace each agent entry point to the OS process.
- [ ] Define and implement one fail-closed broker, disposable workspaces and reviewed promotion.
  `raiker/execution/workspaces.py` now provides the workspace half: a private
  copy without `.git`, `.raiker`, links or special files; a content manifest;
  a diff that rejects links and protected names the task creates; promotion
  that refuses on owner changes made after the snapshot, writes nothing a
  path check refuses, never writes through a link, and restores every original
  on failure; quotas; and crash cleanup. `tests/test_task_workspaces.py`
  exercises real junctions/symlinks and hard links.
  **Wired (2026-10-31).** `NativeSandboxBackend` runs every command in a
  per-(owner, session, working-folder) copy from `TaskWorkspaceRegistry`, kept
  outside the Raiker workspace in `<workspace>-sandboxes/`; the copy holds only
  the command's working folder. The probe's measurements alone decide
  availability, and the backend refuses (`native_disposable_workspace_required`)
  without a registry. The owner reviews and applies or discards a copy through
  `GET /api/command-workspaces` and `POST .../{id}/promote|discard`; promotion
  must name the exact change set the owner saw (`workspace_review_stale`
  otherwise) and is refused while a run in that session is active. Both outcomes
  are audited (`task_workspace_promoted`, `task_workspace_discarded`). Build shows
  the copy's changes with **Apply to project** and **Discard**. `.git` and
  `.raiker` are rejected at any depth, so a task cannot plant a repository.
  Real Windows end-to-end: `git --version` ran in the AppContainer rooted in the
  copy and the project was unchanged; a virtualenv interpreter outside the
  boundary was refused.
  **Task tree (2026-11-01).** File tools and commands now share the copy
  (`raiker/execution/task_tree.py`). A project turn binds its session to the
  project root (`TaskWorkspaceRegistry.bind`); the turn's `PathAuthority` is
  wrapped in a `TaskTreeAuthority` that confines and names every path against
  the real project and then opens it in the copy, creating the copy on the
  first write. Commands take the same copy and run at their cwd inside it.
  Approved writes executed after the turn resolve through the conversation's
  session binding. Components of a copy path are checked for links before use,
  because sandboxed code can create them; this is a path check, not a pinned
  handle, so a command racing a file tool remains a residual risk. Git tools
  (`git_status`, `git_diff`) still describe the real repository, since the copy
  has no `.git`; the copy's changes are reviewed through the task-copy review.
  Checkpoint pre-images are still captured from the real path.
- [ ] Verify Windows AppContainer, macOS Seatbelt and Linux Bubblewrap plus real seccomp enforcement.
- [ ] Implement and measure resource, network, lifecycle and cleanup controls; report only measured capabilities.
- [ ] Migrate command, plugin, MCP, scheduled and delegated execution without host fallback.
- [x] Safely migrate obsolete profiles, then remove container code, UI, packaging and documentation.
- [ ] Implement actual OS enforcement tests with unsandboxed controls and cross-platform CI evidence.
- [ ] Verify installers, upgrades, signing and release gates on supported platforms.

No platform-specific security test, installer test, Playwright test or CI run is
claimed by this initial record. Missing cross-platform evidence is a release
blocker, not evidence that a boundary works.

The shared legacy subprocess launcher and local MCP stdio launcher are blocked with
`native_sandbox_required`; affected plugin, container and network capabilities
are unavailable until migrated. This is not a comprehensive bypass audit or OS
enforcement evidence. The old CI suite contains host-execution expectations and
is failing; it must be migrated without replacing enforcement tests with mocks.

The Python native-driver probe now rejects nonzero exits and malformed availability
or observation fields. This validates the report format only; it does not prove
the runner enforces filesystem, network or process isolation. Plugin execution
remains blocked pending disposable workspaces and enforceable capability policy;
local MCP stdio remains blocked pending sandboxed bidirectional stdio, lifecycle
control and credential handling.

Command risk classification is now separate from the advisory sandbox placement.
The existing host-network classification and gates are preserved; they do not
select a host backend. Placement reports unavailable when the native sandbox or
requested mode cannot be used. The command service still independently probes at
launch. This does not account for all subprocess paths or prove OS enforcement.

The agent-facing Git diff path (`raiker/tools/git.py:run_git`) now disables
external diff and text-conversion drivers, restricts accepted diff arguments,
and rejects pathspec escapes. A real unsandboxed control showed the previous
implementation could launch an external driver. Other Git subprocess paths and
workspace command hooks still require a complete execution-boundary audit; this
change does not classify them as safe.

Workspace command hooks run in the native sandbox (2026-11-01): the script is
copied alone into a throwaway folder under the copy base and run there with the
event on stdin and no network (`run_sandboxed_program`). Without an enforced
boundary they still refuse with `native_sandbox_required`, and an enforcing hook
that cannot run requires an owner decision (`tests/test_hook_fail_closed.py`).
HTTP and built-in hooks retain their separate behavior.

The sanitized command environment now prevents a workspace `.gitconfig` from
being used as Git global configuration, even if an extra environment requests
it. `tests/test_sandbox_git_config.py` exercises real Git; repository-local Git
configuration and other Git launch paths still require a separate audit.

A positive-control test showed a repository clean filter can execute during a
working-tree Git diff despite `--no-ext-diff` and `--no-textconv`. Until the
broker can isolate that operation, `run_git` refuses working-tree diff while
retaining staged diff. Code review propagates the refusal instead of reporting
a clean result. Restore unstaged diff only with a verified native boundary;
other Git operations and filter-triggering cases remain under review.

A positive-control test also found the commit preview and Build artifact diff
helper could launch repository clean filters. Commit proposals and changed-tree
artifact diffs are now unavailable pending native containment; the Build API
returns `git_diff_native_sandbox_required` rather than an empty success.

Build artifact diffs now support staged-only changes through the protected
index-to-HEAD Git diff. A real Git control confirms a configured clean filter
is not started in this case, and staged `.raiker` content is excluded. Mixed
or unstaged changes remain unavailable; truncated output is refused rather than
used as a complete review. Commit proposals remain blocked.

Positive-control Git tests showed repository smudge filters run during task
worktree checkout and branch creation from a different base. Both operations
are now refused pending a sandboxed checkout; creating a branch at HEAD remains
available and was tested in the same fixture. This does not establish safety
of every Git operation or platform.

The native runner policy parser rejects non-absolute workspace paths, lexical
parent traversal, malformed protected-path lists, invalid network/PTY types and
out-of-range limits. Windows unit tests and Linux/macOS cross-target checks cover
the contract; they are not OS enforcement evidence. Symlink and junction races,
real platform filesystem isolation, complete seccomp coverage and resource enforcement remain
release blockers.

The broker requires every mandatory probe observation, including protected-data
reads and descendant termination, to be enforced. The old descendant marker
check did not observe process termination. Windows now retains a live descendant
handle, verifies Job Object membership, and observes termination after job
closure; a real disposable-workspace probe measured it as enforced. Linux now
matches the namespace PID to a unique live descendant, pins it with a pidfd,
and measures exit after Bubblewrap cancellation. The Linux test passed on WSL2;
macOS remains indeterminate and hosted Linux CI evidence is pending. Native
execution remains unavailable until disposable workspaces protect the original
project. Windows job assignment
is checked before a suspended process resumes;
the failure path terminates the process, including in the probe. Unix launch
also fails if resource-limit or Linux parent-death setup fails. These changes do
not replace real OS enforcement or process-cleanup tests.

Native probe scratch directories and write targets now use per-run names. Probe
writes use exclusive creation, cleanup checks the probe nonce before removing
write targets, and scratch cleanup removes only an empty directory rather than
recursively deleting its contents. This reduces accidental collisions with user
data; names and cleanup remain path-based and do not protect against concurrent
replacement by an adversary. Handle-based ownership and cleanup remain open.

Before launching, the runner also checks that the workspace exists and is not a
link or Windows reparse point, that the working directory resolves inside it,
and that existing components of the working directory and protected paths are
not links or reparse points. Missing protected paths remain allowed. These are
preflight checks, not a race-free filesystem boundary: directory handles are
not pinned, ancestors and paths can change after validation, and hard links are
not addressed. The Unix symlink test needs execution on a Unix runner; compiling
it for Linux and macOS is not enforcement evidence.

## Docker and Podman removal

Removed: the persistent container command backend and container tool bridge;
the `container` profile kind and `container_default`; `container_execution_cap`;
the Docker plugin runtime and image pull capabilities; the Docker model
conversion runner; container readiness computation; `containers/**`;
`scripts/scan_containers.py`, `scripts/scan_images.py` and the image-scan CI
job; Settings' container configuration; and the obsolete container threat
models. `raiker/execution/commands/egress_proxy.py` is retained: it is an
authenticated CONNECT proxy that resolves and checks destinations itself, the
intended basis for OS-enforced native egress, and is not yet wired.

Upgrade behaviour. A stored `container` row stays in the database with its
command history. It is listed as *retired*, is never available, cannot be
selected, and refuses with `container_environment_retired`. A tool the owner
assigned to an enabled retired row is refused rather than placed elsewhere.
`native_sandbox` is always selectable, so removing a retired default always has
a destination; a selection of the former `local_native` reads as the native
sandbox, which is stricter. Nothing is converted into host execution.

`raiker/runtime/command_policy.py` still names `docker` and `podman`, as
binaries an agent command may not invoke; that is a denial, not a dependency.

## Cross-platform evidence (hosted CI, PR #239, commit `09cbfd37`)

All four native runner jobs pass: `ubuntu-24.04`, `windows-2025`, `macos-15` and `macos-15-intel`.

| Platform | Measured |
| --- | --- |
| Linux | Bubblewrap + seccomp control-arm tests: filesystem, masked state, egress, descendant reaping and two denied syscalls enforced. |
| Windows | Relay, workspace write, escape write, masked read and descendant reaping enforced; the shared-`.git` adversarial ACL is refused. Egress is indeterminate on hosted runners (gateway drops the control packet) and enforced on the owner's Windows 11 host. |
| macOS (arm64 and Intel) | Seatbelt: workspace read allowed; outside read and write, `.raiker` read and `.git` write denied (direct `sandbox-exec` test); the probe measures relay, writes and masked read enforced. Egress is indeterminate because there is no gateway control on macOS, and descendant containment is indeterminate (not implemented). |

These are boundary measurements, not release evidence: native execution remains
unavailable until disposable workspaces are wired in (see `TO_BE_FIXED.md`).
At that commit the Python suite still had 189 pre-migration host-execution
failures. They were migrated as each feature came back: every Python shard
passes on the PR's final commit (`f0163aad`).

## Open designs: macOS containment and a WSL2 backend (2026-11-01)

**macOS process tree and memory.** XNU has no PID namespace, `RLIMIT_AS` is
not enforced and `RLIMIT_NPROC` counts the whole user, so a command can leave
a detached descendant running and its memory is unbounded. Polling the
runner's children cannot close this: a double fork followed by `setsid`
reparents the grandchild to `launchd` between two polls. The one mechanism
that holds is the one the Windows boundary already uses: run commands as a
dedicated, unprivileged account created once with the owner's approval
(`sysadminctl`, an administrator prompt), so every process the run starts —
detached or not — is that account's, and stopping the run is killing all of
that account's processes. Memory is then bounded by polling the account's
total footprint (`proc_pid_rusage` `ri_phys_footprint`) and stopping the run
past its limit. Until that exists, macOS keeps background and terminal runs
refused (`descendant_reaped` is `indeterminate`), which is fail-closed.

**WSL2 as a Windows option.** Running the Linux runner inside a WSL2
distribution (`wsl.exe -d <distro> --exec …`) would give Windows owners
Bubblewrap, seccomp, a network namespace and Linux toolchains. What it needs:
the Linux runner shipped in the Windows package; every path translated to its
`/mnt/<drive>` form (copy, working folder, policy); the Linux `PATH` rather
than the Windows one; and a probe observation that the command cannot start a
Windows program through WSL interop (`binfmt_misc` registers `/init` with the
fix-binary flag, so hiding `/mnt` and `/run/WSL` must be measured, not
assumed). Allow-listed downloads would stay off in this mode at first: a
Windows `AF_UNIX` proxy socket is not reachable from a WSL2 namespace. The
restricted-account boundary already runs Windows toolchains, so this is an
addition for Linux toolchains, not a gap in containment.

## macOS sandbox account (2026-11-01, implemented; CI evidence pending)

Built as designed above, with `sudo` in place of a privileged helper. A
helper (`SMAppService`/`SMJobBless`) must be Developer ID signed, which would
have made this wait for the Apple certificate; a `sudoers` drop-in does not.

`sudo raiker-command-runner --setup-account` (once, administrator password):

* creates the hidden role account and group `_raikersandbox` (first free id in
  400–499, shell `/usr/bin/false`, home `/var/empty`, no password);
* installs this runner root-owned at `/Library/RaikerSandbox/bin/`, with every
  ancestor root-owned, so only root can change what `sudoers` names;
* creates the copy base `/Library/RaikerSandbox/copies`, owned by the owner,
  `0700`, with one ACL entry letting the account *search* it (not list it);
* writes `/etc/sudoers.d/raiker-sandbox`, checked with `visudo -c` before it
  goes live: the owner may run, as the account only, the installed runner's
  `--account-run` and `--account-stop` (which calls `kill(-1, SIGKILL)`).
  Nothing as root. (`/bin/kill -9 -1` through `sudo` exited non-zero on
  macOS 15 CI, so the runner sends the signal itself.)

A run in a copy under the base (`account::owns`): the owner side takes a
machine-wide lock the account cannot open, kills anything the account still
has (a crashed run), grants the account that one copy (inheritable ACL entries;
the owner gets an inheritable entry too, so what the account creates can be
reviewed, applied and deleted), writes a handoff file into the copy, and
starts `sudo -n -u _raikersandbox <installed runner> --account-run <handoff>`.
The account side checks its identity, reads and deletes the handoff, starts
`sandbox-exec` with the same profile as before, and supervises: it sums
`ri_phys_footprint` over the account's processes every 50 ms and kills all of
them (`kill(-1)`) past `max_memory_bytes`, at the deadline, or when the owner
side is gone. When the run ends the owner side runs `--account-stop` as the account
— every descendant, detached or not — checks none survived, and removes the
copy's grant. `RLIMIT_NPROC` is per user, which is exactly this run.

`setup` refuses without root; `--reset-account` removes the `sudoers` rule
first, then the account and installed runner, and leaves copies (they can hold
unreviewed work). After a Raiker update, `--account-status` reports
`runner_current: false` and the boundary is unavailable until setup is run
again — the price of `sudoers` naming a root-owned binary.

The probe measures the account boundary when it is configured (`boundary:
macos_account`), including `descendant_reaped` from a real `setsid` grandchild;
`--boundary seatbelt` still measures plain Seatbelt. `tests/macos_account.rs`
covers identity, copy isolation, grant removal, a double-forked `setsid`
descendant and the memory limit (with a control arm under a larger limit). CI's
macOS jobs run the setup and require these tests, so the release gate's macOS
check now covers them.

Not yet: background runs and terminals on macOS (the account serves one run at
a time; a small pool of accounts would let runs overlap); Seatbelt's downloads
rule is still unmeasured.

## WSL2 backend (2026-11-01, runner side implemented; unmeasured)

Simplified from the design above: Raiker uses **its own** distribution,
`RaikerSandbox`, never the owner's, and turns the two risky parts off by
configuration (`/etc/wsl.conf`):

* `[interop] enabled=false` (and `appendWindowsPath=false`): WSL registers no
  `binfmt_misc` handler, so nothing in the distribution can start a Windows
  program. Hiding `/init` would not have done this: the handler is registered
  with the fix-binary flag and works inside any mount namespace.
* `[automount] enabled=false`: no `/mnt/c`. Copies live on the
  distribution's own disk (`/var/lib/raiker/copies`), Windows reaches them as
  `\\wsl.localhost\RaikerSandbox\var\lib\raiker\copies\…`, and no
  `/mnt/<drive>` conversion exists to get wrong. It is also faster than 9P.

`raiker-command-runner --setup-wsl --linux-runner <ELF> [--rootfs <tar>]`
(no elevation; distributions are per user) imports the distribution, creates
the run user `raiker`, installs the Linux runner root-owned at
`/opt/raiker/`, installs Bubblewrap if missing, writes `wsl.conf` and restarts
the distribution. `--wsl-status` and `--reset-wsl` (unregisters it, copies
included) complete the set. A policy whose workspace is a copy in the
distribution is rewritten in Linux form (`wsl_paths::translate_policy`),
written into the distribution and run with `wsl.exe -d RaikerSandbox -u raiker
--exec /opt/raiker/raiker-command-runner`, so the boundary is exactly the
Linux one CI measures. At the deadline the backstop kills only the Linux
runner holding that run's policy (its namespace dies with it).
`--probe --boundary wsl` runs the Linux probe in a scratch copy and adds
`windows_interop`: enforced only when no interop handler is enabled, nothing
is mounted under `/mnt` and no interop socket is named.

Refused rather than half-supported: downloads (Raiker's proxy socket is on
Windows, unreachable from the namespace), Windows toolchain mounts, terminals.

Not done: Python does not offer WSL as a choice yet (the copy base, Linux
argv and environment for a run); the release build does not yet ship the
Linux runner inside the Windows package; and nothing here has run on a
Windows machine — it type-checks and lints for `x86_64-pc-windows-gnu`, and
the path, policy, `wsl.conf` and interop logic is unit-tested on Linux. To
measure on a machine with WSL2: is a file Python creates through
`\\wsl.localhost` owned by `raiker` (writable by the run), does the Linux
probe report every observation enforced there, and is `windows_interop`
enforced after setup. Hosted Windows runners cannot run WSL2, so this backend
never counts toward the release gate and stays opt-in.

## MCP servers and plugin code (2026-11-01)

A local stdio MCP server and an installed plugin's entrypoint are both an
interpreter on a workspace script. `raiker/execution/commands/sandboxed_program.py`
runs either one: the folder holding the script (minus `.git` and `.raiker`,
at most 20,000 files and 256 MB) is copied into a throwaway folder under the
copy base, arguments naming a path are rewritten against it (one outside it is
refused), and the program runs through the runner with no network. Output is
bounded while it is read, as before. The interpreter is the first on the path
the sandbox can reach: never one in the project or the owner's home, and on
Windows only one on the system drive.

Two runner changes came with it. On Windows' restricted account the command
received the account's profile environment only, so the environment Raiker
built for the run — Git's `GIT_CONFIG_GLOBAL` guard, an interpreter's encoding,
an MCP server's own secret — never arrived. It now gets the account's identity
and folders (from its `ProfileList` entry, no logon needed) overlaid with the
runner's environment. Building that block from a logon token instead failed
with `ACCESS_DENIED` whenever another run held the account's hive loaded. On
Linux, `toolchain_paths` mounts an interpreter's install prefix read-only when
it lives outside `/usr`, which is where a hosted runner's Python lives.

Measured on Windows 11 (restricted account): an MCP server answered from
`C:\RaikerSandbox\mcp_…\server` and could not open a project file; a plugin
entrypoint printed `refused` for the same read; the account tests pass 6/6
three times in a row in parallel. On WSL2 Ubuntu 24.04 a copied interpreter
under a prefix outside `/usr` failed unmounted and ran mounted.

The Linux probe also changed: its egress control arm targeted a closed port on
the default gateway, and hosted CI networks drop that packet, so egress read
`indeterminate` and every sandboxed command there was refused. It now connects
to a listener on the host's own outward address for the length of the probe.

## Reviewing a copy, and the sandbox card (2026-11-01)

Each file in Build's *Sandbox changes* review opens as a unified diff against
the project (`GET /api/command-workspaces/{workspace_id}/diff?path=`). Only a
path in the copy's change set is answered; a binary side says so instead of
showing bytes, and a long diff is cut at 200 KB and says so. The Settings card
for the local sandbox now lists the seccomp observation too (Linux), with a
failed control arm shown as *Not proven*. Covered by
`tests/test_task_workspace_api.py`, `TaskWorkspaceReview.test.ts` and the
mocked Playwright test *the local sandbox card shows each measured control and
the downloads allow-list*.

## Project setup with project-local dependencies (2026-11-01)

A task copy is set up with the project's own tools, and what they install
stays in the copy:

* **Commands.** `python -m` may run `venv`, `pip`, `pytest` or `unittest`
  (any other module is refused); `cargo` may `build`, `check`, `test`,
  `fetch`, `run`, `fmt`, `clippy`, `doc`, `bench`, `metadata`, `tree` or
  `clean`, never `install`, a `+toolchain` override, `--config` or `-Z`.
  `npm install` / `npm ci` were already allowed. A script in the project
  already runs any code the project holds, so these reach the project's own
  tools rather than code it does not contain. Python's options are now read
  the way Python reads them, which also closed `-cCODE` and `-Ic CODE`, two
  spellings of `-c` the old whole-argument comparison let through.
* **Where things land.** `.venv`, `venv`, `node_modules`, `__pycache__`, test
  and linter caches, Cargo's `target` (beside a `Cargo.toml`) and, at the
  copy's top, the package managers' caches under the sandbox's HOME
  (`.cache`, `.npm`, `.local`, `.cargo`) are the task's environment. They are
  not copied in from the project and never appear in the change set the owner
  reviews, so setting a copy up promotes nothing.
* **Finding the program.** A command naming `.venv/bin/python` runs the
  copy's own interpreter (looked up from the command's folder in the copy, not
  from Raiker's), and a virtualenv's `bin/python` link to the system
  interpreter is accepted because the check is on where the program sits, not
  what it links to. A bare name resolves to the first program on the path the
  sandbox can reach, never the project's or the owner's home's.

Measured on Windows 11 (restricted account) and WSL2 Ubuntu 24.04:
`python -m venv .venv` then `.venv/…/python -m pip --version` succeed in the
copy, the project gains no `.venv`, and the copy's change set is empty
(`tests/test_project_setup_policy.py`). Installing packages needs downloads on
(`pypi.org`, `registry.npmjs.org`, `crates.io` are on the default list).

## Resource limits, measured (2026-11-01)

**Linux.** Where the owner's systemd user manager runs (its bus is at
`/run/user/<uid>/bus`), the runner starts `bwrap` through
`systemd-run --user --scope` with `MemoryMax` (the run's memory limit),
`MemorySwapMax=0` and `TasksMax`, so one cgroup bounds the whole run rather
than each process. `systemd-run --scope` execs `bwrap` in place, so the pid,
process group and seccomp descriptor are unchanged; the bus variables are
unset before the command starts. Elsewhere the per-process rlimits and the
in-namespace process limit are the bounds, and the probe's
`resource_limits` says which (`cgroup_scope` or `rlimit`). Measured in WSL2:
three children holding 160 MB each all finish under a 2 GB limit and do not
all finish under 320 MB (`linux_probe.rs`).

**Windows.** The restricted account's Job Object limits are now measured
with control arms (`windows_account.rs`): a 768 MB allocation succeeds under a
2 GB limit and fails with `OutOfMemoryException` under 384 MB; a child process
starts under a limit of 8 and not under 1.

## Process limit and restart recovery on Linux (2026-11-01)

`max_processes` was applied as `RLIMIT_NPROC` before `bwrap` started. Linux
counts that limit against every task of the real user on the kernel, across
PID namespaces (WSL's distributions share one kernel), so on a busy session
`bwrap` itself could not fork: `Creating new namespace failed: Resource
temporarily unavailable`. Measured in WSL2 with nine tasks of the user
visible: allowances of 8, 16 and 32 failed, 64 ran. The runner now sets the
limit from inside the run's user namespace (`--nproc-limit`, an exec shim the
runner provides read-only at `/run/raiker/runner`), where the kernel counts
only that namespace's tasks. Allowance 8 now runs beside other processes, and
a run allowed 6 cannot start 20 children (`linux_probe.rs`).

A background run on Linux is started under the detached supervisor, which runs
the runner, so the boundary is unchanged and a restart of Raiker reattaches to
the run instead of recording it `lost` (`test_command_supervisor_reattach.py`,
on real Bubblewrap). A run with downloads on stays in-process: its proxy lives
in Raiker.

## Allow-listed downloads (2026-11-01)

Off by default; the owner turns it on and edits the host list in Settings ›
Runtime › *Command downloads* (`GET/PUT /api/command-egress`, audited as
`command_egress_changed`). Defaults are the registries pip, npm, cargo and Git
fetch from. Each run then gets its own proxy (`egress_runtime.EgressRun`) with a
run-scoped HMAC credential, delivered through `HTTP(S)_PROXY`/`ALL_PROXY`, and
the boundary makes that proxy the only route:

| Platform | Mechanism | Measured |
| --- | --- | --- |
| Linux | `--unshare-net` kept; the runner is bind-mounted and runs as `--egress-bridge` inside the namespace, forwarding `127.0.0.1:3128` to the proxy's Unix socket; public CA stores (`/etc/ssl/certs`, `/etc/pki/...`) mounted read-only | WSL2 Ubuntu 24.04: `curl https://pypi.org/...` 200 through the proxy; `example.com` refused 403; `--noproxy '*'` cannot resolve a name; `tests/linux_probe.rs` asserts the bridge reaches the socket and `1.1.1.1:443` is unreachable |
| macOS | Seatbelt keeps `(deny network*)` and adds only `(allow network-outbound (remote ip "localhost:<port>"))` | Profile unit test only; needs a macOS run |
| Windows | Restricted account: its firewall rule blocks every off-machine destination; the runner adds the proxy variables to the account's own environment block (`LogonUserW` + `CreateEnvironmentBlock`). AppContainer refuses, so an AppContainer-only host keeps the run offline | Windows 11: pypi.org 200; example.com 403; `--noproxy '*'` cannot connect; 9 of 9 repeated runs correct |

The proxy checks the host and port against the list **before** any DNS lookup,
so a sandboxed command cannot use name resolution as a covert channel (found
in review; the previous order resolved first). It refuses any DNS answer that
contains a non-public address, connects to the exact address it checked, and
accepts only `CONNECT` to port 443, so a redirect to another host is a new,
separately checked tunnel. Refused destinations are appended to the run's
output so the agent can name the host to ask for.

## Windows MXC evaluation (2026-10-30)

Microsoft MXC is public (`github.com/microsoft/mxc`). It is a cross-platform
execution-container project whose default Windows backend is itself
AppContainer-based, with an experimental Hyper-V Windows Sandbox backend. Its
README states that no MXC profile should currently be treated as a security
boundary, and no source found ties Codex's Windows sandbox to MXC: OpenAI
describes its own sandbox as a custom design. Decision: do not adopt MXC; keep
and harden Raiker's AppContainer + Job Object runner. Revisit when MXC claims a
security boundary. Licence and supported Windows versions were not assessed,
because the security disclaimer already rules it out.

## Git filter programs (2026-10-31)

The interim Git refusals (working-tree diff, commit preview/commit, branch from
a base, task worktree) are replaced by neutralising every configured filter
driver on each local Git invocation (`raiker/tools/git.py:no_filter_drivers`).
Rationale: a repository's content can only *name* a filter; the program comes
from Git configuration. With agent code confined to disposable copies that
contain no `.git`, nothing agent-controlled can define one, and the overrides
stop even owner-configured drivers from running during Raiker's own Git calls.
Verified with positive-control tests for clean and smudge drivers.

## Windows toolchain compatibility (measured 2026-10-31)

Real runs through `CommandService` on Windows 11, each in a disposable copy:

| Command | Result |
| --- | --- |
| `git --version` | Succeeded inside the AppContainer; project unchanged |
| `git init` | Wrote files in the copy (renames work after granting DELETE), then failed creating leading directories |
| Git-for-Windows `echo` / `sort` / `cat` (MSYS) | `0xC0000142` — MSYS runtime cannot initialise in an AppContainer |
| `node script.js` | `EPERM: lstat 'C:\'` while resolving the script's real path |
| virtualenv `python` | `failed to locate pyvenv.cfg: Access is denied` |
| Escape write to the user profile, home-directory read | Refused |

The boundary holds; the toolchains do not run. The cause is structural: tools
stat every ancestor from the drive root, and a drive root grants AppContainers
nothing. Granting it needs administrator rights and a permanent host ACL
change, which this design rules out. Windows build execution therefore needs
either a restricted-token boundary under a dedicated low-privilege local
account (granted only the task copy) or the WSL2 Bubblewrap backend. This is a
release blocker in `TO_BE_FIXED.md`.

