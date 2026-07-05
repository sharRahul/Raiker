# Threat Model - Plugin Code Runtime (Phase 4, slice 14)

`plugin_runtime_cap` is the first capability that runs **arbitrary plugin
code**. It executes an installed plugin's declared entrypoint as a bounded
subprocess. Because plugin code is untrusted, the trust boundary is not the
manifest — it is the **owner**, who must both flip the gate and name the plugin
in an allowlist before any code runs.

This slice deliberately provides the same isolation posture as the existing
`shell_execution` / `process_execution` capabilities (separate process, timeout,
output caps, workspace-scoped cwd, interpreter allowlist). It does **not** yet
provide in-process import isolation or a kernel network-namespace jail; those
remain deferred to a future "sandboxed plugin runtime" slice (the
`container_execution_cap` path is the stronger-isolation option today).

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and
  a confirmation token.
- The plugin must already have an `installed` (non-revoked) record from the
  governed `plugin_install` path. A revoked plugin fails closed with
  `plugin_revoked`; an unknown one with `plugin_not_installed`.
- The plugin id must be present in the owner allowlist
  `RAIKER_PLUGIN_RUNTIME_ALLOWLIST` (comma-separated). The allowlist defaults to
  **empty**, so no installed plugin can run code until the owner explicitly
  names it (`plugin_runtime_not_allowlisted`). The install slice only ever
  records safe read-only permissions, so runtime authorization comes from this
  owner grant, never from the manifest.
- Only interpreters in `{python3, python, node}` may be launched
  (`interpreter_not_allowed:<name>`). The shared sandbox re-checks the
  interpreter against the same allowlist before spawning.
- The entrypoint must resolve to a real file **inside the workspace root**
  (`outside_workspace:entrypoint`, `entrypoint_not_found`). Absolute or `..`
  paths that escape the workspace fail closed.
- Extra arguments must be a list of strings, capped at 32 (`invalid_argument:args`,
  `too_many_args`). Commands are executed as an argv list — never through a
  shell — so shell metacharacters are inert.
- Execution is bounded: default 30s timeout (owner may lower via `timeout`,
  hard-capped at 120s) and 200 KB output caps. Timeouts and spawn failures
  surface as `plugin_runtime_sandbox:<reason>`.
- Runtime artifacts are **metadata only**: execution id, plugin id, interpreter,
  return code, stdout/stderr byte counts, truncation flag, and
  `output_redacted=true`. Plugin stdout/stderr content is never captured into
  events or artifacts.
- Every attempt records a `plugin_execution_records` row with status
  `succeeded`, `failed`, or `denied`.

## Explicit non-goals

- No in-process import or dynamic module loading of plugin code.
- No network-namespace isolation (a plugin subprocess has the host's ambient
  network, exactly as `shell_execution` does — the owner allowlist is the trust
  anchor). Kernel-isolated network-off execution stays in the
  `container_execution_cap` path.
- No plugin package download, archive extraction, or dependency install.
- No filesystem-write, memory, MCP, LSP, hook, monitor, agent, channel, or panel
  activation.
- No elevation of the install policy: manifests still cannot request runtime or
  write permissions; the owner allowlist is separate.

## Acceptance evidence

- `tests/test_phase_4_plugin_runtime.py` proves default-disabled blocking,
  threat-model-ack activation, installed-plugin requirement, owner-allowlist
  requirement (empty = fail closed), interpreter allowlist, workspace-escape
  denial, successful bounded execution, non-zero exit reporting, no
  stdout/stderr leakage in artifacts, revocation fail-closed, and that every
  attempt writes a `plugin_execution_records` row.
- `tests/test_executor_default_registry.py` proves `plugin_runtime_cap` is
  present in `REAL_EXECUTOR_CAPABILITIES`.
- `scripts/validate_runtime_enablement_readiness.py` and
  `scripts/validate_local_single_user_runtime.py` require `plugin_runtime_cap` to
  be a registered high-risk capability that defaults to disabled.
