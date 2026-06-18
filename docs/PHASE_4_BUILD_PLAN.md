# Phase 4 Build Plan — External Channels, Multi-Agent, and Governed Execution

Phase 4 introduces external channel activation, subagents, teams, and remote/container execution only after governed approvals and execution boundaries are complete.

## Dependency Graph

```text
RAIKER-4001 Phase 4 disabled/listable gates
  -> RAIKER-4101 external channel approval contracts
  -> RAIKER-4201 subagent contract and parent/child event model
  -> RAIKER-4301 multi-agent team coordination ledger
  -> RAIKER-4401 remote/container execution policy boundary
  -> RAIKER-4501 enterprise/home-lab controls and audit reports
```

## Tasks

| Task ID | Scope | Contracts/events/storage | Policy | Tests | Acceptance criteria |
|---|---|---|---|---|---|
| RAIKER-4001 | Disabled/listable Phase 4 capability gates | Capability names only | Execution denied | Gate tests | Phase 4 capabilities are discoverable and cannot execute. |
| RAIKER-4101 | External channels and channel approvals | ChannelMessageEnvelope, approval events | Sender allowlists and action-bound approval | Channel denial tests | No external transport activates without pairing and policy. |
| RAIKER-4201 | Subagent contracts | Parent/child task and event linkage | No spawning without policy | Contract tests | Subagents remain inert until lifecycle policy exists. |
| RAIKER-4301 | Multi-agent teams | Team ledger and coordination events | Bounded roles and budgets | Ledger tests | Team work is auditable before execution. |
| RAIKER-4401 | Remote/container execution | Execution environment records | Approval-gated, no destructive operations | Denial tests | Remote/container execution is denied by default. |
| RAIKER-4501 | Enterprise/home-lab controls | Audit views and policy profiles | Admin-controlled limits | Audit tests | Governance reports show channel/execution state. |

## Implemented safe foundation in this pass

- `raiker.phase_gates` lists Phase 4 capabilities as disabled and raises before execution.
- Tests prove representative Phase 4 capabilities are listable and non-executable.

## Gated until later Phase 4 work

External transports, subagent spawning, multi-agent teams, remote execution, and container execution remain disabled until policy, tests, and approval paths are implemented.

## 2026-06-18 implementation update

The current implementation completes the Phase 4 safe foundation layer without activating external execution or autonomous coordination:

- execution profiles for local, container, SSH, and Daytona-style execution are listable for inspection;
- remote/container execution can only produce a denied execution plan with approval requirements and a command preview;
- subagent requests can be represented as parent-linked plans but cannot spawn workers;
- external channel activation status reports pairing and approval-relay state while keeping transports inactive;
- `/execution-profiles` provides terminal inspection parity through the existing CLI command surface.

External transports, subagent spawning, agent teams, approval relays, and remote/container execution remain disabled until pairing, sender trust, budget, policy, approval, audit, and lifecycle controls are complete.
