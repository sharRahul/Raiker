# Raiker live manual test plan

> A repeatable, click-by-click plan a person can follow against a **running**
> Raiker instance, plus the recorded result of the round executed on
> **2026-07-26** against hosted Anthropic (`claude-haiku-4-5-20251001`), with
> focused file-retention re-verification on **2026-07-28** using local Ollama
> (`gemma4:31b-cloud`), and a provider/terminal/storage verification round on
> **2026-08-01** using the same Ollama model.
>
> Every step below was executed in a real Chromium session against
> `raiker-web` serving the built SPA. Screenshots are in
> [`screenshots/working/`](screenshots/working) and
> [`screenshots/not-working/`](screenshots/not-working).
> Defects found are tracked in [`TO_BE_FIXED.md`](TO_BE_FIXED.md).
>
> **Never commit an API key.** Keys go into the sign-in dialog or the server
> process environment, for the duration of the test only.

---

## 0. Scope and sources

This plan covers the whole shipped web surface, derived from
`docs/superpowers/specs/` and `docs/superpowers/plans/`:

| Source document | What it promises | Covered by |
|---|---|---|
| `2026-07-18-adaptive-navigation-design.md` | phone/tablet/desktop navigation | §9 |
| `2026-07-26-conversational-chat-design.md` | bubbles, streaming labels, no governance metadata in Chat | §5 |
| `2026-07-26-chat-composer-context-and-file-inspector-design.md` | configured-model selector, context meter, permission control, file inspector | §5.4–5.6 |
| `2026-07-26-chat-tasks-and-project-assignment-design.md` | governed `create_task` / `assign_session_project` | §7 |

The two specs carry implementation notes stating that the file inspector,
automatic 90 % compaction, provider usage/cost data, and the natural-language
task/project flow are **specified but not shipped**. This plan verifies that
claim rather than assuming it. (The file inspector has since shipped —
FIXED-10; §5.6 now tests a working pane rather than its absence.)

---

## 1. Environment setup

```bash
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
npm --prefix apps/web ci
npm --prefix apps/web run build

# The model egress allowlist is process configuration by design — it is the last
# boundary before bytes leave the machine and is deliberately NOT editable from a
# browser session.
export RAIKER_MODEL_EGRESS_ALLOWLIST='api.anthropic.com,api.openai.com,generativelanguage.googleapis.com,openrouter.ai'

.venv/bin/raiker-web --workspace /tmp/raiker-manual-test --port 8765 --no-browser
```

Open `http://127.0.0.1:8765`.

**Result 2026-07-26:** server up, `GET /api/health` → `{"status": "ok"}`.

---

## 2. First run and lock screen

| # | Step | Expected | Result |
|---|---|---|---|
| 2.1 | Load `/` on a fresh workspace | Lock screen, hero "Hello! I am Raiker.", **Create a User Account** form with Username / Password / Confirm password | ✅ `01-first-run-lock-screen.png` |
| 2.2 | Check pre-auth status strip | "SYSTEM STATUS · Runtime operational" (from `/api/health` only) | ✅ |
| 2.3 | Browser console | 0 errors | ✅ |
| 2.4 | Register the owner account | Dashboard mounts at Workbench | ✅ `02-workbench-home.png` |
| 2.5 | Reload the page | Lock screen returns — the bearer token is in memory only, never `localStorage` | ✅ (by design) |

---

## 3. Navigate every route

Click each sidebar entry in turn: Workbench, Chat, Build, Search Chat, Tasks,
Projects, Sessions, Memory, Brain, Approvals, Permissions, Models, Extensions,
Observability, Settings. Then each hub tab:
`extensions?tab=connectors|mcp|plugins|channels` and
`observe?tab=overview|activity|checkpoints|diagnostics|work|notifications`.

**Result 2026-07-26:** all 15 routes and all 10 hub tabs render, **0 console
errors on every one**. Screenshots `03-route-*.png`, `40-*` … `52-*`.

