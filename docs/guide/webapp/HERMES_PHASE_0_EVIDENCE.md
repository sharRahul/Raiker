# Hermes-informed web experience — Phase 0 evidence

> **Audit date:** 2026-07-23
> **Status:** Phase 0 complete. The five representative journeys were run in a
> disposable local workspace against the built SPA and a loopback `raiker-web`
> server. Their timings, outcomes, and copy observations are recorded below.

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
| `#/connections` | Extensions (connectors) | connector store | install/auth/enable/credentials/remove; create/test an MCP profile | loading, error, empty, selected/busy |
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

Only non-secret fragment state is accepted:

| Key | Route | Type/meaning | Invalid behavior |
|---|---|---|---|
| fragment path | all | one identifier in `NAV_ITEMS` | falls back to `#/home` |
| `project` | all | opaque project selection ID | parsed as `null` when empty/oversized; current shell selection remains server-backed |
| `session` | `#/new-chat`, `#/activity`, `#/checkpoints` | opaque session ID for a resumed conversation or scoped audit/checkpoint view | parsed as `null` when empty/oversized; Chat receives no selected session and Audit/Checkpoints remain unscoped |
| `record` | all | opaque selected-record ID reserved for route consumers | parsed as `null` when empty/oversized |
| `filter` | all | non-secret filter token reserved for route consumers | parsed as `null` when empty/oversized |
| `tab` | all | non-secret selected-tab token reserved for route consumers | parsed as `null` when empty/oversized |

Current internal UI events are deliberately narrow and are not telemetry:

| Event | Producer | Consumer | Payload | Meaning |
|---|---|---|---|---|
| `hashchange` | browser navigation | `App.svelte` | browser hash | restores route and moves focus to `main` |
| `raiker:chats-changed` | Chat, Projects, Sidebar | Sidebar | none | refreshes recent-session list |

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

The browser pass used `npm.cmd run build` and
`python -m apps.api.main --workspace .raiker-e2e --host 127.0.0.1 --port 8765
--no-browser`. It used a fresh local account and deleted the entire workspace
after verification. Timings are action-to-observed-state measurements from the
local browser runner, not a population usability study. There were zero product
misclicks in all five journeys; one automation locator ambiguity was corrected
before interaction and is not counted as a user misclick. Full-page visual
snapshots were reviewed in the local browser and deliberately not retained as
repository artifacts because they contain disposable test-workspace data.

| Journey | Repeatable automation evidence | Live-browser result | Time / copy observation |
|---|---|---|---|
| First unlock and first prompt | `LoginView`, `ChatView`, and `App` component tests | Account registration reached the ready workbench in 14.1 s. The composer opened in 3.3 s; the prompt reached a truthful `model_unavailable: provider_connection_failed` result rather than simulated completion. | Prompt submission entered the governed phase rail in 1.5 s. The failure text was specific and actionable; no confusing copy observed. |
| Resume and search work | `SessionsView` and `SearchChatView` component tests | The saved session restored through its `session` hash link, and search for `runtime posture` returned exactly one matching conversation. | Restore plus navigation: 6.6 s; search result: 0.4 s. The "Open conversation" result clearly preserved the session target. |
| Approval and critical step-up | `ApprovalsView`, `CapabilitiesView`, `StepUpDialog`, and `tests/test_connector_ecosystem.py` | A disposable, immutable GitHub connector-write approval (`appr_c885f12b86a4473a9402b364366ee616`) appeared in the owner's inbox, displayed its 24-hour expiry and redacted arguments, and was denied in 0.6 s without execution. Opening Hosted models' gate produced the required reason, confirmation-token, and threat-acknowledgement dialog in 0.5 s; it was cancelled without mutation. | Review view loaded in 2.1 s. The explicit "Approve and execute once" and denial result made the consequence clear; no confusing copy observed. The browser pass uncovered and verified the fix for sessionless connector approvals being omitted from the owner's list/detail view. |
| Hosted-model selection | `ModelsView` component tests | Anthropic's model chooser stated that provider policy denied the model list while allowing an explicit model ID; hosted gate, egress allowlist, and configured key remained off/fail-closed. | Models opened in 3.4 s; guarded chooser state appeared in 0.6 s. The policy-denial copy and no-silent-fallback posture were clear. |
| Extension connect/diagnose | `ConnectionsView`, `McpView`, and `DiagnosticsView` component tests | GitHub's local MCP starter flow reported `disabled_by_capability_gate`; the vault-key prerequisite was visible and no connection was created. | MCP dialog opened in 0.5 s; diagnostic appeared in 0.8 s. The raw reason code is intentionally honest but should remain paired with remediation copy in later UX work. |

Phase 0 documentation must still be updated whenever a route, endpoint, event,
or capability label changes. Phase 1 retains its own viewport, keyboard, and
visual-regression quality gates.
