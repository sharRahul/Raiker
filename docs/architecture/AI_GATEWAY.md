# AI gateway

Raiker's AI gateway is an in-process execution layer alongside ModelRouter. It uses the existing provider adapters and requires no separately installed proxy or hosted gateway account.

## Request path

1. The existing runtime resolves the owner's selected model and configured fallback sequence.
2. ModelRouter resolves current runtime gates and the saved connection through ModelProviderFactory. Egress checks, metadata-address protection and the credential vault remain authoritative.
3. GatewayProvider sends completion, streaming, embedding and explicit model-probe operations through AIGateway. Health checks and catalogue reads retain their existing paths and do not reset model-execution circuits.
4. AIGateway admits the operation, measures its duration and reported usage, and updates transient failure state. Provider resources close through the existing router lifecycle; streaming iterators close explicitly on cancellation or early exit.
5. The runtime records the existing audit events and usage ledger, governs tools, and persists workflow checkpoints and approvals.

The gateway does not execute tools or replay workflows. A model tool call is still an untrusted proposal.

## Shared retry and fallback policy

ModelAttempts in raiker/models/attempts.py is used by regular and streaming runtime calls. Each configured candidate receives at most one additional transport attempt. Authentication, policy, capability, quota, rate-limit and circuit-open refusals do not earn a generic transport retry. Credential-pool rotation remains the separate, bounded response to a throttled or spent key.

Retries and fallbacks stop after visible text, reasoning or tool output. A failed partial response remains partial; Raiker does not splice a different provider's answer into it. Internal tool-less retries and backup-key attempts re-read connection state and validate current runtime policy. A changed or deleted saved connection aborts that request; a new request resolves the current configuration. Tool-less retries rebuild the provider after reauthorization so environment-backed credentials and endpoints are refreshed too.

Only owner-configured fallback candidates are considered. Each candidate still passes current policy. The gateway does not silently select a cheaper model or widen network permissions.

## Transient failure circuits

The default process-wide service opens a circuit after three consecutive transport failures and waits 30 seconds before allowing one recovery request. Other requests during cooldown or while that recovery is running receive provider_circuit_open; the runtime can proceed to an authorized configured fallback. A successful request, or a permanent provider refusal demonstrating reachability, clears the transient failure streak. Cancellation does not count as a provider failure and releases recovery admission. Late completions from an older circuit generation cannot clear a newer outage.

State is isolated by workspace/owner scope, profile, effective model, endpoint and resolved authentication headers. Connection identity is retained only as a process-keyed digest. The default state limit is 1,024 targets; active and cooling targets cannot be evicted to admit more calls. The service keeps 256 recent metadata records. A restart clears this process-local state. Transient transport failures and gateway cooldown refusals are not additionally fed into the provider-wide capability failure counter, which would pause unrelated credentials. Existing owner-governed capability containment still applies; the gateway does not override a capability the owner or containment monitor has disabled.

AIGateway accepts failure_threshold, cooldown_seconds, max_targets and max_records constructor settings. ModelRouter accepts gateway and gateway_scope for embedded hosts. Owner runtime factories supply stable workspace/principal scopes; an unbound router gets an isolated scope. Production defaults require no new setting or setup step.

## Telemetry and accounting

The raiker.models.gateway logger emits metadata for each admitted or circuit-blocked operation: logical request identifier, attempt number, profile/model, request kind, outcome, duration, normalized provider token counts, and available session/turn identifiers. The bounded in-memory recent() view supports internal diagnostics. It is not a public API or a persistent analytics store.

Prompts, responses, reasoning, tool arguments, provider exception messages, credentials, endpoints and connection fingerprints are excluded. Error labels are allowlisted categories with provider detail suffixes removed. Correlation context is task-local metadata and grants no authority. Main turn calls, hook calls and compaction attach their existing identifiers; background work without a session leaves it absent.

Gateway records are observational and never insert billing rows. The existing ModelUsageLedger and runtime cost meters remain the billing and spending-limit paths, avoiding double accounting. Provider usage that is absent stays absent in gateway telemetry. Existing stopped-stream accounting may record explicitly labeled estimates in the runtime ledger; that is distinct from provider-reported gateway usage. In-flight calls, unknown prices and missing usage mean the existing spending control is not a prepaid hard dollar reservation.

## Coverage and boundaries

All execution through ModelRouter receives gateway instrumentation: Chat, Build, Design, hooks, compaction, vision side tasks, advisor calls, embeddings and model probes. Direct provider users outside ModelRouter are not implicitly instrumented. Model listing and health requests do not constitute inference and bypass the inference circuit. No extra automatic retries are added by the gateway itself.

Provider prompt caching remains available. Response caching, semantic caching/routing, a distributed control plane, multi-tenant hosting and a replacement durable workflow engine are outside this implementation. Existing endpoint policy, permissions, configured fallback and spending settings remain in their current product screens.

## Research basis

- [Steve Kinney: gateway and durable workflows](https://stevekinney.com/writing/ai-gateway-durable-workflows): separate stateless model execution controls from checkpointed task orchestration.
- [MLflow architecture guide](https://mlflow.org/articles/ai-gateway-architecture-a-guide-for-technical-teams/): shared provider access, governance and usage observability.
- [Microsoft GenAI gateway](https://learn.microsoft.com/en-us/ai/playbook/solutions/genai-gateway/): authentication, resource controls and token-aware governance.
- [Kong architecture](https://developer.konghq.com/ai-gateway/architecture/): separate configuration authority from request enforcement; Raiker keeps both local.
- [TrueFoundry guide](https://www.truefoundry.com/blog/ai-gateway): centralized provider access and resilience.
- [MuleSoft guide](https://www.mulesoft.com/ai/what-is-ai-gateway): streaming-aware governance.
- [Multi-model introduction](https://medium.com/@vasanthank29/ai-gateway-architecture-for-multi-model-applications-a-complete-beginner-friendly-guide-fe4b68bf69d8): background overview; implementation decisions above use the primary architecture sources.
