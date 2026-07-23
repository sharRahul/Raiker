# Hermes-Informed Web Experience Improvement Plan

> **Status:** partially implemented (audited 2026-07-22). The existing local-web
> experience delivers portions of this plan; the phase checklist below remains
> the source of truth for work that is not yet delivered.
> **Reviewed source:** `NousResearch/hermes-agent` `main` at
> `9acc4b47f5b2abda0949d07372ecf67938d50a16` (reviewed 2026-07-22), specifically
> its `web/` application.  This is a capability and interaction review, not a
> proposal to copy Hermes's React, Tailwind, external UI dependency, or trust model.
> Raiker remains a local-first Svelte client over a governed, loopback API.

## Goal

Make Raiker feel calm, coherent, and fast for the common journey—open a project,
ask for work, understand what is happening, and make an informed approval—while
keeping every governance boundary explicit.  The resulting application should be a
focused **workbench**, not a dense administration dashboard or a decorative control
panel.

The current Control Deck plan establishes the security and visual foundations. This
plan fills in the product-quality work it does not enumerate: progressive
disclosure, information architecture, operation feedback, durable workspace
navigation, polished empty/loading/error states, and a complete capability map
informed by Hermes.

## Non-negotiable constraints

1. **The server remains authoritative.** The browser never decides risk, fabricates
   readiness, retains credentials/tokens in browser storage, or turns a denied
   operation into a successful-looking UI state.
2. **Local-first remains literal.** Bundle fonts, icons, styles, and scripts; do
   not introduce a CDN, telemetry, remote asset fetch, or hosted dependency merely
   for presentation.
3. **Governance is comprehensible, not hidden.** A user can always see the current
   project, model/provider, runtime state, pending approvals, and why an action is
   blocked. Critical actions still require the existing human/step-up path.
4. **Build on the typed Svelte layer.** Preserve `api.ts`, `apiTypes.ts`,
   `capabilityModel.ts`, status/reason mapping, and the existing component tests;
   do not migrate frameworks as part of a UX redesign.
5. **Responsive and accessible by design.** Keyboard routes, focus restoration,
   `aria-live` status changes, reduced motion, 44px touch targets, WCAG 2.2 AA
   contrast, and useful zero-data/error states are release requirements.

## Findings from the Hermes review

Hermes has a broad, mature dashboard surface: sessions/chat, files, analytics,
models, logs, cron, skills, plugins, MCP, pairing, channels, webhooks, profiles,
configuration, credentials, docs, and system operations. It also has useful
interaction patterns worth adapting: persistent chat, scoped profiles, a sidebar
health strip, page-header actions, searchable/bulk session management, import and
export, model-role selection, CRUD confirmations, editable automation schedules,
plugin slots, authentication/pairing, and operational recovery tools.

Its approach is not a suitable visual or security template for Raiker. A long,
flat sidebar makes a large product feel like an admin console; its broad set of
direct configuration and system controls must not bypass Raiker's governed action
path. Raiker already has a richer safety model—projects, approvals, capability
decision modes, audit events, checkpoints, notifications, and a stop switch—and
should make those strengths legible rather than imitate a generic dashboard.

### Capability disposition

| Hermes web capability | Raiker status / destination | Plan decision |
|---|---|---|
| Chat, session list/search, markdown, model picker | Present across Chat, Sessions, Search Chat, and Models | Unify into the workbench's primary flow; retain sessions while navigating. |
| Files | Project tree and workspace metadata are present; file mutation is governed | Add a project-context file explorer and diff handoff, never a privileged raw editor. |
| Analytics and logs | Activity, Diagnostics, Brain, and Work in Action exist | Create one observability hub with progressive drill-down rather than more top-level pages. |
| Cron / automation blueprints | Tasks support once, daily, and background work; scheduled routines exist | Improve task composer into an automation builder; preserve approval/gate context. |
| Models and auxiliary roles | Models and provider posture exist | Add clear role/fallback summaries and an egress-aware model selector. |
| Profiles | Projects are the current bounded work scope | Do not copy mutable Hermes profiles. Strengthen project switcher, project overview, and per-project context instead. |
| Skills, plugins, toolsets | Capability gates, Connections, MCP, and plugin contracts exist | Ship an **Extensions** hub only for implemented/authorized capabilities; distinguish installed, connected, enabled-for-session, and usable. |
| MCP catalog/server CRUD/OAuth | MCP and Connections views exist | Consolidate into Extensions; preserve monitored transport, vault references, approval, and health/circuit-breaker facts. |
| Channels, pairing, webhooks | Channel/connector work is planned or deferred | Reserve an Integrations area; do not surface controls before contracts, threat models, and runtime execution exist. |
| API-key/environment editor | Vault/security settings and credential lifecycle exist | Never expose raw environment-variable editing or secret reveal. Use vault references, rotate/revoke, health, and redacted last-used data. |
| Config import/export and system operations | Settings, diagnostics, checkpoints, and project export exist | Add only governed, scoped backup/restore/export workflows after contracts and preflight checks exist. |
| Docs and language/theme choices | Guides, settings, theme preference exist | Add contextual help links and a restrained appearance panel. Localization is discovery work, not a visual-redesign prerequisite. |
| Plugin-provided routes | Plugin system is contract-led | Permit declared, sandboxed extension panels only after route/permission/a11y contracts are specified; no arbitrary client injection. |

