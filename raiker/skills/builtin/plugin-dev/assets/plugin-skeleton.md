# Plugin skeleton

Copy this whole layout, then delete what the plugin does not ship. Every path
below is relative to the plugin directory; nothing here refers to an absolute
path on the machine that built it.

```
my-plugin/
├── raiker-plugin.json
├── README.md
├── commands/do-the-thing.md
├── skills/the-workflow/SKILL.md
└── hooks/hooks.json
```

## `raiker-plugin.json`

```json
{
  "schema_version": "1.0",
  "plugin_id": "com.example.raiker.my-plugin",
  "name": "My Plugin",
  "version": "0.1.0",
  "description": "<one line: what an owner gets>",
  "author": {"name": "<you>", "url": "<url or null>"},
  "license": "Apache-2.0",
  "raiker_version": ">=0.1.0 <1.0.0",
  "entrypoints": {
    "commands": ["commands/do-the-thing.md"],
    "skills": ["skills/the-workflow/SKILL.md"],
    "hooks": ["hooks/hooks.json"],
    "agents": [],
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
      "argument_match": {"path": "<the narrowest glob that works>"},
      "reason": "<why this plugin needs it>",
      "required": true,
      "expected_effect": "<what the owner will observe, in their words>"
    }
  ],
  "network": {"required": false, "allowed_hosts": []},
  "memory": {"read_scopes": [], "write_scopes": []},
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

## `commands/do-the-thing.md`

```markdown
---
description: <what a user would type to want this>
argument-hint: "[target]"
allowed-tools: ["read_file"]
---

<The procedure, in numbered steps. $1 is the first argument.>
```

## `skills/the-workflow/SKILL.md`

```markdown
---
name: the-workflow
description: <what it does, then when to use it, in the words a user types>
version: 0.1.0
---

# The workflow

<Procedure first. Why behind each instruction. Failure modes at the end.>
```

## `hooks/hooks.json`

```json
{
  "PreToolUse": [
    {
      "matcher": {"tool": "<tool name from the event catalogue>"},
      "hooks": [
        {"type": "command", "command": "${PLUGIN_ROOT}/scripts/check.sh", "timeout": 5}
      ]
    }
  ]
}
```

Delete the hook entirely unless something genuinely has to run without being
asked. It is the component with the highest cost to a user and the highest bar
in review.

## `README.md`

Three sections, in this order, because it is the order a reviewer needs them:

1. **What it does** — one paragraph, concrete.
2. **What it asks for** — every permission, and the reason in plain words.
3. **How to use it** — the command or trigger, with one worked example.

## Before publishing

- Every `entrypoints` path exists.
- Every declared permission is used; every used permission is declared.
- Installed into a scratch workspace, enabled, and driven the way a user would.
- Dependencies pinned exactly.
- No absolute paths, no inlined secrets, no `default_enabled: true`.
