# Ready to use — simplify Raiker for every machine

**Status:** active plan, opened 2026-11-16. **Owner:** release owner.
**Decision record:** [ADR-0006](../adr/ADR-0006-one-supported-path-per-machine.md).
**Target:** the owner can download Raiker on any of their machines, open it,
connect a model and get useful, safe work done the same day — without a
terminal, without reading the architecture, and without a capability being
silently unavailable.

Raiker is an **autonomous and secure personal AI agent**. The runtime that
makes it secure exists and is tested (governed actions, approvals, the native
sandbox, encrypted storage, audit). What stands between the owner and daily use
is not more capability; it is that the product is **not yet published**, that
**command execution is refused by default on Windows and macOS**, and that the
owner meets **too many decisions on the first day**. This plan removes those
three obstacles and nothing else. It does not reopen any security rule.

It sits beside, and narrows, the [first beta release plan](BETA_RELEASE_PLAN.md):
where the two disagree about *what the owner meets first*, this plan wins;
release gates and evidence stay in that plan and in
[RELEASE_ACCEPTANCE_MATRIX.md](RELEASE_ACCEPTANCE_MATRIX.md). Defects stay in
[TO_BE_FIXED.md](TO_BE_FIXED.md), closures in [FIXED_ITEMS.md](FIXED_ITEMS.md).

## How to read this plan

Each item has an ID (**RU-nn**), what is true **today** with its evidence, the
**change**, and the **done when** check that closes it. Priority **P0** blocks
"ready to use"; **P1** should land with it; **P2** follows. Effort **S** is
under a day, **M** two to five days, **L** more than a week.

## Where Raiker stands (2026-11-16)

