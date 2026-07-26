# Security and policy

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker defaults to deny or ask. A local owner bootstrap creates the owner
principal; only humans with the required role may make governance changes.

## Security philosophy

- **Local-first:** keep work, state, and model choice under the operator's
  control; external access is explicit rather than assumed.
- **Least authority:** a model proposes work but receives no authority merely by
  proposing it.
- **Human control:** people own role, gate, mode, approval, and recovery
  decisions; AI principals cannot elevate themselves.
- **Fail closed:** unknown, unsupported, remote, or sensitive operations refuse
  to run until their full governance and executor requirements are met.
- **Auditable boundaries:** record safe evidence for governed decisions and
  actions without storing secrets, raw prompts, or private reasoning.
- **Frictionless by default:** safe, local, read-oriented work should be easy;
  friction appears only when an action seeks new authority, wider scope, or
  irreversible impact.
- **Zero trust at authority boundaries:** model output, tools, files,
  connectors, and external responses are untrusted until independently checked.

Policy evaluates the principal, capability, domain, risk, workspace scope,
decision mode, and available executor. Strict non-allow blocking, role revoke
governed, and capability gate per action are enforced. AI principals may propose
work but cannot grant themselves authority. Approval resolution is metadata-only.

Strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

Sensitive and remote capabilities remain fail-closed until a real executor,
explicit gate, policy requirements, and applicable human approval are present.
Operational security boundaries are defined in [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md).
