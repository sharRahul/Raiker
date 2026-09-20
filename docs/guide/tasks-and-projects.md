# Tasks and projects

## Tasks

Every scheduled cycle is a fresh governed turn with its own signed machine
identity. A parked task keeps its proposal attribution; continuing after an
approval rotates the token before work resumes. Activity therefore shows which
machine turn acted while account resources remain scoped to the human owner.

**Tasks → Plan work.** The composer asks two questions, in this order: **when
to run**, and — only where there is a choice — **how it runs**.

| When to run | How it runs | Extra fields | Button | Behaviour |
|---|---|---|---|---|
| **Now** | One pass | — | Create task | Runs now, once |
| **Now** | Until it is done | — | Start background agent | Runs asynchronously until its work is complete or you stop it |
| **At a time** | — | Start time | Schedule task | Runs once at that time |
| **Repeating** | — | Repeat, First run | Create routine | Repeats on the chosen interval, anchored to the first run |

A background agent starts now, so **How it runs** is asked under **Now** and
nowhere else — there is no scheduled variant of it to compose.

**Repeat** offers every cadence the scheduler honours: **Keep going** (a cycle
roughly every 20 minutes), **Hourly**, **Daily** and **Weekly**. A routine is
anchored to its **First run**, and every later cycle is counted forward from
that slot rather than from whenever the previous one happened to finish — so a
daily routine created at 4pm for a 9am first run runs at 9am, not at 4pm. The
form previews the next three runs as you choose them, and names the zone the
start time is read in. The preview skips slots that have already passed, because
that is what the scheduler does: a machine that was asleep does not wake up
running the same cycle twice. Build's side panel offers the same choice for a
standing agent; leaving its **First run** empty starts the first cycle on the
next scheduler tick.

A cycle is one governed turn. Policy, permissions and approvals apply to cycle
forty exactly as they did to cycle one, and a schedule only fires while Raiker is
running on this device — a closed laptop is a missed slot, and an elapsed slot is
skipped rather than run late.

### The time a schedule is written in

Raiker tells every turn what the current date, day and time are, in the time
zone you set under **Settings → General → Time and place**. Nothing is left to
the model to remember, and no web connection is needed for it — turning web
access off does not cost a turn its calendar.

That is what makes "remind me tomorrow at 9" and "every Friday at 16:00" mean
what you meant. A recurring schedule keeps your zone rather than a fixed offset,
so `08:00 Europe/London` stays 08:00 local across the GMT/BST change. And each
cycle reads the clock **when it runs**: a routine you created on Monday evening
is told it is Tuesday morning, not Monday.

If you have not set a zone, Raiker offers the one your browser reports and says
so — it will not apply it for you. Setting `Europe/London` and then opening
Raiker from another country is a statement about your schedule, and Raiker does
not treat it as a mistake to correct.

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
- **How to work** — **Chat** or **Build**, offered inside a project. It picks the
  working method the cycles run under and nothing else: same tools, same
  permissions, same approvals. Choose **Build** when the work is *read this
  repository, change it, run the tests*; leave it on **Chat** for everything
  else. A Build task needs a project, which is why the control appears only in
  one. On the board a task says `· Build` when that is what it is, and says
  nothing when it is the ordinary case.

**A parent owns its children's outcomes.** A task that delegated work does not
report *completed* while a child is still open: when its own run finishes it
reads **waiting on delegated work**, and it settles when the last child lands —
completed if every child completed, failed if any failed or was cancelled. The
ownership runs one way only. A child carries its own approvals, because one
decision standing in for an unbounded number of later ones is exactly what the
per-turn permission envelope exists to prevent.

**Raiker can split its own brief.** A task working in its own conversation can
create children there, and each one picks the working method its part needs — the
reading half in Chat, the change-and-test half in Build. The parent is taken from
the conversation the work is running in, never named in the request, so a task can
only ever add to its own tree. Nothing is auto-denied for taking too long: a
delegated child waits for you, as every other decision does.

The list splits into **Open work** and **Completed work**, with counters for
open, scheduled, and finished. Each running item has a **Stop** button; a task
blocked on an approval says so and links to the decision.

Every run stays governed: it uses the same policy, approval, and audit path as
Chat, and stops at a safe boundary rather than being killed.

The global **STOP** switch in the top bar requests cancellation of every queued,
running, or paused task at once — governed and audited, not a force-kill. It
states how many it would reach before you press it, and with nothing running it
is a quiet icon rather than a red one.

## Projects

A project is a **named scope**: its own folder inside the workspace, plus the
sessions and checkpoints created while it is active. It is an organising label,
not an authority — selecting a project grants nothing, and its folder can never
leave the workspace.

**Projects → Create project.** Each card shows its path
(`projects/<slug>`) and session count. **New chat** and **Start in Build** are on
the card; **Archive**, **Move** and **Delete** are in its `⋯` menu, because
deleting a managed project deletes its folder and that is not a neighbour for a
button you press all day. A folder tree shows nesting.

