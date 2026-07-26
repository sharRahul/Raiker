# Raiker Web App — End-to-End User Guide

> A hands-on, click-by-click walkthrough of the **Raiker local web dashboard**
> (`raiker-web`). It was written *by using the app* — every step below was
> performed against a freshly built dashboard, and the screenshots are real
> captures from that run. Where something did **not** work, it is called out and
> tracked in [`../TO_BE_FIXED.md`](../TO_BE_FIXED.md).

Raiker is a **governed AI agent runtime**. The dashboard is one of two launchable
surfaces (the other is the `raiker` terminal client). It talks only to the local
governed API on `127.0.0.1` — it adds no authority of its own, so every read and
every change goes through the same policy, approval, and audit path as the CLI.

## Who this guide is for

A person sitting down at their own machine who wants to **use Raiker through the
browser**: unlock the workspace, chat, create tasks, connect a model, wire up
connectors/MCP, and understand the governance controls.

## The map

| # | Page | What you'll do |
|---|------|----------------|
| 1 | [Install & launch](01-install-and-launch.md) | Build the SPA and start `raiker-web` |
| 2 | [Create your account & unlock](02-account-and-login.md) | First-run registration, login, MFA, recovery |
| 3 | [Dashboard tour](03-dashboard-tour.md) | The Workbench and every destination in the left navigation |
| 4 | [Chat: your first governed turn](04-chat.md) | Send a prompt, read the governance trail, find it later |
| 5 | [Tasks](05-tasks.md) | The four kinds of work: task, scheduled, routine, background agent |
| 6 | [Models & providers](06-models-and-providers.md) | Local runtimes, hosted providers, the fallback sequence |
| 7 | [Capabilities & approvals](07-capabilities-and-approvals.md) | Decision modes, turning capabilities on, the approval queue |
| 8 | [Extensions: connectors & MCP](08-connections-and-mcp.md) | The Extensions hub: readiness, the Connector Store, MCP servers, and what is not available yet |
| 9 | [Security, vault & settings](09-security-vault-and-settings.md) | Vault key, MFA, runtime mode, appearance |
| 10 | [Sessions, search & observability](10-sessions-audit-diagnostics.md) | Where your history and the runtime's honesty live |

## The one thing to understand first: *fail-closed*

Raiker's core rule is **no privileged interface and no silent runtime**. A
capability only works once its policy, storage, audit, and executor are all in
place, and even then an AI-proposed action defaults to **ask** (it pauses for
your decision). Anything not fully integrated stays **disabled** and fails
closed with an honest error — it never guesses or fabricates. So throughout this
guide you will see the app *refuse* to do things until you explicitly grant them.
That is the product working as designed, not a failure.

## Screenshots

- Things that work as documented: [`../screenshots/working/`](../screenshots/working/)
- Things that are broken or confusing: [`../screenshots/not-working/`](../screenshots/not-working/)

## Reference environment

The run behind this guide used:

- Python 3.11, Node 22, a fresh workspace, dashboard on `http://127.0.0.1:8765`.
- Test account `rahul`, runtime mode **Development preview**.
- A hosted Anthropic API key (to exercise the Models connect flow).
