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
| **Repeating** | — | Repeat, First run, Ends, If Raiker was not running | Create routine | Repeats on the chosen cadence, anchored to the first run, in your time zone |

A background agent starts now, so **How it runs** is asked under **Now** and
nowhere else — there is no scheduled variant of it to compose.

**Repeat** offers every cadence the scheduler honours: **Keep going** (a cycle
roughly every 20 minutes), **Hourly**, **Daily**, **Weekdays** (Monday to
Friday) and **Weekly**. A routine is
anchored to its **First run**, and every later cycle is counted forward from
that slot rather than from whenever the previous one happened to finish — so a
daily routine created at 4pm for a 9am first run runs at 9am, not at 4pm. The
form previews the next three runs as you choose them, and names the zone the
start time is read in. The preview skips slots that have already passed, because
that is what the scheduler does: a machine that was asleep does not wake up
running the same cycle twice. Build's side panel offers the same choice for a
standing agent; leaving its **First run** empty starts the first cycle on the
next scheduler tick.

**Daily, Weekdays and Weekly keep the time on your clock.** The zone the form
names is stored with the routine, and each slot is counted in calendar days in
that zone from the first run — so a routine for 09:00 in London runs at 09:00
on both sides of the October and March clock changes. Two edge cases are decided
rather than left to arithmetic: a time that does not exist on the day the clocks
go forward (01:30 in London) runs at the old offset that day only, an hour later
on the wall; a time that happens twice when the clocks go back runs once, at the
first. **Keep going** and **Hourly** are measured in elapsed time instead, since
"an hour from now" is still an hour across a clock change. A weekday routine
whose first run falls on a weekend first runs on the Monday.

**Ends** takes a last day. A routine whose next slot would fall after it
finishes instead of re-arming, and its card says that was its last scheduled
run. Leave it empty to keep going until you stop it.

A cycle is one governed turn. Policy, permissions and approvals apply to cycle
forty exactly as they did to cycle one, and a schedule only fires while Raiker is
running on this device — a closed laptop is a missed slot. **If Raiker was not
running** decides what a routine does about one:

| Choice | What happens to a missed slot |
|---|---|
| **Run it once when Raiker is back** (default) | One late cycle runs when Raiker returns; any other slots missed while it was away are skipped, never owed |
| **Skip it and wait for the next slot** | Nothing runs late. The routine moves to its next slot and its history records the slot as *skipped — missed while Raiker was not running* |

A slot claimed within fifteen minutes is on time, not missed. A one-off task
always runs late — skipping it would mean never running it. The card states a
routine's terms on one line: cadence and next run, zone, end, and *skips missed
runs* when that is the choice.

### The time a schedule is written in

Raiker tells every turn what the current date, day and time are, in the time
zone you set under **Settings → General → Time and place**. Nothing is left to
the model to remember, and no web connection is needed for it — turning web
access off does not cost a turn its calendar.

That is what makes "remind me tomorrow at 9" and "every Friday at 16:00" mean
what you meant. A recurring schedule keeps your zone rather than a fixed offset,
so `08:00 Europe/London` stays 08:00 local across the GMT/BST change — the
schedule stores the zone it was composed in, as described above. And each
cycle reads the clock **when it runs**: a routine you created on Monday evening
is told it is Tuesday morning, not Monday.

Under the control, Settings says what your clock reads in the chosen zone and
its offset from UTC right now — `UTC+05:30`, `UTC−04:00` — and that the offset
moves at a clock change. Changing the zone does not move a task already
scheduled; each keeps the zone it was set in.

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

**A run Raiker was stopped in the middle of is not lost or repeated.** If the
host stops while a task is running, the next start settles that run as one that
did not finish — its history says so — and does not run it again on its own,
because what it did before stopping is not known. A routine moves to its next
slot as after any failed cycle; read its conversation, then **Run now** if you
want it again.

Use the attachment panel to add a workspace path, image, or document. The same
governed attachment payload used by Chat and Build is stored with the task and
delivered when its scheduler turn starts. Attached files appear on the task card
as their own group, not inside the instruction text. Workbench preserves these
files when handing a draft to Task or Schedule.

