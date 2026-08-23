# Working in Build

Build is Raiker's coding surface. It is one conversation pointed at one
repository, with the agent's latitude stated on the composer instead of buried
in settings.

Build adds **no authority of its own**. Every gate, decision mode, approval and
tool is identical to Chat's — the difference is the composer, the operating
protocol a Build turn carries, and the default posture. If something is refused
in Build, it would be refused in Chat too, and the control that opens it is on
**Permissions** either way.

## Before your first Build turn

1. **A model has to be ready.** Build refuses to send until the exact selected
   model has passed a reachability check, and says which control fixes it. See
   [Connecting a model](connecting-a-model.md).
2. **Point Build at a repository.** Use **Repos** on the composer, or `/repos`.
   A local folder must resolve inside your workspace or it is refused; a GitHub
   `owner/repo` coordinate is recorded as a reference and makes no network call
   of its own.
3. **Decide what the agent may do.** A fresh account has every capability gate
   off. Nothing is broken — you have not opened anything yet. Open only what the
   work needs, on [Permissions](permissions-and-runtime-modes.md).

## The three modes

The mode picker is the centre of the composer. A mode is a **turn-scoped
posture** sent with the prompt, not a setting you have to remember to put back.

| Mode | What it does | When to use it |
|---|---|---|
| **Plan** | Refuses file writes, patches and commands outright. The runtime refuses them under `denied_by_turn_posture` — it is not prompt wording asking the model to behave | Reading an unfamiliar codebase, or getting a proposal before anything moves |
| **Edit** | Turns every file write, patch and command into a decision you accept or reject, and the unattended approval modes cannot swallow it | Changing code you want to see change |
| **Auto** | Adds no restriction of its own. The turn runs under exactly the permissions you already granted | Work you have already decided the shape of |

`Shift+Tab` cycles Plan → Edit → Auto without leaving the prompt.

**A mode can only ever tighten.** `allow` and `auto` are refused by the prompt
contract and refused again by the broker, so a turn can never grant itself
authority you have not given it. **That is why Build opens in Auto**: Auto is the
only mode that sends no override, so a new conversation runs under exactly your
standing permissions rather than quietly tightening below them. Choosing Plan or
Edit is a deliberate act.

**A mode changes no standing permission.** The chips write nothing to your
capability modes. Widening a capability stays on Permissions, under the step-up —
a recorded reason and, where the capability demands one, a threat-model
acknowledgement.

Read capabilities are deliberately outside the set a mode covers, so Plan stays
useful: it removes the ability to act, not the ability to look.

## Approval policy is a different control

Beside the mode picker is the approval policy: **Manually approve**,
**Automatically approve**, **Skip all approvals**, or **Decline what needs
asking**.

The mode chooses the *posture* of a coding turn. The approval policy chooses
whether an otherwise-eligible action waits for you. They are not the same
control, and **Skip** omits only the interaction — it never bypasses project or
path confinement, hunk validation, rollback, the sandbox, restricted command
policy, or a critical hold.

**Decline what needs asking** is the unattended posture. An action that would
have parked for a decision is refused instead, so a scheduled run carries on
with what it is allowed to do rather than stopping. Its refusals are recorded as
`denied_no_one_to_ask`, which reads differently from "you denied this" when you
come back to the record.

## The composer

`/` opens the commands Build really has:

| Command | What it does |
|---|---|
| `/plan-mode`, `/edit-mode`, `/auto-mode` | Select the turn posture |
| `/terminal` | Open the governed terminal panel |
| `/repos` | Manage this Build workspace's repository references |
| `/shortcuts` | The keyboard map for this surface |

`@` completes a path out of **the code map you built** — not out of the working
tree. It returns paths only: no symbols, no line numbers, no content. If the map
was never built it says `code_map_not_built` and offers the control that builds
it; if the gate is off it says `code_map_gate_disabled` and links to Permissions.
"Nothing matched" and "nothing could match" send you to different places on
purpose.

Your own messages carry **Copy**, **Edit** and **Retry**. An edit **adds a new
turn** rather than rewriting what you asked, because the transcript is a record.

## Making changes

**One patch, one approval, one reversible change set.** A unified diff may cover
several files, including creates and deletes, and it is applied as a single
approval. There is no partial application: one bad hunk fails the whole proposal.

**Matching is strict about which code you named, not about how you typed it.**
The exact text is tried first; when that finds nothing, the same search runs
again ignoring trailing whitespace and indentation style, and the file keeps its
own indentation rather than adopting the quote's. What does **not** relax is
uniqueness — an edit requires exactly one match, and a relaxed search that hits
two places is refused. Interior spacing is text, not formatting: `a + b` and
`a+b` remain a mismatch.

A section that edits or deletes must name a text file that already exists inside
the workspace; one that creates must name a path that does not. A patch naming
the same file twice is rejected before anything is written.

**Nothing writes into `.raiker/` or `.git/`.** Ever, by any path.

