# Threat Model — Local MCP Connector (Control Deck task 4)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capability is integrated
> and governed/default-ask. Tool output is returned as redacted metadata only.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`mcp_connector_runtime` may join `REAL_EXECUTOR_CAPABILITIES`.

## What the executor does

`raiker/runtime/executors/mcp.py::McpConnectorExecutor`
(`mcp_connect` / `mcp_list_tools` / `mcp_call_tool`) runs a **bounded,
non-interactive** newline-delimited JSON-RPC stdio session against an
owner-configured local MCP server: it writes `initialize` +
`notifications/initialized` + one operation request, closes stdin, and matches
responses back by id. It speaks the documented MCP wire format directly (no
third-party SDK), so the runtime stays hermetic and local-only.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Interpreter allowlist | `command[0]` basename must be in `allowed_mcp_commands()` (`python`/`python3`/`node`, owner-extensible), else `mcp_command_not_allowlisted`. A shell is never a built-in. |
| Workspace-relative args | Any absolute or `..`-escaping argument is rejected with `mcp_argument_path_not_workspace_relative`. |
| Bounded session | `subprocess.Popen` with `cwd=workspace`, no shell; a `communicate` timeout (≤60 s) kills the process (`mcp_session_timeout`). |
| Bounded output | stdout over `MCP_MAX_OUTPUT_BYTES` (200 KB) fails closed (`mcp_response_too_large`). |
| Redacted results | Tool output is returned as length + block-count + redaction flag only — raw content never enters the artifacts or the audit event. |
| Tool errors fail closed | A JSON-RPC error or `isError` result returns `ok=False` (`mcp_tool_error` / `mcp_tool_reported_error`), with the server's message redacted. |
| Owner isolation | Connection bookkeeping writes an owner-scoped `mcp_servers` row keyed by `principal_id`. |
| AI principals | Capability gate + `route_action` block non-human principals from connecting or enabling the gate. |

## Activation requirements

Default gate state is enabled-runtime for the local single-user owner (a real
executor exists), governed per action by the default-`ask` decision mode.
Flipping the gate through the control plane requires a HUMAN
`runtime_gate_manager`, `local_single_user_runtime` mode, the registered
executor, a `threat_model_acks` row referencing this document, and a human
confirmation token. AI principals can never flip the gate.

## Residual risks & non-goals

- The connected server is owner-owned local code reached over stdio; its tool
  output is treated as untrusted and only its size is surfaced. The owner is
  responsible for what a server they configure does.
- Out of scope: remote HTTP/SSE MCP transport, OAuth discovery, arbitrary shell
  commands, and execution of unreviewed remote tools. Those remain fail-closed.
