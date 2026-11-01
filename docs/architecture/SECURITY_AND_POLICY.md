# Security and policy

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker defaults to deny or ask. A local owner bootstrap creates the owner
principal; only humans with the required role may make governance changes.

## Security philosophy

- **Local-first:** keep work, state, and model choice under the operator's
  control; external access is explicit rather than assumed.
- **Least authority:** a model proposes work but receives no authority merely by
  proposing it.
- **Human control:** people own role, gate, mode, approval, and recovery
  decisions; AI principals cannot elevate themselves.
- **Fail closed:** unknown, unsupported, remote, or sensitive operations refuse
  to run until their full governance and executor requirements are met.
- **Auditable boundaries:** record safe evidence for governed decisions and
  actions without storing secrets, raw prompts, or private reasoning.
- **Frictionless by default:** safe, local, read-oriented work should be easy;
  friction appears only when an action seeks new authority, wider scope, or
  irreversible impact.
- **Zero trust at authority boundaries:** model output, tools, files,
  connectors, and external responses are untrusted until independently checked.

Policy evaluates the principal, capability, domain, risk, workspace scope,
decision mode, and available executor. Strict non-allow blocking, role revoke
governed, and capability gate per action are enforced. AI principals may propose
work but cannot grant themselves authority. Approval resolution executes an
approved local file mutation or a governed `shell`/`process` command through the
execution relay and is metadata-only for every other capability. A command must
carry its runtime-authored approval id or standing-grant id; selecting an
execution environment is never authority.

## Local requests and reverse proxies

Some pages and exemptions are for this computer only: password recovery from
the lock screen, the instance list, and the abuse window's exemption for
loopback reads. Each asks one question, `is_local_request`
(`raiker/api/proxy_guard.py`).

**The listener a connection arrived on decides, not the request's headers.** A
header is set by whoever sends the request; the socket a connection was
accepted on is not. `raiker-web` runs one server with up to two listeners and
reads which one accepted a connection from the ASGI scope (`scope["server"]`),
which uvicorn fills from the socket:

* **The local listener** (`--host`/`--port`, loopback by default). A request
  is local when its peer is loopback, it arrived over TCP, and it carries no
  forwarding header. A forwarding header there is refused
  (`proxied_request_refused`): it means a proxy was pointed at the wrong
  listener.
