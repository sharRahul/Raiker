# Threat Model — Local MCP Connector (Control Deck task 4)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capability is integrated
> and governed/default-ask. Tool output never enters an artifact, an audit
> event, or the session log; it reaches the calling model only when the owner
> has raised the decision mode to `allow` (FIXED-17).

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
| Redacted results | The executor's `ExecutionResult` carries length + block-count + redaction flag only — raw content never enters the artifacts, the `action_executed` event, or the monitored session log. |
| Model-facing results | A caller may pass an in-process `content_sink` to receive the tool's text (FIXED-17: a projected `mcp__<server>__<tool>` call, so a model can read what the tool it called returned). The text is bounded (20 000 chars), framed as untrusted data rather than instructions, and never written to a durable record. Broker events additionally drop the *argument values* of such a call: they are opaque values composed for an outside program, not governance-relevant identifiers. |
| Owner consent for a model-issued call | The `mcp_connector_runtime` decision mode governs it, and the default `ask` **withholds**: a standing agent call needs the owner to raise the mode to `allow`. `auto` withholds too — a medium-risk reach into non-Raiker code is never treated as low-risk. |
| No implicit exposure | Only tools a connected server actually advertised are projected, only for the owning principal, and only while the connection is neither paused nor killed. A server name containing the `mcp__` separator is not projected at all, so a projected name can never resolve to a different server. |
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

- The connected server is owner-owned local code reached over stdio. Its output
  is untrusted: only its size is recorded, and the text — when the owner has
  enabled agent calls — is handed to the model labelled as data, never as
  instructions. The owner is responsible for what a server they configure does,
  and for the prompt-injection surface that reading its output creates; that is
  why the decision mode, not the gate alone, is what permits a model-issued
  call.
- Out of scope: remote HTTP/SSE MCP transport, OAuth discovery, arbitrary shell
  commands, and execution of unreviewed remote tools. Those remain fail-closed.
