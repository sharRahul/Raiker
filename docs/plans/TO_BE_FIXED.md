## Release blocker: native sandbox migration incomplete

Real Windows adversarial ACL testing found that an AppContainer can write into
`.git` when that directory grants `ALL APPLICATION PACKAGES` modify access,
despite an explicit deny for the workspace capability SID. An experimental
package-SID deny also failed this test and was removed. The broker remains
unavailable: disposable workspaces and an ACL strategy that passes this real
test are required before Windows execution can be enabled. The failing test is
`appcontainer_denies_protected_and_outside_files_with_a_readable_workspace_control`.
An experimental less-privileged AppContainer (LPAC) passed that filesystem
test but could not initialize Winsock or start the probe descendant on this
machine. The experiment was removed to preserve the existing lifecycle probe.
LPAC needs narrowly justified capabilities and real tests for useful process
creation and network denial before it can replace the current boundary.

The desktop packaging run for PR head `07f345f0` on 2026-10-30 could not
start its macOS job because GitHub's `macos-14` runner was in a scheduled
brownout. The local workflow and release target definitions now select
`macos-15` for Apple Silicon; their configuration tests pass, but the updated
job has not yet run on GitHub. The prior PR CI also has failing Python shards,
Windows lifecycle and Build fault jobs; these are not resolved by the runner
label change.

Native command execution remains unavailable. A Windows probe now retains a
live descendant process handle, checks its Job Object membership and observes
termination after job closure; a real disposable-workspace probe produced an
enforced verdict. This does not protect the original project, so Windows still
refuses availability until disposable workspaces exist. A Linux Bubblewrap
probe in Ubuntu WSL2 now matches a live namespace descendant to its host
process, pins it with a pidfd and observes its exit after supervisor cancellation.
The WSL2 integration test passes; hosted Linux CI and macOS process lifecycle
evidence remain open. Restore execution only after all mandatory observations
and disposable-workspace protections pass. Linux WSL2 tests now verify memory,
CPU, process count and wall deadlines against outside controls; Windows verifies
Job Object CPU-time termination. Linux process-count limits remain per-user and
can be affected by unrelated processes; memory and CPU limits are per process,
not task-wide aggregate quotas. macOS limits, hosted CI and aggregate quotas
remain unverified.

The Unix runner now makes deadline decisions in its child-owner wait loop
instead of leaving a detached PID-targeting watchdog. Linux WSL integration
tests exercise both deadline termination and prompt early completion; real
macOS lifecycle and cancellation evidence is still required.

The Linux boundary no longer mounts the host `/etc`, `/opt` or `/nix` trees.
A WSL Bubblewrap test verifies that `/etc/hostname` is hidden while an outside
control can read it. Toolchains outside `/usr` need a future governed mount;
the remaining broad `/usr` read access and other platform filesystem policies
still require threat-specific review. Runner policies reject a filesystem or
drive root as the workspace, but non-root original projects still require a
disposable workspace before execution may be enabled.

On macOS the Seatbelt executable is resolved only at the system path. Linux
Bubblewrap resolution still searches `PATH`, so an attacker able to influence
that environment or replace its executable could supply a fake boundary.
Require a trusted, non-agent-writable Bubblewrap artifact and verify its
identity before enabling Linux execution; do not treat a `PATH` lookup as proof.

Seatbelt profile construction now refuses non-UTF-8 paths and paths containing
quotes, backslashes or control characters, preventing those path values from
injecting policy expressions. The rejection has Rust unit coverage on Linux;
the revised profile still requires genuine macOS enforcement tests.

The existing credential snapshot now rejects overlapping staging/source roots,
case-insensitively excludes protected directories, rejects Windows reparse
points and compares a file's opened identity against its inspected identity.
Windows hard-link, junction and file-replacement tests pass. This snapshot is
now checked for file modification during copying, and cleanup refuses an
unowned or replaced staging root. Source copying and artifact manifests enforce
entry and byte limits; manifests reject roots that are symlinks or Windows
reparse points. These checks are covered by `tests/test_credential_overlay.py`.
Cleanup permission retries reject known links, reparse points and parent
traversal and do not change permissions on the staging root's parent. These
checks are still subject to concurrent path replacement.
The preliminary conflict check compares affected paths and deleted-directory
descendants against the original snapshot, including case-folded collisions.
It is advisory only: it does not lock paths, authorize writes, promote files,
or provide rollback.
They are not yet a general task workspace:
directory components are not held by pinned
handles, promotion and rollback are missing, and adversarial directory races
remain. Do not remove the native execution gate on this basis.

The Python driver now probes a copied runner in a temporary directory, revokes
its Windows grant and refuses project execution until disposable task workspaces
exist. A real Windows check confirmed the original project, protected directory
and runner-installation ACLs were unchanged by the probe. This does not yet
prove crash recovery or safely revoke every historic grant already made. A real
Windows test also verifies that a workspace capability ACE can be removed by
the existing revocation function; protected child ACL restoration is still open.

The requested Docker-free execution migration has not been implemented or
verified. The command service requires its native backend, and
`raiker/execution/code_placement.py` separates host-risk classification from
sandbox placement. The execution inventory remains incomplete; container,
plugin and MCP execution paths remain separate. Their legacy default launchers
now refuse execution until migrated; other subprocess paths are not yet audited.
The macOS native runner now uses a system-runtime and workspace read allowlist,
but its real enforcement and toolchain compatibility remain unverified.
Linux now installs a seccomp BPF filter;
a WSL2 control-arm test observed personality and unshare blocked inside the
boundary, but the rest of the filter and ARM runtime remain unverified. Inspect
`native/raiker-command-runner/src/boundary_unix.rs`; a dependency probe alone
does not demonstrate OS enforcement. The security impact is potential access
to host files or network by code that the target design intends to isolate.
Complete the inventory, broker migration and adversarial OS-enforcement tests
before treating this architecture as release-ready. Initial findings and the
remaining checklist are in `docs/architecture/NATIVE_SANDBOX_MIGRATION.md`.

## Release blocker: sandboxed command hooks unavailable

Workspace command hooks cannot safely use the legacy host subprocess launcher.
They now refuse with `native_sandbox_required`; an enforcing hook that cannot
run requires an owner decision. This prevents unsandboxed hook code but leaves
command-hook functionality unavailable. Integrate the native broker with
bounded bidirectional stdio and process-tree cleanup, then verify legitimate
hook decisions and adversarial escape attempts on each supported platform.

## Release blocker: sandboxed working-tree diff unavailable

Repository-configured clean filters can launch code during a working-tree diff.
`run_git` refuses this form until it can be executed inside a verified native
boundary; staged diff remains available. Code review reports the refusal rather
than claiming a clean result. Restore working-tree diff with positive-control
filter tests and cross-platform enforcement evidence. The existing
`tests/test_phase_2_5_code_review_workflow.py` currently has 11 failures and 2
passes because unstaged review is unavailable. Other Git paths remain
unverified.

## Release blocker: sandboxed Git commit and artifact diff unavailable

Commit previews, staging and working-tree Build artifact diffs may invoke
repository clean filters on the host. These operations remain unavailable until
they can use a verified native boundary. Staged-only artifact diffs are
available with protected-path exclusion and truncation refusal. The Build changes API returns an explicit unavailable
reason and preserves the changed-file list; the UI must not claim an empty or
reviewed diff. Restore commit previews, approved commits and artifact diffs with
positive-control filter tests, disposable workspaces and platform enforcement
evidence. Existing commit and Build artifact functionality is affected.

## Release blocker: sandboxed Git checkout unavailable

Task worktree creation and branch creation from a specified base can execute
repository smudge filters on the host. Both now refuse until checkout can run
inside a verified native boundary. This prevents uncontained helper execution
but leaves concurrent task worktrees and cross-base branch creation unavailable.
Restore them with disposable workspaces and real cross-platform filter and
cleanup tests; existing worktree functionality tests remain unmet.

## Goal

Make Raiker a secure AI product that combines **four** things: a polished AI
assistant, a governed **personal autonomous agent**, **a capable coding/build agent**, and an
extensible governed agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a coding agent, Raiker
should read a repository, make the change, run the tests, read the failure and
iterate to green, in one governed session. As a platform, Raiker should provide
the governed runtime foundation for models, tools, plugins, interfaces, memory,
approvals, audit events, checkpoints, and integrations.

Governance, observability, policy awareness, control and security are **inherent
properties** of that runtime, not optional layers added around the agent.

