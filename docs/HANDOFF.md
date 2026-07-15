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

## Current product state — 2026-07-15

- The connector write reference (backlog item 5) has landed:
  `GithubConnectorService.create_comment()` is a governed GitHub issue comment
  POST through the same gate + decision mode + credential + egress path as the
  existing `read()` method. The `post_json_url()` sandbox helper supports
  governed POST-with-response-body for connector writes. 14 new tests.
- Conversation organisation has landed its third slice: nested projects/folders.
  Arbitrary-depth folder nesting via hybrid adjacency list (`parent_id`) +
  materialized path (`path`) on the `projects` table. Paths are self-inclusive
  (`/root/child/`), so move/archive operations address exactly one subtree,
  never siblings. Two deletion modes:
  **archive** (AI-autonomous, soft — archives entire subtree) and **delete**
  (human-only, hard with orphanage cascade — descendants reparented to NULL,
  archived, path prefixed with `/orphaned/`). Context inheritance: ancestor
  contexts merge into a session's project context (instructions concatenate
  root→leaf, attachments union, nearest explicit `memory_mode` wins).
  `memory_mode` is `inherit`, `enabled`, or `disabled`; old Boolean clients
  remain compatible. Path
  management is done in Python (not a DB trigger) for reliability. API:
  `GET /api/projects/tree`, `PUT /api/projects/{id}/move` (human-only),
  `PUT /api/projects/{id}/archive` (any authenticated principal),
  `POST /api/projects` accepts `parent_id` for nested creation,
  `DELETE /api/projects/{id}` always requires `confirm=True`. Web:
  `ProjectTreeNode.svelte` recursive component, `ProjectsView` tree section
  with archive/move/delete actions. `ProjectView` includes `parent_id`,
  `path`, `is_archived`, `archived_at`. Tests: `tests/test_nested_projects.py`
  (18), `tests/test_projects.py` (+4 API), `test_api_contract_schemas.py`
  guards `ProjectView` nesting fields. Project-only export has landed; its
  bounded scope is recorded below.
- Reliable memory controls are complete for the current backlog item 3 slice: a
  user-visible Memory view over the EXISTING governed memory store — list
  with provenance, scope, sensitivity, confidence, retention; edit; pin/bookmark;
  forget through the governed path (human-only); per-memory search participation;
  expiry set/clear; import/export; and an incognito opt-out boundary that
  withholds approved project memory from the turn context when on (the memory is
  not deleted). No second memory system is created.
- Hybrid-memory lifecycle now adds reversible archive/restore for governed
  durable memories. Archived records remain preserved but are excluded from
  normal list, exact lookup, and keyword retrieval; forget remains the separate
  human-only tombstone action. The human-only control/API is
  `PUT /api/memory/{memory_id}/archive` with `{ "archived": true|false }`.
- Eidetic observations now persist only provenance metadata, retention class,
  artifact reference, and a SHA-256 checksum of the observed content. Raw
  payload capture and automatic promotion remain deliberately disabled.
- Memory purge is human-only and requires `X-Memory-Purge-Confirm` to exactly
  match the memory ID. It removes the live Markdown/SQLite record and records a
  disposition; retained backups are explicitly disclosed rather than claimed
  erased.
- The hybrid-memory delivery plan is complete for local SQLite: active-only
  FTS, source-versioned `fts`/`vector`/`graph` projection mappings, lifecycle
  fan-out, owner-started reconciliation (`POST /api/memory/reconcile`),
  review-only gist candidates, and explicit owner-confirmed eidetic expiry
  cleanup. Vector/graph creation remains capability-gated; no autonomous raw
  capture, cleanup worker, or model purge authority was introduced.
- Post-handoff memory hardening has shipped: retrieval eligibility excludes
  disabled, expired, future-dated, and superseded memories before FTS, vector,
  graph, or runtime ranking. Vector/hybrid results expose provenance, scope,
  sensitivity, confidence, retention, an untrusted-data label, and score
  contributions. Recall, import/export, backup catalog operations, and backup
  legal-hold changes are lifecycle-audited; the Memory control response exposes
  source, creator, validity, supersession, and remembered-reason metadata,
  including search-disabled records so users can re-enable them. Integrity
  scans now detect checksum mismatches, orphaned artifacts, project-path
  inconsistencies, and failed purge locations; the evaluation corpus covers
  scoped, sensitive, archived, forgotten, corrected, and time-qualified
  records with token and retrieved-storage regression budgets. SQLCipher
  migration also verifies conversion cleanup and encrypted-database access.
