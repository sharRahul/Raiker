# Security architecture

## Signed machine-turn trust boundary

Raiker separates the authenticated human owner from the agentic actor. The
embedded workspace issuer signs a short-lived Ed25519 attestation for each turn;
the broker validates its workspace, owner delegation, session, turn, audience,
lifetime, signature, and active machine principal before policy, credentials,
approvals, hooks, or tools. Executors use the human only as owner scope while
actions and evidence retain the machine actor. Resumes rotate tokens, terminal
turns deactivate principals, and subagents receive signed child identities.
See [the detailed threat model](threat-models/machine-identity.md).

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

Approval resolution executes a narrow allowlist: local file mutations
(`file_write_execution`, `patch_apply_execution`) and governed local commands
(`shell_execution`, `process_execution`), only through the approval execution relay —
a distinct path that re-checks the target's capability gate, decision
mode, policy review, authority id, and selected environment at execution time.
SSH/Daytona profiles are readiness-only and cannot execute. File mutations
additionally capture the pre-image so the change is reversible. For every other capability, approval
resolution remains metadata-only: it records the decision and executes nothing.
Which of the two applies is computed by the server and stated to the owner
before they decide.

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
| SSH remote execution | unavailable until owner profile selection; approval-required |
| Daytona cloud execution | unavailable until owner profile, credential reference, and cost ceiling; approval-required |
| finance, medical, pregnancy, CCTV, home security, hardware | disabled/fail-closed |
| plugin runtime slices | governed only when a real, policy-gated executor is available |

Logs are audit records, not tamper-proof evidence. Credentials remain outside
normal logs and must be supplied through explicit local configuration.

No tamper-proof logging is implemented.
