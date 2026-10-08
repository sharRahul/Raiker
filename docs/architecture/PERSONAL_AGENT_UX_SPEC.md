# Personal-agent UI and UX specification

## Status and decision

**Accepted implementation direction, 2026-10-08; proposed UI work is not shipped.**
[ADR-0002](../adr/ADR-0002-personal-agent-user-experience.md) adopts an outcome-led
experience for the [personal-agent architecture](PERSONAL_AUTONOMOUS_AGENT_SPEC.md).
The [UX implementation plan](../plans/PERSONAL_AGENT_UX_IMPLEMENTATION_PLAN.md)
owns UX-01–UX-12 and their detailed reasons, decisions and acceptance criteria.

The product should let a person ask for an outcome, understand its progress,
make a concrete decision and open the result without learning runtime vocabulary.
Preserve the tested shell and existing work surfaces, model choice and authority.
This target changes presentation, not what the agent is allowed to do.

## Document precedence and current foundations

This specification owns target personal-agent interaction behavior. The
[Control Deck plan](WEB_UI_CONTROL_DECK_PLAN.md) retains shared shell/control
contracts; [visual design](VISUAL_DESIGN_SPEC.md) owns tokens and styling.
Where an older proposed screen name/workflow conflicts with this target, use
this specification for future implementation; do not rename current routes or
claim a migration occurred merely because these docs changed. Implementation
status, actual API schemas, task lifecycle and security contracts remain sources
of truth for supported controls. ADD-26's implemented shell is not reopened.

Reviewed source pointers: `web/src/lib/nav.ts`, `statusMaps.ts`, `reasonCodes.ts`,
`views/TasksView.svelte`, `views/ApprovalsView.svelte`, `views/ChatView.svelte`,
`views/BuildView.svelte`, `views/MemoryView.svelte`, `components/Topbar.svelte`
and `raiker/tasks/lifecycle.py`. Existing navigation, task threads/details,
phase-based actions, approval explanations and delivery-failure states are
foundations to extend, not newly discovered defects. This is a source-based
documentation review, not a fresh visual inspection or completed user study.

## Information architecture and primary journeys

Keep Home, Chat, Build, Design, Threads, Tasks, Projects and Approvals in their
existing roles. Goals are persistent work objects surfaced in Home/Tasks and
their linked conversations, not a mandatory new mode. Settings and observability
retain advanced configuration and evidence. New goal routes need actual backend
support and stable deep links; preserve existing task/thread/project URLs.

| Journey | Default experience | Authority/availability requirement |
|---|---|---|
| First use | Create owner, choose model/location, check readiness, complete a small read task and open its result | No silent provider connection, capability activation or broad permission grant |
| Ask for work | Describe outcome, attach inputs, use optional scope and schedule controls | Distinguish instant reply from persistent goal; ask when duration/effects materially ambiguous |
| Return later | Home shows decisions, progress, recent results and next runs | Owner-scoped server state; stale/unknown state is explicit |
| Follow a goal | Criteria, current step, plan/task tree, blockers, budgets and result links in one view | PAA goal fields must exist before goal-specific UI ships |
| Decide | Exact effect, account/destination, impact, alternatives and existing permission choices | Immutable action and current authority; no UI-only approval or auto-expansion |
| Open result | Usable artifact or confirmed external effect beside its task/thread | Confirmed receipt/validator required; draft, partial and unknown remain distinct |
| Recover | Explain blocker, preserve progress and offer supported next action | Retry/reconnect/resume re-governs; unknown external effect is reconciled before any resend |

## Shared state and action contract

The server owns lifecycle and permitted transitions. Reuse `taskPhase`/status
mappings for tasks; add separate typed goal contracts for PAA states rather than
forcing goal states into task enums. A display label never authorises an action.

