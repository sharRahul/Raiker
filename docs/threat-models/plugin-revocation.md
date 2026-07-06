# Threat Model - Plugin Revocation (Phase 4, slice 10)

`plugin_revocation_cap` may join `REAL_EXECUTOR_CAPABILITIES` for one bounded
operation: a human owner can revoke a previously installed plugin so it can no
longer broker read-only tools through `plugin_execution_cap`. This is not
arbitrary plugin code execution and it does not delete history — it flips the
install record's status to `revoked` and records the change.

Revocation is the fail-closed "off switch" for the install/execution slices
(slices 8 and 9). It must exist before any broader plugin runtime so that a
plugin found to be malicious, over-permissioned, or simply unwanted can be
neutralised without deleting audit trail.

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and
  a confirmation token.
- Action input is metadata only: `plugin_id` and an optional `reason` audit
  label. The `reason` text is never executed or interpreted.
- The plugin must have a current `installed` record from the governed
  `plugin_install` path. Revoking a plugin that is not installed fails closed
  with `plugin_not_installed`.
- Revoking a plugin whose latest record is already `revoked` fails closed with
  `plugin_already_revoked` (idempotent no-op; no second mutation).
- Revocation only updates the `status` column of the latest matching install
  record from `installed` to `revoked`. It never deletes the record, edits
  permissions, imports plugin code, runs scripts, starts processes, opens
  network connections, or writes workspace files.
- After revocation, `plugin_execution_cap` fails closed for that plugin with
  `plugin_revoked` before any broker invocation, so a revoked plugin can no
  longer read files, list directories, glob, or grep.
- Runtime executor artifacts contain only metadata: record id, plugin id,
  previous status, new status, and whether a reason was supplied. Plugin
  contents and permission payloads are not emitted.

## Explicit non-goals

- No Python/PowerShell/shell/plugin-script execution.
- No plugin package download, archive extraction, or filesystem cleanup.
- No plugin imports, dynamic module loading, or subprocess sandbox.
- No network access.
- No filesystem writes outside the SQLite install-record status update.
- No plugin hook, MCP, LSP, monitor, agent, channel, panel, or theme activation
  or deactivation beyond the read-only broker path already denied to a revoked
  plugin.
- No cryptographic signature validation (tracked separately as future work).

## Acceptance evidence

- `tests/test_phase_4_plugin_revocation_runtime.py` proves disabled-gate
  blocking, threat-model-ack activation, installed-plugin requirement,
  successful revocation, idempotent already-revoked handling, no plugin content
  in runtime artifacts, and that `plugin_execution_cap` fails closed with
  `plugin_revoked` after revocation.
- `tests/test_executor_default_registry.py` proves `plugin_revocation_cap` is
  present in `REAL_EXECUTOR_CAPABILITIES`.
- `scripts/validate_runtime_enablement_readiness.py` continues to require the
  gate to default disabled and remote/cloud and Tier-6 sensitive runtimes to
  have no default executor.
