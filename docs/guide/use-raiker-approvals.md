# Approvals

> Use Raiker › Approvals. Back to [Use Raiker](use-raiker.md).

When a capability is in `ask` mode (the default), an AI-proposed action produces
an **approval request** instead of executing. A human resolves it with `/approve`
or `/deny`.

Resolution is **metadata-only** — it records an immutable decision; it does not
itself run the action. An AI principal can never approve its own action. Review
what you approve: approving is how an AI-proposed action becomes permitted to run.
