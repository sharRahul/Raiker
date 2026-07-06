# Use Raiker

> Part of the Raiker documentation set. See also: [Getting Started](getting-started.md),
> [Core Concepts](core-concepts.md), [Capabilities](../RUNTIME_EXECUTORS_SPEC.md).

This page is the task-oriented reference for driving Raiker day to day: the
surfaces you interact with, the command surface, and the everyday workflows.

## Surfaces

Two surfaces are launchable today; both route through the same governed backend
and add no authority of their own:

- **Terminal client** — `raiker --prompt "..."`, interactive stdin, or
  `RAIKER_TUI=plain`. The primary way to run governed turns.
- **Local web dashboard** — the `apps/web` Svelte SPA over the `raiker-web`
  loopback API (single-user, `127.0.0.1` only). Read-only governed views plus the
  same governed prompt / turn / approval / runtime-mutation flows as the CLI, with
  a step-up-gated Security Settings panel.

Desktop, mobile, IDE, voice, and browser-extension clients are specified but
deferred.

## Command surface

Runtime governance is driven by slash commands (full list in
[`RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](../RAIKER_TOOL_AND_PLUGIN_CATALOG.md)):

| Command | What it does |
|---|---|
| `/bootstrap-owner` | Create the owner principal (first run) |
| `/runtime-mode status\|activate\|disable` | View or set the runtime mode |
| `/capability-gates` | List all capability gates and their state |
| `/capability-gate <cap>` | Show one capability's gate detail |
| `/capability-gate enable <cap> --state <state> --confirm <token>` | Enable a capability (human gate manager only) |
| `/capability-gate disable <cap>` | Disable a capability |
| `/capability-mode <cap> [ask\|deny\|always_allow\|auto]` | View or set a capability's decision mode |
| `/runtime-readiness` | Summarize runtime mode, owner, gates |
| `/model use --provider <p> --model <m>` | Select the active model backend |
| `/approve`, `/deny` | Resolve an approval (metadata-only; does not itself execute) |

## Everyday workflows

### Enable and use a capability

1. `/runtime-mode activate local_single_user_runtime`
2. For higher-risk capabilities, record the threat-model acknowledgement.
3. `/capability-gate enable <cap> --state enabled_runtime --confirm <token>`
4. Choose how the AI may act: `/capability-mode <cap> ask|auto|always_allow|deny`.
5. Run a prompt; AI-proposed actions are handled per the decision mode.

### Approvals

When a capability is in `ask` mode (the default), an AI-proposed action produces
an approval request instead of executing. A human resolves it with `/approve` or
`/deny`. Resolution is **metadata-only** — it records an immutable decision; it
does not itself run the action.

### Reminders, calendar, and email (local)

The local Tier-6 executors let the agent keep personal data locally with no
external side effects:

- `reminder_runtime` — create/list reminders (no notification is sent).
- `calendar_runtime` — create/list local calendar events (no external sync/invite).
- `email_runtime` — draft/list emails locally; Raiker **never transmits**. A
  `send` marks a draft `queued_for_send` (and, in the default `ask` mode, first
  asks you) so a human sends it from their own client.

### Inspect what happened

Every proposal, decision, approval, and execution is in the append-only event
log; the web dashboard and event queries reconstruct any governed turn. Runtime
artifacts are metadata-only, so the log never leaks tool output or sensitive
content.

## Where to go next

- **[Platform & Integrations](platform-integrations.md)** — models, channels,
  and execution environments.
- **[Capabilities](../RUNTIME_EXECUTORS_SPEC.md)** — the full per-capability catalog.

## In this section

- [Surfaces](use-raiker-surfaces.md)
- [Command Reference](use-raiker-command-reference.md)
- [Approvals](use-raiker-approvals.md)
- [Reminders, Calendar & Email](use-raiker-local-data.md)
