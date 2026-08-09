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
work but cannot grant themselves authority. Approval resolution executes an
approved local file mutation through the governed execution relay and is
metadata-only for every other capability.

## Per-turn machine identity boundary

Agentic work never enters the broker as the human owner. An embedded workspace
issuer mints a short-lived Ed25519 attestation for each turn and binds it to the
owner delegation, workspace, session, turn, machine principal, and broker
audience. The broker verifies that attestation before policy, credentials,
approvals, hooks, or tools. A resume rotates the token, terminal completion
deactivates it, and a subagent receives a child identity with explicit ancestry.

The verified machine is the action actor; the authenticated human remains the
owner of account-scoped models, connectors, memory, projects, and credentials.
Model-controlled arguments cannot change that owner scope. Machines cannot mint
identities, grant roles, change gates or modes, resolve approvals, satisfy
step-up, or read raw credentials. Approval records preserve the machine proposer
and later human authorizer without persisting the bearer token or signature.
The public key/token IDs and issue/expiry timestamps are snapshotted on the
proposed action, so a resume rotation cannot rewrite approval history. Runtime
execution always receives the machine principal; owner resolution is limited to
resource and control lookup. Activity reports the event emitter separately from
the turn identity, preventing human authorization or runtime events from being
presented as if the agent emitted them.
See [the machine-identity threat model](threat-models/machine-identity.md).

Strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

Sensitive and remote capabilities remain fail-closed until a real executor,
explicit gate, policy requirements, and applicable human approval are present.
Operational security boundaries are defined in [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md).

## Container tool boundary

Container profiles do not grant tools or bypass the broker. Policy, decision
mode, and any approval are resolved first; only then may a statically registered
safe tool be routed to the selected profile. The operator separately allowlists
images through `RAIKER_CONTAINER_IMAGE_ALLOWLIST`; the account separately enables
`container_execution_cap`; and the profile separately assigns tools. All three
must agree.

Docker and Podman runs use no network, a read-only root filesystem, dropped Linux
capabilities, `no-new-privileges`, bounded CPU/memory/PIDs/time/output, a
read-only `/repository` bind, and one action-scoped writable
`/workspace-output`. Requests and responses are bounded JSON over attached stdin
and stdout. The bridge contains no dynamic import, shell, connector, credential,
or arbitrary-command dispatch. Missing runtimes, disallowed images, unsupported
tools, malformed responses, and cleanup failures are explicit and never cause a
host fallback.


## Model supply and readiness controls

Readiness fails closed and is exact-model scoped. Hosted checks make a bounded
one-token request only after explicit owner setup; errors are classified without
returning provider bodies or credentials. Local discovery has no ambient disk
search: the owner approves each absolute root, scans are bounded, and symlink
escapes are ignored. Hub downloads use immutable revisions, expose licence and
gating before confirmation, never place tokens on argv or in returned URLs, and
write collision-safe snapshots. Conversion accepts Safetensors only and runs
without network in a digest-pinned container with read-only source, separate
output, dropped privileges and resource limits.
