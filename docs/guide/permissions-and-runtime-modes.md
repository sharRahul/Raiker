# Permissions and the runtime

Raiker has two controls over what the agent may do:

1. **Capability gate** — the individual switch, per capability, per account.
2. **Decision mode** — per capability, how the agent must ask before doing
   something it is already allowed to do.

Behind both sits one runtime, and one question about it: is it accepting
executions at all? That is the danger-zone switch, not a fifth thing to
configure before your gates mean anything.

---

## Configuring something is permission for it

Raiker's stated [security posture](../architecture/HANDOFF.md#security-posture-read-before-adding-any-restriction) is
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

## The runtime

**Settings → Runtime configuration** states what is running rather than asking
you to pick. There is no mode list: Raiker ships **one runtime**, and a fresh
install has it on, so a gate you turn on means what it says immediately.

The only runtime-level control is **Disable agent runtime** (and **Enable** once
disabled), behind the same step-up dialog every high-risk change uses. Disabling
really disables: while it is off, no capability can reach a runtime state, and
the refusal reads `activation_blocked: runtime_mode_not_active`, which now means
*the agent runtime is disabled* and nothing else.

**This replaced five modes** — Development preview, Local single user safe,
Local single user runtime, Multi user local runtime, and Hosted or networked
runtime. They were a fifth answer in front of four that already decided
everything: the capability's own gate, its threat-model acknowledgement, its
human confirmation token, and whether a real executor is registered for it.
Every capability copy that used to send you to a runtime mode now points at
**Permissions**, because that is where every runtime-level block resolves. If
you have an older bookmark or a stored audit row naming one of the five, it
still resolves to the single runtime rather than failing.

---

## Where work executes

**Settings → Runtime configuration** also chooses where Chat, Build and
scheduled work run: on this machine, or inside the native OS sandbox. Choosing a
remote or container environment is not a way around a permission — remote
commands still need the remote/cloud capability gate and its own credentials.

What a boundary does *not* do is stated on the environment card rather than
implied: the native sandbox is **foreground commands only**, with no PTY, no
background execution, no network grants and no persistence between runs. Those
are not switches waiting to be found; they are not built, and the card says so.
Re-measuring the boundary opens one connection to this host's default gateway on
a closed port, which is how the network claim is tested rather than asserted.

---

## Standing grants

A standing grant answers a *class* of approval once instead of every time. It
lets Raiker run a matching, sub-critical action shape without stopping to ask,
inside the scope and expiry you set, and you can withdraw it at any point.

It is bounded by design: a critical action is never covered by one, the grant
names the tool and the scope pattern it matches, and every use is recorded
against the grant so the record shows what it actually authorised. **Settings →
Security** lists the grants you hold, their use count, and when each expires.

---

## What monitoring records, and what it withholds

Connectors, plugins, subagents, providers, tools and local execution are watched
the same way monitored MCP connections are: sessions, findings, and a pause
control per subject.

What is stored about them is deliberately thin. Lifecycle status and findings
are **redacted** — the record keeps what happened and to which subject, not the
content that passed through — and local scans read only the workspace paths you
configured. The vault key encrypts stored connector credentials (API keys, OAuth
tokens); if it is missing or invalid every connector **fails closed** rather than
falling back to an unencrypted path.

Nothing appears under monitoring until something happens: a subject is listed the
first time it is contained or fails often enough to be watched.

---

## Capability gates

The Permissions page separates what you control from what the current Raiker
agent can derive from it. **Owner** is the gate and decision-mode control;
**Raiker agent** is a read-only result: `Direct`, `Ask`, `Denied`, or
`Unavailable`. The agent cannot change its own authority. *Delegated authority*
at the top of the page shows both for every capability at once — as a table on a
wide window, and as one labelled card per capability on a narrow one, so the
verdict is never the part you have to scroll for. Each agentic turn uses
its own short-lived signed machine identity, so Activity and Approvals can name
the machine actor separately from you, the owner.

Raiker's registry contains 66 capability gates. **Permissions** displays the
owner-operable subset, grouped as follows; deliberately unavailable domains are
kept out of the interactive list and reported in Diagnostics instead.

| Group | Examples |
|---|---|
| Workspace | Audit export, Code map, File writes, Git writes, Memory store/forget, Patch apply, Task creation, Project assignment, Semantic memory, Vector embeddings, Graph indexing |
| Local execution | Shell commands, Processes, Container execution, Subagents, Multi-agent teams |
| Network | Web fetch, Git push, External channels, Channel approval relay |
| Models | Hosted models, Home-lab models, Advisor model, Provider embeddings |
| Connectors | GitHub, Gmail, Google Calendar, Slack, Calendar (local), Email drafts, Reminders, plugin lifecycle |
| MCP | MCP builder, MCP connector |
| Automation | Scheduled routines, Approval execution relay, Admin/policy/role mutation |

