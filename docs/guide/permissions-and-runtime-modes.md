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
pregnancy/baby, home security, hardware operation, and checkpoint-restore
execution. These are **deferred**, not merely gated — no governed executor
exists, so the runtime refuses to pretend one does. SSH remote and Daytona
cloud execution instead require an owner-configured profile, their dedicated
capability gate, and approval for each action.
Observability → Diagnostics lists them under *"Disabled / deferred
capabilities"*.

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

## Composer approval policy

The **approval** pill in the Chat and Build composers is a per-account shared
composer preference that persists across sessions and both surfaces. It decides
how the agent presents actions that are already otherwise eligible to run. It is
separate from the runtime mode, capability gate, and per-capability decision mode
above: those controls decide
whether an action may run at all; the composer policy decides whether the user
is paused for an ordinary eligible action.

| Policy | Behaviour |
|---|---|
| **Manually approve** | Pauses for user approval before each otherwise eligible governed action. |
| **Automatically approve** | Runs an otherwise eligible action without a user pause, while keeping normal status and preview/evidence visible. |
| **Skip all approvals** | Runs an otherwise eligible action without a UI confirmation or generated preview. |

**Skip all approvals is not an unrestricted mode.** It skips only the user
prompt and preview step. The runtime still enforces project/path confinement,
hunk and context validation, atomic rollback for a failed patch, managed policy,
security and sandbox boundaries, restricted-command policy, and critical holds.
An action rejected by any of those protections remains rejected; Raiker does
not guess a malformed edit or force an action through.

The selected policy is remembered for later composer sessions. It does not
change the standing capability configuration in **Permissions**, nor does it
raise the ceiling set by **Settings → General → Runtime mode**.

---

## What "approved" means

Approving does one of two things, and the approval detail tells you which
**before** you decide — it is computed by the server from your own capability
gates, not assumed:

- **Approve and execute once.** A proposed file change (`write_file`,
  `edit_file`, `apply_patch`) is carried out, once, when both the
  `approval_execution_relay` capability and the target's own capability
  (`file_write_execution` / `patch_apply_execution`) are enabled — which is the
  default for an integrated Tier-1 capability. The change is re-governed at
  execution time (gate, decision mode, policy review, and a posture check on your
  session), the previous file contents are checkpointed first so it can be
  rewound, and the response carries `executes_action: true`. Writes into
  `.raiker/` or `.git/` are refused outright.
- **Approve (record only).** Everything else — shell, network, process, and any
  capability outside that pair — records your decision and executes nothing. The
  response carries `executes_action: false`.

Disabling either capability in Permissions returns file approvals to
record-only, and the detail view says so. A **critical** approval never takes
either path: it uses the human-only, step-up-verified critical lifecycle.

Either way, **your decision continues the work.** The turn that proposed the
action keeps its place: resolving the approval hands the model the real result —
or an explicit refusal when you said no — and the same turn picks up from there
rather than making you re-ask. Build streams the continuation straight back into
the conversation; the Approvals inbox offers **Continue the turn** and reports
what the agent did. A turn continues at most once per decision.
