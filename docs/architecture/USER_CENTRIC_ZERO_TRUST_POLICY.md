# User-Centric Zero-Trust Policy

This is Raiker's owner policy. It defines the direction of the product; the
[implementation status](IMPLEMENTATION_STATUS.md) remains the source of truth
for what is available today.

## Principle

Raiker makes safe local work frictionless while keeping the user in control.
It uses zero trust at every authority boundary: never trust an identity, model
output, tool, file, connector, or external response merely because it arrived
through a familiar path; verify it against the applicable policy and scope.

Security is an enabler, not an arbitrary barrier. Routine local, read-oriented
work should stay easy. New authority, wider scope, egress, irreversible work,
or higher risk should receive visible, proportionate verification instead of a
silent bypass.

## Commitments

- Every governed action uses the same path: resolved acting principal,
  capability gate, policy and risk decision, and safe audit evidence. No client,
  model, plugin, or connector has a bypass lane.
- The local owner controls roles, gates, modes, approvals, recovery, and scope.
  AI principals cannot grant, elevate, or retain authority for themselves.
- A recorded approval is never itself the authority to act. Any execution it
  leads to is independently governed and rechecked at the execution boundary —
  gate, decision mode, policy, and posture — and is confined to the narrow set of
  local, reversible, checkpointed capabilities the relay is wired for.
- Evidence is redacted and metadata-oriented; credentials and secret-like
  durable-memory content are denied before persistence.
- Unsupported and sensitive domains remain disabled and fail-closed until a
  real executor and all governance requirements exist. Supported SSH/Daytona
  execution remains unavailable until its owner profile, credential reference,
  policy gate, decision mode, cost ceiling, and explicit approval all permit it.
- Controls should be inspectable, reversible where the underlying operation
  permits it, and least disruptive to ordinary safe work.

See [Security and policy](SECURITY_AND_POLICY.md) for the operating rules,
[Security architecture](SECURITY_ARCHITECTURE.md) for trust boundaries, and
[threat models](../threat-models/) for capability-specific analysis.
