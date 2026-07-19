# Threat Model — Approval Execution Relay (Workstream A, Slice A1)

> Status marker: real executor (`approval_execution_relay`), Tier 1, integrated
> and governed per action. This slice (A1 — **immutable approval intent**)
> hardens the relay's execution-time verification; executor dispatch beyond
> `write_file` (A2/A3) and posture hooks (A4) are separate slices.

Per-capability threat model tracking the relay's execution-time defenses. The
relay is `raiker/runtime/executors/tier1_approval.py::ApprovalExecutionRelay`.

## What this capability is

`ApprovalExecutionRelay` turns a previously-recorded, human-approved action into
an actual execution. It is reached only through
`RuntimeAuthority.route_action()` — the single chokepoint — with an
`approval_execution_relay` governed action whose only argument is an
`approval_id`. The relay:

1. loads the approval and its joined tool action from SQLite (never trusting
   caller-supplied arguments);
2. verifies the approval is still `pending`, still within its TTL, and that the
   action payload has not drifted since approval;
3. resolves the approval to `approved` and performs the underlying write.

The immutable **approval intent** is captured at creation time by
`SQLiteStore.insert_approval`: a `action_payload_sha256` over the canonical
`{tool_name, arguments, risk_level}` payload, plus an `expires_at` TTL
(default 24h).

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Governed entry only | Executor runs only when `route_action()` returns `decision="allow"` — every gate/policy/risk check has already passed. |
| Immutable arguments (TOCTOU) | At execution the relay recomputes `tool_action_payload_sha256` from the tool action *as it stands now* and compares it to the hash stored at approval time. Any drift → `approval_payload_tampered`, no write, approval left `pending`. |
| Bounded lifetime | An approval past `expires_at` resolves to `expired` (via `expire_approval`, guarded on `status='pending'`) and never executes → `approval_expired`. Default TTL 24h. |
| Single resolution | `resolve_approval` / `expire_approval` both carry `WHERE status='pending'`; a resolved approval cannot be re-resolved or re-run. |
| Workspace confinement | Writes go through `resolve_workspace_path()`, which rejects paths outside the workspace root. |
| Metadata-only results | `ExecutionResult` carries only `summary` and metadata `artifacts` (approval_id, path, size_bytes) — never raw file contents. |

## Threats

- **T1 — TOCTOU: arguments mutated between approval and execution.** A human
  approves `write_file safe.txt`; the stored tool action is then altered to
  `write_file evil.txt` before the relay runs. Mitigated: the relay recomputes
  the payload hash and refuses on mismatch (`approval_payload_tampered`); the
  approval stays `pending` and nothing is written. Covered by
  `tests/test_approval_relay_general.py::test_relay_refuses_tampered_payload`.
- **T2 — Stale approval executed long after the fact.** An approval sits
  unresolved indefinitely and is later replayed. Mitigated: a bounded TTL means
  an unresolved approval's resting state becomes `expired`; the relay refuses it
  (`approval_expired`) and marks it expired. Covered by
  `test_relay_refuses_and_expires_stale_approval`. The metadata-only resolution
  path (`ApprovalInbox.resolve`) enforces the same TTL, surfaced by the API as
  HTTP 409 `approval_expired`
  (`tests/test_api_approvals.py::test_expired_approval_rejected`).
- **T3 — Double execution of one approval.** Mitigated: resolution transitions
  guard on `status='pending'`; a second relay call sees a non-pending status and
  returns `approval_already_resolved`. (A2 adds an explicit
  `pending → executing → executed` transition for stronger single-execution
  under concurrency.)
- **T4 — File contents leaked into the audit log.** Mitigated: results are
  metadata-only.
- **T5 — Execution without a registered executor.** Mitigated by fail-closed
  handling upstream in `route_action` (`execution_unavailable:no_executor`).

## What A1 explicitly does not cover

- Executor dispatch for capabilities beyond the `write_file` shape (A2/A3).
- Atomic single-execution nonce / `executing` state under concurrency (A2).
- Posture snapshot + revoked-session denial on the relay (A4).
- Batch/blanket approval of heterogeneous actions (out of scope for Workstream A).
