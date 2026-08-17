# Reference Platform Compatibility Mapping

This document maps Raiker concepts to the reference systems and concepts used to shape the full platform specification.

Raiker is not a clone of any one system. It combines local-first agent runtime, coding-agent UX, hooks, plugins, channels, memory, graph context, local inference, self-improving skills, eidetic-style recall, and GenAI security into a governed architecture.

---

## Claude Code Concept Coverage

| Reference concept | Raiker specification |
|---|---|
| Agentic coding loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tools reference | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Interactive mode | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Rich terminal UX | `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Checkpointing | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Hooks | `docs/HOOKS_SPEC.md` |
| Plugins | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Channels | `docs/CHANNELS_SPEC.md`, `raiker/config/channel-connectors.json` |
| Commands | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| TUI-first command reference | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md` |
| Session events | `docs/HOOKS_SPEC.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tool events | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/HOOKS_SPEC.md` |
| Permission requests | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Subagents/tasks | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Worktrees/execution | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Context compaction | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |

### Claude Code documentation — per-page mapping

Each reference page named in the review brief maps to a Raiker spec and a current code status.
Status: ✅ implemented · 🟡 partial/stub · 🔒 phase_scheduled_disabled · 📘 specified_not_implemented.

| Reference page | Raiker spec | Code status |
|---|---|---|
| `how-claude-code-works` (gather→act→verify loop, harness) | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/RUNTIME_STATE_MACHINE.md` | ✅ loop real; 🟡 verify/context stubs |
| `tools-reference` (built-in tools + permission per tool) | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | ✅ read tools; write/shell approval-gated |
| `interactive-mode` (REPL, shortcuts, steer/interrupt) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | ✅ basic REPL |
| `commands` / slash commands (built-in + custom) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | ✅ 50+ inspection commands |
| `cli-reference` (flags: `--prompt`, `--workspace`, resume/fork) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `README.md` | 🟡 `--prompt`/`--workspace` only |
| `checkpointing` (snapshot before edit, rewind, restore code/convo) | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` | 🟡 write real; restore plan-only |
| `hooks` (31 events; `command|http|mcp_tool|prompt|agent`; matchers; `if`) | `docs/HOOKS_SPEC.md` | 📘 spec only, no code |
| `plugins-reference` (`plugin.json`; skills/agents/hooks/MCP/LSP/monitors; marketplace) | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/PLUGIN_MANIFEST_SCHEMA.md` | 🔒 manifest validation only |
| `channels-reference` (MCP `claude/channel` capability; `notifications/claude/channel`; sender gating; permission relay) | `docs/CHANNELS_SPEC.md`, `raiker/config/channel-connectors.json` | 🔒 registry only |

> Alignment notes: the Claude Code hooks reference documents **31 events** (incl.
> `SessionStart`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `PreCompact`, `PostCompact`,
> `SubagentStart/Stop`, `TaskCreated/Completed`) and **5 handler types**
> (`command`, `http`, `mcp_tool`, `prompt`, `agent`) with a three-level
> `EventName → matcher → hooks[]` config and an optional `if` condition. The channels reference
> models a channel as a **local MCP server** that declares `claude/channel`, emits
> `notifications/claude/channel`, gates inbound by **sender identity** (not room), and can opt
> into **permission relay** via `claude/channel/permission`. Raiker's specs should converge on
> these shapes; see `docs/HOOKS_SPEC.md` and `docs/CHANNELS_SPEC.md`.

---

## Claude Cowork Coverage — delegated Tasks and Schedule

Cowork's two organising ideas are a **Task** (work handed to the agent that
outlives the message you handed it in) and a **Schedule** (that work re-armed on
a cadence). Raiker has both, and the difference is where they run.

| Cowork concept | Raiker behaviour | Code |
|---|---|---|
| Delegate work that outlives the turn | Task rows with progress, a safe-boundary stop, and a finished list stating how each run ended | `raiker/tasks/manager.py`, Tasks view |
| Task parked on a decision | A run waiting on an approval reads as **blocked** with the reason and a link to the decision — not as failed | `raiker/tasks/scheduler.py`, Approvals |
| Recurring schedule | Four named cadences — `continuous` (20 min), `hourly`, `daily`, `weekly` — re-armed after every cycle, so a standing agent keeps working until stopped | `RECURRING_INTERVALS`, `raiker/tasks/scheduler.py` |
| Missed-slot behaviour | `next_run_after` steps from the owner's original slot and skips elapsed ones, so a host that was asleep does not wake owing a backlog | `raiker/tasks/scheduler.py` |
| One cycle = one governed turn | Every cycle passes policy, gates and approvals exactly like a typed prompt; `continuous` is the floor, never an unbounded loop | `raiker/tasks/scheduler.py` |
| Background agents in Build | Scheduled agents and a collapsible background-work rail | Build view |

**Raiker difference.** A scheduled cycle is a governed turn with a named human
owner, not a service account: it is attributable, approval-gated, and auditable
on the same event log as a typed prompt, and an unknown cadence is refused rather
than coerced.

**Where Raiker is behind, and it is structural.** Cowork's schedules run on
someone else's computer; Raiker's run on yours.

- **A schedule only fires while `raiker-web` is running.** The 15-second tick
  that calls `run_due` lives in the FastAPI app's lifespan
  (`raiker/api/app.py`), so a closed laptop is a missed cadence — recorded
  honestly by the skip-elapsed rule, but missed. There is no hosted runner and
  no OS-level scheduled task registration.
- **`scheduled_routines` has no runner at all.** That capability is on-demand by
  construction — *"There is NO background daemon/thread/watcher — the owner (or
  an external trigger) calls `run_due`"* — so it is a governed routine store with
  a manual trigger, not a scheduler.
- **Cadences are four names, not a time.** There is no arbitrary time-of-day, no
  cron expression, no timezone binding, and no one-shot "run once at 17:00". A
  daily task runs a day after whenever it was created.
- **No notification out.** A cycle that finishes while nobody is looking updates
  the Tasks view and the audit log; it does not reach the owner.

---

## OpenClaw-Style Personal Agent Coverage

| Concept | Raiker specification |
|---|---|
| Local-first gateway/control plane | `docs/ARCHITECTURE.md`, `docs/CHANNELS_SPEC.md` |
| Multi-channel inbox | `docs/CHANNELS_SPEC.md`, `raiker/config/channel-connectors.json`, `docs/UI_UX_DESIGN_SPEC.md` |
| Channel pairing and sender allowlists | `docs/CHANNELS_SPEC.md`, `docs/SECURITY_AND_POLICY.md` |
| Channel-to-agent routing | `docs/CHANNELS_SPEC.md`, `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Gateway daemon mode | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Voice wake/talk mode equivalent | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Live canvas/workspace equivalent | `docs/UI_UX_DESIGN_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Companion apps/nodes | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Onboarding and connector setup | `docs/CHANNELS_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| Skills from bundled/global/workspace scopes | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Channel security diagnostics | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/VERIFICATION_PLAN.md` |

---

## Hermes-Agent / Agent Framework Coverage

| Concept | Raiker specification |
|---|---|
| Tool-using agent loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Model-router/provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `raiker/config/model-profiles.json` |
| Global `raiker` TUI entry and in-TUI provider launch | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Structured tool proposal | `docs/CONTRACTS.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Verification/reflection | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Local-first inference support | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Full TUI with streaming output | `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Interrupt and redirect | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Cross-channel conversation continuity | `docs/CHANNELS_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Closed learning loop | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill creation and skill improvement | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Full-text session search with summaries | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| User modelling from confirmed facts | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Scheduled automations | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| Parallel subagents | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Multiple execution backends | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |

---

## Turn transparency control set — what a turn says it did, and what it thought

Reviewed 2026-08-15 while closing BUG-206 and BUG-207, against the transcript
surfaces of **Claude Cowork**, **Claude Code**, **ChatGPT**, **Codex**,
**OpenClaw** and **Hermes Agent**. Scope is only what a running turn shows about
its own work: the calls it made, and the reasoning behind them. Nothing here is
implemented unless the Raiker column says so.

| Control | Reference behaviour | Raiker | Code |
|---|---|---|---|
| A line per tool call while the turn runs | Every reference product shows one | ✅ `[icon] [tool] [action]`, in the model's proposal order | `raiker/tools/broker.py::_stream_tool`, `ToolActivity.svelte` |
| The tool named in the owner's language | Claude Code and Codex print the identifier (`Read`, `Bash`); ChatGPT and Cowork use a phrase | ✅ a phrase (`Read file`, `Run command`), never the identifier | `raiker/tools/presentation.py` |
| What the call acted on | Claude Code shows the path and the full command line; ChatGPT shows a domain | ✅ path, host, program, query — **resolved server-side and redacted first** | `_action_phrase` |
| An icon per tool family | Claude Code, Cowork, ChatGPT | ✅ nine families plus a neutral fallback, so an unknown tool renders as a tool | `icons.ts`, `FAMILY_ICON` |
| A call still running says so | All | ✅ a quiet pulse in the glyph's place, so the row does not resize when it settles | `ToolActivity.svelte` |
| A failed call says why, inline | Claude Code, Codex, Hermes | ✅ the named reason on the row, with a remediation link where one exists | `_failure_reason` |
| A refused call is a row, not a separate block | Claude Code (`permission denied` inline) | ✅ the same row in a refused state, in the place it was refused | BUG-206 slice E |
| A call waiting on a decision says so | Claude Code, Cowork | ✅ `waiting for your decision`, beside the approval card that resolves it | `_stream_tool_waiting` |
| The model's own reasoning, live | ChatGPT (summarised), Claude Code (`thinking`), Codex, Cowork | ✅ collapsed block above the answer, collapsing when the answer starts | `ReasoningBlock.svelte` |
| Reasoning is the provider's, not the product's | All | ✅ `display: summarized` asked for wherever the profile declares it | `AsyncAnthropicMessagesProvider._thinking` |
| No reasoning ⇒ no block | ChatGPT, Claude Code | ✅ absent, never an empty one and never a placeholder | `collectReasoning` |
| Reasoning survives a reload | ChatGPT, Claude Code, Cowork all retain it, and none asks | ✅ retained **on the owner's decision** (Settings → Privacy), and a turn whose working was not kept says so rather than showing nothing | BUG-215: `record_turn_reasoning`, `ReasoningBlock.svelte` |

