# Threat model — telemetry export (`telemetry_export`)

`telemetry_export` takes the governed record **off the machine**: governed
events, as OTLP log records, to an OpenTelemetry collector the owner named.

It exists because Raiker records strictly more per governed action than any
compared product exports — the decision, where the decision came from, the gate
that admitted the action, the approval that carried it, and a hash chain over the
lot — and all of it stayed inside the product.
[Cowork exports six event types this way](https://claude.com/docs/cowork/monitoring),
including `tool_decision`, which carries a decision and its source. What Raiker
lacked was not the record. It was the wire.

It is a sibling of [`audit_export`](audit-export.md), not a corner of it, and the
difference is the whole reason it has its own gate and its own threat model:
an audit export writes a file beside the log; this one **leaves the machine**.

## What the capability does

`raiker/runtime/executors/tier2_telemetry.py` → `TelemetryExportExecutor`:

1. resolves the owner-scoped destination row named by the action's
   `destination_id`, refusing one owned by another principal;
2. reads the credential named by `header_ref` from the environment — a
   named-but-absent variable fails closed;
3. reads the indexed events after the destination's cursor, bounded to 500 per
   run;
4. encodes them as an OTLP/HTTP logs body (`raiker/events/otlp.py`);
5. POSTs it to the destination's `/v1/logs`, through `post_json_url` with an
   egress allowlist of exactly that destination's host; and
6. advances the cursor **only if the delivery landed**.

## What a record carries

| Mode | Contents |
|---|---|
| Default (metadata only) | `event_id`, `event_type`, `actor`, `session_id`, `turn_id`, `task_id`, `risk_level` — every one a column on `events_index`, which is what makes "metadata only" checkable rather than a claim |
| `include_content` (owner opt-in) | The above, plus the event payload through `redact_event_payload` — the same function the on-screen record and the audit export pass through |

The event's **`summary` is deliberately not a default attribute**. A summary
names the object an action acted on, which is a file path more often than not,
and a path is content.

## Reachability

| Question | Answer |
|---|---|
| Has a real executor? | **Yes** — registered in `REAL_EXECUTOR_CAPABILITIES` |
| Reachable by a **model**? | **No.** There is no tool for it in `TOOL_DEFINITIONS`; a delivery is an owner action only |
| Reachable by the owner? | **Yes** — `POST /api/telemetry/destinations/{id}/export` (Observability → Overview), through `RuntimeControlService.run_telemetry_export` |
| Executed on approval? | **No.** It is not in `EXECUTABLE_ON_APPROVAL`; the owner performs it directly, governed |
| Audited? | **Yes.** It enters through `route_action`, so exporting the log is an event in the log |
| Inert by default? | **Yes.** The gate ships enabled, as every capability with a real executor does — and with no destination configured there is nowhere for a record to go. Adding one is human-only |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| Content leaving without the owner asking | Metadata only unless `include_content` was set on the destination; the attribute set is a fixed tuple of index columns rather than "whatever the row had" | `raiker/events/otlp.py` |
| A secret riding out inside an opted-in payload | Every payload passes `redact_event_payload` before it is encoded — the same redaction the on-screen record passes | `raiker/events/export.py` |
| A credential being stored where a browser or a backup can read it | `header_ref` is an environment-variable **name**. The value is read at send time, sent, and never stored, returned, or written to an artifact; the create route refuses to accept a value at all | `tier2_telemetry.py`, `raiker/api/schemas.py` |
| Sending unauthenticated to a destination that needs a credential | A named-but-absent variable fails closed with `telemetry_credential_missing`, and nothing is sent | `tier2_telemetry.py` |
| Exporting to a destination belonging to another account | The row is read with the acting principal's id; a foreign `destination_id` is `telemetry_destination_not_found` | `tier2_telemetry.py` |
| A model choosing where the record goes | No tool exposes this capability, and the endpoint is read from a stored row rather than from an action argument | `raiker/models/tool_registry.py` |
| Events silently lost between runs | The cursor advances only on a delivery that landed, and is `(timestamp, rowid)` — insertion order — rather than `(timestamp, event_id)`, because an event id is a random UUID and one appended inside the same second could sort before the cursor | `raiker/storage/sqlite.py` |
| An unbounded body | 500 records per run, and a 4 MB backstop on the response read | `tier2_telemetry.py` |
| An automation configuring a destination unattended | `create_telemetry_destination` and `delete_telemetry_destination` refuse a non-human principal with `not_authorized_human` | `raiker/control/service.py` |
| A delivery happening with the gate closed | The action passes the `telemetry_export` capability gate before any executor runs; a closed gate returns `disabled_by_capability_gate` | `RuntimeAuthority.route_action` |

## Residual risk, stated plainly

* **A metadata-only export is still a disclosure.** Event types, session ids,
  risk bands and timing describe how the owner works, even with no content. A
  collector operator learns the shape of the work. Nothing here prevents that,
  and nothing should — it is the owner's record and the owner's decision.
* **The destination is trusted because the owner named it.** Raiker does not
  verify the collector's identity beyond TLS, and does not pin a certificate. The
  owner adding the URL is the authorisation, monitored rather than
  allowlist-blocked, as everywhere else in this product.
* **A delivery is not retried on a schedule.** There is no background sender: a
  run happens when the owner asks for one. Events accumulate behind the cursor
  until then, which is visible on the destination's card rather than implied.
* **Nothing is unsent once sent.** Turning `include_content` off stops future
  payloads; it does not reach into a collector and remove what already went.
