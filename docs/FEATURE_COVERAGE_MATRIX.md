# Feature coverage

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

| Area | Status | Notes |
|---|---|---|
| Terminal client and loopback dashboard | implemented_verified | Share the governed backend |
| Model profiles | implemented_policy_gated | Local first; hosted use requires explicit policy |
| Policy, approvals, audit, checkpoints | implemented_verified | Ordinary approval resolution is metadata-only |
| Local runtime executors | implemented_policy_gated | Gate and decision mode checked per action |
| Memory MVP | implemented_verified | Durable mutation remains approval-required |
| Remote/cloud and sensitive domains | disabled_deferred | Fail closed without a real executor |

Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced. The detailed current posture is [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