Deliberately-empty surfaces state *why* they are empty rather than pretending:
Plugins ("A plugin cannot render its own page here until Raiker has an accepted
route, permission, and accessibility contract for it") and Channels.

---

## 4. Connect a hosted model

Re-verified on **2026-07-26 (second round)** against a workspace with **no**
`RAIKER_MODEL_EGRESS_ALLOWLIST`, **no** vault key, **no** runtime mode, and
**no** capability gates — i.e. exactly what a new user has.

| # | Step | Expected | Result |
|---|---|---|---|
| 4.1 | Register the owner account | Dashboard mounts | ✅ |
| 4.2 | Models → Anthropic → **Connect** → paste API key → Connect | `PUT /api/models/anthropic-hosted/connection` **200** `{"connection_configured": true}` | ✅ `95-clean-first-run-connect.png` |
| 4.3 | **Choose model…** | Live catalogue from `api.anthropic.com` | ✅ `15-` |
| 4.4 | Pick a model → **Use model** | `PUT /api/model-selection` 200, "selected" badge | ✅ `16-` |
| 4.5 | Send a prompt in Chat | Streamed reply from the real provider | ✅ `96-` |
| 4.6 | Models header | "1 of 10 providers set up" + total API cost | ✅ `91-` |
| 4.7 | Each provider card | usage line + spend-share bar; local providers read "No API cost" | ✅ `92-` |

**Three refusals that used to block this are gone** — see `TO_BE_FIXED.md`
**FIXED-05**. Configuring a provider is the owner's authorization, the endpoint
configured is authorised with it, and the vault key provisions itself.

**Still refused** (each covered by a test): a provider that was never configured;
a host belonging to no configured provider; a capability gate the owner
*explicitly* turned off; another principal's connections; every deferred
dangerous domain.

Optional hardening still available: set `RAIKER_MODEL_EGRESS_ALLOWLIST` to
pre-authorise hosts before configuring them, and use Settings → Security & Login
to rotate the vault key.

## 5. Chat

### 5.1 A real streamed turn

| # | Step | Expected | Result |
|---|---|---|---|
| 5.1.1 | Chat → type a prompt → Enter | Right-aligned teal user bubble, "Raiker is thinking…" then a left-aligned neutral reply bubble | ✅ `17-`…`20-` |
| 5.1.2 | Inspect the transcript | No phase labels, no "completed", no cache chips, no model metadata | ✅ (matches the conversational-chat design) |
| 5.1.3 | Console | 0 errors | ✅ |

**Result 2026-08-01:** Anthropic and OpenRouter credentials were added only
through their Connect dialogs. Ollama discovered nine models, selected
`gemma4:31b-cloud` globally, and returned the exact requested live reply.
Evidence: `working/194-live-gemma4-31b-cloud-turn.png`. The Ollama connectivity
message was duplicated under unrelated hosted-provider cards; configured-state
evidence is `working/195-live-provider-setup.png`, and the placement defect is
tracked as BUG-47.

### 5.2 Does a new chat appear on the left?

**Yes.** A **RECENT CHATS** group appears in the sidebar with the chat title and
a relative timestamp, plus a `⋯` row menu (Copy local link, Rename, Move to
project, Pin, Archive, Delete). `25-sidebar-recent-chats.png`,
`75-session-row-menu.png`.

### 5.3 Is chat searchable?

**Yes.** Search Chat matches on title **and message text** and offers "Open
conversation →" to resume. Searching `codeword` returned the 2 matching
conversations with turn counts. `26-`, `27-`.

### 5.4 Does a conversation remember its context?

**Yes, after the fix in this round.** ❌→✅ Originally, asking a follow-up in the
**same** chat produced *"I don't have any record of you providing me with a
codeword in our conversation history. This is the first message in our current
session."* — the transcript rendered on screen but prior turns were never sent to
the provider (`not-working/BUG-02-no-conversation-memory.png`).

Re-run on a bare workspace:

| Step | Reply |
|---|---|
| "Remember this codeword: MARIGOLD-42. Reply with just OK." | `OK.` |
| "What was the codeword I gave you? Answer with just the word." | `MARIGOLD-42` ✅ |
| **New chat** → "What codeword did I give you earlier? If you have none, say NONE." | `NONE` ✅ |

Memory within a conversation, isolation between conversations.
`working/96-conversation-memory-fixed.png`,
`working/97-cross-chat-isolation.png`. See `TO_BE_FIXED.md` **FIXED-04**.

### 5.5 Can you see how many tokens remain, and what they cost?

**Yes, after the fixes in this round.** ❌→✅ The popover originally opened at
`0 / NaN (NaN%)` with `aria-valuenow="NaN"`
(`not-working/BUG-01-context-window-NaN.png`); see `TO_BE_FIXED.md`
**FIXED-02**.

It now reads, against a live Anthropic turn:

```
Context window                    2.9K / 200.0K (1%)
Provider-reported usage. Capacity provider-reported.
This chat                                   $0.0030
anthropic, all time                         $0.0059
claude-haiku-4-5-20251001 — list price, as of 2026-07
```

Verified: capacity is pulled from Anthropic's own `max_input_tokens` rather than
configured; used tokens are the provider's reported prompt count; the all-time
figure accumulated correctly across a Chat turn and a Build turn; a local
profile shows *"Runs on this machine — no API cost"*; and a model with no
resolvable price says so instead of showing `$0.00`. The identical control is in
the **Build** composer (`93-build-context-cost-popover.png`).
`working/90-chat-context-cost-popover.png`.

### 5.6 Composer controls

| Control | Behaviour | Result |
|---|---|---|
| `+` → Attach | Image… (`png/jpeg/webp/gif`) and Document… (`txt/md/csv/pdf/docx/xlsx`) | ✅ `72-` |
| Document upload | `POST /api/attachments` 200, chip renders, content reaches the model | ✅ `76-`, `77-` |
| Attachment chip | Clicking it opens a view-only preview pane; `Esc`/**Close file preview** dismisses it; a `.md` file's raw HTML shows as text, an `.xlsx` shows its first sheet, a PDF opens in the browser viewer, an uploaded image displays fitted to the pane | ✅ FIXED-10 |
| Voice input | Present and labelled "(coming soon)" | ✅ honest |
| Planning | auto / Always plan / Never plan | ✅ |
| Model | lists only configured profiles; no free-text model id | ✅ matches spec |
| Context | opens/closes only; never compacts | ✅ (values wrong — 5.5) |
| Permissions | ask / safe auto / Custom permissions… → `#/capabilities` | ✅ |
| New chat | disabled while the current chat is empty | ✅ |

### 5.7 Markdown rendering and one-click PDF

**Rendering: fixed.** ✅ Assistant answers in Chat and Build now render through
the sanitising renderer (`apps/web/src/lib/markdown.ts` behind
`components/Markdown.svelte`): headings, nested lists, GFM tables, fenced code
with a language label, blockquotes, rules, and inline code/emphasis/links. The
DOM check that read `h1: 0, table: 0, pre: 0, code: 0, ul: 0` now returns
`h1: 1, table: 1, pre: 1, code: 2, ul: 2` on the same reply, with `img: 0` and
`script: 0` for injected markup. FIXED-06.
`working/83-FIXED-06-chat-markdown-rendered.png` (was
`not-working/BUG-03-chat-markdown-not-rendered.png`).

**Chat file output: fixed.** After a completed turn, **Copy response** still
copies the rendered answer's source Markdown. Chat no longer offers transcript
export or print actions. When a governed chat turn creates a supported file,
Raiker stores a validated owner-scoped preview copy and adds a chip to that
turn; selecting it opens the read-only file inspector beside the conversation.
Unsupported files are not exposed as generic workspace downloads. FIXED-19.

---

## 6. Approvals

| # | Step | Expected | Result |
|---|---|---|---|
| 6.1 | Ask Chat to `write_file` a report | Reply "Your approval is needed to continue" + Review approval link | ✅ `30-` |
| 6.2 | Approvals → Pending | Row: Write file / File writes / high / pending | ✅ `31-` |
| 6.3 | **Review** | Detail with the proposed unified diff, capability, risk, session link, expiry | ✅ `32-` |
| 6.4 | **Approve and execute once** with relay and target gates enabled | Execution result names the file; the pre-image is checkpointed | ✅ FIXED-08; re-verified `live-retention.md` with Ollama `gemma4:31b-cloud` on 2026-07-28 (`102`–`104`) |
| 6.5 | Check the filesystem | `report.md` exists with the reviewed contents | ✅ FIXED-08 |
| 6.6 | Filters Pending / Approved / Executed / Denied, sort by risk / recency | All work | ✅ FIXED-08 |
| 6.7 | Review and approve a unique `edit_file`, then an `apply_patch` unified diff | Each detail shows the calculated diff; each action changes only its matched line | ✅ FIXED-23 (`98`–`101`) |

The 2026-07-28 focused re-check used a disposable workspace and a fresh owner
account. Ollama `gemma4:31b-cloud` proposed one new Markdown file;
**Approve and execute once** reported a checkpointed write. Opening the same
session again rendered the durable `live-retention.md` chip. Browser console:
0 errors. Evidence: `working/102-live-retention-pending.png` through
`working/104-live-retention-reloaded-session.png`.

`edit_file` fails closed when `old_text` is absent or repeated. `apply_patch`
fails closed on malformed, mismatched, or ambiguous hunk context and reports
the rejected hunk without partially writing the file. Its current scope is one
existing text file per action; multi-file/create/delete/fuzzy patches are not
accepted. **B3's defined strict, single-file scope is complete (FIXED-23); its
broader patch-format expansion is not completed and is deliberately deferred.**

Metadata-only resolution remains the safety model for network, process, and
every other non-relayed capability. Approved local file mutations and bounded
shell commands are the deliberate exceptions: they execute once through the
governed relay, with a fresh gate, policy, posture, and checkpoint check. A
terminal shell approval additionally requires a live control/elevated API
session, shows an effect preview, and requires the approval id to be repeated as
an explicit confirmation. Its result includes bounded stdout/stderr, byte
counts, exit status, truncation state, and the resolving principal. See
FIXED-08, FIXED-23, and FIXED-90. Secret-like stdout/stderr is redacted before
display or durable history.

### 6.8 Terminal approval re-check (2026-08-01)

Automated live-workspace probing verified that `/approve <id>` authenticates
and prints the exact argv, workspace cwd, timeout, and output limit without
executing. The isolated account correctly refused the confirmed command while
its Shell and Approval Relay permissions remained off. The managed test
environment blocked the subsequent UI permission change, so the live execution
half remains to be re-run after an owner explicitly authorises those two
disposable-workspace permissions. The full authenticated
preview/confirm/execute/exactly-once path is covered by
`tests/test_terminal_approval_execution.py`.

---

## 7. Tasks — all four work types

Tasks → Plan work → chip row: **Task**, **Schedule once**, **Daily routine**,
**Background agent**.

| Type | Extra fields | Submit label | Result |
|---|---|---|---|
| Task | — | Create task | ✅ ran immediately, finished |
| Schedule once | Start time (`datetime-local`) | Schedule task | ✅ "Scheduled for 8/1/2026, 9:00:00 AM" |
| Daily routine | Start time | Create daily routine | ✅ "Every day, next run 8/1/2026" |
| Background agent | — | Start background agent | ✅ ran, produced a response + checkpoint |

Also verified: nesting under **Parent work** (the parent select is populated
from existing tasks), Priority Low/Normal/High, the `4 open / 4 scheduled /
3 finished` counters, per-task **Stop**, and Observability → Work in action
showing the same records. `34-task-form-*.png`, `35-tasks-all-types-created.png`.

Two blemishes: one background-agent run emitted `Task failed` in the audit log
with no user-facing reason (fixed — FIXED-13: a run's outcome is now classified,
always carries a stated reason, and is shown on the task card and in Work in
action), and task runs create sessions that appear in **RECENT CHATS** alongside
real conversations (fixed — FIXED-15: task runs are tagged `origin=task` and the
recent-conversation lists ask for `origin=chat`).

---

## 8. Permissions / Capabilities

| # | Step | Result |
|---|---|---|
| 8.1 | 62 gates listed, grouped Workspace / Local execution / Network / Models / Connectors / MCP / Automation | ✅ `29-permissions-full.png` |
| 8.2 | Search box filters live | ✅ |
| 8.3 | Expand a row → description + current decision mode + **Turn on** | ✅ |
| 8.4 | Decision modes Ask / Allow / Auto / Deny per capability | ✅ |
| 8.5 | Step-up dialog: reason (required), confirmation token, threat-model ack; **Confirm change** stays disabled until satisfied | ✅ `10-` |
| 8.6 | Enable 25+ gates (File writes, Shell, Web fetch, Network, Subagents, Processes, MCP builder, MCP connector, Memory store/forget, Semantic memory, Vector embeddings, Graph indexing, Audit export, Advisor, Home-lab models, Container, Multi-agent, External channels, Approval relay, Scheduled routines, Reminders, Calendar, Email drafts) | ✅ all 200 |
| 8.7 | Deferred domains (CCTV, finance, medical, pregnancy, home security, hardware, remote/cloud execution) offer **no enable path** | ✅ fail-closed, 42 listed under Diagnostics |

Note the two-step model: with **Development preview** active a gate can only
reach `enabled_policy_gated`; `enabled_runtime` needs a runtime-enablement mode
(§4.1). Surfaces that check `runtime_enabled` (e.g. MCP) stay disabled until
then. The Permissions banner says this; the failing surface now repeats it
instead of claiming the capability is disabled (fixed — FIXED-16).

---

## 9. Adaptive navigation

| Width | Expected | Result |
|---|---|---|
| 375 px | bottom bar + **More** drawer, no left rail | ✅ `70-`, `71-` |
| 768 px | top-bar menu trigger + same drawer | ✅ |
| 1024 px | full sidebar, no drawer trigger | ✅ |
| 1440 px | full sidebar | ✅ |

At every width: **no horizontal overflow**, 0 console errors. The drawer reports
`aria-expanded=true` on open and `false` after **Escape**, and focus returns to
the trigger. Matches `2026-07-18-adaptive-navigation-design.md` exactly.

---

## 10. Extensions

### 10.1 MCP servers

| # | Step | Result |
|---|---|---|
| 10.1.1 | With MCP gates off: form disabled + a notice naming which of the three shut states it is (FIXED-16) | ✅ |
| 10.1.2 | With `mcp_builder_runtime` + `mcp_connector_runtime` at `enabled_runtime`: name a server, pick "Sample echo server (safe starter)", **Create server** | ✅ `POST /mcp/servers` 200 `53-`, `54-` |
| 10.1.3 | **Test** | `connected · 2 tool(s)` — `echo`, `workspace_ping`; monitored session recorded `mcp_connect · 0 tool calls · ok` | ✅ `57-` |
| 10.1.4 | Stop / Resume / Rename / Delete | ✅ present and wired |
| 10.1.5 | **Use an MCP tool from Chat** | ✅ after FIXED-17 — a connected server's tools are offered as `mcp__<server>__<tool>` once the owner raises the `mcp_connector_runtime` decision mode above the default `ask` |

MCP now works as an *agent capability* as well as a management and monitoring
surface. Discovery is fail-closed (gate off, never connected, or contained ⇒ no
tools offered), the decision mode is what permits a call, and the tool's output
reaches the model as untrusted data while the audit trail keeps metadata only.

### 10.2 Connectors

26 connectors listed with four independent facts (installed / connected /
enabled / usable). The readiness counters correctly read **0 usable** on a fresh
workspace. `40-`.

---

## 11. Observability

All six tabs verified: Overview (readiness, 62 closed gates, pending approvals,
open work, unread notifications, "What changed?" feed), Audit log (append-only,
filterable by session and event type, session ids redacted), Checkpoints
(metadata-only snapshots, "Preview restore impact"), Diagnostics (runtime mode,
5 sessions / 580 events / 9 checkpoints / 12 tasks, readiness checks, per-profile
provider status, 42 deferred capabilities), Work in action, Notifications.
`44-` … `49-`.

---

## 12. Settings

Six tabs: General (language ×5, region, default startup view, runtime mode),
Notification, Personalisation, Storage, Security & Login (vault key, MFA
enrolment, credential security scan, breach check opt-in, password change,
13 active device sessions with per-row Revoke, standing approval grants),
Account. `12-`, `13-`.

---

## 13. Global chrome

| Control | Result |
|---|---|
| Theme toggle | cycles system → light → dark → system; `data-theme` follows; both themes render every view correctly (`61-`…`63b-`) |
| Notification bell | unread count badge; panel with "Mark all read"; matches Observability → Notifications (`64-`) |
| STOP switch | confirm dialog "Stop all active tasks? … It is governed and audited — not a force-kill" (`65-`) |
| Skip to content | present and first in tab order |
| Sidebar scrolling | independent scroll region; transcript scrolls without moving the composer |

---

## 14. Projects

Create project → `POST /api/projects` 200 → card with
`projects/manual-test-project · 0 sessions`, actions Set active / New chat /
Details / Archive / Move / Delete, plus a folder tree. Sessions can be moved in
from the session `⋯` menu. `73-`, `74-`.

---

## 15. Answers to the questions this round was asked

| Question | Answer |
|---|---|
| Does a new chat create a chat on the left? | **Yes** — RECENT CHATS, with a row menu |
| Is the chat searchable? | **Yes** — titles and message text |
| Do conversations remember context? | **Yes** (was broken; FIXED-04) — prior completed turns are replayed, bounded by the model's window; other chats are never mixed in |
| Can you see how many tokens remain? | **Yes** (was `0 / NaN (NaN%)`; FIXED-02) — provider-reported usage against a provider-reported capacity |
| Can you see what a chat has cost? | **Yes** — per-chat and provider all-time, in Chat and Build, for API-key providers only |
| Can you generate a markdown file and view it in the sidebar? | **Yes** — a supported file created by a governed chat turn is stored as a session-authorized preview and opens in the right-hand inspector (FIXED-19) |
| Can you convert markdown to PDF in one click? | **Not from the chat transcript** — transcript export/print controls were removed; generated PDF files open in the right-hand inspector when supported (FIXED-19) |
| Do the different task types work? | **Yes** — all four create, schedule, and run |
| Can you set an API key from the web app? | **Yes** — Connect, paste, done. No gate, allowlist, or vault-key setup first (FIXED-05) |
| Does the MCP server work? | **Yes** — create/connect/monitor, and its tools are callable from Chat under the owner's decision mode (FIXED-17) |
| Do Permissions / Capabilities work? | **Yes** — all 62 gates, four decision modes, step-up enforced |

---

## 16. Re-running this plan

```bash
# from a clean workspace
rm -rf /tmp/raiker-manual-test && mkdir -p /tmp/raiker-manual-test
export RAIKER_MODEL_EGRESS_ALLOWLIST='api.anthropic.com'
.venv/bin/raiker-web --workspace /tmp/raiker-manual-test --port 8765 --no-browser
```

Then work §2 → §14 in order. The plan is deliberately ordered so that each
section's preconditions are satisfied by the sections before it.
