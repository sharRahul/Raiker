# Plugin System Specification

Raiker plugins package reusable platform extensions. Plugins may provide commands, hooks, skills, subagents, channels, MCP servers, tool adapters, themes, TUI panels, memory adapters, model providers, and policy fragments.

Plugins are disabled by default unless explicitly enabled by user, project, or managed policy.

---

## Plugin Goals

The plugin system must support:

1. discoverable extension packages;
2. explicit manifests;
3. permission declarations;
4. trust and signature metadata;
5. install/enable/disable/update/remove lifecycle;
6. project/user/managed scopes;
7. compatibility constraints;
8. security review;
9. event logging;
10. rollback.

---

## Plugin Scopes

| Scope | Description | Default enabled |
|---|---|---:|
| user | Installed for one user across projects | no |
| project | Committed plugin reference for project | no, requires trust |
| local | Project-local gitignored plugin enablement | no |
| managed | Enterprise-approved plugin | yes if policy says so |
| bundled | Shipped with Raiker | yes if built-in and signed |

---

## Plugin Directory Layout

```text
plugins/
  my-plugin/
    raiker-plugin.json
    README.md
    LICENSE
    hooks/
      hooks.json
      scripts/
    commands/
      fix-tests.md
    skills/
      code-review.md
    agents/
      security-reviewer.md
    channels/
      slack-channel.json
    tools/
      tool_manifest.json
    mcp/
      server.json
    tui/
      panels.json
    policies/
      policy.fragment.json
    tests/
```

---

## Plugin Manifest Schema

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
    "tui_panels": []
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

## Plugin Components

### Commands

Plugins may add slash commands. Each command must define:

- name;
- description;
- input schema;
- expansion template;
- required permissions;
- whether it can run in background;
- examples;
- tests.

### Hooks

Plugins may add hooks, but hooks are inactive unless the plugin is enabled. Plugin hooks cannot override managed denies.

### Skills

A skill is a reusable procedural workflow. It must define:

- when to use it;
- required context;
- steps;
- tools it may propose;
- verification criteria;
- memory write rules;
- safety warnings.

### Subagents

A plugin may provide subagent profiles. Each subagent must define:

- role;
- allowed tools;
- model profile;
- memory scope;
- max task duration;
- whether it can ask side questions;
- whether it can spawn other agents.

### Channels

A plugin may add channel connectors. Channel plugins are high risk because they introduce external input.

Required controls:

- sender allowlist;
- pairing/authentication;
- session binding;
- rate limits;
- prompt-injection warnings;
- attachment scanning;
- permission relay policy.

### Tool Adapters

Tool adapters must be registered with the broker. They cannot execute directly from plugin code.

### TUI Panels

Plugins may add TUI panels, such as:

- test results;
- task progress;
- memory inspector;
- policy decisions;
- graph context;
- channel inbox.

Panels are display components only unless explicitly granted action permissions.

---

## Plugin Lifecycle

```text
discover
  -> inspect manifest
  -> verify compatibility
  -> verify checksum/signature if present
  -> security review
  -> install
  -> enable
  -> load components
  -> run validation hooks
  -> emit plugin_enabled event
```

Disable lifecycle:

```text
disable
  -> stop plugin async tasks
  -> unregister hooks/commands/tools/channels/panels
  -> keep audit history
  -> emit plugin_disabled event
```

Update lifecycle:

```text
check update
  -> compare manifest
  -> show permission diff
  -> require approval if permissions increased
  -> backup old version
  -> install new version
  -> run compatibility checks
  -> rollback on failure
```

---

## Permission Diff Requirements

Before enabling or updating a plugin, Raiker must show:

- new tools requested;
- broadened path access;
- network hosts added;
- shell access added;
- memory access added;
- channel access added;
- hooks with decision authority;
- background tasks;
- subagents that can spawn other agents.

---

## Plugin Trust Levels

| Trust level | Meaning |
|---|---|
| `unknown` | No provenance; disabled by default |
| `local_dev` | Local plugin under development |
| `project_reviewed` | Reviewed in this repository |
| `user_trusted` | User explicitly trusted |
| `managed_trusted` | Enterprise approved |
| `bundled_trusted` | Shipped/signed with Raiker |

Trust level does not bypass policy by itself. It only affects default enablement and warnings.

---

## Plugin Events

Required events:

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

## Plugin Security Requirements

Plugins must not:

- auto-enable themselves;
- silently add managed permissions;
- execute tools outside the broker;
- mutate memory outside memory governance;
- open channels without sender/session policy;
- access secrets without explicit permission;
- hide network access;
- disable audit logging;
- suppress security warnings.

---

## Plugin Testing Requirements

Tests must verify:

- manifest validation;
- invalid plugin rejected;
- disabled plugin contributes no hooks/commands/tools;
- permission diff detects increased permissions;
- plugin hook cannot override managed deny;
- plugin tool routes through broker;
- plugin update rollback works;
- plugin channel enforces sender allowlist.
