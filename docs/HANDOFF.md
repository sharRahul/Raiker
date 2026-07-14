# Raiker handoff

Read this file and `docs/IMPLEMENTATION_STATUS.md` before beginning work. Deep
history belongs in git; this is intentionally only the current pick-up point.

## Goal

Make Raiker a secure AI product that combines an AI assistant, a governed AI
agent, and an extensible agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a platform, Raiker should
provide the governed runtime foundation for models, tools, plugins, interfaces,
memory, approvals, audit events, checkpoints, and integrations.

Raiker must support user-owned model choice across LLM backends — local models
such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM;
private-network providers; and hosted API providers such as Anthropic, OpenAI,
Gemini, and OpenRouter. No model, interface, plugin, or capability should
bypass governance. Every action must remain policy-aware, observable,
auditable, approval-driven where required, human-governed, user-controlled, and
fail-closed by design.

## Non-negotiable runtime rules

- Fail closed: a missing gate, policy, credential, allowlist, executor, or
  approval denies the action.
- Route every model and tool action through the existing governance, policy,
  approval, and typed-event paths. Do not add a side-door.
- Keep credentials in owner-controlled storage/environment only. Never render,
  log, or commit them.
- Add a typed event to `EVENT_TYPES` before emitting it.

## Current product state — 2026-07-14

- Conversation organisation has landed its third slice: nested projects/folders.
  Arbitrary-depth folder nesting via hybrid adjacency list (`parent_id`) +
  materialized path (`path`) on the `projects` table. Two deletion modes:
  **archive** (AI-autonomous, soft — archives entire subtree) and **delete**
  (human-only, hard with orphanage cascade — descendants reparented to NULL,
  archived, path prefixed with `orphaned/`). Context inheritance: ancestor
  contexts merge into a session's project context (instructions concatenate
  root→leaf, attachments union, leaf's `memory_enabled` wins). Path
  management is done in Python (not a DB trigger) for reliability. API:
  `GET /api/projects/tree`, `PUT /api/projects/{id}/move` (human-only),
  `PUT /api/projects/{id}/archive` (any authenticated principal),
  `POST /api/projects` accepts `parent_id` for nested creation,
  `DELETE /api/projects/{id}` always requires `confirm=True`. Web:
  `ProjectTreeNode.svelte` recursive component, `ProjectsView` tree section
  with archive/move/delete actions. `ProjectView` includes `parent_id`,
  `path`, `is_archived`, `archived_at`. Tests: `tests/test_nested_projects.py`
  (18), `tests/test_projects.py` (+4 API), `test_api_contract_schemas.py`
  guards `ProjectView` nesting fields. Project-only export remains deferred.
- Reliable memory controls have landed their first slice (backlog item 3): a
  user-visible Memory view over the EXISTING governed memory store — list
  with provenance, scope, sensitivity, confidence, retention; pin/bookmark;
  forget through the governed path (human-only); and an incognito opt-out
  boundary that withholds approved project memory from the turn context when
  on (the memory is not deleted). No second memory system is created.
- Tool execution defects fixed: `connector_read` was denied by policy
  (unknown_or_denied_tool) despite having a real executor — now routed as
  read-shaped like `github_read`; `connector_write` was denied — now routed
  to the approval path whose intent + execution the broker already owned.
  The governed connector tools now actually work when the owner enables them.
- The chat surface opens its "How this turn was governed" timeline while a
  turn streams, so the agent is not a black box — the user sees gather →
  plan → act → verify live instead of a generic "Working…".
