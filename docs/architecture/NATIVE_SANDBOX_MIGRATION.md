# Native sandbox migration: initial findings

Status: **incomplete and not release-ready**. This is an initial inventory, not
the required comprehensive execution-boundary audit. Existing behavior has not
been comprehensively migrated. The command service now requires the native
backend, but other execution paths still exist and Docker and Podman remain.

Baseline: `4d7c14dc9161160e10c417a2f3b5b824c1a646fd` on `origin/main`.

## Known execution paths and blockers

| Path | Current role and evidence | Required work and verification |
| --- | --- | --- |
| `raiker/execution/commands/service.py`, `code_placement.py` | The service routes local-profile commands to the native backend and refuses other non-native profiles. The native backend refuses unavailable boundaries and unsupported background/interactive modes. The earlier router placement logic still describes host execution and needs consolidation. | Verify the native boundary itself, remove contradictory routing and profiles, and test stale approvals and all entry points. `tests/test_native_command_required.py` covers service placement and unavailable-probe refusal, not OS enforcement. |
| `raiker/execution/commands/backends/container.py`, `profiles.py` | Persistent container backend and Docker/Podman profile detection are active. | Replace responsibilities before removal; retain old configuration as inert migration data. Verify upgrades and no reachable runtime invocation. |
| `raiker/runtime/executors/containers.py`, `tier4_plugins.py` | Docker and plugin execution paths remain in source, but their default shared process launcher now refuses execution pending native broker integration. | Migrate or refuse all plugin/container execution through the broker; verify actual boundary and failure behavior. |
| `raiker/runtime/executors/mcp.py`, `sandbox.py`, `raiker/hooks/handlers/command.py` | Local MCP stdio and the shared legacy `run_command` launcher now refuse execution. Other subprocess sites and their callers remain to be audited. | Trace all callers, distinguish trusted infrastructure from agent-controlled execution, and enforce the broker where required. Test malicious child processes. |
| `native/raiker-command-runner/src/boundary_unix.rs` | Bubblewrap and Seatbelt implementations exist; the Seatbelt profile explicitly allows broad file reads. No seccomp implementation was found in the native runner source search. | Narrow reads, add and verify seccomp and enforceable resource controls; test on actual supported Linux and macOS systems. |
| `native/raiker-command-runner/src/boundary_windows.rs` | Existing Windows boundary requires detailed security and lifecycle review. | Verify AppContainer, ACL cleanup, job limits, process descendants and network denial on supported Windows versions with adversarial control-arm tests. |
| `raiker/models/conversion.py` | Model conversion contains Docker-related process management. | Determine trusted infrastructure responsibilities and replace the dependency without exposing untrusted code. |
| `raiker/tools/git.py`, `raiker/control/build_worktrees.py`, `raiker/github/local_methods.py` | Git and worktree operations spawn processes outside the command backend. | Trace configuration, hooks, external helpers and agent control; confine untrusted execution and protect original projects. |
| `raiker/app/`, `desktop/src/`, `scripts/` | Launch, update, packaging, setup and test infrastructure spawn processes. | Classify each operation and preserve separately authorized trusted infrastructure. Audit installers and package the verified runner. |
| `.github/workflows/ci.yml`, `scripts/scan_containers.py`, `scripts/scan_images.py` | Existing CI includes container-specific checks. | Replace only after the corresponding product dependencies are removed; add actual cross-platform enforcement and release-evidence gates. |

Searches also identified process creation in model runtimes, storage probes,
notifications and desktop tests. Their individual trust boundaries, indirect
library calls, UI/API entry points, scheduling, delegation and filesystem/network
operations have not yet been fully traced. This list must not be treated as an
exhaustive inventory or security assessment.

## Ordered checklist

- [ ] Complete the repository-wide inventory and trace each agent entry point to the OS process.
- [ ] Define and implement one fail-closed broker, disposable workspaces and reviewed promotion.
- [ ] Verify Windows AppContainer, macOS Seatbelt and Linux Bubblewrap plus real seccomp enforcement.
- [ ] Implement and measure resource, network, lifecycle and cleanup controls; report only measured capabilities.
- [ ] Migrate command, plugin, MCP, scheduled and delegated execution without host fallback.
- [ ] Safely migrate obsolete profiles, then remove container code, UI, packaging and documentation.
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
