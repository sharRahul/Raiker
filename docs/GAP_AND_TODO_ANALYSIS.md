> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

# Gap & TODO Analysis

Date: 2026-06-21

This document is the canonical "what is still missing" summary produced by the documentation audit.
It replaces the older `REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md`. It separates two kinds of gap:

1. **Missing docs** — code that exists but has no dedicated documentation.
2. **Missing code (TODO)** — behaviour the documentation specifies that is not implemented (or is
   intentionally disabled and awaiting an activation task).

The implementation control ledger is `docs/IMPLEMENTATION_STATUS.md`; this file only tracks gaps.

Backend hardening note (2026-06-21): direct CLI durable-memory mutation bypass is closed via `_govern_admin_mutation`; Runtime Authority / Action Router governs all mutation actions through capability gates, policy engine, risk classification, approval/risk acceptance, and event logging; AI-executable roles, human-only protections, and domain scopes are enforced at the authority level. Enforcement: strict non-allow blocking, role revoke governed, capability gate per action, and risk acceptance enforced before mutation. Runtime readiness: `runtime_enablement_candidate` — `controlled_runtime_mode_activation_implemented`. Human `runtime_gate_manager` can activate `local_single_user_runtime` and enable `admin_mutation`/`role_mutation`; AI cannot activate runtime modes or capability gates. Approval resolution is metadata-only; integrated real executors are governed per action, while no-executor capabilities remain disabled/fail-closed.

Executor implementation update (2026-07-06): the control plane (`raiker/control/`),
the API + session→principal auth surface (`raiker/api/`), the per-capability
`ActivationRequirement` model (`raiker/runtime/authority/activation.py`), and the
executor registry (`raiker/runtime/executors/`) are implemented.
`REAL_EXECUTOR_CAPABILITIES` is the exact source of truth for integrated executors:
Tier 1, Tier 2, graph/semantic/vector/model-provider runtimes, orchestration/channel/
container/scheduled/model/plugin slices, and local email/calendar/reminder stores.
Those gates default `enabled_runtime` and are governed per action (decision mode
default `ask`, PolicyEngine, critical-risk floor, and independent allowlists).
Capabilities outside that set — notably finance/investment/medical/pregnancy/CCTV/
home-security/hardware plus remote/cloud command execution — have **no real executor
and fail closed** (`not_implemented` / `activation_blocked:no_executor`); they cannot
be flipped to a working state and never fabricate success. `has_executor` is
registry-backed (no static allowlist), enforced by
`scripts/validate_runtime_enablement_readiness.py`. Per-capability detail:
`docs/RUNTIME_EXECUTORS_SPEC.md`.

Executor implementation update (2026-07-04): `plugin_install` has moved out of
the no-executor backlog as Phase 4 slice 8. It is a governed local manifest
validation + install-record executor only. Arbitrary plugin code execution,
package fetch, archive extraction, or runtime permission grant still does not
exist.

Executor implementation update (2026-07-04, slice 9): `plugin_execution_cap`
has moved out of the no-executor backlog only for installed-plugin brokered
read-only tool invocation (`read_file`, `list_directory`, `glob`, `grep`)
through `ToolBroker` and `PolicyEngine`. Arbitrary plugin code/import/process,
network, writes, hooks, MCP/LSP, monitors, panels, and runtime permission grants
remain active gaps.

Executor implementation update (2026-07-04/05, slices 10-16): the Tier-4 plugin
path is now substantially implemented and out of the no-executor backlog,
integrated and governed. `plugin_revocation_cap` (slice 10) is the
fail-closed off-switch. Install-time supply-chain controls: dependency pins +
owner allowlist (slice 11), HMAC-SHA256 manifest signatures (slice 12), and
asymmetric Ed25519 signatures against an owner-trusted key (slice 13). **Plugin
code execution now exists** (previously the largest gap): `plugin_runtime_cap`
(slice 14) runs an installed, owner-allowlisted plugin's entrypoint as a bounded
subprocess (interpreter allowlist, workspace-scoped, timeout/output caps,
metadata-only); slice 15 adds optional per-plugin workspace subpath scopes; and
`plugin_sandboxed_runtime_cap` (slice 16) runs the entrypoint inside a
no-network container (read-only rootfs, dropped caps, only the entrypoint file
mounted) for kernel-level isolation. Still active gaps: in-process import of
plugin modules into the host, plugin hooks/MCP/LSP/monitors/panels activation,
per-plugin network-egress allowlisting for the bare-subprocess runtime, and
image build/pull management for the sandboxed runtime.

