# Threat Model — Approval Execution Relay (Workstream A: A1–A4)

> Status marker: real executor (`approval_execution_relay`), Tier 1, integrated
> and governed per action. Covers A1 (immutable approval intent), A2 (executor
> dispatch + single-execution), A3 (coverage beyond `write_file`), and A4
> (zero-trust posture hooks).

Per-capability threat model tracking the relay's execution-time defenses. The
relay is `raiker/runtime/executors/tier1_approval.py::ApprovalExecutionRelay`.

## What this capability is

`ApprovalExecutionRelay` turns a previously-recorded, human-approved action into
an actual execution. It is reached only through
`RuntimeAuthority.route_action()` — the single chokepoint — with an
`approval_execution_relay` governed action whose only argument is an
`approval_id`. Given that id the relay, in order:

1. loads the approval and its joined tool action from SQLite (never trusting
   caller-supplied arguments);
2. verifies the approval is still `pending`, within its TTL, and that the action
   payload has not drifted since approval (**A1**);
3. captures a posture snapshot and denies if the approving session was revoked
   (**A4**);
4. atomically claims the approval `pending → executing` (**A2** single-execution);
5. re-routes the approved action's `action_type` through `route_action` so the
   target runs under its **own** capability gate, decision mode, and PolicyEngine
   review *at execution time* (**A2/A3**), then resolves `executing → executed`.

The immutable **approval intent** is captured at creation time by
`SQLiteStore.insert_approval`: a `action_payload_sha256` over the canonical
`{tool_name, arguments, risk_level}` payload, plus an `expires_at` TTL
(default 24h).

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Governed entry only | The relay runs only when the outer `route_action()` returns `decision="allow"` for `approval_execution_relay`. `approval_execution_relay` is named in `CAPABILITY_GATE_MAP`, so that outer call really does consult the relay's own gate and decision mode — disabling the gate stops every relayed execution, including the API resolution path. |
| Narrow API entry (BUG-06) | `POST /api/approvals/{id}/resolve` reaches the relay only for `file_write_execution` and `patch_apply_execution` (`raiker/approvals/execution.py::EXECUTABLE_ON_APPROVAL`), and never for a `critical` approval. Every other capability keeps metadata-only resolution, so widening what an ordinary approval can execute is an explicit edit to that frozenset, not a side effect. |
| Protected workspace paths | A relayed file mutation resolves through `resolve_writable_workspace_path`, which refuses the `.raiker/` and `.git/` trees — the encrypted store, audit log, vault key, hook definitions and MCP server scripts. Workspace confinement alone would have handed those over once approved writes became real. Reads are unaffected. |
| Bounded resumption (B2) | Resolving an approval unblocks the turn that proposed the action. The parked conversation is principal-scoped, resumable at most once (status check + atomic `suspended → resuming` claim), and never resumable before the approval is resolved. The result handed back names what actually happened — executed, rejected, or approved-but-not-executed — so a metadata-only capability cannot be mistaken for success. |
| Reversible by construction | `route_action` snapshots the target file's pre-image into the checkpoint blob store before the executor runs, so an approved overwrite can be rewound. |
| Immutable arguments (TOCTOU, A1) | At execution the relay recomputes `tool_action_payload_sha256` from the tool action *as it stands now* and compares it to the hash stored at approval time. Any drift → `approval_payload_tampered`, no execution, approval left `pending`. |
| Bounded lifetime (A1) | An approval past `expires_at` resolves to `expired` (via `expire_approval`, guarded on `status='pending'`) and never executes → `approval_expired`. Default TTL 24h. |
| Execution-time re-governance (A2/A3) | The approved action is re-routed through `RuntimeAuthority.route_action` as the approving human. The **target's** capability gate state, decision mode, PolicyEngine review, and (for Tier-2) the threat-ack-gated enablement all apply *again* at execution time — approval-time state is never trusted. |
| Single execution (A2) | `claim_approval_for_execution` performs an atomic `pending → executing` UPDATE guarded on `status='pending'`; only one caller wins. Success → `finalize_approval_execution(executed)`; a target blocked before any executor ran → `release_approval_claim` back to `pending` (safe retry); a target that ran and failed → terminal `execution_failed` (never re-run). |
| No relay-of-relay (A2) | A target whose capability is `approval_execution_relay` is refused (`relay_target_not_permitted`) — no recursion, no relay approving a relay. |
| Posture / revoked session (A4) | `capture_posture` records principal, session, interface, MFA-enrolment; a revoked approving session denies with `posture_degraded:session_revoked` before any claim or execution. |
| Metadata-only audit (A4) | `approval_executed` / `approval_execution_denied` events carry the posture snapshot and target metadata only — never arguments, file contents, or secrets. |

