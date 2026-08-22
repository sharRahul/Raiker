# Raiker

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is a local-first AI-agent runtime. Every model interaction and tool
action passes through policy, capability gates, approvals, and audit records, so
local automation stays under your control.

The launchable local UIs are the plain local terminal client and the local web dashboard — `raiker` and `raiker-app` (or `raiker-web` for explicit service control), the latter on `127.0.0.1`; Phase 8 deferred clients are not available. Approving a proposed file change performs it once, under a fresh gate, policy and posture check, with the previous contents checkpointed. Approved local `shell`, SSH and Daytona actions likewise execute once through their dedicated governed executors; other approvals remain decision-only. Durable memory mutation is broker-governed, and a turn can now propose one from Chat and Build as well as from the terminal client — you see the exact text and decide, and approving really stores or removes the record. Strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

## Quick start

Python 3.11+, Node 20+, Git.

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
. .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

npm --prefix apps/web ci
npm --prefix apps/web run build

raiker-app                              # detects your OS and opens your browser
```

## `raiker-app` command

`raiker-app` is the application entry point. It keeps its data where your
platform expects an application to (`%LOCALAPPDATA%\Raiker` on Windows,
`~/Library/Application Support/Raiker` on macOS, `$XDG_DATA_HOME/raiker` on
Linux — `RAIKER_HOME` overrides all three), binds a free loopback port, and
opens your default browser. If a Raiker is already running it opens that one
rather than starting a second host over the same encrypted workspace. Run
`raiker-app --print-paths` to see what it resolved.

Installation and PowerShell command-not-found help are in
[Getting started](docs/guide/getting-started.md#install).

Subcommands cover the rest of the host's life. Bare `raiker-app` still means
"start Raiker", so a desktop shortcut is unaffected:

```bash
raiker-app service install    # start in the background at sign-in, using your
                              # platform's own service manager: launchd on
                              # macOS, systemd --user on Linux, the Startup
                              # folder on Windows
raiker-app service status     # show whether background startup is registered
raiker-app service uninstall  # remove background startup registration
raiker-app status             # running / paused / needs attention / stopped,
                              # and what background work is in flight
raiker-app pause              # stop starting new background work; already
                              # approved work is allowed to finish
raiker-app resume             # resume scheduled background work
raiker-app quit               # stop the host, reporting waiting work first
raiker-app uninstall          # print exactly what removal takes and what it
                              # keeps; add --yes to carry it out, and
                              # --data keep|export|erase per instance
raiker-app update             # what this build is: signed release, unsigned
                              # build, or source checkout. Add --check to ask
                              # the pinned channel, --apply to install what it
                              # offers, --rollback VERSION to go back
