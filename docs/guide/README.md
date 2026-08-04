# Raiker user guide

Task-shaped instructions for running Raiker's local web dashboard. Everything
here was executed against a live instance on 2026-08-04 — see
[the live manual test plan](../plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md) for the
evidence and [To be fixed](../plans/TO_BE_FIXED.md) for what does not work yet.

| Guide | Read it when |
|---|---|
| [Getting started](getting-started.md) | First install, first run, creating your account |
| [Connecting a model](connecting-a-model.md) | You want Raiker to think — local, home-lab, or hosted |
| [Permissions and the runtime](permissions-and-runtime-modes.md) | Something is refused and you need to know which control opens it |
| [Working in Chat](working-in-chat.md) | Day-to-day conversations, attachments, approvals |
| [Tasks and projects](tasks-and-projects.md) | Scheduling work and organising sessions |
| [Extensions and MCP](extensions-and-mcp.md) | Connectors and Model Context Protocol servers |
| [Troubleshooting](troubleshooting.md) | You hit a reason code and want the fix |

For architecture, contracts, and the security model, start at
[the documentation index](../README.md).

## The one thing to understand first

Raiker **fails closed**. On a fresh account every one of its 62 capability
gates is off and no model provider is reachable. Nothing is broken — you have
not opened anything yet.

**Configuring something is permission for it.** Connecting a provider in
**Models** is the whole of the first step: that act authorises the endpoint you
configured, the encryption key for your credential is created on first use, and
the runtime is already accepting work on a fresh install. You are not asked to
flip a switch, allowlist a host, and mint a key before the thing you just set up
will run.

1. **Model connection** — Models → the provider's card → **Connect**
2. **Capability gates** — Permissions, when you want the agent to do something
   beyond reading and answering (write a file, run a command, read the web)

[Connecting a model](connecting-a-model.md) walks the first in ten minutes;
[Permissions and the runtime](permissions-and-runtime-modes.md) covers the
second.
