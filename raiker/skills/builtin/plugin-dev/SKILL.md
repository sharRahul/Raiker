---
name: plugin-dev
description: Design, build, validate, or debug a plugin — a bundle that adds commands, skills, agents, hooks, MCP servers, panels, or themes to an agent runtime. Use whenever someone says "write a plugin", "package this as a plugin", "add a slash command", "add a hook", "raiker-plugin.json", "plugin.json", "my plugin isn't loading", "the marketplace rejected it", or asks how to distribute a workflow so other people can install it. Use it too when deciding whether something should be a plugin at all rather than a skill, a command, or an MCP server — that choice is made before any file is written and is the one most often got wrong. Do not use it for writing a lone SKILL.md (skill-creator) or a standalone MCP server (mcp-builder); a plugin that bundles either of those is this skill's business.
metadata:
  version: 1.0.0
---

# Plugin developer

A plugin is a *distribution unit*: one directory, one manifest, several kinds of
component, installed and enabled as a single decision. Everything hard about
plugins follows from that. The manifest is a request for authority, the install
is where the owner grants it, and every component inside inherits what was
granted — so a plugin is judged first on whether its authority request is
honest and minimal.

## 1. Decide whether it should be a plugin

| You want to… | Build |
|---|---|
| Change how the agent approaches a kind of task | A **skill** — one `SKILL.md`, no manifest, no permissions |
| Give a repeatable prompt a short name | A **command** |
| Expose an external API or local capability as callable tools | An **MCP server** |
| Ship *several* of the above together, versioned, installable, updatable | A **plugin** |
| Run something on an event (a turn starting, a tool about to run) | A **hook** — inside a plugin if it travels with other parts |

Build the smallest of these that does the job. A plugin wrapping one skill costs
its user a manifest review, a permission decision and an update path, and buys
nothing the skill did not already have.

## 2. Lay out the directory

Auto-discovery does the wiring: put components in the conventional directories
and the manifest names them.

```
my-plugin/
├── raiker-plugin.json     the manifest — the only required file
├── commands/              *.md, one per slash command
├── skills/<name>/SKILL.md one folder per skill
├── agents/                *.md, one per subagent profile
├── hooks/hooks.json       event → matcher → handlers
├── mcp/                   MCP server definitions
├── panels/                TUI / web / mobile panels
├── assets/                templates, themes, static files
└── README.md              what it does, what it asks for, why
```

Reference files inside the plugin by a root-relative path the runtime expands
(`${CLAUDE_PLUGIN_ROOT}` in Claude Code; the manifest's own relative
`entrypoints` paths in Raiker). Never write an absolute path from your machine
into a manifest — it is the single most common reason a plugin installs and then
does nothing on someone else's computer.

## 3. Write the manifest as an honest authority request

The manifest is read by a person deciding whether to trust you. Raiker's schema
is in `docs/PLUGIN_MANIFEST_SCHEMA.md`; the fields that decide acceptance are:

```json
{
  "schema_version": "1.0",
  "plugin_id": "com.example.raiker.release-notes",
  "name": "Release Notes",
  "version": "0.1.0",
  "description": "Drafts release notes from merged pull requests.",
  "author": {"name": "Example", "url": "https://example.com"},
  "license": "Apache-2.0",
  "raiker_version": ">=0.1.0 <1.0.0",
  "entrypoints": {"commands": ["commands/release-notes.md"], "skills": []},
  "permissions": [
    {
      "tool": "read_file",
      "argument_match": {"path": "CHANGELOG.md"},
      "reason": "Read the existing changelog to continue its format",
      "required": true,
      "expected_effect": "The command reads CHANGELOG.md and nothing else."
    }
  ],
  "network": {"required": false, "allowed_hosts": []},
  "memory": {"read_scopes": [], "write_scopes": []},
  "user_config": {},
  "dependencies": [],
  "supply_chain": {"source_url": null, "commit_sha": null, "checksum": null, "signature": null},
  "default_enabled": false
}
```

Four rules carry most of the review:

1. **Ask for the narrowest permission that works.** `{"path": "CHANGELOG.md"}`
   is reviewable; `{"path": "**/*"}` is a request for the whole workspace and
   will be read as one.
2. **`expected_effect` is written for the owner, not for you.** State what they
   will observe, in their words. It is the sentence the permission dialog shows.
3. **`network.required` false, or an explicit `allowed_hosts` list.** "Any host"
   is not a network declaration.
4. **`default_enabled` is false.** A plugin that enables itself has decided
   something that was not its decision.

