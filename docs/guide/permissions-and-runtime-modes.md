# Permissions and the runtime

Raiker has two controls over what the agent may do:

1. **Capability gate** — the individual switch, per capability, per account.
2. **Decision mode** — per capability, how the agent must ask before doing
   something it is already allowed to do.

Behind both sits one runtime, and one question about it: is it accepting
executions at all? That is the danger-zone switch, not a fifth thing to
configure before your gates mean anything.

---

## Finding and changing permissions

Open **Permissions** to inspect the tools reported by your runtime. The page
reads top to bottom in the order the questions arrive.

**Posture** leads: one sentence saying how many of your permissions are
available to Raiker and how many are set to act without asking you, with the
counts beneath it as the page's status filter — **All**, **Available**,
**Unavailable**, **Needs review**, and **Selected** once you have selected
something. Availability describes the capability gate; policy, decision mode and
runtime checks still determine whether an action can execute.

**Needs your attention** and **Common permissions** come next, when there is
anything in them, and both are shortcuts into the registry rather than a second
copy of it. **All permissions** holds everything, grouped, with one toolbar:
search by tool name, identifier, description or group; narrow by **Group**;
**Expand groups** and **Collapse groups**; and **Clear filters** to restore the
full list. Searching reveals matching rows even in collapsed groups.

A row states what is on and what happens — `On · Ask me`, `Off · Never` —
without being opened. Open it to read what the capability does, whether Raiker
may use it on this account, what happens when Raiker wants to, and a **Why**
when this switch does not decide the matter by itself. Turn it on or off from
there. The decision controls are **Ask me**, **Allow**, **Automatic** and
**Never**; broader access continues through the confirmation dialog and
server-side authorization checks.

**How your permissions apply** sits at the foot of the page, closed. It is the
read-only authority summary — evidence for a question you ask second, which is
why it reads after the controls it summarises rather than before them.

Only editable permissions can be selected. The **Selected** chip lets you inspect
the selection, including items outside an earlier search. Bulk changes support
**Ask me** and **Never** only; selection and other mutations are disabled while
an update runs. Partial failures name the refused permissions and retain them
for retry. Refresh removes selections that are no longer editable. Counts,
filters and summaries use the same server-confirmed permission state.

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
agent can derive from it. **Owner control** is the gate and decision-mode
control; **Raiker agent** is a read-only result, and it answers in the same
words the control does — **Ask me**, **Allow**, **Automatic** or **Never** —
plus three that are not decisions at all: `Unavailable` when the capability is
switched off, `Not ready` when something it needs is missing, and `Unknown` when
the stored setting is not one Raiker recognises. Those three answer a different
question — whether it can run at all — which is why they keep their own words.
The agent cannot change its own authority. *Delegated authority*
at the top of the page shows both for every capability at once — as a table on a
wide window, and as one labelled card per capability on a narrow one, so the
verdict is never the part you have to scroll for. Each agentic turn uses
its own short-lived signed machine identity, so Activity and Approvals can name
the machine actor separately from you, the owner.

