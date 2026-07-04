# Threat Model - Plugin Execution (Phase 4, slice 9)

`plugin_execution_cap` may join `REAL_EXECUTOR_CAPABILITIES` for one bounded
operation: an installed plugin can invoke a safe read-only tool through the
existing `ToolBroker` and `PolicyEngine`. This is not arbitrary plugin code
execution. Raiker does not import plugin files, run plugin scripts, start
processes, open network connections, or grant write/runtime permissions in this
slice.

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and
  a confirmation token.
- Action input is metadata only: `plugin_id`, `tool_name`, `tool_args`, and an
  optional `entrypoint` audit label. Entrypoint text is never executed.
- The plugin must already have an `installed` record from the governed
  `plugin_install` path.
- The installed record must include the exact safe tool permission, for example
  `tool:read_file`.
- The only brokered tools in this slice are `read_file`, `list_directory`,
  `glob`, and `grep`. Write, shell, process, network, filesystem mutation,
  memory mutation, MCP/LSP, hooks, monitors, agents, channels, panels, and
  unknown tools fail closed before broker invocation.
- The executor routes allowed tools through `ToolBroker` with the existing
  workspace `PolicyEngine`; workspace path policy and managed denies still
  apply.
- The executor does not attach a broker event writer. This prevents read-file or
  grep output from being emitted by plugin-execution events. Runtime executor
  artifacts contain only metadata: execution id, plugin id, tool name, status,
  policy decision, and `output_redacted=true`.
- Every attempted invocation records a `plugin_execution_records` row with
  status `succeeded`, `denied`, or `failed`.

## Explicit non-goals

- No Python/PowerShell/shell/plugin-script execution.
- No plugin package download or archive extraction.
- No plugin imports, dynamic module loading, or subprocess sandbox.
- No network access.
- No filesystem writes.
- No plugin hook, MCP, LSP, monitor, agent, channel, panel, or theme activation.
- No cryptographic signature validation beyond the install-slice checksum and
  signature presence marker.

## Acceptance evidence

- `tests/test_phase_4_plugin_execution_runtime.py` proves default-disabled
  blocking, threat-model-ack activation, installed-plugin requirement, allowed
  read-only broker invocation, no output leakage in runtime artifacts,
  permission denial, write-tool denial, and workspace-policy preservation.
- `tests/test_executor_default_registry.py` proves `plugin_execution_cap` is now
  present in `REAL_EXECUTOR_CAPABILITIES`.
- `scripts/validate_runtime_enablement_readiness.py` continues to require
  remote/cloud and Tier-6 sensitive runtimes to have no default executor.
