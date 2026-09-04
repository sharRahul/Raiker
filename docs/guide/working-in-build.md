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
4. **Choose a project.** Build reads and writes inside one project and refuses
   to send without one, so the project picker sits in the composer next to the
   mode. A turn run in a project may use **that project's files, that project's
   memory, and your account memory** — nothing from another project. The
   composer names the project it will run in; this is what that name means.
   See [Tasks and projects](tasks-and-projects.md).

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

Your own messages carry **Copy**, **Edit** and **Retry**, plus a `⋯` handle for
**Rewind to before this**. An edit **adds a new turn** rather than rewriting what
you asked, because the transcript is a record.

## Making changes

**One patch, one approval, one reversible change set.** A unified diff may cover
several files, including creates and deletes, and it is applied as a single
approval. Applying is still all-or-nothing: one bad hunk fails the whole
proposal, so a change either lands complete or does not land.

**You read the diff where it was proposed.** A pending decision in Build shows
the change under it — the file it touches, `+n −m`, and the hunk with its own
line numbers — with **Accept** and **Reject** beneath. It is the same governed
preview the Approvals inbox reads and the same record either surface resolves;
**Open in Approvals** is still there when you want the full detail, the execution
evidence, or the identity chain.

**You can accept part of it.** Each hunk carries a checkbox; clear the ones you
do not want and press **Accept**, and only the hunks you kept are applied. A file
whose hunks you all declined is not touched at all. The count above the diff says
where you are — *"2 of 5 hunks"* — with **Select all** and **Select none**.

This is a *smaller* decision, never a different one. What you can accept is
always some part of the change Raiker proposed and you read: there is no way to
edit a line here and approve your own text, because those bytes would be an
action nobody reviewed. Declining every hunk is refused rather than run as an
empty change — reject the proposal instead, which says what happened. The
checkbox appears only where all of that holds: a pending decision, on a diff the
applier understands, with more than one hunk in it.

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

**Every approved mutation is checkpointed first, and you can rewind it from the
turn that made it.** The previous contents are captured before the write, and a
rewind is a governed request rather than a button:

1. Hover your own message, open `⋯`, and choose **Rewind to before this** — or
   start from **Observability → Checkpoints** → *Preview rewind*. It is the same
   panel either way. From the turn it resolves *that turn's* checkpoint, not the
   most recent one; a turn that wrote none says so rather than offering a
   control that would fail.
2. The preflight names every file a rewind would rewrite, delete, or skip, and
   whether any of them was last changed by a different principal. Reading it
   changes nothing.
3. Tick the acknowledgement and press **Request this rewind**. That raises an
   ordinary approval and still changes nothing — the server recomputes its own
   plan, so the request cannot name the files.
4. Approve it in **Approvals**. The workspace goes back, the action re-passes its
   capability gate, policy review and posture check as it runs, and the rewind
   itself is captured — so it can be rewound the same way.

`/checkpoints restore <id>` prints the same preflight from the terminal;
`--confirm` raises the approval.

Two honest limits. A file over 8 MiB has no pre-image (`MAX_PRE_IMAGE_BYTES`), so
it is marked *not restorable* in the preflight and the approval that wrote it
told you so before you approved. And a rewind that would overwrite work last
changed by a different principal is **critical**: it says so before you ask, only
a live human can resolve it, and you will be asked to re-authenticate.

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

## Reading the repository

**Files** on the Build header opens the connected repository beside the
conversation: a tree you expand one folder at a time, and a read-only viewer with
syntax highlighting for the file you open. Drag the divider to resize it, or use
the keyboard on it — arrow keys move it, `Home` and `End` take it to its limits.
Below a narrow window it becomes a sheet from the left instead of a column.

Three things it deliberately does not do:

- **It never writes.** The two calls behind it are a directory listing and one
  bounded file read, both resolved through the same path authority a turn writes
  through and then re-checked against the repository's own root. A change to a
  file is still a proposal you accept.
- **It never walks the whole tree.** One directory is read when you open it, so
  pointing Build at a large repository costs nothing until you look.
- **It never guesses.** A file that is not text, is larger than the viewer's
  limit, or has gone says which of those applies. A language the highlighter does
  not ship a grammar for renders as plain text with no label rather than a wrong
  one.

**@** on the open file puts its path into the composer as the same mention the
completion menu writes, so reading a file leads straight to asking about it.

A GitHub repository is a coordinate, not a checkout: there are no files on this
machine to browse, and the panel says so rather than showing an empty tree.

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

**Language intelligence** is a separate switch beside it, for the questions the
map does not answer. With it on, Raiker can outline one file — every declaration
with its line range — jump to where an exact name is *declared* rather than
ranking a fuzzy match, and check a file for syntax problems. Nothing is stored:
these read the file on disk, which is what makes the outline correct the instant
after an edit.

The two switches are separate because they do different things to your machine.
The code map **writes** an index of your repository; language intelligence writes
nothing at all. You can have either without the other.

Know what the check is and is not: it is **parse-level** — syntax and structure,
not types, imports or lint rules — and it covers Python, JSON, TOML and YAML. A
file in any other language is reported as **not checked**, never as clean, in the
tool result and in Build's file viewer alike. A file that parses can still be
wrong; run the repository's own checker for the rest.

There is no language server. Raiker does not start one, so there is no
cross-file type inference, no rename refactoring and no completions — and
nothing long-running to supervise, crash or leak.

## The operating protocol

A Build turn carries an operating protocol a Chat turn does not: scale the effort
to what is at stake, name the assumption that would waste the work and test it
first, read the file before editing it, and check a claim before making it.

It is sent as a system message on every `surface: "build"` turn, and the surface
travels with the prompt into the audit record — so which protocol a turn ran
under is a fact rather than an inference. **It grants nothing**: every gate,
decision mode, approval and tool is identical on both surfaces. The full protocol
is [`RAIKER_BUILD_PROCESS.md`](../architecture/RAIKER_BUILD_PROCESS.md).

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
- [`BUILD_WORKSPACE_SPEC.md`](../architecture/BUILD_WORKSPACE_SPEC.md) — the specification
  behind this page
