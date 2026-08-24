# Threat Model — Gmail Read-Only Connector (web-app task 4)

> Status marker: runtime_enablement_candidate — real executor, default-ask
> decision mode, owner env-only credential, owner egress allowlist,
> metadata-only events.

Per-capability threat model required by
[`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md) before
`connector_gmail_runtime` may join `REAL_EXECUTOR_CAPABILITIES`. This is the
**second read connector** for Task 4 (governed service connectors) and
replicates the GitHub reference slice
([`connectors-github.md`](connectors-github.md)) exactly — same
store-nothing-new governed pattern, a different host + credential + resource.

## What this capability is

A model may read one Gmail **message** or **thread** through a brokered tool,
`gmail_read(resource, message_id)`. The fetched content is returned to the model
as **untrusted data, never instructions**. Reads only — send/reply/label/modify
actions are deliberately **not implemented** and fail closed.

The read uses Gmail's `format=metadata` view — the message `snippet` plus the
`Subject`/`From`/`To`/`Date` headers — so the connector never handles raw MIME
body bytes or attachments; only the bounded metadata summary crosses the
boundary.

Two surfaces, one governance:

1. **Chat-path tool** (`raiker/runtime/connectors.py::GmailConnectorService`,
   brokered as `gmail_read`): enforces, in order — the `connector_gmail_runtime`
   gate (disabled ⇒ fail closed), the per-capability decision mode (**default
   `ask` ⇒ the read is withheld**; `deny` ⇒ blocked; `auto` withholds too,
   because a network read carrying the owner token's mailbox scope off-machine is
   never low-risk), the owner credential (`RAIKER_GMAIL_TOKEN` unset ⇒ fail
   closed), the owner egress allowlist (`gmail.googleapis.com` absent from
   `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` ⇒ fail closed), and validated request
   components.
2. **Governed-action executor**
   (`raiker/runtime/executors/connectors.py::GmailConnectorExecutor`, operation
   `read`): the activation anchor for the gate. Reached only through
   `route_action` (which applies the gate, decision mode, and approval flow);
   artifacts are **metadata only** — resource, message id, subject, and content
   length — never the fetched body/snippet.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Gate off ⇒ nothing runs | `connector_gmail_runtime` state read from the persisted control plane; absent/disabled ⇒ `connector_gate_disabled`. |
| Default `ask` withholds | Decision mode `ask` (the default) and `auto` return `connector_withheld:*` without contacting Gmail; only an explicit owner `allow` lets standing reads run. `deny` ⇒ `connector_denied_by_decision_mode`. |
| Owner credential, env only | The OAuth token comes from `RAIKER_GMAIL_TOKEN` — never from tool arguments, the prompt, or the UI. Unset ⇒ `connector_not_configured`. |
| Owner egress allowlist | `gmail.googleapis.com` must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` (empty ⇒ deny). Absent ⇒ `connector_egress_denied`. A second, independent boundary on top of the fixed host. |
| No SSRF via model input | The model never supplies a URL. `resource` (`message`/`thread`) and `message_id` (URL-safe Gmail id, `^[A-Za-z0-9_-]{1,256}$`) are validated and the request URL is **built server-side** against the fixed host (`format=metadata`, fixed header set). Bad inputs ⇒ `unsupported_resource` / `invalid_message_id`. |
| Bounded read | Response capped at 200 KB fetched; per-message snippet truncated to 20 000 chars; a thread summarises at most the first 20 messages; a single GET, no following redirects to other hosts (the allowlist is re-checked only at the top-level URL — see residual risks). |
| Untrusted output | The content is wrapped as an untrusted-data block before it reaches the model; assistant/tool content is never instruction authority (existing runtime invariant). |
| No data leakage in audit | Broker events and stored tool actions drop the fetched `content` field; executor artifacts are metadata-only. The token never appears in arguments, URLs, events, or artifacts. Governance-relevant non-secret identifiers (`resource`, `message_id`) are kept for the audit trail. |
| AI principals | Capability gate + `route_action` block non-human principals from enabling the gate or raising the decision mode; enabling is human `runtime_gate_manager` only. |

## Activation requirements

Enabling `connector_gmail_runtime` requires a HUMAN `runtime_gate_manager`, the
`local_single_user_runtime` mode, the registered executor, a `threat_model_acks`
row referencing this document, and a human confirmation token. A *working* read
additionally requires the owner credential (`RAIKER_GMAIL_TOKEN`), the host on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, and the decision mode raised to `allow` —
none of which enabling the gate grants. The read-only **Connections** web
surface (`GET /api/connections`) reports each of these preconditions honestly so
the owner can see exactly what is still fail-closed.

## Residual risks & non-goals

- A read sends the owner's token to Gmail and pulls mailbox content onto the
  machine; that content is subject to Google's data handling and the token's
  scope. The default-ask decision mode exists so this never happens without a
  standing owner decision; the egress allowlist bounds *where* the request can
  go. Scope the token to the minimum needed (read-only `gmail.readonly`).
- `urllib` may follow HTTP redirects; a redirect target is not re-checked
  against the allowlist by `get_url`. The Gmail REST API does not redirect
  cross-host for these endpoints, and the request URL is server-built against
  `gmail.googleapis.com`, so this is low-risk today — but broadening the
  connector to attacker-influenced hosts must add per-hop allowlist enforcement
  first.
- A malicious sender could put adversarial text in a message subject/snippet. It
  is labelled untrusted data and cannot execute anything by itself; every action
  the model proposes afterwards still flows through the broker, policy, and
  approvals.
- The connector reads `format=metadata` only — it never decodes attachments or
  full MIME bodies, so attachment payloads never cross the boundary in this
  slice.
- Out of scope: send/reply/label/modify actions (require approval and a separate
  slice), listing/searching mailboxes, full-body/attachment extraction, other
  connectors (Calendar/Slack — same pattern, separate slices), and interactive
  OAuth/refresh-token flows (this slice uses an owner-provided access token
  only).
