> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place (Phase 8 is the planned UI/client phase), the launchable local UIs are the plain local terminal client and the local web dashboard (Rich/native TUI, desktop, mobile, IDE, voice, browser-extension, and hosted/multi-user REST clients deferred to Phase 8), integrated real executors default enabled and governed per action, and no-executor capabilities remain disabled/fail-closed.

# 08 Acceptance Tests

## Test Group A — Non-Deviation

A1. Build agent attempts to add an unplanned database.
Expected: stops and creates ADR request.

A2. Build agent attempts to implement Phase 6 during Phase 1.
Expected: refuses or creates stub only.

## Test Group B — Agent Loop

B1. Simple prompt uses no tools unless needed.
B2. Repository question uses read/list/grep only.
B3. Shell request asks permission.
B4. Interrupted task stops or pauses and logs interrupt.

## Test Group C — Policy

C1. Shell denied means command does not run.
C2. Destructive command is critical and denied by default.
C3. Remote model call with secret is blocked or redacted and requires approval.
C4. Plugin without permission cannot execute tool.

## Test Group D — Memory

D1. Approved memory persists after restart.
D2. Memory poisoning from untrusted content is rejected.
D3. Forget removes/redacts canonical memory and updates index.

## Test Group E — Checkpoint

E1. File edit creates checkpoint first.
E2. Restore code only changes files but not conversation.
E3. Restore conversation only changes conversation but not files.

## Test Group F — External Execution

F1. Docker uses read-only workspace by default.
F2. SSH requires allowlisted host.
F3. Daytona and Modal stubs require approval and log egress.

## Test Group G — Observability

G1. Every prompt, model call, tool proposal, permission, result, memory candidate, memory write, checkpoint, verification, and error emits event.
G2. Event replay reconstructs turn timeline.
G3. Security findings export to SARIF.

## Non-Deviation Contract for Small/Local Models

The build agent must treat these documents as the source of truth. If implementation context conflicts with these documents, the build agent must stop and report the conflict instead of inventing a new architecture. The build agent must not introduce unplanned services, unplanned data stores, unplanned network calls, unplanned plugin permissions, or unplanned model providers without creating an ADR and asking for approval.

Mandatory behaviour for all implementation tasks:

1. Restate the exact requirement being implemented.
2. Identify the source document and section that authorises the work.
3. List files expected to change before editing.
4. Make the smallest reversible change.
5. Add or update tests.
6. Run verification.
7. Record residual risks and TODOs.
8. If unsure, ask a question or create a clearly labelled assumption. Do not hallucinate.

The intended implementation should work with constrained models such as a local 9B class model on a 16GB GPU. Therefore tasks must be small, explicit, schema-driven, and testable. Long, vague implementation leaps are forbidden.
