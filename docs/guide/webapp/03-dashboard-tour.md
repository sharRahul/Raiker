# 3. Dashboard tour

After unlocking you land on the **Workbench**. The left navigation is grouped
into five stable destinations plus utilities, and the context bar at the top
carries the page title, the active-project switcher, a **notification bell**, a
**System** theme indicator, and a red **STOP** switch.

![Dashboard home](../screenshots/working/02-dashboard-home.png)

## The navigation, group by group

### Home

| Item | What it is |
|------|-----------|
| **Workbench** | The default screen. One composer with its own scope (which conversation it continues, which project bounds it, which model will serve it), plus what is waiting on you, what is running, and what you can resume. Starting work here hands the prompt to Chat, which owns the one governed send path. |

### Work — the things you are working on

| Item | What it is |
|------|-----------|
| **Chat** | Start or continue a governed conversation. It stays mounted while you visit other routes, so an unsent draft and a running turn survive navigation. |
| **Search Chat** | Full-text search across your conversation titles and messages. |
| **Tasks** | Create work as a task, a scheduled run, a daily routine, or a background agent. |
| **Projects** | Named scopes for ongoing work. Opening one shows its instructions, sessions, scoped tasks, files, and checkpoints together. |
| **Sessions** | Every conversation with its turns, and links to the approvals, tasks, checkpoints, and audit events behind them. |

### Knowledge — what Raiker has stored

| Item | What it is |
|------|-----------|
| **Memory** | Approved memories the agent may recall, each with provenance, scope, and sensitivity. Pin or forget them. |
| **Brain** | A map of stored runtime records (sessions, tasks, tools, approvals, memory, schedules, backups). |

### Control — where intent becomes governed action

| Item | What it is |
|------|-----------|
| **Approvals** | Actions the agent proposed that need your decision. Critical decisions require a separate, server-enforced step-up. |
| **Permissions** | For every capability, choose Ask / Allow / Auto / Deny, and turn integrated capabilities on or off. Capabilities are what the *agent* may do; Extensions is where *services* are connected. |
| **Models** | Model profiles, roles, fallback order, and provider gates: pick where Raiker "thinks". |
| **Extensions** | One hub with four tabs — Connectors, MCP servers, Plugins, Channels. Each extension reports four separate facts: installed, account connected, enabled for the session, and usable now. Plugins and channels state that they are not available yet. |

### Observe — the operational record

| Item | What it is |
|------|-----------|
| **Observability** | One hub with six tabs. **Overview** answers four questions — is Raiker ready, is anything waiting for me, what changed, can I safely share this — and every card links to the record behind it. The other tabs are the **Audit log**, **Checkpoints** (metadata snapshots taken at safe points, each with a read-only restore preflight), **Diagnostics**, **Work in action**, and **Notification history**. |

### Utilities

| Item | What it is |
|------|-----------|
| **Settings** | Runtime mode, security posture, appearance, per-account preferences. |

> Older links still work. `#/activity`, `#/checkpoints`, `#/diagnostics`, and
> `#/work` open the Observability hub on the matching tab; `#/connections` and
> `#/mcp` open Extensions on theirs. `#/capabilities` still resolves — only the
> label changed to **Permissions**. Tab selection lives in the address bar, so
> any panel is a shareable location.

## Always-present controls

- **STOP switch** (top-right, red): a governed interrupt that halts work at a safe
  boundary.
- **Notification bell**: surfaces runtime notifications.
- **System / theme**: light and dark themes are both supported; the toggle stamps
  the theme on the page.
- **"Local & loopback-only"** footer: a standing reminder that this dashboard
  never leaves your machine.

> ✅ **Verified:** all 17 views render, in both light and dark themes, with **zero
> browser console errors**. Every view opens with an honest **empty state** on a
> fresh workspace ("No sessions yet", "Nothing waiting on you", etc.) rather than
> fake sample data.

Next: [Chat →](04-chat.md)