```

To keep project-local data in the repository workspace instead of the default
platform data directory, pass `--workspace` consistently. Options work before
or after the subcommand:

```powershell
raiker-app --workspace .
raiker-app --workspace . service install
raiker-app service status --workspace .
```

The same controls are in the app: the **Host** control in the top bar reports
the state, names what a quit would interrupt, offers Pause, Restart and Quit,
and — under **Install & updates** — says what this build is and whether an
update channel is pinned. Opening it makes no outbound request; Raiker contacts
no update service until you pin one.

Releases are built by `.github/workflows/release.yml`, started deliberately from
the Actions tab. It builds a reproducible payload per platform on that
platform's own runner, proves it rebuilds to the same bytes, runs an
encrypted-database packaging test there, builds that platform's installer, and
signs the channel index the updater verifies. **It refuses to build without
code-signing identities** rather than producing something that looks like a
release; run it with `signing: skip` to exercise the pipeline and you get
artifacts named `-unsigned` that the product itself calls unsigned and that the
publish job will not release. No signed artifact has been published yet.

The desktop payload is self-contained: it bundles the API, built dashboard and
native tray integration. On first run, a five-stage wizard creates the local
owner, connects or defers a model, explains the selected privacy posture,
creates and verifies an optional encrypted backup, and opens the workspace.
The tray then provides Open Raiker, Pause/Resume, Restart and Quit through the
same governed host routes as the web control. See
[`docs/DESKTOP_DISTRIBUTION_DESIGN.md`](docs/DESKTOP_DISTRIBUTION_DESIGN.md).

`raiker-web` remains the service entry point for an explicit workspace and port,
and is the only path that can bind beyond loopback (`--allow-public`, which also
requires a hardened owner token):

```bash
raiker-web --workspace . --no-browser   # then open http://127.0.0.1:8765
```

First run uses **owner bootstrap** to create your local **owner principal** — a
username and password held on this machine. There is no cloud account. Every
request thereafter resolves an **acting-principal**.

> **Model setup is part of first run.** A fresh workspace opens the setup flow.
> The Ollama default is only a preference until its exact endpoint and model
> pass readiness; every model-backed action stays disabled meanwhile and links
> to **Models** instead of sending a turn that cannot run.

To connect a hosted model, open **Models**, press **Connect** on the provider,
and paste your API key. Use **Disconnect** on that provider to remove its vault
credential. That is the whole flow — see
[Connecting a model](docs/guide/connecting-a-model.md).

## Owner-authoritative and monitored

Raiker is **owner-authoritative and monitored, not prevention-by-restriction**.
Security here is not restricting you; it is letting you operate without having
your own access taken away.

**Configuring something is permission for it.** Saving a provider's credential
is the authorization to use that provider, and the endpoint you configured is
authorised with it. You are not then asked to satisfy a separate switch, a
separate host allowlist, and a separate encryption key before the thing you just
set up will run.

That consent is scoped and revocable, never a blanket opening: configuring
Anthropic authorises `api.anthropic.com` and nothing else, a provider you have
not configured still fails closed, and a capability you *explicitly* turn off
stays off whatever is configured.

Controls that stand between an AI-proposed action and it happening:

| Control | Where | What it decides |
|---|---|---|
| **Agent runtime** | Settings → Runtime configuration | Whether Raiker accepts new executions at all |
| **Capability gate** | Permissions | Whether this capability exists for you at all |
| **Decision mode** | Permissions, or the Chat and Build composers | Ask / Allow / Auto / Deny before each action |
| **Approval** | Approvals | A human decision on the specific proposed action |

Opening a higher-risk gate is a governed step-up: a human `runtime_gate_manager`,
a reason, a short phrase they type to record their intent, and a threat-model
acknowledgement — all recorded against your principal. The phrase is not a
credential. Owner **recovery** is governed and audited.

A human `runtime_gate_manager` alone may change capability gates or stop the
agent runtime.

There is one runtime. Raiker used to ship five modes — a development preview,
two single-user modes, a multi-user mode and a hosted mode — and require one to
be selected before a capability could reach runtime level. That was a second
switch in front of the switches that decide anything: what an action may do is
already settled by its capability gate, its threat-model acknowledgement, its
human confirmation, and whether a real executor exists for it. The single
runtime does all of it, and the only runtime-level decision left is binary —
accepting executions, or stopped.

The approval detail says what will happen **before** you decide. A proposed
**file change** is performed once, through the governed
approval execution relay — re-governed at execution time, with the previous
contents checkpointed so it can be rewound, and never into `.raiker/` or
`.git/`. Approved **SSH remote** and **Daytona cloud** actions execute once
through bounded, owner-selected profiles with fresh policy, posture, credential,
host-key, and cost-ceiling checks, and an approved local **shell** command runs
once against an allowlist, inside the workspace, under a timeout and an output
bound, with secret-like output redacted before it is recorded. Network and
process approvals record the decision and execute nothing. Disabling either the
`approval_execution_relay` or
`file_write_execution` capability returns file approvals to record-only, and a
critical approval always uses the human-only, step-up-verified lifecycle
instead.

Deferred dangerous domains — finance, medical, CCTV, home security, and hardware actions — have no governed executor
and therefore offer no enable path at all. They fail closed and are listed under
Observability → Diagnostics.

Raiker stays frictionless for safe local work: you remain in control, while
zero-trust verification is applied at every authority boundary.

## What is in the dashboard

| Group | Destinations |
|---|---|
| Home | **Workbench** — the live board: what is running, which agents are standing, what is scheduled, and what needs a decision |
| Work | **Chat**, **Build**, **Search Chat**, **Tasks**, **Projects** |
| Knowledge | **Memory**, **Knowledge Map** |
| Control | **Approvals**, **Permissions**, **Models**, **Extensions** |
| Observe | **Observability** — readiness, audit log, checkpoints, live work, notifications, sessions |
| Utilities | **Settings** — including **Web access** and **Git credential** |

Highlights, each verified against a live instance:

- **Chat** — streamed turns against local or hosted models, image and document
  attachments, sanitised Markdown rendering, source citations, a recent-chat
  list with per-row delete and move-to-project, indexed full-text search across
  titles and message bodies that shows the exchange each result matched on, and
  one-click export of a conversation to HTML, Markdown or PDF; at 90% of a known
  context capacity, older completed exchanges are compacted automatically while
  the transcript remains unchanged.
- **What a turn did, and what it thought** — every tool call gets one line above
  the answer, in the order the model asked: an icon for the family, the tool in
  plain words, and what it acted on. A call still running says so, one waiting on
  your decision says so beside the card that resolves it, and one refused says
  why with a link to the page that would let it through. The phrase is resolved
  on the server under the same redaction the audit record passes — a fetch is
  named by its host and a command by its program — so a line can never say more
  than the log does. Where the model can think before answering, the composer's
  **Thinking** control turns it on and its own reasoning fills a collapsed block
  above the answer, closing when the answer starts. A turn that produced no
  reasoning shows no block at all. Whether that working is **kept** is your
  decision — off unless you turn it on in Settings → Privacy, because it can
  restate anything your prompt contained. Kept working never enters chat search
  and never leaves in an export; when it is not kept, a re-opened turn says so
  rather than reading as a turn that never thought.
- **Two composers, each shaped for its own work** — Chat's is the short one: a
  prompt, what to attach, who to ask, and how much to approve. Build's is the
  coding agent's: the same, plus the **Plan / Edit / Auto** mode it enforces and
  the boundary its commands run in. Neither offers a way into the other, because
  the sidebar already does that, and neither repeats a fact the control beside it
  already reports. `/` opens the commands each surface really has (Chat has
  `/export`, `/schedule` and `/tasks`; Build has `/plan-mode`, `/edit-mode`,
  `/auto-mode`, `/terminal` and `/repos`), `@` completes a path out of the code
  map you built, the prompt box grows with what you write, and `/shortcuts` shows
  the keyboard map. Your own messages carry **Copy**, **Edit** and **Retry** — and an edit
  adds a new turn rather than rewriting what you asked, because the transcript is
  a record. No command grants anything: each one opens a control you already have.
- **Recall** — a turn can read your own past conversations, not only the ones it
  can still see. `conversation_search` searches every exchange you have had,
  narrowed to a date range when the question is about a particular period, and
  returns the matching exchange with its conversation, timestamp and turn id so
  an answer can cite the record instead of reconstructing it. Ambient recall
  offers the conversations that match this prompt rather than the eight most
  recent ones. What it returns is your own transcript, treated as data rather
  than as instruction; **Incognito** switches the whole path off.
- **A reference graph over your own citations** — every source a turn used is
  recorded with the text it contributed, and that record reads both ways. A turn
  can ask which of your conversations cited a file, what was cited alongside it,
  and what the file said *at the time* it was read — without re-opening
  anything. A citation whose file has since been deleted is reported as missing
  rather than dropped, and drawn on the Knowledge Map as a hollow node, because
  work grounded in something gone is a different thing from work grounded in
  nothing.
- **Tasks** — four work types: run now, schedule once, daily routine, and a
  persistent background agent; nestable, prioritised, and stoppable at a safe
  boundary.
- **Models** — local, home-lab, hosted, and advanced providers; live provider
  catalogues; an encrypted per-instance credential vault; a user-owned fallback
  sequence with no silent hosted fallback; first-run setup; approved-root GGUF
  discovery; managed llama.cpp; revision-pinned Hugging Face downloads;
  per-provider token and API-cost accounting with each figure's source named;
  and connected-provider rolling seven-day tokens, turns, requests,
  compactions, known cost, genuine provider data where available, and advisory
  owner budgets.
- **Web access** — Raiker can read public pages and search the web out of the
  box. Settings → Web access holds your blocklist (domains, wildcards, IPs,
  ranges, patterns) and a check that answers "would this be reachable" without
  contacting anything. Private and loopback destinations are refused always,
  and a fetched page arrives as sanitised text with what was removed reported.
- **Git credential** — the token Raiker pushes with, stored encrypted and lent
  to one command at a time under an approval you make once or for a session.
  It never appears in a log, an error, or a command's output.
- **Extensions** — governed service connectors and Model Context Protocol
  servers you can build, connect, monitor, and contain, plus **Skills**:
  `SKILL.md` documents and `*.skill` bundles you upload, import from a
  verified GitHub link, build in place, activate or deactivate, download, and
  delete. Six install on first visit — **algorithm-creator**, **code-review**,
  **mcp-builder**, **plugin-dev**, **security-review** and **skill-creator**. A
  skill adds instructions only — it grants no capability and opens no gate, and
  Raiker never runs code a skill ships.
- **Knowledge Map** — a force-directed graph of what Raiker actually holds. Its
  source picker opens on named places, not on a file browser: your projects'
  files, the files turns generated, approved memory, the encrypted database
  (which already holds Chat, Build, Tasks, Schedules and your uploads), and any
  folder you explicitly grant. A granted folder is read where it is; adding a
  single file from your computer copies it, so it asks first.
- **Observability** — an append-only, account-scoped audit log carrying your own
  conversations *and* the governed steps taken outside them — connecting a
  provider, pinning a model — plus metadata-only checkpoints and exact-model
  readiness evidence with bounded live probes and expiry.

- **Build works to a stated protocol, and the record says which one ran** — a
  Build turn carries an operating protocol a Chat turn does not: scale the effort
  to what is at stake, name the assumption that would waste the work and test it
  first, read the file before editing it, and check a claim before making it
  (`docs/RAIKER_BUILD_PROCESS.md`). The composer surface travels with the prompt
  and is written into the audit record, so which protocol a turn ran under is a
  fact rather than an inference — and it selects a working method only: every
  gate, decision mode, approval and tool is identical on both surfaces.

- **Hooks you can see, not just write** — a hook runs your own logic at a point
  in a turn and may only ever make an action *stricter*: it can deny a tool call
  or turn it into a decision, and can never allow one the runtime refused. Every
  event the configuration format accepts is emitted — sixteen of them, covering
  the session, the prompt, the turn's two possible endings, every tool call,
  approvals, delegations and tasks. `Stop` and `StopFailure` are separate on
  purpose: a turn parked on an approval, or stopped by you, never reports as a
  clean completion.

  They are configured in a file, and Extensions → **Hooks** reports what the
  runtime actually loaded from it — including the ways a rule you wrote still does
  nothing. A file that did not parse is named with the position the parse stopped
  at, and contributes no rules rather than being guessed at. A rule that cannot
  change an outcome reads **Observes only** instead of looking enforcing, and one
  naming a builtin this build does not ship says so rather than being counted as a
  guard. Every match, run, decision, timeout and failure is in the audit log.

- **A plugin contributes something, or says why it cannot** — a plugin runs no
  code of its own. It contributes through a surface that already governs the
  thing contributed, and three kinds now do:

  **Hook rules** load at `plugin` scope *below* every scope you control, so a
  plugin can make an action stricter and can never loosen one you set.
  **Skills** go through the same validator an upload does and arrive **switched
  off** — installing the plugin was consent to *offer* the skill, not to run with
  it — marked *from plugin* on Extensions → Skills so you can always see where an
  instruction came from. **MCP servers** are *offered*, never added: nothing is
  stored as a server, connected or reachable until you press **Add server**, and
  that runs the same governed create path as typing it in yourself. An offer can
  never carry a credential — `https` only, no auth in the URL, and `auth_ref`
  names an environment variable rather than holding a token.

  Revoking the plugin deletes everything it contributed rather than flagging it.
  Extensions → **Plugins** states what each installed plugin provides, read from
  the files the runtime loads rather than from the manifest that described them —
  and lists what a plugin *may* contribute, so "provides nothing" and "may not
  provide anything" read differently.

- **Governed voice in Chat and Build** — dictate into the normal editable
  composer, finish or cancel without sending, then explicitly send through the
  same prompt path as typed text. Completed replies can be read aloud manually;
  one global audio owner prevents overlapping listening/playback, and Raiker
  stores prompt provenance rather than microphone audio. Leaving the surface ends
  its audio: navigating away from a listening composer stops the microphone and
  keeps the words already dictated.

The layout adapts live: a bottom bar plus drawer below 640 px, a menu trigger
plus drawer to 1023 px, and the full sidebar at 1024 px and above.

## Known limits

Raiker's documentation does not run ahead of its code. As of 2026-08-22:

- **Voice is governed and turn-based, not full duplex.** Chat and Build support
  editable dictation and manual response playback. Continuous listening,
  speaking, interruption and hands-free task control remain future work; spoken
  consequential controls will not ship without visible confirmation and the
  same policy/audit route as typed controls.

- **Hooks are complete; plugins are nearly so; channels cannot deliver.** Of the
  three extension surfaces Claude Code ships:

  **Hooks** are done. All sixteen events the format accepts are emitted,
  `PreToolUse` and `PreCompact` decisions are honoured, and both `builtin` and
  `command` handlers execute under a bounded timeout with the program resolved
  inside the workspace. **Turn every hook off** on the Hooks tab stops all of them
  at once and is your setting rather than a fourth config file, so a
  `config/hooks.json` that arrived with a repository cannot re-enable itself. Two
  of the five handler types in the reference format are unbuilt — `http`,
  `mcp_tool`, `prompt` and `agent` need network, model and subagent surfaces that
  are still gated.

  **Plugins** contribute three of the four kinds the Plugins tab names: hook
  rules, skills, and MCP-server *offers*. A plugin is validated, supply-chain
  checked, signature-levelled and recorded first, and each kind needs its own
  declared permission — `event:hook`, `skill:contribute`, `mcp:server` — none of
  which is auto-approved, so you read it in the permission diff before installing.
  **Panels** are the one kind still unavailable: there is no route, permission or
  accessibility contract for a page a plugin drew. **LSP servers** are named in
  the manifest schema and have no surface at all to contribute to. No plugin code
  executes, in the runtime or in your browser.

  **Channels** deliver, and you can now reach that. A channel message is
  **untrusted content with a named sender who is not you** — never a prompt, never
  able to raise a turn's authority, trust from the pairing record rather than from
  the message. Outbound delivery runs through a capability gate and an egress
  allowlist; inbound is recorded, quarantined and its instructions inert. All of
  it existed and was unreachable until the tab gained pairing, so *linked*,
  *enabled*, *trusted* and *reachable* are now four facts shown as four things.
  Three of them are fail-closed by default and the tab names each one and its
  remedy. Rate limits, the spec's routing modes, and resolving an approval over a
  channel are not built — an inbound message never becomes work on its own.

  Tracked in `docs/plans/TO_BE_FIXED.md` → BUG-225 (channel rate limits, routing
  modes and relay resolution), BUG-226 (the hook handler types this build
  refuses: `http`, `mcp_tool`, `prompt` and `agent`), BUG-227 (no LSP surface)
  and BUG-228 (plugin panels).

- **A governed command now runs inside a real OS boundary, and that boundary is
  measured rather than described.** Selecting **Native OS sandbox** runs each
  command in its own Windows AppContainer holding no network capability, with
  the workspace reachable through a single capability grant, `.raiker` denied,
  `.git` read-only, and a Job Object that takes the whole process tree; Linux
  uses bubblewrap and macOS Seatbelt. What the host actually enforces is not
  taken on trust: a probe builds the real boundary over your real workspace and
  runs a child inside it that attempts six things — each one also attempted
  *outside* the boundary as a control. Only "worked outside, refused inside"
  counts. If the control arm fails, the result is **not proven**, and nothing
  turns green on it. All six, and the probe's own outbound destination, are on
  the environment card with a **Re-measure boundary** button.
- **That sandbox is foreground-only, and the card says so.** Inside the native
  sandbox, PTY and raw input, background execution, persistent sessions,
  filtered domain egress, credential quarantine, SSH and Daytona are **not
  built** — its capability set comes from the host probe, and none of them has
  been measured inside an AppContainer. They are absent from the interface
  rather than shown disabled, because a disabled control implies it is one
  setting away. Each has its reason recorded in `docs/plans/TO_BE_FIXED.md` →
  BUG-194. `local_native` remains explicit host access with reduced isolation
  and is still the default selection; **there**, background execution, a POSIX
  terminal and restart reattachment are built, and each environment card lists
  the capabilities that boundary really has. Browser reload restores durable
  output. A Raiker restart now reattaches to a background run whose supervisor
  still answers — by authenticating to it, never by pid — and a run it cannot
  prove is still its own is marked `lost` rather than inventing success.
- **A container boundary persists for a session, and can be reset.** The
  container a session's commands run in is created once and reused, so what one
  command installs the next one can use, and **Reset environment** / **Reset and
  clear cache** put it back to a known state. The native sandbox still creates
  and deletes a profile around every command, deliberately: its container SID is
  a pure function of its name, so a predictable name is a hole.
- **What a turn thought is retained only when the owner chooses.** Reasoning is
  shown live; Settings → Privacy decides whether it is kept. A reopened turn
  states when working was not retained, while retained working remains excluded
  from search and export. Tool-call evidence remains permanent in
  **Observability → Audit log**.
- **A batch of tool calls runs in parallel only when nothing in it needs a
  decision.** Every validated read-only call in a batch is executed
  concurrently; the moment one call in the same batch requires approval, the
  whole batch is walked serially and pauses at that call. Nothing behind the
  pause is lost — the remainder is parked with the turn and re-governed one
  decision at a time when you resume — but a batch containing three edits is
  three decisions, not one.
- **Build patching is strict about which code you named, not about how you
  typed it.** One unified diff may cover several files, including creates and
  deletes, and it is applied as a single approval and a single reversible change
  set. Matching tries the exact text first; when that finds nothing, the same
  search runs again ignoring **trailing whitespace and indentation style**, so a
  quote that used spaces where the file uses a tab still names the right code —
  and the file keeps its own indentation rather than adopting the quote's. What
  does **not** relax is uniqueness: an edit still requires exactly one match and
  a relaxed search that hits two places is refused, so the tolerance can never
  land an edit somewhere it was not meant to. Interior spacing is text, not
  formatting — `a + b` and `a+b` remain a mismatch. A section that edits or
  deletes must name a text file that already exists inside the workspace and one
  that creates must name a path that does not, and a patch naming the same file
  twice is rejected before anything is written. There is still no partial
  application — one bad hunk fails the whole proposal.
- **A push needs its own switch, its own allowlist, and a credential you lend
  rather than leave lying about.** An approved `git_commit` records the change
  set you reviewed, and an approved `git_push` really publishes the branch — but
  publishing is egress carrying repository content off the machine, so it answers
  to **Git push** (`git_push_execution`) rather than to Git writes, and it does
  nothing until the remote's host is on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`. The
  credential is stored encrypted from **Settings → Git credential** and lent to
  one command at a time under a grant you make — **once**, or **for this
  session** — which carries its own expiry and can be withdrawn in a press. It is
  passed in the command's own environment rather than on a command line, and
  removed from every log, error and captured output for as long as the loan
  lasts. `RAIKER_GITHUB_TOKEN` in the host environment still works for an
  install configured that way, and the page says which of the two you are on.
  Only HTTPS GitHub remotes are pushable, because that is the credential Raiker
  holds; it never forces and never deletes a branch.
