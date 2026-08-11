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
| Home | **Workbench** — resume work, see what needs attention |
| Work | **Chat**, **Build**, **Search Chat**, **Tasks**, **Projects** |
| Knowledge | **Memory**, **Knowledge Map** |
| Control | **Approvals**, **Permissions**, **Models**, **Extensions** |
| Observe | **Observability** — readiness, audit log, checkpoints, live work, notifications, sessions |
| Utilities | **Settings** |

Highlights, each verified against a live instance:

- **Chat** — streamed turns against local or hosted models, image and document
  attachments, sanitised Markdown rendering, source citations, a recent-chat
  list with per-row delete and move-to-project, indexed full-text search across
  titles and message bodies that shows the exchange each result matched on, and
  one-click export of a conversation to HTML, Markdown or PDF; at 90% of a known
  context capacity, older completed exchanges are compacted automatically while
  the transcript remains unchanged.
- **Recall** — a turn can read your own past conversations, not only the ones it
  can still see. `conversation_search` searches every exchange you have had,
  narrowed to a date range when the question is about a particular period, and
  returns the matching exchange with its conversation, timestamp and turn id so
  an answer can cite the record instead of reconstructing it. Ambient recall
  offers the conversations that match this prompt rather than the eight most
  recent ones. What it returns is your own transcript, treated as data rather
  than as instruction; **Incognito** switches the whole path off.
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

The layout adapts live: a bottom bar plus drawer below 640 px, a menu trigger
plus drawer to 1023 px, and the full sidebar at 1024 px and above.

## Known limits

Raiker's documentation does not run ahead of its code. As of 2026-08-11:

- **Approved network and process actions still do not run** — approval
  resolution executes file changes and patches, bounded local `shell` commands,
  and the owner-configured SSH and Daytona profiles. `network` and `process`
  keep metadata-only resolution. This is deliberate, not an oversight: a file
  write is checkpointed and reversible, and a shell command is allowlisted,
  workspace-contained, time- and output-bounded, and captured; those two are
  neither. Resolving one still continues the parked turn, with an honest
  "approved, but not executed" result the agent can react to.
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
- **A push needs its own switch, its own allowlist and your own credential.**
  An approved `git_commit` records the change set you reviewed, and an approved
  `git_push` really publishes the branch — but publishing is egress carrying
  repository content off the machine, so it answers to **Git push**
  (`git_push_execution`) rather than to Git writes, and it does nothing until
  the remote's host is on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` and
  `RAIKER_GITHUB_TOKEN` is set. Only HTTPS GitHub remotes are pushable, because
  that is the credential Raiker holds; it never forces and never deletes a
  branch. `github_write` then has a head to open a pull request against.
- **Web fetch takes two deliberate steps to turn on.** `web_fetch` is gated by
  its own capability and withholds by default at `ask`, so a page is fetched
  only once the owner has both enabled the gate and raised the decision mode to
  **Allow** — and then only for a host on `RAIKER_WEB_EGRESS_ALLOWLIST`, which
  is empty until you set it. `web_search` answers the same gate, but Raiker
  ships no search endpoint: it reports `web_search_not_configured` until you
  point it at one.
- **Remembering something is a decision, and Memory store starts off.**
  `memory_write` and `memory_forget` are offered to the model, but like every
  acting capability they answer to their own gate, which ships **off**. With it
  on, a turn proposes the exact sentence it wants to keep and you approve or
  reject it; approving really stores it, and text that looks like a credential
  is refused before you are asked. The Memory page states which of those you are
  in rather than promising proposals a disabled gate cannot produce.
- **A composer mode tightens the turn; it never widens your permissions.**
  Build's **Plan / Edit / Auto** chips are this conversation's posture, sent with
  each prompt and applied to that turn: Plan refuses file writes, patches and
  commands outright, Edit turns each one into a decision, and both leave your
  standing permissions untouched. A turn may only ever tighten itself — `allow`
  and `auto` are refused by the prompt contract — so **Auto** adds no restriction
  of its own and does exactly as much as you already allowed, which the composer
  states rather than implies. Widening a permission still happens on Permissions,
  under the step-up: a recorded reason, and a threat-model acknowledgement where
  the capability demands one.
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
- **Shipped list prices are unverified defaults.** `config/model-profiles.json`
  seeds prices only for the models whose published rate is recorded there, each
  stamped with an `as_of` date. Check them against your provider's current
  pricing page and override anything that has moved; an unpriced model reports
  its cost as unknown rather than as zero.

Where one of these is tracked as work rather than a deliberate boundary, it is
written up with a reproduction and a proposed fix in
[docs/plans/TO_BE_FIXED.md](docs/plans/TO_BE_FIXED.md), which now lists only what
is still open; everything closed keeps its full record — observation, root cause,
and the interface outcome that had to be true first — in
[docs/plans/FIXED_ITEMS.md](docs/plans/FIXED_ITEMS.md).

The 2026-08-10 round closed eleven entries there. **FIXED-133** is the one this
section is written against: a new owner's first message used to fail with the raw
string `model_unavailable: provider_error_unclassified`, and a fresh install now
either answers or explains in a sentence why it cannot. The rest are the OWASP
Agentic Top 10 gaps that review exposed — **FIXED-163** (a failing tool or
provider contained rather than retried to exhaustion), **FIXED-164** (anomaly
detection and containment for every capability, not only MCP), **FIXED-165** (a
delegated subagent result bound to the spawn that produced it), **FIXED-166** (a
plugin signature that states what it proved), **FIXED-167** (a security mapping
whose every row cites the code) and **FIXED-168** (the prompt-injection scanning
hook) — together with **FIXED-161** (the production bundle back under its size
warning), **FIXED-162** (retry, cancellation and partial cleanup that do what
they say), **FIXED-169** (the readiness window above) and **FIXED-170** (the live
acceptance spec running on one provider key).

The 2026-08-08 round's findings are **FIXED-154** through **FIXED-159**, and the
2026-08-10 visual sweep's are **FIXED-149** through **FIXED-153**. The entries
that closed the older limits this section used to list are FIXED-34, FIXED-39,
FIXED-90, FIXED-99, FIXED-101 and FIXED-109, and
[ADD-02](docs/plans/TO_BE_ADDED.md) in the companion document.

The 2026-08-11 round closed **FIXED-181** through **FIXED-186**: multi-call
answer seams, the checked-in live stub, dead transcript markup, automatic 90%
context compaction, the connected-provider rolling seven-day usage view, and
concurrent audit-log integrity. The same round closed two of the limits this
section used to list — reference search over the code map, and matching that
survives whitespace — and **MEM-01** and **MEM-02** in
[docs/plans/MEMORY_RELIABILITY_PLAN.md](docs/plans/MEMORY_RELIABILITY_PLAN.md),
which is the memory audit's own record of what recall can and cannot do yet.

## Documentation

- **[User guide](docs/guide/README.md)** — install, connect a model, permissions,
  Chat, tasks, extensions, troubleshooting.
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