Pin dependencies exactly (`{"plugin_id": "…", "version": "1.2.3"}`). Ranges are
rejected: a range means the authority a user approved can change without them.

Read `references/components.md` for the frontmatter of each component type —
commands, agents, skills, hooks, MCP servers — and the field-by-field rules.

## 4. Build the components

- **Commands** are prompts with a name. Frontmatter carries `description`,
  argument hints, and the tools the command may use. Keep the body a procedure,
  not an essay.
- **Agents** are subagent profiles: frontmatter plus a system prompt. The
  `description` is the whole triggering mechanism — write it in the vocabulary a
  user actually types, and include a concrete example of when to delegate.
- **Skills** follow skill-creator's rules exactly; a plugin does not change
  them. One folder per skill, `SKILL.md` at its top.
- **Hooks** map `event → matcher → handlers[]`. A hook is the only component
  that runs *without* the user asking, so it is held to the strictest standard:
  fast, idempotent, and unable to widen a permission. A hook that cannot state
  what it does in one line is doing too much.
- **MCP servers** get their design from mcp-builder; the plugin only declares
  and configures them.

## 5. Validate before publishing

In this order, because each catches what the next assumes:

1. **Manifest parses and is complete** — every required field, `plugin_id`
   reverse-DNS, `version` semver, `raiker_version` a real range.
2. **Every path in `entrypoints` exists**, and nothing outside the plugin
   directory is referenced.
3. **Every component's frontmatter parses**, and every `name` is a valid slug.
4. **The permission list matches what the components actually do.** Walk each
   component and ask which declared permission it needs. A permission nothing
   uses is a finding against you; a component needing one that is not declared
   will fail closed at runtime and look like a bug.
5. **Install it into a scratch workspace and enable it.** Then use it the way a
   user would. Most plugin defects are discovered in the first thirty seconds of
   real use and in no test.
6. **Read your own README as a stranger.** What it does, what it asks for, why
   it needs that. If the *why* is not there, the permission will be refused.

## 6. When it does not load

| Symptom | Usual cause |
|---|---|
| Nothing appears after enabling | An `entrypoints` path does not exist, or points outside the plugin |
| A command exists but is never suggested | `description` is abstract — rewrite it around what a user types |
| A component works for you and not for others | An absolute path, or a tool you have granted globally and the manifest never requested |
| Install refused | Unpinned dependency, missing required field, or a permission with no `reason`/`expected_effect` |
| A hook does nothing | Matcher never matches; check the event name against the event catalogue, not against memory |
| Update refused | The new version widens permissions — that produces a permission diff which the owner must approve |

## In Raiker

Raiker treats a plugin as a **request**, and separates validating it from
running it. A manifest is validated, its permission diff shown, and its
components registered; execution stays behind the runtime gate for that
component class. That is why a plugin can be reviewed safely before anyone runs
anything it ships.

- **Install and enable** under **Extensions → Plugins**. The permission diff is
  the decision point, and it is shown again on every update that widens.
- **Nothing self-enables.** `default_enabled` true is accepted only for bundled,
  signed, or managed-policy plugins.
- **Secrets in `user_config`** must be declared secret; they are redacted in
  events, diffs and every UI summary.
- **Supply chain**: `checksum` is the SHA-256 of the canonical manifest body;
  with a signing key configured, `signature` must verify or the install fails
  closed.

Raiker's own references: `docs/PLUGIN_SYSTEM_SPEC.md`,
`docs/PLUGIN_MANIFEST_SCHEMA.md`, `docs/HOOKS_SPEC.md`,
`docs/EXTENSIBILITY_MODEL.md`.

### Across agent surfaces

| Control | Elsewhere | In Raiker |
|---|---|---|
| Manifest | Claude Code `plugin.json`; Codex extension manifest | `raiker-plugin.json`, with a required permission block |
| Component discovery | Convention directories | Same layout, declared in `entrypoints` |
| Permission model | Tool allowlists at the session level | Per-permission `reason` + `expected_effect`, diffed on update |
| Hooks | Claude Code hook events; OpenClaw gateway events | `docs/HOOKS_SPEC.md` event catalogue |
| Distribution | Marketplace / git URL | Marketplace entry or git source, with checksum and optional signature |
| Enablement | Enabled on install | Install and enable are separate decisions; nothing runs until the gate for its class is open |
| Updates | Version bump | Version bump **plus** a permission diff whenever authority widens |

`assets/plugin-skeleton.md` is a fill-in-the-blanks manifest plus one command,
one skill and one hook, wired the way this document describes. Copy it rather
than retyping the shape.