- **Web reads are on, and what they may not reach is yours to say.** `web_fetch`
  and `web_search` work on a fresh install: there is no list to fill in first,
  and `web_search` uses a keyless endpoint until you point
  `RAIKER_WEB_SEARCH_ENDPOINT` at your own. What you control is the **blocklist**
  — **Settings → Web access**, or `RAIKER_WEB_EGRESS_BLACKLIST` — which takes a
  domain (covering its subdomains), a wildcard, an IP address, a CIDR range, or a
  `/regex/`, and can be tested against a host without contacting it. What you do
  **not** control, and cannot switch off, is the address guard: https only, no
  credential in the URL, and every address a name resolves to must be public, so
  a fetch can never reach your loopback interface, your home network, or a cloud
  metadata service — including through a name that resolves to one, an
  IPv4-mapped IPv6 address, or a redirect. The connection is pinned to an address
  that already passed, so the destination cannot change between the check and the
  request. Emptying the blocklist opens none of that.
- **A fetched page reaches the model as text, not as markup or instruction.**
  Scripts, styles and comments are dropped; elements a visitor could never see —
  `hidden`, `display:none`, zero-size, off-screen, `aria-hidden` — are removed and
  counted, because text nobody can read is the usual carrier for an instruction
  meant only for a model; zero-width and bidirectional characters are stripped;
  and a line shaped like a conversation role marker is defanged so page text
  cannot open a turn. What was removed is reported alongside the page rather than
  silently swallowed. None of this is a filter that decides whether content is
  safe — the thing that stops a hijack is that fetched text never carries
  instruction authority — but an injection attempt arrives visible and inert.
