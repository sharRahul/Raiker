# Reference platform compatibility

**This document is canonical** for how Raiker compares with the reference
platforms it is measured against. No other document in this repository should
carry a comparison matrix; they link here instead.

Raiker is not a clone of any one system. It combines a local-first agent
runtime, coding-agent UX, hooks, plugins, channels, memory, graph context, local
inference, skills, eidetic-style recall and GenAI security into one governed
architecture. The point of comparing is to find controls worth having and
controls worth refusing — not to reach parity for its own sake.

Last full reconciliation against the code and against primary sources:
**2026-08-23**.

---

## 0. How to read this document

### 0.1 What each part is for

| Part | Answers |
|---|---|
| [1. Reference platforms and sources](#1-reference-platforms-and-sources) | Who Raiker is measured against, and where the claims about them come from |
| [2. Canonical capability matrix](#2-canonical-capability-matrix) | For one capability: does Raiker have it, where, what is missing, and does having it beat the reference set |
| [3. Where Raiker deliberately differs](#3-where-raiker-deliberately-differs) | Controls Raiker implements differently *on purpose*, with the governance argument |
| [4. Deliberately refused](#4-deliberately-refused) | Reference behaviour Raiker will not copy, and why copying it would be worse |
| [5. Prioritised backlog](#5-prioritised-backlog) | Everything unresolved, ordered by priority then effort, with proposed action and effect |
| [6. Control-set reviews](#6-control-set-reviews-evidence) | The dated, source-backed reviews the rows above are drawn from |

### 0.2 Implementation status vocabulary

Every row in Part 2 carries exactly one of these. They are the nine categories
the audit is required to separate, and nothing is described as implemented
unless a named code path does it.

| Status | Meaning |
|---|---|
| **Implemented** | Shipped, reachable by an owner, covered by tests |
| **Implemented (undocumented)** | Shipped and reachable, but the docs did not say so before this reconciliation |
| **Partial** | Some of it ships and the rest is named; a stated boundary, not a silent one |
| **Doc drift** | Documentation described behaviour the code no longer has — corrected in this pass |
| **Proposed** | Not built. A new capability worth adding |
| **Improve** | Built, but a specific improvement is proposed |
| **Remove** | Built or specified, and a candidate for removal or deprecation. No row in Part 2 carries it: nothing Raiker has shipped is a candidate for removal today, and the reference behaviour Raiker refuses to *add* is **Different by design** plus an **AVOID** verdict rather than a removal. What this pass did deprecate is documentation — see [§4.7](#47-what-was-deprecated-in-the-documentation-itself) |
| **N/A** | Not applicable to a local-first, single-owner, user-governed product |
| **Different by design** | Raiker does the job another way because its architecture or governance is better served by it |

### 0.3 Beyond-reference assessment vocabulary

Parity is not automatically desirable. Each row states whether *having the
control at all* would put Raiker ahead of the reference set.

| Verdict | Meaning |
|---|---|
| **YES — differentiator** | Meaningful, and no compared platform has it |
| **YES — improvement** | Meaningful, but at least one compared platform has something like it |
| **PARITY** | Required to stay competitive; not an advantage |
| **NO — little advantage** | Real, but the benefit does not justify the surface |
| **NO — complexity** | The cost is complexity the product would carry forever |
| **NO — conflicts** | It would weaken Raiker's governance, observability or user control |
| **AVOID** | The reference implementation is weaker or less safe than Raiker's approach |

### 0.4 Priority and effort ordering

Part 5 is ordered strictly:

1. High priority + low effort
2. High priority + medium effort
3. High priority + high effort
4. Medium priority + low effort
5. Medium priority + medium effort
6. Medium priority + high effort
7. Low priority + low effort
8. Low priority + medium effort
9. Low priority + high effort

Priority is set by what the change does for **security, reliability,
governance, or the owner's ability to understand and control the product** —
never by how impressive it sounds. A simpler item that makes a refusal legible
outranks a larger one that adds a capability.

### 0.5 Surface vocabulary

The same four words are used throughout this repository:

| Surface | What it names |
|---|---|
| **Raiker Chat** | The assistant surface: `apps/web` Chat view, `surface: "chat"` on a prompt |
| **Raiker Build** | The coding-agent surface: Build view, `surface: "build"`, the Build operating protocol |
| **Shared runtime** | Everything both surfaces route through — gateway, policy engine, `RuntimeAuthority`, tool broker, executors, storage, audit |
| **Platform-wide** | Product-level concerns: install, host lifecycle, identity, settings, extensibility, observability |

Chat and Build **share every gate, decision mode, approval and tool**. They
differ in composer, protocol and default posture, never in authority.

---

## 1. Reference platforms and sources

| Platform | What it is | Raiker surface it is measured against | Primary sources |
|---|---|---|---|
| **Claude Cowork** | Anthropic's knowledge-worker agent: folder/remote sessions, delegated tasks, routines, plugins, connectors | Raiker Chat and the shared runtime | [Cowork overview](https://claude.com/docs/cowork/overview), [Get started](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork), [Schedule recurring tasks](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork), [Projects in Cowork](https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork), [Computer use in Cowork](https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork), [Monitoring (OpenTelemetry)](https://claude.com/docs/cowork/monitoring), [OpenTelemetry monitoring (support article)](https://support.claude.com/en/articles/14477985-monitor-claude-cowork-activity-with-opentelemetry), [Dispatch — background tasks](https://claude.com/docs/cowork/guide/dispatch), [Install plugins](https://claude.com/docs/cowork/guide/plugins), [Cowork changelog](https://claude.com/docs/cowork/changelog), [Skills overview](https://claude.com/docs/skills/overview), [Connectors overview](https://claude.com/docs/connectors/overview) |
| **Claude Code** | Anthropic's coding agent: tools, permissions, sandboxing, hooks, skills, subagents, plugins, MCP | Raiker Build and the shared runtime | [Extend Claude Code](https://code.claude.com/docs/en/features-overview), [How it works](https://code.claude.com/docs/en/how-claude-code-works), [Tools reference](https://code.claude.com/docs/en/tools-reference), [Permissions](https://code.claude.com/docs/en/permissions), [Permission modes](https://code.claude.com/docs/en/permission-modes), [Sandboxing](https://code.claude.com/docs/en/sandboxing), [Sandbox environments](https://code.claude.com/docs/en/sandbox-environments), [Hooks](https://code.claude.com/docs/en/hooks), [Plugins](https://code.claude.com/docs/en/plugins), [Plugins reference](https://code.claude.com/docs/en/plugins-reference), [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces), [Skills](https://code.claude.com/docs/en/skills), [Subagents](https://code.claude.com/docs/en/sub-agents), [Workflows](https://code.claude.com/docs/en/workflows), [Cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), [MCP](https://code.claude.com/docs/en/mcp), [CLAUDE.md](https://code.claude.com/docs/en/memory), [Checkpointing](https://code.claude.com/docs/en/checkpointing), [Artifacts](https://code.claude.com/docs/en/artifacts), [Managed settings](https://code.claude.com/docs/en/managed-settings), [Settings reference](https://code.claude.com/docs/en/settings-reference), [Security](https://code.claude.com/docs/en/security), [Monitoring](https://code.claude.com/docs/en/monitoring-usage), [Sandboxing engineering post](https://www.anthropic.com/engineering/claude-code-sandboxing), [Containment engineering post](https://www.anthropic.com/engineering/how-we-contain-claude) |
| **ChatGPT Chat / Work** | OpenAI's assistant and workspace product: apps/connectors, projects, memory, agent mode, scheduled automations | Raiker Chat and the shared runtime | [Connectors in ChatGPT](https://help.openai.com/en/articles/11487775-connectors-in-chatgpt), [Projects](https://help.openai.com/en/articles/10169521-using-projects), [Memory FAQ](https://help.openai.com/en/articles/8590148-memory-in-chatgpt-faq), [Voice mode FAQ](https://help.openai.com/en/articles/8400625-voice-mode-faq), [ChatGPT Work admin FAQ](https://learn.chatgpt.com/docs/enterprise/work-admin-faq) |
| **OpenAI Codex** | OpenAI's coding agent: CLI, IDE and cloud, with `sandbox_mode` and `approval_policy` as separate controls | Raiker Build and the shared runtime | [Codex sandboxing](https://learn.chatgpt.com/docs/sandboxing), [Codex manual](https://developers.openai.com/codex/codex-manual.md), [Running Codex safely](https://openai.com/index/running-codex-safely/), [Windows sandbox](https://openai.com/index/building-codex-windows-sandbox/), [Codex upgrades](https://openai.com/index/introducing-upgrades-to-codex/), [Codex skills](https://learn.chatgpt.com/docs/build-skills) |
| **OpenClaw** | Open-source local-first personal-agent gateway: channels, exec tool, optional container sandboxing, plugins | Platform-wide, and Raiker's channel and execution surfaces | [Docs](https://docs.openclaw.ai/), [Architecture](https://docs.openclaw.ai/concepts/architecture), [Gateway sandboxing](https://github.com/openclaw/openclaw/blob/main/docs/gateway/sandboxing.md), [Exec tool](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec.md), [Exec approvals](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec-approvals.md), [Control UI](https://docs.openclaw.ai/web/control-ui), [Setup wizard](https://docs.openclaw.ai/start/wizard) |
| **DeepSeek Harness** | MIT-licensed agent harness (developer preview, v0.1, 2026-08-13) where models, tools, skills, sessions, sandboxes, storage, loops, scheduling and UI are all plugins, over an append-only trajectory | Platform-wide, and Raiker's extensibility and observability surfaces | [DeepSeek Harness](https://deepseek.com/harness/en/) |
| **Cross-vendor standards** | Not a platform: the formats every one of the above now implements, which is where interoperability claims have to be measured | Platform-wide | [Model Context Protocol](https://modelcontextprotocol.io/), [MCP versioning and revisions](https://modelcontextprotocol.io/specification/versioning), [MCP Apps (SEP-1865)](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp), [`modelcontextprotocol/ext-apps`](https://github.com/modelcontextprotocol/ext-apps), [Agent Skills](https://agentskills.io), [Agent Skills specification](https://agentskills.io/specification), [`agentskills/agentskills`](https://github.com/agentskills/agentskills) |
| **Hermes Agent** | Nous Research's self-improving agent: seven terminal backends, 40+ tools, pluggable memory providers, autonomous skill creation, 27+ messaging surfaces | Platform-wide, and Raiker's execution, memory and channel surfaces | [Hermes Agent docs](https://hermes-agent.nousresearch.com/docs/), [Features overview](https://hermes-agent.nousresearch.com/docs/user-guide/features/overview), [Tools and toolsets](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools), [Persistent memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory), [Messaging gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/), [Repository](https://github.com/NousResearch/hermes-agent), [Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) |

**Source discipline.** A claim about a reference platform is made only from that
platform's own documentation. Where a source could not be re-read during a
pass, the claim is kept as previously recorded and is not strengthened. "Not
established by cited source" is written rather than a guess.

**Verification status of the source list above.** Every external URL cited in
this document was requested during the 2026-08-23 reconciliation, and the result
recorded per domain rather than assumed. This matters because the previous pass
(2026-08-23) ran in an environment that could not reach most vendor domains and
said so; **that caveat no longer holds and has been removed.** Its
carried-forward claims have now been re-read against the sources themselves.

| Domain group | Status this pass | What it means for the claims drawn from it |
|---|---|---|
| `code.claude.com`, `github.com`, `www.anthropic.com` | Reachable, re-read | Confirmed for a second consecutive pass |
| `claude.com`, `support.claude.com`, `docs.claude.com`, `support.anthropic.com` | **Reachable — newly verified** | Cowork claims were carried forward unverified last pass; re-read here |
| `learn.chatgpt.com`, `developers.openai.com` | **Reachable — newly verified** | Codex sandbox and ChatGPT Work admin claims re-read here |
| `deepseek.com`, `docs.openclaw.ai`, `openclaw.ai`, `hermes-agent.nousresearch.com` | **Reachable — newly verified** | Harness, OpenClaw and Hermes claims re-read here |
| `modelcontextprotocol.io` | **Reachable — read in full this pass** | The versioning page and SEP-1865 were read, not just resolved; both back new rows |
| `agentskills.io` | **Reachable — newly cited** | The overview, the specification and the client list were read this pass |
| `genai.owasp.org`, `huggingface.co`, `openrouter.ai`, `lmstudio.ai`, `docs.ollama.com`, `pypi.org` | Reachable | Entry points confirmed to resolve |
| `openai.com`, `help.openai.com`, `platform.openai.com` | **Bot-blocked (HTTP 403), not dead** | These refuse automated requests. The URLs are canonical and were not invented; claims resting on them alone are still not strengthened |

**Every external URL in the documentation was requested this pass**, not just
those in the table above. All 114 distinct `http(s)` links across `README.md`
and `docs/**` were fetched: **106 answered `200`**, **8 answered `403`** — every
one of them on an `openai.com` host, exactly the bot-blocking already recorded —
and one is `https://example.test`, a deliberate placeholder inside a test
assertion in an archived plan rather than a citation. **No dead link, no
redirect left uncorrected, and no fabricated URL.**

Internal links are no longer audited by hand: `tests/test_docs_consistency.py::test_documentation_links_and_anchors_resolve`
now asserts that every relative link **and every heading anchor** resolves, so a
renamed section fails the build rather than rotting quietly. External URLs stay
manual on purpose — making CI depend on other people's uptime, and on hosts that
answer `403` to automation, would turn a green build into a statement about the
weather.

**What re-reading the newly reachable sources changed.** Four things, each
carried into the rows below:

- **The Codex sandboxing URL had moved.**
  `developers.openai.com/codex/concepts/sandboxing` answers `308 Permanent
  Redirect` to [`learn.chatgpt.com/docs/sandboxing`](https://learn.chatgpt.com/docs/sandboxing),
  which is now cited directly. The claims it backs — `read-only` /
  `workspace-write` / `danger-full-access`, `untrusted` / `on-request` / `never`,
  network denied by default, Seatbelt on macOS, bubblewrap plus optional Landlock
  on Linux, and a native Windows Sandbox under PowerShell — were re-read and are
  unchanged.
- **Cowork's monitoring has a canonical product doc**, not just a support
  article: [`claude.com/docs/cowork/monitoring`](https://claude.com/docs/cowork/monitoring).
  It names six exported events — `user_prompt`, `assistant_response`,
  `tool_result`, `api_request`, `api_error` and `tool_decision` — metadata-only
  by default, with prompt, response and tool-argument content opt-in through
  `otlpContentCapture`. `tool_decision` carries both the decision and its
  *source* (`config`, `hook`, `user_permanent`, `user_temporary`, `user_abort`,
  `user_reject`). That is the closest external analogue to Raiker's audit record,
  and it sharpens the OpenTelemetry backlog item rather than changing it.
- **Hermes supports more messaging surfaces than recorded.** The [messaging
  gateway docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/)
  name **27+** platforms; this document said "20+", which was conservative rather
  than wrong. The messaging source is now cited alongside the tools source.
- **Hermes's seven terminal backends and 40+ tools are confirmed** from the
  vendor's own tools page and repository README, rather than carried forward.

**What this pass (2026-08-23) found that no earlier one had.** Five things, each
carried into the rows below and into the backlog:

- **Skills are now a published open standard, not a Claude Code convention.**
  [Agent Skills](https://agentskills.io) defines `SKILL.md` with a
  [formal specification](https://agentskills.io/specification) — required `name`
  and `description`, optional `license`, `compatibility`, `metadata` and the
  experimental `allowed-tools`, over `scripts/`, `references/` and `assets/`
  directories — and a
  [reference validator](https://github.com/agentskills/agentskills/tree/main/skills-ref).
  **All seven reference platforms implement it**, alongside forty-plus other
  products. Raiker's own format predates the standard and is close to it; the
  differences are now measurable rather than a matter of taste, and
  [§2.6](#26-extensibility--plugins-skills-mcp-channels) records them.
- **Server-contributed interactive UI is now specified and shipping.**
  [MCP Apps (SEP-1865)](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp)
  declares UI resources under a `ui://` scheme, links them to tools through
  metadata, and renders them in a **mandatory sandboxed iframe** with auditable
  JSON-RPC back to the host; Claude
  [ships it](https://claude.com/docs/connectors/building/mcp-apps/getting-started)
  behind a per-app permission prompt. **This corrects a claim in this document.**
  It previously said no compared platform ships plugin UI panels — true of the
  Claude Code *plugin component* list, and false of the product as a whole.
- **Raiker's MCP client is pinned five revisions behind.**
  `MCP_PROTOCOL_VERSION = "2024-11-05"` (`raiker/runtime/executors/mcp.py`); the
  [current revision is `2026-07-28`](https://modelcontextprotocol.io/specification/versioning),
  which replaced the `initialize` handshake with a per-request `_meta` version
  declaration plus a mandatory `server/discover` RPC. This had not been recorded
  anywhere, and it is the underlying reason for two gaps already in the matrix.
- **Cowork has a delegating agent that routes child tasks by surface.**
  [Dispatch](https://claude.com/docs/cowork/guide/dispatch) takes one high-level
  brief, splits it into child tasks, and routes each to **Code** (coding work) or
  **Cowork** (knowledge work), tracking six states including *Awaiting answer*.
  Two details matter for Raiker: it is the concrete form of the delegated-ownership
  gap (BUG-220), and an unanswered permission prompt is **auto-denied after ten
  minutes** while the task continues — a design Raiker should not copy.
- **Two Codex URLs move.** `developers.openai.com/codex/skills` answers `308` to
  [`learn.chatgpt.com/docs/build-skills`](https://learn.chatgpt.com/docs/build-skills)
  (Codex skills additionally accept an optional `agents/openai.yaml` for UI
  metadata, `allow_implicit_invocation` and `dependencies.tools`).
  `developers.openai.com/codex/codex-manual.md` still resolves `200` and is
  unchanged.

**What earlier passes corrected, retained here.** Two URL corrections and three
claim corrections still stand, and are not re-litigated below:

- The Hermes repository URL was once cited as `github.com/hermes-agent-org/hermes`,
  which is not the project's repository; it is
  [`github.com/NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent).
  Fetching it is also what established the seventh terminal backend (Vercel
  Sandbox) an earlier pass had missed.
- One OpenAI help URL was truncated (`…/11487775-connectors-in`) and carries its
  full slug.
- Three claims about reference platforms were wrong and were corrected in place,
  each marked where it appears: hook lifecycle events were recorded as "at parity"
  when Raiker covers sixteen of Claude Code's thirty-one; hook handler types were
  recorded as a gap against Raiker's own document on the grounds that Claude Code
  has only `command`, when it documents and specifies all five; and plugin
  **panels** were recorded as a gap against Claude Code, which has no plugin UI
  panel component at all. **That last correction is itself now superseded**: the
  Claude Code plugin component list still has no panel, but MCP Apps gives a
  connected server a sandboxed interactive UI in the product, so "no compared
  platform ships this" was the wrong frame. See
  [§2.6](#26-extensibility--plugins-skills-mcp-channels).

---

## 2. Canonical capability matrix

Read a row as: *the reference set has this; here is what Raiker has, where it
is, what is missing, and whether having it puts Raiker ahead.*

Part 5 carries the proposed action, governance implication, priority and effort
for every row that is not `Implemented`, `N/A` or `Different by design`.

### 2.1 Agent runtime and execution loop

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Gather → act → verify agentic loop | Claude Code, Codex, Hermes, DeepSeek Harness | Shared runtime | Implemented | `raiker/gateway/agent_gateway.py`, `raiker/runtime/orchestrator.py` | Verification is advisory rather than a gate | PARITY |
| Streamed turn with incremental text | All | Chat, Build | Implemented | `raiker/contracts/streaming.py`, `ChatView.svelte` | — | PARITY |
| Model reasoning shown apart from the answer | ChatGPT, Claude Code, Codex, Cowork | Chat, Build | Implemented | `reasoning_delta`, `ReasoningBlock.svelte` | — | PARITY |
| Retaining the model's reasoning is the owner's choice | None — all retain it, none offers a way not to | Platform-wide | Implemented | `turns.reasoning_text` written only under Settings → Privacy | — | **YES — differentiator** |
| Stop / steer a running turn | Claude Code, Codex, ChatGPT | Chat, Build | Implemented | `POST /api/interrupts`, `raiker/runtime/interrupts.py` | — | PARITY |
| Parallel tool calls in one batch | Claude Code, Codex | Shared runtime | Implemented | `raiker/tools/broker.py` — concurrent for validated read-only calls only | A batch containing an approval is walked serially, by design | **YES — improvement** |
| Turn parks on an approval and resumes | Cowork, Claude Code | Shared runtime | Implemented | `turn_suspended_for_approval` / `turn_resumed_after_approval` | — | **YES — improvement** |
| Per-turn bound on tool calls | Claude Code, Codex | Shared runtime | Implemented | `PromptOptions.max_tool_calls` | — | PARITY |
| Circuit-breaking a repeatedly failing tool or provider | None | Platform-wide | Implemented | `raiker/security/containment.py` | — | **YES — differentiator** |
| Deterministic replay of a run from its event log | DeepSeek Harness | Platform-wide | Proposed | — | Audit is append-style evidence, not a replayable trajectory | **YES — improvement** |
| Dynamic workflows: a script that runs many subagents | Claude Code | Build | Proposed | — | Raiker has one bounded read-only subagent per spawn | NO — complexity |
| Cross-session messaging between agent sessions | Claude Code | Platform-wide | Proposed | — | No session-to-session channel exists | NO — little advantage |

### 2.2 Tools and permissions

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| A named tool set the model may call | All | Shared runtime | Implemented | `raiker/models/tool_registry.py` — 46 `TOOL_DEFINITIONS`, of which 45 are in `MODEL_EXPOSED_TOOLS` (`vector_get` is defined but not offered to a model) | — | PARITY |
| Every advertised tool has a policy verdict | None state it as an invariant | Shared runtime | Implemented | `PolicyEngine` hard-denies anything in neither set; `tests/test_policy_engine.py` | — | **YES — differentiator** |
| Per-tool permission rules | Claude Code (`allow`/`ask`/`deny` rules), Codex, OpenClaw (`tools.allow`) | Permissions | Different by design | Per-capability decision modes over 67 capability gates (`raiker/phase_gates.py`) | Raiker gates a *capability*, not a tool-argument pattern; there is no `Bash(git *)` rule syntax | **Different — see [3.1](#31-a-capability-gate-instead-of-a-tool-argument-rule)** |
| Permission modes for a session | Claude Code (`default`/`acceptEdits`/`plan`/`auto`/`dontAsk`/`bypassPermissions`), Codex (`approval_policy`) | Chat, Build composers | Implemented | `APPROVAL_MODES = {manual, auto, skip, dont_ask}`; Build adds Plan/Edit/Auto | No `bypassPermissions` equivalent — refused, see [4.1](#41-a-mode-that-skips-every-check) | **PARITY**, with one refusal |
| A turn may only tighten its own posture | None — reference modes can widen | Chat, Build | Implemented | `TURN_TIGHTENING_MODES`; `allow`/`auto` refused by the prompt contract | — | **YES — differentiator** |
| An unattended posture that declines instead of asking | Claude Code `dontAsk` | Chat, Build | Implemented | `dont_ask` (BUG-219 / FIXED-262) | — | PARITY |
| A distinct reason for "refused because nobody was watching" | None | Platform-wide | Implemented | `denied_no_one_to_ask` | — | **YES — differentiator** |
| Auto mode reviewed by a classifier model | Claude Code auto mode | Permissions | Different by design | `auto_requires_approval` keys off the action's risk level, and `raiker/runtime/alignment.py` checks the action against the turn's own record — neither is a model call | Raiker's `auto` is deterministic in both halves. Its alignment check is narrower than a classifier and says so: it catches a change to a file the turn never established, not a semantically wrong change to one it did | **Different — see [3.2](#32-a-deterministic-auto-instead-of-a-classifier)** |
| Critical actions never auto-approved | Claude Code protected paths, Codex | Shared runtime | Implemented | `raiker/runtime/authority/critical.py`; critical risk is human-only with step-up | — | **YES — improvement** |
| Standing per-tool grants | Claude Code "don't ask again" | Permissions, Git credential | Implemented | Decision modes; `run_command` standing grants; git-credential loan scopes | — | PARITY |
| Deferring tool schemas to bound context cost | Claude Code `ToolSearch` over deferred tools | Shared runtime | Proposed | — | All 45 model-exposed tools enter every turn's tool list, and every projected MCP tool is added to it. A connected server costs its whole schema on every turn. Same underlying item as MCP tool search in [§2.6](#26-extensibility--plugins-skills-mcp-channels) | **YES — improvement** |
| A structured question to the owner mid-turn | Claude Code `AskUserQuestion`; MCP elicitation (`2026-07-28`); Cowork Dispatch's *Awaiting answer* state | Chat, Build | Proposed | — | Raiker's only mid-turn interruption is an **approval**, which asks *may I do this* and cannot ask *which of these did you mean*. A model that must guess between two readings guesses. The governance question is small — a question grants nothing and executes nothing — which is what makes this cheap | **YES — improvement** |

### 2.3 Approvals, governance and audit

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| A human decision before a risky action | All | Approvals | Implemented | `raiker/approvals/`, Approvals view | — | PARITY |
| Approving actually performs the action | All | Approvals | Implemented | `EXECUTABLE_ON_APPROVAL` — 12 capabilities relayed and re-governed | `process`, `network` and every other capability stay decision-only, deliberately | **YES — improvement** |
| The approval says what will happen *before* the decision | Partially — reference products show the tool call | Approvals | Implemented | `raiker/approval_previews.py`, `approval_preview_registry.py` | — | **YES — improvement** |
| Re-governing at execution time, not only at proposal time | None | Shared runtime | Implemented | `ApprovalExecutionBridge` re-checks gate, policy and posture | — | **YES — differentiator** |
| A step-up for opening a higher-risk gate | Managed policy in Claude Code and ChatGPT Work | Permissions | Implemented | `runtime_gate_manager` + reason + typed phrase + threat-model acknowledgement | The typed phrase is intent, not a credential — WebAuthn step-up is ADD-15 | **YES — differentiator** |
| Append-only local audit of governed work | Claude Code (transcript), DeepSeek Harness (trajectory), OpenClaw | Observability → Audit log | Implemented | `raiker/events/`, 268 declared event types | — | PARITY |
| Audit records that cannot say more than the redaction allows | None | Platform-wide | Implemented | `raiker/tools/presentation.py` resolves the transcript row server-side under the event's own redaction | — | **YES — differentiator** |
| Exportable evidence bundle | Cowork OpenTelemetry export; ChatGPT Work admin logs | Observability | Partial | `audit_export` capability, `raiker/events/export.py` | No REST route surfaces an export; no OpenTelemetry emitter | **PARITY** |
| Machine identity separate from the human owner | None — reference agents act as the user | Shared runtime | Implemented | `raiker/runtime/identity/`, per-turn Ed25519 attestation | — | **YES — differentiator** |
| Organisation-wide managed policy | Claude Code managed settings, ChatGPT Work admin | Platform-wide | N/A | — | Raiker is single-owner and local-first; there is no organisation above the owner | **NO — conflicts** |

### 2.4 Sandboxing and execution environments

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| OS-enforced filesystem isolation for commands | Claude Code (Seatbelt / bubblewrap+seccomp), Codex, OpenClaw (containers) | Build, shared runtime | Implemented | `native/` runner: Windows AppContainer, Linux bubblewrap, macOS Seatbelt | — | PARITY |
| A native **Windows** OS sandbox | Codex only — Claude Code's Bash sandbox does **not** support native Windows and directs users to WSL2 | Build | Implemented | AppContainer + Job Object with `KILL_ON_JOB_CLOSE` | Codex additionally layers a restricted token; Raiker does not, and says so | **YES — improvement** |
| Network denied by default inside the sandbox | Claude Code, Codex, OpenClaw (`network: none`) | Build | Partial | `native_sandbox` holds no network capability; container uses `--network none` | `local_native` is the default selection and has no OS egress boundary | PARITY |
| The boundary is **measured**, not declared | None | Build, Observability | Implemented | `raiker-command-runner --probe`: six differential observations with control arms; `indeterminate` when the control fails | — | **YES — differentiator** |
| Filtered domain egress from inside the sandbox | Claude Code `network.allowedDomains` + proxy | Build | Partial | Policy, HMAC run tokens, CONNECT proxy, address pinning and revocation are built | `filtered_network` stays false without a live bypass/revocation proof | PARITY |
| Credential masking with sentinel substitution at the proxy | Claude Code `sandbox.credentials` `mask` + `injectHosts` | Platform-wide | Proposed | Nearest built control is the git-credential loan (`raiker/runtime/git_credential.py`) | No general sentinel/substitution path for arbitrary credentials | **YES — improvement** |
| Credential files and env vars denied to sandboxed commands | Claude Code `credentials.files` / `credentials.envVars` `deny` | Build | Implemented | Minimal child environment; `.raiker` denied, `.git` read-only | No owner-authored per-path credential deny list | PARITY |
| A persistent session environment | Claude Code, OpenClaw, Hermes | Build | Implemented | Container name is a function of owner+session+profile; reset controls ship with it | `native_sandbox` stays per-run deliberately — a predictable AppContainer name is a hole | PARITY |
| Background start / poll / wait / log / kill | Claude Code, Codex, OpenClaw, Hermes | Build | Implemented | `run_command background:true`, `background_run`, lease reconciliation | POSIX only for PTY and restart reattachment | PARITY |
| PTY / interactive input | Claude Code, Codex, Hermes | Build | Partial | `openpty` on POSIX | Windows ConPTY is unreachable from an AppContainer token (BUG-194) | PARITY |
| Remote SSH / cloud sandbox backends | Hermes (local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox), Codex cloud, OpenClaw (`ssh`, `openshell`) | Build | Partial | SSH and Daytona adapters with host-key pin, cost ceiling and no host fallback | Supervisor install/upgrade lifecycle and live remote proof remain open | PARITY |
| An escape hatch that runs a command outside the sandbox | Claude Code `dangerouslyDisableSandbox`, Codex `danger-full-access` | Build | Different by design | — | Raiker refuses the concept: an unavailable environment is refused, never rerouted to the host | **AVOID — see [4.2](#42-an-escape-hatch-out-of-the-sandbox)** |
| VM-strength containment | Cowork | Build | Proposed | — | Shared-kernel containers only (ADD-12) | NO — complexity |

### 2.5 Extensibility — hooks

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Lifecycle hook events | Claude Code documents **31** | Platform-wide | Partial | `HOOK_EVENTS` — **16**, all 16 dispatched | 15 Claude Code events have no Raiker equivalent: `Setup`, `UserPromptExpansion`, `PostToolBatch`, `Notification`, `MessageDisplay`, `TeammateIdle`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`, `DirectoryAdded`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `Elicitation`, `ElicitationResult` | PARITY |
| Handler types | Claude Code: `command`, `http`, `mcp_tool`, `prompt`, `agent` | Platform-wide | Partial | `HANDLER_TYPES = {command, builtin}` | Four refused, each needing a gated surface (BUG-226). `builtin` is Raiker's own, not one of the five | PARITY |
| Three-level `event → matcher → hooks[]` config with `if` | Claude Code | Platform-wide | Implemented | `raiker/hooks/matchers.py`, `registry.py` | — | PARITY |
| A hook can block an action | Claude Code `PreToolUse` `permissionDecision` | Shared runtime | Implemented | `DECIDING_HOOK_EVENTS = {PreToolUse, PreCompact}` | — | PARITY |
| A hook can **allow** an action the runtime refused | Claude Code (`permissionDecision: "allow"`) | Shared runtime | Different by design | `combine()` accepts only `deny` and `ask` from an authoritative handler | Deliberately absent | **AVOID — see [4.3](#43-a-hook-that-can-grant)** |
| Turn every hook off | Claude Code `disableAllHooks` | Extensions → Hooks | Implemented | `raiker/hooks/owner_switch.py` — an owner setting, not a fourth config file | — | PARITY |
| A read-only browser over configured hooks | Claude Code `/hooks` | Extensions → Hooks | Implemented | `GET /api/hooks` | — | PARITY |
| Saying which rules can actually enforce | None | Extensions → Hooks | Implemented | Per-rule "Can deny or ask" vs "Observes only", derived from the code by test | — | **YES — differentiator** |
| Naming a malformed config's file, line and column without failing the product | None — the cited reference logs or fails silently | Extensions → Hooks | Implemented | `HooksRegistry.load` | — | **YES — differentiator** |
| Async hooks that wake the agent on completion | Claude Code `async` / `asyncRewake` | Platform-wide | Proposed | — | Every Raiker handler is synchronous under a bounded timeout | NO — little advantage |

### 2.6 Extensibility — plugins, skills, MCP, channels

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| A plugin manifest with validation | Claude Code `.claude-plugin/plugin.json` | Extensions → Plugins | Implemented | `raiker/plugins/manifest.py`, `docs/architecture/PLUGIN_MANIFEST_SCHEMA.md` | — | PARITY |
| Plugin-contributed hook rules | Claude Code `hooks/hooks.json` | Extensions → Plugins | Implemented | `raiker/plugins/contributions.py`, `plugin` hook scope below every owner scope | — | **YES — improvement** |
| Plugin-contributed skills | Claude Code `skills/` — installed **active** | Extensions → Skills | Implemented | Behind `skill:contribute`, installed **inactive**, credited to the plugin | — | **YES — differentiator** |
| Plugin-contributed MCP servers | Claude Code `.mcp.json` — configured directly | Extensions → MCP | Different by design | `contributes.mcp_servers` produces an **offer**; nothing is a server until the owner adds it | — | **Different — see [3.3](#33-a-plugin-offers-an-mcp-server-it-does-not-add-one)** |
| Plugin-contributed subagents | Claude Code `agents/` | Extensions → Plugins | Proposed | — | Raiker's subagent is a per-turn bounded read-only contract, not a named installable agent | NO — conflicts |
| Plugin-contributed LSP servers | Claude Code `.lsp.json` | — | Partial | Manifest field accepted and inert | Raiker has **no language-server surface at all** to contribute to (BUG-227) | NO — little advantage |
| Plugin-contributed background monitors | Claude Code `monitors/monitors.json` | — | Proposed | — | A monitor is a long-running command whose stdout enters the turn — an execution surface Raiker keeps closed | NO — conflicts |
| Plugin-contributed executables on `PATH` | Claude Code `bin/` | Extensions → Plugins | Different by design | — | Putting plugin-authored binaries on a command's `PATH` is plugin code execution under another name | **AVOID — see [4.4](#44-plugin-code-on-the-command-path)** |
| Plugin-contributed themes / output styles | Claude Code `themes/`, `output-styles/` | — | Proposed | — | Raiker's design tokens are product-owned (`docs/architecture/VISUAL_DESIGN_SPEC.md`) | NO — little advantage |
| Plugin-contributed UI panels | No Claude Code *plugin component* is a panel — but see the row below; the frame has changed | Extensions → Plugins | Proposed | — | Named in Raiker's own `PLUGIN_SYSTEM_SPEC.md`; no route, permission or accessibility contract (BUG-228). A gap against **Raiker's own spec** | NO — little advantage |
| Server-contributed interactive UI, sandboxed and permission-gated | Claude, via [MCP Apps / SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp); OpenAI, via the Apps SDK it migrates from | Extensions → MCP | Proposed | — | **Corrected this pass.** A `ui://` resource is pre-declared, linked to a tool by metadata, rendered in a mandatory sandboxed iframe, and talks to the host over MCP's own JSON-RPC — so the host can prefetch, cache and security-review it before anything runs, and every message is auditable. That contract fits Raiker's model far better than a plugin-drawn page: the server is already governed, the surface is already sandboxed, and the traffic is already the shape the audit log records. Raiker's MCP client cannot reach it while pinned to `2024-11-05` | **YES — improvement** |
| A plugin marketplace or directory | Claude Code (`claude-plugins-official`, `claude-community`), Cowork Customize | Extensions → Plugins | Different by design | Install from a path or URL with a reviewed permission diff | — | **Different — see [3.4](#34-a-reviewed-permission-diff-instead-of-a-marketplace)** |
| Manifest authorship verification | Claude Code and Codex verify MCP transport, not manifest authorship | Extensions → Plugins | Implemented | HMAC / Ed25519 with `verified` / `present only` / `unsigned` stated either way | Default install verifies checksums only, and says so | **YES — differentiator** |
| Revocation removes what a plugin contributed | Not established by cited source | Extensions → Plugins | Implemented | Contributions are deleted, not flagged | — | **YES — improvement** |
| Owner-authored skills as Markdown | Claude Code `SKILL.md`, Cowork, Hermes | Extensions → Skills | Implemented | `raiker/skills/`, six built-ins installed on first visit | — | PARITY |
| Conformance to the **Agent Skills** open standard | All seven reference platforms, plus 40+ other products ([agentskills.io](https://agentskills.io)) | Extensions → Skills | Implemented | `raiker/skills/conformance.py` — every installed skill is measured against the [specification](https://agentskills.io/specification) on read and the answer is on its card; `raiker/skills/package.py` parses the nested `metadata:` map, `license` and `compatibility` | **Closed 2026-08-24.** Raiker's reader stays a *superset* deliberately — a skill that installed before keeps installing, and is now **told** where it diverges rather than refused. All six built-ins were brought to conformance (their `version:` moved under `metadata:`, one description trimmed under the 1024 cap). `allowed-tools` is the divergence Raiker keeps: parsed, listed on the card, and explicitly not honoured | **YES — improvement.** Everyone implements the format; what is beyond parity is being the implementation that refuses the execution parts, says so against a named standard, and reports rather than refuses |
| A skill grants no capability and ships no runnable code | Claude Code skills can invoke tools and spawn forks | Extensions → Skills | Different by design | `skill_load` returns instructions only; Raiker runs nothing a skill ships | — | **Different — see [3.5](#35-a-skill-is-instruction-only)** |
| Progressive skill loading (index first, body on demand) | Claude Code | Shared runtime | Implemented | Skill index in system context; bodies via `skill_load` | — | PARITY |
| Autonomous skill creation from experience | Hermes | Extensions → Skills | Proposed | `docs/architecture/SELF_IMPROVEMENT_MODEL.md` is specification only | A self-authored skill needs a zero-trust review gate (ADD-06) | **YES — improvement** |
| MCP client over stdio | Claude Code, Codex, Cowork | Extensions → MCP | Implemented | `raiker/runtime/executors/mcp.py`, interpreter allowlist, workspace-relative paths | — | PARITY |
| MCP client over remote transport | Claude Code, Codex, Cowork | Extensions → MCP | Implemented | `http` transport with owner-added URL and optional token; monitored, not allowlist-blocked | No OAuth flow; no SSE/streamable-HTTP session semantics — **because of the row below** | PARITY |
| Current MCP protocol revision | Claude Code, Codex, Cowork track the spec | Extensions → MCP | Partial | `MCP_PROTOCOL_VERSION = "2024-11-05"`, `raiker/runtime/executors/mcp.py` | **Found this pass.** Five revisions behind [`2026-07-28`](https://modelcontextprotocol.io/specification/versioning). The stdio session Raiker runs (`initialize`, `tools/list`, `tools/call`) is valid and interoperates with servers accepting the older handshake; everything added since is out of reach — streamable HTTP, structured tool output, resource links, elicitation, per-request `_meta` version declaration, the mandatory `server/discover` RPC, and MCP Apps. Undocumented until now | PARITY |
| MCP tool search to bound context cost | Claude Code | Shared runtime | Proposed | — | Projected MCP tools all enter the turn's tool list | **YES — improvement** |
| Building an MCP server from the product | Not established by cited source | Extensions → MCP | Implemented | `McpBuilderExecutor`, reviewed dependency-free templates | — | **YES — differentiator** |
| Inbound channels from external messaging surfaces | OpenClaw, Hermes (27+ surfaces) | Extensions → Channels | Partial | Pairing, enable switch, sender allowlist, inbound secret, 60/min per sender, signed outbound | Routing modes and approval relay are not built (BUG-225) | PARITY |
| A channel message can never raise a turn's authority | Not established by cited source — OpenClaw frames channel input as guidance to the model | Shared runtime | Implemented | Untrusted content with a named sender; trust from the pairing record | — | **YES — differentiator** |
| Separating linked / enabled / trusted / reachable | None — a connector is configured and then it works | Extensions → Channels | Implemented | Four stored facts, four remedies, four rows | — | **YES — differentiator** |

### 2.7 Memory and context

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Durable memory across sessions | ChatGPT, Cowork, Hermes | Memory | Implemented | `raiker/memory/store.py`; `memory_write` / `memory_forget` behind their own gate, **off** by default | — | PARITY |
| A memory write is a reviewed proposal, not a side effect | None — reference products write memories automatically | Memory | Implemented | Exact text shown; credential-like text refused before the decision | — | **YES — differentiator** |
| Semantic retrieval by meaning | ChatGPT, Cowork, Hermes (Honcho, Mem0, and other providers) | Memory | Implemented | Named provider or local `llama.cpp` spaces; one governed query embedding is shared by ambient and explicit recall; managed-file chunks carry revision-bound projections | Linear scoring remains backlog #5, a scale limit rather than a semantic correctness gap | **YES — improvement.** Provider/local choice, deny-safe lexical fallback, secret exclusion, exact retrieval legs and revision provenance are one control contract |
| Lexical retrieval ranked by relevance | All | Memory, Search Chat | Implemented | FTS5 + `bm25()`, with an honest FTS4/recency fallback reported on `/api/health` | — | PARITY |
| Approximate-nearest-neighbour vector index | ChatGPT, Cowork, Hermes memory providers | Memory | Partial | Every recall loads all active vectors and scores them in Python | ~431 ms at 3 000 memories, linear, paid every turn | PARITY |
| Retrieval says how each hit was found | None | Memory | Implemented | Per-hit `lexical` / `vector` / `graph` legs; the reply names the embedding space | — | **YES — differentiator** |
| A knowledge graph the model can traverse | Cowork, Hermes | Memory, Knowledge Map | Implemented | `knowledge_graph` tool: `entities`, `neighbors`, gated on `graph_indexing_runtime` | — | PARITY |
| Every graph edge names its evidence | None | Memory | Implemented | Each edge carries the approved memory that evidences it; archiving the evidence removes the edge | — | **YES — differentiator** |
| Capturing what a tool returned | All keep the tool output verbatim | Memory → Observations | Different by design | `eidetic_observations` stores summary, checksum, byte count, retention class — never the material | — | **Different — see [3.6](#36-an-observation-that-is-metadata-by-construction)** |
| Automatic context compaction | Claude Code, ChatGPT, Codex | Chat, Build | Implemented | Compaction at 90% of a known capacity; transcript unchanged | — | PARITY |
| Owner-guided summarisation of a chosen range | Claude Code (`Summarize from here` / `up to here`) | Chat | Proposed | — | Compaction is automatic only | **YES — improvement** |
| Always-on project instructions | Claude Code `CLAUDE.md` and `.claude/rules/`, Codex `AGENTS.md` | Projects | Different by design | Project instructions are governed owner records in the encrypted store, not a repository file | A repository-supplied instruction file would be untrusted content granting standing context | **Different — see [3.7](#37-project-instructions-are-owner-records-not-repository-files)** |
| Path-scoped rules that load with matching files | Claude Code `.claude/rules/` `paths` frontmatter | Projects | Proposed | — | Project instructions are whole-project | NO — little advantage |
| A retention sweep that runs by itself | ChatGPT | Memory | Partial | `expires_at` is computed and stored, enforced at read time | No sweep; cleanup is owner-confirmed (MEM-07) | PARITY |
| Memory import / export | Claude (memory import/export) | Memory | Implemented (undocumented) | `GET /api/memory/export`, `POST /api/memory/import` (`raiker/api/routes_memory.py`), surfaced in the Memory view | Found during this reconciliation: the capability shipped and no document said so | PARITY |

### 2.8 Coding agent — Raiker Build

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Read, search, glob and stat over a workspace | Claude Code, Codex, OpenClaw, Hermes | Build | Implemented | `raiker/tools/filesystem.py` | — | PARITY |
| Unified-diff patching as one reversible change set | Claude Code, Codex | Build | Implemented | `apply_patch`; one approval, one change set, no partial application | — | PARITY |
| Whitespace-tolerant, uniqueness-strict matching | Not established by cited source | Build | Implemented | Exact first, then trailing-whitespace/indentation-insensitive; two matches is a refusal | — | **YES — improvement** |
| Checkpoint before an edit | Claude Code | Shared runtime | Implemented | `raiker/checkpoints/capture.py` — pre-image before every approved mutation | — | PARITY |
| Rewind the workspace to a checkpoint | Claude Code `/rewind` | Observability → Checkpoints | Partial | `CheckpointRestoreExecutor` exists, is registered and is tested; the CLI and web surfaces show a **restore preflight only** | No route, command or tool proposes a restore, so an owner cannot actually rewind | **PARITY** |
| Rewind the conversation as well as the code | Claude Code (`Restore conversation` / `Restore code` / both) | Chat, Build | Partial | Branching seeds a new conversation from a checkpoint | No in-place conversation rewind | PARITY |
| Branch a conversation from a chosen point | ChatGPT, Claude, Claude Code `/branch` | Chat | Implemented | `POST /api/checkpoints/{id}/branch`, branch-origin lineage band | — | **YES — improvement** |
| Repository symbol index / code intelligence | Claude Code LSP plugins, Codex | Build | Partial | `raiker/graph/codemap_service.py`: real parser for Python, bounded patterns for 15 more languages | Textual `find references`; no resolved call graph, no LSP | PARITY |
| Git read commands | All | Build | Implemented | `git_status`, `git_diff`, `git_log` | — | PARITY |
| Governed git write and push | Claude Code, Codex | Build | Implemented | `git_branch`, `git_commit`, `git_push` with its own gate, egress allowlist and lent credential | HTTPS GitHub remotes only; never force, never delete | **YES — improvement** |
| Worktrees for parallel work | Claude Code (`WorktreeCreate`/`Remove`); Mux, Emdash and other agents isolate each agent in its own worktree | Build | Proposed | — | One workspace per Build session. Raiker's answer to the same need is a checkpoint plus a single reversible change set, which is stronger for *undo* and weaker for *parallelism* | NO — little advantage |
| An operating protocol carried by the coding turn | Not established by cited source | Build | Implemented | `docs/architecture/RAIKER_BUILD_PROCESS.md`; the surface is written into the audit record | — | **YES — differentiator** |
| Code review as a first-class action | Claude Code `/code-review` | Build, CLI | Implemented | `/review` with severity filters and saved proposals; `code-review` built-in skill | — | PARITY |
| Publishing session output as a shareable page | Claude Code Artifacts | — | N/A | — | Publishing to a hosted page is egress of workspace content by default | **NO — conflicts** |

### 2.9 Assistant — Raiker Chat

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Streamed conversation with Markdown rendering | All | Chat | Implemented | `ChatView.svelte`, sanitised Markdown | — | PARITY |
| Image and document attachments | ChatGPT, Claude, Cowork | Chat, Build | Implemented | `raiker/runtime/attachments.py`, governed attachment store | — | PARITY |
| Search across conversation history | ChatGPT, Claude, Cowork | Search Chat | Implemented | FTS5 index over titles and message bodies, showing the matched exchange | — | PARITY |
| The model can search past conversations itself | ChatGPT, Cowork | Chat, Build | Implemented | `conversation_search`, date-narrowed, returning conversation/timestamp/turn id | — | PARITY |
| The model's search and the runtime's recall agree | None — most have one path | Shared runtime | Implemented | Both call `retrieve_hybrid_memory`; asserted by test (MEM-11) | — | **YES — differentiator** |
| An incognito path that writes nothing | ChatGPT temporary chat | Chat | Implemented | Incognito switches the recall path off | — | PARITY |
| Export a conversation | ChatGPT, Claude | Chat | Implemented | HTML, Markdown or PDF; reasoning excluded by construction | — | **YES — improvement** |
| Projects as named scopes | ChatGPT Projects, Claude Projects, Cowork Projects | Projects | Implemented | Project instructions, shared attachments, per-project sessions | — | PARITY |
| Citations resolved against what was read | Partially — reference products cite sources | Chat, Knowledge Map | Implemented | Reference graph records the contributed text; a deleted source is reported missing, not dropped | — | **YES — differentiator** |
| Voice input | ChatGPT, Claude | Chat, Build | Implemented | Dictation into the editable draft; Done never sends; no audio stored | — | **YES — improvement** |
| Full-duplex live voice with interruption | ChatGPT, Claude | Chat | Proposed | — | Turn-based only, by decision | PARITY |
| Read a reply aloud | ChatGPT, Claude | Chat | Implemented | Manual playback; code bodies and raw URLs excluded | — | PARITY |
| Computer use / desktop control | Cowork, ChatGPT agent mode | — | N/A | — | Screen and input control is a capability class with no governed executor and no threat model here | **NO — conflicts** |
| Governed **browser** control, distinct from computer use | Cowork via [Claude in Chrome](https://claude.com/docs/cowork/overview); Hermes via CDP and cloud backends | — | Proposed | — | A headless browser driven through a named tool set is a far narrower surface than screen and input control: destinations answer to the same address guard `web_fetch` uses, page text arrives through the same sanitiser, and every navigation is a governed action. Raiker has neither, and conflates the two today | **YES — improvement** |

### 2.10 Tasks, schedules and background work

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Delegate work that outlives the turn | Cowork Tasks, ChatGPT agent mode | Tasks | Implemented | `raiker/tasks/manager.py` | — | PARITY |
| A recurring schedule | Cowork Routines, ChatGPT automations, Hermes cron | Tasks | Partial | Four named cadences (`continuous`, `hourly`, `daily`, `weekly`) | No time-of-day, no cron expression, no timezone binding, no one-shot | PARITY |
| A schedule that fires while the host is closed | Cowork (hosted), ChatGPT | Tasks | Partial | The 15-second tick lives in the FastAPI lifespan | A closed laptop is a missed cadence, recorded honestly | **N/A for a local-first product** |
| A parked run reads as blocked, not failed | Not established by cited source | Tasks | Implemented | `task_blocked` with the reason and a link to the decision | — | **YES — improvement** |
| One cycle is one governed turn | Not established by cited source | Shared runtime | Implemented | Every cycle passes policy, gates and approvals like a typed prompt | — | **YES — differentiator** |
| Notifying the owner when background work finishes | Cowork, ChatGPT | Observability → Notifications | Partial | Notification records exist | No outbound push; a finished cycle updates the view and the log | PARITY |
| Nested / delegated task ownership | Cowork [Dispatch](https://claude.com/docs/cowork/guide/dispatch) | Tasks | Partial | Tasks are nestable | Nothing owns a set of delegated child tasks (BUG-220). Dispatch is the concrete reference shape: one brief, many child tasks, each tracked to a terminal state, children that cannot spawn further children | PARITY |
| A delegating agent that routes a child task to the right **surface** | Cowork Dispatch — coding work to Code, knowledge work to Cowork | Tasks, Chat, Build | Proposed | — | Raiker already has the two surfaces and one governed turn contract across both, so routing a child task to Chat or Build is a scheduling decision rather than a new execution path. Nothing does it today | **YES — improvement** |
| An unanswered permission prompt auto-denies and the task continues | Cowork Dispatch — ten minutes, then denied | Approvals | Different by design | Raiker **parks** the turn (`turn_suspended_for_approval`) and resumes it when the owner decides; `dont_ask` declines immediately and records `denied_no_one_to_ask` | Raiker never silently continues past a decision it did not get. A timeout that proceeds without the action produces a turn whose result depends on how fast someone read a notification | **AVOID** |
| Remote sessions that continue server-side | Cowork remote sessions | — | N/A | — | Raiker runs on the owner's machine by construction | **NO — conflicts** |

### 2.11 Models and providers

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Owner choice of model provider | Codex `model_providers`, OpenClaw, Hermes | Models | Implemented | **Three adapters** (`raiker/models/providers/`): Anthropic Messages, OpenAI-compatible and llama.cpp server. **Ten provider families** across thirteen shipped profiles (`raiker/config/model-profiles.json`): `anthropic`, `openai`, `gemini`, `openrouter`, `ollama`, `ollama-cloud`, `lm-studio`, `llama.cpp`, `huggingface` and generic `openai-compatible` | Two of the thirteen profiles carry a seeded list price, each stamped `as_of`; the rest report cost as unknown rather than as zero | PARITY |
| Local inference | Codex `--oss`, OpenClaw, Hermes | Models | Implemented | Ollama, LM Studio, managed llama.cpp, approved-root GGUF discovery | — | **YES — improvement** |
| Pinned model acquisition | Codex (via Ollama) | Models | Implemented | Ollama pull, revision-pinned Hugging Face GGUF download, isolated conversion | — | **YES — differentiator** |
| Exact-model reachability proven before a turn | None — reference products fail at call time | Platform-wide | Implemented | `POST /api/model-readiness/check`, per owner/profile/model/endpoint, with a TTL | — | **YES — differentiator** |
| An ordered fallback chain with no silent hosted fallback | Claude Code `--fallback-model`, OpenClaw | Models | Implemented | Owner-ordered sequence judged as one chain | — | **YES — improvement** |
| Per-surface default model | None | Models | Implemented | Chat, Build, Tasks and Schedule each remember their own | — | **YES — differentiator** |
| Token and cost accounting | Claude Code `/cost`, ChatGPT usage | Models | Implemented | Per-provider tokens, turns, requests, compactions, known cost, each figure's source named | Shipped list prices are unverified defaults stamped with `as_of` | PARITY |
| Reasoning-effort control | Codex `model_reasoning_effort`, Claude Code thinking levels | Chat, Build | Implemented | Validated against the exact profile's declared values | — | PARITY |
| A secondary fast/auxiliary model | Claude Code small-fast model | Models | Implemented | Advisor model with its own readiness key and Check advisor control | — | PARITY |

### 2.12 Observability, security and data control

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Encrypted local store | Not established by cited source | Platform-wide | Implemented | SQLCipher workspace database | Key-page memory locking ships **off**, with the measured reason stated on `/api/health` | **YES — differentiator** |
| OpenTelemetry export of agent activity | Cowork | Observability | Proposed | — | No OTLP emitter | **YES — improvement** |
| Prompt-injection handling for untrusted content | Claude Code, Codex, ChatGPT frame external content as data | Shared runtime | Implemented | Same framing, plus a deterministic advisory scanner that names the exact page or document and never blocks | — | **YES — differentiator** |
| A fetched page reaches the model as text, not markup | Claude Code, ChatGPT | Shared runtime | Implemented | `raiker/runtime/web_access.py`: invisible elements removed and counted, role markers defanged | — | **YES — improvement** |
| Web egress control | Claude Code `network.allowedDomains` (allowlist) | Settings → Web access | Different by design | Owner **blocklist** plus an address guard that cannot be switched off | — | **Different — see [3.8](#38-a-blocklist-plus-an-address-guard-instead-of-an-allowlist)** |
| Redaction before storage or display | Coding agents suppress known secrets in logs | Platform-wide | Implemented | Incremental UTF-8 redaction at every split, exact loaned secrets, PEM blocks, stream boundaries | — | **YES — improvement** |
| Owner-visible containment of a misbehaving component | Config-level disable in Claude Code and Codex | Settings → Security | Implemented | Per-subject `active`/`paused`/`killed`, revocable in one press | — | **YES — differentiator** |
| Signed, verifiable releases | Not established by cited source | Platform-wide | Partial | `.github/workflows/release.yml` refuses to build without signing identities | No signed artifact has been published yet | PARITY |
| A hardware root of trust for the owner credential | None | Platform-wide | Proposed | — | ADD-14 | **YES — differentiator** |

### 2.13 Interfaces and developer controls

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| A terminal client | Claude Code, Codex, OpenClaw, Hermes | CLI | Implemented | `raiker`, 100+ governed inspection commands | No rich TUI; no resume/fork flags | PARITY |
| A local web control surface | OpenClaw Control UI, Cowork | Web dashboard | Implemented | `apps/web`, loopback-bound | — | PARITY |
| A desktop application | Cowork, ChatGPT, Claude Code Desktop | Desktop | Implemented | `raiker-app`, self-contained payload, tray, five-stage wizard | No signed public release yet | PARITY |
| Slash commands in the composer | Claude Code, Codex, OpenClaw | Chat, Build | Implemented | `composerCommands.ts`; a test walks the whole set so no entry is inert | — | **YES — improvement** |
| Owner-authored slash commands | Claude Code, Codex, OpenClaw | — | Proposed | — | The skill store already holds owner-authored instructions; a command adds a trigger token and an authority question | **YES — improvement** |
| `@`-mention file completion | Claude Code, Codex | Build | Implemented | Completes against the owner-built code map, paths only, under the same gate | — | **YES — differentiator** |
| `!` bash prefix / `#` memory prefix | Claude Code | Chat, Build composers | Different by design | — | Both would be a second route into governed execution and governed memory | **AVOID — see [4.5](#45-a-second-route-into-a-governed-action)** |
| Keyboard shortcut reference in the product | Claude Code `/help`, Codex, OpenClaw | Chat, Build | Implemented | `/shortcuts`, built from the handlers that exist | — | PARITY |
| Responsive layout across viewport sizes | ChatGPT, Cowork | Web dashboard | Implemented | Bottom bar below 640 px, drawer to 1023 px, full sidebar at 1024 px+ | — | PARITY |
| An in-product user guide | Not established by cited source | Utilities → Guide | Implemented | `raiker/guide/`, served read-only from the install | — | **YES — differentiator** |
| IDE extension | Claude Code, Codex | — | Proposed | — | Phase 8 deferred | NO — little advantage |
| A programmatic SDK or headless mode | Claude Code (`-p`, Agent SDK), Codex | — | Proposed | — | The loopback API is the only programmatic surface, and it is owner-authenticated | NO — conflicts |

---

## 3. Where Raiker deliberately differs

Each of these is a place where copying the reference implementation would cost
Raiker something it is not willing to lose. They are decisions, not gaps.

### 3.1 A capability gate instead of a tool-argument rule

Claude Code matches permission rules against tool **arguments** — `Bash(git *)`,
`Edit(*.ts)`. That is expressive, and it puts the security boundary in a pattern
language the owner has to get right; a rule that fails to match is a rule that
silently does nothing.

Raiker gates the **capability** an action crosses. `git_push_execution` is a
different authority from `git_write_execution` because a push leaves the machine
and a commit does not, and no argument pattern is needed to tell them apart. The
cost is real and stated: Raiker cannot express "allow `git status` but ask for
`git push`" as one rule over one tool, and it does not pretend to.

### 3.2 A deterministic `auto` instead of a classifier

Claude Code's auto mode has a second model review each action. Raiker's `auto`
keys off the action's **risk level**
(`raiker/runtime/authority/decision_modes.py::auto_requires_approval`): only
`low`-risk actions run unprompted, and `critical` is human-only whatever the
mode says.

A classifier is more permissive and more useful; it is also a second model whose
judgement the owner cannot audit, reproduce, or appeal. A governed product's
unattended path should be one an owner can predict from a table.

**As of 2026-08-24 it is a risk lookup *and* an alignment check**
([FIXED-282](../plans/FIXED_ITEMS.md)), and the second one is deterministic for the
same reason the first is. It asks whether the turn's own record establishes the
file an action is about to change — the owner's prompt named it, or an earlier
completed step in the same turn read, listed or searched it — and withholds into
the ordinary approval queue when it does not, naming the path.

The honest counterpart, stated rather than implied: it is **narrower** than a
classifier. It will not catch a semantically wrong change to a file the turn
legitimately read, and it is not trying to. What it gives instead is a review
with no model in the authority path, a verdict recomputable from the audit trail
months later, and a refusal that names a file rather than expressing a doubt.

### 3.3 A plugin *offers* an MCP server; it does not add one

An MCP server is a tool source — the highest-authority thing a plugin could
contribute. Every compared platform lets a plugin or config file add one
directly. Raiker stores an **offer**: nothing is a server, connected or
reachable until the owner presses **Add server**, which runs the same governed
create path as typing it in. An offer can never carry a credential — `https`
only, no auth in the URL, and `auth_ref` names an environment variable.

The cost is one click. The gain is that installing a plugin is never, by itself,
consent to a new tool source.

### 3.4 A reviewed permission diff instead of a marketplace

Claude Code has curated and community marketplaces with review pipelines and
commit-SHA pinning. Raiker installs from a path or a URL and shows the owner the
**permission diff** before installing. A marketplace moves the trust decision to
a reviewer the owner never meets; a permission diff keeps it with the owner and
makes the specific grants readable. For a single-owner local product, the second
is the right trade — and it is why Raiker verifies **manifest authorship**, which
neither Claude Code nor Codex does.

### 3.5 A skill is instruction-only

Claude Code skills can invoke tools, restrict tools, and run in a forked
subagent. A Raiker skill is a document: `skill_load` returns instructions, and
Raiker executes nothing a skill ships. A skill therefore grants no capability
and opens no gate, which is what makes "installing a skill" a safe act rather
than a trust decision. Everything a skill asks for still passes the same gates.

**This is a divergence from a published standard, not from one vendor.** The
[Agent Skills specification](https://agentskills.io/specification) names
`scripts/` as "executable code that agents can run", and its experimental
`allowed-tools` field is "a space-separated string of tools that are pre-approved
to run". Raiker reads a skill's `scripts/` directory as text like any other
bundled file and runs none of it, and it would refuse `allowed-tools` even after
learning to parse the field: a skill pre-approving its own tools is a capability
grant arriving through a surface whose entire safety argument is that it grants
nothing. Installing a skill must stay reversible by deleting a document.

The rest of the standard Raiker should meet, and mostly does — see the
conformance row in [§2.6](#26-extensibility--plugins-skills-mcp-channels) for
where it does not.

### 3.6 An observation that is metadata by construction

Every compared product keeps tool output verbatim, because the transcript *is*
the memory — which makes the memory as sensitive as the most sensitive thing the
agent ever read. Raiker's `eidetic_observations` has no column that could hold
the material: summary, checksum, byte count, retention class, and an artifact
reference where one already exists. A credential-like result is refused, and the
refusal is itself a row, so an empty list is distinguishable from a disabled
feature.

### 3.7 Project instructions are owner records, not repository files

`CLAUDE.md` and `AGENTS.md` are files in the repository, so anything that can
write to the repository can write standing instructions into every future turn.
Raiker's project instructions are governed owner records in the encrypted store.
The cost is that a checked-in convention file does not travel with a clone; the
gain is that a pull request cannot grant itself standing context.

### 3.8 A blocklist plus an address guard instead of an allowlist

Claude Code's sandbox reaches only `network.allowedDomains`. Raiker's web reads
work on a fresh install and are bounded by an owner **blocklist** — plus an
address guard the owner cannot switch off: HTTPS only, no credential in the URL,
and every address a name resolves to must be public, re-checked on every redirect
and pinned so the destination cannot change between the check and the request.

An allowlist that ships empty makes the first useful action a configuration task,
and an allowlisted *name* can still resolve to a loopback interface or a cloud
metadata service. Raiker refuses that class outright rather than trusting the
list. **Emptying the blocklist opens none of it.**

---

## 4. Deliberately refused

### 4.1 A mode that skips every check

Claude Code's `bypassPermissions` and Codex's `danger-full-access` exist for
containers and CI. Raiker has no equivalent and will not add one: a governed
agent whose governance can be turned off in one flag has governance as a setting
rather than as a property. The equivalent need — an unattended run that does not
park — is served by `dont_ask`, which **declines** what it is not already allowed
to do instead of allowing everything. **AVOID.**

### 4.2 An escape hatch out of the sandbox

Claude Code retries a sandbox-refused command with `dangerouslyDisableSandbox`
and re-runs it under the ordinary permission flow. Raiker refuses an unavailable
or refusing environment rather than rerouting to the host: the exact selected
profile is probed and used, and there is no silent fallback. A boundary a failure
can step outside of is a boundary that reports enforcement it does not have.
**AVOID.**

### 4.3 A hook that can grant

Claude Code hooks may return `permissionDecision: "allow"`. Raiker's `combine()`
accepts only `deny` and `ask` from an authoritative handler, so nothing a hook
returns can allow an action policy refused. A hook is a subprocess configured in
a file; making it an authority source means a file that arrived with a repository
can widen what the agent may do. **AVOID.**

### 4.4 Plugin code on the command `PATH`

Claude Code plugins may ship `bin/` executables that become bare commands inside
the Bash tool. "No plugin code runs" is a claim Raiker's Plugins tab makes in
those words, and a plugin-authored binary on a command's `PATH` is plugin code
execution with an extra step. **AVOID.**

### 4.5 A second route into a governed action

Claude Code's `!` prefix runs a shell command from the composer and `#` writes a
memory. Both are convenient and both are a second path into an action that
already has a governed one. One governed route per action is the rule the shell
and memory control sets are built on, and a shortcut that skips the approval card
is the exact defect the approval card exists to prevent. **AVOID.**

### 4.6 Publishing session output to a hosted page

Claude Code Artifacts publish session output as a hosted web page. For a
local-first product, publishing workspace content to a remote host by default
inverts the data-control property the product is chosen for. Export to a local
HTML, Markdown or PDF file already serves the reviewable-output need.
**NO — conflicts.**

### 4.7 What was deprecated in the documentation itself

Nothing Raiker ships is a candidate for removal today. The 2026-08-23
reconciliation did deprecate documentation, because keeping a stale claim
reachable is the same defect as shipping one:

| Removed or deprecated | Why |
|---|---|
| Six closed defect entries in `plans/TO_BE_FIXED.md` (BUG-216, 217, 219, 222, 223, 224) | Each was recorded in full in `plans/FIXED_ITEMS.md` as well, so the open list answered two questions and the README's claim that it "lists only what is still open" was false. The entries were removed from the open list and their index rows now name the FIXED number that holds the record |
| The 2026-06-21 "current truth" banner on three specification documents | It stated that approval resolution was metadata-only and that runtime execution was disabled for plugins, channels, shell, network and remote — none of which had been true for months |
| The "GitHub Actions remain paused for quota" instruction, in four documents | Actions run on every pull request and push to `main` |
| `MODEL_PROVIDER_CONTRACT.md`'s "Phase 1 implements only the deterministic `mock` provider" | Real adapters ship. **The replacement text was itself wrong** and is corrected below |
| ★ The claim that a `mock` provider is one of the shipped adapters, in `MODEL_PROVIDER_CONTRACT.md` and `MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | **Three** adapters ship, and there is no mock. `AsyncProviderFactory.create` **refuses** `mock`, `test` and `test_only` profiles with `test_provider_not_available`, and `enabled_for_tests_only` with `test_only_profile_not_runnable`. This is a governance property, not housekeeping: readiness exists to prove an exact model at an exact endpoint can really answer, and a provider that answers without a model would let every readiness gate pass over nothing. Guarded by `tests/test_docs_consistency.py`. The same false claim was corrected in `NON_GOALS_AND_BOUNDARIES.md`, which named it "the offline/test fallback" |
| ★ `EXTENSIBILITY_MODEL.md`'s "two contribution kinds" and "rate limits … remain unbuilt" | Plugins contribute **three** kinds — hook rules, skills and MCP-server offers, each behind its own declared permission — and per-sender inbound rate limiting **is** built (60/minute, `CHANNEL_INBOUND_DEFAULT_MAX`) |
| ★ `THREAT_MODEL.md`'s "`EXECUTABLE_ON_APPROVAL`, an explicit two-member frozenset" | It has **twelve** members. The section was written when it had two and was never revisited, so the repository-wide threat model understated what an approval performs by a factor of six |
| ★ The user guide's "`scripts/` for code to run", four lines below "Raiker never runs code a skill ships" | Raiker stores a skill's `scripts/` and runs none of it. The two sentences contradicted each other on the same page, and the wrong one was the reassuring one |
| ★ `REFERENCE_PLATFORM_COMPATIBILITY.md`'s own "last reconciliation: 2026-08-24" | A date one day in the future, in four documents. Corrected to 2026-08-23 |
| ★ `CHANNELS_SPEC.md`'s "Hermes Agent's 20+ messaging surfaces" | 27+, which this document already recorded — two documents disagreeing about the same cited source |
| The dated sections of `HANDOFF.md` | Deprecated in place with a currency banner naming what replaced them, rather than deleted: a handoff note rewritten after the fact is not a record of anything |
| `EVENT_CATALOG.md`'s "approval resolution does not emit execution events" | It emits `approval_executed`, `approval_execution_denied` and `approval_auto_executed` |
| The claim that web egress answers to `RAIKER_WEB_EGRESS_ALLOWLIST` | That variable no longer exists; egress answers to an owner blocklist plus a non-optional address guard |

---

## 5. Prioritised backlog

Ordered strictly by [§0.4](#04-priority-and-effort-ordering). Every row states
the proposed action, what it does for governance, and whether it puts Raiker
ahead of the reference set.

**This ordering is by priority then effort.** A second ordering — by *how many
of Raiker's four pillars an item unblocks* — is in
[`plans/PILLAR_MAP.md`](../plans/PILLAR_MAP.md). Where the two differ, the
difference is informative rather than a conflict: this document says what an item
costs, the pillar map says what it is for. The two agree that items 1–4 come
first.

**Closed since the last pass.** Two items, both removed rather than left
standing:

- *"Eight gated capabilities have no threat model"* — **done**. Re-deriving the
  comparison found the count understated, because it credited any document that
  mentioned a capability's name in passing; eleven documents were written rather
  than eight, and **all forty-five capabilities with a real executor now have
  one**. See
  [the threat-models index](../threat-models/README.md#coverage--every-capability-with-a-real-executor-has-one).
- *"`RUNTIME_EXECUTORS_SPEC.md` omits 17 capabilities"* was carried here after it
  had already been completed. Re-checked on 2026-08-23: all 66 names in
  `ALL_CAPABILITIES` (`raiker/phase_gates.py`), including all 45 in
  `REAL_EXECUTOR_CAPABILITIES` (`raiker/runtime/executors/__init__.py`), appear in
  [`RUNTIME_EXECUTORS_SPEC.md`](RUNTIME_EXECUTORS_SPEC.md).

A backlog that lists finished work is the same defect as a document that claims
unfinished work is done. Rows are renumbered; **new items from the 2026-08-23
pass are marked ★**.

**Closed 2026-08-25 — four rows, and the whole of the Medium/Low section bar
one.** Items 10, 11, 12 and 25 are struck through in place with what closed them,
and item 1's provider leg is done. Recorded here rather than removed, because a
reader arriving with one of those numbers should not have to guess:

- **#1 — semantic recall closed end to end** ([FIXED-283](../plans/FIXED_ITEMS.md),
  [FIXED-292](../plans/FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered),
  [FIXED-293](../plans/FIXED_ITEMS.md#fixed-293--local-semantic-memory-still-required-a-hosted-provider),
  [FIXED-294](../plans/FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words)).
  Provider and keyless-local writes and reads now share one governed route;
  managed files use revision-safe semantic projections. The remaining linear
  scan is scale backlog #5, not an incomplete semantic path. **YES —
  improvement** for the combined consent, provenance and fallback contract.
- **#12 — the retention sweep** ([FIXED-284](../plans/FIXED_ITEMS.md)).
- **#10 — every cadence reachable, anchored to a chosen first run**
  ([FIXED-285](../plans/FIXED_ITEMS.md)).
- **#11 — a parent owns its children's terminal states**
  ([FIXED-286](../plans/FIXED_ITEMS.md)).
- **#25 — tool rows survive a reload** ([FIXED-287](../plans/FIXED_ITEMS.md)).

Three interface defects found while exercising those live are
[FIXED-288](../plans/FIXED_ITEMS.md): an enabled capability offering "Turn on"
beside "Turn off", a permission list that could not be scanned for what is on,
and a successful readiness check titled "Repair model connection".

**Closed 2026-08-24 — two governance-architecture items that were not on this
list**, because both were raised in
[`plans/GOVERNANCE_ENTRY_PATHS.md`](../plans/GOVERNANCE_ENTRY_PATHS.md) and had not
yet been prioritised here. Recorded so the omission does not read as an oversight:

- **GEP-04 — fifteen capability switches governed nothing**
  ([FIXED-280](../plans/FIXED_ITEMS.md)). Not the ungoverned-action gap it was
  raised as. `plugin_install` was a real hole — the terminal wrote an install
  record without ever reading the gate — and `subagents` was an inert switch;
  the other thirteen were governed elsewhere or reached by nothing. What each
  gate decides is now a checked field the Capabilities page renders.
  **YES — differentiator**: every compared platform ships a permission surface,
  and none tells you which of its switches actually does something.
- **GEP-01 — one shared capability-admission read**
  ([FIXED-279](../plans/FIXED_ITEMS.md)). Eight copies, two drifts, one of them live
  and pointed at the model: the context bundle told it `web_fetch: disabled` on
  an install where the tool would have fetched. **YES — improvement.**

### High priority, low effort

**Empty as of 2026-08-23.** All four rows this section held were closed in one
pass, and each is recorded in
[`plans/FIXED_ITEMS.md`](../plans/FIXED_ITEMS.md) with the interface outcome that
had to be true first:

* **Checkpoint rewind is reachable.** `POST /api/checkpoints/{id}/restore` and
  `/checkpoints restore <id> --confirm` raise an ordinary approval for
  `checkpoint_restore_execution`, now the thirteenth member of
  `EXECUTABLE_ON_APPROVAL`. A cross-principal restore is classified critical and
  takes the human-only lifecycle instead.
* **Audit export has a route.** `audit_export` has an executor and `POST
  /api/audit/export` behind it, plus a listing and a download; the export is
  redacted as the on-screen record is, scoped to the acting principal's own
  account, and is itself an audited event.
* **The second, weaker egress path is deleted.** `NetworkExecutor`, the
  `network_execution` capability and `sandbox.fetch_url` are gone, and
  `WebFetchExecutor` delegates to `WebAccessService`. `process_execution` was
  assessed in the same pass and **kept**: it enters the same `CommandService`
  lifecycle `shell_execution` does, so it is an unused path rather than a weaker
  one.
* **An oversize file says so before you approve.** The approval notice consults
  the target's size and, above `MAX_PRE_IMAGE_BYTES`, replaces the rewind
  sentence with one that states the change cannot be undone and why.

### High priority, medium effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| ~~1~~ | ~~Semantic memory retrieval (MEM-10)~~ | **Done 2026-08-26 — [FIXED-283](../plans/FIXED_ITEMS.md), [FIXED-292](../plans/FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered), [FIXED-293](../plans/FIXED_ITEMS.md#fixed-293--local-semantic-memory-still-required-a-hosted-provider), [FIXED-294](../plans/FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words).** Provider and local GGUF paths build and query named spaces through one governed runtime; managed-file passages are revision-bound and owner/project-scoped | Ask/deny/off fall back without blocking a read; secret-like text is excluded; audit stores model/dimension/hash metadata rather than query text or vectors | **YES — improvement.** The reference semantic feature is parity; the combined local/hosted consent, fallback and exact-provenance control set goes beyond it |
| 2 | Channel routing modes and approval relay (BUG-225) | Implement the spec's routing modes behind their own gate, with the accepted authority contract unchanged | An inbound message becoming work is the highest-risk transition in the product; it needs its own gate, not the transport's | PARITY |
| ~~3~~ | ~~Auto mode has no alignment check (BUG-218)~~ | **Done 2026-08-24 — [FIXED-282](../plans/FIXED_ITEMS.md).** A deterministic check over the turn's own record: an existing file the turn never read, listed or was asked about falls back to the approval queue, with the path named | `auto` is the only mode where an action runs with no human in the loop, and it now performs the review its label implies | **YES — differentiator.** Both reference implementations are model judgements; this one is set membership over the audit trail, with no model in the authority path and an answer that can be recomputed months later |
| 4 | Owner-authored slash commands | Extend the skill store with a trigger token, stating the authority the command carries | Reference products treat a command as a privileged harness path; Raiker's would grant nothing, which is the differentiator | **YES — improvement** |

### High priority, high effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 5 | Vector recall is linear (MEM-10 remainder) | Add an approximate-nearest-neighbour index over the existing vector store | Recall cost is paid on every turn and grows with the owner's history | PARITY |
| 6 | Filtered domain egress unproven | Complete the container proof for allowed traffic, bypass denial and mid-stream revocation | `filtered_network` stays false until the boundary is measured, which is the rule the sandbox card is built on | PARITY |
| 7 | Credential delivery and delta quarantine | Finish copy-on-write delivery and the two-pass delta merge | Post-use quarantine of what a credentialed run left behind is a control no compared product exposes | **YES — differentiator** |
| 8 | Windows PTY and restart reattachment (BUG-194) | Design an authorised Windows transport rather than porting the POSIX one | A named pipe is reachable by name from any session; the authorisation story has to come first | PARITY |

### Medium priority, low effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 9 | Owner-guided summarisation of a range | Add "summarise from here / up to here" over the existing compaction path | Context control becomes the owner's rather than a threshold's | **YES — improvement** |
| ~~10~~ | ~~Task cadences are four names~~ | **Done 2026-08-25 — [FIXED-285](../plans/FIXED_ITEMS.md).** The chip row names the shape of the work and a Repeat select names the interval; every cadence the scheduler honours is reachable from the page that plans work, and a routine is anchored to a first run the owner picked. Build's standing-agent panel takes the same optional start time | A daily task that ran a day after it was created was not a schedule anybody chose | PARITY |
| ~~11~~ | ~~Nothing owns delegated child tasks (BUG-220)~~ | **Done 2026-08-25 — [FIXED-286](../plans/FIXED_ITEMS.md).** A parent with an open child parks as `waiting_for_children` and settles when the last one lands; nothing is inherited downward, so a child still carries its own approvals | A parent that reported done while a child was parked was a false completion. The routing half is item 23 below | PARITY |
| ~~12~~ | ~~Retention sweep (MEM-07)~~ | **Done 2026-08-25 — [FIXED-284](../plans/FIXED_ITEMS.md).** Memory → Observations says how many records are past their retention class and offers the owner-confirmed cleanup. No daemon was added; the deliberate alternative was built. Both the preview and the delete were unscoped and are now scoped to the acting principal | An expiry enforced only at read time was a policy the storage did not keep | PARITY |
| ~~13~~ | ~~**Agent Skills standard conformance**~~ | **Done 2026-08-24 — [FIXED-281](../plans/FIXED_ITEMS.md).** Measured on every read and reported on the skill's card; the nested `metadata:` map, `license` and `compatibility` parse; all six built-ins conform; `allowed-tools` is parsed, listed and explicitly not honoured | A skill an owner writes in Raiker now installs in the other forty products, and the one place Raiker diverges is stated against a named standard rather than asserted as taste | **YES — improvement** |

### Medium priority, medium effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 14 | Hook lifecycle coverage | Add the four Raiker-meaningful events from Claude Code's 31 — `ConfigChange`, `Notification`, `PostToolBatch`, `InstructionsLoaded`. The other eleven are assessed individually in [`HOOKS_SPEC.md`](HOOKS_SPEC.md#which-of-the-fifteen-are-worth-adding): four are N/A to a single-owner local product, five are of little value, and two are blocked behind the mid-turn question surface (item 17) | A hook surface that covers half the lifecycle can enforce guards for half of it. `ConfigChange` is the one that goes beyond parity: "the owner changed a setting" is a governance fact nothing in Raiker can currently hook | PARITY, except `ConfigChange` — **YES, differentiator** |
| 15 | The `prompt` hook handler (BUG-226) | Build it first of the four: it makes no outbound request and its output is context, not a decision | Each refused handler needs a gated surface; this is the only one that needs none | PARITY |
| 16 | MCP tool search and deferred tool schemas | Bound the context cost of projected MCP tools, and of the 45 built-ins that enter every turn | A connected server should not cost every turn its whole schema | **YES — improvement** |
| 17 ★ | **A structured question to the owner mid-turn** | Add one question surface — the model asks, the owner picks, the turn continues — reusing the approval transport and the same redaction | Today Raiker's only mid-turn interruption asks *may I do this*. There is no way to ask *which of these did you mean*, so a model facing two readings guesses and the owner finds out afterwards. A question grants nothing, executes nothing and needs no gate of its own, which is what makes it cheap; MCP's `2026-07-28` elicitation would then have a surface to land on | **YES — improvement** |
| 18 | OpenTelemetry export | Emit governed events over OTLP behind its own capability gate, metadata-only by default with content capture as an explicit opt-in | [Cowork exports six events this way](https://claude.com/docs/cowork/monitoring) — including `tool_decision`, which carries the decision *and* its source. Raiker already records strictly more per action than that; what it lacks is the wire to carry it anywhere | **YES — improvement** |
| 19 | Credential masking with sentinel substitution | Generalise the git-credential loan into a sentinel/substitution path for owner-declared credentials | A command that authenticates without ever holding the secret is strictly better than one that holds it briefly | **YES — improvement** |

### Medium priority, high effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 20 | Deterministic replay | Make the event log replayable, as DeepSeek Harness's trajectory is | Replay turns an audit trail into a verification tool | **YES — improvement** |
| 21 | Autonomous skill creation with a review gate | Implement `SELF_IMPROVEMENT_MODEL.md` behind a zero-trust review (ADD-06) | A self-authored instruction that reaches turns without review is self-granted agency | **YES — improvement** |
| 22 | Remote supervisor install lifecycle | Complete SSH/Daytona supervisor install, upgrade and live proof | Remote backends are adapters today and readiness-blocked in practice | PARITY |
| 23 ★ | **A delegating task that owns its children and routes by surface** | Extend BUG-220's parent/child ownership so a parent also chooses Chat or Build per child, as [Cowork Dispatch](https://claude.com/docs/cowork/guide/dispatch) does — **without** its ten-minute auto-deny, which Raiker refuses | Raiker already has both surfaces under one governed turn contract, so this is scheduling rather than a new execution path. It is the difference between "tasks nest" and "one brief becomes finished work" | **YES — improvement** |
| 24 ★ | **Governed browser control** | A headless browser behind its own capability and its own threat model: destinations answer to `web_fetch`'s address guard, page text through the same sanitiser, every navigation a governed action, no screen or input control | The reference platforms reach the web interactively ([Claude in Chrome](https://claude.com/docs/cowork/overview), Hermes via CDP) and Raiker can only read a page. Doing it as a *narrow tool set* rather than as computer use is the governance argument — and keeps [§2.9](#29-assistant--raiker-chat)'s refusal of screen control intact | **YES — improvement** |

### Low priority, low effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| ~~25~~ | ~~Tool rows do not survive a reload~~ | **Done 2026-08-25 — [FIXED-287](../plans/FIXED_ITEMS.md).** Rebuilt from `tool_actions` through the same presentation function the live stream uses, so a reloaded row carries exactly what the live one did and cannot carry more | A transcript that lost half its record on reload was a weaker record | PARITY |
| 26 | Live-spec sign-in (BUG-229) | Let the live specs sign in against a non-empty workspace | A test harness that only works on an empty workspace tests an empty workspace | NO — little advantage |

### Low priority, medium effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 27 | Plugin panels (BUG-228) | If built, declarative only, so "no plugin code runs in this browser" stays literally true | A gap against Raiker's own spec. **Reassessed this pass:** the row below is the better answer to the same need, and building both would be two contradictory UI-contribution models | NO — little advantage |
| 28 ★ | **MCP Apps ([SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp))** | Once the protocol revision above lands, render a connected server's pre-declared `ui://` resource in a sandboxed iframe under its own capability gate and a per-app owner permission | This is the shape Raiker would have had to invent for panels, already specified and already reviewed by someone else: the resource is declared ahead of time so the host can fetch and inspect it before anything runs, the iframe sandbox is mandatory rather than advisory, and every message between the UI and the host is MCP JSON-RPC — auditable in the record Raiker already keeps. It also arrives with the property Raiker's plugin model insists on: the UI belongs to a server the owner already added, not to a plugin that added itself | **YES — improvement** |
| 29 | Path-scoped project rules | Scope project instructions to path patterns | Smaller standing context is a real benefit; the authority question is already settled | NO — little advantage |
| 30 | Conversation rewind in place | Restore a conversation to a chosen turn, as `/rewind` does | Branching already covers the safe half; in-place rewind discards a record | NO — little advantage |

### Low priority, high effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 31 | LSP surface (BUG-227) | Decide whether Raiker wants a language-server client at all before building one to satisfy a manifest field | The code map already answers part of the need | NO — little advantage |
| 32 | Ephemeral micro-VMs (ADD-12) | Replace shared-kernel containers for the highest-risk work | A different class of boundary; only Cowork has one | NO — complexity |
| 33 | IDE extension | Phase 8 deferred | No governance effect; a surface question | NO — little advantage |

---

## 6. Control-set reviews (evidence)

The dated rounds this document is drawn from are the
[**reference review log**](REFERENCE_REVIEW_LOG.md) — every review since
2026-08-16, with the platforms it was run against, the scope it covered, what it
shipped, and what it deliberately did not build.

They are kept apart from Parts 0–5 on purpose. A canonical comparison that also
carries every round it went through stops describing the product as it is and
becomes a record of how it got there; both are worth having, and they answer
different questions. **Where a review and Part 2 disagree, Part 2 is current.**

The log also holds the concept-to-specification maps — Claude Code concept
coverage and its per-page documentation mapping, Cowork delegated tasks and
schedule, OpenClaw-style personal agent, Hermes-style agent framework, eidetic
memory, multi-agent, graph context, skills, memory, local inference,
LangChain/LangGraph-style runtime, OWASP GenAI, self-improvement, mem0-style
memory and memsearch-style semantic search — and every control-set review
(turn transparency, composer, turn continuation, model readiness, desktop
onboarding, governed shell and sandbox, resilience and containment, observation
capture, agent-reachable memory, text search and retrieval, skills and extension
authoring, first-run provider setup, live work, governed voice, and conversation
branching).

---

## 7. Rule for new references

This is a standing rule, not a record of one pass.

When Raiker adopts a concept from another platform, the documentation must add
the concept name, Raiker's behaviour, the contract or schema, the lifecycle,
the storage, the security rules, the events, the tests, the UI surface, and the
build phase. **If these are not all present, the concept is not considered fully
specified** and must not be described as implemented.

Two additions to the rule, from the 2026-08-23 pass:

- **Cite the standard, not only the product.** Where a concept has an open
  specification — [MCP](https://modelcontextprotocol.io/),
  [Agent Skills](https://agentskills.io/specification) — the specification is the
  source, and a vendor's implementation of it is a second citation rather than
  the first. It is the difference between "Claude Code does this" and "this is
  the format, and here is how far Raiker conforms".
- **Record the protocol revision a client speaks.** Raiker's MCP client was five
  revisions behind the current specification, and nothing in the documentation
  said so, because no row asked. A version number is a capability claim.
