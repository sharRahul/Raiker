# Model transport security hardening (follow-up plan)

**Status: planned, not implemented.** A separate change from
[ADR-0004](../adr/ADR-0004-connection-bound-model-authorization.md), which
retired `RAIKER_MODEL_EGRESS_ALLOWLIST` and bound every off-machine model
request to the origin of the owner's saved connection. That change decides
*which origin* a request may go to. This plan is about *which address* the
socket actually reaches once a name is resolved, which ADR-0004 left to the
HTTP client.

Nothing here is a release blocker for ADR-0004. The review found no immediate
critical vulnerability that the allowlist removal made reachable: the retired
allowlist matched hostnames and never checked resolved addresses either, so
every gap listed below existed before ADR-0004 and is unchanged by it.

## Current behaviour (as of ADR-0004)

| Aspect | What happens now |
|---|---|
| Origin | Scheme, host and effective port must equal the saved connection's (`canonical_origin`). |
| Endpoint class | `classify_endpoint` labels a URL `local_machine`, `private_network` or `remote_hosted` from its **text**: literal IPs by range, names by suffix (`.local`, `.lan`, `.internal`, `.home.arpa`, single-label). |
| DNS | Resolved by httpx (provider calls) or urllib (image calls) when the connection is opened. Not checked. |
| Redirects | Not followed (httpx default, asserted; urllib helpers refuse them). |
| Proxies | httpx `trust_env=True` for non-loopback origins (owner's `HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY`/`NO_PROXY`); loopback origins never use a proxy. urllib helpers use the default `ProxyHandler`. |
| TLS | Default certificate verification; SNI and Host are the connection's name. |
| Credentials | Per request, never on a pooled client; never re-sent on a redirect. |

## Gaps this plan closes

1. **A `remote_hosted` name that resolves to a private, loopback or link-local
   address** is dialled. Example: a saved connection for
   `https://models.example.com` whose DNS answer becomes `10.0.0.5` or
   `127.0.0.1`. The request carries the owner's key to a host the owner did
   not mean.
2. **DNS rebinding.** Even with a check at resolve time, a second resolution by
   the HTTP client can return a different answer.
3. **Cloud metadata services** (`169.254.169.254`, `fd00:ec2::254`,
   `metadata.google.internal`) are reachable as a `private_network` endpoint by
   name or literal today if the owner saves them. They should never be a model
   destination.
4. **Proxy behaviour is implicit.** A plain-HTTP private-network endpoint sent
   through an HTTP proxy exposes its key to the proxy. `NO_PROXY` handling of
   private ranges depends on the owner's environment.
5. **No network-level SSRF regression tests** exist for the model path; the
   current tests are origin-level.

## Design

### D1 — Dial-time classification by resolved address

Add `raiker/models/transport_guard.py` with one function,
`resolve_for_dial(origin, declared_kind) -> list[address]`, used by both
transports:

- Resolve the host once (`getaddrinfo`, all families).
- Classify **every** answer with the existing `web_policy.address_is_reachable`
  and `literal_address` helpers rather than writing a second classifier.
- Rules by the connection's declared class:
  - `remote_hosted`: every answer must be a public unicast address. Any
    private, loopback, link-local, multicast, reserved, CGNAT (`100.64/10`) or
    metadata answer refuses with `model_dial_refused:non_public_address`.
  - `private_network`: answers must be private, link-local (only if explicitly
    allowed — see D3) or loopback **only** when the connection is a loopback
    name. Public answers refuse (`model_dial_refused:public_address_for_private`)
    so a home-lab name that starts resolving to the internet is noticed.
  - `local_machine`: answers must be loopback.
- Metadata addresses refuse for every class (D3).

### D2 — Address pinning

Dial the address that passed D1, keeping the original name for TLS SNI,
certificate verification and the `Host` header:

- **httpx**: a custom `httpx.AsyncHTTPTransport` subclass (or an
  `httpcore` network backend) that overrides connect to the pinned address. Pin
  per request, because the pool is per origin and an answer can change between
  requests.
- **urllib** (image helpers): reuse `web_policy.pinned_https_opener`, already
  used for MCP, which does exactly this.

**Feasibility and risks — assess before implementing:**

- httpx does not expose a supported "connect to this IP" hook; the options are a
  custom `httpcore` backend or resolving via a patched `socket.getaddrinfo`
  scoped to the call. The backend route is cleaner and must be tested against
  the pinned httpx/httpcore versions in `uv.lock`; upgrades can break it.
- Pinning interacts with HTTP/2 connection reuse: a reused connection was pinned
  when it was opened, which is correct, but the pool must not reuse it after the
  origin's answer has changed class. Keying the pool by `(origin, address)` is
  the simplest correct rule.
- Through an HTTPS proxy, the client does not resolve the destination — the
  proxy does. Pinning cannot apply; see D4.
- IPv6 happy-eyeballs: pin the first passing answer per family and fall back in
  order; never fall back to an address that failed D1.

### D3 — Exceptions that must keep working

- **Loopback** (Ollama, LM Studio, llama.cpp, MLX, managed local inference):
  unchanged; no proxy, no connection required.
- **Private network** (home-lab vLLM, LM Studio remote, a GPU box on
  `192.168.x.x`, `*.local`, single-label names): unchanged for private answers.
- **Link-local** (`169.254.0.0/16`, `fe80::/10`): refused by default, with an
  explicit per-connection owner opt-in for the rare direct-cable setup — never
  for `169.254.169.254`.
- **Metadata** (`169.254.169.254`, `fd00:ec2::254`, `100.100.100.200`, and the
  names `metadata.google.internal`, `metadata.azure.com`): always refused, no
  opt-in.

### D4 — Proxy policy

- Keep honouring the owner's proxy environment for hosted origins; it is the
  owner's own configuration.
- Refuse sending a **plain-HTTP** request carrying a credential through a proxy
  (`model_dial_refused:credential_over_http_proxy`), with an owner-facing
  explanation; HTTPS through a proxy is an end-to-end tunnel and stays allowed.
- Private-network origins bypass the proxy by default (add their hosts to the
  client's `NO_PROXY` equivalent), matching loopback.
- Document the effective behaviour on the Models page posture ("Through your
  proxy: yes/no").

### D5 — TLS and credential-origin

- Keep default verification; add a test that a certificate for another name is
  refused before any header is sent.
- Assert that a credential is only ever attached to a request whose URL origin
  equals the connection's (a unit-level guard in `providers/http.py`), so a
  future adapter bug that builds an absolute URL to another host fails closed.

## Acceptance criteria

1. A `remote_hosted` connection whose name resolves to any non-public address
   is refused before a socket is opened, with a named reason, and no request
   bytes leave the machine.
2. A resolution change between check and connect cannot change the dialled
   address (pinning), proven with a resolver stub that answers differently on
   the second call.
3. Metadata addresses are refused for every class, by literal and by name.
4. Every shipped local and private-network profile still works against a real
   loopback server and a private-range test server.
5. Hosted providers still work through an HTTPS proxy; a plain-HTTP keyed
   request through a proxy is refused.
6. No measurable latency regression on a pooled connection (resolution once per
   new connection, not per request on a kept-alive one).

## Suggested test scenarios

| ID | Scenario | Expected |
|---|---|---|
| NET-01 | Hosted name → `10.0.0.5` | Refused `non_public_address`, server receives nothing |
| NET-02 | Hosted name → `127.0.0.1` | Refused |
| NET-03 | Hosted name → public, then `127.0.0.1` on second lookup | Dials the first answer only |
| NET-04 | Private connection `http://169.254.169.254` | Refused `metadata_address` |
| NET-05 | Private connection `http://metadata.google.internal` | Refused |
| NET-06 | Private name → `192.168.1.20` | Allowed |
| NET-07 | Private name → public address | Refused `public_address_for_private` |
| NET-08 | Loopback Ollama | Allowed, no proxy used even with `HTTPS_PROXY` set |
| NET-09 | Hosted via HTTPS proxy | Allowed |
| NET-10 | Keyed `http://` private endpoint via HTTP proxy | Refused |
| NET-11 | Certificate for another name | Refused before headers are sent |
| NET-12 | IPv6 hosted name with mixed public/ULA answers | Refused (any non-public answer) |

## Dependencies

- `raiker/runtime/web_policy.py` (`address_is_reachable`, `literal_address`,
  `pinned_https_opener`) — reuse, do not duplicate.
- `raiker/models/transport.py` (`ProviderClientPool`) — pool key change.
- httpx / httpcore versions pinned in `uv.lock`.

## Residual risk after this plan

- A public address the owner connected can still be malicious; the connection
  is the owner's trust decision.
- A proxy the owner configured sees hosted traffic metadata (destination host
  via `CONNECT`).
- Name-based private classification (`.local`, single-label) remains a hint;
  D1 makes the resolved address authoritative.