- Conversation organisation has landed a second slice: per-session tags.
  Tags are organizing labels only (like the per-session `pinned` flag and
  the `projects` table) — they grant nothing and change no gate, policy, or
  authority. A `session_tags` table holds a many-to-many tag set;
  `DashboardService.set_session_tags` is human-only, normalizes input
  (trim/lowercase/dedupe/length+count caps), and reuses the same
  user/session visibility boundary (an account cannot retag another
  account's session). `delete_session` and `delete_project` cascade
  `session_tags`. API: `PUT /api/sessions/{id}/tags`; the Sessions view
  renders chips with per-chip × remove, an inline add-tag input, and a
  tag-substring filter. Project-only export remains deferred.
- Conversation organisation has landed its first slice: per-session
  pin/bookmark and single + bulk delete in the Sessions view. Pinned
  sessions surface first; deletion is human-only and respects the same
  user/session visibility boundary as every governed read (an account
  cannot delete or pin another account's session). The per-session events
  transcript file is removed on delete so it is not orphaned.
- Chat search is a real full-history search over chat titles, prompts, and
  summaries. Reopening a search result now hydrates its persisted turns in
  the chat surface (prompt + the agent's response message + status) and lets
  the user continue the same session — no new session is created merely to
  view history. The live per-event timeline is not replayed for restored
  turns; new turns stream as usual. The backend `/api/sessions/{id}` read
  enforces the same user/session visibility boundary as every governed read.
- Projects create/select/delete storage-backed project scopes. Deleting a
  project permanently deletes its chats and project directory after an explicit
  warning; project deletion does not delete chats outside that project.
  Nested projects/folders now support arbitrary-depth hierarchy, move, and
  archive operations (see above).
- The web topbar is deliberately minimal. It does not display a raw principal
  ID, runtime-ready label, or model chip.
- Projects provide bounded, explicit context for their assigned chats:
  instructions, shared attachment references, and an opt-in approved-memory
  boundary (`project:<project_id>`). A chat outside the project receives none
  of that context. Nested folders inherit ancestor context via
  `DashboardService.get_session_context`.
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

**Project-only export + real reminders.** Memory controls have landed their
first slice (list/pin/forget + incognito), conversation organisation has
landed three slices (pin/bookmark + delete, per-session tags, and nested
projects/folders with archive/orphanage delete + context inheritance). The
remaining organisation backlog (project-only export) and backlog item 4
(real reminders/routines — an opt-in local scheduler that executes
approved, bounded actions) are the next assistant-workflow gaps. Build one
governed vertical slice at a time against the current codebase.

## Prioritised product backlog

Validate each item against the current codebase before starting it. Build one
governed vertical slice at a time.

1. **Project context:** project instructions, shared attachments, and an
   opt-in project-memory boundary. Chats moved into a project must inherit that
   bounded context; moving out must remove it. Project schedules must remain
   project-scoped. This is the clearest assistant workflow gap.
2. **Conversation organisation:** nested projects/folders, tags, pin/bookmark,
   and bulk delete/export have landed. Project-only export remains deferred.
   Search exists and hydrates persisted transcripts on reopen.
3. **Reliable memory controls:** user-visible memory list with edit, pin,
   delete, scope, provenance, expiry, import/export, and search-participation
   controls. Include a separate opt-out/incognito boundary. Reuse the governed
   memory store; do not create a second memory system.
4. **Real reminders and routines:** an opt-in local scheduler that executes
   only an approved, bounded reminder/action, with delivery status, retries,
   pause, and cancellation. Stored-only task metadata is not automation.
5. **Connector write reference:** one narrow, real service write (for example,
   GitHub issue comment) through immutable intent + approval + an actual
   executor. Never make a write action execute on `ask` alone.
6. **Agent evaluation and observability:** trace a goal/plan/tool/approval
   chain with latency, cost, outcome, and user feedback; add record/replayable
   regression scenarios, outcome review, and an OpenTelemetry-compatible export
   with configurable prompt/content redaction before making autonomy broader.
7. **Agent identity and least privilege:** distinct agent/service identities,
   short-lived scoped credentials, per-tool grants, and a user-facing access
   review. Existing principal and approval controls are a base, not a complete
   agent-identity surface.
8. **Reusable governed workflows:** project/user skills and plugin-packaged
   playbooks with clear scope, provenance, review, and versioning. Add
   deterministic pre/post tool and session hooks only where enforcement or
   audit must be guaranteed; route them through the existing policy and event
   paths. Current plugin hooks remain deliberately inactive.
9. **Interoperability activation:** a governed MCP activation surface with
   capability manifests, per-server permissions, approval-aware calls, and
   lifecycle/audit state. Current MCP startup readiness is intentionally
   disabled.
10. **Always-available channel gateway:** a local, long-lived, paired-device
    gateway for approved messaging channels, with per-channel session routing,
    idempotent delivery, connection health, resume/reconnect across approved
    devices, and explicit remote-access trust. Build on the existing webhook
    reference channel; do not turn inbound messages into trusted instructions.
11. **Supervised computer use:** only after connector writes and the gateway
    are mature, add a connector-first fallback for browser/screen interaction.
    Require per-application approval and blocklists, keep sensitive domains
    excluded, label screen content untrusted, and make every side effect
    approval-gated and auditable.

### Research basis (2026-07-14)

This backlog is informed by provider documentation, not only OpenAI research:

- **Claude and Claude Cowork:** projects have isolated chat history, knowledge,
  attachments, and instructions; Cowork combines connected tools, scheduled
  work, plugins, explicit folder/tool bounds, deletion approval, computer-use
  safeguards, and enterprise observability. Claude also separates project chat
  search/memory and supports memory import/export. This reinforces items 1, 3,
  4, 5, 6, 7, and 11.
- **Claude Code:** persistent project context, skills, isolated subagents and
  teams, MCP, lifecycle hooks, and distributable plugins separate reusable
  workflows from deterministic guardrails. This informs items 6, 8, and 9.
- **OpenAI Codex:** skills, plugins, scheduled work, sandboxed task execution,
  and record/replay demonstrate the value of maintainable, testable automation.
  This informs items 4, 6, and 8.
- **Hermes Agent:** persistent memory, self-created/reused skills, command
  approval/container isolation, cron delivery, and a messaging gateway make
  memory controls, bounded automation, and transport governance product-level
  concerns. This informs items 3, 4, 8, and 10.
- **OpenClaw:** a single self-hosted gateway owns channel routing, sessions,
  device pairing, typed events, health, and idempotent side effects. This
  informs item 10.

Primary sources: [Claude support collection](https://support.claude.com/en/collections/4078531-claude), [Claude Projects](https://support.claude.com/en/articles/9517075-what-are-projects), [Claude chat search and memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context), [Claude memory import/export](https://support.claude.com/en/articles/12123587-import-and-export-your-memory-from-claude), [Cowork support collection](https://support.claude.com/en/collections/19667525-claude-cowork), [Cowork project tasks](https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork), [Cowork computer use](https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork), [Cowork OpenTelemetry](https://support.claude.com/en/articles/14477985-monitor-claude-cowork-activity-with-opentelemetry), [Claude Code documentation](https://code.claude.com/docs/en/), [Claude Code extensions](https://code.claude.com/docs/en/features-overview), [Claude Code hooks](https://code.claude.com/docs/en/agent-sdk/hooks), [OpenAI Codex manual](https://developers.openai.com/codex/codex-manual.md), [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs), [OpenClaw overview](https://docs.openclaw.ai/), and [OpenClaw gateway architecture](https://docs.openclaw.ai/concepts/architecture).

## Verification and handoff

For a backend slice, run focused tests first, then `pytest`, `ruff check .`,
and the relevant validation scripts. For web work run, from `apps/web`,
`npm run check`, `npm run lint`, `npm test -- --run`, and `npm run build`.
Record only the commands actually run and their results in the commit/PR; do
not copy old green counts into this file.
