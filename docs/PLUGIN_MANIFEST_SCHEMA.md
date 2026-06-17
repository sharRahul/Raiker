# Plugin Manifest Schema

This document is the strict schema reference for Raiker plugin manifests. It complements `docs/PLUGIN_SYSTEM_SPEC.md`.

Phase 1 must not execute plugins. Phase 3 introduces plugin validation and execution only after manifest validation, permission diff, trust checks, policy review, and tests exist.

---

## Canonical File

Every plugin must define:

```text
raiker-plugin.json
```

The file must be UTF-8 JSON. Unknown fields are rejected unless the schema version explicitly allows extensions.

---

## Required Manifest Schema

```json
{
  "schema_version": "1.0",
  "plugin_id": "com.example.raiker.security-review",
  "name": "Security Review Tools",
  "version": "0.1.0",
  "description": "Adds security review commands, hooks, and a subagent.",
  "author": {
    "name": "Example",
    "url": "https://example.com"
  },
  "license": "MIT",
  "raiker_version": ">=0.1.0 <1.0.0",
  "entrypoints": {
    "commands": ["commands/security-review.md"],
    "hooks": ["hooks/hooks.json"],
    "skills": ["skills/threat-model.md"],
    "agents": ["agents/security-reviewer.md"],
    "channels": [],
    "tools": [],
    "mcp_servers": [],
    "tui_panels": [],
    "web_panels": [],
    "mobile_panels": []
  },
  "permissions": [
    {
      "tool": "read_file",
      "argument_match": {"path": "**/*"},
      "reason": "Read source files for review"
    }
  ],
  "network": {
    "required": false,
    "allowed_hosts": []
  },
  "memory": {
    "read_scopes": [],
    "write_scopes": []
  },
  "supply_chain": {
    "source_url": null,
    "commit_sha": null,
    "checksum": null,
    "signature": null
  },
  "default_enabled": false
}
```

---

## Required Fields

| Field | Rule |
|---|---|
| `schema_version` | Required, currently `1.0`. |
| `plugin_id` | Required reverse-DNS-style stable ID. |
| `name` | Required human-readable name. |
| `version` | Required semantic version. |
| `description` | Required short description. |
| `author` | Required object with at least `name`. |
| `license` | Required license identifier or `proprietary`. |
| `raiker_version` | Required compatibility range. |
| `entrypoints` | Required object; arrays default to empty. |
| `permissions` | Required array; can be empty. |
| `network.required` | Required boolean. |
| `network.allowed_hosts` | Required array. |
| `supply_chain` | Required object; values may be null for local dev. |
| `default_enabled` | Required boolean; must be false except bundled/signed plugins. |

---

## Permission Declaration Rules

Plugin permissions are requests, not grants. A plugin cannot grant itself access.

Each permission must include:

- tool or capability name;
- argument/path/host/scope match where relevant;
- reason;
- whether permission is optional or required;
- expected user-visible effect.

Permission expansion during update must create a permission diff and require approval.

---

## Trust Rules

Allowed trust levels:

```text
unknown
local_dev
project_reviewed
user_trusted
managed_trusted
bundled_trusted
```

Trust level affects warnings and default enablement only. Trust does not bypass policy.

---

## Plugin Runtime Boundaries

Plugins must not:

- execute tools directly;
- run shell commands outside the broker;
- register channels without sender/session policy;
- write memory outside memory governance;
- add hooks with hidden decision authority;
- access secrets without explicit permission;
- disable events or policy checks;
- auto-enable themselves.

---

## Required Events

- `plugin_discovered`
- `plugin_manifest_loaded`
- `plugin_manifest_invalid`
- `plugin_permission_diff_created`
- `plugin_installed`
- `plugin_enabled`
- `plugin_disabled`
- `plugin_updated`
- `plugin_update_failed`
- `plugin_removed`
- `plugin_component_registered`
- `plugin_component_failed`

---

## Acceptance Tests

Tests must prove:

1. valid manifest loads;
2. missing required field is rejected;
3. unknown fields are rejected in strict mode;
4. invalid version range is rejected;
5. `default_enabled=true` is rejected unless bundled/managed policy allows it;
6. permission diff detects added shell/network/memory/channel access;
7. disabled plugin contributes no commands/hooks/tools/channels/panels;
8. plugin tool adapter routes through Tool Broker;
9. plugin hook cannot override managed deny;
10. plugin channel requires pairing and sender trust.
