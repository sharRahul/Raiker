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
The three highest-priority, lowest-effort items are:

1. **Checkpoint rewind is unreachable.** The restore executor exists, is
   registered and is tested; no route, terminal command or model tool proposes a
   restore. Both `/checkpoints restore` and the web Checkpoints view compute a
   preflight and perform nothing.
2. **Audit export has no route.** The manifest is produced and stored and cannot
   be taken out of the product. (Memory export, by contrast, *is* reachable —
   `GET /api/memory/export`, `raiker/api/routes_memory.py` — which is what makes
   the audit gap conspicuous.)
3. **Two egress implementations exist, and the weaker one is registered.**
   `WebFetchExecutor` and `NetworkExecutor` reach the network through
   `sandbox.fetch_url` with a hard-coded four-host allowlist and none of
   `WebAccessService`'s address guard. Neither is reachable from any product
   route, and both are in the default executor registry. Candidate for removal
   rather than completion — see
   [`threat-models/network-execution.md`](threat-models/network-execution.md).
4. **Raiker's MCP client is pinned to protocol revision `2024-11-05`**, five
   revisions behind the current
   [`2026-07-28`](https://modelcontextprotocol.io/specification/versioning). It
   is why remote MCP has no OAuth flow and no streamable-HTTP session semantics.

The **eight capabilities with no threat model** were a third item here and are
**closed** (2026-08-23). Re-deriving the comparison found the count understated —
it credited a passing mention — so eleven documents were written rather than
eight, and all forty-five capabilities with a real executor now have one. See
[the threat-models index](threat-models/README.md#coverage--every-capability-with-a-real-executor-has-one).

`RUNTIME_EXECUTORS_SPEC.md` completeness was a fourth item here and is **closed**:
re-checked on 2026-08-23, all 67 capabilities in `raiker/phase_gates.py` appear in
it. It is kept named rather than silently dropped, because the pattern it
represents — a canonical status document that omits capabilities — is the one
worth watching for.

Strict non-allow blocking, role revoke governed, and capability gate per action remain the baseline.
