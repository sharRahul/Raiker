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

## Status — 2026-11-25

What is done and what is left, item by item. *Done* means shipped and tested;
*partly done* names the slice that shipped; the live journey on a published
build is still owed for every item (the regular-use journeys in
[TESTING.md](TESTING.md#regular-use-journeys)).

| Item | State | Done | Left |
|---|---|---|---|
| RU-01 Publish pre-releases | Open | — | Publish `0.9.0-beta.N` from green `main`; clean-machine installs |
| RU-02 Update in place | Open | — | Update channel, Roll back, data kept across both |
| RU-03 Windows sandbox without WSL2 | Partly done | WSL2 is used by itself when it is set up and the owner never chose ([FIXED-1563](FIXED_ITEMS.md#fixed-1563--windows-refused-every-command-until-the-owner-found-the-sandbox-setting)); commands, hooks and generated MCP servers run there on the distribution's `python3`/`node` ([FIXED-1560](FIXED_ITEMS.md#fixed-1560--with-wsl2-chosen-mcp-servers-and-hooks-still-had-no-boundary-on-windows)); a source checkout's Linux runner is documented in Troubleshooting | The restricted-account boundary stays refused until its four gaps close (per-account profile reset, explicit descendant ACLs, explicit allows below denied roots, loopback-port approximation); its setup in Raiker's first run |
| RU-04 Linux and macOS | Partly done | Linux Bubblewrap enforced (2026-11-16 journeys); Health, Settings and the posture gate name the distribution's Bubblewrap install command when it is missing ([FIXED-1570](FIXED_ITEMS.md#fixed-1570--linux-without-bubblewrap-was-reported-as-sandboxed)) | macOS account setup behind one prompt; the same Build turn on Ubuntu 24.04 and macOS 15 |
| RU-05 WSL2 and MXC options | Partly done | WSL2 is available and measured; MXC SDK 1.1.0's ProcessContainer passes eleven Windows probe observations ([evaluation](../architecture/NATIVE_SANDBOX_MIGRATION.md#windows-mxc-evaluation-2026-11-26)) | Production MXC adapter and lifecycle/resource-limit qualification before offering it |
| RU-06 Ten families | Done | Families, lines and the unit test ([FIXED-1537](FIXED_ITEMS.md#fixed-1537--permissions-was-grouped-in-six-headings-an-owner-had-to-learn)); live sweep of every family at 1440 and 390 px (RT-PERM-SWEEP-01, 2026-11-26) | — |
| RU-07 Three postures | Partly done | Per-conversation command grant on the approval card ([FIXED-1540](FIXED_ITEMS.md#fixed-1540--a-command-could-not-be-allowed-for-a-conversation-from-any-screen)); per-MCP-server *use without asking* ([FIXED-1562](FIXED_ITEMS.md#fixed-1562--a-trusted-mcp-server-could-only-be-used-by-allowing-every-server)); the three postures and their unit-tested mapping ([FIXED-1567](FIXED_ITEMS.md#fixed-1567--permissions-had-no-posture-only-sixty-rows-to-set-one-by-one)) | A Build journey in *Work in the sandbox* that asks only for `git push` |
| RU-08 Health | Partly done | `raiker doctor` with each fix ([FIXED-1552](FIXED_ITEMS.md#fixed-1552--there-was-no-raiker-doctor)); **This machine** on Observability → *Health, in detail* ([FIXED-1564](FIXED_ITEMS.md#fixed-1564--the-health-page-did-not-show-this-machines-readiness)); sandbox, backups, embedding, voice, updates and always-on facts with the page that fixes each ([FIXED-1566](FIXED_ITEMS.md#fixed-1566--health-did-not-say-what-first-run-had-left-unset)); model and disk-and-memory facts in the same list ([FIXED-1574](FIXED_ITEMS.md#fixed-1574--health-did-not-say-whether-a-model-answers-or-the-disk-is-filling)) | A fresh-machine pass showing exactly what first run fixes |
| RU-09 Four-step first run | Partly done | Model step says which models suit numbers and code ([FIXED-1538](FIXED_ITEMS.md#fixed-1538--first-run-did-not-say-which-models-suit-numbers-and-code)) ; *This machine* facts and the *Posture* choice ([FIXED-1571](FIXED_ITEMS.md#fixed-1571--first-run-set-up-the-device-but-not-the-machine-and-never-asked-for-a-posture)) | A timed first useful answer under ten minutes on Windows and Linux |
| RU-10 Keep or skip under the answer | Done | [FIXED-1539](FIXED_ITEMS.md#fixed-1539--a-memory-raiker-proposed-could-only-be-kept-from-memory), owner's words only ([FIXED-1548](FIXED_ITEMS.md#fixed-1548--a-sentence-the-model-invented-was-offered-to-keep-as-a-memory)); RT-1125-08 | — |
| RU-11 Memory as a summary | Done | Summary, inline Edit/Forget, Use memory, saved conversation Incognito and local meaning setup; real embedding and four chat-turn conditions pass ([FIXED-1584](FIXED_ITEMS.md#fixed-1584--conversation-incognito-was-missing-and-goal-noticing-ignored-memory-opt-out)) | None for RU-11; clean-machine timing remains RU-09 |
| RU-12 Remembers its own work | Done | Lessons from a project task's own command records, kept with Undo and recalled in that project unless its memory is disabled; the failing command's result carries the lesson ([FIXED-1585](FIXED_ITEMS.md#fixed-1585--raiker-did-not-remember-what-its-own-work-taught), [FIXED-1589](FIXED_ITEMS.md#fixed-1589--lessons-were-never-filed-or-recalled-in-a-real-project)); live three-task journey on Windows passes ([record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-28-ru-12-lessons-in-a-real-project)) | — |
| RU-13 Always-on host | Partly done | Detached desktop host and existing per-user startup; matching workspace/port registration, frozen launch command and honest Windows restart controls ([FIXED-1593](FIXED_ITEMS.md#fixed-1593--startup-registration-promised-a-restart-it-could-not-perform)) | Supervised Windows host, in-app setup, Linux lingering, service ownership and delivery/logout/reboot qualification |
| RU-14 Pause and Resume a running step | Open | — | Park a turn at the next safe boundary, freeze a command, resume |
| RU-15 Raiker as an MCP server | Done | `raiker mcp-serve`: seven read-only tools over stdio, each read governed and audited ([FIXED-1590](FIXED_ITEMS.md#fixed-1590--other-agents-could-not-reach-raikers-memory-notes-or-tasks)) | Writes over MCP need an approval channel the caller can wait on; not planned |
| RU-16 Import another agent's setup | Done | `AGENTS.md`/`CLAUDE.md`/`.cursorrules` ([FIXED-1536](FIXED_ITEMS.md#fixed-1536--a-projects-agentsmd-or-claudemd-was-ignored), [FIXED-1542](FIXED_ITEMS.md#fixed-1542--a-projects-cursorrules-was-ignored)), Hermes and Markdown memory ([FIXED-1541](FIXED_ITEMS.md#fixed-1541--another-agents-markdown-memory-could-not-be-imported)), Claude Desktop / Cursor `mcpServers` paste ([FIXED-1561](FIXED_ITEMS.md#fixed-1561--an-owner-could-not-add-a-local-mcp-server-and-none-could-drive-an-application)) ; the `.cursor/rules` folder ([FIXED-1569](FIXED_ITEMS.md#fixed-1569--a-projects-cursorrules-folder-was-ignored)); ChatGPT and Claude `conversations.json` ([FIXED-1572](FIXED_ITEMS.md#fixed-1572--chatgpt-and-claude-conversation-exports-could-not-be-imported)) | — |
| RU-17 Move to another machine | Done | Passphrase-sealed move file from Settings → Backups, opened by first run's *I have a backup*; re-keyed on arrival, provider keys asked for again ([FIXED-1597](FIXED_ITEMS.md#fixed-1597--raiker-could-not-be-moved-to-another-machine)); live two-host journey passes | — |
| RU-21 A project for Build has a folder | Done | Bare commands run in the project ([FIXED-1549](FIXED_ITEMS.md#fixed-1549--a-projects-command-with-no-folder-ran-at-the-workspace-root)); **Create project** makes `~/Raiker Projects/<name>` ([FIXED-1559](FIXED_ITEMS.md#fixed-1559--a-new-project-had-no-folder-outside-raikers-data)); RT-1125-11 | RU-J4 on a published build |
| RU-22 Build runs declared checks | Done | The runtime proposes each declared check the model did not run ([FIXED-1558](FIXED_ITEMS.md#fixed-1558--build-left-declared-checks-to-the-model)); the card says what verifies ([FIXED-1554](FIXED_ITEMS.md#fixed-1554--not-verified-did-not-say-how-to-verify)) | RU-J4 ending *Verified* live |

**Also done on 2026-11-25, outside the RU list:** MCP servers the owner adds run
as the owner, outside the command sandbox, as in Claude Code and Codex, so they
can drive applications on Windows too (FIXED-1561); a local Ollama is reached
through its own API with a context sized to the request (FIXED-1556); an
interpreter a toolchain manager installed in the home folder is reachable,
read-only, when it holds no credential (FIXED-1557).

**Still pending, beyond the open items above:** an MCP call cannot be asked about
mid-turn (it is allowed per server or held); Ollama Cloud models need the owner's
own quota; the published-build live journeys RU-J1 to RU-J5.

## What the reference agents do

**Lifecycle review, 2026-11-28:** checked the requested references again before
repairing the startup/restart boundary. [Claude's desktop documentation](https://code.claude.com/docs/en/desktop)
and [Cursor's Cloud Agents](https://cursor.com/docs/cloud-agent) distinguish
the client from where work runs. [ChatGPT scheduled tasks](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt)
and [Perplexity Computer](https://www.perplexity.ai/en-GB/hub/workshops/introducing-perplexity-computer)
document scheduled work; [Meta's own Muse page](https://ai.meta.com/muse/)
now provides a first-party background-work reference. [Hermes gateway internals](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-internals)
and its [setup source](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/gateway_setup_service.py)
explicitly distinguish a running gateway from an installed service. Raiker's
decision follows that distinction: a Startup file is not a supervisor, and
matching registration is not logout/reboot evidence. These references do not
substitute for Raiker's own containment and lifecycle tests.

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
*Progress 2026-11-25:* a project turn's command with no folder runs in the
project's copy, not the workspace root ([FIXED-1549](FIXED_ITEMS.md#fixed-1549--a-projects-command-with-no-folder-ran-at-the-workspace-root));
**Create project** now makes `~/Raiker Projects/<name>` and attaches it
([FIXED-1559](FIXED_ITEMS.md#fixed-1559--a-new-project-had-no-folder-outside-raikers-data)); the RU-J4 live run on the published build is open.

**RU-22 · Build runs the declared checks itself. P1, M.** When the model has
finished, Build runs the project's declared checks in the sandbox (asking like
any command) so the outcome is *Verified* or says what failed, whatever command
form the model chose.
*Done when* RU-J4 ends *Verified*.
*Progress 2026-11-25:* the outcome says what would verify it ([FIXED-1554](FIXED_ITEMS.md#fixed-1554--not-verified-did-not-say-how-to-verify)); Since FIXED-1558 Build runs the declared checks itself once the model has
finished; the RU-J4 live run is open.

### C. Permissions: strict, and easy to use

**RU-06 · Ten families in plain words. P1, M.** Group the 80 rows into ten
families an owner recognises — Files, Commands, Web, Messages and calendar,
Memory, Git and GitHub, Models, Money, Devices and home, Other agents and
plugins — each with one line on what it allows and its current setting. The
per-capability rows stay under each family.
*Done when* every capability belongs to exactly one family (unit test) and the
surface sweep passes.
*Progress 2026-11-25:* the families, their lines and the unit test shipped
([FIXED-1537](FIXED_ITEMS.md#fixed-1537--permissions-was-grouped-in-six-headings-an-owner-had-to-learn)); the live surface sweep is not re-run.

**RU-07 · Three postures. P1, M.** Permissions exposes **Default mode**:
**Ask first**, **Work in the sandbox** (edits and commands *inside the disposable
copy* run without a prompt; anything that leaves the copy, the machine, writes
durable memory, sends a message or spends money asks) and **Read-only**. Each
is a documented bundle of existing decision modes, changed through the same
step-up; customising one is said. The posture falls back to *Ask first* when
the sandbox probe is not fully enforced.
Show the per-conversation command grant on the command's approval card
(*Allow `python3 -m unittest` for this conversation*), so `run_command` is
reachable without the API. *Shipped 2026-11-25 ([FIXED-1540](FIXED_ITEMS.md#fixed-1540--a-command-could-not-be-allowed-for-a-conversation-from-any-screen)). The three postures
and their mapping shipped 2026-11-26 ([FIXED-1567](FIXED_ITEMS.md#fixed-1567--permissions-had-no-posture-only-sixty-rows-to-set-one-by-one)); the Build journey in
*Work in the sandbox* passed copied preparation and three declared tests on
2026-11-27; repository Apply/Git-push qualification remains open.*
*Done when* the posture → mode mapping is unit-tested and a Build journey in
**Work in the sandbox** asks only for `git push`.

**RU-08 · Health. P0, M.** One page (and `raiker doctor`) listing each
readiness fact with the page that fixes it: model, command sandbox, encryption
and backups, embedding model, voice, updates, disk and memory, always-on host.
*Done when* a fresh machine shows exactly what first run fixes, and nothing
after.
*Progress 2026-11-25:* `raiker doctor` prints first run's machine checks with
their fixes ([FIXED-1552](FIXED_ITEMS.md#fixed-1552--there-was-no-raiker-doctor));
Observability → *Health, in detail* opens on the same checks as **This
machine** ([FIXED-1564](FIXED_ITEMS.md#fixed-1564--the-health-page-did-not-show-this-machines-readiness)), and lists the command sandbox, backups,
embedding model, voice, updates and always-on host with the page that fixes
each ([FIXED-1566](FIXED_ITEMS.md#fixed-1566--health-did-not-say-what-first-run-had-left-unset)).

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
*Progress 2026-11-25:* Keep and Not this under the answer shipped
([FIXED-1539](FIXED_ITEMS.md#fixed-1539--a-memory-raiker-proposed-could-only-be-kept-from-memory)); the live journey is not re-run.

**RU-11 · One memory page that reads as a summary. P1, M.** Memory opens on
**What Raiker knows about you**: approved memories grouped by topic, each
editable and forgettable in place, with a count of suggestions waiting. One
switch (*Use memory*), Incognito for a conversation, and *Find by meaning
(stays on this computer)* as a single choice when the embedding model is local
(Provider embeddings scoped to the loopback profile only). Recall settings move
under Memory › Controls.
*Done when* the memory journeys pass with no visit to Permissions or Settings.
*Completed 2026-11-27:* summary, controls, local setup and saved conversation
Incognito ship. The real-host journey verifies edit/forget, refused authorization,
an unavailable endpoint, real Ollama indexing and paraphrase search. Four real
Qwen turns verify memory on, conversation Incognito, global memory off and
memory restored, with persisted recall disclosures and desktop/phone captures.
Goal suggestions also respect both opt-outs. No Permissions or Settings visit
is needed for the Memory journey; fixture model authorization is explicit
([live record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-27-memory-summary)).

**RU-12 · Raiker remembers its own work. P2, M.** After a task, Raiker may
propose a *lesson* ("`npm test` needs `--runInBand` in this repository"),
reviewed like any memory and recalled for the same project.
*Done when* a lesson kept on one task is recalled on the next in that project.
*Progress 2026-11-27:* the model records a lesson with `record_lesson`, and the
runtime files it only on this task's evidence (the failing command, then the
passing one, no file change between); a same-program variant is also caught
without the model. Lessons are kept without asking and shown with Undo; one
about a declared check asks, and Keep fixes the check. A failed command carries
the kept lesson about it, and a lesson whose command fails is archived as stale
([FIXED-1586](FIXED_ITEMS.md#fixed-1586--every-memory-waited-for-an-approval)).
The live two-task journey is pending.

**Decision 2026-11-27 — memory any tool can read, no integrations.** Raiker's
memory combines Obsidian's layer (linked Markdown with properties, wikilinks and
block ids, readable and editable by any tool) with Hindsight's (atomic facts,
entities, and recall by words, meaning, graph and time). It uses neither
product: the vault is plain files, and recall stays in Raiker's governed store.
Taken from Hermes Agent: scan memory writes for injection and invisible
characters, and keep memory bounded. Not taken yet:
- **Hindsight's rank fusion (RRF).** Raiker's weighted fusion is calibrated by
  the recall evaluation corpus, so switching means re-calibrating first.
- ~~**Hindsight's `reflect` and observation consolidation.**~~ (done without a model call, FIXED-1592)
- ~~**Hermes's frozen per-session memory snapshot**~~ (done, FIXED-1592), which keeps the prompt
  cache warm. A forget must still take effect immediately, so the snapshot
  would need invalidating whenever a memory changes.

**Decision 2026-11-27 — almost no memory approvals.** Raiker keeps the owner's
own words and evidence-backed lessons without asking and shows each with Undo,
as ChatGPT does; it still asks for the model's own sentences, personal
identifiers and check fixes, and **Ask before remembering** restores approval
for everything. This replaces "nothing is stored until Keep" for RU-10.

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
*Done 2026-11-28:* `raiker mcp-serve` ([FIXED-1590](FIXED_ITEMS.md#fixed-1590--other-agents-could-not-reach-raikers-memory-notes-or-tasks)).

**RU-16 · Import another agent's setup. P1, M.** Read `AGENTS.md`, `CLAUDE.md`
and `.cursor/rules` as RAIKER.md does — reviewed by digest before use — and
import memories and conversations from ChatGPT and Claude exports, and Hermes
Agent's `MEMORY.md`/`USER.md`, as suggestions to review.
*Progress 2026-11-25:* a project root's `AGENTS.md` or `CLAUDE.md` is read
when it has no `RAIKER.md` ([FIXED-1536](FIXED_ITEMS.md#fixed-1536--a-projects-agentsmd-or-claudemd-was-ignored)); Hermes Agent's `MEMORY.md`/`USER.md` and Markdown bullet lists import
through Memory's review ([FIXED-1541](FIXED_ITEMS.md#fixed-1541--another-agents-markdown-memory-could-not-be-imported)); `.cursor/rules` and the
ChatGPT and Claude exports are open.

**RU-17 · Move Raiker to another machine. P1, M.** An encrypted export of
workspace, settings and personas, imported by first run's *I have a backup*;
provider keys are asked for again.
*Done 2026-11-28* ([FIXED-1597](FIXED_ITEMS.md#fixed-1597--raiker-could-not-be-moved-to-another-machine)).

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

- **2026-11-28 (Open RU review)** — repaired startup identity, frozen launch
  commands and Windows restart reporting (FIXED-1593); early refusals no
  longer file phantom sessions (FIXED-1594); Memory names its tools permission
  without contradicting project lessons (FIXED-1595). The remaining native,
  first-run, always-on, Pause/Resume and migration work is retained explicitly
  in [Open defects](TO_BE_FIXED.md#open-ru-qualification--review-2026-11-28).

- **2026-11-28 (Notes handoff)** — the linked Markdown notebook is tested from
  the real browser: create/edit, properties, links/backlinks, rename/relink,
  conflict recovery, search, daily notes and trash. **Notes folder** names the
  shared notebook/memory control. Draft retention, graph refresh and shared UI
  tokens are corrected. See [FIXED-1588](FIXED_ITEMS.md#fixed-1588--the-notes-handoff-needed-safe-editing-tests-and-a-consistent-folder-control)
  and the [Notes plan](NOTES_PLAN.md) for the existing-screen delivery and
  separately planned graph/Canvas/Bases/agent-writing expansion. Low-approval
  memory policy is preserved. RU-12's live two-task qualification remains separate.

- **2026-11-27 (Memory vault)** — memory as linked Markdown any tool can read
  and edit (Obsidian layer), recall by time (Hindsight's fourth leg), and Hermes
  Agent's injection scan before anything is kept without asking (FIXED-1587).
- **2026-11-27 (Almost no approvals)** — Raiker keeps trusted memories itself
  with Undo; lessons are model-recorded on verified evidence, fix declared
  checks, come back when their command fails and retire when stale (FIXED-1586).
- **2026-11-28 (Lessons live)** — RU-12 done: on Windows with WSL2 and a
  local model, a failed-then-fixed command filed a lesson, the next task used
  it, and it was archived when the original command passed (FIXED-1591 found
  on the way).
- **2026-11-28 (MCP server)** — RU-15 done: `raiker mcp-serve` serves
  memory, notes, conversations, Library and tasks to other agents, read-only,
  through the broker and audit (FIXED-1590).
- **2026-11-27 (Lessons)** — RU-12 built: project lessons from Raiker's own
  command records, kept under the answer and recalled in that project only
  (FIXED-1585). The live two-task journey remains.
- **2026-11-27 (Memory summary)** — RU-11's landing summary, inline Edit/Forget,
  Use memory and local setup in Memory Controls shipped. Import preserves topics.
  RT-MEM-SUMMARY-01 passes on an isolated Windows host, including real Ollama
  semantic search, four real chat-turn conditions and saved conversation Incognito.
  RU-11 is complete; its two completed dedicated plans were removed.
  The six active workflows still match the repository files;
  the two historical workflows remain disabled. The parent plan retains open work.

- **2026-11-27** — Shared approval authorization and the Permissions/work-page
  refinement shipped ([FIXED-1578](FIXED_ITEMS.md#fixed-1578--preparation-and-approval-policy-disagreed-across-workflows),
  [FIXED-1580](FIXED_ITEMS.md#fixed-1580--permissions-repeated-policy-and-work-pages-exposed-routine-metadata)).
  Real WSL2 Build preparation/checks and real-account approval UI passed;
  the full Apply/push, native-account and clean-machine gates remain open.
  All triggered workflows passed for `82f0cf1d`. Earlier failed attempts below
  are historical evidence, not the current copied-write behavior.

- **2026-11-26 (real WSL2 Build)** — RU-07's live journey found a product
  blocker: the first proposed file write still asked despite the sandbox
  posture's Allow mapping. No approval was accepted. The failing criterion
  and broker/root-confinement work are recorded in
  [TO_BE_FIXED](TO_BE_FIXED.md#windows-build-posture--found-live-2026-11-26);
  no Build or Git push sign-off is claimed.

- **2026-11-26 (MXC evaluation)** — RU-05's missing Windows probe is recorded:
  the pinned SDK's native ProcessContainer passes all eleven observations,
  including protected descendants and an explicit ACL under a denied root.
  The reproducible evaluation does not enable a production backend
  ([FIXED-1577](FIXED_ITEMS.md#fixed-1577--the-mxc-assessment-had-no-current-windows-measurement)).

- **2026-11-26 (Windows review)** — The posture now requires measured
  enforcement ([FIXED-1575](FIXED_ITEMS.md#fixed-1575--the-sandbox-posture-trusted-installation-instead-of-enforcement)).
  WSL2's eight probe observations pass on the Windows development PC; the
  native account remains refused and its logon denials are absent. The six
  current workflows were retained; two stale GitHub records were disabled
  ([review](TESTING.md#github-workflow-review--2026-11-26)). RU-03, RU-05,
  RU-07 and RU-09 remain open as recorded in the
  [live report](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-26-windows-readiness-and-workflow-review).

- **2026-11-26 (later)** — RU-08's model and disk-and-memory facts shipped
  ([FIXED-1574](FIXED_ITEMS.md#fixed-1574--health-did-not-say-whether-a-model-answers-or-the-disk-is-filling)).
  RU-03's four runner gaps, RU-05's MXC probe and RU-07's WSL2 sign-off need
  the Windows test PC, and RU-09's timed run needs a clean machine; none were
  claimed from this Linux host.
- **2026-11-26** — RU-06 and RU-16 done; RU-07's three postures, RU-08's
  first-run facts on Health, RU-09's *This machine* and *Posture* steps and
  RU-04's Linux package line shipped. What is left is in
  [TO_BE_FIXED](TO_BE_FIXED.md#2026-11-26-round--found-not-fixed).
- **2026-11-25** — Status table added. RU-10, RU-21 and RU-22 done; RU-03,
  RU-07, RU-08 and RU-16 advanced; MCP servers the owner adds run as the owner.
- **2026-11-16** — Opened from the reference review. Rewritten the same day
  with the owner's direction: a native Windows sandbox without WSL2 (the
  restricted-account boundary, matching Codex's `elevated` design), strict but
  simple permissions, the memory verdict, an always-on host and a Pause that
  interrupts a running step.
