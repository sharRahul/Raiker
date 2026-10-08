# Runtime orchestration

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

PAA-02 in the [delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md)
adds a durable coordinator above task turns. It selects a dependency-ready step,
claims a lease, reserves remaining goal/child budget and invokes the existing
gateway. It cannot call an executor directly. Approval/question waits park
dependent work; independent work may proceed within the same scope. Resume,
retry and restart revalidate current owner/envelope version, revocation,
readiness and authority. See the [target spec](PERSONAL_AUTONOMOUS_AGENT_SPEC.md).
This coordinator is planned; existing turn orchestration stays authoritative.
