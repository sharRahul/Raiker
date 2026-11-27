# Approval process redesign

**Status:** approved design, implementation active. **Owner:** release owner.
Approved 2026-11-26, including the explicit direction that this applies to
Chat, Build, Design and every other workflow. This plan owns the authorization
redesign; [Ready to use](READY_TO_USE_PLAN.md) retains release qualification.

## Contract

The default is autonomous work inside a verified sandbox, with approval
before consequential effects. Read-only and Ask first remain available.
The same rules apply to Chat, Build, Design, goals, schedules, connectors,
MCP and delegated execution. A surface or model cannot grant authority.

An enabled capability is availability, not approval for every effect. An
authorization is one of **Allowed**, **Needs your decision**, or **Blocked**.
The broker and the runtime must use the same decision rule, with a fresh
execution-time check. Model risk labels and text never prove confinement.

Inside an authenticated task's disposable copy, approved reads, file edits
and commands can proceed without a prompt while containment, owner limits
and the capability remain valid. The real project changes only after Apply.
Without a verified boundary, execution is blocked with setup guidance; no
unrestricted fallback is offered. Explicit turn Ask/Deny and standing denials
continue to tighten the result.

Consequential effects ask by default: Apply to the real project, push,
send/publish, calendar mutations, purchases/payments, durable memory changes,
installation outside the copy, and new data access or network destinations.
Already approved model/provider budgets and normal internal task/audit/draft
bookkeeping are not re-approved for every step. Unknown effects fail closed.

## Decisions and delegation

Cards show the concrete effect, account/destination, exact content/diff,
limits, and why a decision is needed. Responses are **Approve once**,
**Allow for this task…** when a bounded grant is applicable, and
**Don't do this**. Later defers without authorizing or rejecting.

One-time approval is bound to the reviewed payload and target. Task grants
name operations/resources, have an expiry, remain revocable and end with
their task. Critical effects require live human confirmation and never gain
reusable approval. Broad recurring delegation remains an explicit Permissions
operation. An old Skip/Auto configuration must not silently become a grant.
Existing explicit denials are retained during migration.

Chat, Build, Design and the inbox render the same approval state and actions.
An approval is not an execution receipt: Waiting, Approved, Running,
Succeeded, Failed and Outcome unknown remain distinct. Eligible work resumes
automatically. Changed payloads, targets, permissions or expired authority
require revalidation. Execution is atomically claimed; uncertain external
effects are reconciled before retry, not asserted to be exactly once.

## Implementation plan

**Goal:** consistent authorization and approval lifecycle across all workflows.
**Architecture:** reuse RuntimeAuthority, the approval store, existing bounded
grants, payload hashes and suspended-turn claims. Extract a shared decision
rule instead of adding another permission system. Server-derived task-copy
evidence authorizes preparation; the executor rechecks containment.
**Tech stack:** Python, SQLite/SQLCipher, Svelte/TypeScript, pytest, Vitest and
Playwright. No new runtime dependency; one agent, inline execution.

### A1 — Shared authorization decision

Files: `raiker/runtime/authority/preparation.py`,
`raiker/runtime/authority/router.py`, `raiker/tools/broker.py`,
`tests/test_approval_authorization.py`.

Interface: RuntimeAuthority's existing governed result records decision and
reason. Shared `ordinary_approval` and `confined_preparation` checks establish
which policy pause a runtime-derived scope can satisfy. Review does not execute
or spend authority; dispatch rechecks it. Model arguments never supply proof.

- [x] Write failing behavior tests: a verified copied edit executes; the real
  source is unchanged; an outside write asks; false/unread proof blocks code;
  Ask/Deny, revoked grants, critical actions and egress remain restrictive.
- [x] Run the regression before implementation and observe the missing result.
- [x] Implement the shared evaluator and connect both broker and runtime;
  remove the broker's independent interpretation of ordinary approval.
- [x] Re-run authorization, critical, grant, machine-identity and approval-mode
  suites. Every executed effect must have a real result and audit basis.

### A2 — Scope and default across every workflow

Files: `raiker/runtime/orchestrator.py`, `raiker/execution/task_tree.py`,
`raiker/api/routes_approvals.py`, approval-mode schemas/defaults,
`tests/test_task_tree.py`, prompt/scheduler/Design integration tests.

