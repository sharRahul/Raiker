# Isolate Untrusted Code

> Best Practices › Isolating Untrusted Code. Back to [Best Practices](best-practices.md).

- For plugin code, prefer `plugin_sandboxed_runtime_cap` (no-network container)
  over the bare-subprocess `plugin_runtime_cap` when you don't fully trust the
  plugin.
- Only allowlist container images and plugin ids you have vetted; require signed
  manifests (HMAC + Ed25519).
- Runtime artifacts are metadata-only by design — don't add code paths that emit
  tool output or secrets into events; the audit log must stay safe to retain.