Completed items (no longer active gaps):
- strict runtime enforcement — completed
- controlled runtime mode activation — implemented
- persisted runtime mode state — implemented
- persisted capability gate state — implemented
- owner bootstrap — implemented and verified
- persisted owner principal — implemented
- acting principal resolution — implemented
- local single-user production hardening — implemented
- production_ready_local_single_user_runtime — ready

---

## 1. Missing documentation (code without a dedicated spec)

| Area | Code | State | Suggested doc |
|---|---|---|---|
| Subagent planning | `raiker/agents/subagents.py` | Stub: `SubagentPlan` always returns `can_spawn=False` (`phase4_subagents_disabled_until_parent_policy_and_budget_controls_exist`). Covered only indirectly by `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`. | Add a short "current state" note to the multi-agent spec, or a dedicated `AGENTS_SPEC.md`. |
| Skill registry | `raiker/skills/__init__.py` | Metadata-only skill-candidate registry (Phase 9), disabled by default. No dedicated spec; only referenced from the self-improvement spec. | Document the skill-candidate lifecycle alongside `docs/SELF_IMPROVEMENT_MODEL.md`. |
| Agent Gateway | `raiker/gateway/agent_gateway.py` | Real metadata/contract surface, but documented only inside `docs/ARCHITECTURE.md` / `docs/RUNTIME_ORCHESTRATION_SPEC.md`. | Optional standalone `GATEWAY_SPEC.md` if the surface grows. |
| Approvals package | `raiker/approvals/` | Real `ApprovalInbox` (list/resolve) + readiness registry; covered by contracts/acceptance docs but no dedicated approvals spec. | Optional `APPROVALS_SPEC.md`. |

All other `raiker/` subsystems have at least one dedicated or clearly-mapped spec under `docs/`.

---

## 2. Missing code / TODO (documentation ahead of implementation)

These are **intentionally disabled** and correctly marked as such in the ledger. They are listed here
so the backlog is explicit. Each requires a named activation task with policy, storage, events,
approval, audit, and acceptance tests before it can be enabled.

| Feature | Spec | Current code reality | Status |
|---|---|---|---|
| Hook handler types `http` / `mcp_tool` / `prompt` / `agent` | `docs/HOOKS_SPEC.md` | `raiker/hooks/` implements only `builtin` + `command` handlers. | `specified_not_implemented` |
| Subagent spawning & multi-agent team execution | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` | Real bounded/governed in-process executors exist in `REAL_EXECUTOR_CAPABILITIES`; the older planning helper in `raiker/agents/subagents.py` remains a non-runtime stub and broader autonomous spawning extensions are deferred. | `implemented_policy_gated` (bounded slice); broader extensions `phase_scheduled_disabled` |
| Plugin code execution | `docs/PLUGIN_SYSTEM_SPEC.md` | Bounded subprocess runtime and no-network container runtime exist for installed owner-allowlisted plugins; in-process import isolation, hooks/MCP/LSP/monitors/panels, per-plugin network egress, and image build/pull management remain deferred. | `implemented_policy_gated` (bounded slice); broader extensions `phase_scheduled_disabled` |
| Graph/codemap runtime indexing | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` | Real governed local graph indexing executor exists; broader graph query/planning extensions remain deferred. | `implemented_policy_gated` (bounded slice); extensions `phase_scheduled_disabled` |
| Semantic/vector memory writes & embeddings | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_GOVERNANCE_RULES.md` | Real governed semantic memory, local deterministic vector embedding/search, and provider-backed embedding executors exist; broader learned semantics, external sync, and unrestricted memory automation remain deferred. | `implemented_policy_gated` (bounded slices); extensions `phase_scheduled_disabled` |
| External channel transports & notifications | `docs/CHANNELS_SPEC.md` | One bounded webhook transport and metadata-only channel approval relay exist with owner egress/pairing controls; broader channels/notifications remain deferred. | `implemented_policy_gated` (reference slice); extensions `phase_scheduled_disabled` |
| Remote/container/cloud execution | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` | Local container execution exists as a governed no-network/no-host-mount executor; remote/cloud command execution has no real executor and fails closed. | container `implemented_policy_gated`; remote/cloud `phase_scheduled_disabled` |
| Approval execution / approval relay runtime | `docs/CONTRACTS.md`, `docs/SECURITY_AND_POLICY.md` | Approval inbox resolution remains metadata-only; the separate `approval_execution_relay` executor exists for governed approved file-write proposals and does not make `/approve` execute actions. | `metadata_only` for resolution; relay `implemented_policy_gated` |
| Launchable Desktop / Mobile / IDE apps and hosted/multi-user REST API | `docs/UI_UX_DESIGN_SPEC.md` | Session-model records and read-only contracts only; no launchable apps. | `specified_not_implemented` |
| Local web dashboard (`apps/web` + `raiker-web` loopback API) | `docs/UI-implementation/` | **Implemented and launchable** (single-user, `127.0.0.1`): read-only governed views, governed prompt/turn/approval/runtime-mutation flows (approval resolution metadata-only), step-up-gated Security Settings; adds no authority. | `implemented_read_only` / `implemented_policy_gated` / `metadata_only` |
| Scheduled automations / hosted routines runtime | `docs/IMPLEMENTATION_STATUS.md` (Phase 5) | Local on-demand scheduled routines executor exists (no daemon); hosted/background routine platform remains deferred. | local slice `implemented_policy_gated`; hosted/background `phase_scheduled_disabled` |

