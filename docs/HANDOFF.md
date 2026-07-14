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
   bounded context; moving out must remove it. Project schedules must remain
   project-scoped. This is the clearest assistant workflow gap.
2. **Conversation organisation:** nested projects/folders, tags, pin/bookmark,
   bulk move/delete/export, and project-only export. Search exists; these do
   not.
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