- **Remembering something is a decision, and Memory store starts off.**
  `memory_write` and `memory_forget` are offered to the model, but like every
  acting capability they answer to their own gate, which ships **off**. With it
  on, a turn proposes the exact sentence it wants to keep and you approve or
  reject it; approving really stores it, and text that looks like a credential
  is refused before you are asked. The Memory page states which of those you are
  in rather than promising proposals a disabled gate cannot produce.
- **A composer mode tightens the turn; it never widens your permissions.**
  Build's **Plan / Edit / Auto** modes are this conversation's posture, sent with
  each prompt and applied to that turn: Plan refuses file writes, patches and
  commands outright, Edit turns each one into a decision, and both leave your
  standing permissions untouched. A turn may only ever tighten itself — `allow`
  and `auto` are refused by the prompt contract — so **Auto** adds no restriction
  of its own and does exactly as much as you already allowed, which the composer
  states rather than implies. That is why Build **opens in Auto**: the default
  posture is the one that defers to Permissions instead of quietly overriding it.
  Widening a permission still happens on Permissions, under the step-up: a
  recorded reason, and a threat-model acknowledgement where the capability
  demands one.
- **The code map answers where a name is defined and where it is used, but it
  matches text rather than resolving a call graph.** Turning on **Code map** lets
  Raiker index the repository Build points at, so the agent can ask where
  something is defined instead of guessing a search pattern; it is rebuilt on
  demand and refreshed for the files an approved change touched. Python is parsed
  with a real parser; fifteen other languages are matched with bounded patterns,
  which finds most declarations and misses unusual ones — each file records which
  extractor produced it. **Find references** answers the other half — what would
  break if you changed this — by scanning the files that map already accepted for
  word-boundary uses of one identifier, excluding the declaration itself. It is
  textual, so a same-named symbol from another module matches too, and it says so
  rather than implying a precision it does not have. A scan that hits one of its
  bounds reports `partial` and names the bound rather than presenting a partial
  answer as a complete one. There is still no resolved call graph and no
  embeddings over the tree.
