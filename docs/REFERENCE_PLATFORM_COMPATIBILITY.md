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
**2026-08-24**.

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
| **Claude Cowork** | Anthropic's knowledge-worker agent: folder/remote sessions, delegated tasks, routines, plugins, connectors | Raiker Chat and the shared runtime | [Cowork overview](https://claude.com/docs/cowork/overview), [Get started](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork), [Schedule recurring tasks](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork), [Projects in Cowork](https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork), [Computer use in Cowork](https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork), [Monitoring (OpenTelemetry)](https://claude.com/docs/cowork/monitoring), [OpenTelemetry monitoring (support article)](https://support.claude.com/en/articles/14477985-monitor-claude-cowork-activity-with-opentelemetry) |
| **Claude Code** | Anthropic's coding agent: tools, permissions, sandboxing, hooks, skills, subagents, plugins, MCP | Raiker Build and the shared runtime | [Extend Claude Code](https://code.claude.com/docs/en/features-overview), [How it works](https://code.claude.com/docs/en/how-claude-code-works), [Tools reference](https://code.claude.com/docs/en/tools-reference), [Permissions](https://code.claude.com/docs/en/permissions), [Permission modes](https://code.claude.com/docs/en/permission-modes), [Sandboxing](https://code.claude.com/docs/en/sandboxing), [Sandbox environments](https://code.claude.com/docs/en/sandbox-environments), [Hooks](https://code.claude.com/docs/en/hooks), [Plugins](https://code.claude.com/docs/en/plugins), [Plugins reference](https://code.claude.com/docs/en/plugins-reference), [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces), [Skills](https://code.claude.com/docs/en/skills), [Subagents](https://code.claude.com/docs/en/sub-agents), [Workflows](https://code.claude.com/docs/en/workflows), [Cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), [MCP](https://code.claude.com/docs/en/mcp), [CLAUDE.md](https://code.claude.com/docs/en/memory), [Checkpointing](https://code.claude.com/docs/en/checkpointing), [Artifacts](https://code.claude.com/docs/en/artifacts), [Managed settings](https://code.claude.com/docs/en/managed-settings), [Settings reference](https://code.claude.com/docs/en/settings-reference), [Security](https://code.claude.com/docs/en/security), [Monitoring](https://code.claude.com/docs/en/monitoring-usage), [Sandboxing engineering post](https://www.anthropic.com/engineering/claude-code-sandboxing), [Containment engineering post](https://www.anthropic.com/engineering/how-we-contain-claude) |
| **ChatGPT Chat / Work** | OpenAI's assistant and workspace product: apps/connectors, projects, memory, agent mode, scheduled automations | Raiker Chat and the shared runtime | [Connectors in ChatGPT](https://help.openai.com/en/articles/11487775-connectors-in-chatgpt), [Projects](https://help.openai.com/en/articles/10169521-using-projects), [Memory FAQ](https://help.openai.com/en/articles/8590148-memory-in-chatgpt-faq), [Voice mode FAQ](https://help.openai.com/en/articles/8400625-voice-mode-faq), [ChatGPT Work admin FAQ](https://learn.chatgpt.com/docs/enterprise/work-admin-faq) |
| **OpenAI Codex** | OpenAI's coding agent: CLI, IDE and cloud, with `sandbox_mode` and `approval_policy` as separate controls | Raiker Build and the shared runtime | [Codex sandboxing](https://learn.chatgpt.com/docs/sandboxing), [Codex manual](https://developers.openai.com/codex/codex-manual.md), [Running Codex safely](https://openai.com/index/running-codex-safely/), [Windows sandbox](https://openai.com/index/building-codex-windows-sandbox/), [Codex upgrades](https://openai.com/index/introducing-upgrades-to-codex/) |
| **OpenClaw** | Open-source local-first personal-agent gateway: channels, exec tool, optional container sandboxing, plugins | Platform-wide, and Raiker's channel and execution surfaces | [Docs](https://docs.openclaw.ai/), [Architecture](https://docs.openclaw.ai/concepts/architecture), [Gateway sandboxing](https://github.com/openclaw/openclaw/blob/main/docs/gateway/sandboxing.md), [Exec tool](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec.md), [Exec approvals](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec-approvals.md), [Control UI](https://docs.openclaw.ai/web/control-ui), [Setup wizard](https://docs.openclaw.ai/start/wizard) |
| **DeepSeek Harness** | MIT-licensed agent harness (developer preview, v0.1, 2026-08-13) where models, tools, skills, sessions, sandboxes, storage, loops, scheduling and UI are all plugins, over an append-only trajectory | Platform-wide, and Raiker's extensibility and observability surfaces | [DeepSeek Harness](https://deepseek.com/harness/en/) |
| **Hermes Agent** | Nous Research's self-improving agent: seven terminal backends, 40+ tools, pluggable memory providers, autonomous skill creation, 27+ messaging surfaces | Platform-wide, and Raiker's execution, memory and channel surfaces | [Hermes Agent docs](https://hermes-agent.nousresearch.com/docs/), [Features overview](https://hermes-agent.nousresearch.com/docs/user-guide/features/overview), [Tools and toolsets](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools), [Persistent memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory), [Messaging gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/), [Repository](https://github.com/NousResearch/hermes-agent) |

**Source discipline.** A claim about a reference platform is made only from that
platform's own documentation. Where a source could not be re-read during a
pass, the claim is kept as previously recorded and is not strengthened. "Not
established by cited source" is written rather than a guess.

**Verification status of the source list above.** Every external URL cited in
this document was requested during the 2026-08-24 reconciliation, and the result
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
| `modelcontextprotocol.io`, `genai.owasp.org`, `huggingface.co`, `openrouter.ai`, `lmstudio.ai`, `docs.ollama.com`, `pypi.org` | Reachable | Entry points confirmed to resolve |
| `openai.com`, `help.openai.com`, `platform.openai.com` | **Bot-blocked (HTTP 403), not dead** | These refuse automated requests. The URLs are canonical and were not invented; claims resting on them alone are still not strengthened |

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
  and it sharpens backlog item 19 rather than changing it.
- **Hermes supports more messaging surfaces than recorded.** The [messaging
  gateway docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/)
  name **27+** platforms; this document said "20+", which was conservative rather
  than wrong. The messaging source is now cited alongside the tools source.
- **Hermes's seven terminal backends and 40+ tools are confirmed** from the
  vendor's own tools page and repository README, rather than carried forward.

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
  panel component at all.

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
| Auto mode reviewed by a classifier model | Claude Code auto mode | Permissions | Different by design | `auto_requires_approval` keys off the action's risk level, not a model call | Raiker's `auto` is deterministic; it has no alignment check of its own (BUG-218) | **Different — see [3.2](#32-a-deterministic-auto-instead-of-a-classifier)** |
| Critical actions never auto-approved | Claude Code protected paths, Codex | Shared runtime | Implemented | `raiker/runtime/authority/critical.py`; critical risk is human-only with step-up | — | **YES — improvement** |
| Standing per-tool grants | Claude Code "don't ask again" | Permissions, Git credential | Implemented | Decision modes; `run_command` standing grants; git-credential loan scopes | — | PARITY |

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
| A plugin manifest with validation | Claude Code `.claude-plugin/plugin.json` | Extensions → Plugins | Implemented | `raiker/plugins/manifest.py`, `docs/PLUGIN_MANIFEST_SCHEMA.md` | — | PARITY |
| Plugin-contributed hook rules | Claude Code `hooks/hooks.json` | Extensions → Plugins | Implemented | `raiker/plugins/contributions.py`, `plugin` hook scope below every owner scope | — | **YES — improvement** |
| Plugin-contributed skills | Claude Code `skills/` — installed **active** | Extensions → Skills | Implemented | Behind `skill:contribute`, installed **inactive**, credited to the plugin | — | **YES — differentiator** |
| Plugin-contributed MCP servers | Claude Code `.mcp.json` — configured directly | Extensions → MCP | Different by design | `contributes.mcp_servers` produces an **offer**; nothing is a server until the owner adds it | — | **Different — see [3.3](#33-a-plugin-offers-an-mcp-server-it-does-not-add-one)** |
| Plugin-contributed subagents | Claude Code `agents/` | Extensions → Plugins | Proposed | — | Raiker's subagent is a per-turn bounded read-only contract, not a named installable agent | NO — conflicts |
| Plugin-contributed LSP servers | Claude Code `.lsp.json` | — | Partial | Manifest field accepted and inert | Raiker has **no language-server surface at all** to contribute to (BUG-227) | NO — little advantage |
| Plugin-contributed background monitors | Claude Code `monitors/monitors.json` | — | Proposed | — | A monitor is a long-running command whose stdout enters the turn — an execution surface Raiker keeps closed | NO — conflicts |
| Plugin-contributed executables on `PATH` | Claude Code `bin/` | Extensions → Plugins | Different by design | — | Putting plugin-authored binaries on a command's `PATH` is plugin code execution under another name | **AVOID — see [4.4](#44-plugin-code-on-the-command-path)** |
| Plugin-contributed themes / output styles | Claude Code `themes/`, `output-styles/` | — | Proposed | — | Raiker's design tokens are product-owned (`docs/VISUAL_DESIGN_SPEC.md`) | NO — little advantage |
| Plugin-contributed UI panels | **None of the compared platforms** — Claude Code plugin components are skills, agents, hooks, MCP, LSP and monitors | Extensions → Plugins | Proposed | — | Named in Raiker's own `PLUGIN_SYSTEM_SPEC.md`; no route, permission or accessibility contract (BUG-228). This is a gap against **Raiker's own spec**, not against a reference platform | NO — little advantage |
| A plugin marketplace or directory | Claude Code (`claude-plugins-official`, `claude-community`), Cowork Customize | Extensions → Plugins | Different by design | Install from a path or URL with a reviewed permission diff | — | **Different — see [3.4](#34-a-reviewed-permission-diff-instead-of-a-marketplace)** |
| Manifest authorship verification | Claude Code and Codex verify MCP transport, not manifest authorship | Extensions → Plugins | Implemented | HMAC / Ed25519 with `verified` / `present only` / `unsigned` stated either way | Default install verifies checksums only, and says so | **YES — differentiator** |
| Revocation removes what a plugin contributed | Not established by cited source | Extensions → Plugins | Implemented | Contributions are deleted, not flagged | — | **YES — improvement** |
| Owner-authored skills as Markdown | Claude Code `SKILL.md`, Cowork, Hermes | Extensions → Skills | Implemented | `raiker/skills/`, six built-ins installed on first visit | — | PARITY |
| A skill grants no capability and ships no runnable code | Claude Code skills can invoke tools and spawn forks | Extensions → Skills | Different by design | `skill_load` returns instructions only; Raiker runs nothing a skill ships | — | **Different — see [3.5](#35-a-skill-is-instruction-only)** |
| Progressive skill loading (index first, body on demand) | Claude Code | Shared runtime | Implemented | Skill index in system context; bodies via `skill_load` | — | PARITY |
| Autonomous skill creation from experience | Hermes | Extensions → Skills | Proposed | `docs/SELF_IMPROVEMENT_MODEL.md` is specification only | A self-authored skill needs a zero-trust review gate (ADD-06) | **YES — improvement** |
| MCP client over stdio | Claude Code, Codex, Cowork | Extensions → MCP | Implemented | `raiker/runtime/executors/mcp.py`, interpreter allowlist, workspace-relative paths | — | PARITY |
| MCP client over remote transport | Claude Code, Codex, Cowork | Extensions → MCP | Implemented | `http` transport with owner-added URL and optional token; monitored, not allowlist-blocked | No OAuth flow; no SSE/streamable-HTTP session semantics | PARITY |
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
| Semantic retrieval by meaning | ChatGPT, Cowork, Hermes (Honcho, Mem0, and other providers) | Memory | Partial | `raiker/vector/__init__.py` is a feature-hashing bag-of-tokens embedding with no model | A default install can recall a paraphrase only through shared words (MEM-10) | PARITY |
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
| Worktrees for parallel work | Claude Code (`WorktreeCreate`/`Remove`) | Build | Proposed | — | One workspace per Build session | NO — little advantage |
| An operating protocol carried by the coding turn | Not established by cited source | Build | Implemented | `docs/RAIKER_BUILD_PROCESS.md`; the surface is written into the audit record | — | **YES — differentiator** |
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

### 2.10 Tasks, schedules and background work

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Delegate work that outlives the turn | Cowork Tasks, ChatGPT agent mode | Tasks | Implemented | `raiker/tasks/manager.py` | — | PARITY |
| A recurring schedule | Cowork Routines, ChatGPT automations, Hermes cron | Tasks | Partial | Four named cadences (`continuous`, `hourly`, `daily`, `weekly`) | No time-of-day, no cron expression, no timezone binding, no one-shot | PARITY |
| A schedule that fires while the host is closed | Cowork (hosted), ChatGPT | Tasks | Partial | The 15-second tick lives in the FastAPI lifespan | A closed laptop is a missed cadence, recorded honestly | **N/A for a local-first product** |
| A parked run reads as blocked, not failed | Not established by cited source | Tasks | Implemented | `task_blocked` with the reason and a link to the decision | — | **YES — improvement** |
| One cycle is one governed turn | Not established by cited source | Shared runtime | Implemented | Every cycle passes policy, gates and approvals like a typed prompt | — | **YES — differentiator** |
| Notifying the owner when background work finishes | Cowork, ChatGPT | Observability → Notifications | Partial | Notification records exist | No outbound push; a finished cycle updates the view and the log | PARITY |
| Nested / delegated task ownership | Cowork | Tasks | Partial | Tasks are nestable | Nothing owns a set of delegated child tasks (BUG-220) | PARITY |
| Remote sessions that continue server-side | Cowork remote sessions | — | N/A | — | Raiker runs on the owner's machine by construction | **NO — conflicts** |

### 2.11 Models and providers

| Reference capability | Platform(s) | Raiker surface | Status | Where | Gap | Beyond? |
|---|---|---|---|---|---|---|
| Owner choice of model provider | Codex `model_providers`, OpenClaw, Hermes | Models | Implemented | Anthropic Messages, OpenAI-compatible, llama.cpp server adapters | — | PARITY |
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
unattended path should be one an owner can predict from a table. The honest
counterpart is that Raiker's `auto` has **no alignment check of its own**
(BUG-218) — it is a risk lookup, and it is described as one.

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
| `MODEL_PROVIDER_CONTRACT.md`'s "Phase 1 implements only the deterministic `mock` provider" | Four adapters ship |
| The dated sections of `HANDOFF.md` | Deprecated in place with a currency banner naming what replaced them, rather than deleted: a handoff note rewritten after the fact is not a record of anything |
| `EVENT_CATALOG.md`'s "approval resolution does not emit execution events" | It emits `approval_executed`, `approval_execution_denied` and `approval_auto_executed` |
| The claim that web egress answers to `RAIKER_WEB_EGRESS_ALLOWLIST` | That variable no longer exists; egress answers to an owner blocklist plus a non-optional address guard |

---

## 5. Prioritised backlog

Ordered strictly by [§0.4](#04-priority-and-effort-ordering). Every row states
the proposed action, what it does for governance, and whether it puts Raiker
ahead of the reference set.

**Closed since the last pass.** *"`RUNTIME_EXECUTORS_SPEC.md` omits 17
capabilities"* was carried here as a high-priority, low-effort item after it had
already been completed. Re-checked on 2026-08-24: all 67 names in
`ALL_CAPABILITIES` (`raiker/phase_gates.py`), including all 45 in
`REAL_EXECUTOR_CAPABILITIES` (`raiker/runtime/executors/__init__.py`), appear in
[`RUNTIME_EXECUTORS_SPEC.md`](RUNTIME_EXECUTORS_SPEC.md). The row is removed and
the remainder renumbered. A backlog that lists finished work is the same defect
as a document that claims unfinished work is done.

### High priority, low effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 1 | Checkpoint rewind is unreachable | Surface the existing `CheckpointRestoreExecutor` behind an approval — a route and a Checkpoints action — or state in the product that restore is preflight-only | Recoverability is a stated product property; today the executor exists and no owner can reach it | PARITY |
| 2 | Audit export has no route | Expose `audit_export` over the loopback API and the Observability view | An audit an owner cannot take out of the product is evidence they cannot use | PARITY |
| 3 | Eight gated capabilities have no threat model | Write the missing eight, listed in [the threat-models index](threat-models/README.md#capabilities-with-a-real-executor-and-no-threat-model) | Opening a higher-risk gate requires a threat-model acknowledgement. For these eight — including the two durable-memory mutations an approval really performs, and both egress capabilities — there is no written analysis to acknowledge | PARITY |

### High priority, medium effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 4 | Semantic memory retrieval (MEM-10) | Let the owner select a real embedding model — a local download or an explicit provider egress — keeping the labelled hashing fallback as the default | Memory that cannot recall a paraphrase is the largest honest gap in the product | PARITY |
| 5 | Channel routing modes and approval relay (BUG-225) | Implement the spec's routing modes behind their own gate, with the accepted authority contract unchanged | An inbound message becoming work is the highest-risk transition in the product; it needs its own gate, not the transport's | PARITY |
| 6 | Auto mode has no alignment check (BUG-218) | Add a deterministic, auditable second check to `auto` — not a classifier | `auto` is the only mode where an action runs with no human in the loop | **YES — differentiator** |
| 7 | Owner-authored slash commands | Extend the skill store with a trigger token, stating the authority the command carries | Reference products treat a command as a privileged harness path; Raiker's would grant nothing, which is the differentiator | **YES — improvement** |

### High priority, high effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 8 | Vector recall is linear (MEM-10 remainder) | Add an approximate-nearest-neighbour index over the existing vector store | Recall cost is paid on every turn and grows with the owner's history | PARITY |
| 9 | Filtered domain egress unproven | Complete the container proof for allowed traffic, bypass denial and mid-stream revocation | `filtered_network` stays false until the boundary is measured, which is the rule the sandbox card is built on | PARITY |
| 10 | Credential delivery and delta quarantine | Finish copy-on-write delivery and the two-pass delta merge | Post-use quarantine of what a credentialed run left behind is a control no compared product exposes | **YES — differentiator** |
| 11 | Windows PTY and restart reattachment (BUG-194) | Design an authorised Windows transport rather than porting the POSIX one | A named pipe is reachable by name from any session; the authorisation story has to come first | PARITY |

### Medium priority, low effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 12 | Owner-guided summarisation of a range | Add "summarise from here / up to here" over the existing compaction path | Context control becomes the owner's rather than a threshold's | **YES — improvement** |
| 13 | Task cadences are four names | Accept a time-of-day and a one-shot run-at | A daily task that runs a day after it was created is not a schedule an owner chose | PARITY |
| 14 | Nothing owns delegated child tasks (BUG-220) | Give a delegating task ownership of its children's terminal states | A parent that reports done while a child is parked is a false completion | PARITY |
| 15 | Retention sweep (MEM-07) | Run the sweep the stored `expires_at` already describes | An expiry enforced only at read time is a policy the storage does not keep | PARITY |

### Medium priority, medium effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 16 | Hook lifecycle coverage | Add the Raiker-meaningful events from Claude Code's 31: `Notification`, `ConfigChange`, `PostToolBatch`, `InstructionsLoaded` | A hook surface that covers half the lifecycle can enforce guards for half of it | PARITY |
| 17 | The `prompt` hook handler (BUG-226) | Build it first of the four: it makes no outbound request and its output is context, not a decision | Each refused handler needs a gated surface; this is the only one that needs none | PARITY |
| 18 | MCP tool search | Bound the context cost of projected MCP tools | A connected server should not cost every turn its whole schema | **YES — improvement** |
| 19 | OpenTelemetry export | Emit governed events over OTLP behind its own capability gate, metadata-only by default with content capture as an explicit opt-in | [Cowork exports six events this way](https://claude.com/docs/cowork/monitoring) — including `tool_decision`, which carries the decision *and* its source. Raiker already records strictly more per action than that; what it lacks is the wire to carry it anywhere | **YES — improvement** |
| 20 | Credential masking with sentinel substitution | Generalise the git-credential loan into a sentinel/substitution path for owner-declared credentials | A command that authenticates without ever holding the secret is strictly better than one that holds it briefly | **YES — improvement** |

### Medium priority, high effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 21 | Deterministic replay | Make the event log replayable, as DeepSeek Harness's trajectory is | Replay turns an audit trail into a verification tool | **YES — improvement** |
| 22 | Autonomous skill creation with a review gate | Implement `SELF_IMPROVEMENT_MODEL.md` behind a zero-trust review (ADD-06) | A self-authored instruction that reaches turns without review is self-granted agency | **YES — improvement** |
| 23 | Remote supervisor install lifecycle | Complete SSH/Daytona supervisor install, upgrade and live proof | Remote backends are adapters today and readiness-blocked in practice | PARITY |

### Low priority, low effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 24 | Tool rows do not survive a reload | Rehydrate the per-turn tool rows from the durable events, as reasoning already does | A transcript that loses half its record on reload is a weaker record | PARITY |
| 25 | Live-spec sign-in (BUG-229) | Let the live specs sign in against a non-empty workspace | A test harness that only works on an empty workspace tests an empty workspace | NO — little advantage |

### Low priority, medium effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 26 | Plugin panels (BUG-228) | If built, declarative only, so "no plugin code runs in this browser" stays literally true | This is a gap against Raiker's own spec, not against a reference platform | NO — little advantage |
| 27 | Path-scoped project rules | Scope project instructions to path patterns | Smaller standing context is a real benefit; the authority question is already settled | NO — little advantage |
| 28 | Conversation rewind in place | Restore a conversation to a chosen turn, as `/rewind` does | Branching already covers the safe half; in-place rewind discards a record | NO — little advantage |

### Low priority, high effort

| # | Capability | Proposed action | Governance effect | Beyond? |
|---|---|---|---|---|
| 29 | LSP surface (BUG-227) | Decide whether Raiker wants a language-server client at all before building one to satisfy a manifest field | The code map already answers part of the need | NO — little advantage |
| 30 | Ephemeral micro-VMs (ADD-12) | Replace shared-kernel containers for the highest-risk work | A different class of boundary; only Cowork has one | NO — complexity |
| 31 | IDE extension | Phase 8 deferred | No governance effect; a surface question | NO — little advantage |

---

## 6. Control-set reviews (evidence)

Everything below is the dated, source-backed working the matrix above is drawn
from. Each review states the date it was run, the platforms it was run against,
and the scope it covers. **Where a review and Part 2 disagree, Part 2 is
current** — the reviews are kept because they carry the reasoning and the
evidence, not because each row is still true.

Rows superseded by a later round are marked where they were found during the
2026-08-23 reconciliation.

## 2026-08-21 implementation and reference review

Status is strict: **at parity** means both sides are evidenced; **beyond**
requires a useful additional tested Raiker control; **partial** means a safe
foundation exists but required execution proof is absent; **absent** means no
working Raiker path exists. “Not established by cited source” replaces guesses
about a reference platform.

| Platform | Current primary-source control set | Raiker status | Compatibility requirement / differentiator |
|---|---|---|---|
| Claude Cowork / Claude chat | Connectors can read local/remote sources and take actions; the cited documentation does not establish Raiker-style receipts, graph review, or checkpoint-health semantics. [Anthropic connectors](https://support.anthropic.com/en/articles/11817150-connect-your-tools-to-unlock-a-smarter-more-capable-ai-companion) | **Partial** | Chat, projects, tasks, approvals, connectors, memory review and provider choice ship. Hosted schedules, the full connector catalogue and desktop reach remain behind. Evidence-bound graph proposals and visible checkpoint non-reversibility are meaningful improvements: **yes**, because inferred memory and failed rollback promises become reviewable. |
| Claude Code | OS-enforced filesystem/network sandboxing, allowed domains, deny-first permissions and hooks are documented; sandbox unavailability can fail closed. [Sandboxing](https://code.claude.com/docs/en/sandboxing), [permissions](https://code.claude.com/docs/en/permissions), [hooks](https://code.claude.com/docs/en/hooks) | **Partial** | Raiker has measured boundaries, governed commands, approvals, checkpoints, plans and read-only subagents. Hooks closed their own event gap on 2026-08-22 — every event Raiker's schema accepts is emitted, and an owner off switch exists (FIXED-255, FIXED-254); *corrected 2026-08-23: that is sixteen of Claude Code's thirty-one, not parity.* Plugins now contribute hook rules, skills and MCP-server offers (FIXED-256, FIXED-259, FIXED-260). Active per-run egress revocation would be meaningful: **yes**, but only after real bypass/revocation proof. |
| ChatGPT Chat / Work | Apps support search, deep research, sync and confirmed writes; projects can use project-only memory and memory sources expose recalled inputs. [Apps](https://help.openai.com/en/articles/11487775-connectors-in-chatgpt), [Projects](https://help.openai.com/en/articles/10169521-using-projects), [Memory](https://help.openai.com/en/articles/8590148-memory-in-chatgpt-faq) | **Partial** | Raiker is at parity for multi-provider chat, projects, governed writes and owner-reviewed durable memory, but behind the app directory, hosted operation and broad multimodal work surface. Evidence-edge acceptance/rejection is meaningful: **yes**; the cited sources do not establish an equivalent. |
| Codex | Local/cloud agents default to filesystem sandboxing with network disabled; cloud can allow trusted domains and local commands can request elevation. [Codex upgrades](https://openai.com/index/introducing-upgrades-to-codex/), [Windows sandbox](https://openai.com/index/building-codex-windows-sandbox/) | **Partial** | Raiker is at parity for workspace-bounded execution, no-network native sandboxing, foreground/background receipts, persistent container sessions and approvals. It is behind Codex's production domain-network and cloud/worktree lifecycle. Two-pass credential delta quarantine is meaningful: **yes**, conditional on real copy-on-write delivery proof. |
| OpenClaw | Exec supports foreground/background/process/PTY, host or sandbox routing, allowlists and approval modes; its docs state sandboxing is off by default. [Exec](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec.md), [approvals](https://github.com/openclaw/openclaw/blob/main/docs/tools/exec-approvals.md) | **Partial** | Raiker's deny-by-default authority binding, immutable receipts and measured cards are stronger controls; OpenClaw leads in channels, plugins, PTY breadth and node-host execution. One lifecycle across local/container/SSH/Daytona is meaningful: **yes**; supervised install and broad remote parity remain partial. |
| DeepSeek Harness | The developer preview composes models, tools, skills, sessions, sandboxes, storage, loops, scheduling and UI as plugins; append-only trajectory drives resume/fork/search/replay. [DeepSeek Harness](https://deepseek.com/harness/en/) | **Partial** | Raiker has append-only audit, resume/branch/search, scoped tools and stronger approval/checkpoint semantics; DeepSeek leads in uniform plugin composability and trajectory replay. A governed projection from one audit/control plane is meaningful: **yes**; deterministic replay and plugin parity remain absent. |
| Hermes Agent | Hermes documents seven terminal backends — local, Docker, SSH, Singularity, Modal, Daytona and Vercel Sandbox — plus persistent environments, broad tools and optional cross-session memory. [Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration), [tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) | **Partial** | Raiker has local, native, container, SSH and Daytona foundations with owner-scoped approvals, host pins and cost reservations, but lacks Modal/Singularity breadth and working credentialed remote persistence. Purpose-bound credentials plus discard-only uncertain deltas are meaningful: **yes**, once live copy-on-write proof enables delivery. |

### Categorical decisions for proposed additions

| Proposed control | Meaningful improvement that could put Raiker beyond the reference set? | Decision |
|---|---|---|
| Deep-path-safe I/O plus visible non-reversibility | **Yes — proven** | Shipped for BUG-216; a silent rollback failure becomes durable health and receipt evidence. |
| Owner-scoped entity extraction with evidence/review | **Yes — proven** | Shipped for MEM-06; parser output is a proposal, never an accepted fact. |
| Unified governed foreground SSH/Daytona lifecycle | **Yes — partial** | Envelope, host-key/cost refusal and no-fallback adapters ship; supervised install/persistence remain. |
| Filtered egress with HMAC grants, address pinning and revocation | **Yes — conditional** | Policy, proxy, lifecycle and honest UI ship; no Docker daemon was available for mandatory bypass/revocation proof, so `filtered_network` stays false. |
| Credential delivery with two-pass delta quarantine | **Yes — conditional** | Safe snapshot/scanner, discard-only API and UI ship; delivery/merge stay off pending real disposable-container proof. |
| Publisher-verified runner and helper-image pins | **Yes — conditional** | Signed-manifest/Authenticode primitives and exact OCI digest receipts ship; developer packages report package-relative integrity until external trust anchors are verified. |
| Windows PTY/restart attachment outside a proven sandbox transport | **No** | Convenience would weaken the boundary, so it remains unsupported. |
| Governed turn-based dictation and manual read-aloud | **Yes — proven** | Dictation itself is parity with Claude and ChatGPT; explicit-send invariance, exact draft rollback, constrained provenance and a single cross-surface audio owner are the meaningful improvement. |
| Full-duplex live conversation with interruption and hands-free task control | **Yes — conditional** | Continuous voice is parity with Claude and ChatGPT. It becomes a differentiator only when spoken task controls retain visible state, action-bound confirmation, gateway policy and durable accepted/refused receipts. |

---

## 2026-08-22 review — hooks, plugins and channels

The standing "largest single gap to Claude Code" was hooks → plugins → channels.
This round closed the first, took the first slice of the second, and left the
third with its reason.

| Area | Reference control set | Raiker after this round | Status |
|---|---|---|---|
| Hook lifecycle events | Claude Code documents **31** events. [Hooks](https://code.claude.com/docs/en/hooks) | Sixteen events accepted and **all sixteen emitted**; the accepted set and the emitted set are equal, derived from the call sites by a test so they cannot drift | **Partial** — *corrected 2026-08-23: this row previously read "at parity", which was parity with Raiker's own event list rather than with the reference. Raiker covers 16 of Claude Code's 31; see [§2.5](#25-extensibility--hooks) for the 15 that have no equivalent* |
| Turn-end signalling | One `Stop`, with a separate `SubagentStop` | `Stop` and `StopFailure` are separate events: a turn parked on an approval or stopped by the owner never reports as a clean completion | **Beyond**, narrowly — see below |
| Turning hooks off | `disableAllHooks` in settings; `--settings` for one run | Owner setting; rules stay listed and marked off rather than hidden | **At parity** (FIXED-254) |
| Which rules actually enforce | Not established by cited source | Every rule states whether it can decide or only observes, whether its event is emitted, and which file it came from | **Beyond** (FIXED-253) |
| Plugin contributions | Claude Code plugins bundle skills, agents, hooks, MCP servers and LSP servers; Cowork installs them from **Customize**. [Plugins](https://code.claude.com/docs/en/plugins) | Hook rules only, at `plugin` scope below every owner scope, behind a declared `event:hook` permission, deleted on revocation | **Partial** — superseded by the second pass below, which added skills and MCP-server offers |
| Plugin authorship verification | Claude Code and Codex verify MCP server transport, not manifest authorship | HMAC / Ed25519 manifest verification with a first-class `verified` / `present only` / `unsigned` level either way | **Beyond** (FIXED-166) |
| Channels / inbound delivery | OpenClaw leads here; Claude Code has no equivalent | Specified in `CHANNELS_SPEC.md`; a connector registry exists, no delivery path does | **Absent** |

### Categorical confirmation — does this go beyond the reference set?

| Proposed control | Meaningful improvement that could put Raiker beyond the reference set? | Decision |
|---|---|---|
| Emitting the seven missing lifecycle events | **No — parity.** Claude Code documents them; Raiker specified them and emitted nine | Shipped (FIXED-255). Necessary to be honest about the surface, not a differentiator |
| Splitting `Stop` from `StopFailure` | **Yes — small, proven.** The cited reference has one `Stop`. A rule written to react to *completion* firing on a run that was stopped or parked is a correctness bug the single event invites | Shipped. Narrow, but real: it is the difference between "the turn ended" and "the turn succeeded" |
| Deriving the emitted-event set from the source | **Yes — proven.** No cited reference publishes which of its documented events a given build really emits | Shipped (FIXED-253, extended by FIXED-255). A configured rule that can never run is the worst kind of safeguard |
| Plugin contributions arriving only through an already-governed surface | **Yes — structural.** Claude Code plugins bundle code that runs; Raiker's contribute through hooks, which already have an execution model, a timeout, an audit trail and a scope below every owner scope | Shipped (FIXED-256). It is also *less* capable than the reference set today, which the Plugins tab states rather than hides |
| Revocation deleting a contribution rather than flagging it | **Yes — proven.** Prevents the state where the page says revoked and the runtime still runs the rule | Shipped (FIXED-256) |
| A general "plugin code runs" step | **No — refused.** It would need an authority story none of the remaining contribution kinds requires | Not taken, deliberately |
| Channel delivery controls | **Not yet assessable.** Inbound delivery is the highest-risk surface in the reference set — OpenClaw's own docs treat channels as the place external input enters — and offering controls before an accepted threat model would be the opposite of governed | Deferred. The tab says so rather than hiding the gap |

### What is still behind, stated plainly

* **Plugin skills, MCP servers and panels.** *Superseded by the second pass
  below:* skills shipped as FIXED-259 and MCP-server offers as FIXED-260; panels
  are now BUG-228.
* **Channels.** No inbound or outbound delivery. `CHANNELS_SPEC.md` has the
  design and `ConnectorRegistry` already validates transport, auth, pairing and
  allowlist requirements per profile. *Superseded by the second pass below:* the
  missing decision — what a channel message *is* in a turn — was made and accepted
  as FIXED-261. *Superseded again by the second pass below:* delivery was not
  absent, it was unreachable — see FIXED-265. Tracked as BUG-225.
* **A marketplace or plugin directory.** Not planned; installing from a path or
  URL with a reviewed permission diff is the local-first equivalent.
* **Hook handler types.** Two accepted (`command`, `builtin` — the second being
  Raiker's own code rather than one of the reference five). `http`, `mcp_tool`,
  `prompt` and `agent` are refused at parse time: the first needs a revocable
  egress grant, `mcp_tool` would let a hook reach authority the turn did not
  have, and the last two need a model-call budget. Tracked as BUG-226.

---

## 2026-08-22 review, second pass — plugin skills, plugin MCP offers, channel contract

The first pass of this round closed hooks, took the first slice of plugins, and
left channels with its reason. This pass took the two plugin kinds the first pass
named as next, and settled the decision channels were blocked on.

| Area | Reference control set | Raiker after this pass | Status |
|---|---|---|---|
| Plugin-contributed skills | Claude Code plugins bundle skills; installing the plugin installs them **active**. [Plugins](https://code.claude.com/docs/en/plugins) | `contributes.skills` behind a declared `skill:contribute` permission, validated by the same reader an upload goes through, installed **inactive**, credited to the plugin on the row, deleted on revocation | **Beyond** (FIXED-259) |
| Plugin-contributed MCP servers | Claude Code plugins declare MCP servers and they are configured; Codex does the same through `config.toml` | `contributes.mcp_servers` produces an **offer**. Nothing is stored as a server, connected or reachable until the owner adds it through the ordinary governed create path | **Deliberately different** (FIXED-260) |
| Credential handling in a contributed server | An MCP declaration may carry a URL with embedded auth | `https` only; a URL carrying a username or password is refused; `auth_ref` must name an environment variable; re-validated on read so a hand-edited file cannot smuggle one in | **Beyond** (FIXED-260) |
| Plugin-contributed panels | *(corrected 2026-08-23)* **No compared platform ships plugin UI panels.** Claude Code's plugin components are skills, agents, hooks, MCP servers, LSP servers and monitors. [Plugins reference](https://code.claude.com/docs/en/plugins-reference) | Not available. No route, permission or accessibility contract exists | **Behind Raiker's own spec**, not behind a reference platform — BUG-228 |
| Plugin-contributed LSP servers | Claude Code plugins bundle LSP servers | The manifest field is accepted and inert **because Raiker has no language-server surface at all**, not because a gate is closed | **Behind** — BUG-227 |
| What a channel message is in a turn | OpenClaw treats channels as where external input enters, framed as guidance to the model | Accepted contract: untrusted content with a named sender who is not the owner; never a prompt, never able to raise the turn's authority, trust resolved from the pairing record | **Beyond** (FIXED-261) |
| Channel delivery | OpenClaw ships inbound and outbound; Claude Code has no equivalent | Outbound through a capability gate and an egress allowlist; inbound behind an owner secret with sender allowlisting, recorded untrusted and quarantined. All of it was built and **unreachable** — no way to pair — until the owner surface shipped | **At parity for transport** (FIXED-265) |
| Separating linked / enabled / trusted / reachable | No cited reference separates them; a connector is configured and then it works | Four stored facts with four remedies, shown as four things: pairing, an enable switch, a sender allowlist, and three fail-closed gates named individually | **Beyond** (FIXED-265) |
| Channel routing modes | OpenClaw routes an inbound message into work | Recorded and quarantined only. No routing mode is implemented, so a channel message never becomes work on its own | **Behind, deliberately** — BUG-225 |
| Channel rate limits | Present in the reference set | Fixed window per `(connector, sender)`, 60/min by default, with the refusal recorded as an event rather than a silent 429 | **At parity**, and the recorded refusal is slightly beyond (FIXED-267) |
| Outbound webhook signing | Signed webhooks are standard | `X-Raiker-Signature` (HMAC-SHA256 over the exact bytes) plus a delivered-at header; unset secret means unsigned and **says so on the page**, rather than silently unsigned | **At parity**, and reporting it is beyond (FIXED-268) |
| Unattended approval posture | Claude Code's `dontAsk` auto-denies anything not already allowed by a rule. [Permissions](https://code.claude.com/docs/en/permissions) | `dont_ask`, a fourth composer mode: an otherwise-eligible action is refused rather than queued, so a scheduled run carries on with what it is allowed instead of parking | **At parity** (FIXED-262) |
| Why an unattended action was refused | Not distinguished by any cited reference | `denied_no_one_to_ask`, named apart from "the owner denied this" and "this turn writes nothing" | **Beyond**, narrowly (FIXED-262) |

### Categorical confirmation — does this go beyond the reference set?

| Proposed control | Meaningful improvement that could put Raiker beyond Cowork, Claude Code, ChatGPT Chat/Work, Codex, OpenClaw, DeepSeek Harness and Hermes? | Decision |
|---|---|---|
| A plugin's skill arriving **inactive** | **Yes — proven, and none of the seven does it.** Claude Code and Cowork install a bundled skill active; the marketplace and the install prompt are the owner's only protection. Splitting "offer" from "run with" makes the second consent explicit, and costs one click | Shipped (FIXED-259) |
| Crediting a contributed skill to its plugin on the row | **Yes.** OpenClaw is closest and carries no provenance on the row. "Where did this instruction come from" should be answerable from the surface, not from a directory listing | Shipped (FIXED-259) |
| Refusing rename/delete on a contributed skill, keeping download | **Yes — small.** Both would be undone by the next reconcile, so offering them would lose the row silently. Keeping download means reading exactly what a plugin put into your turns is always possible | Shipped (FIXED-259) |
| A plugin **offering** an MCP server instead of adding one | **Yes — the sharpest divergence in this release.** An MCP server is a tool source: the highest-authority thing a plugin could add. Every reference platform lets a plugin or config file add one directly. Costing one click to buy an explicit, gated, audited grant is the right trade, and it is the pattern to keep as further kinds land | Shipped (FIXED-260) |
| Re-validating an offer on read, not only on write | **Yes — proven.** Otherwise the file the install wrote and the file the surface reads can diverge, and hand-editing becomes a bypass | Shipped (FIXED-260) |
| Refusing a credential inside a contributed endpoint | **Yes.** A plugin author handing the owner a token to paste into a field not built to hold one is a realistic path to a leaked secret, and no cited reference refuses it | Shipped (FIXED-260) |
| Deciding what a channel message **is** before building transport | **Yes — this is where Raiker should intend to lead.** Claude Code has no channel concept. OpenClaw's framing is guidance to the model rather than a structural envelope. ChatGPT Work's connectors and Hermes' inbound paths carry sender identity but no stated "cannot raise authority" rule. The transport is commodity; the contract is not | Shipped (FIXED-261) |
| Giving channels an owner surface | **Yes — and it corrected the round's premise.** Delivery was not missing; it was unreachable, because nothing let the owner pair a connector. The lesson generalises: a gap read as "unbuilt" should be checked against the code before it is built twice | Shipped (FIXED-265) |
| Reporting each fail-closed gate separately | **Yes.** Three defaults refuse — the capability, the egress allowlist, the inbound secret — and each has a different remedy. Every cited reference collapses this into one enable switch, which is why "it's on and nothing happens" is a support question there and a readable page here | Shipped (FIXED-265) |
| Routing an inbound message into a turn | **No — refused.** Recording and quarantining are the safe defaults, and the routing modes in `CHANNELS_SPEC.md` are a target rather than a description. Implementing them before rate limits and the relay story would be the wrong order | Open on BUG-225 |
| Exempting booleans from key-based redaction | **Yes — small and general.** A filter that replaces `False` with a truthy marker does not protect a secret; it states the negation of a fact, and every client reads it confidently | Shipped (FIXED-266) |
| Bounding an allowlisted channel sender | **No — parity**, and closing a gap Raiker's own spec had named. The *recorded* refusal is the part worth keeping: a 429 with no audit trail leaves the owner unable to tell "nobody is sending" from "everything is being dropped" | Shipped (FIXED-267) |
| Signing outbound deliveries, and saying when they are not signed | **Partly.** Signed webhooks are standard; it was Raiker that was behind its own connector profile. What goes beyond is telling the owner *on the page* that deliveries are currently unsigned — the gap between what a profile declares and what the transport does is exactly what a governed product should surface | Shipped (FIXED-268) |
| A plugin panel that renders plugin-authored code | **No — refused.** "No plugin code runs in this browser" is a claim the Plugins tab makes in those words. A declarative panel keeps it literally true and makes the accessibility contract enforceable at render time | Recorded as the intended shape in BUG-228 |
| Building an LSP client to satisfy a manifest field | **No — refused.** That is the tail wagging the dog. Whether Raiker wants a language-server client at all is a scope decision that comes first, and the codemap already answers part of the need | Recorded in BUG-227 |
| A fourth approval mode that declines instead of asking | **No — parity**, and worth taking for exactly that reason: an owner arriving from Claude Code's `dontAsk` had no equivalent, and their unattended runs parked instead of proceeding | Shipped (FIXED-262) |
| Naming *why* an unattended action was refused | **Yes — small, and free.** No cited reference separates "declined because nobody was watching" from "declined because you said no". Reading an unattended run's record afterwards, they are not the same fact: only one of them means running it again while watching would have worked | Shipped (FIXED-262) |
| A detail line under every approval mode | **Yes — a consequence of the fourth mode.** *Skip* and *Decline* both mean "stop asking me" and do opposite things; a label alone cannot carry that, and a mode picker whose options can be misread is a safety surface that misinforms | Shipped (FIXED-262) |

### What is still behind, stated plainly (superseding the list above)

* **Plugin panels.** The last contribution kind. Tracked as BUG-228, split out of
  BUG-221 so it can be worked on its own terms.
* **Plugin LSP servers.** No surface exists to contribute to. Tracked as BUG-227.
* **Channels.** *Superseded:* outbound and inbound both existed and are now
  reachable (FIXED-265), rate-limited (FIXED-267) and signed (FIXED-268). What is
  still behind is above the transport — the spec's routing modes, and resolving
  an approval over a channel. Tracked as BUG-225.
* **A marketplace or plugin directory.** Still not planned; installing from a
  path or URL with a reviewed permission diff is the local-first equivalent.
* **Hook handler types.** Unchanged from the first pass, and worth restating:
  `command` is the only handler type **Claude Code's own hooks have**, so the four
  Raiker refuses are a gap against Raiker's own reference document rather than
  against Claude Code. Tracked as BUG-226.

---

## Concept-to-specification maps

The tables in this group answer one narrow question — *which Raiker document
specifies this reference concept* — and **say nothing about implementation
status**. For status, read [Part 2](#2-canonical-capability-matrix). They are
kept because a concept with no owning document is a concept nobody is
responsible for.

### Claude Code Concept Coverage

| Reference concept | Raiker specification |
|---|---|
| Agentic coding loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tools reference | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Interactive mode | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Rich terminal UX | `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
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

#### Claude Code documentation — per-page mapping

Each reference page named in the review brief maps to a Raiker spec and a current code status.
Status: ✅ implemented · 🟡 partial/stub · 🔒 phase_scheduled_disabled · 📘 specified_not_implemented.

| Reference page | Raiker spec | Code status |
|---|---|---|
| `how-claude-code-works` (gather→act→verify loop, harness) | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/RUNTIME_STATE_MACHINE.md` | ✅ loop real; 🟡 verify/context stubs |
| `tools-reference` (built-in tools + permission per tool) | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | ✅ read tools; write/shell approval-gated |
| `interactive-mode` (REPL, shortcuts, steer/interrupt) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | ✅ basic REPL |
| `commands` / slash commands (built-in + custom) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | ✅ 50+ inspection commands |
| `cli-reference` (flags: `--prompt`, `--workspace`, resume/fork) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `README.md` | 🟡 `--prompt`/`--workspace` only |
| [`checkpointing`](https://code.claude.com/docs/en/checkpointing) (snapshot before each prompt; `/rewind` restores code, conversation or both; summarize-from/up-to-here) | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` | 🟡 capture real and automatic; a real `CheckpointRestoreExecutor` exists and is registered, but **no route, command or tool proposes a restore** — every owner surface shows a preflight only. Conversation branching from a checkpoint ships (FIXED-227) |
| `hooks` (31 events; `command` \| `http` \| `mcp_tool` \| `prompt` \| `agent`; matchers; `if`) | `docs/HOOKS_SPEC.md` | 🟡 dispatcher, matchers and `if` real; **16 events, all of them emitted** (FIXED-255), 2 handler types, owner off switch and owner surface at Extensions → Hooks |
| [`plugins-reference`](https://code.claude.com/docs/en/plugins-reference) (`plugin.json`; skills, agents, hooks, MCP servers, LSP servers, monitors, `bin/`, themes, output styles, workflows, `userConfig`, `channels`, `dependencies`; marketplaces) | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/PLUGIN_MANIFEST_SCHEMA.md` | 🟡 manifest validation, supply chain and signature level, plus contributed **hook rules** (FIXED-256), **skills** (FIXED-259) and **MCP-server offers** (FIXED-260). Agents, LSP servers, monitors, `bin/` executables, themes and output styles are not contributable — several deliberately, see [§4](#4-deliberately-refused). No marketplace, by decision ([§3.4](#34-a-reviewed-permission-diff-instead-of-a-marketplace)) |
| `channels-reference` (MCP `claude/channel` capability; `notifications/claude/channel`; sender gating; permission relay) | `docs/CHANNELS_SPEC.md`, `raiker/config/channel-connectors.json` | 🟡 *corrected 2026-08-23:* transport, pairing, sender allowlist, inbound secret, per-sender rate limit and signed outbound delivery all ship (FIXED-265, FIXED-267, FIXED-268). Routing modes and approval relay do not (BUG-225) |

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

### Claude Cowork Coverage — delegated Tasks and Schedule

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

### OpenClaw-Style Personal Agent Coverage

| Concept | Raiker specification |
|---|---|
| Local-first gateway/control plane | `docs/ARCHITECTURE.md`, `docs/CHANNELS_SPEC.md` |
| Multi-channel inbox | `docs/CHANNELS_SPEC.md`, `raiker/config/channel-connectors.json`, `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md` |
| Channel pairing and sender allowlists | `docs/CHANNELS_SPEC.md`, `docs/SECURITY_AND_POLICY.md` |
| Channel-to-agent routing | `docs/CHANNELS_SPEC.md`, `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Gateway daemon mode | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Voice wake/talk mode equivalent | `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/CHANNELS_SPEC.md` |
| Live canvas/workspace equivalent | `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Companion apps/nodes | `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/CHANNELS_SPEC.md` |
| Onboarding and connector setup | `docs/CHANNELS_SPEC.md`, `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md` |
| Skills from bundled/global/workspace scopes | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Channel security diagnostics | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/VERIFICATION_PLAN.md` |

---

### Hermes-Agent / Agent Framework Coverage

| Concept | Raiker specification |
|---|---|
| Tool-using agent loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Model-router/provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `raiker/config/model-profiles.json` |
| Global `raiker` TUI entry and in-TUI provider launch | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Structured tool proposal | `docs/CONTRACTS.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Verification/reflection | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Local-first inference support | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Full TUI with streaming output | `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Interrupt and redirect | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Cross-channel conversation continuity | `docs/CHANNELS_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Closed learning loop | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill creation and skill improvement | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Full-text session search with summaries | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| User modelling from confirmed facts | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Scheduled automations | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md` |
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
| Branch a conversation from a message | ChatGPT, Claude, Claude Code `/branch` | ✅ *superseded 2026-08-16:* shipped as FIXED-227 — `POST /api/checkpoints/{id}/branch` seeds a second conversation and a lineage band names its source. See [Conversation branching](#conversation-branching--the-c14-remainder) | ✅ |
| Governed voice input | ChatGPT and Claude offer voice conversation | **Dictate** writes into the editable Chat or Build draft; **Done** never sends, **Cancel** restores the exact prior draft, and only the normal Send path creates a turn. Provenance is constrained metadata and no audio is stored | ✅ beyond |
| Manual response read-aloud | ChatGPT and Claude voice surfaces speak responses | Completed answers expose **Read aloud** and **Stop speaking**; playback is never automatic and code bodies, citation syntax and raw URLs are excluded | ✅ |

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
| ~~Branch-from-here~~ | ChatGPT, Claude | **Shipped** as FIXED-227 — a conversation fork over the existing checkpoint manifest, with a lineage band that makes two branches of one conversation legible |

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
| Persistent environment | Claude Code and OpenClaw can retain a sandbox/session boundary between commands | ✅ **for the container backend** (2026-08-17): the container's name is a function of owner, session and profile rather than of the run, so a session's second command lands in the boundary its first one left behind — what it installed, wrote to `/tmp`, or left in the private cache is still there. Liveness is asked of the runtime rather than assumed from Raiker's own map, so a container removed underneath the runtime is rebuilt rather than `exec`-ed into. `native_sandbox` still creates and deletes a profile around each command and says so, because a predictable AppContainer name is a hole — the container SID is a pure function of the name | ✅ |
| Foreground output and exit status | All coding-agent references provide it | Split-safe redacted stdout/stderr, total byte counts, truncation, timeout, terminal state, and exit code | ✅ |
| Provider-independent model-to-command path | Market leaders route tool calls consistently across supported model providers | Anthropic (Haiku 4.5), OpenRouter (Gemini 3.7 Flash), OpenAI (GPT-4o Mini) and Ollama (gemma4:31b-cloud) each completed the same live Build → approval → exact-argv command **inside the AppContainer** → output → receipt on 2026-08-15 (`r0815-build-governed-terminal-appcontainer.png`) | ✅ beyond |
| Background start/poll/wait/log/kill | Claude Code, Codex, OpenClaw, and Hermes expose long-running process controls | `run_command background:true` returns a `run_id` without waiting; `background_run` polls, pages the log from a resumable sequence, waits with a bounded timeout, and kills. The enforcer that makes this offerable ships with it: every background run holds a **lease** the supervising thread renews only while the process is alive, and `reconcile_leases` terminates and finalises any run whose lease lapsed with a receipt naming `command_background_lease_expired` — so a crashed supervisor produces a reclaimed run, never an orphan holding a sandbox grant. A foreground run holds no lease and is never swept. On Windows, a surrounding sandbox can refuse `taskkill`; Raiker now closes the owned stdin and kills its direct child in that case so cancellation still reaches a terminal receipt instead of remaining `running` forever. This is **parity and a safeguard, not a differentiator** | ✅ |
| PTY and raw input | Claude Code/Codex terminal workflows support interactive programs | ✅ **on POSIX**: `openpty` gives the child a controlling terminal, `background_run action=input` types into it, and the test proves the *program* read the bytes rather than the terminal echoing them (`sort` returns its input reordered after ^D). ❌ **on Windows**, with the reason unchanged and named: `CreatePseudoConsole` builds its console objects in the caller's context, unreachable from an AppContainer token, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. `pty_supported()` reports the platform's real answer; input to a run without a terminal is refused as `command_input_requires_pty` rather than written to a pipe where the bytes would arrive and the effect would not | 🟡 |
| Process-tree stop and timeout | Coding agents must stop descendants, not only the launcher | Local runner creates a process group and kills its tree; container stop removes the worker; native Windows runs are held by a kill-on-close Job Object; UI stop is owner-scoped and idempotent. A Windows host that denies the tree utility gets a direct-child terminal fallback, which is never promoted into proof that descendants were reaped | ✅ |
| Network denied by default | Codex and Claude Code sandbox network by default; OpenClaw supports sandbox network policy | ✅ **for `native_sandbox`**, where the container holds no network capability and the measured egress observation is `enforced`; container uses `--network none`. `local_native` is still the default selection and has no OS egress boundary, so the row is scoped rather than claimed for the product default | 🟡 |
| Filtered domain escalation and revocation | Claude Code supports domain/proxy policy; mature sandboxes can grant bounded egress | IDNA/wildcard/port policy, HMAC run tokens, a runnable authenticated CONNECT proxy, public-address pinning, active-socket revocation, durable grants/verdicts and Runtime configuration are implemented. `filtered_network` stays false until a real container proves allowed traffic, bypass denial and mid-stream revocation. **Potentially beyond the references: yes**, because the durable per-run verdict and revocation evidence add accountability; **shipped claim: partial**, because this host has no Docker proof | 🟡 |
| Secret-free child environment | Sandboxes should not inherit host credentials | Local and container launchers construct a minimal environment; literal/pattern credentials are rejected before persistence | ✅ |
| Purpose-bound credential delivery and delta quarantine | Reference tools can use credentials; Raiker's target adds post-run local quarantine | A disposable workspace excludes `.raiker` and `.git`, holds Git metadata separately read-only, rejects links/mount drift/collisions, computes create/change/delete metadata, quarantines secret-like output, and exposes owner-scoped review/discard UI. Disposal restores only owner permission needed to remove the read-only snapshot on POSIX and Windows ([FIXED-246](plans/FIXED_ITEMS.md)). Credential injection and a measured copy-on-write merge path remain unbuilt, so `credential_delivery` stays false. **Beyond the references: yes if completed**, because post-use quarantine is a meaningful control none of the compared products exposes; **today: partial** | 🟡 |
| Redaction before storage or display | Coding agents suppress known secrets in logs | Incremental UTF-8 redaction covers all current patterns at every split, exact loaned secrets, PEM blocks, explicit stdout/stderr boundaries that prevent cross-stream reconstruction, and fail-closed bounded pending data before persistence | ✅ beyond |
| Durable output catch-up after browser/navigation reload | Reference desktop agents retain command history | Owner-scoped ordered chunks and receipts reload into Build without replaying a command; returning from Approvals refreshes open/collapsed panes and selects the current session's run | ✅ |
| Immutable execution receipt | Reference products expose activity/history, generally without a canonical receipt digest | Canonical terminal receipt binds authority, environment, command-template digest, output truncation, and redaction count; replacement is refused. It now separates two claims that are easy to blend and mean different things: `boundary_constructed` is what **this run's** runner built, `probe_observations` is what **the host** was measured to enforce, with the time it was measured | ✅ beyond |
| Restart reattachment and honest uncertainty | Codex/OpenClaw supervise long-running work across UI/runtime churn | ✅ **on POSIX** (2026-08-17): a background run is started inside a detached supervisor — its own session, its own deadline, its own redactor, an append-only journal, and an `AF_UNIX` control channel speaking the authenticated frames the cross-language protocol vectors already cover. Raiker keeps the socket path and the instance key encrypted in `command_runs.encrypted_backend_handle`, so reattachment is an **authentication**, not a pid lookup: a socket that answers a frame the stored key verifies is this run's supervisor, and a pid — which can be reused by a stranger — never was. `recover_owner` reattaches before it recovers, and the lease reconciler asks the same question before reclaiming, so a live run is never killed because the runtime that was watching it restarted. Every case the runtime cannot *prove* — no handle, a locked vault, a socket that is gone, a socket that fails the key — still produces the honest `lost` receipt. ❌ **on Windows**: a named pipe is reachable by name from any session on the machine, so its authorisation story needs its own design and its own proof; `command_supervisor_platform_unsupported` says so by name rather than a weaker thing shipping under the same label | ✅ |
| SSH and managed cloud sandbox | Claude Code/Codex support remote/cloud execution patterns; Hermes supports remote tools | Foreground SSH and Daytona adapters now use an exact remote envelope, fixed supervisor path, host-key pin and cumulative cost budget with no host fallback. Readiness still requires an independently installed supervisor whose digest/protocol probe passes; install/upgrade lifecycle and live remote proof remain open. **Beyond the references: no for transport parity; yes conditionally for the fail-closed identity and cost evidence** | 🟡 |
| Reset/recreate and recovery controls | Persistent sandboxes need an owner reset and cleanup path | ✅ **for the container backend** (2026-08-17): persistence and reset shipped as one control, because an environment that accumulates state and can never be cleared is worse than one that never persists — the owner has no way back to a known state. `POST /api/execution-environments/{profile_id}/reset` takes **Reset environment** (discard the boundary, keep the private cache) and **Reset and clear cache** (discard both), and refuses `execution_environment_not_persistent` on a profile that rebuilds itself around every command rather than offering an action with no effect. The control appears on the environment card only where `persistent_environment` is true | ✅ |
| Capability truthfulness | Reference products vary in how unavailable controls are projected | Features come from a **differential measurement** against the real workspace, never from configuration: each observation is taken inside and outside the boundary, an unmatched control arm reports `indeterminate`, and no `CommandFeatures` field is true without its observation. The six results and the probe's own outbound destination are on the environment card, with **Re-measure boundary** (`r0815-runtime-native-sandbox-observations.png`) | ✅ beyond |

The governance lead is real and unchanged: authority provenance, durable
redacted catch-up, immutable receipts, exact environment choice, honest `lost`
outcomes — and now a boundary that is **measured rather than declared**, which no
reference product exposes to its owner.

**Updated 2026-08-17 (first pass).** Background supervision, the agent-facing
observation tool, and PTY/raw input on POSIX shipped and were proven — see the
rows above and `tests/test_background_execution.py`.

**Updated 2026-08-17 (second pass).** Restart reattachment, the persistent
session boundary and the owner's reset control shipped together, and the three
were built together for the same reason the first pass built the lease with the
observation tool: each alone is worse than none of them. A boundary that
persists with no reset is a boundary the owner cannot get back to a known state;
a supervisor that outlives Raiker with no authenticated reattachment is an
orphan. Proven by `tests/test_command_supervisor_reattach.py` — which restarts
the service for real and asserts that the half of the output the first one never
saw arrives exactly once — and `tests/test_persistent_command_container.py`.

Raiker still does **not** match the market leader's complete shell capability:
Windows PTY, Windows restart reattachment, filtered domain egress, credential
quarantine and remote backends remain absent, each with its reason recorded in
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
| PTY / interactive input **on Windows** | Claude Code, Codex, Hermes | Closed on POSIX (2026-08-17). ConPTY objects are built in the caller's context and are not reachable from an AppContainer token. Needs a spike, not a flag |
| Restart reattachment **on Windows** | Codex, OpenClaw | Closed on POSIX (2026-08-17) over `AF_UNIX`, whose authorisation is the directory's. A named pipe is reachable by name from any session on the machine, so the equivalent needs its own design and its own proof rather than the same code with a different transport |
| Filtered domain egress | Claude Code | The AppContainer loopback exemption needs elevation; a Linux proxy-only namespace is a separate build |
| Persistent boundary for the **native sandbox** | Claude Code, OpenClaw, Hermes | Closed for the container backend (2026-08-17). Per-run AppContainer profiles stay deliberate: the container SID is a pure function of the name, so a predictable name is a hole |
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

## Observation capture control set — what the agent saw, and what it refused to keep

Reviewed 2026-08-17 while closing **MEM-04**, against the "what does the agent
remember about its own work" surfaces of **Claude Cowork**, **Claude Code**,
**ChatGPT**, **Codex**, **OpenClaw**, **DeepSeek Harness** and **Hermes Agent**.
Scope is only that: the record a system keeps of material a tool returned, as
distinct from the durable memories an owner approved. Nothing here is a claim
about the rest of those products, and nothing is implemented unless the Raiker
column says so.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Reference behaviour | Raiker | Status |
|---|---|---|---|
| A record that a tool returned material | Every reference product keeps the tool result in the transcript for the length of the session | One `eidetic_observations` row per governed tool result, recorded by the broker at the moment the result lands, surviving the session | ✅ |
| The record is **not a second copy** of the material | ChatGPT, Claude Code and Cowork all retain the tool output verbatim in conversation storage | Summary, checksum, byte count, retention class and — where one already exists — an artifact reference. There is no column that could hold the material, so this is the shape of the schema rather than a policy applied to it | ✅ beyond |
| Material that looks like a credential is **not** captured | None of the reference products treat a tool result differently on sensitivity | The classifier that already refuses credential-like memory text runs first; a credential- or secret-like result is refused | ✅ beyond |
| A refusal is **visible**, not silent | — | The refusal is itself a row, carrying its reason, so an empty Observations list is distinguishable from a disabled feature and from a session where everything was refused | ✅ beyond |
| A refused observation keeps **no digest either** | — | A SHA-256 of a credential is still a fact about the credential, so a skipped row stores neither the checksum nor the byte count | ✅ beyond |
| Retention is a **class**, not a session lifetime | ChatGPT retains conversation content under an account-level setting; Claude Code retains a local transcript | Six named classes from the spec, chosen by what produced the material: outside web, connector and MCP results and command output get 7 days; workspace material gets 30. The expiry is computed and stored, so the owner reads a date rather than a policy | ✅ beyond |
| Outside material is never promotable to durable memory | Every reference product frames external content as data, then stores it beside first-party content | `promotable_to_memory` is false for `external_web`, `connector` and `mcp_tool` by construction, so an untrusted page can be observed without ever becoming a memory candidate | ✅ beyond |
| A conclusion may propose a durable memory | Cowork and ChatGPT propose memories from conversation | A gist is proposed only from a *conclusion* — a generated document, a subagent digest — never from each file read, and lands `pending_review`. It becomes durable memory only through the approval every other memory needs | ✅ |
| The owner can see and delete what was captured | ChatGPT and Claude offer conversation deletion; none offers a per-observation view | Memory → **Observations**: every row with its kind, retention, expiry, sensitivity and checksum, filterable by kind, refusal or pending gist, with a delete control per row and a discard for a proposed gist | ✅ beyond |
| Capture never fails the work | — | Recording is best-effort by construction: a bookkeeping failure emits `eidetic_observation_skipped` and leaves the tool result untouched. Trading a reliability property for a bookkeeping one would be the wrong trade | ✅ beyond |
| The record points back at the turn it came from | Claude Code and Codex link a tool call to its place in the transcript | `source_event_id` names the real `tool_completed` event, and the broker now returns the event id so the link is checkable rather than asserted | 🟡 — the link is durable; opening it from the Observations row is MEM-08 |

**Where Raiker leads, and why it is worth keeping.**

| Control | Why no reference product has it | Where it is |
|---|---|---|
| An observation that is **metadata by construction** | Every reference product keeps tool output verbatim because the transcript *is* the memory. That makes the memory as sensitive as the most sensitive thing the agent ever read. Separating "we saw this" from "here is what we saw" lets recall be broad and storage stay narrow | shipped: `raiker/memory/capture.py`, `eidetic_observations` |
| A **refusal that is a row** | A product that silently skips sensitive material leaves its owner unable to tell "nothing happened" from "everything was refused". Both look like an empty list | shipped: `capture_status` / `skip_reason` |
| **Trust travelling with provenance** | Reference products label external content as untrusted for the length of the turn. Here the label is durable: an observation of a fetched page can never be promoted, months later, by a path that has forgotten where it came from | shipped: `FIRST_PARTY_SOURCES` |
| A retention class chosen by **what produced the material** | Reference retention is per account or per conversation. A fetched page and a workspace file have very different half-lives, and one setting cannot express that | shipped: `RETENTION_BY_SOURCE` |

**What a reference product does that Raiker does not.**

| Missing control | Who has it | What it would take |
|---|---|---|
| Opening a recalled answer at the turn it came from | ChatGPT and Claude link a cited memory to its conversation | The `source_event_id` is durable and correct; the missing part is the read-back surface — tracked as **MEM-08** |
| Exact replay of an observation's material | None (they keep the material instead) | Deliberately not built: replay would need the material, and the point of the row is that Raiker does not hold it. The governed artifact reference is the honest substitute where one exists |
| Automatic entity extraction from an observation | Cowork and ChatGPT populate a profile from conversation | **Shipped 2026-08-21 (MEM-06 / FIXED-241):** deterministic owner-scoped proposals carry evidence and require review before projection |
| A retention sweep that runs by itself | ChatGPT expires conversation content on a schedule | Tracked as **MEM-07**. The expiry is computed and stored per row today; what is missing is the sweep, and an owner-confirmed cleanup already exists in its place |

**Ideas that go beyond every reference product, not yet built.** Recorded so the
list is a decision rather than a gap: an observation that carries the
**capability** the tool call crossed, so the owner reads a governed shape rather
than a tool name; a **diff between two observations of the same path**, which the
checksums already make computable without storing either version; and a
retention class the owner can *change per row* after the fact, since the expiry
is a stored date rather than a derived one.

---

### Eidetic Memory Coverage

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

### Ruflo-Style Multi-Agent Coverage

| Concept | Raiker specification |
|---|---|
| Multi-agent teams | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Subagent roles | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Background task progress | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Team UI | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/VISUAL_DESIGN_SPEC.md`, `docs/WEB_UI_CONTROL_DECK_PLAN.md` |
| Agent recursion limits | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Enterprise security/governance | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

### Graphify-Style Graph Context Coverage

| Concept | Raiker specification |
|---|---|
| Project graph extraction | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Symbols/entities/relations | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Graph queries | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Graph-backed context retrieval | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Staleness detection | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Recursive CTE traversal | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |

---

### Skills Coverage

| Concept | Raiker specification |
|---|---|
| Procedural workflows | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill packaging | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill activation | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill safety/verification | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Skill self-improvement | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |

---

### Memory Coverage

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

### llama.cpp / Local Inference Coverage

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

### LangChain/LangGraph-Style Runtime Coverage

| Concept | Raiker specification |
|---|---|
| Agent framework vs runtime distinction | `docs/ARCHITECTURE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Durable execution | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Human-in-the-loop | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Streaming | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Persistence | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Low-level orchestration | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |

---

### OWASP GenAI/LLM Security Coverage

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

### Superpowers-Style Skills / Self-Improvement Coverage

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

### mem0-Style Memory Coverage

Reference: `mem0ai/mem0` — a universal memory layer with `add`/`search`/`retrieve` over user,
session, and agent scopes, using hybrid retrieval (semantic embeddings + keyword/BM25 + entity
linking) and provenance.

| mem0 concept | Raiker specification |
|---|---|
| `add` memory from interactions (candidate-first) | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| `search` (semantic + keyword hybrid) | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (FTS5 + BM25 + vector metadata) |
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

### memsearch-Style Semantic Search Coverage

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

## Agent-reachable memory and knowledge-graph control set

Reviewed **2026-08-17**, second pass, against **Claude Cowork**, **Claude
Code**, **ChatGPT**, **Codex**, **OpenClaw**, **DeepSeek Harness** and **Hermes
Agent**. Scope is only one question, asked because it had never been asked
directly: *of everything Raiker knows, how much can the model itself reach, and
does what it reaches agree with what the runtime hands it?* Nothing here is a
claim about the rest of those products.

The audit found three defects, all of the same shape — a capability that
existed, worked, and was **unreachable or inconsistent from a turn**. None
would have shown up as a failure; each produced correct output from a weaker
input than the product had available.

Status: ✅ at parity or beyond · 🟡 partial · ❌ absent.

| Control | Market bar | Raiker implementation | Status |
|---|---|---|---|
| The agent can search durable memory | Cowork and ChatGPT expose saved-memory recall to the model | `memory_search`, `memory_list`, `memory_get`, in Chat and Build alike — no per-surface filtering | ✅ |
| The agent can search past conversations | Cowork and ChatGPT recall prior threads | `conversation_search` over the FTS5 index, both sides of an exchange attributed | ✅ |
| **The agent's search and the runtime's own recall agree** | Not a control any reference product exposes — most have exactly one path | **MEM-11.** They disagreed: `memory_search` ran the lexical index while the ambient recall injected into the *same turn* ran all of hybrid retrieval. Two answers to one question, and the weaker one was the half the model could steer. Both now call `retrieve_hybrid_memory`, and a test asserts the two return the same memories in the same order | ✅ beyond |
| The agent can traverse a knowledge graph | Cowork surfaces connected work; ChatGPT relates saved memories; Hermes exposes graph tools | **MEM-13.** Raiker stored a governed entity graph, drew it for a person, and consumed it internally — and no tool could walk it. `knowledge_graph` now does: `entities` to discover, `neighbors` to traverse, gated on `graph_indexing_runtime` | ✅ |
| Every graph edge names its evidence | No reference product does this — a graph edge is a fact about the topology | Each edge carries the **approved memory that evidences it**, its confidence, and its direction, so a claim reached through the graph is traceable to a sentence the owner approved rather than asserted from a shape. Archiving the evidence removes the edge, proven by test | ✅ beyond |
| A retrieval result says how it was found | Reference products return ranked results without provenance per hit | Every hit names the **legs** that found it (`lexical` / `vector` / `graph`) and the reply names the embedding space searched and whether it can match meaning. A lexical-only hit cannot read as corroborated by three independent signals | ✅ beyond |
| The owner's retrieval setting governs every path | Not applicable to products with one path | **MEM-11, second half.** Choosing a recall backend changed the injected context and left the model's own search untouched, so the Memory page described a choice that did not apply to half of what reached the model. One setting now governs both, and the card says so | ✅ beyond |
| Hybrid retrieval actually runs all its legs | Reference products do not describe their retrieval as legged | **MEM-12.** The graph leg was gated on an `entity_id` the only production caller never passed, so the third leg never ran on a real turn. Anchors are now resolved from the query by whole-term match, bounded to three, and reported. Two paths to one memory take `max`, not a sum, so a densely connected entity cannot outrank an exact match on topology | ✅ |
| Graph anchoring cannot fire on a coincidence | — | Matching is on whole normalized terms with space padding, never `LIKE '%term%'`: "nas" must not anchor on "nasty business". A traversal seeded from a coincidence is worse than no traversal, because it adds unrelated memories to a turn wearing the label "recalled". Asserted by test | ✅ beyond |

### The Knowledge Map — what a map of your work should show

Added **2026-08-17** after the map was found to be showing the runtime's own
bookkeeping. Measured: 20 of 22 nodes on a real workspace were typed `tool`, and
none of them was a tool. Compared against how **Claude Cowork**, **ChatGPT**,
**OpenClaw** and **Hermes Agent** surface the relationship between a
conversation, the material it used, and the files it touched.

| Control | Market bar | Raiker implementation | Status |
|---|---|---|---|
| Conversations are distinguishable by kind | Cowork and ChatGPT separate chats from delegated work in their lists | Chat, Build and task runs are three node types with three colours. `sessions.origin` always knew; the map did not read it. An unknown origin still draws rather than vanishing | ✅ |
| Work is grouped by project | Cowork groups by project; ChatGPT by folder | Sessions hang from their project node, and the project from the owner | ✅ |
| The map shows what an answer was grounded in | ChatGPT shows per-message citations; none of the reference products draws them as a **shared graph** | `turn_sources` becomes typed nodes — a cited file looks like a file, a fetched page like a source. A file cited in three sessions is one node with three edges | ✅ beyond |
| Files the owner attached are visible | Cowork and ChatGPT list attachments per thread | Attachment nodes edged from their session, metadata only — the stored blob is never read to draw a node | ✅ |
| Tool use is summarised, not enumerated | Reference products show a per-turn activity list, not a graph | One node per `(session, tool)` carrying its use count and whether every run failed. Forty runs of `read_file` is one node reading "40 uses" | ✅ beyond |
| Nothing on the map floats | Not a control any reference product states | Every node has an anchor. A memory whose source event has aged out of the page is resolved to its session in one batch query, and failing that to the owner. Asserted by a test that walks the whole graph | ✅ beyond |

**Raiker difference.** The reference products present this material as *lists*:
a thread list, a citation list under a message, an attachment tray. Raiker
presents it as one graph in which the same file cited by three different
conversations is visibly one file — which is the question a list cannot answer
and the reason a map is worth having at all.

**Deliberately still a human surface.** The Knowledge Map page is not exposed to
the model. Everything on it is reachable through `conversation_search`,
`memory_search`, `knowledge_graph` and the task and approval tools, so a second
path would add no capability — and a second path to the same facts is exactly
the defect MEM-11 was.

### The reference graph — material a model can read, not just a picture

Added **2026-08-17**, third pass, after reviewing
[`obsidianmd/obsidian-developer-docs`](https://github.com/obsidianmd/obsidian-developer-docs)
at the owner's suggestion. The question it settled: the knowledge graph Raiker
had exposed to models was a graph of **claims** — entities and approved
sentences about them — and a model building an understanding of a workspace also
needs the graph of **material**: which work used which source, what was used
beside it, and what that source actually said.

Obsidian's `MetadataCache` turned out to describe exactly the reading Raiker was
not doing. `turn_sources` already records one row per source a turn used,
carrying the target's locator and the bounded passage that reached the model —
`resolvedLinks`, `getBacklinksForFile` and a block reference in one table, read
only ever forwards, for the chips under a single answer. Nothing was derived;
the ledger was read from the other end.

Three properties were borrowed deliberately, each because Raiker would have got
it wrong without them.

| Control | Market bar | Raiker implementation | Status |
|---|---|---|---|
| A model can ask what else used a source | Cowork and ChatGPT show citations *under a message*; none exposes the inverse | `knowledge_graph action=references locator=…` returns the conversations that cited it, each with the surface it ran on (Chat or Build) and its own reference count | ✅ beyond |
| A reference carries a count, not just existence | Obsidian counts references per link; no agent product does | Every edge reports `refs` and `turns`. A conversation that leaned on a file across nine turns and one that glanced at it once are different facts, and collapsing them discards the only signal that says which matters | ✅ beyond |
| A broken reference is reported, not dropped | `unresolvedLinks` is a first-class half of Obsidian's cache; agent products silently omit dead citations | Resolution is `resolved`, `unresolved`, `external` or `attachment`. A citation whose file has been deleted comes back marked, because "the answer rested on something that is gone" is more useful than a shorter list — and omitting it would make the work look ungrounded rather than grounded in something missing | ✅ beyond |
| A reference resolves to text, not a document | A citation elsewhere is a link the model must re-open | `action=passages` returns the bounded text the source handed an earlier turn, with its session, turn and capture time. A backlink without a passage is a rumour | ✅ beyond |
| The text is dated as a snapshot | — | Every passage says it is what reached a turn *then*. Unsaid, a model would quote a year-old passage as the present contents of a file it never opened | ✅ beyond |
| Related material is weighted by its evidence | A vault's links are authored; Raiker's are inferred | Co-cited sources report `shared_sessions` — the number of conversations that needed both. Nobody wrote these edges, so the strength of the claim travels with it rather than hiding behind a line on a picture | ✅ beyond |
| Reading references opens nothing new | — | `references` and `passages` re-run no tool, re-read no file, and reach only material that already entered one of this owner's turns. Both are owner-scoped in SQL, and a test asserts another account's passages are unreadable | ✅ |
| The map shows unresolved references too | Obsidian renders unresolved links distinctly; no agent product draws them | A cited file that no longer exists is drawn hollow with a dashed outline and reads **Missing** in the inspector, searchable as `status:missing` | ✅ beyond |

**Read the table above as scoped to link mechanics, not as a verdict on the
graph.** Every row is a specific control, and each judgement holds for that
control. What the table does *not* say — and what a reader would wrongly infer
from eight rows of "beyond" — is that Raiker's knowledge graph is at parity with
Obsidian's overall. **It is not.** The rows above cover the half that was
ported; this is the half that was not.

| Obsidian | Raiker | Status |
|---|---|---|
| **Authored links** — a person writes `[[deploy]]` and *states* the relationship | Nothing. There is no way to create an edge by hand anywhere in the product; every edge is inferred from co-citation or extracted from approved memory | ❌ absent |
| Headings, sections and list items — sub-document structure | Not modelled | ❌ absent |
| Block references (`^id`) — a stable, addressable anchor into a document | `source_id` is per-turn, not a document anchor, and `passage` is text with no stored coordinates. `locate_passage` re-finds it at open time instead | 🟡 partial |
| Tags as graph entities | Memories carry tags; tags are neither nodes nor a map filter | ❌ absent |
| Embeds and transclusion | Not modelled | ❌ absent |
| Frontmatter and `frontmatterLinks` | Not modelled | ❌ absent |
| Aliases, and `getFirstLinkpathDest` shortest-path link resolution | No alias table; entity matching is exact whole-term on `normalized_name` | ❌ absent |
| Unlinked mentions | Not modelled | ❌ absent |

**The difference underneath all of it.** Obsidian graphs a corpus a person
*authored*, and its unit is a document with internal structure. Raiker graphs
work it *observed*, and its unit is a citation with no sub-document model at all.
So even the parity rows above are parity on mechanics over different material: an
Obsidian edge means *someone said these are related*, and a Raiker edge means
*some work needed both of these*. That is the much weaker claim, which is why
co-citation edges are labelled `shared_sessions` rather than presented as links,
and why the reference graph is not fed into retrieval scoring — an inferred edge
is good enough to *offer a model somewhere to look* and not good enough to
*change what a search returns*.

**2026-08-21 update.** Raiker's knowledge graph has two populated halves. The
reference half fills from `turn_sources`; the claims half fills only from
accepted, evidence-bound entity and relationship proposals. Inferred parser
output stays in review and cannot reorder recall until accepted.

**Closing the gap, in effort order.** Tags as graph nodes (low — memories
already carry them); stored passage offsets, which also settles the
block-reference row (medium); the MEM-06 extractor (medium, and the binding
extractor follow-through (shipped as MEM-06); authored links (medium, but a product question before an
engineering one — it would make Raiker partly a vault, which may not be what it
should be).

---

### Categorical confirmation — does this go beyond the reference platforms?

Asked and answered per addition, rather than assumed.

| Addition | Beyond the reference platforms? | Why, categorically |
|---|---|---|
| One retrieval path for the agent and the runtime (MEM-11) | **Parity-restoring, not beyond.** | Every reference product has exactly one retrieval path, so none can have this bug. Raiker had two and they disagreed. Fixing it removes a defect Raiker invented for itself; it does not create an advantage. Stated plainly because the alternative is to bank a repair as a differentiator. |
| Per-hit leg provenance (`sources`) | **Yes, beyond.** | Cowork, ChatGPT, Codex and Claude Code return ranked results; none tells the model *which retrieval mechanism* found each one. It matters because a model weighing whether to trust a recalled fact is currently reasoning from rank alone, and rank conflates "three signals agree" with "one signal is confident". |
| Evidence-bearing graph edges | **Yes, beyond.** | A knowledge graph elsewhere is a derived structure asserted by the system. Raiker's edges each name an approved memory, so a graph claim is auditable back to owner consent and revocable by archiving that memory. No reference product ties graph topology to a governed approval record. |
| Naming the embedding space on every reply | **Yes, beyond.** | Reference products do not disclose which embedding answered, because they have one and it does not change. Raiker's is owner-selected and may be a labelled lexical fallback, so not saying would be a claim of semantics it may not have. |
| Bounded, reported graph anchoring | **Yes, beyond.** | Products with graph retrieval do not disclose *what the traversal started from*. Naming the anchors turns "the graph leg ran" into "it ran from *helios*", which is the difference between a fact a reader can check and one they must accept. |
| A model-facing graph traversal tool | **Parity.** | Hermes exposes graph tools and Cowork surfaces connected work. Raiker had the data and not the tool; this closes a gap rather than opening a lead. The *governance* of that tool — capability gate, evidence per edge, sensitivity filtering inherited from memory — is where the lead is, and it is listed separately above. |
| Backlinks over the citation ledger (MEM-14) | **Yes, beyond.** | Cowork, ChatGPT, Codex and Claude Code all show a model what *this* turn used, and none lets it ask what *other* work used the same thing. The inverse is where the value is: it is how a model discovers that a file it just read is the one three earlier conversations argued about, which is a fact no forward citation list can produce. Obsidian has it for a vault of authored notes; no agent product has it for a work history. |
| Reference counts and co-citation weights | **Yes, beyond.** | Borrowed from Obsidian rather than invented, and beyond the agent field because no reference product models the citation record as a graph at all. Counting matters for the same reason it does in a vault: presence is nearly free and frequency is not, so an uncounted edge set ranks a passing mention with a dependency. |
| Unresolved references reported rather than dropped | **Yes, beyond.** | The reference platforms drop dead citations silently, which is the failure mode that looks like success — the work reads as ungrounded rather than as grounded in something deleted. Raiker reports four resolution states and refuses to guess about targets it never held, calling a web page `external` rather than `unresolved`. |
| Stored passages, dated as snapshots | **Yes, beyond.** | Two claims at once. That a reference resolves to *text* rather than to a document is Obsidian's block reference applied to a citation record. That the text is labelled as what reached a turn at a moment is Raiker's own: it is the difference between a quotation and an unchecked assertion about a file's present contents, and a model given the first without the second will make the second. |
| Refusing to feed inferred edges into retrieval | **A restraint, not a capability.** | Recorded because the opposite is the tempting build. Co-citation edges are inferred, and wiring them into scoring would let "these two files were open together once" reorder a search — topology outranking evidence, which is the failure MEM-12's `max`-not-sum rule already exists to prevent. The reference graph offers a model somewhere to look; it does not change what a search returns. |

**Deliberately not built, with the reason.** The **Knowledge Map** page stays a
human surface. It is a visualisation of sessions, tasks, approvals, memories and
backups — every one of which the model already reaches through
`conversation_search`, `memory_search`, `knowledge_graph`, and the task and
approval tools. Exposing it again as a tool would be a second path to the same
facts with no new capability, and a second path is exactly what MEM-11 was.
The *knowledge graph* is the part that was genuinely unreachable, and that is
what `knowledge_graph` covers.

**Still open.** Semantic recall remains off on a default install (MEM-10), so
the vector leg is the labelled lexical fallback until an owner selects a model —
which means the paraphrase case is still answered by the graph leg or not at
all. `MEM-04`, `MEM-06` through `MEM-09` are unchanged by this round; MEM-06 in
particular is load-bearing here, because the graph leg now works and **nothing
populates the graph** on a default install, so it is reachable and empty.

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
| Relevance-ranked lexical recall | Every reference product ranks recall by relevance, not by time | Both indexes are FTS5 and both searches order by `bm25()` before recency, at one index evaluation per query — the rank is selected alongside `memory_id` and joined, not computed per row (23 ms against 800 memories; the correlated form measured 5.2 s, produced correct answers, and is now guarded by a plan-shape test because no timing or correctness test caught it). Memory weights the approved sentence above its tags (`0.0, 1.0, 0.4`); conversation search weights only the indexed `text` column. Proven by the case MEM-05 described: the best answer is the *oldest* row and survives a limit of two | ✅ |
| Search engine chosen by measurement | Not a control any reference product exposes | The engine is **probed**, not declared: a temporary `fts5` virtual table is created and dropped, because a build can advertise `ENABLE_FTS5` and still refuse the module. A build without FTS5 keeps FTS4, keeps working, and says so on `/api/health` — `snippet()` takes its six arguments in a different order on each engine, so the order is derived from the probe rather than written once and assumed | ✅ beyond |
| A capability claim that expires with its dependency | Not a control any reference product exposes | The FTS4 claim these indexes were built on was **true when written** and went stale when `sqlcipher3-wheels` gained FTS5 at 0.5.6 — while the declared floor `>=0.5.0` named a version that was never published. Three things now stop that recurring: the floor is `>=0.5.6` with the per-version measurements recorded beside it, CI asserts FTS5 with `bm25()` before the suite runs, and `packaging_smoke_test.py` asserts the same of the frozen release bundle. A degraded build fails a build rather than a search | ✅ beyond |
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
tracked as **MEM-10**, raised in this round in
[`plans/MEMORY_RELIABILITY_PLAN.md`](plans/MEMORY_RELIABILITY_PLAN.md).
`MEM-04`, `MEM-06`, `MEM-07`, `MEM-08` and `MEM-09` are unchanged by this round.

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
| Hooks | Claude Code hook events; OpenClaw gateway events | Sixteen events, all emitted; a hook can block or annotate, never grant; owner off switch; the page states which rules can decide and which only observe | ✅ |
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
| A `Chat` \| `Build` surface toggle that carries the draft | **Removed in the 2026-08-21 composer round — see below** | Removed because the sidebar already moves between the two surfaces, and a switch in the control bar of an open conversation is one more control on a bar that had to get shorter. The cited Cowork source describes choosing Cowork *when starting* work from the message box; it does not establish a mid-conversation switch, so nothing in the reference set is lost by dropping one. |
| Governance chips on the same bar | **Yes** | No reference composer carries an approval-mode chip, an execution-environment badge and a measured context-capacity badge at all, because none of them has a governed answer to put in one. |

**Voice has since landed.** GAP-CHAT C16 is closed by FIXED-247: both composers
carry one shared microphone control, owner-triggered response playback, one
global audio owner and the same explicit Send boundary. Full-duplex live voice
is recorded as future work rather than implied by the turn-based control.

---

## Governed voice control set — GAP-CHAT C16

Reviewed 2026-08-21 against official descriptions of
[ChatGPT voice](https://help.openai.com/en/articles/8400625-voice-mode-faq) and
[Claude voice mode](https://support.anthropic.com/en/articles/11101966-using-voice-mode-on-claude-mobile-apps),
and against the documented control surfaces of Claude Code, Codex, OpenClaw,
DeepSeek Harness and Hermes Agent cited elsewhere in this document. Where those
primary sources do not establish a voice control, this table says so rather
than inferring one.

| Control | Reference requirement | Raiker result | Beyond the reference set? |
|---|---|---|---|
| Dictation in Chat | ChatGPT and Claude accept spoken input | Browser recognition writes into the ordinary editable Chat composer | **No — parity** |
| Dictation in Build | No equivalent is established for Claude Code, Codex, DeepSeek Harness or Hermes Agent by the cited primary sources | The identical control and state machine ship in Build | **Yes** — coding work gains voice without a second execution route |
| Explicit send | Voice conversation products may submit a spoken turn as conversation input | Recognition can never call submit; **Done** finalises only, and a later Enter or **Send** is required | **Yes** — the owner can review the exact instruction before it enters an agent loop |
| Reversible draft | Editing is possible in text composers | **Cancel** and permission/error recovery restore the byte-for-byte pre-dictation draft | **Yes** — speech is an undoable draft operation |
| Input provenance | The reviewed voice products disclose voice use, but do not establish Raiker's gateway metadata contract | Only `typed`, `dictated` or `mixed` pass HTTP, envelope and gateway validation; audit retains the value, not audio or another transcript | **Yes** — useful, privacy-preserving control evidence |
| Manual read-aloud | ChatGPT and Claude speak responses in voice mode | Only a completed answer can be read; playback is manual and interruptible | **No — parity**, with a safer turn-based default |
| One audio owner | Voice products coordinate listening and speaking within their own live session | Starting Chat dictation, Build dictation or response playback stops the previous owner | **Yes** — cross-surface displacement prevents hidden listening or overlapping output |
| Language and processing disclosure | ChatGPT and Claude expose voice/language behavior | Owner-scoped language choice; UI states that recognition and playback depend on browser/OS services and may use online processing | **No — required parity and disclosure** |
| Full-duplex conversation | ChatGPT and Claude support continuous voice, spoken replies and interruption | Not built. Continuous listening, barge-in, hands-free control and wake/stop state remain future work | **No — currently behind** |
| Governed full-duplex task control | No cited reference establishes action-bound spoken confirmations plus accepted/refused receipts | Proposed: visible live transcript, explicit confirmation for consequential controls, barge-in cancellation, gateway/policy parity and durable receipts | **Yes — conditional**; this is the bar for the future feature to be more than parity |

Compatibility requirements for the future full-duplex path are strict: it must
reuse the prompt and task-control gateway contracts; distinguish conversation,
dictation, speaking and consequential-control confirmation states; expose a
persistent stop affordance; stop listening on route, lock and owner changes;
make interruption cancel the exact playback/turn it names; and store neither raw
audio nor a shadow transcript by default. OpenClaw, DeepSeek Harness and Hermes
Agent remain relevant harness comparisons for gateway, tool and control parity,
but their cited primary sources do not establish an equivalent end-user voice
surface.

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
[BUG-216, closed as FIXED-240](plans/FIXED_ITEMS.md#fixed-240--deep-windows-paths-silently-made-approved-writes-irreversible): on Windows, a workspace nested deeper than
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

## 2026-08-17 review — BUG-194's remainder and MEM-04

Same categorical question as the 2026-08-16 round: for each control this round
added or proposed, **does it take Raiker past Claude Cowork, Claude Code,
ChatGPT, Codex, OpenClaw, DeepSeek Harness and Hermes Agent — yes or no** — and
why. Parity is still not a failure; it is the honest answer for table stakes
Raiker did not have.

### Shipped this round

| Control | Beyond the reference set? | Why |
|---|---|---|
| Eidetic observation recorded for every governed tool result | **No — parity in intent, different in kind** | Every reference product already keeps what a tool returned; it keeps the *material*. Raiker keeping a record was the gap (MEM-04), and closing it is table stakes. What the record contains is where the difference starts. |
| An observation that carries no material, by schema | **Yes** | ChatGPT, Claude Code, Cowork and Codex retain tool output verbatim in conversation storage, which makes their memory exactly as sensitive as the most sensitive thing the agent ever read. A row of summary, checksum, byte count and retention class cannot leak what it never held. |
| Refusing to capture credential-shaped material | **Yes** | No reference product treats a tool result differently on sensitivity — the transcript takes whatever came back. Raiker runs the classifier that already refuses credential-like memory text before anything is written. |
| A refusal that is itself a visible row | **Yes** | The alternative every product takes is silence, and silence makes "nothing ran", "everything was refused" and "this feature is off" identical from where the owner sits. |
| A skipped observation storing no digest either | **Yes** | A SHA-256 of a credential is still a fact about the credential. No reference product faces the question because none skips. |
| Retention class chosen by what produced the material | **Yes** | Reference retention is per account or per conversation, one setting for everything. A fetched page and a workspace file have different half-lives and one setting cannot say so. |
| Untrusted provenance that survives into storage | **Yes** | Every reference product labels external content as untrusted *for the length of the turn*, then stores it beside first-party content. Here `promotable_to_memory` is false for web, connector and MCP material permanently, so a fetched page cannot become a memory candidate months later through a path that forgot where it came from. |
| Memory → Observations, with per-row delete | **Yes** | ChatGPT and Claude offer conversation deletion; none offers a view of *what the agent recorded seeing*, with its retention, its expiry and its refusals. |
| Restart reattachment for a background run | **No — parity** | Codex and OpenClaw supervise long-running work across runtime churn. Raiker did not; now it does, on POSIX. |
| Reattachment as an **authentication**, not a pid lookup | **Yes** | A pid can be reused by a stranger, which is why the BUG-194 entry refused to build reattachment on one. Raiker keeps the run's instance key encrypted at rest and reattaches by proving identity over an authenticated frame — a socket that cannot answer it is refused, and the run stays honestly `lost`. |
| Persistent session boundary for the container backend | **No — parity** | Claude Code, OpenClaw and Hermes retain a session boundary. This closes a gap; it does not pass them. |
| Persistence and reset shipped as one control | **Yes** | Reference products with a persistent sandbox generally offer a rebuild as a configuration action, if at all. Treating "it accumulates state" and "you can get back to a known state" as one feature, and refusing the reset by name on a boundary that has nothing to reset, is the governed version. |
| The environment card deriving capabilities **and limitations** from measured flags | **Yes** | Reference products show a fixed feature list per sandbox mode. Raiker's card builds both its positive rows and its unavailable summary from the backend's own `CommandFeatures`, so a capability cannot be simultaneously advertised and denied. The rendering correction itself is parity; the single-source, evidence-bound disclosure is the differentiator ([FIXED-245](plans/FIXED_ITEMS.md)). |

### Proposed and deliberately not built

| Proposal | Beyond the reference set? | Why it was not built now |
|---|---|---|
| Restart reattachment **on Windows** | **No — parity** (Codex, OpenClaw) | `AF_UNIX` borrows the directory's authorisation. A named pipe is reachable by name from any session on the machine, so the equivalent needs its own design and its own proof — the same reason Windows PTY is still open. |
| Exact replay of an observation's material | **No — and deliberately behind** | Every reference product can replay because it kept the material. Raiker cannot, because it did not, and that is the trade the row exists to make. The governed artifact reference is the honest substitute where one exists. |
| A retention sweep that runs by itself | **No — parity** (ChatGPT expires on a schedule) | Tracked as MEM-07. The expiry date is computed and stored per row today, and an owner-confirmed cleanup exists in its place; what is missing is the unattended sweep. |
| Opening a recalled answer at the turn it came from | **No — parity** (ChatGPT, Claude) | Tracked as MEM-08. `source_event_id` is durable and correct; the missing part is the read-back surface. |
| An observation naming the **capability** the call crossed | **Yes** | No reference product's tool record is governed at all, so none can say which authority a result came through. |
| A **diff between two observations of the same path** | **Yes** | The checksums already make "this changed" computable without either version being stored. No reference product can do this without keeping both copies. |
| A boundary-drift watcher | **Yes** | Carried forward from the 2026-08-15 round, unchanged: re-measure when a firewall service or a protected path's DACL changes rather than on a timer. |

**The pattern, restated.** Every row marked *Yes* is the same move as last round:
the reference product keeps the thing, and Raiker keeps **an accountable record
of the thing** — the provenance, the class, the refusal, the authority. The two
new ones this round are worth naming separately, because they are the same idea
applied to storage and to process identity: an observation that cannot leak what
it never held, and a reattachment that cannot be spoofed by a number the kernel
hands out again.

---

## 2026-08-21 review (second round) — Build modes, Cowork-shaped Chat, and the C16 re-verification

Same categorical question as every round: for each control this round added,
removed or verified, **does it take Raiker past Claude Cowork, Claude Code,
ChatGPT Chat/Work, Codex, OpenClaw, DeepSeek Harness and Hermes Agent — yes or
no** — and why.

Primary sources read for this round:
[Cowork overview](https://claude.com/docs/cowork/overview),
[Cowork Dispatch](https://claude.com/docs/cowork/guide/dispatch),
[Cowork projects](https://claude.com/docs/cowork/guide/projects),
[Get started with Cowork](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork),
[Claude Code permissions](https://code.claude.com/docs/en/permissions) and
[Claude voice mode](https://support.claude.com/en/articles/11101966-use-voice-mode).
Where a cited source does not establish a control, this section says so rather
than inferring one.

### Shipped this round

| Control | Beyond the reference set? | Why |
|---|---|---|
| Build opens in **Auto** | **No — parity in shape, and a correctness fix** | Claude Code starts in a mode set by `defaultMode` and cycles with `Shift+Tab`; Raiker's cycle already matched. Opening in **Edit** meant every new Build conversation silently tightened *below* the owner's own Permissions page, which is the opposite of what a default should do. Auto is the only mode that sends no override, so opening in it defers to Permissions instead of overriding it. |
| The Build operating protocol, selected by surface | **Yes — narrowly** | Claude Code, Codex and Hermes all ship a standing system prompt, and Cowork ships skills; that part is parity. What the cited sources do not establish is a protocol whose *selection is a recorded fact*: Raiker's prompt envelope carries `surface`, the gateway validates it against a closed set and writes it into `prompt_received`, so the audit log states which protocol a turn ran under instead of leaving it to be inferred. See [`RAIKER_BUILD_PROCESS.md`](RAIKER_BUILD_PROCESS.md). |
| A surface that selects a method and never authority | **Yes** | An unknown surface is refused (`invalid_prompt_surface`) rather than defaulted to Build, and a test asserts the two surfaces are offered an identical tool set. Reference products vary the system prompt per mode freely, because in none of them does the prompt sit inside a governance envelope that could be widened by it. |
| The Cowork-minimal Chat composer | **No — parity** | Cowork's composer is short. Raiker's carried a Build switch, an execution-environment badge and a context-capacity chip that repeated what the context ring already reported. Removing three controls is not a differentiator; keeping the two governance chips that *do* have a governed answer is the part that stays. |
| The Code-minimal Build composer | **No — parity** | Claude Code's Mode menu carries its own explanation. Raiker printed the same explanation three more times — a per-mode paragraph above the box, an info button and a tooltip. One menu now carries it; the only line left above the composer is the one the menu cannot know, which is what the owner's standing permissions actually allow under Auto. |
| `/schedule` and `/tasks` in Chat | **No — parity** | Cowork has `/schedule` and a **Scheduled** sidebar. Raiker already had the cadences (one-off, daily routine, background agent) and the governed `create_task` tool; what was missing was the shortcut from the conversation to them. Neither command creates or starts anything — a command that silently scheduled work is the invisible automation the approval path exists to prevent. |
| C16 audio released when a surface is navigated away from | **Yes — and it was a real defect** | Found by this round's independent re-verification, not by a report. Chat and Build stay *mounted* across route visits so a long conversation survives a trip to Permissions, which meant the unmount cleanup carrying the `route` reason never ran on an ordinary navigation: dictation kept listening behind a hidden composer whose only **Cancel** control was hidden with it. Both surfaces now release the audio owner the moment they stop being on screen, keeping the finalized words exactly as **Done** would. No cited reference product keeps a conversation surface mounted while hidden, so none faces this — but Raiker made the invisible-capture promise, which is why it had to be kept. |

### Independent verification — GAP-CHAT C16

Re-checked against the code rather than against the closure note. Nine of the ten
claims held as written; the tenth is the defect fixed above.

| C16 claim | Verified how | Result |
|---|---|---|
| One shared **Dictate** control in Chat and Build | `VoiceDictationControl` is imported and rendered by both views | ✅ holds |
| Dictation writes into the ordinary editable draft | `onchange` writes `promptText`; the textarea is unchanged and still typable | ✅ holds |
| **Done** finalises without sending | `done()` calls `preserveFinalized()` and releases the owner; it never calls `submit` | ✅ holds |
| The first `Enter` finalises, a later one sends | `submit()` returns early while `voiceControl.active()` | ✅ holds |
| **Cancel** restores the byte-for-byte pre-dictation draft | `cancel()` restores the snapshot and caret, and resets provenance through `onrestored` | ✅ holds |
| Only `typed` / `dictated` / `mixed` cross the boundary | Pydantic `Literal` at the route, `normalize_input_mode` in the envelope **and** again in the gateway | ✅ holds |
| No audio and no second transcript retained | `prompt_received` carries `client_type`, `prompt_length`, `input_mode` and `surface` only; a test asserts the spoken text is absent from the record | ✅ holds |
| Read-aloud is manual, completed-only, and skips code and URLs | Rendered under `{#if !turn.streaming}`; `speechText` replaces fenced code with "Code block." and strips raw URLs | ✅ holds |
| One audio owner across both surfaces | A module-level `audioSessionCoordinator`; starting recognition or playback displaces the previous owner and notifies it | ✅ holds |
| Listening stops on route change | The `route` cleanup ran only on unmount and on **New chat**, and neither happens on an ordinary navigation | ❌ **fixed this round** |

The boundary itself is also confirmed correct against the reference set. Claude's
own documentation states that dictation is available in Cowork and Code while
voice mode is not — so shipping turn-based dictation in both surfaces and leaving
full-duplex conversation out is the same line Anthropic draws, not a shortfall.

### Gaps this round identified and did **not** close

Recorded here and, where they are work rather than a decision, in
[`plans/TO_BE_FIXED.md`](plans/TO_BE_FIXED.md).

| Gap | Reference | Raiker today | Compatibility requirement to close it |
|---|---|---|---|
| **Auto mode has no safety classifier** | Claude Code's `auto` "auto-approves tool calls with background safety checks that verify actions align with your request"; Cowork's Auto "reviews each action for safety" and blocks what it judges unsafe | Raiker's Auto sends no override and defers to standing permissions. There is no second opinion on whether an action matches what was asked | A classifier would have to be a *governed* reviewer: its verdict recorded as evidence on the approval, never a silent grant, and never able to widen a gate. Absent that it is a heuristic that makes Auto feel safer without being safer, which is worse than not having it |
| **`dontAsk` and `bypassPermissions` postures** | Claude Code offers both; Cowork's Skip is the second | Raiker has Manual / Auto / Skip on the approval chip; there is no deny-unless-preapproved posture | `dontAsk` is the more useful of the two for a governed runtime and maps cleanly onto existing decision modes. It is a mode-list addition, not new enforcement |
| **Cowork Dispatch** — one conversation that plans, spawns child tasks, and routes each to Chat or Build | [Dispatch](https://claude.com/docs/cowork/guide/dispatch) | `spawn_subagent`, background agents, nested tasks and a live work board all exist; what is missing is the single briefing conversation that owns them and the per-child routing | The routing decision has to be visible and re-decidable, and each child must carry its own approvals rather than inheriting the parent's. Raiker's per-task session model already supports this; the surface does not exist |
| **Ten-minute auto-deny on an unanswered forwarded approval** | Dispatch forwards a child's permission prompt and denies it automatically after ten minutes | Raiker approvals wait indefinitely | A timeout is only safe if the expiry is itself a recorded decision with its reason, not a silent drop |
| **Project links** | A Cowork project holds reference URLs alongside folders and instructions | Raiker projects hold instructions, shared attachments, a root subpath and an opt-in approved-memory boundary — links are absent | A link is a fetch the agent may perform, so it belongs to the web-access gate rather than to project metadata. That is the design question, not the storage |
| **Hosted scheduling** | Cowork's scheduled tasks "run in the cloud, so they don't need your computer to be awake" | Raiker schedules run on the resident local host | Out of scope by design — Raiker is local-first and single-user. Recorded so the difference is stated rather than looking like an oversight |
| **Hooks, plugins and channels** | Claude Code ships all three; Cowork installs plugins from **Customize** | **Hooks: at parity** (2026-08-22 — 16 events all emitted, owner off switch, owner surface). **Plugins: partial** — a plugin contributes hook rules at `plugin` scope; skills, MCP servers and panels do not. **Channels: absent** — specified in `CHANNELS_SPEC.md`, no delivery path | Reduced 2026-08-22. Channels are now the largest remaining piece, and the one that still needs an accepted threat model before controls are offered |

### Recommended improvements, in the order they are worth doing

1. **`dontAsk` as a fourth approval posture.** Low effort, real coverage gain,
   and it needs no new enforcement — the decision modes already express it.
2. **A governed alignment reviewer for Auto.** The differentiator is not the
   classifier; it is that its verdict is recorded as evidence on the decision and
   can never widen a gate. Only worth building with that constraint.
3. **A Dispatch-shaped briefing conversation.** Raiker has every part except the
   surface that owns the children and routes each to Chat or Build.
4. **Hooks execution**, which unblocks plugins and channels behind it.

---

## 2026-08-22 review — hooks, and the plugins/channels remainder

The largest single gap to Claude Code has been *hooks → plugins → channels* for
several rounds. This round closed the part of it that was closable, and this
section states exactly which part that was.

Primary source read for this round:
[Claude Code hooks reference](https://code.claude.com/docs/en/hooks) — its event
list, five handler types, settings scopes, decision fields, matcher syntax,
`/hooks` browser, `disableAllHooks`, and its documented behaviour on a malformed
config.

### What was actually true before this round

Worth stating, because two earlier entries in this document were stale. The
hooks *backend* was not "spec only": `raiker/hooks/` is a working dispatcher,
wired through the gateway and the tool broker, with nine dispatched events and a
`PreToolUse` deny that really short-circuits to a denied `PolicyDecision`. What
was missing was everything an owner could see or trust:

| Before | After |
|---|---|
| A typo in `.raiker/hooks.json` raised out of `HooksRegistry.load` inside the `AgentGateway` constructor, so **every prompt in the product failed** with a raw `JSONDecodeError` | A source that cannot be parsed contributes no rules and is reported; the others load; the runtime is untouched |
| No route, no page. Hooks were written into JSON and observed by reading the audit log by hand | Extensions → **Hooks** over `GET /api/hooks` |
| A rule on `SessionEnd` parsed, matched nothing, and looked exactly like one that worked | Marked *configured but never fires*, against a published `DISPATCHED_HOOK_EVENTS` a test derives from the call sites |
| A rule naming a builtin this build does not ship was counted as enforcing and failed at dispatch | Reported unavailable, excluded from "can decide", with the real builtin names published beside it |

### Shipped this round

| Control | Beyond the reference set? | Why |
|---|---|---|
| A read-only hooks browser | **No — parity.** Claude Code's `/hooks` is a read-only browser over events, matchers, handlers and source files | Raiker had nothing. This is the bar, not a differentiator, and the panel is deliberately read-only for the same reason `/hooks` is: the config files are the owner's own text. |
| A malformed config named, located, and survived | **Yes** | The cited reference documents that invalid JSON "fails silently or logs errors". Raiker names the file, the line and column the parse stopped at, states that its rules did not load, and keeps every other source and the whole runtime working. Failing closed for the file without failing closed for the product is the useful half. |
| A configured rule that can never fire, marked | **Yes — with an honest caveat** | No reference product needs this, because Claude Code emits every event it documents. Raiker does not, so the marking exists to make a Raiker gap visible rather than to beat anyone. It is a differentiator in *kind* — the surface refuses to let a dead rule look enforcing — and a consequence of being behind on event coverage. |
| A handler naming a builtin that does not exist, marked | **Yes** | Same shape as the row above and the same reasoning: the rule parses, matches, and fails every time. Counting it as a guard would be the surface asserting a safeguard that is not there. |
| Rules separated into **Can deny or ask** and **Observes only** | **Yes** | Claude Code documents which events can block in prose. Raiker computes it per rule, from the event *and* whether that rule's handlers hold decision authority, and prints the answer on the rule. |
| An owner off switch that keeps the rules visible | **No — parity, with one small difference** | Claude Code has `disableAllHooks`; Raiker had nothing, so the switch itself is the bar. The difference is that the rules stay listed and the page says they are loaded and will not run, rather than the surface going empty — off is a state to display, not an erasure. It is an owner setting rather than a fourth config source, so a `config/hooks.json` that travelled with a repository cannot re-enable itself ([FIXED-254](plans/FIXED_ITEMS.md)). |
| Hooks may only ever tighten | **Yes — already true, now visible** | Claude Code hooks return `permissionDecision: "allow"`, so a hook there can *grant*. Raiker's `combine()` accepts only `deny` and `ask` from an authoritative handler; nothing a hook returns can allow an action policy refused. The panel now says so on the page rather than leaving it to the spec. |

### Gaps this round identified and did **not** close

| Gap | Reference | Raiker today | Compatibility requirement to close it |
|---|---|---|---|
| ~~**22 of ~31 lifecycle events**~~ | Claude Code fires `Stop`, `SubagentStart/Stop`, `TaskCreated/Completed`, `PostToolBatch`, `Notification`, `FileChanged`, `ConfigChange`, `Elicitation`, `WorktreeCreate/Remove` and more | **Closed 2026-08-22 as [FIXED-255](plans/FIXED_ITEMS.md).** Sixteen events accepted, all sixteen emitted — `Stop`, `StopFailure`, `SubagentStart/Stop`, `TaskCreated/Completed` and `SessionEnd` gained call sites | The rule this round established held: an event is published as dispatched only when a test can derive it from the code, and the test now derives all sixteen |
| **Four of five handler types** | `http`, `mcp_tool`, `prompt`, `agent` | `command` and `builtin`. Unchanged; now tracked as **BUG-226** | Each needs a gated surface Raiker keeps closed: network egress, the MCP broker, a model call, a subagent. A hook that reaches the network is an egress decision before it is a hook |
| **Plugin execution** | Claude Code plugins bundle skills, agents, hooks, MCP servers, LSP servers and monitors; Cowork installs them from **Customize** | **Reduced 2026-08-22 as [FIXED-256](plans/FIXED_ITEMS.md), then again the same day.** *Superseded by the second pass:* skills shipped as FIXED-259 and MCP-server **offers** as FIXED-260. `execution_enabled` stays `False` — a contributed rule runs as a *hook* | The blocking question was what a plugin's code is allowed to be, and the answer taken is that it gets no execution surface of its own. Panels (BUG-228) and LSP (BUG-227) remain |
| **Channel delivery** | Claude Code channels relay permissions and messages over MCP | *Superseded by the second pass:* delivery was not absent, it was **unreachable** — no way to pair. Pairing, the sender allowlist, the inbound secret, per-sender rate limits and signed outbound delivery all shipped (FIXED-265, FIXED-267, FIXED-268). What remains is above the transport: routing modes and approval relay, tracked as **BUG-225** | The gate is a decision about what an inbound message becoming *work* means, not the transport code |

### Recommended improvements, in the order they are worth doing

1. ~~**`disableAllHooks`**~~ — shipped this round as
   [FIXED-254](plans/FIXED_ITEMS.md).
2. ~~**`Stop` and `SubagentStop`**~~ — shipped 2026-08-22 as
   [FIXED-255](plans/FIXED_ITEMS.md), along with `StopFailure`, `SubagentStart`,
   `TaskCreated`, `TaskCompleted` and `SessionEnd`. The prediction held: every one
   had an obvious call site already in the runtime.
3. ~~**Plugin execution**~~ (BUG-221) — first kind shipped 2026-08-22 as
   [FIXED-256](plans/FIXED_ITEMS.md). It was a design task about authority, and
   the answer was that a plugin gets no execution surface of its own. Skills,
   MCP servers and panels remain, in that order.
4. ~~**Channel activation**~~ (BUG-225) — the transport half shipped 2026-08-22
   as [FIXED-265](plans/FIXED_ITEMS.md), [FIXED-267](plans/FIXED_ITEMS.md) and
   [FIXED-268](plans/FIXED_ITEMS.md). Routing modes and approval relay remain,
   and their gate is still a threat model rather than an implementation.
5. **The four refused handler types** (BUG-226). `prompt` first — it makes no
   outbound request and its output is context, not a decision.

---

## Rule For New References

When Raiker adopts a concept from another platform, the docs must add concept name, Raiker behaviour, contract/schema, lifecycle, storage, security rules, events, tests, UI surface, and build phase.

If these are not present, the concept is not considered fully specified.