Expand a row for its description and current decision mode, then **Turn on**.

### Off, and on by default

Most rows read **Off** until you turn them on: this account is fail-closed, and
nothing decided is not consent. A few read **On by default** instead. Those are
the capabilities whose enforcing path reads an *empty* gate table as the shipped
default rather than as a refusal — turning web access off is a decision you make,
and an untouched install is not that decision.

The badge is what the runtime would actually answer, not what the table happens
to hold, so the page cannot say a capability is off while the tool would run. The
row's card names which rule applies, and the only action such a row offers is
**Turn off** — that writes the refusal, and a written refusal always wins from
then on.

Two things worth knowing about how these rows behave elsewhere:

- **Memory store and Memory forget are reachable from Chat and Build.** With the
  gate on, a turn can propose remembering a durable fact or deleting a stored
  one; you see the exact text before deciding, approving really stores or
  removes the record, and text that looks like a credential is refused before
  you are asked. With the gate off — the shipped default — no turn can propose
  either, and the Memory page says so rather than promising proposals it cannot
  produce.
- **Build's Mode menu — Plan / Edit / Auto — does not change anything on this
  page.** It is the posture of one conversation, sent with each prompt and applied
  to that turn: Plan refuses file writes, patches and commands, Edit turns each one
  into a decision. A turn may only ever tighten itself, so **Auto** adds no
  restriction of its own and does exactly as much as the modes here already
  allow — which the Build composer states. `Shift+Tab` cycles the three, and
  Build **opens in Auto**: opening in a mode that sends no override means a new
  conversation runs under exactly what you set here, rather than silently
  tightening below it. Widening a permission happens here, under the step-up.

### The step-up dialog

Higher-risk capabilities (shell, processes, network, web fetch, hosted models,
MCP) require all three of:

- a **reason**;
- a **confirmation token** — any phrase you type, recording human intent. It is
  not a credential you have to obtain from anywhere;
- a **threat-model acknowledgement** tick.

**Confirm change** stays disabled until they are satisfied.

The acknowledgement points at a real document. As of 2026-08-23 **every
capability with a working executor has a written threat model** — what it does,
what it could go wrong, what stops it, and what risk is left over — indexed at
[`docs/threat-models/`](../threat-models/README.md). Read the one for the
capability you are opening. The most consequential are
[governed command execution](../threat-models/shell-execution.md),
[web reads](../threat-models/web-fetch.md),
[workspace file mutation](../threat-models/workspace-file-mutation.md) and
[durable memory writes](../threat-models/memory-write.md).

### Capabilities with no enable path

Some capabilities show no row at all: CCTV, finance, medical,
pregnancy/baby, home security, and hardware operation (18 registry entries are
not owner-operable). These are **deferred**,
not merely gated — no governed executor exists, so the runtime refuses to pretend
one does. SSH remote and Daytona cloud execution instead require an
owner-configured profile, their dedicated capability gate, and approval for each
action. Their **Remote execution** and **Cloud execution** rows are listed and
can be turned on after setup. Both have governed executors, but remain
unavailable until the owner configures and selects a compatible profile;
unsupported remote or cloud profile types still fail closed.

**Checkpoint restore** used to be listed here and is not deferred: it has had a
real executor since Workstream B, and it was unenableable only because it had no
entry in the activation registry — a block with no requirement to satisfy. That
entry landed with **FIXED-106**, so it turns on like any other Tier-1 capability.
Since **FIXED-270** it also has callers: Observability → Checkpoints, and
`/checkpoints restore <id> --confirm`. **Audit export** is beside it for the same
reason — a capability that had no executor at all until **FIXED-271**, and now
answers to Observability → Audit log → Export.
Observability → Diagnostics lists them under *"Disabled / deferred
capabilities"*.

### Code map

**Code map** is the switch over the repository index Build uses to find where
something is defined. It is off until you turn it on, and off means nothing is
scanned and nothing stored is read — Raiker does not index your tree because it
could.

With it on, the map is built when you connect a repository, when you point Build
at one that has never been indexed, and whenever you press **Rebuild index** in
Build → Repositories. It is refreshed for the files an approved change touched,
so the line numbers it hands out stay the line numbers the code is on. It is
never built during a turn.

The map records what each file is and what it declares — no file contents — and
what the agent gets back from it is coordinates: a path, a line range, a
signature. Reading the code still goes through the same file read, the same
workspace containment, and the same policy check as any other read, so turning
the map on does not widen what the agent may open. Turn it off and the agent
falls back to searching by pattern.

*Not to be confused with* **Graph memory indexing**, further down the same group.
That is a separate, unimplemented subsystem — a durable governed store of code
relationships — and it shows no **Turn on**.

---

## Decision modes

Independently of whether a capability is on, each has a decision mode:

