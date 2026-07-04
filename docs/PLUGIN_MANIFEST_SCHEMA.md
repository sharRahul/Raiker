# Plugin Manifest Schema

This document is the strict schema reference for Raiker plugin manifests. It complements `docs/PLUGIN_SYSTEM_SPEC.md` and the Raiker-native inventory in [`docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](RAIKER_TOOL_AND_PLUGIN_CATALOG.md).

Phase 1 must not execute plugins. Phase 3 introduces plugin validation and planning only after manifest validation, permission diff, trust checks, policy review, and tests exist. Runtime plugin execution remains disabled until explicit phase gates are complete.

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
    "skills": ["skills/threat-model/SKILL.md"],
    "agents": ["agents/security-reviewer.md"],
    "channels": [],
    "tools": [],
    "mcp_servers": [],
    "lsp_servers": [],
    "monitors": [],
    "tui_panels": [],
    "web_panels": [],
    "mobile_panels": [],
    "output_styles": [],
    "themes": []
  },
  "permissions": [
    {
      "tool": "read_file",
      "argument_match": {"path": "**/*"},
      "reason": "Read source files for review",
      "required": true,
      "expected_effect": "Allows the plugin skill to inspect source files."
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
  "user_config": {},
  "dependencies": [],
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
| `memory` | Required object with read/write scope arrays. |
| `user_config` | Required object; can be empty. |
| `dependencies` | Required array; can be empty. |
| `supply_chain` | Required object; values may be null for local dev. |
| `default_enabled` | Required boolean; must be false except bundled/signed or managed-policy plugins. |

---

## Entrypoint Fields

All entrypoints are metadata during Phase 3 planning unless the relevant runtime gate is explicitly enabled.

| Entrypoint | Component | First phase | Runtime activation rule |
|---|---|---:|---|
| `commands` | Slash commands / prompt shortcuts | Phase 3 | Expands into action contracts only. |
| `skills` | Reusable workflows | Phase 2 to Phase 3 | Proposes tools through Tool Broker. |
| `hooks` | Lifecycle/event handlers | Phase 3 | Cannot override managed denies. |
| `agents` | Subagent profiles | Phase 4 | Spawning disabled until lifecycle policy exists. |
| `channels` | External channel connectors | Phase 4 | Pairing/sender trust required. |
| `tools` | Tool adapters | Phase 3 | Must register through Tool Broker. |
| `mcp_servers` | MCP server definitions | Phase 3 to Phase 4 | Startup disabled until trust and approval gates exist. |
| `lsp_servers` | LSP/code-intelligence server definitions | Phase 3 | Startup disabled until workspace/plugin trust. |
| `monitors` | Background monitor/watch definitions | Phase 4 | Disabled by default; shell-equivalent approval required. |
| `tui_panels` | Terminal panels | Phase 3 | Display-only unless action permissions granted. |
| `web_panels` | Web/dashboard panels | Phase 3 | Must use shared workspace/action contracts. |
| `mobile_panels` | Mobile cards/panels | Phase 4 | Must preserve action-bound approval. |
| `output_styles` | Response/output style definitions | Phase 3 | Visual/rendering only; cannot hide policy or audit. |
| `themes` | Color theme definitions | Phase 3 | Visual-only; no runtime authority. |

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

## User Configuration Rules

`user_config` may declare typed plugin settings prompted at enable time or edited later.

Configuration fields must declare:

- key;
- type;
- default value;
- whether the value is secret/sensitive;
- scope: user, local, project, or managed;
- which tool permissions or runtime components the value affects.

Secret-like values must be redacted in events, plugin details, permission diffs, and UI summaries.

---

## Dependency Rules

`dependencies` must declare plugin IDs and compatible version ranges. Enabling dependencies must create a transitive permission diff.

**Install-time enforcement (Phase 4 slice 11):** the governed `plugin_install`
path validates declared dependencies statically and fails closed before writing
an install record. Each dependency must be an **exact pin** — object form
`{"plugin_id": "...", "version": "1.2.3"}` or string form `"dep.id==1.2.3"` /
`"dep.id@1.2.3"`; ranges, wildcards, and `latest` are rejected as
`dependency_unpinned`. Each dependency plugin id must be on the owner allowlist
`RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST` (comma-separated; empty = fail closed for
any declared dependency), otherwise `dependency_not_allowlisted`. Raiker does not
download, resolve transitively, or install a dependency in this slice.

A dependency cannot silently enable:

- shell/PowerShell/Python execution;
- MCP or LSP servers;
- monitors;
- external channels;
- subagents or workflows;
- network access;
- memory writes.

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
- run shell, PowerShell, Python, MCP, LSP, monitor, remote, or container processes outside the broker and phase gates;
- register channels without sender/session policy;
- write memory outside memory governance;
- add hooks with hidden decision authority;
- apply output styles that hide policy, audit, citations, or warnings;
- access secrets without explicit permission;
- disable events or policy checks;
- auto-enable themselves.

---

## Required Events

- `plugin_discovered`
- `plugin_manifest_loaded`
- `plugin_manifest_invalid`
- `plugin_permission_diff_created`
- `plugin_component_inventory_created`
- `plugin_dependency_diff_created`
- `plugin_installed`
- `plugin_enabled`
- `plugin_disabled`
- `plugin_updated`
- `plugin_update_failed`
- `plugin_removed`
- `plugin_reloaded`
- `plugin_component_registered`
- `plugin_component_failed`
- `plugin_mcp_server_planned`
- `plugin_lsp_server_planned`
- `plugin_monitor_planned`
- `plugin_runtime_activation_denied`

---

## Acceptance Tests

Tests must prove:

1. valid manifest loads;
2. missing required field is rejected;
3. unknown fields are rejected in strict mode;
4. invalid version range is rejected;
5. `default_enabled=true` is rejected unless bundled/managed policy allows it;
6. permission diff detects added shell/network/memory/channel access;
7. dependency diff detects transitive permission increases;
8. disabled plugin contributes no commands/hooks/tools/channels/panels/MCP servers/LSP servers/monitors;
9. plugin tool adapter routes through Tool Broker;
10. plugin hook cannot override managed deny;
11. plugin channel requires pairing and sender trust;
12. MCP/LSP server declarations remain inert until trust and approval gates pass;
13. monitor declarations remain inert until Phase 4 monitor policy passes;
14. output styles and themes cannot hide policy, audit, citations, or warnings;
15. user-config secret values are redacted.

## Phase 3 rollout slice A validation boundary

The implementation accepts the legacy compact test shape (`id`, `name`, `version`, `permissions`) and the canonical `plugin_id` field for validation/planning compatibility. Entrypoints are metadata only. Unknown trust levels, missing required fields, unsupported permission prefixes, and unsafe permission strings are denied during planning. Runtime execution remains disabled.

The expanded Raiker plugin component set added in this document is phase-scheduled only. It must not activate MCP servers, LSP servers, monitors, channels, subagents, hosted marketplace behavior, output styles, themes, or runtime plugin execution until their explicit implementation tasks and tests exist.
