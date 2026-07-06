# What Is Not Available

> Capabilities › Deferred. Back to [Capabilities](capabilities.md).

These remain **fail-closed** (no executor) by design:

- Remote / cloud command execution (`remote_execution_cap`, `cloud_execution_cap`).
- Sensitive Tier-6 domains: finance, investment, medical, pregnancy/baby, cctv,
  home security, hardware.

Now available as real, governed executors (default-disabled gate; enable through
the governed path): local embeddings (`vector_embedding_runtime`) and
provider-backed semantic embeddings (`model_provider_runtime`, egress-gated).

Each needs a real integration plus its own threat model before it can join
`REAL_EXECUTOR_CAPABILITIES`. Progress is tracked in
[`GAP_AND_TODO_ANALYSIS.md`](../GAP_AND_TODO_ANALYSIS.md) and
[`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md).
