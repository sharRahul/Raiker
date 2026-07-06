# Plugins

> Platform & Integrations › Plugins. Back to [Platform & Integrations](platform-integrations.md).

Installed plugins are governed on install (signed manifests — HMAC + Ed25519 —
dependency controls, safe permissions) and can run in escalating isolation:

- **Brokered read-only tools** (`plugin_execution_cap`) — no code, just safe
  read tools through the broker.
- **Bounded subprocess** (`plugin_runtime_cap`) — the entrypoint runs as a
  subprocess; owner plugin allowlist + interpreter allowlist + workspace scope.
- **No-network container** (`plugin_sandboxed_runtime_cap`) — the entrypoint runs
  inside an owner-allowlisted image with `--network none` and only the entrypoint
  file mounted read-only.

Prefer the container runtime for untrusted plugins. See
[`PLUGIN_SYSTEM_SPEC.md`](../PLUGIN_SYSTEM_SPEC.md).