The details under the composer are two groups. **Schedule** — repeat, first run,
ends and the missed-run choice, with the preview — appears only when the work
has a time. **Organisation** holds the rest:

- **Title** — derived from your instruction; type one to override it.
- **Priority** — Low / Normal / High.
- **Make this part of other work…** — reveals **Part of**, which nests the task
  under an existing one. A child of a task is a subtask; a child of a routine is
  a subroutine. It waits behind the button because most work is not part of
  other work.
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
completed if every child completed, failed if any failed or was cancelled.
**A decision on the parent reaches its children.** Pausing, resuming or stopping
a parent carries down to every task it delegated, and their children, each
reading *Delegated by a task the owner stopped: …*; a child that had already
finished is history and is left alone. The ownership runs one way only. A child carries its own approvals, because one
decision standing in for an unbounded number of later ones is exactly what the
per-turn permission envelope exists to prevent.

**Raiker can split its own brief.** A task working in its own conversation can
create children there, and each one picks the working method its part needs — the
reading half in Chat, the change-and-test half in Build. The parent is taken from
the conversation the work is running in, never named in the request, so a task can
only ever add to its own tree. Nothing is auto-denied for taking too long: a
delegated child waits for you, as every other decision does.

The list splits into **Open work** and **Finished work**, with counters for
open, scheduled, and finished. A task blocked on an approval says so and links
to the decision. Delegated work folds under the task that delegated it: the
parent shows a bar and *N of M delegated tasks settled · Show*, and **Show**
lists all of it — a settled child included, under its parent rather than again
under Finished work.

**Whether you were told is its own fact.** Background work that ends sends you a
notice, and if that notice could not be written — or the desktop notification
command you configured failed — the task still reads as what it was, *completed*
or *failed*, with **Delivery failed** and why beside it. Raiker never re-runs
work because its notice did not arrive.

**Will it run?** A scheduled or repeating task has a **Will it run?** button. It
answers before the run rather than after it, from what Raiker has on record:
whether the scheduler is running (or Raiker is paused), the routine's next run
and the clock it is read on, whether its model passed its last check, whether
quiet hours will hold its notice, and its limits. Each line reads *Fine*,
*Check*, *Will not run* or *Unknown*, with **Fix it** where something in Raiker
fixes it. It sends nothing to a provider and starts nothing — and a fact it could
not read is *Unknown*, never fine.

**One run has a time limit.** Each run of a routine is stopped after an hour
unless you set its own limit, from 1 to 720 minutes, under **Will it run?**. At
the limit the run is asked to stop at its next safe point, the same way **Stop**
asks — a step already under way finishes and is recorded — and the run is
recorded as stopped by its limit. It counts as a run that did not complete, so a
routine that always overruns is paused after three, like one that always fails.

**And a tool-call limit, if you want one.** Under **Will it run?**, *Tool-call
limit per run* (1 to 1,000) stops a run after that many tool calls; left empty,
a run keeps the runtime's own ceiling. **Will it run?** says both limits —
*Each run is stopped after 60 minutes or 40 tool calls.*

**And a cost limit.** *Cost limit per run* ($0.01 to $1,000) stops a run once
what it has spent reaches that amount, priced from the provider's own token
counts — cached prompt tokens included — at the rate Models → Pricing shows.
It is checked before each further question to the model, so a run can go over
by at most the one answer that crossed it, and a stopped run counts as one that
did not complete. A model with no known price cannot be held to an amount:
**Will it run?** says so, rather than letting the limit look like protection.

**A task is filed once.** Pressing **Create task** twice, or again after a lost
connection, files the draft once: the composer sends one key per draft and the
server returns the first answer for it. Change the draft and save again, and it
is a new task.

### One lifecycle, and what each part of it lets you press

Every task is in one of these phases, served by the runtime with the task, and
every surface — the Tasks page, Home's boards, Build's side panel — offers the
same controls for the same phase:

| Phase | Means | You can |
|---|---|---|
| **not started** | Filed and parked until you run it — how a task Raiker proposed arrives | **Run now**, **Cancel** |
| **scheduled** | Waiting for a future slot | **Cancel** |
| **queued** | Due; the next scheduler tick claims it | **Cancel** |
| **running** | A turn is in flight, including a granted approval being replayed and a stop you already asked for | **Stop** (not again while it is stopping) |
| **waiting** | Parked until something outside the run moves it: a decision, an answer, delegated work, or a pause | **Stop**; **Continue now** for a decided approval or a pause |
| **completed / failed / stopped** | Finished | **Run again** on one-off work |

