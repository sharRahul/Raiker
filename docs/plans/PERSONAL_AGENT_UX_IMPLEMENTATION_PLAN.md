# Personal-agent UI and UX implementation plan

## Status, ownership and rationale

**Accepted implementation direction: 2026-10-08. UX-01–UX-12 are planned;
implementation, visual inspection and usability evidence are not claimed.**
The owner requested documentation so the recommended UI/UX can be implemented,
with detailed reasons and decisions for every task. This plan turns that request
into concrete work against the [target UX specification](../architecture/PERSONAL_AGENT_UX_SPEC.md)
and [ADR-0002](../adr/ADR-0002-personal-agent-user-experience.md).

PAA-07 owns the product outcome and backend dependencies; UX IDs own the
interaction/presentation tasks below. Existing BUG/ADD/DEC records keep their
scope/status. ADD-26's implemented shell remains a foundation, not new unfinished
work. Reviewed code is a baseline, not evidence that every recommended change is
a current defect. No UI code, new route, capability default or authority changes
are made by this documentation update.

Each task has a reason, binding decision, considered alternatives, implementation
scope, dependencies, state/failure contract and verifiable acceptance. Accountable
roles are responsibilities to assign during implementation, not named people.
Status starts planned and evidence not run for every task. Change a decision by
recording rationale, effects on dependencies and acceptance; never silently drift.

## Priority and rollout

| Wave | Task IDs | Outcome and prerequisite |
|---|---|---|
| 0 | UX-01, ongoing UX-11 | Inventory and typed interaction contract before new states/views |
| 1 | UX-02/03/05/07/09 | Improve intake, Home, decisions, result discovery and recovery using existing supported paths |
| 2 | UX-04/06/08/10 | Add goal detail, personal context and continuity only as PAA contracts land |
| 3 | UX-12, final UX-11 coverage | Observed usability, regressions and candidate release qualification |

A wave is dependency ordering, not permission to bypass open release/security
work. Incremental slices may land without all PAA features if their current
scope is accurate; no simulated goal, watcher, receipt or unavailable action is
presented as working. Preserve existing stable task/thread links and support
readable records when rolling back presentation.

## Task ledger