**Where Raiker leads, and why it is worth keeping.**

| Control | Why no reference product has it | Where it is |
|---|---|---|
| A transcript row that **cannot say more than the audit log** | Every reference product assembles its row in the client from the raw tool arguments it already has in memory. Raiker resolves the phrase server-side, through the same redaction the durable event passes, so the two surfaces cannot drift and a leak cannot be a client bug | shipped: `raiker/tools/presentation.py` is the only place that decides |
| A URL narrowed to its **host**, and a command to its **program** | Claude Code prints the whole command line and ChatGPT the whole URL. A signed URL carries its credential in the query string, in a shape pattern-based redaction reads as ordinary base64; a command argument can be a password. Both stay in full in the event, where they are evidence, and out of the line an over-the-shoulder reader sees | shipped |
| A tool whose **arguments are dropped from the event** derives no phrase either | `consult_advisor` and projected MCP tools have their argument values scrubbed from the durable record. The transcript is held to the same rule rather than being the looser surface | shipped |
| **Proposal order**, not completion order | Independent reads run concurrently (B4), so the events arrive in whatever order the worker threads finished. The rows are opened from the validated proposals, so the turn reads in the order the model asked | shipped: `_stream_tool_proposed` |
| A row surface **guarded against silent drift** | The row exists in two languages and the failure is silent: a family with no glyph renders the fallback, which is what the fallback is for. No reference product can check this, because none resolves the row on the server in the first place | shipped: two tests comparing the family tables in both directions, confirmed to fail when the drift is introduced |
| The thinking request shape **negotiated with the model**, not declared | A provider profile declares one reasoning mode for every model behind it. Measured against the live Anthropic catalogue on 2026-08-15, five models refuse `thinking.type.enabled` and three refuse `thinking.type.adaptive`; a static declaration fails the whole turn with a 400 for whichever half it is wrong about | shipped: the provider records the spelling the refusal names and re-issues once |
| Retention of the model's working is the **owner's decision**, and its absence is **stated** | ChatGPT, Claude Code and Cowork all keep the reasoning they show, and none offers a way not to. The model's working can restate anything the prompt contained and is the one part of a turn an owner may specifically not want on disk, so Raiker keeps it only on an explicit setting — and records *how much* working a turn produced either way, so a re-opened turn says **the working was not kept** rather than reading as a turn that never thought | shipped (BUG-215): `turns.reasoning_chars` is always written, `turns.reasoning_text` only when Settings → Privacy says so |
| Retained working is **excluded from search and export by construction** | A product that retains reasoning generally indexes and exports it with the rest of the conversation | shipped: `conversation_fts` projects `prompt_text` and `summary` only, and `build_transcript` reads the same two fields — the exclusion is the shape of the code, not a filter that can be forgotten |

**What a reference product does that Raiker does not.** Each is open work with a
reason rather than an oversight; each is recorded in `plans/TO_BE_FIXED.md`.

| Missing control | Who has it | What it would take |
|---|---|---|
| Tool rows that survive a reload | ChatGPT, Claude Code, Cowork | Reasoning now rehydrates from the turn row (BUG-215); the tool rows still rebuild from the stream. The durable events the Audit view reads already hold them, so this is a governed read-back of the per-turn event slice rather than a new record |
| A tool row that expands into its result | Claude Code, Codex | The row is deliberately a summary; the result is in the Audit log. An expander would need a governed read-back of the redacted result payload, not the raw one the model saw |
| Live output from a long-running command | Claude Code, Codex, Hermes | Blocked on the same background execution BUG-194 describes: there is no run to stream from until a supervisor owns it |
| Token and time cost per call on the row | Codex | Per-call attribution needs the provider to report it, which none of Raiker's do at call granularity; per-turn cost is already shown |

**Ideas that go beyond every reference product, not yet built.** Recorded so the
list is a decision rather than a gap: a row that names the **capability** a call
crossed rather than only the tool, so an owner reading a turn sees the governed
shape of it; a per-turn *diff* of what the calls changed, assembled from the
checkpoints already written before each write; and a reasoning block that marks
the sentences the answer actually acted on, since the runtime already ledgers the
sources a turn read.

---

## Composer control set — how a prompt is written, corrected and re-run

Reviewed 2026-08-16 while closing GAP-BUILD **B19** and GAP-CHAT **C14**,
against the composer surfaces of **Claude Cowork**, **Claude Code**,
**ChatGPT**, **Codex**, **OpenClaw** and **Hermes Agent**. Scope is only the box
a prompt is written in and the actions on a message already sent. Nothing here
is a claim about the rest of those products, and nothing is implemented unless
the Raiker column says so.

Two composers, two reference bars, deliberately: **Chat** is measured against
the Claude and ChatGPT assistant composer, **Build** against the Claude Code and
Codex coding-agent composer. They share one implementation
(`apps/web/src/lib/composerCommands.ts`) so the two keyboards cannot drift into
two different products, and differ only where the surfaces genuinely differ.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Reference behaviour | Raiker | Status |
|---|---|---|---|
| Slash commands | Claude Code (`/model`, `/clear`), Codex, ChatGPT, OpenClaw all open a command menu on `/` | `/` at the start of the prompt opens a filtered menu; each entry runs a control the surface already has. Chat carries `/export`, Build carries the three modes, `/terminal` and `/repos` | ✅ |
| A listed command that really runs | Reference products list only working commands | Every entry dispatches to an existing control, checked by a test that walks the whole set. There is no "coming soon" row — an inert menu item is a promise the product does not keep | ✅ beyond |
| `@`-mention file completion | Claude Code and Codex complete workspace paths; ChatGPT and Cowork complete uploaded files and connectors | `@` completes against the **code map the owner built**, paths and languages only, behind the same `code_map_indexing` gate as every other map read | ✅ |
| A completion that cannot become a listing surface | Claude Code and Codex read the working tree directly | `GET /api/code/map/paths` reads the index the owner explicitly built, never the filesystem, and returns no symbols, no line numbers and no content. It can name nothing the owner's own indexing run did not already accept | ✅ beyond |
| An empty menu that says which emptiness it is | None distinguish them | A map that was never built answers `code_map_not_built` with the control that fixes it; a gate that is off answers `code_map_gate_disabled` with the Permissions link. "Nothing matched" and "nothing could match" send the owner to different places | ✅ beyond |
| Auto-growing prompt box | Claude, ChatGPT, Claude Code | Grows with the text to a ceiling, then scrolls | ✅ |
| Keyboard map, in the product | Claude Code (`/help`), Codex, OpenClaw | `/shortcuts` and a composer link open a per-surface sheet built from `shortcuts()`, which lists only bindings the handlers implement | ✅ |
| Mode cycling from the prompt | Claude Code cycles plan / accept-edits with Shift+Tab | Shift+Tab cycles Plan → Edit → Auto, and the modes are enforced by the runtime rather than by prompt wording | ✅ |
| Stop a running turn from the composer | Claude Code (Esc), Codex, ChatGPT | Stop and steer controls plus `/stop`, all on the same governed `POST /api/interrupts` | ✅ |
| Copy a message | All | Copy on the owner's own message, and per-code-block copy in the answer | ✅ |
| Edit a prompt and send it again | ChatGPT, Claude, Cowork | Edit puts the prompt back in the composer. It does **not** rewrite the transcript: the original turn stays and the edited one is a new turn | ✅ beyond |
| Retry / regenerate | ChatGPT, Claude, Claude Code | Retry sends the same prompt again as a new turn, under whatever mode is selected now | ✅ |
| Attachments from the composer | All | Upload, workspace path, drag-and-drop, with the same governed store both surfaces share | ✅ |
| Queue a message while a turn runs | Claude Code, Codex | Steer queues the owner's words into the running turn, arriving as a user message before the model is asked anything else | ✅ |
| `!` bash prefix and `#` memory prefix | Claude Code | ❌ absent. Both would be a second route into governed execution and governed memory writes, beside the approval path that exists — the "one governed route" rule the shell control set is built on | ❌ by decision |
| Branch a conversation from a message | ChatGPT, Claude | ❌ absent. Checkpoints already record the point to branch from; the missing part is a conversation-fork surface, tracked as C14 | ❌ |
| Voice input | ChatGPT, Claude mobile | ❌ absent, and labelled as absent rather than "coming soon" (C16) | ❌ |

**Where Raiker leads, and why it is worth keeping.**

