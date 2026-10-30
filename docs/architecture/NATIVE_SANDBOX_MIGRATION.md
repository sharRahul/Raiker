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
| `raiker/runtime/executors/containers.py`, `tier4_plugins.py` | **Removed:** `container_execution_cap`, `plugin_sandboxed_runtime_cap`, `plugin_sandbox_image_pull_cap` and their executors. The remaining plugin runtime uses the shared launcher, which refuses with `native_sandbox_required`. | Run plugin code through the broker with bidirectional stdio once disposable workspaces exist. |
| `raiker/runtime/executors/mcp.py`, `sandbox.py`, `raiker/hooks/handlers/command.py` | Local MCP stdio and the shared legacy `run_command` launcher now refuse execution. Other subprocess sites and their callers remain to be audited. | Trace all callers, distinguish trusted infrastructure from agent-controlled execution, and enforce the broker where required. Test malicious child processes. |
| `native/raiker-command-runner/src/boundary_unix.rs` | Bubblewrap installs seccomp; two denied syscalls were measured with control arms in WSL2. Seatbelt uses a narrower runtime and workspace read allowlist, unverified on macOS. | Validate Seatbelt enforcement and toolchain access, additional seccomp restrictions, and resource controls on supported systems. |
| `native/raiker-command-runner/src/boundary_windows.rs` | Existing Windows boundary requires detailed security and lifecycle review. | Verify AppContainer, ACL cleanup, job limits, process descendants and network denial on supported Windows versions with adversarial control-arm tests. |
| `raiker/models/conversion.py` | **Docker runner removed.** Conversion refuses with `model_conversion_native_toolchain_required`; preview, provenance and cleanup remain. | Package llama.cpp's converter and quantizer and run them in the native sandbox. |
| `raiker/tools/git.py`, `raiker/control/build_worktrees.py`, `raiker/github/local_methods.py` | Git and worktree operations spawn processes outside the command backend. | Trace configuration, hooks, external helpers and agent control; confine untrusted execution and protect original projects. |
| `raiker/app/`, `desktop/src/`, `scripts/` | Launch, update, packaging, setup and test infrastructure spawn processes. | Classify each operation and preserve separately authorized trusted infrastructure. Audit installers and package the verified runner. |
| `.github/workflows/ci.yml`, `scripts/scan_containers.py`, `scripts/scan_images.py`, `containers/**` | **Removed** with the product dependency: the container definition check, the grype image scan, its exception file and both Containerfiles. The native runner job runs on `ubuntu-24.04`, `windows-2025`, `macos-15` and `macos-15-intel`. | Add release-evidence gates that fail packaging when a platform's enforcement tests have not passed. |

Searches also identified process creation in model runtimes, storage probes,
notifications and desktop tests. Their individual trust boundaries, indirect
library calls, UI/API entry points, scheduling, delegation and filesystem/network
operations have not yet been fully traced. This list must not be treated as an
exhaustive inventory or security assessment.

## Ordered checklist

- [ ] Complete the repository-wide inventory and trace each agent entry point to the OS process.
- [ ] Define and implement one fail-closed broker, disposable workspaces and reviewed promotion.
  `raiker/execution/workspaces.py` now provides the workspace half: a private
  copy without `.git`, `.raiker`, links or special files; a content manifest;
  a diff that rejects links and protected names the task creates; promotion
  that refuses on owner changes made after the snapshot, writes nothing a
  path check refuses, never writes through a link, and restores every original
  on failure; quotas; and crash cleanup. `tests/test_task_workspaces.py`
  exercises real junctions/symlinks and hard links. It is **not yet wired** into
  the command service, so native execution remains unavailable.
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

Workspace command hooks are blocked with `native_sandbox_required` until the
broker supports sandboxed stdio. An enforcing hook that cannot run continues to
require an owner decision, as verified by `tests/test_hook_fail_closed.py`.
Restoring hook execution requires bounded stdio and lifecycle containment; this
is a release blocker and the previous host-execution integration tests remain
unmet. HTTP and built-in hooks retain their separate behavior.

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

## Cross-platform evidence (hosted CI, PR #239)

| Platform | Result | Evidence |
| --- | --- | --- |
| Linux (`ubuntu-24.04`) | Native runner tests pass, including real Bubblewrap and seccomp control-arm tests | CI job *Native runner (ubuntu-24.04)* |
| Windows (`windows-2025`) | Adversarial ACL test passes after the fail-closed change. The probe's descendant could not open `\\.\NUL` in the AppContainer; the probe now uses private pipes. Rerun pending. | CI job *Native runner (windows-2025)* |
| macOS (`macos-15`, `macos-15-intel`) | Failing: `RLIMIT_AS` rejected (EINVAL), then `cat` denied `file-read-data /`. Both addressed; rerun pending | CI jobs *Native runner (macos-15*)* and the Seatbelt denial log step |

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

