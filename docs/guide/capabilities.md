# Capabilities

> Part of the Raiker documentation set. See also: [Core Concepts](core-concepts.md),
> [Platform & Integrations](platform-integrations.md),
> [Implementation](../IMPLEMENTATION_STATUS.md).

A **capability** is a named thing Raiker can do. Every capability has a gate that
ships **disabled** and fails closed; a capability only performs real work if it
has a registered executor *and* its owner has governed it into an enabled state.
The authoritative, per-capability source of truth is
[`RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) — this page is the map.

## Two states that matter

- **Has a real executor?** Only capabilities in `REAL_EXECUTOR_CAPABILITIES` can
  ever execute. Everything else is absent from the registry and fails closed
  (`activation_blocked:no_executor` / `execution_unavailable:no_executor`) — it
  can't be flipped into a working state, and it never fabricates success.
- **Enabled?** Every gate defaults disabled. Enabling is a governed, human-only,
  audited transition (runtime mode + registered executor + threat-model ack for
  higher-risk caps + confirmation token). See [Core Concepts](core-concepts.md).

Once enabled, a capability's **decision mode** (`ask` / `deny` / `allow` /
`auto`) shapes how AI-proposed actions on it are treated — see
[Decision Modes](../DECISION_MODES_SPEC.md).

## Capability tiers

Capabilities are grouped by blast radius:

| Tier | Scope | Examples (real executors today) |
|---|---|---|
| **1** | Local, reversible | file write, patch apply, approval relay, memory write/forget |
| **2** | Sandboxed execution / allowlisted egress | shell, process, web fetch, network |
| **3** | Local code intelligence | graph indexing, semantic memory |
| **4** | Plugins | install, brokered read-only exec, revocation, subprocess runtime, no-network container runtime |
| **5** | Channels, containers, models | reference channel, container execution, scheduled routines, hosted/private model runtime |
| **6** | Sensitive real-world domains | **local-only**: reminders, calendar, email drafts |

Tier-6's sensitive domains (finance, investment, medical, pregnancy/baby, cctv,
home security, hardware) intentionally **have no executor** and stay fail-closed
until each has a real external integration plus its own threat model. The
reminder / calendar / email executors are promoted only because they are purely
local (no network, no external delivery — email never sends).

## Plugins

Installed plugins are a capability family of their own: signed manifests (HMAC +
Ed25519), dependency controls, brokered read-only tool access, a bounded
subprocess runtime, and a fully network-isolated container runtime — all gated on
an owner plugin allowlist. See [`PLUGIN_SYSTEM_SPEC.md`](../PLUGIN_SYSTEM_SPEC.md)
and [`RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](../RAIKER_TOOL_AND_PLUGIN_CATALOG.md).

## What is NOT available

Remote/cloud command execution, embeddings/model-provider runtime, several
code-intelligence writers, and all sensitive Tier-6 domains remain fail-closed.
[`GAP_AND_TODO_ANALYSIS.md`](../GAP_AND_TODO_ANALYSIS.md) tracks these gaps and
[`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md) is the build ledger.

## Where to go next

- **[Runtime Executors Spec](../RUNTIME_EXECUTORS_SPEC.md)** — the per-capability
  catalog (source of truth).
- **[Implementation](../IMPLEMENTATION_STATUS.md)** — what is built, verified, or
  deferred.

## In this section

- [The Capability Model](capabilities-capability-model.md)
- [Capability Tiers](capabilities-tiers.md)
- [What Is Not Available](capabilities-deferred.md)