| Control | Why no reference product has it | Where it is |
|---|---|---|
| A completion menu that **reads an index, not a disk** | Every reference coding agent completes `@` against the live working tree, so the completion surface is as wide as the process's filesystem access. Raiker completes against the map the owner chose to build, under the same gate, and returns paths only — so the autocomplete cannot be a wider read than the tool it feeds | shipped: `CodeMapService.complete_paths` |
| **One command vocabulary** across an assistant and a coding agent | Claude and Claude Code are separate products with separate keyboards; ChatGPT and Codex likewise. Raiker's two surfaces resolve their commands through one module, so `/model` and `@` behave identically and a test proves each surface offers only commands it can run | shipped: `composerCommands.ts` |
| An edit that **adds a turn instead of replacing one** | ChatGPT and Claude replace the edited message and discard what followed it. For a governed agent the transcript is evidence — a record that quietly changes what was asked is not one — so the original turn stays and the edit is a new turn beneath it | shipped: `MessageActions.svelte` |
| A slash command that **grants nothing** | In every reference product a command is a privileged path into the harness. Here each one opens a control the owner already has; there is no command that raises a capability, skips an approval, or reaches the model with more authority than typing would | shipped, by construction |

**What a reference product does that Raiker does not.** Each is open work with a
reason, not an oversight.

| Missing control | Who has it | What it would take |
|---|---|---|
| Custom, owner-authored slash commands | Claude Code, Codex, OpenClaw | The skill store already holds owner-authored instructions with a review path. A command is that plus a trigger token, and the honest version has to state what authority the command carries — which is what makes it a design task rather than a parser change |
| `@`-mention of a connector, a memory or a past conversation | ChatGPT, Cowork | Each is a different governed read with its own gate. One completion menu over four authorities needs the menu to say which one a row would use, or it becomes a way to reach a capability without noticing |
| Inline file preview from a mention | Claude Code, Cowork | Chat has an inspector for attachments; Build has none, and giving it one is B13 rather than a composer change |
| Branch-from-here | ChatGPT, Claude | A conversation fork over the existing checkpoint manifest, plus a surface that makes two branches of one conversation legible |

**Ideas that go beyond every reference product, not yet built.** Recorded so the
list is a decision rather than a gap: a slash command that shows **which
capability gate** it would cross before it runs, so an owner sees the governed
shape of a shortcut; an `@`-mention that reports the file's **index freshness**
beside it, since the code map already records when each path was last parsed;
and a composer that names the **standing grants in force** for the mode selected,
rather than leaving the owner to read Permissions in another route.

---

## Turn continuation and command attribution control set

Reviewed 2026-08-16 while closing BUG-196 and BUG-197, against the
long-running-work surfaces of **Claude Cowork**, **Claude Code**, **ChatGPT**,
**Codex**, **OpenClaw** and **Hermes Agent**. Scope is only what a surface says
about a turn that parked on a decision, and what a command run says about where
it ran.

| Control | Reference behaviour | Raiker | Status |
|---|---|---|---|
| A decision made elsewhere continues the turn | Cowork and Claude Code continue work approved from another surface | ✅ broadcast plus an authenticated poll; the server's atomic claim decides | ✅ |
| Losing the race to continue is **not an error** | Reference products generally serialise on one client and do not surface the race | ✅ a refusal that means "already acted on" is reported as continued, never as a failed turn | ✅ beyond |
| A refused stream carries its **reason**, not just a status | Reference products surface a generic failure for a refused stream | ✅ the streaming path parses the same `reason_code` the plain path does, so a lost race, an unrecorded decision and an unreadable parked state are told apart | ✅ beyond (BUG-196) |
| The turn's own state decides what the owner is told | — | ✅ a turn already carrying a finished response reports nothing, whatever refused a later duplicate attempt | ✅ beyond |
| A run names where it ran, while it is running | Claude Code and Codex name the sandbox in their activity view | ✅ the backend is written to the run at start, so the browsable row and the immutable receipt agree from the first moment | ✅ (BUG-197) |

Raiker difference: the race a parked turn creates is **designed for rather than
avoided**. Every reference product with cross-surface approval serialises on a
single client and treats a conflict as an error; Raiker lets both clients try,
resolves it atomically in the store, and holds the interface to the rule that a
turn which completed must never report that it could not.

---

## Model readiness and acquisition control set

Reviewed 2026-08-09 while closing BUG-69, against the model-selection and
model-readiness controls of **Claude Cowork**, **Claude Code**, **ChatGPT**,
**Codex**, **OpenClaw**, and **Hermes Agent**. Scope is only the model control
set: how each system lets an owner pick a model, prove it works, learn why it
does not, and obtain one. Nothing here is a claim about the rest of those
products.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Reference behaviour (where it exists) | Raiker | Status |
|---|---|---|---|
| Global default model | Claude Code `settings.json → model`; Codex `config.toml → model`; ChatGPT account default | Models → Global model | ✅ |
| Per-turn / per-conversation model | Claude Code `/model`; ChatGPT per-conversation picker; Codex `-m` | `ModelPicker`, `/model use` | ✅ |
| Per-task / scheduled-run model | Claude Code subagent frontmatter `model:`; Codex profiles | `model_profile` + `model` on a task, rechecked at run time | ✅ |
| Per-surface default model | None — Claude Code, ChatGPT and Codex each hold one session/global model | Chat, Build, Tasks and Schedule each remember their own (`/api/surface-models`) | ✅ beyond |
| Several local models serving at once | Codex `--oss` runs one Ollama model; none manage concurrent local servers | Four managed llama.cpp slots, own port and served name each, plus Ollama/LM Studio multi-model endpoints | ✅ beyond |
| A starting point before the first search | LM Studio and Ollama show curated/trending models | Hugging Face opens on the most-downloaded GGUF repositories | ✅ |
| Ordered fallback model | Claude Code `--fallback-model`; OpenClaw provider fallback | Owner-ordered fallback sequence, readiness-judged as one chain (Task 13) | ✅ |
| Custom OpenAI-compatible provider | Codex `model_providers` (base URL, env key, headers) | `generic-openai-compatible` plus a custom endpoint on any card | ✅ |
| Credential entry and storage | Claude Code `/login` / API key; Codex `env_key`; ChatGPT account | Connect dialog → encrypted vault; never on argv or in logs | ✅ |
| Exact-model reachability check | Claude Code `/doctor`, `/status`; OpenClaw `doctor` | `POST /api/model-readiness/check`, per exact owner/profile/model/endpoint | ✅ |
| Distinct billing / quota exhaustion | ChatGPT usage caps; Claude Code credit-balance and usage-limit messages; Codex quota errors | `quota_exhausted` state and `provider_quota_exhausted` code (Task 13) | ✅ |
| Distinct auth failure | All | `authentication_failed` | ✅ |
| Refuse work before submission when nothing is ready | None — all four coding agents fail at call time | Fail-closed gate on Workbench, Chat, Build, Tasks, Schedule, and background runs, draft preserved | ✅ beyond |
| Guided first-run model setup | ChatGPT desktop quickstart; OpenClaw and Hermes provider onboarding | Resumable instance/model/privacy/backup/finish wizard; configured models must pass exact readiness before completion, while defer remains explicit | ✅ |
| Context window and capability metadata | Claude Code `/context`; Codex `model_context_window`; ChatGPT model descriptions | Discovered capacity with its source, Details drawer | ✅ |
| Cost and usage per model | Claude Code `/cost`; ChatGPT usage | Pricing tab, per-profile spend | ✅ |
| Reasoning-effort control | Codex `model_reasoning_effort`; Claude Code thinking levels | `reasoning_effort` validated against the exact profile's declared values | ✅ |
| Local runtime install / connect | Codex `--oss` (Ollama) | Vendor-sourced install plans for Ollama, LM Studio, llama.cpp; never bundled | ✅ beyond |
| Model acquisition (pull / download / convert) | Codex pulls via Ollama | Ollama pull, revision-pinned Hugging Face GGUF download, isolated Safetensors→GGUF conversion | ✅ beyond |
| Readiness of a secondary / auxiliary model | Claude Code `ANTHROPIC_SMALL_FAST_MODEL` | Advisor model resolves through the same per-profile pin as the chat chain, carries a readiness observation under its own exact key, and shows the chip, the exact model and **Check advisor** beside the selector (FIXED-158) | ✅ |
| Continuous / background revalidation | ChatGPT and Claude Code re-check per request | Owner-set window (1–120 minutes, default 5) plus opportunistic background revalidation while a work surface is open; the invalidation hooks stay authoritative over the timer (FIXED-169) | ✅ |
| Single-provider live acceptance run | n/a | Each provider leg is skipped when its key is absent; the run fails only with no key at all, and asserts the readiness state machine rather than one account's entitlement (FIXED-170) | ✅ |

Raiker difference: readiness is **exact and pre-submission**. Every reference
system above lets an owner select a model that cannot run and discovers the
problem when the request fails. Raiker binds readiness to the exact
owner/profile/model/endpoint tuple, persists the observation with a short TTL,
and refuses to create a turn, task, schedule, or background run until something
in the resolved chain is proven ready.

---

## Desktop onboarding, host control, governed work and portable evidence

Reviewed 2026-08-11 while designing BUG-46, BUG-48, BUG-51, BUG-60, BUG-64,
BUG-65 and BUG-88, against the applicable desktop, setup, approval, scheduling
and evidence controls of **Claude Cowork**, **Claude Code**, **ChatGPT**,
**Codex**, **OpenClaw**, and **Hermes Agent**. Scope is only this control set;
nothing here is a claim about the rest of those products.

