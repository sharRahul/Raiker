# Extensions and MCP

**Extensions** has five tabs: Connectors, MCP servers, Skills, Plugins, Channels.

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
be at a **runtime** state, which means a runtime-enablement mode must be active
first (see [Permissions and runtime modes](permissions-and-runtime-modes.md)).
Until then the form is disabled.

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

**Current limit (BUG-12):** a connected server's tools are **not** offered to
the model in Chat. MCP works today as a management and monitoring surface, not
yet as an agent capability. See [To be fixed](../plans/TO_BE_FIXED.md).

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

Three install on first visit: **algorithm-creator**, **mcp-builder**, and
**skill-creator**. Delete or rename one and it stays gone — Raiker records that
it was offered once and does not restore it.

### Pasting a skill link into Chat or Build

Paste a GitHub skill URL into either composer and a notice appears offering to
**Verify skill**. Verifying fetches and validates the document and reports its
real name and description; nothing is stored until you then choose **Add to
Skills**. Dismissing leaves your prompt exactly as typed.

## Plugins and Channels

Both tabs are intentionally empty and say so:

> A plugin cannot render its own page here until Raiker has an accepted route,
> permission, and accessibility contract for it. Listing them early would
> suggest an authority the runtime does not enforce, so this tab stays empty on
> purpose.

> Inbound and outbound delivery needs an accepted contract and threat model
> before Raiker offers controls for it. This tab exists so the gap is visible
> rather than silently missing.

No plugin code runs in your browser.
