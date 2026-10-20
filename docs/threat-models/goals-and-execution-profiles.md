# Threat model — durable goals and execution profiles

**Shipped 2026-10-20 as the first slices of PA-D01 and PA-D02** of the
[personal-agent specification](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md). A
goal carries an outcome across sessions; its steps run as ordinary tasks. An
execution profile is the Settings-owned ceiling on which models a goal's work
may reach and whether personal memory travels with it.

The coordinator adds no tool, no grant and no executor. What it adds is
*continuity*: work the owner started keeps being filed after they leave. That
is the property this review is about.

## What the code does

| Step | Function | Behaviour |
|---|---|---|
| Intake | `routes_goals.create_goal`, `store.clean_plan` | Human-only; a draft has no permission to run; steps depend only on earlier steps, so there is no cycle |
| Accept | `GoalCoordinator.accept` | Needs a required criterion, a step and a configured model; pins the profile Settings binds, by id and version |
| File a step | `GoalCoordinator.advance`, `_dispatch` | Reserves a step run compared-and-set, judges the goal's model and every fallback against the profile, files an ordinary task through `DashboardService.create_task` |
| Run a step | `TaskScheduler._run_claimed_task` → `GoalCoordinator.guard_task` | Re-checks the goal is running and the chain is inside the profile just before the turn; otherwise the task is cancelled unstarted |
| Withhold memory | `store.withhold_session_memory`, `ContextGatherer._memory_disclosure`, `ToolBroker` | A hosted-capable step under a profile that keeps memory local recalls nothing and the memory tools answer `withheld` |
| Assess | `GoalCoordinator._assess` | Completed only when every required criterion has evidence: its steps finished, or the owner confirmed it |
| Stop / Pause | `GoalCoordinator.stop`, `pause` | Stop through `InterruptController` with its cascade; Pause parks unclaimed steps |

## Assets

| Asset | Why it matters |
|---|---|
| Owner authority | A goal keeps filing work; it must never decide to start, widen or resume itself |
| The model boundary | An owner who chose *Private local* has said nothing may reach a hosted provider |
| Personal memory | Facts the owner approved for local recall, not for every hosted model a step might use |
| Budget | Unattended continuation is unattended spend |
| The audit trail | What ran, under which profile version, and who decided |

## Trust boundaries

1. **Owner session → goal routes.** Every mutation is human-only; there is no
   model tool for creating, accepting, starting or resuming a goal, or for
   changing a profile.
2. **Coordinator → task runtime.** A step is filed as an ordinary task. From
   there the policy engine, broker, approvals and runtime authority apply
   exactly as to a task the owner filed by hand.
3. **Settings → profile → every dispatch.** A profile change is a new version;
   work pinned to the old one pauses.
4. **Step output → goal state.** A step's text never changes the goal. Only a
   task's recorded status and the owner's confirmation do.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| A prompt, memory, connector or step's own output creates, starts or resumes a goal | No tool exists for it; the routes are human-only (`require_human`) | `raiker/api/routes_goals.py` |
| A goal's steps gain authority a hand-filed task would not have | Steps are created through the same `create_task` path with the owner's principal; no grant, decision mode or approval is set by the coordinator | `GoalCoordinator._dispatch` |
| A local-only goal reaches a hosted model through the owner's fallback sequence | Every entry of the selected-plus-fallback chain is judged; an unresolvable entry reads as disallowed, never as local | `profiles.model_chain`, `chain_refusal` |
| The owner changes their default model or fallbacks after a step was filed | The scheduler re-checks the chain just before the run and cancels the unstarted task; the run is refunded and the goal waits | `GoalCoordinator.guard_task` |
| A step runs on whatever an empty selection resolves to | A goal must name a configured model before it is accepted ([FIXED-1054](../plans/FIXED_ITEMS.md#fixed-1054--a-goals-steps-ran-on-whatever-an-empty-model-selection-resolved-to)) | `GoalCoordinator.accept` |
| Personal memory goes to a hosted model under *Balanced* | The step's conversation is marked; ambient recall is off and five memory-reading tools answer `withheld`; an unreadable marker withholds | `store.session_memory_withheld`, `ToolBroker._PERSONAL_MEMORY_TOOLS` |
| A profile change silently applies to work in flight | The pinned version is compared on every pass; a mismatch pauses the goal; only Start or Resume adopts the new version, after rechecking it | `GoalCoordinator.advance`, `_revalidate` |
| Two tabs or two passes file the same step twice | The step-run reservation and the step claim are compared-and-set in one transaction | `_dispatch` |
| Unattended spend | Step-run limit reserved before dispatch; cost reconciled from the usage ledger and passed to each step's task as its own per-run limit | `_budget_exhausted`, `_dispatch` |
| A model's answer claims the goal is done | Completion is read from task status and owner confirmation only | `_auto_evidence`, `_assess` |
| Stop leaves delegated work running | Stop goes through `InterruptController` with its delegation cascade; the scheduler will not run a step of a goal that is not running | `stop`, `guard_task` |
| Audit events vanish | Every event type is declared in `EVENT_TYPES` and a test reads them back ([FIXED-1056](../plans/FIXED_ITEMS.md#fixed-1056--goal-and-profile-audit-events-would-have-been-dropped-without-a-word)) | `raiker/contracts/models.py` |
| The audit log becomes a copy of the owner's plans | Events carry ids, states, reasons and counts; the step's instruction stays in its task | `GoalCoordinator._audit` |

## Residual risk, stated plainly

- **Profiles bound goal steps only.** Ordinary Chat, Build and scheduled tasks
  are not held to the active profile yet
  ([BUG-356](../plans/TO_BE_FIXED.md#bug-356--execution-profiles-govern-goal-steps-only-and-cover-one-data-class)).
- **Placement is a model profile's flag.** A custom OpenAI-compatible endpoint
  reads as hosted even on `localhost` — conservative, so it over-refuses rather
  than leaks.
- **Memory is the only data class.** Attachments, research references and
  selected files are not step inputs yet, so there is nothing else to withhold.
- **Pause does not interrupt a running turn.** A step already running finishes
  its current turn; Stop is the control that ends it.
- **"Its steps finished" is not verification.** It records that the steps
  counting toward a criterion completed; whether the result is good is the
  owner's call through **Confirm met**, until validator-backed criteria land
  ([BUG-355](../plans/TO_BE_FIXED.md#bug-355--goals-ship-without-intake-from-chat-validator-backed-criteria-or-a-restart-scenario)).
- **The host must be running.** A goal advances on the local scheduler's tick;
  there is no off-machine continuation.

## Evidence

- `raiker/goals/` and `raiker/api/routes_goals.py`
- `tests/test_goals_and_execution_profiles.py` — lifecycle, intake, revision,
  owner isolation, profile refusal across the fallback chain, scheduler guard,
  memory withholding, Stop, Pause/Resume revalidation, budgets, audit events
- `web/e2e/goals-execution-profiles-live.spec.ts` — RT-GOAL-01 to RT-GOAL-07
  against hosted Anthropic
