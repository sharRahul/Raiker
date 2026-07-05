> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

# Security Architecture

The launchable local interfaces are the plain local terminal client and the local web dashboard
(`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only). The web
dashboard adds no authority of its own: every read and mutation routes through the same Agent
Gateway, RuntimeAuthority, PolicyEngine, ToolBroker, approval, and event-logging path as the CLI,
and approval resolution is metadata-only. Rich/native TUI, desktop, mobile, IDE, voice, browser
extension, and hosted/multi-user REST/API clients are Phase 8 deferred, specified/deferred, not
active runtime.

### Local web dashboard trust boundary

- The API server binds to loopback (`127.0.0.1`) only and is single-user; it must not be exposed on
  a public interface. The SPA obtains a bearer token from `POST /api/auth/session` for the local
  owner principal and holds it **in memory only** (never `localStorage`/`sessionStorage`).
- Session minting is human-only: AI principals cannot mint a session, interrupt tasks, or mutate
  runtime gates (`human_principal_required` / authority denials still fire via the API).
- Responses pass through the redaction middleware before leaving the server; secret-like strings are
  redacted from API responses, event logs, and approval previews. There is no secret/credential
  store — secret storage is not implemented (deferred).
- Runtime mutations from the dashboard go through a step-up window that only *collects and forwards*
  the backend-required `reason` / confirmation token / threat-model acknowledgement; it grants
  nothing `RuntimeAuthority` would not already require.

## Local single-user production readiness

The local single-user runtime is production-ready because privileged local actions require persisted human authority and RuntimeAuthority enforcement.

### Owner bootstrap trust boundary

- First-run owner bootstrap creates a persisted owner principal, user, and role in the SQLite store.
- The owner principal is persisted in the `principals` table with role `rl_owner`, `rl_admin`, `rl_rgm`, `rl_approver`.
- The `runtime_gate_manager` role (`rl_rgm`) is created during bootstrap as a system role.
- All production-path CLI commands use `resolve_local_principal()` to resolve the acting principal, which validates principal existence, active status, and human-only role requirements.
- AI principals are denied at the authority level from activating runtime modes or changing capability gate state.
- Runtime mode state is persisted in the `runtime_mode_state` table.
- Capability gate state is persisted in the `capability_gate_state` table.
- Recovery/break-glass flow (`--force-recover`) is supported and audited via events.
- All privileged mutations generate audit events (owner_bootstrap_created, runtime_mode_activated, capability_gate_enabled, etc.).

### Deferred execution domains

The following remain disabled/deferred and are not covered by the local production readiness declaration:
- Approval execution relay
- Shell/process execution
- Network/web fetch
- Plugin execution
- Graph/codemap runtime indexing
- Semantic/vector writes
- External channels
- Remote/container/cloud execution
- Hosted routines/schedulers
- Desktop/web/mobile/dashboard/ide/api runtime clients

---

## Backend Posture

| Area | Current status | Notes |
|---|---|---|
| Gateway, runtime, policy, broker, approvals, checkpoints | `implemented_read_only` / `implemented_policy_gated` | Every runtime action stays on the governed backend path. |
| File reads, git reads, workspace inspection | `implemented_read_only` | Workspace-confined and policy-reviewed. |
| File mutation proposals | `implemented_approval_required` | Approval creates metadata only; no approval execution relay. |
| Durable memory CLI mutation | `implemented_approval_required` | `/memory-store` and `/memory-forget` are brokered approval requests only by default. |
| Durable memory governed write contract | `implemented_policy_gated` | Available only through the broker-governed path with provenance, retention, approval state, and event logging. |
| Approval resolution | `metadata_only` | `/approve` and `/deny` resolve one immutable approval record; they do not execute actions. |
| Semantic/vector writes, embeddings, graph indexing | `disabled_deferred` | Readiness/preview only; runtime execution disabled. |
| Plugin execution | `implemented_policy_gated` | Real governed executors exist — install, brokered read-only, revocation, and code runtime (bounded subprocess + no-network container); gates default-disabled. See `docs/RUNTIME_EXECUTORS_SPEC.md`. |
| External channels | `disabled_deferred` | Metadata/readiness only; no relay/runtime transport. |
| Remote/container/cloud execution | `disabled_deferred` | Profiles and readiness records may exist; execution remains off. |
| Hosted providers | `implemented_policy_gated` | Explicit policy, API key, and egress/budget controls required. |
| Deterministic/mock providers | `test_only` | Never a silent production fallback. |

## Runtime Authority / Governed Action Path

All actions (CLI, future UI, automation, plugin, model tool call, channel, background task) must pass through a single governed path:

```text
Client / CLI / Future UI / Automation / Agent
→ Gateway
→ Runtime Authority / Action Router
→ Capability Gate
→ PolicyEngine
→ Risk Classifier
→ Approval / Risk Acceptance where required
→ ToolBroker or Governed Service Executor
→ EventLog + SQLite
→ Checkpoint where needed
→ Response / Report
```

The `RuntimeAuthority` (`raiker/runtime/authority/router.py`) is the central governance point. It enforces:
- Principal active/expired status
- Domain scope boundaries
- AI role restrictions (no self-approval, no self-grant, no gate enablement)
- Human-only role protections
- Risk level escalation (critical requires human confirmation)
- Risk acceptance validation

The `ActionRouter` provides a unified `route()` method that creates `GovernedAction` records and routes them through the full authority chain.

## AI-Executable Roles

Four AI roles are defined:

| Role | Auto-allowed | Requires approval/risk acceptance | Denied |
|------|-------------|-----------------------------------|--------|
| **assistant** | read, search, summarise, draft, plan, recommend, prepare actions, create reports, reminders | send email, delete email, move money, buy/sell stock, share records, medical decisions, grant permissions, enable runtime gates | - |
| **automation** | scheduled summaries, recurring reports, alerts, reminders, monitoring | Must be scoped by task; cannot self-expand scope | buy/sell stock, move money, change portfolio settings |
| **operator** | check runtime status, check backups, diagnostics, maintenance recommendations | delete backups, change CCTV settings, disable monitoring, restart service | enable runtime gates, change security policy, remote execution, delete CCTV footage |
| **developer** | read workspace, inspect git diff, review findings, plans, proposals | write_file, edit_file, apply_patch, run tests, shell commands, memory mutations | approve own action, merge PR, change policy, grant roles, enable runtime gates, install/execute plugins |

## Human-Only Roles

The following roles are reserved for humans and cannot be assigned to AI principals:
`owner`, `admin`, `approver`, `security_admin`, `finance_approver`, `medical_decision_maker`, `runtime_gate_manager`

## Domain Scopes

Actions are scoped to domains: `email`, `calendar`, `reminders`, `documents`, `finance`, `investments`, `medical`, `pregnancy_baby`, `home_security`, `cctv`, `hardware`, `systems`, `projects`, `coding`, `shopping`, `travel`.

A principal's effective permissions are the intersection of their role permissions, domain scopes, workspace policy, capability gate state, task scope, and risk acceptance/approval state.

## Risk Levels

| Level | Behavior |
|-------|----------|
| Low | Auto-allowed for permitted roles |
| Medium | Auto-allowed if pre-approved rule exists |
| High | Requires approval or risk acceptance |
| Critical | Always requires human confirmation |

## Risk Acceptance

Users can explicitly accept risk. A risk acceptance record captures: `risk_acceptance_id`, `accepted_by`, `accepted_for_principal_id`, `action_id`, `action_type`, `domain_scope`, `risk_level`, `risk_summary`, `data_involved`, `expected_effect`, `one_time_or_reusable`, `expires_at`.

Risk acceptance cannot be used by AI to approve its own actions, and critical-risk actions always require human confirmation regardless of risk acceptance state.

## Effective Permission Calculation

```
effective_permissions =
  delegating_human_permissions
  ∩ ai_role_permissions
  ∩ domain_scope_permissions
  ∩ workspace_policy
  ∩ capability_gate_state
  ∩ task_scope
  ∩ risk_acceptance_or_approval_state
```

## Trust Boundaries

All mutable actions must follow:

```text
Gateway -> Runtime Authority -> ToolBroker -> PolicyEngine -> Approval/Event/Checkpoint handling
```

Model output is always untrusted. No tool, plugin, channel, subagent, remote, memory, or approval path is allowed to execute outside that authority chain.

## Guarantees

- Deny-by-default policy for unknown tools/actions.
- Workspace path confinement for read tools.
- Secret/credential-like durable memory content is denied before approval creation.
- Approval records are bound to action ID and stored payload hash; tampered pending approval payloads fail closed.
- JSONL event log plus SQLite event index remain local-first and append-only in style.
- Approval resolution is metadata-only and does not execute actions.
- Checkpoint creation and turn closure are gateway finalisation events.
- Hosted providers require explicit policy; there is no silent local-to-hosted fallback.

## Non-Guarantees

- No cryptographic immutability or non-repudiation is implemented.
- No tamper-proof logging is implemented.
- No approval execution relay is implemented.
- No plugin runtime, channel runtime, remote execution runtime, graph runtime indexing, semantic/vector write runtime, or UI/API client runtime is enabled.
- No provider health-checked default selection is implemented; the current default is a static local-first profile choice.

## Runtime Mode and Capability Gate Activation

Runtime mode and capability gate activation is governed by `RuntimeAuthority`. Only the human `runtime_gate_manager` role can activate `local_single_user_runtime` or enable `admin_mutation`/`role_mutation` capability gates. AI principals cannot activate runtime modes or capability gates. Activation events are audited via the event log. Runtime mode state is persisted in the `runtime_mode_state` table; capability gate state is persisted in the `capability_gate_state` table. All 47 capabilities remain default-disabled.

## Disabled Capabilities

- shell/process execution | disabled/deferred
- network/web fetch | disabled/deferred
- plugin execution | disabled/deferred
- graph runtime indexing | disabled/deferred
- semantic/vector writes | disabled/deferred
- approval execution relay | disabled/deferred
- external channels | disabled/deferred
- remote/container/cloud execution | disabled/deferred
- hosted routines/schedulers | disabled/deferred
- desktop/web/mobile/dashboard/ide/api runtime clients | disabled/deferred
