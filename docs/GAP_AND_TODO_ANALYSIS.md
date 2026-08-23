# Gaps and deferred work

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

## Completed items

The local terminal client, loopback dashboard, owner bootstrap, policy and
approval boundaries, audit records, model profile selection, and governed local
runtime slices are implemented.

## No longer active gaps

Historical phase plans, temporary CI-quota instructions, and completed slice
checklists are not active product documentation. Current status is maintained in
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Deferred work

- Sensitive finance, investment, medical, pregnancy, CCTV, home-security, and
  hardware operations. **No executor exists**, so there is no enable path at all;
  they fail closed and are listed under Observability → Diagnostics.
- Hosted multi-user deployment and native/mobile/IDE clients.
- Tamper-evident audit storage and a dedicated secret-management service.

These areas remain disabled and fail closed. Strict non-allow blocking, role
revoke governed, and capability gate per action remain the baseline.

**Corrected 2026-08-23: remote and cloud command execution is no longer deferred.**
`remote_execution_cap` and `cloud_execution_cap` have real foreground executors
with an exact remote envelope, a pinned host key, a fixed supervisor path and a
cumulative cost budget, and an approval relays them. What is still open is the
supervisor install/upgrade lifecycle and live remote proof — BUG-194 in
[to be fixed](plans/TO_BE_FIXED.md).

## Open work, in the order it is worth doing

The full, prioritised, source-cited backlog is
[§5 of the reference compatibility document](REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).
The four highest-priority, lowest-effort items are:

1. **Checkpoint rewind is unreachable.** The restore executor exists; no surface
   proposes a restore.
2. **`RUNTIME_EXECUTORS_SPEC.md` completeness**, now fixed — kept here as the
   pattern to watch for: a canonical status document that omits capabilities.
3. **Audit export has no route.** The manifest is produced and stored and cannot
   be taken out of the product. (Memory export, by contrast, *is* reachable —
   `GET /api/memory/export` — which is what makes the audit gap conspicuous.)

Strict non-allow blocking, role revoke governed, and capability gate per action remain the baseline.
