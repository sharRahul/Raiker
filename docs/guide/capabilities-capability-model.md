# The Capability Model

> Capabilities › Capability Model. Back to [Capabilities](capabilities.md).

Two states decide what a capability can do:

- **Has a real executor?** Only capabilities in `REAL_EXECUTOR_CAPABILITIES` can
  ever execute. Everything else is absent from the registry and fails closed
  (`activation_blocked:no_executor`) — it can't be flipped on and never fakes
  success.
- **Enabled?** Every gate defaults disabled; enabling is a governed, human-only,
  audited transition.

Once enabled, the [decision mode](core-concepts-decision-modes.md) shapes how
AI-proposed actions are treated. The authoritative per-capability source of truth
is [`RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md).