- [x] Add failing tests parametrized across Chat/Build/Design/task origins;
  no-project tasks must also prepare in a disposable copy.
- [x] Bind trusted task roots before the first write/command and recheck them
  at execution. Keep workspace/protected-path, links and cross-owner refusals.
- [x] Introduce the autonomous sandbox default through the common prompt
  configuration; translate legacy modes conservatively and preserve explicit
  owner denials. No surface-specific authorization exception is permitted.
- [ ] Verify mixed action turns, cold start, revocation, sandbox loss,
  scheduled/headless work and continuation through the common gateway.

### A3 — Shared owner decision and lifecycle

Files: `web/src/lib/approvalMode.ts`, shared approval presentation/actions,
`ApprovalPrompt.svelte`, `ApprovalsView.svelte`, Chat/Build/Design consumers,
matching Vitest suites and API read-model contracts when needed.

- [ ] Add failing tests for the three actions, bounded task grant eligibility,
  one shared pending decision and separate decision/execution states.
- [x] Replace conflicting Skip/Auto controls with consistent authority and
  unattended handling. Keep technical details behind disclosure.
- [x] Use the same presentation/actions for inline cards and the inbox;
  preserve immutable previews, expiry, step-up and automatic continuation.
- [ ] Test changed-payload refusal, concurrent tabs, lost execution response,
  restart, keyboard use, 390 px and light/dark views.

### A4 — Qualification, documentation and delivery

- [ ] Run real Chat, Build and Design preparation-to-consequence journeys;
  ordinary in-copy work proceeds and the final consequential effect asks.
- [x] Run the WSL2 Build regression and inspect the source/copy and real check
  receipts. Record screenshots and failed/unavailable cases honestly.
- [ ] Update the user guide, live-test record, fixed/open ledgers and linked
  readiness plans. Preserve canonical document indexes and anchors.
- [ ] Run relevant Python/TypeScript/native checks, commit and push, then
  monitor every triggered GitHub workflow to completion and resolve failures.

## Reference decisions

Primary references reviewed 2026-11-26:

* [OpenAI / ChatGPT](https://learn.chatgpt.com/docs/agent-approvals-security):
  keep technical containment separate from consent.
* [Claude](https://code.claude.com/docs/en/permissions): scoped rules and
  bounded sandbox auto-allow, with explicit restrictions retained.
* [Cursor](https://cursor.com/docs/agent/security): distinguish best-effort
  approval guardrails from an enforced boundary.
* [Meta Muse](https://www.meta.com/en-gb/help/superintelligence/1385290430137537/):
  readable effect approval and explicit scopes.
* [Perplexity](https://www.perplexity.ai/changelog/deep-research-command-panel-forking-inline-actions-and-enterprise-controls):
  contextual confirmations with one place for the owner's response.
* [Hermes source](https://github.com/NousResearch/hermes-agent/blob/main/tools/approval.py):
  shared decision handling and explicit session/transport lifetimes.

Raiker retains deterministic enforcement, encrypted records and critical
confirmation. A classifier, model instruction or trusted-looking transcript
is not an authorization source.

## Implementation evidence — 2026-11-27

The common broker/runtime path now supports the sandbox posture, including
unattended preparation. Tests cover all three prompt surfaces without a
project, copied writes across tool origins, outside writes, false/missing
proof, owner/session mismatches, explicit restrictions and authorized failures.
Commands retain the machine actor but use the session owner's copy. A measured
WSL2 run exposed and a regression reproduced separate copies for an attached
project outside the data folder; default command routing now uses that trusted
project binding. Grant use is claimed with a compare-and-swap against the
reviewed counter, limits, expiry and revocation before execution.

Approval controls share one button component across inline cards, the global
prompt and inbox. Legacy Auto maps to confined preparation; Skip maps to manual.
Setup reads measured enforcement before selecting the sandbox default and
does not replace a choice the owner has already made.

The real WSL2 runtime and model-driven Build preparation/check journey passed;
the Chat/inbox browser case passed at desktop and 390 px. Screenshots and exact
evidence are in the [live record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-27-shared-approval-redesign).
Local task drafts are eligible internal bookkeeping; scheduling or starting
them still requires its ordinary authority. Full consequence journeys, Design
live qualification and the remaining lifecycle/accessibility cases stay open.
