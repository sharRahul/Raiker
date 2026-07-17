# Threat Model — Local MCP Builder (Control Deck task 4)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capability is integrated
> and governed/default-ask. Events are metadata-only.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`mcp_builder_runtime` may join `REAL_EXECUTOR_CAPABILITIES`.

## What the executor does

`raiker/runtime/executors/mcp.py::McpBuilderExecutor` (`mcp_server_create`)
writes a reviewed, dependency-free **local stdio** MCP server template to a
validated workspace-relative path and records an owner-scoped profile row in
`mcp_servers`. It performs a single filesystem write; it never spawns a process,
reaches the network, or executes the generated server.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Reviewed templates only | `template` must be an exact key in `_TEMPLATES`, else `mcp_unknown_template`. |
| Workspace-relative output | Absolute or `..`-escaping `output_path` is rejected with `mcp_output_path_not_workspace_relative`. |
| Safe server name | `name` is normalized to `[A-Za-z0-9._-]`, non-empty, ≤64 chars, else `mcp_invalid_server_name`. |
| Owner isolation | Every `mcp_servers` row is keyed by `principal_id`; one owner can never list or resolve another owner's servers. |
| Redacted events | Artifacts carry name/template/relative-path/byte-count only — never the file contents. |
| No fabricated success | A failed write returns `ok=False` with a reason; nothing is recorded as connected. |
| AI principals | Capability gate + `route_action` block non-human principals from building or enabling the gate. |

## Activation requirements

Default gate state is enabled-runtime for the local single-user owner (a real
executor exists), governed per action by the default-`ask` decision mode.
Flipping the gate through the control plane requires a HUMAN
`runtime_gate_manager`, `local_single_user_runtime` mode, the registered
executor, a `threat_model_acks` row referencing this document, and a human
confirmation token. AI principals can never flip the gate.

## Residual risks & non-goals

- The generated server is owner-owned code; the owner must review it before
  pointing anything sensitive at it. The shipped `python-stdio-echo` template is
  side-effect-free (echo + liveness only).
- Out of scope: remote MCP transport, OAuth discovery, non-stdio servers, and
  writing outside the workspace. Those remain fail-closed.