**Start in Build** and **New chat** both open that Work mode *in the project*:
the composer names it before you press Send, and the conversation or Build turn
is filed under it. Neither narrows what Raiker may retrieve — Chat's recall stays
account-wide by design — because where work is *filed* and what a turn may
*read* are two separate things. Nothing that already exists is re-filed: changing
the project changes where the next piece of work starts, not where past work
lives.

To move an existing conversation in, drag a recent chat onto the project, or use
**Move to project** from the session's `⋯` menu.

Opening a project shows what belongs to it, in five sections rather than one
long column:

| Section | What is in it |
|---|---|
| **Overview** | The project's instructions and memory setting, and how many of each kind of thing is under it |
| **Files** | The project's folder, and any file's provenance |
| **Work** | The sessions started in it, and the tasks scoped to it |
| **Assets** | The **images** generated in [Design](design.md) while it was the working project |
| **Evidence** | The checkpoints taken in its sessions |

It opens on **Overview**, and the counts there say whether a section holds
anything before you open it. An edit to the instructions is kept while you move
between sections, and the other sections say so until you save it. Pictures made
with no project chosen stand alone and are not shown under any project.

Click any of those images to open **that** picture in Design, with the canvas
scoped to this project and a **Show all images** way back out. **View all in
Design** keeps the project too, so neither route drops you into every image you
have ever generated. The strip shows eight and says how many there are when
there are more.

## The work board

**Workbench** is the first thing Raiker opens on, and it answers one question:
what is Raiker doing right now. It has three boards.

- **Running now** — a governed cycle in flight. Each one can be stopped at its
  next safe boundary. A repeating task appears here *while its cycle runs*, and
  carries its cadence and next slot with it.
- **Standing agents** — work with a repeating cadence that is waiting for its
  next cycle, one governed turn per cycle.
- **Scheduled runs** — a single future run that has not fired yet.

A standing agent whose cycle is running is one row, not two. It used to appear on
both boards, which is two true statements about one piece of work and reads as
two pieces of work.

**Stop, Continue and Run now mean the same thing wherever you press them** — on
the board, on the Tasks page, or in Build's side panel. *Stop* asks the run to
stop at its next safe boundary, so a cycle already in flight finishes its current
step; it is never a force-kill. When Raiker cannot tell whether the request took
effect it says so and offers the task's own history, rather than reporting that
nothing happened — a request that lost its answer may well have been applied.

## One task, and everything it has done

Every task has an address of its own: **`#/tasks?task=…`**, reached by pressing
its title on the work board, on the Tasks page, or in Build's side panel. It
opens above the board rather than instead of it, so following a link never costs
you the page you were on.

What it shows is the task's **attempts**, newest first — not a second account of
the task, but the governed events its own lifecycle wrote, grouped into the runs
they describe. So the history and the audit log cannot disagree: it *is* the
audit log, read at the scope of one task.

- **An attempt** opens when a cycle starts and closes on whatever settled it —
  completed, did not complete, waiting for approval, stopped, or waiting on
  delegated work.
- **A continuation** is numbered alongside the runs and named for what released
  it, because a parked run being let through is not the same as the work having
  been tried twice. When the runtime recorded *which* decision released it, the
  attempt links to that decision.
- **A run that never settled** says *still running* rather than anything
  reassuring. That is the row to look for when a Stop or Run now could not be
  confirmed.
- **A routine's cycles each get their own attempt.** A repeating task is
  rescheduled rather than completed, so what Tuesday's cycle did used to be a
  summary line Wednesday's cycle overwrote.
- **Filed** is its own record, above the first attempt, so a task that has not
  run yet opens on when you asked for it rather than on nothing.

A task belonging to another account has no address here: its id answers *"That
task is not on this account's board"*, which is the same visibility rule the
board itself applies.

![A task's attempt history, with each run's outcome and the conversation it
produced](../screenshots/2026-09-15-task-history/task-attempt-history.png)

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
link to **Tasks**, where the card carries the run's own conversation thread and
its title opens the attempt history above.

**Settings → Notifications** decides where you see it, and nothing else. *Show
unread notices inside Raiker* docks the newest unread one in the corner of
whatever page you are on — opening it marks it read and takes you to what it is
about, and the bell in the top bar counts them either way; *Alert me outside Raiker*
raises the browser's own notification for the same ones, only while Raiker is not
the window you are looking at, and it never leaves this machine. If the browser
has blocked notifications, the page says so rather than leaving a switch that
silently does nothing.

Every notice is recorded in **Observability → Notifications** whether or not
either switch showed it, so turning both off loses nothing.

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
task run no longer appears among the owner's own conversations — those are on
**Threads**, and task sessions are in Observability → Sessions (**FIXED-15**) —
and approving a task the agent proposed now creates it (**FIXED-106**).