* **The remote listener**, off by default and chosen in **Settings → Security →
  Remote access** (owner's decision 2026-10-26): a *private network* address
  that Raiker serves over HTTPS with the owner's certificate, or a *reverse
  proxy* listener (`127.0.0.1:<port>` or a Unix socket). Every request there is
  remote, whatever its headers: recovery, instances, host Quit/Restart, the
  tray exchange and remote-access changes refused; HTTPS required (on the proxy
  listener, `X-Forwarded-Proto: https` is believed there and only there); HSTS;
  rate limited apart from local requests.
* A connection with no TCP address (a Unix socket) is never local.

**Remote requests need two-step sign-in (BUG-358).** There is no shared
secret: `RAIKER_OWNER_TOKEN` was required to open a remote listener and nothing
ever read it, so it is removed. The remote listener does not open while an
account has no MFA; a remote sign-in needs the password **and** a code; and
every authenticated remote request must carry a session made from another
device, verified with a code, against the MFA enrolment in force now
(`AuthMiddleware` in `raiker/api/auth.py`). Turning MFA off or resetting it
suspends remote access at once and retires every session verified against the
old enrolment. Remote sessions are cookie-only (`Secure`, `HttpOnly`,
`SameSite=Strict`, 12 hours idle, 7 days at most); no bearer token is returned.
Turning MFA off, resetting it and changing remote access need a fresh code.
This computer is unchanged: local sign-in works without MFA. Full design,
lifecycle and regression scenarios:
[REMOTE_ACCESS.md](REMOTE_ACCESS.md).

uvicorn runs with `proxy_headers=False`, so no header can replace the peer.
Forwarding headers only ever make a request less trusted. Diagnostics reports
the listener and every refused or served proxied request.

**What this cannot see.** A proxy pointed at the local listener that adds no
forwarding header is, on that socket, the same as a browser on the server, and
is treated as local. No check inside the request can tell them apart; the
documentation therefore never points a proxy at the local listener, and the
proxy listener exists so that it never has to
([FIXED-1266](../plans/FIXED_ITEMS.md#fixed-1266--a-proxy-that-sent-no-forwarding-header-was-still-read-as-local-bug-347-review)).

## Per-turn machine identity boundary

Agentic work never enters the broker as the human owner. An embedded workspace
issuer mints a short-lived Ed25519 attestation for each turn and binds it to the
owner delegation, workspace, session, turn, machine principal, and broker
audience. The broker verifies that attestation before policy, credentials,
approvals, hooks, or tools. A resume rotates the token, terminal completion
deactivates it, and a subagent receives a child identity with explicit ancestry.

The verified machine is the action actor; the authenticated human remains the
owner of account-scoped models, connectors, memory, projects, and credentials.
Model-controlled arguments cannot change that owner scope. Machines cannot mint
identities, grant roles, change gates or modes, resolve approvals, satisfy
step-up, or read raw credentials. Approval records preserve the machine proposer
and later human authorizer without persisting the bearer token or signature.
The public key/token IDs and issue/expiry timestamps are snapshotted on the
proposed action, so a resume rotation cannot rewrite approval history. Runtime
execution always receives the machine principal; owner resolution is limited to
resource and control lookup. Activity reports the event emitter separately from
the turn identity, preventing human authorization or runtime events from being
presented as if the agent emitted them.
See [the machine-identity threat model](../threat-models/machine-identity.md).

Strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

Sensitive and remote capabilities remain fail-closed until a real executor,
explicit gate, policy requirements, and applicable human approval are present.
Operational security boundaries are defined in [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md).

## Forge credentials and repository authority

GitHub is the one forge. Its credential is whichever method the owner selected
(vault token, the legacy `RAIKER_GITHUB_TOKEN`, gh CLI, a saved Git credential,
SSH, or a GitHub App sign-in or installation), checked against its GitHub
account, and lent to `github.com` only — for one command or one conversation,
narrowed to operation, repository and branch — through a helper that answers no
other host, after clearing every inherited credential helper. An agent's push or
GitHub write runs without a per-step approval only under a repository
delegation ([FIXED-886](../plans/FIXED_ITEMS.md#fixed-886--a-standing-grant-or-allow-mode-alone-let-an-agent-push-or-write-to-github)).

The accepted target ([DEC-21b as amended 2026-10-12](GITHUB_CONNECTION_SPEC.md))
keeps three layers apart: GitHub's own permissions (the outer limit), Raiker's
capability gates, decision modes and repository-bound delegations (the inner
limit), and a human approval or explicit delegation (the trigger). Signing in,
installing the GitHub App, selecting repositories or storing a credential
grants nothing by itself. A credential found on the machine — gh CLI sign-in,
an OS credential-manager entry, an SSH key — is used only after the owner
selects it and its account is verified, and only through the broker. Tokens,
refresh tokens, App private keys and client secrets never reach a model, a
transcript, a log or an agent sandbox, and a method whose controls cannot be
enforced is unavailable rather than ungoverned.

## Native sandbox boundary (Docker and Podman removed)

Raiker does not use Docker or Podman. Agent-controlled commands run only through
the native runner (`native/raiker-command-runner`): AppContainer with a Job
Object on Windows, Bubblewrap with seccomp on Linux and Seatbelt on macOS. A
stored container profile from an earlier version is listed as retired, refuses
with `container_environment_retired`, and never falls back to the host. Until
disposable task workspaces exist the runner reports itself unavailable, so
governed commands are refused rather than run against the owner's project. See
`docs/architecture/NATIVE_SANDBOX_MIGRATION.md` and the release blockers in
`docs/plans/TO_BE_FIXED.md`.

## Governed command boundary

Approved `shell`/`process` and standing-grant `run_command` share one
owner-scoped durable lifecycle. There is no command-create API. The selected
environment is authoritative: unavailable container, SSH, and Daytona profiles
fail closed rather than running locally. Explicit `local_native` is a narrow
argv-only host runner with a constructed secret-free environment and must be
presented as reduced isolation, not as an OS sandbox.

Command material is encrypted; the query surface exposes only safe display,
digests, state, byte/redaction counters, environment, and authority provenance.
Incremental UTF-8 redaction runs before any chunk is stored or shown, holds
structured/partial secrets until decided, and replaces overlong undecidable
input rather than allowing unbounded memory. Terminal state and receipt are
committed together, and a receipt binds the authority, profile, backend,
template digest, truncation, and redaction count. Browser reload reads ordered
durable chunks. If process restart leaves no authenticatable backend handle,
Raiker records `lost`; it never infers success.

The selected container command path preserves the exact approved argv and
requires a digest-pinned image, no network, read-only root, dropped
capabilities, `no-new-privileges`, bounded resources, `.raiker` masking, and
read-only `.git`.

The `native_sandbox` path is an operating-system boundary. On Windows each
command runs in its own AppContainer, created before launch and deleted at reap
— per run, because the container SID is a pure function of the profile name and
a predictable name would let any local process enter a container the workspace
already trusts. The profile holds **no network capability**, so egress is
dropped by the Windows Filtering Platform rather than by a rule the command is
asked to respect. The workspace is reachable through a single capability grant
written once; `.raiker` and `.git` carry protected DACLs with explicit entries
that are re-verified before every launch, because an explicit ACE is what beats
an inherited one and a recreated `.raiker` would otherwise carry only the
inherited allow. A Job Object with `KILL_ON_JOB_CLOSE` takes the whole process
tree, and the runner itself is bound to a job the runtime owns so a hard kill of
Raiker is reaped by the kernel. Linux uses bubblewrap with `--unshare-net`;
macOS uses a generated Seatbelt profile and reports its weaker process-tree
posture rather than inheriting the claim.

**No capability is claimed that was not measured.** A probe builds the real
boundary over the real workspace and runs a child inside it that attempts six
things, each also attempted outside the boundary as a control arm: the stream
relay, a write inside the workspace, a write to the workspace's parent and to
the user profile, a read of masked `.raiker`, an outbound connection, and a
detached grandchild. Only *outside succeeded and inside failed* counts as
enforcement. *Outside failed* is `indeterminate` and never turns a capability
on — without that rule an air-gapped host would report a network boundary it
does not have, and a host whose firewall service is stopped would report
AppContainer network isolation that is no longer being applied. The receipt
keeps two claims apart: `boundary_constructed` is what this run's runner built,
`probe_observations` is what the host was measured to enforce and when.

PTY/background supervision, filtered egress, credential quarantine, restart
reattachment, persistent sessions, and remote command supervisors are still not
security boundaries; see BUG-194 and the compatibility matrix.


## Server-side request forgery (SSRF)

**Requirement (owner, 2026-10-26): a tool-calling agent must not be able to make
Raiker send a request to the owner's own network or a cloud metadata service.**
Every path by which a model's tool call can choose, or steer, a destination is
listed here with what stops it. A path that is not in this table does not take
a destination from a model.

| Path | What the model controls | What stops SSRF | Where |
|---|---|---|---|
| `web_fetch`, `web_extract`, `web_search` (and its extended reads) | The URL | Only `http` and `https`. Every address the name resolves to must be public (loopback, private, link-local, CGNAT, multicast, unspecified and IPv4-mapped forms refused); the built-in names (`localhost`, `*.local`, metadata hosts) always refused. The connection is pinned to the checked address, so DNS cannot change between check and request. Redirects are never followed by the client; each hop is checked again. Flagging a site alerts and does not refuse, but nothing opens the address guard | `raiker/runtime/web_policy.py`, `web_access.py` |
| The same reads on a proxy-only host | The URL | Only a name this machine cannot resolve takes the proxy, and only when it has the shape of a public name (`public_shaped_name`): a single-label name or a private-network suffix (`.corp`, `.internal`, `.lan`, `.home.arpa`, …) is refused, never proxied, and a literal address never reaches the proxy. The name is then looked up through the proxy over DNS over HTTPS (`RAIKER_WEB_DOH_ENDPOINT`, default Cloudflare's) and every answer must pass the address guard; **a lookup that cannot be made refuses the read** (`web_host_unverified`, owner's decision 2026-10-26) | `web_policy.py` (`resolve_via_proxy`) |
| Connector reads and writes (GitHub, Gmail, Calendar, Slack, manifest connectors) | Path values, ids, bodies | The host is fixed by the connector, never taken from the model; model values are percent-encoded into the path; the host must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`; **no redirect is ever followed** (`redirect_refused:<status>`), so a token cannot be carried to another host | `raiker/runtime/executors/sandbox.py` (`get_url`, `post_url`, `post_json_url`), `connector_ecosystem.py` |
| Remote MCP calls | Tool arguments only; the endpoint is the owner's | Endpoint classified when the owner adds it; pinned to its checked address; redirects re-checked and never followed by the client | `mcp_endpoint_policy.py`, `sandbox.py` (`_mcp_opener`) |
| Shell commands | The command | `curl`, `wget`, `nc`, `ssh`, `socat` and the interpreters are refused as commands; code runs in the native sandbox with no network, or on the host only after the owner turns on `host_network_code_execution` | `raiker/runtime/command_policy.py`, `raiker/execution/code_placement.py` |
| `git_push` | The remote name | Only `https` or SSH to a known forge host, no credentials in the URL, the host on the push egress allowlist | `raiker/tools/git.py` |

**Residual risk, stated plainly.** On a proxy-only host the checked DNS
answer is not a pin: the proxy resolves the name again when it connects, so a
name re-pointed to a private address in the moment between the two lookups
(DNS rebinding with a very short TTL) is the remaining window. A name that
simply points inside a network is refused. Code the owner has allowed to run on
the host with network access (`host_network_code_execution`) can reach anything
the host can; that is an owner grant of arbitrary code, not a URL Raiker can
check.

## Model supply and readiness controls

Readiness fails closed and is exact-model scoped. Hosted checks make a bounded
one-token request only after explicit owner setup; errors are classified without
returning provider bodies or credentials. Local discovery has no ambient disk
search: the owner approves each absolute root, scans are bounded, and symlink
escapes are ignored. Hub downloads use immutable revisions, expose licence and
gating before confirmation, never place tokens on argv or in returned URLs, and
write collision-safe snapshots. Conversion accepts Safetensors only and runs
without network in a digest-pinned container with read-only source, separate
output, dropped privileges and resource limits.

### Usage credentials and compaction summaries

Inference credentials remain write-only and encrypted. OpenAI and Anthropic
organization-usage integrations accept an optional, separately encrypted admin
key; it is used only by the explicit provider-usage refresh and never by model
execution. OpenRouter uses its ordinary API key for the provider's key-status
endpoint. Ollama exposes no account quota. All provider responses are bounded to
1 MiB, normalized immediately to non-negative finite numeric metrics, and cached
without account identifiers, key labels, response bodies, headers, or secrets.

Conversation compaction sends only completed earlier exchanges to the already
selected provider. The request has no tools and reasoning is disabled. Stored
summaries are scoped to owner and session in the encrypted database; the audit
log contains counts, estimates, boundaries, and safe reason codes only. The
original transcript remains authoritative and unchanged.
