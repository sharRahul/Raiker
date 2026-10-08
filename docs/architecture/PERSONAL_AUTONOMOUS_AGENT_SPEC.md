# Personal autonomous-agent architecture

## Decision and scope

**Accepted product and architecture direction: 2026-10-07. Implementation is
staged and separately evidenced.** Raiker should be a personal autonomous agent
that understands an owner's context, accepts outcome-based goals, plans and
executes bounded work, continues across sessions, and verifies useful results.
Its assistant, coding/build agent and extensible platform remain part of one
product. See [ADR-0001](../adr/ADR-0001-personal-autonomous-agent.md).

Autonomy means independently choosing and completing steps within delegated
scope. It does not grant new capability permissions, change defaults, or
approve actions. A suggestion, memory, schedule, project or connector connection
is never authority. Preserve the owner-authoritative, monitored posture in
[Security and policy](SECURITY_AND_POLICY.md).

This specification defines the target. [Implementation status](IMPLEMENTATION_STATUS.md)
remains authoritative for shipped features, and the
[delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md) owns PAA work
and acceptance gates. No new goal API, database table, event or browser executor
is implemented by this documentation change.

## Reference ideas and Raiker adaptations

These are design inspirations from primary documentation checked on 2026-10-07,
not code audits, parity claims or a promise to reproduce every feature.

| Reference and source | Idea to adopt | Adaptation for Raiker | Acceptance owner |
|---|---|---|---|
| [Muse product](https://ai.meta.com/muse/) | Delegate a goal and keep progress moving across sessions | Durable goal with success criteria, plan revisions, task links and confirmed outcomes | PAA-01/02/08 |
| [Muse connector guidelines](https://muse.ai/platform/docs) | Finish workflows, show the concrete effect, distinguish pending from confirmed, recover without duplicate effects | Typed effect contracts, account/destination-bound approvals, provider receipts and reconciliation | PAA-05/08 |
| [Claude projects](https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork) | Reuse files, instructions and work context in projects | Reuse Raiker projects and personal context; distinguish filing from retrieval scope | PAA-03/07 |
| [Claude scheduled tasks](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork) | Recurring work produces finished outputs with connected tools | Extend the existing scheduler and task threads; identify the actual host that must be running | PAA-04/07 |
| [Claude skills](https://support.claude.com/en/articles/12512176-what-are-skills) | Package repeatable procedures and load relevant context progressively | Versioned instruction-only skills with reviewed tool dependencies and owner activation | PAA-09 |
| [OpenClaw heartbeat](https://docs.openclaw.ai/gateway/heartbeat) | Proactive checks can stay quiet when there is nothing useful to report | Opt-in standing intent with bounded polling, deduplication and usefulness measurement | PAA-04 |
| [OpenClaw automation](https://docs.openclaw.ai/automation/cron-jobs) and [channels](https://docs.openclaw.ai/channels) | Persistent gateway, scheduled work and delivery through familiar channels | Reuse the Raiker host, scheduler and authenticated channel gateway; preserve sender and target checks | PAA-04/10 |
| [Hermes memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/) | Personal context and past work improve later tasks | Governed preferences and episodes with provenance, freshness, correction and deletion | PAA-03 |
| [Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/) | Successful work becomes reusable procedural knowledge | Propose a skill from a verified outcome, evaluate it and review its authority before activation | PAA-09 |

Claude's current help pages describe a gradual unified Claude experience and
remote scheduling, with older locally scheduled tasks retaining their host.
Record the exact surface, plan and execution host in any comparison. Raiker's
local scheduler does not inherit another product's remote availability.
Muse's persistent VM is inspiration for continuity, not evidence that Raiker
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
   starts an ordinary gateway turn. Context is data, never authority.
5. Each tool call uses existing broker, policy, RuntimeAuthority, credential and
   executor boundaries. A child receives no greater authority than its parent.
6. Receipts and independent checks update progress. Approvals and questions
   park only dependent work; independent steps may continue within scope.
7. The goal finishes only when every mandatory criterion has evidence, or it
   records partial/blocked/failed/stopped status with preserved progress.
8. Delivery is a separate outcome. A lost notification never re-executes work.

The coordinator must be model-independent for claims, leases, budgets, policy
and terminal decisions. Models may propose plans and revisions. Owner choices
or consequential scope changes require the existing governing decision path.

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
A restart revalidates owner, goal/envelope version, revocation, model readiness,
executor and lease before continuing. Do not reuse an expired turn token.

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
approval lifecycle remain authoritative; Muse permission defaults are not copied.

## User experience and learning

Use the existing Chat/Build/Tasks/Projects/Approvals/Activity surfaces. The target
adds goal progress and references instead of requiring an additional work mode.
A home overview should answer: what is progressing, what needs my decision,
what finished, what failed and why, and what is due next. A goal details view
shows criteria, plan, task tree, sources, receipts, budgets, pause/resume/stop
and next action. Keep implementation details out of routine user decisions.

A verified workflow may produce a proposed reusable skill. It carries sources,
version, fixtures, validators, tool dependencies and a permission diff. Evaluate
it before owner review/activation; rollback or revoke it independently. Learning
never rewrites policy, silently broadens permissions or installs model-authored
code. Instruction-only Raiker skills remain distinct from governed script tools.

## Acceptance and claim rule

PAA-01–PAA-11 in the [delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md)
are the rollout gates. Use existing CR evidence levels, preserve older live
records, and run identical declared scenarios on exact supported reference
surfaces before asserting parity. No benchmark was performed for this update.
Release wording remains “personal-agent direction” until the relevant goal,
background, integration, memory and recovery scenarios have end-to-end evidence.

## Detailed UI and UX implementation decisions — 2026-10-08

The [UX specification](PERSONAL_AGENT_UX_SPEC.md) and
[UX-01–UX-12 task plan](../plans/PERSONAL_AGENT_UX_IMPLEMENTATION_PLAN.md) make the
user-experience target implementable. They define outcome intake, Home sections,
goal criteria/tasks, concrete approvals, schedule/host readiness, usable results,
inspectable personal context, supported recovery, continuity and accessibility.
PAA-07 retains outcome ownership; PAA-01/02/03/04/05/08/10 supply actual data and
authority dependencies. No UI infers completion, readiness or allowed actions
from model prose. Goal controls wait for backend contracts; existing work modes,
model choice, lifecycle and permission decisions remain.