**Cancel** and **Stop** are the same governed request; Cancel is its name before
anything has run. **Run now** is offered only before work has started — a
scheduled run keeps its slot, because running it early would be a second cycle.
**Run again files new work** with the same instruction, project, method, model
and files. A finished run is never replayed in place, so nothing it did — a
message sent, a file written — is repeated by pressing a button, and its own
history stays exactly as it ended. A routine is never run again: it re-arms
itself.

**A routine that keeps failing is paused.** A routine re-arms after every cycle,
whatever the cycle did, so one whose key expired or whose model went away would
otherwise fail on every slot. After **three cycles in a row** that did not
complete, Raiker pauses it instead, says why on its card — with what the last
cycle said — and tells you in the notification centre. A cycle that completes
starts the count again, so an occasional failure never stops a working routine.
Nothing is retried on its own: **Continue now** runs it once and puts it back on
its schedule, and **Stop** ends it.

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
(`projects/<slug>`), how many chats it holds and when it was last worked in.
**New chat** and **Start in Build** are on the card; **Archive**, **Move** and
**Delete** are in its `⋯` menu, because deleting a managed project deletes its
folder and that is not a neighbour for a button you press all day. A folder tree
shows nesting.

**Current project** is the one project new work starts in — the same one every
composer names. Projects says which it is, with **Stop working in it** beside it.
That is a different fact from the two lists, **Active** and **Archived**: a
project can be active without being the current one.

**Archive and restore.** Archiving a project archives what is inside it too, and
it leaves the Active list and every project picker. Nothing expires: an archived
project keeps its chats, files and tasks until you restore or delete it. Open it
from **Archived** to read it, and **Restore** to bring it back — with the
projects that were archived *with* it. A project inside it that you had archived
on its own, earlier, stays archived. A project whose parent is still archived is
restored by restoring the parent.

**Move** opens the folder tree, indented, with **Top level** first. The project
and everything inside it stay in the list but cannot be chosen — a project
cannot go inside itself — and archived folders are not offered. Its chats, files
and the projects inside it move with it; no folder on disk changes.

**Delete** first counts what will go: the chats and their exchanges, tasks,
checkpoints and files, and — for a managed project — the folder and how much is
in it. Projects inside it are kept, archived and moved to the top level. Nothing
deleted goes to a bin, so the dialog offers **Export project** first. You confirm
by typing the project's name, and removing a managed project's folder also asks
for your password (or authenticator code), as deleting your account does. An
attached folder is never touched: deleting its project removes Raiker's record of
it, not your files.

**Start in Build** and **New chat** both open that Work mode *in the project*:
the composer names it before you press Send, and the conversation or Build turn
is filed under it. Neither narrows what Raiker may retrieve — Chat's recall stays
account-wide by design — because where work is *filed* and what a turn may
*read* are two separate things. Nothing that already exists is re-filed: changing
the project changes where the next piece of work starts, not where past work
lives.

To move an existing conversation in, drag a recent chat onto the project, or use
**Move to project** from the session's `⋯` menu.

**Getting back to it.** Chat, Build, Design and Tasks each name the project a
turn runs inside, in the context line beside the composer. Opening that line
gives you **Open project work**, which opens *that* project rather than the list
of them.

Opening a project shows what belongs to it, in five sections rather than one
long column:

| Section | What is in it |
|---|---|
| **Overview** | The project's instructions and memory setting, and how many of each kind of thing is under it |
| **Files** | The project's folder, any file's provenance, and the files its chats shared, by name, type and size |
| **Work** | The chats started in it — each with its title, last activity, mode and status, and a click away from where it left off — and the tasks scoped to it |
| **Assets** | The **images** generated in [Design](design.md) while it was the working project |
| **Evidence** | The checkpoints taken in its sessions |

