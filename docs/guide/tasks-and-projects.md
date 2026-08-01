# Tasks and projects

## Tasks

**Tasks → Plan work.** Pick one of four work types from the chip row; the form
adapts to your choice.

| Type | Extra field | Button | Behaviour |
|---|---|---|---|
| **Task** | — | Create task | Runs now |
| **Schedule once** | Start time | Schedule task | Runs once at that time |
| **Daily routine** | Start time | Create daily routine | Repeats every day from then |
| **Background agent** | — | Start background agent | Runs asynchronously until its work is complete or you stop it |

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

## Where to watch work run

**Observability → Work in action** is the live board: tasks in flight, scheduled
work with next-run times, and recorded subagents. Idle character movement there
is visual only — it does not mean the agent is working.

**Observability → Audit log** is the append-only record of every governed step,
filterable by session and event type.

## Known limits

- A background-agent run can end `failed` in the audit log without a
  user-visible reason (BUG-09).
- Task runs create sessions that appear in the sidebar's **RECENT CHATS**
  alongside real conversations (BUG-10).
- Creating a task by asking for one in Chat is specified but not shipped — the
  governed `create_task` tool exists, the conversational flow around it does
  not. See `docs/superpowers/plans/2026-07-26-chat-tasks-and-project-assignment.md`.
