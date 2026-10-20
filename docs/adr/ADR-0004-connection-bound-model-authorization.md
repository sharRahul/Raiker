# ADR-0004: Model destinations are authorized by the owner's saved connection

## Status

Accepted and implemented on 2026-10-20. Supersedes the "Deliberately not
changed" note in FIXED-05 and the egress rows of the model threat models.

## Date

2026-10-20

## Context

Before this change, an off-machine model request had to pass two independent
destination checks:

1. the owner's saved connection for the profile (FIXED-05 made a connection
   authorize its own host), **and**
2. `RAIKER_MODEL_EGRESS_ALLOWLIST`, a process-wide list of hostname globs, which
   still had to be non-empty in four places that did not consult connections at
   all: the hosted/private connectivity executors, provider-backed embeddings
   (twice), and image generation.

The review behind this ADR found the second check was redundant where it agreed
with the first, and wrong where it did not:

- **Redundant.** In the factory, a configured connection already authorized its
  own host; the allowlist only mattered for profiles with *no* connection — an
  environment key plus an environment allowlist, a path that existed so an
  agent could reach a provider the owner had never connected in the product.
- **Blocking owner choices.** Embeddings and image generation refused a provider
  the owner had connected, solely because the environment list was empty
  (`model_egress_denied:no_allowlist`, `egress_denied:no_allowlist`).
- **Weaker than it looked.** It matched hostnames, not origins: a port or scheme
  change kept matching. The connectivity executors took the endpoint and the
  probe path from **action arguments**, so the allowlist was the only thing
  between a model-proposed URL and a GET. The urllib model helpers followed
  redirects, re-sending the `Authorization` header to wherever a response
  pointed, after the allowlist had been checked on the first URL only.
- **A second consent switch.** It sat in front of a decision the owner had
  already made by connecting a provider, which `HANDOFF.md` → "Security
  posture" rejects.

### Hermes Agent, for comparison

Hermes Agent's provider setup is `~/.hermes/config.yaml` (`provider`,
`base_url`, `model`, or named `custom_providers`) plus secrets in
`~/.hermes/.env`, set interactively with `hermes model` and checked with
`hermes doctor`. Configuring a provider is the whole of the setup: there is no
second host allowlist. That is the experience this ADR adopts. What Raiker keeps
that Hermes does not have: per-owner encrypted connections, capability gates
whose explicit revocation always wins, approvals and audit on every governed
action, and — new here — an origin binding that an environment override or an
agent cannot move.

## Decision

Authorization of an off-machine model destination is, in order:

1. **Explicit owner revocation** of `hosted_model_runtime` /
   `private_network_model_runtime` — refuses. Re-read on every provider build,
   so it stops the next call of a running turn.
2. **Runtime gates and capability policy** — unchanged.
3. **The owner's saved connection for the profile** — authorizes the canonical
   origin it is bound to (`scheme://host:effective-port`): the endpoint saved
   in the connection, or, for a connection that saved only a key, the profile's
   shipped endpoint. Paths stay the provider adapter's.
4. **No connection** — refused (`model_connection_required`). Loopback
   endpoints need no connection.

Consequences in code:

- `endpoint_policy.authorize_model_destination` and `canonical_origin` replace
  `model_egress_allowlist` / `enforce_model_egress`. `canonical_origin` refuses
  embedded credentials, whitespace/backslashes, invalid ports and numeric hosts
  that are not plain dotted-quad IPv4.
- `validate_endpoint_policy` restricts by `local_only` only. A profile's
  `requires_egress_policy` flag remains declarative metadata (and OpenRouter's
  egress/budget declaration check); it no longer stops a custom endpoint from
  being on the owner's network or the internet, which FIXED-935 documented but
  the code refused.
- The connectivity executors take `profile_id` and refuse `endpoint`,
  `models_path`, `url`, `base_url` and `path`; they check through the provider
  adapter's own route.
- Embeddings, the advisor, readiness, catalogue, side tasks and fallback all go
  through the factory and therefore the same rule; the advisor router now
  resolves the owner's connections at all.
- Image generation requires the connection, the hosted gate, and a connection
  bound to the provider's fixed image origin, so a key saved for a custom
  endpoint is never sent to OpenAI's or Google's image service.
- `post_json` / `post_multipart` refuse redirects (`redirect_refused:<status>`);
  httpx provider clients already did not follow them, and that is now asserted.
- Pooled provider clients never send a loopback origin through an environment
  proxy.
- `RAIKER_MODEL_EGRESS_ALLOWLIST` is ignored. If it is set, one warning naming
  the variable (never its value) is logged per process.
- The `model_egress_allowlist_configured` field is removed from `GET
  /api/models`; the Models posture shows connected off-machine providers
  instead.

## Compatibility

- **Environment-only setups** (provider key in the environment, host in the old
  allowlist, nothing saved in Models) stop working until the owner connects the
  provider once. The connect dialog offers **Use the key from `<VARIABLE>`**,
  which saves a connection recording only that its key comes from the
  environment (`credential_source: environment`); the key itself is never stored
  or sent to the browser. This is deliberate: an environment variable alone must
  not let an agent reach an off-machine model.
- **Profiles with `endpoint_env`** (none ship; possible in a
  `RAIKER_CONFIG_DIR` override): saving the connection records the variable's
  value at that moment as the connection's endpoint. A later change to the
  variable does not move the connection; saving again does.
- **CLI `/model` inspection commands** build routers without an owner, so they
  list and launch local models only.
- **Integrity sweep** baselines recorded with a `model` allowlist entry are
  read without it, so upgrading does not report drift once.

## Not changed

Connector, channel, web-access, MCP, hook and command egress controls; the
capability gates, decision modes and approvals; credential storage; sensitivity
rules for embeddings; readiness, budget, timeout and retry policy.

## Residual risk

The *address* a name resolves to was left to the HTTP client by this decision.
The follow-up transport hardening now decides it at dial time
(`raiker/models/transport_guard.py`; [FIXED-1021](../plans/FIXED_ITEMS.md#fixed-1021--a-hosted-model-name-was-dialled-wherever-its-dns-answer-pointed-was-bug-349)
to [FIXED-1030](../plans/FIXED_ITEMS.md#fixed-1030--a-refused-dial-and-other-classified-denials-read-as-enable-its-gate)):
every answer is classified against the connection's class, the passing address
is pinned, metadata services are always refused, and the proxy route is
explicit. What remains is that a request the owner's proxy carries is resolved
by that proxy, so it is not pinned; and a public address the owner connected is
the owner's trust decision.