Raiker's registry contains 66 capability gates. **Permissions** displays the
owner-operable subset, grouped as follows; deliberately unavailable domains are
kept out of the interactive list altogether, and named in
[Capabilities with no enable path](#capabilities-with-no-enable-path) below.

| Group | Examples |
|---|---|
| Workspace | Audit export, Code map, Language intelligence, File writes, Git writes, Memory store/forget, Patch apply, Task creation, Project assignment, Semantic memory, Vector embeddings, Graph indexing |
| Local execution | Shell commands, Processes, Container execution, Subagents, Multi-agent teams |
| Network | Web fetch, Git push, Telemetry export, External channels, Channel approval relay |
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
  one. **Ask me** shows the exact text before you decide; **Allow** sends an
  ordinary memory write directly through the governed executor without a
  second approval prompt; **Never** refuses it. Text that looks like a credential
  is refused before any of those paths can store it. With the gate off — the
  shipped default — no turn can propose either, and the Memory page says so
  rather than promising proposals it cannot produce.
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
answers to Observability → Audit log → Export. **Telemetry export** is its
sibling and sits in **Network** rather than beside it: they carry the same
record, and an audit export writes a file beside the log while a telemetry
export leaves the machine.

Observability used to carry a *"Disabled / deferred capabilities"* chip list, and
it is gone. It did not show the domains above. It showed the **phase gates** —
the build-out flags each capability carries in the shipped registry — which is a
different list, and one that reads as a lie on a page: it named `web_ui` and
`dashboard` as disabled to an owner reading it in the dashboard, in a browser.
Two facts, both recorded here rather than displayed:

* **Which capabilities you cannot turn on** is the set above, and every
  capability's own state is on its **Permissions** card, where the switch is.
* **The phase gates**, for anyone tracing a refusal to its origin, are:
  `dashboard`, `desktop_ui`, `graph_codemap_indexing`, `graph_codemap_planning`,
  `plugin_execution`, `semantic_memory_review_queue`, `semantic_memory_writes`
  and `web_ui` (phase 3); `container_execution`, `external_channels` and
  `remote_execution` (phase 4); `admin_mutation`, `policy_mutation` and
  `role_mutation` (phase 5). A phase gate is not an account decision and never
  refuses a turn on its own — per-account resolution is what the Permissions page
  reads and writes. `/capabilities` in the terminal client prints the current set
  from the registry if you would rather ask the build than the guide.

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

### Language intelligence

**Language intelligence** sits beside Code map and is a different switch on
purpose. With it on, Raiker can outline one file, jump to where an exact name is
declared, and check a file for syntax problems after editing it.

The distinction between the two is what each does to your machine. Code map
**writes** an index of your repository and keeps it. Language intelligence writes
nothing at all — every answer is a parse of a file the agent could already open
with a file read, and nothing outlives the turn that asked. So you can have
either without the other, and turning one off does not quietly disable half of
the other.

What it checks and what it does not: the check is parse-level — syntax and
structure, not types, imports or lint rules — over Python, JSON, TOML and YAML. A
file in any other language is reported as **not checked**, never as clean. There
is no language server: Raiker starts no long-running process for this, which is
why there is no cross-file type inference, no rename refactoring and no
completions.

*Not to be confused with* **Graph memory indexing**, further down the same group.
That is a separate, unimplemented subsystem — a durable governed store of code
relationships — and it shows no **Turn on**.

---

## Decision modes

Independently of whether a capability is on, each has a decision mode:

| Mode | Behaviour |
|---|---|
| **Ask me** *(default)* | Raiker stops and waits for your decision each time. |
| **Allow** | Raiker goes ahead without asking, within policy. |
| **Automatic** | Raiker goes ahead and keeps going, within policy. The most permissive answer. |
| **Never** | Raiker refuses this, whatever asks for it. |

These are the owner-facing words for the four modes the runtime enforces. The
stored values, the API and the audit still read `ask`, `allow`, `auto` and
`deny`: **Never** answers *what should happen*, and `deny` is the name of the
mechanism that enforces it. Nothing about the authority model changed with the
wording.

A capability and its mode answer two different questions, and the page asks them
in that order when a row is opened — **Can Raiker use this?**, then **When Raiker
wants to use it**. That is what makes `On` + `Never` intelligible rather than
contradictory: the capability is available, and every attempt to use it is
refused.

Expand a capability's row on **Permissions** to change its mode. A change is
governed like any other: it asks for a reason and is recorded against your
principal.

A mode Raiker does not recognise — an older record, or a value from a newer
build — reads as **Unknown** rather than being guessed at. Unknown is not
evidence of permission: refresh the page, and if it persists, review the
capability's configuration.

There is no unrestricted mode, by design.

### Getting to a permission from the top of the page

Two sections sit above the full registry and both are shortcuts into it rather
than a second copy of it. Neither carries its own control: two editable copies
of one permission is how a page comes to disagree with itself, so both move you
to the one control that exists.

* **Common permissions** — the handful most owners come to change. **Manage**
  opens that capability's own row in the list below: it clears any filter that
  would hide it, expands its group, opens the row and puts the keyboard on it.
* **Needs your attention** — the capabilities set to **Automatic**, because that
  is the one mode that acts with nobody in the loop. **Review** opens the same
  row the same way. An entry says *runs automatically, without asking you* only
  when the capability is actually available and ready; when it is not, it says
  so, because configuring Automatic is not evidence that anything is running.

Both derive from the same list the registry renders, so a change made on a row
is reflected in them as soon as the runtime confirms it — they cannot show you a
mode the list below disagrees with.

### The delegated-authority summary

**How your permissions apply**, at the foot of **Permissions**, is a
**read-only summary** of the capabilities this account configures the most
authority for. It restates what you set — `On · Ask me`, `Off · Never` — beside
what that means for the agent: **Ask me**, **Allow**, **Automatic**, **Never**,
**Not ready**, **Unavailable** or **Unknown**. It uses the same words the
controls do, so one policy never has two names on one screen.

It describes *account configuration*. A task's own scope and the runtime's checks
at the moment of use can narrow what a turn may actually do, so a row reading
**Allow** is a statement about your settings and not a promise about a
particular action. Change anything it shows in the list below it.

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

### Being told a decision is waiting

A pending decision announces itself wherever you are in Raiker, with **Approve**,
**Deny** and **Decide later**. When Raiker is not the window you are looking at —
which is exactly when a background task raises one — it can also raise your
browser's own notification. That is off until you turn on **Desktop alerts**
under **Settings → Notifications**, it is only ever raised while Raiker is *not*
visible, and it announces each decision once. Nothing leaves this machine: it is
the browser's notification, not an email or a push service. The Approvals inbox
remains the record, and a decision you defer waits there.