**Every approved mutation is checkpointed first.** The previous contents are
captured before the write. Note the honest limit: **the checkpoint capture is
complete and automatic, but there is no owner-facing rewind.** The Checkpoints
view and `/checkpoints restore` both compute a *preflight* — what a restore would
change — and perform nothing. To undo an applied change today, use git, or ask
the agent to reverse the edit.

## Running commands

An approved `shell` command runs **once**, against an allowlist, inside the
workspace, under a timeout and an output bound, with secret-like output redacted
before it is recorded.

**Where it runs is your choice, and the card says what that boundary really
enforces.** Selecting **Native OS sandbox** runs each command in its own Windows
AppContainer, Linux bubblewrap, or macOS Seatbelt boundary with no network
capability, the workspace reachable through a single grant, `.raiker` denied and
`.git` read-only. What the host actually enforces is measured, not assumed: a
probe runs a child inside the real boundary attempting six things, each also
attempted *outside* as a control. Only "worked outside, refused inside" counts;
if the control arm fails the result is **not proven** and nothing turns green.

`local_native` — explicit host access with reduced isolation — is the default
selection, and it is where background execution, a POSIX terminal and restart
reattachment are built. The native sandbox is foreground-only, and its card lists
what it does *not* have rather than showing disabled controls.

A container boundary persists for a session, so what one command installs the
next can use, and **Reset environment** puts it back to a known state.

## Committing and pushing

A `git_commit` records the change set you reviewed and stages exactly the paths
you saw — never `--all` — so `.raiker/` and `.git/` cannot be swept in, and the
repository's own hooks are disabled for the invocation.

**A push answers to its own switch.** Publishing sends repository content off
the machine, so `git_push` answers to **Git push** (`git_push_execution`) rather
than to Git writes, and it does nothing until the remote's host is on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`. The credential is stored encrypted from
**Settings → Git credential** and lent to one command at a time under a grant you
make — **once**, or **for this session** — carrying its own expiry, withdrawable
in one press, passed in the command's environment rather than on a command line,
and removed from every log, error and captured output for as long as the loan
lasts. Only HTTPS GitHub remotes are pushable. Raiker never forces and never
deletes a branch.

## Finding your way around code

Turning on **Code map** lets Raiker index the repository Build points at, so the
agent can ask where something is defined instead of guessing a search pattern. It
is rebuilt on demand and refreshed for the files an approved change touched.

Know what it is: Python is parsed with a real parser; fifteen other languages are
matched with bounded patterns, and each file records which extractor produced it.
**Find references** scans the files the map already accepted for word-boundary
uses of one identifier. It is textual, so a same-named symbol from another module
matches too — and it says so rather than implying a precision it does not have. A
scan that hits one of its bounds reports `partial` and names the bound. There is
no resolved call graph.

## The operating protocol

A Build turn carries an operating protocol a Chat turn does not: scale the effort
to what is at stake, name the assumption that would waste the work and test it
first, read the file before editing it, and check a claim before making it.

It is sent as a system message on every `surface: "build"` turn, and the surface
travels with the prompt into the audit record — so which protocol a turn ran
under is a fact rather than an inference. **It grants nothing**: every gate,
decision mode, approval and tool is identical on both surfaces. The full protocol
is [`RAIKER_BUILD_PROCESS.md`](../RAIKER_BUILD_PROCESS.md).

## Background work and scheduled agents

A Build turn can be handed to the background queue, and a task can be given a
cadence — `continuous` (20 minutes), `hourly`, `daily` or `weekly`. Each cycle is
**one governed turn**: it passes policy, gates and approvals exactly like a typed
prompt, and a cycle that parks on a decision reads as **blocked** with the reason,
not as failed.

Two honest limits: a schedule only fires while Raiker is running, so a closed
laptop is a missed cadence (recorded as skipped rather than owed); and a cycle
that finishes while nobody is looking updates the Tasks view and the audit log
without reaching you.

## When something is refused

Every refusal names the control that would allow it and links to the page that
holds it. The usual four, in the order they are checked:

1. **Agent runtime** — Settings → Runtime configuration. Is Raiker accepting new
   executions at all?
2. **Capability gate** — Permissions. Does this capability exist for you?
3. **Decision mode** — Permissions, or the composer. Ask, Allow, Auto or Deny?
4. **Approval** — Approvals. Your decision on this specific action.

A turn posture is a fifth, above all of them, and can only tighten.

Reason codes and their fixes are in [Troubleshooting](troubleshooting.md).

## Related

- [Permissions and the runtime](permissions-and-runtime-modes.md) — the control
  that opens whatever was refused
- [Working in Chat](working-in-chat.md) — the assistant surface, and the controls
  the two share
- [Tasks and projects](tasks-and-projects.md) — scheduling and organising work
- [`BUILD_WORKSPACE_SPEC.md`](../BUILD_WORKSPACE_SPEC.md) — the specification
  behind this page
