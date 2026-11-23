# Ready to use — Raiker on the owner's desktop, every day

**Status:** active plan, opened 2026-11-16, rewritten the same day with the
owner's direction. **Owner:** release owner.
**Decision record:** [ADR-0006](../adr/ADR-0006-one-supported-path-per-machine.md).
**Release gates and evidence:** [BETA_RELEASE_PLAN.md](BETA_RELEASE_PLAN.md).
**How it is tested:** [TESTING.md](TESTING.md).

Raiker is an **autonomous and secure personal AI agent**. The governed runtime
exists and is tested. This plan is the remaining work between that runtime and
the owner using Raiker every day on a **Windows or Linux desktop**, with macOS
supported and a phone app later. Every item keeps Raiker strict: no approval,
audit record, encryption step or sandbox observation is removed to make
something simpler.

## Owner direction (2026-11-16)

| Area | Direction |
|---|---|
| Coding agent | Commands must not be refused by default on Windows and macOS. |
| Command sandbox | One default per platform with its setup in Raiker: **Bubblewrap** on Linux, **Seatbelt** on macOS, and a **native Windows sandbox that does not need WSL2**. WSL2 stays an option, not a requirement. |
| Permissions and approvals | Keep them strict; make them easy to use. |
| Memory | Confirm whether Raiker is at par or ahead, and make memory easy to use. |
| Goals, tasks, schedules | Raiker can run as an **always-on host**, and **Pause interrupts a step that is already running**. |
| Devices | Windows and Linux desktops first; macOS supported; a phone app is a later plan. |

## Where Raiker stands (2026-11-16)