## Target information architecture

Replace the current three large, mixed-purpose navigation groups with five stable
destinations. Badges communicate only actionable or changed state, never vanity
counts.

1. **Home / Workbench** — default route. Recent project and sessions, resumable
   work, active task/turn state, approval annunciator, and a focused prompt entry.
2. **Work** — Chat, Sessions, Tasks & routines, Projects, and Search. These are
   work objects, linked by project/session/task context rather than isolated pages.
3. **Knowledge** — Memory, Brain, Checkpoints, and project files/context. Each
   page states exactly what is stored, where it came from, and the available safe
   action.
4. **Control** — Approvals, Models, Capabilities, and Extensions (Connections,
   MCP, future plugins/channels). This is where intent becomes governed action.
5. **Observe** — Activity, Diagnostics, Work in Action, and notification history.
   It is a read-first operational record with deep links back to the affected work.

Settings moves to a fixed footer utility, alongside the master stop and connection
status. On narrow screens, use a bottom navigation for Home, Work, Approvals,
Control, and More; keep the stop control persistent and reachable without opening
a drawer.

Every deep link encodes only non-secret state (route, project, session, selected
record). Back/forward must restore filters and selection. The top bar becomes a
single context bar: breadcrumb/project switcher on the left; runtime health,
pending approvals, model/provider, notifications, and stop on the right. Avoid a
second page title when the body already names the object.

## Experience specifications

### 1. Workbench: the default, useful first screen

Create a responsive two-column landing surface. The main column begins with a
single natural-language composer; it has a session chooser, project scope, model
summary, attachment/context affordance, and compact disclosure of what will be
governed. The secondary column contains only high-value live information: approval
count, active task/turn, and one-click resume cards. Empty states teach the next
safe action; first-run onboarding is a checklist, not a modal tour.

When a turn runs, preserve the composer and show the existing four-phase state
grouping as a compact progress rail. Tool calls, planned changes, approval waits,
citations, failures, and retry/recovery actions are inline, ordered, and
expandable. Do not use simulated progress or decorative agent activity.

### 2. Conversation and sessions

Keep the active chat mounted while the user visits another route, matching the
useful Hermes persistent-chat behavior without leaking subscriptions. Add a
workspace session rail with search, filters (project, status, date), pin/archive,
rename, import/export where the backend supports it, and bulk operations only with
clear scope/confirmation. A session detail side panel should link its turns,
approvals, tasks, checkpoints, memories, model/provider, and audit events so users
do not hunt across five screens.

### 3. Approvals as an understandable decision queue

Make Approvals a triage queue rather than a modal destination: priority/risk
sorting; readable action summary; impact, scope, evidence, and reason code; diff or
redacted argument preview; expiry; and a visible “what happens next.” Approve,
reject, and step-up must have distinct focus-safe flows. Add bulk rejection only
when the server can bind it to exact immutable approval ids; never bulk approve.
Notifications, the top-bar badge, and deep links must all resolve to the same
approval detail.

### 4. Projects, files, memory, brain, and checkpoints

Turn Projects into a context home: objective, permitted workspace roots, recent
sessions/tasks, a compact tree, stored knowledge, and checkpoint timeline. Selecting
a file opens an inspect/diff pane with provenance and links to the approval or turn
that produced it. Memory and Brain should default to plain-language lists and search
rather than graph-first visualization; render the graph only as an optional,
keyboard-accessible relationship explorer. Checkpoint restore is an explicitly
dangerous, preflighted funnel showing affected files, cross-principal escalation,
undo/rollback facts, and audit links.

### 5. Tasks, routines, and active work

Refactor the task composer into progressive choices: **do now**, **schedule once**,
**repeat**, or **background agent**. Each choice reveals only relevant cadence,
scope, model, budget, and delivery controls. Task cards show owner, project,
current step, last meaningful event, next run, stop/pause availability, and the
governing decision—not a character animation. The Work in Action page becomes a
live board with list/table alternatives, status filters, and event-linked details.

### 6. Models, capabilities, and extensions

