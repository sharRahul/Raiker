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
   to send without one. Pick one from `+` → **Work in a project**, or from the
   **Choose one** offer in the line under the composer that says a project is
   still needed. A turn run in a project may use **that project's files, that
   project's memory, and your account memory** — nothing from another project.
   The composer's context line names the project it will run in; this is what
   that name means. See [Tasks and projects](tasks-and-projects.md).

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

Build uses the same composer as Chat and Design, with one control Chat does not
have:

```text
[ + ]  [ Tools ]  [ Auto ▾ ]     Project Raiker · Raiker/main · 12%   Sonnet 4.5  [ Send ]
```

The **mode** stays on the bar because it decides how much the next press is
allowed to do and it changes from turn to turn. The repository and the project
are in the context line, because a turn that may edit files or run a command has
to say where — and that is a fact to read, not a control to operate.

The composer names two different things: **Filed in** the project — where the
conversation is kept — and **works in** the workspace folder every relative read,
write and command starts from. A managed project's own folder is not where
commands start, and the line does not pretend it is.

Open the context line and it reads as one boundary, in the order that decides
where a turn's work lands: **Filed in → Works in → Repository → Runs on → Model**. The model
entry says whether it is your default or this work's own choice, and names a
fallback that would answer instead rather than letting it stand in silently.
The line never guesses a fact it could not read — an environment that could not
be read is absent, not assumed to be this machine.

The whole line is Raiker's own answer, read from the same selections a turn is
held to, rather than pieced together by the page. It also says where a local
repository may be written and whether the model **leaves this machine**. When a
link would stop the turn — no project, an environment that is not available, a
model that cannot run — the line under the composer names that one link and
offers the place that fixes it.

`+` adds to this turn: **Upload a file**, **Choose from the project**, **Mention
a file from the code map**, **Work in a project**, **Dictate**.

**Tools** carries what Build can be asked to do, including two Chat does not
have — **Run a command** in the governed terminal, and the code-map mention
above. A capability that is turned off is listed with the reason and a way to
change it; nothing in the menu grants anything, and the runtime still judges
each action when it is invoked.

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
always some part of the change Raiker proposed and you read. Declining every
hunk is refused rather than run as an empty change — reject the proposal
instead, which says what happened. The checkbox appears only where all of that
holds: a pending decision, on a diff the applier understands, with more than one
hunk in it.

**You can also correct it — as your own proposal.** **Edit…** beside Accept and
Reject opens the proposed diff for you to change. Pressing **Propose as a new
change** denies what Raiker offered and raises *yours* in its place, with its own
preview and its own approval. Nothing runs until you accept that.

It works this way rather than as an edit box on the decision in front of you
because an edit is a **different action**, not a smaller one. A narrowing is
provably inside the change you already read; bytes you typed are not, and the
one thing Raiker will never do is run arguments no human approved after seeing
them. So you see them — the audit trail records the original as denied, names
what replaced it, and the change that executes is the one you signed off.

