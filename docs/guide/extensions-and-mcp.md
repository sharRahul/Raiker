# Extensions and MCP

**Extensions** has six tabs: Connectors, MCP servers, Skills, Hooks, Plugins, Channels.

## Connectors

A connector is a governed link to an outside service. Raiker keeps four facts
about each one **separate** and confirms all of them server-side before it will
call anything:

| Fact | Meaning |
|---|---|
| Installed | Present in the workspace |
| Connected | An account credential is stored (its value is never shown) |
| Enabled | Switched on for this session |
| Usable | Every condition confirmed by the server |

A connector appearing in the catalogue means nothing on its own. The readiness
counters at the top read `0 usable` on a fresh workspace, which is correct.

Reference connectors with real, governed read paths: **GitHub**, **Gmail**,
**Google Calendar**, **Slack**. Each needs, at minimum:

1. its capability gate on (`connector_github_runtime`, etc.);
2. a decision mode above the default `ask`;
3. an owner credential in the server environment (`RAIKER_GITHUB_TOKEN`, …);
4. its host on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`.

Miss any one and the read fails closed with a named reason —
`connector_gate_disabled`, `connector_withheld_ask`, `connector_not_configured`,
`connector_egress_denied`. Fetched content is always framed as **untrusted
data**, never as instructions.

**Import manifest** adds a manifest-driven connector.

## MCP servers

Raiker can build, connect to, and monitor Model Context Protocol servers.

**Prerequisites:** both `mcp_builder_runtime` and `mcp_connector_runtime` must
be at a **runtime** state — turn each on in **Permissions**. Until then the form
is disabled and the page says which of the two is missing.

To create one:

1. Enter a server name.
2. Pick a template — *Sample echo server (safe starter)* ships with Raiker.
3. **Create server**. The generated file lands at
   `.raiker/mcp/servers/<name>.py`; writing it goes through the normal file-write
   approval path.
4. **Test** connects and discovers tools. The echo template exposes `echo` and
   `workspace_ping`.

Each server card shows its command, template, last connection, discovered tools,
and recent monitored sessions. Controls: **Test**, **Stop** / **Resume**,
**Rename**, **Delete**. Stop is an instant containment switch — it refuses all
sessions for that connection and is revocable.

### Can Raiker actually call it?

A connected server's tools are callable in Chat and Build as
`mcp__<server>__<tool>`, under the same policy review, containment, and audit
path as everything else. **Two owner controls stand between "connected" and
"callable", and the page states both** rather than leaving you to infer the
second from the first:

- the `mcp_connector_runtime` **capability gate**; and
- that capability's **decision mode**. The default `ask` withholds a tool call
  for a decision a running turn cannot wait for, so tools are projected only at
  **Allow** (or at **Auto** with a low-risk floor).

When Raiker cannot call them, a banner names the exact reason and links to the
control that changes it. When it can, the same place says how many tools are
available and in what form. Each connected card carries the matching **Callable
by Raiker** / **Not callable yet** chip, so a card can no longer disagree with
the runtime.

A call's arguments stay out of the audit trail — the record keeps
`arguments_length` and `content_redacted: true`, not the payload. Reaching a
registered server runs code Raiker does not own, which is why the call carries
the same risk band as a connector read.

## Skills

A skill is a `SKILL.md` document — instructions Raiker follows when the task
matches. Installing one adds guidance and nothing else: **it grants no
capability, opens no gate, and Raiker never runs code a skill ships.** That is
why this tab needs no capability gate, unlike Connectors and MCP.

### What a skill looks like

Markdown with a `---` frontmatter block carrying at least `name` and
`description`:

```markdown
---
name: release-notes
description: Draft release notes. Use when cutting a release or summarising a diff.
version: 1.0.0
---

# Release notes

