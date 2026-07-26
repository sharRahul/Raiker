# Raiker user guide

Task-shaped instructions for running Raiker's local web dashboard. Everything
here was executed against a live instance on 2026-07-26 — see
[the live manual test plan](../plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md) for the
evidence and [To be fixed](../plans/TO_BE_FIXED.md) for what does not work yet.

| Guide | Read it when |
|---|---|
| [Getting started](getting-started.md) | First install, first run, creating your account |
| [Connecting a model](connecting-a-model.md) | You want Raiker to think — local, home-lab, or hosted |
| [Permissions and runtime modes](permissions-and-runtime-modes.md) | Something is refused and you need to know which control opens it |
| [Working in Chat](working-in-chat.md) | Day-to-day conversations, attachments, approvals |
| [Tasks and projects](tasks-and-projects.md) | Scheduling work and organising sessions |
| [Extensions and MCP](extensions-and-mcp.md) | Connectors and Model Context Protocol servers |
| [Troubleshooting](troubleshooting.md) | You hit a reason code and want the fix |

For architecture, contracts, and the security model, start at
[the documentation index](../README.md).

## The one thing to understand first

Raiker **fails closed**. On a fresh account every one of its 62 capability
gates is off, no model provider is reachable, and no credential can be stored.
Nothing is broken — you have not opened anything yet. Work in this order and
each surface unlocks cleanly:

1. **Runtime mode** — Settings → General
2. **Vault key** — Settings → Security & Login
3. **Capability gates** — Permissions
4. **Model connection** — Models

[Connecting a model](connecting-a-model.md) walks all four in ten minutes.