| Fact | Evidence |
|---|---|
| No release has ever been published. Every installer is a CI artifact the owner has to find under **Actions**. | `gh release list` is empty; [Getting started](../guide/getting-started.md#install-the-desktop-app) |
| The installers exist for Windows x86-64/Arm (emulated), macOS Apple silicon, Linux x86-64/ARM64, and pass their package smoke tests. | [RELEASE_ACCEPTANCE_MATRIX.md](RELEASE_ACCEPTANCE_MATRIX.md), `desktop-package.yml` |
| Linux enforces the command sandbox (Bubblewrap + seccomp) on a stock install. | [Native sandbox migration](../architecture/NATIVE_SANDBOX_MIGRATION.md) |
| On Windows, the AppContainer boundary still fails the real `.git` ACL test, so execution is refused — **but the WSL2 boundary measured every observation enforced** on the owner's Windows 11 PC (2026-11-08). | [WSL2 re-measured](../architecture/NATIVE_SANDBOX_MIGRATION.md#wsl2-re-measured-on-the-beta-candidate-2026-11-08), [TO_BE_FIXED § native sandbox](TO_BE_FIXED.md#release-blocker-native-sandbox-migration-incomplete) |
| On macOS, a dedicated sandbox account under Seatbelt is implemented and passed macOS 15 CI; it needs one administrator setup step that only exists as a command (`sudo raiker-command-runner --setup-account`). | [macOS sandbox account](../architecture/NATIVE_SANDBOX_MIGRATION.md#macos-sandbox-account-2026-11-01-implemented-measured-on-macos-15-ci) |
| Permissions lists **80** rows over **70** capabilities; Settings has **16** sections. Every row is honest, and most owners will never need to read them. | `web/src/lib/capabilityModel.ts`, `web/src/lib/settingsSections.ts`, [Implementation status](../architecture/IMPLEMENTATION_STATUS.md) |
| Hosted models (Anthropic, OpenAI, OpenRouter), local Ollama models and search by meaning with the built-in `nomic-embed-text` pass live. | [Live record 2026-11-19](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-19-personas-local-ollama-search-by-meaning-and-native-decks) |
| Search by meaning works only after the owner turns on **Provider embeddings**, sets it to Always allow, and builds Memory's index — three steps nobody would find. | [TO_BE_FIXED § 2026-11-19](TO_BE_FIXED.md#2026-11-19-round--found-not-fixed) |

## What the reference agents do, and what Raiker takes from each

Read for shape and practice, not copied. Each row names what Raiker adopts and
what it deliberately does not.

| Reference | What it does well | Raiker adopts | Raiker does not adopt |
|---|---|---|---|
| **Claude Code** ([sandboxing](https://code.claude.com/docs/en/sandboxing), [sandbox environments](https://code.claude.com/docs/en/sandbox-environments)) | OS sandbox per platform: Seatbelt on macOS, Bubblewrap on Linux **and WSL2**; native Windows is not sandboxed and is pointed at WSL2. Permission modes decide *whether* a tool runs; the sandbox decides *what it can reach* once it runs, so sandboxed commands can run without a prompt. | WSL2 as Windows' command boundary (RU-03); "inside the sandbox, no prompt" as the everyday posture for commands (RU-07); a short, named set of postures instead of a per-capability first impression. | Running unsandboxed on native Windows. |
| **ChatGPT** (desktop and agent) | One download, sign in, start typing. Agent work runs in a separate virtual computer, and the user takes over for log-ins and payments. Memory is one switch plus a list you can edit. | First run ends in a working chat in minutes (RU-05); a turn that needs the owner says so and waits (already true of approvals); Memory's controls on one page (RU-10). | A provider-hosted account as the only way in; Raiker stays local-first and works with the owner's own keys and local models. |
| **Cursor** | Few modes (Agent / Ask / Manual), project rules in a file, an auto-run allowlist, and background agents in remote machines. | RAIKER.md already matches project rules; three postures (RU-07); remote execution stays an explicit option (SSH and Daytona already exist). | A global "run everything" switch. |
| **Perplexity** | Answer first, sources beside it; spaces that group research. | Already present (source chips, Library, projects); this plan only makes web access part of the first-day defaults where the owner chooses it (RU-06). | — |
| **Meta Muse** ([personal agent launch](https://thenextweb.com/news/meta-muse-personal-ai-agent-launch), [Muse Spark](https://engadget.com/ai/metas-muse-spark-model-brings-reasoning-capabilities-to-the-meta-ai-app-161456684.html)) | Consumer-grade simplicity: a named personal agent across apps and voice, tasks run in an isolated cloud machine, payments through a dedicated agent wallet. Coverage notes that trust is the barrier to handing over personal affairs. | Trust made visible: every action is said before it runs and recorded after; personas give the agent a name and voice (ADR-0005). | Holding the owner's card or paying on their behalf (Raiker's money rules stay: the owner approves and the provider's own page does it); cloud-only execution. |
| **Hermes Agent** (Nous Research, [docs](https://hermes-agent.nousresearch.com/docs/), [overview](https://parallel.ai/articles/what-is-hermes-agent)) | One-line install, a setup wizard, a `doctor` command, and a choice of terminal backends (local, Docker, SSH and hosted sandboxes) set by one config value; runs on a small always-on server and reaches the owner through chat apps. | A **Health check** that diagnoses and fixes in place (RU-04); the execution backend named and chosen in one place (RU-03); "Raiker on an always-on machine" as a documented later path (RU-14). | Docker as the default sandbox (Raiker removed Docker/Podman in favour of native boundaries; see the [sandbox migration](../architecture/NATIVE_SANDBOX_MIGRATION.md#docker-and-podman-removal)). |

## Principles

1. **One supported path per machine.** For each platform the owner meets one
   way to install, one command boundary and one update channel. Alternatives
   stay available under **Advanced**, never on the first screen.
2. **Safe by default, useful by default.** The defaults must already be able to
   do the everyday work (chat, research, files in a project, commands inside
   the sandbox) without a prompt for what cannot leave the boundary, and must
   ask for everything that can.
3. **Unavailable is said, with the fix.** A capability the machine cannot
   provide is shown with the one step that makes it available (or that it
   cannot be), never as a silent refusal on first use.
4. **Fewer decisions, not fewer safeguards.** Simplification removes choices
   from the first day; it never removes an approval, an audit record, an
   encryption step or a sandbox observation.
5. **Published or it does not exist.** The owner installs from a release page,
   with `SHA256SUMS.txt`, and gets updates from inside the app.

## The plan

### Milestone A — the owner can install and use it (P0)

**RU-01 · Publish rolling personal releases. P0, S.**
*Today:* `release.yml` exists and ran on 2026-11-15, but nothing is published.
*Change:* publish `0.9.0-beta.N` as a GitHub **pre-release** from `main` when
CI is green, one asset per platform plus `SHA256SUMS.txt`, unsigned under the
[personal beta scope](PERSONAL_BETA_SCOPE.md), with the unsigned-build steps
for Windows SmartScreen and macOS Gatekeeper on the release page.
*Done when:* `gh release list` shows a pre-release whose assets install on a
clean Windows 11, macOS 15 and Ubuntu 24.04 machine (IN-5 in the beta plan),
and Getting started links to it.

**RU-02 · In-app updates from that channel. P0, M.**
*Today:* the updater, manifest checks and pre-update backup are specified in
the beta plan (IN-4) and implemented for the desktop shell.
*Change:* point the default channel at the published pre-releases; **Settings ›
About & updates** shows the current and available version and **Update**.
*Done when:* an installed `beta.N` updates to `beta.N+1` in place, keeps its
data, and **Roll back** returns to `beta.N` (IN-4 evidence).

**RU-03 · Commands run on every desktop platform, in its sandbox. P0, L.**
*Today:* Linux enforced; Windows refused (AppContainer ACL gap); macOS needs a
command-line setup.
*Change (ADR-0006 §1):*
- **Windows:** the WSL2 boundary becomes the default command backend. **Raiker
  Setup** offers *Set up the command sandbox* (imports the `RaikerSandbox`
  distribution with systemd on, installs the packaged Linux runner, runs the
  probe). Linux toolchains (Node, Python, Git, Rust) run inside the
  distribution against the project copy. Windows-only toolchains (MSBuild,
  PowerShell scripts) are not reachable there, because the boundary denies WSL
  interop; the restricted-account and AppContainer backends that would run them
  stay under **Advanced** and stay refused until each passes its own probe.
- **macOS:** **Raiker Setup** runs the existing `--setup-account` step behind
  one administrator prompt, then the probe.
- **Linux:** no change; Setup states that Bubblewrap is present or names the
  package to install.
- Where the owner declines the setup, commands stay refused, and Build says so
  with the button that sets it up.
*Done when:* on a clean Windows 11, macOS 15 and Ubuntu 24.04 machine, the probe
reports every mandatory observation **enforced** after Setup, and a Build turn
runs `npm test` (or `pytest`) in a disposable copy and shows its output; the
beta plan's SB-1/SB-2/SB-6 rows are updated with that evidence.

**RU-04 · A Health check that fixes, not only reports. P0, M.**
*Today:* Diagnostics shows readiness facts; fixes live on other pages.
*Change:* one **Health** page (and `raiker doctor` from a terminal for the
same checks) listing, per row, *what works / what does not / the button that
fixes it*: model reachable, command sandbox, encryption and backups, embedding
model, voice runtime, updates, disk and memory headroom. Each fix routes
through the page that owns it, so no new authority path exists.
*Done when:* every row has a live check and a working fix route; a fresh
machine with nothing set up shows exactly the rows RU-05 will fix, and none
after it.

**RU-05 · A ten-minute first run that ends in a working chat. P0, M.**
*Today:* account → model setup → several optional screens; search by meaning
and commands need separate trips into Settings and Permissions.
*Change:* first run is **four** steps — *Account* (password, recovery codes),
*Model* (sign in to a provider with a key, or pick a local model Raiker finds
or installs), *This machine* (command sandbox from RU-03, the built-in
embedding model when Ollama is present, backups to a folder), *Posture*
(RU-07). Each step has a **Skip — do this later**, and Health lists what was
skipped. The workbench opens on a composer with three example requests that
work with what was set up.
*Done when:* a person who has never seen Raiker reaches a first answer in under
ten minutes on each platform (timed on three clean machines), and Health shows
nothing unexpected afterwards.

### Milestone B — fewer decisions every day (P1)

**RU-06 · Search by meaning without three hidden steps. P1, S.**
*Today:* needs Provider embeddings on, Always allow, and an index build.
*Change:* when the built-in model is local (`nomic-embed-text` on loopback
Ollama, or the managed llama.cpp entry once its hash is recorded), first run's
*This machine* step offers **Find things by meaning (stays on this computer)**;
accepting it turns on that one capability scoped to the **local** embedding
profile only, and the background indexer builds the space. A hosted embedding
model still asks exactly as today.
*Done when:* on a fresh workspace with Ollama, accepting the step and asking
Threads for *Japan holiday* finds a *Kyoto* chat with no visit to Permissions
(RT-1119-04 without its first two steps).

**RU-07 · Three postures in place of a first-day permission list. P1, M.**
*Today:* 80 permission rows, each with a decision mode; a fresh account starts
on the local baseline and Build is one decision.
*Change (ADR-0006 §2):* **Settings › Permissions** opens on three postures —
**Ask first** (today's baseline), **Work in the sandbox** (file edits and
commands inside the disposable copy run without a prompt; anything that leaves
the copy, the machine or spends money asks), **Read-only** (nothing changes
anywhere). A posture is a named bundle of the existing decision modes — no
new authority path, the same step-up to change it. The per-capability list
stays one click away as **Customise**, and a customised posture says so.
*Done when:* choosing a posture writes exactly the documented modes (unit
test over the mapping), every row stays reachable, and the live Build journey
passes in **Work in the sandbox** with no prompt for in-copy edits and a prompt
for `git push`.

**RU-08 · Settings in five groups. P1, M.**
*Today:* 16 sections.
*Change:* **You** (account, personalisation, personas, notifications, voice),
**Models**, **Permissions & privacy** (postures, privacy, web access,
execution profiles), **Data** (memory, backups, usage), **This machine**
(health, runtime, updates, advanced). Deep links keep working
(`#/settings?tab=…` maps to the new place).
*Done when:* every existing `tab=` link lands on its section; the surface sweep
(`surface-sweep-live.spec.ts`) passes; no setting is lost.

**RU-09 · One place for what is not ready. P1, S.**
*Today:* limits are spread across KNOWN_LIMITS, the beta guide and TO_BE_FIXED.
*Change:* Health's last section, **Not available on this machine**, lists each
refused capability with its reason code's owner copy and whether a fix exists;
the beta guide links to it.
*Done when:* every capability the runtime refuses on the host appears there,
and none that it allows.

**RU-10 · Memory on one page. P1, S.**
*Today:* Memory has five tabs and Settings › Memory engine holds the recall
backend.
*Change:* Memory opens on **What Raiker remembers** (search, edit, forget) with
**Suggestions** as a count; recall backend and indexing move under Memory ›
Controls; Settings links there.
*Done when:* the memory live specs pass against the new layout and no control
is lost.

### Milestone C — any machine, any time (P2)

**RU-11 · Small machines.** A *Light* profile chosen automatically below 8 GB
RAM: no local chat model offered by default, hosted or LAN model first, voice
Lite only, background indexing paced. *Done when:* the installed app is usable
on a 4 GB VM with a hosted model.

**RU-12 · Windows on Arm, natively.** Build the host for `windows-arm64` (today
it runs under emulation). *Done when:* the arm64 installer passes the package
smoke tests on an Arm runner.

**RU-13 · Portable data.** **Move Raiker to another machine**: an encrypted
export of workspace, settings and personas, imported by first run's *I have a
backup*. *Done when:* a workspace moved Windows → macOS keeps its
conversations, memory and personas, and asks for provider keys again (keys are
never exported in clear).

**RU-14 · Raiker on an always-on machine.** A documented, tested path to run
the host on a home server or small VPS and reach it from the owner's devices
through Remote access (two-step sign-in is already mandatory), with goals and
routines running while the laptop sleeps. *Done when:* RT-SEC-04 to RT-SEC-12
pass from a second device against a Linux server install.

## What gets simpler, and what does not change

| Simpler | Unchanged |
|---|---|
| One install per platform, from a release page, updated in place | Hashes verified; unsigned builds labelled as such |
| Commands work after one Setup step on every desktop OS | Commands never run outside a measured, enforced sandbox |
| Three postures on the first screen of Permissions | Every capability, decision mode, approval and audit record |
| Four first-run steps, each skippable | Account, encryption and recovery codes are not skippable |
| Search by meaning offered locally in one step | A hosted embedding model still asks first |
| Five Settings groups | Every setting; every deep link |

## Delivery order

1. **Week 1:** RU-01, RU-04 (checks first, fixes as they land), RU-06.
2. **Week 2:** RU-03 Windows (WSL2 default) and macOS (Setup step); RU-05.
3. **Week 3:** RU-02, RU-07, RU-09; clean-machine runs on three platforms.
4. **Week 4:** RU-08, RU-10; the seven beta journeys on the published build.
5. **After:** RU-11 to RU-14.

Anything P0 that is not green by week 3 is shown as *Not available on this
machine* (RU-09) with its fix, rather than delaying the release.

## Changelog

- **2026-11-16** — Opened. Reference review (Claude Code, ChatGPT, Cursor,
  Perplexity, Meta Muse, Hermes Agent); decisions recorded in
  [ADR-0006](../adr/ADR-0006-one-supported-path-per-machine.md).