- Still pending for production memory: a representative consented benchmark
  and live quality/latency/cost thresholds; provider-backed runtime retrieval,
  entity extraction/review, and runtime hybrid integration; principal/workspace
  isolation and managed per-workspace key lifecycle; real encrypted backup and
  restore/erasure drills; monitoring, daemon/worker operation, load/soak/chaos
  evidence; and independent security, privacy, and pilot/benchmark evidence.
- The next memory program is staged in `HYBRID_MEMORY_IMPLEMENTATION_PLAN.md`
  (Stages F–J): retrieval-authority/evaluation, gated semantic + entity
  retrieval, tenancy/encryption/backup operations, reliability/scale, then
  independent benchmark evidence. Do not market the current implementation as
  “best”; that claim requires the Stage J evidence.
- The roadmap explicitly covers the full production checklist: FTS/vector/graph
  retrieval with filtering before ranking; precision/recall/latency/cost;
  corrections and temporal/supersession states; per-workspace encrypted data
  keys; legal holds and verified/pending backup erasure; rate-limited,
  idempotent jobs; recovery/rollback/integrity/load/chaos evidence; and
  human controls, review queues, and evidence-preserving consolidation.
- Stage F has begun: `RAIKER-2009` makes SQLite + active-only FTS authoritative
  for governed memory retrieval and keeps corrections/search opt-outs/expiry
  synchronized. `raiker.memory.evaluation` provides the initial
  `memory-eval-v1` lexical quality/safety harness; it is not yet a persisted
  benchmark service or an external comparison.
- `RAIKER-2010` extends Stage F with temporal correction: a human correction
  creates a replacement memory, preserves the old fact as superseded evidence,
  and removes it from active retrieval. Aggregate evaluation runs are persisted
  locally; corpus fixtures and regression thresholds remain outstanding.
- `memory-eval-v1` now includes deterministic scope, archive, and supersession
  fixtures with a CI precision/recall/zero-leak regression check. It is still a
  small local corpus, not the representative benchmark required by Stage J.
- Stage G/I early slices are implemented but not complete: governed durable
  memory can project to local vectors; entity relationships require active
  evidence; hybrid retrieval deduplicates active lexical/vector/graph results;
  and an owner-started integrity report finds stale indexes/projections/edges.
  Stage H's backup catalog records retention, legal hold, restore verification,
  and erasure disposition. SQLCipher now encrypts the SQLite database, FTS4,
  vectors, and graph rows using a workspace-derived key; tenant isolation,
  telemetry, and operational proof remain required.
- The first maintenance-job primitive is now present: idempotent `reconcile`
  and `integrity_scan` jobs have SQLite leases, retries, and dead-letter state,
  per-workspace rate limits, and lifecycle audit rows, but no daemon, telemetry,
  or load/chaos proof exists yet.
- SQLCipher is provided by `pysqlcipher3static` (imported as `pysqlcipher3`).
  The bundled build lacks FTS5, so Raiker uses encrypted FTS4 and deterministic
  recency ordering. Legacy plaintext databases are converted once and the
  transient plaintext source is removed after success.
- The phased contract for the remaining archive-first eidetic-memory work is
  [HYBRID_MEMORY_IMPLEMENTATION_PLAN.md](HYBRID_MEMORY_IMPLEMENTATION_PLAN.md).
  It keeps SQLite authoritative, separates project hierarchy from entity graph,
  and requires human-confirmed multi-store purge rather than a model delete tool.
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
  tag-substring filter. Project-only export has landed; its bounded scope is
  recorded below.
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
  surface are implemented. GitHub issue-comment creation is the one shipped,
  governed connector write reference; other connector write operations remain
  unimplemented and fail closed.
- Plugin code has two real, governed runtimes: bounded subprocess and a
  no-network/read-only container. Host in-process import of plugin code is an
  explicit security non-goal, not a deferred implementation task.
- The sandbox image has a governed, pull-only acquisition capability. It accepts
  only an exact owner-allowlisted image/registry, invokes only `docker pull`,
  and never builds or runs an image.
- Project-only export has landed as an authenticated, human-initiated download
  of the existing redacted JSONL audit timeline. It includes exactly the
  project's direct sessions, never descendant-project sessions, and applies
  the same account visibility as project sessions, including legacy unowned
  sessions. Each export is capped at the 10,000 most recent matching events;
  one bounded event-index snapshot supplies both its manifest and JSONL rows.
  The download response exposes no filesystem path. Attachments, project
  memory, and reminder scheduling are excluded.
- Tasks can persist schedules and recurrence, but reminder delivery is on-demand
  (no daemon). `ScheduledRoutinesExecutor` is a real registered executor that
  runs governed subagent work on demand (`raiker/runtime/executors/scheduled.py`);
  it is not stored-only as previously claimed — the earlier claim was stale.
