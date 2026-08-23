# Plugin System Specification

Raiker plugins package reusable platform extensions.

**What a plugin contributes today — three kinds.** A plugin runs **no code of its
own**, in the runtime or in the browser. It contributes through a surface that
already governs the thing contributed, and each kind needs its own declared
permission, none of which is auto-approved:

| Kind | Permission | How it arrives |
|---|---|---|
| **Hook rules** | `event:hook` | Loaded at `plugin` scope, *below* every scope the owner controls, so a plugin can make an action stricter and can never loosen one the owner set |
| **Skills** | `skill:contribute` | Through the same validator an upload goes through, installed **switched off**, marked *from plugin* on Extensions → Skills |
| **MCP servers** | `mcp:server` | As an **offer**. Nothing is stored as a server, connected or reachable until the owner presses **Add server**, which runs the ordinary governed create path. An offer can never carry a credential — `https` only, no auth in the URL, `auth_ref` names an environment variable |

Revoking a plugin **deletes** what it contributed rather than flagging it.

**Everything below this line is the design target, not the shipped surface.** The
full list this document specifies — commands, subagents, channels, LSP servers,
monitors, tool adapters, themes, output styles, TUI panels, web/dashboard panels,
mobile panels, memory adapters, model providers, user-configurable settings and
policy fragments — is what a plugin *may eventually* provide. Two of them are
tracked as work (**panels**, BUG-228; **LSP servers**, BUG-227) and several are
[deliberately refused](REFERENCE_PLATFORM_COMPATIBILITY.md#4-deliberately-refused):
a plugin-authored executable on a command's `PATH` is plugin code execution with
an extra step, and a background monitor is a long-running command whose output
enters the turn.

Panels are worth naming precisely, and the precise statement changed on
2026-08-23. No *plugin component* in any compared platform is a panel —
[Claude Code's plugin components](https://code.claude.com/docs/en/plugins-reference)
are skills, agents, hooks, MCP servers, LSP servers and monitors — so as a
**plugin** contribution this is still a gap against this document rather than
against a reference platform.

What has changed is that the industry now has a specified, sandboxed way to do
the same job from the other side. **MCP Apps**
([SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp),
[`modelcontextprotocol/ext-apps`](https://github.com/modelcontextprotocol/ext-apps))
lets an MCP *server* pre-declare a UI resource under a `ui://` scheme, link it to
a tool through metadata, and have the host render it in a **mandatory sandboxed
iframe** with every message travelling over MCP's own JSON-RPC; Claude
[ships it](https://claude.com/docs/connectors/building/mcp-apps/getting-started)
behind a per-app owner permission.

That contract suits Raiker better than a plugin-drawn page would, for three
reasons this document already argues elsewhere: the server is something the
owner added deliberately rather than something a plugin added on its behalf; the
resource is declared ahead of time, so it can be fetched and reviewed before
anything runs; and the traffic is already the shape the audit log records. If
Raiker ever renders contributed UI, **this is the route to take, and a
`panels.json` is the route to drop** — building both would be two contradictory
UI-contribution models. Raiker's MCP client cannot reach it while pinned to
protocol revision `2024-11-05`; see
[`REFERENCE_PLATFORM_COMPATIBILITY.md` §2.6](REFERENCE_PLATFORM_COMPATIBILITY.md#26-extensibility--plugins-skills-mcp-channels).

Plugin execution slices are governed/default-ask unless explicitly tightened or disabled by user, project, or managed policy; broader plugin extensions remain deferred/fail-closed.

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
    phase8-ui/
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

A **plugin** cannot contribute a subagent. Raiker's own subagent surface is
implemented — `spawn_subagent` runs a caller-supplied list of read-only steps,
each re-brokered through the policy engine, and the `subagents` capability gate
ships off and is owner-flippable — but it is a per-turn bounded contract rather
than a named installable agent, so there is nothing for a plugin to register.

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

- governed/default-ask unless explicitly disabled or tightened;
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

## What A Plugin Actually Contributes Today

The component catalogue above is the target surface. This section is the build.

Until BUG-221, installing a plugin validated its manifest, checked its supply
chain, resolved its signature and wrote an install record — and then nothing
happened. `PluginRegistrationPlan.execution_enabled` was `False` by construction,
so a plugin contributed no skill, no agent, no hook, no MCP server and no panel.

The blocking question was never packaging. It was **what a plugin's code is
allowed to be**, and every other extension surface already answers it: a skill is
instructions and runs nothing, a connector is a brokered tool behind a capability
gate, a hook is argv resolved inside the workspace under a bounded timeout.

The answer taken is that a plugin **does not get an execution surface of its
own**. It contributes through a surface that already governs the thing
contributed, and they are taken in the order their authority story is written.

| Contribution | Available | Why it is where it is |
|---|---|---|
| Hooks | **yes** | A hook already has an execution model, a timeout, an audit trail and a scope. `plugin` sits below `managed`, `user`, `project` and `local`, so a plugin rule can make an action stricter and can never override a deny the owner set. |
| Skills | **yes** | Instruction text Raiker never executes, validated by the same reader an uploaded `SKILL.md` goes through. Provenance is carried on the stored row and the document lives inside the directory revocation already deletes. |
| MCP servers | no | Already brokered and gated, but not yet contributable from a manifest. |
| Panels | no | Need a route, permission and accessibility contract that does not exist. |

`execution_enabled` stays `False`. It is a different claim: a plugin still runs no
code of its own, and a hook rule it contributed runs as a **hook**, under the
hook's rules, not as plugin code.

### Contributing Hooks

A manifest declares the rules under `contributes.hooks`, in the same shape as a
hooks configuration file:

```json
{
  "id": "acme-guard",
  "version": "1.2.0",
  "permissions": ["event:hook"],
  "contributes": {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "shell",
          "if": "shell(rm -rf *)",
          "handlers": [
            { "id": "acme-block", "type": "builtin", "builtin": "block_destructive_shell" }
          ]
        }
      ]
    }
  }
}
```

Three refusals, all fail-closed and all named:

1. **No declared permission, no contribution.** The manifest must ask for
   `event:hook`. That permission is not in `SAFE_READ_ONLY`, so a plugin asking
   for it can never be auto-planned — the plan lands on `pending_approval` and the
   owner reads it in the permission diff *before* installing.
2. **A malformed contribution is refused at plan time**, with the parse error
   named, rather than being written and discovered later as a file that silently
   loads nothing.
3. **The contribution is a file the owner can read and delete.** Installing
   writes `.raiker/plugins/<plugin_id>/hooks.json`; the plugin id is held to a
   directory-safe shape rather than sanitised into one, so two ids can never
   collapse onto the same folder.

The plan and the CLI both state what would be contributed before the install, and
Extensions → Plugins states what each installed plugin provides — read from the
files the runtime loads, not from the manifest that described them.

### Contributing Skills

A manifest declares skills under `contributes.skills`, as a list (a single
mapping is accepted for a plugin shipping exactly one). Two shapes, both ending
at the same validator:

```json
{
  "id": "acme-skills",
  "version": "2.0.0",
  "permissions": ["skill:contribute"],
  "contributes": {
    "skills": [
      {
        "name": "acme-review",
        "description": "Review a change against Acme's internal checklist.",
        "body": "Check the changelog, then the tests, then the migration."
      },
      {
        "name": "acme-release",
        "document": "---\nname: acme-release\ndescription: Cut a release.\n---\n\nTag, then ship.\n"
      }
    ]
  }
}
```

`document` is a whole `SKILL.md` passed through verbatim; `body` is the prose
alone, with the frontmatter assembled the way `/skill-build` assembles it — so a
plugin cannot express a skill Raiker would otherwise refuse to build.

A skill runs nothing, which is why it came second and not first. What it does do
is put instruction text into the owner's turns, so five properties hold:

1. **Asking is required, and it is read before the install.** The manifest must
   ask for `skill:contribute`. It is outside `SAFE_READ_ONLY`, so the plan lands
   on `pending_approval` and the permission diff states it.
2. **It arrives switched off.** Installing the plugin was consent to *offer* the
   skill, not to run with it. The owner activates each one on Extensions →
   Skills, and that is a second, separate decision.
3. **Existence is on disk; the owner's choice is in the store.**
   `.raiker/plugins/<id>/skills/<name>/SKILL.md` decides what exists — it is what
   revocation deletes — and `SkillsService.sync_plugin_skills` reconciles the two
   in one direction only, preserving the on/off choice across a refresh.
4. **It never overwrites a skill the owner owns.** A name collision with an
   uploaded, built or imported skill leaves the owner's in place and drops the
   plugin's copy. Rename and delete are refused on a contributed skill with
   `skill_provided_by_plugin`, because the next sync would undo either; revoking
   the plugin is the control that removes it.
5. **One bad entry refuses only itself.** A manifest contributing five skills
   where the third is malformed installs four and names the one it dropped. More
   than `MAX_CONTRIBUTED_SKILLS` (20) is refused whole rather than truncated.

A refusal on one kind never removes the other: a manifest whose hooks are
malformed still installs its valid skills, and says which half it dropped.

### Revocation

Revoking a plugin **deletes** its contributed rules and skills rather than
annotating the record. `HooksRegistry.load` reads files and has no store to consult, so leaving
the file behind would produce the one state revocation exists to prevent: the page
says revoked and the runtime still runs the rule. `PluginRevocationExecutor`
reports `contributions_removed` in its artifacts, so a removal that did not happen
is visible rather than assumed.

Re-installing replaces the files rather than adding a second set, so an upgrade
that dropped a rule or a skill drops it here too. The skills store follows: a row
whose plugin no longer has a directory is deleted on the next sync, and the
runtime syncs before advertising what is active, so an active row cannot outlive
the file that authorised it.

---

## Phase 3 rollout slice A plugin policy boundary

Plugin registration planning now evaluates manifests as inert data. The planner may return `planned`, `pending_approval`, or `denied`; it never imports entrypoints, evaluates strings, launches subprocesses, opens network connections, starts MCP/LSP servers, starts monitors, applies output styles, loads themes, enables channels, or enables execution. Shell, network, filesystem mutation, MCP, LSP, monitor, channel, subagent, and hosted-service permissions require explicit future policy and approval lifecycle work before activation.
