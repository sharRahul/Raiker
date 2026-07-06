# What Is Not Available

> Capabilities › Deferred. Back to [Capabilities](capabilities.md).

These remain **fail-closed** (no executor) by design:

- Remote / cloud command execution (`remote_execution_cap`, `cloud_execution_cap`).
- Embeddings and model-provider runtime (`vector_embedding_runtime`,
  `model_provider_runtime`) and some code-intelligence writers.
- Sensitive Tier-6 domains: finance, investment, medical, pregnancy/baby, cctv,
  home security, hardware.

Each needs a real integration plus its own threat model before it can join
`REAL_EXECUTOR_CAPABILITIES`. Progress is tracked in
[`GAP_AND_TODO_ANALYSIS.md`](../GAP_AND_TODO_ANALYSIS.md) and
[`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md).
