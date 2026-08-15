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
| Channels | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` |
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
| `channels-reference` (MCP `claude/channel` capability; `notifications/claude/channel`; sender gating; permission relay) | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` | 🔒 registry only |

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

## OpenClaw-Style Personal Agent Coverage

| Concept | Raiker specification |
|---|---|
| Local-first gateway/control plane | `docs/ARCHITECTURE.md`, `docs/CHANNELS_SPEC.md` |
| Multi-channel inbox | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json`, `docs/UI_UX_DESIGN_SPEC.md` |
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
| Model-router/provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json` |
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
| Background start/poll/wait/log/kill | Claude Code, Codex, OpenClaw, and Hermes expose long-running process controls | Durable poll/log and stop exist for a running foreground command; background start/wait/lease controls are absent and refused by name. A background run needs an enforcer that outlives the turn — see the BUG-194 remainder | 🟡 |
| PTY and raw input | Claude Code/Codex terminal workflows support interactive programs | Contracts refuse PTY/input by name and the UI shows no input control. `CreatePseudoConsole` builds its console objects in the caller's context and they are not reachable from an AppContainer token; a PTY that only worked outside the sandbox would not be this control | ❌ |
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

Raiker still does **not** match the market leader's complete shell capability.
PTY/background supervision, filtered domain egress, restart reattachment,
persistent sessions, credential quarantine, a container session supervisor and
remote backends remain absent, each with its reason recorded in
[`plans/TO_BE_FIXED.md`](plans/TO_BE_FIXED.md) → BUG-194. They are tracked as
open work rather than hidden behind a parity claim.

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
| PTY / interactive input | Claude Code, Codex, Hermes | ConPTY objects are built in the caller's context and are not reachable from an AppContainer token. Needs a spike, not a flag |
| Background start/poll/wait/log/kill | Claude Code, Codex, OpenClaw, Hermes | A lease the runner owns, a durable runner identity that survives pid reuse, and reconciliation that works while the vault is locked |
| An agent-facing `process` tool | Hermes | Backgrounding without it makes an agent re-run commands it cannot observe |
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
| Local inference profiles | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json` |
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
| Hybrid lexical + vector ranking | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (FTS4 + vector; recency-ordered, not relevance-ranked) |
| Sensitivity/provenance filters on retrieval | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Vector store backend abstraction | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |

Raiker difference: vector writes, embedding creation, and background indexing are
phase-scheduled and **disabled** until governance, approval-preview, and retention controls land.

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

## Rule For New References

When Raiker adopts a concept from another platform, the docs must add concept name, Raiker behaviour, contract/schema, lifecycle, storage, security rules, events, tests, UI surface, and build phase.

If these are not present, the concept is not considered fully specified.