Primary sources: [Claude Cowork setup](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork),
[Claude Cowork scheduled tasks](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork),
[Claude Code Desktop](https://code.claude.com/docs/en/desktop),
[Claude Code permissions](https://code.claude.com/docs/en/permissions),
[ChatGPT/Codex desktop app](https://learn.chatgpt.com/docs/app),
[ChatGPT/Codex permissions](https://learn.chatgpt.com/docs/permission-modes),
[ChatGPT scheduled tasks](https://learn.chatgpt.com/docs/automations),
[Codex approvals and sandboxing](https://learn.chatgpt.com/docs/agent-approvals-security),
[OpenClaw onboarding](https://docs.openclaw.ai/start/wizard),
[OpenClaw Control UI](https://docs.openclaw.ai/web/control-ui),
[OpenClaw Windows Hub](https://openclaw.ai/), and
[Hermes quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart).

Status: ✅ at parity or beyond · 🟡 partial / designed · ❌ absent.

| Control | Reference behaviour (where it exists) | Raiker | Status |
|---|---|---|---|
| No-terminal desktop first run | ChatGPT and Claude Desktop install and onboard in-app; OpenClaw Windows Hub exposes setup; Hermes ships a desktop installer | Self-contained payload and five-stage in-app wizard; no Python, Node, terminal, or environment editing | ✅ |
| Provider choice proven by a real call | OpenClaw tests detected/selected inference before continuing; Hermes says to verify a clean chat before adding gateway, cron or skills | Setup invokes exact readiness for the chosen owner/profile/model/endpoint before completion; defer is explicit | ✅ |
| Native host presence and lifecycle | Claude/ChatGPT Desktop are resident applications; OpenClaw Windows Hub exposes native tray controls | Native tray uses a one-time, host-control-only session and the same Open/Pause/Restart/Quit routes as the web Host control | ✅ |
| Technical boundary separate from approval policy | Codex separates OS sandbox mode from approval policy; Claude Code combines ordered permission rules with OS sandboxing | Policy engine, capability gates and execution environments are separate runtime layers | ✅ |
| Deny/withhold is runtime-visible | Claude Code exposes tool activity and permission decisions; OpenClaw persists approval decisions and resolver attribution | Every executor-level withheld call emits a runtime-authored refusal event/card with source, reason and a Permissions route, independent of model narration | ✅ |
| Configuration shown as authoritative is consumed | Claude Code and Codex document live settings; OpenClaw Labs hides unshipped switches; Hermes Blank Slate writes explicit tool configuration | Dead `denied_actions` was removed; an invariant prevents an action being both allowed and approval-required | ✅ |
| Creating work is distinct from scheduling/running it | ChatGPT and Claude Cowork use explicit Scheduled workflows and manual runs; Hermes separates cron create and run | Owner-authored tasks retain start-now semantics; model-proposed tasks are parked until explicit **Run now** | ✅ |
| Portable evidence resolves its own citations | Reference products keep source-backed work reviewable in the surface; shareable OpenClaw/Hermes diagnostics are sanitized | Each transcript turn exports its portable source ledger; unresolved markers are stripped and counted, and source passages stay local | ✅ |
| Local and exposed traffic have different trust posture | Codex defaults to local sandbox/no network; OpenClaw distinguishes direct loopback control from paired remote devices | Verified direct loopback reads bypass the DoS budget; writes and every public-bind request remain rate-limited, and proxy headers cannot forge loopback | ✅ |
| Database encryption and key-memory lock are stated separately | None of the six reference products exposes this embedded-database distinction | Security reports **Encrypted** separately from **Locked in memory / Degraded**; the lock probe runs in a crash-contained child and never infers memory safety from encryption | ✅ beyond |

Design contract and closure evidence:
[`plans/FIXED_ITEMS.md`](plans/FIXED_ITEMS.md) — FIXED entries for BUG-46, 48,
51, 60, 64, 65 and 88. Implemented and live-verified on Windows on 2026-08-11. Evidence is under
[`plans/screenshots/working/`](plans/screenshots/working/); the SQLCipher host
reports the expected degraded memory-lock posture while database encryption
and application health remain independently verified.

---

## Governed shell, sandbox, environment, and recovery control set

Reviewed 2026-08-14 against the shell and sandbox controls documented by
**Claude Code**, **Codex**, **OpenClaw**, and **Hermes Agent**, and the governed
work surfaces of **Claude Cowork** and **ChatGPT**. Primary sources:
[Codex sandbox design](https://openai.com/index/running-codex-safely/),
[Codex Windows sandbox](https://openai.com/index/building-codex-windows-sandbox/),
[Claude Code sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing),
[Claude Code containment](https://www.anthropic.com/engineering/how-we-contain-claude),
[OpenClaw sandboxing](https://github.com/openclaw/openclaw/blob/main/docs/gateway/sandboxing.md),
[OpenClaw exec approvals](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec-approvals.md), and
[Hermes tools](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/tools.md).

Re-verified live on **2026-08-15** after the native OS sandbox landed
(screenshots prefixed `r0815-` in [`plans/screenshots/working/`](plans/screenshots/working)).

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent. A row is green only
when the current product path and tests prove it; specification alone does not
count, and a **measurement whose control arm failed does not count either**.
Docker was unavailable on the 2026-08-14 Windows live-test host, so the
container command row remains partial even though its automated contract passes.

**How the sandbox rows are proven.** `raiker-command-runner --probe` builds the
real boundary over the real workspace and runs a child inside it that attempts
six things, each against a control arm run *outside* the boundary: the stream
relay, a write inside the workspace, a write to the workspace's parent and to
the user profile, a read of the masked `.raiker`, an outbound connection, and a
**detached** grandchild. Only *outside succeeded and inside failed* counts as
enforcement; *outside failed* is `indeterminate` and never turns a row green.
All six measured `enforced` on the 2026-08-15 Windows host, and the same six are
shown to the owner on the environment card.

| Control | Market bar | Raiker implementation | Status |
|---|---|---|---|
| Technical isolation separate from approval policy | Codex and Claude Code distinguish sandbox boundaries from permission decisions | Execution environment selection, capability policy, approval, and standing grants are independent and all are rechecked at execution | ✅ |
| One governed route for commands | Mature coding agents do not expose an unaudited second shell path | Approved `shell`/`process` and granted `run_command` converge on one `CommandService`; no command-create API exists | ✅ beyond |
| Runtime-authored authority proof | Approval history is visible in reference products | Every run stores its approval or standing-grant kind/id outside encrypted command material and binds it into the receipt digest | ✅ beyond |
| Authoritative environment; no silent fallback | Codex/Claude/OpenClaw keep sandbox selection authoritative | Exact selected profile is probed and used; unavailable container/SSH/Daytona is refused, never rerouted to host | ✅ |
| Explicit host-access posture | Codex exposes full-access/danger modes distinctly | `local_native` is argv-only and shown as **Host access — reduced isolation**, not called a sandbox | ✅ |
| Native OS sandbox | Codex uses a Windows restricted token/AppContainer boundary; Claude Code uses OS sandbox primitives | Packaged `raiker-command-runner`: a **per-run** Windows AppContainer holding one workspace capability and no network capability, a Job Object with `KILL_ON_JOB_CLOSE`, `.raiker` denied and `.git` read-only with protected DACLs re-verified before every launch; bubblewrap on Linux and Seatbelt on macOS. Codex additionally layers a restricted token; Raiker does not yet, and says so rather than letting "AppContainer" stand in for the pair (`r0815-native-sandbox-card.png`) | ✅ |
| Container command sandbox | Claude/OpenClaw support container isolation | Digest-pinned, no-network, read-only/capability-dropped worker with `.raiker` masked, `.git` read-only, and CPU/memory/PID bounds; automated only on this host | 🟡 |
| Persistent environment | Claude Code and OpenClaw can retain a sandbox/session boundary between commands | Current command container is per run; cache identity and reset internals exist but persistence is not exposed or proven | ❌ |
| Foreground output and exit status | All coding-agent references provide it | Split-safe redacted stdout/stderr, total byte counts, truncation, timeout, terminal state, and exit code | ✅ |
| Provider-independent model-to-command path | Market leaders route tool calls consistently across supported model providers | Anthropic (Haiku 4.5), OpenRouter (Gemini 3.7 Flash), OpenAI (GPT-4o Mini) and Ollama (gemma4:31b-cloud) each completed the same live Build → approval → exact-argv command **inside the AppContainer** → output → receipt on 2026-08-15 (`r0815-build-governed-terminal-appcontainer.png`) | ✅ beyond |
| Background start/poll/wait/log/kill | Claude Code, Codex, OpenClaw, and Hermes expose long-running process controls | `run_command background:true` returns a `run_id` without waiting; `background_run` polls, pages the log from a resumable sequence, waits with a bounded timeout, and kills. The enforcer that makes this offerable ships with it: every background run holds a **lease** the supervising thread renews only while the process is alive, and `reconcile_leases` terminates and finalises any run whose lease lapsed with a receipt naming `command_background_lease_expired` — so a crashed supervisor produces a reclaimed run, never an orphan holding a sandbox grant. A foreground run holds no lease and is never swept | ✅ |
| PTY and raw input | Claude Code/Codex terminal workflows support interactive programs | ✅ **on POSIX**: `openpty` gives the child a controlling terminal, `background_run action=input` types into it, and the test proves the *program* read the bytes rather than the terminal echoing them (`sort` returns its input reordered after ^D). ❌ **on Windows**, with the reason unchanged and named: `CreatePseudoConsole` builds its console objects in the caller's context, unreachable from an AppContainer token, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. `pty_supported()` reports the platform's real answer; input to a run without a terminal is refused as `command_input_requires_pty` rather than written to a pipe where the bytes would arrive and the effect would not | 🟡 |
| Process-tree stop and timeout | Coding agents must stop descendants, not only the launcher | Local runner creates a process group and kills its tree; container stop removes the worker; UI stop is owner-scoped and idempotent | ✅ |
| Network denied by default | Codex and Claude Code sandbox network by default; OpenClaw supports sandbox network policy | ✅ **for `native_sandbox`**, where the container holds no network capability and the measured egress observation is `enforced`; container uses `--network none`. `local_native` is still the default selection and has no OS egress boundary, so the row is scoped rather than claimed for the product default | 🟡 |
| Filtered domain escalation and revocation | Claude Code supports domain/proxy policy; mature sandboxes can grant bounded egress | Tables and design exist; authenticated proxy, DNS/address enforcement, grant retry, and active revocation are not implemented | ❌ |
| Secret-free child environment | Sandboxes should not inherit host credentials | Local and container launchers construct a minimal environment; literal/pattern credentials are rejected before persistence | ✅ |
| Purpose-bound credential delivery and delta quarantine | Reference tools can use credentials; Raiker's target adds post-run local quarantine | Storage contracts exist, but delivery, scan, merge/discard UI, and cleanup saga are not connected to command execution | ❌ |
| Redaction before storage or display | Coding agents suppress known secrets in logs | Incremental UTF-8 redaction covers all current patterns at every split, exact loaned secrets, PEM blocks, explicit stdout/stderr boundaries that prevent cross-stream reconstruction, and fail-closed bounded pending data before persistence | ✅ beyond |
| Durable output catch-up after browser/navigation reload | Reference desktop agents retain command history | Owner-scoped ordered chunks and receipts reload into Build without replaying a command; returning from Approvals refreshes open/collapsed panes and selects the current session's run | ✅ |
| Immutable execution receipt | Reference products expose activity/history, generally without a canonical receipt digest | Canonical terminal receipt binds authority, environment, command-template digest, output truncation, and redaction count; replacement is refused. It now separates two claims that are easy to blend and mean different things: `boundary_constructed` is what **this run's** runner built, `probe_observations` is what **the host** was measured to enforce, with the time it was measured | ✅ beyond |
| Restart reattachment and honest uncertainty | Codex/OpenClaw supervise long-running work across UI/runtime churn | Browser reload works; a Raiker process restart cannot reattach and marks any unprovable active run `lost` with a receipt rather than inferring success. The runner is bound to a Job Object the runtime owns, so a hard kill of Raiker is reaped by the kernel rather than orphaning a sandboxed process | 🟡 |
| SSH and managed cloud sandbox | Claude Code/Codex support remote/cloud execution patterns; Hermes supports remote tools | Profiles are selectable but command-supervisor readiness fails closed; no execution is claimed | ❌ |
| Reset/recreate and recovery controls | Persistent sandboxes need an owner reset and cleanup path | Backend reset internals exist, but no owner-authorised API/UI or restart-safe cleanup saga is shipped | ❌ |
| Capability truthfulness | Reference products vary in how unavailable controls are projected | Features come from a **differential measurement** against the real workspace, never from configuration: each observation is taken inside and outside the boundary, an unmatched control arm reports `indeterminate`, and no `CommandFeatures` field is true without its observation. The six results and the probe's own outbound destination are on the environment card, with **Re-measure boundary** (`r0815-runtime-native-sandbox-observations.png`) | ✅ beyond |

The governance lead is real and unchanged: authority provenance, durable
redacted catch-up, immutable receipts, exact environment choice, honest `lost`
outcomes — and now a boundary that is **measured rather than declared**, which no
reference product exposes to its owner.

**Updated 2026-08-17.** Background supervision, the agent-facing observation
tool, and PTY/raw input on POSIX are now shipped and proven — see the rows above
and `tests/test_background_execution.py`. Raiker still does **not** match the
market leader's complete shell capability: Windows PTY, filtered domain egress,
restart reattachment, persistent sessions, credential quarantine, a container
session supervisor and remote backends remain absent, each with its reason
recorded in [`plans/TO_BE_FIXED.md`](plans/TO_BE_FIXED.md) → BUG-194. They are
tracked as open work rather than hidden behind a parity claim.

Design contract and open work:
[`plans/TO_BE_FIXED.md`](plans/TO_BE_FIXED.md) → BUG-194.

### For review — controls Raiker leads on, and controls it still lacks

Raised 2026-08-15 while closing the native-sandbox half of BUG-194. Nothing here
is implemented unless a row above says so; this is the list the owner asked for,
kept separate from the parity table so an idea is never mistaken for a feature.

**Where Raiker now leads, and why it is worth keeping.**

| Control | Why no reference product has it | Where it is |
|---|---|---|
| A boundary that is **measured, not declared** | Codex, Claude Code, OpenClaw and Hermes all describe their sandbox in documentation and configuration. None runs a child inside the boundary and reports back what it could actually do. A sandbox whose enforcement silently stopped — a disabled firewall service, a restricted user namespace — looks identical to a working one | shipped: six differential observations on the environment card |
| **Three-valued** capability reporting | Every reference product's sandbox is on or off. `indeterminate` — "the control arm failed, so this proves nothing" — is the state that stops an air-gapped machine reporting a network boundary it does not have | shipped |
| Two claims kept apart in the receipt | `boundary_constructed` (this run) versus `probe_observations` (this host, at this time). Reference products expose activity history; none distinguishes what contained *this* command from what the machine was measured to do earlier | shipped |
| An owner-visible **Re-measure**, with its own egress disclosed | The readiness check makes one outbound connection. A product whose posture is "no network by default" should say that out loud rather than let someone find it in a firewall log | shipped |

**What a reference product does that Raiker does not.** Each is open work with a
reason, not an oversight; the reasons are in `plans/TO_BE_FIXED.md` → BUG-194.

| Missing control | Who has it | What it would take |
|---|---|---|
| PTY / interactive input **on Windows** | Claude Code, Codex, Hermes | Closed on POSIX (2026-08-17). ConPTY objects are built in the caller's context and are not reachable from an AppContainer token. Needs a spike, not a flag |
| Filtered domain egress | Claude Code | The AppContainer loopback exemption needs elevation; a Linux proxy-only namespace is a separate build |
| Persistent session boundary | Claude Code, OpenClaw, Hermes | Per-run profiles are deliberate. Persistence is a container-session change |
| Restricted token beneath the AppContainer | Codex | Layering `CreateRestrictedToken` under the security-capabilities attribute is the fragile part of this FFI, and a LowBox token already carries most of it |
| SSH / managed cloud sandbox | Hermes, Codex | Remote supervisor adapters |
| VM-strength containment | Claude Cowork | A different class of boundary again |

**Ideas that go beyond every reference product, not yet built.** Recorded so the
list is a decision rather than a gap: a boundary-drift watcher that re-measures
when the firewall service or a protected path's DACL changes rather than on a
timer; a receipt that carries the probe's *failing* observations as first-class
evidence when a run proceeds under a degraded boundary; and an owner-facing
diff of what a command's boundary allowed compared with the previous run of the
same command template.

---

## Resilience and containment control set

Reviewed 2026-08-10 while closing BUG-76 through BUG-81, against the failure
handling and component-containment controls of **Claude Cowork**, **Claude
Code**, **ChatGPT**, **Codex**, **OpenClaw**, and **Hermes Agent**. Scope is only
that control set: what each system does when a tool, a connector, a provider or a
delegated agent starts failing or misbehaving, and what the owner can see and do
about it. Nothing here is a claim about the rest of those products.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Reference behaviour (where it exists) | Raiker | Status |
|---|---|---|---|
| Per-turn tool-call bound | Claude Code and Codex bound a turn's tool calls | `PromptOptions.max_tool_calls`, enforced in the orchestrator loop | ✅ |
| Provider retry with fallback | Claude Code `--fallback-model`; OpenClaw provider fallback | Ordered fallback chain, one transport re-attempt, each attempt evented | ✅ |
| Circuit breaker on a repeatedly failing component | None — every reference system retries under a budget and reports the last error | Durable consecutive-failure state per tool and per provider, a threshold that contains the subject with a stated reason, a half-open probe after a cooldown, and refusal in between (FIXED-163) | ✅ beyond |
| Behaviour baseline and anomaly rules per component | None | Five deterministic rules — new host, volume spike, tool-set swap, sensitive-data shape, error burst — over a rolling per-subject baseline, for connectors, plugins, subagents, providers, tools and local execution (FIXED-164) | ✅ beyond |
| Owner-visible containment with a one-call resume | Claude Code and Codex let an owner disable a whole MCP server or tool in config | Per-subject `active` / `paused` / `killed`, each revocable in one press from Settings → Security & sign-in, with the reason and failure count on screen | ✅ beyond |
| Delegated-agent result verification | None — Claude Code subagents and Codex sub-tasks return results in-process, unattested | Spawn-scoped Ed25519 attestation binding the result digest to the spawn, verified before the result becomes a turn source, recorded on the hash-chained event (FIXED-165) | ✅ beyond |
| Extension signature verification | Claude Code and Codex verify MCP server transport but not manifest authorship; ChatGPT reviews connectors centrally | HMAC or Ed25519 manifest verification when a key is configured, and a first-class `verified` / `present only` / `unsigned` level stated on every installed plugin either way (FIXED-166) | ✅ beyond |
| Prompt-injection signal on untrusted content | Claude Code, Codex and ChatGPT frame external content as data; none report a suspected attempt to the operator | The same framing, plus a deterministic advisory scanner that names the exact page or document in a finding and never blocks (FIXED-168) | ✅ beyond |
| Resumable / cancellable model acquisition | Ollama and LM Studio resume and cancel downloads | Typed payload dispatch on retry, cooperative cancellation in every worker, and a separately confirmed partial-file deletion bounded to an approved root (FIXED-162) | ✅ |

Raiker difference: containment is **per subject and owner-revocable**. The
reference systems answer a misbehaving component with configuration — turn the
server off, remove the tool — which is all-or-nothing and takes effect only on
the next start. Raiker contains the exact subject at the moment it misbehaves,
says why in the owner's words, and gives the state back in one press.

---

## Eidetic Memory Coverage

| Concept | Raiker specification |
|---|---|
| Raw observation capture | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Observation checksum and artifact reference | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Gist memory compression | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Exact replay with provenance | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Retention classes | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Memory deletion/forgetting | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Skill learning from trajectories | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

## Ruflo-Style Multi-Agent Coverage

| Concept | Raiker specification |
|---|---|
| Multi-agent teams | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Subagent roles | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Background task progress | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Team UI | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| Agent recursion limits | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Enterprise security/governance | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

## Graphify-Style Graph Context Coverage

| Concept | Raiker specification |
|---|---|
| Project graph extraction | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Symbols/entities/relations | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Graph queries | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Graph-backed context retrieval | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Staleness detection | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Recursive CTE traversal | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |

---

## Skills Coverage

| Concept | Raiker specification |
|---|---|
| Procedural workflows | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill packaging | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill activation | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill safety/verification | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Skill self-improvement | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |

---

## Memory Coverage

| Concept | Raiker specification |
|---|---|
| User/profile memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Project memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Episodic memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Procedural memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Semantic/vector memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Memory scoring/provenance | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Memory correction/forgetting | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Memory poisoning controls | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Eidetic observation and gist memory | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |

---

## llama.cpp / Local Inference Coverage

| Concept | Raiker specification |
|---|---|
| Local inference profiles | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `raiker/config/model-profiles.json` |
| Provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| TUI model launch | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Context windows | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Quantisation/hardware notes | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Streaming | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Tool-call modes for local models | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |

---

## LangChain/LangGraph-Style Runtime Coverage

| Concept | Raiker specification |
|---|---|
| Agent framework vs runtime distinction | `docs/ARCHITECTURE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Durable execution | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Human-in-the-loop | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Streaming | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Persistence | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Low-level orchestration | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |

---

## OWASP GenAI/LLM Security Coverage

| Concept | Raiker specification |
|---|---|
| Prompt injection | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Sensitive data disclosure | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Supply chain | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Memory/data poisoning | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Improper output handling | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Excessive agency | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| System prompt leakage | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Vector/embedding weaknesses | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Misinformation | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Unbounded consumption | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |

---

## Superpowers-Style Skills / Self-Improvement Coverage

Reference: `obra/Superpowers` — an agent accrues composable, reusable skills and invokes them on
demand. Mapped to Raiker's skills + self-improvement surfaces.

| Concept | Raiker specification |
|---|---|
| Reusable named skill unit | `docs/EXTENSIBILITY_MODEL.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill distilled from a successful trajectory | `docs/SELF_IMPROVEMENT_MODEL.md` |
| On-demand skill load (cheap until used) | `docs/EXTENSIBILITY_MODEL.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill activation gated by review | `docs/SELF_IMPROVEMENT_MODEL.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill safety/verification before reuse | `docs/SELF_IMPROVEMENT_MODEL.md`, `docs/VERIFICATION_PLAN.md` |
| Confidence/decay/forgetting of skills | `docs/SELF_IMPROVEMENT_MODEL.md` |

---

## mem0-Style Memory Coverage

Reference: `mem0ai/mem0` — a universal memory layer with `add`/`search`/`retrieve` over user,
session, and agent scopes, using hybrid retrieval (semantic embeddings + keyword/BM25 + entity
linking) and provenance.

| mem0 concept | Raiker specification |
|---|---|
| `add` memory from interactions (candidate-first) | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| `search` (semantic + keyword hybrid) | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (FTS4 + vector metadata; no BM25) |
| `retrieve` filtered by scope/metadata | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| User / session / agent memory scopes | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Provenance + confidence scoring | `docs/MEMORY_GOVERNANCE_RULES.md` |
| Update / correct / forget | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Self-hosted/local-first deployment | `docs/ARCHITECTURE.md` (local-first, SQLite-backed) |

Raiker difference: memory writes are **candidate-first and governance-gated**. A turn proposes
`memory_write` / `memory_forget` with the exact text, the owner sees it and decides, and
credential-like text is refused before the decision is offered (FIXED-156). The gate ships off,
and every surface says which of the two states it is in rather than promising proposals it
cannot produce. Durable semantic/vector writes remain disabled (`raiker/memory/readiness.py`).

---

## memsearch-Style Semantic Search Coverage

Reference: `zilliztech/memsearch` — embedding-backed semantic memory/search over an agent's
history with a vector index.

| Concept | Raiker specification |
|---|---|
| Embedding-backed memory index | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (vector metadata tables) |
| Semantic retrieval over session history | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Hybrid lexical + vector ranking | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (FTS5 + BM25 relevance + vector; see the retrieval control set below) |
| Sensitivity/provenance filters on retrieval | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Vector store backend abstraction | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |

Raiker difference: vector writes, embedding creation, and background indexing are
phase-scheduled and **disabled** until governance, approval-preview, and retention controls land.
The **read** path is no longer silent about that — see the control set below.

---

## Text search and memory retrieval control set

Reviewed **2026-08-17** while migrating full-text search from FTS4 to FTS5
(RAIKER-2025) and making the vector leg name its own embedding space (MEM-03),
against the retrieval controls of **Claude Cowork**, **Claude Code**,
**ChatGPT**, **Codex**, **OpenClaw**, **DeepSeek Harness** and **Hermes Agent**.
Scope is only how each system finds an earlier fact and how honestly it reports
what it searched. Nothing here is a claim about the rest of those products.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Market bar | Raiker implementation | Status |
|---|---|---|---|
| Relevance-ranked lexical recall | Every reference product ranks recall by relevance, not by time | Both indexes are FTS5 and both searches order by `bm25()` before recency. Memory weights the approved sentence above its tags (`0.0, 1.0, 0.4`); conversation search weights only the indexed `text` column. Proven by the case MEM-05 described: the best answer is the *oldest* row and survives a limit of two | ✅ |
| Search engine chosen by measurement | Not a control any reference product exposes | The engine is **probed**, not declared: a temporary `fts5` virtual table is created and dropped, because a build can advertise `ENABLE_FTS5` and still refuse the module. A build without FTS5 keeps FTS4, keeps working, and says so — `snippet()` takes its six arguments in a different order on each engine, so the order is derived from the probe rather than written once and assumed | ✅ beyond |
| Zero-downtime index migration | Reference products own their storage and migrate it out of band | Both indexes are **rebuildable projections**, never a second source of truth, so the migration drops and recomputes from the governed table. A workspace opened once on a build without FTS5 is converted the next time it is opened on one that has it, and a workspace interrupted halfway is completed on the next open | ✅ |
| Prose is searched as prose | Mixed. Several products leak the index's query grammar to the user | `NOT`, `NEAR`, `AND` and `OR` are keywords in both engines. Every term is lower-cased to a bareword, so `NOT deployment` finds the memory containing both words instead of raising or answering with the opposite of what was asked | ✅ beyond |
| Semantic (paraphrase) recall | Cowork, ChatGPT and Hermes recall a paraphrase through a learned embedding | The vector leg resolves an **owner-selected embedding space** and embeds the query in that same space. A workspace holding provider or local-model vectors searches them; a default install runs the labelled hashing fallback, which matches words rather than meaning. Semantic recall itself is therefore available but not on by default, because it needs either a downloaded model or accepted egress | 🟡 |
| One embedding space per search | Assumed rather than stated by reference products | Storage fetches exactly one `embedding_model` and retrieval embeds the query with that backend. When the stored vectors are semantic and no governed embedder is available, the vector leg is **dropped** rather than answered from the hashing embedding — a cosine between two different spaces is not a weaker signal, it is a meaningless one | ✅ beyond |
| The interface names the space it searched | No reference product tells the user which embedding answered | Memory → **Recall backend** states the model in force and, in one sentence, whether a paraphrase can recall anything at all. `HybridMemoryResult` carries `vector_backend` and `vector_backend_semantic`; `semantic_memory_status()` reports the read backend separately from the write gate — the two used to be one field that was true of writes and silent about reads | ✅ beyond |
| A selection that cannot be honoured is refused | Mixed; several products silently fall back | Selecting a space this workspace holds no vectors in is refused with `embedding_backend_unknown`, and a stored selection that later becomes empty resolves to the fallback **with the reason attached** (`embedding_backend_selected_has_no_vectors:<model>`) rather than answering from a corpus the owner did not choose | ✅ beyond |
| Measurements attributable to an engine | Not exposed by reference products | `memory_evaluation_runs.backend_version` is written from the probe, so an FTS4 run and an FTS5 run of the same corpus are never compared as if they were the same measurement | ✅ beyond |

**Raiker difference.** Every reference product answers "here is what I found".
Raiker answers "here is what I found, *and here is the index and the embedding
that found it, and what that index cannot do*". The fallback is not hidden
behind the word "vector", and a search that could only be answered dishonestly
returns one leg fewer instead.

**Still open, with reasons.** Semantic recall is off on a default install
because the honest options are a model download or provider egress, and both are
the owner's decision rather than a default. A bundled local sentence-embedding
model reachable through the existing llama.cpp runtime is the next step and is
tracked in [`plans/MEMORY_RELIABILITY_PLAN.md`](plans/MEMORY_RELIABILITY_PLAN.md)
→ MEM-03. `MEM-04`, `MEM-06`, `MEM-07`, `MEM-08` and `MEM-09` are unchanged by
this round.

---

## Skills and extension-authoring control set

Reviewed 2026-08-10 while shipping the built-in skills, against the
skill/plugin/extension-authoring controls of **Claude Cowork**, **Claude Code**,
**ChatGPT**, **Codex**, **OpenClaw**, and **Hermes Agent**. Scope is only how a
system lets an owner add reusable instructions and extensions, decide when they
apply, and bound what they may do. Nothing here is a claim about the rest of
those products.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Reference behaviour (where it exists) | Raiker | Status |
|---|---|---|---|
| Skill document format | Claude Code / Cowork `SKILL.md` with `name` + `description` frontmatter | Identical; a skill written for either installs in the other | ✅ |
| Bundled skill resources | `references/`, `scripts/`, `assets/` beside `SKILL.md` | Same layout, packed as a `*.skill` zip, validated before storage | ✅ |
| Triggering | Description scanned each request | Same, for every active skill | ✅ |
| Turning one off without losing it | Uninstall, or move it out of the directory | Deactivate: installed, withheld from every turn, one click back | ✅ beyond |
| Where a skill may come from | Local file, marketplace, git URL | Upload, in-place authoring, or import from an allowlisted host, fetched through the sandbox egress boundary and validated first | ✅ |
| What a skill may do | Instructions; some surfaces execute bundled scripts | Instructions only — Raiker never executes what a skill ships | ✅ beyond |
| Authority a skill carries | Inherits the session's tool grants | None. A skill cannot open a gate or widen an approval | ✅ beyond |
| Shipped skills | Claude Code plugins (code review, security review, plugin-dev, mcp-builder, skill-creator) | Six built in: algorithm-creator, code-review, mcp-builder, plugin-dev, security-review, skill-creator | ✅ |
| Plugin manifest | Claude Code `plugin.json` | `raiker-plugin.json` with a required per-permission `reason` and `expected_effect` | ✅ beyond |
| Permission change on update | Version bump | Version bump **plus** a permission diff whenever authority widens | ✅ beyond |
| Enabling a plugin | Enabled on install | Install and enable are separate decisions; execution stays behind the gate for the component class | ✅ beyond |
| Hooks | Claude Code hook events; OpenClaw gateway events | `docs/HOOKS_SPEC.md` event catalogue; a hook can block or annotate, never grant | 📘 specified |
| MCP servers | stdio + streamable HTTP; HTTP+SSE deprecated | Same transports, owner-added, per-connection monitoring and re-consent on a surface change | ✅ |
| Protocol revision covered | 2026-07-28 (stateless core, MRTR, cacheable lists) | `mcp-builder` ships the revision reference and the migration checklist | ✅ |
| Self-created skills | Hermes proposes skills after successful tasks | Skill candidates recorded for owner review; never auto-installed | ✅ |

Raiker difference: a skill is **instructions and nothing else**. Every other
system on this list lets an extension carry, or inherit, some execution
authority; in Raiker the authority is held entirely by the runtime's gates, so
installing a skill is a low-risk, reversible act and reviewing one is a
document review rather than a code review.

---

---

## First-run provider setup control set — how an owner gets a model at all

Reviewed **2026-08-16 (second round)** against the onboarding of **Claude Code**
(`/login`, then a model picker), **Claude Cowork** and **ChatGPT** (an account is
the model), **Codex** (sign in, or an API key in the environment), **OpenClaw**
(a connector wizard), **DeepSeek Harness** and **Hermes Agent** (a model list with
a search box, keys in a config file).

The first thing every one of these products does well is make "which model, and is
it reachable" answerable in the place it is asked. Raiker's first-run stage asked
the question and could not answer it — see
[FIXED-223](plans/FIXED_ITEMS.md). What it has now:

| Control | Raiker behaviour | Code |
|---|---|---|
| One row per provider, not per configured profile | Nine rows built from the registry: llama.cpp, Ollama, LM Studio, OpenAI-compatible, Anthropic, OpenAI, OpenRouter, Ollama Cloud, Hugging Face, Gemini | `ProviderMatrix.svelte` |
| Local runtimes are **detected**, not configured | The row asks the runtime what it is serving and offers the answer; `llama.cpp` reads the approved-folder GGUF library and can start a server on one | `providerModels`, `modelLibrary`, `deployLocalModel` |
| A key produces that provider's **own** catalogue | Store the credential, then `GET /api/models/{profile}/provider-models`; the dropdown is the provider's answer and no model name is ever invented | `list_provider_models` |
| A credential is write-only from the interface | The row can report that a key is stored and can forget it; the value is never read back into the page, and a live run asserts the key appears nowhere in the DOM | `saveModelConnection`, vault |
| Every failure names itself | Not running · refused the credential · blocked by provider policy · publishes no model list — four different sentences, because they send the owner to four different places | `catalogueNote` |
| Pinning a model is still a governed act | Gate-manager only, enforced server-side, and readiness is measured against the exact model before any model-backed work | `set_model_selection`, `ModelReadinessService` |

**Raiker difference.** In every reference product, connecting a provider is an
account action and the model list is a consequence of it. Here the two are
separate facts that the screen keeps separate: *a credential is stored*, *the
provider answered with N models*, *this exact model has passed a readiness check*.
An owner can be in the first state and not the third, and the interface says so
rather than presenting a model that will fail at turn time.

**Where Raiker is behind, found in the same review.**

| Gap | Reference behaviour | Meaningful improvement if built? |
|---|---|---|
| A 413-model catalogue is a flat `<select>` | Hermes Agent and Cursor put a **search box** above the model list; Claude Code's menu keeps five models and hides the rest behind **More models ›** | **No — parity, and built in this round.** OpenRouter really does serve 413 models, and a native select of that length is technically honest and practically unusable. A catalogue past twelve models now carries a filter that matches on both the raw id and the displayed name — an owner reading "Sonnet 4.5" should not have to know it is `claude-sonnet-4-5-20250929` — and a filter matching nothing says so rather than presenting an empty picker. Below the threshold the control is absent rather than in the way. |
| No usage or limit reading beside the model | Claude's composer shows plan usage — context window, 5-hour limit, weekly — under the model chip | **Yes, if each figure names its source.** Raiker already has a per-provider weekly token budget and a usage ledger; surfacing *the owner's own* budget and spend at the point of choosing a model would beat a hosted product's opaque "68% of weekly", because the number would be attributable to a ledger the owner can read. |
| No automatic model choice | Claude Code and Cursor offer an "auto" model that the product picks | **No, and deliberately not.** A product that picks the model decides where the owner's content goes. The ordered fallback sequence is the governed version of the same convenience: the owner writes the order, and `no_silent_hosted_fallback` keeps a local-first posture from being quietly widened. |

---

## Live-work control set — what the product says is happening right now

Reviewed **2026-08-16 (second round)** against **Claude Cowork** (a Tasks list and
a Schedule), **Claude Code** (`/background`, the background-task chips),
**Codex** (a queue of cloud tasks), **ChatGPT** (Tasks), **OpenClaw** (a live
canvas), and **Hermes Agent**.

Raiker's default screen used to open with a composer that could not send anything
([FIXED-225](plans/FIXED_ITEMS.md)). It is now a board, and the board's
contribution is a **taxonomy** the reference products do not draw:

| Group | The fact it answers | Why it is separate |
|---|---|---|
| Running now | A governed cycle is in flight, or parked on a decision | This is the only group where **Stop** means "stop something happening" |
| Standing agents | Work with a repeating cadence that re-arms after each cycle | An agent between cycles is *armed*, not running — the scheduler stores it as `queued` with its next slot, and counting it as running is the overcount BUG-09 was filed about |
| Scheduled runs | One future run that has not fired | Cancelling this cancels a plan, not a process |

Every reference product collapses at least two of these into one list called
"Tasks". A row that is waiting, a row that is running, and a row that will run in
a week are three different things to do something about, and naming them
separately is what makes a stop button mean one thing.

| Control | Raiker behaviour |
|---|---|
| Stop at a safe boundary, from the board | The same governed `POST /api/interrupts` every other surface uses — never a kill |
| A blocked row names its blocker | `waiting_for_approval` reads as *"Blocked on a decision you have not made yet"* with a link to the decision, not as a failure |
| A cadence reads as English | `Runs hourly`, `Keeps going until stopped`, plus the next cycle as a relative time |
| Live without a reload | A 15-second poll, the same cadence the Tasks page uses on the same data |
| No second send path | Starting work is a link to the one surface that owns a composer for that kind of work |

**Where Raiker is behind, and it is unchanged and structural.** The board now makes
the existing limitation *visible* rather than removing it, which is the honest
intermediate step:

| Gap | Reference behaviour | Meaningful improvement if built? |
|---|---|---|
| A schedule fires only while Raiker is running on this device | Cowork, ChatGPT and Codex run schedules on someone else's computer | **No — parity, and it is a deployment question, not a feature.** Raiker is local-first by construction. The nearest honest improvement is OS-level scheduled-task registration so a closed laptop wakes for its own cadence, with the audit trail staying local. |
| Four named cadences, no time-of-day or cron | Cowork and ChatGPT take an arbitrary time and a timezone | **No — parity, and worth building.** A daily routine anchored to "whenever it was created" is a real limitation the board now displays as *next cycle …*, which makes it obvious rather than surprising. |
| A cycle that finishes while nobody is looking reaches nobody | Cowork and ChatGPT notify | **Yes, if the notification carries the governed outcome.** Raiker has a notification centre and an event log; a notification that says *which* run ended, how, and links to the decision it needed would beat "your task is done" — but a notification that leaves the machine is an egress decision and has to be gated as one. |

---

## Composer parity — the second pass

The [composer control set](#composer-control-set--how-a-prompt-is-written-corrected-and-re-run)
above records the first pass (slash commands, `@` completion, message actions).
This round changed the composer's **shape** to match the reference products and
moved one control to where it belongs — see
[FIXED-228](plans/FIXED_ITEMS.md).

| Control | Beyond the reference set? | Why |
|---|---|---|
| One control bar under a full-width prompt | **Parity.** Claude, Claude Code, ChatGPT and Hermes all keep `+` at the left and the model chip at the right | Raiker kept its per-turn controls in a column beside the textarea, which cost the prompt a third of the card and put the model chip where no reader would look for it. |
| The thinking budget inside the model menu | **Parity with Claude Code**, which nests **Effort ›** and a **Thinking** switch in its model menu | And it fixes a Raiker-specific incoherence: "Thinking: default" and "send no effort" were one fact spelled two ways. They are now one control. |
| Effort levels are only ever the model's own | **Yes** | Claude Code offers Low…Max for every model in its list. Raiker offers exactly the values the backend advertises for that exact profile, and a model that publishes none has **no** Effort section rather than a disabled one. |
| Build's posture as one chip and one Mode menu | **Parity with Claude Code's Mode menu** (Auto / Accept edits / Plan, with 1/2/3) | Raiker's three modes are server-enforced per turn and may only ever *tighten*, which Claude Code's cannot claim — but the control's shape is theirs, and three always-visible buttons made a posture look like a filter. |
| A `Chat | Build` surface toggle that carries the draft | **Parity with Claude's `Chat | Cowork`**, with one difference worth naming | It moves the prompt and its staged files and **sends nothing**; neither surface's governance changes. Deciding which room a half-typed prompt belongs in used to mean abandoning it. |
| Governance chips on the same bar | **Yes** | No reference composer carries an approval-mode chip, an execution-environment badge and a measured context-capacity badge at all, because none of them has a governed answer to put in one. |

**Still absent, and named rather than mocked up.** There is no microphone and no
dictation: ChatGPT and Claude both have one. GAP-CHAT C16 records it, and the
control is absent rather than present-and-disabled.

---

## Conversation branching — the C14 remainder

| Concept | Claude / ChatGPT | Raiker | Beyond? |
|---|---|---|---|
| Edit a past message | Replaces the message and discards everything after it | Adds a new turn; the original stays | **Yes** — for a governed agent the transcript is evidence |
| Branch from a point | ChatGPT and Claude both fork a conversation | `POST /api/checkpoints/{id}/branch` seeds a second conversation from that turn's checkpoint | **Parity in capability, beyond in accounting** |
| Say where a branch came from | Neither shows lineage in the transcript | A lineage band names and links the source conversation, and states that it kept every turn it had | **Yes** |
| Branch what has no state | Both branch from any message | Absent on a turn with no checkpoint, with the reason stated | **Yes** — a seed invented from the transcript is not the state the turn actually ran in |

Shipped as [FIXED-227](plans/FIXED_ITEMS.md); the last open row of GAP-CHAT C14 is
closed.

---

## Safeguards reviewed this round

Two safeguards were found to be *saying* more than they were doing. Both are
recorded because a safeguard that reports success without acting is worse than an
absent one — it teaches the owner to trust a signal that means nothing.

| Safeguard | What it was doing | Now |
|---|---|---|
| Response redaction | Destroying three legitimate OpenRouter model ids for being 41 characters long, flattening them into one identical string | A named `model` field family with the segmented-path fallback; every credential shape still matched first ([FIXED-224](plans/FIXED_ITEMS.md)) |
| The readiness dialog's **Check again** | Reporting "Check complete" when it had no profile and no model to check | Reports what it actually did ([FIXED-226](plans/FIXED_ITEMS.md)) |

And one is failing in a way the product does not surface, recorded open as
[BUG-216](plans/TO_BE_FIXED.md): on Windows, a workspace nested deeper than
~170 characters cannot open its checkpoint locks, so pre-image capture fails and
the only trace is a `checkpoint_capture_failed` event nothing displays. No
reference product makes a reversibility promise of this kind, so there is nothing
to be behind — but Raiker does make it, which is exactly why it has to be either
kept or visibly broken.

---

## 2026-08-16 review (first round) — what was added, and whether it goes beyond the reference set

Requested as a categorical answer rather than a narrative: for each control this
round added or proposed, **does it take Raiker past Claude Cowork, Claude Code,
ChatGPT, Codex, OpenClaw, DeepSeek Harness and Hermes Agent — yes or no** — and
why. "Parity" is not a failure: some of these are table stakes that Raiker simply
did not have, and saying so is more useful than calling everything a
differentiator.

### Shipped this round

| Control | Beyond the reference set? | Why |
|---|---|---|
| A refused stream carrying its `reason_code` | **Yes** | Reference products surface a generic failure for a refused stream. Raiker tells a lost race, an unrecorded decision and an unreadable parked state apart, and only the last is an error. |
| A finished turn never reporting that it could not continue | **Yes** | No reference product resolves a cross-surface approval race at all — they serialise on one client. Raiker lets both try, resolves it atomically in the store, and holds the interface to the rule that state, not the race, decides what the owner is told. |
| A run naming its backend while in flight | **Parity** | Claude Code and Codex name the sandbox in their activity view. This closes a gap where Raiker's own two surfaces disagreed; it does not pass them. |
| Owner-decided retention of the model's working | **Yes** | ChatGPT, Claude Code and Cowork all keep the reasoning they show and none offers a way not to. Raiker makes it a decision, defaults it off, and excludes retained working from search and export by the shape of the code. |
| Saying *the working was not kept* | **Yes** | The alternative every product takes is showing nothing, which reads as a turn that never thought. Recording the amount without the content is what makes the honest sentence possible. |
| Slash commands, `@` completion, keyboard map, auto-grow | **Parity** | Straightforwardly the bar Claude, ChatGPT, Claude Code and Codex set. Raiker did not have it; now it does. |
| A command menu where every entry runs and none grants | **Yes** | In every reference product a slash command is a privileged path into the harness. Here each one opens a control the owner already has, and a test walks the whole set. |
| `@` completion that reads an index, not a disk | **Yes** | Reference coding agents complete against the live working tree, so the completion surface is as wide as the process's filesystem access. Raiker completes against the map the owner chose to build, under the same gate, returning paths only. |
| An empty menu that says *which* emptiness it is | **Yes** | None of them distinguishes "nothing matched" from "nothing could match", and the two send the owner to different places. |
| Edit-and-resend that adds a turn rather than replacing one | **Yes** | ChatGPT and Claude replace the edited message and discard what followed. For a governed agent the transcript is evidence; a record that quietly changes what was asked is not one. |
| An event's predecessor found by position, not by a whole-second timestamp | **Parity, and load-bearing** | Not a feature any reference product advertises. It is the difference between an integrity report that can be believed and one that cries tamper on an intact log under ordinary load. Recorded as [FIXED-222](plans/FIXED_ITEMS.md). |

### Proposed and deliberately not built

Each is recorded where the work is tracked rather than implied to exist.

| Proposal | Beyond the reference set? | Why it was not built now |
|---|---|---|
| Owner-authored custom slash commands | **No — parity** (Claude Code, Codex, OpenClaw have them) | The skill store already holds owner-authored instructions with a review path. The honest version has to state what authority a command carries, which makes it a governance design task rather than a parser change. |
| `@`-mention of a connector, a memory or a past conversation | **Yes**, if the menu names the authority each row would use | One completion menu over four governed reads becomes a way to reach a capability without noticing, unless the row says which one. That is the design work. |
| Branch-a-conversation-from-here | **Built in the second round of the same day** — see [FIXED-227](plans/FIXED_ITEMS.md) | It needed a conversation fork over the existing checkpoint manifest plus a surface that makes two branches legible; both landed, and the lineage band is the part no reference product has. |
| A slash command that shows the capability gate it would cross | **Yes** | No reference product's command surface is governed at all, so none can show this. It would make the governed shape of a shortcut visible before it runs. |
| An `@`-mention that reports each file's index freshness | **Yes** | The code map already records when each path was last parsed; no reference product's completion can say how stale its answer is. |
| Background execution, PTY, filtered egress, restart reattachment | **No — parity** (Claude Code, Codex, OpenClaw, Hermes) | Each is a component rather than a flag. See [`plans/TO_BE_FIXED.md`](plans/TO_BE_FIXED.md) → BUG-194 for the per-row reason; the controls are absent from the interface rather than disabled. |
| Surfacing the memory integrity report at all | **Parity, and a prerequisite** | `inspect_memory_integrity` has no route, no scheduler entry and no panel, so MEM-09's conversation-index check would join a report nothing displays. Re-scoped in [`plans/MEMORY_RELIABILITY_PLAN.md`](plans/MEMORY_RELIABILITY_PLAN.md). |

**The pattern worth keeping.** Every row marked *Yes* is the same move: the
reference product shows a result, and Raiker shows the result **plus what it
rests on** — the reason behind a refusal, the authority behind a command, the
index behind a completion, the decision behind what is kept. None of them is a
new capability. They are the same capability, made accountable, which is the only
axis on which a governed agent can beat a faster one.

---

## Rule For New References

When Raiker adopts a concept from another platform, the docs must add concept name, Raiker behaviour, contract/schema, lifecycle, storage, security rules, events, tests, UI surface, and build phase.

If these are not present, the concept is not considered fully specified.