It opens on **Overview**, and the counts there say whether a section holds
anything before you open it. An edit to the instructions is kept while you move
between sections, and the other sections say so until you save it. If the
project's context was saved from another tab after this page opened it, **Save
context** saves nothing and says so, keeping your text — reopen the project to
see the newer version first. A move from a stale tree is refused the same way. Pictures made
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

**Quiet hours** are off until you turn them on. Choose when they start and end;
they are read on your own time zone's clock (the one in **General**), so 22:00 is
22:00 on both sides of a clock change. While they are on, nothing interrupts you
— not an approval, not a routine that stopped, not a security notice. Everything
is still recorded, the bell still counts it, and work that needs a decision
waits for one in **Approvals**. When they end you get one summary of what is
still unread — *While quiet hours were on: 3 notices were held* — not every
notice again, and it is offered once, whichever tab or device you open next.

The only way through is an **exception** you turn on: *Let security alerts
through*, inside Raiker, outside it, or both. Both start off. It covers security
findings and containment — a capability or server Raiker has stopped — and
nothing else; what a model writes in a notice can never make it urgent.

**What interrupts you** lets you stop a kind of notice from appearing in the
corner and on the desktop at any time of day — background work, security
findings and containment, or extensions and MCP servers. It is still recorded and
counted. Decisions have no such switch: work is waiting on them.

**Send a test notice** sends one through exactly the path a real notice takes,
using what is saved, and says what happened to it — shown now, or held until
quiet hours end. The desktop notification command you may have configured
(`RAIKER_OS_NOTIFY_CMD`) follows the same rules.

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

## Using Raiker as a personal agent

Raiker's personal-agent direction brings your context, goals, tasks and results
together. Today you can use Chat, memory, projects, scheduled/background tasks
and supported connectors. A dedicated durable goal coordinator, standing-intent
monitoring and general browser automation remain planned. This page explains
current workflows and marks the target clearly.

### Start with an outcome

Tell Raiker what you want to finish, which inputs it should use and what would
make the result useful. For example: “Compare these three vendor documents,
make a table with price and support terms, and save a report with source links.”
Name constraints such as deadline, relevant accounts and whether you want a
draft or a real external action. Raiker's tools still follow your permissions;
a goal or attached document does not approve a send or purchase.

Use [Chat](working-in-chat.md) for general work and
[Build](working-in-build.md) for code. A [project](tasks-and-projects.md)
groups related work. Current Chat recall is account-wide; putting work in a
project does not by itself restrict what the conversation can recall.

### Continue work and repeat it

Use **Tasks → Plan work** to run once, start a background agent, schedule one
run or create a routine. Review its thread to see results and steer future
cycles. Each cycle remains governed. Raiker must be running on an awake host;
a schedule is not a cloud service. See [Tasks and projects](tasks-and-projects.md)
for missed runs, timezone, budgets, delegated work and **Will it run?**.

Use the task controls to pause/continue/stop where offered, and the global STOP
control to request cancellation across work. A step already underway may finish
before stopping. Read the actual outcome and committed effects in its thread;
a lost notice does not mean the task failed or should be repeated.

### Give context deliberately

Set your timezone in Settings and review [Memory](memory.md) for capture,
recall, corrections, retention and forget/purge. Connect only the services and
accounts your workflow needs. Review the proposed action's destination and
arguments when approval is requested. A model may be local, private-network or
hosted; check where your context will be sent in
[Connecting a model](connecting-a-model.md).

Quiet hours hold interruptions according to your settings; they do not approve
work or stop the scheduler. Held decisions remain in the inbox. See
[Permissions and the runtime](permissions-and-runtime-modes.md).

### What the next personal-agent stages will add

The target is a goal record with explicit success criteria, a durable plan and
linked tasks that survive restarts; inspectable personal preferences; opt-in
proactive checks; provider-confirmed effects; and proposed reusable skills from
verified work. You should see what is progressing, what needs your decision,
what finished and what remains blocked. These are planned outcomes, not controls
available in the current interface.

Current web access reads and extracts web content; it cannot click or fill
forms in an interactive browser. Supported connectors have their own limits,
and a local reminder or calendar record is not evidence of an external service
change. Check [Known limits](known-limits.md) before relying on a workflow.

Developers can follow the [architecture](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
and [delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md).