> **Which open work blocks which pillar is in [`PILLAR_MAP.md`](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
> and how an action reaches an executor at all is in
> [`GOVERNANCE_ENTRY_PATHS.md`](PERSONAL_AUTONOMOUS_AGENT_SPEC.md).** This preamble is
> repeated in several plans because each is read on its own; the pillar map is
> the one place that says what the whole set adds up to.

Raiker must support user-owned model choice across LLM backends — local models
such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM;
private-network providers; and hosted API providers such as Anthropic, OpenAI,
Gemini, and OpenRouter. No model, interface, plugin, or capability should
bypass governance. Every action must remain policy-aware, observable,
auditable, approval-driven where required, human-governed, user-controlled, and
fail-closed by design.

## Security posture (read before adding any restriction)

Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
Security is not restricting the user; it is a frictionless system that lets the
owner operate securely without having their access taken away. Do **not** put a
hard block in front of the owner's legitimate choices (e.g. connecting a remote
MCP server) by default — **allow, monitor, surface anomalies as findings +
notifications, and give the owner an instant stop plus an automatic revocable
pause for the irreversible/high-severity cases.** Reserve hard prevention for a
last resort and justify it against this posture. Full statement:
`docs/architecture/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

# To be fixed

## Windows high-DPI window restoration

On a Windows display at 150% scaling, the Electron shell geometry test observed
a requested 900×640 window saved as 901×641 and restored as 904×643. The shell
test fixture uses a fixed scale of 1 to make its exact-size CI assertions
deterministic, but this does not verify high-DPI restoration. Investigate the
Electron/Windows bounds conversion and add a separate high-DPI regression test
before claiming exact window-size restoration at non-default scale factors.

## Local voice delivery — release blockers

The local-only privacy changes do not complete the requested voice experience.
Before beta, provide a verified managed speech engine and model installer with
process lifecycle and recovery; validate Design dictation end to end and make
the composer controls consistent; validate cancellation, permissions and recording limits
end to end; and test real recognition plus packaged Windows, macOS and Linux
releases. Existing local servers are configured manually. A successful mock
transcription does not demonstrate model accuracy or packaging support.
The speech routes now also use the existing local-request guard, but their
full remote and proxy threat boundary still needs end-to-end validation.
Record installation artifact provenance and checksums before running
downloaded code. No cross-platform release validation has been performed here.

On Windows, an optional real-engine test passed for the English JFK fixture
using the CPU-only whisper.cpp b5454 binary and multilingual tiny model after
checking their published SHA-256 hashes. The 11-second fixture took about 0.44
seconds through Raiker's transcription function on the test machine. Hindi,
microphone capture, managed installation and packaged applications remain
unverified; this single measurement is not a performance guarantee.
The optional `tests/test_speech_real_engine.py` takes a loopback endpoint in
`RAIKER_SPEECH_TEST_ENDPOINT` and, per language, a WAV path and expected text in
`RAIKER_SPEECH_TEST_EN_WAV` / `RAIKER_SPEECH_TEST_EN_TEXT` or the corresponding
`HI` variables. It skips languages without those inputs. The tested sources
were the upstream whisper.cpp b5454 Windows x64 archive, the pinned multilingual
tiny model from ggerganov/whisper.cpp, and the upstream JFK WAV sample.

## Reading order

1. **Open-defect index** — the table below is the current source of truth for status.
2. **Open defect records** — BUG-194, BUG-248, BUG-287, BUG-339, BUG-348, BUG-351, BUG-352, BUG-354, BUG-355, BUG-356 and BUG-359, in numeric order.
3. **Verification follow-up** — newly observed failures that still need triage.
4. **Reference baseline and decisions** — verified behavior and historical direction; these sections do not add open defects.

Open defects originally found while executing
[the live manual test plan](TESTING.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Every deferred item found by the FIXED-01 through FIXED-48
audit is an explicit BUG with a required user-interface outcome, so closing
backend work cannot leave an invisible or misleading product surface.

**Closed entries live in [`FIXED_ITEMS.md`](FIXED_ITEMS.md).** They are still
evidence — what was observed, the root cause, and the user-interface outcome that
had to be true before it could be called closed — but they are no longer mixed in
with the open work, so this document answers one question: what is left.

[`GAP_BUILD_CHAT.md`](BUILD_WORKSPACE_SPEC.md) — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: `screenshots/not-working/` (defects),
`screenshots/working/` (verified behaviour).

**Only unresolved BUG entries are indexed below.** Closed bugs and completed memory/governance reviews are recorded in [`FIXED_ITEMS.md`](FIXED_ITEMS.md), with historical rationale in Git history. The separate [Build/Chat capability gap ledger](BUILD_WORKSPACE_SPEC.md) is not a BUG list.

**Historical ID collision:** `BUG-280` was reused for two unrelated findings. The closed Observability empty-state defect is [FIXED-391](FIXED_ITEMS.md#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line); the weather/provider live-evidence `BUG-280` closed in two halves, the clock as [FIXED-539](FIXED_ITEMS.md#fixed-539--a-real-turn-now-answers-from-raikers-clock-and-the-weather-half-still-cannot-be-measured-here) and the weather as [FIXED-926](FIXED_ITEMS.md#fixed-926--a-real-model-read-real-weather-from-open-meteo-was-bug-280).

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — rechecked 2026-10-19: Docker Desktop and Ollama are reachable on this host, but the mandatory live bypass/revocation/credential proof and production signing anchor remain |
| [BUG-248](#bug-248--twenty-seven-live-specs-still-sign-in-inside-a-test-body) | Low | Live test harness | Open remainder — reduced again 2026-09-29 by four (`composer-parity-and-turn-honesty`, `fts5-mem03-bug194`, `mem04-bug194-observations`, `bug-37-39-40-41`), each re-run live and brought up to the product; converting them found [FIXED-632](FIXED_ITEMS.md#fixed-632--an-approval-card-covered-settings-save-changes) and [FIXED-633](FIXED_ITEMS.md#fixed-633--choosing-the-default-density-closed-the-panel-it-was-chosen-in). Ten sign in on their own: three must, and seven provider scenarios can now be converted one at a time with reachable providers |
| [BUG-287](#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider) | Medium | Design / image runtime / live evidence | Open remainder — reduced 2026-10-18: real OpenAI generation, edit, four-result variation, lineage, permission-off refusal and empty-allowlist refusal passed; a source-image provider refusal and a live research-reference **Sent with** check remain |
| [BUG-339](#bug-339--the-issue-to-pull-request-routine-has-a-template-and-no-runner) | Low | Tasks / routines | Open remainder — reduced 2026-10-18 ([FIXED-950](FIXED_ITEMS.md#fixed-950--the-issue-to-pull-request-routine-can-now-be-scheduled-as-a-build-task-bug-339-reduced)): the template schedules a governed Build task from Settings → GitHub; RR-40 live evidence against a consented repository remains; 2026-10-19 the pull request receipt ([FIXED-974](FIXED_ITEMS.md#fixed-974--a-pull-request-raiker-opened-was-known-only-from-the-create-response-br-12)) and the task's repository binding ([FIXED-976](FIXED_ITEMS.md#fixed-976--a-scheduled-build-task-ran-in-whatever-repository-build-was-pointed-at-br-02)) the run will read back are in place |
| [BUG-348](#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial) | Medium | Design / composition | Open remainder — reduced 2026-10-20 ([FIXED-998](FIXED_ITEMS.md#fixed-998--a-layer-could-only-be-moved-with-the-arrow-keys-dw-02-bug-348) to [FIXED-1010](FIXED_ITEMS.md#fixed-1010--after-a-restart-the-design-agent-said-no-chat-model-was-connected)): pointer editing, imports, components, notes, vector PDF and proposal receipts ship; selecting inside a group on the canvas, brand-guide import, system-level components and presentation export remain |
| [BUG-351](#bug-351--cli-model-commands-cannot-reach-a-connected-hosted-provider) | Low | CLI / models | Open — compatibility consequence of ADR-0004, found 2026-10-20 |
| [BUG-352](#bug-352--a-custom-endpoint-saved-off-the-machine-shows-no-route-on-its-card) | Low | Models / UI | Open — found 2026-10-20 in the BUG-349 live round (MT-03) |
| [BUG-354](#bug-354--the-workspace-key-cannot-be-rotated-in-place) | Low | Storage / memory key | Open — found 2026-10-20 writing the MEM-KEY-05 runbook; the runbook gives the export/import route |
| [BUG-355](#bug-355--goals-ship-without-intake-from-chat-validator-backed-criteria-or-a-restart-scenario) | Medium | Goals / personal agent | Open remainder of PA-D01 — the first slice shipped 2026-10-20 ([FIXED-1039](FIXED_ITEMS.md#fixed-1039--an-outcome-could-live-only-in-a-chat-transcript-there-was-no-durable-goal-goal-01-pa-d01) to [FIXED-1048](FIXED_ITEMS.md#fixed-1048--a-goal-had-no-budget-across-its-steps-goal-10-pa-d01)) |
| [BUG-356](#bug-356--execution-profiles-govern-goal-steps-only-and-cover-one-data-class) | Medium | Execution profiles / models / data handling | Open remainder of PA-D02 — the first slice shipped 2026-10-20 ([FIXED-1049](FIXED_ITEMS.md#fixed-1049--there-was-nowhere-to-say-where-a-goals-work-may-run-prof-01-pa-d02) to [FIXED-1051](FIXED_ITEMS.md#fixed-1051--changing-the-boundary-would-have-applied-silently-to-work-in-flight-prof-03-pa-d02)) |
| [BUG-359](#bug-359--remote-access-is-verified-live-on-linux-only-and-has-five-known-limits) | Low | Host / remote access | Open remainder of BUG-347/BUG-358 — remote access shipped 2026-10-26 ([FIXED-1266](FIXED_ITEMS.md#fixed-1266--a-proxy-that-sent-no-forwarding-header-was-still-read-as-local-bug-347-review) to [FIXED-1273](FIXED_ITEMS.md#fixed-1273--security-settings-showed-their-defaults-as-the-accounts-state-while-loading-found-live)); live runs on Linux only, and five limits named in the record |

The open defects below retain their original reproductions and remediation contracts. Closed defect evidence is in [`FIXED_ITEMS.md`](FIXED_ITEMS.md); previously removed topic-review rationale remains in Git history.

---

## BUG-194 — The governed shell has an OS boundary, but no interactive, background or remote execution

**Severity: Low (was Medium, was High). Area: shell / sandbox / recovery.
Status: Open — reduced three times.**

**2026-08-28 verification.** Docker is installed but its daemon is unavailable
on this host, and Podman is not installed. Raiker therefore continues to refuse
container-network execution rather than claim unverified direct-DNS/direct-TCP
bypass, active-stream revocation, or copy-on-write credential-delivery proof.
The container proof and a production signing anchor remain open.

**2026-10-19 recheck.** Docker Desktop 4.88.1 answered `docker version` and
the local Ollama service answered `ollama list`; Podman is still not installed.
That removes the stopped-daemon blocker from this host, but it does not close
the defect: the repository still has no live proof that an approved container
allows only the declared egress, refuses a bypass, revokes an active stream,
or delivers credentials through the copy-on-write/delta-quarantine path. The
production signing anchor is also still absent. The product therefore remains
correct to keep `filtered_network` and credential delivery unadvertised.

**2026-08-21 update.** Foreground SSH and Daytona now enter the same
`CommandService` lifecycle through a canonical length-prefixed envelope, exact
SSH host-key pin, Daytona cost reservation and fixed remote supervisor path;
neither falls back to the host. Container egress has normalized domain/port
policy, public-address pinning, HMAC-scoped grants, revocation state and a real
CONNECT proxy. Credential work has a disposable workspace/Git snapshot,
failure-closed scanner, discard-only quarantine API and review UI. Runner trust
distinguishes publisher-verified, package-relative and developer-unverified
postures, and placeholder supervisor digests were removed.

The item remains open for unproved parts: this host had no Docker/Podman daemon
for live direct-DNS/direct-TCP bypass, active-stream revocation or credential
copy-on-write delivery/merge tests, and no production signing anchor. Windows
PTY and restart reattachment remain explicitly unsupported. Configuration
never turns any of these capabilities on.

**What changed, 2026-08-15.** A governed command now runs inside a real
operating-system boundary, and what that boundary enforces is **measured rather
than declared**. Closed as [FIXED-195](FIXED_ITEMS.md).

**What changed, 2026-08-17.** The two rows this entry called the smallest are
closed as [FIXED-229](FIXED_ITEMS.md), and they were built the way the entry said
they had to be — as components, together, with the enforcer.

The 2026-08-16 review declined to advance them on the grounds that background
execution needs "a supervisor that outlives the turn together with the
agent-facing tool that makes a background run observable; shipping either half
alone is worse than refusing." That reasoning was right and is what this round
followed. Both halves shipped in one change:

* **The enforcer.** Every background run holds a lease. A thread renews it only
  while the process it is watching is alive and this runtime is up, so a lease
  that keeps moving forward *is* the evidence of a live run and a lease that
  stops is evidence of the opposite — including on a hard kill, where no handler
  of ours runs at all. `reconcile_leases` terminates and finalises any run whose
  lease lapsed, with a receipt naming `command_background_lease_expired`. A
  foreground run holds no lease and is never swept, so a missing lease is never
  read as an expired one. A background run is also bounded by a hard two-hour
  ceiling, because a run with no deadline is a run whose lease renews forever and
  the reclaim path would never fire.
* **The observing half.** `background_run` — `list`, `poll`, `log`, `wait`,
  `kill`, `input` — owner-scoped on every action, reading the durable run row and
  the already-redacted output chunks. It starts nothing and grants nothing: a run
  it can see is one the session's command grant already authorised.

**The tool is not called `process`, and that matters.** The original entry named
it `process`. That name already routes to the `process_execution` capability —
arbitrary host process control, which the runtime classifies as critical and the
policy holds for approval. Registering an observation tool under it would have
attached a read verdict to host process control. The collision surfaced as a
hard `policy actions cannot have conflicting verdicts: process` failure rather
than a silent widening, which is the invariant working.

**PTY and raw input are closed on POSIX and stay open on Windows.** `openpty`
gives the child a controlling terminal and `background_run action=input` types
into it; the proof is that the *program* read the bytes, not that the terminal
echoed them. Windows is unchanged and the reason is unchanged: `CreatePseudoConsole`
builds its console objects in the caller's context, unreachable from an
AppContainer token, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as
incompatible with the handle-list attribute the boundary requires.
`pty_supported()` reports the platform's real answer, and input to a run without
a terminal is refused as `command_input_requires_pty` rather than written to a
pipe where the bytes would arrive and the effect would not.

**What changed, 2026-08-17 (second pass).** The two rows this entry had left as
the largest components are closed as [FIXED-238](FIXED_ITEMS.md) and
[FIXED-239](FIXED_ITEMS.md), and they were built the way the entry said they had
to be — together, because each alone is worse than neither.

* **Restart reattachment.** A background run is started inside a detached
  supervisor that is a module of the Raiker package, so it is packaged by
  construction. It holds the child in its own session, the deadline that bounds
  it, the redactor, and an append-only journal, and it is reached over an
  `AF_UNIX` socket speaking the authenticated frames the protocol codec already
  had cross-language vectors for. The socket path and the instance key live
  encrypted in `command_runs.encrypted_backend_handle`, so **reattachment is an
  authentication rather than a pid lookup** — which is precisely the objection
  this entry raised against building it on a pid file. Every case the runtime
  cannot prove — no handle, a locked vault, a socket that is gone, a socket that
  fails the key — still produces the honest `lost` receipt.
* **Persistent environment.** The container's name is a function of owner,
  session and profile rather than of the run, so a session's second command
  lands in the boundary its first one left behind. Persistence shipped with its
  reset, because an environment that accumulates state and can never be cleared
  is worse than one that never persists.

**Still observed.** Select `native_sandbox` and request network, credential, SSH
or Daytona execution and the backend fails closed with the corresponding named
reason; the native sandbox additionally still refuses background, PTY and
persistence, because its capability set comes from the host probe and none has
been measured inside an AppContainer — and per-run AppContainer profiles stay
deliberate, since the container SID is a pure function of the name. On
**Windows**, restart reattachment is refused by name
(`command_supervisor_platform_unsupported`) and a background run is still
reconciled to `lost` across a restart.

**Root cause, per item.** Each of these is a component rather than a flag, which
is why none of them was half-built:

| Remaining item | Why it is not built |
|---|---|
| ~~**Background start/poll/wait/log/kill**~~ | **Closed 2026-08-17** as [FIXED-229](FIXED_ITEMS.md#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one) on the `local_native` backend, with the lease, the reclaim path and the `background_run` tool shipped together. Not claimed for `native_sandbox`, whose capabilities come from the host probe. |
| ~~**PTY and raw input**~~ | **Closed on POSIX 2026-08-17** as [FIXED-229](FIXED_ITEMS.md#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one). Windows unchanged: `CreatePseudoConsole` builds its console objects in the caller's context; they are not reachable from an AppContainer token without an explicit capability, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. A PTY that only works outside the sandbox is not the control the row describes. |
| ~~**Restart reattachment**~~ | **Closed on POSIX 2026-08-17** as [FIXED-238](FIXED_ITEMS.md#fixed-238--a-background-run-could-not-survive-the-restart-of-the-runtime-that-started-it), with the detached supervisor, the authenticated `AF_UNIX` control channel and the encrypted restart-safe handle shipped together. Windows unchanged and refused by name: a named pipe is reachable by name from any session on the machine, so the equivalent needs its own design and its own proof rather than the same code with a different transport. |
| ~~**Persistent environment**~~ | **Closed for the container backend 2026-08-17** as [FIXED-239](FIXED_ITEMS.md#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist), together with the owner's reset and reset-and-clear-cache controls. Per-run AppContainer profiles are still created and deleted around each command, deliberately: a predictable container name is a hole, because the container SID is a pure function of the name. |
| **Filtered domain egress** | The AppContainer loopback exemption needs elevation, and a Linux proxy-only namespace is a separate netns build. Refused with a named reason on every backend rather than partially claimed. |
| **Credential delivery and delta quarantine; SSH; Daytona** | Unchanged. None is a local subscription client or external coding assistant control; all three remain storage contracts and selectable-but-refused profiles. |
| ~~**Container session supervisor**~~ | **Closed 2026-08-17** as part of [FIXED-239](FIXED_ITEMS.md#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist): the session's container is created once and reused, liveness is asked of the runtime rather than assumed, and the backend is held for the life of the service so there is somewhere to remember it. |
| **Signature verification of the runner** | The runner's SHA-256 is recorded at build time, checked before use, and carried into the receipt. That detects corruption and casual replacement; it is **not** protection against an attacker with write access to the install directory, who could replace Raiker itself. Authenticode chain verification is not implemented. |

**Required fix.** For each remaining row: Windows PTY and Windows restart
reattachment once the ConPTY/AppContainer and named-pipe-authorisation questions
are settled by a spike; an authenticated domain proxy with DNS/address checking
and active revocation; purpose-bound credential delivery plus two-pass delta
quarantine; and SSH/Daytona supervisor adapters. Prove every backend
independently and preserve the no-fallback and honest-`lost` rules.

**Required user-interface outcome.** Further met. Runtime shows the exact probed
boundary and its six measured observations, and Build shows the boundary a
command ran in plus failure navigation. Background and PTY are agent-facing
controls rather than interface ones — an agent starts and observes a background
run through `run_command`/`background_run`, and the run appears in the same
owner-visible command list, with the same receipt, as a foreground one. Each
environment card now lists the capabilities that boundary really has, built from
the backend's own `CommandFeatures` rather than from configuration, and carries
the **Reset environment** and **Reset and clear cache** controls where — and
only where — the boundary persists. **Filtered network remains absent** rather
than disabled: an absent control is the honest projection of an unbuilt
capability, where a disabled one implies it is a setting away. No row may turn
green from configuration or specification alone.

## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline. Re-verified end
to end on **2026-08-08** against hosted Anthropic (see
[the live manual test plan](TESTING.md) for the full round):

first-run bootstrap and owner sign-in; **all 14 routes and 22 hub tabs with 0
console errors**; connecting a hosted provider from the web app and pinning a
model from the live catalogue; **all ten Anthropic models answering a live turn**;
a real streamed turn with sanitised Markdown (headings, lists, GFM tables,
fenced code); conversation memory within a chat and isolation between chats;
per-chat and provider all-time cost; recent-chat list; chat search over titles
and message text; the four task types (immediate, scheduled, daily routine,
background agent) with parent nesting, priority, counters and stop; the approval
lifecycle end to end — proposal, unified diff, **Approve and execute once**, the
file on disk, and the resumed turn; the file inspector for a generated Markdown
file and for a generated PDF; **Export conversation… in HTML, Markdown and PDF**
plus **Print / Save as PDF**; markdown → PDF through `create_document`; document
and image attachments reaching the model with source citations; MCP server
create / connect / discover / **call from Chat** under the owner's decision mode,
with the result marked untrusted; Build repository connect, code-map build and
`code_map_search`; `update_plan` checklists and `spawn_subagent`; capability
step-up (reason required, Confirm disabled until supplied); the deferred domains
CCTV, finance, medical and home security offering no row at all; Observability's
seven tabs on real data; Settings' sections; theme cycling system → light → dark;
the notification centre and Mark all read; the STOP switch; and adaptive
navigation at 375 / 768 / 1024 / 1440 px with no horizontal overflow, correct
`aria-expanded`, and focus returned to the trigger.

---

## BUG-248 — Twenty-seven live specs still sign in inside a test body

**Severity: Low. Area: live test harness. Status: Open remainder — raised
2026-08-30 while closing [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in),
reduced from twenty-seven to twenty the same day
([FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite)),
to **twelve** on 2026-09-04, to eleven on 2026-09-21 and to **nine** on
2026-09-28, then recounted as **ten** on 2026-09-29 under the stricter
test-body definition below.**

**2026-10-18, later — the seven type a key, so they are owner-run.** Each of
the seven fills a provider key from `RAIKER_LIVE_*_KEY` into the Models dialog.
An agent session must not enter a real provider key, so each conversion is
re-run by the owner with those variables set, or after the specs are taught to
reuse a connection the owner made through Models.

**2026-10-18 — provider access is no longer the reason to defer the seven.**
OpenAI, OpenRouter, Anthropic and Ollama each completed a real turn from this
host while closing [FIXED-944](FIXED_ITEMS.md#fixed-944--all-four-providers-answer-the-owner-identity-question-with-the-chosen-name).
The seven provider scenarios are still converted only one at a time and re-run,
as this entry requires. The same round also found that `signInAsOwner` rejected
the current exact **Welcome** heading; [FIXED-946](FIXED_ITEMS.md#fixed-946--the-live-sign-in-helper-rejected-the-current-welcome-heading)
repairs that shared precondition without changing the inline-sign-in count.

**2026-10-19 live recheck.** In a fresh isolated workspace, the supplied
Anthropic key was entered through Models (never written to a spec or log) and
`anthropic-key-live.spec.ts` passed its real catalogue round. This is provider
access evidence only; it does not convert the remaining inline sign-ins or
close the ten-spec remainder, which still requires each scenario to be
converted and re-run with its own real provider.

**2026-09-29 — four more, and two product defects behind them.**
`composer-parity-and-turn-honesty-live`, `fts5-mem03-bug194-live`,
`mem04-bug194-observations-live` and `bug-37-39-40-41-live` sign in through
`signInAsOwner`. Each signed in on its first run and then failed on the product
having moved — Memory's recall posture now on *Recall & indexing* with the picker
on Settings → Memory engine, Observations on *Suggestions*, the terminal button
named *Show the governed terminal*, Tasks opening on its composer, message search
an explicit **Search message text**, density under a disclosure — and each was
brought up to the product rather than relaxed. Two of the failures were the
product, not the spec, and are fixed:

* the retention step passed on one run and timed out on the next because an
  approval card covered Settings' **Save changes**
  ([FIXED-632](FIXED_ITEMS.md#fixed-632--an-approval-card-covered-settings-save-changes));
* choosing *Comfortable* closed the disclosure it was chosen in
  ([FIXED-633](FIXED_ITEMS.md#fixed-633--choosing-the-default-density-closed-the-panel-it-was-chosen-in)).

`checkModelReady` now takes the first outcome it finds: an exhausted account
says so twice, as a chip and as the outcome line. That is how the round found
the provided key's credit balance exhausted part-way through, confirmed against
the provider directly. Every step of the four was run live after its edit;
`fts5`'s second test could not be re-run end to end after that point, so its
corrected search step was driven on its own against the transcript its earlier
turn had written, and passed.

**The count, recounted.** This entry counted sign-ins inside a test body.
Counting every live spec that signs in without the shared helper gives ten after
this pass: `review-first-run-honesty`, `wizard-workbench-composer` and
`workbench` must keep their own, and `add-01-container-providers`,
`add-03-machine-identity-providers`, `bug-29-34`, `bug-36-38-42-43`,
`bug-69-model-readiness`, `governed-shell-provider-matrix` and
`review-provider-matrix` each need OpenRouter, OpenAI, Gemini or Ollama. Those
providers are now reachable here except for Gemini, so these scenarios can be
converted and re-run in later one-spec passes; the rule below still says they
are not converted blind.

**2026-09-28 — two more, and the one reverted on 2026-09-04 among them.**
`review-readiness-probe-live` and `c17-b14-recall-and-inline-diff-live`, run
against the second 2026-09-28 round's workspace with a key that answers. Both
signed in through the shared helper on the first run and then failed on the
product having moved, never on the sign-in:

* `review-readiness-probe` waited for a **Hosted** tab the Models redesign
  removed. It now reaches the card through `hostedProviderCard`, and asserts
  what its title claims — that **Test** settles on an outcome for the pinned
  model — through `checkModelReady` rather than only logging the card's text.
* C17's memory import is on *Recall & indexing* now, and a record shows on
  *Memories*. B14 met the same Build drift `bug-242-build-restore-mem-09-live`
  records — the project behind `+`, a model chosen for the turn, and **Run**
  rather than **Send** — and a reset workspace with no project, so it creates
  one first.

All three tests then passed live
([the second 2026-09-28 round](TESTING.md)).

**2026-09-04 — eight more, each re-run against a *used* workspace.**
`guide-surface`, `review-chat-surface`, `containment-surface`, `visual-refresh`,
`knowledge-map-work`, `reference-graph`, `bug-69-local-model-library` and
`bug-69-huggingface`. Re-running each against a workspace that already had an
owner, a scan and a connection is what made the conversions evidence rather than
substitutions: three of the eight failed *after* the sign-in, for reasons that
were nothing to do with it, and each of those is a defect this round fixed rather
than an assertion it relaxed —

* `containment-surface` documented its seeding as a shell block for a person to
  run by hand, so a round that did not run it met a red assertion about a list
  that was empty *because the product was behaving correctly*. It now performs
  its own precondition and skips with the reason when it cannot.
* `bug-69-local-model-library` asserted `getByText("Raiker Live GGUF")` against
  the whole page. Its own scan puts that name into every model picker on the
  screen, so the assertion passed exactly once — on a workspace where nothing had
  been scanned before — and then failed as a strict-mode violation naming four
  elements. Scoped to the inventory the test is about.
* `bug-69-huggingface` answered "no network to huggingface.co" with a
  three-minute timeout on a click, and blamed the click. It now states the
  precondition after the sign-in and the search have both actually happened, so
  what it still verifies on such a host is real.

**One conversion was reverted rather than committed unverified.**
`c17-b14-recall-and-inline-diff-live` needs a provider that answers, and this
round's key does not ([BUG-273](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more)).
The rule this entry states — *a blind bulk edit would replace verified sign-ins
with unverified ones* — applies to a careful edit that cannot be re-run just as
much as to a blind one.

**Observed.** Thirty-seven live specs delegate to `signInAsOwner`. Twenty-seven
others sign in *inline* in a test body, and those copies are the ones BUG-229
described: several still key on the empty-workspace greeting.

**Seven are done, each re-run as it was converted** — `all-pages`,
`all-pages-theme`, `observability`, `default-ollama`, `memory-knowledge-context`,
`memory-semantic` and `memory-vector-index`. That found three pieces of drift
nothing else would have, including a spec still driving a Vite dev server on port
5174; they are recorded in FIXED-328. **Ten are left** after the 2026-09-29
recount, and the reason they are left is unchanged.

**Why they were left.** They vary in a way the function-shaped ones did not —
different bases, different landing routes, some navigating to the route under
test *before* signing in. And `page.goto` with only the hash changed does not
re-render this app (recorded in `real-work-chat-build-live.spec.ts`), so
replacing "go to Models, sign in there" with "sign in on the workbench, then go
to Models" is a behaviour change per spec rather than a substitution. A blind
bulk edit would replace twenty-seven verified sign-ins with unverified ones.

**Three of them must keep their own.** `review-first-run-honesty-live`,
`wizard-workbench-composer-live` and `workbench-live` sign in *as the thing under
test*; sharing the helper there would hide the behaviour they exist to check.

**Proposed fix.** One spec at a time, each re-run as it is converted — which is
how the evidence behind its FIXED entry is refreshed rather than invalidated.

**Required user-interface outcome.** None; this is harness-only.

---

## BUG-287 — The image provider round trip is unverified against a real provider

> **2026-10-03 — and now references.** [FIXED-733](FIXED_ITEMS.md#fixed-733--research-could-only-reach-a-picture-by-being-pasted-into-the-prompt)
> lets a consented research reference travel with a prompt as its own audited
> argument, composed after the prompt by the executor. It is proven to the
> provider's request body with a stubbed transport, not against a real
> provider, and the research turn that makes a reference needs a search
> provider this host cannot reach either. The live round that closes this entry
> should send one reference and read it back in the inspector's **Sent with**.

> **2026-09-15 — what the round trip now has to prove changed.**
> [FIXED-542](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all)
> found that `image_generation` had no key in `CAPABILITY_GATE_MAP`, so the
> owner's switch reached no gate: the action was approval-required by policy and
> nothing else. The row is there now, which means a live round has a second thing
> to measure — that turning **Image generation** off actually refuses a
> generation, not only that a key produces an image.

**Severity: Medium. Area: Design / image runtime / live evidence. Raised while
closing [BUG-277](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network),
2026-09-13.**

**Observed.** Before 2026-10-18 the lineage runtime and canvas were verified only
with controlled transports because the host refused provider egress. That limit
is gone. A real OpenAI `gpt-image-1` round generated a cobalt-blue mug, edited it
to an emerald-green mug with a gold rim, and returned all four requested
variations. The canvas showed six assets, two versions for the edited chain,
**Edited from** lineage and the four assets under **From the same request**.

**What *was* exercised against the running server.** The governed route, the
owner-scoped subject resolution, the count bound and its zero case, lineage
recorded on refusals, `project_id` carried from the composer through to the
stored row, and the canvas composing real rows read back through `GET /api/images`.
The multipart wire format is proven against a real socket — a live HTTP server
parses the body with Python's own MIME parser and the image comes back byte for
byte (`tests/test_multipart_egress.py`).

**What is not known.** The real-provider shape is now known for OpenAI generation,
edit and four-result variation. Two contracts remain unverified: how a provider
refusal reads when the *source image itself* is refused, and whether a consented
research reference reaches the real provider and appears in the inspector's
**Sent with** list. Design currently edits generated assets; it does not expose
an arbitrary source-image upload that could honestly manufacture the first case.

**Proposed fix.** Add or identify the governed source-image path and exercise a
real provider refusal against it. Separately, create one consented research
reference with a reachable search provider, send it with a real image request,
and read it back under **Sent with**. Keep both as evidence tasks: the successful
real OpenAI round must not be repeated merely to prove already-observed shapes.

**2026-10-18 — real-provider evidence.** The owner entered the image-capable key
through Models. With **Image generation** off, Design disabled **Generate** and
named the gate. With it on and no allowed provider host, the attempt became a
recorded refusal naming the empty allowlist. After `api.openai.com` was allowed,
generation, edit, lineage and four variations completed and were inspected in
the running UI. The same pass fixed [FIXED-945](FIXED_ITEMS.md#fixed-945--design-offered-image-models-from-unconnected-providers),
found because the picker also offered an unconnected Gemini profile.

**2026-10-20 — the source-image path exists.** [FIXED-1002](FIXED_ITEMS.md#fixed-1002--the-owners-own-picture-or-logo-could-not-be-brought-into-design-dw-04-bug-348)
lets the owner import their own picture as an `import` asset under Images, and
an edit of it goes through the same governed executor as any edit. That is the
path a source-image refusal can be exercised on. This round's host had an
Anthropic key only, which has no image model, so neither remaining contract was
observed.

**Interface outcome that has to be true before this closes.** The two remaining
contracts above are observed through a real provider and shown in the inspector.

---

## BUG-339 — The issue-to-pull-request routine has a template and no runner

**Severity: Low. Area: Tasks / routines. Status: Open — found 2026-10-12
building ADD-27 GH-55.**

**Observed.** `raiker/github/routines.py` names the routine's steps and, given
its delegation, which would run and which would ask — read-only by default,
writes only under a delegation re-validated first, never merge. Scheduled
routines (`raiker/runtime/executors/scheduled.py`) run a bounded **read-only**
subagent, so nothing can yet carry the plan's write steps out unattended.

**Effect.** The issue-to-PR routine of PA-S07 / RR-40 is an owner-driven flow
today, not a scheduled one.

**Proposed fix.** A routine kind that runs a governed agent turn (not a
subagent) under the routine's delegation reference, with the plan's decisions as
its ceiling; live evidence is RR-40 against a consented repository.

**2026-10-18 — narrower than it reads.** A scheduled **Task** already runs a
governed agent turn (`raiker/tasks/scheduler.py`), and the authority router
already lets an AI-proposed repository write run unprompted only under a
covering, re-validated delegation (`_repository_delegation` in
`raiker/runtime/authority/router.py`); anything uncovered parks for approval.
What is missing is the binding: creating that Task from the issue-to-PR template
with the plan's steps as its instructions and `NEVER_IN_ROUTINE` as a refusal,
plus RR-40's live run, which needs a connected model and a consented GitHub
repository on this host.

**2026-10-18, later — the binding ships.** [FIXED-950](FIXED_ITEMS.md#fixed-950--the-issue-to-pull-request-routine-can-now-be-scheduled-as-a-build-task-bug-339-reduced)
adds `POST /api/github/routines/issue-to-pr` (a read-only plan plus the Build
task's instructions) and Settings → GitHub → *Issue to pull request*, which
schedules that task through Tasks. **What remains is RR-40:** one scheduled run
against a consented repository with a connected model and a delegation, read
back as a branch, a commit and a pull request receipt, with a merge never
attempted unprompted.

**2026-10-19 live recheck.** `bug-339-issue-to-pr-routine-live.spec.ts`
passed 1/1 against the isolated running service: the plan named the branch,
push and pull-request steps as owner approvals, named merge as never allowed,
and kept scheduling disabled without a selected consented repository. RR-40
therefore remains open; no external repository was changed in this run.

---

## BUG-348 — The Design canvas is edited by keyboard and inspector only, and five DW requirements are still partial

**Severity: Medium. Area: Design / composition. Status: Open remainder — found
2026-10-19 while closing DW-D02 to DW-D06 ([FIXED-979](FIXED_ITEMS.md#fixed-979--a-design-was-one-picture-never-a-document-of-layers-dw-01-dw-02)
to [FIXED-996](FIXED_ITEMS.md#fixed-996--a-conflicting-edits-explanation-vanished-in-the-reload-it-caused));
reduced 2026-10-20 by [FIXED-998](FIXED_ITEMS.md#fixed-998--a-layer-could-only-be-moved-with-the-arrow-keys-dw-02-bug-348)
to [FIXED-1010](FIXED_ITEMS.md#fixed-1010--after-a-restart-the-design-agent-said-no-chat-model-was-connected).**

**Observed.** The structured canvas, versions, systems, agent proposals,
checks, exports and the Build handoff ship and pass live. The 2026-10-20 round
added pointer drag, resize and rotate handles, multi-select, align, distribute,
snapping with guides, owner picture import, tokens-file and picture-palette
system import, document components, notes, a vector PDF and durable proposal
receipts, and passed 7/7 live. What is still a gap against
[the Design workspace](DESIGN_WORKSPACE_SPEC.md):

| Requirement | What exists | What is missing |
|---|---|---|
| DW-02 direct manipulation | Drag, resize and rotate handles, multi-select, align, distribute, snapping and guides | Clicking a layer inside a group on the canvas selects the group; its children are selected from Layers |
| DW-06 system sources and components | Tokens files (CSS, JSON), a picture's colours, typed values; components kept in their document | Importing from a brand-guide document (PDF); components shared through a design system across documents |
| DW-11 formats | PNG, raster PDF, vector PDF, SVG, JSON | Presentation and document formats; vector PDF text beyond Windows-1252 (counted and written as `?`) |

The canvas also draws text in the browser's font while PNG and both PDFs use the
host's raster font (recorded with each export), so a line can break in a
slightly different place on screen than in the file; Check measures with the
export font. T-11 and T-12 still need the five model-driven runs the Testing
protocol requires.

**Proposed fix.** One slice per row, each with its own live evidence: canvas
selection inside groups (double-click to enter a group), then a brand-guide
reader through the existing document attachment extraction, then system-level
components, then a presentation export.

**Required user-interface outcome.** The remaining rows are reachable from the
Documents workspace and absent until they are.

## BUG-351 — CLI model commands cannot reach a connected hosted provider

**Severity: Low. Area: CLI / models. Status: Open — compatibility consequence of
ADR-0004, found 2026-10-20.**

**Observed.** The terminal `/model` list, launch and use commands build a
`ModelRouter` with no owner, so they read no saved connections. Before ADR-0004
an environment key plus `RAIKER_MODEL_EGRESS_ALLOWLIST` reached a hosted
provider from those commands; now they refuse with `model_connection_required`
and work only for local models. Chat turns from the CLI go through
`AgentGateway` with the owner and are unaffected.

**Root cause.** `raiker/cli/commands.py` predates per-owner connections and
never resolves the terminal's owner.

**Proposed fix.** Resolve the bootstrapped local owner with
`resolve_local_principal` and pass `connection_resolver` and
`runtime_policy_resolver` for that owner, as `owner_model_runtime` does.

**Required user-interface outcome.** `/model` in the terminal lists and
launches the owner's connected providers, and an unconnected one says
*connect it in Models* rather than naming an environment variable.


## BUG-352 — A custom endpoint saved off the machine shows no route on its card

**Severity: Low. Area: Models / UI. Status: Open — found 2026-10-20 in the
BUG-349 live round (MT-03, `docs/screenshots/2026-10-20-model-transport-guard/04`).**

**Observed.** The OpenAI-compatible card connected to
`https://models.raiker-live.example/v1` showed no posture line — no *Needs
network*, and no *Direct connection* / *Through your proxy* — while every
shipped hosted card did.

