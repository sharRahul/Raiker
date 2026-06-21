# Security Architecture

Current launchable interface is the plain local terminal client only. Rich/native TUI, desktop, web, dashboard, mobile, IDE, voice, browser extension, and REST/API clients are Phase 8 deferred, specified/deferred, not active runtime.

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
| Plugin execution | `disabled_deferred` | Planning/readiness only. |
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
