# Best Practices

> Part of the Raiker documentation set. See also: [Core Concepts](core-concepts.md),
> [Use Raiker](use-raiker.md), [Security Architecture](../SECURITY_ARCHITECTURE.md).

Raiker is safe by default. These practices keep it that way as you grant it more
power.

## Grant the least capability, in the tightest mode

- Enable only the capabilities a task actually needs; leave everything else
  disabled (the default).
- Keep the **decision mode** as tight as the task allows. `ask` (the default) is
  the safe choice; move to `auto` for low-risk, well-scoped capabilities; reserve
  `allow` for capabilities you fully trust, and remember it still can't
  bypass the critical-risk human floor.
- Prefer `deny` to leaving a capability enabled-but-unused.

## Keep humans on the critical path

- `runtime_gate_manager` is human-only for a reason: never wire an automation to
  enable gates or change decision modes.
- Treat threat-model acknowledgements as real decisions — read the
  `docs/threat-models/` doc before enabling a capability, not after.
- Approvals are metadata-only; approving records a decision, it does not execute.
  Review what you approve.

## Constrain egress and inputs

- Off-machine model access, channels, and any network capability are fail-closed
  until you set the relevant **owner egress allowlist**
  (`RAIKER_MODEL_EGRESS_ALLOWLIST`, `RAIKER_CHANNEL_EGRESS_ALLOWLIST`,
  `RAIKER_CONTAINER_IMAGE_ALLOWLIST`, `RAIKER_PLUGIN_RUNTIME_ALLOWLIST`, …). Keep
  them as small as possible; an empty allowlist denies everything.
- Treat model output and inbound channel/plugin content as **untrusted** — it
  can only ever resolve to allowlisted hosts and governed tools.

## Prefer stronger isolation for untrusted code

- For plugin code, prefer `plugin_sandboxed_runtime_cap` (no-network container)
  over the bare-subprocess `plugin_runtime_cap` when you don't fully trust the
  plugin.
- Only allowlist container images and plugin ids you have vetted; require signed
  manifests.

## Keep the audit trail meaningful

- Runtime artifacts are metadata-only by design — do not add code paths that emit
  tool output or secrets into events. The log must stay safe to retain.
- Provider keys and allowlist values are never displayed; keep it that way in any
  new surface.

## Verify before you trust a status

- A capability is not "done" until it is `implemented_verified` with real
  evidence. Run the [local validation gate](../LOCAL_VALIDATION_GATE.md) and the
  full test suite before relying on a change.

## Where to go next

- **[Security Architecture](../SECURITY_ARCHITECTURE.md)** — the deeper posture and
  deferred-control gaps.
- **[Implementation](implementation.md)** — the slice discipline and validation
  gate.

## In this section

- [Grant the Least Capability](best-practices-least-capability.md)
- [Constrain Egress & Inputs](best-practices-egress-and-inputs.md)
- [Isolate Untrusted Code](best-practices-isolating-untrusted-code.md)
