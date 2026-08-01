# Feature coverage

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

| Area | Status | Notes |
|---|---|---|
| Terminal client and loopback dashboard | implemented_verified | Share the governed backend |
| Model profiles | implemented_policy_gated | Local first; hosted use requires explicit policy |
| Policy, approvals, audit, checkpoints | implemented_verified | Approval resolution executes an approved file mutation (relayed, re-governed, checkpointed); metadata-only otherwise |
| Local runtime executors | implemented_policy_gated | Gate and decision mode checked per action |
| Memory MVP | implemented_verified | Proposal decisions, scope/expiry changes, forget/purge, and owner-scoped history are governed |
| Build workspace (coding surface) | implemented_policy_gated | Composer modes set real decision modes; repository references grant nothing and fail closed |
| Scheduled background agents | implemented_policy_gated | One governed turn per cycle; unknown cadences refused |
| SSH/Daytona execution | implemented_approval_required | Owner profile and env-only credential references; no local-to-remote fallback |
| Sensitive domains | disabled_deferred | Finance, medical, CCTV, hardware, and similar domains fail closed without an executor |

Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced. The detailed current posture is [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
