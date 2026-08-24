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
