# Raiker

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is a local-first AI-agent runtime. Every model interaction and tool
action passes through policy, capability gates, approvals, and audit records, so
local automation stays under your control.

It is one product wearing three faces: **Chat**, a polished assistant; **Build**,
a coding agent; and the governed platform both run on. Governance, observability,
policy awareness and security are properties of that platform, not a layer
wrapped around it — there is no model, tool, skill, plugin, interface, runtime or
execution path that reaches an action without crossing them, and your choice of
model (local, home-lab, private-network or hosted) changes none of it.

The launchable local UIs are the plain local terminal client and the local web dashboard
— `raiker`, and `raiker-app` (or `raiker-web` for explicit service control) on
`127.0.0.1`. Phase 8 deferred clients — mobile, IDE, hosted multi-user — are not
available.

Approving an action performs it: twelve capabilities execute once through the
governed relay, each re-governed at execution time, and `process`, `network` and
other approvals remain decision-only. Durable memory mutation is broker-governed
and proposable from Chat, Build and the terminal client — you see the exact text
and decide, and approving really stores or removes the record.
Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced.

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
platform data directory, pass `--workspace` consistently — before or after the
subcommand (`raiker-app --workspace .`, `raiker-app service status --workspace .`).

The same controls are in the app, under **Host** in the top bar. Opening it
makes no outbound request; Raiker contacts no update service until you pin a
channel. The desktop payload is self-contained — API, built dashboard and native
tray — and first run is a five-stage wizard: owner, model, privacy posture,
optional encrypted backup, workspace. Releases are built by a
`workflow_dispatch` pipeline that **refuses to build without code-signing
identities**; no signed artifact has been published yet. See
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

**Model setup is part of first run.** A fresh workspace opens the setup flow,
and a selected model is only a preference until its exact endpoint and model
pass readiness; every model-backed action stays disabled meanwhile and links to
**Models** rather than sending a turn that cannot run. To connect a hosted
model: **Models** → **Connect** → paste the key. That is the whole flow — see
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
| **Decision mode** | Permissions | The standing per-capability policy: Ask, Allow, Auto or Deny before each action |
| **Turn posture** | The Chat and Build composers | This conversation's own tightening — Build's Plan / Edit / Auto, plus the approval policy (Manually approve, Automatically approve, Skip, or **Decline what needs asking**). A turn may only ever tighten; `allow` and `auto` are refused by the prompt contract |
| **Approval** | Approvals | A human decision on the specific proposed action |

Opening a higher-risk gate is a governed step-up: a human `runtime_gate_manager`,
a reason, a short phrase they type to record their intent, and a threat-model
acknowledgement — all recorded against your principal. The phrase is not a
credential. Owner **recovery** is governed and audited.

A human `runtime_gate_manager` alone may change capability gates or stop the
agent runtime.

There is one runtime, and its only decision is binary: accepting executions, or
stopped. Raiker used to require one of five modes to be selected before a
capability could reach runtime level — a second switch in front of the switches
that decide anything, since what an action may do is already settled by its
capability gate, its threat-model acknowledgement, its human confirmation, and
whether a real executor exists for it.

**The approval detail says what will happen before you decide.** Twelve
capabilities are performed once through the governed approval execution relay,
re-governed at execution time: file writes and patches (previous contents
checkpointed, never into `.raiker/` or `.git/`), a bounded local `shell`
command, git branches, commits and pushes, a GitHub write, durable memory writes
and forgets, task and project rows, and owner-selected SSH and Daytona actions.
`process`, `network` and every other approval record the decision and execute
nothing. Disabling either the `approval_execution_relay` or the target
capability returns those approvals to record-only, and a critical approval always
uses the human-only, step-up-verified lifecycle instead.

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
| Utilities | **Guide** — the user guide, served from this install — and **Settings**, including **Web access** and **Git credential** |

The layout adapts live: a bottom bar plus drawer below 640 px, a menu trigger
plus drawer to 1023 px, and the full sidebar at 1024 px and above.

### The parts worth knowing about

Each is verified against a live instance. [The user
guide](docs/guide/README.md) is the task-shaped version of all of it.