| User-visible state | Required information | Action behavior |
|---|---|---|
| Loading | Work is being retrieved | Prevent duplicate mutation; do not render zero items as known empty |
| Empty | Why nothing exists and a relevant supported first action | No dummy goal/cards or implied connection |
| Not started / scheduled / queued | Saved scope, time/zone or next claim | Existing lifecycle controls only; no invented early scheduled run |
| Working | Current observed step, elapsed time and scope | Stop/control according to server; no fabricated percentage or ETA |
| Needs your decision | Blocked effect, why it waits and linked immutable proposal | Review exact decision; no misleading generic Continue |
| Waiting on work / service | Named unresolved dependency and last observation | Independent authorised work may proceed; parent cannot show completed |
| Paused / stopping | Why paused or when stop was requested; pending in-flight effect | Continue only where allowed; stopping is not already stopped |
| Completed / partial | Verified outputs and unmet criteria if any | Open result; Run again creates new work according to lifecycle |
| Failed / unknown outcome | Concrete cause and preserved progress/effect uncertainty | Supported recovery; never blind replay of possible external effect |
| Stale / offline / unavailable | Last updated time, host/model/service reason | Recheck/reconnect; never call unavailable work ready |

Work success, goal completion, provider effect confirmation and notification
delivery are separate facts. Display them separately. A calendar draft is not an
event created, a file link is not a verified usable artifact, and a hidden toast
is not lost work. Real progress estimates must identify their source; indeterminate
progress is the default when there is no reliable denominator.

## Read models and mutation boundaries

UX-01 freezes the actual data inventory and needed response models. Goal views
need owner-scoped IDs, criteria/results, dependency states, plan revision,
current/last observed step, task/thread/approval references, result receipts,
next-run zone/host/readiness, budgets and permitted actions. Personal-context
views need provenance, explicit/inferred status, freshness, sensitivity,
retention and supported correction/forget actions. Treat these as target fields,
not fields already present on existing endpoints.

Reuse current generated clients; schema additions need response models, OpenAPI
and TypeScript regeneration, tests for owner scoping and contract versioning.
Prefer bounded aggregates/pagination over one request per card. Reconcile a
lost stream from authoritative state; new cursor replay requires its own backend
implementation. Optimistic UI may show a pending request, never an unconfirmed
effect. Preserve idempotency keys and reject stale revisions.

## Copy, defaults and progressive disclosure

Lead with owner-relevant purpose: “Needs your decision”, “Waiting for the calendar
service”, “Open report”, “Reconnect account”. Place capability IDs, machine
identity, raw reason code and audit detail behind an inspectable technical view.
Use shared mappings so Home, task, conversation and notification say the same
thing. Keep account, recipient, cost, irreversible impact and privacy disclosures
visible when they affect the decision; advanced configuration is optional, not
hidden consequential information. Use the established authority choices and
unset defaults; do not add a simplified mode that silently enables tools.

Ask follow-ups only for materially missing information. Preserve the owner's
draft/files/project when switching surfaces. Changing where work is filed does
not imply project-isolated recall. Private/local-only work does not silently
select hosted inference; changed destination/effect requires the applicable
current governing decision again.

## Responsive design and accessibility

Reuse local fonts, semantic tokens, reduced-motion behavior and accessible
shared drawers/dialogs. At 390/834/1440/1920 widths and declared higher-resolution
support, core journeys must fit without page-level horizontal overflow; tables
and code may scroll in a labeled bounded region. Test both themes, keyboard-only
operation, screen-reader labels/announcements and 200% zoom. Core controls must
have visible focus, text/icon state cues, readable contrast and no hover-only
access. Mobile goal detail is a usable sectioned page, not compressed desktop
columns. Progress announcements must be throttled and must not steal focus.

## Rollout and verification

Implement UX waves in dependency order, keep current working flows available,
use reversible presentation changes and owner-scoped feature availability.
No inert target control is rendered before its backend path exists. Do not
change permissions to make a usability test easier. UX-12 produces real
first-user evidence; source review and screenshot polish are not completion.
Map UX tasks to [RR release scenarios](../plans/RELEASE_ACCEPTANCE_TEST_SCENARIOS.md),
particularly RR-05/06/09/19/21/26/28/33/34/36, and CR-10/12 for competitive
usability claims. All new UX evidence starts not run.