Raiker refuses a replacement that is empty, that is not a readable diff, that is
identical to the proposal, or that reaches a file the original never named. The
last is not about permission — the new approval would govern it — but a change
to somewhere else is a change to propose on its own terms.

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
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`. The credential is the one you select in
**Settings → GitHub** — a stored token, your GitHub CLI sign-in, a saved Git
credential or an SSH key, each checked against the GitHub account it claims —
and it is lent to one command at a time under a grant you make — **once**, or
**for the conversation** that proposed the push — narrowed to the repository and
branch, carrying its own expiry, withdrawable in one press, passed in the
command's environment rather than on a command line, and removed from every
log, error and captured output for as long as the loan lasts. The approval
records the commit it showed you, and the push sends that commit or refuses if
the branch moved; afterwards the remote's branch is read back and the result
says whether it was confirmed. GitHub.com remotes only, over HTTPS or SSH.
Raiker never forces and never deletes a branch.

**Letting the agent push without asking each time** takes a **delegation**
(Settings → GitHub → *Delegations*): one repository, the operations you allow,
the branches it may touch (a prefix such as `raiker/*`, never the default
branch), how long, and how many actions. Neither a standing grant nor setting
**Git push** to *always allow* is enough on its own. Merging, deleting a branch
and changing workflows are never delegated. Before each step the delegation is
checked again — credential, account, installation and repository — and if
anything changed, the step waits for you. Before a push or a pull request Raiker
also asks GitHub whose repository it is now (once a minute at most); a
repository transferred, re-created or out of reach makes the step wait. On a
repository with a GitHub remote, creating a branch and committing follow the same
rule: an agent does them unprompted only on a branch a delegation covers.

**Handing Raiker an issue to fix** (Settings → GitHub → *Issue to pull
request*): choose a delegation — or none, and every write asks — the issue
number and a work branch, then **Show the plan**. Each step says whether it
*Runs*, *Runs under the delegation* or *Asks you first*, and merging, deleting a
branch, protected branches and workflows are listed as never part of it.
Nothing is scheduled until you pick the project that holds the repository's
local checkout and press **Schedule as a Build task**. The task's instructions
are not its authority: each write still meets the same delegation check, and
anything it does not cover waits in Approvals.

**The task runs in one repository.** Point Build at the repository's local
checkout — or at a worktree made for this issue — *before* you schedule it: the
plan says *Runs in widget — the repository Build is pointed at now, and only
there*. Each run checks that Build is still pointed at it. If you have since
chosen another repository, or none, the run does not start, changes nothing,
and its history says which repository it was set up for and which Build is
pointed at now; select the first again to let it run.

**Pull requests Raiker opened** are listed under **Changes → Pull requests**
with what GitHub itself confirmed. After GitHub accepts a new pull request,
Raiker reads it back with the same credential: **Confirmed by GitHub** means
that read returned the number, head branch and base branch Raiker asked for,
with the head commit it shows; **GitHub answered differently** means it
returned another branch or number; **Not confirmed** means the read-back
failed, so only the create response is known. The approval's result says the
same. A receipt is evidence only; merging stays with you, on GitHub.

## Whether a change was checked

A Build turn that changed files says what its own record supports, under the
answer: **Verified**, **Not verified**, **Partly applied**, **Checks failed**,
**Waiting on you**, **Stopped** or **Result unknown**. A turn that changed
nothing shows nothing — unless a change it proposed is still waiting for your
approval, which reads **Waiting on you**. **Partly applied** means some of the
changes it proposed landed and others failed or were refused; **Stopped** means
you stopped it after it changed files, and what it applied stays.

The checks are yours. In **Work → Projects**, open the project and write one
command per line under **Checks** (at most ten), such as `pytest -q` or
`npm test`, then **Save context**. Build turns in that project are asked to run
each one exactly as written after their last change. **Verified** means every
check ran *after* the last change and exited 0, read from Raiker's own command
record, not from what the model said it did. A check that ran before the last
change, a command that only looks like it, or no checks at all leaves the
change **Not verified**; the line lists each check and what happened to it.

Three more things can only lower the answer, never raise it:

- **Where a check ran.** A check counts only in the selected repository's
  folder. The agent runs it there by passing that folder as the command's
  working directory; the same command run at the workspace root, which checks a
  different tree, reads *ran outside the repository folder (in the workspace
  root)*.
- **What is on disk.** Every file the turn wrote is read back afterwards. A file
  that is no longer there is listed as *no longer on disk* and keeps the turn
  **Not verified**. A file someone changed later is listed as *changed since this
  turn*; it does not undo checks that passed on what the turn wrote.
- **Whether the target moved.** A Build turn records the folder, repository,
  branch and command environment it started on. If any of them has changed since
  — you switched branch, say — the line says *The branch this turn started on has
  changed since* and the turn is not verified across it. Otherwise it says where
  the turn ran: *Ran in app on main from abc1234*. A commit the turn made itself
  is not the target moving.

## Where a turn runs

The Build header shows the target beside the repository name: the branch and
commit, and where code such as a test run would execute — **Sandbox**, **This
computer**, **Your environment** or **Remote environment**. Hover or focus it for
the folder, the repository's identity (its remote, with any credentials taken
out), the command environment and the target's fingerprint. A GitHub repository
reads **GitHub · no checkout**.

On a repository with a GitHub identity, the target also says what a turn here
may do **without asking you**: **Delegated: push, pull request on raiker/\*** when
a delegation covers this repository, or **Writes ask you** when none does.
Hovering lists each delegation's operations, branch pattern, whether it may open
a pull request, when it ends and how many actions it has left, that merging is
never delegated, and whether a Git credential is selected.

If the repository's folder has moved or been deleted, the header says so and a
Build turn **does not start**: the message names the folder and asks you to
reconnect the repository or choose another. The file and git tools would
otherwise fall back to the workspace root, which is not the repository you
pointed Build at.

A turn that is waiting for your approval is checked again before it continues.
If its folder, repository, branch or environment changed while it waited, it is
**not continued**: the turn says *This turn was not continued: the folder,
repository, branch or environment it started on has changed since*, and you
start a new turn where you are now.

The same check covers the authority the turn started under. A Build turn
records the delegations on its repository and the Git credential selected when
it began. If, while it waited, you **revoked** one of those delegations (or it
expired or ran out of actions), or removed, replaced or invalidated that
credential, it is **not continued** either — *a repository delegation it started
under was revoked or ran out, or the Git credential it would use was removed or
replaced* — and nothing more runs. Check **Settings → GitHub**, then start a new
turn.

**Stopping a turn** keeps its record. A Build turn you stop is closed as
**Stopped** at its next safe boundary; the target it started on stays recorded,
its outcome is judged against that target, and the folder is free at once — a
turn in another conversation in the same checkout can start straight away.

### Working on two things at once: worktrees

Two Build conversations writing into one checkout would change each other's
files. So while another conversation's Build turn is running in the same folder,
a new one does not start and says why. Give the second piece of work its own
folder instead:

1. Open the repository menu on the Build header and press **New worktree** on
   the repository.
2. Name it — `fix-login`, say. Raiker creates `<repository>.worktrees/fix-login`
   on a new branch `raiker/fix-login` from the current commit, and connects it as
   its own repository. Your main checkout does not move.
3. Press **Use** on the new entry. The header now shows `raiker/fix-login`, and
   that conversation's turns, Changes and outcome are the worktree's.

An existing branch, or one already checked out somewhere, is refused rather than
shared. **Remove worktree** removes the folder only when it has no uncommitted
changes — otherwise nothing is removed and it says so — and always keeps the
branch and its commits.

A turn that has shown *running* for more than fifteen minutes is treated as
abandoned (a host that stopped mid-turn), so it never holds a folder for ever.

### Which commits Raiker made

A commit Raiker records on your approval ends with two lines naming the
conversation and turn it came from:

```
Raiker-Session: sess_…
Raiker-Turn: turn_…
```

The commit's approval card says so before you decide. **Changes → Recent commits** reads them back. **Made in Raiker** means the turn
they name is one this Raiker recorded; **Says Raiker — no record here** means the
lines are there and nothing here backs them (anyone can type them, and a commit
made by another installation has them too). A commit without them is simply a
commit. These lines are evidence for whoever reads the history; nothing in Raiker
reads them to decide what may run.

If you sign your own commits, Recent commits also shows Git's verdict on each
signature: **Signed**, **Signed — key not trusted here**, **Bad signature**,
**Signed — key expired**, **Signed — key revoked** or **Signed — can't check
here** (no verifier on this machine). An unsigned commit shows nothing. Raiker
never signs a commit itself — a signing key that asks for a passphrase would
stall the approved commit — so this reports your signing, not its own.

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

### The workbench

Beside the conversation, one pane shows four views of the same workspace —
**Changes**, **Preview**, **Terminal** and **Runs** — rather than four panels
competing for the column. Which one is in front follows what just happened:
opening a file brings Preview forward, starting a command brings Terminal, and a
turn that changed files brings Changes — except while you are reading that
turn's own output, because you are already looking at the thing the event is
about. A turn finishing never *opens* a closed pane; it is not a request to look
at anything.

Where you left it is where it comes back. The view you were reading and whether
the pane was open survive a reload, the same way the file explorer's width and
open state do — and, like the explorer, neither is restored as a drawer over a
narrow window you did not ask to open.

**An approval comes first.** On a narrow window the workbench and the file
explorer open as drawers over the conversation, which is where an approval is
reviewed. When a turn raises a new approval they step aside, keeping the view
and place you had, so the decision is not hidden under something you were
reading. Reopening one while the approval is still waiting is your choice, and
it stays open.

### Reviewing the patch

**Changes** offers **Review this patch** above the diff. It reviews the exact
uncommitted patch — the same change set a commit would record — and lists each
finding with its severity, the file and line, what was found and what to do:

- a possible credential added (the value is never shown);
- an unresolved merge conflict marker;
- a debugger breakpoint left in source code;
- a change to a CI or workflow definition, which Build leaves to you;
- added text that tells a model to ignore its instructions or reveal its prompt —
  issue and repository text is data, never an instruction to Raiker;
- source changed with no test change;
- a changed file that **no longer parses**, at its line — an independent parser,
  the same one the file viewer and the agent's own diagnostics use. With
  **Language intelligence** off in Permissions the review says the parse check
  did not run rather than implying the files are fine.

Each finding new since the last review of this repository is marked **New**, and
anything the last review raised that is gone is listed under **Fixed since the
last review**. When the patch has changed since its last review, Changes says the
last review was of an earlier version.

**Ask Raiker to fix** on a finding writes a request for exactly that fix into the
composer — the file, the line, the finding, and *Do not commit, push or merge* —
for you to read, edit and send. It sends nothing itself, so a repair is one more
ordinary turn under your modes and approvals. When that turn settles and the patch has
changed, Changes reviews it again **once**, by itself, and says *Reviewed again
after the repair* — nothing loops, and the next repair is again yours to ask
for. A finding raised by several reviews in a row says **In 3 reviews in a
row**, so a repair that is not working is visible before you ask for it again.

**Ask the model to review** (it names the model chosen in the composer, such as
**Ask the Anthropic assistant Haiku 5.5 to review**) sends the same exact patch to that model and
shows what it thinks is wrong under **Model review**. Before it is sent, every
line passes through Raiker's credential redaction and the patch is framed as
data, not instructions; no tools are offered. Its findings are kept to the files
the patch changed, are at most **Medium**, and are labelled *These are its
reading, not checks*: they never make a turn **Verified** or keep one from it.
The reading is stored for that patch and that model, so asking again shows the
stored reading instead of asking twice, and a different model or an edited
patch is a new reading. The request uses your provider connection and is
audited as `patch_model_review_completed` (which model, which patch, how many
findings — never the patch or the answer). An answer Raiker cannot read is said
as such and stores nothing.

**Signed here.** Each stored review — Raiker's own and a model's — is signed
with this installation's key when it is taken and checked every time it is
shown. **Signed here** means it is exactly what was taken. If the stored review
has been changed since, Changes says *This stored review no longer matches the
signature Raiker made when it was taken … don't rely on these findings*. The
signature is evidence only; it grants and blocks nothing.

If a declared check passes but the review you took of the current patch has a
high-severity finding, the turn's outcome stays **Not verified** and says so.

The review is kept for that exact patch, identified by its fingerprint. Opening
Changes again on the same patch shows **Reviewed** with the same findings rather
than a fresh set; any edit makes it a different patch, and the button comes back.
The review reads only: it changes no file, and acting on a finding is an
ordinary change you approve.

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
- [`BUILD_WORKSPACE_SPEC.md`](../plans/BUILD_WORKSPACE_SPEC.md) — the specification
  behind this page
