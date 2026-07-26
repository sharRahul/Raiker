# Security architecture

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is local-first. It treats model output, workspace content, connector
responses, and external data as untrusted. Every action must pass the policy and
runtime-authority boundary.

## Authority

**Owner bootstrap** creates the persisted **owner principal**. Each request has
an acting principal. AI principals cannot hold human-only roles, including
`runtime_gate_manager`, and cannot activate runtime modes or capability gates.
`RuntimeAuthority` persists and evaluates `runtime_mode_state` and
`capability_gate_state`; owner recovery is explicit, local, and audited.

Approval resolution is metadata-only. The approval execution relay is a distinct,
governed execution path with its own checks; it does not make ordinary approval
resolution execute actions.

## Boundaries

| Boundary | Control |
|---|---|
| Client to gateway | Loopback web API, authentication, principal resolution |
| Model to tools | Schema validation, policy, capability and decision-mode checks |
| Sensitive mutation | Human approval and executor-specific controls |
| Workspace data | Path containment, redaction, and audit metadata |
| External services | Explicit egress and credential policy |

| Capability | Default posture |
|---|---|
| remote execution | disabled/fail-closed |
| cloud execution | disabled/fail-closed |
| finance, medical, pregnancy, CCTV, home security, hardware | disabled/fail-closed |
| plugin runtime slices | governed only when a real, policy-gated executor is available |

Logs are audit records, not tamper-proof evidence. Credentials remain outside
normal logs and must be supplied through explicit local configuration.

finance/investment/medical/pregnancy/CCTV/home-security/hardware domains | disabled/fail-closed

No tamper-proof logging is implemented.
