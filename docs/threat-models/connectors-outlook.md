# Threat Model — Outlook Read-Only Connector (Microsoft Graph)

> Status marker: runtime_enablement_candidate — real executor, default-ask
> decision mode, browser sign-in or owner env-only credential, Graph host only,
> metadata-only events.

Per-capability threat model required by
[`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md) before
`connector_outlook_runtime` may join `REAL_EXECUTOR_CAPABILITIES`. It follows
the Calendar slice ([`connectors-gcal.md`](connectors-gcal.md)): the same
governed pattern, with a different host, credential and set of resources.

## What this capability is

A model may read the owner's Outlook mail and calendar through a brokered tool,
`outlook_read(resource, item_id, count)`:

* `messages`: the newest inbox messages, at most ten.
* `events`: the next events, at most ten.
* `message` or `event`: one item, by id.

Each item is a fixed field selection: subject, people, times, location and
Graph's own short `bodyPreview`, never the full body or attachments. The
content is returned to the model as **untrusted data, never instructions**.
Reads only: send, reply, move, delete, accept and decline are deliberately
**not implemented**.

Two surfaces, one governance:

1. **Chat-path tool** (`raiker/runtime/connectors.py::OutlookConnectorService`,
   brokered as `outlook_read`).
2. **Governed-action executor**
   (`raiker/runtime/executors/connectors.py::OutlookConnectorExecutor`,
   operation `read`), reached only through `route_action`. Its artifacts are
   metadata only.

## The credential: a browser sign-in

The owner connects Outlook with **Connect**, which opens Microsoft's own
sign-in page in the system browser (RFC 8252, `raiker/runtime/connector_oauth.py`).

* **PKCE S256** and a random single-use `state` (32 bytes) bind the answer to
  the owner's own attempt. The attempt expires after ten minutes and is spent on
  first use, so a replayed or forged callback is refused.
* The redirect goes only to `127.0.0.1`/`localhost`, which Microsoft accepts for
  a *Mobile and desktop* public client. No client secret exists.
* The scopes are read-only: `User.Read Mail.Read Calendars.Read`, plus
  `offline_access` for a refresh token.
* The tokens are kept encrypted in the connector vault and never appear in an
  event, a log, an API response or a URL. An expired access token is renewed
  with the refresh token. A renewal Microsoft refuses fails closed as
  `connector_reauth_required`.
* The owner's own registration supplies the client ID, saved from Settings or
  set as `RAIKER_MICROSOFT_OAUTH_CLIENT_ID`. A bare token in
  `RAIKER_OUTLOOK_TOKEN` also works, for headless hosts.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Gate off ⇒ nothing runs | `connector_outlook_runtime` absent or disabled ⇒ `connector_gate_disabled`. |
| Default `ask` withholds | `ask` (the default) and `auto` return `connector_withheld:*` without contacting Microsoft; only an explicit owner `allow` lets standing reads run. `deny` ⇒ `connector_denied_by_decision_mode`. |
| A signed-in account | No signed-in account and no `RAIKER_OUTLOOK_TOKEN` ⇒ `connector_not_configured`. |
| One host | Signing in is the owner's consent to reach `graph.microsoft.com` and nothing else. Without a sign-in, that host must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`. |
| No SSRF via model input | The model never supplies a URL. `resource` is one of four words, `item_id` matches a strict character class and is path-encoded, and `count` is clamped to 1–10. The URL is built on the fixed host. |
| Bounded read | A fixed `$select`, at most ten items, content truncated to 20,000 characters, one GET. |
| Untrusted output | Wrapped as an untrusted-data block before the model reads it. |
| No data leakage in audit | Broker events and stored tool actions drop the fetched `content`; executor artifacts are metadata only. |
| AI principals | Enabling the gate or raising the decision mode is a human `runtime_gate_manager` action only. |

## Activation requirements

Enabling `connector_outlook_runtime` requires a HUMAN `runtime_gate_manager`,
the agent runtime switched on, the registered executor, a `threat_model_acks`
row referencing this document, and a human confirmation token. A *working* read
also needs a signed-in account and the decision mode raised to `allow`.

## Residual risks and non-goals

- A read sends the owner's token to Microsoft and brings mail and calendar
  metadata onto the machine, where it is subject to Microsoft's handling and the
  token's scope. The default-ask decision mode gates this.
- A message's subject or preview may be written by anyone who emails the
  owner. It is labelled untrusted and cannot run anything by itself; any action
  it prompts still goes through the broker, policy and approvals.
- Out of scope: sending, replying, moving, deleting, responding to invitations,
  attachments, full message bodies, searching, and shared mailboxes.
