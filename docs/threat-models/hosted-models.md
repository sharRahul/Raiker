# Threat Model — Hosted & Private-Network Model Runtime (Phase 4, slice 7)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capabilities are now
> integrated and governed/default-ask; they were historically disabled/deferred
> before their executors landed. Approval resolution is metadata-only.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`hosted_model_runtime` and `private_network_model_runtime` may join
`REAL_EXECUTOR_CAPABILITIES`. This slice satisfies the per-integration opt-in
checklist recorded in [`remote-cloud.md`](remote-cloud.md) for the two
model-runtime capabilities; **remote/cloud command execution stays
fail-closed** per that document.

## What this slice covers

Two things, both fail-closed by default:

1. **Executors**
   (`raiker/runtime/executors/models_runtime.py`):
   `HostedModelRuntimeExecutor` / `PrivateNetworkModelRuntimeExecutor` run a
   single bounded operation, `connectivity_check` — a metadata-only
   reachability probe (HTTP GET of the endpoint's models path) of an
   **owner-allowlisted** model endpoint. Artifacts carry endpoint kind,
   HTTP status, and byte counts only — never the URL, host, response body,
   or any credential.
2. **Chat-path policy wiring**
   (`raiker/models/policy_state.py`,
   `raiker/models/endpoint_policy.py::enforce_model_egress`): the production
   `ModelRouter` derives its `ProviderRuntimePolicy` from the persisted
   capability gates. If both gates are deliberately disabled, hosted and
   private-network model profiles cannot be constructed at all
   (`hosted_provider_requires_explicit_policy` /
   `private_network_provider_requires_explicit_policy`). Even with a gate
   enabled, every off-machine provider construction re-checks the owner
   egress allowlist and fails closed without it.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| No egress by default | `RAIKER_MODEL_EGRESS_ALLOWLIST` empty ⇒ `model_egress_denied:no_allowlist` on both the executor probe and every hosted/private provider construction. |
| Gate off ⇒ no provider | `provider_runtime_policy_from_gates` returns all-false policy unless the owner enabled the gate through the governed control plane. |
| Credentials | API keys are injected by the provider factory from owner env vars (`api_key_env`) only — never accepted from model/action arguments, never logged, never in artifacts/events. |
| Hosted requires TLS | `hosted_https_required` (executor) and `hosted_http_endpoint_rejected` (endpoint policy). |
| Endpoint kind pinned | Hosted executor only accepts `remote_hosted` endpoints; private-network executor only accepts `private_network` endpoints (`endpoint_kind_not_allowed:*`). Local endpoints are never subject to these gates. |
| Bounded probe | Response size capped, short timeout; failures fail closed (`fetch_failed:*` / `egress_denied:*`). |
| No data leakage | Events/artifacts carry metadata only (endpoint kind, status, byte counts) — never prompts, completions, URLs, hosts, headers, or keys. |
| Budget (hosted paid) | OpenRouter (and any paid hosted profile) additionally requires budget policy metadata (`openrouter_requires_budget_policy`). |
| AI principals | Capability gate + `route_action` block non-human principals from running or enabling the gates. |

## Activation requirements

Default gate state is **DISABLED** for both capabilities. Enabling requires a
HUMAN `runtime_gate_manager`, the `local_single_user_runtime` mode (the model
API is called *from* the owner's local machine, like the reference channel),
the registered executor, a `threat_model_acks` row referencing this document,
and a human confirmation token. AI principals can never flip the gates.

## Residual risks & non-goals

- Prompts/completions sent to a hosted provider **leave the machine** and are
  subject to that provider's data handling. The egress allowlist is the
  boundary: the owner must only allowlist providers they trust with prompt
  content.
- A leaked owner env var leaks the API key; Raiker never writes keys to
  storage, events, or artifacts, but env hygiene is the owner's
  responsibility.
- Out of scope (still fail-closed): remote command execution over
  SSH/VPS, cloud-provider execution (`remote_execution_cap`,
  `cloud_execution_cap`), silent local→hosted fallback (never implemented),
  and any provider not reachable through the owner allowlist.