The full list of disabled runtime flags (all `False`) is enforced by
`scripts/validate_repo_truthfulness.py` and documented in `docs/IMPLEMENTATION_STATUS.md`.

---

## 3. Structural notes

- **Phase 8 exists.** Phase 8 is the planned UI/client implementation phase and is recorded in `docs/ARCHITECTURE.md` and `docs/IMPLEMENTATION_STATUS.md`.
- **Pre-existing lint/type debt (out of scope for this docs audit):** `ruff check .` and
  `mypy raiker apps tests` currently report errors on the development branch (notably in
  the removed legacy Textual implementation and old tests) that predate this change. They are tracked here so
  they are not forgotten; the repo's documentation-truthfulness gate
  (`scripts/validate_repo_truthfulness.py`, `scripts/validate_phase_status.py`) and `pytest` pass.

## Phase 8 deferred UI/client and runtime implementation backlog (current, actionable)

All items below are specified but not implemented unless explicitly marked otherwise. They must not be enabled until policy, storage, event, and test gates exist and pass local validation.

| Feature | Current code reality | Relevant docs/specs | Status label | Proposed phase/task ID | Required policy/storage/events/tests | Safety gates that remain disabled | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| Rich/native TUI | Active Rich/Textual runtime removed; plain terminal remains. | UI/UX spec, command spec | phase8_deferred | RAIKER-8001 | Client contract tests, no bypass of AgentGateway/ToolBroker/PolicyEngine/approvals/events. | runtime_execution_enabled=false | Launches only after explicit Phase 8 scope; no Rich/Textual import required before then. |
| Desktop UI | Contract/readiness records only; no launchable app. | UI/UX spec | phase8_deferred | RAIKER-8101 | Auth/session storage, event-stream tests, approval binding tests. | external_channels_enabled=false | Desktop app cannot execute directly and uses gateway contracts. |
| Local web UI (`apps/web` + `raiker-web` loopback API) | **Implemented and launchable** local single-user dashboard: read-only governed views, governed prompt/turn/approval/runtime-mutation flows (approval resolution metadata-only), step-up-gated Security Settings. | `docs/UI-implementation/`, contracts | implemented (`implemented_read_only`/`implemented_policy_gated`/`metadata_only`) | RAIKER-8201 (done) | Auth (loopback, in-memory token), event redaction, API contract + security-regression tests (present). | network_execution_enabled=false | Adds no authority; routes through gateway/RuntimeAuthority/broker; runtime execution flags stay disabled. |
| Hosted/multi-user REST API | Contract/spec only; no hosted API server (the local loopback API is single-user). | UI/UX, contracts | phase8_deferred | RAIKER-8202 | Auth, CSRF/CORS, multi-user isolation, event redaction. | network_execution_enabled=false | Hosted server remains absent until authenticated policy-gated implementation. |
| Standalone native/mobile Dashboard | Read-only views are delivered via the local web dashboard; standalone native/mobile dashboards remain metadata/readiness only. | Feature matrix | phase8_deferred | RAIKER-8301 | Read-only event projections, redaction, parity tests. | notifications_enabled=false | Standalone dashboards are read-only unless future approvals permit writes. |
| Mobile apps | Contract/spec only. | UI/UX | phase8_deferred | RAIKER-8401 | Device session storage, approval UX tests, notification policy. | external_channels_enabled=false | Mobile approvals bind to same approval records. |
| IDE extension | Session contracts only; no extension runtime. | UI/UX, contracts | phase8_deferred | RAIKER-8501 | Workspace trust, editor transport, command parity tests. | process_execution_enabled=false | Extension cannot run tools outside gateway policy. |
| Voice UI and Browser Extension | Spec only. | UI/UX | phase8_deferred | RAIKER-8601 | Consent, transcript redaction, extension permissions tests. | external_channels_enabled=false | No microphone/browser access before explicit enablement. |
| Hook handler types http/mcp_tool/prompt/agent | Hook specs exist; handlers missing. | HOOKS_SPEC | specified_not_implemented | RAIKER-8701 | Handler policy, audit events, dry-run tests. | network_execution_enabled=false, plugin_execution_enabled=false | Unsupported hook types fail closed with clear errors. |
| Subagent spawning/team execution | Strategy docs/contracts only. | MULTI_AGENT_AND_SUBAGENT_STRATEGY | specified_not_implemented | RAIKER-8702 | Agent identity, budgets, event causality, cancellation tests. | runtime_execution_enabled=false | No subagent runtime until isolation and policy tests exist. |
| Plugin code execution | **Implemented (integrated, governed)**: `plugin_runtime_cap` (bounded subprocess, slice 14) and `plugin_sandboxed_runtime_cap` (no-network container, slice 16), gated on an owner plugin allowlist + interpreter allowlist + workspace/subpath scope, with HMAC/Ed25519 install signatures and revocation. | Tool/plugin catalog, `docs/RUNTIME_EXECUTORS_SPEC.md` | implemented (`implemented_policy_gated`) | RAIKER-8703 | Remaining: in-process module import, hooks/MCP/LSP/monitors/panels, per-plugin network egress, image build/pull. | plugin runtime gates default `enabled_runtime` but executor allowlists fail closed | Plugin code runs only when the integrated gate is enabled, the standing decision/risk policy allows execution, and the owner allowlists the plugin; otherwise it fails closed. |
| Graph/codemap runtime indexing | Real bounded local executor exists; richer graph query/planning remains deferred. | Architecture, memory specs | implemented_policy_gated (bounded); extensions deferred | RAIKER-9001 | Index storage migrations, redaction, incremental tests. | graph_indexing_enabled=false | Index writes occur only through the governed real executor; broader graph extensions require explicit opt-in and tests. |
| Semantic/vector writes and embeddings | Real bounded semantic memory, local vector embedding/search, and provider embedding executors exist; broader external/learned-memory extensions remain deferred. | Memory specs | implemented_policy_gated (bounded); extensions deferred | RAIKER-9002 | Vector store policy, retention, embedding-provider tests. | semantic_memory_writes_enabled=false, vector_writes_enabled=false, embedding_creation_enabled=false | Embedding/vector operations occur only through the governed real executors; broader memory extensions require policy and storage gates. |
| External transports and notifications | One reference webhook transport and metadata-only relay exist; additional transports/notifications remain deferred. | Channels specs | implemented_policy_gated (reference); extensions deferred | RAIKER-8704 | Connector auth, outbound allowlist, redacted event tests. | external_channels_enabled=false, notifications_enabled=false | Outbound messages require explicit connector pairing and owner egress allowlist. |
| Remote/container/cloud execution | Local container executor exists; remote/cloud command execution remains no-executor/fail-closed. | Runtime orchestration | container implemented_policy_gated; remote/cloud deferred | RAIKER-8705 | Isolation, secrets, artifact storage, egress tests. | remote_execution_enabled=false, container_execution_enabled=false, cloud_execution_enabled=false | Remote execution impossible until policies pass. |
| Approval execution and relay runtime | Approval resolution remains metadata-only; separate approval execution relay exists for governed approved file-write proposals. | Approval specs | metadata_only + implemented_policy_gated relay | RAIKER-8706 | Human binding, replay protection, audit events, rollback tests. | approval_execution_enabled=false, approval_relay_runtime_enabled=false | Approval actions remain metadata-only until safe execution exists. |
| Scheduled automations/hosted routines | Local on-demand scheduled routines executor exists; hosted/background scheduler remains deferred. | Runtime specs | implemented_policy_gated local; hosted deferred | RAIKER-8707 | Scheduler storage, owner consent, budget/egress tests. | runtime_execution_enabled=false | No background hosted routines before explicit enablement. |
| Deferred filesystem/code tools delete/copy/move, PowerShell/Python execution, web search/fetch, LSP | Not implemented as executable tools. | Tool catalog | specified_not_implemented | RAIKER-8708 | ToolBroker policy, previews, approvals, sandbox tests. | process_execution_enabled=false, shell_execution_enabled=false, network_execution_enabled=false | Tools appear only as disabled/deferred until tests and approvals exist. |
| `/sessions` command | No safe session-listing slash command is currently dispatched. | Command catalog | missing_deferred | RAIKER-8709 | Read-only session query, redacted output, command/help tests. | runtime_execution_enabled=false | Either implement read-only listing or keep omitted from help/catalog. |