| Fact | Evidence |
|---|---|
| No release has been published; installers exist only as CI artifacts. | `gh release list` is empty; [Getting started](../guide/getting-started.md#install-the-desktop-app) |
| **Linux** enforces the command sandbox (Bubblewrap + seccomp) on a stock install. | [Native sandbox migration](../architecture/NATIVE_SANDBOX_MIGRATION.md) |
| **Windows already has a native sandbox without WSL2**: the restricted-account boundary (`RaikerSandbox` users, a Job Object, an outbound firewall rule and a WFP loopback filter). It measured every observation enforced on the owner's Windows 11 PC and ran Node, Git, MSYS and system Python. It is not on by default because its one-time setup needs an administrator and exists only as a command (`raiker-command-runner --setup-account`). | [Windows restricted-account sandbox](../architecture/WINDOWS_RESTRICTED_ACCOUNT_SANDBOX.md) |
| AppContainer, the older Windows boundary, fails a real `.git` ACL test and blocks ordinary toolchains. WSL2 measured enforced on 2026-11-08. | [TO_BE_FIXED § native sandbox](TO_BE_FIXED.md#release-blocker-native-sandbox-migration-incomplete) |
| **macOS** has a sandbox account under Seatbelt, passing macOS 15 CI, set up only from the command line with `sudo`. | [macOS sandbox account](../architecture/NATIVE_SANDBOX_MIGRATION.md#macos-sandbox-account-2026-11-01-implemented-measured-on-macos-15-ci) |
| Permissions lists 80 rows over 70 capabilities; Settings has 16 sections. | `web/src/lib/capabilityModel.ts`, `web/src/lib/settingsSections.ts` |
| Pause stops filing new goal steps; a running step finishes its turn. Stop interrupts at the next safe boundary but cannot resume. | [BUG-355](TO_BE_FIXED.md#bug-355--goals-ship-without-intake-from-chat-validator-backed-criteria-or-a-restart-scenario) |
| Goals and routines run only while Raiker is open; Restart from Settings needs `systemd --user` or `launchd`. | [Remote access](../architecture/REMOTE_ACCESS.md) |
| **Regular use on Linux (2026-11-16):** a first Build turn wrote code but could not run its tests — *Set up for Build* did not include commands, and `run_command`'s grant has no screen. Fixed for the preset (FIXED-1528); the grant remains (RU-07). | [Regular-use journeys](TESTING.md#regular-use-journeys), [TO_BE_FIXED](TO_BE_FIXED.md#2026-11-16-regular-use--found-not-fixed) |
| Hosted models, local Ollama models and search by meaning pass live; search by meaning needed three hidden steps. | [Live record 2026-11-19](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-19-personas-local-ollama-search-by-meaning-and-native-decks) |

## What the reference agents do

Reviewed 2026-11-16 from each product's own documentation where it is public,
and from its source where it is open. Claude, ChatGPT, Cursor, Perplexity and
Meta Muse are closed products, so only their documentation (and, for Meta
Muse, press coverage) can be read. **Hermes Agent** (MIT) and the **OpenAI
Codex** Windows sandbox (`openai/codex`, `codex-rs/windows-sandbox-rs`) are open
source and were read at source level.

| Reference | What was found | What Raiker takes |
|---|---|---|
| **Claude Code** — [sandboxing](https://code.claude.com/docs/en/sandboxing), [permissions](https://code.claude.com/docs/en/permissions), [memory](https://code.claude.com/docs/en/memory) | Seatbelt on macOS, Bubblewrap on Linux and WSL2; no native Windows sandbox. Six permission modes (`default`/Manual, `acceptEdits`, `plan`, `auto` with a classifier, `dontAsk`, `bypassPermissions`). Memory is `CLAUDE.md` (owner-written, and it reads `AGENTS.md`) plus **auto memory** Claude writes and the owner can open and edit. | Postures that separate *whether* a tool runs from *what it can reach* (RU-07); reading `AGENTS.md`/`CLAUDE.md` as reviewed instructions (RU-16); a readable, editable memory summary (RU-11). Not taken: a classifier as the authority, a bypass mode. |
| **OpenAI Codex (ChatGPT)** — [Windows sandbox docs](https://learn.chatgpt.com/docs/windows/windows-sandbox), [design post](https://openai.com/index/building-codex-windows-sandbox/), source | Native Windows sandbox, recommended over WSL2. Three modes: `mxc` (Windows' own process isolation, Windows 11 24H2+), `elevated` (dedicated lower-privilege sandbox users, filesystem boundaries and firewall rules, one administrator-approved setup) and `unelevated` (a restricted token derived from the user, ACL rules, weaker network isolation). | Raiker's restricted-account boundary **is** the `elevated` design; it becomes Windows' default with its setup in Raiker (RU-03). MXC is re-evaluated (RU-05). The `unelevated` design is not a default because it cannot contain the network. |
| **ChatGPT** — [memory help](https://help.openai.com/en/articles/8590148-memory-faq) | Memory updates itself and shows a readable, editable summary; it references past chats; one switch, Temporary Chat for none. | One memory page that reads as a summary, one switch, Incognito (RU-10, RU-11). |
| **Cursor** — [docs](https://docs.cursor.com/get-started/concepts) | A few agent modes, project rules in `.cursor/rules`, background agents with local-to-cloud hand-off; general memories were folded into rules. | Rules imported like RAIKER.md (RU-16); Raiker's always-on host is its background agent (RU-13). |
| **Perplexity** — [assistants with memory](https://www.perplexity.ai/en-GB/hub/blog/introducing-ai-assistants-with-memory), [scheduled tasks](https://testingcatalog.com/perplexity-adds-scheduled-tasks-feature-for-pro-and-enterprise-users) | Answers with sources; memory on/off with incognito; scheduled searches; "Brain" remembers the agent's own work (what failed, what was corrected). | Sources already ship. Memory of Raiker's own work is a P2 item (RU-12). |
| **Meta Muse** — [launch](https://thenextweb.com/news/meta-muse-personal-ai-agent-launch), [Muse Spark](https://engadget.com/ai/metas-muse-spark-model-brings-reasoning-capabilities-to-the-meta-ai-app-161456684.html) (press coverage; no first-party text was reachable) | A named personal agent that keeps working after the app closes, in an isolated cloud machine, paying through an agent wallet; coverage names trust as the barrier. | Always-on work on the owner's own machine (RU-13); every action said before and recorded after. Not taken: holding the owner's card. |
| **Hermes Agent** — [source](https://github.com/NousResearch/hermes-agent), [docs](https://hermes-agent.nousresearch.com/docs/) | Native Windows installer (PowerShell) as well as Linux/macOS; six terminal backends (local, Docker, SSH, Modal, Daytona, Vercel Sandbox); `hermes setup`, `hermes doctor`; an always-on gateway (Telegram, Discord, Slack, WhatsApp, Signal, email); memory in `MEMORY.md` and `USER.md` plus FTS5 session search; `AGENTS.md` for workspace instructions; `/stop` or a new message interrupts; `hermes import-agent` imports from Claude Code, Codex and Cursor. | Health with fixes (RU-08); the always-on host with chat-app reach (RU-13); importing another agent's instructions and memory (RU-16). Not taken: Docker as the default boundary. |

## The plan

Priority **P0** blocks "ready to use"; **P1** lands with it; **P2** follows.
Effort **S** < 1 day, **M** 2–5 days, **L** > 1 week.

### A. Install and update

**RU-01 · Publish personal pre-releases. P0, S.** Publish `0.9.0-beta.N` as a
GitHub pre-release from green `main`: one asset per platform and
`SHA256SUMS.txt`, unsigned under the [owner scope](BETA_RELEASE_PLAN.md#appendix-a--owner-scope-2026-11-09),
with the SmartScreen and Gatekeeper steps on the release page.
*Done when* a clean Windows 11 and Ubuntu 24.04 machine install from the
release page, and Getting started links to it.

**RU-02 · Update in place. P0, M.** The app updates from that channel, keeps
data, and **Roll back** returns to the previous build (IN-4).
*Done when* `beta.N` → `beta.N+1` → roll back keeps conversations, memory and
personas on both platforms.

### B. Commands run on every desktop, in a native sandbox

**RU-03 · Windows: the native restricted-account sandbox by default, no WSL2.
P0, M.** Raiker Setup's *This machine* step offers **Set up the command
sandbox**: one UAC prompt runs `--setup-account` (sandbox users and group,
`C:\RaikerSandbox`, the outbound firewall rule, the WFP loopback filter), then
the probe. Commands then run in a disposable copy as `RaikerSandbox`, with
Windows toolchains (Node, Git, Python, MSYS). Close the account's known gaps
before calling it the default: a per-task profile reset, logon-right denials
(network and remote) and the explicit-ACE scan under denied drive roots
([TO_BE_FIXED](TO_BE_FIXED.md#release-blocker-native-sandbox-migration-incomplete)).
AppContainer is retired as an execution boundary. Declining setup leaves
commands refused, said with the button that sets it up.
*Done when* on a clean Windows 11 PC, after one UAC prompt, the probe reports
every mandatory observation enforced, and a Build turn runs `npm test` and
`pytest` in a copy and shows their output.

**RU-04 · Linux and macOS. Linux P0 S, macOS P1 M.** Linux: Setup confirms
Bubblewrap (or names the package). macOS: Setup runs the sandbox-account setup
behind one administrator prompt, then the probe.
*Done when* the same Build turn passes on Ubuntu 24.04 and macOS 15.

**RU-05 · WSL2 and MXC as options. P2, M.** WSL2 stays available under
**Advanced** for Linux toolchains on Windows. Re-evaluate Microsoft's MXC with
Raiker's probe: Codex now recommends MXC on Windows 11 24H2+, which supersedes
the 2026-10-30 note that no source tied Codex to it
([MXC evaluation](../architecture/NATIVE_SANDBOX_MIGRATION.md#windows-mxc-evaluation-2026-10-30)).
*Done when* MXC's probe result is recorded; it is offered only if every
mandatory observation is enforced.

**RU-21 · A project for Build has a folder. P0, S.** Creating a project from
Build or Projects asks for its folder (or makes one under `~/Raiker Projects`);
Build never works in Raiker's own data folder.
*Done when* RU-J4 applies its change to the project folder with **Apply to
project**.

**RU-22 · Build runs the declared checks itself. P1, M.** When the model has
finished, Build runs the project's declared checks in the sandbox (asking like
any command) so the outcome is *Verified* or says what failed, whatever command
form the model chose.
*Done when* RU-J4 ends *Verified*.

### C. Permissions: strict, and easy to use

**RU-06 · Ten families in plain words. P1, M.** Group the 80 rows into ten
families an owner recognises — Files, Commands, Web, Messages and calendar,
Memory, Git and GitHub, Models, Money, Devices and home, Other agents and
plugins — each with one line on what it allows and its current setting. The
per-capability rows stay under each family.
*Done when* every capability belongs to exactly one family (unit test) and the
surface sweep passes.

**RU-07 · Three postures. P1, M.** Permissions opens on **Ask first** (today's
baseline), **Work in the sandbox** (edits and commands *inside the disposable
copy* run without a prompt; anything that leaves the copy, the machine, writes
durable memory, sends a message or spends money asks) and **Read-only**. Each
is a documented bundle of existing decision modes, changed through the same
step-up; customising one is said. The posture falls back to *Ask first* when
the sandbox probe is not fully enforced.
Show the per-conversation command grant on the command's approval card
(*Allow `python3 -m unittest` for this conversation*), so `run_command` is
reachable without the API.
*Done when* the posture → mode mapping is unit-tested and a Build journey in
**Work in the sandbox** asks only for `git push`.

**RU-08 · Health. P0, M.** One page (and `raiker doctor`) listing each
readiness fact with the page that fixes it: model, command sandbox, encryption
and backups, embedding model, voice, updates, disk and memory, always-on host.
*Done when* a fresh machine shows exactly what first run fixes, and nothing
after.

**RU-09 · Four-step first run. P0, M.** *Account* → *Model* → *This machine*
(command sandbox, local embedding model, backups, always-on) → *Posture*.
Each but *Account* can be skipped and is listed on Health.
*Done when* a first-time user reaches a first useful answer in under ten
minutes on Windows and Linux.

### D. Memory: ahead on control, behind on ease

**Verdict (2026-11-16).** Raiker is **ahead** of the references on control:
every memory has provenance, scope, retention and a review step; recall is
local by default (`nomic-embed-text`), Incognito withholds everything, and
forgetting is the owner's alone. It is **at par** on recall breadth: approved
memories, search of past conversations by words and by meaning (FTS5 and
embeddings, as in Hermes Agent and ChatGPT's chat-history reference), the
Library and RAIKER.md. It is **behind** on ease: proposals need a visit to
Memory, there is no readable summary (ChatGPT, Claude auto memory), five tabs
plus a Settings section, three hidden steps for search by meaning, and it does
not read `AGENTS.md`/`CLAUDE.md`. It also does not remember its own work
(Perplexity Brain, Hermes Agent's self-written skills).

**RU-10 · Keep or skip, where the answer is. P1, S.** A memory Raiker proposes
appears under the answer as *Remember: "…"* with **Keep** and **Not this**;
nothing is stored until Keep, exactly as today, but without leaving the
conversation. Batch review stays in Memory.
*Done when* a proposal is kept from Chat and appears in Memory with its
provenance.

**RU-11 · One memory page that reads as a summary. P1, M.** Memory opens on
**What Raiker knows about you**: approved memories grouped by topic, each
editable and forgettable in place, with a count of suggestions waiting. One
switch (*Use memory*), Incognito for a conversation, and *Find by meaning
(stays on this computer)* as a single choice when the embedding model is local
(Provider embeddings scoped to the loopback profile only). Recall settings move
under Memory › Controls.
*Done when* the memory journeys pass with no visit to Permissions or Settings.

**RU-12 · Raiker remembers its own work. P2, M.** After a task, Raiker may
propose a *lesson* ("`npm test` needs `--runInBand` in this repository"),
reviewed like any memory and recalled for the same project.
*Done when* a lesson kept on one task is recalled on the next in that project.

### E. Always on, and a Pause that really pauses

**RU-13 · Raiker as an always-on host. P0, L.** The host runs without the
window: a **Keep Raiker running** choice registers it as a user service
(`systemd --user` with lingering on Linux; a per-user logon task or Windows
service on Windows; `launchd` on macOS), and the desktop app becomes a client
of the running host (local, or a home server or small VPS reached through
Remote access with its mandatory two-step sign-in). Goals, routines and
background runs continue when the window is closed; results reach the owner
through notifications and paired channels (Signal, Telegram). Restart from
Settings works on every platform once registered.
*Done when* on Windows and Linux a routine scheduled for five minutes later
runs with the window closed, its result is delivered, and the host survives a
log-out and a reboot.

**RU-14 · Pause interrupts a running step and Resume continues it. P0, L.**
Pause takes effect at the running step's **next safe boundary**: before the
next model call, between tool calls, and — for a running command — by freezing
its process tree (`cgroup.freeze` on Linux, the Job Object's processes on
Windows, `SIGSTOP` to the sandbox account's processes on macOS). The turn is
parked in the suspended-turn store the approval path already uses
(`insert_suspended_turn`), with its messages, pending calls, spend and
persona; **Resume** re-enters the same turn. A command frozen longer than a
limit (default 30 minutes) is stopped and reported, never left holding the
sandbox; a pause never skips an approval, and a resumed turn re-checks
permissions, profile and budget before its next action.
*Done when* a goal step running a two-minute command is paused, stays frozen
with no further output, and on Resume finishes with the same result as
uninterrupted; and a Chat turn paused between tool calls resumes with its
history intact (the last row of BUG-355).

### F. Interoperability

**RU-15 · Raiker as an MCP server. P2, M.** Other agents (Claude, ChatGPT,
Cursor, Hermes Agent) can call Raiker's memory search, Library and tasks over
MCP; every call enters the same gateway, approvals and audit.

**RU-16 · Import another agent's setup. P1, M.** Read `AGENTS.md`, `CLAUDE.md`
and `.cursor/rules` as RAIKER.md does — reviewed by digest before use — and
import memories and conversations from ChatGPT and Claude exports, and Hermes
Agent's `MEMORY.md`/`USER.md`, as suggestions to review.

**RU-17 · Move Raiker to another machine. P1, M.** An encrypted export of
workspace, settings and personas, imported by first run's *I have a backup*;
provider keys are asked for again.

### G. Later

* **RU-18 · Phone app.** A client of the always-on host (RU-13); the PWA first.
* **RU-19 · Small machines.** A *Light* profile below 8 GB of memory.
* **RU-20 · Windows on Arm, native.**

## Delivery order

1. **Week 1:** RU-01, RU-08, RU-03 (setup in Raiker; account gaps closed).
2. **Week 2:** RU-09, RU-04 (Linux), RU-10, RU-11.
3. **Week 3:** RU-14 (Pause), RU-02, RU-07, RU-06.
4. **Week 4:** RU-13 (always-on), RU-16, RU-17; the regular-use journeys in
   [TESTING.md](TESTING.md#regular-use-journeys) on the published build.
5. **After:** RU-04 (macOS), RU-05, RU-12, RU-15, RU-18 to RU-20.

A P0 item that is not green by week 3 is shown on Health as *Not available on
this machine*, with its fix, rather than delaying the release.

The [regular-use journeys](TESTING.md#regular-use-journeys) record the testing
coverage and live runs. RU-J4 checks the declared test result for both Build
turns, and RU-J5 checks the approved facts in Memory before recall in a new
chat. Release qualification still requires a live run on the published build.

## Changelog

- **2026-11-16** — Opened from the reference review. Rewritten the same day
  with the owner's direction: a native Windows sandbox without WSL2 (the
  restricted-account boundary, matching Codex's `elevated` design), strict but
  simple permissions, the memory verdict, an always-on host and a Pause that
  interrupts a running step.