**Root cause.** `ModelProfileView.off_machine` and the posture flags are read
from the profile's own shipped endpoint (`http://127.0.0.1:8000/v1`), not from
the endpoint the owner saved. `proxy_route` already uses the saved endpoint;
the line that would show it is gated on `off_machine`.

**Proposed fix.** Classify the saved connection's endpoint when there is one
for `off_machine` and the posture, and check every count that reads
`off_machine` (posture totals, `remote_profile_count`) still means what it says.

**Required user-interface outcome.** A custom endpoint pointed at the owner's
network or the internet reads like any other off-machine card, with its route.

## BUG-354 — The workspace key cannot be rotated in place

**Severity: Low. Area: Storage / memory key. Status: Open — found 2026-10-20
writing the MEM-KEY-05 runbook ([FIXED-1036](FIXED_ITEMS.md#fixed-1036--the-memory-key-had-no-runbook-and-nothing-checked-the-key-stays-out-of-memory-mem-key-05)).**

**Observed.** `.raiker/app.key` is generated once per workspace and derives the
SQLCipher database key (`raiker/auth/app_key.py`, `SQLiteStore._open_keyed`).
Nothing rekeys the database: there is no `PRAGMA rekey` path, no route and no
setting. An owner who believes the key was copied off the machine can only
export memories and import them into a new workspace, which leaves
conversations, review history and backups behind.

**Root cause.** Rotation was never in scope; backups record a key fingerprint
and restore requires the same key, so a rekey also has to say what happens to
backups made with the old key.

**Proposed fix.** An owner-started, step-up-verified **Rotate workspace key**:
take a verified backup, `PRAGMA rekey` the live database to a new key written
atomically beside the old one, re-verify, then retire the old key file; mark
older backups as needing the retired key, which the owner can keep or discard.
Fail closed and leave the old key in place on any error.

**Required user-interface outcome.** **Settings → Security & sign-in** offers
the rotation, says which existing backups will still need the old key, and
reports the new key fingerprint after a verified rekey.

## BUG-355 — Goals ship without intake from Chat, validator-backed criteria or a restart scenario

**Severity: Medium. Area: Goals / personal agent. Status: Open remainder of
PA-D01 — the first slice shipped 2026-10-20 ([FIXED-1039](FIXED_ITEMS.md#fixed-1039--an-outcome-could-live-only-in-a-chat-transcript-there-was-no-durable-goal-goal-01-pa-d01)
to [FIXED-1048](FIXED_ITEMS.md#fixed-1048--a-goal-had-no-budget-across-its-steps-goal-10-pa-d01)).**

**Observed.** Durable goals, their lifecycle, coordinator, evidence, Stop,
Pause/Resume and budgets pass unit and live tests. Against
[the personal-agent specification](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) these
remain:

| Requirement | What exists | What is missing |
|---|---|---|
| Outcome intake | **Work → Goals** form; from Chat, **Make this a goal** and goals noticed in conversation fill it in ([FIXED-1252](FIXED_ITEMS.md#fixed-1252--the-same-aim-across-conversations-was-never-offered-as-a-goal-qui-f03)) | Starting a goal from a Build turn; asking only for materially missing facts |
| Criteria validators | *Met when its steps finish* (a record the steps finished) and *You confirm it* | A Build step's `completed_verified` outcome, a destination read-back or another independent validator as evidence |
| Leases and recovery | Each step is a task with the task's own claim generation and lease; an interrupted dispatch fails after two minutes rather than re-filing | A goal-level lease for concurrent coordinators across hosts, and the host-restart live scenario the register names |
| Pause | Files nothing new and parks unclaimed steps; a running step finishes its current turn | A pause that reaches a running step's next safe boundary without stopping it |

**Proposed fix.** One slice per row, each with its own live evidence: a
*Make this a goal* action in Chat that prefills intake, then a Build-verified
validator reading the step's turn outcome, then the restart scenario through
`scripts/build_restart_fault.py`'s pattern, then a safe-boundary pause.

**Required user-interface outcome.** Each row is reachable from the surface it
belongs to and absent until it works.

## BUG-356 — Execution profiles govern goal steps only, and cover one data class

**Severity: Medium. Area: Execution profiles / models / data handling. Status:
Open remainder of PA-D02 — the first slice shipped 2026-10-20 ([FIXED-1049](FIXED_ITEMS.md#fixed-1049--there-was-nowhere-to-say-where-a-goals-work-may-run-prof-01-pa-d02)
to [FIXED-1051](FIXED_ITEMS.md#fixed-1051--changing-the-boundary-would-have-applied-silently-to-work-in-flight-prof-03-pa-d02)).**

**Observed.** A profile is enforced on every goal step, before it is filed and
before it runs, across the owner's whole fallback chain, and withholds personal
memory from a hosted step where it says so. It does not yet reach:

* **Ordinary Chat, Build and scheduled tasks.** The specification makes the
  active profile the ceiling for all new work; today it bounds goal steps only.
  Settings says so.
* **Hosts.** Steps run on this host; a profile cannot yet name a private
  always-on host or a remote executor (PA-D07).
* **Other data classes.** Attachments, research references and selected files
  are not yet steps' inputs, so there is nothing to withhold; when they are,
  the profile needs a field per class.
* **Egress and retention constraints** per provider.
* **Placement of a custom endpoint.** A model profile's placement is its
  `local_only` flag, so a generic OpenAI-compatible endpoint on `localhost`
  reads as hosted and Private local refuses it. Conservative, and stated on the
  Settings page, but wrong for that owner.

**Proposed fix.** Extend enforcement to every prompt route through the
gateway's model selection (the same chain check), classify a custom endpoint by
its saved route (`raiker/models/endpoint_policy.py`), then add host and
data-class fields as PA-D05/PA-D07 give steps those inputs.

**Required user-interface outcome.** Settings → Execution profiles states what
each profile governs; a refused Chat or Build turn names the profile and offers
the Settings route, exactly as a goal step does.

## BUG-359 — Remote access is verified live on Linux only and has five known limits

**Severity: Low. Area: Host / remote access. Status: Open remainder — found
2026-10-26 closing BUG-347 and BUG-358
([REMOTE_ACCESS.md](../architecture/REMOTE_ACCESS.md)).**

**Observed.** Remote access — the three modes, mandatory two-step sign-in,
suspension, fresh MFA, signed-in devices, apply/restart/roll back/turn off —
passed its unit, contract and live tests (RT-SEC-01 to RT-SEC-12) on Linux.
What remains:

1. **Windows and macOS are covered by CI unit tests only** (job *Remote
   access*: real TCP and TLS servers, `SO_EXCLUSIVEADDRUSE`, socket path
   length). No live browser round has run on either.
2. **Restart from Settings needs a service manager.** A host not registered
   with `systemd --user` or `launchd` (and every Windows host) exits on
   Restart; the owner opens Raiker again. Settings says so.
3. **A changed TLS certificate needs a restart.** The private listener loads
   the certificate and key once at start; a renewed certificate is served from
   the next start.
4. **Every request through a reverse proxy shares one rate-limit bucket**,
   because the proxy is the only peer Raiker sees on that listener and
   forwarding headers are never believed. A busy proxy can throttle the owner's
   own remote session; it cannot reach the local listener's bucket.
5. **A certificate path in a check message can show as `[REDACTED_SECRET]`**:
   the response redactor treats a path under a temporary directory named like a
   secret as one. The check result is right; only the wording loses the path.

Seen in the final live round's screenshots, cosmetic: the lock screen on
another device still headlines its note *On this computer*; the *Remote access
is suspended* notice stays in the notification tray after two-step sign-in is
turned on again; and the coloured *On* state sits a little left of the other
rows' values.

The IPv6 private-address path (`fc00::/7`) is unit-tested and was not run
live; mobile apps that will sign in remotely are later work and need the same
password-and-code rule.

**Proposed fix.** Run RT-SEC-04 to RT-SEC-12 on a Windows and a macOS host;
reload the TLS context on a file change (or offer *Reload certificate* in
Details); key the proxy bucket by session once signed in; narrow the redactor
rule for file paths in check messages; say *From another device* on the remote lock
screen; mark the suspension notice read when MFA is on again.

**Required user-interface outcome.** None beyond today's: Settings → Security →
Remote access already says when a restart is needed, and Details shows the
check that failed.

## 2026-10-19 verification follow-up — five Windows full-suite failures

The focused regression set, documentation contracts, Ruff, mypy, and web checks passed. The complete local Python suite reached 100% but reported five failures on this Windows host:

- `tests/test_bug_308_code_placement.py::TestTheCommandServiceNeverRunsHostCodeUnasked::test_an_ordinary_command_needs_nothing_new` (`pwd` ended in `command_launch_failed`)
- `tests/test_command_workspace_is_not_global.py::test_no_workspace_still_means_the_process_directory` (expected `SandboxError` was not raised)
- `tests/test_git_push_path.py::TestProposalFailsClosed::test_not_a_repository` (returned `push_egress_denied` instead of `not_a_git_repository`)
- `tests/test_git_write_path.py::TestBranchProposal::test_a_non_repository_fails_closed` (returned no `error` object)
- `tests/test_notification_quiet_hours.py::test_the_os_command_obeys_the_stored_desktop_decision` (configured `true` notifier returned `failed` instead of `sent`)

These are not closed by this documentation/live-test pass. They need follow-up investigation to determine which are Windows-environment assumptions and which are regressions in command, Git proposal, or notification behavior.

## 2026-10-21 verification follow-up — the top bar's STOP count after a finished turn

In the Quiet UI live round, the RT-QUI-05 capture taken just after a 120-line
answer finished shows the top bar's **STOP** control with a count of 1 while
Chat showed no running turn. Home then listed *2 proposed memories to review*,
so the running item was probably the memory-proposal pass after the turn, but
this was not confirmed. Triage: read `GET /api/work-in-flight` at that moment and
check that whatever the STOP count includes is named where the owner can see it.

## 2026-10-21 Quiet UI round 2 — what is still open

Round 2 shipped [FIXED-1080](FIXED_ITEMS.md#fixed-1080--home-offered-five-threads-to-continue-instead-of-the-one-with-its-next-step-qui-h01)
to [FIXED-1100](FIXED_ITEMS.md#fixed-1100--a-long-conversation-rendered-every-turn-qui-g04);
the layout round shipped [FIXED-1101](FIXED_ITEMS.md#fixed-1101--the-shell-was-wider-and-looser-than-the-layout-system-qui-l01-qui-l14)
to [FIXED-1123](FIXED_ITEMS.md#fixed-1123--chats-readiness-steps-disappeared-with-the-models-overview-qui-l08).
These parts of the same items are not done:

* **QUI-G01 — two pages are still a little over budget** after the
  2026-10-25 round ([FIXED-1174](FIXED_ITEMS.md#fixed-1174--settings--privacy-general-and-advanced-were-over-their-size-budget-qui-l03-qui-g01)):
  Memory › Controls (929 px at 1440×900 against 900) and Memory › Map (922 px,
  a canvas). Diagnostics, Privacy, General and Advanced now fit. The report is
  in `all-pages-live.spec.ts`; it becomes a failing check once these two fit.
* **QUI-G06 — about 200 other error messages** still give a status code, or
  *Could not X*, without what it affected and a next step. The pattern and the
  helper are in `web/src/lib/errorCopy.ts`; the ones on Stop, steer, continuing,
  export, upload, file lookup and saving a task are done.
* **QUI-G04 — actions that paint before their request returns.** Long
  transcripts are windowed; optimistic rename, pin and archive with a visible
  roll-back are not built.
* **QUI-L11 — the moves out of Diagnostics.** Overview as issue cards and
  Recovery shipped 2026-10-25 ([FIXED-1170](FIXED_ITEMS.md#fixed-1170--diagnostics-opened-on-seven-tiles-reading-ready-and-0-qui-l11),
  [FIXED-1171](FIXED_ITEMS.md#fixed-1171--restoring-a-checkpoint-was-the-dominant-button-and-named-little-qui-l11)).
  Sessions as Work › Threads, activity inside each task and project, and
  Recovery reached from the affected task are not built; Diagnostics keeps its
  six tabs until they are.
* **QUI-L12 — Projects as rows.** Work's lists page after 50 and threads and
  goals are 64 px rows; Projects is still a card grid.
* **Older live specs still drive the pages the layout round replaced.** About
  70 specs under `web/e2e/*-live.spec.ts` (written before 2026-10-21) open
  Models by its old tabs, Extensions tabs, Permissions rows that opened in
  place, and the Settings sections that moved. The old addresses forward, but
  the steps inside them (open a row in place, a provider card on the page)
  no longer exist. `quiet-ui-layout-live`, `all-pages-live`,
  `quiet-ui-accessibility-live`, `quiet-ui-home-chat-live` and the shared
  helpers (`hosted-provider.ts`) are updated; the rest need the same before
  they are run again (related to BUG-248).
* **QUI-W02 and QUI-H02 — the companion.** Its pick in Hello and its picture on
  a first-day Home wait for the companion's art (QUI-V05).
* **QUI-C04 — *More*** (schedule, research depth, answer style) is not built.
  **Run in background** sits in Tools until it is. The profile chip on both
  composers shipped 2026-10-22 ([FIXED-1130](FIXED_ITEMS.md#fixed-1130--a-conversation-could-not-say-how-careful-raiker-should-be-qui-p02)).

## 2026-10-22 Quiet UI approvals round — what is still open

The approvals round of [02](quiet-ui/02_PERMISSIONS_AND_APPROVALS.md#status)
shipped [FIXED-1125](FIXED_ITEMS.md#fixed-1125--an-unanswered-approval-waited-a-day-and-the-wait-could-not-be-set-qui-p06)
to [FIXED-1135](FIXED_ITEMS.md#fixed-1135--nothing-checked-that-a-model-could-not-draw-an-approval-card-qui-p05-acceptance).
These parts of the same document are not done:

* **QUI-P03 — Allow with limits.** Permissions offers *Ask me*, *Allow*,
  *Automatic* and *Never*. A limited allow (account, recipients or domains,
  attachments, volume, sensitive data still asks, scope, expiry) needs a rule
  the runtime evaluates; Settings › Security's *Standing approval grants*
  (action type, risk ceiling, scope, expiry) is the closest existing record and
  the likely base. Until it exists, **Within limits** (QUI-P02), **Allow for
  this task** (QUI-P05) and the suggestion in QUI-P09 are not offered.
* **QUI-P04 — connection presets and accounts.** *Read only* (the default for a
  new connection), *Ask before changes* and *Custom*, several named accounts per
  service, and recent activity under the list need a per-connection policy and
  account record. Today a connection is on or off for the session, and each
  operation's `requires_confirmation` comes from its manifest.
* **QUI-P08 — Approvals you've given** in Memory › Controls, with Undo, together
  with *What Raiker has learned to do* (QUI-F09).

## 2026-10-26 storage upgrade — what is still open

- **SQLite 3.54.1 is not available inside SQLCipher yet.** The owner asked for SQLite 3.54.1 and SQLCipher 4.19.0. SQLCipher is a fork of SQLite and its SQLite version is its own baseline: 4.19.0, the newest release, and SQLCipher's main branch are both on **3.53.4**, which is what Raiker now runs ([FIXED-1249](FIXED_ITEMS.md#fixed-1249--sqlcipher-was-4120-from-a-third-party-fork)). Merging SQLite 3.54.1 into SQLCipher's encryption code ourselves would ship an unreviewed fork of the cipher, so it was not done. Close this when a SQLCipher release moves its baseline to 3.54 and `sqlcipher3` publishes wheels for it: raise the floors in `pyproject.toml`, the CI step and `scripts/packaging_smoke_test.py`.
- **The desktop packaging workflow has not run with memory security on *auto*.** `desktop-package.yml` runs only when desktop or packaging paths change, and its two `off` overrides are removed ([FIXED-1248](FIXED_ITEMS.md#fixed-1248--sqlcipher-memory-security-could-still-be-switched-off)). The installers' smoke tests will resolve *auto* on the next desktop change; a runner whose probe fails runs unlocked and says so, so no failure is expected, but it is unverified.
- **Forty locked packages have newer releases.** Only the setuptools advisory was taken ([FIXED-1251](FIXED_ITEMS.md#fixed-1251--the-locked-build-set-carried-a-setuptools-advisory)). The rest, FastAPI 0.141 → 0.162 and Starlette 1.6 → 1.10 among them, are a dependency refresh to do as its own change with the full suite and a live pass.

## Agent tool inventory — open items (document closed 2026-10-26)

`docs/plans/AGENT_TOOL_INVENTORY.md` was worked in three rounds on 2026-10-25 and 2026-10-26 and then removed: every item is shipped, already in Raiker, or carried here. Shipped: [FIXED-1189](FIXED_ITEMS.md#fixed-1189--grep-searched-literal-text-only-with-no-context-lines-tool-02) to [FIXED-1236](FIXED_ITEMS.md#fixed-1236--builds-plan-posture-sent-planning_mode-always-and-nothing-read-it-tool-151). The capability matrix the inventory built, the input to the tools refactor, is now in [RAIKER_TOOL_AND_PLUGIN_CATALOG.md](../architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md#tool-capability-matrix). Each row below keeps the inventory's *Proposed Raiker capability* as written; it is a backlog idea, not a decision, and still needs its own design, threat model and approval ([THREAT_MODEL.md](../architecture/THREAT_MODEL.md)).

**Already in Raiker, so not carried:** TOOL-12 and TOOL-95 (`tool_search` defers tool schemas), TOOL-25 (local `git_branch`, `git_commit`, `git_push`), TOOL-41 (`create_task` with a schedule, asked first), TOOL-98 (one shell tool), TOOL-106 (`create_document` writes .docx, .xlsx and .pdf), TOOL-107 (chart answer blocks), TOOL-109, TOOL-116 (image generation in Design), TOOL-117 (read aloud and dictation), TOOL-118, TOOL-121, TOOL-122 (see TOOL-93), TOOL-128 and TOOL-153 (a paired messaging channel), TOOL-150 (scheduled tasks; see TOOL-44 and TOOL-45), TOOL-152 (backups in Settings). **Decided by the owner, so closed:** TOOL-91's provenance rule. On 2026-10-25 the owner ruled that `web_fetch` refuses no URL and alerts on flagged ones ([FIXED-1221](FIXED_ITEMS.md#fixed-1221--web_fetch-refused-a-site-the-owner-had-flagged-instead-of-reading-it-with-an-alert)). **Not applicable:** the rest of TOOL-46, which is about a cloud session.

### Waits for the tools refactor

These reshape the tool set itself; doing them one by one would be undone by the refactor.

| Item | Inventory tool | Proposed Raiker capability |
|---|---|---|
| TOOL-99 | Text editor (`text_editor_20250728`, `_20250124`), client | Merge `write_file`, `edit_file`, `apply_patch` into one editor tool with commands (the `insert_line` and `cell` parts shipped). |
| TOOL-102 | Tool definition properties | The refactor's tool manifest carries these: strict schemas, examples, deferral and caller limits per tool |
| TOOL-110 | `terminal`: `terminal`, `process_manage` | One execution tool with a *where* argument chosen from the owner's configured backends |
| TOOL-111 | `file`: `read_file`, `write_file`, `patch`, `search_files` | Hermes does it with four tools; a reference point for consolidating Raiker's six |
| TOOL-130 | Approvals, checkpoints, toolset profiles | **Named toolsets per surface and posture** as the refactor's unit: Chat, Build, Design, a routine and a subagent each get a declared set |
| TOOL-96 | MCP connector (`mcp_toolset`, beta), server | Keep MCP in the broker; adopt the per-tool allow and defer settings in each connection's manifest |

### Needs its own threat model before any code

Each reaches outside the broker's current reach: a browser, the desktop, payments, credentials handed to code, or a second policy process.

| Item | Inventory tool | Proposed Raiker capability |
|---|---|---|
| TOOL-100 | Computer use (`computer_toolset_20260801`; betas `computer_20251124`, `computer_20250124`), client | A governed desktop-control toolset for the desktop shell, every action shown live and stoppable, off unless the owner turns it on |
| TOOL-101 | Browser use (`browser_toolset_20260801`), client | A governed browser toolset (see the matrix: all three agents have one) |
| TOOL-108 | Claude in Chrome, Cowork (Claude apps) | The browser toolset (TOOL-101) first in the desktop shell's own window, not the owner's profile |
| TOOL-113 | `browser`: `browser_exec`, `browser_cdp`, `browser_dialog`, `browser_vault` | Browser toolset (matrix row); credentials from the vault filled by the broker, never shown to the model |
| TOOL-141 | Browser subagent | The browser toolset as its own subagent, the main turn seeing only its summary |
| TOOL-142 | Sentinel | A second, model-free policy check on every egress and connector write, outside the agent's process |
| TOOL-143 | Approval scopes | *For this task* and *for the next hour* as approval scopes |
| TOOL-144 | Surrogate credentials | Surrogate tokens for sandboxed code, swapped by the broker |
| TOOL-145 | Purchases | Out of scope until a payments threat model exists; critical, asked every time |
| TOOL-93 | Programmatic tool calling (`allowed_callers`) | Let a sandboxed script call read-only Raiker tools through the broker, each call still gated and audited |
| TOOL-92 | Code execution (`code_execution_20260521`, `_20260120`, `_20250825`), server | A disposable analysis sandbox that takes the owner's attached files and returns files, not only output |
| TOOL-140 | Secure VM | A per-owner workspace the owner can open and watch, the same one the agent works in |

### Needs infrastructure Raiker does not run

A push service, an inbound webhook endpoint, a cloud repository host or a second conversation runner.

| Item | Inventory tool | Proposed Raiker capability |
|---|---|---|
| TOOL-44 | `watch_url`, `unwatch_url` | Inbound webhooks for routines, signed and owner-approved per source |
| TOOL-45 | `PushNotification`, `ReadNotifications` | A mobile push channel for *Approval needed* and *Task failed*, under the same quiet hours (DEC-21a) |
| TOOL-40 | `create_session`, `send_message`, `interrupt_session`, `archive_session`, `unarchive_session`, `get_session`, `list_sessions`, `list_events`, `get_event`, `set_session_title`, `set_session_tags` | One conversation starting and steering another (a routine delegating to a fresh thread), owner-visible in Threads |
| TOOL-43 | `subscribe_pr_activity`, `unsubscribe_pr_activity` | Build follows its own pull request and fixes CI or answers review, within its permissions |
| TOOL-42 | `send_later` | A reminder that continues the same conversation, shown in Tasks |
| TOOL-06 | `ScheduleWakeup` | A self-scheduled continuation of a turn, shown in Tasks and stoppable |
| TOOL-31 | `create_repository`, `fork_repository` | `create_repository` and `fork_repository` on GitHub, asked first and critical. |

### Needs a connector or catalogue Raiker does not have yet

Each is a new connector, a plugin catalogue, or a provider tool to align with.

| Item | Inventory tool | Proposed Raiker capability |
|---|---|---|
| TOOL-63 | `Figma` (design context, screenshots, variables, Code Connect, `use_figma`, diagrams, …) | A Figma connector for Design: read a frame as a reference, export a design |
| TOOL-64 | `Canva` (create, edit, export, brand kits, …) | A Canva connector for Design exports |
| TOOL-65 | `DesignSync` | Keep `app.css` tokens and an external design system in step |
| TOOL-71 | `ListPlugins`, `SearchPlugins`, `SuggestPluginInstall` | Suggest a plugin from the catalogue; installing stays the owner's |
| TOOL-70 | `Skill`, `ListSkills`, `SearchSkills`, `SuggestSkills` | Suggest a skill that is not installed yet (searching installed skills shipped, FIXED-1217). |
| TOOL-73 | `ListMcpResourcesTool`, `ReadMcpResourceTool`, `ReadMcpResourceDirTool` | MCP resources in Connections › Advanced, read-only |
| TOOL-94 | Advisor (`advisor_20260301`, beta), server | Align `consult_advisor` with the provider tool where the provider offers it |
| TOOL-112 | `web`: `web_search`, `web_extract`; `x_search` | Source-specific search as connector tools, not core |
| TOOL-127 | Messaging toolsets: `discord`, `discord_admin`, `feishu_doc_read`, `feishu_drive_*` | Per-platform tools as connector manifests, not core tools |
| TOOL-146 | Connectors and skills | Show each connection's read and write grants separately |
| TOOL-80 | Google Workspace | Google Workspace beyond today's `gmail_read` and `gcal_read`: Drive, Docs and Sheets reads, and drafts, labels and calendar writes, each write asked first. |
| TOOL-81 | Messaging and work | Slack beyond `slack_read`, plus Asana, Linear, ClickUp, Atlassian, monday.com and Notion, as manifest-driven connectors. |
| TOOL-82 | Sales, finance and commerce | Sales, finance and commerce services (Apollo.io, HubSpot, QuickBooks, Xero, Stripe, PayPal) as manifest-driven connectors; anything that spends is critical. |
| TOOL-83 | Consumer and travel | Consumer and travel services (job search, booking, flights) as manifest-driven connectors. |

### A product feature of its own

Each is a surface or a loop larger than one tool, with its own design to settle.

| Item | Inventory tool | Proposed Raiker capability |
|---|---|---|
| TOOL-05 | `Monitor` | `watch`: a bounded, owner-visible watch on a background command or a feed, ending on a stated condition |
| TOOL-07 | `Agent`, `SendMessage`, `ListAgents` | Message a running subagent; list subagents; a fork that inherits the turn's context |
| TOOL-10 | `EnterWorktree`, `ExitWorktree` | Model-requested worktree for an experiment, discarded unless kept |
| TOOL-04 | `TaskCreate`, `TaskUpdate`, `TaskGet`, `TaskList`, `TaskStop` | An owner per plan item and stopping a running item (`blocked_by` shipped, FIXED-1202). |
| TOOL-47 | `SendUserFile` | `create_document` already attaches; a *render now* hint for images and HTML |
| TOOL-60 | `Artifact` (publish, read, list, open, pin, delete, quickstart), `ArtifactComments`, `ArtifactData` | The Library (QUI-F15) as a place for pages Raiker makes, with comments, private by default |
| TOOL-61 | `Claude_Docs` (`batch`, `create`, `read`, `update`, `query`, `export`, `delete`, `guide`) | Documents in the Library that a turn can edit section by section, with history |
| TOOL-62 | `pdf-viewer` (`display_pdf`, `interact`, `list_pdfs`) | PDF annotation and form filling in Design or Chat, asked before a signed file leaves |
| TOOL-66 | `ReportFindings` | Build's patch review (`review_patch`) as typed findings the transcript draws |
| TOOL-74 | `ShowOnboardingRolePicker` | A role choice in the setup conversation (QUI-W02) that pre-selects starters and connectors |
| TOOL-75 | `Artifact` `quickstart` and types | Templates in Design and the Library |
| TOOL-97 | Memory (`memory_20250818`), client | A scheduled consolidation pass over Memory (merge duplicates, retire stale facts) that proposes its changes in Suggestions |
| TOOL-105 | Research (Claude apps) | A research mode in Chat: a bounded plan of searches, shown as it runs, ending in a cited document. `web_search` depth `extended` (FIXED-1235) is its first step. |
| TOOL-115 | `vision`: `vision_analyze`; `video`: `video_analyze` | `video_analyze` for an attached clip |
| TOOL-119 | `memory`: `memory`; `session_search`: `session_search`; `context_engine` | A *save this?* nudge after a long task, landing in Suggestions; summaries on `conversation_search` hits |
| TOOL-120 | `skills`: `skills_list`, `skill_view`, `skill_manage` | The model drafts a skill from a finished task, proposed to the owner, never installed by itself |
| TOOL-123 | `delegation`: `delegate_task` | Asynchronous subagents with a toolset chosen per task and a typed result |
| TOOL-125 | `kanban`: `kanban_show`, `kanban_list`, `kanban_create`, `kanban_complete`, `kanban_block`, `kanban_unblock`, `kanban_link`, `kanban_comment`, `kanban_heartbeat`, `kanban_request_review`, `kanban_request_changes`, `kanban_attach`, `kanban_attach_url`, `kanban_attachments` | Task tools for the model: comment, block on another task, attach a file, ask for review; a heartbeat on a long task |
| TOOL-129 | `desktop_ui`: `read_terminal`, `close_terminal`, `desktop_preview`, `drive_preview`, `annotate_preview`, `read_window_below`, `focus_pane`, `gui_tour`, `show_tip`, `set_theme`; `onboarding`: `setup_beat`; `project`: `desktop_project` | A guided tour (`gui_tour`); help sources and contextual parts shipped (FIXED-1215, FIXED-1225). |
| TOOL-147 | Memory and observers | A *verifier* that checks a turn's claimed result (tests run, file written) before the turn reports done |
| TOOL-148 | Subagent fan-out | Parallel Build subagents, each in a worktree, under one approval budget |
| TOOL-149 | Custom tools, documents, images | Model-written tools proposed as skills (TOOL-120) |

### Blocked on a provider or a host

Raiker's side is ready to take them; something outside it is not.

| Item | Inventory tool | Proposed Raiker capability |
|---|---|---|
| TOOL-02 | `Read`, `Write`, `Edit`, `Glob`, `Grep` | Images in `read_file`: a tool result is text for every provider adapter, so each adapter has to carry an image part in a tool result first. |
| TOOL-20 | `actions_list`, `actions_get`, `get_job_logs` | Raw CI job logs: GitHub redirects a log request to a storage host outside the connector egress rule, and the token must not follow a redirect (BUG-350). `checks` and `run_jobs` give annotations and failed steps instead. |
| TOOL-28 | `issue_read`, `issue_write`, `list_issues`, `search_issues`, `add_issue_comment`, `update_issue_comment`, `sub_issue_write`, `list_issue_types`, `list_issue_fields`, `get_label` | Writing sub-issues; reading them shipped (FIXED-1232). |

### Found while working the inventory, not yet fixed

* **The approval card does not show an edit's diff inline.** RT-TOOL-04: the
  Safety card for an `edit_file` says *Approving writes this exact change to
  src/palette.py* and offers **Change**, but the replacement itself is only in
  the change view. For a `replace_all` edit, the number of places it changes
  is worth saying on the card, and for a notebook edit (RT-TOOL-21) *Affects*
  names the file but not the cell, which the row already shows. Not triaged.
* **A live web search is unproven on the test host.** Its proxy refuses
  `duckduckgo.com` by its own network policy (403), so the proxy route for
  search is proven by the unit suite only; a read of `github.com` through the
  same proxy works (RT-TOOL-20). Re-run RT-TOOL-20 with a search on a host
  whose network allows DuckDuckGo.
* **Web reads are refused on a proxy host that blocks DNS over HTTPS.** By the
  owner's decision of 2026-10-26 a proxied name must be looked up through the
  proxy first ([FIXED-1239](FIXED_ITEMS.md#fixed-1239--a-proxied-name-was-reached-without-checking-where-it-leads-ssrf)).
  The test host's proxy refuses `cloudflare-dns.com` and `dns.google`, so a name
  it cannot resolve directly is refused as unverified (RT-TOOL-23); names it
  resolves itself are read on the pinned route.
* **The threat feeds are unproven live.** The test host cannot reach
  `urlhaus.abuse.ch` or `openphish.com`, so the feeds' download is proven with
  fixtures only and Settings shows *Could not reach the feed* there. Run
  RT-TOOL-20 on a host that can reach them and read a URLhaus-listed host.
* **`tests/test_lock_screen_recovery.py` fails intermittently under parallel
  load.** Twice in this round one of its tests failed in a three-shard parallel
  run and passed alone and in every rerun (the restore and same-origin cases).
  Not reproduced on CI; triage the timing it depends on.
* **`github.com/about` raised the *suspicious text* alert** (RT-TOOL-20). The
  sanitiser's instruction-shape check may be too eager on product pages that
  talk about AI; triage against its rules before relaxing anything.
* **A Build Plan turn's record says *No plan required for this turn*** under
  *How this turn was governed* while the turn writes a plan (RT-TOOL-22): the
  pipeline's planning stage and the Plan posture are two different things with
  the same word.

## 2026-10-25 Quiet UI polish round — what is still open

The round of 2026-10-25 shipped
[FIXED-1168](FIXED_ITEMS.md#fixed-1168--the-app-mark-was-the-eye-orb-qui-w01-qui-v03-qui-v04)
to [FIXED-1187](FIXED_ITEMS.md#fixed-1187--the-readiness-strip-and-a-footer-line-disagreed-closed-as-not-reproducing).
Found or left open in it:

* **QUI-V05 — the companion.** The open ring and palette are in; the companion
  waits for its art, and with it the pick in Hello (QUI-W02) and the picture on
  a first-day Home (QUI-H02).
* ***Loading conversation…* stays after a reopened conversation has drawn.**
  Seen in the RT-QUI-66 captures: after a reload the transcript, the tool row
  and the Safety card are on screen while the line above still says it is
  loading. Not triaged: which of the reads after the transcript (attachments,
  sources, recall) holds the flag.
* **Older live specs and this round's changes.** Live specs written before
  2026-10-25 that click **Re-measure boundary** or **Reset environment** in
  Settings › Advanced › Runtime now need to open that environment's *Details*;
  specs that look for *Recall & indexing* use the old tab name (the address
  still forwards); and specs that sort an empty Approvals queue find no sort.
  The mocked suite and `quiet-ui-polish-live` are updated (related to
  BUG-248).
* **The Workstations view keeps its own colours.** Diagnostics › Work in
  action's optional *Workstations* scene draws desks and characters in fixed
  colours rather than tokens, so it does not follow the QUI-V01 palette. It is
  opt-in and kept by an earlier decision; restyling it is open.
* **A Python test is sensitive to a loaded machine.**
  `test_background_execution.py::test_a_foreground_run_holds_no_lease_and_is_never_swept`
  failed once in a four-worker local run and passes alone; CI runs each shard
  serially. Watch it in the shards.

## Quiet UI features and improvements — open items (document closed 2026-10-26)

`docs/plans/quiet-ui/06_FEATURES_AND_IMPROVEMENTS.md` was worked in two rounds
and then removed: every item is shipped, or carried here. The first round
(2026-10-24) shipped
[FIXED-1150](FIXED_ITEMS.md#fixed-1150--nothing-outside-chat-said-that-work-was-running-qui-f04)
to [FIXED-1167](FIXED_ITEMS.md#fixed-1167--two-long-transcript-tests-ran-at-their-time-limit-quality-found-this-round);
the second (2026-10-26) shipped goals noticed in conversation, named accounts,
the Library with 04's **Pin to project**, undo windows, project limits, routine
results to a channel, corrections made by editing and the task receipt
([FIXED-1252](FIXED_ITEMS.md#fixed-1252--the-same-aim-across-conversations-was-never-offered-as-a-goal-qui-f03)
to [FIXED-1263](FIXED_ITEMS.md#fixed-1263--key-figures-read-1200-where-1200-was-meant-found-this-round)).
QUI-F08 and QUI-F23 shipped earlier as [02, QUI-P06](quiet-ui/02_PERMISSIONS_AND_APPROVALS.md#status)
and [03, QUI-H04](quiet-ui/03_WELCOME_HOME_AND_CHAT.md#status).

* **QUI-F14 — a companion on the desktop.** Planned as *Later*: an opt-in, off
  by default, small transparent window that reacts only to *needs your
  decision* and *done*. It waits for the companion's art
  ([08](quiet-ui/08_BRAND_AND_VISUAL_SYSTEM.md#status)).
* **Docked notices cover the right column.** Found live in RT-QUI-78: after a
  routine runs, its notices dock over the right-hand side of the page and cover
  controls there (a project's **Save** under *Project limits*) until they are
  dismissed. The spec dismisses them; the page should keep its controls clear.
* **The account on an approval is shown in monospace.** The card's *Account*
  line draws *Work Gmail* in the code face used for paths and commands. It is a
  name the owner chose and should read as text.
* **Goals are noticed by shared words, not by meaning.** Two requests about the
  same aim in different words are not matched; two unrelated requests that
  share three uncommon words can be. **Not now** keeps a wrong offer from
  returning.
* **A routine's channel delivery is refused while the channel's outbound gate
  is off,** which is the default. The task row says *last one not sent*; the
  form says the gate applies, but not where to turn it on.
* **Older live specs answer native confirms.** Eight earlier live specs wait
  for the browser's `dialog` event; the in-app dialog (QUI-F10) needs them to
  press its button instead. The mocked suite and both rounds' live specs do.
* **One approvals test is load-sensitive.**
  `tests/test_api_approvals.py::TestApprovalsResolve::test_approved_shell_executes_once_with_bounded_evidence`
  failed once in a full local shard under load and passes alone and in its
  file. Not reproduced in CI.

## 2026-10-23 Quiet UI visual answers round — what is still open

The visual answers of [04](quiet-ui/04_VISUAL_ANSWERS.md#status) shipped
[FIXED-1136](FIXED_ITEMS.md#fixed-1136--a-turn-could-not-say-these-are-the-headline-numbers-qui-a04)
to [FIXED-1149](FIXED_ITEMS.md#fixed-1149--a-chart-in-a-transcript-bubble-was-too-small-to-read-and-its-legend-had-no-colours-04-screenshot-review).
These parts of the same document are not done:

* **QUI-A08 — diagrams.** Planned as *Later*. Mermaid would be the first
  diagram library in the bundle, and the built UI makes no external requests,
  so it has to ship inside the app.
* **The three-block limit and the answer style are guidance to the model.**
  Found live: on *Visual where it helps*, Haiku 4.5 once split key figures into
  three blocks (five blocks in one answer) before the instruction said to keep
  them in one, and on *Mostly text* once drew a comparison until the instruction
  said it overrides the general guidance. Above three blocks the answer offers
  **Create document**. Nothing enforces either rule in the runtime, because the
  runtime cannot tell whether the owner asked for a report or for a table.
* **A corrected-block retry streams twice.** On a local model, the first answer
  streams, then the corrected one streams after it, and the final response
  replaces both. Not seen live (this round used a hosted model, which is not
  retried).

## Decision statements added 2026-10-05

**Basis:** repository snapshot `2898b247c9e02d537c6f61e866ed670578e49b42`.
These statements supply missing implementation direction. **Recommended** means
a proposed choice, not an owner approval or a verified fix. The original BUG
entries retain their status and acceptance evidence.

### BUG-226 and BUG-228 — Do not create alternate execution contracts
**Retired from this ledger 2026-10-18** ([FIXED-951](FIXED_ITEMS.md#fixed-951--three-open-entries-were-decided-boundaries-or-superseded-work-not-defects-bug-226-bug-228-bug-234));
the boundary they describe is kept in [KNOWN_LIMITS.md](../architecture/KNOWN_LIMITS.md#boundaries-raiker-chose).

**Decision — retained deferral for hooks; recommended convergence for UI.**
Keep `mcp_tool` and `agent` hook types unsupported until each has bounded,
non-escalating authority, its own resource budget, recursion limits and
execution-time revalidation. For contributed UI, follow the one MCP Apps
contract instead of implementing a second `panels.json` renderer. BUG-228 may
close as superseded once the replacement scope is accepted and its obsolete
promises are reconciled — both done 2026-10-18.

**Reason and acceptance.** A hook must not call a tool the originating turn
cannot call. Two contributed-UI models duplicate permission, isolation and
accessibility work. Test denial/revocation and recursion for hooks, and
per-app grants, message validation, iframe isolation and keyboard access for UI.
A sandboxed iframe still runs third-party code; the product must describe its
boundary accurately rather than claim that no browser code runs.
References: [hook type contract](../../raiker/hooks/contracts.py),
[MCP Apps in KNOWN_LIMITS](../architecture/KNOWN_LIMITS.md#boundaries-raiker-chose),
[DEC-23](TESTING.md).

## Personal-agent direction — 2026-10-07

The owner accepted the [personal-agent architecture](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
inspired by reference personal agent, external hosted assistant, reference platform and reference personal agent. New durable goals,
context, proactivity, outcome verification and reviewed learning work is owned
by [PAA-01–PAA-11](PERSONAL_AUTONOMOUS_AGENT_SPEC.md). Existing items in
this ledger keep their status, dependencies and evidence; accepting the target
does not close a defect or mark an ADD shipped. Browser ADD-23, off-machine
ADD-11, memory ADD-25 and self-improvement ADD-05/06 retain their own boundaries.

Personal-agent release claims require the relevant PA-S scenarios and existing
CR evidence gates. Preserve capability defaults, quiet-hours DEC-21a, accepted
Git OAuth scope, model choice and coding quality. New observations go to the
proper defect/evidence ledger; do not duplicate the PAA backlog here.