| ID | Task | Wave | Accountable role | Status / evidence |
|---|---|---|---|---|
| UX-01 | [Inventory and shared interaction contracts](#ux-01) | Wave 0 | Frontend/API maintainer | Planned / not run |
| UX-02 | [First use and outcome-based work intake](#ux-02) | Wave 1 | Product/frontend maintainer | Planned / not run |
| UX-03 | [Home overview of useful work and decisions](#ux-03) | Wave 1 | Product/frontend maintainer | Planned / not run |
| UX-04 | [One goal detail with criteria and linked tasks](#ux-04) | Wave 2 | Product/runtime/frontend maintainer | Planned / not run |
| UX-05 | [Concrete, understandable approval decisions](#ux-05) | Wave 1 | Security/product/frontend maintainer | Planned / not run |
| UX-06 | [Truthful background work and schedule controls](#ux-06) | Wave 2 | Scheduler/product/frontend maintainer | Planned / not run |
| UX-07 | [Accessible results and confirmed external outcomes](#ux-07) | Wave 1 | Artifact/product/frontend maintainer | Planned / not run |
| UX-08 | [Inspectable personal preferences and memory](#ux-08) | Wave 2 | Memory/privacy/product maintainer | Planned / not run |
| UX-09 | [Recovery that preserves work and avoids duplicate effects](#ux-09) | Wave 1 | Runtime/product/frontend maintainer | Planned / not run |
| UX-10 | [Continuity across conversation, project and work detail](#ux-10) | Wave 2 | Frontend/API maintainer | Planned / not run |
| UX-11 | [Responsive and accessible shared interaction behavior](#ux-11) | Wave 0–3 | Design/accessibility/frontend maintainer | Planned / not run |
| UX-12 | [Observed usability and release qualification](#ux-12) | Wave 3 | Release/product reviewer | Planned / not run |

## UX-01

**Inventory and shared interaction contracts. Wave 0. Accountable: Frontend/API maintainer. Status: planned; evidence: not run.**

**Reason.** New goal views can become inconsistent with Tasks, Home or approvals if each invents its own state and action rules. Several useful task/delegation/delivery behaviors already exist, so recreating them would introduce regressions rather than improve usability.

**Decision.** Freeze the supported data/action inventory before screen work. Keep existing navigation IDs, task phases and generated API clients; add separate versioned goal/read models only where necessary. Treat the server as authority for availability and permitted transitions.

**Alternatives and trade-off.** A frontend-only aggregate is quick but can diverge, lose owner scope and fan out requests. A whole-client rewrite discards tested logic. Prefer bounded server aggregates plus existing shared mappings, with migration only for genuinely new contracts.

**Implementation tasks.** Inventory current Home/Tasks/Chat/Build/Approvals/Memory inputs and routes; list present vs proposed fields; define goal/task/thread/result/approval IDs and deep links; specify paginated aggregate responses, freshness/revision and idempotency; regenerate OpenAPI/TypeScript when schemas land.

**Dependencies and scope.** PAA-01/02/07 for goal fields; current taskPhase/statusMaps/reasonCodes/nav contracts; API response-model and generated-wrapper checks.

**State and failure decisions.** Loading, empty, partial fetch, stale revision and offline must be distinct. No missing field is converted to ready/zero/completed. Existing links continue to resolve; unknown states offer inspectable recovery rather than fabricated actions.

**Acceptance and evidence.** Contract fixtures and server/client parity tests cover every state; owner scope and stale-update rejection hold; no per-card permission fan-out; RR-11/13/26/35. Publish an inventory with production entry points before dependent UX work.


## UX-02

**First use and outcome-based work intake. Wave 1. Accountable: Product/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** Users should express what they want completed rather than understand task types, model plumbing or tool permissions first. However, silently interpreting a casual request as indefinite monitoring or an external send would violate their intent.

**Decision.** Use natural-language outcome intake on existing composers, with attachments and a compact scope summary. Keep model/location disclosure visible. Offer Now, Later and Repeating through existing task composition; create a persistent goal only with clear scope and supported PAA contracts. Ask only when ambiguity materially affects duration, destination, privacy or result.

**Alternatives and trade-off.** A large mandatory configuration form adds friction; fully hidden auto-routing can choose the wrong workspace or cadence. Choose an outcome-led composer with optional advanced controls and a visible editable intent summary, retaining manual Chat/Build selection.

**Implementation tasks.** Document first-run owner/model/readiness path and small read-task success; preserve draft/files/project across handoffs; describe how intake selects answer vs task vs goal; preview criteria, schedule, account and resulting persistence; expose relevant limits and make follow-up answers resume the same draft.

**Dependencies and scope.** UX-01; existing composer/task creation; PAA-01/02 for persistent goal creation. Basic composer improvement may ship without goals, but may not label ordinary tasks as durable goals.

**State and failure decisions.** Unready model links to setup without discarding input. Pending create disables duplicate submission while retaining idempotency. Cancel returns to the untouched draft. An uncertain interpretation produces one focused question rather than committing an external action.

**Acceptance and evidence.** Three first-time evaluators complete read/report intake using shipped guidance without developer repair; attachments/draft survive mode/project handoff and failed creation; no silent permissions/provider/cadence change; RR-01/05/10/13/26/33.


## UX-03

**Home overview of useful work and decisions. Wave 1. Accountable: Product/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** A person returning to an autonomous agent needs to know what needs attention, what is progressing and where the results are. A control-heavy dashboard or undifferentiated activity log makes the owner reconstruct this themselves.

**Decision.** Organise Home around Needs your decision, In progress, Ready to open and Due next. Use bounded owner-scoped data and links to authoritative detail. Prioritise waiting decisions without turning them into alarm-like promotion; completed work is surfaced by useful results rather than raw event volume.

**Alternatives and trade-off.** An event feed is comprehensive but mixes evidence with useful outcomes. A new separate Goals landing page fragments entry. Extend Home while keeping Activity for detailed traces and Tasks for work management.

**Implementation tasks.** Define each section eligibility/order/pagination; include title, meaningful status, current observed step, last update and relevant result/decision link; show next run with zone/host readiness; dismiss visual attention without deleting work; filter settled/archived data without losing access.

**Dependencies and scope.** UX-01; PAA-01/02/07 for goal aggregates; existing task/readiness/notification data for incremental sections.

**State and failure decisions.** Loading is not an empty dashboard. Stale/offline cards show last observation. No task simultaneously counts as completed and waiting. Delivery failure appears separately from usable results; unknown readiness cannot appear as a green due run.

**Acceptance and evidence.** Cross-check every Home count/status/link against task/goal/approval records during refresh, restart and competing tabs; decisions and results reachable by keyboard; no phantom progress; RR-06/19/22/26/28/33/34.


## UX-04

**One goal detail with criteria and linked tasks. Wave 2. Accountable: Product/runtime/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** Persistent goals need more than a task list: users must see what done means, why work waits and how subtasks contribute. Showing every child as independent completed work can obscure unresolved parent outcomes.

**Decision.** Use a goal detail view linked from Home/Tasks/conversations with outcome, criteria, observed step, plan revision, dependency/task tree, decisions, budgets and results. Keep goal and task lifecycles separate. Required criteria and unresolved children determine completion; model-written summaries cannot override that.

**Alternatives and trade-off.** Expanding a transcript alone hides structure; adding a new mandatory Goal work mode makes users choose implementation concepts. Provide one object detail within existing work navigation, with conversation for steering and Activity for evidence.

**Implementation tasks.** Define header status/actions and sectioned mobile layout; map goal criteria to validators/results; show current plan and meaningful revisions; link each child/thread/approval; expand advanced history on demand; require supported pause/continue/stop/archive controls with clear effect preview.

**Dependencies and scope.** UX-01/03; PAA-01/02/08 goal/dependency/outcome contracts. Do not ship simulated goals before these exist.

**State and failure decisions.** Waiting identifies approval, answer, service or child. Partial names unmet criteria. Stopping remains pending until acknowledged by runtime. Plan changes preserve previous effects/history and never reuse approval for a changed action. Archived goals remain readable.

**Acceptance and evidence.** Restart/approval/child-failure/Stop scenario preserves lineage and criteria; each result has an independent check; parent never completes early; allowed actions match server; mobile and keyboard detail usable; RR-05/06/12/20/21/26/34.


## UX-05

**Concrete, understandable approval decisions. Wave 1. Accountable: Security/product/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** An approval is meaningful only if the owner can understand the effect and scope. Raw capability names add cognitive work, while an oversimplified Allow button can conceal recipients, costs or irreversible impact.

**Decision.** Lead with what will change, the selected account/destination, significant impact and why a decision is needed. Show existing authority choices only when allowed by current contracts. Keep exact immutable arguments and technical trace inspectable; consequential facts are never hidden behind advanced disclosure.

**Alternatives and trade-off.** Raw JSON is accurate but hard to review. Blanket approve-task shortcuts are convenient but can cover unrelated later effects. Use a human-readable effect preview backed by immutable typed data, preserving existing critical approval/step-up rules.

**Implementation tasks.** Create shared effect presentation for file/command/connector/goal proposals; display draft vs real effect; describe consequences of allow/deny and continuation; provide item count/diff where applicable; handle critical step-up and expiry; use identical wording in modal, inbox and task link.

**Dependencies and scope.** UX-01; current approval snapshot/relay/security contracts; PAA-05/08 for new connector effect receipts. This task changes no Ask/Allow/Auto/Deny defaults or scope.

**State and failure decisions.** Changed recipient/account/arguments/revision invalidates the covered preview. Revoked/expired decision shows why and requires current governing path. Pending approval cannot show effect completed; double-click/reconnect cannot execute twice. A denial explains preserved progress.

**Acceptance and evidence.** First-time users correctly identify account, destination and effect before deciding; stale/changed/revoked variants have zero unauthorised effects; critical lifecycle unchanged; focus/labels usable; RR-09/11/12/15/21/23/33.


## UX-06

**Truthful background work and schedule controls. Wave 2. Accountable: Scheduler/product/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** Background work is valuable only when the user knows whether it will run, when, where and under which limits. A persistent-agent label without an awake host/readiness check creates a false promise.

**Decision.** Extend existing Will it run? diagnostics and task threads instead of adding a separate schedule wizard. Show next run/timezone, execution host, model/service readiness, missed-run rule, end condition and effective limits. Keep notification/quiet hours distinct from execution.

**Alternatives and trade-off.** A simple on/off switch hides blockers; showing every runtime setting in the primary card overwhelms routine use. Present a concise readiness summary with linked fix actions and expandable terms, sourced from the server.

**Implementation tasks.** Integrate diagnostics in routine/goal detail; preview upcoming slots; show observed pause/failure limit and remaining budget; explain opt-in proactive monitor condition/cooldown/expiry; link held notices and supported host settings; validate schedule before filing and preserve draft on failure.

**Dependencies and scope.** UX-01/04; existing scheduler/doctor/delivery policy; PAA-04/10 for new standing intents/private-host support; DEC-21a unchanged.

**State and failure decisions.** Host asleep/offline or unknown price/readiness is explicit. Stale checks show age. Missed runs explain run-once vs skip; quiet hours do not approve pending work. No UI toggle activates a watcher/remote host without a real governed path.

**Acceptance and evidence.** DST/missed-run/end-date/failure-limit/unknown-price cases match actual records; unattended outcome and delivery remain separate; no duplicate trigger or noisy empty monitor; RR-08/17/18/19/20/22/30.


## UX-07

**Accessible results and confirmed external outcomes. Wave 1. Accountable: Artifact/product/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** Users benefit from an opened useful result, not a final message saying done. Reports scattered through logs or a remote write without a receipt force users to verify basic completion themselves.

**Decision.** Present results next to the conversation and work item, with Open/Download or a confirmed provider link where supported, provenance, verified time and unmet criteria. Distinguish draft, local record, confirmed effect, partial output and unknown outcome. Delivery state remains a separate field.

**Alternatives and trade-off.** A unified green Done badge collapses incompatible outcomes. A standalone new artifact app fragments work. Use linked result cards and the existing artifact surfaces, with typed receipts and independent format checks.

**Implementation tasks.** Define artifact metadata/actions, expired/missing access behavior, source links and safe previews; connect task/goal criteria to results; include provider confirmation/reference and account/destination without secret URLs; make download/open failure recoverable; support usable result handoff across Chat/Build/Tasks.

**Dependencies and scope.** UX-01; existing artifacts and BuildArtifactPane; PAA-07/08 and PAA-05 receipts for external effects. Do not imply every file format/provider link is already supported.

**State and failure decisions.** Missing/corrupt artifact cannot count as usable completion. Unknown external effect remains unknown. Failed notification cannot remove verified output. File disappearance or stale provider link gets named recovery without replaying work.

**Acceptance and evidence.** Open each advertised format in intended consumer, verify criterion/content and destination read-back, audit final claims; keyboard/screen-reader actions work; no secret disclosure; RR-05/07/09/15/22/23/34.


## UX-08

**Inspectable personal preferences and memory. Wave 2. Accountable: Memory/privacy/product maintainer. Status: planned; evidence: not run.**

**Reason.** A personal agent should be understandable and correctable. If settings, inferred preferences and remembered facts are presented alike, the owner cannot tell why the agent made a choice or fix stale context.

**Decision.** Offer a clear personal-context view linked to existing Memory/Settings rather than a second uncontrolled profile store. Distinguish explicit settings, owner-stated facts and inferred candidates; show source/freshness/scope and supported correction/forget/retention controls.

**Alternatives and trade-off.** A friendly opaque profile hides provenance; copying all records into a new profile creates conflicting deletion behavior. Use governed references and a simple overview with detailed lifecycle inspection.

**Implementation tasks.** Define overview for timezone, communication preferences and priorities where supported; link each item to source and governance state; correct with supersession; show which remembered context influenced a goal; explain account-wide recall vs project filing; propagate deletion to derived UI caches/indexes.

**Dependencies and scope.** UX-01; existing memory/settings/lifecycle; PAA-03 and relevant ADD-25 dependencies only where needed for expansion.

**State and failure decisions.** Unreviewed inference is labeled candidate, not owner fact. Stale/conflicting facts are visible. Pending forget is not already purged. Removal clears derived displayed context according to declared purge contract; hosted inference location is not concealed.

**Acceptance and evidence.** Paraphrase/distractor recall, correction/expiry/forget/purge and two-owner checks pass; person can trace and correct a preference using shipped guide; no permission granted by memory; RR-10/13/14/15/16/33.


## UX-09

**Recovery that preserves work and avoids duplicate effects. Wave 1. Accountable: Runtime/product/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** A generic failure message or Retry can cause users to repeat effects or abandon completed progress. Personal-agent work can fail at model, credential, host, artifact or provider-confirmation boundaries, requiring different actions.

**Decision.** Explain what failed, what is preserved, whether any effect may already have happened and the supported next action. Prefer specific Reconnect account, Check result or Continue preserved work over a generic Retry. Keep raw reason/audit available behind detail.

**Alternatives and trade-off.** Always retry simplifies UI but can duplicate sends. Exposing only raw errors is precise but unhelpful. Shared reason-to-recovery mappings use server-supported actions; ambiguous provider effects require reconciliation before any resend.

**Implementation tasks.** Create recovery copy/actions for readiness, rate limit, credential expiry, missing input, budget exhaustion, partial artifact and unknown effect; link to exact settings/decision/receipt; preserve drafts/history; record retried run lineage and cancellation; distinguish Run again new work from continuation.

**Dependencies and scope.** UX-01/05/07; existing reasonCodes/task lifecycle; PAA-02/08 recovery/receipt contracts for new goals.

**State and failure decisions.** Reconnect does not automatically grant broader scopes. Changed environment or approval is re-governed. No Continue control for a terminal run. Unknown outcome offers supported status check/owner review and never blind resubmission. Successful prior steps remain visible.

**Acceptance and evidence.** Injected provider/credential/host/disk/after-commit faults reach useful recovery with no duplicate effect or lost draft; all claims match actual state; RR-12/21/22/23/24/25/26/33/34.


## UX-10

**Continuity across conversation, project and work detail. Wave 2. Accountable: Frontend/API maintainer. Status: planned; evidence: not run.**

**Reason.** Delegation crosses multiple views. Losing the draft, project or result link during handoff forces users to remember IDs and repeat instructions; multiple interpretations of the same status weaken trust.

**Decision.** Keep stable owner-scoped links and one authoritative work identity across conversation, goal, task, approval and artifact. Preserve existing deep links, draft/attachment handling and manual work-mode choice. Back/refresh restores reading context without implicitly changing execution.

**Alternatives and trade-off.** A new top-level mode for every object creates navigation overhead; modal-only detail breaks linking and history. Use existing navigation plus supported object addresses and predictable breadcrumbs/back behavior.

**Implementation tasks.** Define relationship links and return targets; preserve composer draft/files/project in mode/task handoffs; reconcile reload/reconnect from authoritative state; handle deleted/archived/inaccessible references; synchronise status across tabs and supported channels without duplicating task creation.

**Dependencies and scope.** UX-01/04/07/09; PAA-01/02/07 for goal addresses; PAA-10 only for new channel continuation. No channel approval authority is added.

**State and failure decisions.** Access-denied/deleted references explain loss without leaking private titles. Project change affects future filing, not past ownership/recall policy. A stale tab re-reads version and does not replay an old mutation. Browser back never silently resumes work.

**Acceptance and evidence.** Keyboard/back/refresh/two-tab/reconnect journeys preserve identities and drafts; all result/approval links resolve to correct owner/version; cross-surface counts/actions agree; RR-06/12/13/26/30/33.


## UX-11

**Responsive and accessible shared interaction behavior. Wave 0–3. Accountable: Design/accessibility/frontend maintainer. Status: planned; evidence: not run.**

**Reason.** An agent cannot be user-friendly if decisions, results or Stop depend on mouse hover, colour or wide screens. Existing semantic tokens and tested drawer/dialog logic should be reused, not replaced with a new inconsistent visual system.

**Decision.** Keep implemented ADD-26 shell, local fonts/tokens and restrained motion. Apply keyboard, screen-reader, zoom, responsive and theme checks to each new journey. Mobile goal detail uses sections rather than compressed columns; progress updates do not steal focus.

**Alternatives and trade-off.** A visual-only desktop review misses interaction failures; building a separate mobile frontend duplicates states. Reuse shared accessible components and test realistic interactions at documented widths and zoom.

**Implementation tasks.** Add focus/announcement rules, text/icon state cues, minimum target and contrast checks from existing accessibility contract; respect reduced motion; trap/restore modal focus; preserve scroll; bound table/code scrolling; render all loading/empty/error/partial/waiting states in both themes.

**Dependencies and scope.** Existing VISUAL_DESIGN_SPEC and shared components; UX-01 state contract; applies to every UX task, not a final cosmetic phase.

**State and failure decisions.** Opening an approval restores focus on close; rerender does not reset reading/typing; notifications are not the sole decision access; slow updates are throttled; unavailable control reason is accessible and does not appear actionable.

**Acceptance and evidence.** 390/834/1440/1920 and declared high-resolution support, both themes, 200% zoom, keyboard-only and screen reader core journeys pass; no page overflow, invisible focus, colour-only state or inaccessible Stop/approval/result; RR-19/21/28/33/34.


## UX-12

**Observed usability and release qualification. Wave 3. Accountable: Release/product reviewer. Status: planned; evidence: not run.**

**Reason.** An implementer can navigate a product they built while a first-time user still fails. Screenshots, component tests or familiar-user feedback cannot show that ordinary people can delegate, approve, recover and find usable results.

**Decision.** Use the RR release protocol with three first-time evaluators on realistic tasks, record all attempts/help/interventions and independently check outcomes. Core completion without developer repair is the gate; benchmark CR-10/12 separately for competitive claims.

**Alternatives and trade-off.** A subjective polished rating does not prove completion. Averaging away one inaccessible/unsafe core flow hides a blocker. Keep task-level outcomes and authority/privacy invariants, with predetermined budgets and transparent exclusions.

**Implementation tasks.** Freeze candidate/UX task/configuration/fixtures; evaluate onboarding, report goal, approval, scheduled run, result opening, correction and recovery; record action count/time/help and comprehension of scope; test responsive/keyboard/screen-reader paths; file defects and rerun affected dependencies at final candidate.

**Dependencies and scope.** UX-02–11 supported production paths; PAA-11; RR-01/05/06/09/16/21/26/28/33/34/35/36. Planned browser/channel/learning UI tested only when advertised and implemented.

**State and failure decisions.** Blocked/unrun mandatory journey cannot become a pass through documentation. Preserve failures, stand-ins and partial results. A missing optional feature is an explicit support limit, not a clickable inert promise. No study or UI implementation is performed by this plan.

**Acceptance and evidence.** All three evaluators complete each advertised core task with shipped guidance and no developer repair; all RR mandatory gates/evidence satisfied; independent reviewer records exact candidate/GO or NO-GO. Source/screenshots alone cannot close UX tasks.

## Implementation and closure checklist

Before coding a task, record the slice, actual backend fields/entry points,
accepted decision, owner role, dependency versions, affected states and RR IDs.
Use existing contracts; regenerate API artifacts only for real schema changes.
Keep first-user copy free of implementation vocabulary while exposing meaningful
account/cost/privacy facts. An approved visual design never changes permission.

For UI changes run web lint/check/unit/build/mocked interaction suites and the
relevant backend/contract checks, then real served journey tests and independent
result/effect checks. Retain screenshots tied to actions, keyboard/focus and
accessibility evidence, before/after task metrics, faults and residual limits.
Link executed results from LIVE_TEST_ROUNDS; do not invent a new round here.

Close UX work only after its acceptance criteria pass on the declared scope.
Update spec, guides, implementation status and RR scorecard in the same change.
A new unresolved issue belongs in TO_BE_FIXED; a planned UX feature stays here.
Independent release review uses RR-36; aesthetic improvements do not waive
blocked/unrun usability, authority, privacy or completion gates.
