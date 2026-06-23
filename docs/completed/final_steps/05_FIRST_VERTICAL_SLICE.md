# First Vertical Slice — Prove the Whole Loop End-to-End

> Build this **before** scaling out executors. It proves the full path
> *authenticate → view gates → flip a gate → executor runs → audit streams back*
> with the smallest safe capability, so the architecture is validated before the
> large, risky tiers are built.

Chosen capability: **`approval_execution_relay`** (+ `file_write_execution` /
`patch_apply_execution` as the action it executes). Rationale: local, reversible,
high-leverage (it makes `/approve` and the existing proposal pipeline real), and it
exercises every layer without external integrations, sandboxes, or egress.

---

## Scope of the slice

Pull the minimum from each workstream:

| From | Tasks | What lands |
|---|---|---|
| A | A001–A005 | `RuntimeControlService` + DTOs + CLI refactor. |
| B | B001–B004, B007, B009 | App factory, session store, auth→principal, control routes, redaction guard, security tests. (Defer B005/B006 prompt+stream, B008 full CSRF hardening to after the slice if needed for time — but keep auth + redaction.) |
| C | C001–C006 | Activation requirement framework + remove denylist; make **only** `approval_execution_relay` (+ the two file-exec caps) satisfiable. |
| D | D000 + Tier 1 (`approval_execution_relay`, `file_write_execution`, `patch_apply_execution`) | Executor registry + the three Tier-1 executors. |

Everything else stays disabled and unsatisfiable.

---

## End-to-end acceptance scenario (must pass as an integration test)

`tests/test_vertical_slice_e2e.py`:

1. Fresh workspace; run owner bootstrap (`/bootstrap-owner` path).
2. Boot `create_app(workspace)`; issue an owner API token.
3. `GET /api/capability-gates` → `approval_execution_relay` shows
   `state=disabled`, `can_current_principal_change=true`.
4. Create a file-change proposal via the existing review/proposal pipeline.
5. Activate runtime mode (`POST /api/runtime-mode/activate` →
   `local_single_user_runtime`) as owner.
6. Record threat-model ack for the three capabilities.
7. `POST /api/capability-gates/approval_execution_relay/set` →
   `enabled_runtime` as owner → **succeeds** (Workstream C satisfied).
8. Approve the proposal → executor applies the file change on disk → returns
   `ExecutionResult(ok=true)` → `action_executed` event present (redacted).
9. `GET /api/runtime-readiness` reflects the enabled capability.
10. Disable the capability → a subsequent approve **fails closed**
    (`disabled_by_capability_gate`), no file change.

### Negative cases (same test file)
- AI principal attempts step 7 → `403` / authority denial; gate stays disabled.
- Step 7 without runtime mode active → `activation_blocked:runtime_mode_not_active`.
- Step 7 without threat-model ack → `activation_blocked:no_threat_model_ack`.
- Approve with gate enabled but executor unregistered (simulated) →
  `execution_unavailable:no_executor`, no side effect.
- Response bodies contain no secrets/file-contents/Authorization headers.

---

## Definition of done for the slice

- All steps above pass as automated tests.
- Full §5 validation gate (`00_README_PROGRAM_OVERVIEW.md`) passes.
- `docs/IMPLEMENTATION_STATUS.md` updated: `approval_execution_relay`,
  `file_write_execution`, `patch_apply_execution` move to their real enabled
  status with evidence; all other runtime flags remain `False`.
- A short `docs/THREAT_MODEL.md` addition for these three capabilities.

Once green, the same pattern repeats for Tier 2 → Tier 6 in
`04_WORKSTREAM_D_EXECUTORS_PER_CAPABILITY.md`.
</content>
