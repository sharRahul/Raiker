# Capability Gates

> Core Concepts › Capability Gates. Back to [Core Concepts](core-concepts.md).

Raiker's abilities are enumerated as capabilities, each with a **gate**. Every
gate ships **disabled** and fails closed.

A capability can only execute after its gate is moved to an enabled runtime state
through the governed activation path, which checks:

- the active **runtime mode**,
- a **registered real executor** (a capability with no executor can never be
  enabled — it fails closed rather than fabricating success),
- a recorded **threat-model acknowledgement** for higher-risk capabilities,
- a human **confirmation token**.

Only a human `runtime_gate_manager` can flip a gate, and every transition is
audited. See [Capabilities › Tiers](capabilities-tiers.md) for how capabilities
are grouped by blast radius.
