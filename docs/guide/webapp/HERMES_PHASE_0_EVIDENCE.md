# Hermes-informed web experience — Phase 0 evidence

> **Audit date:** 2026-07-22  
> **Status:** Phase 0 implementation evidence complete; the required live-browser
> journey recording is blocked by the environment (no installed browser; the
> Playwright Chromium download is forbidden with HTTP 403). This document must be
> updated with timings, misclicks, and screenshots before Phase 1 is declared
> complete.

This is a source-of-truth audit of the launchable local Svelte dashboard. It is
deliberately descriptive: no item in this document grants a browser capability or
changes server authority.

## Inventory method

The inventory was produced by reviewing every App route and every `api.*` use in
`apps/web/src`, then reconciling the methods with the typed endpoint definitions
in `apps/web/src/lib/api.ts`. Repeat it after each route/API change:

```bash
rg -o 'api\.[A-Za-z0-9_]+' apps/web/src --glob '*.{svelte,ts}' | sed 's/.*api\.//' | sort -u
rg -n '"/api/' apps/web/src/lib/api.ts
```

The applicable capability labels are derived from the server-provided
`CapabilityGate` contract. The browser maps them through `capabilityLabel`,
`isDeferred`, and decision-mode copy; it never derives gate state or readiness.

## Route and state inventory

| Route | Surface | Server reads | Mutations initiated by UI | Intentional states |
|---|---|---|---|---|
| `#/home` | Workbench | sessions, tasks, pending approvals | none | loading, unavailable, empty resume list |
| `#/new-chat?session=` | Chat | sessions/models/turn data | prompt stream, attachment upload, interrupt | draft, streaming phase rail, approval wait, completed, failed |
| `#/search-chat` | Search chat | chat search | none | idle, loading, no match, error |
| `#/tasks` | Tasks/routines | tasks | create task, safe-boundary interrupt | loading, error, no work, saving/stopping |
| `#/projects` | Projects | projects, project/context/tree | create/edit/archive/move/export/select | loading, error, empty, confirmation/busy |
| `#/sessions` | Sessions | sessions, session, turn | rename/pin/tag/move/archive/delete/bulk delete | loading, error, empty, selection/busy |
| `#/memory` | Memory | memories/settings | edit/pin/search/expiry/incognito/import/export/forget | loading, error, empty, saving |
| `#/brain` | Brain | brain | add/remove source | loading, error, empty, busy |
| `#/checkpoints?session=` | Checkpoints | checkpoints | existing governed checkpoint actions only | loading, error, empty, busy |
| `#/approvals` | Approvals | approval list/detail | resolve approval | loading, error, empty, review/busy/notice |
| `#/capabilities` | Capabilities | gates/runtime | gate/mode/ack mutations | loading, error, deferred, step-up/busy |
| `#/models` | Models | models/provider models | select/connect/advisor/fallback | loading, error, empty, connect/busy |
| `#/connections` | Extensions (connectors) | connector store | install/auth/enable/credentials/remove | loading, error, empty, selected/busy |
| `#/mcp` | MCP servers | servers/sessions/findings | create/connect/rename/pause/resume/delete | loading, error, empty, selected/busy |
| `#/activity?session=` | Audit log | events | none | loading, error, empty, filters |
| `#/diagnostics` | Diagnostics | diagnostics/security health | scan/check security | loading, error, empty, checking |
| `#/work` | Work in Action | task/activity records | existing task controls only | loading, error, empty, filtered |
| `#/settings` | Settings | settings/security/vault/grants | preference, vault, security, grant, account mutations | loading, error, saving, step-up |

Authentication is a separate lock/bootstrap state machine: `locked`,
`verifying`, `ready`, and `verification_failed`. The workspace shell mounts only
after the server-backed bootstrap reads succeed.

## API and mutation boundary

All API calls are typed in `apps/web/src/lib/api.ts`; authenticated requests go
to loopback `/api/*`. Read APIs include settings, runtime, diagnostics, models,
projects, sessions, turns, tasks, approvals, events, memory, brain, checkpoints,
connector/MCP status, notifications, and security health. UI mutations are
limited to the existing server endpoints for authentication, settings, vault and
security controls, governed capability/runtime changes, model selection, chat
and attachments, project/session/task organisation, approval resolution,
memory, connector/MCP lifecycle, and security scans.

The UI has no policy decision endpoint. In particular, capability and runtime
changes, prompt execution, connector lifecycle, and approval resolution are
server-validated; no browser token or secret is persisted by this contract.

## Route query-state and UI-event schema

Only non-secret URL state is accepted:

| Key | Route | Type/meaning | Invalid behavior |
|---|---|---|---|
| path | all | one identifier in `NAV_ITEMS` | falls back to `#/home` |
| `session` | `#/new-chat`, `#/activity`, `#/checkpoints` | opaque session ID for a resumed conversation or scoped audit/checkpoint view | Chat receives no selected session if absent/invalid; Audit and Checkpoints remain unscoped |

Current internal UI events are deliberately narrow and are not telemetry:

| Event | Producer | Consumer | Payload | Meaning |
|---|---|---|---|---|
| `hashchange` | browser navigation | `App.svelte` | browser hash | restores route and moves focus to `main` |
| `raiker:chats-changed` | Chat, Projects, Sidebar | Sidebar | none | refreshes recent-session list |
| `raiker:projects-changed` | project UI | Sidebar | none | refreshes project list |

New event names must be namespaced `raiker:`, carry no secret or prompt content,
and document producer, consumer, payload, and idempotency in this table.

## Missing read models and intentionally deferred surfaces

The following plan requirements do **not** have an adequate server-backed summary
contract and must not be simulated in the client: a combined project work/file
overview with provenance, checkpoint restore preflight/rollback impact, immutable
approval expiry/priority triage summary, extension lifecycle/readiness aggregate,
and a consolidated observability/correlation/support-bundle model. Channels,
webhooks, arbitrary plugin routes, raw secret editing, backup/restore, and
automation delivery targets remain deferred.

## Representative-journey baseline

| Journey | Repeatable automation evidence | Live-browser result | Required next evidence |
|---|---|---|---|
| First unlock and first prompt | `LoginView`, `ChatView`, and `App` component tests | blocked | time to unlock/prompt completion, misclick count, screenshot |
| Resume and search work | `SessionsView` and `SearchChatView` component tests | blocked | restoration/search timing and selected-session confirmation |
| Approval and critical step-up | `ApprovalsView`, `CapabilitiesView`, and `StepUpDialog` component tests | blocked | exact approval ID, expiry/step-up outcome, timing |
| Hosted-model selection | `ModelsView` component tests | blocked | egress acknowledgement and fallback outcome |
| Extension connect/diagnose | `ConnectionsView`, `McpView`, and `DiagnosticsView` component tests | blocked | lifecycle/health outcome and remediation copy |

The browser limitation is an environment limitation, not passing evidence. The
Phase 0 documentation will be behind implementation if a new route, endpoint,
event, or capability label is added without updating this inventory.
