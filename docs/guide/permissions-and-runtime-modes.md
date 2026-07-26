# Permissions and runtime modes

Raiker has two independent controls, and a capability needs **both**:

1. **Runtime mode** — the ceiling. How far any capability may be enabled at all.
2. **Capability gate** — the individual switch, per capability, per account.

On top of those sits a third, softer control: the **decision mode**, which says
how the agent must ask before doing something it is already allowed to do.

---

## Configuring something is permission for it

Raiker's stated posture (`docs/HANDOFF.md` → "Security posture") is
**owner-authoritative and monitored, not prevention-by-restriction**. A gate in
front of a choice the owner has already, deliberately made is not security — it
is friction that teaches people to click through warnings.

So **saving a provider's credential is the authorization to use that provider**,
and the endpoint you configured is authorised with it. You are not asked to
separately flip a switch, separately allowlist the host, and separately create
an encryption key before the thing you just set up will work.

What that does *not* change:

- Every turn still runs through the same policy, approval, audit, and
  monitoring paths. Consent by configuration changes who has to click, not what
  gets recorded.
- **Explicit revocation wins.** A capability you deliberately turn off stays
  off, whatever is configured.
- Consent is **scoped**. Configuring Anthropic authorises `api.anthropic.com`,
  not every host on the internet.
- Deferred dangerous domains remain unavailable, and critical actions still stop
  for approval.

---

## Runtime modes

**Settings → General → Runtime mode.** Modes, least to most permissive:

| Mode | Effect |
|---|---|
| Development preview *(default)* | Everything stays off. Gates can reach a policy-gated state but never a true runtime state. |
| Local single user safe | Conservative local operation. |
| Local single user runtime | The normal single-user working mode. |
| Multi user local runtime | Several local principals. |
| Hosted or networked runtime | Off-machine operation. |

Activating a mode is governed: it asks for a reason and records the change
against your principal.

**Why this matters in practice.** With *Development preview* active, turning a
gate on gets you `enabled_policy_gated`, not `enabled_runtime`. Surfaces that
check for a true runtime capability — MCP is the clearest example — stay
disabled and say "enable it in Capabilities", even though you just did. The
missing piece is the runtime mode, not the gate.

---

## Capability gates

**Permissions** lists all 62 gates, grouped:

| Group | Examples |
|---|---|
| Workspace | Audit export, File writes, Memory store/forget, Patch apply, Semantic memory, Vector embeddings, Graph indexing |
| Local execution | Shell commands, Processes, Container execution, Subagents, Multi-agent teams |
| Network | Network requests, Web fetch, External channels, Channel approval relay |
| Models | Hosted models, Home-lab models, Advisor model, Provider embeddings |
| Connectors | GitHub, Gmail, Google Calendar, Slack, Calendar (local), Email drafts, Reminders, plugin lifecycle |
| MCP | MCP builder, MCP connector |
| Automation | Scheduled routines, Approval execution relay, Admin/policy/role mutation |

Expand a row for its description and current decision mode, then **Turn on**.

### The step-up dialog

Higher-risk capabilities (shell, processes, network, web fetch, hosted models,
MCP) require all three of:

- a **reason**;
- a **confirmation token** — any phrase you type, recording human intent. It is
  not a credential you have to obtain from anywhere;
- a **threat-model acknowledgement** tick.

**Confirm change** stays disabled until they are satisfied.

### Capabilities with no enable path

Some capabilities show no **Turn on** at all: CCTV, finance, medical,
pregnancy/baby, home security, hardware operation, remote and cloud execution,
checkpoint-restore execution. These are **deferred**, not merely gated — no
governed executor exists, so the runtime refuses to pretend one does.
Observability → Diagnostics lists them (42 on a stock install) under *"Disabled
/ deferred capabilities"*.

---

## Decision modes

Independently of whether a capability is on, each has a decision mode:

| Mode | Behaviour |
|---|---|
| **Ask** *(default)* | Every AI-proposed action pauses for your approval. |
| **Allow** | Permitted without prompting. |
| **Auto** | Runs automatically. |
| **Deny** | Always refused, whatever the gate says. |

Chat's **Permissions** control is a shortcut over the same audited machinery:

- *Ask every time* → sets eligible capabilities to Ask;
- *Approve safe actions* → sets eligible capabilities to Auto;
- *Custom permissions…* → opens this page.

There is no unrestricted mode, by design.

---

## What "approved" means

Approval resolution is **metadata-only by default**: recording a decision does
*not* execute the action. The approval detail says so, and the response carries
`executes_action: false`. Turning an approval into an execution is a separately
governed capability (`approval_execution_relay`) — see
[To be fixed](../plans/TO_BE_FIXED.md) BUG-06 for the current limits.