- Real reminders have landed their first governed slice: `ReminderRuntimeExecutor`
  now supports `deliver_due`, `pause`, `cancel`, and `retry` operations through the
  existing governed path. The `reminders` table has `delivery_status`, `retry_count`,
  `max_retries`, and `delivered_at` columns. `deliver_due` is on-demand (no daemon).
  Caveat: `_deliver_due` never produces a failure path (hard-codes success), so
  retry machinery is structural-only; `max_retries` is validated but not persisted.
  5 new event types, 7 new tests.
- Agent identity and least privilege has landed its first slice (backlog item 7):
  `/principal create <type> <id> [--display-name <name>] [--role <role_id>]...
  [--scope <domain_scope>]... [--expires <iso_datetime>]` creates non-human
  principals (ai_agent, automation, system) through the governed admin-mutation
  path. Bootstrap-owner now enables admin_mutation/role_mutation/policy_mutation
  capability gates so the owner can manage principals immediately. 4 new tests.
  Missing: scoped credentials, per-tool grants, user-facing access review (see
  code-verified audit below).

## Asset status

`raiker-hero*.png`, `raiker-mark*.png`, PWA icons, and favicons are RGBA files
with transparent pixels. The web CSS uses them as direct transparent background
images. Their public URLs now include a deployment version query, so existing
clients fetch the transparent files instead of retaining an old opaque copy.

## Code-verified backlog audit — 2026-07-14

Each backlog item was verified against the actual codebase (not docs). Gaps and
contradictions are recorded honestly. File:line citations are in
`docs/IMPLEMENTATION_STATUS.md`.

1. **Project context** — ✅ CURRENT SLICE COMPLETE
   - ✅ Project instructions, shared attachments, opt-in project-memory boundary
     all wired into the live context gatherer
     (`raiker/context/gatherer.py:126-165`).
   - ✅ Incognito override enforced at runtime
     (`raiker/context/gatherer.py:152-157`).
   - ✅ Chats move in/out through human-only `PUT /api/sessions/{id}/project`;
     the stored project scope changes the next turn's bounded context and emits
     `session_project_changed`.
   - ✅ Tasks/schedules persist nullable `project_id`, stamp the selected active
     project by default, and list filtering keeps project task views scoped.
   - ✅ The live gatherer uses `load_effective_project_context`, merging active
     ancestors root→leaf exactly once.

2. **Conversation organisation** — ✅ CURRENT SLICE COMPLETE
   - ✅ Nested projects/folders, tags, pin/bookmark, project-only export, search
     with transcript hydration — all implemented with schema, storage, service,
     API, and web.
   - ✅ Bulk delete is one human-only `DELETE /api/sessions/bulk` request. It
     validates every selected visible session before one transactional cascade,
     so invalid or unauthorized selections delete none.

3. **Reliable memory controls** — ✅ CURRENT SLICE COMPLETE
   - ✅ List, pin, delete (governed), scope filter, provenance display, incognito
     boundary, store reuse.
   - ✅ Edit, expiry set/clear, import/export, and per-memory
     search-participation controls are wired through store, service, API, web UI,
     and tests.

4. **Real reminders and routines** — ⚠️ FIRST SLICE + DOC CONTRADICTION
   - ✅ Create/list/deliver_due/pause/cancel/retry with `delivery_status`,
     `retry_count`, `max_retries`, `delivered_at` columns and governance gating.
   - ❌ **No real scheduler** — `deliver_due` is on-demand only (no daemon, no
     timer, no clock).
   - ⚠️ `_deliver_due` never produces a failure path (hard-codes `True` at
     `raiker/runtime/executors/reminders.py:123`), so retry machinery is
     structural-only. `max_retries` is validated but not persisted to the row
     (`raiker/storage/sqlite.py:2861-2880`).
   - ❌ **DOC CONTRADICTION:** HANDOFF.md says "scheduled-task automation remains
     stored-only" (`docs/HANDOFF.md:180`), but `ScheduledRoutinesExecutor` is a
     real, registered executor that runs governed subagent work on demand
     (`raiker/runtime/executors/scheduled.py:95-152`,
     `raiker/runtime/executors/__init__.py:131,211`). The claim is stale.

5. **Connector write reference** — ✅ CURRENT SLICE COMPLETE
   - ✅ Generic `connector_write` immutable-intent + approval + executor path IS
     wired end-to-end: broker creates intent
     (`raiker/tools/broker.py:485-500`), approval-resolve invokes
     `ConnectorInvoker.invoke`
     (`raiker/api/routes_approvals.py:120`,
     `raiker/runtime/connector_ecosystem.py:224-280`). Never executes on `ask`
     alone.
   - ✅ `GithubConnectorExecutor` dispatches only `create_comment` in addition
     to reads, reuses the existing approval/gate path, and returns metadata-only
     artifacts. Other operations still fail closed.

