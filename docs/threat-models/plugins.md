# Threat Model - Plugin Install (Phase 4, slice 8)

`plugin_install` may join `REAL_EXECUTOR_CAPABILITIES` for one narrow operation:
recording a local plugin manifest after validation. This slice does not fetch,
unpack, import, execute, enable, or sandbox plugin code. `plugin_execution_cap`
remains fail-closed with no default executor.

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and
  a confirmation token.
- Action input is `manifest_path` only. The executor resolves it inside the
  workspace and rejects absolute/relative escapes with
  `outside_workspace:manifest_path`.
- Manifest files are local JSON objects only and are capped at 1 MB.
- The existing plugin registration policy must return `planned`. Denied or
  pending-approval manifests fail closed and create no install record.
- Supply-chain checks are current repository checks: checksum verification over
  canonical manifest JSON plus required signature field presence. The signature
  field is a presence marker in this slice, not cryptographic signature
  validation.
- Safe install permissions are read-only only (`tool:read_file`,
  `tool:list_directory`, `tool:glob`, `tool:grep`, `event:read`, `ui:panel`,
  `memory:read`). Network, write, shell, filesystem-write, import, eval, exec,
  path escape, and unknown permissions do not install.
- Events and executor artifacts are metadata only: record id, plugin id, version,
  trust level, permission count, and `execution_enabled=false`. Manifest content,
  permission bodies beyond count, and file contents are not emitted.

## Explicit non-goals

- No plugin code execution.
- No package download or marketplace fetch.
- No archive extraction or filesystem writes beyond the install-record table.
- No runtime permission grants.
- No automatic enablement of plugin panels, tools, hooks, MCP servers, or agents.

## Acceptance evidence

- `tests/test_phase_4_plugin_install_runtime.py` proves default-disabled
  blocking, threat-model-ack activation, safe manifest install recording, risky
  permission rejection, bad checksum rejection, and workspace path rejection.
- `tests/test_executor_default_registry.py` proves `plugin_install` is registered
  while `plugin_execution_cap` remains absent from `REAL_EXECUTOR_CAPABILITIES`.
- `scripts/validate_runtime_enablement_readiness.py` continues to require
  `plugin_execution_cap` to have no default executor.