## Security architecture and deferred-control gaps

### Conversational chat follow-up (2026-07-26)

The normal Chat UI is delivered as a presentation-only transcript; it hides
governance cards and keeps evidence in Sessions/Checkpoints. The open work is
server-backed provider token accounting/cost/quota reporting, safe automatic
compaction at the approved global 90% threshold, session-authorized file
previews, and the conversational task/project workflow. The latter still needs
clarification/ambiguity state, normal completion receipts, and persistent
exactly-once approval resumption. Do not enable or advertise those deferred
behaviours until their storage, authorization, and regression tests exist.

`docs/SECURITY_ARCHITECTURE.md` is the dedicated current security architecture document. The remaining security items below are missing/deferred unless a future implementation task explicitly marks them implemented with code, tests, validation, and documentation.

| Security gap | Current status | Required future work |
|---|---|---|---|
| Runtime Authority strict enforcement | `implemented_policy_gated` with known gaps | Non-allow decisions do not yet block execution in development/safe modes; `/role revoke` does not yet call `_govern_admin_mutation`; capability gate checks per action are not yet enforced. Add strict enforcement tests and wire missing commands through governance. |
| Runtime Authority validator depth | `implemented_verified` for surface-level checks | `validate_runtime_enablement_readiness.py` does not prove no direct mutation bypasses exist; add deep static analysis for ungoverned mutation paths. |
| Formal threat model review per deferred capability | missing/deferred | Run and record a threat-model review before enabling each Phase 8 client, plugin runtime, channel transport, remote execution adapter, shell/process/network tool, graph indexer, semantic/vector writer, subagent/team runtime, approval relay, or scheduler. |
| Authentication/authorization model for future Web/API clients | missing/deferred | Define identities, roles, sessions, tokens/cookies, CSRF/CORS, rate limits, admin boundaries, and API authorization tests before any Web/API server is runtime-enabled. |
| Secure session isolation for future multi-client interfaces | missing/deferred | Bind client identity, session scope, approval authority, event subscriptions, and redaction policy before Desktop/Web/Mobile/IDE/API clients can share sessions. |
| Plugin sandboxing model | **largely implemented** (slices 12-16) | Signatures (HMAC + Ed25519), install/activate governance, revocation off-switch, event logging, and abuse/fail-closed tests exist; plugin code runs as a bounded subprocess or in a no-network container with an owner plugin/image allowlist and per-plugin subpath scope. Remaining: in-process module import isolation, per-plugin network-egress allowlisting for the subprocess runtime, and image build/pull management. |
| Remote execution sandboxing model | missing/deferred | Define container/remote/cloud isolation, secret injection, egress limits, artifact handling, cost/budget policy, cancellation, and audit records before remote execution is enabled. |
| Secret storage and redaction design | missing/deferred | Add API-key/connector-token storage, rotation, masking, export redaction, provider prompt redaction, and regression tests before broader hosted/external integrations. |
| Log integrity/tamper evidence | missing/deferred | Add hash chaining, verification/export semantics, retention policy, and tamper-evidence tests if Raiker needs stronger audit guarantees than local append-style logs. |
| Provider data-leakage controls | missing/deferred | Add endpoint allowlists, hosted-provider egress policy, prompt/context redaction, no silent fallback tests, and provider-risk audit events. |
| Enterprise policy profiles | missing/deferred | Define managed policy profiles, policy precedence, import/export, audit evidence, and tests before claiming enterprise enforcement. |
| Security regression tests | missing/deferred | Add suites for prompt injection, tool output injection, malicious tool calls, path escape, approval bypass, provider leakage, plugin abuse, hook abuse, memory poisoning, cross-session leakage, and deferred-gate regressions. |