1. Read the diff since the last tag.
2. Group changes by what a user would notice.
```

`name` must be a lowercase slug. The `description` is what decides *when* the
skill applies, so it carries the triggers rather than a summary.

A `*.skill` file is a zip holding `<name>/SKILL.md` plus any supporting files —
`references/` for detail loaded only when needed, `scripts/` for code to run,
`assets/` for templates. Bundles are capped at 2 MB.

### Adding one

| Route | What happens |
|---|---|
| **Upload** | A `SKILL.md` or `*.skill` file, validated server-side before storage |
| **Import from a link** | A GitHub URL to a raw `SKILL.md`; fetched, verified, then stored |
| **Build a skill** | Write name, description, and body in place; held to the same contract |

Import reaches only `raw.githubusercontent.com`, `github.com` (blob URLs are
rewritten to raw), and `gist.githubusercontent.com`. Any other host is refused
by name — `skill_unsupported_source` — without a request being made. A `.skill`
archive **cannot** be imported from a link (the fetch path is text-only);
download it and upload the file.

Uploads fail closed with a named reason: `skill_missing_description`,
`skill_invalid_name`, `skill_missing_skill_md`, `skill_unsafe_member_path` (an
archive member that would escape its own folder), `skill_too_large`.
Re-installing a skill under a name you already have refreshes the stored
document in place and **keeps your active/inactive choice** — an update never
silently re-enables something you turned off.

### Managing them

Each row offers **Activate** / **Deactivate**, **Rename**, **Download**, and
**Delete**, plus a details panel with the checksum, the source, and the file
list. An uploaded archive downloads byte-for-byte; a skill that arrived as a
bare document is packed into `<name>.skill` on demand.

Deactivating keeps the skill stored and withholds it from every turn — the fast
way to test whether a skill is helping.

### How a skill reaches a turn

Only the **index** — one line of `name: description` per active skill — goes
into a turn's system context. When one applies, the model calls the `skill_load`
tool to read its body, and can pass a `file` from the skill's own file list to
read one bundled reference. Ten installed skills therefore cost ten lines, not
ten documents.

### Shipped skills

Six install on first visit:

| Skill | What it is for |
|---|---|
| **algorithm-creator** | Designing and verifying an algorithm before writing it |
| **code-review** | Reviewing a diff or a pull request, and reporting only findings worth acting on |
| **mcp-builder** | Building, debugging, or migrating an MCP server, against the current protocol revision |
| **plugin-dev** | Designing, building and validating a plugin, manifest included |
| **security-review** | Auditing a change for exploitable defects, agent-surface classes included |
| **skill-creator** | Writing a new skill, or diagnosing one that never triggers |

Delete or rename one and it stays gone — Raiker records that it was offered once
and does not restore it.

### Pasting a skill link into Chat or Build

Paste a GitHub skill URL into either composer and a notice appears offering to
**Verify skill**. Verifying fetches and validates the document and reports its
real name and description; nothing is stored until you then choose **Add to
Skills**. Dismissing leaves your prompt exactly as typed.

## Hooks

A hook runs your own logic at a point in a turn. It can only make an action
**stricter**: a hook may deny a tool call or turn it into a decision you answer,
and it can never allow one the runtime refused, skip an approval, or reach past
the tool broker.

Hooks are configured in a file, not on this page. Raiker reads four, in this
order of authority:

| File | Scope | For |
|---|---|---|
| `config/managed-hooks.json` | managed | Rules nothing below may override |
| `config/hooks.json` | project | Rules that travel with the repository |
| `.raiker/hooks.json` | local | Rules for this machine only |
| `.raiker/plugins/<id>/hooks.json` | plugin | Rules an installed plugin contributed |

A lower scope can never override a higher-scope deny — so a plugin can make an
action stricter and can never loosen one you set.

```json
{
  "schema_version": "1.0",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "shell|process",
        "handlers": [
          { "id": "guard", "type": "builtin", "builtin": "block_destructive_shell" }
        ]
      }
    ]
  }
}
```

`matcher` takes `*`, an exact tool name, `a|b` alternatives, or `re:<regex>`. An
optional `"if"` narrows further on the arguments — `"shell(rm -rf *)"` fires only
for a command matching that glob. A malformed guard fails closed rather than
widening the rule.

### Turning them off

**Turn every hook off** on the Hooks tab stops all of them at once. It is your
setting, not a fourth configuration file — `config/hooks.json` travels with a
repository, so a project you clone can bring rules that run commands on your
machine, and refusing them should not mean editing someone else's checked-in
file. A file a project ships cannot re-enable itself.

The rules stay listed while the switch is on, and the page says they are loaded
and will not run, so you can see what you turned off. The setting takes effect on
your next turn; nothing needs restarting.

### What the Hooks tab tells you

Extensions → **Hooks** reports what the runtime actually loaded, which is not
always what you wrote. Three states are worth knowing, and each is one the file
alone cannot show you:

- **A file that did not parse.** It contributes no rules — Raiker will not guess
  at a config it cannot read — and the tab names the file and where the parse
  stopped. Everything else keeps working; fix the file and reload.
- **A rule that never fires.** Every event this build's schema accepts is now
  emitted, so there is nothing on the list marked dead today. The state is still
  reported, because the schema and the emitted set are allowed to diverge again:
  a rule on an event a later build accepts before wiring parses cleanly and never
  runs, and would be shown as such rather than left looking enforcing.
- **A rule that cannot change anything.** Only `PreToolUse` and `PreCompact`
  decisions are honoured, and only from a handler holding decision authority — a
  builtin always has it, a `command` handler only when you set
  `"decision_authority": true`. Everything else observes. The tab labels each
  rule **Can deny or ask** or **Observes only**, and warns when a rule names a
  builtin this build does not have.

The tab also lists every event a rule may name and every builtin handler that
exists, because you are writing the file by hand and guessing a name produces a
rule that fails every time it matches. There are sixteen events: the session
starting and ending, a prompt being submitted, the turn's two possible endings
(`Stop` when it produced an answer, `StopFailure` when it failed, was stopped, or
is parked on an approval), compaction either side, every tool call and its
approval outcomes, a delegation starting and stopping, and a task being created
and reaching a terminal state.

Every match, run, decision, timeout and failure is in **Observability → Audit
log** as `hook_matched`, `hook_executed`, `hook_decision`, `hook_timeout` and
`hook_failed`. The tab shows the recent ones inline.

A `command` handler is argv only — never a shell string — its program must
resolve **inside the workspace**, it runs with a minimal environment and a
bounded timeout, and its output is truncated. A timeout or an error is recorded
and the action falls through to normal policy rather than being blocked by a
hook that did not answer.

## Plugins

A plugin runs **no code of its own**. It contributes through a surface that
already governs the thing contributed, and the first of those is hooks.

To contribute hook rules, a manifest declares the permission and the rules:

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

`event:hook` is required. Without it the rules are refused and the plan says so
by name — and because that permission is never auto-approved, you read it in the
permission diff *before* installing rather than discovering it afterwards.
Installing writes the rules to `.raiker/plugins/acme-guard/hooks.json`, where you
can read them; they load at `plugin` scope, below every scope you control.

Install and inspect from the CLI:

```
/plugin-plan path/to/raiker-plugin.json
/plugin-plan path/to/raiker-plugin.json --install
```

The plan states the permissions, the reasons, and what would be contributed. A
malformed `contributes.hooks` block is refused there, with the parse error named,
rather than written and silently loading nothing.

**Revoking a plugin deletes its rules.** Not flags them — deletes them, so there
is no state where the page says revoked and the runtime still runs the rule.
Re-installing replaces rather than adds, so an upgrade that dropped a rule drops
it here too.

Extensions → **Plugins** states what each installed plugin provides, read from the
files the runtime loads rather than from the manifest that described them. It also
lists what a plugin *may* contribute:

| Contribution | Available |
|---|---|
| Hooks | yes |
| Skills | not yet — they run nothing, and need a provenance story first |
| MCP servers | not yet — already brokered and gated, but not contributable |
| Panels | not yet — needs a route, permission and accessibility contract |

so "provides nothing" and "may not provide anything" read differently.

No plugin code runs in your browser.

## Channels

The tab is intentionally empty and says so:

> Inbound and outbound delivery needs an accepted contract and threat model
> before Raiker offers controls for it. This tab exists so the gap is visible
> rather than silently missing.

Inbound delivery is the highest-risk surface in this class — it is where external
input enters — so the gate here is the threat model, not the code.
