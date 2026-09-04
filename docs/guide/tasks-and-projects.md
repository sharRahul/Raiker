# Tasks and projects

## Tasks

Every scheduled cycle is a fresh governed turn with its own signed machine
identity. A parked task keeps its proposal attribution; continuing after an
approval rotates the token before work resumes. Activity therefore shows which
machine turn acted while account resources remain scoped to the human owner.

**Tasks → Plan work.** Pick one of four work types from the chip row; the form
adapts to your choice.

| Type | Extra fields | Button | Behaviour |
|---|---|---|---|
| **Task** | — | Create task | Runs now |
| **Once** | Start time | Schedule task | Runs once at that time |
| **Routine** | Repeat, First run | Create routine | Repeats on the chosen interval, anchored to the first run |
| **Background** | — | Start background agent | Runs asynchronously until its work is complete or you stop it |

**Repeat** offers every cadence the scheduler honours: **Keep going** (a cycle
roughly every 20 minutes), **Hourly**, **Daily** and **Weekly**. A routine is
anchored to its **First run**, and every later cycle is counted forward from
that slot rather than from whenever the previous one happened to finish — so a
daily routine created at 4pm for a 9am first run runs at 9am, not at 4pm. Build's
side panel offers the same choice for a standing agent; leaving its **First run**
empty starts the first cycle on the next scheduler tick.

A cycle is one governed turn. Policy, permissions and approvals apply to cycle
forty exactly as they did to cycle one, and a schedule only fires while Raiker is
running on this device — a closed laptop is a missed slot, and an elapsed slot is
skipped rather than run late.

**Every task has a conversation of its own.** Each cycle runs in it, so a routine
builds up a readable history instead of overwriting a one-line summary. The card
carries **Thread · N** once there is something to read; it opens in Chat, where
you can see what each cycle actually did and **reply**. A reply is not a note
filed somewhere — the next cycle runs in that same conversation and reads it, so
replying is how you steer a routine without editing its instructions. Routine
threads also appear on **Threads** beside your own conversations.

Use the attachment panel to add a workspace path, image, or document. The same
governed attachment payload used by Chat and Build is stored with the task and
delivered when its scheduler turn starts. Attached files appear on the task card
as their own group, not inside the instruction text. Workbench preserves these
files when handing a draft to Task or Schedule.

Common fields:

- **Title** — required.
- **Instructions** — required. The outcome, context, or constraints.
- **Parent work** — nest under an existing task. A child of a task is a subtask;
  a child of a routine is a subroutine.
- **Priority** — Low / Normal / High.

**A parent owns its children's outcomes.** A task that delegated work does not
report *completed* while a child is still open: when its own run finishes it
reads **waiting on delegated work**, and it settles when the last child lands —
completed if every child completed, failed if any failed or was cancelled. The
ownership runs one way only. A child carries its own approvals, because one
decision standing in for an unbounded number of later ones is exactly what the
per-turn permission envelope exists to prevent.

The list splits into **Open work** and **Completed work**, with counters for
open, scheduled, and finished. Each running item has a **Stop** button; a task
blocked on an approval says so and links to the decision.

Every run stays governed: it uses the same policy, approval, and audit path as
Chat, and stops at a safe boundary rather than being killed.

The global **STOP** switch in the top bar requests cancellation of every queued,
running, or paused task at once — governed and audited, not a force-kill.

## Projects

A project is a **named scope**: its own folder inside the workspace, plus the
sessions and checkpoints created while it is active. It is an organising label,
not an authority — selecting a project grants nothing, and its folder can never
leave the workspace.

**Projects → Create project.** Each card shows its path
(`projects/<slug>`) and session count, with actions: **Set active**, **New
chat** (starts a conversation inside it), **Details**, **Archive**, **Move**,
**Delete**. A folder tree shows nesting.

To move an existing conversation in, drag a recent chat onto the project, or use
**Move to project** from the session's `⋯` menu.

## The work board

**Workbench** is the first thing Raiker opens on, and it answers one question:
what is Raiker doing right now. It has three boards.

- **Running now** — a governed cycle in flight. Each one can be stopped at its
  next safe boundary.
- **Standing agents** — work with a repeating cadence, one governed turn per
  cycle.
- **Scheduled runs** — a single future run that has not fired yet.

## Where to watch work run

**Observability → Work in action** is the live board: tasks in flight, scheduled
work with next-run times, and recorded subagents. Idle character movement there
is visual only — it does not mean the agent is working.

**Observability → Audit log** is the append-only record of every governed step,
filterable by session and event type.

## Being told when background work ends

A scheduled or recurring task that finishes — or fails — writes a notification,
so a routine that ran overnight is not something you have to remember to go and
check. It appears on the bell and in **Observability → Notifications**, with a
link to **Tasks**, where the card carries the run's own conversation thread.

If you have allowed browser notifications and turned **Settings → Notifications
→ Desktop** on, the same notice reaches you outside the window — but only while
Raiker is not the window you are looking at, and it never leaves this machine.

**Only work you were not watching notifies.** An ordinary Chat turn is a task
too, and a banner behind an answer you are reading is noise, so those are
silent. The notice carries the task's title and whether it finished; what the
run actually produced stays in its thread, because a notification can end up on
a lock screen and the thread is one click away.

## Asking for a task in Chat

You can also ask Raiker for a task instead of filling the form in. The model
calls the governed `create_task` tool, which raises a real high-risk **Create
task** approval naming exactly what it would create, and approving it creates the
task here — the inbox answers *Executed once — “…” now exists* with a **Review in
Tasks** link beside it (**FIXED-106**).

Two things decide whether that happens, and both are yours:

- **Permissions → Workspace → Task creation** must be on, along with **Approval
  execution relay**. Until they are, the approval detail says *"Approval
  resolution is metadata-only"* and the button reads **Approve (record only)** —
  so you are told which of the two you are about to do **before** you decide, not
  after.
- **Project assignment** is the same control for the sibling tool,
  `assign_session_project`, which moves the conversation that proposed it into a
  project. A project is an organising label, so the move grants nothing.

## Known limits

As of 2026-08-08, one edge remains here:

- **A task created by approving a proposal starts on its own.** A task with no
  explicit time is work requested now, so approving a **Create task** proposal
  both creates the row and queues it: the resident host claims it on its next
  tick and runs it as a governed turn. That is the same behaviour as **Tasks →
  Plan work**, and the run is brokered and stoppable like any other — but the
  decision you are shown says "creates the task", not "creates and starts it".
  Tracked as BUG-64 in [To be fixed](../plans/TO_BE_FIXED.md).

Three limits this section used to list have shipped and are gone from it: a
background-agent run now ends with a user-visible reason (**FIXED-13**), a
task run no longer appears in the sidebar's **RECENT CHATS** — that list is
conversations, and task sessions are in Observability → Sessions (**FIXED-15**) —
and approving a task the agent proposed now creates it (**FIXED-106**).