| | What it is, and the part that is unusual |
|---|---|
| **Chat** | Streamed turns, image and document attachments, sanitised Markdown, source citations, indexed full-text search that shows the exchange each result matched, and export to HTML, Markdown or PDF. At 90% of a known context capacity older exchanges compact automatically and the transcript stays unchanged. → [Working in Chat](docs/guide/working-in-chat.md) |
| **Build** | The coding agent: Plan / Edit / Auto as a turn posture the runtime enforces, one unified diff as one reversible change set, a governed terminal in a measured OS boundary, and a governed push. It carries an operating protocol a Chat turn does not, and **which protocol ran is written into the audit record** rather than inferred. Every gate, decision mode, approval and tool is identical on both surfaces. → [Working in Build](docs/guide/working-in-build.md) |
| **What a turn did, and thought** | One line per tool call in the model's proposal order, with running, waiting, failed and refused states. **The phrase is resolved on the server under the same redaction the audit record passes** — a fetch is named by its host, a command by its program — so a row can never say more than the log does. Reasoning fills a collapsed block; whether it is *kept* is your decision (Settings → Privacy), and a turn whose working was not kept says so |
| **Recall** | `conversation_search` reads every exchange you have had, date-narrowed, returning the conversation, timestamp and turn id so an answer cites the record. Ambient recall offers what matches this prompt rather than the eight most recent. Your transcript is treated as data, never instruction; **Incognito** switches the path off |
| **Knowledge Map** | A force-directed graph of what Raiker actually holds, over a source picker of named places rather than a file browser. Every citation records the text it contributed and reads both ways; a citation whose file is gone is drawn as a hollow node rather than dropped |
| **Tasks** | Run now, schedule once, daily routine, or a persistent background agent — nestable, prioritised, stoppable at a safe boundary. Each cycle is one governed turn |
| **Models** | Local, home-lab, hosted and advanced providers; live catalogues; an encrypted per-instance vault; an owner-ordered fallback with no silent hosted fallback; approved-root GGUF discovery, managed llama.cpp and revision-pinned Hugging Face downloads; per-provider token and cost accounting with each figure's source named. → [Connecting a model](docs/guide/connecting-a-model.md) |
| **Web access** | Reads work out of the box. You control a **blocklist**; what you cannot switch off is the address guard — HTTPS only, no credential in the URL, every resolved address public, re-checked on each redirect. A fetched page arrives as sanitised text with what was removed reported |
| **Git credential** | The token Raiker pushes with, stored encrypted and lent to one command at a time under a grant you make once or for a session. It never appears in a log, an error, or a command's output |
| **Extensions** | Connectors, MCP servers you can build and contain, **Skills** (six install on first visit; a skill adds instructions only and Raiker runs no code it ships), **Hooks** and **Plugins**. → [Extensions and MCP](docs/guide/extensions-and-mcp.md) |
| **Hooks** | A hook may only ever make an action *stricter* — nothing it returns can allow what the runtime refused. Extensions → Hooks reports what the runtime **actually loaded**, including the three ways a rule you wrote still does nothing: its file did not parse, its event is never dispatched, or nothing on it carries a decision |
| **Plugins** | A plugin runs no code of its own. It contributes through surfaces that already govern the thing contributed — hook rules below every scope you control, skills that arrive **switched off**, and MCP servers that are *offered*, never added. Revoking deletes what it contributed rather than flagging it |
| **Voice** | Dictate into the normal editable composer; **Done** never sends, **Cancel** restores the exact prior draft, and only Send creates a turn. Replies read aloud on request. Raiker stores prompt provenance, never microphone audio |
| **Observability** | An append-only, account-scoped audit log carrying your conversations *and* the governed steps taken outside them, plus metadata-only checkpoints and exact-model readiness evidence with bounded probes and expiry |

## Known limits

Raiker's documentation does not run ahead of its code, and the honest list is
long enough to deserve its own page:
**[docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md)**. It separates the boundaries
Raiker *chose* from the places it is simply behind. The five worth knowing
before you decide anything:

| Limit | In short |
|---|---|
| **Memory does not retrieve by meaning** | Both halves of "hybrid" retrieval are lexical. The default vector space is a feature-hashing bag of tokens with no model, so a paraphrase is recalled only through shared words |
| **Checkpoint rewind is not reachable** | Capture is automatic and complete before every approved mutation; no route, command or tool proposes a restore. Recovery is git |
| **Hooks cover half the reference lifecycle** | Sixteen of the thirty-one events Claude Code documents, and one of five handler types |
| **Voice is turn-based, not full duplex** | Editable dictation and manual playback. Continuous listening and hands-free control are future work |
| **The audit log cannot be exported from the product** | The redacted manifest is produced into the store; no route surfaces it |

Open defects are in [docs/plans/TO_BE_FIXED.md](docs/plans/TO_BE_FIXED.md), each
with a reproduction and a proposed fix; what closing one is worth is in
[docs/REFERENCE_PLATFORM_COMPATIBILITY.md §5](docs/REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).

## Documentation

**[docs/README.md](docs/README.md) indexes every maintained document** and names
the canonical one per question. Start there rather than guessing a filename.
The five most people want:

| | |
|---|---|
| **[User guide](docs/guide/README.md)** | Install, connect a model, permissions, [Chat](docs/guide/working-in-chat.md), [Build](docs/guide/working-in-build.md), tasks, extensions, troubleshooting. The same eight sections are served **inside the app** under Utilities → **Guide**, read-only from the install, so a running Raiker carries its own help. `RAIKER_GUIDE_DIR` points it at a different checkout |
| **[Implementation status](docs/IMPLEMENTATION_STATUS.md)** | What is implemented right now, kept apart from what is recorded, previewed or planned |
| **[Known limits](docs/KNOWN_LIMITS.md)** | What this build cannot do — the boundaries Raiker chose, separated from the places it is simply behind. Every item measured on the shipped build |
| **[Reference platform compatibility](docs/REFERENCE_PLATFORM_COMPATIBILITY.md)** | The canonical, source-cited comparison against Claude Cowork, Claude Code, ChatGPT Chat/Work, OpenAI Codex, OpenClaw, DeepSeek Harness and Hermes Agent: what Raiker has, what it lacks, what it does differently on purpose, what it refuses to copy, and the prioritised backlog. **No other document carries a comparison matrix** |
| **[Security philosophy and policy](docs/SECURITY_AND_POLICY.md)** | Read before enabling any governed capability |

Evidence: [the live manual test plan](docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md)
is a repeatable click-by-click round with the last full run recorded (2026-08-08,
every model Anthropic's catalogue returned), and
[screenshots](docs/plans/screenshots) carry the targeted rounds since, through
2026-08-22.

For contribution and vulnerability reporting see
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
