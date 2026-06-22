# Functional UI Test Scenarios

> Planning document. End-to-end **functional test scenarios** for the governed-agent UI, covering
> the 14 primary workflows. Each scenario is **runnable manually now** and **automatable later**
> (Playwright/component tests in M7 reference these scenario IDs, e.g. `FT-03`). Expected backend
> events use **real** event types. Negative-path scenarios cross-reference `05_TEST_MATRIX.md`.
>
> **Truthfulness:** scenarios must observe the real runtime. With the `mock-test` model profile the
> turn loop is deterministic; **no hosted calls, no fake runtime success, sensitive domains stay
> disabled.** A scenario that can only pass by faking backend state is invalid.

## Seed / fixtures (deterministic local setup)

Preconditions shared by all scenarios:
1. Fresh workspace; bootstrap an owner principal (existing `bootstrap_owner` /
   `resolve_local_principal` path). This creates the owner + `runtime_gate_manager` role.
2. Launch the local API (`apps/api/main.py`, bound `127.0.0.1`).
3. Mint a token via `POST /api/auth/session` (owner) and load the SPA.
4. Model profile = `mock-test` (deterministic); hosted providers remain policy-gated/unavailable.
5. All Tier 2–6 capability gates remain at their default **disabled/deferred** state.

Test data helpers: reuse pytest fixtures noted in the repo (`bootstrapped_workspace`,
`ApprovalInbox`, `EventViewer`, `CheckpointService`) for the automated layer.

## Scenarios

| ID | Workflow | Preconditions | Steps | Expected UI state | Expected backend events |
|---|---|---|---|---|---|
| FT-01 | Start/resume a session | seed done | Open Home; start a new session; reopen it | Session appears in list; resuming shows prior turns | session/turn rows present (read) |
| FT-02 | Submit a prompt | session open, `mock-test` | Type a prompt, Send | Timeline shows the turn; status → completed | `prompt_received` → … → `turn_closed` |
| FT-03 | gather→plan→act→verify | FT-02 | Watch the streamed timeline | 4 phase rows with status + timestamps | `plan_created`, `policy_decision`, `verification_completed` |
| FT-04 | Model/provider status | seed done | Open Models | Current profile shown; "no silent hosted fallback" note; hosted = unavailable/deferred | model profile read |
| FT-05 | Tool proposal preview | prompt that proposes a file write | Submit; open the `ActionProposalCard` | Card shows tool, risk, affected files, diff, `Approval-required` | `action_proposed`, `policy_decision`, `approval_requested` |
| FT-06 | Approve an action (metadata-only) | FT-05 pending approval | Open Approvals → approve with reason | Banner "metadata-only; not executed"; status → approved; **no execution** | `approval_received`; `executes_action=false` |
| FT-07 | Deny an action | FT-05 pending approval | Deny with reason | Status → denied | `approval_denied` |
| FT-08 | Policy decision + risk view | FT-05 | Open the proposal's policy detail | Risk level + plain-English policy reason shown | `policy_decision` payload rendered |
| FT-09 | Capability-gate status | seed done | Open Capabilities | Matrix grouped by domain/tier; Tier 2–6 show Disabled/Deferred; explainer available | gate reads |
| FT-10 | Runtime-mode status | seed done | Open Runtime Gates | Current mode + `allowed_transitions`; read-only | runtime-mode read |
| FT-11 | Checkpoints / rewind metadata | after FT-02 | Open Checkpoints | Checkpoint for the turn with metadata; rewind shown as metadata only | checkpoint read (`checkpoint_created` exists) |
| FT-12 | Audit / event log | after FT-02 | Open Events; filter by turn | Append-only events for the turn; filters work | event reads |
| FT-13 | Diagnostics / readiness | seed done | Open Diagnostics | Readiness matches `/api/runtime-readiness`; disabled caps + provider health listed; local-only scope note | diagnostics read |
| FT-14 | Disabled/deferred display | seed done | Inspect a sensitive domain (e.g. `email_runtime`) in Capabilities | Shows Deferred + explainer (status, why, what's required, future/deferred) | none (read) |

## Negative-path scenarios (governance proofs)

| ID | Scenario | Steps | Expected | Matrix ref |
|---|---|---|---|---|
| FT-N1 | Enable a fail-closed cap | Security Settings → step-up → enable `shell_execution` | Blocked; explainer `activation_blocked:no_executor`; not enabled | #2 |
| FT-N2 | Gate change as AI principal | Mint/use an AI principal; attempt a gate mutation | `403 ai_cannot_manage_runtime_gates`; plain-English message | #7 |
| FT-N3 | STOP a running task | Start a task; press STOP; confirm | Cancels at safe boundary; events shown | #6 |
| FT-N4 | STOP as AI principal | AI principal calls interrupt | 403 | #8 |
| FT-N5 | Self-approve as AI | AI principal resolves its own approval | Denied (`ai_cannot_approve_own_action`) | #9 |
| FT-N6 | Token storage check | Inspect browser storage after login | Token not in localStorage/sessionStorage | #10 |
| FT-N7 | Secret Settings | Open Secret Settings | Read-only; "secret storage not implemented (deferred)"; no input | #12 |

## Automation notes (M7)
- Drive scenarios via Playwright against the local server with the `mock-test` profile.
- Each automated test asserts both **UI state** and the **emitted events** (via `GET /api/events`),
  so a green UI that didn't actually exercise the governed path still fails.
- Negative-path tests assert the **backend** denial (status + `reason_code`), independent of the UI.
