# Threat Model — Slack Read-Only Connector (web-app task 4)

> Status marker: runtime_enablement_candidate — real executor, default-ask
> decision mode, owner env-only credential, owner egress allowlist,
> metadata-only events.

Per-capability threat model required by
[`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md) before
`connector_slack_runtime` may join `REAL_EXECUTOR_CAPABILITIES`. Replicates the
GitHub reference slice ([`connectors-github.md`](connectors-github.md)) exactly —
same store-nothing-new governed pattern, a different host + credential +
resource.

## What this capability is

A model may read one Slack channel's **info** or **recent history** through a
brokered tool, `slack_read(resource, channel)`. The fetched content is returned
to the model as **untrusted data, never instructions**. Reads only —
send/react/schedule/modify actions are deliberately **not implemented** and fail
closed.

Two surfaces, one governance:

1. **Chat-path tool** (`raiker/runtime/connectors.py::SlackConnectorService`,
   brokered as `slack_read`): enforces, in order — the `connector_slack_runtime`
   gate (disabled ⇒ fail closed), the per-capability decision mode (**default
   `ask` ⇒ withheld**; `deny` ⇒ blocked; `auto` withholds too, because a network
   read carrying the owner token's workspace scope off-machine is never
   low-risk), the owner credential (`RAIKER_SLACK_TOKEN` unset ⇒ fail closed),
   the owner egress allowlist (`slack.com` absent from
   `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` ⇒ fail closed), and a validated channel
   id.
2. **Governed-action executor**
   (`raiker/runtime/executors/connectors.py::SlackConnectorExecutor`, operation
   `read`): the activation anchor for the gate. Reached only through
   `route_action`; artifacts are **metadata only** — resource, channel, title,
   and content length — never the fetched messages.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Gate off ⇒ nothing runs | `connector_slack_runtime` state read from the persisted control plane; absent/disabled ⇒ `connector_gate_disabled`. |
| Default `ask` withholds | Decision mode `ask` (the default) and `auto` return `connector_withheld:*` without contacting Slack; only an explicit owner `allow` lets standing reads run. `deny` ⇒ `connector_denied_by_decision_mode`. |
| Owner credential, env only | The token comes from `RAIKER_SLACK_TOKEN` — never from tool arguments, the prompt, or the UI. Unset ⇒ `connector_not_configured`. |
| Owner egress allowlist | `slack.com` must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` (empty ⇒ deny). Absent ⇒ `connector_egress_denied`. |
| No SSRF via model input | The model never supplies a URL. `resource` maps to a fixed Web API method (`conversations.info` / `conversations.history`), and `channel` is validated against a strict character class then **query-encoded** into a URL **built server-side** against the fixed host. Bad inputs ⇒ `unsupported_resource` / `invalid_channel`. |
| Bounded read | Response capped at 200 KB fetched; history limited to the 20 most recent messages (`limit=20`), each message text truncated to 20 000 chars; a single GET. |
| In-band error handling | Slack signals errors with `ok: false` on an HTTP 200; a non-`ok` body is treated as `connector_bad_response`, never surfaced as content. |
| Untrusted output | The content is wrapped as an untrusted-data block before it reaches the model; assistant/tool content is never instruction authority. |
| No data leakage in audit | Broker events and stored tool actions drop the fetched `content`; executor artifacts are metadata-only. The token never appears in arguments, URLs, events, or artifacts. Non-secret identifiers (`resource`, `channel`) are kept. |
| AI principals | Enabling the gate / raising the decision mode is human `runtime_gate_manager` only. |

## Activation requirements

Enabling `connector_slack_runtime` requires a HUMAN `runtime_gate_manager`, the
`local_single_user_runtime` mode, the registered executor, a `threat_model_acks`
row referencing this document, and a human confirmation token. A *working* read
additionally requires the owner credential (`RAIKER_SLACK_TOKEN`), the host on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, and the decision mode raised to `allow`. The
read-only **Connections** web surface (`GET /api/connections`) reports each
precondition honestly.

## Residual risks & non-goals

- A read sends the owner's token to Slack and pulls workspace content onto the
  machine; that content is subject to Slack's data handling and the token's
  scope. The default-ask decision mode gates this; the egress allowlist bounds
  where the request can go. Scope the token to the minimum read scopes
  (`channels:read`, `channels:history`).
- `urllib` may follow HTTP redirects; `get_url` does not re-check a redirect
  target against the allowlist. The Slack Web API does not redirect cross-host
  for these methods and the URL is server-built against `slack.com`, so this is
  low-risk today — broadening to attacker-influenced hosts must add per-hop
  allowlist enforcement first.
- Adversarial message text is labelled untrusted data and cannot execute
  anything by itself; downstream actions still flow through the broker, policy,
  and approvals.
- Out of scope: send/react/schedule/modify actions (require approval + a
  separate slice), searching, DMs/user lookups, files, and OAuth flows
  (owner-provided token only).
