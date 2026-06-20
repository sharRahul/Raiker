# Phase 6 Build Plan — Channels, Multi-Agent, and Remote Execution

Phase 6 activates the channel connectors, subagent delegation, and remote execution profiles that were specified in Phase 4 of the full implementation blueprint but never built (Phase 4 was scoped to memory MVP only).

Phase 6 must not bypass earlier phase gates. All execution remains policy-gated, approval-required, and disabled-by-default.

---

## Dependency Graph

```text
RAIKER-6001 external channel connectors (REST, Email, Slack, Teams, Discord, Signal)
  -> RAIKER-6101 channel approval relay and sender trust
  -> RAIKER-6201 subagent contracts and bounded delegation
  -> RAIKER-6301 multi-agent team coordination
  -> RAIKER-6401 remote/container execution profiles
  -> RAIKER-6501 execution budget and cleanup
```

---

## Tasks

| Task ID | Scope | Contracts/events/storage | Policy | Tests | Acceptance criteria |
|---|---|---|---|---|---|
| RAIKER-6001 | External channel connector profiles and wiring | ChannelMessageEnvelope, channel event types | Sender allowlists; disabled by default | Channel profile tests | Channel connectors are listable, pair-able, and transport-inactive until policy approved. |
| RAIKER-6101 | Channel approval relay | Approval relay events, relay state | Action-bound approval; no relay without pairing | Relay denial tests | Approval relay over channels is denied by default; explicit policy required. |
| RAIKER-6201 | Subagent contracts and delegation | Parent/child task events, subagent records | No spawning without policy; bounded context/tools/depth/time/cost | Subagent contract tests | Subagents remain inert until lifecycle policy exists; bounded by max depth and cost. |
| RAIKER-6301 | Multi-agent team coordination | Team ledger events, coordination records | Bounded roles and budgets; no autonomous spawning | Team ledger tests | Team work is auditable and policy-gated before execution. |
| RAIKER-6401 | Remote/container execution profiles | Execution environment records, denied plans | Approval-gated; pinned images; no destructive ops | Remote denial tests | Remote/container execution is denied by default; requires explicit profile and approval. |
| RAIKER-6501 | Execution budget and cleanup | Budget, job, cleanup records | Budget and egress policy; cleanup required | Budget denial tests | Cloud/remote jobs cannot exceed configured budget; cleanup is mandatory. |

---

## Storage requirements

Allowed Phase 6 storage categories:

- channel pairing and trust records;
- approval relay state;
- subagent and team metadata;
- remote/container execution profiles;
- execution budget and cleanup records.

Forbidden without explicit later task:

- active graph node/edge write paths;
- unredacted lifecycle payload exports;
- unmanaged hosted execution tables.

---

## Validation requirements

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python scripts/validate_phase_status.py
```

Phase 6 tests must prove:

- unknown channel sender rejected;
- approval relay denied by default;
- subagent cannot exceed configured tools/depth/cost;
- multi-agent team work is policy-gated;
- remote/container execution requires explicit profile and approval;
- budget limits stop job execution.

---

## Completion rule

Phase 6 is not complete until channels, approval relay, subagents, teams, remote execution, budget controls, cleanup, tests, and docs are all present.
