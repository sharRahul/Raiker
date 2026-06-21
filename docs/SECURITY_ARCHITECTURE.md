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

## Trust Boundaries

All mutable actions must follow:

```text
Gateway -> Runtime -> ToolBroker -> PolicyEngine -> Approval/Event/Checkpoint handling
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
