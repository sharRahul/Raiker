# Runtime orchestration

## Shared preparation and approval authority — 2026-11-27

The current prompt approval modes are `manual`, `sandbox`, `dont_ask`.
Legacy prompt `auto` maps to sandbox preparation and `skip` to manual;
per-capability `auto` and Build's turn-mode IDs remain separate contracts.
Preparation depends on runtime-derived owner/session scope and fresh measured
containment, not model text. Explicit saved Ask/Deny, capability gates and
critical human confirmation remain authoritative. Approval records a decision;
actual executor results establish execution success, failure or unknown outcome.
See [decision modes](DECISION_MODES_SPEC.md) and the
[approval contract](../plans/APPROVAL_REDESIGN.md#contract).


The gateway orchestrates a turn: resolve principal, gather bounded context,
obtain a model response, validate proposed tool calls, apply policy, route any
allowed action through RuntimeAuthority, then record safe audit metadata and a
checkpoint.

The terminal client and loopback dashboard use this same path. Context and tool
results are observations, never authority. A denied or approval-required action
must not run merely because a model requested it.

Runtime modes, capability gates, decision modes, and executor availability are
checked at action time. Remote/cloud and sensitive no-executor domains remain
disabled and fail closed.

## Goal coordination target

PAA-02 in the [delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
adds a durable coordinator above task turns. It selects a dependency-ready step,
claims a lease, reserves remaining goal/child budget and invokes the existing
gateway. It cannot call an executor directly. Approval/question waits park
dependent work; independent work may proceed within the same scope. Resume,
retry and restart revalidate current owner/envelope version, revocation,
readiness and authority. See the [target spec](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md).
This coordinator is planned; existing turn orchestration stays authoritative.
