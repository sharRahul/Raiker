# Extensibility Model

Status: specification + partial implementation. This doc unifies Raiker's five extension
surfaces — **tools, hooks, skills, plugins, channels** — into one mental model, with consistent
trust, registration, and policy rules. It exists because these surfaces are currently described
in separate specs with no single overview, which makes the extensibility story hard to reason
about as a whole.

Reference inspiration: Claude Code's extension layer (skills, MCP, hooks, subagents, plugins,
channels) sits *on top of* a fixed agentic core; Raiker adopts the same separation. Source of
truth remains this repository.

---

## 1. The one rule

Every extension, regardless of surface, obeys the same invariant:

> An extension may **add capability or make execution stricter**, but it can never bypass the
> tool broker, the policy engine, the approval flow, or the event log.

Extensions are **untrusted by default** and become trusted only through explicit scope,
manifest, pairing, or managed policy.

---

## 2. The five surfaces

| Surface | What it extends | Registration | Execution path | Code state | Spec |
|---|---|---|---|---|---|
| **Tools** | New actions the agent can take | Tool broker registry | Broker → policy → (approval) → execute | ✅ built-in tools real; plugin tools planned | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| **Hooks** | Logic at lifecycle points (pre/post tool, session, prompt) | Hook config (scoped) | Hook dispatcher with bounded decision authority | ✅ implemented (`builtin`+`command`); `http`/`mcp_tool`/`prompt`/`agent` deferred | `docs/HOOKS_SPEC.md`, `raiker/hooks/` |
| **Skills** | Reusable instruction documents (`SKILL.md`, `*.skill`) | Frontmatter validated on install; owner-scoped store | Indexed into the turn; body read through the governed `skill_load` tool | ✅ implemented (`raiker/skills/`, Extensions → Skills) | `docs/guide/extensions-and-mcp.md`, `docs/SELF_IMPROVEMENT_MODEL.md` |
| **Plugins** | Bundles of tools + hooks + skills + channels + servers | Plugin manifest + permission diff | Components register through their own surfaces; nothing auto-executes | 🔒 manifest validation only | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/PLUGIN_MANIFEST_SCHEMA.md` |
| **Channels** | New interfaces/transports (chat, webhook, voice) | Connector profile + pairing | Inbound normalises to `ChannelMessageEnvelope` → gateway → same runtime | 🔒 registry only, no transport | `docs/CHANNELS_SPEC.md` |

Legend: ✅ implemented · 🔒 phase_scheduled_disabled · 📘 specified_not_implemented.

---

## 3. Trust & scope ordering

When two extensions disagree, the stricter wins, and scope precedence applies (highest first):

```
managed (enterprise policy)
  > user
  > project (committed)
  > local (gitignored)
  > plugin
  > skill
  > session
```

- A lower-scope extension can never override a higher-scope **deny**.
- Plugin/skill/channel extensions are advisory unless explicitly granted decision authority.
- Channels additionally require **sender gating** (pairing + sender allowlist) before any
  inbound content reaches the runtime — an ungated channel is a prompt-injection vector
  (see `docs/OWASP_GENAI_SECURITY_MAPPING.md`).

---

## 4. Lifecycle (uniform across surfaces)

```
declare (manifest/config/profile)
  -> validate (schema + permission diff; no code import yet)
  -> review (user/managed approval; preview shown)
  -> enable (scoped, logged)
  -> use (always through broker/policy/event path)
  -> update (re-diff permissions; re-approve)
  -> disable / uninstall (logged; artifacts revoked)
```

Validation and review must never import or execute extension code. This is exactly what the
plugin layer does today (`raiker/plugins/policy.py` validates manifests and emits a registration
plan with execution disabled).

---

## 5. Supply-chain controls

- Manifests are explicit and declare every permission they want.
- A **permission diff** is shown before enable/update.
- Plugin execution slices are **governed/default-ask** and require owner trust/allowlists; broader plugin extensions remain deferred/fail-closed.
- Recommended (not yet implemented): manifest signing/checksums and provenance, plus a managed
  allowlist of trusted publishers (LLM03, `docs/OWASP_GENAI_SECURITY_MAPPING.md`).

---

## 6. How to choose a surface

| You want to… | Use |
|---|---|
| Give the agent a new deterministic action | **Tool** (via plugin or built-in) |
| React to a lifecycle event (lint on edit, block a command) | **Hook** |
| Package a repeatable multi-step procedure | **Skill** |
| Distribute a set of the above together | **Plugin** |
| Add a new way to talk to Raiker (chat/webhook/voice) | **Channel** |

---

## 7. Current code status

- **Tools:** implemented for the built-in safe set; plugin-provided tools are planned to register
  through the same broker.
- **Plugins / Channels:** registry + manifest/profile validation only; **no execution/transport**
  (`raiker/plugins/`, `raiker/channels/`).
- **Hooks:** **implemented** (`raiker/hooks/`) — `builtin` + `command` handlers, scoped config,
  decision authority, and lifecycle dispatch wired through the broker and gateway. `http`,
  `mcp_tool`, `prompt`, and `agent` handlers are deferred until their gated surfaces exist.
- **Skills:** **implemented** (`raiker/skills/`, `raiker/api/routes_skills.py`, Extensions →
  Skills). A skill is instruction text, never code Raiker executes, which is why it is the one
  surface with no capability gate of its own: it cannot add authority, so there is nothing to
  gate. What it *can* do is influence a turn, so the boundaries that exist are about integrity
  and scope rather than execution:
  - **Validation before storage.** `raiker/skills/package.py` is the trust boundary for an
    uploaded file. It parses frontmatter without a real deserializer, and rejects absolute
    members, parent-directory escapes, symlinks, oversized entries, and zip bombs before a byte
    is written. Nothing in that module imports, runs, or evaluates what it reads.
  - **Owner scope.** Every read and mutation is keyed to the installing principal, and
    mutations are human-only. One owner's skill is invisible to another.
  - **Egress.** Import reaches only the published-skill hosts, through the existing sandbox
    egress boundary, against this module's own allowlist rather than a model-supplied one.
  - **Withholding is real.** A deactivated skill is absent from the turn index *and* refused by
    `skill_load`, so turning one off withholds it rather than hiding it.
  - **Progressive disclosure.** Only the index (one line per active skill) enters a turn. The
    body, and any one bundled file, are read on demand through the broker like any other
    governed read — so they appear in the tool-action record and the event log.

The remaining pieces to complete this model are plugin execution and channel transport; both
must register through — and be gated by — the existing broker/policy/event infrastructure.

## Where each surface is seen

An extension surface that cannot be inspected is one the owner has to take on
trust, which is the opposite of what this model is for.

| Surface | Owner surface | State |
|---|---|---|
| Connectors | Extensions → Connectors | Install, connect, enable, and the four facts behind "usable" |
| MCP servers | Extensions → MCP servers | Create, connect, monitor |
| Skills | Extensions → Skills | Install and review; grants nothing and runs no code |
| Hooks | Extensions → **Hooks** | Read-only: what loaded, what can fire, what can decide, what it did |
| Plugins | Extensions → Plugins | Install records and signature level; **no plugin code executes** |
| Channels | Extensions → Channels | Named as unavailable rather than silently missing |

Hooks are read-only on purpose. The three configuration files are the owner's own
text on disk, and a page that rewrote them would need an authority story of its
own — so the surface reports what the runtime loaded, including a file it could
not read, and leaves the editing where the owner already has it.
