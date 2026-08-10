# Plugin components, field by field

Read while building a component. Each section gives the file shape, the fields
that decide whether it works, and the failure that follows from getting one
wrong.

- [Commands](#commands)
- [Agents / subagent profiles](#agents--subagent-profiles)
- [Skills](#skills)
- [Hooks](#hooks)
- [MCP servers](#mcp-servers)
- [Panels, output styles and themes](#panels-output-styles-and-themes)
- [User configuration](#user-configuration)

## Commands

`commands/<name>.md` — a named prompt.

```markdown
---
description: Draft release notes from the pull requests merged since the last tag.
argument-hint: "[since-tag]"
allowed-tools: ["read_file", "git_log"]
---

Read the merged pull requests since $1 (default: the latest tag) and draft
release notes in the format `CHANGELOG.md` already uses…
```

| Field | Rule | Failure if wrong |
|---|---|---|
| `description` | One line, in the words a user types | The command is never suggested |
| `argument-hint` | What the arguments are, shown in the picker | Users guess and pass the wrong thing |
| `allowed-tools` | The narrowest set the body needs | Too wide: an authority request nobody reviewed. Too narrow: fails closed mid-run |

The body is a procedure. `$1`, `$2`, `$ARGUMENTS` interpolate the invocation.
Keep it short — a command that needs three screens of instruction is a skill
wearing a command's frontmatter.

## Agents / subagent profiles

`agents/<name>.md` — frontmatter plus a system prompt.

```markdown
---
name: release-historian
description: Use when someone asks what changed between two versions, or needs a
  release summary. Example — "what went into 0.4.2?" → delegate here.
tools: ["read_file", "git_log"]
model: inherit
---

You reconstruct what changed between two revisions…
```

The `description` is the whole delegation mechanism: it is what the orchestrator
reads when deciding whether to hand work over. Write the trigger, not the
philosophy, and include one concrete example. An agent that never gets delegated
to has a description problem, never a prompt problem.

Give an agent the smallest tool set that lets it finish. An agent with the full
tool surface is not a subagent, it is a second copy of the main loop.

## Skills

`skills/<name>/SKILL.md`, one folder per skill, plus optional
`references/`, `scripts/`, `assets/` beside it. The rules are skill-creator's
and do not change inside a plugin:

- `name` is a lowercase slug matching the folder;
- `description` states triggers in user vocabulary — it is the only part read
  every turn;
- the body is a procedure, and every non-obvious instruction says why;
- anything long moves to `references/`, with the body saying **when** to read it.

A plugin bundling several skills should say in its README how they relate;
otherwise they compete for the same triggers and the wrong one loads.

## Hooks

`hooks/hooks.json` — `event → matcher → handlers[]`.

```json
{
  "PreToolUse": [
    {
      "matcher": {"tool": "shell_exec"},
      "if": "${workspace.is_dirty}",
      "hooks": [
        {"type": "command", "command": "${PLUGIN_ROOT}/scripts/check-clean.sh", "timeout": 5}
      ]
    }
  ]
}
```

Handler types are `command`, `http`, `mcp_tool`, `prompt`, and `agent`. Which
events exist is not a thing to remember — read the event catalogue
(`docs/EVENT_CATALOG.md`, `docs/HOOKS_SPEC.md`) and use the exact name. A
misspelled event does not error; it simply never fires, which is the single
hardest plugin bug to notice.

Four rules, because a hook runs without anyone asking:

1. **Fast.** It sits on the path of every matching event. Put a timeout on it.
2. **Idempotent.** Events can be delivered more than once.
3. **Cannot widen authority.** A hook may block or annotate; it may not grant.
   A managed deny is never overridable by a hook.
4. **Silent on success.** A hook that prints on every turn is a hook users
   disable.

## MCP servers

Declared in the manifest, defined under `mcp/`:

```json
{
  "release-tools": {
    "type": "stdio",
    "command": "node",
    "args": ["${PLUGIN_ROOT}/mcp/server.js"],
    "env": {"RELEASE_TOKEN": "${user_config.release_token}"}
  }
}
```

Transports are `stdio`, `streamable-http`, and (legacy, being retired)
HTTP+SSE. Design of the server itself belongs to mcp-builder; from the plugin's
side the rules are: never inline a credential (take it from `user_config`,
declared secret), declare every host the server contacts in
`network.allowed_hosts`, and remember that a server's tools inherit the
plugin's granted authority — a narrow manifest with a wide server is a
mis-declaration.

## Panels, output styles and themes

Presentation components carry no runtime authority and must not be able to hide
policy or audit state. A panel that renders an approval must show what the
approval says, not a summary of it. Themes and output styles are visual only —
if a theme changes what a warning says, it is not a theme.

## User configuration

```json
"user_config": {
  "release_token": {
    "type": "string",
    "default": null,
    "secret": true,
    "scope": "user",
    "affects": ["mcp_servers.release-tools"]
  }
}
```

Every field declares its type, default, whether it is secret, its scope (user,
local, project, managed) and which component it affects. `affects` is what lets
an owner see why a value is being asked for. A secret field is redacted
everywhere: events, plugin details, permission diffs, UI summaries — do not
build a component that echoes one back for confirmation.
