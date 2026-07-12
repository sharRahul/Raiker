# Threat Model — Google Calendar Read-Only Connector (web-app task 4)

> Status marker: runtime_enablement_candidate — real executor, default-ask
> decision mode, owner env-only credential, owner egress allowlist,
> metadata-only events.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`connector_gcal_runtime` may join `REAL_EXECUTOR_CAPABILITIES`. Replicates the
GitHub reference slice ([`connectors-github.md`](connectors-github.md)) exactly —
same store-nothing-new governed pattern, a different host + credential +
resource.

## What this capability is

A model may read one Google Calendar **event** or **calendar** through a brokered
tool, `gcal_read(resource, calendar_id, event_id)`. The fetched content is
returned to the model as **untrusted data, never instructions**. Reads only —
create/update/delete/respond actions are deliberately **not implemented** and
fail closed.

Two surfaces, one governance:

1. **Chat-path tool** (`raiker/runtime/connectors.py::GcalConnectorService`,
   brokered as `gcal_read`): enforces, in order — the `connector_gcal_runtime`
   gate (disabled ⇒ fail closed), the per-capability decision mode (**default
   `ask` ⇒ withheld**; `deny` ⇒ blocked; `auto` withholds too, because a network
   read carrying the owner token's calendar scope off-machine is never
   low-risk), the owner credential (`RAIKER_GCAL_TOKEN` unset ⇒ fail closed), the
   owner egress allowlist (`www.googleapis.com` absent from
   `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` ⇒ fail closed), and validated request
   components.
2. **Governed-action executor**
   (`raiker/runtime/executors/connectors.py::GcalConnectorExecutor`, operation
   `read`): the activation anchor for the gate. Reached only through
   `route_action`; artifacts are **metadata only** — resource, calendar id,
   event id, title, and content length — never the fetched body.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Gate off ⇒ nothing runs | `connector_gcal_runtime` state read from the persisted control plane; absent/disabled ⇒ `connector_gate_disabled`. |
| Default `ask` withholds | Decision mode `ask` (the default) and `auto` return `connector_withheld:*` without contacting Google; only an explicit owner `allow` lets standing reads run. `deny` ⇒ `connector_denied_by_decision_mode`. |
| Owner credential, env only | The OAuth token comes from `RAIKER_GCAL_TOKEN` — never from tool arguments, the prompt, or the UI. Unset ⇒ `connector_not_configured`. |
| Owner egress allowlist | `www.googleapis.com` must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` (empty ⇒ deny). Absent ⇒ `connector_egress_denied`. |
| No SSRF via model input | The model never supplies a URL. `resource` (`event`/`calendar`), `calendar_id`, and `event_id` are validated against strict character classes, then **path-encoded** into a URL **built server-side** against the fixed host. Bad inputs ⇒ `unsupported_resource` / `invalid_calendar_id` / `invalid_event_id`. |
| Bounded read | Response capped at 200 KB fetched; description/body truncated to 20 000 chars; attendee list summarised as a count only; a single GET. |
| Untrusted output | The content is wrapped as an untrusted-data block before it reaches the model; assistant/tool content is never instruction authority. |
| No data leakage in audit | Broker events and stored tool actions drop the fetched `content`; executor artifacts are metadata-only. The token never appears in arguments, URLs, events, or artifacts. Non-secret identifiers (`resource`, `calendar_id`, `event_id`) are kept. |
| AI principals | Enabling the gate / raising the decision mode is human `runtime_gate_manager` only. |

## Activation requirements

Enabling `connector_gcal_runtime` requires a HUMAN `runtime_gate_manager`, the
`local_single_user_runtime` mode, the registered executor, a `threat_model_acks`
row referencing this document, and a human confirmation token. A *working* read
additionally requires the owner credential (`RAIKER_GCAL_TOKEN`), the host on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, and the decision mode raised to `allow`. The
read-only **Connections** web surface (`GET /api/connections`) reports each
precondition honestly.

## Residual risks & non-goals

- A read sends the owner's token to Google and pulls calendar content onto the
  machine; that content is subject to Google's data handling and the token's
  scope. The default-ask decision mode gates this; the egress allowlist bounds
  where the request can go. Scope the token to read-only (`calendar.readonly`).
- `urllib` may follow HTTP redirects; `get_url` does not re-check a redirect
  target against the allowlist. The Calendar REST API does not redirect
  cross-host for these endpoints and the URL is server-built against
  `www.googleapis.com`, so this is low-risk today — broadening to
  attacker-influenced hosts must add per-hop allowlist enforcement first.
- Adversarial event summaries/descriptions are labelled untrusted data and
  cannot execute anything by themselves; downstream actions still flow through
  the broker, policy, and approvals.
- Out of scope: create/update/delete/respond actions (require approval + a
  separate slice), listing/searching events, free/busy queries, other
  connectors, and interactive OAuth/refresh-token flows (owner-provided access
  token only).
