# First beta release plan

**Status:** active plan, opened 2026-11-02. **Owner:** release owner.
**Target:** Raiker `0.9.0-beta.1`, the first public beta, as soon as the gates in
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
[RELEASE_ACCEPTANCE_MATRIX.md](RELEASE_ACCEPTANCE_MATRIX.md). Native voice
conversation has its own specification:
[VOICE_CONVERSATION_SPEC.md](VOICE_CONVERSATION_SPEC.md).

## How to read this plan

| Mark | Meaning |
|---|---|
| ✅ | Done and evidenced (the evidence is named) |
| 🟡 | Implemented, evidence missing or partial on some platform |
| 🔴 | Not done; a release blocker for the scope it belongs to |
| ⚪ | Out of beta scope by decision; the product must refuse or hide it |

Priority: **P0** blocks `beta.1`; **P1** should land in `beta.1` but can slip
to `beta.2` with a known-issue entry; **P2** is after beta.

Effort: **S** under a day, **M** two to five days, **L** more than a week.

## The beta in one paragraph

`beta.1` is a **local, single-owner desktop app** on Windows 10/11 x64, macOS
12+ on Apple silicon and Linux x64/arm64. It offers Chat, Build, Models,
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
| 1 | Native sandbox & security | Ship limited — execution only where measured | Windows ACL gaps, macOS CI evidence, fail-closed audit |
| 2 | Desktop installation & updates | Ship | Signing identities, clean-machine first launch, signed update |
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
- macOS uses a Seatbelt profile plus a sandbox-account pool, but has **no
  hosted CI evidence**. `RLIMIT_AS` is not enforced by XNU, so the footprint
  supervisor replaces it.
- Plugins and local MCP stdio servers run in the native sandbox and are refused
  on hosts without an enforced boundary.
