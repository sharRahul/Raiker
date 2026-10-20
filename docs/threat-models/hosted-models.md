# Threat Model — Hosted & Private-Network Model Runtime (Phase 4, slice 7)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capabilities are now
> integrated and governed/default-ask; they were historically disabled/deferred
> before their executors landed. Approval resolution is metadata-only.

Per-capability threat model required by
[`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md) before
`hosted_model_runtime` and `private_network_model_runtime` may join
`REAL_EXECUTOR_CAPABILITIES`. This slice satisfies the per-integration opt-in
checklist recorded in [`remote-cloud.md`](remote-cloud.md) for the two
model-runtime capabilities. SSH/Daytona command execution remains separately
owner-profile gated; other remote/cloud providers stay fail-closed.

## What this slice covers

Two things, both fail-closed by default:

1. **Executors**
   (`raiker/runtime/executors/models_runtime.py`):
   `HostedModelRuntimeExecutor` / `PrivateNetworkModelRuntimeExecutor` run a
   single bounded operation, `connectivity_check`, on **one of the owner's saved
   model connections, named by `profile_id`**. The action carries no endpoint
   and no path: `endpoint`, `models_path`, `url`, `base_url` and `path` are
   refused by name (`argument_not_accepted:<name>`). The destination, the
   credential and the route come from the owner's connection and the provider
   adapter (its shipped `models_path`), resolved by the same factory a turn
   uses. The check lists the provider's models over the adapter's HTTP client —
   no redirects, capped body, 15-second bound — and its artifacts carry the
   profile id, provider, endpoint kind and model count only: never the URL,
   host, response body or a credential.
2. **Chat-path authorization**
   (`raiker/models/policy_state.py`, `raiker/models/factory.py`,
   `raiker/models/endpoint_policy.py::authorize_model_destination`):
   every off-machine provider construction — chat, streaming, readiness,
   catalogue, embeddings, advisor, side tasks, fallback — requires the owner's
   saved connection **for that profile**, and the request must go to the
   **origin** that connection is bound to (scheme, host, effective port). A
   gate the owner explicitly turned off refuses regardless of connections
   (`hosted_provider_requires_explicit_policy` /
   `private_network_provider_requires_explicit_policy`), and the gates are
   re-read for every provider build, so a revocation stops the next call of a
   turn that is already running.

## Authorization order

1. **Explicit owner revocation** of `hosted_model_runtime` /
   `private_network_model_runtime` — refuses.
2. **Runtime gates and capability policy** — unchanged; a capability's own gate,
   decision mode and approvals still apply.
3. **The owner's saved connection for the profile** — authorizes the origin it
   is bound to: the endpoint saved in it, or, for a connection that saved only a
   key, the profile's own shipped endpoint. An `endpoint_env` override or a
   profile edit cannot move it (`model_connection_origin_mismatch`).
4. **No connection** — an off-machine request is refused
   (`model_connection_required`). A loopback endpoint needs no connection.

`RAIKER_MODEL_EGRESS_ALLOWLIST` is **retired**. It used to be required as well
as a saved connection; an installation that still sets it is told once in the
log, and the variable neither opens nor closes anything. See
[ADR-0004](../adr/ADR-0004-connection-bound-model-authorization.md).

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| No off-machine model without the owner's connection | `model_connection_required` from the factory for every hosted/private construction, and from the connectivity executors, image generation and embeddings. An API key in the environment alone authorizes nothing. |
| Connection bound to its origin | `canonical_origin` normalises scheme, host (case, trailing dot, IP text form) and effective port; any difference is `model_connection_origin_mismatch`. Paths stay the adapter's. |
| Unsafe endpoints refused | Embedded user info (`endpoint_userinfo_rejected`), whitespace/backslashes or invalid ports (`endpoint_invalid`), and numeric hosts that are not a plain dotted IPv4 address (`endpoint_ambiguous_host`). |
| Gate off ⇒ no provider | `provider_runtime_policy_from_gates`; an explicit revocation always wins, re-read per provider build. |
| Owner-scoped | Connections are read by `(principal_id, profile_id)` from the encrypted vault; another principal's or another profile's connection is never consulted. |
| Agents cannot authorize | A connection is created, changed or removed only through the authenticated owner's `PUT /api/models/{profile_id}/connection` (and the local subscription client sign-in route). No action, tool, plugin or model output reaches those. |
| Credentials | From the owner's connection, or — for a connection the owner saved to use it — the provider's own environment variable. Never from action arguments, never logged, never in artifacts or events. |
| Hosted requires TLS | `hosted_https_required` (executor) and `hosted_http_endpoint_rejected` (endpoint policy) unless the profile sets `allow_remote_http`. Private-network HTTP is allowed. |
| Endpoint kind pinned | Hosted executor accepts only `remote_hosted`; private-network executor only `private_network` (`endpoint_kind_not_allowed:*`). |
| No redirects | httpx provider clients do not follow redirects (asserted); the urllib model helpers (`post_json`, `post_multipart`) refuse them (`redirect_refused:<status>`), so a key is never re-sent to a host a response names. |
| Dial-time address | `transport_guard.resolve_for_dial` resolves the name once per new connection and classifies every answer: hosted must be public (`model_dial_refused:non_public_address`), home lab private (`public_address_for_private`, `loopback_for_private`), link-local only with the connection's opt-in (`link_local_address`), metadata services never (`metadata_address`). `GuardedNetworkBackend` dials the address that passed; TLS and `Host` keep the name, so rebinding cannot move a connection. |
| Proxies | `transport_guard.proxy_for`: a hosted origin honours the owner's `HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY` minus `NO_PROXY`; loopback and private-network origins never use a proxy. A keyed plain-HTTP request through a proxy is refused (`credential_over_http_proxy`). Models shows the route per card and in the posture. |
| Credential origin | A credentialed request for an origin other than its client's is refused (`model_credential_origin_mismatch`). |
| No data leakage | Events/artifacts carry metadata only — never prompts, completions, URLs, hosts, headers or keys. |
| Budget (hosted paid) | OpenRouter additionally requires budget policy metadata (`openrouter_requires_budget_policy`). |
| AI principals | Capability gate + `route_action` block non-human principals from enabling the gates. |

## Activation requirements

Default gate state is **DISABLED** for both capabilities. Enabling requires a
HUMAN `runtime_gate_manager`, the agent runtime switched on (the model
API is called *from* the owner's local machine, like the reference channel),
the registered executor, a `threat_model_acks` row referencing this document,
and a human confirmation token. AI principals can never flip the gates. Saving
a connection is the owner's consent to use that provider, and only that one.

## Residual risks & non-goals

- Prompts/completions sent to a hosted provider **leave the machine** and are
  subject to that provider's data handling. The connection is the boundary:
  the owner should only connect providers they trust with prompt content.
- A request the owner's proxy carries is resolved by the proxy, so its address
  is not checked or pinned here; the proxy sees the destination host (via
  `CONNECT`). Name-based private classification (`.local`, single-label) is a
  hint; the resolved address is authoritative.
- An HTTP private-network endpoint sends its key in clear text on the owner's
  network (never through a proxy).
- A leaked owner environment variable leaks the API key; Raiker never writes an
  environment key to storage, events or artifacts.
- Out of scope (still fail-closed): remote command execution over SSH/VPS,
  cloud-provider execution (`remote_execution_cap`, `cloud_execution_cap`),
  and silent local→hosted fallback (never implemented).