Use a shared side-panel/drawer pattern for model, gate, connector, and MCP details.
Model selection presents local choices first and labels hosted providers with a
plain-language egress boundary, capability prerequisites, fallback role, cost/health
facts only when supplied by the server, and the exact acknowledgement/approval path.
Capabilities retain the decision-mode-first control from the adopted Control Deck
plan; gate state, executor readiness, reason code, and blocked remediation belong in
expandable detail.

Combine Connections and MCP into an **Extensions** hub with tabs for connectors,
MCP servers, plugins, and future channels. Each card has four separate facts:
installed, credential/account connected, runtime enabled, and currently usable.
Installation/import, OAuth, secret rotation, remote transport, enablement, testing,
and removal must each use their existing or future governed server endpoint and
show monitor/circuit-breaker status. Do not make an extension appear available from
metadata alone.

### 7. Observability, diagnostics, and recovery

Make one Observability hub with a concise status overview followed by tabs/links to
the append-only activity timeline, runtime diagnostics, notification history, active
work, and integrity/readiness checks. The overview answers: *Is Raiker ready? Is
anything waiting for me? What changed? Can I safely proceed?* Each status card links
to concrete evidence, never an opaque green/red dot. Add filterable event views,
correlation links among turn/task/approval/checkpoint, copyable redacted diagnostic
bundles, and retry guidance that never claims a recovery was completed until the API
confirms it.

## Shared design-system work

1. Consolidate tokens in `app.css`: semantic surfaces, text, border, success/warn/
   risk colors, spacing, radii, elevation, motion, focus ring, density, and font
   scale. Eliminate per-view one-off colors, shadows, and modal styles.
2. Complete and document reusable Svelte primitives: page header/context bar,
   toolbar/filter bar, card/list row, status badge, empty/loading/error state,
   side panel, confirm/step-up dialog, segmented control, data table, timeline,
   inline notice, toast/notification center, and skeleton. Every primitive includes
   keyboard, focus trap/return, escape, responsive, and reduced-motion behavior.
3. Establish content rules: sentence case; user outcome before implementation
   detail; no unexplained IDs or reason codes; monospace only for machine values;
   one primary action per region; destructive language names the consequence.
4. Audit density at 1280px and 375px. A dense table is allowed in Observe; Work and
   Control default to scannable cards/lists. Avoid dashboard-card inflation.

## Delivery sequence

### Audit evidence — 2026-07-22

The previous completion claim was incorrect and has been withdrawn. The current
implementation is **partial**, with an audited route/API inventory and 198
component tests, but without the end-to-end and visual evidence required by this
plan.

| Phase | Audited state | Evidence and remaining work |
|---|---|---|
| 0 | complete | Route/API/mutation inventory, non-secret route-state and UI-event contracts, Phase 1 journey baseline, missing read-model inventory, and threat-model review are recorded in `docs/guide/webapp/PHASE_1_PREREQUISITES.md`. Browser-measured usability evidence remains a Phase 1 quality-gate requirement. |
| 0 | partial | Typed API-backed route views and component tests exist. The five measured representative journeys, UI-event schema, and documented missing-read-model inventory have not been recorded. |
| 1 | partial | The shell has grouped navigation, responsive drawer/bottom navigation, tokenized styles, route focus handling, notification access, and a persistent stop control. Visual-regression, keyboard-route, and supported-viewport evidence are absent. |
| 2 | partial | Workbench summaries, chat/session links, a persistent chat host, task cadence choices, session bulk actions, and approval previews exist. Session detail side panel/cross-links, approval triage sorting/expiry/step-up flow, and browser E2E coverage are not complete. |
| 3 | partial | Existing project, memory, brain, checkpoint, model/fallback, capability, connector, and MCP views cover parts of the scope. A project context home/file inspect pane, checkpoint preflight funnel, and one tabbed Extensions hub are not complete. |
| 4 | partial | Activity, diagnostics, Work in Action, and notifications are separate implemented views. A consolidated observability hub, redacted diagnostic export contract, and offline/reconnect/denial/session-restoration browser E2E evidence are not complete. |

Deferred entries (channels, arbitrary plugin panels, raw secret editing, backup
restore, and uncontracted automation delivery) remain absent rather than being
presented as available. Documentation was behind the actual implementation claim;
this audit corrects it. Future changes must update the status and coverage ledgers
in the same commit as the implementation and its verification evidence.

### Phase 0 evidence update — 2026-07-22

The detailed route, API/mutation, state, capability-label, query-state, UI-event,
missing-read-model, and representative-journey audit is recorded in
[`docs/guide/webapp/HERMES_PHASE_0_EVIDENCE.md`](../guide/webapp/HERMES_PHASE_0_EVIDENCE.md).
The source inventory and contracts are complete. The five required local-browser
journey recordings remain blocked by the browser-download restriction and must be
completed before Phase 1 can be claimed complete.

