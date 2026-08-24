# Threat Model — MCP Monitoring & Containment (Monitored MCP Connections, Phases B–C)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. Grounded in
> `docs/architecture/SECURITY_AND_POLICY.md` → "Security Philosophy": owner-chosen MCP
> connections are **monitored and containable**, not prevention-blocked.

Covers the monitoring layer (Phase B) and the containment layer (Phase C) that
sit on top of the `mcp_connector_runtime` capability (stdio + remote HTTP). The
transports are covered by `docs/threat-models/mcp-connector.md` (stdio) and
`docs/threat-models/mcp-remote.md` (HTTP).

## What the monitor does (Phase B)

After each governed MCP session the executor
(`raiker/runtime/executors/mcp.py::McpConnectorExecutor`) hands **redacted
telemetry** (`McpSessionTelemetry`) to
`raiker/security/mcp_monitor.py::McpSessionMonitor`. The monitor writes one
redacted `mcp_session_log` row (tool-call count, hosts as netloc only, byte
counts, error count, outcome), forms a rolling per-connection baseline, and
evaluates five deterministic anomaly rules — **new host**, **volume spike**,
**tool-set swap**, **sensitive-data shape**, **error/refusal burst**. Each hit
raises a redacted `security_findings` row and an `mcp_anomaly_detected` event.
The sensitive-shape rule classifies a value's *shape* transiently in the executor
(`shape_sensitivity`) and hands the monitor only a label — the value itself is
discarded before it can be stored.

## What containment does (Phase C)

`raiker/security/mcp_monitor.py::McpContainment` is the single owner-authoritative
transition path, shared by the monitor's automatic circuit breaker and the
owner's manual controls. Every transition writes `mcp_servers.monitor_state`
(`active` | `paused` | `killed`) plus a redacted `paused_reason` / `paused_at`,
emits its audit event (`mcp_connection_paused` / `mcp_connection_resumed` /
`mcp_connection_killed`), and raises an owner-facing `notifications` row.

- **Auto-pause circuit breaker.** A **high-severity** finding (tool-set swap,
  error/auth-failure burst, or a sensitive-shape value coinciding with a new
  host) transitions the connection to `paused` — once, without churning an
  ongoing incident.
- **Containment gate.** Before a session runs, the connector executor resolves
  the owning connection and refuses a `paused`/`killed` one with a clear,
  non-fabricated reason (`mcp_connection_paused` / `mcp_connection_killed`).
- **Owner controls.** `pause` (one-call stop), `kill` (instant kill switch), and
  `resume` (revoke either back to `active`) are human-only, owner-scoped
  control-service operations behind `POST /api/mcp/servers/{id}/pause|resume|kill`.
- **Surfacing.** Every finding and every transition raises a notification;
  `GET /api/mcp/servers/{id}/findings` and `GET /api/notifications` (+ mark-read)
  are owner-scoped read surfaces.

## Boundaries enforced (fail-closed / redacted)

| Control | Mechanism |
|---|---|
| No payload in telemetry | `McpSessionTelemetry` has no field that can hold a raw payload, token, argument value, or full URL — only counts, netloc hostnames, and sensitivity *labels*. |
| No value in findings/events | `security_findings.redacted_detail_json` and the `mcp_anomaly_detected` payload carry labels/counts/hostnames/tool names only. The raw value is dropped in the executor before the monitor is called. |
| No value in notifications | `notifications.title` / `body` are redacted human-readable copy; a pause/kill reason is a rule code + summary, never a payload. |
| Containment is honest, not a ban | A `paused`/`killed` session is refused as a missing-prerequisite (`mcp_connection_paused` / `mcp_connection_killed`), and the owner can always `resume` — containment never removes the owner's access. |
| Auto-pause fires once | The breaker transitions only when the connection is currently `active`, so one ongoing incident cannot churn `paused_at` or re-emit the event. |
| Owner isolation | Every read (baseline, findings, notifications) and every write (session log, finding, notification, state transition) is keyed by `principal_id`; a foreign owner resolves nothing and a foreign transition returns `False` with no side effect. |
| Human-only containment | `pause`/`kill`/`resume` resolve the acting principal and reject AI principals (`resolve_local_principal` + `principal_type != HUMAN`). The AI is never the trust anchor and cannot contain, resume, or bypass a connection. |
| Monitoring never fails the session | A monitoring/storage hiccup is swallowed (`_observe`) so a successful governed session is never turned into a failure; a raised finding still surfaces through the finding store + event. |

## Residual risks & non-goals

- **Post-hoc detection.** The monitor evaluates a session *after* it completes, so
  the first high-severity session runs before the breaker pauses the *next* one.
  This is the intended "monitor + contain" posture (detection is not prevention);
  the irreversible-action surface is bounded by the redacted, capability-gated
  executor and the instant owner kill switch.
- **Deterministic rules only.** The five rules are conservative and explainable —
  no fabricated "smart" scoring. Novel abuse that fits none of the rules is not
  auto-paused, but every session is still logged and owner-reviewable.
- **Rebuild resets state.** An explicit owner rebuild of a server profile
  (`mcp_server_create`) re-creates the row and returns `monitor_state` to
  `active`; this is a deliberate owner re-provisioning action, and containment
  remains owner-revocable regardless.
