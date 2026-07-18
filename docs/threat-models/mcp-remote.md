# Threat Model — Remote MCP Transport (Monitored MCP Connections, Phase A)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. Grounded in
> `docs/SECURITY_AND_POLICY.md` → "Security Philosophy": owner-added remote
> connections are **allowed and monitored**, not prevention-blocked.

Per-capability threat model for the remote (HTTP) branch of the existing
`mcp_connector_runtime` capability. The stdio branch is covered by
`docs/threat-models/mcp-connector.md`.

## What the executor does

`raiker/runtime/executors/mcp.py::McpConnectorExecutor` gains an `http`
transport. For a connection whose stored `transport == "http"`, `mcp_connect` /
`mcp_list_tools` / `mcp_call_tool` run a bounded JSON-RPC-over-HTTP session
against the owner-added `endpoint_url` (`initialize` → `tools/list` or
`tools/call`), via `raiker/runtime/executors/sandbox.py::post_json_rpc`. An
`Mcp-Session-Id` returned by `initialize` is carried to later requests. Reached
only through `route_action` (capability gate + decision mode + approval + audit).

## Posture: monitored, not allowlist-blocked

Consistent with the Security Philosophy, the owner **adding** a remote URL is the
authorization. The transport does **not** require a pre-configured egress
allowlist and does not pre-emptively block the owner's chosen host. Safety comes
from **visibility + containment**, delivered across the monitored-MCP phases:
Phase A records the connection (`mcp_connection_added`, redacted to host only);
Phase B watches each session (redacted per-session telemetry + anomaly findings);
Phase C adds findings + notifications + an instant kill switch and a revocable
auto-pause circuit breaker. This document covers Phase A's transport; Phases B
and C are **implemented** and covered by `docs/threat-models/mcp-monitoring.md`.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Scheme validation | Only `http`/`https` endpoints; else `mcp_remote_invalid_endpoint`. |
| Owner token never stored | The token lives in an owner env var named by `auth_ref`; only the reference (name) is persisted — never the token. Read at call time. |
| Missing token fails closed | An `auth_ref` set but its env var unset → `mcp_remote_token_missing` (honest missing-prerequisite, not fabricated success). |
| Token never logged/returned | The bearer header is sent verbatim by `post_json_rpc` and never returned; artifacts/events carry metadata only. The API response layer additionally scrubs token-like values (`redact_response_body`). |
| Redacted output | Tool output returns block count + content length + redaction flag — never the raw content. |
| Bounded session | Per-request timeout (≤60 s) and a ≤200 KB response cap (`mcp_response_too_large`); unreachable host → `mcp_remote_unreachable`. |
| Tool errors fail closed | A JSON-RPC error or `isError` result → `ok=False` (`mcp_tool_error` / `mcp_tool_reported_error`), message redacted. |
| Owner isolation | The connection profile is keyed by `principal_id`; create/connect/rename/delete are owner-scoped, human-only. |
| Governance | AI principals are blocked by the capability gate + `route_action`; the AI can neither add a connection nor flip the gate. |

## Residual risks & non-goals (this phase)

- **No OAuth redirect flow yet** — remote auth is an owner-supplied token
  (env-referenced). OAuth authorization-code is a later additive phase.
- **Streaming/SSE** — the transport parses a single JSON response, a JSON array,
  simple SSE `data:` frames, or newline-delimited JSON. Long-lived SSE streams
  are out of scope for Phase A.
- **Redirects** — the initial scheme/host is validated; cross-host redirect
  hardening is tightened in a later phase.
- **Monitoring/containment** (anomaly detection, findings, notifications, kill
  switch, auto-pause) are **implemented** in Phases B–C per
  `docs/plans/2026-07-17-monitored-mcp-connections.md`; see
  `docs/threat-models/mcp-monitoring.md`. A remote connection is recorded,
  anomaly-scored per session, and owner-controllable (test/rename/delete/pause/
  resume/kill).