### Phase 0 — Evidence, usability baseline, and contracts

- Inventory every current Raiker route, API call, mutation, loading/error/empty
  state, and all current capability labels; reconcile it with the disposition table
  above and the feature-coverage matrix.
- Run five representative journeys with a local build: first unlock and first prompt;
  resume/search work; approval and critical step-up; select a hosted model; connect
  or diagnose an extension. Record task completion, misclicks, time-to-approval,
  and confusing copy as baseline evidence.
- Define route/query-state and UI-event schemas; identify missing read-only summary
  endpoints before building components. Update API contracts, threat models, and
  coverage documentation before claiming a deferred feature is available.

### Phase 1 — Shell, navigation, and visual cleanup

- Implement the new navigation, context bar, mobile bottom navigation, persistent
  stop/status/approval access, and route-state restoration.
- Apply tokens and shared primitives to the shell, then migrate one representative
  list, form, modal, and detail view to prove the system before broad rewrites.
- Add visual-regression screenshots at desktop/mobile, keyboard navigation tests,
  and theme/reduced-motion coverage. No capability change in this phase.

### Phase 2 — The daily work loop

- Ship Workbench, persistent chat host, session rail/detail, search/filter state,
  turn phase rail, and cross-links among session/task/approval/audit records.
- Rebuild Approvals and Tasks/Routines using shared components, precise optimistic
  state rules, API-confirmed mutations, and end-to-end test paths.
- Measure the baseline journeys again; do not proceed while core work is slower or
  less accessible than the current interface.

### Phase 3 — Context and governed control

- Deliver the project context home, plain-language knowledge views, preflighted
  checkpoint flow, model-role/fallback UX, capabilities detail, and Extensions hub.
- Add only backend read models needed for honest summaries (for example, an
  extension lifecycle/readiness aggregate or project work overview). Every mutation
  continues through existing gate, approval, vault, and audit checks.
- Keep channels, webhooks, plugin route slots, automation delivery targets, backup
  restore, and localization behind their own accepted contracts and threat-model
  work; their navigation entries stay absent or explicitly “not yet available.”

### Phase 4 — Observability, recovery, and quality bar

- Consolidate Activity, Diagnostics, Work in Action, and notification history;
  add evidence/deep links and redacted support export if a server contract permits.
- Add browser end-to-end coverage for offline/error/reconnect, expired approvals,
  denied gates, session restoration, project switching, and critical-action denial.
- Reconcile `docs/IMPLEMENTATION_STATUS.md`, `docs/FEATURE_COVERAGE_MATRIX.md`,
  guides, screenshots, and the accessibility report with what actually shipped.

## Acceptance criteria and measures

The redesign is complete only when all of the following are evidenced in CI and a
local browser run:

- A user can identify the active project, model/provider, runtime readiness, and
  pending approval count from any primary route without opening Settings.
- A new or resumed governed turn, approval decision, task stop, model selection,
  and extension failure each communicate an accurate server-backed final state and
  link to their audit evidence.
- At 375px, primary navigation, composer, approval decision, and master stop are
  usable with no horizontal scrolling; keyboard-only and screen-reader flows have
  tested focus order and announcements.
- No visual surface introduces an external request, secret value/reveal, browser
  token storage, client-side policy decision, or bypass of a governed mutation.
- All route-level components have intentional loading, empty, permission-denied,
  unavailable, and recoverable-error states; no raw exception is user-facing.
- Lighthouse/accessibility checks, Svelte component tests, API contract tests,
  security regression tests, lint, type checks, and production build pass. The
  quality gate also includes screenshot review at the supported viewport set.

## Documentation and truthfulness rule

This plan deliberately lists future capabilities separately from implemented ones.
As each phase changes a contract or delivers an interface, update the corresponding
implementation status, feature coverage, API/schema, guide, threat model, test
evidence, and working screenshots in the same change. If any one of those artifacts
lags implementation, explicitly record that documentation is behind the change and
needs updating; do not market the capability as complete.

## Explicit non-goals

- No framework migration, remote SaaS dashboard, telemetry, CDN assets, or visual
  clone of Hermes.
- No raw shell/terminal, unrestricted file editor, raw environment-secret editor,
  client-side plugin code execution, or direct system-operation controls.
- No generic “AI is working” animation as evidence of execution, no fake progress,
  and no auto-approval/bulk approval path.
- No implementation of deferred Hermes-style features until Raiker has the required
  runtime capability, API contract, tests, documentation, and threat model.
