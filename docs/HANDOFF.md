# Raiker handoff

Read this file and `docs/IMPLEMENTATION_STATUS.md` before beginning work. Deep
history belongs in git; this is intentionally only the current pick-up point.

## Non-negotiable runtime rules

- Fail closed: a missing gate, policy, credential, allowlist, executor, or
  approval denies the action.
- Route every model and tool action through the existing governance, policy,
  approval, and typed-event paths. Do not add a side-door.
- Keep credentials in owner-controlled storage/environment only. Never render,
  log, or commit them.
- Add a typed event to `EVENT_TYPES` before emitting it.

## Current product state — 2026-07-14

- Chat search is a real full-history search over chat titles, prompts, and
  summaries. Results show session titles and reopen the selected chat.
- Projects create/select/delete storage-backed project scopes. Deleting a
  project permanently deletes its chats and project directory after an explicit
  warning; project deletion does not delete chats outside that project.
- The web topbar is deliberately minimal. It does not display a raw principal
  ID, runtime-ready label, or model chip.
- Projects currently organise sessions only. They do **not** yet provide
  project-specific instructions, shared files, or project-scoped memory.
- The generic connector store, four governed read connectors (GitHub, Gmail,
  Calendar, Slack), approvals, audit events, budgets, and the connector web
  surface are implemented. The first real write action remains unimplemented.
- Plugin code has two real, governed runtimes: bounded subprocess and a
  no-network/read-only container. Host in-process import of plugin code is an
  explicit security non-goal, not a deferred implementation task.
- The sandbox image has a governed, pull-only acquisition capability. It accepts
  only an exact owner-allowlisted image/registry, invokes only `docker pull`,
  and never builds or runs an image.
- Tasks can persist schedules and recurrence, but scheduling is stored-only:
  it never runs work or sends a reminder.

## Asset status

`raiker-hero*.png`, `raiker-mark*.png`, PWA icons, and favicons are RGBA files
with transparent pixels. The web CSS uses them as direct transparent background
images. Their public URLs now include a deployment version query, so existing
clients fetch the transparent files instead of retaining an old opaque copy.

## Next implementation slice — requires design approval

**First real connector write action.**

Implement one narrow service mutation (recommended: a GitHub issue comment)
through the connector store's immutable write intent and approval path. It must
use an actual service executor, server-built URL, owner credential and egress
allowlist, metadata-only audit, replay protection, and an approval before the
network request. It must never execute merely because the capability is `ask`.

Do not broaden it to arbitrary OpenAPI mutations in the same slice. Write a
threat model, tests, and implementation plan first.

## Prioritised product backlog

Validate each item against the current codebase before starting it. Build one
governed vertical slice at a time.

1. **Project context:** project instructions, shared attachments, and an
   opt-in project-memory boundary. Chats moved into a project must inherit that
   bounded context; moving out must remove it. This is the clearest assistant
   workflow gap.
2. **Conversation organisation:** nested projects/folders, tags, pin/bookmark,
   bulk move/delete/export, and project-only export. Search exists; these do
   not.
3. **Reliable memory controls:** user-visible memory list with edit, pin,
   delete, scope, provenance, and expiry controls. Reuse the governed memory
   store; do not create a second memory system.
4. **Real reminders and routines:** an opt-in local scheduler that executes
   only an approved, bounded reminder/action, with delivery status, retries,
   pause, and cancellation. Stored-only task metadata is not automation.
5. **Connector write reference:** one narrow, real service write (for example,
   GitHub issue comment) through immutable intent + approval + an actual
   executor. Never make a write action execute on `ask` alone.
6. **Agent evaluation and observability:** trace a goal/plan/tool/approval
   chain with latency, cost, outcome, and user feedback; add replayable
   regression scenarios before making autonomy broader.
7. **Agent identity and least privilege:** distinct agent/service identities,
   short-lived scoped credentials, per-tool grants, and a user-facing access
   review. Existing principal and approval controls are a base, not a complete
   agent-identity surface.
8. **Interoperability activation:** a governed MCP activation surface with
   capability manifests, per-server permissions, approval-aware calls, and
   lifecycle/audit state. Current MCP startup readiness is intentionally
   disabled.

### Research signals behind the backlog

- Users repeatedly ask for project-only memory, files/instructions, nested
  folders, tags, and export: [OpenAI Projects documentation](https://help.openai.com/en/articles/10169521-projects-in-chatgpt), [Reddit folder/tag/export request](https://www.reddit.com/r/ChatGPT/comments/1shhv7z/openai_gave_us_projects_instead_of_folders_and/), and [Reddit project-memory discussion](https://www.reddit.com/r/ChatGPT/comments/1r9uk8s/i_tried_using_chatgpt_projects_to_organize_400/).
- Reminders and recurring tasks are a mainstream assistant expectation:
  [ChatGPT scheduled-task coverage](https://techcrunch.com/2025/01/14/chatgpt-now-lets-you-schedule-reminders-and-recurring-tasks/).
- Mature agent platforms emphasise policy/tool permissions/approvals and
  observability: [Observe.AI Agent Platform](https://www.observe.ai/platform/agent-platform),
  [Microsoft Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/authorization-agent-id),
  and the [MIT AI Agent Index](https://aiagentindex.mit.edu/data/2025-AI-Agent-Index.pdf).

## Verification and handoff

For a backend slice, run focused tests first, then `pytest`, `ruff check .`,
and the relevant validation scripts. For web work run, from `apps/web`,
`npm run check`, `npm run lint`, `npm test -- --run`, and `npm run build`.
Record only the commands actually run and their results in the commit/PR; do
not copy old green counts into this file.