6. **Agent evaluation and observability** — ⚠️ BASELINE ONLY
   - ✅ `TurnTrace`/`PhaseSpan`/`ToolCallSpan`/`ModelCallSpan` with
     `build_turn_trace()` and `/trace` CLI
     (`raiker/trace/builder.py:103-281`).
   - ❌ **Missing (zero code): user feedback, $cost model, record/replay
     scenarios, outcome review, OpenTelemetry export, configurable trace-layer
     redaction.**

7. **Agent identity and least privilege** — ⚠️ FIRST SLICE
   - ✅ `/principal create` for ai_agent/automation/system through governed
     admin-mutation, with roles, domain scopes, and `expires_at`
     (`raiker/cli/commands.py:2659-2709`).
   - ❌ **Missing (zero code): short-lived scoped credentials (as an
     agent-identity feature), per-tool grants, user-facing access review.**
     Authorisation is by role + global capability gate, not per-principal
     per-tool grants.

## Prioritised product backlog

Validate each item against the current codebase before starting it. Build one
governed vertical slice at a time.

1. **Project context:** project instructions, shared attachments, and an
   opt-in project-memory boundary. Chats moved into a project must inherit that
   bounded context; moving out must remove it. Project schedules remain
   project-scoped. The complete slice is now wired through storage, service,
   API, web, and the live gatherer (see code-verified audit above).
2. **Conversation organisation:** nested projects/folders, tags, pin/bookmark,
   bulk delete, and project-only export have landed. Search exists and
   hydrates persisted transcripts on reopen.
3. **Reliable memory controls:** user-visible memory list with edit, pin,
   delete, scope, provenance, expiry, import/export, and search-participation
   controls. Include a separate opt-out/incognito boundary. Reuse the governed
   memory store; do not create a second memory system.
 4. **Real reminders and routines:** an opt-in local scheduler that executes
     only an approved, bounded reminder/action, with delivery status, retries,
     pause, and cancellation. First slice landed: `deliver_due`, `pause`,
     `cancel`, `retry` on `ReminderRuntimeExecutor` with delivery status
     tracking. No daemon — `deliver_due` is on-demand. `ScheduledRoutinesExecutor`
     is a real registered executor that runs governed subagent work on demand
     (not stored-only as previously claimed — corrected above).
 5. **Connector write reference:** one narrow, real service write (for example,
    GitHub issue comment) through immutable intent + approval + an actual
    executor. Never make a write action execute on `ask` alone. Generic
    `connector_write` path is wired end-to-end; `GithubConnectorExecutor`
    dispatches `GithubConnectorService.create_comment()` through the same
    approval path. Other connector write operations remain fail closed.
6. **Agent evaluation and observability:** trace a goal/plan/tool/approval
   chain with latency, cost, outcome, and user feedback; add record/replayable
   regression scenarios, outcome review, and an OpenTelemetry-compatible export
   with configurable prompt/content redaction before making autonomy broader.
7. **Agent identity and least privilege:** distinct agent/service identities,
   short-lived scoped credentials, per-tool grants, and a user-facing access
   review. Existing principal and approval controls are a base, not a complete
   agent-identity surface. First slice landed: `/principal create` for
   non-human principals through the governed admin-mutation path.
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

## Next implementation slice — requires design approval

Agent identity and least privilege (backlog item 7) has landed its first slice:
`/principal create` for non-human principals through the governed admin-mutation
path, with bootstrap-owner enabling the admin mutation capability gates. Remaining
work for item 7: short-lived scoped credentials, per-tool grants, and a
user-facing access review surface.

The code-verified audit above shows that remaining gaps from items 1-7 are now
concentrated in:
- Item 4: local scheduler daemon, real delivery failure/retry behavior, persisted
  `max_retries`, and stale reminder docs.
- Item 6: user feedback, cost model, record/replay, OTel export, trace redaction.
- Item 7: scoped credentials, per-tool grants, access review.

Pick one gap and build one governed vertical slice at a time.

## Verification and handoff

For a backend slice, run focused tests first, then `pytest`, `ruff check .`,
and the relevant validation scripts. For web work run, from `apps/web`,
`npm run check`, `npm run lint`, `npm test -- --run`, and `npm run build`.
Record only the commands actually run and their results in the commit/PR; do
not copy old green counts into this file.
