# Chat task and project-assignment actions

## Purpose

Let a user create tasks, reminders, and alarms, or assign the current chat to
a project through natural conversation. Raiker must ask concise follow-up
questions for missing details, use the existing governed task/project services
for every mutation, and post a normal conversational receipt on success.

## Interaction

Raiker recognizes requests to create a task, reminder, alarm, or schedule and
extracts a title, description, date/time, recurrence, and project when they
are present. It asks only for required missing facts. For example, “remind me
tomorrow” requires a time; “set an alarm for 07:00” creates a one-time reminder
with that time.

When the action completes, Raiker writes a clear receipt in the transcript:

> Created task: Send the report — reminds you Friday at 09:00. Review it in Tasks.

The receipt states what the task is and what it will do, and links to Tasks.
It contains no governance, policy, event, or checkpoint payload.

For “move this/last chat to <project>”, Raiker resolves the current session and
matches only projects visible to the user. A unique match is used. No match
produces a concise not-found reply. Multiple matching projects produce a
numbered/labelled choice question; nothing moves until the user chooses.
Successful moves state the chat title and destination and link to Projects.

## Architecture and authorization

Add focused `create_task` and `assign_session_project` tool specifications to
the governed chat tool registry. The tool broker carries the authenticated
principal and active session id to executors as trusted execution context; those
values are never model-provided arguments. Their executors validate structured
arguments and call the existing `DashboardService.create_task` and
`DashboardService.set_session_project` methods; they do not write SQLite
directly or make a browser-side mutation.

The current global permission policy remains authoritative. An action follows
the existing approval/decision-mode path, and only a completed result creates a
chat receipt. Failed, denied, or unresolved actions receive a concise
user-facing explanation without claiming completion. Existing task and session
events provide the audit trail in Tasks, Sessions, and Checkpoints.

For these two local, reversible actions, approval resolution resumes the exact
previously validated action once. The resume record carries the original action
id plus trusted principal/session context, rejects a second execution, and
emits the normal tool completion evidence. It never reconstructs arguments from
new model text or a browser request.

## Data and validation

- Task title is required and follows the existing task title limits.
- Date/time is normalized server-side and a missing or ambiguous time is
  clarified rather than guessed.
- Reminders/alarms are represented by the existing task `reminder_at` and
  `scheduled_at` fields; recurrence uses the existing task recurrence format.
- Project matching is case-insensitive exact-name first, then a bounded
  case-insensitive contains match. Matches are scoped to the current user.
- Session assignment may target only the active chat session and a project
  visible to the user; no session id is accepted from the model.

## Verification

- Unit tests cover extraction/clarification state, exact and ambiguous project
  matching, task creation, reminder normalization, and current-session scope.
- API/tool tests prove the chat action invokes existing services and preserves
  their authorization/audit behavior.
- Web chat tests cover follow-up prompts and normal success receipts with Tasks
  or Projects links, without governance metadata.

## Non-goals

- No browser-side direct task or project mutation.
- No silent choice among duplicate project names.
- No arbitrary session assignment by a model-supplied identifier.
- No governance cards in the chat transcript.
