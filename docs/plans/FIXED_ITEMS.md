Warning: truncated output (original token count: 581430)
... 1277142 bytes omitted ...

# Fixed items

## FIXED-1283 — Managed llama.cpp selected a source-only release as a runtime download

**Observed.** The managed llama.cpp installer selected GitHub's newest stable
release even when it published source archives only. The live engine job then
failed because no platform runtime archive existed.

**Fixed.** PR #246 selects the newest stable release that has an appropriate
runtime archive. The live `llama-cpp.yml` jobs passed on Windows, macOS and
Linux at `aff48e7`.

**Evidence.** The PR #246 GitHub Actions run and
`tests/test_llama_cpp_releases.py`. CUDA/Vulkan owner-machine runs and
fresh signed-installer evidence remain release requirements, not closure
evidence for this defect.

## FIXED-1284 — Beta feedback and runtime state were not clear from every page

**Observed.** Beta feedback lived only inside Settings, so the shell gave no
visible indication that the user was on a beta or where to report an issue.
Models, Tasks and Runtime also began their state labels with unrelated backend
words, forcing users to interpret each page separately.

**Fixed.** The top bar now has a keyboard-reachable **Beta** link to Settings
→ General → Beta feedback. `web/src/lib/betaStatus.ts` owns the five beta
states (*Ready*, *Working*, *Needs you*, *Unavailable*, *Failed*). Models,
Tasks, Sessions and Runtime show that state first while retaining the exact
measured detail after it.

**Evidence.** `betaStatus.test.ts`, `Topbar.test.ts`, `TasksView.test.ts`,
`ModelsView.test.ts` and `SessionsView.test.ts`: 147 focused tests passed;
`npm run check`, `npm run lint` and `npm run build` passed. The retained
browser scenario is `web/e2e/beta-ui-live.spec.ts` (`RT-BETA-UX-01`); it is
still required on the release candidate.

## Windows sandboxed runs were one at a time, so background runs were impossible

The restricted account's grant covered one copy for one run behind a
machine-wide lock, so a background run would have held every other command.
Runs in the same copy now overlap (a dev server beside a test run); a run in a
different copy waits for the copy's last run, so the account still holds at
most one copy at a time. Each run keeps a holder file open without sharing in
the owner's profile, which the account cannot write, and a crashed run's holder
is pruned. Background runs are now offered on Windows. Measured on Windows 11:
same-copy run started in 1.7 s beside a running one, another copy waited for
it, no grant was left behind, and killing the runner killed the account's
process tree. Covered by `native/raiker-command-runner/tests/windows_account.rs`
and `tests/test_command_backends.py`.

## Command hooks were refused everywhere

Workspace command hooks refused with `native_sandbox_required` because the only
launcher ran them on the host. A hook's script now runs alone in a throwaway
folder in the native sandbox, with the event on its stdin and no network: it
can decide from the event but cannot read or change the project, Raiker's
state or anything else. A host without an enforced boundary still refuses the
hook, and an enforcing hook that cannot run still needs the owner's decision.
Hooks reuse a probe at most 30 seconds old, because they fire on every tool
call. Measured on Windows 11: a real hook could not see a file in the project
and its decision came back. Covered by `tests/test_command_hook_isolation.py`.

## Sandboxed commands could not run in the background or with a terminal (Linux)

On Linux, where the probe measures descendant reaping inside Bubblewrap,
`background_run` and interactive runs now work in the sandbox: Raiker hands the
runner a pseudo-terminal and bwrap passes it through, with `--new-session`
keeping the command from injecting terminal input. Stopping the run, or Raiker
exiting, takes the whole PID namespace down. Windows and macOS keep refusing by
name (see `TO_BE_FIXED.md`). Covered by
`tests/test_command_backends.py` and the real-terminal test in
`native/raiker-command-runner/tests/linux_probe.rs`.

## Sandboxed commands could not download packages

The native boundary denied all network, so `pip install`, `npm install`,
`cargo fetch` and `git clone` could not run. The owner can now allow downloads
from a host list (off by default). Each run gets its own authenticated proxy,
and the OS makes it the only route: a loopback bridge into the private network
namespace on Linux, a single-port Seatbelt rule on macOS, and the restricted
account's firewall on Windows. Measured end-to-end on Linux and Windows; macOS
still needs a run. The proxy now checks the allow-list before resolving a name,
which closes a DNS covert channel in the earlier proxy. Covered by
`tests/test_command_egress_runtime.py`, `tests/test_native_egress.py`,
`native/raiker-command-runner/tests/linux_probe.rs` and
`web/src/lib/views/settings/CommandDownloads.test.ts`.

## File edits and commands worked on two different trees

File tools wrote the real project while commands ran in a copy taken at the
first command, so a test run missed the edit just made and a formatter's output
was invisible to the next read. A session now has one task tree. A project
turn binds its session to the project root, and the first write or command
takes one copy of the whole project; every read, write, edit, patch, grep,
glob and command cwd inside the project then resolves into that copy, under
the same names, policy and confinement as before. The project changes only
when the owner applies the reviewed copy. An approved write executed after its
turn follows the conversation's session (`origin_session_id`), so approval
cannot write around the copy. A link a sandboxed command plants in the copy is
never followed (`task_copy_link`), and a copy wider than one the session
already holds is refused (`task_copy_scope_conflict`) instead of splitting the
work. Turns without a project keep the old behaviour until a command makes a
copy, then follow it. Covered by `tests/test_task_tree.py`.

## Windows builds could not run in the AppContainer sandbox

AppContainer blocked Node (`EPERM: lstat 'C:\\'`), Git, MSYS tools and
virtualenv Python. Windows build commands now run as a dedicated restricted
local account (`RaikerSandbox`) set up once with the owner's approval, inside a
copy under `C:\\RaikerSandbox`, in a Job Object with UI restrictions and an
outbound firewall block. Measured on the owner's PC: every probe observation
enforced, the toolchains run, and profile, data-drive and network escapes are
refused. Gaps remain listed in `TO_BE_FIXED.md`.

## Local Git could run repository filter programs; diff, commit and worktrees were blocked

A `.gitattributes` line names a filter driver; the program it runs comes from
Git configuration, and `status`, `diff`, `add`, `switch` and `worktree add` ran
it on the host. Every local Git invocation (`run_git` and the governed `_git`)
now passes `-c filter.<driver>.clean= / smudge= / process=` and
`required=false` for each configured driver, so no filter program can run;
`core.fsmonitor` and hooks were already off. A positive control showed the
configured driver ran without these overrides and never with them. This
replaces the interim refusals: working-tree diff, untracked-file diffs, commit
previews and commits, branch creation from a base and task worktrees work
again, and `tests/test_local_git_environment.py` asserts each succeeds without
the filter starting. A diff Git refuses is still never reported as a clean
review. Agent code no longer touches a project's `.git` at all; it runs in a
disposable copy without one.

## Native commands ran against the owner's project instead of a disposable copy

Governed commands now run in a per-session copy of their working folder, kept
outside the Raiker workspace. Nothing reaches the project until the owner
applies the exact change set they reviewed in Build; a stale review, an owner
edit made after the snapshot, an active run, a link or a nested `.git`/`.raiker`
is refused, and a failed promotion restores every original. Discard leaves the
project unchanged. Covered by `tests/test_task_workspaces.py`,
`tests/test_task_workspace_api.py`, `tests/test_command_backends.py` and
`web/src/lib/components/TaskWorkspaceReview.test.ts`, plus a real Windows
AppContainer run. Network mediation, background/PTY execution and toolchain
provisioning remain open in `TO_BE_FIXED.md`.

## Docker and Podman removed as Raiker execution dependencies

Raiker no longer invokes Docker or Podman. Removed: the persistent container
command backend, the container tool bridge, `container_execution_cap`, the
Docker plugin runtime (`plugin_sandboxed_runtime_cap`) and image pull
(`plugin_sandbox_image_pull_cap`), the Docker model-conversion runner,
`containers/**`, the container definition and image-scan CI checks, and the
container options in Settings. Upgrades are safe: a stored container profile is
listed as *retired*, refuses with `container_environment_retired`, is never
converted to host execution, and can be removed with its command history kept;
a tool an owner assigned to it is refused rather than moved. Covered by
`tests/test_command_backends.py`, `tests/test_execution_environments.py`,
`tests/test_execution_profiles.py` and `tests/test_tool_broker.py`. This does
not make native execution available; see the release blockers in
`TO_BE_FIXED.md`.

## Windows read-only protection bypassed by an all-packages grant

Measured locally and on `windows-2025`: with `ALL APPLICATION PACKAGES:(M)` on
`.git`, a sandboxed process wrote into `.git` despite the capability deny entry,
because Windows ignores capability SIDs in deny entries during the AppContainer
access check. The runner now refuses to launch when a protected path grants
`ALL APPLICATION PACKAGES` or `ALL RESTRICTED APPLICATION PACKAGES` any write
right (read-only paths) or any right (masked paths). The adversarial test in
`native/raiker-command-runner/tests/windows_probe.rs` passes locally and in CI.
Explicit grants on files below the protected directory are not scanned.

## Seatbelt profile allowed signals to and services outside the sandbox

The macOS profile allowed unrestricted `signal` and `mach-lookup`, so a command
could signal any of the owner's processes or ask launchd services to act
outside the sandbox. Signals and process inspection are now limited to the same
sandbox and Mach lookups to a named allowlist; unit tests assert both. macOS
also no longer requests `RLIMIT_AS`, which XNU rejects with EINVAL (measured on
`macos-15`); memory is reported unenforced there rather than every launch
failing. Real Seatbelt enforcement evidence is still pending.

## Native boundary helpers could be selected from an untrusted search path

The Unix runner selects Bubblewrap and Seatbelt only from fixed system paths,
requires root-owned, non-writable executable and directory components, and
rejects a symlink in an untrusted directory. The Windows probe resolves its
route utility from the system directory. Linux tests exercise fake helper
rejection and real Bubblewrap execution; Windows tests exercise the system
route lookup. This does not replace signed runner verification or the other
open sandbox controls. Unix changes are in checkpoint `f9329835`.

## Native runner policy injection and unrestricted root workspace

Seatbelt profile generation rejects unrepresentable path characters before
launch, preventing paths from injecting profile expressions. Runner filesystem
validation also rejects filesystem and Windows drive roots as workspaces.
Rust unit tests exercise the rejection paths on Linux and Windows. These fixes
do not establish a disposable workspace or prove macOS enforcement.

## Unix runner deadline ownership and Linux host configuration exposure

The Unix runner handles deadline termination in the child-owner wait loop,
without a detached PID-targeting watchdog. Bubblewrap no longer exposes whole
host `/etc`, `/opt` or `/nix` trees. Linux WSL integration tests exercise an
early exit, deadline termination and denial of a host `/etc` read with an
outside positive control. Linux helper identity, task-wide quotas and other
filesystem protections remain open.

## Native runner policy parser silently accepted malformed restrictions

The runner rejects lexical parent traversal, malformed protected-path lists,
invalid policy field types and out-of-range resource limits instead of silently
dropping or widening them. Rust policy tests cover these inputs. This is parser
validation only; symlink containment and OS enforcement remain open.

## Uncontained checkout filters in task worktree and cross-base branch creation

Task worktree creation and branch creation from an explicit base now refuse
until Git checkout can run inside a verified native boundary. Real Git tests in
`tests/test_local_git_environment.py` demonstrate that both previous paths
started a configured smudge filter; the refusal prevents that launch. Branch
creation at HEAD remains available in the tested scenario. This is containment,
not a completed sandbox or a restoration of task-worktree functionality.

## Workspace Git configuration used as global configuration

The sanitized process environment now points Git's global configuration at the
OS null device and disables system configuration, including after extra
environment values are merged. `tests/test_sandbox_git_config.py` verifies with
real Git that an agent-written workspace `.gitconfig` is not read as global
configuration. Repository-local configuration and other launch paths remain
subject to the open native sandbox migration.

## Agent Git diff external-driver execution

The agent-facing `run_git` diff path now disables external diff and textconv
drivers and refuses unsafe diff arguments and escaping pathspecs. A control run
showed the former path could launch an external driver; regression coverage is
in `tests/test_local_git_environment.py`. This fixes that specific path, not
other Git subprocesses or the native sandbox migration as a whole.

Every defect and gap that has been **closed**, with the evidence that closed
it. Split out of [`TO_BE_FIXED.md`](TO_BE_FIXED.md) so that document reads as
what it is named for — the open work — while the record of what was fixed, and
why it was fixed the way it was, stays intact and citable here.

Nothing was rewritten in the move. Each entry keeps its original number, its
observation, its root cause, and the user-interface outcome that had to be true
before it could be called closed. An entry that superseded or was superseded by
another says so in place.

The security posture these fixes answer to — **owner-authoritative and
monitored, not prevention-by-restriction** — is stated at the top of
[`TO_BE_FIXED.md`](TO_BE_FIXED.md) and in
[`docs/architecture/SECURITY_AND_POLICY.md`](../architecture/SECURITY_AND_POLICY.md).

Evidence: `screenshots/working/` (verified behaviour),
`screenshots/not-working/` (the defects as found).

## Release packaging maintenance

### FIXED-RELEASE-07 — the artifact download still ran on Node.js 20

**Fixed 2026-10-26, reported by the owner from the Desktop package run.** GitHub
warned that `actions/download-artifact@634f93cb…` targets Node.js 20 and was
being forced onto Node.js 24. The pin was v5.0.0, annotated *(Node 24)* in both
workflows; its `action.yml` says `node20`, and so does v6.0.0. FIXED-RELEASE-02
had counted it as moved. All six uses in `desktop-package.yml` and
`release.yml` now pin v7.0.0 (`37930b1c…`, December 2025), the first release
whose `action.yml` says `node24`; its only change from v6 is that runtime, so
the inputs (`name`, `pattern`, `path`) behave as before. The other pinned
actions (`checkout`, `setup-node`, `setup-python`, `upload-artifact`) were each
read at their pinned commit and declare `node24`. `tests/test_release_workflow.py`
passes.

### FIXED-RELEASE-06 — seven workflows became three

**Fixed 2026-10-19, at the owner's request.** `web.yml`, `desktop.yml`,
`licensing.yml` and the new Build fault workflow are now jobs in `ci.yml` (**Web
UI**, **Electron shell**, **Licensing and SBOM**, **Build faults**), so one CI
run on each pull request and push to `main` shows every gate. The web job loses
its path filter and runs on every change — a superset of the GCR-15 contract
paths `tests/test_web_workflow.py` still checks. `desktop-package.yml` stays its
own workflow because `release.yml` calls it per platform; `release.yml` stays
manual. `docs/architecture/VERIFICATION_PLAN.md` describes the three.

### FIXED-RELEASE-05 — the README explains running Raiker under WSL2 and on a VPS

