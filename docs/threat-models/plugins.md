# Threat Model - Plugin Install (Phase 4, slice 8)

`plugin_install` may join `REAL_EXECUTOR_CAPABILITIES` for one narrow operation:
recording a local plugin manifest after validation. This slice does not fetch,
unpack, import, execute, enable, or sandbox plugin code. The follow-on
`plugin_execution_cap` slice is documented separately in
`docs/threat-models/plugin-execution.md` and is limited to brokered read-only
tool invocation for installed plugins.

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
- Supply-chain checks are checksum verification over canonical manifest JSON
  plus signature verification. **Signature verification (slice 12):** when the
  owner sets `RAIKER_PLUGIN_SIGNING_KEY`, the manifest `signature` must be a
  valid HMAC-SHA256 over the canonical manifest content (the same body the
  checksum covers); a wrong, missing, or non-string signature fails closed
  (`signature_invalid` / `no_signature_in_manifest`) and no install record is
  written. When the key is unset, the signature remains a presence marker for
  the local-dev baseline (unchanged). Trust-model limit: this is a symmetric
  (owner-held key) integrity+authenticity check, not third-party asymmetric
  supply-chain signing; Ed25519 verification against an owner-trusted public key
  is tracked as future work (blocked on a usable crypto dependency in this
  environment).
- Safe install permissions are read-only only (`tool:read_file`,
  `tool:list_directory`, `tool:glob`, `tool:grep`, `event:read`, `ui:panel`,
  `memory:read`). Network, write, shell, filesystem-write, import, eval, exec,
  path escape, and unknown permissions do not install.
- **Dependency controls (slice 11):** any declared `dependencies` are validated
  statically and fail closed before an install record is written. Each
  dependency must resolve to an exact `(plugin_id, version)` pin — ranges,
  wildcards, and `latest` are rejected as `dependency_unpinned` — and each
  dependency plugin id must be on the owner allowlist
  `RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST` (comma-separated; empty = fail closed for
  any declared dependency). A manifest with no dependencies is unaffected. This
  is pure static validation: Raiker never downloads, resolves transitively, or
  installs a dependency in this slice.
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
- `tests/test_phase_4_plugin_dependency_controls.py` proves unpinned/unallowlisted
  dependencies fail closed at both the plan and governed-install layers, that
  pinned+allowlisted dependencies install, and that a dependency-free manifest is
  unaffected.
- `tests/test_phase_4_plugin_signature_verification.py` proves the presence-marker
  baseline when no signing key is set, HMAC verification when the owner key is
  set, fail-closed on wrong/other-key/tampered signatures, and that the governed
  install fails closed on a bad signature while installing a validly-signed
  manifest.
- `tests/test_executor_default_registry.py` proves `plugin_install` is registered
  while `plugin_execution_cap` remains absent from `REAL_EXECUTOR_CAPABILITIES`.
- `scripts/validate_runtime_enablement_readiness.py` continues to require
  `plugin_execution_cap` to have no default executor.