## Threats

- **T1 — TOCTOU: arguments mutated between approval and execution (A1).** A human
  approves `write_file safe.txt`; the stored tool action is then altered before
  the relay runs. Mitigated: hash recomputation refuses on mismatch
  (`approval_payload_tampered`); the approval stays `pending`. Covered by
  `tests/test_approval_relay_general.py::test_relay_refuses_tampered_payload`.
- **T2 — Stale approval replayed (A1).** Mitigated: a bounded TTL means an
  unresolved approval's resting state becomes `expired`; the relay refuses it
  (`approval_expired`). The metadata-only `ApprovalInbox.resolve` path enforces
  the same TTL, surfaced by the API as HTTP 409 `approval_expired`. Covered by
  `test_relay_refuses_and_expires_stale_approval`,
  `tests/test_api_approvals.py::test_expired_approval_rejected`.
- **T3 — Double execution of one approval (A2).** An approval is relayed twice
  (race or replay). Mitigated: the atomic `pending → executing` claim means the
  loser sees a non-pending row and stops (`approval_already_resolved`); the
  target executes at most once. Covered by `test_relay_executes_at_most_once`,
  `test_relay_rejects_claimed_approval`.
- **T4 — Approval-time gate/policy trusted at execution (A2/A3).** A capability
  is enabled at approval time then disabled before execution (or a policy
  changes). Mitigated: the target is re-governed at execution time; a disabled
  target gate refuses (`target_not_executed:*`) and the claim is released to
  `pending`. Covered by `test_relay_refuses_disabled_target_gate_and_releases`.
- **T5 — Privilege via arbitrary target capability (A3).** The relay only ever
  executes the exact `{tool_name, arguments, risk_level}` the human approved
  (hash-pinned), routed through that capability's own gate/mode/policy. Tier-2
  targets still require their gate to be enabled (which required the threat-ack),
  and critical-risk targets hit the human-confirmation floor in `route_action`:
  they execute via the relay only when accompanied by a one-shot
  `CriticalConfirmation` issued by `resolve_critical_approval` (F7) — the relay
  carries it onto the target but never mints one, so a critical action cannot be
  relayed without a live human's step-up-verified decision. Coverage across
  `apply_patch`, `memory_write`, and Tier-2 `shell` in `test_relay_dispatches_*`;
  critical gating in `tests/test_critical_lifecycle.py`.
- **T6 — Approving session revoked between approval and execution (A4).**
  Mitigated: the posture check denies with `posture_degraded:session_revoked`
  before any claim; the approval remains actionable from a live session. Covered
  by `test_relay_denies_revoked_session`.
- **T7 — Sensitive data leaked into the audit log.** Mitigated: relay events and
  results are metadata-only (approval id, target action id, capability, decision,
  posture). Never arguments or content.
- **T8 — An approved write rewrites the governance substrate (BUG-06).** Once
  approval resolution really executes, a model-proposed `write_file` targeting
  `.raiker/hooks.json` (hooks run commands), the vault key, the encrypted store,
  or `.git/hooks/*` would be inside the workspace and therefore inside
  `resolve_workspace_path`'s boundary. Mitigated by
  `resolve_writable_workspace_path`, applied at both proposal time (so no
  un-executable approval is parked) and at the executor — the authoritative
  boundary. Refusal is `protected_workspace_path`, the approval becomes terminal
  `execution_failed`, and nothing is written. Covered by
  `tests/test_filesystem_tools.py` and
  `tests/test_approval_execution_wiring.py::TestWriteBoundaries`.
- **T9 — Resolution widening beyond what was reviewed (BUG-06).** The API path
  could have relayed *any* approved capability, silently turning `shell` into a
  one-click execution. Mitigated: the relayable set is an explicit frozenset of
  two local, checkpointed, reversible file capabilities, and
  `tests/test_security_regression_ui.py::TestApprovalExecutionIsNarrow` fails if
  a Tier-2 approval ever starts executing on resolution.

## What Workstream A does not cover

- Approving actions for capabilities with **no real executor** — they stay
  `activation_blocked:no_executor` and the relay reports `target_not_executed`.
- Batch/blanket approval of heterogeneous actions (one approval, one action).
- The critical-risk approval lifecycle itself (notify → manual human decision →
  deny/execute) lives in Workstream F7 —
  `docs/threat-models/critical-approval-lifecycle.md`. The relay is only its
  execution arm: it runs a critical target solely when carrying the one-shot
  `CriticalConfirmation` that lifecycle issues.
- Recursive or delegated relays (a relay may never execute another relay).
