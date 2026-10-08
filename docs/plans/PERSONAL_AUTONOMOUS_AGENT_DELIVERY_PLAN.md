# Personal autonomous-agent delivery plan

## Authority, status and scope

**Accepted direction, 2026-10-07. All PAA items are planned; no implementation
or live/competitive qualification is claimed by this update.** The owner asked
for a personal autonomous agent inspired by Muse.ai, Claude.ai, OpenClaw and
Hermes Agent. The [architecture](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
and [ADR](../adr/ADR-0001-personal-autonomous-agent.md) define the decision.
PAA IDs own new goal/personal-agent delivery work. They do not replace existing
BUG/ADD/DEC closures or retroactively turn proposals into shipped features.

Use [PILLAR_MAP](PILLAR_MAP.md) for product dependencies,
[GOVERNANCE_ENTRY_PATHS](GOVERNANCE_ENTRY_PATHS.md) for authority,
[competitive evidence](COMPETITIVE_READINESS_DEMONSTRATION_AND_EVIDENCE.md)
for evidence levels and [implementation status](../architecture/IMPLEMENTATION_STATUS.md)
for current availability. Preserve all four product pillars and local/private/
hosted model choice. New feature scope belongs here; an observed defect belongs
in TO_BE_FIXED; verified closure requires traceable evidence.

## Delivery sequence and acceptance ownership

Accountable roles below describe implementation/review responsibilities, not
assigned people. Each owner must record revision, entry points and evidence
before promoting a requirement from planned to implemented or verified.

| ID / phase | Outcome and concrete work | Dependencies and existing ownership | Accountable role | Exit evidence |
|---|---|---|---|---|
| PAA-01 / A | Durable goals with criteria, context/task links, plan versions, lifecycle, owner-scoped migrations and archive/export/delete | Existing task/project stores; ADR-0001 | Runtime/storage maintainer | Round-trip and migration tests; owner separation; restart resumes the same goal; deletion/retention checks |
| PAA-02 / B | Goal coordinator uses existing tasks, dependency graph, atomic leases, fresh identity, aggregate budget reservations and truthful parent completion | PAA-01; existing scheduler, identity and delegation paths | Runtime maintainer | Multiple workers claim once; blocked child prevents completion; approval/restart/Stop/revocation traces; budget across children/cycles |
| PAA-03 / B | Inspectable personal context/profile with explicit vs inferred facts, freshness, timezone, governed memory and correction/purge | PAA-01; existing memory lifecycle; ADD-25 only for optional scale expansion | Memory/privacy maintainer | Fixed recall corpus; stale/conflicting facts; corrected timezone; forget removes derived references; actual hosted/local context inspection |
| PAA-04 / C | Owner-created standing intents: scheduled/polling checks, cooldowns, freshness, deduplication, daily budgets and quiet digest; later supported event adapters | PAA-02/03; existing task schedule and DEC-21a | Scheduler/host maintainer | No useful change means no unnecessary alert; DST/missed slots; duplicate trigger; invalid sender/event; budget; no work while stopped |
| PAA-05 / C | Verified connector workflows with effect schemas, read/write classification, least scope, exact approvals, receipts, reconciliation and revocation | PAA-02; existing connector executor/vault; preserve accepted OAuth scope decisions | Integrations maintainer | Real read → proposed write → decision → provider-confirmed result; changed arguments; expired/revoked credential; unknown timeout with no resend |
| PAA-06 / D | Bounded isolated browser workflow with account/session isolation, secret-safe handoff, typed actions, egress policy and destination verification | PAA-05; ADD-23 owns executor; ADD-11 is not implicitly activated | Execution/security maintainer | Isolated-session navigation/form fixture; denied effect; injection; redirect/private-address refusal; credential redaction; disconnect/cleanup |
| PAA-07 / C | Goal progress in existing Home/Chat/Build/Tasks, usable artifacts, named blockers, sources, receipts, budgets and pause/resume/stop | PAA-01/02; current shell/UX work including ADD-26 retains ownership | Product/UI maintainer | Observed complete workflow; keyboard/focus/mobile checks; screenshots tied to actions; no inert controls or false success |
| PAA-08 / B–D | Independent outcome verification, durable effect journal, bounded retry classes and honest partial/unknown results | PAA-02; integration receipts depend on PAA-05; browser effects on PAA-06 | Verification/runtime maintainer | Crash before/after effect; destination read-back; duplicate prevention; partial deliverables; unsupported compensation reported |
| PAA-09 / E | Turn verified outcomes into proposed versioned skills with fixtures, permission diff, owner activation and revocation | PAA-03/08; ADD-05/06/21 retain skill/self-improvement ownership | Skills/security maintainer | Useful repeat-run improvement; malformed/poisoned skill; no authority expansion; rejected activation; rollback and uninstall |
| PAA-10 / D | Continue personal goals through paired channels and an explicitly selected always-on private host | PAA-02/04/05; existing CHANNELS_SPEC; ADD-11 for new off-machine transport | Host/channel maintainer | Authenticated sender to verified effect; impersonation/replay refusal; host offline/reconnect/missed-run; Stop/revocation from supported surfaces |
| PAA-11 / each phase | Publish support matrix and outcome evidence, test reference products on identical supported scenarios and gate claims | CR-01–CR-12; all relevant PAA prerequisites | Release/evidence maintainer | Complete run records, independent validators, five clean trials per supported product/configuration and visible blocked/unsupported cases |

Phase A defines contracts and storage without background effects. Phase B earns
local multi-step goal completion, context and recovery. Phase C earns proactive
read/draft workflows and supported real connector effects. Phase D earns browser
and selected off-machine continuity only after their isolation/reachability
gates. Phase E evaluates learning separately. Existing coding capability stays
available throughout; none of these phases permits an authority bypass.

## Scenarios to demonstrate

These are runnable acceptance briefs, not executed results. Freeze fixtures,
allowed accounts/effects, budgets, timing, validator and retry policy before
running. Use real models/services for end-to-end claims; disclose every stand-in.

| Scenario | Request and fixture | Independent success check | Failure/authority cases | PAA / CR |
|---|---|---|---|---|
| PA-S01 Daily briefing | Summarise a consented test inbox and calendar at 09:00 Europe/London, create a linked report; fixed messages/events | Expected items, source links, timestamps and accessible artifact; no send | DST, stale data, host asleep, expired token, quiet hours, no new items | 03/04/05/07; CR-03/04/05/09 |
| PA-S02 Persistent goal | Research three service options, produce a comparison and prepare a draft enquiry; restart after first step | All criteria met, same goal/task IDs, durable plan and draft, no actual send | Changed preference, approval pause, duplicate worker, child failure, global Stop | 01/02/03/08; CR-01/07/11 |
| PA-S03 Connector completion | In an owner-selected test calendar, propose then create an event with exact attendees/time and verify it | Provider event ID and read-back match approved payload/account; cancellation where supported | Wrong account, changed attendee/time, revoke before execution, timeout after provider commit | 05/08; CR-03/07/09/11 |
| PA-S04 Proactive monitor | Watch a consented public page for a specific change; notify only on a useful fresh change | One notice per change with source/time; bounded cost and polling; digest policy respected | Duplicate/out-of-order events, page prompt injection, repeated empty runs, quiet hours | 04/07; CR-01/05/07/10 |
| PA-S05 Browser fallback | Complete a form on an isolated test service with no connector; stop before any unapproved consequential submit | Expected fields and destination receipt for approved submit; session/account isolation | Private-address redirect, untrusted instructions, sensitive-field handoff, disconnect, changed submit effect | 06/08; CR-03/07/09/11 |
| PA-S06 Reusable workflow | Convert a verified weekly-report process into a proposed skill; review and rerun on a new fixed corpus | New report passes validator with recorded skill version and no extra authority | Poisoned skill, missing tool, permission diff, correction, rollback/revocation | 03/09; CR-04/06/09 |
| PA-S07 Personal coding goal | Fix a real repository bug from a failing test, validate, prepare a commit/review result and report next steps | Hidden behavioral/regression checks pass; focused diff and readable artifact | Recoverable tool error, model outage, approval resume, cost limit, unresolved delegated child | 02/07/08; CR-01/02/08/09/11 |
| PA-S08 Channel continuity | Start a scoped research goal from a paired channel, review in dashboard, stop a child, return confirmed progress | Same goal and owner across surfaces; correct destination; stopped descendants; no premature completion | Sender spoof/replay, mismatched account, offline host, invalid approval response | 02/10; CR-03/07/10/11 |

PA-S03/05 use test accounts and fixtures; no real purchase/booking or unrelated
person-directed communication is authorised by a test-plan entry. Unsupported
service/effect domains stay explicit. Drafting, creating a local record and
sending to a real service must be scored separately.

## Evidence record and release gates

For each scenario record: PAA/CR IDs, date/run ID, Raiker SHA or exact reference
product version/surface, OS, host/inference/tool location, model and settings,
fixture hashes, validator version, owner/account scopes (redacted), granted
permissions, limits, initial state, full task/tool/approval/child trace,
artifacts, provider receipts/read-back, fault injection, interventions,
elapsed time, tokens/cost, delivery result and residual limitations.

Mark outcome as passed, failed, blocked, unsupported, not run or not applicable.
Mark evidence separately as planned, implemented, component-verified,
end-to-end verified or competitively benchmarked. Record every attempt;
unsupported scenarios remain visible. No privacy/authority breach, duplicate
consequential effect or false completion is averaged away by successful runs.
Existing real Raiker live rounds remain valid within their recorded scope;
this plan neither resets them nor upgrades them to goal or competitor proof.

Before claiming a personal-agent release, PA-S01/02/03/04/07 and relevant
lifecycle/privacy/Stop faults need end-to-end evidence on each advertised
configuration. Browser, off-machine continuity and learning claims additionally
require PA-S05/08/06 respectively. A release may omit unsupported optional
flows with clear limits. Competitive parity requires CR's matched-model and
native-product tracks on exact named surfaces; source similarities do not count.

## Documentation and closure procedure

For each implemented PAA item update the spec's baseline table, implementation
status, feature coverage, known limits, API/contracts/events and user guide.
Add immutable run references in LIVE_TEST_ROUNDS and the relevant closure
record; do not add a FIXED entry until work and evidence exist. Keep this plan's
status and CR support matrix aligned. New adapter or schema changes must include
migration/versioning and revocation behavior, then pass existing validation.

## Decisions preserved and open implementation choices

Accepted: one runtime; durable goals reuse tasks; local-first host and chosen
models; bounded owner-controlled proactivity; verified effects; reviewed learning.
Preserved: quiet hours and enumerated exceptions (DEC-21a), existing Git OAuth
provider decision, capability unset rules, account-wide Chat recall, sensitive
domain limits and hosted multi-user deferral. Browser implementation remains
ADD-23 and off-machine gateway expansion remains ADD-11.

Before their phase activates, implementations must document supported first
connector workflows, polling sources/frequency, goal retention defaults,
budget reservation/unknown-price policy and optional always-on host profiles.
These are delivery choices, not unanswered permission questions blocking this
documentation update. No undocumented activation or implied production support.

## Release qualification beyond feature completion — 2026-10-08

[RR-01–RR-36](RELEASE_ACCEPTANCE_TEST_SCENARIOS.md) extend PA-S briefs into a
candidate release protocol. Every implementation needs component tests plus
real entry-point/outcome proof at the advertised configuration. PAA-11 owns the
complete candidate scorecard and evidence collection; an independent release
reviewer owns final GO/NO-GO. All new RR cases start not run, with overall verdict
NOT ASSESSED. Historical rounds and component statuses remain unchanged.

| PAA ownership | Required release scenarios |
|---|---|
| PAA-01/02 durable goals/coordinator | RR-02/03/06/11/12/13/20/21/22/23/26 |
| PAA-03 personal context | RR-10/13/14/15/16 |
| PAA-04 proactivity | RR-08/17/18/19/20/22 |
| PAA-05/08 connector effects and verification | RR-05/07/09/12/14/15/23/24/25/34 |
| PAA-06 browser | RR-29 plus RR-11–15/21/23/24 |
| PAA-07 usable progress/results | RR-05/06/21/26/28/33/34 |
| PAA-09 learning | RR-16/31/32 |
| PAA-10 channels/private-host continuity | RR-04/17/21/22/30 |
| PAA-11 release evidence | RR-01–04/10/27/28/33/35/36 and every applicable B+P/W/C/L result |

Core personal-agent release requires baseline B+P cases and the earlier required
PA-S scenarios. Optional claims require their own cases. Candidate installation,
upgrade/restore, negative authority/privacy cases, restart/ambiguous effects,
72-hour soak and first-use checks are mandatory in addition to useful workflow
completion. Release scope can be honest and narrower than competitors; parity
claims still require separate CR evidence. The protocol defines thresholds to
freeze before execution; this update does not run it or declare release readiness.

## PAA-07 UI and UX task decisions — 2026-10-08

PAA-07 is decomposed into
[UX-01–UX-12](PERSONAL_AGENT_UX_IMPLEMENTATION_PLAN.md), each with a detailed
reason, accepted decision, alternatives, concrete work, dependencies,
state/failure rules and acceptance evidence. The
[UX spec](../architecture/PERSONAL_AGENT_UX_SPEC.md) owns interaction behavior;
backend PAA contracts remain prerequisites rather than simulated frontend data.

Wave 0 freezes shared state/read models and accessibility. Wave 1 improves intake,
Home, approvals, result opening and recovery using real current paths. Wave 2
adds goal detail, context and continuity as their PAA contracts land. Wave 3
runs observed first-user and release qualification. Existing ADD-26 shell and
manual Chat/Build work modes remain. UX tasks start planned/not run; no release
or implementation state is upgraded by accepting their design.
