# First beta release plan

> Owner scope update: personal use for at most five users, PC first and
> phone/iPad later; no commercial-grade distribution/signing prerequisite.
> Piper is removed in favor of Kokoro-82M. The earlier `6c211b60` signed
> candidate/audit precede this change and retain their original SHA.
> [Authoritative scope and remaining engineering checks](#appendix-a--owner-scope-2026-11-09).
>
> 2026-11-16: what the owner meets first — publishing, the default command
> boundary per platform (WSL2 on Windows), first run, postures and Health — is
> owned by the [ready-to-use plan](READY_TO_USE_PLAN.md)
> ([ADR-0006](../adr/ADR-0006-one-supported-path-per-machine.md)); this plan
> keeps the release gates and their evidence.


**Status:** active plan, opened 2026-11-02. **Owner:** release owner.
**Target:** Raiker `0.9.0-beta.1`, the personal PC beta for at most five users, as soon as the applicable gates in
[Beta release criteria](#beta-release-criteria) pass on one commit.

This plan turns the beta checklist into tracked work. For each of the twelve
areas it records what the code does **today** (with the evidence or the
document that says so), what is left, the UI and UX changes the area needs,
the evidence that closes it, and the beta decision: **Ship**, **Ship limited**
(available with a stated limit), **Preview** (off by default, labelled), or
**Not in beta** (hidden or refused, never half-working).

It does not replace the ledgers. Defects stay in
[TO_BE_FIXED.md](TO_BE_FIXED.md); closures go to
[FIXED_ITEMS.md](FIXED_ITEMS.md); scenarios and run records follow
[TESTING.md](TESTING.md); desktop package evidence lives in
[desktop package acceptance matrix](#appendix-d--desktop-package-acceptance-matrix). Native voice
conversation has its own specification:
[VOICE_CONVERSATION_SPEC.md](VOICE_CONVERSATION_SPEC.md).

## How to read this plan

| Mark | Meaning |
|---|---|
| ✅ | Done and evidenced (the evidence is named) |
| 🟡 | Implemented, evidence missing or partial on some platform |
| 🔴 | Not done; a release blocker for the scope it belongs to |
| ⚪ | Out of beta scope by decision; the product must refuse or hide it |
| ⏭ | Moved to `beta.2` by the owner's decision; not a `beta.1` blocker |

Priority: **P0** blocks `beta.1`; **P1** should land in `beta.1` but can slip
to `beta.2` with a known-issue entry; **P2** is after beta.

Effort: **S** under a day, **M** two to five days, **L** more than a week.

## The beta in one paragraph

`beta.1` is a **local, single-owner desktop app**, qualified first on the owner's
Windows PC. Linux artifacts retain their separately recorded evidence; macOS
owner-hardware qualification waits for beta.2. Phone and iPad access is later
work. It offers Chat, Build, Models,
Tasks, Schedule, Memory and Settings. It works with hosted providers and with
local models (Ollama, LM Studio, and the llama.cpp engine Raiker installs).
**Command execution runs only where the native sandbox measures as enforced
on that host, and is refused everywhere else** — that is already the fail-closed
behaviour, and the beta ships with it rather than waiting for every platform.
Voice ships as **on-device dictation and read-aloud** (managed engines, see the
voice spec, Phase V1); hands-free conversation is a **Preview**. Design ships
limited (no live image provider claim until BUG-287 closes). Remote access,
plugins that need network, and unverified integrations are **Not in beta** or
**Preview**.

## Beta scope by area

| # | Area | Beta decision | P0 items left |
|---|---|---|---|
| 1 | Native sandbox & security | Ship limited — execution only where measured | Windows ACL/profile gaps, safe promotion, fail-closed audit |
| 2 | Desktop installation & updates | Ship | Fresh PC installation, update/rollback and exact-candidate evidence |
| 3 | AI models & local inference | Ship | Live llama.cpp CI evidence, failure-mode tests |
| 4 | Core autonomous agent | Ship | Restart-recovery scenario, honest-completion tests |
| 5 | Build & coding agent | Ship limited — disposable copy only | Conflict detection on Apply, iterate-on-failure evidence |
| 6 | Memory & data protection | Ship | Corruption recovery drill, egress audit |
| 7 | UI & UX | Ship | Quiet UI open items, error copy audit, accessibility pass |
| 8 | Voice & design | Ship limited (dictation, read-aloud); conversation Preview | Managed speech engine, permission/cancel tests |
| 9 | Plugins, integrations & permissions | Ship limited — supported list only | Supported/experimental labels, revoke tests |
| 10 | End-to-end testing | Gate | Seven journeys with real models and evidence |
| 11 | CI/CD & release quality | Gate | All workflows green on the release commit |
| 12 | Documentation & beta operations | Ship | Feedback route, known issues, withdrawal process |

---

## 1. Native sandbox & security

**Today.** The Docker-free native sandbox is **incomplete and not release-ready**
on every platform (TO_BE_FIXED, *Release blocker: native sandbox migration
incomplete*). What exists:

- Linux Bubblewrap (and Bubblewrap inside WSL2) measures memory, CPU, process
  count and wall-time limits against outside controls, and hides host
  configuration. It passed on hosted Ubuntu once the targeted AppArmor profile
  was loaded.
- Windows uses a pool of four restricted accounts with a WFP loopback filter,
  Job Object limits and ConPTY terminals, measured on Windows 11. Known gaps:
  per-task profile reset, LSA logon-right denials, explicit ACEs under denied
  roots, and AppContainer's `ALL APPLICATION PACKAGES` exposure on `.git`.
- macOS uses a Seatbelt profile plus a sandbox-account pool. Hosted runner
  checks have passed (SB-2); owner-hardware qualification waits for beta.2.
  `RLIMIT_AS` is not enforced by XNU, so the footprint supervisor replaces it.
- Plugins and local MCP stdio servers run in the native sandbox and are refused
  on hosts without an enforced boundary.
- Disposable per-session project copies with reviewed Apply are wired in.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| SB-1 | Windows isolation: ACLs, network, credentials, account cleanup | 🔴 | P0 | L | Per-task profile reset; deny network/remote logon rights; scan explicit ACEs under denied roots; scan explicit grants inside `.git`; measure the WFP filter on hosted and owner machines; account cleanup on uninstall |
| SB-2 | macOS Seatbelt enforcement, containment, limits | ⏭ | P0 | M | **Moved to beta.2 (owner, 2026-11-08).** macOS hardware runs wait for beta.2; the hosted macOS runner checks stay in CI. Native-runner checks passed on `macos-15` and `macos-15-intel` for `9c532624`. Preserve this evidence on the release commit and add fresh-installer, toolchain and adversarial tests. |
| SB-3 | Linux Bubblewrap and WSL2 enforcement | ✅ | — | — | **2026-11-08:** WSL2 re-measured on the candidate with every observation enforced, `windows_interop` included; the systemd user-manager requirement for whole-run limits is in the Build guide ([record](../architecture/NATIVE_SANDBOX_MIGRATION.md#wsl2-re-measured-on-the-beta-candidate-2026-11-08)) |
| SB-4 | Commands, plugins, hooks and local MCP use the sandbox or fail closed | ✅ | — | — | **Inventory test landed** (`tests/test_process_spawn_inventory.py`): every process-spawning module in `raiker/` is listed with a reviewed category (sandbox, Raiker-owned program, host lifecycle, read-only facts, owner-approved host operation); a new spawn site or any shell use fails CI. **2026-11-08:** `tests/test_hook_events_need_the_boundary.py` checks all 20 dispatched events: the command hook never starts on the host, the refusal is recorded as `native_sandbox_required`, and an enforcing hook on a deciding event asks the owner |
| SB-5 | Disposable workspaces, reviewed promotion, rollback, crash recovery | 🟡 | P0 | M | **2026-11-08:** Undo Apply and a journalled Apply that a hard kill part-way rolls back on the next start ([FIXED-1332](FIXED_ITEMS.md#fixed-1332--an-apply-could-not-be-undone-and-a-crash-part-way-left-the-project-half-written-sb-5)). **2026-11-09:** Linux Apply now pins no-follow parent handles and survives link swaps and persistent ENOSPC ([FIXED-1370](FIXED_ITEMS.md#fixed-1370--linux-apply-could-follow-a-parent-swapped-after-its-link-check), [FIXED-1371](FIXED_ITEMS.md#fixed-1371--failed-apply-rollback-discarded-the-only-recovery-backups)). Still required: Windows/macOS promotion handles and the separate TaskTree file-tool race |
| SB-6 | No protected-file writes, no limit escape, no direct host execution | 🟡 | P0 | M | Adversarial suite per platform (below), run in CI where hosted runners allow it and recorded from owner machines where they do not |

**Adversarial suite (SB-6), one test per attack:** write `.git/config`,
`.raiker/`, the user's home dotfiles and a sibling project; follow a symlink
or junction out of the copy; fork bomb; memory balloon; detached daemon that
outlives the task; open a socket to a host loopback service; read another
sandbox account's copy; read the vault key file.

**Beta decision.** Ship limited. Execution is available on a host only when
`NativeSandboxDriver.probe` reports every mandatory observation enforced. Where
it is not, Chat, Models, Memory and planning still work, and command-based
tools refuse with a sentence and a link.

**UI / UX.**
- Settings → Advanced → Runtime → **Command sandbox** shows a per-observation table (enforced /
  not enforced / unknown) and one line on what that means: *"Commands run in
  an isolated copy of your project"*, or *"Commands are turned off on this
  computer because X could not be confirmed"*.
- ✅ The composer's runtime chip turns amber with *"Commands unavailable here"*
  when the probe fails. Build's Run button is disabled with that tooltip, not
  hidden; Plan and Propose still work (FIXED-1315, RT-BETA-06).
- An approval card for a command always states where it will run (*isolated
  copy*, *WSL2*, *restricted account*).

---

## 2. Desktop installation & updates

**Today.** `desktop-package.yml` builds and smoke-tests every target unsigned.
The installers check requirements before copying files, and the first-run
setup verifies each component (Appendix D, run 39327713463: all
seven jobs green). Later signed-candidate evidence for `6c211b60` is recorded
below; do not infer a public release from it. Commercial publisher identities
are outside the personal-beta scope. Runner publisher pins remain a separate
integrity limitation (`runner_publisher.py`).

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| IN-1 | Working installers per supported OS | 🟡 | P0 | S | The current unsigned matrix passed, including `macos-15`; rerun the full signed candidate on the exact release commit. |
| IN-2 | Dependencies installed or guided | 🟡 | P0 | M | Bubblewrap/AppArmor on Linux: the setup check names the exact package command per distro and offers **Copy command**. WSL2 Ubuntu Base download from Settings with checksum. llama.cpp and the speech engines are installed by Raiker on demand (done for llama.cpp in PR #245; speech engines in the voice V1 change, with the catalogue pins listed under VD-1) |
| IN-3 | Signing and runner authenticity | ⏭ | P0 | M | **Moved to beta.2 (owner, 2026-11-08).** A real Windows code-signing certificate and an Apple Developer ID wait for beta.2. Until then, the self-signed Windows and GPG Linux signing that already passes stays in the pipeline. **2026-11-07:** `signing: require-except-macos` signs Windows (self-signed beta certificate) and Linux (GPG), and every signed installer is checked against the identities pinned in `desktop/signing/identities.json`; signed candidate run [42430871211](https://github.com/sharRahul/Raiker/actions/runs/42430871211) passed on every target ([FIXED-1320](FIXED_ITEMS.md#fixed-1320--both-authenticode-readers-handed-powershell-a-path-it-throws-away-in-3-found-this-round), [FIXED-1321](FIXED_ITEMS.md#fixed-1321--windows-and-linux-builds-could-not-be-signed-without-an-apple-identity-and-nothing-checked-the-signer-in-3)). Still required: a CA-issued Authenticode certificate, then `WINDOWS_PUBLISHER_PINS` and `publisher_verified`; an Apple Developer ID for macOS (TO_BE_FIXED, *Windows builds are signed with a self-signed beta certificate*) |
| IN-4 | Upgrades, rollback, clean uninstall | 🟡 | P0 | M | Signed-channel update test (0.9.0-beta.1 → beta.2) per platform; a downgrade path that restores the previous app while the schema generation is unchanged (the store already refuses a newer schema — `store_schema_newer`); uninstall removes the sandbox accounts, WFP filter and runner grants on Windows |
| IN-5 | First launch on clean machines | ⏭ | P0 | M | **Moved to beta.2 (owner, 2026-11-08).** Clean-install runs on fresh VMs wait for beta.2. Run T-01 on fresh VMs: Windows 10 22H2, Windows 11 24H2, macOS 14 and 15, Ubuntu 22.04/24.04, Fedora 40; record in RELEASE_ACCEPTANCE_MATRIX |

**UI / UX.**
- The installer's *Checking this computer* page gains an optional
  **Voice & local AI** step: off by default, with sizes and a recommendation
  from detected hardware (see voice spec §6). It only records the choice; the
  downloads run inside Raiker after first start, so the installer stays small.
- First-run setup ends on a **Ready** page listing what was set up and what was
  skipped, each with a *Set up later in Settings* link.
- Settings → **About & updates** shows the channel (*Beta*), the installed version,
  a signature status (*Verified by Raiker* / *Unsigned development build*), and
  **Roll back to previous version** when one is kept. ✅ Release stage and
  signature (FIXED-1315, RT-BETA-01); the rollback action waits on IN-4.

---

## 3. AI models & local inference

**Today.**
- Hosted providers and Ollama/LM Studio have readiness checks, a decision
  service, fallback sequences and live specs.
- **PR #245** adds the managed llama.cpp engine:
  - hardware detection (CUDA, Vulkan, Metal, CPU) and verified installs from
    ggml-org releases;
  - GPU-layer, context and memory planning with a memory guard;
  - a supervisor with health checks, out-of-memory recovery, crash restart,
    restore at startup and clean shutdown;
  - Models UI for all of it;
  - unit, integration, API and UI tests, plus a CI workflow on all three OSes.
- The initial 2026-11-02 live matrix failed before installation because the
  stable release had no runtime archives. PR #246 repaired selection of a
  verified build-bearing release; the three-OS live jobs passed. Owner GPU
  hardware and fresh signed-installer evidence remain in MD-2.
- **2026-11-06 hosted UI check:** Anthropic, OpenRouter and OpenAI passed real
  UI credential entry, catalogue selection, readiness and exact-model Chat
  answers ([run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-real-provider-ui-validation)).
  MD-1 remains open for local providers and release-commit qualification.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| MD-1 | Cloud and local provider connections | 🟡 | P0 | S | **2026-11-07:** providers outside the six are tagged *Experimental* in Models › Add ([FIXED-1315](FIXED_ITEMS.md#fixed-1315--the-betas-labels-and-limits-were-not-visible-where-the-owner-decides-beta-plan-1-2-3-6-8-9)). Anthropic, OpenRouter, OpenAI and Ollama (a cloud model) passed live through the UI ([run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-beta-release-plan-round)). The managed llama.cpp engine passed live on the owner's NVIDIA GPU ([RT-GPU-02](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-gpu-signing-and-settings-round)). **2026-11-08:** all five owner-reachable providers completed a live Chat turn that lists the workspace with a tool: Anthropic (`claude-haiku-5-5`, with a workspace ID), OpenAI (`gpt-5-nano`, after [FIXED-1343](FIXED_ITEMS.md#fixed-1343--every-openai-gpt-5-model-was-refused-and-read-as-cannot-execute)), OpenRouter, Ollama (`gpt-oss:20b-cloud`) and LM Studio (`qwen/qwen3-8b`, 32K context, on the GPU). Output limits were measured per provider ([FIXED-1344](FIXED_ITEMS.md#fixed-1344--hosted-and-local-server-profiles-stopped-answers-at-1024-tokens)). Still required: the same on the release commit |
| MD-2 | llama.cpp native install, deploy, GPU config | 🟡 | P0 | S | PR #246 repaired automatic source-only stable-release selection; the `llama-cpp.yml` live jobs passed on Windows, macOS and Linux. **2026-11-07:** NVIDIA passed on the owner's RTX 4080 SUPER: Raiker recommended and installed the CUDA build (b12192) and served a model entirely on the GPU ([run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-gpu-signing-and-settings-round)). Still required: AMD (Vulkan), plus fresh signed-installer validation on the release candidate. **AMD (Vulkan) moved to beta.2 (owner, 2026-11-08);** the NVIDIA run is the beta.1 evidence. |
| MD-3 | GGUF downloads, integrity, inference | ✅ | — | — | **2026-11-07:** every written file is checked against the hub's LFS SHA-256 (or Git blob id) and removed on a mismatch ([FIXED-1313](FIXED_ITEMS.md#fixed-1313--a-downloaded-gguf-was-never-checked-against-the-bytes-the-hub-publishes-md-3)). Live RT-GPU-02: a Hugging Face GGUF pinned to a revision, verified, served on the GPU and answering in Chat; it found and fixed every auto-sized turn being refused ([FIXED-1319](FIXED_ITEMS.md#fixed-1319--every-turn-to-a-local-gguf-sized-on-auto-was-refused-with-a-bare-http-400-md-3-found-on-the-owners-gpu), [run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-gpu-signing-and-settings-round)) |
| MD-4 | Detection, readiness, selection, fallback | ✅ | — | — | Model decision service, readiness ledger and fallback sequence (FIXED items) |
| MD-5 | Failures, rate limits, timeouts, recovery | ✅ | — | — | **2026-11-07:** the matrix runs against a real local socket for both adapters (`tests/test_provider_fault_matrix.py`). It found and fixed a cut-off stream recorded as finished, and `Retry-After` is now carried ([FIXED-1312](FIXED_ITEMS.md#fixed-1312--a-stream-that-closed-early-was-recorded-as-a-finished-answer-md-5-found-this-round)). **2026-11-08:** *Rate-limited until …* on Models, no re-check before it, and a receipt that names the fallback and why ([FIXED-1323](FIXED_ITEMS.md#fixed-1323--rate-limits-and-fallbacks-were-not-said-where-the-owner-reads-them-md-5)) |

**UI / UX.**
- Settings → Advanced → Model serving: Running models holds the engine;
  Advanced holds GPU/context/memory tuning. Library and Activity have their own
  focused sections. Models keeps the inventory and Add flow.
- Every provider row shows one state word (*Ready*, *Needs key*, *Not running*,
  *Rate-limited until 14:32*) with one action button.
- When a fallback answers, the turn receipt says so in the turn: *"Answered by
  Llama 3.2 3B (local) because Claude was rate-limited."*

---

## 4. Core autonomous agent capabilities

**Today.**
- Goals carry multi-step plans under execution profiles.
- Every tool call passes the governed runtime: capability gates, decision
  modes and approvals.
- Emergency stop and cancellation exist.
- The scheduler recovers abandoned rows at boot
  (`_recover_abandoned_operations`, DEC-24 step 3).
- Open: BUG-355 (goal intake, validator-backed criteria, restart scenario) and
  BUG-356 (profiles cover goal steps only).

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| AG-1 | Plan, execute, complete multi-step tasks | 🟡 | P0 | M | T-03 with a real model, five runs on fresh state (TESTING protocol) |
| AG-2 | Every tool call through permissions and governance | ✅ | — | — | **2026-11-07:** every tool resolves to a gate or is listed with the authority it answers to ([FIXED-1310](FIXED_ITEMS.md#fixed-1310--thirty-tools-had-no-capability-gate-and-no-reviewed-reason-ag-2)). **2026-11-08:** `test_voice_turns_cannot_change_governance`: a spoken turn uses the same route and gateway, and `input_mode` is read only for the reply style, never by approvals, the tool broker or the authority |
| AG-3 | Approve, reject, cancel, emergency stop | ✅ | — | — | Approval relay, STOP and cancel (FIXED items, live specs) |
| AG-4 | Scheduling, background, restart recovery | ✅ | — | — | **2026-11-08:** `scripts/goal_restart_fault.py` kills the host mid-step and restarts it: the step settles as failed with the reason, the goal never reads completed, nothing is filed or run twice; in CI ([FIXED-1331](FIXED_ITEMS.md#fixed-1331--a-goal-step-the-host-died-in-read-only-failed-ag-4-found-by-the-restart-drill)) |
| AG-5 | Accurate reporting, no false claims | ✅ | — | — | **2026-11-08:** a refused or failed action is closed in the answer by the runtime's own **Not done** line, whatever the model claims ([FIXED-1328](FIXED_ITEMS.md#fixed-1328--an-answer-could-claim-an-action-that-failed-ag-5)); a 7B model now serves on the owner's GPU (RT-GPU-03) for the real-model run |

**UI / UX.** The goal page shows a *receipt list* per step (done / failed /
skipped, each with evidence), and a final summary that is assembled from those
receipts rather than from model prose alone. STOP is always visible while any
work runs (top bar), and so is the count of running items.

---

## 5. Build & coding agent

**Today.**
- File tools and commands share one disposable copy per session.
- Changes are reviewed and applied by the owner.
- Commits and branches act on the project only after Apply.
- Protected files are refused.
- BR-D02 tests run on Windows CI.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| BD-1 | Repo analysis, editing, test execution | 🟡 | P0 | S | T-08 on a disposable repository with a real model, on Linux and on Windows (restricted account) |
| BD-2 | Works in disposable copies | ✅ | — | — | Per-session task tree (TO_BE_FIXED sandbox table) |
| BD-3 | Diffs, review, Apply, Discard | ✅ | — | — | Live RT-BETA-07/08 with captures ([run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-beta-release-plan-round), [FIXED-1311](FIXED_ITEMS.md#fixed-1311--a-build-apply-that-met-the-owners-own-edit-had-no-way-forward-bd-4)) |
| BD-4 | Git safety, protected files, conflicts | ✅ | — | — | Apply refuses a conflict unless the owner chooses **Overwrite** after seeing both versions; the original is backed up and the choice audited ([FIXED-1311](FIXED_ITEMS.md#fixed-1311--a-build-apply-that-met-the-owners-own-edit-had-no-way-forward-bd-4)) |
| BD-5 | Diagnose failures, iterate, report | ✅ | — | — | **2026-11-08:** passed live three times out of three with Qwen3-8B Q4_K_M served by Raiker on the owner's RTX GPU (`scripts/live_build_fix_loop.py`): the agent read the repository, fixed the bug, its edit was approved, and the declared check `python -m unittest discover -q` ran after the change and passed, so the outcome was `completed_verified` with one check run. The runs found and fixed FIXED-1334 to FIXED-1336 and FIXED-1338 to FIXED-1341 |

**UI / UX.**
- The Changes pane groups files by *new / modified / deleted*, with a per-file
  Apply and Discard as well as *Apply all*.
- A conflict shows a three-way view (original at copy time, original now, the
  copy) with **Keep mine**, **Keep theirs** and **Open both**.
- ✅ The Build header always says *"Working in an isolated copy — nothing changes
  in your project until you Apply."* (on the sandbox review, FIXED-1311).

---

## 6. Memory & data protection

**Today.**
- SQLCipher (`sqlcipher3` 0.6.4, SQLCipher 4.19.0) is the store, and the vault
  key is provisioned at first write.
- Backups (create, verify, restore to a copy), schema-generation guards and the
  deletion journal exist.
- The support bundle refuses to build if anything secret-shaped survives
  redaction.
- ~~BUG-354: the workspace key cannot be rotated in place~~ — closed 2026-11-15 (FIXED-1452, FIXED-1453).

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| MM-1 | Encrypted storage and configuration | ✅ | — | — | `tests/test_sqlcipher_memory_security.py`, `tests/test_memory_sqlcipher.py` (CI) |
| MM-2 | Persist, retrieve, correct, delete | ✅ | — | — | T-04 scenario; memory governance tests |
| MM-3 | No credential or private-data leaks to models or logs | ✅ | — | — | `Data safety drills` now provides required automated transport/key/recovery regressions. **2026-11-08:** the canary drill runs in Data safety drills; it found the memory mirror holding secrets in plain text ([FIXED-1330](FIXED_ITEMS.md#fixed-1330--a-memorys-readable-mirror-held-passwords-and-card-numbers-in-plain-text-mm-3-found-by-the-drill)). See [data-safety evidence](#appendix-c--data-safety-evidence). |
| MM-4 | Backup, migration, corruption recovery | ✅ | — | — | Automated backup and lock-screen recovery checks are required in `Data safety drills`. **2026-11-08:** the destructive drill (truncate, flipped pages, missing key, full disk) runs in Data safety drills; it found a full disk answering a bare 500 ([FIXED-1329](FIXED_ITEMS.md#fixed-1329--a-full-disk-reached-the-owner-as-a-bare-500-mm-4-found-by-the-drill)) |
| MM-5 | No unexpected cloud transmission | 🟡 | P0 | M | `scripts/verify_egress_audit.py` rejects a capture shorter than 30 minutes or with an unapproved host. Still required: owner-machine local-profile recording while all features are used, then attach its redacted verifier report and capture hash. |
| MM-6 | Key rotation (BUG-354) | ✅ | — | — | Closed 2026-11-15: verified backup, `PRAGMA rekey`, re-sealed secrets, retired keys for older backups ([FIXED-1452](FIXED_ITEMS.md#fixed-1452--the-workspace-key-could-not-be-rotated-in-place-bug-354), [FIXED-1453](FIXED_ITEMS.md#fixed-1453--settings-could-not-rotate-the-workspace-key-or-say-which-backups-need-the-old-one-bug-354)); RT-1115-02 live |

**UI / UX.**
- Settings → **Privacy** gains a *"What leaves this computer"* panel, listing
  each configured destination and what may be sent there (model prompts,
  connector calls, update checks). ✅ FIXED-1315, RT-BETA-02.
- ✅ Backup reminders appear in the top bar when no verified backup is newer than
  14 days. Evidence: `web/src/lib/components/Topbar.svelte` shows a *Make a
  backup* link to Settings → General from every page (reachable at every width;
  the label collapses to the warning icon below 1100px); it re-reads every ten
  minutes and at once when a backup is made, verified or removed, and a failed
  read shows nothing. The rule is shared with Home's seven-day note
  (`web/src/lib/backupReminder.ts`, `TOP_BAR_BACKUP_STALE_DAYS`); tests in
  `Topbar.test.ts` and `backupReminder.test.ts`.

---

## 7. UI & user experience

**Today.**
- The Quiet UI redesign is largely shipped (QUIET_UI_PLAN.md; FIXED-1150 and
  later). Open items are listed in TO_BE_FIXED (*Quiet UI round 2*,
  *approvals round*, *polish round*).
- Size budgets are measured (QUI-G01) but are still a report, not a gate.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| UX-1 | Quiet UI across retained pages | ✅ | — | — | **2026-11-07:** QUI-G01 is a failing check (RT-BETA-10) for Chat, Build, Models, Settings › General, Privacy and About & updates, and Account and Backups. General's exception is gone: Account and Backups are sections of their own ([FIXED-1318](FIXED_ITEMS.md#fixed-1318--settings--general-was-over-its-size-budget-because-it-held-the-account-and-backups-ux-1)). **2026-11-08:** three open rows fixed (docked notices fold into the bell on every page, the approval's account reads as text, the routine delivery note links Permissions); the rest moved to beta.2 with known-issue entries in the beta guide |
| UX-2 | Composer, navigation, model selection consistent | ✅ | — | — | Existing component coverage names the Chat and Build grammars; this round adds the shared five-state vocabulary and a live `RT-BETA-UX-01` route check. **2026-11-08:** the parity assertion found Build's order differing from Chat's; fixed, and checked in mocked e2e ([FIXED-1326](FIXED_ITEMS.md#fixed-1326--build-and-chat-ordered-the-shared-composer-controls-differently-ux-2)). |
| UX-3 | Permission controls, runtime status, approvals | ✅ | — | — | QUI-P01–P09 (approvals round) |
| UX-4 | Understandable errors and recovery actions | ✅ | — | — | Whole-route audit `tests/test_route_reason_copy.py`: every literal route refusal has copy, and `failure()` says why ([FIXED-1309](FIXED_ITEMS.md#fixed-1309--eighty-route-refusals-reached-the-owner-as-a-bare-machine-code-ux-4)) |
| UX-5 | Responsive layouts, accessibility, desktop usability | 🟡 | P0 | M | **2026-11-07:** RT-BETA-09 finds no serious or critical axe violation on any destination at 1440, 1280 and 390 ([FIXED-1317](FIXED_ITEMS.md#fixed-1317--settings-sections-were-off-the-card-system-and-the-activity-table-could-not-be-scrolled-by-keyboard-found-this-round-ux-5)). **2026-11-08:** keyboard-only T-14 passes live (`keyboard-only-live.spec.ts`, 5/5: start, stop, find with Ctrl+K, back up, reach Approvals; every stop named with visible focus), finding FIXED-1333. Still required: NVDA and VoiceOver passes by a person |

**2026-11-06 shared UI refinement.** The owner's settings cog, simpler Models
and shared Apple/macOS design pass are implemented. The running-host review
checked 54 default/nested addresses in light 1440×900 and dark 1280×800, plus
a short-window form/focus check; see the
[recorded results](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-shared-ui-refinement).
These layout observations do not close UX-1/UX-5's size, axe, screen-reader,
platform or usability gates.

**UI / UX deliverables for beta.**
1. **Beta badge** in the top bar, linking to *Send feedback* (area 12).
2. **Unavailable is visible, not hidden.** A control that the host cannot run
   (commands, voice, image generation) stays visible but disabled. It carries a
   one-line reason and a *Set up* link where something can be done. Controls
   for features that are **Not in beta** are removed.
3. **One status vocabulary** across Models, Tasks and Settings: *Ready*,
   *Working*, *Needs you*, *Unavailable*, *Failed*. Each has one colour token
   and an icon, never colour alone.

**2026-11-06 UX implementation slice.** The top bar now contains a keyboard-
reachable **Beta** link to Settings → General → Beta feedback. `betaStatus.ts`
is the single mapping for task/turn, model-readiness and runtime states; Models,
Tasks, Sessions and Settings → Runtime show the shared status first and retain
the measured detail after it. Unit/UI evidence is `betaStatus.test.ts`,
`Topbar.test.ts`, `TasksView.test.ts`, `ModelsView.test.ts` and
`SessionsView.test.ts` (147 focused tests). `RT-BETA-UX-01` captures the
badge and Runtime state on a fresh host. It remains a required live check on
the release candidate; it was not recorded in this development environment
because the Playwright browser download was unavailable.

---

## 8. Voice & design

**Today.**
- Dictation posts audio to an owner-configured local transcription server.
  Browser speech recognition is never used.
- Read-aloud uses the operating system's speech engine, limited to voices that
  report `localService` (`voice.ts`).
- There is no managed speech engine (TO_BE_FIXED, *Local voice delivery —
  release blockers*).
- Design: structured documents, exports and the Build handoff pass
  (T-11/T-12, 2026-10-19). BUG-287 (live image provider round trip) and
  BUG-348 (canvas editing, five DW items partial) are open.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| VD-1 | On-device dictation and read-aloud setup | 🟡 | P0 | L | **Implemented** (voice spec V1): verified catalogue (`raiker/config/voice-catalogue.json`), profiles with a hardware recommendation, shared `ResourceLedger` and placement planner, digest-verified installer run as a model operation, contained whisper-server and a token-protected Kokoro speaking worker, idle and low-memory unload, Settings › Voice, the *Voice* first-run step, dictation and read-aloud on the managed engines. Kokoro speaking was installed, verified and run for real here (`tests/test_voice_live.py`). **2026-11-09:** all five Whisper models are pinned to immutable revisions, LFS SHA-256 and exact sizes ([FIXED-1373](FIXED_ITEMS.md#fixed-1373--whisper-models-still-had-no-immutable-download-pins)). **Owner scope, 2026-11-09:** Piper and its sidecar/licence work are removed (FIXED-1378). Personal frozen Kokoro workers have real Linux and Windows workflow evidence with retained GPL runtime notices and pinned sources; this does not approve public redistribution. Still required for the PC candidate: full managed speech/microphone round trip and §14 acceptance. Linux Whisper packaging and macOS owner-hardware qualification retain their separate scope in PERSONAL_BETA_SCOPE.md |
| VD-2 | Mic permissions, cancellation, audio privacy, no browser speech | ✅ | — | — | **2026-11-07:** the unused browser adapter is removed and a test fails if any source reads `SpeechRecognition` ([FIXED-1314](FIXED_ITEMS.md#fixed-1314--the-page-still-carried-a-browser-speech-recognition-adapter-vd-2)); read-aloud refuses non-local voices (done). **2026-11-08:** fake-microphone live run 6/6 (denied, cancel, device lost, the page's own 6-minute stop, no `SpeechRecognition`) found and fixed four defects ([FIXED-1327](FIXED_ITEMS.md#fixed-1327--the-microphone-could-fail-in-four-ways-the-owner-was-told-about-wrongly-or-not-at-all-vd-2)) |
| VD-3 | Design composer, templates, attachments, image generation | 🟡 | P1 | M | Image generation is labelled **Preview** (2026-11-07, FIXED-1315). Still required: ship the document editor; drop the label once BUG-287 has a real-provider round trip |
| VD-4 | Disable unfinished capabilities clearly | ✅ | — | — | Hands-free conversation is **Preview** behind Settings › Voice (*Hands-free conversation*), and the conversation panel carries a *Preview* label; voice components that cannot be offered yet are shown with their reason, not hidden. BUG-348's unfinished rows are absent from the menus, and a guard test keeps them out (2026-11-07, FIXED-1315) |
| VD-5 | Native voice conversation | 🟡 | P1 | L | **V2 Preview implemented**: conversation panel in Chat (*Talk*), push to talk, hands-free with Silero VAD v5 (onnxruntime-web, bundled; real-model test), streaming sentence-by-sentence speech, barge-in that stops audio and cancels the turn, approvals asked for on screen only, `input_mode: spoken` with a spoken-style hint. Still required: the §14 V2 acceptance on the reference laptop (P50 first audio < 1.5 s, barge-in < 200 ms), a Playwright fake-microphone end-to-end run; V3 after beta |

**UI / UX.** See [VOICE_CONVERSATION_SPEC.md §8](VOICE_CONVERSATION_SPEC.md#8-ui-and-ux).
The composer microphone has three states (*Set up voice*, *Dictate*,
*Recording 0:12 — Stop / Cancel*). Read-aloud shows which engine will speak
(*Kokoro · on this device*).

---

## 9. Plugins, integrations & permissions

**Today.**
- Plugins and local MCP run sandboxed with no network, and are refused on
  hosts without an enforced boundary.
- Connector accounts and OAuth exist; permission grants, revocation and audit
  records exist (governance tests).
- The agent tool inventory lists many items as needing their own threat model
  or connector.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| PL-1 | Install, configure, remove supported integrations | 🟡 | P0 | M | A **supported list** for beta: GitHub, email (IMAP/SMTP), calendar (CalDAV), web search, local MCP stdio. Each gets one live install → use → revoke → remove run. **2026-11-08:** Gmail, Google Calendar and Outlook connect by browser sign-in; Outlook is a new governed read connector ([FIXED-1347](FIXED_ITEMS.md#fixed-1347--there-was-no-way-to-read-outlook-mail-or-calendar)); GitHub's own App is one click from Advanced |
| PL-2 | Grants, revocation, audit | ✅ | — | — | Governance suite |
| PL-3 | OAuth and credential storage | 🟡 | P0 | S | Vault encryption and expiry checks are tested; a provider 401 marks the local credential `reauth_required` so it is not retried. Still required: expired-token and owner-revoked-token live checks for GitHub on the release candidate. Provider-specific OAuth revoke endpoints are not claimed until Raiker has registered clients. **2026-11-08:** Gmail, Google Calendar and Outlook sign in in the owner's browser with PKCE, a single-use state, a loopback-only redirect and vault-kept tokens that renew themselves ([FIXED-1346](FIXED_ITEMS.md#fixed-1346--gmail-calendar-and-outlook-now-sign-in-in-the-owners-browser)). Still required: one live sign-in per provider with the owner's registered clients |
| PL-4 | Plugins and MCP cannot bypass the sandbox | ✅ | — | — | **2026-11-08:** `tests/test_mcp_adversarial_server.py` starts a hostile local MCP server the way Raiker does; its loopback (fixed port) and internet connections, home and project reads, write outside its folder and a child process's write all fail on this Windows 11 host's enforced boundary, and a host without one refuses to start it. The Windows dynamic-port loopback range stays the documented limit (TO_BE_FIXED, *Network mediation*) |
| PL-5 | Supported vs experimental | 🟡 | P0 | S | Every connector has a `support_level` and is **Experimental** by default; the Add list shows the label and an experimental install asks once more (2026-11-07, FIXED-1315, RT-BETA-04). MCP servers carry their source instead, *Raiker sample*, *From a plugin* or *Added by you* with *Raiker has not reviewed this server* (2026-11-08, FIXED-1359, RT-MCP-PL5-01). Still required: live evidence to promote the supported beta list |

**UI / UX.** The Extensions page has two sections, *Supported* and
*Experimental*. An experimental card has an amber badge and the install dialog
says what has not been verified. Each connection's detail shows its grants and
the last ten audit records with **Revoke**.

---

## 10. End-to-end testing

**Today.** TESTING.md defines T-01–T-16 (sixteen real-user journeys) and the
run-record protocol. Live specs exist for many rounds, and T-11/T-12 passed
with a real model. No single release-candidate run covers seven journeys from
a fresh install.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| E2E-1 | Seven journeys from fresh install to completion | 🔴 | P0 | L | The beta set: **T-01** first use, **T-03** durable outcome with restart, **T-04** memory correct/forget, **T-08** issue-to-PR, **T-13** stop/resume/budget, **T-14** accessibility, **T-15** security and resilience; plus **V-01** voice dictation once VD-1 lands |
| E2E-2 | Real models, not only mocks | 🟡 | P0 | M | **Hosted path run 2026-11-02** (see [run record](#run-record--2026-11-02-real-hosted-model)): eight real-model specs, 53/53 tests green. Remaining: the same journeys on a local llama.cpp model, and on fresh installers rather than a source host |
| E2E-3 | Offline, lost connectivity, crashes, restarts, pressure | 🔴 | P0 | M | A fault harness: drop the network mid-turn; kill the host; fill the disk to 98%; cap RAM with a cgroup or Job Object. Assert honest states and no data loss |
| E2E-4 | Adversarial sandbox, filesystem, credential tests | 🟡 | P0 | M | SB-6 plus MM-3 |
| E2E-5 | Playwright screenshots and execution evidence | 🟡 | P0 | S | Every journey stores screenshots, a HAR, the event log and receipts under the run record |

---

## 11. CI/CD & release quality

**Today.**
- `ci.yml` runs ruff, mypy, three pytest shards, SAST, secret scan,
  dependency audit, the web pipeline, Windows lifecycle, Build fault and
  remote-access jobs.
- `desktop-package.yml` builds every target; `release.yml` drafts releases.
- `llama-cpp.yml` (PR #245) adds a three-OS engine job and a weekly live job.
- PR #246 (`aff48e7`) repaired the llama.cpp release selection, and the three
  llama.cpp **live** jobs passed on Windows, macOS and Linux. The full required
  release suite must still be green again on the exact release commit.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| CI-1 | All mandatory workflows green on the release commit | 🟡 | P0 | M | The three llama.cpp live jobs are green after PR #246, and the release gate requires the complete beta-critical CI, llama.cpp, native-runner and data-safety suites using the latest GitHub Actions result for the exact commit. Remaining: a green candidate-release run with its signed artifacts and attached evidence. |
| CI-2 | Ruff, mypy, lint, unit, integration, security, packaging | 🟡 | P0 | S | Already wired; part of CI-1 |
| CI-3 | Per-platform artifacts verified independently | ✅ | — | — | **2026-11-08:** each signed build is verified against the pinned identities before install and on the installed program, in the release run ([42430871211](https://github.com/sharRahul/Raiker/actions/runs/42430871211)); the downloaded artifacts re-verify on the owner's machine (Windows Authenticode, Linux GPG under WSL, channel and provenance with the release key) |
| CI-4 | Dependency vulnerability and secret scans | ✅ | — | — | `pip-audit`/`npm audit` and `scan_secrets.py` in CI |
| CI-5 | Versioned, verified artifacts with reproducible evidence | ✅ | — | — | **2026-11-08:** the release run writes `RELEASE_EVIDENCE.md` from its own outputs (`scripts/release_evidence.py`): commit, run, signing, each installer's SHA-256 and manifest signature, the signed channel, SBOM and provenance; a missing output fails the run, and the file is attached to the draft |

---

## 12. Documentation & beta operations

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| DOC-1 | Reconcile TO_BE_FIXED, FIXED_ITEMS and architecture docs | 🟡 | P0 | M | Reconciled 2026-11-02: FIXED-1283 closes the llama.cpp release-selection defect; TO_BE_FIXED and the native-sandbox architecture retain only release evidence and platform-signing gaps. Repeat this pass on the final release commit; every ✅ row must name its FIXED item. |
| DOC-2 | Supported OS, hardware, known limitations | ✅ | — | — | [Beta guide](../guide/beta.md) (this round) with README's requirements and [KNOWN_LIMITS](../architecture/KNOWN_LIMITS.md) |
| DOC-3 | Install, setup, troubleshooting, uninstall guides | ✅ | — | — | getting-started, troubleshooting, managing-the-host (Uninstall); engine-specific rows added in PR #245 |
| DOC-4 | In-app bug reporting and feedback route | ✅ | — | — | Settings → General → **Beta feedback** and GitHub issue forms (this round) |
| DOC-5 | Beta criteria, known issues, rollback or withdrawal | ✅ | — | — | [Beta release criteria](#beta-release-criteria) below and the beta guide's *Known issues* and *If a beta is withdrawn* |

---

### Run record — 2026-11-02, real hosted model

- **Host and model:** a fresh `raiker-web` built from PR #245 (`c494e65`), a
  new encrypted workspace per spec (`scripts/reset_live_workspace.py`), Linux
  x86-64.
- **Credential:** Anthropic connected through **Add model** with an
  identity-linked key and its Workspace ID, typed from the run's environment
  only. A scan after the run found neither in any file, log or commit; the key
  file and workspaces were deleted.
- **Model:** `claude-haiku-4-5-20251001` (the specs' default).

| Spec | Area | Result |
|---|---|---|
| `model-connection-anthropic-live` LC-01, LC-02 | 3 (connect, readiness, real turn) | ✅ 2/2 |
| `quiet-ui-home-chat-live` | 4, 7 | ✅ 9/9 |
| `goals-execution-profiles-live` | 4 (multi-step goals) | ✅ 7/7 |
| `mem-brief-recall-mode-live` | 6 | ✅ 6/6 |
| `quiet-ui-permissions-live` | 4, 7, 9 (approvals) | ✅ 9/9 |
| `br-d02-d04-build-target-and-review-live` | 5 | ✅ 4/4 (after a spec fix) |
| `dw-design-documents-live` | 8 | ✅ 6/6 (after a spec fix) |
| `tool-inventory-live` | 4 (agent tools) | ✅ 10/10 (with the documented `src/` fixture) |

Spec drift found and fixed in the same PR:
- the Connect dialog now opens over **Add model**;
- the Permissions page's category rail replaced the search field;
- the proposal state reads *Accepted*, capitalised.

None was a product failure. Still open: the older `model-connection-anthropic-live`
LC-03/LC-04 and about twenty pre-Quiet-UI live specs drive the retired
Permissions search field. They need rewriting against the category rail
(TO_BE_FIXED, *Live specs that predate the Permissions redesign*).

This covers E2E-2 for the hosted path. The local llama.cpp path is still due
from the `llama-cpp.yml` live job.

## Beta release criteria

The personal `beta.1` candidate is accepted only when **every applicable** item
below is true on one commit under [the owner's scope](#appendix-a--owner-scope-2026-11-09),
and the release owner signs off in `RELEASE_EVIDENCE.md`.

1. **CI.** Every required workflow is green on the exact commit: `ci.yml`,
   `web` jobs, `desktop-package.yml`, `llama-cpp.yml` (engine and live),
   SAST, secrets and dependency audit.
2. **Sandbox.** On each qualified host, either the native sandbox probe reports
   every mandatory observation enforced and SB-6 passes, or command execution
   is refused on that platform and the beta guide says so.
3. **Installers.** The applicable IN-1 to IN-5 checks pass for the PC candidate.
   Verified hashes and truthful unsigned-build guidance are required; commercial
   signing identities and public distribution are outside this personal scope.
4. **Journeys.** The seven E2E-1 journeys pass with real models, with evidence
   stored.
5. **Data.** MM-3 (canary) and MM-4 (corruption drill) pass; MM-5 egress
   audit recorded.
6. **No P0 open.** Every P0 row above is ✅, or is moved to *Not in beta* with
   the product refusing it and the beta guide listing it.
7. **Known issues** in the beta guide are current as of the commit.

### Withdrawal and rollback

- **Severity 1** (data loss, a sandbox escape, a credential leak, or remote
  code execution): the release owner unpublishes the GitHub release within an
  hour of confirmation. They then mark the update channel's manifest as
  withdrawn so installed copies stop offering it, and post an advisory on the
  release page and in SECURITY.md. Installed copies show a banner on next start
  with the advisory and **Roll back** (IN-4).
- **Severity 2** (a broken core journey): a fixed `beta.N+1` within seven
  days, or withdrawal if it is not possible.
- Rollback keeps data: the store refuses only a *newer* schema, so a beta
  that added no migration can be rolled back in place. A beta that added one
  says so in its notes. Rolling back past it restores the pre-update backup
  that the updater takes before any migration (IN-4 adds this backup).

## Delivery order

1. **Week 1 — gates that cost little.** Merge PR #245 (with this round's beta
   guide, feedback route, issue forms and spawn inventory test). Add
   `support_level` (PL-5) and the reason-code label audit (UX-4).
   Fix the CI failures (CI-1).
2. **Week 2 — voice V1 and data drills.** Managed whisper.cpp and Kokoro
   (VD-1). MM-3 canary, MM-4 corruption drill, MM-5 egress audit. Apply
   conflict refusal (BD-4).
3. **Week 3 — platforms.** macOS sandbox CI (SB-2), Windows gaps (SB-1),
   signing (IN-3), clean-machine runs (IN-5).
4. **Week 4 — the candidate.** The seven journeys with real models (E2E-1/2),
   the fault harness (E2E-3), reconciliation (DOC-1), sign-off.

Anything not green at the start of week 4 is moved to *Not in beta* with the
product refusing it, rather than delaying the date.

## Changelog

- **2026-11-08** — Connectors: browser sign-in for Gmail, Google Calendar and Outlook (FIXED-1346), a governed Outlook read connector (FIXED-1347), and a one-click GitHub App registration link.
- **2026-11-08** — MD-1: Anthropic, OpenAI, OpenRouter, Ollama and LM Studio each completed a live tool-using Chat turn with the owner's keys, entered through the UI. GPT-5 was unusable before FIXED-1343; output limits were measured and set (FIXED-1344).
- **2026-11-08** — Owner moved signing (a real certificate and an Apple Developer ID), fresh-VM installs, macOS hardware and the AMD GPU run to beta.2: IN-3, IN-5 and SB-2 are now ⏭, and so is the AMD half of MD-2.
- **2026-11-08** — BD-5 closed: Qwen3-8B on the owner's GPU fixed a failing test with the check verified, three runs out of three. The runs found eight defects, all fixed (FIXED-1334 to FIXED-1342).
- **2026-11-08** — BD-5 live runs on the owner's GPU found four defects, all fixed (FIXED-1334 to FIXED-1337).
- **2026-11-08** — SB-3, SB-4, CI-3 and CI-5 closed: WSL2 re-measured, every hook event refuses without a boundary, release evidence written by the run.
- **2026-11-08** — UX-1 closed: three Quiet UI rows fixed, the rest moved to beta.2 as known issues.
- **2026-11-08** — UX-5 keyboard-only T-14 passes live; it found a readiness promise the server did not keep (FIXED-1333).
- **2026-11-08** — PL-4 closed by an adversarial MCP server test.
- **2026-11-08** — SB-5: Undo Apply and crash-safe Apply (FIXED-1332).
- **2026-11-08** — AG-4 closed by a host-restart drill in CI (FIXED-1331).
- **2026-11-08** — AG-5, MM-3 and MM-4 closed (FIXED-1328 to FIXED-1330); a 7B GGUF in two shards downloads, verifies and serves on the owner's GPU (RT-GPU-03).
- **2026-11-08** — VD-2 closed by a fake-microphone live run (FIXED-1327).
- **2026-11-08** — Toward the beta: MD-5, AG-2 and UX-2 closed (FIXED-1323,
  FIXED-1326 and the voice governance invariant). Also fixed: a local GGUF's
  location line (FIXED-1322), the stale Build review (FIXED-1324), llama.cpp
  auto-install racing an upstream upload (FIXED-1325), and the Windows mypy
  `os.getuid` gap.

- **2026-11-07 (second round)** — Owner decisions: Account and Backups become
  Settings sections; this machine (RTX 4080 SUPER) is the GPU test machine;
  sign Windows and Linux now, macOS later. UX-1's last exception closed
  (FIXED-1318); MD-3 closed and MD-2's NVIDIA run passed, finding a High defect
  in auto context sizing (FIXED-1319); IN-3 moved to 🟡 with per-OS signing and
  pinned verification (FIXED-1320, FIXED-1321). LM Studio could not be checked
  (broken install). [Run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-gpu-signing-and-settings-round).

- **2026-11-07** — Beta round: fifteen items (AG-2, UX-1, UX-4, UX-5, BD-3,
  BD-4, MD-1, MD-3, MD-5, PL-5, VD-2, VD-3, VD-4 and the §1, §2 and §6 UI
  deliverables), FIXED-1309 to FIXED-1317. Four defects were found and fixed on
  the way: a cut-off stream recorded as finished, a cloud model called local, an
  off-system Settings card, and an unfocusable table. Live evidence: the
  [run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-beta-release-plan-round), 10/10 plus three hosted providers and Ollama.

- **2026-11-06** — Recorded the owner-requested cog/Models simplification,
  shared cross-page refinement and three real hosted-provider UI checks.
  Release-commit, local-provider, native-platform and usability gates remain open.

- **2026-11-02** — Plan opened. Delivered in the same round:
  - DOC-2, DOC-3 and DOC-5: the [beta guide](../guide/beta.md), with
    supported systems, scope, known issues, updating, withdrawal and uninstall,
    plus these criteria.
  - DOC-4: Settings → General → **Beta feedback** (prefilled GitHub issue forms,
    optional redacted diagnostics) and `.github/ISSUE_TEMPLATE/`.
  - SB-4: the process-spawn inventory test.

  MD-2's source-only release-selection defect is closed in FIXED-1283 (PR
  #246); its Windows, macOS and Linux live jobs passed. GPU-owner and
  signed-installer evidence remain open. PR #247 adds the required data-safety
  drill gate and its formal owner-machine evidence procedure.

## 2026-11-09 — Linux owner-machine readiness run

Target: Ubuntu 24.04 x86-64 in Codespaces. This is a Linux test candidate,
not a published beta or clean-desktop installation. Decisions for this run:

1. Keep beta scope and release sign-off criteria unchanged; never bypass a
   failed sandbox or packaging check to obtain a pass.
2. Validate the release inventory before producing candidate evidence
   ([FIXED-1368](FIXED_ITEMS.md#fixed-1368--release-evidence-could-approve-a-directory-with-no-installer)).
3. Run privacy canary, destructive recovery and egress-verifier regressions.
4. Kill/restart a live goal and confirm honest completion and no duplicate work.
5. Build and probe the native runner on this host.
6. Build an unsigned `0.0.0` Linux desktop test package with normal smoke checks.
   The workspace's Python 3.14 lacks a shared library, so use an isolated system
   Python 3.12 virtual environment for packaging, not a weakened freeze check.
7. Keep the required 30-minute metadata-only egress recording, real-model
   journeys and exact-commit installer acceptance open until actually recorded.

Local artifacts live under `output/linux-beta/`: `data-safety.xml`,
`goal-restart.json` and `native-probe.json`. The focused safety run passed seven
tests. The live restart reports `interrupted_by_restart`, one model call before
and after restart, and the same task id. The native probe reports Bubblewrap
available with descendant reaping, egress, escape-write denial, masked reads,
relay and seccomp enforced; runner trust is `package_relative_integrity`.
These source-tree measurements do not replace frozen/installed-host evidence.

**Installed result.** The frozen and installed host smoke checks passed; the
unpacked and installed desktop suites each passed 2/2 under Xvfb. The `.deb`
is installed at `/opt/Raiker` and the new-profile Home screenshot was inspected.
AppImage and `.deb` artifacts with hashes are in `output/linux-beta/packages/`.
The all-format wrapper stopped at RPM; that format is not accepted on this run.
The owner selected `sharRahul/raiker-test-sandbox` for RR-40, but this integration
cannot create repositories (HTTP 403); that journey waits for repository access.

## 2026-11-09 — Linux hardening and qualification follow-through

[The nine-workstream run record](#appendix-b--linux-qualification-record-2026-11-09) separates source,
installed-host, controlled-provider and real-model evidence. Linux Apply
parent races and rollback under persistent ENOSPC are fixed (FIXED-1370/1371);
a fresh-profile threat-feed egress defect is fixed (FIXED-1372); Whisper pins
are resolved (FIXED-1373); RPM compression has a tested memory bound
(FIXED-1374). Actual bounded storage exhaustion, goal kill/restart, fifteen
native Linux adversarial/resource tests and real llama.cpp CPU inference
passed. Full Voice V1, seven real-model journeys, live OAuth revocation,
30-minute exact-candidate all-feature egress, signed candidate qualification
and owner sign-off retain their gates. No beta scope decision was changed.

The egress follow-through also found an unrequested ChatGPT status sidecar
(FIXED-1375): unconnected status reads are now passive, with explicit owner
actions for sign-in and adoption. The failed egress receipts remain attached;
MM-5 is still partial pending a fresh exact-candidate recording.

CI, engine/live inference and data safety are green on runtime `8a053a90`.
The exact Release Plan verification script passed locally, but GitHub rejected
the signed non-published candidate dispatch with 403 (Actions access). CI-1
and CI-5 retain the signed candidate/evidence requirement;
[the run record](#github-qualification-and-release-dispatch-access)
contains the workflow links, access blocker and concrete manual command.

The full installed-shell capture also found Electron startup resolver traffic
that the host-only trace missed. FIXED-1376 disables automatic DoH and
non-loopback shell resource requests; 36 unit and 13 UI tests pass. Chromium's
non-sending IPv6 UDP route probe remains explicitly recorded. A fresh candidate
with this shell correction needs its own CI, package and egress evidence.
[Follow-through](#electron-network-process-follow-through).

## 2026-11-09 — Completed bounded installed-shell audit

The `6c211b60` installed unsigned Linux shell/host audit passes its predeclared
fresh-profile scope: 1,862 seconds of actual destination activity, 4,115
observations, no unexpected hosts. The 30-minute navigation driver completed
62 visits without failure; screenshot states were inspected. Chromium's 135
non-sending IPv6 UDP route probes and native control probes remain explicit
in the scope and receipts. Earlier failed captures remain failed.

**MM-5 remains partial:** no selected useful model, managed speech, enabled
external connector, owner-machine full-feature sign-off or signed-artifact
capture is inferred. All four qualification workflows for runtime `6c211b60`
are green; downloaded CI Linux artifact hashes and RPM digests verify.
[Evidence and limits](#completed-installed-shell-audit-and-ci-artifact-verification).

## 2026-11-09 — Signed candidate output verified

[Release 42650624663](https://github.com/sharRahul/Raiker/actions/runs/42650624663)
passed for exact runtime `6c211b60`, version `0.9.0`, beta channel,
`require-except-macos`, publication disabled. Independent checks passed for
all 10 installer hashes/Ed25519 manifests, six Linux GPG signatures, signed
channel/provenance, SBOM binding, repository lock hash and checksum files.
The product verifier and generated evidence inventory pass. The owner's
manual dispatch supplied the needed access; this candidate is no longer
blocked on candidate creation. Windows native checks passed in the workflow;
macOS retains its platform-signing exception.

This establishes CI-1/CI-5 candidate-output evidence, not beta sign-off.
Full Voice/licence/packaged-speech, seven real-model journeys, live connector
revocation/reconnect, full-feature signed-artifact egress and owner-machine
acceptance remain open. The reporting fix preserves that candidate's SHA; the subsequent owner-requested
Kokoro/Piper runtime change requires a new personal candidate.
[Artifact, signatures and receipts](#verified-non-published-signed-candidate).

## 2026-11-09 — Windows owner-PC follow-through

The owner asked to continue beyond the twenty recovery scenarios. The plan now
uses the owner scope (Appendix A) consistently: personal PC qualification first,
Kokoro only, no commercial signing prerequisite. Unresolved safeguards and
real-model journey gates remain; this is not release-owner sign-off.

- **UX-4/UX-5:** twenty recovery scenarios pass across the diagnostic round and
  focused rerun. Keyboard-only T-14 passes 5/5 with real hosted Haiku 4.5,
  including a stopped turn and a verified backup. RT-BETA-09/10 pass the axe
  destination sweep (1440/1280/390) and existing page-size budgets. NVDA human
  qualification is still separate. FIXED-1379–1383 record the discovered fixes.
- **AG-4/E2E-3:** the real Windows host kill/restart drill passes with a scripted
  delayed model: one model call before/after, identical task identity, failed
  step reason `interrupted_by_restart`, no false completion or duplicate work.
  This is a process-crash check, not a real-model T-03 completion claim.
  `Redacted receipt`.
- **MM-3/MM-4/SB-4:** 13 canary, destructive recovery, egress-verifier and spawn
  inventory tests pass. Forty provider-fault, truthful-reporting, persistence
  and disposable-workspace tests pass. These do not close a full-feature
  30-minute owner-PC traffic audit.
- **IN/VD-1:** downloaded personal Windows artifact from run `42670993951`,
  exact package commit `5860a1f6`, verified both NSIS/MSI SHA-256 values, and
  administratively extracted the MSI (exit 0). On this PC its frozen host passes
  encrypted store/FTS5/setup/restart smoke; the real Kokoro worker passes
  token refusal, nonzero 24 kHz WAV and shutdown; packaged-window/onboarding
  Playwright passes 2/2 with screenshots inspected. This is extracted-package
  evidence, not owner-machine install/uninstall evidence or a candidate built
  from the later recovery fixes.
  `Host receipt`,
  `worker result`.
- **CI-2:** full Windows mypy passes 1,285 files; Ruff and documentation contracts
  pass. Linux filesystem attack tests remain skipped on Windows. Exact-commit
  candidate packaging and required GitHub checks remain required.

See the [Live Test run](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-09-windows-beta-recovery-twenty-case-round).

### Windows provider and speech follow-through

All five owner-reachable provider Chat paths now have Windows UI evidence:
Anthropic, OpenAI, OpenRouter, Ollama and LM Studio. The latter four pass in
one four-case run, including idle work-count read-back. Tool-use and
exact-final-candidate qualification remain MD-1/E2E work.

The real Windows Kokoro → Whisper engine round trip passes with a verified CPU
engine and pinned English base model, with zero word errors for its known
sentence. It found and fixed the missing approved CDN and post-contact
redirect checks (FIXED-1384). The personal Windows voice workflow now includes
this opt-in round trip. Six Chromium fake-device cases pass separately; full
managed Voice UI/microphone acceptance is not inferred from either layer.
The real streamed-stop retention case passes and removes that specific live
check from TO_BE_FIXED. Current runs are detailed in
[Live Test](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-09-pc-providers-speech-engines-and-streamed-stop).

Still needed for personal sign-off: the remaining durable personal outcome,
full memory journey, issue-to-PR and stop/resume/budget journeys with approved
fixtures; actual PC install/update/uninstall; safe platform-specific promotion
and sandbox hardening or measured refusal; full managed speech/microphone;
a scoped 30-minute full-feature PC traffic capture; applicable connector
lifecycle and human screen-reader evidence. The connected test instance has no
approved mail/calendar/GitHub OAuth clients; the owner has been asked which
instance/accounts to qualify. Existing model keys do not supply those clients.

## 2026-11-10 — Continued Windows qualification

- **MM-2/T-04:** real Qwen UI import, correction and forgetting pass across
  three distinct completed conversations after FIXED-1387. The first strict
  run found forgotten facts returning through ambient historical snippets;
  both matching and recent-history fallback now exclude stale memory sources
  and answers. Explicit transcript search is retained. This slice does not
  close every T-04 mode. FIXED-1386 repairs nested Escape handling discovered
  during fresh local-model setup.
  Reusing an old diagnostic workspace exposed BUG-360: answers that already
  copied a fact indirectly have no contributing-session provenance. This is
  an open privacy blocker; the fresh-workspace pass does not close it.
- **VD-1:** exact personal frozen package `63dcdc53` installs verified managed
  engines through Settings, speaks/hears with 89% word match and removes files
  to 0 B on this PC. Its workflow passes all three real frozen voice tests.
  Actual microphone routing and owner-PC install/update/uninstall remain open.
  Follow-up: Chromium's file-backed fake microphone now passes real managed
  dictation, using the WAV from the shipped Preview control. The expected
  sentence appears in the draft, no prompt is submitted, capture tracks end,
  and removal returns to 0 B. Physical microphone/acoustic qualification remains.
- **AG-3/UX-3:** seven real Anthropic goal/profile cases pass on a fresh instance.
  These do not substitute for an approved durable calendar/mail outcome.
- **SB-1/SB-2:** ten current-source Windows disposable-account integration tests
  pass using the existing pool. Ordinary-directory native/WSL probes correctly
  refuse availability; unresolved account/profile/ACL and promotion hardening
  retain their existing gates.

[Scenario procedures, screenshots and limitations](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-10-windows-memory-correction-and-managed-voice).

### Human tester handoff and empty-state alignment

The [standalone human tester guide](../guide/human-beta-testing.md) now gives
novices a coordinator-prepared test pack, numbered steps, expected results and
a report template for first-use understanding, real NVDA speech, physical
audio, account-owner consent, display readability and personal acceptance.
It distinguishes these human observations from engineering work the agent can
test; missing connector setup is a preparation blocker, not a human-only test.
No human case is qualified by the guide's creation. Personal scope remains at
most five users, PC first, without a new mandatory multi-person study.

FIXED-1388 centers empty list/detail states across the content width, including
Approvals with a remembered divider width. Pending/History pass live geometry
checks at desktop and narrow widths. This is an automated layout correction,
not a replacement for human readability or NVDA acceptance.

## Appendix A — Owner scope (2026-11-09)

> Merged from `docs/plans/BETA_RELEASE_PLAN.md` on 2026-11-16; the original file was removed.

This records the owner's explicit clarification during Linux beta work and
supersedes broader distribution assumptions in earlier release plans.

- **Audience:** personal use, at most five users. This is the supported scale,
  not a new account-count lock silently introduced into existing workspaces.
- **Devices:** the owner's own PC first; phone and iPad app access later.
  A future mobile client can use the PC's authenticated service. Native app,
  web app and store delivery choices are not decided by this clarification.
- **Distribution:** no mass production or commercial-grade publisher/signing
  infrastructure is required. Unsigned personal test packages with verified
  hashes are acceptable. Existing beta signatures/pins can be kept for
  integrity; purchased certificates, notarization and public release/market
  delivery are not personal-beta prerequisites.
- **Speech:** remove Piper engines and voices. Every managed TTS profile uses
  Kokoro-82M: int8 for Lite/Balanced, fp32 for High quality. The OS local-voice
  fallback remains. Piper's dataset/voice licence ambiguity and JSON sidecar
  are removed work, not pending acceptance gates.
- **Keep:** authentication and user isolation, approved connector authority,
  safe Apply/rollback, backup/recovery, stop/limits, digest verification and
  truthful capability states. Small scale does not waive these safeguards.
- **Acceptance:** focus PC journeys on the owner's actual chosen model and
  enabled connections. A broad five-repeat all-model/all-platform matrix,
  three-person novice study and public distribution programme are later
  general-release evidence, not blockers to a private personal trial.
  Do not claim untested mobile access, OAuth revocation, packaged speech or
  full-feature local-only traffic as passed.

### Kokoro licence and runtime evidence

The [Kokoro-82M model card](https://huggingface.co/hexgrad/Kokoro-82M)
classifies the model as Apache-2.0. The [kokoro-onnx implementation](https://github.com/thewh1teagle/kokoro-onnx)
is MIT; its runtime depends on phonemizer/espeak-ng. Those retain their own
licences and notices. Removing Piper removes the ambiguous per-voice review;
it is not evidence that every Kokoro runtime dependency is permissive or
already bundled. No licence policy is broadened by assumption.

Real int8 synthesis using verified catalogue assets and `kokoro-onnx==0.6.1`
passed: 24 kHz nonzero PCM, 1.877-second clip, 295,440 KiB peak RSS, and no IP
destination observations during direct inference. The managed live test
correctly refused under the host's available-memory guard (less than its
2 GiB reserve free); that refusal is retained. This proves direct synthesis,
not full managed-service or frozen-package acceptance.

The earlier signed candidate and 31-minute scoped audit identify runtime
`6c211b60`. They precede Piper removal and are historical qualification
receipts. New artifacts must name the later runtime commit; do not relabel
those earlier outputs as containing this change.

### Personal packaged TTS

The opt-in `--bundle-voice` Linux freeze has passed a real worker test using
catalogue-verified assets: loopback token authentication, nonzero 24 kHz WAV,
and clean stop. This is distinct from the full-profile admission refusal above.
The build checks exact runtime versions from `requirements/voice.txt`, retains
licence metadata and [voice notices](../licensing/voice/README.md), and does
not enable a public distribution/signing requirement.

Example private build, in a Python 3.12 build environment:

```bash
python -m pip install --require-hashes -r requirements/release-build.txt
python -m pip install --require-hashes -r requirements/voice.txt
python -m pip install --no-deps -e .
python scripts/build_desktop_app.py --version 0.9.0 --channel beta \
  --target linux-x86_64 --commit "$(git rev-parse HEAD)" --bundle-voice \
  --out output/personal-beta
```

Use a clean committed source revision for candidate provenance. The ordinary
public workflow does not opt into this private runtime bundle. A later mobile
client does not need to run the speech model on the phone/iPad to use the PC's
authenticated service.

### Personal Windows qualification

`.github/workflows/personal-windows-voice.yml` qualifies the same opt-in
runtime natively on Windows without a production signing service. It builds
its own static WSL2 runner, freezes the host with `--bundle-voice`, produces
**unsigned** NSIS/MSI installers and checks their `SHA256SUMS`, installs the
per-user package silently, and then tests the installed copy:
`desktop_smoke --expect-unsigned`, the real Kokoro tests in
`tests/test_voice_live.py` against the installed host
(`RAIKER_VOICE_LIVE=1`, `RAIKER_VOICE_PACKAGED_HOST`), and the packaged
window/onboarding Playwright specs. It then uninstalls and confirms removal.

The uploaded `personal-windows-kokoro` artifact also carries the corresponding
sources from `python -m scripts.package_voice_sources`: espeak-ng 1.52.0,
espeakng-loader 0.2.4 and phonemizer 3.6.0, each pinned by URL, size and
SHA-256 in [`runtime-sources.json`](../licensing/voice/runtime-sources.json)
and refused on mismatch, plus a `git archive` of the building commit, the
GPL-3.0 and loader MIT texts, `VOICE_RUNTIME_INVENTORY.json` and an SPDX SBOM.
Every voice runtime dependency resolves to an SPDX licence there. This is
personal qualification evidence, not approval for public redistribution.

The 13 exact optional runtime dependency versions were also queried against
OSV on 2026-11-09: no advisory IDs were returned. This is a dated dependency
check, not a permanent safety assertion.

## Appendix B — Linux qualification record (2026-11-09)

> Merged from `docs/plans/BETA_RELEASE_PLAN.md` on 2026-11-16; the original file was removed.

> Owner scope update: personal use for at most five users, PC first and
> phone/iPad later; no commercial-grade distribution/signing prerequisite.
> Piper is removed in favor of Kokoro-82M. The earlier `6c211b60` signed
> candidate/audit precede this change and retain their original SHA.
> [Authoritative scope and remaining engineering checks](BETA_RELEASE_PLAN.md#appendix-a--owner-scope-2026-11-09).


This continues the installed Linux test-candidate run. The host is Ubuntu
24.04 x86-64 in Codespaces (2 processors, 8 GiB RAM). These measurements do
not constitute beta sign-off. Existing owner decisions about beta.2, signing,
fresh VMs and hardware remain in force.

### Work and evidence

| Requested work | Result and limit |
|---|---|
| RPM and all-format packaging | Reproduced FPM's `rpmbuild failed (exit code )` using its default `w9T.xzdio`, peaking above 1.9 GiB RSS. A controlled 512 MiB address-space test fails with that compressor and succeeds with `w6.xzdio`. RPM now explicitly uses single-threaded level-6 xz. The original signal is not identified, so memory exhaustion is an inference, not a proved historical OOM. The fresh Python 3.12 freeze, smoke checks and full AppImage/DEB/RPM wrapper passed. All three SHA-256 checks pass; RPM reports xz level 6 and its payload digests verify. RPM native Fedora installation remains untested. |
| Disposable Apply | Linux Apply pins both trees' parent directories with `O_DIRECTORY | O_NOFOLLOW` until Apply/rollback completes. Reads pin the leaf once and reject nonregular files. Atomic rollback replaces directory entries instead of truncating a possible link referent. Six deterministic adversarial tests cover parent swaps on both sides, symlink/hardlink substitution during rollback, FIFO substitution and persistent ENOSPC. **Windows/macOS handles and the file-tool TaskTree path race remain open.** |
| Managed Voice V1 | Five Whisper model files now have immutable Hugging Face revisions, exact sizes and LFS SHA-256 digests. Amy has a digest but remains refused for licence review. Linux/macOS whisper-server assets, packaged speech execution and Kokoro's GPL-related dependency review remain blockers; VD-1 stays partial. |
| Seven journeys | First-run setup and keyboard/zoom UI checks ran, with screenshots inspected. The updated first-run spec explicitly defers Voice. These are partial T-01/T-14 evidence; the seven full journeys and five fresh-state model-driven repetitions are **not** declared passed. See the journey table below. |
| Fault injection | Actual storage exhaustion on a dedicated 16 MiB tmpfs filled to 98.02%; Apply retained its journal and recovered the originals once space returned. A live host was killed mid-goal and restarted: same task, one model call, `interrupted_by_restart`, no false completion. Provider socket faults and native resource-limit tests passed. |
| Integration lifecycle | 39 automated expiry, rejected refresh, vault/removal and connector lifecycle tests passed. They use controlled provider responses. Live provider revocation and the full supported-connector install/use/revoke/remove/reconnect matrix remain blocked by unavailable registered clients/accounts. |
| Egress audit | The fresh installed `6c211b60` shell/host capture passes its predeclared scope: 1,862 seconds of observed activity, 4,115 observations, no unexpected destinations. All 135 Chromium IPv6 UDP route probes fail with ENETUNREACH and close without same-thread sends. Earlier failed traces remain failed. This unsigned, credential-free navigation profile does **not** close the all-feature signed-candidate MM-5 gate. |
| Release documentation | This record reconciles the beta plan, open defects, fixed items and acceptance matrix; no platform or owner-machine gate is closed from a different test. |
| Candidate artifacts | Release `42650624663` produced non-published `0.9.0` beta artifacts from exact runtime commit `6c211b60`. All 10 installer hashes/Ed25519 manifests, six Linux GPG signatures, signed channel/provenance, SBOM binding and lock/checksum files independently verify against repository pins. The product verifier passes. macOS platform signing remains excepted; feature/journey/owner sign-off gates remain open. |

Local evidence is retained under `output/linux-beta/` (ignored build output):

| Receipt | What actually passed |
|---|---|
| `rpm-before.log`, `rpm-compression-pressure.json` | Original failure reproduced; bounded-compression comparison |
| `apply-privacy.xml` | 36 Apply, journal/crash-recovery and reputation tests |
| `storage-exhaustion.json`, `storage-exhaustion-live.xml` | Real bounded ENOSPC, journal retained, originals restored |
| `journey-fault-regressions.xml` | 99 memory-forget, stop/control, socket-provider faults, privacy/recovery and connector regressions |
| `goal-restart-current.json` | Real kill/restart, scripted model only; one call before and after, same task ID |
| `linux-native-adversarial.log` | 15 native Linux tests, including memory, CPU and process limits, descendant containment and filtered egress |
| `voice-v1.xml`, `voice-pins.txt` | 23 voice tests and the revision/digest resolution log; no live packaged speech claim |
| `local-inference.xml`, `local-inference.log` | Real verified llama.cpp b12223 CPU install, tiny GGUF inference, second slot, reconfiguration, restart and shutdown |
| `integration-lifecycle.xml` | 39 automated connector lifecycle tests; not live provider sign-in/revocation |
| `release-contracts.xml` | 66 release-evidence, workflow, desktop and documentation contracts |
| `web-components.log` | 39 setup and Web access component tests |
| `web-check.log`, `ruff.txt`, `mypy.txt` | Svelte: zero errors/warnings; Ruff passed; mypy: 631 source files |
| `journeys-corrected-ui.log`, `accessibility-corrected-ui.log` | Onboarding 1/1; keyboard destination sweep and 200% zoom 2/2 |

### Journey qualification

| Journey | This run | Still required for acceptance |
|---|---|---|
| T-01 | Source-host first-run wizard passed, including Voice → Not now and truthful model-deferred state | Fresh installed candidate, permitted useful model and first-task receipt |
| T-03 | Actual host restart drill passed with a scripted model | Calendar/preferences/draft itinerary scenario with a real model, repeated on fresh state |
| T-04 | Forget/suppression regressions passed | Correction/forget/repeated relevant task in the installed UI with real inference and receipts |
| T-08 | Authorized `sharRahul/raiker-test-sandbox` returns 404 to this session; previous creation attempt returned 403 | Repository access, actual bug/branch/check/push/draft-PR receipt; no merge |
| T-13 | Stop, control and provider-fault regressions passed | Real goal with children/pending effects, resume revalidation, and time/cost pause receipts |
| T-14 | Keyboard traversal and 200% zoom passed; screenshots inspected | Screen reader and three first-time evaluators; complete start/approve/stop/find/recover scenario |
| T-15 | Native adversarial, privacy/recovery, provider socket faults and actual storage exhaustion passed | Full hostile-content/expired-provider/duplicate-trigger journey on the installed exact candidate |

Tiny `stories260K` inference verifies the engine lifecycle, not a useful
tool-using assistant. It cannot be used to close the seven journeys.

### Voice licence and distribution review

Whisper models are pinned to
`ggerganov/whisper.cpp@5359861c739e955e79d9a303bcbc70fb988958b1`, under
the existing MIT catalogue classification. The installer still verifies the
actual downloaded bytes; resolving an LFS object ID does not execute a model.

Amy is pinned to
`rhasspy/piper-voices@e7229f7d33a10e145e109b886d661984201ac3c4` but is
**not approved**. Its [upstream model card](https://huggingface.co/rhasspy/piper-voices/blob/e7229f7d33a10e145e109b886d661984201ac3c4/en/en_US/amy/medium/MODEL_CARD)
points to Mimic3 for dataset terms and states Lessac fine-tuning provenance.
The engine's MIT licence does not establish the voice/dataset's terms.
The separate Piper JSON sidecar also needs a pinned digest and verified
installation before enabling this voice; the existing ONNX entry alone is
insufficient. Kokoro's `espeak-ng` distribution review stays open under
[the licensing policy](../licensing/LICENSING_POLICY.md).

### Egress findings and interpretation

The installed pre-fix host's startup thread contacted URLhaus and OpenPhish
before owner setup. This was public-feed retrieval, not evidence that private
content was uploaded, but it contradicts an unconditional local-only traffic
claim. The correction preserves local matching and existing cached lists.
After the first owner-requested update, stale feeds can refresh at startup;
`RAIKER_THREAT_FEEDS=off` still disables background refresh.

Use `scripts/strace_egress_metadata.py` to extract only timestamps and IP
destinations from a private `strace -f -ttt -s 0` network trace, then pass that
JSONL to `scripts/verify_egress_audit.py`. The converter retains failed attempts
and never invents start/end observations. A route-discovery UDP `connect`
does not itself prove a transmitted packet. Native probes also deliberately
contact a listener on the host's own non-loopback address; distinguish those
controls in the record rather than silently dropping them or adding arbitrary
external hosts to the release allowlist.

### Visual evidence

These are **source-host** screenshots, taken with a changed working tree over
`304e71ff`; they are not presented as frozen-candidate screenshots. Original
capture metadata is retained beside them as `source-manifest.json`.

!`Voice is optional and unsupported options are labelled`

!`Setup saved with the model explicitly deferred`

!`Chat composer at the 200 percent zoom equivalent`

### Reference decisions

The package change follows RPM's documented [payload compression flags](https://rpm.org/docs/latest/man/rpm-payloadflags.7).
The containment review also consulted [Claude Code's filesystem/network sandbox guidance](https://code.claude.com/docs/en/sandboxing)
and [Hermes Agent's security boundary documentation](https://github.com/NousResearch/hermes-agent/blob/main/SECURITY.md).
These references inform implementation review; none supplies Raiker's test
evidence, licences, sign-off or authorization to widen beta scope.

### Artifact and audit receipts

The new local all-format artifacts are unsigned `0.0.0` test builds from this
working tree, collected under `output/linux-beta/packages-hardened/`. They do
not carry an exact-commit provenance claim. Their
`checksums`,
`compression-pressure result`,
`real storage-pressure receipt`
and `goal restart receipt`
are retained with this record.

Both timed network recordings are retained privately under `output/` and
contain no captured payloads. The `installed pre-fix verdict`
and `corrected-source verdict`
are **not approved**. The latter trace's first/last recorded syscall events
span 1,805.76 seconds, but the existing verifier measures first/last connection
activity (181 seconds), which cannot qualify its idle tail. Do not fabricate
connection observations to fill that gap. In addition to documented local
probe/route-discovery destinations, the navigation sweep observed external
addresses still requiring attribution and an explicit local-only policy.
The corrected startup guard alone does not close MM-5.

### Sidecar status and RPM payload follow-through

The navigation sweep also exercised ChatGPT subscription status, which started
the installed Codex App Server before this Raiker profile had connected it.
FIXED-1375 makes an unconnected status read passive (`not_connected`) and
retains explicit sign-in/adoption. This corrects another unsolicited-network
path; it does not retroactively approve either failed capture or establish
that every external address in them came from this process. Local evidence:
`passive-codex.xml` (22 tests), `codex-contracts-locked.log` (5 contract cases),
`passive-codex-mypy.txt` and `passive-codex-web-check-final.log`. API generation
was verified under the locked Python 3.12 build environment; the workspace's
Python 3.14 renders some existing optional-union inventory names differently.

The RPM's extracted host passed the full smoke/restart/setup-persistence suite
(`rpm-host-smoke.txt`). Its onboarding window passed. The separate first-run
window test initially observed a renderer crash during Setup; its isolated
fresh-profile retry passed (`rpm-window-retry.log`). Both attempts are retained.
A retry does not erase the initial crash; native Fedora installation and a
repeatability check remain outside this Ubuntu extraction test.

### GitHub qualification and release-dispatch access

Runtime commit `8a053a907b9c9e97bef4163f479650ac3d652f28` is pushed to main.
[CI](https://github.com/sharRahul/Raiker/actions/runs/42639300007),
[llama.cpp engine](https://github.com/sharRahul/Raiker/actions/runs/42639300373)
and [Data safety drills](https://github.com/sharRahul/Raiker/actions/runs/42639300064)
are all green, including Ruff, mypy, lint/type checking, every Python shard,
security/dependency checks and real inference on all three operating systems.
The exact verification script from Release → Plan also passed locally for
that SHA (`receipt`).
The previous runtime/packaging commit `91b07ce2` additionally passed all desktop
targets and the Windows-on-Arm emulated installation in
[Desktop package](https://github.com/sharRahul/Raiker/actions/runs/42637512116).
That packaging evidence is explicitly not an exact-`8a053a90` package claim.

The signed, non-published release dispatch was attempted with version `0.9.0`,
channel `beta`, signing `require-except-macos`, and `publish=false`. GitHub
rejected it: **403 Resource not accessible by integration**. No release run or
new signed artifacts were created by that attempt. Actions write access or an
owner-triggered manual run is required; do not change the workflow's deliberate
manual trigger or weaken its gate to bypass this permission boundary.

Once access is available, the concrete non-publishing command is:

```bash
gh workflow run release.yml --ref main \
  -f version=0.9.0 -f channel=beta -f signing=require-except-macos \
  -F publish=false
```

Recheck every required result on the SHA selected by that run. Signed channel,
SBOM, provenance and `RELEASE_EVIDENCE.md` must come from its actual outputs;
they remain blocked here. An unsigned local candidate cannot substitute for
those trust records. Publication remains blocked by the feature/journey/audit
gates independently of workflow access.

The final source UI status check returned `not_connected`, kept the explicit
adoption button visible, and observed no public destinations in its focused
trace (`UI receipt`,
`network receipt`).
It is a short regression check, not MM-5 acceptance.

!`Explicit sign-in and adoption without a background account check`

### Electron network process follow-through

The unsigned exact-commit `0.9.0` candidate from
`2f0ede1d8d09efe93458369d278dfdbc70d76120` built in all three formats;
checksums, installed DEB host smoke/restart/setup persistence and local SPDX
generation passed (`candidate-2f0ede1d/`, `candidate-installed-smoke.txt`,
`candidate-sbom.log`). It is unsigned and is not an approved release.

A new installed-shell capture includes Electron and its child host, rather
than only the host. Its startup network process attempted public IPv4 Google
connections before owner setup. FIXED-1376 disables automatic DoH before the
default session exists, suppresses external hostname resolution and cancels
non-loopback renderer HTTP(S)/websocket resource requests. The local host and
explicit external-browser actions keep their respective roles.

Validation: 36 desktop unit tests and 13 shell UI tests passed. The new
embedded-resource test first reaches its server outside the shell, then proves
the renderer request is blocked before it reaches that server. The corrected
focused startup trace has no corresponding public IPv4 connections;
`its raw destination report`
retains `2001:4860:4860::8888`. This is **not claimed as zero public-address
syscalls**: a separate socket/close trace shows a UDP socket whose connect
fails with ENETUNREACH and closes without a DNS payload. Chromium documents
that literal address as its [IPv6 route/reachability heuristic](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/net/dns/README.md#IPv6-and-connectivity).
Do not equate that non-sending route probe with a completed DoH request, or
silently omit it from the conservative audit input.

Implementation follows Electron's [resolver API](https://www.electronjs.org/docs/latest/api/app#appconfigurehostresolveroptions)
and Chromium's [host-resolution remapping](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/net/dns/README.md#Request-remapping).
A short startup regression is not a replacement for a fresh 30-minute
installed-candidate audit. The pre-fix full-shell trace remains failed.

The owner started [Release 42642643448](https://github.com/sharRahul/Raiker/actions/runs/42642643448)
on `2f0ede1d`. Plan correctly refused because that commit's CI had not yet
finished; packaging/signing did not start. Its macOS native job was cancelled
while queued, then the failed-job rerun completed successfully: CI, engine/live
and data-safety workflows on `2f0ede1d` are green. The shell correction changes
the candidate source again: qualify its own commit and start a new Release run
for that commit rather than treating the older run as evidence for the fix.

### Completed installed-shell audit and CI artifact verification

Runtime commit: `6c211b605d3c42d77215ff69cbed3f346c95d685`.
[CI](https://github.com/sharRahul/Raiker/actions/runs/42646385241),
[data safety](https://github.com/sharRahul/Raiker/actions/runs/42646385452),
[engine/live inference](https://github.com/sharRahul/Raiker/actions/runs/42646385237)
and the complete [desktop matrix](https://github.com/sharRahul/Raiker/actions/runs/42646385236)
are green. The macOS live-inference job was cancelled before starting; its
failed-job rerun passed. The `exact Release Plan gate`
passed on this same commit. `Workflow receipt`.

The downloaded unsigned CI `0.0.0` Linux artifacts all match their recorded
hashes and sizes; RPM reports `xz 6` and passes its payload digests.
Installed DEB and AppImage smoke/restart/setup persistence, packaged onboarding
and uninstall-with-data-retention passed on GitHub's Linux runner.
`Artifact verification`.
The separate local unsigned `0.9.0` candidate also passed hash checks, installed
host smoke and SPDX/licence inventory. Its extracted AppImage payload passed
first launch (one test); this is not a claim of native FUSE mounting here.

The final installed-shell audit used that local unsigned `0.9.0` DEB. Its
`scope`
was recorded before capture: fresh synthetic owner, no model selected, Voice
off, no connected external services. Electron and its frozen-host descendants
were traced with payloads elided. The driver completed 62 page visits over
30 minutes and recorded no navigation failures.
`UI receipt`.
The recorder was stopped after that exercise, before its 33-minute safety timeout.

The unchanged verifier approved **1,862 seconds** of actual destination activity,
**4,115 observations**, and **zero unexpected hosts** against that scope.
`Verifier report`.
The source metadata capture SHA-256 is
`1bb8fb59ae41f2b27dc6fa45a5af088c38875c3a06575a02d6de37f5222b15ba`.
`Capture/trace hashes and limits`.
The private trace and JSONL remain in ignored `output/linux-beta/egress-shell-hardened/`;
only redacted receipts are committed.

The predeclared exceptions include this machine's native sandbox/control
probes and Chromium's literal IPv6 route heuristic. All **135** Chromium
observations use UDP, fail with ENETUNREACH, and close without a send on the
same thread before close.
`Probe receipt`.
This is not a zero-public-address-syscall claim. The earlier threat-feed,
ChatGPT sidecar and Electron public-request failures are retained in the
historical receipts; no destinations or timestamps were removed to obtain approval.

**MM-5 stays partial:** this credential-free navigation profile does not cover
useful-model inference, installed managed speech, enabled connectors, full
owner-machine canary/recovery evidence or a fresh audit of the signed artifact.
The seven journeys and owner sign-off remain open. Inspected screenshots:

!`Installed candidate with no selected model`
!`Installed candidate Voice availability`
!`Installed candidate with no connected services`

### Verified non-published signed candidate

The owner started [Release 42650624663](https://github.com/sharRahul/Raiker/actions/runs/42650624663)
with version **`0.9.0`**, channel **`beta`**, signing **`require-except-macos`**,
and **`publish=false`**. Plan's exact-commit gate passed on runtime
`6c211b605d3c42d77215ff69cbed3f346c95d685`; every native packaging job,
Windows ARM emulation, matrix and channel job passed. Publication jobs were
skipped. The earlier `0.9.0-beta1` attempt was correctly refused by the updater's
X.Y.Z version rule; it produced no candidate. The successful run supersedes
the Actions-dispatch blocker for **this candidate** through the owner's manual
start, without changing the session's dispatch permissions.

Download the [release-channel artifact](https://github.com/sharRahul/Raiker/actions/runs/42650624663/artifacts/13690398721)
(30-day workflow retention). A local copy is retained in ignored
`output/linux-beta/release-channel-6c211b60/`.

Independent verification used the repository-pinned Ed25519 key and an isolated
GPG keyring imported from the repository's pinned Linux public key:

- All **10** installer manifest signatures and artifact SHA-256 hashes pass.
- All **six Linux** detached GPG signatures match fingerprint
  `248BC52909AAAAFDFA77EF0D0BFFAD3B8A2024C1`.
- Channel and provenance signatures pass against the pinned Ed25519 key;
  the published public key matches that pin.
- Provenance names exact runtime `6c211b60` and this workflow; its `uv.lock`
  hash matches the repository. SBOM and artifact digests and every checksum
  file verify.
- The product's own release verifier passes using the repository pin.
- The generated `RELEASE_EVIDENCE.md` names the correct commit and contains
  no missing-output marker.

`Verification receipt`,
`workflow results`,
`product verification`,
`generated release evidence`,
and `signed provenance`
(`detached signature`).
Windows Authenticode identity and native installation were checked on Windows
by the workflow, not independently executed on Linux. macOS remains unsigned
at the platform level under the existing beta exception; its Ed25519 manifests
still verify. No GitHub release or publication is claimed from this run.

The reporting correction (FIXED-1377) does not change that candidate. The
owner subsequently requested Piper removal and a personal Kokoro build; that
runtime change needs its own candidate. These earlier signed outputs remain
exactly `6c211b60` and must not be relabelled as containing Piper removal.
CI-1/CI-5 candidate-output evidence is now present, but the seven real-model
journeys, VD-1 licences/assets/packaged speech, live OAuth/connector lifecycle,
full-feature signed-artifact MM-5 and release-owner sign-off remain gates.

### Owner scope and Kokoro-only personal build

The owner clarified personal use by at most five users, own PC first and
phone/iPad app access later; production distribution/signing infrastructure
is not required. [Authoritative scope](BETA_RELEASE_PLAN.md#appendix-a--owner-scope-2026-11-09).

Piper engines/voices and their worker/profile/planner/download paths are
removed. Lite and Balanced use verified Kokoro-82M int8 plus its voice bank;
High uses fp32. A removed/unknown saved voice falls back to the Kokoro default.
Regression tests reject removed engine/item/profile selections and preserve
valid Kokoro voice choices. Piper licence/sidecar review is removed work.

Real direct synthesis passed with verified catalogue assets and Kokoro-ONNX
0.6.1: 24 kHz, nonzero PCM, 1.877-second clip, 295,440 KiB peak RSS, no observed
IP destination during synthesis.
`Synthesis receipt`.
The full managed live test correctly refused this busy machine's available
memory below its 2 GiB reserve; the guard was not weakened.

The explicit `--bundle-voice` build option requires the separately hash-locked
`requirements/voice.txt`, verifies exact installed versions, and includes the
runtime, phonemizer library/data, dependency metadata and licence notices.
It refuses reuse through `--skip-freeze` rather than claiming an old host
contains voice. No dependency policy was broadened silently.
[Runtime notices](../licensing/voice/README.md).

The first frozen Linux worker test **passed** using the bundled executable,
verified real model assets and authenticated loopback requests; unauthenticated
health requests are refused, WAV output is 24 kHz/nonzero and the worker stops.
`Frozen-worker receipt`.
That is a working-tree freeze qualification, not an exact-commit installer
claim. Full profile memory admission, Linux Whisper packaging, actual microphone
round trip and owner's own-PC trial remain separate checks.

The earlier signed DEB was also installed locally and passed its signed
provenance, fresh owner/setup and restart persistence smoke.
`Installed signed-candidate receipt`.
This receipt remains attached to pre-removal runtime `6c211b60`.

## Appendix C — Data-safety evidence

> Merged from `docs/plans/BETA_RELEASE_PLAN.md` on 2026-11-16; the original file was removed.

This ledger distinguishes automated regression evidence from evidence that
must be recorded on a release-candidate owner machine. A row is not release
evidence until it names the exact commit, GitHub Actions run, and artifact.

### Automated boundary and recovery evidence

`Data safety drills` is a required release check. It runs the following
deterministic tests together:

- `tests/test_embedding_trusted_classification.py`
- `tests/test_memory_key_never_leaves.py`
- `tests/test_memory_semantic_index.py`
- `tests/test_model_transport_guard.py`
- `tests/test_multipart_egress.py`
- `tests/test_store_key_guard.py`
- `tests/test_lock_screen_recovery.py`
- `tests/test_workspace_backups.py`
- `tests/test_verify_egress_audit.py`

The check proves the guarded model transport and workspace-key boundaries, and
the checked backup/lock-screen recovery paths. It is not a substitute for the
owner-machine canary, destructive recovery, or network recording below.

| Evidence | Status | Required release record |
| --- | --- | --- |
| Automated boundary/recovery suite | Passing on PR #247 head `80af4407e307206d5d620673fc32b33ee3d34ef8` | Link the successful `Data safety drills` run after the commit is merged; re-run on the exact release commit. |
| Credential/privacy canary | Automated (2026-11-08): `tests/test_privacy_canary_drill.py` in Data safety drills | Put distinct fake key, password, and card markers in a connector, memory, and file. Exercise a turn, task, and support export. Attach redacted model-request, event/log, and export searches that find none of the markers. |
| Destructive recovery drill | Automated (2026-11-08): `tests/test_destructive_recovery_drill.py` in Data safety drills | On a disposable release candidate, truncate the database, flip a page byte, remove the key file, and exhaust disk space during a write. Record the newest verified backup offered and prove no empty workspace was silently created. |
| Local-only egress audit | Pending owner-machine recording | Record at least 30 minutes of metadata-only connection observations while using all enabled local-profile features. Attach the approved verifier report and the capture hash. |

### Local-only egress audit procedure

Run the release candidate with a recording proxy or connection monitor that
emits **metadata-only JSON Lines**. Every observation must contain only:

```json
{"timestamp":"2026-11-02T10:00:00Z","host":"127.0.0.1"}
```

Do not store request bodies, headers, URLs, tokens, or raw packets in the
release record. With no owner-configured remote destination, the allowed hosts
should normally be loopback only. Verify the capture with:

```bash
python scripts/verify_egress_audit.py \
  --capture /secure/path/local-only.jsonl \
  --allowed-host 127.0.0.1 \
  --allowed-host ::1 \
  --scope local-only \
  --output release-evidence/local-only-egress.json
```

The verifier writes a redacted report containing only timing, destination host
names, a SHA-256 of the source capture, and the pass/fail reasons. It exits
non-zero if the recording is under 30 minutes or observes an unapproved host.
Publish the report and capture hash, not the capture itself. If the owner has
explicitly configured a remote destination, list that exact destination with
an explanation in the release record before running the audit.

### Release sign-off rule

The release approver must attach the four records above to the exact release
commit. A passing CI check alone must not convert a pending owner-machine row
into a pass.

### 2026-11-09 — Linux test-candidate evidence

On Ubuntu 24.04 x86-64 (Codespaces), the privacy canary, destructive recovery
and audit-verifier regression suite passed: local JUnit artifact
`output/linux-beta/data-safety.xml`. These are automated regressions run locally,
not the owner-recorded release-candidate observations required above.
The verifier now refuses thresholds below the documented 1,800-second minimum
([FIXED-1369](FIXED_ITEMS.md#fixed-1369--the-release-egress-audit-could-be-shortened-to-one-second)).
No 30-minute network recording was generated or inferred from these tests.

### Installed-host egress finding — 2026-11-09 follow-through

The timed connection trace found public threat-feed downloads at startup on
a fresh profile. FIXED-1372 makes the first download owner-requested (or an
explicit environment opt-in); local matching still uses cached lists. The
[run record](BETA_RELEASE_PLAN.md#egress-findings-and-interpretation) records
the finding and separates installed pre-fix evidence from the corrected-source
recording. A corrected-source recording cannot close exact-candidate MM-5.
`strace_egress_metadata.py` extracts only actual destination/timing observations
and keeps failed attempts; the verifier's 1,800-second minimum is unchanged.

### 2026-11-09 — Completed bounded installed-shell audit

The `6c211b60` installed unsigned Linux shell/host audit passes its predeclared
fresh-profile scope: 1,862 seconds of actual destination activity, 4,115
observations, no unexpected hosts. The 30-minute navigation driver completed
62 visits without failure; screenshot states were inspected. Chromium's 135
non-sending IPv6 UDP route probes and native control probes remain explicit
in the scope and receipts. Earlier failed captures remain failed.

**MM-5 remains partial:** no selected useful model, managed speech, enabled
external connector, owner-machine full-feature sign-off or signed-artifact
capture is inferred. All four qualification workflows for runtime `6c211b60`
are green; downloaded CI Linux artifact hashes and RPM digests verify.
[Evidence and limits](BETA_RELEASE_PLAN.md#completed-installed-shell-audit-and-ci-artifact-verification).

## Appendix D — Desktop package acceptance matrix

> Merged from `docs/plans/BETA_RELEASE_PLAN.md` on 2026-11-16; the original file was removed.

> Owner scope update: personal use for at most five users, PC first and
> phone/iPad later; no commercial-grade distribution/signing prerequisite.
> Piper is removed in favor of Kokoro-82M. The earlier `6c211b60` signed
> candidate/audit precede this change and retain their original SHA.
> [Authoritative scope and remaining engineering checks](BETA_RELEASE_PLAN.md#appendix-a--owner-scope-2026-11-09).


Per-platform evidence for the desktop installers
([ADR-0003](../adr/ADR-0003-desktop-distribution.md)). A result is **PASS**
only when it was executed and the evidence is named. **NOT TESTED** means it
has not been run. **BLOCKED** names the blocker. Nothing here is inferred from
another platform.

Builds are unsigned until the release owner configures the signing identities
([Releasing](../guide/releasing.md#publishing-a-signed-release)), so every
row below is for an **unsigned** build.

### Matrix

Status as of 2026-10-20. CI evidence: `.github/workflows/desktop-package.yml`,
[run 39327713463](https://github.com/sharRahul/Raiker/actions/runs/39327713463)
(attempt 2) on commit `9c65e86` on `main` (PR #236) — all seven jobs green: the
four build targets, the emulated Windows-on-Arm install, web assets and the
release acceptance summary. Earlier runs 39051611755 on `808409c` (PR #235),
39044354934 on `6758e64` and 39041854653 on `914b60a` passed before it. Each
target runs on its own GitHub-hosted runner, unsigned, version stamp `0.0.0`,
and its artifact holds its installers and the evidence files named below. The
workflow runs on pull requests and pushes to `main` that touch packaging paths,
on demand, and from `release.yml`; a change outside those paths (such as the 2026-10-20 model
transport work) does not re-run it.

**What a release carries.** A draft GitHub release has exactly one installer
per platform (`RELEASE_ASSETS`, `raiker/app/desktop_release.py`;
`scripts/select_release_assets.py`): `windows-x86_64-setup.exe`, the same
installer as `windows-arm64-setup.exe`, `macos-arm64.dmg`,
`linux-x86_64.AppImage` and `linux-arm64.AppImage`, with `SHA256SUMS.txt`. The
`.msi`, `.zip`, `.deb` and `.rpm` formats in the table are built and tested on
every run but are not attached to a release. No release has been published
yet.

| Target (runner) | Installers | Build + frozen-host smoke | Install | Installed-host smoke | Window + onboarding | Uninstall keeps data | Signed-channel update |
|---|---|---|---|---|---|---|---|
| windows-x86_64 (`windows-2022`) | setup.exe, msi | PASS | PASS — NSIS `/S` per user, Start-menu shortcut present; MSI `/qn` per user | PASS (NSIS and MSI) | PASS | PASS — NSIS uninstall; MSI `/x` | NOT TESTED |
| Windows on Arm (`windows-11-arm`, x86-64 package under emulation) | setup.exe (x86-64) | n/a — no native build | PASS — NSIS `/S` per user | PASS | NOT TESTED | PASS — NSIS uninstall | NOT TESTED |
| macos-arm64 (`macos-14`) | dmg, zip | PASS | PASS — app copied from the mounted dmg to ~/Applications | PASS | PASS | PASS — app removed, ~/Library/Application Support/Raiker kept | NOT TESTED |
| linux-x86_64 (`ubuntu-22.04`) | AppImage, deb, rpm | PASS | PASS — `apt-get install ./…deb` | PASS (deb and AppImage) | PASS | PASS — `apt-get remove raiker`, ~/.local/share/raiker kept | NOT TESTED |
| linux-arm64 (`ubuntu-22.04-arm`) | AppImage, deb, rpm | PASS | PASS | PASS (deb and AppImage) | PASS | PASS | NOT TESTED |

"Installed-host smoke" is `raiker.app.desktop_smoke` from an empty profile:
provenance (unsigned), ready, health, encrypted store, FTS5, web app served,
owner registration, setup required, system check with no blocking failure,
installation check with no failed mandatory component, setup saved, quit,
restart over the same profile, sign-in and setup progress after restart.
"Window + onboarding" is `packaged-live.spec.ts` and
`packaged-onboarding-live.spec.ts` against the installed executable: the
**Raiker Setup** window opens first (Finish installing → *Checking this
computer* lists what it found → host started → verified → *Raiker is ready*),
**Open Raiker** opens the window on first run, and an owner registers and walks
Welcome → Model (Decide later) → Privacy → Permissions → Setup saved → Home.

**Installation-time checks.** Windows: every NSIS install in CI is silent
(`/S`), which runs the same memory and free-space measurement in `customInit`
and installs only when it passes — PASS on both Windows rows. The interactive
*Checking this computer* page itself is NOT TESTED (no GUI driver for the NSIS
wizard in CI); it compiles in electron-builder's include order. Linux: the
`.deb` pre-install check ran and passed in each `apt-get install` (and
locally: "Raiker: checking this computer before installing … memory: 16093
MB"). The refusal paths (too little memory or disk) are NOT TESTED on a real
machine.

**Windows on Arm** — there is no native arm64 package (`cryptography` ships
no win_arm64 wheel, so the host cannot be frozen there). The x86-64 installer
was installed, smoke-tested from an empty profile and uninstalled on a
`windows-11-arm` runner under Windows' x64 emulation (evidence
`smoke-installed-windows-arm64.txt`, `uninstall-windows-arm64.txt`). The
window tests were not run there.

**.rpm** packages are built and checksummed on both Linux runners but are not
installed in CI (the runners are Debian-based); NOT TESTED beyond `rpm -qp`
inspection locally (package name `raiker`).

**Not covered by any row:** signed builds (no identities configured),
Gatekeeper on a quarantined download, SmartScreen, a real model provider, and
an update through a published signed channel.

### Beta readiness — host checks (2026-10-26)

What a beta tester's host does that the installer rows above do not cover,
checked on a source build served by `raiker-web`:

| Check | Status | How |
|---|---|---|
| A forwarded request on the local listener is refused and says what to change | PASS | RT-SEC-01; `tests/test_proxied_loopback.py` |
| Diagnostics names a refused proxy, with flags kept on one line | PASS | RT-SEC-02 |
| Every request on the proxy listener is remote, with no forwarding header or a misleading one: recovery refused, rate limited, HSTS over HTTPS | PASS (live, unit, and a real uvicorn server) | RT-SEC-03; `test_a_real_server_tells_its_listeners_apart` |
| The proxy listener as a Unix socket (`--proxy-socket`), mode `0660` | PASS (by hand and unit) | `test_a_real_unix_socket_listener_is_remote`; [WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md), BUG-347 review round |
| The host refuses to start while `RAIKER_TRUSTED_PROXY` is set, and refuses `--allow-public` or a non-loopback `--host`; `RAIKER_OWNER_TOKEN` is not read | PASS (unit and by hand) | `tests/test_proxied_loopback.py`, `tests/test_remote_auth.py` |
| Remote access is chosen, checked, applied with fresh MFA, restarted into, rolled back and turned off from Settings; the UI shows only what the running host reports | PASS (live, Linux) | RT-SEC-04 to RT-SEC-07, RT-SEC-11, RT-SEC-12 |
| Another device needs the password and a code over HTTPS; password-only and local sessions are refused; MFA off suspends at once | PASS (live, Linux; unit on all three) | RT-SEC-08 to RT-SEC-10; `tests/test_remote_auth.py` |
| Real listeners (TCP, TLS, Unix socket), port claims and restart status on Windows and macOS | PASS (CI job *Remote access*) | `tests/test_remote_access.py`, `tests/test_proxied_loopback.py`; no live browser round on either ([BUG-359](TO_BE_FIXED.md#bug-359--remote-access-is-verified-live-on-linux-only-and-has-five-known-limits)) |
| The packaged desktop host behind a proxy | NOT TESTED | The desktop app binds loopback for its own window; it is not meant to sit behind a proxy |

### Local evidence (Linux x86-64)

Built with `python scripts/build_desktop_app.py --version 0.1.0` at the PR's
first commit:

- `Raiker-0.1.0-linux-x86_64-unsigned.AppImage` (182 MB), `.deb` (150 MB),
  `.rpm` (134 MB); `sha256sum --check SHA256SUMS-linux-x86_64.txt` → all OK.
- Frozen-host smoke before packaging: 20 PASS, 0 FAIL.
- `apt-get install ./Raiker-0.1.0-linux-x86_64-unsigned.deb` → installed to
  `/opt/Raiker`, `/usr/share/applications/raiker.desktop`, `/usr/bin/raiker`.
- `python -m raiker.app.desktop_smoke --host /opt/Raiker/resources/host/Raiker
  --expect-unsigned` → 20 PASS: provenance, ready, health, encrypted store,
  FTS5, web app served, owner registration, setup required, system check (no
  blocking failure), installation check (no failed mandatory component), setup
  saved, quit, restart opens the same profile, sign-in after restart, setup
  progress survives restart. The governed-command runner is present at
  `_internal/raiker/native/linux-x86_64/` and executable.
- `xvfb-run npx playwright test --project=live packaged` with
  `RAIKER_PACKAGED_APP=/opt/Raiker/raiker` → 2 passed: the installed window
  starts its bundled host and opens on first run; an owner registers and
  completes Welcome → This device → Model (Decide later) → Privacy →
  Permissions → Check (no "Needs attention") → Setup saved → Home.
- Reinstalling the rebuilt `.deb` over the first (`apt-get install --reinstall`)
  succeeded and the new build passed the same two window tests: a package
  upgrade in place, not an update through the signed channel.

### Scenario coverage

| Scenario | Status | How |
|---|---|---|
| Fresh install, no developer tools on the profile | PASS on Linux (local); per-target in CI | Smoke test from an empty profile; the host is frozen and uses no system Python |
| Setup wizard completes | PASS on Linux (local) | `packaged-onboarding-live.spec.ts` |
| Backend starts automatically and restarts | PASS on Linux (local) | Window starts the host; smoke test quits and restarts it |
| A supported AI provider answers | NOT TESTED | Needs a provider credential or a local runtime on the runner; the Check stage's model request covers it on a real machine |
| Basic agent task within approved permissions | NOT TESTED in packaged builds | Covered for source builds by the existing live suites |
| No internet during install and first run | PASS by construction on Linux (local) | Installer downloads nothing; smoke test makes no outbound request |
| Interrupted download, corrupted or untrusted update | PASS (unit) | `tests/test_desktop_update.py`: tampered digest, foreign key, wrong version refused |
| Insufficient disk / memory, unsupported architecture or OS | PASS (unit) | `tests/test_system_check.py`; Windows installer `customInit` refuses old and 32-bit Windows |
| Keystore unavailable or locked | PASS (unit) | `tests/test_os_keystore.py`: fail closed, never regenerated, file fallback |
| Missing optional local runtime | PASS (unit and UI) | System check reports it as optional; Models links the official download |
| Uninstall keeping data | Per-target in CI | Uninstall steps assert app removed, data kept |
| Uninstall removing selected data | NOT TESTED in CI | Interactive dialog (Windows) / Settings → Account → Delete my account; keyring removal covered by `tests/test_os_keystore.py` |
| Update through the signed desktop channel | PASS (unit); NOT TESTED end to end | Needs a published signed release and a channel host |
| Failed-update recovery | PASS (unit) | `.previous` rollback for AppImage; NSIS installer is transactional |
| API keys not written to logs | Unchanged existing redaction | Existing log redaction tests; the smoke test sends no key |
| Installer privileges minimised | PASS (config + CI) | `perMachine: false`, `allowElevation: false`; CI installs without elevation |

### Linux hardening qualification — 2026-11-09

[Detailed run record and limits](BETA_RELEASE_PLAN.md#appendix-b--linux-qualification-record-2026-11-09). The source-host
onboarding test passed after explicitly deferring Voice, and keyboard traversal
and 200% zoom passed 2/2 with inspected screenshots. Real llama.cpp b12223 CPU
inference and slot lifecycle passed; fifteen native containment/resource tests
passed. Real ENOSPC on a 98.02%-full dedicated tmpfs retained the Apply journal
and restored every original after space returned. These are not clean-machine
or signed installed-candidate acceptance.

The RPM failure reproduced with FPM's level-9 multithreaded compressor; a
512 MiB controlled comparison passes with the newly selected level-6
single-threaded compressor. Accept AppImage, DEB and RPM together only after
the full wrapper and artifact checks succeed. Keep signed update/rollback,
packaged managed speech, all seven real-model journeys, full local-only
egress qualification and exact-commit release evidence open until measured.

**Local all-format follow-through:** Python 3.12 freeze and frozen smoke passed;
the complete wrapper now produced AppImage, DEB and RPM. All three SHA-256
checks pass, and RPM's header confirms `xz 6`; payload digests pass. These
unsigned `0.0.0` working-tree artifacts have no exact-commit provenance claim.
RPM's extracted frozen host/window checks and native Fedora installation are
separate from successful package creation. The corrected-source 1,805.76-second
trace retains a **not approved** verifier result and does not close MM-5; see
the [receipts](BETA_RELEASE_PLAN.md#artifact-and-audit-receipts).

**RPM payload checks:** extracted frozen-host smoke, restart and setup
persistence passed. Extracted-window onboarding passed; the independent
first-run window test crashed its renderer on its first attempt and passed an
isolated fresh-profile retry. This is Ubuntu payload evidence, not Fedora RPM
installation acceptance. Both attempts are retained in the run record.

FIXED-1375 prevents unconnected ChatGPT status reads from starting Codex App
Server. Candidate egress qualification must include that correction and a
fresh recording; earlier failed reports are not superseded by unit tests.

**Exact runtime qualification:** `8a053a90` passed CI, data-safety drills and
all llama.cpp engine/live jobs. The exact Release Plan script passed locally.
The signed non-published candidate dispatch was refused by GitHub (403,
Actions access), so signed candidate artifacts and generated release evidence
remain **BLOCKED**, not passed. The earlier desktop matrix on `91b07ce2` is
green on every target, including Windows-on-Arm emulation.
[Receipts and workflow links](BETA_RELEASE_PLAN.md#github-qualification-and-release-dispatch-access).

The full installed-shell capture also found Electron startup resolver traffic
that the host-only trace missed. FIXED-1376 disables automatic DoH and
non-loopback shell resource requests; 36 unit and 13 UI tests pass. Chromium's
non-sending IPv6 UDP route probe remains explicitly recorded. A fresh candidate
with this shell correction needs its own CI, package and egress evidence.
[Follow-through](BETA_RELEASE_PLAN.md#electron-network-process-follow-through).

### 2026-11-09 — Completed bounded installed-shell audit

The `6c211b60` installed unsigned Linux shell/host audit passes its predeclared
fresh-profile scope: 1,862 seconds of actual destination activity, 4,115
observations, no unexpected hosts. The 30-minute navigation driver completed
62 visits without failure; screenshot states were inspected. Chromium's 135
non-sending IPv6 UDP route probes and native control probes remain explicit
in the scope and receipts. Earlier failed captures remain failed.

**MM-5 remains partial:** no selected useful model, managed speech, enabled
external connector, owner-machine full-feature sign-off or signed-artifact
capture is inferred. All four qualification workflows for runtime `6c211b60`
are green; downloaded CI Linux artifact hashes and RPM digests verify.
[Evidence and limits](BETA_RELEASE_PLAN.md#completed-installed-shell-audit-and-ci-artifact-verification).

### 2026-11-09 — Signed candidate output verified

[Release 42650624663](https://github.com/sharRahul/Raiker/actions/runs/42650624663)
passed for exact runtime `6c211b60`, version `0.9.0`, beta channel,
`require-except-macos`, publication disabled. Independent checks passed for
all 10 installer hashes/Ed25519 manifests, six Linux GPG signatures, signed
channel/provenance, SBOM binding, repository lock hash and checksum files.
The product verifier and generated evidence inventory pass. The owner's
manual dispatch supplied the needed access; this candidate is no longer
blocked on candidate creation. Windows native checks passed in the workflow;
macOS retains its platform-signing exception.

This establishes CI-1/CI-5 candidate-output evidence, not beta sign-off.
Full Voice/licence/packaged-speech, seven real-model journeys, live connector
revocation/reconnect, full-feature signed-artifact egress and owner-machine
acceptance remain open. The reporting fix preserves that candidate's SHA; the subsequent owner-requested
Kokoro/Piper runtime change requires a new personal candidate.
[Artifact, signatures and receipts](BETA_RELEASE_PLAN.md#verified-non-published-signed-candidate).