**Fixed 2026-10-19.** The README gains *Running Raiker under WSL2 or on a VPS*:
WSL2 install, building inside the Linux file system, reaching the loopback host
from Windows, model and credential notes; a VPS as an unprivileged user under
systemd, bound to loopback and reached through an SSH tunnel, or bound to a
private VPN address with `--allow-public` and a hardened `RAIKER_OWNER_TOKEN`.
Writing it found that a reverse proxy pointed at `127.0.0.1` would make remote
requests look local; the README warns against it and
BUG-347 recorded the defect, closed as
[FIXED-1264](#fixed-1264--a-reverse-proxy-on-the-same-machine-made-every-remote-request-look-local-bug-347).

### FIXED-RELEASE-04 — a draft release carries one installer per platform, named for the platform

**Fixed 2026-10-19.** The last beta draft attached every installer format with
their manifests, checksums and smoke reports, and unsigned builds were named
`-unsigned`. The owner asked for one artefact per platform and no "unsigned"
in names. `raiker.app.desktop_release.release_asset_names` now chooses five
files — Windows x86-64 and Arm `setup.exe` (Arm is the x86-64 program tested on
a Windows on Arm runner, as ADR-0003 decided), macOS Apple-silicon `.dmg`,
Linux x86-64 and ARM64 `.AppImage` — and `scripts/select_release_assets.py`
copies them under platform names with a `SHA256SUMS.txt` whose contents go in
the release notes. Both draft jobs attach only those five. Every format is
still built, installed and tested on every run. Filenames no longer carry
`-unsigned`; signing state stays in `installation.json` and the manifest.
`tests/test_desktop_release.py` and `tests/test_release_workflow.py` pin it.

### FIXED-RELEASE-03 — the README identity check followed the owner's wording

**Fixed 2026-10-19.** The owner removed "local-first" from the README's opening
description (`bc54a63`), and `scripts/validate_documentation_truthfulness.py`
still required the old phrase, which turned CI's Python job red on the next
push (1 failed, 7142 passed). The validator now requires "personal autonomous AI
agent", the identity the README states; `tests/test_documentation_validators.py`
passes.

### FIXED-RELEASE-02 — GitHub Actions and JavaScript builds use Node.js 24

**Fixed 2026-10-19.** GitHub Actions checkout, setup, upload and download
actions now use their Node.js 24-compatible releases. The web and desktop
workflows build with Node.js 24, and the three JavaScript packages declare
Node.js 24 or newer in their engine requirements. No release workflow was
dispatched for this maintenance change.

### FIXED-RELEASE-01 — unsupported Intel macOS desktop target removed

**Fixed 2026-10-19.** The desktop release matrix, target registry, installer
guides, architecture decision, acceptance matrix and beta release notes now
ship macOS Apple-silicon artifacts only. The headless payload target list was
left unchanged. Focused release tests passed after the matrix and registry
were made identical.

**Those two capture sets are no longer stored in the repository.** They were
removed on 2026-09-06 to stop carrying roughly a hundred megabytes of binaries
in the tree. Entries below still name the capture each observation came from,
as a plain filename rather than a link, so the record of *what was photographed*
survives even though the photograph does not. A filename in this document is
therefore a reference to evidence that was taken and reviewed at the time, not a
file you can open. The two capture sets that remain — `screenshots/pages/` and
`screenshots/widths/` — are still in the tree and still linked.

| ID | Severity | Area | Status |
|---|---|---|---|
| [FIXED-01](#fixed-01--model-connection-showed-a-raw-reason-code-with-no-way-to-act-on-it) | High | Models | Fixed |
| [FIXED-02](#fixed-02--context-meter-showed-0--nan-nan-token-counts-stripped-from-the-audit-log) | High | Chat / API redaction | Fixed |
| [FIXED-03](#fixed-03--no-token-or-cost-accounting-models-showed-a-meaningless-percentage) | Medium | Models / Chat / Build | Fixed |
| [FIXED-04](#fixed-04--chat-had-no-conversation-memory-at-all-was-bug-02-critical) | **Critical** | Chat orchestration | Fixed (was BUG-02) |
| [FIXED-05](#fixed-05--three-separate-walls-in-front-of-a-provider-the-owner-had-already-chosen) | High | Models / policy | Fixed |
| [FIXED-06](#fixed-06--markdown-is-not-rendered-in-chat) | High | Chat / Build rendering | Fixed (was BUG-03) |
| [FIXED-07](#fixed-07--over-broad-redaction-destroyed-legitimate-assistant-text-and-chat-titles-was-bug-04) | High | API redaction | Fixed (was BUG-04) |
| [FIXED-08](#fixed-08--nothing-in-the-app-could-actually-write-a-file-was-bug-06) | **Critical** | Approvals / file output | Fixed (was BUG-06) |
| [FIXED-09](#fixed-09--the-agent-stopped-dead-at-its-first-write-was-gap-build-b2) | **Critical** | Build / Chat agent loop | Fixed (was GAP-BUILD B2) |
| [FIXED-10](#fixed-10--no-file-inspector-attachment-chips-were-not-interactive) | Medium | Chat / attachments | Fixed (was BUG-07) |
| [FIXED-11](#fixed-11--redaction-destroyed-every-server-issued-path-and-url) | High | API redaction | Fixed (found while fixing BUG-07) |
| [FIXED-12](#fixed-12--chat-transcript-export-path-was-bug-08-superseded-by-fixed-19) | Medium | Export | Superseded by FIXED-19 (was BUG-08) |
| [FIXED-13](#fixed-13--a-background-agent-run-reported-task-failed-with-no-user-facing-reason-was-bug-09) | Medium | Tasks | Fixed (was BUG-09) |
| [FIXED-14](#fixed-14--redaction-destroyed-every-server-issued-record-id) | High | API redaction | Fixed (found while fixing BUG-09) |
| [FIXED-15](#fixed-15--task-runs-polluted-recent-chats-was-bug-10) | Low | Chat / Tasks | Fixed (was BUG-10) |
| [FIXED-16](#fixed-16--a-surface-blocked-by-runtime-mode-did-not-say-so-was-bug-11) | Medium | Permissions | Fixed (was BUG-11) |
| [FIXED-17](#fixed-17--mcp-servers-could-not-be-used-by-the-agent-was-bug-12) | High | MCP | Fixed (was BUG-12) |
| [FIXED-18](#fixed-18--confirmation-token-is-explained-in-the-step-up-dialog-was-bug-13) | Low | Permissions | Fixed (was BUG-13) |
| [FIXED-19](#fixed-19--chat-transcripts-were-offered-as-files-even-when-no-file-existed) | Medium | Chat / file output | Fixed (found while fixing BUG-13) |
| [FIXED-20](#fixed-20--approved-chat-and-build-files-could-be-lost-from-their-session) | High | Chat / Build file retention | Fixed (found while fixing BUG-14) |
| [FIXED-21](#fixed-21--ci-validation-had-stale-import-and-typing-debt) | Low | CI quality gates | Fixed (found while verifying BUG-14) |
| [FIXED-22](#fixed-22--repeated-file-recording-could-duplicate-a-session-artifact) | Low | Chat / Build file retention | Fixed (found while fixing BUG-14) |
| [FIXED-23](#fixed-23--builds-edit-and-patch-tools-overwrote-whole-files-was-gap-build-b3) | High | Build / patch application | Fixed (was GAP-BUILD B3) |
| [FIXED-24](#fixed-24--readme-known-limits-described-already-shipped-behaviour-as-missing) | Low | Documentation / known limits | Fixed (found while verifying FIXED-23) |
| [FIXED-25](#fixed-25--local-repository-references-used-host-native-separators) | Low | Build / cross-platform paths | Fixed (found while verifying FIXED-23) |
| [FIXED-26](#fixed-26--the-cost-popover-test-asserts-a-different-currency-label-than-the-ui-was-bug-14) | Low | Chat / cost presentation tests | Fixed (was BUG-14) |
| [FIXED-27](#fixed-27--github-actions-declared-the-deprecated-node-20-runtime-was-bug-15) | Low | CI / action runtime | Fixed (was BUG-15) |
| [FIXED-28](#fixed-28--web-validation-emitted-repeated-node-localstorage-warnings-was-bug-16) | Low | Web test runtime | Fixed (was BUG-16) |
| [FIXED-29](#fixed-29--b3-single-target-patches-rejected-common-unified-diff-forms) | Medium | Build / patch application | Fixed (B3 single-target expansion) |
| [FIXED-30](#fixed-30--model-api-keys-disappeared-after-restart) | Medium | Models / credential persistence | Fixed |
| [FIXED-31](#fixed-31--chat-and-build-composers-lacked-a-consistent-finishing-pass) | Medium | Chat / Build composer | Fixed |
| [FIXED-32](#fixed-32--web-development-dependencies-had-known-security-advisories-was-bug-17) | High | Web development dependencies | Fixed (was BUG-17) |
| [FIXED-33](#fixed-33--python-tests-emitted-a-starlettehttpx-deprecation-warning-was-bug-18) | Low | Python test dependencies | Fixed (was BUG-18) |
| [FIXED-34](#fixed-34--one-approval-could-not-govern-an-atomic-multi-file-patch-b3-expansion) | High | Build / multi-file patch application | Fixed (B3 expansion) |
| [FIXED-35](#fixed-35--settings-and-models-exposed-implementation-detail-and-visual-noise) | Medium | Settings / Models | Fixed |
| [FIXED-36](#fixed-36--composers-had-no-raiker-owned-english-checking-path) | Medium | Writing quality | Fixed (optional local integration) |
| [FIXED-37](#fixed-37--connector-operations-and-outbound-bodies-were-invisible-c2) | High | Chat / connector actions | Fixed (C2 inventory and preview) |
| [FIXED-38](#fixed-38--connector-manifests-can-declare-bounded-operation-scoped-compensation-bug-19) | Medium | Chat / connector compensation | Fixed (was BUG-19) |
| [FIXED-39](BUILD_WORKSPACE_SPEC.md) | High | Build / parallel tool execution | Fixed (was B4) |
| [FIXED-40](BUILD_WORKSPACE_SPEC.md) | High | Chat / document output | Fixed (was C1) |
| [FIXED-41](BUILD_WORKSPACE_SPEC.md) | High | Chat / connector execution | Fixed (C2 multiple-call expansion) |
| [FIXED-42](BUILD_WORKSPACE_SPEC.md) | High | Chat / cross-work recall | Fixed (was C3) |
| [FIXED-43](#fixed-43--chat-creates-first-class-docx-xlsx-pdf-and-markdown-artifacts-c1) | High | Chat / document output | Fixed (C1 format expansion) |
| [FIXED-44](#fixed-44--sessions-can-grant-a-bounded-command-feedback-channel-b5) | High | Build / command feedback | Fixed except host network containment (B5) |
| [FIXED-45](#fixed-45--generated-files-have-a-response-linked-preview-surface-c4c5) | Medium | Chat / file inspector and output | Fixed (C4/C5 validation and presentation) |
| [FIXED-46](#fixed-46--workbench-is-activity-aware-and-action-oriented) | Medium | Workbench | Fixed (activity-aware dashboard redesign) |
| [FIXED-47](#fixed-47--owner-granted-commands-have-kernel-enforced-network-isolation) | High | Build / command containment | Fixed (was BUG-20) |
| [FIXED-48](#fixed-48--settings-and-workbench-distinguish-preferences-from-governed-work) | Medium | Settings / Workbench | Fixed (settings and dashboard refinement) |
| [FIXED-49](#fixed-49--memory-knowledge-map-and-context-usage-expose-user-controls-first) | Medium | Memory / Knowledge Map / context window | Fixed (visual control redesign) |
| [FIXED-50](#fixed-50--local-model-context-capacity-is-discovered-from-the-active-runtime) | High | Local models / context capacity | Fixed (runtime capacity discovery) |
| [FIXED-51](#fixed-51--force-simulation-rebuilt-itself-on-every-animation-tick) | High | Knowledge Map / force simulation | Fixed (found during live Playwright verification) |
| [FIXED-52](#fixed-52--knowledge-map-initially-bypassed-raikers-shared-theme) | Medium | Knowledge Map / theme integration | Fixed (found during visual review) |
| [FIXED-53](#fixed-53--provider-pricing-is-synchronised-into-a-historical-registry) | Medium | Models / pricing | Fixed (was BUG-21) |
| [FIXED-54](#fixed-54--chat-and-build-export-a-transcript-and-print-as-a-document) | Medium | Chat / Build export | Fixed (was BUG-22) |
| [FIXED-55](#fixed-55--rendered-code-blocks-carry-daily-use-interaction-controls) | Low | Chat / Build code ergonomics | Fixed (was BUG-23) |
| [FIXED-56](#fixed-56--approval-resolution-in-another-tab-continues-chat) | High | Approvals / cross-tab continuation | Fixed (was BUG-24) |
| [FIXED-57](#fixed-57--the-shipped-model-profile-existed-as-two-divergent-copies) | Low | Models / shipped configuration | Fixed (found while fixing BUG-21) |
| [FIXED-58](#fixed-58--playwright-could-not-launch-the-pre-installed-browser) | Low | Web test runtime | Fixed (found while verifying BUG-21) |
| [FIXED-59](#fixed-59--scheduled-work-could-not-resume-after-its-approval-was-granted) | High | Tasks / approval continuation | Fixed (was BUG-25) |
| [FIXED-60](#fixed-60--image-inspection-had-no-zoom-pan-or-rotation-controls) | Low | File inspector / images | Fixed (was BUG-26) |
| [FIXED-61](#fixed-61--memory-and-file-provenance-could-not-open-the-exact-source-passage) | Medium | Memory / provenance | Fixed (was BUG-27) |
| [FIXED-62](#fixed-62--generated-artifacts-had-no-download-surface) | Medium | Chat / artifact download | Fixed (was BUG-28) |
| [FIXED-63](#fixed-63--raiker-had-five-runtimes-and-needed-one) | High | Runtime | Fixed (single runtime; no mode selection) |
| [FIXED-64](#fixed-64--the-build-composer-could-not-carry-a-file) | Low | Build / composer attachments | Fixed (was BUG-35) |
| [FIXED-65](#fixed-65--chat-build-and-the-workbench-composed-work-three-different-ways) | Medium | Composers / Chat, Build, Workbench | Fixed (shared composer) |
| [FIXED-66](#fixed-66--raiker-did-not-start-like-an-application-on-any-platform) | Medium | Distribution / cross-platform launch | Fixed (`raiker-app`) |
| [FIXED-67](#fixed-67--an-attached-file-did-not-look-like-the-file-it-was) | Medium | Composers / attachment presentation | Fixed (attached files look like files) |
| [FIXED-68](#fixed-68--governed-memory-lifecycle-is-complete-was-bug-29) | High | Memory / governed lifecycle | Fixed (was BUG-29) |
| [FIXED-69](#fixed-69--knowledge-map-source-review-and-persistence-are-available-was-bug-30) | Medium | Knowledge Map / sources and scale | Fixed (was BUG-30) |
| [FIXED-70](#fixed-70--owner-selected-ssh-and-daytona-execution-are-governed-was-bug-31) | High | Build / remote execution containment | Fixed (was BUG-31) |
| [FIXED-71](#fixed-71--local-context-capacity-refresh-and-administrator-overrides-ship-was-bug-33) | Medium | Local models / capacity administration | Fixed (was BUG-33) |
| [FIXED-72](#fixed-72--reloaded-chat-restores-the-parked-approval-was-bug-34) | Medium | Chat / restored approval state | Fixed (was BUG-34) |
| [FIXED-73](#fixed-73--attached-files-sit-outside-chat-and-build-speech-bubbles) | Low | Chat / Build attachment layout | Fixed |
| [FIXED-74](#fixed-74--the-standing-command-container-crashed-before-launch-on-windows) | Medium | Build / Windows container sandbox | Fixed (found during verification) |
| [FIXED-75](#fixed-75--capacity-history-order-was-unstable-for-same-timestamp-changes) | Low | Models / capacity history ordering | Fixed (found in GitHub CI) |
| [FIXED-76](#fixed-76--the-shipped-model-profile-copies-and-human-review-cadence-stay-in-step-was-bug-36) | Low | Models / shipped price review cadence | Fixed (was BUG-36) |
| [FIXED-77](#fixed-77--source-coordinates-identify-the-passage-inside-a-turn-was-bug-38) | Medium | Memory / source coordinates | Fixed (was BUG-38) |
| [FIXED-78](#fixed-78--daytona-budgets-reconcile-cumulative-provider-spend-was-bug-42) | Medium | Cloud execution / billing | Fixed (was BUG-42) |
| [FIXED-79](#fixed-79--knowledge-map-and-export-dialogs-have-clean-accessibility-semantics-was-bug-43) | Low | Web / accessibility | Fixed (was BUG-43) |
| [FIXED-80](#fixed-80--schedule-carries-and-presents-attachments-like-chat-and-build) | Low | Schedule / attachments | Fixed (consistency improvement) |
| [FIXED-81](#fixed-81--submission-waits-for-attachment-uploads-on-every-composer) | Medium | Chat / Build / Workbench / Tasks | Fixed (found during live verification) |
| [FIXED-82](#fixed-82--live-axe-findings-are-closed-in-export-and-knowledge-map) | Medium | Export / Knowledge Map accessibility | Fixed (found by live axe verification) |
| [FIXED-83](#fixed-83--chat-export-has-deterministic-keyboard-activation) | Medium | Chat / export keyboard activation | Fixed (found during live verification) |
| [FIXED-84](#fixed-84--accessibility-test-dependencies-pass-the-licensing-gate) | Low | CI / dependency licensing | Fixed (found during workflow verification) |
| [FIXED-85](#fixed-85--a-settings-choice-made-while-the-page-was-still-loading-was-silently-discarded) | Medium | Settings / concurrent load | Fixed (found while verifying BUG-37) |
| [FIXED-86](#fixed-86--the-visual-language-is-finished-and-written-down-was-bug-37) | Low | Design system / visual language | Fixed (was BUG-37) |
| [FIXED-87](#fixed-87--an-approved-scheduled-run-continues-immediately-was-bug-39) | Low | Scheduler / continuation latency | Fixed (was BUG-39) |
| [FIXED-88](#fixed-88--raiker-app-installs-registers-controls-and-removes-itself-was-bug-40) | Medium | Distribution / host lifecycle | Fixed (was BUG-40, less packaging — closed by FIXED-92) |
| [FIXED-89](#fixed-89--e2ecomposerspects-matches-the-app-and-ci-runs-it-was-bug-41) | Low | Web / e2e regression suite | Fixed (was BUG-41) |
| [FIXED-90](#fixed-90--terminal-approval-authenticates-previews-executes-and-continues-was-bug-32) | Medium | Terminal / approval execution | Fixed (was BUG-32) |
| [FIXED-91](#fixed-91--a-worker-pays-sqlcipher-key-derivation-once-per-workspace-was-bug-45) | Low | Storage / per-request key derivation | Fixed (was BUG-45) |
| [FIXED-92](#fixed-92--a-manually-triggered-release-pipeline-and-a-signed-update-channel-was-bug-44) | Medium | Distribution / release pipeline and signed updates | Fixed (was BUG-44, less the wizard and tray — see BUG-48) |
| [FIXED-93](#fixed-93--a-provider-test-result-appears-only-under-the-provider-that-ran-it-was-bug-47) | Low | Models / provider test feedback | Fixed (was BUG-47) |
| [FIXED-94](#fixed-94--build-had-no-plan-for-the-work-in-front-of-it-was-b6) | High | Build / turn plan state | Fixed (was B6) |
| [FIXED-95](#fixed-95--the-model-could-not-delegate-a-wide-search-was-b7) | High | Build / model-spawned subagents | Fixed (was B7) |
| [FIXED-96](#fixed-96--a-connected-mcp-server-did-not-say-whether-the-agent-could-use-it-b8-review) | Medium | Extensions / MCP agent reachability | Fixed (B8 review; found the surface was silent) |
| [FIXED-97](#fixed-97--an-event-the-runtime-emitted-but-never-declared-killed-the-turn) | High | Runtime / undeclared event types | Fixed (found during B6 live testing; B4's drop evidence killed the turn) |
| [FIXED-98](#fixed-98--tools-were-advertised-to-the-model-that-policy-always-denied) | High | Policy / advertised tools with no verdict | Fixed (found while implementing B6/B7) |
| [FIXED-99](#fixed-99--a-policy-refusal-in-a-fresh-batch-dropped-the-calls-behind-it-was-bug-52) | Medium | Runtime / batched policy refusal | Fixed (was BUG-52) |
| [FIXED-100](#fixed-100--the-sqlcipher-connection-cache-never-let-a-workspace-go-was-bug-50) | Medium | Storage / connection cache holds every workspace open | Fixed (was BUG-50) |
| [FIXED-101](#fixed-101--the-agent-could-not-read-a-page-it-was-told-to-read-was-b12c7) | High | Chat / Build — governed web access | Fixed (was B12/C7) |
| [FIXED-102](#fixed-102--a-running-turn-could-not-be-stopped-or-corrected-was-b17c13) | High | Chat / Build — stop and steer a running turn | Fixed (was B17/C13) |
| [FIXED-103](#fixed-103--readmes-known-limits-described-behaviour-that-has-since-shipped-was-bug-58) | Low | Documentation / README known limits are stale | Fixed (was BUG-58) |
| [FIXED-104](#fixed-104--the-context-bundles-fixed-capability-flags-talked-a-model-out-of-tools-it-can-use-was-bug-57) | Medium | Context / stale capability flags mislead the model | Fixed (was BUG-57) |
| [FIXED-105](#fixed-105--the-user-guides-known-limits-were-stale-in-every-line-was-bug-61) | Medium | Documentation / the user guide's "Known limits" are entirely stale | Fixed (was BUG-61) |
| [FIXED-106](#fixed-106--the-agent-could-propose-a-task-it-could-never-create-was-bug-62) | Medium | Tasks / an approved task is really created | Fixed (was BUG-62) |
| [FIXED-107](#fixed-107--an-answer-drawn-from-the-owners-own-material-named-no-source) | High | Chat / Build — source citations and the passage used | Fixed (was C6 and the last of C4) |
| [FIXED-108](#fixed-108--a-deleted-conversation-left-its-plan-its-controls-and-its-sources-behind) | Medium | Storage / session-keyed rows outliving the conversation | Fixed (found while implementing FIXED-107) |
| [FIXED-109](#fixed-109--the-agent-could-describe-a-change-it-could-neither-commit-nor-propose) | High | Build / Chat — the governed git write path | Fixed (was B11) |
| [FIXED-110](#fixed-110--the-git-tools-could-not-reach-a-repository-connected-as-a-sub-folder) | Low | Build / git tools and the selected repository | Fixed (was BUG-66) |
| [FIXED-111](#fixed-111--a-committed-branch-could-not-be-pushed) | Medium | Build / Chat — the governed push | Fixed (was BUG-67) |
| [FIXED-112](#fixed-112--a-proposal-the-runtime-had-already-refused-was-raised-as-a-decision) | Medium | Runtime / an unperformable proposal raised as a decision | Fixed (found while verifying FIXED-111) |
| [FIXED-113](#fixed-113--every-turn-started-cold-the-repository-had-no-index) | High | Build / Chat — the repository code map | Fixed (was B9) |
| [FIXED-114](#fixed-114--build-showed-repository-state-as-it-stood-before-a-visit-to-permissions) | Low | Build / stale repository state after a visit elsewhere | Fixed (found while verifying FIXED-113) |
| [FIXED-115](#fixed-115--a-shipped-skill-check-failed-after-compileall-which-ci-itself-runs-was-bug-56) | Low | Tests / a shipped-skill check breaks after `compileall` | Fixed (was BUG-56) |
| [FIXED-116](#fixed-116--a-fresh-workspace-silently-defaulted-to-llamacpp-instead-of-ollama) | High | Models / first-run default | Fixed (Ollama `gemma4:31b-cloud` is the visible and runtime default) |
| [FIXED-117](#fixed-117--container-tools-could-not-complete-a-cold-real-docker-run) | High | Container tools / cold start and stdin bridge | Fixed (found during ADD-01 live Docker verification) |
| [FIXED-118](#fixed-118--the-execution-environment-badge-linked-to-a-route-that-did-not-exist) | Medium | Web / execution-environment deep link | Fixed (found during ADD-01 Playwright verification) |
| [FIXED-119](#fixed-119--offline-gateway-tests-changed-meaning-when-local-ollama-was-running) | Low | Tests / live Ollama leaked into offline scenarios | Fixed (found during ADD-01 baseline verification) |
| [FIXED-120](#fixed-120--machine-identity-chips-overwhelmed-the-activity-actor-column) | Low | Activity / machine identity density | Fixed (found during ADD-03 screenshot review) |
| [FIXED-121](#fixed-121--a-passing-export-test-emitted-a-delayed-jsdom-navigation-error) | Low | Web tests / export download navigation noise | Fixed (found during ADD-03 full verification) |
| [FIXED-122](#fixed-122--windows-host-status-checks-could-interrupt-the-process-they-inspected) | High | Windows host status / destructive PID probe | Fixed (found during ADD-03 full verification) |
| [FIXED-123](#fixed-123--plugin-execution-generated-an-unsupported-fallback-turn-id) | Medium | Plugin execution / invalid fallback turn id | Fixed (found during ADD-03 full verification) |
| [FIXED-124](#fixed-124--project-exports-reversed-events-created-in-the-same-second) | Medium | Project export / unstable same-second event order | Fixed (found during ADD-03 full verification) |
| [FIXED-125](#fixed-125--auto-and-skip-execution-replaced-the-machine-actor-with-the-owner) | High | Auto/skip runtime / human principal replaced the signed machine actor | Fixed (found during ADD-03 independent review) |
| [FIXED-126](#fixed-126--non-terminal-exits-leaked-active-machine-principals) | High | Machine identity / abnormal and delegated paths leaked active principals | Fixed (found during ADD-03 independent review) |
| [FIXED-127](#fixed-127--activity-hid-the-event-actor-behind-a-contextual-turn-identity) | Medium | Activity / contextual turn identity hid the literal event actor | Fixed (found during ADD-03 independent review) |
| [FIXED-128](#fixed-128--resume-rotation-could-rewrite-approval-identity-metadata) | High | Approvals / resume rotation rewrote proposal identity timestamps | Fixed (found during ADD-03 independent review) |
| [FIXED-129](#fixed-129--authority-matrix-ignored-failed-readiness-facts) | Low | Permissions / authority matrix ignored readiness failures | Fixed (found during ADD-03 independent review) |
| [FIXED-130](#fixed-130--approval-identity-metadata-overlapped-at-desktop-width) | Low | Approvals / identity metadata overlapped at desktop width | Fixed (found during ADD-03 screenshot review) |
| [FIXED-131](#fixed-131--concurrent-first-use-store-bootstrap-deadlocked-in-fts-repair) | High | SQLite bootstrap / concurrent first-use FTS rebuild deadlocked | Fixed (found in ADD-03 GitHub CI) |
| [FIXED-132](#fixed-132--linux-mypy-rejected-guarded-windows-process-apis) | Medium | Windows process probe / Linux MyPy rejected guarded ctypes APIs | Fixed (found in ADD-03 GitHub CI) |
| [FIXED-133](#fixed-133--a-new-users-first-message-failed-with-a-raw-reason-code) | High | First run / universal exact-model readiness and setup (BUG-69) | Fixed (2026-08-09 live round) |
| [FIXED-134](#fixed-134--redaction-corrupted-path-derived-local-model-ids) | High | Local library / redaction corrupted path-derived deployment IDs | Fixed (found in BUG-69 live download/deploy) |
| [FIXED-135](#fixed-135--model-activity-did-not-refresh-background-state) | Medium | Model Activity / background jobs never refreshed after mount | Fixed (found in BUG-69 screenshot review) |
| [FIXED-136](#fixed-136--managed-llamacpp-could-outlive-graceful-host-shutdown) | High | Managed llama.cpp / graceful host shutdown could leave the child alive | Fixed (found in BUG-69 shutdown verification) |
| [FIXED-137](#fixed-137--redaction-destroyed-an-approved-model-library-root) | High | API redaction / an unprefixed `path` field was destroyed | Fixed (found in GitHub CI after BUG-69) |
| [FIXED-138](#fixed-138--billing-exhaustion-was-reported-as-an-unreachable-provider) | High | Model readiness / an empty account balance was reported as an unreachable provider | Fixed (found in the BUG-69 parity review) |
| [FIXED-139](#fixed-139--the-readiness-gate-ignored-the-fallback-chain-the-runtime-uses) | High | Model readiness / the gate ignored the fallback chain the runtime actually tries | Fixed (found in the BUG-69 parity review) |
| [FIXED-140](#fixed-140--models-claimed-providers-were-set-up-and-test-proved-nothing) | High | Models UI / the page counted saved credentials as "set up" and Test proved nothing | Fixed (found in the BUG-69 parity review) |
| [FIXED-141](#fixed-141--three-models-tabs-were-unreachable-by-deep-link) | Medium | Models navigation / three tabs were unreachable by deep link and silently opened Providers | Fixed (found while splitting the Models page) |
| [FIXED-142](#fixed-142--enabling-web-fetch-made-every-turn-that-used-it-fail) | High | Runtime / a tool call that blocked the event loop killed its own turn | Fixed (was BUG-72) |
| [FIXED-143](#fixed-143--the-live-evidence-suite-could-not-reach-a-provider-card-at-all) | High | Live tests / the whole live evidence suite could not reach a provider card | Fixed (found while verifying FIXED-142) |
| [FIXED-144](#fixed-144--the-first-run-model-sheet-rendered-the-settings-page-underneath-it) | Low | Web / the first-run model sheet rendered Settings underneath it | Fixed (found while verifying FIXED-142) |
| [FIXED-145](#fixed-145--the-first-run-screen-was-titled-workbench) | Low | Web / the first-run screen was titled "Workbench" | Fixed (found in the 2026-08-10 visual sweep) |
| [FIXED-146](#fixed-146--the-knowledge-maps-count-pill-contradicted-its-own-empty-state) | Low | Knowledge Map / the count pill contradicted the empty state | Fixed (found in the 2026-08-10 visual sweep) |
| [FIXED-147](#fixed-147--the-knowledge-map-ignored-a-system-dark-preference) | Medium | Knowledge Map / the graph ignored a system dark preference | Fixed (found in the 2026-08-10 visual sweep) |
| [FIXED-148](#fixed-148--1-models-ready) | Low | Models / "1 models ready" | Fixed (found in the 2026-08-10 visual sweep) |
| [FIXED-149](#fixed-149--the-bug-47-live-scenario-expected-two-models-tabs-on-screen-at-once-was-bug-85) | Low | Live tests / the BUG-47 scenario expected two Models tabs on screen at once | Fixed (was BUG-85) |
| [FIXED-150](#fixed-150--sqlcipher-ran-out-of-locked-memory-and-locked-the-owner-out-was-bug-86) | **Critical** | Storage / SQLCipher ran out of locked memory and locked the owner out | Fixed (was BUG-86) |
| [FIXED-151](#fixed-151--the-audit-log-showed-nothing-though-governed-events-were-recorded-was-bug-87) | Medium | Observability / the audit log showed nothing though governed events were recorded | Fixed (was BUG-87) |
| [FIXED-152](#fixed-152--the-knowledge-maps-source-picker-browsed-the-whole-raiker-installation) | High | Knowledge Map / the source picker browsed the whole Raiker installation | Fixed (reported 2026-08-10) |
| [FIXED-153](#fixed-153--the-audit-logs-turn-identity-column-rendered-â) | Low | Observability / the audit log's turn-identity column rendered mojibake | Fixed (found while verifying FIXED-151) |
| [FIXED-154](#fixed-154--the-context-meter-read-nan-input--nan-output) | Medium | Chat / Build — context meter read `NaN input · NaN output` | Fixed (was BUG-68) |
| [FIXED-155](#fixed-155--builds-mode-chips-rewrote-global-decision-modes-with-no-step-up) | Medium | Build / mode chips rewrote global decision modes with no step-up | Fixed (was BUG-70) |
| [FIXED-156](#fixed-156--memory-could-never-be-written-from-chat-or-build) | Medium | Memory / a gated capability no turn could ever reach | Fixed (was BUG-71) |
| [FIXED-157](#fixed-157--a-conversation-could-end-saying-the-approved-action-was-not-executed) | Medium | Chat / a resumed turn could deny an execution that happened | Fixed (was BUG-73) |
| [FIXED-158](#fixed-158--the-advisor-model-was-never-readiness-checked) | Medium | Model readiness / the advisor model was never readiness-checked or surfaced | Fixed (was BUG-82) |
| [FIXED-159](#fixed-159--a-composer-permission-control-shipped-and-was-rendered-by-nothing) | Low | Web / a composer permission control shipped unused | Fixed (was BUG-63, closed with FIXED-155) |
| [FIXED-160](#fixed-160--a-throttled-read-reported-only-unavailable-429) | Low | Models / a throttled read reported only `Unavailable (429)` | Fixed (found while verifying FIXED-158 live) |
| [FIXED-161](#fixed-161--the-production-web-bundle-no-longer-exceeds-the-chunk-warning) | Low | Web build / the main production JavaScript chunk exceeded the 500 kB warning threshold | Fixed (was BUG-74) |
| [FIXED-162](#fixed-162--retry-cancellation-and-partial-cleanup-do-what-they-say) | Medium | Model activity / retry, cancellation and partial-file cleanup were record-only for some job types | Fixed (was BUG-75) |
| [FIXED-163](#fixed-163--a-failing-tool-or-provider-is-contained-not-retried-to-exhaustion) | Medium | Runtime / a failing tool or provider was retried until its budget ran out, every turn | Fixed (was BUG-76) |
| [FIXED-164](#fixed-164--anomaly-detection-and-containment-cover-every-capability) | High | Security monitoring / anomaly detection and containment covered MCP connections only | Fixed (was BUG-77) |
| [FIXED-165](#fixed-165--a-delegated-subagent-result-is-bound-to-the-spawn-that-produced-it) | Medium | Subagents / a delegated result carried no identity binding to the spawn that produced it | Fixed (was BUG-78) |
| [FIXED-166](#fixed-166--a-plugin-signature-states-what-it-actually-proved) | Medium | Plugins / a manifest signature was a presence marker by default and the owner was never told | Fixed (was BUG-79) |
| [FIXED-167](#fixed-167--the-genai-security-mapping-matches-shipped-code) | Low | Documentation / the GenAI mapping called the verifier a stub | Fixed (was BUG-80) |
| [FIXED-168](#fixed-168--untrusted-context-is-scanned-and-a-suspicious-source-is-named) | Low | Context / no prompt-injection scanning hook existed, though the security mapping requires one | Fixed (was BUG-81) |
| [FIXED-169](#fixed-169--readiness-has-an-owner-set-window-and-quiet-revalidation) | Low | Model readiness / one fixed five-minute TTL and no background revalidation | Fixed (was BUG-83) |
| [FIXED-170](#fixed-170--the-bug-69-live-acceptance-spec-runs-with-one-provider-key) | Low | Live tests / the BUG-69 acceptance spec could not run with a single provider key | Fixed (was BUG-84) |
| [FIXED-171](#fixed-171--windows-sqlcipher-memory-locking-is-crash-contained-and-explicit) | Medium | Storage / Windows locked memory | Fixed (was BUG-46) |
| [FIXED-172](#fixed-172--first-run-is-guided-and-the-desktop-host-has-a-native-tray) | Medium | Distribution / setup wizard and native tray | Fixed (was BUG-48) |
| [FIXED-173](#fixed-173--policy-configuration-no-longer-advertises-a-dead-deny-set) | Low | Policy / dead `denied_actions` configuration | Fixed (was BUG-51) |
| [FIXED-174](#fixed-174--every-governed-withheld-call-is-disclosed-by-the-runtime) | Low | Runtime / governed refusal destination and disclosure | Fixed (was BUG-59 and BUG-60) |
| [FIXED-175](#fixed-175--approving-task-creation-does-not-schedule-execution) | Low | Tasks / creation and execution intent | Fixed (was BUG-64) |
| [FIXED-176](#fixed-176--exported-transcripts-carry-a-portable-citation-ledger) | Low | Export / portable citation ledgers | Fixed (was BUG-65) |
| [FIXED-177](#fixed-177--ordinary-loopback-reads-no-longer-spend-the-public-dos-budget) | Low | Web / loopback and public-bind rate limits | Fixed (was BUG-88) |
| [FIXED-178](#fixed-178--a-connected-provider-credential-can-be-removed-in-the-app) | Low | Models / remove a provider credential in-app | Fixed (found during live verification) |
| [FIXED-179](#fixed-179--release-artifact-actions-are-pinned-immutably) | Low | CI / immutable release artifact actions | Fixed (was BUG-49) |
| [FIXED-180](#fixed-180--linux-ci-no-longer-stalls-with-every-test-store-memory-locked) | Medium | CI / Linux SQLCipher test throughput | Fixed (found during hosted verification) |
| [FIXED-181](#fixed-181--multi-call-answer-passes-are-separated-in-chat-was-bug-53) | Low | Chat / multi-call answer separation | Fixed (was BUG-53) |
| [FIXED-182](#fixed-182--the-live-end-to-end-model-stub-is-reproducible-was-bug-54) | Medium | Web e2e / checked-in deterministic model stub | Fixed (was BUG-54) |
| [FIXED-183](#fixed-183--chat-has-one-live-transcript-implementation-was-bug-55) | Low | Chat / disabled transcript implementation | Fixed (was BUG-55) |
| [FIXED-184](#fixed-184--context-compacts-automatically-at-90-former-known-limit) | High | Runtime / automatic context compaction | Fixed (former Known Limit) |
| [FIXED-185](#fixed-185--connected-providers-have-a-truthful-rolling-usage-view-former-known-limit) | Medium | Models / connected-provider rolling usage | Fixed (former Known Limit) |
| [FIXED-186](#fixed-186--concurrent-event-writers-preserve-jsonl-and-its-hash-chain) | High | Audit / concurrent event writers could tear JSONL and its hash chain | Fixed (found during final verification) |
| [FIXED-187](#fixed-187--a-turn-could-not-read-a-past-conversation) | **Critical** | Recall / a turn could not read a past conversation | Fixed (was MEM-01) |
| [FIXED-188](#fixed-188--ambient-recall-offered-the-eight-most-recent-chats-whatever-the-turn-was-about) | High | Context assembly / ambient recall offered the eight most recent chats | Fixed (was MEM-02) |
| [FIXED-189](#fixed-189--a-recalled-exchange-was-truncated-before-the-model-could-read-it) | Medium | Recall / a search result was truncated mid-sentence for the model | Fixed (found during the live round) |
| [FIXED-190](#fixed-190--the-code-map-found-declarations-and-nothing-that-used-them) | Medium | Build / the code map had no reference search | Fixed (was a README known limit) |
| [FIXED-191](#fixed-191--an-edit-failed-because-the-model-mis-transcribed-whitespace) | Medium | Build / matching failed on whitespace the model mis-transcribed | Fixed (was a README known limit) |
| [FIXED-192](#fixed-192--the-tray-drew-its-own-icon-and-the-appimage-shipped-an-empty-one) | Medium | Desktop / the tray drew its own icon and the AppImage shipped an empty one | Fixed |
| [FIXED-193](#fixed-193--eight-views-re-declared-the-same-control-styling-four-different-ways) | Low | Visual consistency / eight views re-declared the same control styling | Fixed |
| [FIXED-195](#fixed-195--a-governed-command-had-no-operating-system-boundary) | High | Shell / sandbox | Fixed (was part of BUG-194) |
| [FIXED-198](#fixed-198--registering-one-tool-meant-twelve-edits-across-seven-files) | Medium | Codebase structure | Fixed (was OPT-01) |
| [FIXED-199](#fixed-199--the-rust-and-python-command-codecs-could-not-authenticate-each-other) | High | Command protocol | Fixed |
| [FIXED-200](#fixed-200--memory-recall-re-ran-the-full-text-match-once-per-candidate-row) | **Critical** | Memory retrieval / performance | Fixed |
| [FIXED-201](#fixed-201--an-ordinary-prompt-could-raise-a-sqlite-error-out-of-memory-recall) | High | Memory retrieval | Fixed |
| [FIXED-202](#fixed-202--memories-with-no-similarity-to-the-prompt-were-recalled-into-context) | High | Memory retrieval / context | Fixed |
| [FIXED-203](#fixed-203--chunk_text-looped-forever-when-the-overlap-reached-the-chunk-size) | Low | Vector chunking | Fixed |
| [FIXED-204](#fixed-204--the-first-screen-an-owner-sees-called-five-unreachable-backends-connected) | High | First-run setup / Models honesty | Fixed (was BUG-198) |
| [FIXED-209](#fixed-209--the-guide-the-interface-was-explaining-from-is-now-inside-the-product) | Medium | Documentation surface | Fixed (BUG-208 slice A) |
| [FIXED-210](#fixed-210--nine-pages-stopped-teaching-and-the-provider-card-stopped-shouting) | Medium | UI density | Fixed (BUG-208 slices B, D, E) |
| [FIXED-211](#fixed-211--the-last-three-teaching-surfaces-and-an-emoji-that-was-never-a-reaction) | Medium | UI density | Fixed (BUG-208 slices C, F — entry closed) |
| [FIXED-212](#fixed-212--the-built-in-config-and-icon-had-two-copies-and-the-repository-one-silently-won) | Medium | Packaging / configuration | Fixed |
| [FIXED-213](#fixed-213--a-tool-call-was-invisible-in-chat-was-bug-206) | High | Chat / streaming surface | Fixed (was BUG-206 — entry closed) |
| [FIXED-214](#fixed-214--the-models-real-reasoning-was-requested-discarded-and-replaced-with-three-canned-sentences-was-bug-207) | Medium | Chat / streaming honesty | Fixed (was BUG-207 — entry closed) |
| [FIXED-215](#fixed-215--the-all-pages-evidence-sweep-photographed-the-setup-wizard-instead-of-the-pages) | Low | Live tests | Fixed (found while verifying FIXED-213/214) |
| [FIXED-216](#fixed-216--a-successful-turn-reported-that-it-could-not-continue-was-bug-196) | Medium | Build / Chat turn resume | Fixed (was BUG-196 — entry closed) |
| [FIXED-217](#fixed-217--a-command-runs-backend-column-was-never-written-was-bug-197) | Low | Command store | Fixed (was BUG-197 — entry closed) |
| [FIXED-218](#fixed-218--a-plain-pytest-tests-run-failed-because-cipher_memory_security-is-a-one-way-latch-was-bug-205) | Low | Test isolation / SQLCipher posture | Fixed (was BUG-205 — entry closed) |
| [FIXED-219](#fixed-219--reasoning-was-shown-live-and-then-forgotten-was-bug-215) | Low | Chat / reasoning retention | Fixed (was BUG-215 — entry closed) |
| [FIXED-220](#fixed-220--the-composer-was-a-textarea-and-a-send-button-gap-build-b19-gap-chat-c14) | Medium | Chat / Build composer | Fixed (GAP-BUILD B19, GAP-CHAT C14) |
| [FIXED-221](#fixed-221--three-settings-sections-had-deep-links-that-silently-opened-general) | Low | Settings navigation | Fixed (found while shipping FIXED-219) |
| [FIXED-222](#fixed-222--the-audit-chain-looked-for-an-events-predecessor-by-a-whole-second-timestamp) | High | Audit integrity | Fixed (found running the suite under load) |
| [FIXED-223](#fixed-223--the-first-run-model-stage-could-not-answer-the-question-it-asked) | High | First-run setup / Models | Fixed |
| [FIXED-224](#fixed-224--three-openrouter-models-became-one-string-and-froze-the-row-that-listed-them) | High | API redaction / model picker | Fixed |
| [FIXED-225](#fixed-225--the-workbench-opened-with-a-composer-that-could-not-send) | Medium | Workbench | Fixed |
| [FIXED-226](#fixed-226--check-again-reported-check-complete-when-it-had-checked-nothing) | Medium | Model readiness | Fixed |
| [FIXED-227](#fixed-227--branch-from-here-the-last-open-part-of-c14) | — | Chat / checkpoints (GAP-CHAT C14) | Fixed |
| [FIXED-228](#fixed-228--the-composer-hid-the-thinking-budget-behind-a-second-dropdown-and-lost-its-focus-ring) | Low | Composer | Fixed |
| [FIXED-229](#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one) | High | Shell / background execution (BUG-194) | Fixed |
| [FIXED-230](#fixed-230--the-vector-leg-searched-one-embedding-space-and-the-query-was-embedded-in-another) | High | Memory retrieval (MEM-03) | Fixed |
| [FIXED-231](#fixed-231--full-text-search-ranked-by-time-because-a-plan-document-said-fts5-was-unavailable) | High | Text search / retrieval (MEM-05) | Fixed |
| [FIXED-232](#fixed-232--the-agents-memory-search-and-the-runtimes-recall-were-two-different-searches) | High | Retrieval consistency (MEM-11) | Fixed |
| [FIXED-233](#fixed-233--the-graph-leg-of-hybrid-retrieval-never-ran-on-a-real-turn) | High | Retrieval quality (MEM-12) | Fixed |
| [FIXED-234](#fixed-234--the-knowledge-graph-could-be-looked-at-but-not-asked) | Medium | Agent reach (MEM-13) | Fixed |
| [FIXED-235](#fixed-235--the-knowledge-map-was-a-map-of-the-runtimes-bookkeeping-not-the-owners-work) | High | Knowledge Map (BUG-218) | Fixed |
| [FIXED-236](#fixed-236--the-citation-ledger-recorded-every-reference-and-could-only-be-read-forwards) | Medium | Reference graph (MEM-14) | Fixed |
| [FIXED-237](#fixed-237--eidetic-capture-was-implemented-and-never-called) | High | Eidetic / Stage C (MEM-04) | Fixed |
| [FIXED-238](#fixed-238--a-background-run-could-not-survive-the-restart-of-the-runtime-that-started-it) | Medium | Shell / recovery (BUG-194) | Fixed |
| [FIXED-239](#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist) | Medium | Shell / sandbox (BUG-194) | Fixed |
| [FIXED-240](#fixed-240--deep-windows-paths-silently-made-approved-writes-irreversible) | High | checkpoints / Windows paths (BUG-216) | Fixed 2026-08-21 |
| [FIXED-241](#fixed-241--the-memory-entity-graph-had-no-evidence-producing-extractor) | Medium | memory graph (MEM-06) | Fixed 2026-08-21 |
| [FIXED-242](#fixed-242--runtime-settings-crashed-while-rendering-measured-runner-trust) | High | Runtime UI/API | Fixed (found during live Playwright verification on 2026-08-21) |
| [FIXED-243](#fixed-243--a-denied-windows-tree-kill-left-cancelled-runs-running-forever) | High | Shell / background execution (BUG-194) | Fixed (found during the complete Windows gate run on 2026-08-21) |
| [FIXED-244](#fixed-244--the-sqlcipher-posture-test-bypassed-its-own-crash-probe) | Medium | Windows test reliability | Fixed (found during the complete gate run on 2026-08-21) |
| [FIXED-245](#fixed-245--the-local-runtime-card-contradicted-its-measured-capabilities) | Medium | Runtime UI / capability truthfulness (BUG-194) | Fixed (found during focused live Playwright verification on 2026-08-21) |
| [FIXED-246](#fixed-246--read-only-quarantine-disposal-was-only-proven-on-windows) | High | credential delta quarantine / CI portability (BUG-194) | Fixed (found by the exact-SHA GitHub Python workflow on 2026-08-21) |
| [FIXED-247](#fixed-247--voice-controls-were-labels-rather-than-governed-input) | High | Chat / Build / prompt provenance (GAP-CHAT C16) | Fixed 2026-08-21 |
| [FIXED-248](#fixed-248--build-defaulted-to-a-mode-that-overrode-the-owners-own-permissions) | Medium | Build composer / decision modes | Fixed 2026-08-21 |
| [FIXED-249](#fixed-249--dictation-kept-listening-from-a-page-the-owner-had-left) | High | Chat / Build voice (GAP-CHAT C16) | Fixed 2026-08-21 |
| [FIXED-250](#fixed-250--the-composers-carried-each-others-controls-and-said-the-same-thing-four-times) | Low | Chat / Build composer | Fixed 2026-08-21 |
| [FIXED-251](#fixed-251--build-had-no-operating-protocol-and-no-record-of-which-one-ran) | Medium | Runtime orchestration / Build | Fixed 2026-08-21 |
| [FIXED-252](#fixed-252--one-typo-in-a-hooks-file-made-every-prompt-fail) | High | hooks / runtime startup | Fixed 2026-08-22 |
| [FIXED-253](#fixed-253--hooks-enforced-things-nothing-could-see) | Medium | hooks / Extensions | Fixed 2026-08-22 |
| [FIXED-254](#fixed-254--refusing-a-projects-hooks-meant-editing-the-projects-file) | Low | hooks | Fixed 2026-08-22 (BUG-222) |
| [FIXED-255](#fixed-255--seven-lifecycle-events-were-specified-and-never-emitted) | Medium | hooks / lifecycle | Fixed 2026-08-22 (BUG-223) |
| [FIXED-256](#fixed-256--a-plugin-was-recorded-and-then-provided-nothing) | Medium | plugins / extensibility | Fixed 2026-08-22 (BUG-221, first contribution kind) |
| [FIXED-257](#fixed-257--the-selected-tab-could-be-off-the-screen-it-was-selected-on) | Low | navigation / responsive | Fixed 2026-08-22 |
| [FIXED-258](#fixed-258--twenty-web-tests-failed-on-a-current-node-and-passed-on-cis) | Low | web tests / environment | Fixed 2026-08-22 (BUG-224) |
| [FIXED-259](#fixed-259--a-plugin-can-contribute-a-skill-and-it-arrives-switched-off) | Medium → Low | plugins / skills / extensibility | Fixed 2026-08-22 (BUG-221 step 2) |
| [FIXED-260](#fixed-260--a-plugin-can-offer-an-mcp-server-and-an-offer-is-not-a-server) | Medium → Low | plugins / MCP / extensibility | Fixed 2026-08-22 (BUG-221 step 3) |
| [FIXED-261](#fixed-261--what-a-channel-message-is-in-a-turn-is-now-decided) | Medium | channels / threat model | Fixed 2026-08-22 (BUG-225 step 1) |
| [FIXED-262](#fixed-262--there-is-an-unattended-posture-now-decline-instead-of-asking) | Low | approval modes | Fixed 2026-08-22 (BUG-219) |
| [FIXED-263](#fixed-263--the-approval-posture-menu-opened-into-the-fold) | Low | composer / web UI | Fixed 2026-08-22 |
| [FIXED-264](#fixed-264--a-live-specs-sign-in-depended-on-how-much-history-the-instance-had) | Low | live test harness | Fixed 2026-08-22 |
| [FIXED-265](#fixed-265--channels-have-an-owner-surface-and-the-tab-stops-denying-the-transport) | Medium | channels / extensibility | Fixed 2026-08-22 (BUG-225 steps 2 and 3) |
| [FIXED-266](#fixed-266--a-boolean-was-redacted-into-the-opposite-of-the-truth) | Medium | API redaction | Fixed 2026-08-22 |
| [FIXED-267](#fixed-267--an-allowlisted-channel-sender-is-no-longer-unbounded) | Medium | channels / abuse resistance | Fixed 2026-08-22 (BUG-225) |
| [FIXED-268](#fixed-268--a-signed-http-callback-was-posting-an-unsigned-body) | Medium | channels / outbound integrity | Fixed 2026-08-22 |
| [FIXED-269](#fixed-269--two-overlapping-reconciles-could-delete-each-others-plugin-skills) | Low | plugins / skills | Fixed 2026-08-22 |
| [FIXED-270](#fixed-270--checkpoint-rewind-was-built-registered-tested-and-unreachable) | High | checkpoints / recovery | Fixed (was BUG-230) |
| [FIXED-271](#fixed-271--the-audit-log-could-not-be-taken-out-of-the-product) | High | observability / evidence | Fixed (was BUG-231) |
| [FIXED-272](#fixed-272--two-egress-implementations-existed-and-the-weaker-one-was-registered) | High | egress / governance | Fixed (was BUG-232) |
| [FIXED-273](#fixed-273--an-approval-promised-a-rewind-it-could-not-give-for-a-file-over-8-mib) | Medium | checkpoints / approvals | Fixed (was BUG-233) |
| [FIXED-274](#fixed-274--the-mcp-client-was-five-protocol-revisions-behind) | Medium | MCP / interoperability | Fixed (was BUG-234) |
| [FIXED-275](#fixed-275--a-relayed-write-was-captured-under-a-session-no-checkpoint-belongs-to) | High | checkpoints / approvals | Fixed (was BUG-235; raised and closed 2026-08-23 while verifying FIXED-270 live) |
| [FIXED-276](#fixed-276--an-audit-exports-manifest-hash-was-redacted-into-unusability) | Medium | API redaction / observability | Fixed (was BUG-236; raised and closed 2026-08-23 while verifying FIXED-271 live) |
| [FIXED-277](#fixed-277--the-terminal-client-died-on-its-own-output-under-a-legacy-code-page) | Low | CLI / Windows | Fixed (was BUG-237; raised and closed 2026-08-23 while exercising the terminal half of FIXED-270) |
| [FIXED-278](#fixed-278--every-restart-asked-the-owner-to-set-up-a-model-they-had-already-set-up) | High | models / readiness | Fixed (was BUG-238; raised and closed 2026-08-23) |
| [FIXED-279](#fixed-279--eight-copies-of-one-governance-check-and-two-of-them-had-already-drifted) | Low → Medium once measured | governance architecture | Fixed (was GEP-01; raised 2026-08-23, closed 2026-08-24) |
| [FIXED-280](#fixed-280--fifteen-capability-switches-that-governed-nothing-and-one-that-should-have) | Medium | governance architecture | Fixed (was GEP-04; raised 2026-08-23, closed 2026-08-24) |
| [FIXED-281](#fixed-281--a-skill-written-in-raiker-was-not-guaranteed-to-work-anywhere-else) | Medium | skills / interoperability | Fixed (was ADD-21; raised 2026-08-23, closed 2026-08-24) |
| [FIXED-282](#fixed-282--auto-promised-a-review-it-did-not-perform) | Medium | decision modes / Build / Chat | Fixed (was BUG-218; raised 2026-08-21, closed 2026-08-24) |
| [FIXED-283](#fixed-283--semantic-recall-was-selectable-and-nothing-could-ever-produce-a-space-to-select) | Medium | memory / retrieval quality | Fixed (was MEM-10 first leg; raised 2026-08-17, closed 2026-08-25) |
| [FIXED-284](#fixed-284--nothing-expired-because-the-sweep-the-retention-classes-describe-was-never-offered) | Medium | memory / retention | Fixed (was MEM-07; raised 2026-08-11, closed 2026-08-25) |
| [FIXED-285](#fixed-285--four-cadences-existed-and-the-composer-offered-one-of-them) | Low | tasks / scheduling | Fixed (was backlog #10; closed 2026-08-25) |
| [FIXED-286](#fixed-286--a-task-reported-done-while-the-work-it-delegated-was-still-open) | Medium | tasks / delegation | Fixed (was BUG-220; raised 2026-08-21, closed 2026-08-25) |
| [FIXED-287](#fixed-287--a-reopened-transcript-showed-the-answer-and-nothing-about-how-it-was-reached) | Low | Chat / transcript record | Fixed (was backlog #25; closed 2026-08-25) |
| [FIXED-288](#fixed-288--three-interface-defects-found-while-exercising-the-four-above) | Low → Medium | Permissions / Models | Fixed (raised and closed 2026-08-25 during the live round) |
| [FIXED-289](#fixed-289--uploaded-files-had-nowhere-to-live-and-build-inherited-a-project-nothing-on-screen-named) | Medium | Memory / Projects / Chat / Build retrieval | Fixed (closed 2026-08-25) |
| [FIXED-290](#fixed-290--four-controls-that-outlived-the-selector-they-belonged-to) | Medium | Projects / Build / Chat / Workbench | Fixed (raised and closed 2026-08-25 by the screenshot refresh) |
| [FIXED-291](#fixed-291--a-project-could-only-ever-be-a-folder-raiker-made) | Medium | Projects / path containment / knowledge indexing / Build retrieval | Fixed (closed 2026-08-26) |
| [FIXED-292](#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | Medium | Memory / governed model egress | Fixed (closed 2026-08-26) |
| [FIXED-293](#fixed-293--local-semantic-recall-was-declared-and-blocked-by-a-remote-egress-check) | High | Memory / local models / governance | Fixed (closed 2026-08-26) |
| [FIXED-294](#fixed-294--managed-documents-could-only-be-recalled-with-shared-words) | High | Memory / Projects / managed files | Fixed (was BUG-240 remainder; closed 2026-08-26) |
| [FIXED-295](#fixed-295--ollama-cloud-chat-was-offered-as-an-embedding-model) | Medium | Models / Memory UI honesty | Fixed (found and closed 2026-08-26) |
| [FIXED-296](#fixed-296--a-library-change-left-semantic-index-controls-stale) | Medium | Memory / managed-file UX | Fixed (found and closed 2026-08-26) |
| [FIXED-297](#fixed-297--web-development-dependencies-regained-known-denial-of-service-advisories) | High | Web development dependencies | Fixed (found and closed 2026-08-26) |
| [FIXED-298](#fixed-298--a-paired-channel-could-still-only-record-a-message) | High | Channels / routing / approval relay | Fixed (was BUG-225; closed 2026-08-27) |
| [FIXED-299](#fixed-299--skills-had-no-owner-authored-command-handle) | High | Skills / Chat / Build commands | Fixed (was backlog #4 and C9 remainder; closed 2026-08-27) |
| [FIXED-300](#fixed-300--the-mlx-runtime-test-assumed-posix-path-rendering-on-windows) | Low | Test portability / MLX | Fixed (found during release verification; closed 2026-08-28) |
| [FIXED-301](#fixed-301--every-memory-recall-rebuilt-and-linearly-scanned-the-entire-vector-space) | High | Memory / retrieval scale / web UI | Fixed (was backlog #5; closed 2026-08-28) |
| [FIXED-302](#fixed-302--memory-permission-loading-was-presented-as-a-permission-read-failure) | Low | Memory / web UI | Fixed (found during live vector-retrieval verification; closed 2026-08-28) |
| [FIXED-303](#fixed-303--prompt-hooks-needed-a-model-call-without-a-private-authority-path) | Medium | Hooks / model governance / web UI | Fixed (was backlog #15, BUG-226 remainder; closed 2026-08-28) |
| [FIXED-304](#fixed-304--owner-setting-changes-had-no-hookable-governance-boundary) | Medium | Hooks / Settings / web UI | Fixed (was backlog #14, first half; closed 2026-08-28) |
| [FIXED-305](#fixed-305--the-three-remaining-worth-adding-hook-events-had-no-call-site) | Medium | Hooks / runtime / notifications / web UI | Fixed (closed backlog #14; closed 2026-08-28) |
| [FIXED-306](#fixed-306--compaction-was-the-thresholds-decision-and-the-owner-had-no-say) | Medium | Chat / context / web UI | Fixed (closed backlog #9; closed 2026-08-29) |
| [FIXED-307](#fixed-307--four-risk-bands-no-definitions-and-two-of-them-unreachable) | High | Policy / risk classification / governance | Fixed (closed 2026-08-29) |
| [FIXED-308](#fixed-308--raiker-could-ask-permission-and-could-not-ask-what-you-meant) | Medium | Chat / approvals / web UI | Fixed (closed ADD-22 and backlog #17; closed 2026-08-29) |
| [FIXED-309](#fixed-309--build-opened-an-empty-conversation-after-a-reload) | Medium | Build / web UI | Fixed (was BUG-242; closed 2026-08-29) |
| [FIXED-310](#fixed-310--the-memory-integrity-report-existed-and-nothing-could-reach-it) | Medium | Memory / diagnostics / web UI | Fixed (was MEM-09; closed 2026-08-29) |
| [FIXED-311](#fixed-311--recall-was-invisible-at-the-moment-it-was-used) | Medium | Chat / memory / web UI | Fixed (was C17; closed 2026-08-29) |
| [FIXED-312](#fixed-312--the-core-act-of-code-review-was-a-route-change-away) | Medium | Build / approvals / web UI | Fixed (was B14's review half; closed 2026-08-29) |
| [FIXED-313](#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport) | Low | Live test harness / evidence | Fixed (was BUG-241; closed 2026-08-29) |
| [FIXED-314](#fixed-314--a-question-could-not-recall-the-memory-that-answered-it) | High | Memory / retrieval | Fixed (was BUG-243, raised and closed 2026-08-29) |
| [FIXED-315](#fixed-315--the-one-control-that-makes-an-agent-safe-to-leave-running-was-in-another-route) | Medium | Build / Chat / checkpoints / web UI | Fixed (was B18; closed 2026-08-29) |
| [FIXED-316](#fixed-316--every-turn-coordinate-was-a-dead-end) | Medium | Chat / Build / memory / web UI | Fixed (was MEM-08; closed 2026-08-29) |
| [FIXED-317](#fixed-317--three-tools-declared-a-source-and-produced-none) | Medium | Runtime / citations / provenance | Fixed (raised and closed 2026-08-29) |
| [FIXED-318](#fixed-318--a-checkbox-was-thirteen-pixels-in-five-places) | Low | Web UI / accessibility | Fixed (raised and closed 2026-08-29) |
| [FIXED-319](#fixed-319--importing-the-same-memory-twice-stored-it-twice) | Low | Memory / import | Fixed (was BUG-244; closed 2026-08-29) |
| [FIXED-320](#fixed-320--the-authority-matrix-hid-its-own-verdicts-on-a-phone) | Low | Permissions / web UI | Fixed (was BUG-246, raised and closed 2026-08-29) |
| [FIXED-321](#fixed-321--build-could-change-a-repository-and-never-show-it) | Medium | Build / web UI | Fixed (was GAP-BUILD B13; closed 2026-08-30) |
| [FIXED-322](#fixed-322--permissions-said-off-about-a-capability-that-would-have-run) | Low | Capability gates / web UI | Fixed (was BUG-239's live half; closed 2026-08-30) |
| [FIXED-323](#fixed-323--a-cited-past-conversation-named-its-exchanges-and-could-not-open-one) | Low | Memory / citations | Fixed (was BUG-245; closed 2026-08-30) |
| [FIXED-324](#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in) | Low | Live test harness | Fixed (was BUG-229's remainder; closed 2026-08-30) |
| [FIXED-325](#fixed-325--a-phone-was-clipping-the-models-page-and-the-knowledge-map-never-resized) | Medium | Web UI / responsive | Fixed (raised and closed 2026-08-30) |
| [FIXED-326](#fixed-326--a-fixed_items-link-pointed-at-a-heading-that-does-not-exist) | Low | Documentation / CI | Fixed (was BUG-249; closed 2026-08-30) |
| [FIXED-327](#fixed-327--the-setup-wizard-trapped-every-live-spec-after-the-first-one) | Medium | Live test harness | Fixed (raised and closed 2026-08-30) |
| [FIXED-328](#fixed-328--one-owner-for-the-whole-live-suite) | Low | Live test harness | Fixed (was BUG-247, and seven of BUG-248's twenty-seven; closed 2026-08-30) |
| [FIXED-329](#fixed-329--three-controls-a-narrow-window-silently-removed) | Medium | Chat / Build / web UI | Fixed (raised and closed 2026-08-30) |
| [FIXED-330](#fixed-330--the-overview-counted-one-set-of-gates-and-linked-to-another) | Low | Observability / web UI | Fixed (raised and closed 2026-08-30) |
| [FIXED-331](#fixed-331--a-turn-the-reader-walked-away-from-was-never-recorded) | High | Runtime / gateway / durability | Fixed (raised and closed 2026-08-30) |
| [FIXED-332](#fixed-332--main-was-red-on-ruff-and-mypy) | Medium | CI / repository hygiene | Fixed (raised and closed 2026-09-03) |
| [FIXED-333](#fixed-333--a-repository-file-test-asserted-bytes-its-own-fixture-could-not-write-on-windows) | Low | Tests / portability | Fixed (raised and closed 2026-09-03) |
| [FIXED-334](#fixed-334--a-signed-in-chatgpt-subscription-was-refused-by-the-policy-gate-it-had-already-satisfied) | High | Models / ChatGPT subscription | Fixed (raised and closed 2026-09-03) |
| [FIXED-335](#fixed-335--the-subscription-row-hid-every-account-control-the-moment-it-connected) | High | Models / ChatGPT subscription | Fixed (raised and closed 2026-09-03) |
| [FIXED-336](#fixed-336--a-device-without-codex-reported-a-failed-status-read-rather-than-a-missing-program) | Low | Models / ChatGPT subscription | Fixed (raised and closed 2026-09-03) |
| [FIXED-337](#fixed-337--five-providers-shared-one-anonymous-square) | Low | Models / web UI | Fixed (raised and closed 2026-09-03) |
| [FIXED-338](#fixed-338--the-browser-filled-the-owner-raiker-password-into-provider-credential-boxes) | High | Models / credential handling | Fixed (raised and closed 2026-09-03) |
| [FIXED-339](#fixed-339--mlx-was-offered-on-machines-that-cannot-run-it) | Medium | Models / platform honesty | Fixed (raised and closed 2026-09-03) |
| [FIXED-340](#fixed-340--pickers-offered-models-that-could-not-answer) | High | Models / every picker | Fixed (raised and closed 2026-09-03) |
| [FIXED-341](#fixed-341--a-model-that-was-set-up-and-selected-was-refused-for-never-having-been-checked) | High | Models / readiness | Fixed (raised and closed 2026-09-03) |
| [FIXED-342](#fixed-342--the-model-menu-opened-in-the-corner-of-whatever-column-it-was-dropped-into) | Medium | Web UI / model picker | Fixed (raised and closed 2026-09-03) |
| [FIXED-343](#fixed-343--one-model-per-provider-was-the-only-thing-a-picker-could-offer) | High | Models / selection | Fixed (raised and closed 2026-09-03) |
| [FIXED-344](#fixed-344--an-approval-raised-anywhere-had-to-be-hunted-down-in-the-inbox) | High | Approvals / web UI | Fixed (raised and closed 2026-09-03) |
| [FIXED-345](#fixed-345--the-host-panel-pointed-at-a-command-line-for-an-update-settings-can-apply) | Low | Host control / updates | Fixed (raised and closed 2026-09-03) |
| [FIXED-346](#fixed-346--the-models-page-said-no-models-were-ready-on-an-instance-with-models-set-up) | Medium | Models / web UI | Fixed (raised and closed 2026-09-03) |
| [FIXED-347](#fixed-347--choosing-a-model-was-an-accordion-inside-a-provider-card) | Medium | Models / web UI | Fixed (raised and closed 2026-09-03) |
| [FIXED-348](#fixed-348--an-attachment-button-that-could-do-nothing-still-looked-like-a-button) | Low | Chat / Build / attachments | Fixed (raised and closed 2026-09-03) |
| [FIXED-349](#fixed-349--three-provider-marks-were-drawn-as-letters-beside-the-real-ones) | Low | Models / web UI | Fixed (raised and closed 2026-09-03) |
| [FIXED-350](#fixed-350--dropping-a-file-worked-in-one-place-and-was-ignored-in-four) | Low | Web UI / attachments | Fixed 2026-09-03 (BUG-252) |
| [FIXED-351](#fixed-351--a-decision-raised-while-raiker-was-in-the-background-reached-nobody) | Low | Approvals / notifications | Fixed 2026-09-03 (BUG-255) |
| [FIXED-352](#fixed-352--every-path-an-owner-typed-was-a-path-they-had-to-know) | Medium | Web UI / file and folder selection | Fixed 2026-09-03 (BUG-251) |
| [FIXED-353](#fixed-353--reloading-the-page-signed-the-owner-out) | Medium | Authentication / web UI | Fixed 2026-09-03 (BUG-253) |
| [FIXED-354](#fixed-354--a-subscriptions-own-usage-and-limits-were-not-shown) | Medium | Models / Observability | Fixed 2026-09-03 (BUG-254) |
| [FIXED-355](#fixed-355--a-rejected-key-was-reported-as-a-network-failure) | Medium | Models / provider errors | Fixed 2026-09-03 (BUG-257) |
| [FIXED-356](#fixed-356--a-picker-offered-and-defaulted-to-a-model-that-cannot-answer) | High | Models / every picker | Fixed 2026-09-03 (BUG-258) |
| [FIXED-357](#fixed-357--a-fresh-raiker-adopted-whichever-chatgpt-account-codex-was-signed-in-to) | High | Models / ChatGPT subscription | Fixed 2026-09-03 (BUG-259) |
| [FIXED-358](#fixed-358--choosing-among-four-hundred-models-was-a-dropdown-with-no-search) | High | Models / web UI | Fixed 2026-09-03 (BUG-260, BUG-263, BUG-264) |
| [FIXED-359](#fixed-359--first-run-could-detect-a-missing-runtime-and-not-offer-to-install-it) | Medium | Models / first run | Fixed 2026-09-03 (BUG-261, BUG-262) |
| [FIXED-360](#fixed-360--a-policy-refusal-was-reported-as-a-wrong-password) | Medium | Authentication / web UI | Fixed 2026-09-03 (BUG-265) |
| [FIXED-361](#fixed-361--the-folder-picker-handed-back-redacted_secret-instead-of-a-path) | High | Web UI / redaction | Fixed 2026-09-03 (BUG-268) |
| [FIXED-362](#fixed-362--an-expected-answer-was-written-to-the-console-as-a-failure) | Low | Authentication / web UI | Fixed 2026-09-03 (BUG-267) |
| [FIXED-363](#fixed-363--dictation-was-the-last-surface-that-was-not-local) | Medium | Voice / privacy posture | Fixed 2026-09-03 (BUG-256) |
| [FIXED-364](#fixed-364--a-live-round-could-start-on-the-previous-rounds-data) | Low | Live test harness / host lifecycle | Fixed 2026-09-03 (BUG-266) |
| [FIXED-365](#fixed-365--a-fresh-install-named-a-model-nobody-had) | Medium | Models / first-run default | Fixed 2026-09-03 (BUG-270) |
| [FIXED-366](#fixed-366--build-could-read-a-repository-and-not-understand-it) | — | Build / language intelligence | Fixed 2026-09-03 (GAP-BUILD B10; BUG-227 answered by decision) |
| [FIXED-367](#fixed-367--background-work-finished-into-a-status-line) | — | Chat / tasks | Fixed 2026-09-03 (GAP-CHAT C11) |
| [FIXED-368](#fixed-368--where-did-i-say-that-was-answered-what-am-i-working-on-was-not) | — | Chat / cross-chat surface | Fixed 2026-09-03 (GAP-CHAT C18) |
| [FIXED-369](#fixed-369--a-reviewer-could-accept-a-change-or-reject-it-and-nothing-between) | — | Build / Approvals / code review | Fixed 2026-09-03 (GAP-BUILD B14 remainder) |
| [FIXED-370](#fixed-370--a-valid-key-was-reported-as-a-bare-http-status) | Medium | Models / provider errors | Fixed 2026-09-03 (BUG-272, raised and closed in the same round) |
| [FIXED-371](#fixed-371--two-controls-with-nothing-in-them-found-by-the-sweep) | Low | Web UI | Fixed 2026-09-03 (found by this round's own UI sweep) |
| [FIXED-372](#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one) | Medium | Models / provider connection | Fixed 2026-09-04 (BUG-274, the remainder FIXED-370 left) |
| [FIXED-373](#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local) | Low | Voice / privacy posture | Fixed 2026-09-04 (BUG-269) |
| [FIXED-374](#fixed-374--a-routine-ran-all-night-and-told-nobody) | Medium | Tasks / notifications | Fixed 2026-09-04 (GAP-CHAT C10, first half) |
| [FIXED-375](#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one) | Low | Build / Approvals / code review | Fixed 2026-09-04 (BUG-271; closes GAP-BUILD B14) |
| [FIXED-376](#fixed-376--every-turn-paid-for-forty-nine-tool-schemas-to-call-two) | Medium | Models / context cost | Fixed 2026-09-04 (compatibility backlog item 16) |
| [FIXED-377](#fixed-377--a-projected-mcp-tool-had-no-arguments) | Medium | MCP / models / context cost | Fixed 2026-09-04 (compatibility backlog item 16, the MCP half) |
| [FIXED-378](#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport) | Low | MCP / interoperability | Fixed 2026-09-04 (the transport half of BUG-234) |
| [FIXED-379](#fixed-379--raiker-recorded-more-than-anyone-exports-and-could-not-export-it) | Medium | Observability / governed events | Fixed 2026-09-04 (compatibility backlog item 18) |
| [FIXED-380](#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two) | Low | Hooks / handlers | Fixed 2026-09-04 (the `http` slice of BUG-226) |
| [FIXED-381](#fixed-381--a-parent-owned-its-childrens-outcomes-and-could-not-say-how-they-work) | Medium | Tasks / delegation | Fixed 2026-09-04 (compatibility backlog item 23) |
| [FIXED-382](#fixed-382--the-model-picker-said-unreachable-about-a-provider-that-had-just-answered) | Medium | Models / provider errors / web UI | Fixed 2026-09-04 (BUG-275, raised and closed in this round) |
| [FIXED-383](#fixed-383--the-model-control-was-an-empty-circle-whenever-no-model-was-chosen) | Low | Web UI / composer | Fixed 2026-09-04 (found by this round's width sweep) |
| [FIXED-384](#fixed-384--two-path-fields-taught-a-shape-that-cannot-exist-on-two-of-three-platforms) | Low | Web UI / model library | Fixed 2026-09-04 (found by this round's width sweep) |
| [FIXED-385](#fixed-385--two-surfaces-named-themselves-twice-and-a-new-switch-named-itself-not-at-all) | Low | Web UI / Settings and Permissions | Fixed 2026-09-04 (found by this round's width sweep) |
| [FIXED-386](#fixed-386--governed-events-only-left-when-somebody-pressed-a-button) | Low | Observability / telemetry export | Fixed 2026-09-04 (BUG-276; completes backlog #18) |
| [FIXED-387](#fixed-387--a-tool-result-had-one-shape-and-the-revision-defines-six) | Low | MCP / interoperability | Fixed 2026-09-04 (reduces BUG-234) |
| [FIXED-388](#fixed-388--a-valid-key-was-answered-with-check-your-network) | **High** | Models / provider errors | Fixed 2026-09-04 (BUG-277, raised and closed in this round) |
| [FIXED-389](#fixed-389--twenty-six-connectors-said-they-were-installed-under-a-card-saying-none-were) | Medium | Extensions / accessibility | Fixed 2026-09-04 (BUG-278, raised by this round's page sweep) |
| [FIXED-390](#fixed-390--three-surfaces-said-next-and-printed-a-full-timestamp) | Low | Web UI / time formatting | Fixed 2026-09-04 (BUG-279, raised while verifying FIXED-386) |
| [FIXED-391](#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line) | Low | Web UI / consistency | Fixed 2026-09-04 (BUG-280, raised by this round's page sweep) |
| [FIXED-392](#fixed-392--the-source-said-a-gate-ships-enabled-the-product-said-it-was-off) | Low | Documentation / capability defaults | Fixed 2026-09-04 (BUG-281, raised while verifying FIXED-386 live) |
| [FIXED-393](#fixed-393--the-guide-described-a-boundary-the-product-removed-nine-days-earlier) | Medium | Documentation / memory | Fixed 2026-09-04 (BUG-282, raised by this round's page sweep) |
| [FIXED-394](#fixed-394--thirty-destinations-and-two-of-them-were-copies-of-the-others) | Low | Web UI / information architecture | Fixed 2026-09-04 (BUG-283, raised by the owner) |
| [FIXED-395](#fixed-395--three-mobile-bleeds-that-only-existed-once-the-workspace-held-anything) | Medium | Web UI / responsive layout | Fixed 2026-09-04 (BUG-284, found by the width sweep on a *used* workspace) |
| [FIXED-396](#fixed-396--eight-provider-cards-printed-the-same-placeholder-about-pinning) | Low | Models / information architecture | Fixed 2026-09-04 (raised by the owner) |
| [FIXED-397](#fixed-397--a-chip-list-of-disabled-capabilities-that-named-the-page-it-was-drawn-on) | Medium | Observability / documentation truthfulness | Fixed 2026-09-04 (raised by the owner) |
| [FIXED-398](#fixed-398--the-design-system-was-stated-in-a-comment-and-enforced-by-nothing) | High | Web UI / design system | Fixed 2026-09-04 (raised by the owner, from Hermes Agent and OpenClaw) |
| [FIXED-399](#fixed-399--the-knowledge-map-carried-four-palettes-and-two-of-them-were-the-same-one) | High | Web UI / theming | Fixed 2026-09-04 (found by FIXED-398's audit) |
| [FIXED-400](#fixed-400--ten-var-references-to-tokens-that-do-not-exist) | Medium | Web UI / design system | Fixed 2026-09-04 (found by FIXED-398's audit) |
| [FIXED-401](#fixed-401--a-scale-that-existed-and-a-sidebar-that-vanished-instead-of-collapsing) | Medium | Web UI / shell | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-402](#fixed-402--messaging-is-its-own-destination-and-telegram-is-a-real-transport) | High | Channels / messaging | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-403](#fixed-403--the-design-surface-governed-image-generation-from-nothing) | High | Design / image generation | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-404](#fixed-404--a-nine-step-type-scale-with-sixty-three-sizes-in-front-of-it) | Medium | Web UI / design system | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-405](#fixed-405--the-element-floor-was-a-ceiling-and-it-painted-the-page-out) | High | Web UI / shell | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-406](#fixed-406--an-if-chain-that-works-for-two-transports-and-stops-at-three) | Medium | Channels / messaging | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-407](#fixed-407--a-gigabyte-of-downloads-because-the-interpreter-was-python-310) | Medium | Install / dependencies | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-408](#fixed-408--one-composer-three-surfaces-and-design-where-it-belongs) | Medium | Web UI / work surfaces | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-409](#fixed-409--raiker-could-start-at-sign-in-but-had-no-icon-to-click) | Medium | Desktop integration / uninstall | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-410](#fixed-410--the-design-model-picker-was-empty-on-every-real-install) | **High** | Design / models | Fixed 2026-09-05 (raised by the owner) |
| [FIXED-411](#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own) | **High** | MCP / interoperability | Fixed 2026-09-05 (reduces BUG-234) |
| [FIXED-412](#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped) | Medium | MCP / interoperability | Fixed 2026-09-05 (reduces BUG-234) |
| [FIXED-413](#fixed-413--the-stop-switch-shouted-on-every-page-and-could-not-say-what-it-would-reach) | Medium | Web UI / governed interrupt | Fixed 2026-09-05 (found live) |
| [FIXED-414](#fixed-414--the-hub-could-not-be-reached-and-the-panel-said-search-the-catalogue) | Low | Models / Hugging Face | Fixed 2026-09-05 (found live) |
| [FIXED-415](#fixed-415--a-hub-tab-addressed-as-a-path-opened-the-workbench) | Low | Web UI / routing | Fixed 2026-09-05 (found live) |
| [FIXED-416](#fixed-416--both-every-page-sweeps-had-stopped-covering-every-page) | Medium | Live test harness / evidence | Fixed 2026-09-05 (found live) |
| [FIXED-417](#fixed-417--the-guides-tour-of-the-shell-described-a-shell-that-had-moved) | Medium | Documentation / web UI | Fixed 2026-09-05 (found live) |
| [FIXED-418](#fixed-418--every-settings-section-opened-general-on-the-only-route-to-settings) | Medium | Web UI / routing | Fixed 2026-09-05 (found live) |
| [FIXED-419](#fixed-419--four-live-guards-had-gone-stale-and-could-not-say-so) | Medium | Live test harness / evidence | Fixed 2026-09-05 (found live) |
| [FIXED-420](#fixed-420--a-failed-conversions-cleanup-could-delete-every-model-beside-it) | **Critical** | Models / destructive cleanup | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-421](#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled) | High | Models / durable operations | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-422](#fixed-422--retry-checked-the-kind-and-the-payload-and-never-the-state) | High | Models / durable operations | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-423](#fixed-423--a-multi-gigabyte-download-ran-inside-the-request-that-asked-for-it) | Medium/High | Models / Hugging Face | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-424](#fixed-424--two-models-one-folder-apart-were-indexed-as-one) | High | Models / local library | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-425](#fixed-425--a-method-whose-contract-was-to-return-health-raised-instead) | Medium | Models / provider contract | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-426](#fixed-426--a-thinking-budget-that-left-the-answer-nothing) | Medium/High | Models / Anthropic provider | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-427](#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence) | Medium/High | Host lifecycle / observability | Fixed 2026-09-05 (third-pass static review) |
| [FIXED-428](#fixed-428--every-conversion-in-activity-was-called-snapshotredacted_secret) | Medium | Web UI / API redaction | Fixed 2026-09-05 (found live) |
| [FIXED-429](#fixed-429--a-shared-live-helper-spent-a-whole-spec-timeout-on-a-button-nobody-needed) | Low | Live test harness | Fixed 2026-09-05 (found live) |
| [FIXED-430](#fixed-430--five-surfaces-asked-would-this-model-run-by-building-one-and-dropping-it) | High | Models / provider construction | Fixed 2026-09-06 (first-pass static review) |
| [FIXED-431](#fixed-431--a-reasoning-setting-judged-against-whichever-profile-was-first-in-the-file) | Medium/High | Models / reasoning controls | Fixed 2026-09-06 (first-pass static review) |
| [FIXED-432](#fixed-432--two-commands-running-at-once-could-be-judged-against-each-others-workspace) | High | Shell / command policy | Fixed 2026-09-06 (first-pass static review) |
| [FIXED-433](#fixed-433--a-database-raiker-could-not-read-was-reported-as-a-model-the-owner-never-chose) | Medium | Models / configured-model resolution | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-434](#fixed-434--two-public-parameters-that-changed-nothing) | Low | Models / API clarity | Fixed 2026-09-06 (first-pass static review) |
| [FIXED-435](#fixed-435--the-models-page-said-a-gate-was-on-above-providers-it-would-refuse) | Medium | Models / capability gates / web UI | Fixed 2026-09-06 (found live) |
| [FIXED-436](#fixed-436--the-registry-raiker-loaded-depended-on-the-folder-it-was-started-from) | Medium | Startup / built-in configuration | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-437](#fixed-437--a-download-the-host-restarted-away-from-stayed-running-for-ever) | Medium/High | Models / durable operations | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-438](#fixed-438--two-deploys-at-once-could-take-the-same-slot-and-the-same-port) | High | Models / managed local runtimes | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-439](#fixed-439--a-runtime-on-a-custom-port-reported-the-slots-declared-one) | Medium | Models / managed local runtimes | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-440](#fixed-440--two-expired-calls-presented-the-same-refresh-token-and-one-was-already-retired) | Medium/High | Connectors / OAuth | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-441](#fixed-441--an-event-the-index-never-heard-of-was-invisible-to-the-check-for-exactly-that) | High | Observability / event integrity | Fixed 2026-09-06 (third-pass static review) |
| [FIXED-442](#fixed-442--seven-tests-asserted-facts-about-the-laptop-running-them) | Low | Test suite / hermeticity | Fixed 2026-09-06 (found while verifying FIXED-436) |
| [FIXED-443](#fixed-443--the-web-suite-was-red-on-main-before-any-of-this) | Medium | Web CI | Fixed 2026-09-07 |
| [FIXED-444](#fixed-444--a-named-type-step-that-resolved-to-its-neighbour) | Low | Design system | Fixed 2026-09-07 (VIS2-01) |
| [FIXED-445](#fixed-445--two-lines-of-standing-prose-under-every-page-of-the-product) | Low | Navigation | Fixed 2026-09-07 (VIS2-02) |
| [FIXED-446](#fixed-446--design-was-a-work-mode-the-shell-did-not-draw) | High | Navigation / product model | Fixed 2026-09-07 (VIS2-03, VIS2-09) |
| [FIXED-447](#fixed-447--ctrl-k-printed-to-a-keyboard-that-has-no-ctrl-there) | Low | Shortcuts | Fixed 2026-09-07 (VIS2-04) |
| [FIXED-448](#fixed-448--the-posture-chip-said-protected-while-its-colour-said-otherwise) | Medium | Governance copy | Fixed 2026-09-07 (VIS2-07) |
| [FIXED-449](#fixed-449--five-ways-of-saying-which-row-you-are-on) | Low | Navigation | Fixed 2026-09-07 (VIS2-08) |
| [FIXED-450](#fixed-450--success-colour-as-the-standing-state-of-everything-that-is-merely-fine) | Low | Visual system | Fixed 2026-09-07 (VIS2-16) |
| [FIXED-451](#fixed-451--five-stores-five-read-paths-and-no-way-to-say-which-was-wrong) | **Critical** | Models / contract | Fixed 2026-09-07 (MODEL-01) |
| [FIXED-452](#fixed-452--design-had-no-model-default-of-its-own) | High | Models / Design | Fixed 2026-09-07 (MODEL-02) |
| [FIXED-453](#fixed-453--the-models-page-was-a-filing-system-for-its-own-rows) | High | Models | Fixed 2026-09-07 (MODEL-03…15) |
| [FIXED-454](#fixed-454--the-composer-grew-one-permanent-button-at-a-time) | High | Composer | Fixed 2026-09-07 (COMPOSER-01…20) |
| [FIXED-455](#fixed-455--two-reads-whose-shape-nothing-checked-took-the-page-down) | High | Web resilience | Fixed 2026-09-07 (found live) |
| [FIXED-456](#fixed-456--three-models-modals-that-escape-could-not-close) | Medium | Models / accessibility | Fixed 2026-09-07 (found live) |
| [FIXED-457](#fixed-457--rows-that-offered-raikers-own-placeholder-as-a-models-name) | Low | Models | Fixed 2026-09-07 (found live) |
| [FIXED-458](#fixed-458--a-mobile-sheet-that-was-32px-short-of-being-one) | Low | Composer / mobile | Fixed 2026-09-07 |
| [FIXED-459](#fixed-459--nothing-in-raiker-told-a-model-what-day-it-was) | **Critical** | Runtime / environment context | Fixed 2026-09-07 (ENV-01…05) |
| [FIXED-460](#fixed-460--weather-was-a-page-to-interpret-rather-than-a-reading-to-report) | High | Runtime / weather | Fixed 2026-09-07 (WEATHER-01…03) |
| [FIXED-461](#fixed-461--four-derivations-of-one-fact-about-what-a-turn-can-read) | High | Runtime / read capabilities | Fixed 2026-09-07 (WEB-01…09) |
| [FIXED-462](#fixed-462--the-hugging-face-flow-did-all-six-steps-at-once) | Medium | Models | Fixed 2026-09-07 (MODEL-09) |
| [FIXED-463](#fixed-463--come-back-and-press-look-again) | Medium | Models | Fixed 2026-09-07 (MODEL-14) |
| [FIXED-464](#fixed-464--every-live-round-had-been-writing-its-evidence-outside-the-repository) | High | Live test harness | Fixed 2026-09-07 (found live) |
| [FIXED-465](#fixed-465--eighteen-live-specs-waiting-for-a-tab-the-redesign-removed) | High | Live test harness | Fixed 2026-09-07 (found live) |
| [FIXED-466](#fixed-466--the-control-whose-job-was-to-say-connect-a-model-said-nothing) | Low | Design / composer | Fixed 2026-09-07 (found live) |
| [FIXED-467](#fixed-467--builds-third-pane-showed-tools-not-the-work) | Medium | Build | Fixed 2026-09-07 (VIS2-12) |
| [FIXED-468](#fixed-468--extensions-opened-on-a-category-instead-of-on-what-raiker-can-reach) | Medium | Extensions | Fixed 2026-09-07 (VIS2-10) |
| [FIXED-469](#fixed-469--the-project-was-chosen-again-on-every-surface) | Medium | Chat / Build / Design | Fixed 2026-09-07 (VIS2-11) |
| [FIXED-470](#fixed-470--tasks-asked-to-be-filled-in-rather-than-instructed) | Medium | Tasks | Fixed 2026-09-07 (COMPOSER-10) |
| [FIXED-471](#fixed-471--one-primary-action-that-did-not-say-what-it-would-do) | Low | Composer | Fixed 2026-09-07 (COMPOSER-15) |
| [FIXED-472](#fixed-472--every-row-wore-the-same-weight-as-the-row-that-needed-you) | Medium | Skills / sessions / approvals | Fixed 2026-09-07 (VIS2-13, VIS2-18) |
| [FIXED-473](#fixed-473--fifty-three-specs-wrote-their-evidence-one-directory-above-the-repository) | High | Live test harness | Fixed 2026-09-07 (found live) |
| [FIXED-474](#fixed-474--thirteen-z-index-numbers-and-no-way-to-say-what-was-above-what) | Medium | Shell / overlays | Fixed 2026-09-07 (VIS2-17) |
| [FIXED-475](#fixed-475--memory-allow-stopped-at-a-second-approval-gate) | High | Memory / capability authority | Fixed 2026-09-08 |
| [FIXED-476](#fixed-476--a-valid-owner-timezone-became-utc-on-windows) | High | Runtime / environment context | Fixed 2026-09-08 |
| [FIXED-477](#fixed-477--ollama-cloud-was-labelled-local-only-and-free) | Medium | Models / provider honesty | Fixed 2026-09-08 |
| [FIXED-478](#fixed-478--a-work-draft-was-lost-at-every-mode-switch) | Medium | Chat / Build / Design | Fixed 2026-09-08 (COMPOSER-11) |
| [FIXED-479](#fixed-479--a-large-paste-could-hide-the-conversation-it-belonged-to) | Low | Chat / Build composer | Fixed 2026-09-08 (COMPOSER-14) |
| [FIXED-480](#fixed-480--directly-allowed-memories-were-recallable-and-invisible) | High | Memory / web UI | Fixed 2026-09-08 (found live) |
| [FIXED-481](#fixed-481--one-elevation-for-two-grounds-and-a-picture-inside-a-card) | Low | Theme / design / shell | Fixed 2026-09-07 (VIS2-14, VIS2-15) |
| [FIXED-482](#fixed-482--designs-bar-printed-the-same-size-twice) | Low | Design / composer | Fixed 2026-09-07 (found live) |
| [FIXED-483](#fixed-483--three-work-modes-agreeing-by-habit-rather-than-by-contract) | Medium | Chat / Build / Design | Fixed 2026-09-07 (VIS2-21, VIS2-20) |
| [FIXED-484](#fixed-484--home-offered-two-of-the-three-work-modes) | Medium | Home | Fixed 2026-09-07 (page-by-page §1) |
| [FIXED-485](#fixed-485--memory-kept-settings-records-and-decisions-at-one-visual-level) | Medium | Memory | Fixed 2026-09-07 (page-by-page §10) |
| [FIXED-486](#fixed-486--two-parallel-systems-where-there-were-two-questions) | Medium | Permissions | Fixed 2026-09-07 (page-by-page) |
| [FIXED-487](#fixed-487--a-catalogue-that-existed-only-as-long-as-the-response-carrying-it) | High | Models / composer | Fixed 2026-09-12 (GLOBAL-MODEL-01/02/06/08) |
| [FIXED-488](#fixed-488--first-launch-taught-infrastructure-before-it-taught-the-product) | Medium | First launch / onboarding | Fixed 2026-09-12 (FIRST-02…FIRST-10) |
| [FIXED-489](#fixed-489--a-remembered-catalogue-outlived-the-connection-that-earned-it) | Medium | Models / provider catalogue | Fixed 2026-09-12 (found live) |
| [FIXED-490](#fixed-490--a-composer-holding-eleven-choosable-models-said-none-was-set-up) | Low | Chat / Build / Tasks composer | Fixed 2026-09-12 (found live) |
| [FIX…212152 tokens truncated…d never rotates or animates it; an empty label makes it decorative beside a visible name. The wordmark is lowercase *raiker* in Inter. The lock screen shows the ring alone: the hero render, its three orbit rings, the accent bars under the headings and the glass blur are gone. `scripts/render_brand_icons.py` draws every PNG from the same geometry (favicons light and dark, `favicon.ico`, the touch and manifest icons, `raiker/assets/raiker-icon.png`, the Setup window's mark), and `scripts/desktop_installer_art.py` redraws the installer art on the new palette.

**Evidence.** `LoginView.test.ts`, `Sidebar.test.ts`; RT-QUI-57.

## FIXED-1169 — The palette and type were not the ones 08 decided (QUI-V01, QUI-V02)

**Severity: Medium. Area: Design tokens. Status: Fixed 2026-10-25.**

**Observed.** `app.css` and the desktop shell still used the earlier slate palette and Manrope; 08 decided warm neutrals, `#2F6F8F` / `#78B7D5` for primary action, `#8A6411` for attention text, and Inter.

**Fixed.** Both themes take the QUI-V01 roles (background, surface, text, secondary text, primary action, attention fill and text, success, risk), with the derived soft fills and borders checked for contrast. Inter (`@fontsource-variable/inter` 5.3.0, SIL OFL 1.1) replaces Manrope in the web app and the desktop shell; the font licence notes are updated. The palette test now pins the QUI-V01 roles and checks secondary text on surface, background and sunken fills, accent on background, and success and risk on their soft fills at 4.5:1, and that the light attention fill stays a fill.

**Evidence.** `appCss.test.ts`; RT-QUI-57, RT-QUI-70 (dark theme).

## FIXED-1170 — Diagnostics opened on seven tiles reading Ready and 0 (QUI-L11)

**Severity: Medium. Area: Diagnostics. Status: Fixed 2026-10-25.**

**Observed.** Overview showed a list, then three and four big-number tiles (*Closed capability gates 46*), what changed, the support bundle and telemetry, all at one level; a healthy install was 1,222 px of resting state. Each unset setting was one row reading *1 required setting is unset* with the runtime's sentence as detail.

**Fixed.** Overview is **What needs attention**: one flat card per issue with the problem, what it affects, the kind of problem in words and an icon, *last checked*, the safe fix as its button, and the runtime's own words under *Technical details*. An unset default model reads *No default model is chosen* with **Choose a model**, the same words as Home. With nothing wrong it is one line. *What is working*, *What changed*, *Share or export* and *Health, in detail* are folded rows below. No coloured side stripe carries a status.

**Evidence.** `ObserveView.test.ts`, `observeAttention.test.ts`; RT-QUI-61.

## FIXED-1171 — Restoring a checkpoint was the dominant button and named little (QUI-L11)

**Severity: Low. Area: Recovery. Status: Fixed 2026-10-25.**

**Observed.** The tab was *Checkpoints*, the panel *Rewind preflight*, and *Request this rewind* was the primary button.

**Fixed.** The tab is **Recovery**. The panel, *Before you restore*, says where the checkpoint came from and when, *What will be undone* (each file, and *changed since this point* in words), *What stays as it is* (skipped files, and anything that already left the computer), and the safety checkpoint taken before it runs. **Keep things as they are** and **Ask to restore** are both ordinary buttons. Deviation: there is no separate *Create safety checkpoint* button, because the restore already captures the current state first.

**Evidence.** `CheckpointsView.test.ts`, `ChatView.rewind.test.ts`; RT-QUI-61.

## FIXED-1172 — Work's lists had no page size, and threads drew glyphs as icons (QUI-L12)

**Severity: Low. Area: Work. Status: Fixed 2026-10-25.**

**Observed.** Tasks, Goals and Projects drew every row; thread rows were as short as their text, and a pin was a `★` and tag removal a `×`.

**Fixed.** One page size for Work (`pagination.ts`, 50) with **Show N more** and *Showing 50 of 120* (`ShowMore.svelte`) on Tasks, Goals and Projects; Threads already paged from the server. Thread and goal rows are at least 64 px. The pin and the remove button are drawn icons. Deviation: Projects stays a card grid.

**Evidence.** `pagination.test.ts`, `TasksView.test.ts`, `GoalsView.test.ts`, `ProjectsView.test.ts`, `SearchChatView.test.ts`.

## FIXED-1173 — Memory carried Recall and the Knowledge Map as tabs (QUI-L12)

**Severity: Low. Area: Memory. Status: Fixed 2026-10-25.**

**Fixed.** Memory has five tabs: Overview, Memories, Suggestions, Sources, Controls. Controls holds recall and indexing (incognito, recall mode, backend, import and export) below *What Raiker has learned to do* and *Approvals you've given*; `#/memory?tab=recall` forwards there. The map is still `#/memory?tab=map` and `#/brain`, opened from Memories' **See on the map**, and carries a way back instead of the tab strip.

**Evidence.** `MemoryView.test.ts`, `memoryHub.test.ts`, `nav.test.ts`; RT-QUI-62.

## FIXED-1174 — Settings › Privacy, General and Advanced were over their size budget (QUI-L03, QUI-G01)

**Severity: Low. Area: Settings. Status: Fixed 2026-10-25.**

**Observed.** At 1280×800: Privacy about 1,970 px, General 1,399 px (1,470 px with Inter), Advanced 1,793 px, against 1,200 px.

**Fixed.** Privacy is rows: what is kept and what can leave, one line each with where it is governed, and the explanations under *How this works* disclosures; *Keep the model's working with the turn* is a switch row. General has two cards (*Language and time*, *Startup and answers*) with one-line help, and Delete account is a row of the Profile card. Advanced › Runtime shows each execution environment as one line with its measurements under *Details*. General is 1,197 px, Privacy 1,135 px and Advanced 1,195 px.

**Evidence.** `General.test.ts`, `Privacy.test.ts`, `Account.test.ts`, `BackupsCard.test.ts`, `Runtime.test.ts`; RT-QUI-63.

## FIXED-1175 — Design had no revision strip and Build's postures said Edit and Auto (QUI-L13)

**Severity: Low. Area: Design / Build. Status: Fixed 2026-10-25.**

**Fixed.** Once a picture exists, the three newest sit above Design's composer as 56 px thumbnails; pressing one selects it, so Enter edits it. Build's postures are **Plan · Suggest changes · Run within limits**, each with its consequence; the stored ids are unchanged. Export already existed only for a picture that exists, and Build's rail and side panel were already closed by default.

**Evidence.** `DesignView.test.ts`, `BuildView.test.ts`; RT-QUI-67.

## FIXED-1176 — Connecting a provider and using it in Chat left no default model (BUG-357)

**Severity: Medium. Area: Models / Home. Status: Fixed 2026-10-25.**

**Observed.** RT-QUI-07 and RT-QUI-10: Home said *No default model is chosen* beside a Chat that answered with Haiku 4.5, because a Chat choice is remembered per surface and never sets the default.

**Fixed.** The gap offers **Use Haiku 4.5, as in Chat** when Chat has a model of its own, beside **Choose a model**; it sets the default only when pressed, and a failure says nothing changed. Add model's review step already asks to **Make default** once.

**Evidence.** `WorkbenchView.test.ts`, `readinessGaps.test.ts`; RT-QUI-59.

## FIXED-1177 — Quick Entry before sign-in showed the lock screen in a 560×120 window

**Severity: Low. Area: Desktop. Status: Fixed 2026-10-25.**

**Fixed.** Signed out, `#/quick-entry` says *Sign in to Raiker first* with **Open Raiker**, which hides Quick Entry and brings the main window forward through a new `showMainWindow` bridge call (`raiker:show-main`, accepted only from Raiker's own origin). In a browser it opens Home.

**Evidence.** `App.test.ts`, `desktop/e2e/shell.spec.ts` (bridge surface); RT-QUI-58.

## FIXED-1178 — A notice outlived the decision it announced

**Severity: Low. Area: Notifications. Status: Fixed 2026-10-25.**

**Observed.** RT-QUI-51 and RT-QUI-55: *Input needed* stayed after the question was answered, and an approval's notice after its decision.

**Fixed.** Every path that settles an approval (approve, deny, answer, expire) marks the *Approval needed*, *Input needed* or critical notice for that approval read, and nothing else.

**Evidence.** `tests/test_approval_notice_settles.py`; RT-QUI-65.

## FIXED-1179 — An expired approval stayed pending in storage and its row still waited

**Severity: Medium. Area: Approvals. Status: Fixed 2026-10-25.**

**Observed.** RT-QUI-31: the Safety card said *Not done: no decision* while the tool row above it said *waiting for your decision*, and the approval stayed `pending` until something tried to decide it.

**Fixed.** The host tick has an `approval_expiry` pass: every pending approval past its time limit is settled to `expired` through the same guarded transition a decision uses, its call's row and its notice settle with it, and an `approval_expired` event names the approval, the call and the tool. The tool row reads *not done — no decision* beside an expired card, live or reopened. Found live this round: on a reopened conversation the swept row read *failed*; it reads *not done* too.

**Evidence.** `tests/test_approval_notice_settles.py`, `ToolActivity.test.ts`; RT-QUI-66.

## FIXED-1180 — A streaming answer showed its raiker: block as raw JSON (04)

**Severity: Low. Area: Chat / Build. Status: Fixed 2026-10-25.**

**Fixed.** While a turn streams, each `raiker:` fence, finished or still open, is held back and shown as one line naming it (*Preparing key figures…*); the drawn block replaces it when the turn ends. Ordinary code samples are untouched.

**Evidence.** `answerBlocks.test.ts`; RT-QUI-64 (every sample taken during the stream was free of the fence).

## FIXED-1181 — The Careful profile was remembered in one browser only (QUI-P02)

**Severity: Low. Area: Chat. Status: Fixed 2026-10-25.**

**Observed.** A Careful conversation opened on another device read Standard.

**Fixed.** The owner decided on 2026-10-25 that the profile belongs to the conversation. Sessions carry `conversation_profile` (migration `RAIKER-2122-session-conversation-profile`), set through `PUT /api/sessions/{id}/profile`, which accepts only Careful or Standard, is human-only and respects account boundaries. A choice an earlier build kept in this browser is moved to the conversation once.

**Evidence.** `tests/test_session_conversation_profile.py`, contract case, `conversationProfile.test.ts`, `ChatView.profile.test.ts`; RT-QUI-60.

## FIXED-1182 — Cards and callouts carried coloured side stripes (UI pass)

**Severity: Low. Area: Web. Status: Fixed 2026-10-25.**

**Observed.** Twenty-six rules drew a 2–4 px coloured left border on a card, callout or list item as its status (the Safety card, readiness tiles, previews, held items, the notification panel).

**Fixed.** Each is a full 1 px border in the matching soft colour, and the state each stripe stood for is also said in words. Neutral quote and timeline rules stay.

## FIXED-1183 — Small labels were uppercase and letter-spaced above headings (UI pass)

**Severity: Low. Area: Web. Status: Fixed 2026-10-25.**

**Fixed.** The 54 rules that set a label in letter-spaced capitals are sentence case, and `.kicker` and `.eyebrow` are small, semi-bold metadata. Eyebrows that sat directly above a heading (Models' *Model in use*, the Knowledge Map, Advanced › Runtime, Updates) are gone; *Model in use* is the first fact under the model's name.

## FIXED-1184 — The browser's own surfaces were not themed (UI pass)

**Severity: Low. Area: Web. Status: Fixed 2026-10-25.**

**Fixed.** The caret takes the accent, and table cells, meters and times use tabular numerals.

## FIXED-1185 — Stray controls repeated or floated on several pages (UI pass)

**Severity: Low. Area: Web. Status: Fixed 2026-10-25.**

**Observed.** Home had a row of two icons alone between the starters and *Needs your attention*; Models, Memory, Approvals and Recovery started with a help icon on a row of its own; Connections showed **Add connection** twice when nothing was connected; Approvals offered a sort over an empty queue; the map kept Memory's refresh row above its way back.

**Fixed.** Help and refresh sit beside the heading or the page actions they belong to; an empty Connections page has one **Add connection**; an empty queue hides its sort; the map shows only its way back.

**Evidence.** RT-QUI-68, RT-QUI-70 screenshots.

## FIXED-1186 — The Plan card was reported to cover the line under it (closed as not reproducing)

**Severity: Low. Area: Chat. Status: Closed 2026-10-25.**

**Observed (2026-10-23).** RT-QUI-37's capture showed the Plan card over a turn's *Completed · N steps* line.

**Closed.** The Plan card sits in the column's flow above the scrolling transcript, not over it; the earlier capture showed the transcript scrolled under the card's edge. RT-QUI-69 checks a planned turn's status line sits wholly below the card.

## FIXED-1187 — The readiness strip and a footer line disagreed (closed as not reproducing)

**Severity: Low. Area: Composer. Status: Closed 2026-10-25.**

**Observed (2026-10-19).** *Checking this model — you can still send* above the composer while a footer read *No readiness check exists for this exact model*.

**Closed.** The Quiet UI composer has one readiness line; the footer that read the record differently is gone. RT-QUI-59 checks that after connecting Anthropic without **Check**, Chat shows at most one readiness line and never that sentence.

## FIXED-1188 — The Python CI job reached its 45-minute limit

**Severity: Medium. Area: CI. Status: Fixed 2026-10-25.**

**Observed.** CI run 39612791351 was cancelled at the job's 45-minute limit partway through the tests; the suite alone took 40 min 42 s on the run before it.

**Fixed.** The suite runs in a new `python-tests` job, three shards in parallel, each serial as before. `scripts/test_shard.py` deals test files to shards longest first by the per-file seconds in `tests/test_durations.json` (measured from a full run; a new file counts as the median), and the Python 3.11 job checks that every file is in exactly one shard. The shards come to about 1,100 s each on a local run of 3,296 s.

**Evidence.** `tests/test_ci_workflow.py`.

## FIXED-1189 — grep searched literal text only, with no context lines (TOOL-02)

**Severity: Medium. Area: Tools. Status: Fixed 2026-10-25.**

**Observed.** The agent tool inventory (closed 2026-10-26), TOOL-02: `grep` advertised only `query`, matched it literally and returned one line per hit, so a model looking for every `def area_…` read whole files instead. Its executor already took `path`, `include` and `max_results`, but the schema never offered them.

**Fixed.** `grep` advertises `path`, `include`, `regex`, `ignore_case`, `context` (0–5 lines either side) and `max_results` (1–500). Literal stays the default. A regular expression is bounded before it is compiled: at most 500 characters, and a pattern with a quantified group that is itself quantified (`(a+)+`) is refused as `pattern_nested_quantifier`, because Python's `re` has no time limit and such a pattern can hold the host's thread. The container bridge passes the same arguments.

**Evidence.** `tests/test_filesystem_tools.py`; RT-TOOL-02.

## FIXED-1190 — edit_file could replace exactly one occurrence (TOOL-02)

**Severity: Medium. Area: Tools. Status: Fixed 2026-10-25.**

**Observed.** Renaming a variable used three times took three approvals, because `edit_file` refused any `old_text` that was not unique.

**Fixed.** `replace_all: true` replaces every exact occurrence and still needs at least one. The broker's preview, the approval diff and the executor read the call through one function (`edit_options`), so the change the owner approves is the change that runs. Without the flag an ambiguous match is still refused.

**Evidence.** `tests/test_filesystem_tools.py`; RT-TOOL-04 (one approval renamed `colour` to `shade` on all three lines).

## FIXED-1191 — edit_file could not insert at a line (TOOL-99)

**Severity: Low. Area: Tools. Status: Fixed 2026-10-25.**

**Fixed.** `insert_line` inserts `new_text` after that line (0 is the top) with `old_text` left empty. `old_text` became optional for this, and the validator still refuses an edit that names neither (`missing_argument:old_text`); naming both, or `insert_line` with `replace_all`, is refused by name, as is a line past the end.

**Evidence.** `tests/test_filesystem_tools.py`, `tests/test_tool_broker.py`.

## FIXED-1192 — read_file read the first 200 KB of a text file and nothing else (TOOL-02)

**Severity: Medium. Area: Tools. Status: Fixed 2026-10-25.**

**Fixed.** `offset` and `limit` read a line range of a file up to 5 MB, and the result says `line_start`, `line_end` and `line_count`. A PDF in the workspace is read as text by `pages` (`"3"` or `"1-5"`, at most 20 pages a call, from a PDF of at most 50 MB) with the same local pypdf reader uploads use, each page marked. Without the new arguments a call returns what it did before. Images are not read yet (TO_BE_FIXED, TOOL round).

**Evidence.** `tests/test_filesystem_tools.py`; RT-TOOL-03.

## FIXED-1193 — A question could not say which option Raiker would choose (TOOL-08)

**Severity: Low. Area: Chat / Approvals. Status: Fixed 2026-10-25.**

**Fixed.** An `ask_owner_question` option may carry `recommended: true` (at most one per question, refused otherwise) and a `preview` of up to 1,200 characters. The question card in Chat and Build, and the Approvals page, draw a **Recommended** tag beside that option and never pre-select it; the preview of the option picked is shown under the options. Both surfaces read the question through one parser, which drops the tags if more than one option claims them.

**Evidence.** `tests/test_owner_question.py`, `clarify.test.ts`; RT-TOOL-05.

## FIXED-1194 — web_search could not be kept to sources the turn trusted (TOOL-90)

**Severity: Low. Area: Web access. Status: Fixed 2026-10-25.**

**Fixed.** `web_search` takes `allowed_domains` and `blocked_domains` (host names, at most 20 each). Results are filtered in the host before any of them reaches the turn: a result is kept when its host is, or is under, an allowed domain and is not under a blocked one. The lists narrow what comes back and never widen the owner's blocklist, which still governs every page fetched afterwards. A list that keeps nothing says so (`web_search_no_results_in_domains`).

**Evidence.** `tests/test_web_access.py`.

## FIXED-1195 — Every web_fetch cost up to 20,000 characters of context (TOOL-91)

**Severity: Low. Area: Web access. Status: Fixed 2026-10-25.**

**Fixed.** `max_chars` lowers the content cap for one call, between 500 and 20,000; it can never raise it. The approval relay's executor passes it too. The provenance rule and PDF pages from the inventory are not done (TO_BE_FIXED, TOOL round).

**Evidence.** `tests/test_web_access.py`.

## FIXED-1196 — A push could publish a committed credential (TOOL-30)

**Severity: High. Area: Git. Status: Fixed 2026-10-25.**

**Observed.** `scripts/scan_secrets.py` failed CI on a committed key, but nothing in Raiker looked before Build pushed one, and a pushed credential cannot be taken back.

**Fixed.** The push preview reads the added lines of every outgoing commit (lines a later commit removes still count, because the remote keeps history) and matches them against the shapes CI fails on, now kept once in `raiker/security/secret_shapes.py` and imported by the script. A match refuses the push as `outgoing_commits_contain_credentials` before the owner is asked, naming each finding's path, line, rule and fingerprint, never the value, with the next step. A fixture the repository excuses, with an unexpired date, in its own `.github/secret-scan-exceptions.json` is not counted.

**Evidence.** `tests/test_git_push_binding.py`, `tests/test_scan_secrets.py`.

## FIXED-1197 — Build could not read its own CI (TOOL-20, TOOL-22)

**Severity: Medium. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` gains `checks` (a commit's check runs by `ref`, or a pull request's by `number`, with the summary and up to 20 annotations of each of the first five failures), `workflow_runs` (recent runs, optionally of one branch) and `run_jobs` (a run's jobs and the steps that failed). Each is governed exactly like an issue read: gate, decision mode, owner credential and the `api.github.com` egress rule. An App installation token for them is narrowed to `checks: read` and `actions: read`, both added to the permission ceiling. Raw job logs are not read: GitHub serves them from a storage host the connector egress rule does not include (TO_BE_FIXED, TOOL round).

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1198 — A remote file or the repository's history needed a clone (TOOL-23, TOOL-24)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` gains `commits` (the 20 newest, optionally from a `ref`) and `file` (one text file by `path` at an optional `ref`, refused for `..`, a directory, a binary or a file too large for the contents API). A transcript row and its source name the resource when there is no number.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1199 — A pull request Raiker opened could not be corrected (TOOL-26)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_write` takes `update_pull_request`: a new title, a new body or both, sent as one PATCH under approval. Never the state, the base branch or a merge, which stay the owner's. Because it names no branch, a branch-scoped delegation cannot cover it, so it always asks.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1200 — A how-do-I question about Raiker was answered from memory (TOOL-46)

**Severity: Medium. Area: Tools / Help. Status: Fixed 2026-10-25.**

**Fixed.** A new low-risk, local tool, `help_read`, reads the guide the help panel shows: no arguments lists the articles, `query` returns matching lines from the best five, `slug` reads one article (matched against the listing, never used as a path). It is in the core set every turn carries, is cited as a **Raiker help** source, and its row says which article or search it read. Found live: the turn receipt counted the articles as *2 files read*; help reads are not the owner's files and are no longer counted.

**Evidence.** `tests/test_help_read_tool.py`; RT-TOOL-06.

## FIXED-1201 — A task's prompt was never checked for injected instructions (TOOL-124)

**Severity: Medium. Area: Tasks / Security. Status: Fixed 2026-10-25.**

**Fixed.** Every task saved through Tasks or the API has its title and instructions scanned with the deterministic rules untrusted context already gets. A match raises a redacted security finding and the notice *A task's instructions look injected*, naming the task and the rules and telling the owner to read the instructions before they run unattended; the prompt itself is never stored in the finding. It never blocks the save. A task a model proposes says the same on its approval card before the owner approves it. Found live: the first wording reused *used as data, never as instructions*, which is untrue of a prompt that is instructions.

**Evidence.** `tests/test_scheduled_prompt_scan.py`; RT-TOOL-10.

## FIXED-1202 — Plan steps could not say what they waited on (TOOL-04)

**Severity: Low. Area: Chat / Build. Status: Fixed 2026-10-25.**

**Fixed.** An `update_plan` step may carry `blocked_by`, the numbers of up to five other steps. The plan is refused, with a reason the model can correct, when a number is unknown or the step's own, when the steps form a cycle, or when a step is in progress or done before what it waits on is done. The Plan card says *Waits on steps 1 and 2* under an unfinished step, and the plan re-sent to the model says *(after step 1, 2)*.

**Evidence.** `tests/test_agent_plan_and_subagents.py`, `agentPlan.test.ts`; RT-TOOL-07.

## FIXED-1203 — A conversation could not be summarised or measured from the composer (TOOL-131)

**Severity: Low. Area: Chat. Status: Fixed 2026-10-25.**

**Fixed.** Chat's composer has `/compress`, which summarises the conversation through its latest settled turn for the model (the turn menu's **Summarise**; the transcript keeps every word), and `/insights`, a sheet over the composer with the turns and model calls, the model, tokens in and out, the cost from the conversation's ledger (*Not priced* when it cannot be), the tool calls with how many asked the owner or were not done, and the most-used tools. Found live: the first version counted model calls as turns, printed the cost unformatted and lost the space before a separator.

**Evidence.** `threadInsights.test.ts`, `composerCommands.test.ts`; RT-TOOL-08, RT-TOOL-09.

## FIXED-1204 — The live work line counted a routine queued for later as running (found live)

**Severity: Low. Area: Top bar. Status: Fixed 2026-10-25.**

**Observed.** RT-TOOL-10: two routines whose first run was in 2030 made the top bar read *2 tasks running*.

**Fixed.** A queued task whose scheduled time is still ahead is waiting for its slot and is left out of the line; one that is due still counts.

**Evidence.** `liveWork.test.ts`; RT-TOOL-10.

## FIXED-1205 — Branches, tags and releases needed a clone (TOOL-23)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` gains `branches` (with the head commit and whether the branch is protected), `tags` and `releases` (tag, name, date, draft or pre-release, and the start of the notes), each governed like every GitHub read and narrowed to `contents: read`.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1206 — A turn could not search a repository's code on GitHub (TOOL-24)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` `search_code` takes a `query` of at most 256 characters, always scoped to the named repository (`repo:owner/name` is added by Raiker, never by the model), and returns the matching paths.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1207 — Issues could be read one number at a time (TOOL-28)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` gains `issues` (open issues and pull requests, each marked as which), `search_issues` (a `query` within the repository) and `issue_comments` (an issue's or pull request's comments, with their ids). Comments are untrusted content like every GitHub read.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1208 — Review comments could not be read or answered (TOOL-27)

**Severity: Medium. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` `review_comments` lists a pull request's review comments with file, line, id and which comment each replies to. `github_write` `reply_review_comment` posts one reply in a thread (`number`, `comment_id`, `body`), asked first; a branch-scoped delegation cannot cover it. Resolving a thread needs GitHub's GraphQL API and is not done.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1209 — A pull request's branch could not be brought up to date (TOOL-26)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_write` `update_pull_request_branch` asks GitHub to merge the base into the pull request's branch (GitHub's *Update branch*: a merge commit, never a rebase or force-push). It is a push, so it asks first, and no delegation covers it because it names no branch.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1210 — A failed CI run could not be re-run from a turn (TOOL-21)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_write` `rerun_failed_jobs` re-runs a workflow run's failed jobs once, asked first, under an installation token narrowed to `actions: write` (the permission ceiling now allows `actions: write`; reads still ask for `actions: read`).

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1211 — A turn could not say which GitHub account it was acting as (TOOL-29)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-25.**

**Fixed.** `github_read` `account` returns the connected account's login, name and type.

**Evidence.** `tests/test_github_connector.py`.

## FIXED-1212 — A PDF on the web came back as garbled text (TOOL-91)

**Severity: Medium. Area: Web access. Status: Fixed 2026-10-25.**

**Observed.** `web_fetch` decoded every body as text, so a PDF reached the model as binary noise, and the 400 KB fetch limit cut most PDFs short.

**Fixed.** A PDF response (by content type or its `%PDF-` header) is read up to 10 MB, kept as bytes, turned into text locally with pypdf, page by page with each page marked, and then passed through the same sanitiser as any page. `pages` chooses a page or range (at most 20; default the first 20). A cut-short or damaged PDF says so (`pdf_unreadable`). Requests now accept `application/pdf`.

**Evidence.** `tests/test_web_access.py`.

## FIXED-1213 — Build had no /compress or /insights (TOOL-131)

**Severity: Low. Area: Build. Status: Fixed 2026-10-25.**

**Fixed.** Both commands are in the shared composer list, so Build has them too: `/compress` summarises through the latest settled turn and `/insights` opens the same sheet over Build's composer. Chat and Build word the summary's outcome with one function.

**Evidence.** `threadInsights.test.ts`, `composerCommands.test.ts`; RT-TOOL-16.

## FIXED-1214 — Leaving Build's Plan posture was a menu change, not a decision on the plan (TOOL-09)

**Severity: Medium. Area: Build. Status: Fixed 2026-10-25.**

**Fixed.** When a Plan turn has written a plan with steps still to do, the plan card says *Made in Plan, so nothing has changed yet.* with **Approve plan · Suggest changes**. Pressing it moves the posture to Suggest changes, where every change still asks, and sends *Go ahead with the plan. Every change still asks me first.* Nothing moves from planning to acting without that press.

**Evidence.** `buildModes.test.ts`; RT-TOOL-15.

## FIXED-1215 — A Raiker help source opened an excerpt, not the article (TOOL-129)

**Severity: Low. Area: Chat / Help. Status: Fixed 2026-10-25.**

**Fixed.** A **Raiker help** source chip opens the help panel on the article the turn read (or the article list for a search), where the owner reads the guide, instead of the source inspector.

**Evidence.** `SourceChips.test.ts`; RT-TOOL-14.

## FIXED-1216 — A turn that needed an unconnected service could only explain how to connect it (TOOL-72, TOOL-126)

**Severity: Medium. Area: Chat / Connections. Status: Fixed 2026-10-25.**

**Fixed.** A new low-risk tool, `suggest_connection`, names a service from Raiker's connector catalogue with the turn's reason. Its row carries an **Add connection** card (*Connect Gmail* and the reason), in Chat and Build; the card links to `#/connections?add=gmail`, which opens the Add connection dialog on that service. The tool connects, stores and reaches nothing, and a connection still grants nothing until Permissions allows it. The client draws a link only to an address inside Connections. Found live: a reopened conversation showed the row without its card; the card is now rebuilt from the call's stored arguments and the catalogue.

**Evidence.** `tests/test_suggest_connection.py`, `chatPresentation.test.ts`; RT-TOOL-12.

## FIXED-1217 — A turn could load a skill only by its exact name (TOOL-70)

**Severity: Low. Area: Skills. Status: Fixed 2026-10-25.**

**Fixed.** A new low-risk tool, `skill_search`, searches the owner's installed skills by what they do, weighting the name above the description above the body, and lists them all with no query. A skill the owner turned off is named as off, with where to turn it on, and its instructions stay withheld.

**Evidence.** `tests/test_skill_search.py`; RT-TOOL-13.

## FIXED-1218 — A recalled memory did not say which conversation it came from (TOOL-104)

**Severity: Low. Area: Memory. Status: Fixed 2026-10-25.**

**Fixed.** Each `memory_search` hit remembered in one of the owner's conversations carries that conversation's id and title, read from the memory's own provenance; a conversation that is gone or belongs to another account is left out. The tool tells the model to say which conversation a fact came from when it uses it.

**Evidence.** `tests/test_phase_4_memory_mvp.py`.

## FIXED-1219 — A background command finished unseen unless the model polled (TOOL-01)

**Severity: Medium. Area: Shell / runtime. Status: Fixed 2026-10-25.**

**Fixed.** Each turn starts with one system line naming this conversation's background commands that finished since the previous turn began, with their state and exit code, and those still running, from the durable run rows (at most five of each). A `background_runs_reported` event records the notice's length. It grants nothing: reading a log or stopping a run still goes through `background_run`.

**Evidence.** `tests/test_background_notice.py`.

## FIXED-1220 — Web reads and remote MCP calls failed on a host whose only route out is a proxy (BUG-353)

**Severity: Medium. Area: Web access / MCP / transport. Status: Fixed 2026-10-26.**

**Fixed.** The route is decided before the opener. A name this host cannot resolve, with `HTTPS_PROXY` set, goes through the proxy, unpinned, with the owner's flagged sites and the address guard applied to what can still be checked; a resolved public name is dialled at its checked address with `direct=True`, so urllib never tunnels the pinned address through a proxy. Remote MCP endpoints take the same decision: a public endpoint goes through the configured proxy, and otherwise its pinned address is dialled directly. DuckDuckGo stays the zero-configuration search provider, and this is what lets it work on a proxied host.

**Evidence.** `tests/test_web_access.py` (`TestReadsAlertRatherThanRefuse`, the proxy route), `tests/test_mcp_remote_transport_trust.py`. Live, the proxy on the test host refuses `duckduckgo.com` by its own network policy, so a live search could not be shown here; `github.com` was read through the proxy (RT-TOOL-20).

## FIXED-1221 — web_fetch refused a site the owner had flagged instead of reading it with an alert

**Severity: Medium. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** Owner's decision, 2026-10-25: `web_fetch` does not refuse a URL; it alerts. A site on the owner's flagged list (Settings › Web access, or `RAIKER_WEB_EGRESS_BLACKLIST`) is read, and the result opens with a *Raiker alert* line the model is told to pass on, naming the rule that matched. The same holds for `web_search` endpoints, `web_extract` and every redirect hop. What still refuses is the owner's own network: loopback, private and link-local addresses, `*.local`, metadata services and the other built-in names, because those are not pages on the internet and reading them would let a turn reach local services, Raiker's own API among them.

**Evidence.** `tests/test_web_access.py` (`test_a_flagged_host_is_read_with_an_alert`, `test_a_flagged_search_endpoint_is_still_searched`), `tests/test_web_egress_blocklist.py`; RT-TOOL-20.

## FIXED-1222 — Plain http and a URL with credentials in it were refused outright

**Severity: Low. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** A plain `http://` page is read with a *not encrypted* alert, through a pinned plain-http opener, and a URL carrying `user:password@` is read with the credentials removed and an alert saying so. Any other scheme (`file:`, `ftp:`) is still refused as not a web address.

**Evidence.** `tests/test_web_access.py` (`TestReadsAlertRatherThanRefuse`), `tests/test_global_read_capabilities.py`.

## FIXED-1223 — A page Raiker had already flagged was read again with no word of it

**Severity: Medium. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** A read now says when the page was flagged before: if the injection scanner has a finding for that address, the result carries a *flagged before* alert, and a page whose text is shaped like instructions carries a *suspicious text* alert, both beside the untrusted-content framing that was already there.

**Evidence.** `tests/test_web_access.py` (`TestReadsAlertRatherThanRefuse`).

## FIXED-1224 — A read's alerts had nowhere to show, and Settings described a blocklist that no longer blocked

**Severity: Low. Area: Chat / Settings. Status: Fixed 2026-10-26.**

**Fixed.** A `web_fetch` or `web_extract` row shows its alerts under the row (*Alerts for this read*, a warning icon per alert), live and on a reopened conversation. Settings › Web access now says what is true: Raiker reads any public page and searches with DuckDuckGo with no account or key; the owner's list is **Flagged sites** (**Flag**, **Remove**), read with an alert; the built-in names are *always refused*, with why; and the address check answers *is read, with an alert*.

**Evidence.** `chatPresentation.test.ts`, `WebAccess.test.ts`, `tests/test_web_egress_blocklist.py`; RT-TOOL-20.

## FIXED-1225 — The help panel showed a whole chapter when the owner wanted one part of it

**Severity: Medium. Area: Help. Status: Fixed 2026-10-26.**

**Fixed.** Owner's directive, 2026-10-25: the help panel no longer hands over the full guide page. An article opens as its intro and an *In this article* list of its parts (each `## ` heading, with its first sentence); a part opens on its own, with *Previous* and *Next* and a back button to its article. Pressing **?** on a page lands on the part that answers it where one does (Approvals on *What approved means*, Permissions on *Capability gates*). Search matches part titles and summaries and lands on the part. `/api/guide/{slug}` returns the intro and the parts list, and `?part=<id>` one part; a guide link's `#fragment` opens the part that holds that heading.

**Evidence.** `tests/test_guide_surface.py`, `HelpPanel.test.ts`, `guideLinks.test.ts`, `guideSections.test.ts`; RT-TOOL-17, RT-TOOL-18.

## FIXED-1226 — help_read returned up to 20,000 characters of a whole article

**Severity: Low. Area: Help / tools. Status: Fixed 2026-10-26.**

**Fixed.** `help_read` with a slug returns the article's intro and its parts; `part` reads one part (at most 12,000 characters); a query returns the matching parts, a heading match weighted above a body match. A help source chip carries `slug#part`, so it opens the panel on the part the turn read.

**Evidence.** `tests/test_help_read_tool.py`.

## FIXED-1227 — Two help parts came back with the same redacted id and could not be opened (found live)

**Severity: Medium. Area: Help / API. Status: Fixed 2026-10-26.**

**Fixed.** The API's response redactor read a long heading anchor (`configuring-something-is-permission-for-it`) as a credential. Two such parts in one article came back as the same `[REDACTED_SECRET]`, the panel's keyed list refused the duplicate, and the view stopped updating. The guide routes now serve their text as written: they return Markdown shipped in `docs/guide`, which cannot carry an owner's secret.

**Evidence.** `tests/test_guide_surface.py::test_part_ids_reach_the_panel_unredacted`; RT-TOOL-17.

## FIXED-1228 — Help text broke at every source line (found live)

**Severity: Low. Area: Help. Status: Fixed 2026-10-26.**

**Fixed.** The guide is wrapped at about 80 columns for reading in a checkout, and the transcript renderer keeps a single newline as a line break, so every source line became its own ragged line in a 360 px panel. Hard-wrapped paragraphs and list items are joined before rendering; headings, lists, quotes, tables and fenced code keep their lines.

**Evidence.** `guideLinks.test.ts`; RT-TOOL-17 screenshot.

## FIXED-1229 — A help search typed while an article loaded was replaced by the article (found live)

**Severity: Low. Area: Help. Status: Fixed 2026-10-26.**

**Fixed.** Each load and each keystroke in search takes a number, and a load that returns after a newer one started is dropped, so an article cannot land over results the owner has started typing for. The panel's open effect also tracks only the request itself, so the panel element binding no longer reopens it.

**Evidence.** `HelpPanel.test.ts` (*never lets a slow article land over a search already typed*); RT-TOOL-18.

## FIXED-1230 — Help summaries showed their own Markdown (found live)

**Severity: Low. Area: Help. Status: Fixed 2026-10-26.**

**Fixed.** A summary is the first full sentence of the first prose paragraph, with emphasis, code marks and link targets removed, skipping a paragraph that continues a list or code block and a numbered item.

**Evidence.** `tests/test_guide_surface.py::test_summaries_are_plain_words_not_markdown`.

## FIXED-1231 — A review thread could be answered but not resolved (TOOL-27)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-26.**

**Fixed.** `github_write resolve_review_thread` (number and any `comment_id` in the thread) finds the thread through GitHub's GraphQL API by the REST comment id `review_comments` shows and resolves it, asked first like every write. An already-resolved thread says so; a comment in no thread fails by name.

**Evidence.** `tests/test_github_connector.py::test_resolve_review_thread_finds_the_thread_by_comment_and_is_governed`.

## FIXED-1232 — A turn could not say who has access to a repository or read an issue's sub-issues (TOOL-28, TOOL-29)

**Severity: Low. Area: GitHub connector. Status: Fixed 2026-10-26.**

**Fixed.** `github_read` takes `collaborators` (each login and role), `teams` (each team and its permission) and `sub_issues` (an issue's sub-issues, one line each), read-only and governed like the other reads.

**Evidence.** `tests/test_github_connector.py::test_collaborators_teams_and_sub_issues`.

## FIXED-1233 — A Jupyter notebook could be edited only as raw JSON (TOOL-03)

**Severity: Medium. Area: Files. Status: Fixed 2026-10-26.**

**Fixed.** `read_file` shows a notebook as its numbered cells (type, id, source, and a count of outputs by type), and `edit_file` takes `cell` (an index or a cell id): the edit, in any of its modes, applies to that cell's source, and the file is written back with its own indentation and key order so the approved diff is the cell. It is `edit_file`, so the approval, checkpoint and execution path are the ones every edit takes; the row reads *demo.ipynb › cell 1*.

**Evidence.** `tests/test_filesystem_tools.py::test_notebook_read_as_cells_and_edited_by_cell`; RT-TOOL-21.

## FIXED-1234 — A question about a long page got its first 20,000 characters (TOOL-11)

**Severity: Medium. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** `web_fetch` takes `question`: the page is read whole (up to 400,000 characters), and the lines that bear on the question come back with a line either side, in page order, within `max_chars`. Local and lexical: no model reads the page, and the passages are the page's own words.

**Evidence.** `tests/test_web_access.py::test_a_question_returns_the_passages_that_bear_on_it`; RT-TOOL-20.

## FIXED-1235 — A search returned snippets and left the reading to another round of tool calls (TOOL-11)

**Severity: Low. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** `web_search` takes `depth: "extended"`, which also reads the top three results with the query as their question and returns their passages, each read governed and alerted exactly like a `web_fetch`.

**Evidence.** `tests/test_web_access.py::test_an_extended_search_reads_the_top_results`.

## FIXED-1236 — Build's Plan posture sent planning_mode always and nothing read it (TOOL-151)

**Severity: Medium. Area: Build. Status: Fixed 2026-10-26.**

**Fixed.** A Plan turn now carries a system instruction: research read-only, write the plan with `update_plan`, then question the plan before presenting it (which assumption breaks it, what it depends on that was not read, the smallest version, how each step is checked, what it could break for someone else) and end with *Questions I asked of this plan*. A `plan_posture_applied` event records it.

**Evidence.** `tests/test_plan_posture_grill.py`; RT-TOOL-22.

## FIXED-1237 — Connector and channel requests followed redirects to any host, with the owner's token (BUG-350)

**Severity: High. Area: Connectors / channels / SSRF. Status: Fixed 2026-10-26.**

**Fixed.** `get_url`, `post_url` and `post_json_url`, the helpers behind every connector read and write (GitHub, Gmail, Calendar, Slack, manifest connectors, the new GraphQL calls), channel delivery, skill imports and breach monitoring, used urllib's default opener, which follows `301`/`302`/`303`/`307`/`308` to whatever host the response names and re-sends the headers. An allowlisted host answering `302 → http://169.254.169.254/…` would have been followed, carrying the `Authorization` header: SSRF and token leakage together. All three now go through the shared no-redirect opener, and a redirect fails as `redirect_refused:<status>`, never followed. Found auditing SSRF on the owner's requirement that tool-calling agents cannot reach the owner's own network.

**Evidence.** `tests/test_ssrf_redirects.py`: the bug record's own reproduction (two loopback servers, the first redirecting to the second) against each helper, and the second server receives nothing.

## FIXED-1238 — The proxy route could reach the owner's internal names (found auditing SSRF)

**Severity: Medium. Area: Web access / SSRF. Status: Fixed 2026-10-26.**

**Fixed.** The proxy route added for BUG-353 sent any name this machine could not resolve to the owner's proxy, and a corporate proxy can often resolve internal names (`intranet`, `wiki.corp`, `db.internal`) that Raiker never sees. Only a name with the shape of a public one now takes the proxy: two or more valid labels and an alphabetic top-level label that is not a private-network suffix (`.corp`, `.internal`, `.lan`, `.local`, `.home.arpa` and the RFC 6761 special-use names). Anything else is refused as unresolved. The SSRF position across every model-steered request path is now written down in [SECURITY_AND_POLICY.md](../architecture/SECURITY_AND_POLICY.md#server-side-request-forgery-ssrf), with the residual stated.

**Evidence.** `tests/test_ssrf_redirects.py` (`test_only_public_shaped_names_may_take_the_proxy`, `test_an_internal_name_is_refused_not_proxied`, and the address guard pinned against sixteen non-public addresses, NAT64 and 6to4 forms among them).

## FIXED-1239 — A proxied name was reached without checking where it leads (SSRF)

**Severity: Medium. Area: Web access / SSRF. Status: Fixed 2026-10-26.**

**Fixed.** Owner's decision, 2026-10-26: on a proxy-only host, a public-shaped name is looked up through the proxy over DNS over HTTPS (`RAIKER_WEB_DOH_ENDPOINT`, default `https://cloudflare-dns.com/dns-query`, A and AAAA) before the proxy is asked to reach it, and every answer must pass the address guard, so `rebind.example.org → 10.0.0.5` is refused as not public. A lookup that cannot be made or read refuses the read as `web_host_unverified`, with a sentence naming the setting; it is never read unchecked. The lookup itself goes only to an `https` resolver and follows no redirect. Stated with the remaining window (a re-point between the two lookups) in [SECURITY_AND_POLICY.md](../architecture/SECURITY_AND_POLICY.md#server-side-request-forgery-ssrf).

**Evidence.** `tests/test_ssrf_redirects.py` (`test_a_proxied_name_is_looked_up_and_its_answers_guarded`, `test_the_lookup_reads_a_and_aaaa_answers_and_fails_closed`), `tests/test_web_access.py`.

## FIXED-1240 — A flag meant any rule anyone typed, not a site registered as malicious

**Severity: Medium. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** Owner's decision, 2026-10-26: Raiker flags only sites a public threat feed registers as malicious. Two free, keyless feeds are downloaded to the workspace (`.raiker/threat_feeds/`): URLhaus (abuse.ch) for hosts that distribute malware, matched by host, and the OpenPhish community feed for phishing pages, matched by exact page. A match raises a `malicious_site` alert on the read, on the row, and in what the model is told to pass on; a redirect's landing page is checked too. Matching is local, so the address being read is never sent anywhere to be checked. Feeds refresh at startup when older than a day and from **Update now** in Settings › Web access, which shows each feed's size, when it was updated, and why an update failed. A feed that cannot be reached keeps its last copy. The owner's own flag rules stay as an option.

**Evidence.** `tests/test_site_reputation.py`, `WebAccess.test.ts`; RT-TOOL-20. The test host cannot reach either feed, so their download is proven with fixtures.

## FIXED-1241 — Known sites and the services the owner signs in to could be flagged

**Severity: Medium. Area: Web access. Status: Fixed 2026-10-26.**

**Fixed.** GitHub, Google, Slack, the other connectors' hosts, the forges Raiker pushes to, model providers and a short list of widely used sites are never flagged as a whole: no owner rule, environment rule or feed entry for the site raises an alert on them, and Settings refuses to flag one (*github.com is a known site and is never flagged*). One page on such a site that a feed lists (a phishing page on a site builder) is still flagged, as that page. The round-3 live test had flagged github.com by hand to prove the alert; it now proves the refusal instead.

**Evidence.** `tests/test_site_reputation.py`; RT-TOOL-20.

## FIXED-1242 — Every rule Settings refused said only that it could not be understood

**Severity: Low. Area: Settings. Status: Fixed 2026-10-26.**

**Fixed.** The rule endpoint sent its refusal as a plain string, while the page reads `detail.reason_code`, so an invalid domain, a bad wildcard and a regex that would not compile all showed *That rule could not be understood.* Refusals now carry their reason code, and the page says which shape failed.

**Evidence.** `tests/test_site_reputation.py::test_settings_refuses_to_flag_a_known_site`, `WebAccess.test.ts`.

## FIXED-1243 — A credential in a tool result was sent to the model as it was (OWASP LLM02)

**Severity: High. Area: Runtime / data protection. Status: Fixed 2026-10-26.**

**Fixed.** A file the agent read, a log it fetched or a page it opened went to the model, possibly hosted, verbatim; only the event log was redacted. Every published credential shape (Anthropic, OpenAI, GitHub, Hugging Face, AWS, Slack, Google, Stripe keys and private key blocks) is now replaced with `[credential removed: <kind>]` in the copy the model reads, so it can say a key is there without ever holding it.

**Evidence.** `tests/test_tool_result_credentials.py`.

## FIXED-1244 — A security alert fired on GitHub's own About page (found live)

**Severity: Medium. Area: Security monitoring. Status: Fixed 2026-10-26.**

**Fixed.** The capability monitor labelled any text containing the word *secret*, or any 40-character token, as secret-like, so a page about secret scanning or a URL with a long slug raised *handled a value that looks like a secret or credential*. The monitor now alerts on credential shapes only; memory keeps its broader rule for deciding what may be remembered.

**Evidence.** `tests/test_mcp_monitor.py::test_shape_sensitivity_labels_secrets_only`; RT-TOOL-23 screenshot.

## FIXED-1245 — A refused web read showed its reason code on the row (found live)

**Severity: Low. Area: Chat. Status: Fixed 2026-10-26.**

**Fixed.** `refused — web_host_unverified:duckduckgo.com` is now *refused — could not check where it leads through your proxy*, and the other address-guard refusals read the same way (*it points inside your own network*, *that name does not resolve*).

**Evidence.** `chatPresentation.test.ts`; RT-TOOL-23.

## FIXED-1246 — Settings counted the always-refused names as flags

**Severity: Low. Area: Settings. Status: Fixed 2026-10-26.**

**Fixed.** *Your own flags* said *8 rules in force, 0 yours, 0 from this host's environment, 8 built in*, but the built-in names are the local network and metadata hosts, always refused, not flagged. The line now counts only the owner's and the environment's flags; the built-in names stay listed under *Set outside this app*.

**Evidence.** `WebAccess.test.ts`; RT-TOOL-20 screenshot.

## FIXED-1247 — Tests had to switch SQLCipher memory security off because creating a workspace replayed 208 migrations

**Severity: Medium. Area: Storage / testing. Status: Fixed 2026-10-26.**

**Observed.** The test suite, CI (five jobs) and the release packaging set `RAIKER_SQLCIPHER_MEMORY_SECURITY=off`, because with the product's default (*auto*, which locks key pages where a probe passes) the suite ran about seven times slower. The owner asked whether needing that switch meant something was wrong in the implementation. It did.

**Root cause, measured.** Memory security barely changes everyday work: 2,000 reads on an open connection took 0.002 s off and 0.003 s on. What it slowed was *building* a workspace. A fresh database replayed every migration, 155 of them `ALTER TABLE ... ADD COLUMN`; each ALTER makes SQLite rebuild its schema, and with memory security on every freed allocation of that rebuild is wiped (13 ms per ALTER against 1 ms). One workspace took about 3 s on against 0.4 s off, and the suite creates thousands. The design note in `raiker/storage/sqlite.py` put the cost at "seven times on every store operation", which was the build, not the operations. It also said memory security was off by default, while the code has defaulted to *auto* since 2026-10-20; the note, KNOWN_LIMITS and a test docstring are corrected to what the code does.

**Fixed.** The first fresh workspace in a process is built by the migrations as before, and its schema and bookkeeping rows, nothing else, are exported to a template under a random per-process key in a private temporary directory, deleted at exit. Every later fresh workspace is a copy, re-keyed to that workspace's own key, with its migration timestamps reset: about 0.08 s with memory security on or off. An existing database is never touched, a template that cannot be used falls back to the normal build, and `RAIKER_SCHEMA_TEMPLATE=off` turns it off. Twenty new workspaces now take 1.9 s with memory security on (59 s before) and 1.25 s off (8 s before). One template is kept per full-text engine, so a build that resolved FTS4 is never handed FTS5 tables. CI's five overrides are removed; the desktop packaging workflow kept its own until [FIXED-1248](#fixed-1248--sqlcipher-memory-security-could-still-be-switched-off) removed the `off` mode altogether.

**Evidence.** `tests/test_schema_template.py` (the copy has the same schema and its own key, carries no data written after the build, never replaces an existing database, follows the search engine, and can be switched off); the full suite, run without the override (743 s in three local shards), found three tests that the template changed, which now count connections by database path and key templates by engine.

## FIXED-1248 — SQLCipher memory security could still be switched off

**Severity: Medium. Area: Storage / security. Status: Fixed 2026-10-26.**

**Observed.** After [FIXED-1247](#fixed-1247--tests-had-to-switch-sqlcipher-memory-security-off-because-creating-a-workspace-replayed-208-migrations) the only reason for `RAIKER_SQLCIPHER_MEMORY_SECURITY=off` was gone, and the owner ruled it is not worth keeping: an opt-out that leaves key pages unlocked, for no measured gain.

**Fixed.** `resolve_memory_security` accepts `on` (required, fails closed) and otherwise resolves *auto* (enabled after the disposable probe passes). A stale `off`, `0`, `false` or `no` is read as *auto* with a logged warning, so an old service file cannot weaken the posture. `memory_security_mode` on the health wire is now `"auto" | "on"`. Settings → Security → Database encryption loses its *Disabled by user* state. The two `off` overrides in `desktop-package.yml` and the default in `scripts/build_restart_fault.py` are removed. Guide, troubleshooting, storage spec, memory strategy and KNOWN_LIMITS describe the two modes.

**Evidence.** `tests/test_sqlcipher_memory_security.py` now runs under the real default; the off cases became probe-failure cases, and `test_a_stale_off_is_read_as_auto_and_logged` covers all four removed spellings. `tests/test_ci_workflow.py` still asserts no override on the test step.

## FIXED-1249 — SQLCipher was 4.12.0 from a third-party fork

**Severity: Medium. Area: Storage / dependencies. Status: Fixed 2026-10-26.**

**Observed.** Raiker took SQLCipher from `sqlcipher3-wheels`, a fork that packages wheels for the upstream `sqlcipher3` binding. Its newest release, 0.5.7 (January 2026), bundles SQLCipher 4.12.0 community on SQLite 3.51.1. The owner asked for SQLCipher 4.19.0 and SQLite 3.54.1.

**Fixed.** The dependency is now the upstream `sqlcipher3>=0.6.4` (released 2026-10-13, wheels for CPython 3.11 to 3.14 on Windows, macOS and Linux including arm64 and musl). It installs the same `sqlcipher3` module, so no import changed. Measured from the wheel: **SQLCipher 4.19.0 community, SQLite 3.53.4**, `ENABLE_FTS5`. SQLite 3.54.1 is not available: SQLCipher is a fork of SQLite, its version is SQLCipher's own baseline, and both 4.19.0 and SQLCipher's main branch are on 3.53.4. That gap is carried in TO_BE_FIXED. `uv.lock` and both `requirements/release*.txt` exports are regenerated. CI's floor check now asserts SQLCipher ≥ 4.19.0 and SQLite ≥ 3.53.4 as well as FTS5 with `bm25()`, `scripts/packaging_smoke_test.py` asserts the SQLCipher floor in the frozen bundle, and CI's lock check moves from `uv==0.8.17` to `uv==0.12.24`, the newest release at least two weeks old (the lock is now revision 5, which the old pin could not have written). README tells a source install to remove `sqlcipher3-wheels` before reinstalling, because both packages provide the same module. The upstream wheel ships pysqlite's zlib licence text but declares no licence in its metadata, which CI's licensing job read as unknown; `scripts/licensing_check.py` now recognises a bundled licence text by its full wording (Zlib only, every phrase required), and reports `sqlcipher3` as Zlib, which the policy permits.

**Evidence.** The full suite in three shards on SQLCipher 4.19.0 without the override; the CI step's version and FTS5 assertions run on every push.

## FIXED-1250 — Search fell back to FTS4 and recency ordering on a build without FTS5

**Severity: Medium. Area: Storage / search. Status: Fixed 2026-10-26.**

**Observed.** The text indexes used FTS5 where the build had it and fell back to FTS4 otherwise. The fallback answered every query but ranked by recency, which is indistinguishable from working, and it kept a second `snippet()` argument order, a recency-only memory query and per-engine schema templates alive for a build no supported platform has. The owner asked for FTS4 to go.

**Fixed.** FTS5 is required. `SQLiteStore.text_search_engine` still probes with a throwaway `temp` table, and a build without FTS5 now refuses the store with `store_text_search_unavailable`; the lock screen says the install is missing full-text search and to reinstall, and offers no backups (nothing is wrong with the data). The FTS4 search branches in memory, conversation and file search are removed, `snippet()` has one form, and `require_text_search_engine` accepts only `fts5`. `TEXT_SEARCH_FTS4` is kept only to recognise an index an older release built, which `_migrate_text_search_engine` converts on open as before.

**Evidence.** `tests/test_text_search_fts5.py`: `test_a_build_without_fts5_refuses_to_open_by_name` (store and health), the upgrade rehearsal now built from real FTS4 tables, and the in-place conversion test. `web/src/lib/views/LoginView.test.ts`: the lock-screen line for `store_text_search_unavailable`.

## FIXED-1251 — The locked build set carried a setuptools advisory

**Severity: Low. Area: Dependencies. Status: Fixed 2026-10-26.**

**Observed.** Auditing the regenerated lock for the SQLCipher change, `pip-audit` on `requirements/release-build.txt` reported GHSA-xmj3-9gf7-h52w against setuptools 84.0.0, fixed in 84.1.0. CI's supply-chain job would have failed on its next run.

**Fixed.** `uv lock --upgrade-package setuptools==84.1.0`, the smallest release with the fix, and both exports regenerated. Nothing else was upgraded: a blanket `uv lock --upgrade` would move 40 packages, among them FastAPI 0.141 → 0.162 and Starlette 1.6 → 1.10, which is a separate change with its own verification. `npm audit --omit=dev` reports nothing for `web/` or `desktop/`.

**Evidence.** `pip-audit` on both exports: no known vulnerabilities.


## FIXED-1252 — The same aim across conversations was never offered as a goal (QUI-F03)

**Severity: Medium. Area: Goals / Chat. Status: Fixed 2026-10-26.**

**Observed.** [06, QUI-F03](quiet-ui/README.md#documents) asked Raiker to notice an aim that comes up in more than one conversation and offer to track it, once, never again after **Not now**. Goals could only be written from Work › Goals, so an aim stated in Chat stayed in the transcript.

**Fixed.** Two ways in, both ending at the Goals form the owner already uses; nothing runs until the owner saves the goal, accepts it and starts it. **Make this a goal** in a finished turn's actions opens Work › Goals filled in from the request, with *Filled in from “…”* naming the request and the conversation's project kept (`goalHandoff.ts`). `raiker/goals/noticing.py` compares the newest request with the owner's earlier conversations by shared content words (at least three, and at least half of the shorter request), skips aims already a goal and aims dismissed before, and `GET /api/goals/suggestion` answers with at most one. `GoalSuggestion.svelte` shows it under the conversation as *This looks like an ongoing goal. Track it?* with **Track it** and **Not now**; **Not now** is kept (migration `RAIKER-2124-goal-suggestion-dismissals`) so the same aim is never offered again. Matching is by words, not by a model, so it reads nothing outside the owner's own conversations.

**Evidence.** `tests/test_goal_noticing.py`; `GoalSuggestion.test.ts`, `goalHandoff.test.ts`; RT-QUI-74 and RT-QUI-75.

## FIXED-1253 — A service held one account, and an approval did not say which (QUI-F07)

**Severity: Medium. Area: Connections / approvals. Status: Fixed 2026-10-26.**

**Observed.** The connector store kept one credential per service, so "Work Gmail" and "Personal Gmail" could not both be connected, and an approval card for a send could not name the account it would use.

**Fixed.** `raiker/runtime/connector_accounts.py` keeps named accounts per connector (migration `RAIKER-2125-connector-accounts`); each has its own credential slot (`connector#account`), the first is the default, and the existing single credential stays the default account, so nothing connected before has to be redone. A connection's page lists its accounts, adds, renames and removes them, and saves each one's credential (`ConnectorAccounts.svelte`). A connector action takes an `account` by its name; the broker resolves it before approval, a write intent records the account it was approved for, and the invoker reads that account's credential only. The approval card's *Account* line names it (*Work Gmail*), and the safety summary counts it among what the action affects. The model sees the account names, never their credentials.

**Evidence.** `tests/test_connector_accounts.py`; `approvalSafety.test.ts`; RT-QUI-76, RT-QUI-77.

## FIXED-1254 — What Raiker had made was scattered across conversations, with no Library (QUI-F15)

**Severity: Medium. Area: Work / projects. Status: Fixed 2026-10-26.**

**Observed.** Generated documents, Design images and documents, pull requests and answer blocks were each reachable only from the conversation or page that made them. QUI-F15 asked for one place, filtered by project and type, each item opening where it came from.

**Fixed.** `raiker/control/library.py` reads what already exists, owner-scoped and newest first: generated documents with their download, Design images and documents, pinned answer blocks and pull requests Raiker opened. `GET /api/library` filters by `kind` and `project_id` and refuses an unknown kind or another account's project. **Work › Library** lists them with type filters and image thumbnails; every item opens its conversation (`#/new-chat?session=…&turn=…`) or its Design document. A project's page has the same list as *Project library* (images are under Design), which replaces the *Assets* tab. An uncaptioned pinned block is named from its contents (*Revenue, Costs*), not *Key figures*.

**Evidence.** `tests/test_library.py`; `LibraryView.test.ts`; contract cases in `tests/contract_cases/library.py`; RT-QUI-72, RT-QUI-73.

## FIXED-1255 — An answer block could not be pinned to a project (04, Pin to project)

**Severity: Low. Area: Chat / visual answers. Status: Fixed 2026-10-26.**

**Observed.** [04](quiet-ui/04_VISUAL_ANSWERS.md#status) left **Pin to project** open in the block toolbar because nothing could keep a block outside its turn.

**Fixed.** **Pin** in every drawn block's toolbar keeps it in the Library (migration `RAIKER-2123-library-pins`), under the conversation's project when it has one; pressed again it reads **Pinned** and unpins. The pin is copied from the stored answer and validated again on the server: prose, a refused block or a place past the end of the answer is refused (`library_pin_not_a_block`), and nothing the browser sends becomes the pinned data. Pinning the same block twice keeps one pin. A pin moves between projects or out of one from the Library.

**Evidence.** `tests/test_library.py`; `AnswerBlock.test.ts`; RT-QUI-72, RT-QUI-73.

## FIXED-1256 — An approved send went out at once, with no way to take it back (QUI-F19)

**Severity: Medium. Area: Approvals / connectors. Status: Fixed 2026-10-26.**

**Observed.** QUI-F19 asked for *Sending in 10 s · Undo* after an approved email or message. The connector write path sent as soon as the approval resolved.

**Fixed.** `raiker/runtime/held_sends.py` holds an approved connector write for ten seconds between the approval and the send (migration `RAIKER-2126-held-sends`). The approval card and Approvals show *Sending in N s* and **Undo**; `POST /api/approvals/{id}/undo-send` cancels it while held, and the card reads *Not sent: you took it back* (`SEND_UNDONE`). **Stop** reaches a held send too: stopping the turn undoes every send it still holds. The hold is an addition to approval, never a substitute: nothing is held that was not approved, and an undone send cannot be resumed.

**Evidence.** `tests/test_held_sends.py` (the suite runs with a short hold); `SafetyCard.test.ts`; RT-QUI-77.

## FIXED-1257 — A project could not limit what Raiker may touch in it (QUI-F21)

**Severity: Medium. Area: Projects / policy. Status: Fixed 2026-10-26.**

**Observed.** QUI-F21 asked for a project's own permission limits ("may push to this one repository only"). The runtime stored no per-project policy.

**Fixed.** `raiker/policy/project_limits.py` keeps, per project (migration `RAIKER-2127-project-limits`), the repositories, web domains and connections its conversations may reach; an empty list means no limit. The broker applies them before approval to every conversation in the project: a push to another remote, a fetch of another domain or a call to another connection is refused with `denied_by_project_limit_*` and a sentence naming the limit, so the owner is never asked to approve something the project forbids. A project's Overview has **Project limits** to set them (`GET`/`PUT /api/projects/{id}/limits`), and the composer says *Project limits apply* when the chosen project has any. Limits narrow; they never grant.

**Evidence.** `tests/test_project_limits.py`; `ProjectLimits.test.ts`; contract cases in `tests/contract_cases/projects.py`; RT-QUI-73, RT-QUI-79.

## FIXED-1258 — A routine's result could not go to a connected channel (QUI-F06)

**Severity: Low. Area: Tasks / channels. Status: Fixed 2026-10-26.**

**Observed.** A routine's result went to Home and to its own conversation only. Sending it to Telegram or Slack is an unattended outbound send, which the 2026-10-24 round left open until it had its own consent.

**Fixed.** The task form offers *Also send each result to* a paired channel, a box the owner ticks, which says what it allows: *Raiker sends each finished run's result there without asking again, while that channel is on and your permissions allow channel messages*. A delivery without that consent is refused by the server (`raiker/tasks/routine_delivery.py`, migration `RAIKER-2128-routine-deliveries`). A completed run is delivered through the channel executor's existing gates, so a channel whose outbound gate is off refuses and the run says so. Active and finished rows read *Also to …*, and the delivery can be removed from the task (`DELETE /api/tasks/{id}/delivery`).

**Evidence.** `tests/test_routine_delivery.py`; `TasksView.test.ts`; RT-QUI-78.

## FIXED-1259 — Editing Raiker's draft never offered a memory (QUI-F20)

**Severity: Low. Area: Approvals / memory. Status: Fixed 2026-10-26.**

**Observed.** A correction typed in words was offered as a memory, but one made by rewriting Raiker's proposed change was not, because an edit says what the owner wanted and not why.

**Fixed.** After **Edit…** on a proposed change, Approvals asks once, *You changed Raiker's draft. Anything to remember for next time?*, in the owner's own words (`EditedDraftMemory.svelte`). **Save** files them through the same proposal and decision Memory › Suggestions uses, so secret-like text is still refused; **Dismiss** keeps nothing. Raiker does not guess a lesson from the diff.

**Evidence.** `EditedDraftMemory.test.ts`; RT-QUI-80.

## FIXED-1260 — Edit… was never offered on a proposed patch (found this round)

**Severity: Medium. Area: Approvals / Build. Status: Fixed 2026-10-26.**

**Observed.** Working QUI-F20 live, **Edit…** never appeared on an `apply_patch` approval. The editor looked for a preview of kind `patch`; the broker sends `file_diff`, so the owner could only allow or deny a change, never correct it.

**Fixed.** `editablePatch.ts` decides from the action and its arguments, not the preview kind, so Approvals and Build offer **Edit…** on every proposed patch with a body.

**Evidence.** `editablePatch.test.ts`, `ApprovalsView.test.ts`; RT-QUI-80.

## FIXED-1261 — A background task had no receipt (QUI-F16, found this round)

**Severity: Low. Area: Tasks. Status: Fixed 2026-10-26.**

**Observed.** The receipt was per turn, so a scheduled task's run, which can span several turns, had none in Tasks.

**Fixed.** `GET /api/tasks/{id}/receipt` adds up the turns of the task's run (`DashboardService.task_receipt`): model, approximate cost, what was read, what changed or was sent and what left this computer. Tasks shows it as one line on active and finished rows; the rows open only when asked, so the page does not read every receipt on load.

**Evidence.** `tests/test_turn_receipt.py`; `turnReceipt.test.ts`; RT-QUI-78.

## FIXED-1262 — Approval notices showed Markdown asterisks (found this round)

**Severity: Low. Area: Notices. Status: Fixed 2026-10-26.**

**Observed.** An approval whose permission switch is off read *…because \*\*Image generation\*\* is off in Permissions*, and an over-cap change read *\*\*This change cannot be rewound.\*\**: every surface draws an approval's notice as a sentence, and `raiker/control/dashboard_parts/approvals.py` wrote Markdown into it.

**Fixed.** Both notices are plain text.

**Evidence.** Screenshot review of this round's approvals; the approval suites read the notices unchanged.

## FIXED-1263 — Key figures read 1200 where 1,200 was meant (found this round)

**Severity: Low. Area: Visual answers. Status: Fixed 2026-10-26.**

**Observed.** A key-figure tile showed *$1200*. Large figures are read at a glance, and ungrouped digits are not.

**Fixed.** `displayFigure` groups thousands in the tiles only; the block's data, **Copy**, **CSV** and **Show as text** keep the number as given.

**Evidence.** `answerBlocks.test.ts`; RT-QUI-72 screenshot.

## FIXED-1264 — A reverse proxy on the same machine made every remote request look local (BUG-347)

**Severity: Medium. Area: Host / remote access. Status: Fixed 2026-10-26. Was BUG-347.**

**Observed.** `raiker-web` decided what is local from the socket peer. A reverse proxy on the same machine (Caddy, nginx) forwarding to `127.0.0.1:8765` is itself that peer, so on a VPS that followed the common "proxy to localhost" pattern every request from the internet arrived as a local one: password recovery reachable from anywhere, reads exempt from the abuse window, and none of the public-bind guardrails in force, because the bind was loopback.

**Owner's decision (2026-10-26).** Refuse by default; trust a named proxy on request.

**Superseded in part, the same day, by [FIXED-1266](#fixed-1266--a-proxy-that-sent-no-forwarding-header-was-still-read-as-local-bug-347-review).** The owner's review found that trusting a proxy by its headers leaves a proxy that sends none looking local; the trusted proxy (`RAIKER_TRUSTED_PROXY`) was replaced by a listener of its own. The refusal of forwarded requests on the local listener, the single `is_local_request` and Diagnostics below still stand.

**Fixed.** `raiker/api/proxy_guard.py`. A request carrying any forwarding header (`Forwarded`, `X-Forwarded-For`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Real-IP`) is never local, whatever its peer. On a loopback-only host it is refused with `403 proxied_request_refused` and a sentence naming the two ways to run behind a proxy (`RAIKER_TRUSTED_PROXY`, or `--allow-public` on a private address) and that an SSH tunnel needs neither. An owner who names the proxy's address in `RAIKER_TRUSTED_PROXY` gets its requests served under the public posture: remote for recovery, instances and the loopback rate exemption, rate limited, and with HSTS when the proxy says the browser came over HTTPS. Trusting a proxy needs `RAIKER_OWNER_TOKEN`, as `--allow-public` does, and the host refuses to start without it or with an entry that is not an address. Forwarding headers still identify nothing; they only ever make a request less trusted. Recovery, instances and the rate limiter all ask the one `is_local_request`. **Diagnostics** names the host's remote access (`remote_access` on `/api/diagnostics`): a refused proxied request raises *Requests through a reverse proxy are being refused* with what to change, and a trusted proxy raises *Raiker is reachable from the internet through a proxy*. README, *Managing the host* and the security guide describe both set-ups.

**Evidence.** `tests/test_proxied_loopback.py` (13 tests: every forwarding header refused with the security headers kept, recovery refused through a trusted proxy, no loopback rate exemption, Diagnostics, address-only entries, the owner-token requirement, fail-closed configuration); `tests/test_api_rest_hardening.py`; `observeAttention.test.ts`; RT-SEC-01, RT-SEC-02, and a manual check behind a trusted proxy (served with HSTS, recovery 403, rate limited at 120).

## FIXED-1265 — uvicorn rewrote the socket peer from X-Forwarded-For (found fixing BUG-347)

**Severity: Medium. Area: Host / remote access. Status: Fixed 2026-10-26.**

**Observed.** Live, a trusted proxy's requests were refused. uvicorn's default `proxy_headers=True` trusts `X-Forwarded-For` from `127.0.0.1` and replaces the request's client with the address in the header, so the proxy's own peer never reached Raiker: a header was deciding who the client was, the thing BUG-88 had ruled out.

**Fixed.** `raiker-web` and the desktop launcher start uvicorn with `proxy_headers=False` and `forwarded_allow_ips=""`, so the socket peer is always the peer.

**Evidence.** `tests/test_proxied_loopback.py::test_the_server_never_lets_uvicorn_rewrite_the_peer`; RT-SEC-01.

## FIXED-1266 — A proxy that sent no forwarding header was still read as local (BUG-347 review)

**Severity: High. Area: Host / remote access. Status: Fixed 2026-10-26.**

**Observed.** The owner's code review of [FIXED-1264](#fixed-1264--a-reverse-proxy-on-the-same-machine-made-every-remote-request-look-local-bug-347): the guard told a proxy apart by its forwarding headers, and passed a request with none straight through. A reverse proxy on the same machine that forwards to `127.0.0.1:8765` without `X-Forwarded-For` or its relatives (nginx and Caddy can both be set up that way) arrives from a loopback peer with nothing to mark it, so local-only pages and the loopback rate exemption were reachable through it again. Diagnostics could not see it either. The trusted-proxy setting had the same dependency: a trusted proxy that sent no header was served as local.

**Root cause.** Headers are written by the sender. On one socket, a header-less proxy and a browser on the server are the same bytes; nothing inside the request can be the boundary.

**Owner's decision (2026-10-26, from the review).** Classify a connection by the listener it arrived on. Keep the loopback listener local-only, give the proxy a listener of its own where every request is remote, keep the owner-token requirement, rate limiting and HTTPS protections for proxy traffic.

**Fixed.**

* `raiker-web --proxy-socket PATH` (a Unix domain socket, mode `0660`) or `--proxy-port N` (`127.0.0.1:N`, for Windows) opens a proxy listener beside the local one. One uvicorn server holds both sockets; `ProxyListener.accepted` reads which socket took the connection from `scope["server"]`, which uvicorn fills from the socket and no request can set. Every request there is marked remote before anything asks: recovery and instances refused, no loopback rate exemption, its own rate-limit bucket (`proxy-listener`, since the address a proxy reports identifies nobody), HSTS when the proxy received HTTPS. A header claiming `127.0.0.1` changes nothing.
* A connection with no TCP address (a Unix socket) is never local, on any listener.
* The local listener keeps refusing forwarded requests, now with a reason that names the proxy listener.
* Start-up refuses a proxy listener without `RAIKER_OWNER_TOKEN`, with `--allow-public`, on the same port as `--port`, or with both options; a socket path holding anything but a stale socket (a file, or a socket another process is serving) is left alone and refused, and the socket is created owner-and-group only rather than narrowed after. `RAIKER_TRUSTED_PROXY` is no longer read: the host refuses to start while it is set, so a configuration made for it cannot silently change meaning.
* Diagnostics: `remote_access.mode` is `loopback`, `proxy_listener` or `public`, with the listener it names (`127.0.0.1:8766`, `unix:/run/raiker/proxy.sock`). Refusals on the local listener are reported whether or not a proxy listener is open. A flag or variable in an issue card no longer breaks across lines at its hyphens (`--proxy-port` read *--* / *proxy-port*), which closes the *--allow-public wraps* item carried from Quiet UI 06.
* README, *Managing the host*, troubleshooting, the security policy and KNOWN_LIMITS describe the two listeners and never point a proxy at the local one.

**What it cannot do.** A proxy pointed at the local listener that sends no forwarding header is still the same as a browser on the server, and is treated as local. That is now a configuration the documentation never describes, not one Raiker asks for; KNOWN_LIMITS says so.

**Evidence.** `tests/test_proxied_loopback.py` (27 tests): every forwarding header and a misleading `X-Forwarded-For: 127.0.0.1` refused on the local listener; the proxy listener remote with no header and with misleading ones; HSTS only over HTTPS; the proxy's own rate-limit bucket; IPv4 and IPv6 loopback on each listener; Unix-socket connections never local; WebSockets classified the same way; Diagnostics; every start-up refusal including `RAIKER_TRUSTED_PROXY`; the socket's mode and stale-socket handling; and a **real uvicorn server** with both listeners (TCP proxy port, and a Unix socket through `httpx`), so the guard is checked against what uvicorn actually puts in `scope["server"]`. `tests/test_api_rest_hardening.py`; `observeAttention.test.ts`, `ObserveView.test.ts`. Live: RT-SEC-01 to RT-SEC-03, and `raiker-web --proxy-socket` by hand with `curl --unix-socket`.


## FIXED-1267 — Remote access was gated by a token nothing read (BUG-358)

**Severity: High. Area: Host / remote access / auth. Status: Fixed 2026-10-26. Was BUG-358.**

**Observed.** `raiker-web` refused `--allow-public`, `--proxy-port` and `--proxy-socket` unless `RAIKER_OWNER_TOKEN` was set, and its help, the README and the guides called it a hardened owner token that bound the owner session. Nothing read its value. A remote browser signed in with the password alone whenever MFA was off, and a session made on this computer worked from anywhere it could be sent.

**Owner's decision (2026-10-26).** Remove `RAIKER_OWNER_TOKEN`; require MFA for all remote access; no shared secret replaces it. The owner's password and a verified code are the mechanism, which also suits the mobile apps planned to reach Raiker later.

**Fixed.**

* The token is no longer read or required; a stale one is mentioned once at start. The docstrings and messages that claimed it bound a session are corrected.
* A remote listener opens only while every account has MFA; otherwise the start is `suspended_mfa`.
* From another device, sign-in is the password **and** a code, always; with no MFA it is refused as `remote_access_suspended`. No bearer token is returned to another device: the session is an `HttpOnly`, `Secure`, `SameSite=Strict` cookie, 12 hours idle (sliding) and 7 days at most.
* Sessions record `assurance` (password or mfa), `origin` (local or remote) and the `mfa_epoch` they were verified against (migration `RAIKER-2129-remote-access`). `AuthMiddleware` refuses a remote request on any session that is not remote, MFA-verified and current, so a session from this computer — password-only or not — opens nothing remotely.
* Turning MFA off or resetting it moves the account's enrolment counter, retiring every session verified against the old one; turning it off signs out every other device, keeps the page's own session, records a `suspended` event and notifies the owner.
* Turning MFA off, resetting it, and applying or rolling back remote access need **fresh MFA**: an elevated session granted on a code from the current enrolment (`fresh_mfa_required` otherwise). From another device elevation needs the password and a code. A reset is staged beside the active enrolment and swapped in only when the new authenticator's first code is confirmed, so remote access stays up during it.
* Sign-in, remote-access and tray answers carry `Cache-Control: no-store`.
* Signed-in devices lists each session's browser as reported (never treated as identity), *This computer* or *Another device*, *Signed in with a code* or *Password only*, and last activity, with *Sign out* per session and *Sign out all other devices* (`POST /api/auth/sessions/revoke-others`).

**Evidence.** `tests/test_remote_auth.py` (17 tests: local access without MFA; suspended without MFA; password alone yields only a ticket; password and code sign in with a protected cookie and no bearer token; wrong codes refused, logged and locked out; local sessions refused remotely; MFA off suspends; a staged reset retires old verifications; revoke one and revoke others across devices; fresh MFA for sensitive actions and both factors remotely; local-only operations refused remotely; disable from another device at once; HTTPS required; shorter remote lifetimes; the token no longer read; no-store); `tests/contract_cases/remote_access.py`; `SecurityLogin.test.ts`; live RT-SEC-05, RT-SEC-08 to RT-SEC-10. Design: [REMOTE_ACCESS.md](../architecture/REMOTE_ACCESS.md).

## FIXED-1268 — Remote access could be set only with start options, and nothing showed what was open (BUG-347 UI)

**Severity: Medium. Area: Settings / host / Diagnostics. Status: Fixed 2026-10-26.**

**Observed.** Reaching Raiker from another device meant `raiker-web` start options and environment variables; the desktop app and a service had no way to do it, the Host menu said *This machine only — loopback, not the network* whatever was true, and nothing confirmed what a host actually had open.

**Owner's decision (2026-10-26).** Keep BUG-347's dedicated-listener architecture and add one Remote access experience under Settings → Security, with three modes (This device only, Private network, Reverse proxy), never trusting forwarding headers to decide what is local.

**Fixed.**

* `raiker/app/remote_access.py` validates, stores (desired, previous, last start) and opens the remote listener; `raiker/app/host_start.py` gives `raiker-app` and `raiker-web` one start sequence, so the desktop app, a service and a server started by hand open the same listeners. A private-network listener serves HTTPS with the owner's certificate (a second uvicorn server on the same loop, `raiker/api/server_runner.py`); a proxy listener is a loopback port or a `0660` Unix socket. On Windows ports are claimed with `SO_EXCLUSIVEADDRUSE`, so a port in use is never shared.
* `GET /api/remote-access` reports what the running host has open; `check`, `apply` and `rollback` are this computer's, with fresh MFA and (to apply) an explicit confirmation; `disable` works from any signed-in device and takes effect at once. A setting that cannot start falls back to the previous one or to this device only; an unreadable one starts this device only.
* **Settings → Security → Remote access**: rows for state, connection, two-step sign-in readiness and HTTPS, with problems in words; a guided dialog (choose, details with an *Advanced* fold, server checks, review of who can reach the sign-in page, fresh MFA, then Restart now or quit and reopen); Details with the last start, recent events and Go back; Turn off in one confirmation.
* The Host menu's *Reachable from* reads the host's status. Diagnostics adds remote access on or suspended, HTTPS never seen through a proxy, remote sign-in and code failures in 24 hours, and a start that failed or fell back. A flag or variable in a card no longer breaks across lines.
* `--allow-public` and a non-loopback `--host` are retired with a message naming the new options; `--private-host`, `--private-port`, `--tls-cert` and `--tls-key` join `--proxy-port` and `--proxy-socket` as start options.

Found live in this round and fixed before it closed: re-applying a listener the host still held after it was turned off was reported *in use by another program*; a setting that failed to start read *Waiting for a restart* instead of *Not working*; the Remote access rows kept their old state after two-step sign-in was turned off until the page was reloaded.

**Evidence.** `tests/test_remote_access.py` (32 tests), `tests/test_proxied_loopback.py` (real servers over TCP, a Unix socket and TLS), `remoteAccess.test.ts`, `RemoteAccessSettings.test.ts`, `HostControl.test.ts`, `observeAttention.test.ts`; CI job *Remote access* on Windows and macOS; live RT-SEC-04 to RT-SEC-12.

## FIXED-1269 — Restart left a systemd host stopped, and was no graceful stop on Windows (found building BUG-358)

**Severity: Medium. Area: Host lifecycle. Status: Fixed 2026-10-26.**

**Observed.** Restart sets exit status 75, the status the systemd unit (`RestartForceExitStatus=75`) and launchd restart on, and signals its own process. uvicorn, after its graceful shutdown, restores the previous signal handler and raises SIGTERM again, so the process died by signal (status 143) and the launcher never returned 75; systemd's `Restart=on-failure` reads a SIGTERM death as a clean stop, so the host stopped and stayed stopped. HostControl's record was not cleared either. On Windows, `os.kill(pid, SIGTERM)` is `TerminateProcess`: no graceful shutdown at all.

**Fixed.** `raiker/api/server_runner.py` runs uvicorn without re-raising the signal, and puts `request_stop` on the app, which sets the server's own exit flag; Restart and Quit use it on every platform and fall back to a signal only for a host started some other way.

**Evidence.** `test_a_sigterm_lets_the_host_return_instead_of_dying` (a real process returns 75 after SIGTERM), `test_restart_stops_the_server_gracefully_with_its_exit_status`.

## FIXED-1270 — A known password bought unlimited MFA code guesses (found building BUG-358)

**Severity: High. Area: Auth. Status: Fixed 2026-10-26.**

**Observed.** A successful password check reset the failed-attempt counter even when MFA was still to come. Signing in again between wrong codes therefore cleared the five-attempt lockout every time: anyone with the password could guess codes without limit.

**Fixed.** With MFA on, the password no longer clears the counter; only a verified code does. Five wrong codes lock the account for fifteen minutes, as five wrong passwords do.

**Evidence.** `test_wrong_codes_are_refused_logged_and_lock_out`.

## FIXED-1271 — Any signed-in session could switch MFA off by starting enrolment again (found building BUG-358)

**Severity: High. Area: Auth. Status: Fixed 2026-10-26.**

**Observed.** `POST /api/auth/mfa/enroll` needed only a session, and over an active enrolment it stored a new secret and marked MFA not enrolled. A session without fresh proof could turn two-step sign-in off this way, where turning it off directly needed an elevation.

**Fixed.** Over an active enrolment it needs fresh MFA, and the new secret is staged beside the active one, which stays in force until the new authenticator's first code is confirmed.

**Evidence.** `test_an_mfa_reset_is_staged_and_retires_old_verifications`; `SecurityLogin.test.ts` (reset only with the password and a fresh code).

## FIXED-1272 — Host Quit and Restart, and the tray's session exchange, answered other devices (found building BUG-358)

**Severity: Medium. Area: Host / remote access. Status: Fixed 2026-10-26.**

**Observed.** `/api/host/quit` and `/api/host/restart` needed only a host-control session, and `/api/tray/session` only its one-time secret; none was restricted to this computer.

**Fixed.** All three are this computer only (`loopback_only`). Another device can still turn remote access off, which needs neither.

**Evidence.** `test_local_only_operations_refuse_another_device`; live RT-SEC-08.

## FIXED-1273 — Security settings showed their defaults as the account's state while loading (found live)

**Severity: Low. Area: Settings. Status: Fixed 2026-10-26.**

**Observed.** Until its reads returned, Settings → Security said two-step sign-in *Off*, *0 signed in* and the vault key *Missing*, which are the component's defaults, not the account's state. Found in the RT-SEC-07 screenshot.

**Fixed.** Those rows say *Reading…* until the server has answered, and their actions wait for it.

**Evidence.** `SecurityLogin.test.ts` (says it is reading, not Off).

## FIXED-1274 — A signed-in owner on another device was rate limited within a minute (found live)

**Severity: Medium. Area: Host / remote access. Status: Fixed 2026-10-26.**

**Observed.** In the final RT-SEC run, signing in again from the other device after a few pages was answered `429`, and the lock screen said *Authentication failed.* Every remote request — the dozens of reads one dashboard page makes included — was counted in the same 120-a-minute window that limits sign-in attempts, so ordinary use from another device locked the owner out of signing in.

**Fixed.** `RateLimitMiddleware` (`raiker/api/security.py`) counts a request that presents a session (a bearer token or the session cookie) in a window of its own, five times wider, per peer. Sign-in, MFA, elevation, recovery and the session mint (`SIGN_IN_PATHS`) stay in the strict window whatever the request carries, so a credential cannot buy more password or code guesses; a forged credential buys only the wider, still bounded, read window and is refused by the auth check. The lock screen says *Too many attempts in the last minute* for a `429` instead of blaming the password.

**Evidence.** `tests/test_api_rest_hardening.py::test_a_signed_in_client_has_a_wider_window_of_its_own` (and the existing limits, adjusted to the two windows); `LoginView.test.ts` (too many attempts); live RT-SEC-07 to RT-SEC-11 in one run with no `429` in the host log.

## FIXED-1275 — Local MCP servers and plugin code could not run at all after host launchers were blocked (native sandbox)

**Severity: High. Area: Execution / MCP / plugins. Status: Fixed 2026-11-01.**

**Observed.** Once host process launchers were blocked, every local stdio MCP session and every plugin entrypoint refused with `native_sandbox_required`, even on hosts whose boundary was enforced.

**Fixed.** Both run in the native sandbox through `raiker/execution/commands/sandboxed_program.py`: the script's folder is copied into a throwaway folder and runs there with no network; output stays bounded while read. Hosts without an enforced boundary still refuse.

**Evidence.** `tests/test_mcp_sandbox.py`, `tests/test_plugin_sandbox.py` (real boundary on Windows 11), the MCP suite (`test_mcp_runtime.py`, `test_mcp_server_secrets.py`, `test_mcp_process_environment.py`, …).

## FIXED-1276 — Commands on Windows' restricted account never received the environment Raiker built for them

**Severity: High. Area: Native sandbox (Windows). Status: Fixed 2026-11-01.**

**Observed.** The account boundary started every command with the account's profile environment only, so `GIT_CONFIG_GLOBAL` (which keeps a planted `.gitconfig` from becoming Git's global configuration), interpreter settings and an MCP server's own secret were dropped.

**Fixed.** The runner overlays its environment on the account's identity and folders, read from the account's `ProfileList` entry; building the block from a logon token failed with `ACCESS_DENIED` while another run held the hive.

**Evidence.** `account_windows.rs` unit test `the_runner_environment_overlays_the_profile_but_not_the_account_identity`; `tests/windows_account.rs` 6/6, three parallel runs; `tests/test_mcp_server_secrets.py` on the real boundary.

## FIXED-1277 — Hosted Linux CI measured egress as indeterminate, so every sandboxed command there refused

**Severity: High. Area: Native sandbox (Linux). Status: Fixed 2026-11-01.**

**Observed.** The probe's egress control arm connected to a closed port on the default gateway; hosted networks drop that packet silently, so the outside arm never answered and `NativeSandboxProof.available` was false on CI.

**Fixed.** The probe listens on the host's own outward (never loopback) address for the length of the measurement; no packet leaves the machine. The gateway remains the fallback without a default route.

**Evidence.** CI "Show the native sandbox measurement" now prints `True … 'egress': 'enforced'`; WSL2 probe `connect_destination` is the host's own address.

## FIXED-1278 — Linux sandboxed commands failed to start on a busy session (`RLIMIT_NPROC`)

**Severity: High. Area: Native sandbox (Linux). Status: Fixed 2026-11-01.**

**Observed.** With `max_processes` 64 (commands) or 32 (hooks, MCP, plugins), `bwrap` failed with `Creating new namespace failed: Resource temporarily unavailable` on hosts where the user already ran other tasks: the kernel counts the limit against all of the user's tasks, in every PID namespace.

**Fixed.** The runner sets the limit inside the run's user namespace through its own exec shim (`--nproc-limit`), where only the run's tasks count.

**Evidence.** `linux_probe.rs`: `a_small_process_allowance_still_launches_beside_the_users_other_processes`, `the_process_allowance_still_stops_a_run_that_forks_past_it`; WSL2 measurement in `NATIVE_SANDBOX_MIGRATION.md`.

## FIXED-1279 — Native background runs were lost on every restart of Raiker (BUG-194 regression)

**Severity: Medium. Area: Commands. Status: Fixed 2026-11-01.**

**Observed.** The native backend started background runs in-process, so the detached supervisor the host backend used was gone and a restart recorded each run `lost`.

**Fixed.** On Linux a background run without downloads is started under the detached supervisor, which runs the runner; `restart_recovery` is reported only there.

**Evidence.** `tests/test_command_supervisor_reattach.py` on real Bubblewrap (WSL2).

## FIXED-1280 — `python -cCODE` and `python -Ic CODE` passed the command policy's `-c` refusal

**Severity: Medium. Area: Command policy. Status: Fixed 2026-11-01.**

**Observed.** The policy compared each whole argument with `-c`, so the attached (`-cCODE`) and clustered (`-Ic`) spellings Python accepts were let through.

**Fixed.** Python's options are parsed as Python parses them, stopping at the script or the module; `-c` in any spelling is refused and `-m` names one of `venv`, `pip`, `pytest`, `unittest`.

**Evidence.** `tests/test_project_setup_policy.py::test_other_code_and_other_cargo_commands_are_refused`.

## FIXED-1281 — Sandboxed commands ran the first program on Raiker's path, or a copy's program looked up from Raiker's folder

**Severity: Medium. Area: Native sandbox. Status: Fixed 2026-11-01.**

**Observed.** A bare `python` resolved to the project's own `.venv` interpreter on another drive, which the Windows sandbox account cannot run; `.venv/bin/python` was looked up from Raiker's working folder rather than the copy; and a virtualenv's linked `bin/python` was refused as outside the workspace.

**Fixed.** `command_executable` resolves a path-like name in the command's folder in the copy and a bare name to the first program the sandbox can reach; the binary check is on where the program sits, not what it links to.

**Evidence.** `tests/test_project_setup_policy.py::test_a_real_copy_gets_its_own_virtualenv_and_promotes_none_of_it` on Windows 11 and WSL2.

---
## FIXED-1282 — A release could ship a commit whose sandbox was unproven, and an unsigned beta carried no verifiable origin

**Severity: Medium. Area: Release. Status: Fixed 2026-11-01.**

**Observed.** `release.yml` built and published from any commit, including one whose native-runner enforcement tests had failed on a platform it ships to. A beta built without platform identities (`signing: skip`) reached owners with only a SHA-256 in the same release notes to check it against, which proves nothing about who built it.

**Fixed.** The `plan` job refuses a commit unless every `Native runner (<os>)` check from `ci.yml` passed on that exact commit. Both draft jobs sign every download keylessly with the repository's GitHub identity (`actions/attest-build-provenance`, Sigstore, with `id-token: write`) and then run `gh attestation verify --signer-workflow …/release.yml` on each file before the draft exists; the notes tell owners to run the same command.

**Evidence.** `tests/test_release_workflow.py::test_a_release_requires_the_sandbox_enforcement_tests_on_every_platform` (the gate's platform list must match the CI matrix) and `::test_every_published_download_is_signed_with_the_repository_identity`; the gate's query run against `d2d61d37` returned all four platforms `success`.
