# Capability Tiers

> Capabilities › Tiers. Back to [Capabilities](capabilities.md).

Capabilities are grouped by blast radius:

| Tier | Scope | Real executors today |
|---|---|---|
| **1** | Local, reversible | file write, patch apply, approval relay, memory write/forget |
| **2** | Sandboxed / allowlisted egress | shell, process, web fetch, network |
| **3** | Local code intelligence | graph indexing, semantic memory |
| **4** | Plugins | install, brokered read-only, revocation, subprocess + no-network container runtime |
| **5** | Channels, containers, models | reference channel, container execution, scheduled routines, hosted/private model runtime |
| **6** | Sensitive real-world domains | local-only: reminders, calendar, email drafts |

Tier-6's sensitive domains (finance, medical, cctv, home security, hardware, …)
have **no executor** and stay fail-closed until each has a real integration and
its own threat model. See [What Is Not Available](capabilities-deferred.md).
