# Threat Model - Sandboxed Plugin Code Runtime (Phase 4, slice 16)

`plugin_sandboxed_runtime_cap` runs an installed plugin's entrypoint **inside a
container** with no network, a read-only rootfs, dropped capabilities, and only
the single entrypoint file bind-mounted read-only. It is the stronger-isolation
counterpart to `plugin_runtime_cap` (slice 14), which runs a bare subprocess
with the host's ambient network. Use this capability when the owner wants
untrusted plugin code to run with kernel-level network and filesystem isolation.

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and
  a confirmation token.
- The plugin must have a non-revoked `installed` record from the governed
  `plugin_install` path (`plugin_not_installed` / `plugin_revoked`).
- The plugin id must be in the owner allowlist `RAIKER_PLUGIN_RUNTIME_ALLOWLIST`
  (empty = fail closed → `plugin_runtime_not_allowlisted`). This is the same
  owner grant that authorizes bare-subprocess runtime; the owner names which
  plugins may run code at all.
- The owner must select a container image in `RAIKER_PLUGIN_RUNTIME_IMAGE`
  (`plugin_runtime_image_unset`) **and** that image must be in the shared owner
  image allowlist `container_image_allowlist()`
  (`RAIKER_CONTAINER_IMAGE_ALLOWLIST`) or the run fails closed
  (`image_not_allowed`). An empty allowlist denies everything.
- Only interpreters in `{python3, python, node}` may be launched
  (`interpreter_not_allowed:<name>`); the entrypoint must resolve inside the
  workspace root (`outside_workspace:entrypoint`, `entrypoint_not_found`) and,
  when configured, inside the plugin's `RAIKER_PLUGIN_RUNTIME_SCOPES` subpath
  (`entrypoint_outside_plugin_scope`, `plugin_scope_invalid`).
- Extra arguments must be a list of strings, capped at 32. The container is run
  as an argv list — never through a shell.
- The container is run with `--network none`, `--read-only`, `--cap-drop ALL`,
  `--security-opt no-new-privileges`, `--memory 512m`, `--cpus 1`, and
  `--pids-limit 256`. **No** host path is mounted except the single entrypoint
  file, bind-mounted read-only at `/plugin/<name>`. The workspace is never
  mounted.
- Bounded: default 60s timeout (owner may lower via `timeout`, hard-capped at
  300s) and 200 KB output caps. Missing daemon / sandbox errors surface as
  `plugin_sandbox:<reason>` (e.g. `plugin_sandbox:docker_unavailable`);
  non-zero exit as `plugin_sandbox_exit:<code>`.
- Runtime artifacts are metadata only (execution id, plugin id, image,
  interpreter, `network_isolated=true`, return code, byte counts,
  `output_redacted=true`); container stdout/stderr content is never captured
  into events or artifacts. Every attempt records a `plugin_execution_records`
  row.

## Explicit non-goals

- No workspace mount — plugin code sees only its own entrypoint file, not the
  repository.
- No network access from the container (kernel network namespace `none`).
- No in-process import or dynamic module loading of plugin code in the host.
- No plugin package download, archive extraction, or dependency install.
- No plugin hook, MCP, LSP, monitor, agent, channel, or panel activation.
- No image build or pull management — the owner supplies and allowlists the
  image out of band.

## Acceptance evidence

- `tests/test_phase_4_plugin_sandboxed_runtime.py` proves disabled-gate
  blocking, threat-model-ack activation, installed-plugin requirement, owner
  plugin-allowlist requirement, image-unset and image-not-allowlisted
  fail-closed, interpreter allowlist, workspace-escape denial, the no-network /
  read-only / single-file-mount docker argv, successful bounded execution with
  no output leakage, non-zero-exit reporting, and revocation fail-closed.
- `tests/test_executor_default_registry.py` proves
  `plugin_sandboxed_runtime_cap` is present in `REAL_EXECUTOR_CAPABILITIES`.
- `scripts/validate_runtime_enablement_readiness.py` and
  `scripts/validate_local_single_user_runtime.py` require the capability to be a
  registered high-risk capability that defaults to disabled.