| Mode | Behaviour |
|---|---|
| **Ask** *(default)* | Every AI-proposed action pauses for your approval. |
| **Allow** | Permitted without prompting. |
| **Auto** | Runs automatically. |
| **Deny** | Always refused, whatever the gate says. |

Expand a capability's row on **Permissions** to change its mode. A change is
governed like any other: it asks for a reason and is recorded against your
principal.

There is no unrestricted mode, by design.

---

## Composer approval policy

The **approval** pill in the Chat and Build composers is a per-account shared
composer preference that persists across sessions and both surfaces. It decides
how the agent presents actions that are already otherwise eligible to run. It is
separate from the capability gate and the per-capability decision mode above:
those controls decide whether an action may run at all; the composer policy
decides whether the user is paused for an ordinary eligible action.

| Policy | Behaviour |
|---|---|
| **Manually approve** | Pauses for user approval before each otherwise eligible governed action. |
| **Automatically approve** | Runs an otherwise eligible action without a user pause, while keeping normal status and preview/evidence visible. |
| **Skip all approvals** | Runs an otherwise eligible action without a UI confirmation or generated preview. |
| **Decline, don't ask** | Refuses an otherwise eligible action instead of queuing it. |

**Skip and Decline are opposites, and the menu says so under each.** Both stop
Raiker asking you. *Skip* then **runs** the action; *Decline* then **refuses**
it. Decline is the posture for a run with nobody watching — a scheduled routine
at 06:00 cannot answer a prompt, and parking on one is not the same as declining:
only the refusal lets the rest of the work carry on. The refusal is recorded like
any other, with its own reason (`denied_no_one_to_ask`) so an audit reader can
tell *"you refused this"* from *"nobody was there to ask"* — and only the second
means running it again while you are watching would have worked.

Decline can only ever refuse **more**. It never widens a gate, never skips one,
and an action policy already allows is untouched.

**Skip all approvals is not an unrestricted mode.** It skips only the user
prompt and preview step. The runtime still enforces project/path confinement,
hunk and context validation, atomic rollback for a failed patch, managed policy,
security and sandbox boundaries, restricted-command policy, and critical holds.
An action rejected by any of those protections remains rejected; Raiker does
not guess a malformed edit or force an action through.

The selected policy is remembered for later composer sessions. It does not
change the standing capability configuration in **Permissions**, and it cannot
run anything while the agent runtime is disabled in
**Settings → Runtime configuration**.

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
- **Approve and create it once.** A proposed task (`create_task`) or a proposed
  move of the conversation into a project (`assign_session_project`) is carried
  out the same way, under `task_management_runtime` and
  `project_assignment_runtime` — both listed in Permissions under **Workspace**
  as *Task creation* and *Project assignment*. Each is a local, reversible,
  owner-scoped row rather than a file, so the notice names what it creates
  instead of promising a checkpointed diff, and the inbox links to the result.
- **Approve and record it once.** A proposed branch (`git_branch`) or commit
  (`git_commit`) is carried out under `git_write_execution`, listed in
  Permissions under **Workspace** as *Git writes*. Before you decide you see the
  change git itself would record — for a commit the exact file list and the
  whole diff, including files git does not track yet; for a branch the two refs
  it moves between. Approving stages exactly those paths and nothing else:
  `.raiker/` and `.git/` are never swept in, whatever else is in your working
  tree, and the repository's own hooks do not run. The notice names the branch
  or the commit that now exists. This is git history rather than a checkpointed
  file write, so undo it in git.
- **Approve and publish it once.** A proposed push (`git_push`) is carried out
  under its own capability, `git_push_execution`, listed in Permissions under
  **Network** as *Git push* — separate from *Git writes*, because letting Raiker
  change your repository is not the same decision as letting it publish. Before
  you decide you see the repository, the remote and its host, the branch, and the
  commits the remote does not have. It never forces and never deletes a branch,
  and it does nothing at all until the remote's host is on
  `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` and `RAIKER_GITHUB_TOKEN` is set. Unlike a
  commit, this leaves your machine and git cannot take it back — undo it on the
  remote.
- **Approve (record only).** Everything else — network, process, and any
  capability outside that set — records your decision and executes nothing. The
  response carries `executes_action: false`.

Disabling any of these capabilities in Permissions returns its approvals to
record-only, and the detail view says so **before** you decide — the button reads
**Approve (record only)** rather than **Approve and execute once**. A **critical**
approval never takes either path: it uses the human-only, step-up-verified
critical lifecycle.

Either way, **your decision continues the work.** The turn that proposed the
action keeps its place: resolving the approval hands the model the real result —
or an explicit refusal when you said no — and the same turn picks up from there
rather than making you re-ask. Build streams the continuation straight back into
the conversation; the Approvals inbox offers **Continue the turn** and reports
what the agent did. A turn continues at most once per decision.
