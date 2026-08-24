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
metadata:
  version: 1.0.0
---

# Release notes

1. Read the diff since the last tag.
2. Group changes by what a user would notice.
```

`name` must be a lowercase slug. The `description` is what decides *when* the
skill applies, so it carries the triggers rather than a summary. A version goes
under `metadata:`, which is where the standard puts it — Raiker also reads a
top-level `version:` for skills written before the standard existed, and says on
the card that a strict reader elsewhere would drop it.

A `*.skill` file is a zip holding `<name>/SKILL.md` plus any supporting files —
`references/` for detail loaded only when needed, `assets/` for templates, and
`scripts/`, which is where the format expects executable code. **Raiker stores a
`scripts/` file and never runs it.** A script in a Raiker skill is readable text
the agent may open through `skill_load` like any other bundled file, and running
what it says still means proposing a `shell` command that passes its own gate,
its own decision mode and your approval. Bundles are capped at 2 MB.

### Skills written elsewhere, and skills written here

The `SKILL.md` format is an open standard —
[Agent Skills](https://agentskills.io), with a published
[specification](https://agentskills.io/specification) — implemented by Claude,
Claude Code, ChatGPT and Codex, Hermes Agent, OpenClaw and around forty other
products. Raiker reads the same file, requires the same two fields, and loads
skills the same way (index first, body on demand), so a skill from elsewhere
generally installs here.

**Every installed skill is measured against the standard, and the answer is on
its card.** Open **Details** on any skill and the *Agent Skills standard* block
says whether it would install in the other forty products, names any field that
would stop it, and shows its `license` and `compatibility` if it declares them.

**The measurement never refuses a skill.** Raiker's reader is deliberately
*looser* than the standard — it accepts `.` and `_` in a name where the standard
allows only `a-z`, `0-9` and single hyphens, and keeps a description up to 2000
characters where the standard caps it at 1024 — and a skill you already rely on
keeps working. What changes is that you are told, rather than finding out when
you try to use it somewhere else. The card distinguishes:

| What you see | What it means |
|---|---|
| **standard** | It should install in any tool that reads the format |
| **portable, with notes** | It installs everywhere; a strict reader may drop a field, such as a top-level `version:` that belongs under `metadata:` |
| **N portability issues** | It works in Raiker and another tool may refuse it. The finding names the field and the rule |

Two differences are deliberate rather than gaps:

- **Raiker runs nothing.** The standard permits an agent to execute a skill's
  bundled scripts, and several products do. Raiker does not, and this is a
  decision rather than an omission: a skill is instruction text, and instruction
  text that can also execute is a capability arriving without a gate.
- **`allowed-tools` is read and refused.** A skill pre-approving its own tools
  is exactly the grant this tab's "grants no capability" promise exists to
  prevent. Raiker parses the field, lists the tools it names on the card under
  *Not pre-approved*, and says plainly that it is not honoured — which is
  stronger than ignoring a field its author believes is doing something. Every
  tool call a turn makes while following that skill is governed exactly as it
  would be otherwise.

If you want a skill that travels, the card's findings are the checklist;
[`skills-ref validate`](https://github.com/agentskills/agentskills/tree/main/skills-ref)
is the standard's own validator and will say the same thing.

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

Two limits worth knowing before you write a rule. Only `PreToolUse` and
`PreCompact` decisions change an outcome — every other event is observation, and
the tab says which of the two a rule is. And a hook may only ever make an action
**stricter**: it can deny a call or turn it into a decision, and nothing it
returns can allow one the runtime refused.

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
| Hooks | yes — rules at `plugin` scope, below every scope you control |
| Skills | yes — instruction text, installed **switched off** and credited to the plugin |
| MCP servers | yes — a plugin may *offer* one; adding it is your action |
| Panels | not yet — needs a route, permission and accessibility contract |

so "provides nothing" and "may not provide anything" read differently.

No plugin code runs in your browser.

### A plugin's skills

A plugin that asks for `skill:contribute` may ship `SKILL.md` documents. They go
through the same validator an upload does, land in
`.raiker/plugins/<id>/skills/<name>/SKILL.md`, and appear on Extensions → Skills
marked **from plugin** with the plugin's id.

They arrive **inactive**. Installing the plugin was consent to *offer* the skill,
not to run with it — you switch each one on yourself, and that is a second,
separate decision.

Rename and Delete are not offered on a plugin's skill, because the next sync
would undo either. **Download** is, so you can read exactly what it says. To
remove one, revoke the plugin: that deletes the file, and the row goes with it.

A plugin's skill never overwrites one of yours. If the names collide, yours stays.

### A plugin's MCP servers

A plugin that asks for `mcp:server` may **offer** a server — a name, a transport,
an HTTPS endpoint or a reviewed template, and the name of the environment
variable holding the token. It is a description, not a connection: nothing is
added, connected, or reachable until you press **Add server** on Extensions →
MCP servers, and that runs the same governed create path as typing it in.

An offer can never carry a credential. A plaintext `http://` endpoint, a URL with
a username or password in it, or an `auth_ref` that is not an environment
variable name is refused at install, and re-validated when the offer is read — so
hand-editing the file afterwards cannot smuggle one in.

## Channels

A channel is the one place where content Raiker did not ask for enters a turn.
That content is defined: **untrusted content with a named sender who is not you.**
Never a prompt. Never able to enable a capability, widen an approval mode, or
approve anything. Trust comes from the pairing record, never from anything inside
the message.

The tab lists every connector profile and lets you **pair** one. Pairing does not
switch it on and does not trust anyone — linked, enabled and trusted are three
separate facts, and the tab shows them separately:

- **Pair** stores the link, switched off, with whatever sender allowlist you gave
  it. A profile that accepts inbound messages cannot be paired without one.
- **Turn on** is a second decision.
- **Send a test delivery** runs the *same governed path* a real delivery takes —
  the capability gate, the decision mode, the egress allowlist and the audit
  event all apply. It is not a shortcut that proves nothing.
- **Unpair** deletes the link. Both the outbound executor and the inbound
  receiver read that record, so unpairing is what actually stops the channel.

Four things are fail-closed or off by default, and each has its own remedy, so
the tab reports them one by one rather than as a single "ready":

| Gate | What it is | Where you change it |
|---|---|---|
| Capability | `external_channel_runtime` | Permissions |
| Egress | `RAIKER_CHANNEL_EGRESS_ALLOWLIST` — empty means deny | Your environment |
| Signing | `RAIKER_CHANNEL_OUTBOUND_SECRET` — unset means unsigned, not refused | Your environment |
| Inbound secret | `RAIKER_CHANNEL_INBOUND_SECRET` — unset means refuse | Your environment |

A fifth row states the **inbound budget**: 60 messages per sender per minute by
default, `RAIKER_CHANNEL_INBOUND_RATE` to change it. Allowlisting says *who* may
speak; the budget says how often, and they are different questions — a sender
that goes over is refused and the refusal is recorded, so a channel that goes
quiet is answerable from Observability rather than a mystery.

**An inbound message never becomes a turn on its own.** It is recorded as a
governed event, quarantined, and its instructions are inert whatever the sender
wrote. Accepted and rejected messages both appear in Observability → Activity.

Still unbuilt: the routing modes in the spec, and resolving an approval over a
channel — the relay queue is deliberately pending-only, because a channel that
can raise an approval can be used to *ask for* one.
Full contract: [`docs/CHANNELS_SPEC.md`](../CHANNELS_SPEC.md).