- **A component that keeps failing is contained, and stays contained until you
  say otherwise.** Budgets alone let a hard-down provider or a broken tool spend
  a whole turn one doomed call at a time, so Raiker counts consecutive failures
  per tool and per provider in durable state: three in a row pauses that subject
  with a stated reason and a raised finding, and further calls are refused rather
  than retried. After a minute one call is let through as a probe; if it works,
  the pause clears itself. Nothing here is a ban — Settings → Security & sign-in
  lists every contained subject with its reason and clears it in one press — but
  a turn that finds every model contained says so instead of trying them all
  again.
- **Suspicious content in a source is reported, never blocked.** Text a page,
  message or attachment carries that is shaped like a prompt-injection attempt —
  cancelling earlier instructions, impersonating a system turn, asking for a key,
  asking to skip approval, hidden characters — raises a finding naming that exact
  document or URL. It is deliberately advisory: the thing that actually stops a
  hijack is the deny-by-default tool gate, and external content is framed as data
  and never as instruction whatever the scan finds. The rules are fixed patterns
  with names, not a classifier, because a filter that is right most of the time
  would read as an assurance it cannot give.
- **A plugin signature proves an author only once you configure a key.** Raiker
  verifies manifest checksums always, and manifest signatures against
  `RAIKER_PLUGIN_SIGNING_KEY` (yours) or `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` (a
  publisher's) when either is set. With neither set — the default — a signature
  is recorded as **Present only**: the checksum still catches an accidental edit,
  but nothing was checked against an author. Extensions → Plugins states which of
  the three levels each installed plugin earned and what would raise it. The
  default is not silently hardened; it is stated.
- **A model check expires, and Raiker re-confirms it quietly rather than
  stopping you.** Before any surface will send, the exact model has to have
  passed a reachability check; that check is good for five minutes by default and
  1–120 minutes by your setting (Settings → Runtime). While a work surface is
  open, the selected model is re-confirmed in the background as its window runs
  down, so a long session does not spontaneously disable Send — and connecting,
  switching model, pulling, or changing an endpoint or credential still
  invalidates a check immediately, whatever the window is set to.
- **Key pages are not locked into RAM by default.** The workspace database is
  SQLCipher-encrypted. SQLCipher can additionally lock the pages holding key
  material so they never reach swap — and Raiker leaves that **off**, explicitly,
  for two measured reasons: it costs about seven times on every store operation
  (0.17 s versus 1.14 s for a bootstrap plus two hundred reads), and when the
  platform's locked-memory allowance runs out the failure is not slow work but
  `MemoryError` on every request, because authentication opens the store — the
  lockout FIXED-150 records. Which posture you are on is not left to guesswork:
  `GET /api/health` reports the setting, the reason, and the allowance this
  machine would have given. Set `RAIKER_SQLCIPHER_MEMORY_SECURITY=on` to demand
  the stronger one; a refused lock then fails closed and names why.
- **Shipped list prices are unverified defaults.** `raiker/config/model-profiles.json`
  seeds prices only for the models whose published rate is recorded there, each
  stamped with an `as_of` date. Check them against your provider's current
  pricing page and override anything that has moved; an unpriced model reports
  its cost as unknown rather than as zero.

### Where Raiker is behind the general standard for agent products

The limits above are boundaries Raiker chose. These are the ones where it is
simply behind, stated at the point they stop being theoretical. Each is measured
on the shipped build, not estimated.

- **Memory does not retrieve by meaning — it retrieves by shared words.** Both
  halves of "hybrid" retrieval are lexical. The vector half
  (`raiker/vector/__init__.py`) is a feature-hashing bag-of-tokens embedding
  computed offline with no model: it scores word overlap, so a memory that
  answers the question in different words scores zero and is not recalled. Ask
  *"what theme does the user like"* and a stored *"the owner prefers dark
  mode"* is reachable only through the one word the two sentences happen to
  share. Products that advertise memory use a real embedding model here.
  **Partly addressed 2026-08-17 (FIXED-230):** retrieval now resolves one
  owner-selected embedding space, embeds the query in that same space, and
  refuses to mix two — and the Memory page names the space in force and says
  whether a paraphrase can recall anything at all, rather than letting the word
  "vector" imply semantics that are not there. What remains is a model to
  select: a default install still holds only the labelled hashing fallback, and
  the two honest routes to better (a download, or provider egress) are both the
  owner's decision. Tracked as MEM-10; the durable semantic/vector write path is
  disabled outright (`raiker/memory/semantic.py`).
- ~~**Lexical results are ordered by recency, not relevance.**~~ **Fixed
  2026-08-17.** This said the bundled SQLCipher build had no FTS5 and therefore
  no BM25, which was true of `sqlcipher3-wheels` 0.5.2 and 0.5.4 and stopped
  being true at 0.5.6 without anyone re-measuring. Both text indexes are now
  FTS5 and both searches rank by `bm25()` before recency, so the exact answer
  from two years ago ranks first instead of being dropped. The engine is probed
  at runtime and reported on `/api/health`; a build genuinely without FTS5 still
  falls back to FTS4 and recency, and says so. Closed as FIXED-231.
- **Every recall reads every embedding.** Retrieval loads all active vectors for
  the scope, rebuilds the index in memory, and scores them in Python on each
  call. There is no approximate-nearest-neighbour index and no cache. After the
  2026-08-15 fix to the query plan (FIXED-200) one recall costs ~30 ms at 200
  memories, ~124 ms at 1 000 and ~431 ms at 3 000 — linear, paid on every turn,
  before the model is asked anything. It is usable into the low thousands and
  degrades steadily above that; the vector stores comparable products use are
  sublinear and measured in millions. Raiker will not fall over at 10 000
  memories, but recall will cost more than a second of every turn.
- **A natural-language question drops the lexical half of retrieval
  altogether.** Terms shorter than three characters are discarded and the rest
  are combined with an implicit `AND`, so *"Kubernetes rollout"* matches and
  *"how does the Kubernetes rollout work"* matches nothing — the longer and more
  natural the question, the likelier every term must appear in one memory. The
  vector half still answers, and it is lexical too.
- **Entity relationships are evidence-bound and reviewed; nothing expires by
  itself.** Approved memory and conversation evidence now creates owner-scoped
  entity/relationship proposals, and only accepted proposals reach graph recall
  (MEM-06 / FIXED-241). No retention sweep is started, so `expires_at` is enforced only at read time
  and expired rows are collected only when the owner confirms a cleanup
  (MEM-07). Eidetic capture is invoked by the runtime as of 2026-08-17 (MEM-04),
  and what it recorded is in **Memory → Observations**; what it cannot do is
  replay the material, because it deliberately never held it.
- **The governed shell keeps unproved controls off.** Foreground SSH and Daytona
  adapters, filtered-egress policy/proxy/revocation, credential delta snapshots
  and runner trust verification now exist. This host had no container daemon or
  production signing anchor, so live egress bypass, credential delivery/merge
  and publisher verification remain unavailable rather than configuration-
  enabled. PTY and restart reattachment are POSIX-only; see BUG-194.
- **Plugins are one contribution kind short; channels stop short of routing.**
  Hooks reached parity on 2026-08-22 — every event the format accepts is emitted,
  with an owner off switch and a page that states which rules actually enforce.
  Plugins went on to contribute skills and MCP-server offers the same day;
  **panels** are the one kind left, and LSP servers have no surface to contribute
  to. Channels gained their authority contract and then their owner surface: the
  transport had been built and unreachable, and pairing is what reaches it. What
  is still short there is above the transport — per-channel rate limits, the
  spec's routing modes, and resolving an approval over a channel.

The memory items are the ones to weigh first if you are choosing Raiker for its
memory: the full audit, with reproductions, is
[docs/plans/MEMORY_RELIABILITY_PLAN.md](docs/plans/MEMORY_RELIABILITY_PLAN.md).

Where one of these is tracked as work rather than a deliberate boundary, it is
written up with a reproduction and a proposed fix in
[docs/plans/TO_BE_FIXED.md](docs/plans/TO_BE_FIXED.md), which now lists only what
is still open; everything closed keeps its full record — observation, root cause,
and the interface outcome that had to be true first — in
[docs/plans/FIXED_ITEMS.md](docs/plans/FIXED_ITEMS.md).

## Documentation

- **[User guide](docs/guide/README.md)** — install, connect a model, permissions,
  Chat, tasks, extensions, troubleshooting. **Also inside the app**, under
  Utilities → **Guide**: the same seven sections, served read-only from the
  install, so a running Raiker carries its own help rather than sending you to a
  repository. Set `RAIKER_GUIDE_DIR` to read a different checkout's copy.
- **[Documentation index](docs/README.md)** — architecture, security model,
  commands, API contracts, capability status, verification.
- **[Live manual test plan](docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md)** — a
  repeatable end-to-end plan and the recorded result of the last round
  (2026-08-11, four provider connections plus a live Ollama turn), with
  [screenshots](docs/plans/screenshots) of what worked and what did not.
- **[Security philosophy and policy](docs/SECURITY_AND_POLICY.md)** — read this
  before enabling any governed capability.

For contribution and vulnerability reporting see
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
