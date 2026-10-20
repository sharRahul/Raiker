# Personal autonomous-agent architecture

## Decision and scope

**Accepted product and architecture direction: 2026-10-07. Implementation is
staged and separately evidenced.** Raiker should be a personal autonomous agent
that understands an owner's context, accepts outcome-based goals, plans and
executes bounded work, continues across sessions, and verifies useful results.
It is the owner's all-purpose digital agent: one product for thinking, research,
creation, communication, organisation, coding, automation and connected-service
work, not disconnected point tools. Its assistant, coding/build agent and
extensible platform remain part of one product. See
[ADR-0001](../adr/ADR-0001-personal-autonomous-agent.md).
The product serves one individual owner. Personal work may involve the owner's
workplace or organisational accounts, but Raiker does not become a tenant or
staff-management application, and remote service administration never supersedes
that owner's explicit authority.

Autonomy means independently choosing and completing steps within delegated
scope. It does not grant new capability permissions, change defaults, or
approve actions. A suggestion, memory, schedule, project or connector connection
is never authority. Preserve the owner-authoritative, monitored posture in
[Security and policy](../architecture/SECURITY_AND_POLICY.md).

This specification defines the target. [Implementation status](../architecture/IMPLEMENTATION_STATUS.md)
remains authoritative for shipped features, and the
[delivery plan](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) owns PAA work
and acceptance gates. The first slices of PA-D01, PA-D02 and PA-D06 shipped on
2026-10-20 — durable goals, Settings-owned execution profiles, **Work → Goals**
and Home's Goals board ([FIXED-1039](FIXED_ITEMS.md#fixed-1039--an-outcome-could-live-only-in-a-chat-transcript-there-was-no-durable-goal-goal-01-pa-d01)
to [FIXED-1053](FIXED_ITEMS.md#fixed-1053--home-could-not-say-which-outcomes-needed-the-owner-ux-goals-02-pa-d06));
the register below says what each still lacks. No browser executor exists.

## Personal product boundary

Raiker is designed for **one individual owner**, their devices and projects, and
the services they explicitly connect. Its optional home-lab, private-network
and hosted model/runner integrations are *execution choices for that owner*, not
a separate organisational deployment or administration product. Do not add
team administration, corporate policy consoles, tenant provisioning, managed
employee accounts or organisational sales requirements to the personal-agent
roadmap. Those are not prerequisites for durable goals, personal memory,
proactivity, coding or verified outcomes.

The owner controls profiles, models, permissions, credentials, schedules, audit
records, retention and Stop. Shared/reachable services still need identity,
isolation, approval, revocation, budget and audit safeguards. A third-party
provider's organisational billing or account terminology may be documented when
technically necessary; it does not change Raiker's product audience.

## Unified personal-agent outcome contract — 2026-10-15

Raiker's product target is the continuous, unified experience: **the owner gives
Raiker an outcome and can return to a verified result, an honest blocker, or a
safe decision that only they can make.** It combines durable autonomy, governed
personal memory and connected actions with the specialised Build and Design
workspaces. It adopts the useful outcome continuity of personal agents while
retaining Raiker's explicit authority, local-first control and inspectable
evidence.

A goal is the cross-surface contract. It may ask ordinary Chat work to research
and draft, [Build](BUILD_WORKSPACE_SPEC.md) to produce verified repository work,
[Design](DESIGN_WORKSPACE_SPEC.md) to produce a versioned design artifact,
Memory to retrieve or correct owner context, and a supported connector or
browser workflow to create a verified external effect. Those are goal steps,
not independent success claims: the coordinator aggregates their artifacts,
receipts, validations, budgets, blockers and authority into one owner-visible
outcome.

The coordinator chooses a suitable already-authorised step and execution path;
it does not invent authority, silently move data, or replace an unavailable
capability with a broader one. Each specialised workspace remains responsible
for its own requirements and evidence. The personal-agent layer owns only their
composition, lifecycle, user-visible progress and final outcome assessment.

### Settings-owned execution profiles

Owners must not configure a firewall in every prompt. **Settings** is the only
place that creates, edits, activates or binds an execution profile. A profile is
the reusable boundary for model/inference, host, data handling and baseline
action posture. New goals inherit the owner's active profile; Settings may bind
an existing profile to a project. A prompt, memory item, schedule, connector,
agent or subagent cannot select or change one.

A profile declares at least:

- allowed model providers/models and whether their supported API or connection
  may be used;
- allowed execution hosts, including local device, owner-selected private
  always-on host, or a separately governed remote executor;
- data classes that may leave the owner-controlled host, including whether
  selected files, attachments, images, research references or personal-memory
  entries may be sent to each provider;
- provider/host egress, credential and retention constraints; and
- baseline action posture, budgets and required human approvals.

Settings may offer comprehensible templates such as **Private local**,
**Balanced**, and **Cloud-first**, but each remains an owner-inspectable profile
rather than a hidden provider fallback. A cloud model through an approved API or
provider connection is a supported execution choice for owners without local
hardware; it does not make local files, sensitive memory, credentials or an
always-on cloud agent implicitly available to that model. Subscription access is
used only through a provider's supported API or integration, never by automating
credentials or bypassing provider terms.

Surfaces show the active profile as read-only context—for example, which models,
host and data classes are available—without asking the owner to configure it
mid-task. A model picker may choose only among models already allowed by the
profile. If a goal cannot meet its requirements inside the profile, it becomes
blocked with the exact reason and a route to Settings; it does not show inline
policy toggles, silently change provider/host, or transmit additional context.
Concrete consequential actions still require their separately applicable
approval; approving an email, PR or export is not profile configuration.
An execution profile is a ceiling and baseline: Build/Design turn modes and
approval-policy controls may further restrict it, but cannot waive its required
human approvals, budgets, egress/data limits or standing capability gates.

Changing an active or project-bound profile is an audited Settings action. A
running goal pauses at a safe boundary and revalidates profile version, host,
model readiness, data scope, budget and delegation before any further work.

## Reference ideas and Raiker adaptations

These are design inspirations from primary documentation checked on 2026-10-07,
not code audits, parity claims or a promise to reproduce every feature.

| Reference and source | Idea to adopt | Adaptation for Raiker | Acceptance owner |
|---|---|---|---|
| reference personal agent product | Delegate a goal and keep progress moving across sessions | Durable goal with success criteria, plan revisions, task links and confirmed outcomes | PAA-01/02/08 |
| reference personal agent product workflow | Finish workflows, show the concrete effect, distinguish pending from confirmed, recover without duplicate effects | Typed effect contracts, account/destination-bound approvals, provider receipts and reconciliation | PAA-05/08 |
| the Anthropic assistant projects | Reuse files, instructions and work context in projects | Reuse Raiker projects and personal context; distinguish filing from retrieval scope | PAA-03/07 |
| the Anthropic assistant scheduled tasks | Recurring work produces finished outputs with connected tools | Extend the existing scheduler and task threads; identify the actual host that must be running | PAA-04/07 |
| the Anthropic assistant skills | Package repeatable procedures and load relevant context progressively | Versioned instruction-only skills with reviewed tool dependencies and owner activation | PAA-09 |
| reference platform heartbeat | Proactive checks can stay quiet when there is nothing useful to report | Opt-in standing intent with bounded polling, deduplication and usefulness measurement | PAA-04 |
| reference platform automation and channels | Persistent gateway, scheduled work and delivery through familiar channels | Reuse the Raiker host, scheduler and authenticated channel gateway; preserve sender and target checks | PAA-04/10 |
| reference platform memory | Personal context and past work improve later tasks | Governed preferences and episodes with provenance, freshness, correction and deletion | PAA-03 |
| reference platform skills | Successful work becomes reusable procedural knowledge | Propose a skill from a verified outcome, evaluate it and review its authority before activation | PAA-09 |

the Anthropic assistant's current help pages describe a gradual unified the Anthropic assistant experience and
remote scheduling, with older locally scheduled tasks retaining their host.
Record the exact surface, plan and execution host in any comparison. Raiker's
local scheduler does not inherit another product's remote availability.
reference personal agent's persistent VM is inspiration for continuity, not evidence that Raiker
has a persistent browser or VM; bounded browser work remains ADD-23/PAA-06.

## Existing foundations and remaining work

Baseline inspected: `568e88f98cb566418648a166e5db41e719364a5f`.
Code and tests below are implementation pointers, not proof of live-service or
competitive success. Existing dated live rounds retain their stated scope.

| Foundation | Production pointer | Existing test pointer | Remaining target |
|---|---|---|---|
| Task ownership and lifecycle | `raiker/tasks/manager.py`, `raiker/tasks/lifecycle.py` | `tests/test_task_delegation_ownership.py`, `tests/test_task_lifecycle_phases.py` | Goal-to-task mapping and independent goal completion |
| Scheduled turns and approval continuation | `raiker/tasks/scheduler.py`, `raiker/tasks/schedule.py` | `tests/test_task_scheduler.py`, `tests/test_task_schedule_terms.py` | Standing-intent triggers and cross-run goal orchestration |
| Runtime budgets and diagnostics | `raiker/tasks/run_limit.py`, `raiker/tasks/cost_limit.py`, `raiker/tasks/doctor.py` | `tests/test_routine_run_limit_and_doctor.py` | Aggregate goal budgets across children and cycles |
| Memory and retrieval | `raiker/memory/governance.py`, `raiker/memory/retrieval.py` | `tests/test_memory_lifecycle_usage_import.py`, `tests/test_memory_retrieval_hardening.py` | Explicit personal profile and goal-linked context policy |
| Connectors and credentials | `raiker/runtime/connector_ecosystem.py`, `raiker/security/credentials.py` | `tests/test_connector_tool_policy.py`, `tests/test_credential_security.py` | Workflow-level service effects, destination verification and reconciliation |
| Notifications and attention | `raiker/notify/delivery_policy.py`, `raiker/notify/task_notifier.py` | `tests/test_notification_quiet_hours.py`, `tests/test_task_finished_notification.py` | Proactive digest and suggestion usefulness controls |
| Gateway and machine identity | `raiker/gateway/agent_gateway.py`, `raiker/runtime/identity/` | Existing identity and governance suites | Every new goal/trigger path must converge on these boundaries |
| Web access | `raiker/runtime/web_access.py` | Existing web-access tests | Interactive isolated browser remains planned; fetch is not browser control |

## One runtime, two orchestration lifetimes

A goal survives individual conversations and task runs. A turn remains the
bounded unit of model/tool execution and signed machine identity. The target
adds a coordinator around existing task execution, never a second tool broker.

1. The authenticated owner expresses an outcome, inputs and constraints.
2. Intake resolves scope, creates a draft goal and asks only for materially
   missing facts. Approval requests show the concrete proposed effect.
3. An owner-accepted plan links existing tasks/routines to success criteria.
4. The coordinator selects a due step from durable state, reserves budget and
   starts an ordinary gateway turn under the active execution profile. Context
   is data, never authority.
5. Each tool call passes through `PolicyEngine.review`, the broker,
   `RuntimeAuthority`, credential and executor boundaries. A child receives no
   greater authority than its parent.
6. Receipts and independent checks update progress. Approvals and questions
   park only dependent work; independent steps may continue within scope.
7. The goal finishes only when every mandatory criterion has evidence, or it
   records partial/blocked/failed/stopped status with preserved progress.
8. Delivery is a separate outcome. A lost notification never re-executes work.

The coordinator must be model-independent for claims, leases, budgets, policy
and terminal decisions. Models may propose plans and revisions. Owner choices
or consequential scope changes require the existing governing decision path.
It also remains provider- and host-honest: a local-only goal stays local, and a
cloud-allowed goal sends only the profile-authorised task material to its named
provider. A failed local model or unavailable host is a named blocker, not a
reason to silently fall back to another provider.

## Proposed durable contracts

These are logical target records, not current Python classes or API payloads.
Reuse existing task, session, approval and event records by reference. Add
versioned owner-scoped SQLite migrations only when PAA-01/02 contracts land;
keep bounded artifacts encrypted under existing storage/retention rules.

| Record | Required fields and relationships |
|---|---|
| Goal | `goal_id`, `owner_id`, title/objective, success criteria and validators, context references, optional `project_id`, plan version, status/reason, timestamps, budget policy and revision |
| Goal step | `step_id`, `goal_id`, dependency IDs, linked task/run IDs, expected deliverables/effects, validator, state, result references and failure/retry classification |
| Delegation envelope | Owner-issued ID/version, goal and task scope, permitted accounts/resources/destinations/environments, allowed effect classes, expiry, budgets, revocation status and audit reference |
| Execution profile | Owner-scoped ID/version, allowed models/providers, permitted hosts, per-provider data classes, egress/credential/retention constraints, budget/action posture, active/project binding and audit reference |
| Standing intent | Owner, goal/scope, schedule or supported event source, predicate, freshness window, cooldown/deduplication key, expiry, delivery preferences and active/paused status |
| Personal context reference | Memory/source ID, origin, owner/project scope, confidence, sensitivity, observed/expiry times and correction/deletion state |
| Effect receipt | Action/goal/step/task/run IDs, provider/account/destination references, idempotency key, request fingerprint, quoted/pending/confirmed/failed/cancelled/unknown outcome, external confirmation ID and observed time |
| Outcome assessment | Success criterion, validator/version, artifact/receipt reference, result, limits and verified time; distinguish deterministic checks from model judgement |

A delegation envelope narrows existing authority. It cannot turn an off gate on,
replace policy, override a denied action or grant a human-only role. If generic
envelopes are unsupported, that flow stays unavailable rather than mapping to
an unscoped grant. Financial execution remains within existing domain limits;
this direction does not enable purchases, transfers or trades.

Concurrent workers claim a step/run with a durable lease and compare-and-set
version. Goal budgets reserve before dispatch and reconcile actual usage after.
A restart revalidates owner, goal/envelope and execution-profile versions,
revocation, model readiness, executor and lease before continuing. Do not reuse
an expired turn token.

## Goal lifecycle and recovery

Target goal states are separate from current task phases and runtime states.

| State | Entry and exit rule |
|---|---|
| Draft | Intake and success criteria recorded; no implicit permission to run |
| Ready | Owner accepted the execution scope and required dependencies are available |
| Running | At least one bounded step is in flight |
| Waiting | Named external dependency, approval, answer or unresolved child blocks progress |
| Paused | Owner pause, budget exhaustion or repeated failure; explicit continuation rechecks scope |
| Completed | Every mandatory criterion independently verified; optional work identified |
| Partial | Some usable outcomes verified; unmet criteria named; no full-success claim |
| Failed | Unrecoverable failure with receipts and recovery options retained |
| Stopped | Stop reached a safe boundary; committed effects and remaining work reported |
| Archived | Owner hides settled work without reactivating it or granting authority |

Record waiting reasons separately so an approval is not called a failure.
Resuming creates/continues an ordinary governed turn with fresh identity and
current checks. A parent may not complete while mandatory children are open.
Stop propagates to all active descendants and prevents new claims. State and
receipt commits must be durable before releasing the claim.

Exactly-once external effects cannot be promised for arbitrary services.
Use provider idempotency where supported, persist effect intent before dispatch,
and reconcile an ambiguous timeout by querying status. If the service has no
reliable status/idempotency support, keep `unknown`, park and ask the owner;
never blindly resend or claim success. Restore/compensation applies only where
supported and authorised; a local checkpoint does not undo an email or booking.

## Personal context without permission by memory

The target personal profile contains owner-chosen preferences, timezone,
communication style and goal priorities, each linked to governed memory or an
explicit setting. Inferences are candidates, visibly distinguished from owner
statements. Corrections supersede old values; expired facts are refreshed or
marked stale. Forget/purge propagates to derived profile and goal-context indexes.
Do not infer sensitive personal attributes as a condition of using the agent.

Projects remain organisation and context, not authority. Current Chat recall is
account-wide by design; the target must not claim project-isolated recall until
an explicit retrieval policy exists and is evidenced. Explain what a turn used,
allow owner inspection and correction, and minimise data sent to hosted models.
Private/local context cannot silently switch to a hosted fallback.

Memory retrieval is constrained by the active execution profile as well as the
memory record's own scope and sensitivity. A cloud-allowed goal may use only
the profile-authorised context classes and explicitly selected material; a
profile never turns a private or sensitive memory record into cloud context by
default. The owner can inspect why a memory item was used, correct it, remove
it, or change the future profile in Settings; none of those actions rewrite a
past provider receipt.

## Bounded proactivity and host availability

Start with existing routines and explicit opt-in polling intents. Event-driven
watchers are a later adapter, not a reason to add a parallel executor. Every
trigger validates source identity, scope, freshness and duplicate key. Batching,
cooldowns, polling frequency and daily cost limits prevent empty work and noise.
Suggestions do not activate a goal or extend authority on their own.

Quiet hours are attention preferences, not execution permission. Preserve
DEC-21a: quiet hours opt-in; critical exceptions off by default and limited to
the existing enumerated security kinds; held notices stay in the inbox and may
produce one summary. Urgent wording generated by a model grants no exception.

Local background work requires an awake, running Raiker host. A future
owner-selected always-on private host must expose heartbeats, missed-run policy,
reconnect and revocation. Hosted multi-user service and off-machine gateways
retain their existing scope decisions; this plan does not silently deploy them.

## Connector and browser completion contracts

Each advertised workflow declares accounts/scopes, input/output schema,
read/write/consequential effect class, approval boundary, rate limits,
idempotency/status behavior, receipts and follow-up operations. Prefer a
supported connector for reliable effects; browser fallback must be disclosed.
Read-only connection options and credential revocation are owner controls.
Credential references remain outside prompts, traces and tool-visible output.
The active execution profile further bounds which provider/host may process the
workflow's data; a connector connection alone does not override that boundary.

ADD-23 owns browser implementation: isolated named sessions, owner-selected
profile, bounded navigate/read/click/fill/upload/download operations, endpoint
and redirect revalidation, account separation, action/egress classification,
secret-safe sign-in handoff, downloads in approved roots and session teardown.
Reuse WebAccessService's egress guarantees; do not give JavaScript evaluation,
raw CDP or unrestricted host-browser authority to the model. A browser click
must be classified by its effect. Page text cannot authorise sends or purchases.
No login, CAPTCHA, MFA or identity-check bypass is part of the target.

Consequential effects require the applicable exact human decision and current
scope. Changed price, recipient, destination, arguments or plan/envelope version
invalidates the covered proposal. Existing Raiker decision modes and critical
approval lifecycle remain authoritative; reference personal agent permission defaults are not copied.

**Repository work (2026-10-12).** GitHub repositories follow the
[GitHub connection specification](../architecture/GITHUB_CONNECTION_SPEC.md) (DEC-21b as
amended). Signing in, installing the App or storing a credential grants no
effect. A goal that pushes or opens pull requests runs under an explicit,
stored delegation naming the repository id, operations and branch pattern; a
read delegation never writes, a PR delegation never merges, a scheduled run
creates no authority, a resumed run revalidates delegation, credential,
installation and permission first, and a child never exceeds its parent
(PAA-12). Issue, PR and comment text is untrusted data and cannot select a
credential or change a decision mode.

## User experience and learning

Use the existing Chat/Build/Tasks/Projects/Approvals/Activity surfaces. The target
adds goal progress and references instead of requiring an additional work mode.
A home overview should answer: what is progressing, what needs my decision,
what finished, what failed and why, and what is due next. A goal details view
shows criteria, plan, task tree, sources, receipts, budgets, pause/resume/stop
and next action. Keep implementation details out of routine user decisions.
The active execution profile is disclosed as concise read-only context, with a
Settings route when it blocks work; routine goal surfaces do not expose model,
egress or data-class configuration switches.

A verified workflow may produce a proposed reusable skill. It carries sources,
version, fixtures, validators, tool dependencies and a permission diff. Evaluate
it before owner review/activation; rollback or revoke it independently. Learning
never rewrites policy, silently broadens permissions or installs model-authored
code. Instruction-only Raiker skills remain distinct from governed script tools.
PAA-09's evaluation, quarantine/restore, failure-recall and metric contracts are
in [SELF_IMPROVEMENT_MODEL.md](../architecture/SELF_IMPROVEMENT_MODEL.md)
sections 6–9.

## Acceptance and claim rule

PAA-01–PAA-12 in the [delivery plan](PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
are the rollout gates. Use existing CR evidence levels, preserve older live
records, and run identical declared scenarios on exact supported reference
surfaces before asserting parity. No benchmark was performed for this update.
Release wording remains “personal-agent direction” until the relevant goal,
background, integration, memory and recovery scenarios have end-to-end evidence.

## Detailed UI and UX implementation decisions — 2026-10-08

The [UX specification](PERSONAL_AGENT_UX_SPEC.md) and
[UX-01–UX-12 task plan](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) make the
user-experience target implementable. They define outcome intake, Home sections,
goal criteria/tasks, concrete approvals, schedule/host readiness, usable results,
inspectable personal context, supported recovery, continuity and accessibility.
PAA-07 retains outcome ownership; PAA-01/02/03/04/05/08/10 supply actual data and
authority dependencies. No UI infers completion, readiness or allowed actions
from model prose. Goal controls wait for backend contracts; existing work modes,
model choice, lifecycle and permission decisions remain.

## reference personal agent distinction and benchmark scope — 2026-10-12

The reference is **reference personal agent, the personal AI agent**, not a generic reference personal agent service, **reference personal agent Code**, or the **reference personal agent Wonder/Wonder Full** models. Meta's product launch documents persistent goals, cloud Secure VM/browser, background execution, app connections, remembered context and owner-reviewed consequential actions; its security engineering description provides the vendor's containment design. The 2026-10-12 model release describes Active Memory/Active Focus as model properties and is not evidence that reference personal agent's finished-work success rate improved. Raiker adapts the experience through PAA-01/02/03/04/05/06/08/10 while retaining user-selected inference and owner-scoped authority. Exact comparison tests and permission/host differences are in [RCD-10](PERSONAL_AUTONOMOUS_AGENT_SPEC.md). No parity claim or activation is implied.

## Consolidated personal-agent delivery register

This register replaces the personal-agent, UX, autonomy, governance and future
capability plans formerly held in `docs/plans/`. Each row is a delivery record:
its objective, reason, accepted decision and closure evidence are required before
status can change. Existing BUG closures remain only in `FIXED_ITEMS.md`.

| ID / status | Objective | Reason | Accepted decision and closure evidence |
|---|---|---|---|
| PA-D01 / First slice implemented 2026-10-20 | Durable goals, steps, leases, budgets, recovery and final outcome assessment. | A chat transcript cannot continue an outcome safely across sessions, workers or restarts. | Reuse task/runtime records under one coordinator, never a second broker. Close with durable-goal, restart, child-blocker, budget and Stop scenarios. **First slice ([FIXED-1039](FIXED_ITEMS.md#fixed-1039--an-outcome-could-live-only-in-a-chat-transcript-there-was-no-durable-goal-goal-01-pa-d01) to [FIXED-1048](FIXED_ITEMS.md#fixed-1048--a-goal-had-no-budget-across-its-steps-goal-10-pa-d01))**: owner-scoped goals with criteria, an acyclic plan of steps and compare-and-set revisions; the ten states with server-served actions and named waiting reasons; Start files due steps as ordinary governed tasks and the scheduler tick carries the plan forward; completion only from per-criterion evidence (*its steps finished* or *confirmed by you*); Stop through the task interrupt cascade; Pause/Resume with revalidation; step-run and cost budgets reserved before dispatch and reconciled from the usage ledger. Live RT-GOAL-01 to RT-GOAL-07. **Remaining ([BUG-355](TO_BE_FIXED.md#bug-355--goals-ship-without-intake-from-chat-validator-backed-criteria-or-a-restart-scenario))**: intake from Chat, Build-verified and other validator-backed criteria, durable step leases beyond the task claim, and the host-restart scenario. |
| PA-D02 / First slice implemented 2026-10-20 | Settings-owned execution profiles across local, hybrid and cloud model use. | Owners without capable local hardware need practical approved cloud models without silent data/host fallback or per-turn firewall configuration. | Profiles constrain providers/models, host, data classes, egress, retention, budget and approvals; prompts cannot change them. Close with blocked-profile, allowed-cloud, local-only and profile-change/revalidation scenarios. **First slice ([FIXED-1049](FIXED_ITEMS.md#fixed-1049--there-was-nowhere-to-say-where-a-goals-work-may-run-prof-01-pa-d02) to [FIXED-1051](FIXED_ITEMS.md#fixed-1051--changing-the-boundary-would-have-applied-silently-to-work-in-flight-prof-03-pa-d02))**: versioned profiles made only in **Settings → Execution profiles** from Private local, Balanced or Cloud-first, with model placement, providers, memory-to-hosted and budgets; every model in the selected-plus-fallback chain judged before dispatch and before run; memory withheld from hosted steps where the profile says so; a change pauses goals at a safe boundary; project binding. All four closure scenarios pass live. **Remaining ([BUG-356](TO_BE_FIXED.md#bug-356--execution-profiles-govern-goal-steps-only-and-cover-one-data-class))**: profiles bound goal steps only — ordinary Chat, Build and scheduled tasks are unchanged — and cover models and memory, not hosts, attachments, research references, egress or retention. |
| PA-D03 / Planned | Correctable personal memory and explicit profile context. | Durable autonomy needs useful context, but memory must not become hidden authority or irreversible inference. | Preserve source, scope, freshness, sensitivity, correction and deletion; profile controls cloud eligibility. Close with stale/conflicting/corrected/forgotten-memory tests. |
| PA-D04 / Planned | Opt-in standing intents and useful proactivity. | The agent must continue helpful work without noisy, duplicate or unbounded background activity. | Reuse the scheduler with source validation, cooldown, deduplication, quiet hours and daily budgets. Close with no-change, useful-change, DST, host-offline and hostile-trigger cases. |
| PA-D05 / Planned | Verified connected actions and browser fallback. | A personal agent must do more than draft text, but effects require exact destinations, receipt/reconciliation and safe isolation. | Model typed connector effects first; use an isolated bounded browser only where no connector exists. Close with account/destination, changed-payload, timeout, revoke, redirect and injection tests. |
| PA-D06 / Partly implemented 2026-10-20 | One owner-visible UX for intake, goals, approvals, progress, results, context and recovery. | Continuous autonomy fails if the owner cannot understand scope, intervene or find a usable result. | Extend existing Home/Chat/Build/Design/Tasks/Approvals rather than add a parallel mode; implement the UX-01–UX-12 decisions: truthful state read models, outcome intake, goals, concrete approvals, schedule readiness, results, context, recovery, continuity and accessibility. Close with first-user and assistive-technology scenarios. **Slice ([FIXED-1052](FIXED_ITEMS.md#fixed-1052--goals-had-no-page-ux-goals-01-pa-d06), [FIXED-1053](FIXED_ITEMS.md#fixed-1053--home-could-not-say-which-outcomes-needed-the-owner-ux-goals-02-pa-d06))**: **Work → Goals** (intake, list, detail with criteria evidence, steps, task links, read-only profile, budget and the server's own actions) and Home's Goals board (needs you, in progress, finished). Outcome intake from Chat, results view, context inspection and the first-user and assistive-technology scenarios remain. |
| PA-D07 / Planned | Paired-channel and private-host continuity. | Useful long-running outcomes need explicit availability and safe reach beyond one foreground device. | Use authenticated paired channels and an owner-selected always-on private host; no availability fiction. Close with sender spoof/replay, offline/reconnect, remote Stop and missed-run cases. |
| PA-D08 / Planned | Reviewed learning and reusable skills. | Verified work should improve future work without letting the agent rewrite policy or self-grant tools. | Propose versioned skills from verified outcomes, evaluate fixtures/permission diff, then require owner activation and revocation. Close with poisoned skill, capability increase, rollback, fresh-fixture, regression-replay, quarantine/restore and failure-recall cases ([SELF_IMPROVEMENT_MODEL.md](../architecture/SELF_IMPROVEMENT_MODEL.md) sections 6–9, 11). |
| PA-D09 / Planned | Runtime integrity and security-depth improvements. | More autonomy widens impact unless policy, identity, audit, credentials, execution and extension boundaries remain inspectable. | Consolidates ADD-04–10 and ADD-12–18: transaction lineage/Stop, policy-as-code, replay, context tiering, credential sanitisation, micro-VM evaluation, MCP supply-chain controls, optional hardware root/step-up, safety critic/debate and future multi-principal boundaries. Each remains separately scoped and may not weaken owner authority. Close through targeted threat, recovery, conformance and owner-decision evidence. |
| PA-D10 / Planned | Governed browser and interactive extension surfaces. | Browser and third-party UI unlock real tasks but can become an authority bypass. | Consolidates ADD-23/24: typed browser operations, isolated sessions, egress and secret-safe handoff; sandboxed server-contributed UI under the existing broker. Close with malicious-page, redirect, malformed-extension and revocation tests. |
| PA-D11 / Planned | Cross-surface outcome evidence and honest comparative claims. | Capability lists do not establish that a person receives a completed result. | Use identical declared fixtures, independent validators and retained traces for personal-agent, competitor and release claims. Close only through the Testing protocol. |
| PA-D12 / Implemented/archival foundations | Preserve governed container execution, sequential tool decisions, agent identity, structured questions, skills interoperability and adaptive shell foundations. | These completed foundations remain prerequisites, not open work. | Retain their current contracts/tests and their closure evidence in `FIXED_ITEMS.md`; do not relabel them as planned work. |
