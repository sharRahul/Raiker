# Execution Environments

> Platform & Integrations › Execution Environments. Back to [Platform & Integrations](platform-integrations.md).

- **Local sandbox** — `shell_execution` / `process_execution` run through a
  bounded subprocess sandbox (timeouts, output caps, command allowlist).
- **Containers** — `container_execution_cap` runs an owner-allowlisted image with
  `--network none`, read-only rootfs, dropped capabilities, and resource limits.
- **Remote / cloud** — `remote_execution_cap` / `cloud_execution_cap` remain
  fail-closed by design pending real isolation, egress, and secret handling.

For plugin execution environments, see [Plugins](platform-integrations-plugins.md).
