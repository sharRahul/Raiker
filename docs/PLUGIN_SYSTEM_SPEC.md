# Plugin System Specification

Raiker plugins package reusable platform extensions. Plugins may provide commands, hooks, skills, subagents, channels, MCP servers, LSP servers, monitors, tool adapters, themes, output styles, TUI panels, web/dashboard panels, mobile panels, memory adapters, model providers, user-configurable settings, dependency metadata, and policy fragments.

Plugins are disabled by default unless explicitly enabled by user, project, or managed policy.

The Raiker-native plugin component inventory and phase placement is tracked in [`docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](RAIKER_TOOL_AND_PLUGIN_CATALOG.md). Future builders must update that catalog when adding or changing plugin component types.

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
10. rollback;
11. component inventory and token/context-cost inspection;
12. reload/refresh semantics that do not auto-enable runtime code;
13. dependency and permission-diff review;
14. local-first operation with hosted/marketplace features gated until Phase 5.

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
      code-review/
        SKILL.md
        reference.md
        scripts/
    agents/
      security-reviewer.md
    channels/
      slack-channel.json
    tools/
      tool_manifest.json
    mcp/
      server.json
    lsp/
      server.json
    monitors/
      monitors.json
    tui/
      panels.json
    web/
      panels.json
    mobile/
      cards.json
    output-styles/
      terse.md
    themes/
      dark-raiker.json
    policies/
      policy.fragment.json
    tests/
```

---

## Plugin Manifest Schema

The strict manifest schema is defined in [`docs/PLUGIN_MANIFEST_SCHEMA.md`](PLUGIN_MANIFEST_SCHEMA.md). The example below is illustrative and must remain aligned with that schema.

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

Commands expand into Raiker action contracts. They must not execute code directly.

### Skills

A skill is a reusable procedural workflow. It must define:

- when to use it;
- required context;
- steps;
- tools it may propose;
- verification criteria;
- memory write rules;
- safety warnings.

Skills may be packaged as plugin components, but they still propose tools through the Tool Broker.

### Hooks

Plugins may add hooks, but hooks are inactive unless the plugin is enabled. Plugin hooks cannot override managed denies.

Hooks may target lifecycle, prompt, tool, permission, notification, task, subagent, compaction, plugin, and stop events only through documented hook contracts. Hook command execution uses the same command policy as normal tool execution.

### Subagents

A plugin may provide subagent profiles. Each subagent must define:

- role;
- allowed tools;
- denied tools;
- model profile;
- memory scope;
- max task duration;
- isolation profile;
- whether it can ask side questions;
- whether it can spawn other agents.

Subagent runtime spawning remains disabled until Phase 4 lifecycle and approval controls exist.

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

### MCP Servers

Plugins may declare MCP server configurations. MCP servers remain disabled until explicit trust, egress, resource visibility, and approval controls exist.

Required controls:

- per-server trust gate;
- startup approval;
- host/process/transport declaration;
- resource and tool inventory;
- `mcp_list_resources` and `mcp_read_resource` policy mapping;
- prompt-injection treatment for all MCP outputs;
- bounded startup wait and cancellation.

### LSP Servers

Plugins may declare LSP/code-intelligence server configurations. LSP servers may support diagnostics, definitions, references, type info, symbols, implementations, and call hierarchy.

Required controls:

- trusted workspace gate;
- trusted plugin gate;
- language/server binary provenance;
- read-only default;
- bounded diagnostics output;
- no shell/server startup without policy approval.

### Monitors

Plugins may declare background monitors/watchers. Monitors are high risk because they run commands or watchers in the background and feed events into the runtime.

Required controls:

- disabled by default;
- explicit enablement and approval;
- command policy equivalent to `shell`/`powershell`;
- event rate limiting;
- cancellation;
- maximum lifetime;
- no secret/log exfiltration;
- prompt-injection handling for monitor output.

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

### Web and Dashboard Panels

Plugins may add web/dashboard panels only through the shared workspace inspection/action contracts. They must not receive private bypass APIs or hidden tool execution privileges.

### Mobile Panels and Approval Cards

Plugins may add mobile panels or approval-card renderers only after mobile/client approval contracts exist. Mobile plugin UI must preserve action-bound approval and secret redaction.

### Output Styles

Plugins may add output style definitions that affect presentation. Output styles are visual/rendering components only.

Output styles must not:

- hide policy warnings;
- suppress citations, audit events, approval cards, or safety notices;
- change tool permissions;
- alter memory governance;
- impersonate system/managed policy messages.

### Themes

Plugins may add color themes. Themes are visual-only and must not have runtime authority.

### User Configuration

Plugins may declare user-configurable values. Configuration values must be typed, scoped, redacted where sensitive, and included in permission review if they affect network, memory, channels, shell, MCP, LSP, monitors, or hosted services.

### Dependencies

Plugins may declare dependencies on other plugins. Enabling a dependency must show the full transitive permission diff and cannot silently enable runtime code.

### Marketplace / Registry Metadata

Plugin marketplace or registry support is Phase 5. It requires supply-chain review, checksums/signatures, provenance, managed allow/deny policy, rollback, and privacy controls.

---

## Plugin Lifecycle

```text
discover
  -> inspect manifest
  -> verify compatibility
  -> verify checksum/signature if present
  -> calculate component inventory and permission diff
  -> security review
  -> install
  -> enable
  -> load components through phase gates
  -> run validation hooks only if policy permits
  -> emit plugin_enabled event
```

Disable lifecycle:

```text
disable
  -> stop plugin async tasks
  -> unregister hooks/commands/tools/channels/panels/servers/monitors
  -> keep audit history
  -> emit plugin_disabled event
```

Update lifecycle:

```text
check update
  -> compare manifest
  -> show permission diff
  -> show dependency diff
  -> require approval if permissions or runtime components increased
  -> backup old version
  -> install new version
  -> run compatibility checks
  -> rollback on failure
```

Reload lifecycle:

```text
reload
  -> reload inert metadata and display components
  -> recompute permission diff
  -> do not auto-enable new runtime components
  -> require restart/approval for monitors, MCP servers, LSP servers, channels, or hooks that execute commands
```

---

## Permission Diff Requirements

Before enabling or updating a plugin, Raiker must show:

- new tools requested;
- broadened path access;
- network hosts added;
- shell/PowerShell/Python execution added;
- memory access added;
- channel access added;
- hooks with decision authority;
- background tasks or monitors;
- MCP servers;
- LSP servers;
- output styles that affect response rendering;
- themes that alter UI;
- user configuration fields and sensitivity;
- dependencies and transitive permissions;
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

## Plugin Security Requirements

Plugins must not:

- auto-enable themselves;
- silently add managed permissions;
- execute tools outside the broker;
- mutate memory outside memory governance;
- open channels without sender/session policy;
- start MCP, LSP, monitor, shell, PowerShell, Python, remote, or container processes without approval and phase gates;
- access secrets without explicit permission;
- hide network access;
- hide dependencies or transitive permissions;
- disable audit logging;
- suppress security warnings.

---

## Plugin Testing Requirements

Tests must verify:

- manifest validation;
- invalid plugin rejected;
- disabled plugin contributes no hooks/commands/tools/channels/panels/servers/monitors;
- permission diff detects increased permissions;
- dependency diff detects transitive permissions;
- plugin hook cannot override managed deny;
- plugin tool routes through broker;
- plugin MCP and LSP servers do not start without trust and approval;
- plugin monitors do not start without explicit enablement and are cancellable;
- output styles and themes cannot alter policy or hide warnings;
- plugin update rollback works;
- plugin channel enforces sender allowlist.

## Phase 3 rollout slice A plugin policy boundary

Plugin registration planning now evaluates manifests as inert data. The planner may return `planned`, `pending_approval`, or `denied`; it never imports entrypoints, evaluates strings, launches subprocesses, opens network connections, starts MCP/LSP servers, starts monitors, applies output styles, loads themes, enables channels, or enables execution. Shell, network, filesystem mutation, MCP, LSP, monitor, channel, subagent, and hosted-service permissions require explicit future policy and approval lifecycle work before activation.