- Disposable per-session project copies with reviewed Apply are wired in.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| SB-1 | Windows isolation: ACLs, network, credentials, account cleanup | 🔴 | P0 | L | Per-task profile reset; deny network/remote logon rights; scan explicit ACEs under denied roots; scan explicit grants inside `.git`; measure the WFP filter on hosted and owner machines; account cleanup on uninstall |
| SB-2 | macOS Seatbelt enforcement, containment, limits | 🟡 | P0 | M | Native-runner checks passed on `macos-15` and `macos-15-intel` for `9c532624`. Preserve this evidence on the release commit and add fresh-installer, toolchain and adversarial tests. |
| SB-3 | Linux Bubblewrap and WSL2 enforcement | 🟡 | P0 | S | WSL2 was measured on Windows 11 and its static runner is packaged. Re-run on the release commit and document the systemd user-manager requirement for aggregate limits. |
| SB-4 | Commands, plugins, hooks and local MCP use the sandbox or fail closed | 🟡 | P0 | S | **Inventory test landed** (`tests/test_process_spawn_inventory.py`): every process-spawning module in `raiker/` is listed with a reviewed category (sandbox, Raiker-owned program, host lifecycle, read-only facts, owner-approved host operation); a new spawn site or any shell use fails CI. Remaining: one live check per hook type that a hook command is refused on a host without an enforced boundary |
| SB-5 | Disposable workspaces, reviewed promotion, rollback, crash recovery | 🟡 | P0 | M | **2026-11-08:** Undo Apply and a journalled Apply that a hard kill part-way rolls back on the next start ([FIXED-1332](FIXED_ITEMS.md#fixed-1332--an-apply-could-not-be-undone-and-a-crash-part-way-left-the-project-half-written-sb-5)). Still required: the pinned-handle link check (residual race documented today) |
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
setup verifies each component (RELEASE_ACCEPTANCE_MATRIX, run 39327713463: all
seven jobs green). No release has been published, signing secrets are not
configured, and runner publisher pins are empty (`runner_publisher.py`).

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| IN-1 | Working installers per supported OS | 🟡 | P0 | S | The current unsigned matrix passed, including `macos-15`; rerun the full signed candidate on the exact release commit. |
| IN-2 | Dependencies installed or guided | 🟡 | P0 | M | Bubblewrap/AppArmor on Linux: the setup check names the exact package command per distro and offers **Copy command**. WSL2 Ubuntu Base download from Settings with checksum. llama.cpp and the speech engines are installed by Raiker on demand (done for llama.cpp in PR #245; speech engines in the voice V1 change, with the catalogue pins listed under VD-1) |
| IN-3 | Signing and runner authenticity | 🟡 | P0 | M | **2026-11-07:** `signing: require-except-macos` signs Windows (self-signed beta certificate) and Linux (GPG), and every signed installer is checked against the identities pinned in `desktop/signing/identities.json`; signed candidate run [42430871211](https://github.com/sharRahul/Raiker/actions/runs/42430871211) passed on every target ([FIXED-1320](FIXED_ITEMS.md#fixed-1320--both-authenticode-readers-handed-powershell-a-path-it-throws-away-in-3-found-this-round), [FIXED-1321](FIXED_ITEMS.md#fixed-1321--windows-and-linux-builds-could-not-be-signed-without-an-apple-identity-and-nothing-checked-the-signer-in-3)). Still required: a CA-issued Authenticode certificate, then `WINDOWS_PUBLISHER_PINS` and `publisher_verified`; an Apple Developer ID for macOS (TO_BE_FIXED, *Windows builds are signed with a self-signed beta certificate*) |
| IN-4 | Upgrades, rollback, clean uninstall | 🟡 | P0 | M | Signed-channel update test (0.9.0-beta.1 → beta.2) per platform; a downgrade path that restores the previous app while the schema generation is unchanged (the store already refuses a newer schema — `store_schema_newer`); uninstall removes the sandbox accounts, WFP filter and runner grants on Windows |
| IN-5 | First launch on clean machines | 🔴 | P0 | M | Run T-01 on fresh VMs: Windows 10 22H2, Windows 11 24H2, macOS 14 and 15, Ubuntu 22.04/24.04, Fedora 40; record in RELEASE_ACCEPTANCE_MATRIX |

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
| MD-1 | Cloud and local provider connections | 🟡 | P0 | S | **2026-11-07:** providers outside the six are tagged *Experimental* in Models › Add ([FIXED-1315](FIXED_ITEMS.md#fixed-1315--the-betas-labels-and-limits-were-not-visible-where-the-owner-decides-beta-plan-1-2-3-6-8-9)). Anthropic, OpenRouter, OpenAI and Ollama (a cloud model) passed live through the UI ([run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-beta-release-plan-round)). The managed llama.cpp engine passed live on the owner's NVIDIA GPU ([RT-GPU-02](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-gpu-signing-and-settings-round)). Still required: LM Studio (the owner machine's install is broken; TO_BE_FIXED), and all six on the release commit |
| MD-2 | llama.cpp native install, deploy, GPU config | 🟡 | P0 | S | PR #246 repaired automatic source-only stable-release selection; the `llama-cpp.yml` live jobs passed on Windows, macOS and Linux. **2026-11-07:** NVIDIA passed on the owner's RTX 4080 SUPER: Raiker recommended and installed the CUDA build (b12192) and served a model entirely on the GPU ([run record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-gpu-signing-and-settings-round)). Still required: AMD (Vulkan), plus fresh signed-installer validation on the release candidate. |
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
| BD-5 | Diagnose failures, iterate, report | 🟡 | P1 | M | A scripted failing test that the agent must fix within three iterations; the report lists each attempt |

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
- BUG-354: the workspace key cannot be rotated in place.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| MM-1 | Encrypted storage and configuration | ✅ | — | — | `tests/test_sqlcipher_memory_security.py`, `tests/test_memory_sqlcipher.py` (CI) |
| MM-2 | Persist, retrieve, correct, delete | ✅ | — | — | T-04 scenario; memory governance tests |
| MM-3 | No credential or private-data leaks to models or logs | ✅ | — | — | `Data safety drills` now provides required automated transport/key/recovery regressions. **2026-11-08:** the canary drill runs in Data safety drills; it found the memory mirror holding secrets in plain text ([FIXED-1330](FIXED_ITEMS.md#fixed-1330--a-memorys-readable-mirror-held-passwords-and-card-numbers-in-plain-text-mm-3-found-by-the-drill)). See [data-safety evidence](DATA_SAFETY_EVIDENCE.md). |
| MM-4 | Backup, migration, corruption recovery | ✅ | — | — | Automated backup and lock-screen recovery checks are required in `Data safety drills`. **2026-11-08:** the destructive drill (truncate, flipped pages, missing key, full disk) runs in Data safety drills; it found a full disk answering a bare 500 ([FIXED-1329](FIXED_ITEMS.md#fixed-1329--a-full-disk-reached-the-owner-as-a-bare-500-mm-4-found-by-the-drill)) |
| MM-5 | No unexpected cloud transmission | 🟡 | P0 | M | `scripts/verify_egress_audit.py` rejects a capture shorter than 30 minutes or with an unapproved host. Still required: owner-machine local-profile recording while all features are used, then attach its redacted verifier report and capture hash. |
| MM-6 | Key rotation (BUG-354) | 🔴 | P2 | M | After beta; documented as a known limitation |

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
- The Quiet UI redesign is largely shipped (quiet-ui/README; FIXED-1150 and
  later). Open items are listed in TO_BE_FIXED (*Quiet UI round 2*,
  *approvals round*, *polish round*).
- Size budgets are measured (QUI-G01) but are still a report, not a gate.

| ID | Item | State | P | Effort | Work left |
|---|---|---|---|---|---|
| UX-1 | Quiet UI across retained pages | 🟡 | P0 | M | **2026-11-07:** QUI-G01 is a failing check (RT-BETA-10) for Chat, Build, Models, Settings › General, Privacy and About & updates, and Account and Backups. General's exception is gone: Account and Backups are sections of their own ([FIXED-1318](FIXED_ITEMS.md#fixed-1318--settings--general-was-over-its-size-budget-because-it-held-the-account-and-backups-ux-1)). Still required: close or move the open Quiet UI rows |
| UX-2 | Composer, navigation, model selection consistent | ✅ | — | — | Existing component coverage names the Chat and Build grammars; this round adds the shared five-state vocabulary and a live `RT-BETA-UX-01` route check. **2026-11-08:** the parity assertion found Build's order differing from Chat's; fixed, and checked in mocked e2e ([FIXED-1326](FIXED_ITEMS.md#fixed-1326--build-and-chat-ordered-the-shared-composer-controls-differently-ux-2)). |
| UX-3 | Permission controls, runtime status, approvals | ✅ | — | — | QUI-P01–P09 (approvals round) |
| UX-4 | Understandable errors and recovery actions | ✅ | — | — | Whole-route audit `tests/test_route_reason_copy.py`: every literal route refusal has copy, and `failure()` says why ([FIXED-1309](FIXED_ITEMS.md#fixed-1309--eighty-route-refusals-reached-the-owner-as-a-bare-machine-code-ux-4)) |
| UX-5 | Responsive layouts, accessibility, desktop usability | 🟡 | P0 | M | **2026-11-07:** RT-BETA-09 finds no serious or critical axe violation on any destination at 1440, 1280 and 390 ([FIXED-1317](FIXED_ITEMS.md#fixed-1317--settings-sections-were-off-the-card-system-and-the-activity-table-could-not-be-scrolled-by-keyboard-found-this-round-ux-5)). Still required: keyboard-only T-14; NVDA and VoiceOver passes |

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
| VD-1 | On-device dictation and read-aloud setup | 🟡 | P0 | L | **Implemented** (voice spec V1): verified catalogue (`raiker/config/voice-catalogue.json`), profiles with a hardware recommendation, shared `ResourceLedger` and placement planner, digest-verified installer run as a model operation, contained whisper-server and a token-protected speaking worker (Kokoro/Piper), idle and low-memory unload, Settings › Voice, the *Voice* first-run step, dictation and read-aloud on the managed engines. Kokoro speaking was installed, verified and run for real here (`tests/test_voice_live.py`). Still required: pin the Whisper models and Piper voices (`python -m scripts.pin_voice_catalogue --write` where Hugging Face is reachable; Piper voice licences reviewed), build Linux/macOS `whisper-server` in the release workflow, bundle `kokoro-onnx` once its espeak-ng (GPL-3.0) use is signed off, and run the §14 acceptance on all three OSes |
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
| PL-1 | Install, configure, remove supported integrations | 🟡 | P0 | M | A **supported list** for beta: GitHub, email (IMAP/SMTP), calendar (CalDAV), web search, local MCP stdio. Each gets one live install → use → revoke → remove run |
| PL-2 | Grants, revocation, audit | ✅ | — | — | Governance suite |
| PL-3 | OAuth and credential storage | 🟡 | P0 | S | Vault encryption and expiry checks are tested; a provider 401 marks the local credential `reauth_required` so it is not retried. Still required: expired-token and owner-revoked-token live checks for GitHub on the release candidate. Provider-specific OAuth revoke endpoints are not claimed until Raiker has registered clients. |
| PL-4 | Plugins and MCP cannot bypass the sandbox | 🟡 | P0 | S | Covered by SB-4/SB-6; add an MCP server that tries network, a home read and a spawn outside its folder |
| PL-5 | Supported vs experimental | 🟡 | P0 | S | Every connector has a `support_level` and is **Experimental** by default; the Add list shows the label and an experimental install asks once more (2026-11-07, FIXED-1315, RT-BETA-04). Still required: live evidence to promote the supported beta list; MCP has no catalogue to label (TO_BE_FIXED, *MCP servers have no catalogue to label*) |

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
| CI-3 | Per-platform artifacts verified independently | 🟡 | P0 | S | Each target downloads its own artifact in a fresh job and runs the installed-host smoke (exists); signed builds are now verified against the pinned identities before install and on the installed program (`raiker.app.platform_signatures`, FIXED-1321); signed candidate [42430871211](https://github.com/sharRahul/Raiker/actions/runs/42430871211) passed (Windows and Linux signed, macOS unsigned); still required: the run on the exact release commit |
| CI-4 | Dependency vulnerability and secret scans | ✅ | — | — | `pip-audit`/`npm audit` and `scan_secrets.py` in CI |
| CI-5 | Versioned, verified artifacts with reproducible evidence | 🟡 | P0 | M | The release carries `SHA256SUMS.txt` (exists), an SBOM (`licensing_check.py --sbom`), a provenance attestation (`actions/attest-build-provenance`) and a `RELEASE_EVIDENCE.md` linking the run IDs |

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

`beta.1` is published only when **every** item below is true on one commit,
and the release owner signs off in `RELEASE_EVIDENCE.md`.

1. **CI.** Every required workflow is green on the exact commit: `ci.yml`,
   `web` jobs, `desktop-package.yml`, `llama-cpp.yml` (engine and live),
   SAST, secrets and dependency audit.
2. **Sandbox.** On each platform, either the native sandbox probe reports
   every mandatory observation enforced and SB-6 passes, or command execution
   is refused on that platform and the beta guide says so.
3. **Installers.** IN-1 to IN-5 pass on clean machines. Builds are signed on
   macOS and Windows, or the beta guide states the build is unsigned and how to
   open it. *Unsigned is acceptable for a closed beta only.*
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
2. **Week 2 — voice V1 and data drills.** Managed whisper.cpp and Piper/Kokoro
   (VD-1). MM-3 canary, MM-4 corruption drill, MM-5 egress audit. Apply
   conflict refusal (BD-4).
3. **Week 3 — platforms.** macOS sandbox CI (SB-2), Windows gaps (SB-1),
   signing (IN-3), clean-machine runs (IN-5).
4. **Week 4 — the candidate.** The seven journeys with real models (E2E-1/2),
   the fault harness (E2E-3), reconciliation (DOC-1), sign-off.

Anything not green at the start of week 4 is moved to *Not in beta* with the
product refusing it, rather than delaying the date.

## Changelog

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
