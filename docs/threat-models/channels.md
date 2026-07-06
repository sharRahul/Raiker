# Threat Model — Reference Channel (Phase 4, slice 4)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capabilities are now
> integrated and governed/default-ask; they were historically disabled/deferred
> before their executors landed. Approval resolution is metadata-only.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`external_channel_runtime` and `channel_approval_relay` may join
`REAL_EXECUTOR_CAPABILITIES`. This is the **one reference channel** (webhook
transport) for the sandboxed-first Phase 4 rollout; other transports and
multi-connector fan-out remain gated/fail-closed.

## What the executors do

- `external_channel_runtime`
  (`raiker/runtime/executors/channels.py::ExternalChannelExecutor`) delivers a
  message to a **paired, enabled** connector by HTTP POST, constrained by an
  owner-controlled egress allowlist.
- `channel_approval_relay` (`ChannelApprovalRelayExecutor`) records a
  **pending** approval relay for a paired connector. It never resolves an
  approval — resolution stays metadata-only / owner-only.
- Inbound is separate (`raiker/api/routes_channels.py`): a receiver that is
  authenticated by an owner channel secret and labels **all** inbound traffic
  untrusted + quarantined; it records a governed event and executes nothing.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| No egress by default | `RAIKER_CHANNEL_EGRESS_ALLOWLIST` empty ⇒ `egress_denied:no_allowlist`. Model-proposed URLs can only reach owner-allowlisted hosts. |
| Connector must be paired | Delivery/relay require an enabled `channel_pairings` row, else `channel_not_paired_or_disabled`. |
| Outbound is bounded | `https`/`http` only, response size capped, short timeout; failures fail closed (`delivery_failed:*`). |
| No data leakage | Events carry metadata only (connector id, byte counts, status) — never the message text or target URL. |
| Inbound untrusted | Inbound is always `trust_level: untrusted`, `instructions_inert: true`, quarantined; requires the owner channel secret and a sender on the pairing allowlist (`sender_not_allowlisted` otherwise). |
| Relay is metadata-only | A relay is recorded `pending`; it cannot approve/execute anything. |
| AI principals | Capability gate + `route_action` block non-human principals from running or enabling the gate. |

## Activation requirements

Default gate state is **DISABLED**. Enabling requires a HUMAN
`runtime_gate_manager`, the `local_single_user_runtime` mode (Raiker is
single-user; the channel is a single-owner bridge), the registered executor, a
`threat_model_acks` row referencing this document, and a human confirmation
token. AI principals can never flip the gate.

## Residual risks & non-goals

- The outbound URL may come from (untrusted) action args; the **egress
  allowlist is the security boundary**, so it must only contain hosts the owner
  trusts. TLS for inbound exposure must be terminated by a reverse proxy.
- Out of scope: Slack/Signal/Teams/Discord native connectors, multi-connector
  routing, automatic approval resolution over a channel, and inbound messages
  driving the agent loop. Those remain gated and fail closed.
