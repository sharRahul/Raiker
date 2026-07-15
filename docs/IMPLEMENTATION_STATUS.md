> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

# Implementation Status

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

> Current truth update (2026-07-13): The local-owner workstream now includes a
> principal-scoped Inbox task-create route and Tasks UI. `priority`,
> `scheduled_at`, `recurrence`, and `reminder_at` persist on tasks; scheduling is
> stored planning metadata only and never starts work or sends a reminder. The
> connector gallery is implemented as the governed Connector Store UI. The web
> test setup also handles Node 25's invalid empty localStorage-file stub without
> changing browser runtime behavior. Web check/lint/test/build, ruff, mypy, and
> all repository truthfulness/readiness validators are green.

> Current truth update (2026-07-04): Phase 4 slice 8 promotes `plugin_install`
> to a real governed executor for local manifest validation and install-record
> creation only. Phase 4 slice 9 promotes `plugin_execution_cap` only for
> installed-plugin brokered read-only tool invocation through ToolBroker and
> PolicyEngine. Phase 4 slice 10 promotes `plugin_revocation_cap` as the
> fail-closed off-switch: a human owner revokes an installed plugin (status
> `installed` → `revoked`) so `plugin_execution_cap` then fails closed with
> `plugin_revoked` before any broker call. Phase 4 slice 11 adds install-time
> dependency controls: the governed `plugin_install` path fails closed on any
> declared dependency that is not an exact pin or not on the owner allowlist
> `RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST` (empty = fail closed), and never downloads
> or resolves dependencies. Phase 4 slice 12 adds plugin manifest signature
> verification: when the owner sets `RAIKER_PLUGIN_SIGNING_KEY`, the manifest
> `signature` must be a valid HMAC-SHA256 over the canonical manifest body or the
> governed install fails closed (`signature_invalid`); when unset, the presence
> marker remains for local dev. Phase 4 slice 13 adds asymmetric supply-chain
> signing: when the owner sets `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` (hex), the
> manifest `supply_chain.ed25519_signature` must be a valid Ed25519 signature over
> the same canonical body verified against that owner-trusted public key or the
> governed install fails closed (`asymmetric_signature_invalid` and peers;
> `asymmetric_backend_unavailable` never fails open); unset skips the check so
> existing manifests are unaffected. The HMAC (symmetric owner key) and Ed25519
> (asymmetric author-signed against an owner-trusted public key) checks are
> enforced independently. Phase 4 slice 14 promotes `plugin_runtime_cap`: the
> first capability that runs **arbitrary plugin code**, executing an installed
> plugin's declared entrypoint as a bounded subprocess (interpreter allowlist
> `python3`/`python`/`node`, workspace-scoped script, timeout + output caps,
> metadata-only artifacts). It fails closed unless the plugin has a non-revoked
> `installed` record **and** the owner names it in the allowlist
> `RAIKER_PLUGIN_RUNTIME_ALLOWLIST` (empty = fail closed) — the owner grant, not
> the manifest, authorizes code execution. Its isolation posture equals
> `shell_execution`/`process_execution`; in-process import isolation and a
> network-namespace jail remain deferred (the `container_execution_cap` path is
> the stronger-isolation option today). See
> `docs/threat-models/plugin-runtime.md`. Phase 4 slice 15 adds an optional
> per-plugin workspace subpath scope (`RAIKER_PLUGIN_RUNTIME_SCOPES`) so the owner
> grant to `plugin_runtime_cap` is not all-or-nothing
> (`entrypoint_outside_plugin_scope` / `plugin_scope_invalid`). Phase 4 slice 16
> adds `plugin_sandboxed_runtime_cap`: the network-isolated variant that runs the
> entrypoint inside an owner-allowlisted container
> (`RAIKER_PLUGIN_RUNTIME_IMAGE` in `container_image_allowlist()`) with
> `--network none`, a read-only rootfs, dropped capabilities, and only the single
> entrypoint file bind-mounted read-only — the workspace is never mounted. See
> `docs/threat-models/plugin-sandboxed-runtime.md`. In-process import isolation
> of plugin code in the host remains deferred. Where the older 2026-06-22
> paragraph below says "plugins" have no executor, read that as the not-yet-built
> import/in-process model; the per-capability source of truth is
> `docs/RUNTIME_EXECUTORS_SPEC.md`.

> Current truth update (2026-07-12): web-app task 5 adds **project folders** —
> a governance-neutral organizing scope. A `projects` table (id, name,
> `root_subpath`, created_at) plus a `project_id` column on `sessions`; the
> project root is derived server-side from the name (slug under `projects/`)
> and verified to stay inside the workspace (fail closed). A persisted active
> project (single-scope `active_project` row) stamps new sessions; checkpoints
> scope to a project through their session. API: `GET/POST /api/projects`,
> `PUT /api/projects/selection`, `GET /api/projects/{id}`, and `project_id`
> filters on `GET /api/sessions` / `GET /api/checkpoints` (Bearer-authenticated
> like every governed read; create/select are human gate-manager only). Web: a
> Projects view (create/list/set-active/detail) and a topbar active-project
> switcher; Sessions and Checkpoints filter by the active project. A project
> grants no capability — creating or selecting one changes no gate, mode, or
> policy. Tests: `tests/test_projects.py` (14) + `ProjectsView.test.ts` (5).

> Current truth update (2026-07-14): real reminders have landed their first
> governed slice (backlog item 4) — `ReminderRuntimeExecutor` now supports
> `deliver_due`, `pause`, `cancel`, and `retry` operations through the existing
> governance path. The `reminders` table has `delivery_status`, `retry_count`,
> `max_retries`, and `delivered_at` columns. `deliver_due` is on-demand (no
> daemon), matching the `scheduled_routines` pattern. 5 new event types
> (`reminder_delivered`, `reminder_paused`, `reminder_cancelled`,
> `reminder_retried`). 7 new tests. The stored-only reminder metadata from
> earlier work is now genuinely actionable.
>
> **Correction (2026-07-14):** the earlier claim "Scheduled-task automation
> remains stored-only" is stale and contradicted by code.
> `ScheduledRoutinesExecutor` is a real, registered executor
> (`raiker/runtime/executors/scheduled.py:33-158`,
> `raiker/runtime/executors/__init__.py:131,211`) that runs governed subagent
> work on demand (no daemon, but real execution when `run_due`/`run` is
> invoked). The "never runs work" claim was incorrect.
>
> **Caveats (2026-07-14):** `_deliver_due` never produces a failure path
> (hard-codes `True` at `raiker/runtime/executors/reminders.py:123`), so retry
> machinery is structural-only. `max_retries` is validated by `_create` but
> not persisted to the row (`raiker/storage/sqlite.py:2861-2880` — the column
> defaults to 3 at the DB level). `_retry` resets a `delivered` reminder to
> `active` (re-queue semantic), not a failed-delivery retry.
>
> Tests: `tests/test_phase_6_reminder_runtime.py` (+7). Validators:
> ruff, mypy, pytest (1687) all green.
>
> Current truth update (2026-07-15): the hybrid-memory implementation plan is
> complete for the local SQLite deployment. It now has active-only SQLite FTS,
> source-versioned lifecycle mappings for `fts`/`vector`/`graph` projections,
> owner-started reconciliation, review-only gist records, and exact-ID
> owner-confirmed eidetic cleanup. Archive, restore, forget, and purge update
> retrieval eligibility; purge records completed local locations and retained
> backup disposition. Vector/graph writes remain existing capability-gated
> adapters—there is no autonomous raw capture, cleanup worker, or model purge
> tool.

> Current truth update (2026-07-15): reliable memory controls are complete for
> the current backlog item 3 slice — a user-visible Memory view over the
> EXISTING governed memory store. No second memory system is created.
> `DashboardService` exposes list, edit, pin, governed forget, per-memory search
> participation, expiry set/clear, import/export, settings, and incognito. API:
> `GET /api/memory`, `PUT /api/memory/{id}`,
> `PUT /api/memory/{id}/pin`, `PUT /api/memory/{id}/search`,
> `PUT /api/memory/{id}/expiry`, `DELETE /api/memory/{id}`,
> `GET /api/memory/export`, `POST /api/memory/import`,
> `GET /api/memory/settings`, `PUT /api/memory/incognito`. Storage:
> `memory_pins` (organizing label, grants nothing) + `memory_settings`
> (single-row incognito flag) tables. The context gatherer reads the
> incognito flag and, when it is on, withholds approved project memory from
> the turn context (the memory is not deleted — only excluded from the
> model's view). Web: `MemoryView` now supports list/edit/pin/forget/search
> toggle/expiry/import/export/incognito. Tests: `tests/test_memory_controls.py`,
> `tests/test_api_contract_schemas.py`, `MemoryView.test.ts`. This is a controls slice — no new capability,
> gate, policy, or executor is added.

> Current truth update (2026-07-15): archive-first durable-memory lifecycle
> has landed. Migration `RAIKER-2003-memory-archive-lifecycle` adds
> `approved_memory.archived_at`; the existing Markdown record carries the same
> metadata. `set_memory_archived` preserves text and provenance while excluding
> archived memories from list, exact lookup, and keyword retrieval. Restore is
> the same human-only control path with `archived=false`; forget remains a
> tombstone, not an archive. API: `PUT /api/memory/{id}/archive`. Tests cover
> archive exclusion and restore in `test_phase_4_memory_mvp.py` and
> `test_memory_controls.py`.

> Current truth update (2026-07-15): `RAIKER-2004-eidetic-observations`
> provides the first high-fidelity observation foundation. `record_observation`
> writes source event/session, human-readable summary, retention, optional
> artifact reference, and a SHA-256 content checksum to SQLite; it does not
> persist raw payloads or enable automatic promotion. `obs_` is a registered
> contract ID prefix. Test: `tests/test_eidetic_observations.py`.

> Current truth update (2026-07-15): the human-only purge path is implemented
> as `DELETE /api/memory/{id}/purge` and requires
> `X-Memory-Purge-Confirm: <id>`. It deletes live Markdown/SQLite memory,
> writes a `memory_purge_records` disposition audit row, and reports retained
> backups as pending disposition. No agent purge tool exists. Test:
> `test_purge_requires_exact_confirmation`.
>
> Tool policy defect fix (2026-07-14): `connector_read` and
> `connector_write` were denied by the policy engine
> (`unknown_or_denied_tool`) despite being advertised to the model and
> having a real executor / intent handling in the broker — so the governed
> connector tools silently failed. `connector_read` is now routed as
> read-shaped (governed inside the tool, like `github_read`); 
> `connector_write` is now routed to the approval path whose immutable
> intent + execution the broker already owned. Tests:
> `tests/test_connector_tool_policy.py` (3). UX: the chat surface opens
> its governed timeline while a turn streams (not a black box).

> Current truth update (2026-07-14): conversation organisation has landed its
> first slice — per-session pin/bookmark and single + bulk delete. The
> `sessions` table gained a `pinned` column (organizing label only, default 0;
> like `projects`, it grants nothing and changes no gate, policy, or
> authority). `DashboardService.set_session_pinned` /
> `delete_session` are human-only and resolve the acting principal through
> the existing `RuntimeControlService`; they reuse the same
> user/session visibility boundary as `list_sessions` (an account cannot pin
> or delete another account's session; legacy unattributed sessions remain
> visible/deletable by any authenticated human). `delete_session` cascades
> turns, events_index, tool_actions, policy_decisions, checkpoints, tasks,
> and removes the per-session events JSONL transcript file so it is not
> orphaned (mirrors `delete_project`'s cascade scope). API:
> `PUT /api/sessions/{id}/pin` and `DELETE /api/sessions/{id}` (the latter
> requires `X-Session-Delete-Confirm: <id>` like project deletion). Web:
> `SessionsView` surfaces pinned sessions first, offers a per-row pin toggle,
> multi-select checkboxes, and a bulk-delete bar. Tests:
> `tests/test_session_organisation.py` (13), `SessionsView.test.ts` (4), and
> `tests/test_api_contract_schemas.py` now guards `pinned` on `SessionSummary`.
> This is an organizing slice — no new capability, gate, policy, or executor.
>
> Conversation organisation remainder (2026-07-14): per-session tags have
> landed. A `session_tags` table (session_id, tag, created_at; FK ON DELETE
> CASCADE; index on tag) holds a many-to-many organizing label set — like
> the `pinned` column and the `projects` table, it grants nothing and
> changes no gate, policy, or authority. `DashboardService.set_session_tags`
> is human-only, normalizes input (trim, collapse whitespace, lowercase,
> dedupe, `[a-z0-9][a-z0-9 &._-]*`, 1..32 chars each, max 12 tags), and
> reuses the same user/session visibility boundary as `set_session_pinned`
> (an account cannot retag another account's session). Full-replace semantics
> (empty list clears the set). `delete_session` and `delete_project` cascade
> `session_tags` so rows are never orphaned (FK cascade is the belt; the
> explicit cascade is the suspenders). `SessionView` carries `tags`; the
> storage layer returns them sorted alphabetically. API:
> `PUT /api/sessions/{id}/tags` (422 on invalid input, 403 on unknown/not-
> owned session, 200 on success). Web: `SessionsView` renders tag chips
> with per-chip × remove, an inline add-tag input + button per row, and a
> tag-substring filter input in the head row. Tests:
> `tests/test_session_organisation.py` (+7: round-trip, unknown session,
> AI principal denied, invalid tags rejected, tags cleared on delete, API
> round-trip, isolation), `SessionsView.test.ts` (+4: chip render, add,
> remove, filter), `tests/test_api_contract_schemas.py` now guards `tags`
> on `SessionSummary`. Nested projects/folders and project-only export are
> recorded in the current-truth updates below.

> Current truth update (2026-07-14): chat search now hydrates the persisted
> transcript when a result is reopened. `ChatView` calls the existing governed
> `GET /api/sessions/{id}` read on mount when a `session` query param is
> present and renders each persisted turn (prompt + the agent's response
> message from `turn.summary` + status) so the user can continue the same
> session — no new session is created merely to view history. The live
> per-event timeline is not replayed for restored turns; new turns stream as
> usual. The backend read is Bearer-authenticated and enforces the same
> user/session visibility boundary as every governed read (an account cannot
> read another account's session; legacy unattributed sessions remain
> visible). No new capability, gate, policy, or executor is added. Tests:
> `ChatView.test.ts` (+2).

> Current truth update (2026-07-14): nested projects/folders have landed
> (conversation organisation remainder, third slice). Arbitrary-depth folder
> nesting via hybrid adjacency list (`parent_id` FK, `ON DELETE SET NULL`)
> + materialized path (`path`, e.g. `/p1/p4/p12/`) on the `projects` table.
> Migration `RAIKER-1012-projects-nesting` adds `parent_id`, `path`,
> `is_archived`, `archived_at` columns + three indexes. Path management is
> done in Python (not a DB trigger) for reliability — the trigger approach
> caused `NOT NULL` constraint failures when explicit Python path updates
> ran alongside trigger logic. Two deletion modes: **archive**
> (AI-autonomous — any authenticated principal may soft-archive a subtree;
> idempotent) and **delete** (human-only, always requires `confirm=True`;
> hard-deletes target, orphans + archives descendants with
> `path='orphaned/<id>/'`). `delete_project_with_orphanage` cleans up
> sessions for the target project (FK: `ON DELETE NO ACTION`) and clears
> `active_project` if referencing the target. Context inheritance:
> `DashboardService.get_session_context` merges ancestor contexts into the
> session's project context — instructions concatenate root→leaf, attachment
> IDs union, leaf's `memory_enabled` wins. `create_project` accepts
> `parent_id` for nested creation. Storage methods: `create_project`
> (with `parent_id` + path computation), `list_project_tree`,
> `move_project` (cycle check + REPLACE-based descendant path update),
> `archive_project`, `delete_project_with_orphanage`, `get_ancestor_contexts`.
> API: `GET /api/projects/tree`, `PUT /api/projects/{id}/move` (human-only),
> `PUT /api/projects/{id}/archive` (any authenticated), `POST /api/projects`
> accepts `parent_id`, `DELETE /api/projects/{id}` always requires
> `X-Project-Delete-Confirm` header. `MoveProjectRequest` schema with
> `extra="forbid"`. Web: `ProjectTreeNode` type + `ProjectTreeNode.svelte`
> recursive Svelte 5 component, `projectTree`/`moveProject`/`archiveProject`
> API client, `ProjectsView` tree section with archive/move/delete actions.

> **Correction (2026-07-15):** materialized paths now include every node's
> own ID (`/p1/p4/p12/`), not only its ancestors. The prior representation
> could make a move or archive of one sibling affect all folders sharing that
> parent path. Migration `RAIKER-1014-project-self-inclusive-path` backfills
> legacy paths from `parent_id`; `RAIKER-1013-project-memory-inheritance` adds
> tri-state `project_contexts.memory_mode` (`inherit|enabled|disabled`), while
> retaining compatibility with the legacy Boolean `memory_enabled`. Effective
> project context now uses the nearest explicit mode from active ancestors;
> instructions still merge root→leaf and attachments still union. Storage path
> changes occur transactionally and use the self-inclusive prefix. Regression
> tests prove sibling isolation and nearest-ancestor inheritance in
> `tests/test_nested_projects.py`.
> `ProjectView` (Python DTO + TS interface) includes `parent_id`, `path`,
> `is_archived`, `archived_at`. Tests: `tests/test_nested_projects.py` (20:
> migration, tree queries, move + cycle, archive + idempotent, delete +
> orphanage, ancestor contexts, service AI-autonomous archive, human-only
> move/delete, context merge), `tests/test_projects.py` (+4 API: tree list,
> move happy path, move 422, archive happy path),
> `tests/test_api_contract_schemas.py` guards `PROJECT_VIEW` and
> `PROJECTS_LIST`. This is an organizing slice — no new capability, gate,
> policy, or executor is added. The subsequent project-only export is
> recorded below.
> Validators: ruff, mypy, pytest (49 focused), tsc, vitest (129) all green.

> Current truth update (2026-07-14): project folders now have a bounded,
> explicit context record: project instructions, validated references to
> uploaded attachments, and opt-in approved memory scoped as
> `project:<project_id>`. Context is resolved from the chat's stored project,
> not merely the currently selected project, so chats outside that project do
> not inherit it. The Projects detail view can edit instructions and the memory
> switch; authenticated `PUT /api/projects/{id}/context` validates attachment
> IDs and limits before persisting. This remains a context boundary, not an
> authority grant. `tests/test_projects.py` covers API round-trip and
> project-only context inclusion.
>
> Current truth update (2026-07-14): project-only export has landed as an
> authenticated, human-initiated download of the existing redacted JSONL audit
> timeline. It exports exactly sessions directly assigned to the selected
> project, never sessions in descendant projects. Account visibility mirrors
> project-session visibility, including legacy unowned sessions. The download
> is capped at the 10,000 most recent matching events, with one bounded
> event-index snapshot supplying both its manifest and JSONL rows. The response
> exposes no filesystem path. Attachments, project memory, and reminder
> scheduling are excluded from this slice. Real reminders have since landed
> their first governed slice (see update above).

> Current truth update (2026-07-14): the connector write reference has landed
> (backlog item 5) — `GithubConnectorService.create_comment()` posts one
> governed GitHub issue comment through the same gate + decision mode +
> credential + egress path as `read()`. The `post_json_url()` sandbox helper
> supports governed POST-with-response-body for connector writes. The generic
> `connector_write` tool (intent + approval + `ConnectorInvoker.invoke()`)
> remains the model-initiated write path; `create_comment()` is the hardcoded
> reference demonstrating how a specific write operation is implemented with
> full governance. Tests: `test_github_connector.py` (+14 for write governance
> and success), `tests/test_connector_ecosystem.py` has an existing API-level
> write lifecycle test. Validators: ruff, mypy, pytest (1697) all green.
>
> **Correction (2026-07-14):** `GithubConnectorService.create_comment()` exists
> with full governance and 14 unit tests (`raiker/runtime/connectors.py:211-312`)
> but is **NOT dispatched by any runtime path.** `GithubConnectorExecutor`
> rejects all non-`read` operations (`raiker/runtime/executors/connectors.py:42-47`).
> No executor dispatch, API route, or CLI command calls `create_comment()`. A
> model turn cannot post a GitHub comment through it today. The generic
> `connector_write` immutable-intent + approval + executor path IS wired
> end-to-end (`raiker/tools/broker.py:485-500` →
> `raiker/api/routes_approvals.py:120` →
> `raiker/runtime/connector_ecosystem.py:224-280`).

> Current truth update (2026-07-14): agent identity and least privilege (backlog
> item 7) has landed its first slice: `/principal create <type> <id>` creates
> non-human principals (ai_agent, automation, system) through the governed
> admin-mutation path with optional roles, domain scopes, and expiry.
> Bootstrap-owner now enables admin_mutation/role_mutation/policy_mutation
> capability gates so the owner can manage principals immediately. `principal_create`
> added to policy allowed_read_actions. Tests: `test_phase_2_terminal_commands.py`
> (+4: requires owner, invalid type, success, no args), `test_runtime_authority.py`
> (updated admin mutation governance tests). Validators: ruff, mypy, pytest green.
>
> **Code-verified gaps for item 7:** scoped credentials, per-tool grants, and
> user-facing access review have zero code (greps return nothing). Authorisation
> is by role + global capability gate, not per-principal per-tool grants.
> `ConnectorVault` stores per-principal per-connector credentials with
> `expires_at` (`raiker/runtime/connector_ecosystem.py:86-108`) but this is the
> existing connector-credential vault, not an item-7 agent-identity slice.

> Current truth update (2026-07-14): agent evaluation and observability baseline
> (backlog item 6) has landed: `raiker/trace/` with `TurnTrace` / `PhaseSpan` /
> `ToolCallSpan` / `ModelCallSpan` dataclasses, `build_turn_trace()` that reads
> existing typed events and reconstructs the gather → plan → act → verify →
> respond chain with per-phase latency via `turn_state_changed` boundaries, and
> a `format_trace()` output. The `/trace <session_id> <turn_id>` CLI command
> surfaces the trace. Two-pass matching avoids non-deterministic event ordering
> when timestamps are identical. Tests: `test_trace.py` (9: empty, basic, no
> tools, model calls, failed, denied, wrong turn, format, empty format).
> Validators: ruff, mypy, pytest (1708) all green.
>
> **Code-verified gaps for item 6:** user feedback, $cost model, record/replay
> scenarios, outcome review, OpenTelemetry export, and configurable trace-layer
> redaction all have zero code (greps for `user_feedback`, `record_replay`,
> `replay_scenario`, `opentelemetry`, `otel`, `otlp`, `redact` in `raiker/trace/`
> return nothing). Token counts are captured on `ModelCallSpan` but no $/credit
> cost model exists.

---

## Code-verified backlog audit — 2026-07-14

Each backlog item (1-7) was verified against the actual codebase with
file:line citations. Gaps and doc contradictions are recorded honestly.

### Item 1 — Project context — ✅ CURRENT SLICE COMPLETE

- ✅ Project instructions: schema `project_contexts.instructions`
  (`raiker/storage/migrations.py:1136-1142`); load/save
  (`raiker/storage/sqlite.py:578,596`); service
  (`raiker/control/dashboard.py:912-945`); API `PUT /api/projects/{id}/context`
  (`raiker/api/routes_dashboard.py:330-349`); folded into turn bundle
  (`raiker/context/gatherer.py:158-160`).
- ✅ Shared attachments: `project_contexts.attachment_ids_json`; validated
  against governed attachment store (max 20,
  `raiker/control/dashboard.py:931-935`); folded into gatherer
  (`raiker/context/gatherer.py:126-141`).
- ✅ Opt-in project-memory boundary: per-project `memory_enabled`
  (`raiker/storage/migrations.py:1140`); global incognito override
  (`raiker/storage/migrations.py:1263-1267`,
  `raiker/control/dashboard.py:734-749`); enforced in gatherer
  (`raiker/context/gatherer.py:151-165`).
- ✅ **Chat move in/out:** human-only `PUT /api/sessions/{id}/project` calls
  `DashboardService.set_session_project`, applies the normal owner boundary,
  persists `sessions.project_id`, and emits `session_project_changed`.
- ✅ **Project-scoped schedules:** nullable `tasks.project_id` persists the
  explicit or active project, and the task API/UI filter by it.
- ✅ **Ancestor-context inheritance:** the live gatherer uses
  `load_effective_project_context`, which combines active ancestors root→leaf
  once while applying the nearest explicit `memory_mode` override.

### Item 2 — Conversation organisation — ✅ CURRENT SLICE COMPLETE

- ✅ Nested projects/folders: schema
  (`raiker/storage/migrations.py:1288-1304`); storage
  (`raiker/storage/sqlite.py:551-562,714-762,764-803`); service
  (`raiker/control/dashboard.py:828-865,951-979,887-910`); API
  (`raiker/api/routes_dashboard.py:235-253,276-282,370-398`); web
  (`apps/web/src/lib/components/ProjectTreeNode.svelte`,
  `apps/web/src/lib/views/ProjectsView.svelte:278-373`); tests
  (`tests/test_nested_projects.py` — 20).
- ✅ Tags: schema (`raiker/storage/migrations.py:1270-1286`); storage
  (`raiker/storage/sqlite.py:862-902`); service
  (`raiker/control/dashboard.py:599-652`); API
  (`raiker/api/routes_dashboard.py:152-180`); web
  (`apps/web/src/lib/views/SessionsView.svelte:192-315`); tests
  (`tests/test_session_organisation.py`).
- ✅ Pin/bookmark: storage (`raiker/storage/sqlite.py:484-488,832-851`);
  service (`raiker/control/dashboard.py:548-569`); API
  (`raiker/api/routes_dashboard.py:101-122`); web
  (`apps/web/src/lib/views/SessionsView.svelte:38-69,317-325`).
- ✅ **Bulk delete:** human-only `DELETE /api/sessions/bulk` validates all
  selected sessions against the normal visibility boundary before deleting every
  validated session through one SQLite transaction. The UI sends one request;
  an invalid or unauthorized ID leaves every selected session intact.
- ✅ Project-only export: service
  (`raiker/control/dashboard.py:810-826`); export engine
  (`raiker/events/export.py:154-228`); project filter is direct-assignment only
  (`raiker/storage/sqlite.py:1326-1329`); API
  (`raiker/api/routes_dashboard.py:299-327`); web
  (`apps/web/src/lib/api.ts:347-356`). Attachments, project memory, and
  reminder scheduling are excluded.
- ✅ Search + transcript hydration: backend
  (`raiker/storage/sqlite.py:674-689`,
  `raiker/control/dashboard.py:528-529`,
  `raiker/api/routes_dashboard.py:80-86`); web hydration
  (`apps/web/src/lib/views/ChatView.svelte:261-304`); live per-event timeline
  not replayed for restored turns.

### Item 3 — Reliable memory controls — ✅ CURRENT SLICE COMPLETE

- ✅ List/scope/provenance/pin/delete/incognito reuse the existing governed
  markdown memory store; no second memory system was added.
- ✅ Edit is wired through `PUT /api/memory/{id}`,
  `DashboardService.edit_memory_controlled`, and `raiker.memory.store.update_memory`.
- ✅ Expiry set/clear is wired through `PUT /api/memory/{id}/expiry` and the
  stored `expires_at` metadata; expired memories are hidden from list/search/get
  while still updateable for clearing expiry.
- ✅ Import/export is wired through `GET /api/memory/export` and
  `POST /api/memory/import`; imports write through the governed memory store.
- ✅ Search participation is wired through `PUT /api/memory/{id}/search` and the
  stored `search_enabled` metadata; `search_memory` skips disabled entries.
- ✅ Web UI exposes edit, pin, forget, include-in-search, expiry, import/export,
  and incognito controls in `MemoryView.svelte`.
- ✅ Contract and regression coverage: `tests/test_memory_controls.py`,
  `tests/test_api_contract_schemas.py`, and `MemoryView.test.ts`.

### Item 4 — Real reminders and routines — ⚠️ FIRST SLICE + DOC CONTRADICTION

- ✅ Create/list/deliver_due/pause/cancel/retry:
  `raiker/runtime/executors/reminders.py:20-188`; storage
  (`raiker/storage/sqlite.py:2861-2921`); schema
  (`raiker/storage/migrations.py:978-991` + ALTER TABLE at
  `raiker/storage/sqlite.py:451-459`); tests
  (`tests/test_phase_6_reminder_runtime.py` — 12).
- ✅ Delivery status: `delivery_status` column
  (`active`/`delivered`/`paused`/`cancelled`); `delivered_at` timestamp.
- ✅ Retries: `retry_count` + `max_retries` columns; `_retry` increments
  (`raiker/runtime/executors/reminders.py:160-178`).
- ✅ Governance gating + threat-model ack required; content redaction in
  artifacts (`tests/test_phase_6_reminder_runtime.py`).
- ❌ **No real scheduler:** `deliver_due` is on-demand only (no daemon, no
  timer, no clock). Docs admit this.
- ⚠️ **`_deliver_due` never fails** (`raiker/runtime/executors/reminders.py:123`
  hard-codes `True`), so retry machinery is structural-only.
- ⚠️ **`max_retries` not persisted** — validated by `_create` but not written to
  the row (`raiker/storage/sqlite.py:2861-2880`); defaults to 3 at DB level.
- ❌ **DOC CONTRADICTION:** "scheduled-task automation remains stored-only" is
  stale. `ScheduledRoutinesExecutor` is a real, registered executor
  (`raiker/runtime/executors/scheduled.py:33-158`,
  `raiker/runtime/executors/__init__.py:131,211`) that runs governed subagent
  work on demand.

### Item 5 — Connector write reference — ✅ CURRENT SLICE COMPLETE

- ✅ Generic `connector_write` immutable-intent + approval + executor path IS
  wired end-to-end:
  - Policy: `approval_required_actions` (`raiker/policy/config.py:67`);
    classification (`raiker/models/tool_call_validation.py:40`).
  - Broker intent: `connector_write_intents` table
    (`raiker/storage/migrations.py:1178-1193`); broker creates intent
    (`raiker/tools/broker.py:485-500`).
  - Approval-resolve executor: atomic claim + `ConnectorInvoker.invoke`
    (`raiker/api/routes_approvals.py:65-148`).
  - ConnectorInvoker: HTTPS + manifest + egress + vault + OAuth refresh
    (`raiker/runtime/connector_ecosystem.py:224-280`).
  - Never on `ask` alone: `connector_write` is in `approval_required_actions`
    and NOT in the route_action capability map
    (`raiker/runtime/authority/router.py:50-93`).
  - Tests: `tests/test_connector_ecosystem.py:89-189`.
- ✅ **`GithubConnectorService.create_comment()` runtime dispatch:**
  `GithubConnectorExecutor` accepts only `create_comment`, calls the governed
  service with its already-routed gate/mode decision, and exposes only repo,
  issue number, comment ID, and URL as artifacts. Unknown operations remain
  fail-closed. `tests/test_github_connector.py` covers the path.

### Item 6 — Agent evaluation and observability — ⚠️ BASELINE ONLY

- ✅ `TurnTrace`/`PhaseSpan`/`ToolCallSpan`/`ModelCallSpan`
  (`raiker/trace/models.py:6-46`); `build_turn_trace()`
  (`raiker/trace/builder.py:103-281`); `/trace` CLI
  (`raiker/cli/commands.py:2922-2939`); tests
  (`tests/test_trace.py` — 9).
- ✅ Per-phase latency (`duration_ms`); turn `total_duration_ms`; token counts
  on `ModelCallSpan`.
- ✅ Status/outcome: `completed`/`failed`/`denied`/`last:<event>`
  (`raiker/trace/builder.py:123-135`).
- ❌ **Missing (zero code):** user feedback, $cost model, record/replay
  scenarios, outcome review, OpenTelemetry export, configurable trace-layer
  redaction.

### Item 7 — Agent identity and least privilege — ⚠️ FIRST SLICE

- ✅ `/principal create <type> <id>` for ai_agent/automation/system through
  governed admin-mutation (`raiker/cli/commands.py:2659-2709`); dispatch
  (`raiker/cli/commands.py:2837-2838`); `PrincipalType` enum
  (`raiker/runtime/authority/models.py:8`).
- ✅ Roles, domain scopes, `expires_at` on principals
  (`raiker/storage/sqlite.py:2431-2456`); CLI `--expires`
  (`raiker/cli/commands.py:2685-2686`).
- ✅ Bootstrap-owner enables admin_mutation/role_mutation/policy_mutation
  capability gates (`raiker/cli/principal_resolver.py:162-172`).
- ✅ `principal_create` in policy `allowed_read_actions`
  (`raiker/policy/config.py:47`).
- ✅ Tests: `tests/test_phase_2_terminal_commands.py` (+4),
  `tests/test_runtime_authority.py` (updated).
- ❌ **Missing (zero code):** scoped credentials (as agent-identity feature;
  `ConnectorVault` expiry is unrelated), per-tool grants (authorisation is by
  role + global gate), user-facing access review (only `/principal <id>` and
  `/principals` exist — not an access-review surface).

> Current truth (2026-06-22): the launchable local UIs are the plain local terminal client and the local web dashboard (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only; read-only governed views + governed prompt/turn/approval/runtime-mutation flows where approval resolution is metadata-only; adds no authority of its own). Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST/API clients are Phase 8 deferred, specified but not implemented. Phase 3 is complete only for safe foundation/readiness slices A-P; Phase 4 memory MVP is implemented; Phase 5-7 remain metadata/readiness/contract surfaces unless code and tests explicitly prove runtime behavior. Real local executors exist and are governed-flippable for: Tier 1 (`approval_execution_relay`, `file_write_execution`, `patch_apply_execution`, `memory_write_execution`, `memory_forget_execution`), Tier 2 (`shell_execution`, `process_execution`, `web_fetch`, `network_execution` — sandboxed/egress-allowlisted), Tier 3 local code-intelligence (`graph_indexing_runtime`, `semantic_memory_runtime`, `vector_embedding_runtime` — a deterministic local hashing embedding with no model download / no network, persisting a `vector_records` row and supporting cosine `search`/retrieval over the stored local-model vectors (ids+scores, metadata-only) — and `model_provider_runtime` — a provider-backed **semantic** embedding, egress-gated: owner egress allowlist + hosted/private gate state + API-key-from-env, `embed` only), the Phase 4 promoted slices (`subagents`, `multi_agent_teams`, `external_channel_runtime`, `channel_approval_relay`, `container_execution_cap`, `scheduled_routines`), and — Phase 4 slice 7 — `hosted_model_runtime` / `private_network_model_runtime` (owner egress allowlist `RAIKER_MODEL_EGRESS_ALLOWLIST`, empty = fail closed; gate-derived provider policy on the chat path), and — web-app task 2 — `advisor_model_runtime` (a local model may consult one owner-picked advisor profile through the brokered `consult_advisor` tool; default-ask decision mode withholds, provider policy is re-checked per call, and the question/answer never enter audit payloads — see `docs/threat-models/advisor-model.md`), and — web-app task 4 — `connector_github_runtime` (a model may read one GitHub issue/PR through the brokered `github_read` tool; default-ask decision mode withholds, the owner credential is env-only `RAIKER_GITHUB_TOKEN`, the host must be on the owner connector egress allowlist `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` — empty = fail closed — the request URL is built server-side from validated components, the fetched body is returned as untrusted data and never enters audit payloads; reference slice for governed service connectors — see `docs/threat-models/connectors-github.md`), and — web-app task 4, second read connector — `connector_gmail_runtime` (a model may read one Gmail message/thread through the brokered `gmail_read` tool; identical governed pattern — default-ask decision mode withholds, the owner credential is env-only `RAIKER_GMAIL_TOKEN`, the host `gmail.googleapis.com` must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, the request URL is built server-side with `format=metadata`, the fetched snippet+headers are returned as untrusted data and never enter audit payloads — see `docs/threat-models/connectors-gmail.md`), and — web-app task 4, third + fourth read connectors — `connector_gcal_runtime` (Google Calendar event/calendar read via the brokered `gcal_read` tool; env-only `RAIKER_GCAL_TOKEN`, host `www.googleapis.com`, server-built path-encoded URL — see `docs/threat-models/connectors-gcal.md`) and `connector_slack_runtime` (Slack channel info/history read via the brokered `slack_read` tool; env-only `RAIKER_SLACK_TOKEN`, host `slack.com`, fixed Web API method with a validated channel id, `ok:false` treated as a bad response — see `docs/threat-models/connectors-slack.md`); all four connectors share the identical fail-closed governed pattern (gate + default-`ask` decision mode + owner egress allowlist + metadata-only audit; reads only). Every other capability — remote/cloud command execution and all still-fail-closed Tier-6 sensitive domains (finance/investment/medical/pregnancy/cctv/home-security/hardware) — has **no real executor and fails closed** (`not_implemented` / `activation_blocked:no_executor`); it cannot be flipped to a working state. Capability-gate default posture (updated): **integrated capabilities — those with a real executor — ship `enabled_runtime` by default**, while capabilities that are not integrated yet (no real executor) stay `disabled` and fail closed. Enabling a gate does not by itself let an AI act unattended: AI-proposed actions are still governed by the per-capability **decision mode (default `ask`)**, the critical-risk human-confirmation floor, PolicyEngine hard-denies, and executor-level env allowlists (model egress / plugin / container image), which are independent of the gate and remain fail-closed. Disabling any gate is owner/`runtime_gate_manager`-only, governed, reversible, and audited. Per-capability detail: [`docs/RUNTIME_EXECUTORS_SPEC.md`](RUNTIME_EXECUTORS_SPEC.md).


Security architecture status and deferred-control gates are summarized in [`docs/SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md).

This document is the implementation control ledger for Raiker. It converts the existing phase blueprint into a builder-proof status view so a local or cloud coding agent can tell what is specified, what is implemented, what is intentionally disabled, and what must not be built yet.

A feature marked as specified is not automatically implemented. A feature marked as phase-scheduled is not permission to invent behaviour in code. A feature may only be marked `implemented_verified` when the implementation maps to documented task IDs, required tests exist, and validation has passed for the current change set.

## Canonical Backend Capability Statuses

The backend foundation uses these current-status labels when the simpler phase ledger terms would be ambiguous:

- `implemented_read_only`
- `implemented_policy_gated`
- `implemented_approval_required`
- `metadata_only`
- `readiness_only`
- `dry_run_only`
- `contract_only`
- `disabled_deferred`
- `test_only`

Current high-signal truth:

- Approval resolution is `metadata_only`: `/approve` and `/deny` do not execute actions.
- Approval resolution is metadata-only.
- CLI durable memory mutation is `implemented_approval_required`: requests are brokered and approval-required by default.
- Governed durable memory writes are `implemented_policy_gated`: they require provenance, retention, approval_state, confidence, trust_score, and event logging on the governed path.
- Integrated real executors (including graph indexing, semantic/vector runtimes, plugin execution slices, channel runtime, container, scheduled routines, model-provider runtime, and local email/calendar/reminder stores) are `implemented_policy_gated`/governed per action; remote/cloud command execution and sensitive finance/investment/medical/pregnancy/CCTV/home-security/hardware domains remain `disabled_deferred` and fail closed.
- **Runtime Authority / Action Router** (`raiker/runtime/authority/`) is `implemented_policy_gated` — governs all mutation actions through capability gates, policy engine, risk classification, approval/risk acceptance, and event logging.
- **AI-executable role model** is `implemented_policy_gated` — defines `assistant`, `automation`, `operator`, `developer` roles with per-role permissions, denied capabilities, and self-approval/self-grant restrictions.
- **Human-only role protection** is `implemented_policy_gated` — `owner`, `admin`, `approver`, `security_admin`, `finance_approver`, `medical_decision_maker`, `runtime_gate_manager` cannot be assigned to AI principals.
- **Domain scopes** are `implemented_policy_gated` — 16 domain scopes enforced at the authority level.
- **Risk acceptance model** is `implemented_policy_gated` — risk acceptance records with required fields, expiry, one-time/reusable, and event logging.
- **Capability registry** is `implemented_policy_gated` — expanded to 50+ capabilities; integrated real-executor capabilities default `enabled_runtime`, while no-executor capabilities remain disabled/fail-closed.
- **Event redaction** is `implemented_policy_gated` — extended with bank/card/medical ID patterns.
- **Runtime enablement validator** is `implemented_verified` — `scripts/validate_runtime_enablement_readiness.py`.

### Enforcement status

- Runtime readiness decision: `runtime_enablement_candidate` — `controlled_runtime_mode_activation_implemented`.
- `production_ready_local_single_user_runtime`: `ready` — see validation evidence below.
- strict non-allow blocking: enforced — `_govern_admin_mutation` blocks on all non-allow decisions (`deny`, `needs_approval`, `needs_risk_acceptance`, `needs_human_confirmation`, `disabled_by_capability_gate`).
- role revoke governed: enforced — routes through `_govern_admin_mutation` / RuntimeAuthority before mutation.
- capability gate per action: enforced — `RuntimeAuthority.check_capability_gate()` checks the relevant gate for each governed action and returns `disabled_by_capability_gate` when the gate is disabled.
- risk acceptance enforcement: enforced — one-time risk acceptances are consumed (deleted) on use; expired, mismatched, or missing acceptances block execution; critical-risk always requires human confirmation.
- **Validator depth**: `scripts/validate_runtime_enablement_readiness.py` now detects direct store mutation patterns in CLI handlers without governance, and validates documentation markers across all 8 required docs.
- Approval resolution remains `metadata_only` — does not execute approved actions.
- No UI/API client implements RuntimeAuthority as the sole authority path (no UI/API clients exist yet).

### Controlled runtime mode activation

- **Controlled runtime mode activation**: `controlled_runtime_mode_activation_implemented` — RuntimeAuthority governs activation of runtime modes and capability gates through persisted state.
- **Runtime mode state persistence**: `runtime_mode_state` table stores the current runtime mode (`local_single_user_runtime`, `deferred_runtime`, etc.) and is read by RuntimeAuthority at startup.
- **Capability gate state persistence**: `capability_gate_state` table stores enabled/disabled state for all 53 capability gates; integrated real-executor gates default enabled and no-executor gates default disabled. Persisted state survives restarts.
- **RuntimeAuthority integration**: `RuntimeAuthority.check_runtime_mode()` and `RuntimeAuthority.enforce_capability_gate_state()` read from persisted SQLite state rather than in-memory defaults. Integrated real-executor capabilities default enabled; no-executor capabilities remain disabled/fail-closed.
- **CLI commands**: `/runtime-mode status|activate|disable`, `/capability-gates`, `/capability-gate detail|enable|disable`, `/runtime-readiness` are implemented and route through RuntimeAuthority governance.
- **Human-only activation**: `runtime_gate_manager` role (human-only) can activate `local_single_user_runtime` and enable `admin_mutation`/`role_mutation` capability gates. AI principals cannot activate runtime modes or capability gates.
- **Tests**: `tests/test_runtime_mode_activation.py`, `tests/test_capability_gate_persistence.py`, `tests/test_runtime_authority_mode_gate.py`.
- **Owner bootstrap flow**: `implemented_verified` — `/bootstrap-owner` creates owner principal, role, events; recovery flow with `--force-recover` supported; `resolve_local_principal()` replaces synthetic `cli_local` for all production-path principal resolution. Tests: `tests/test_local_single_user_runtime.py`.
- **Local single-user production hardening**: `implemented_verified` — first-run owner bootstrap, persisted owner principal, acting-principal resolution, runtime-gate-manager authorization, recovery/break-glass flow, AI principal denial for runtime mode/capability gate changes.
- **Production-ready local single-user runtime**: `ready` — all production readiness criteria completed and validated. See validation evidence below.
- **Deferred runtimes** remain disabled. Approval resolution remains metadata-only and never executes actions; `approval_execution_relay` is a separate integrated governed executor for approved file-write proposals. Integrated real-executor capabilities default enabled; no-executor capabilities remain disabled/fail-closed.

---

## Status Vocabulary

| Status | Meaning | Builder action |
|---|---|---|
| `specified_not_implemented` | The behaviour is documented, but code is not present yet. | Implement only through a named task and tests. |
| `phase_1_required` | Required for the Phase 1 MVP. | Build in Phase 1 task order. |
| `phase_scheduled_disabled` | Contract/profile/storage boundary may exist, but runtime wiring is disabled until a later phase. | Preserve contracts and registries; do not activate. |
| `implemented_unverified` | Code exists, but current acceptance validation is missing, incomplete, or not yet recorded for the active change set. | Run/repair tests before marking complete. |
| `implemented_verified` | Code and tests satisfy the acceptance criteria for the active change set. | Keep stable; regressions must fail CI. |
| `blocked_by_spec_gap` | Required behaviour is not detailed enough to implement safely. | Update docs before code. |
| `out_of_scope` | Deliberately not a Raiker goal. | Do not implement unless the non-goal is changed through ADR. |

---

## Known Documentation/Code Gaps (Review 2026-06-19)

A repository review (`docs/GAP_AND_TODO_ANALYSIS.md`) verified the following gaps
where documentation runs ahead of code. These are recorded here so the ledger stays trustworthy;
none of them change the validator-required Phase 1/2/3 markers below.

| Area | Documented as | Verified code reality | Honest status |
|---|---|---|---|
| Hooks | Full lifecycle spec (`docs/HOOKS_SPEC.md`) | `raiker/hooks/` implements `builtin`+`command` handlers, scoped config, decision authority, and dispatch wired through the broker/gateway; `http`/`mcp_tool`/`prompt`/`agent` deferred | `implemented_verified` (core); remaining handler types `specified_not_implemented` |
| Local model providers | llama.cpp native default through async OpenAI-compatible adapter; Ollama/LM Studio/vLLM/generic/OpenRouter profile-compatible and policy-gated; deterministic test-only | `raiker/models/providers/openai_compatible.py` uses `httpx.AsyncClient`; production gateway runs the operator-selected profile (persisted via `/model use`), defaulting to llama.cpp, and never falls back to deterministic; OpenRouter/private/hosted profiles require explicit policy | `implemented_verified` (async adapter + policy gates) |
| Local provider health-check | Phase 2 `implemented_verified` | `raiker/models/health.py` probes the llama.cpp `/health` endpoint over HTTP | accurate |
| Model-driven tool calls | "gather→act→verify" loop | `raiker/runtime/orchestrator.py` runs a bounded model-driven loop; model tool calls validated by `raiker/models/tool_call_validation.py` (OWASP LLM05) | `implemented_verified` |
| Verifier / verification step | "verify results" loop phase | `raiker/verification/` + `raiker/runtime/verifier.py` run deterministic safety/result-shape checks (tool-call schema, denied/approval non-execution, read result shape, mutation gating); integrated into the runtime loop | `implemented_verified` (deterministic safety/result-shape verification; not a semantic-correctness proof) |
| Context gathering | repository understanding feeding the model | `raiker/context/` builds a bounded `ContextBundle` of safe Phase 1/2 local metadata with provenance, trust level, sensitivity, redaction, and budgeting; the fixed `sources=["current_prompt"]` stub is removed from the runtime path | `implemented_verified` (Phase 1/2-safe bounded local-metadata context; not full repository intelligence) |
| Code review workflow | implied by "coding platform" | no review module present | `specified_not_implemented` (remains a separate follow-up; not required by Phase 1/2 acceptance) |

These do not activate or disable any runtime capability; they correct the *claimed* maturity only.
Close them via named phase tasks with tests before marking any `implemented_verified`.

## Validation evidence for production_ready_local_single_user_runtime

```text
ruff: passed
mypy: passed
pytest: 790 passed, 2 skipped
validate_phase_status: passed
validate_repo_truthfulness: passed
validate_runtime_enablement_readiness: passed
validate_local_single_user_runtime: passed
compileall: passed
```

### Phase 1/2 runtime maturity update (context gathering + verifier)

The two long-standing Phase 1/2 runtime stubs are now closed:

- **Context gathering** is now `implemented_verified` for Phase 1/2-safe bounded local-metadata
  context. `raiker/context/` produces a deterministic `ContextBundle` from safe sources only
  (current prompt, workspace summary, recent events, tasks, checkpoints, approvals, memory
  status/candidates, model profile, capability status). Every item carries source type, trust
  level, provenance, sensitivity, and redaction metadata; the bundle is budgeted by item count
  and characters; secrets/tokens/emails/private keys are redacted with deterministic
  placeholders. The runtime no longer records the fixed `sources=["current_prompt"]` stub.
  This is bounded metadata/local-summary context only, not full repository intelligence, and it
  does not enable semantic search, vector memory, graph runtime, plugin execution, external
  channels, or remote/container/cloud execution.
- **Verifier** is now `implemented_verified` for deterministic safety/result-shape verification.
  `raiker/verification/` checks tool-call schemas (unknown/invalid calls fail and are not
  executed), confirms denied actions did not execute, confirms approval-required actions stopped
  before execution with an approval record, validates safe read-tool result shape, and confirms
  mutation proposals stay approval-gated. Verifier output never exposes hidden reasoning,
  chain-of-thought, scratchpads, or system prompts. This is safety/result-shape verification, not
  a semantic-correctness proof.
- **Code review workflow** is now delivered as the Phase 2.5 local code-review workflow MVP
  (`implemented_verified` for CLI-only, read-only, bounded local diff review using deterministic
  rule-based findings and metadata-only events). See the Phase 2.5 status section below.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_1_2_context_gatherer.py`, `tests/test_phase_1_2_verifier.py`,
`tests/test_phase_1_2_runtime_gather_act_verify.py`.

---

## Phase 2.5 Local Code-Review Workflow Status

Phase 2.5 local code-review workflow MVP: `implemented_verified` for CLI-only, read-only, bounded
local diff review using deterministic rule-based findings and metadata-only events.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `raiker/review/` review engine (models, workflow, classifier, diff parser, render) | `phase_2_5` | `implemented_verified` | `raiker/review/` | `tests/test_phase_2_5_code_review_workflow.py` |
| `/review` CLI command surface (`--summary`, `--staged`, `--path`, `--json`, `--limit`, `--severity`) | `phase_2_5` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_2_5_code_review_cli.py` |
| Deterministic rule-based findings + metadata-only review events | `phase_2_5` | `implemented_verified` | `raiker/review/classifier.py`, `raiker/review/workflow.py` | `tests/test_phase_2_5_code_review_safety.py` |

Scope and boundaries:

- Review collects local Git status/diff through the existing policy-mediated `ToolBroker`/
  `PolicyEngine` git wrappers and the Phase 1/2-safe context gatherer. It does not call
  `subprocess`, shell, process, or network directly from `raiker/review/`.
- Review is read-only: it never mutates files, stages/unstages the Git index, commits, runs tests,
  applies fixes, or starts watchers/workers/daemons.
- Raw diffs, file contents, and secrets are never placed into findings or event payloads; secret-like
  content is redacted before findings/events.
- This MVP is deterministic/rule-based local CLI review only. It is **not** model-assisted review,
  GitHub PR review automation, a web/dashboard review UI, an IDE review UI, external-channel review
  delivery, plugin-based review, or semantic/graph review intelligence. Those remain deferred.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_2_5_code_review_workflow.py`, `tests/test_phase_2_5_code_review_cli.py`,
`tests/test_phase_2_5_code_review_safety.py`.

Phase 2.5 review hardening: `implemented_verified` for filtered-summary consistency and
metadata-only untracked-file detection.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `--severity`/`--limit` summary rebuilt from filtered findings | `phase_2_5` | `implemented_verified` | `raiker/review/render.py`, `raiker/cli/commands.py` | `tests/test_phase_2_5_code_review_hardening.py` |
| Metadata-only untracked-file detection in `/review` | `phase_2_5` | `implemented_verified` | `raiker/review/workflow.py` | `tests/test_phase_2_5_code_review_hardening.py` |

Hardening details:
- `rebuild_review_result_with_findings()` rebuilds `ReviewSummary.findings_count`,
  `severity_counts`, `categories`, and `event_metadata` from filtered findings.
- Filtering order is severity threshold first, limit second, summary rebuild third.
- `_collect_untracked_files()` uses `git_status` through `ToolBroker`/`PolicyEngine`.
- Untracked files are detected as metadata only; their contents are not read or leaked.
- Event payloads include safe `untracked_count` but not file contents or raw diffs.

Scope and boundaries (same as MVP — no expansion):
- Review collects local Git status/diff through the existing policy-mediated `ToolBroker`/
  `PolicyEngine` git wrappers and the Phase 1/2-safe context gatherer. It does not call
  `subprocess`, shell, process, or network directly from `raiker/review/`.
- Review is read-only: it never mutates files, stages/unstages the Git index, commits, runs tests,
  applies fixes, or starts watchers/workers/daemons.
- Raw diffs, file contents, and secrets are never placed into findings or event payloads; secret-like
  content is redacted before findings/events.
- This hardening is deterministic/rule-based local CLI review only. It is **not** model-assisted
  review, GitHub PR review automation, a web/dashboard review UI, an IDE review UI, external-channel
  review delivery, plugin-based review, or semantic/graph review intelligence. Those remain deferred.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_2_5_code_review_hardening.py`, `tests/test_phase_2_5_code_review_cli.py`,
`tests/test_phase_2_5_code_review_workflow.py`, `tests/test_phase_2_5_code_review_safety.py`.

---

## Phase 2.6 Review-to-Action Proposal Workflow Status

Phase 2.6 review-to-action proposal workflow: `implemented_verified` for local CLI-only proposal
generation from deterministic review findings.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `ReviewActionProposal` model + deterministic `generate_action_proposals()` | `phase_2_6` | `implemented_verified` | `raiker/review/models.py`, `raiker/review/proposals.py` | `tests/test_phase_2_6_review_action_proposals.py` |
| `/review --propose-fixes` / `--proposals-only` CLI surface | `phase_2_6` | `implemented_verified` | `raiker/cli/commands.py`, `raiker/review/render.py` | `tests/test_phase_2_6_review_action_proposal_cli.py` |
| Proposal text/JSON rendering + metadata-only `review_proposals_created` event | `phase_2_6` | `implemented_verified` | `raiker/review/render.py`, `raiker/review/workflow.py` | `tests/test_phase_2_6_review_action_proposal_safety.py` |

Scope and boundaries:

- Phase 2.6 is proposal-only. No fixes are applied. No files are modified. No tests are run.
  No shell/process/network execution is used. No GitHub PR automation is implemented. No
  UI/API/IDE/dashboard/mobile surface is implemented. No model-assisted/semantic review is
  implemented. No Phase 3/4 runtime capability is enabled.
- Proposals are generated in memory from the (filtered) review findings and returned in
  `ReviewResult.action_proposals`. `--severity`/`--limit` filtering applies before proposal
  generation so proposals align with visible findings.
- No proposal contains raw diff, raw file contents, raw secrets, prompt text, private
  reasoning, chain-of-thought, or raw tool output.
- Every proposal that could change files has `requires_approval=True` and
  `would_modify_files=True`; info-only/no-action proposals have both false.
- `raiker/review/` (including `raiker/review/proposals.py`) does not import `subprocess`,
  `socket`, `requests`, `httpx`, `urllib`, or `asyncio`.
- No Phase 3/4 runtime capability is enabled by this change. All disabled runtime flags remain
  false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

Evidence: `tests/test_phase_2_6_review_action_proposals.py`,
`tests/test_phase_2_6_review_action_proposal_cli.py`,
`tests/test_phase_2_6_review_action_proposal_safety.py`,
`tests/test_pre_phase_3_readiness.py`.

Pre-Phase-3 readiness audit: `docs/IMPLEMENTATION_STATUS.md` records that Phase 1, Phase 2,
Phase 2.5, and Phase 2.6 are complete and that it is safe to start Phase 3 planning next. It does
not mark Phase 3 runtime activation complete; Phase 4 remains blocked.

---

## Phase 3 Slice A Proposal Lifecycle Foundation Status

Phase 3 Slice A proposal lifecycle foundation: implemented_verified for local metadata-only
proposal lifecycle tracking of review action proposals.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `ProposalLifecycleRecord` model + `ProposalLifecycleStore` | `phase_3_slice_a` | `implemented_verified` | `raiker/review/lifecycle.py`, `raiker/review/models.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_models.py`, `tests/test_phase_3_slice_a_proposal_lifecycle_storage.py` |
| `/review --propose-fixes --save-proposals` persists proposals | `phase_3_slice_a` | `implemented_verified` | `raiker/cli/commands.py`, `raiker/review/lifecycle.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_cli.py` |
| `/proposals` and `/proposal <proposal_id>` CLI surfaces | `phase_3_slice_a` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_cli.py` |
| Metadata-only proposal lifecycle events | `phase_3_slice_a` | `implemented_verified` | `raiker/review/lifecycle.py`, `raiker/contracts/models.py` | `tests/test_phase_3_slice_a_proposal_lifecycle_safety.py` |

Scope and boundaries:

- Phase 3 Slice A is metadata-only; proposal-only; no proposal execution; no auto-fix; no patch
  application; no file mutation; no staging/unstaging; no test execution; no GitHub PR automation;
  no UI/API/IDE/dashboard/mobile; no approval execution; no Phase 4.
- `approval_execution_enabled` remains false. All disabled runtime flags remain false:
  plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled,
  vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled,
  approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled,
  external_channels_enabled, notifications_enabled, remote_execution_enabled,
  container_execution_enabled, cloud_execution_enabled, process_execution_enabled,
  shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.
- Lifecycle statuses are planning labels only: `proposed`, `acknowledged`, `deferred`,
  `rejected`, `superseded`. No status implies execution approval (`approved`,
  `approved_for_execution`, `ready_to_apply`, `execute` are deliberately excluded).
- No raw diff, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw
  tool output, or patch content is stored in records or event payloads.
- `raiker/review/` (including `raiker/review/lifecycle.py`) does not import `subprocess`,
  `socket`, `requests`, `httpx`, `urllib`, or `asyncio`. Lifecycle operations never mutate files,
  stages/unstages the Git index, commits, runs tests, applies fixes, or executes
  shell/process/network calls.
- This slice does not implement Phase 3 runtime execution, Phase 4, or any disabled runtime
  capability.

Evidence: `tests/test_phase_3_slice_a_proposal_lifecycle_models.py`,
`tests/test_phase_3_slice_a_proposal_lifecycle_storage.py`,
`tests/test_phase_3_slice_a_proposal_lifecycle_cli.py`,
`tests/test_phase_3_slice_a_proposal_lifecycle_safety.py`,
`tests/test_phase_3_slice_a_docs_truthfulness.py`.

Spec: `docs/IMPLEMENTATION_STATUS.md`.

## Phase 3 Slice B Approval Planning Preview Status

Phase 3 Slice B approval planning preview: `implemented_verified` for metadata-only approval
planning previews derived from saved proposal lifecycle records.

| Capability | Phase | Status | Source | Tests |
|---|---|---|---|---|
| `ProposalApprovalPreview` model + `approval_preview_from_lifecycle_record()` | `phase_3_slice_b` | `implemented_verified` | `raiker/review/models.py`, `raiker/review/approval_preview.py` | `tests/test_phase_3_slice_b_approval_preview_models.py` |
| `ProposalApprovalPreviewStore` + `proposal_approval_previews` table | `phase_3_slice_b` | `implemented_verified` | `raiker/review/approval_preview.py`, `raiker/storage/migrations.py` | `tests/test_phase_3_slice_b_approval_preview_storage.py` |
| `/proposal <proposal_id> --approval-preview` CLI surface | `phase_3_slice_b` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_3_slice_b_approval_preview_cli.py` |
| `/approval-previews` and `/approval-preview <preview_id>` CLI surfaces | `phase_3_slice_b` | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_3_slice_b_approval_preview_cli.py` |
| Metadata-only approval preview events | `phase_3_slice_b` | `implemented_verified` | `raiker/review/approval_preview.py`, `raiker/contracts/models.py` | `tests/test_phase_3_slice_b_approval_preview_safety.py` |

Scope and boundaries:

- Phase 3 Slice B is preview-only; no approval execution; no proposal execution; no auto-fix; no
  patch application; no file mutation; no staging/unstaging; no test execution; no GitHub PR
  automation; no UI/API/IDE/dashboard/mobile; no Phase 4.
- Phase 3 Slice B itself was preview-only and enabled no runtime execution. Current
  per-capability executor status is tracked in
  [`docs/RUNTIME_EXECUTORS_SPEC.md`](RUNTIME_EXECUTORS_SPEC.md) and the "Executor
  enablement status" section below; do not read this historical slice note as the
  current runtime flag state.
- Preview statuses are planning labels only: `preview_created`, `needs_human_review`, `blocked`,
  `ready_for_planning`, `superseded`. No status implies execution approval.
- No raw diff, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw
  tool output, or patch content is stored in preview records or event payloads.
- `raiker/review/approval_preview.py` does not import `subprocess`, `socket`, `requests`, `httpx`,
  `urllib`, or `asyncio`. Preview operations never mutate files, stage/unstage the Git index,
  commit, run tests, apply fixes, or execute shell/process/network calls.

Evidence: `tests/test_phase_3_slice_b_approval_preview_models.py`,
`tests/test_phase_3_slice_b_approval_preview_storage.py`,
`tests/test_phase_3_slice_b_approval_preview_cli.py`,
`tests/test_phase_3_slice_b_approval_preview_safety.py`,
`tests/test_phase_3_slice_b_docs_truthfulness.py`.

Spec: `docs/IMPLEMENTATION_STATUS.md`.

### Local validation baseline (2026-06-19)

After Phase 3 Slice B approval planning preview:

| Check | Result |
|---|---|
| ruff | All checks passed |
| mypy | Success, 209 source files |
| pytest | TBD |
| validate_phase_status.py | passed |
| validate_repo_truthfulness.py | passed |

If dependency metadata tests fail after dependency changes, branch switching, or local environment
rebuilds, refresh local editable-install metadata with:

```bash
python -m pip install -e .
```

Do not commit generated metadata/cache files including `*.egg-info/`, `build/`, `dist/`,
`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, or virtual environments.

---

## Phase 7 Desktop, Web, Plugins Runtime, Graph Index, Semantic Memory, IDE Status

Phase 7 activates the runtime features deferred from Phase 3 (safe foundation/readiness slices A-P only were implemented). All execution remains policy-gated and approval-required.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-7001 Desktop app session model | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7101 Web API session model | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7201 Dashboard data parity | `specified_not_implemented` | — | Dashboard widgets require UI framework. |
| RAIKER-7301 Mobile apps | `specified_not_implemented` | — | Mobile apps require native build toolchain. |
| RAIKER-7401 Plugin runtime execution | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7501 Graph/codemap runtime indexing | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7601 Semantic/vector memory writes | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |
| RAIKER-7701 IDE extension session model | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_phase_7_desktop_web_plugins_graph_memory_ide.py` |

All execution remains policy-gated. No runtime is activated without explicit policy, approval, and audit.

---

## Phase 1 MVP Status

Post-restore audit note: the long-form Phase 1 build plan is restored and remains the detailed scope source for implemented/verified Phase 1 behavior. Later Slice G/H lifecycle metadata does not change Phase 1 runtime scope.

PR #6 added the initial Phase 1 MVP runtime core.
PR #8 reconciled documentation and version baseline.
PR #11 removed generated Python bytecode artifacts and strengthened .gitignore.

**Validation status (2026-06-17):** The full validation set was run on the `phase-1-runtime-core-validation-baseline` branch. All validation commands pass, event sequences are verified, and security invariants hold. The Phase 1 final acceptance criteria are met. See the validation PR for exact command outputs and artifact inspection results.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---:|---:|---|---|
| Python package scaffold | `phase_1_required` | `implemented_verified` | `docs/foundation/09_IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md` | import/package smoke |
| Global `raiker` command | `phase_1_required` | `implemented_verified` | `README.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_scaffold.py`, terminal smoke |
| Equal-interface metadata | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/FEATURE_COVERAGE_MATRIX.md` | `tests/test_equal_interface_invariant.py` or equivalent invariant coverage |
| PromptEnvelope contract | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | `tests/test_contracts.py` |
| AgentEvent contract | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/EVENT_CATALOG.md` | `tests/test_event_log.py` |
| SQLite bootstrap | `phase_1_required` | `implemented_verified` | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_storage_sqlite.py` |
| Append-only JSONL event writer | `phase_1_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_event_log.py` |
| Static policy engine | `phase_1_required` | `implemented_verified` | `docs/SECURITY_AND_POLICY.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | `tests/test_policy_engine.py` |
| Tool broker skeleton | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | `tests/test_tool_broker.py` |
| `read_file` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | path safety tests |
| `list_directory` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | stable sorted output tests |
| `glob` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | bounded result tests |
| `grep` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | text-only and bounded output tests |
| Local action proposal | `phase_1_required` | `implemented_verified` | `docs/SECURITY_AND_POLICY.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | approval-required tests |
| Mock model provider | `phase_1_required` | `implemented_verified` | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | deterministic output tests |
| Model profile registry | `phase_1_required` | `implemented_verified` | `config/model-profiles.json`, `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | registry load tests |
| Channel connector registry | `phase_1_required` | `implemented_verified` | `config/channel-connectors.json`, `docs/CHANNELS_SPEC.md` | disabled/listable tests |
| Runtime state machine | `phase_1_required` | `implemented_verified` | `docs/RUNTIME_STATE_MACHINE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` | transition tests |
| Agent gateway | `phase_1_required` | `implemented_verified` | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` | gateway validation tests |
| Session manager | `phase_1_required` | `implemented_verified` | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | create/load tests |
| Checkpoint stub | `phase_1_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | write/read stub tests |
| Terminal client MVP | `phase_1_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` | terminal smoke tests |

---

## Phase-Scheduled Disabled Capabilities

The following capabilities may have config profiles, schemas, or storage boundaries in Phase 1, but must not be wired into active behaviour until their phase task explicitly allows it.

| Capability | First active phase | Required Phase 1 behaviour |
|---|---|---:|---|
| Desktop UI | Phase 3 | Preserve equal-interface contracts only. |
| Web UI and dashboard | Phase 3 | Preserve action parity and storage metrics contracts only. |
| Apple mobile app | Phase 3 | Connector profile may be disabled/listable; no active transport. |
| Android mobile app | Phase 3 | Connector profile may be disabled/listable; no active transport. |
| Plugin execution | Phase 3 | Validate/describe manifest shape only; no plugin code execution. |
| Semantic/vector memory writes | Phase 3 | Preserve storage metadata boundaries; no active embedding writes. |
| Graph/codemap runtime indexing | Phase 3 | Preserve schema/spec only; no runtime indexing. |
| External channels | Phase 4 | Profiles disabled unless explicitly paired in later phase. |
| Subagents and multi-agent teams | Phase 4 | Contracts/spec only; no spawning. |
| Remote/container execution | Phase 4 | Execution profiles disabled; no command routing. |
| Hosted model billing controls | Phase 5 | Budget records implemented; hosted providers remain policy-gated disabled. |
| Managed policies | Phase 5 | Implemented: managed deny wins over user/project/plugin allow. |
| Org/home-lab roles | Phase 5 | Implemented: users, roles, grants, session binding. |
| Audit export | Phase 5 | Implemented: export manifests, redaction, hash-chain integrity. |
| Plugin marketplace | Phase 5 | Implemented: checksum/signature verification, install records. |
| Hosted routines | Phase 5 | Implemented: metadata-only routine records; no execution. |
| Retention/backup | Phase 5 | Implemented: retention policies, legal hold, backup manifests. |

---

## Phase 2 Rich Local Workspace Status

Post-restore audit note: the long-form Phase 2 build plan is restored and remains the detailed scope source for implemented/verified Phase 2 behavior. Later Slice G/H lifecycle metadata depends on Phase 2 concepts but does not expand Phase 2 runtime authority.

PR #12 established the Phase 2 build plan, CI baseline, task manager, event viewer, checkpoint timeline, and inspection commands. This table tracks all Phase 2 capabilities.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---|---|---|---|
| Phase 2 build plan and status ledger | `phase_2_required` | `implemented_verified` | `docs/foundation/09_IMPLEMENTATION_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md` | doc consistency |
| CI baseline | `phase_2_required` | `implemented_verified` | `.github/workflows/ci.yml`, `docs/VERIFICATION_PLAN.md` | workflow syntax |
| Task record contract and storage helpers | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_task_manager.py` |
| Background task manager service | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | `tests/test_phase_2_task_manager.py` |
| Task lifecycle events and event indexing | `phase_2_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | task event tests |
| Event viewer query service | `phase_2_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_event_viewer.py` |
| Checkpoint timeline listing | `phase_2_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_checkpoint_timeline.py` |
| /status terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /tasks terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /events terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /checkpoints terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| Side-question child-turn contract | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | side-question contract tests |
| Read-only side-question runtime | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | side-question runtime tests |
| Interrupt/steer action contracts | `phase_2_required` | `implemented_verified` | `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` | interrupt contract tests |
| Safe-boundary interrupt handling | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | interrupt runtime tests |
| Approval inbox service | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | approval inbox tests |
| Approval terminal commands | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | terminal approval tests |
| Checkpoint restore/fork planning | `phase_2_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` | restore/fork tests |
| stat_path and diff_files tools | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | stat/diff tests |
| write_file/edit_file/apply_patch | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | file mutation approval tests |
| git status/diff/log wrappers | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | git wrapper tests |
| Local provider health-check | `phase_2_required` | `implemented_verified` | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | health check tests |
| Memory candidate listing | `phase_2_required` | `implemented_verified` | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` | memory candidate tests |
| Phase 2 integration validation | `phase_2_required` | `implemented_verified` | `docs/VERIFICATION_PLAN.md` | integration smoke tests |

---

## Phase 3 and Phase 4 Planning Status

Detailed Phase 3 and Phase 4 plans are now recorded in `docs/IMPLEMENTATION_STATUS.md` and `docs/IMPLEMENTATION_STATUS.md`. Safe foundations now include disabled/listable capability gates, plugin manifest validation without code execution, graph/codemap planning schemas, semantic-memory disabled status reporting, remote/container execution profiles, subagent planning, external-channel activation status, and terminal inspection commands. Tests prove these foundations are discoverable and remain non-executable until policy, storage, approval, and lifecycle controls are complete.

| Phase | Implemented foundation | Runtime state | Evidence |
|---|---|---|---|
| Phase 3 | Capability gates, `/capabilities`, plugin manifest validation, graph/codemap planning, semantic-memory status, `/semantic-memory` | Disabled/non-executing | `tests/test_phase_3_phase_4_implementation.py` |
| Phase 4 | Capability gates, `/execution-profiles`, remote/container execution planning, subagent planning, external-channel activation status | Disabled/non-executing | `tests/test_phase_3_phase_4_implementation.py` |

## Validation Evidence (2026-06-18)

**Local validation** was performed on `main` (no fixes needed — all checks passed):

| Aspect | Detail |
|---|---|
| **Date/time** | 2026-06-18 07:51 UTC |
| **OS** | Windows (PowerShell) |
| **Python version** | 3.13.5 |
| **Virtual environment** | `.venv` |
| **Commands run** | `ruff check .`, `mypy raiker apps tests`, `pytest`, `scripts/validate_phase_status.py`, `raiker --help`, `raiker --prompt "Hello Raiker"`, comprehensive smoke script |
| **Test result** | 93/93 passed |
| **Ruff** | All checks passed |
| **Mypy** | No issues (87 files) |
| **Phase status validation** | Passed |
| **Fixes made** | None — all checks passed on first run |
| **Phase 3 runtime disabled** | plugin_execution, graph_codemap_indexing, semantic_memory_writes all confirmed disabled |
| **Phase 4 runtime disabled** | external_channels, subagents, multi_agent_teams, remote_execution, container_execution all confirmed disabled |
| **Assessments** | Phase 1 and Phase 2 remain `implemented_verified`. Phase 3/4 safe foundations are correct, discoverable, tested, and non-executing. No runtime features were activated.|

## Status Update Rule

A builder may change a row to `implemented_verified` only when all of these are true:

1. The implementation maps to a Phase 1 task ID or later phase task ID.
2. The implementation follows the canonical docs listed in this file.
3. Required tests exist and pass for the active change set.
4. Validation output is included in the PR.
5. Event names, storage tables, contracts, and policy decisions match the specs.
6. The equal primary-interface invariant remains intact.

If any of these are false, the correct status is `implemented_unverified` or `blocked_by_spec_gap`.

---

## Documentation Gap Handling

When a builder finds conflicting or incomplete documentation, it must stop the implementation task and create a documentation update first. The documentation update must identify:

- affected feature;
- build phase;
- conflicting files;
- chosen canonical behaviour;
- contracts affected;
- storage affected;
- events emitted;
- policy/security impact;
- tests required.

Undocumented behaviour is not approved Raiker behaviour.

## Phase 3 rollout slice A status — 2026-06-18

Phase 3 is **not complete**. The first rollout slice is `implemented_verified` after adding read-only workspace contract parity and plugin policy/registration planning.

| Slice | Status | Evidence |
|---|---:|---|
| RAIKER-3101 desktop/web/dashboard contract parity foundation | `implemented_verified` | `raiker/workspace/inspection.py`, `tests/test_phase_3_workspace_inspection.py`, `tests/test_phase_3_equal_workspace_clients.py` |
| RAIKER-3201 plugin execution policy boundary without execution | `implemented_verified` | `raiker/plugins/policy.py`, `raiker/plugins/registry.py`, `tests/test_phase_3_plugin_policy.py` |
| Phase 3 capability state model | `implemented_verified` | `raiker/phase_gates.py`, `tests/test_phase_3_capability_states.py` |
| Read-only CLI inspection commands | `implemented_verified` | `/workspace`, `/clients`, `/plugins`, `/plugin-plan <manifest_path>`, `tests/test_phase_3_terminal_commands.py` |

Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain non-executing.

## Temporary CI Pause — GitHub Actions quota exhausted

- GitHub Actions are temporarily paused or unavailable due run-limit/quota exhaustion.
- Local validation is mandatory while Actions are paused; use `docs/LOCAL_VALIDATION_GATE.md` as the source of truth for required commands and evidence.
- Full CI must be re-enabled before future release tagging or when quota becomes available.
- This is not a waiver of validation requirements.

## Phase 3 rollout slice B status — 2026-06-18

Phase 3 is **not complete**. Slice B adds the RAIKER-3501 read-only rich workspace view/API foundation while preserving all disabled runtime gates.

| Slice | Status | Evidence |
|---|---:|---|
| RAIKER-3501 read-only rich workspace view/API foundation | `implemented_verified` after local validation evidence is recorded | `raiker/workspace/views.py`, `tests/test_phase_3_workspace_views.py` |
| `/workspace-view` read-only CLI summary | `implemented_verified` after local validation evidence is recorded | `raiker/cli/commands.py`, `tests/test_phase_3_workspace_views.py` |

The view layer consumes the shared workspace inspection contract and renders deterministic text, JSON-safe, dashboard, client capability, and plugin plan summaries. It does not execute tools, create approvals, call models, write memory, execute plugin code, activate channels, start remote/container execution, or expose secret-like values.

Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain non-executing.

## Phase 3 Slice C/D governance update (local validation required)

The older Phase 3 Slice C/D governance note is superseded by the current executor posture: graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding now have real governed executors. Broader graph query/planning automation, learned semantics, external sync, and no-executor extensions remain deferred/fail-closed.

Safety status for this slice:

- GitHub Actions remain paused due quota exhaustion; do not claim GitHub CI passed while paused.
- Local validation evidence remains mandatory under `docs/LOCAL_VALIDATION_GATE.md`.
- Plugin execution slices are integrated governed executors; broader plugin extensions remain deferred/fail-closed.
- Graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding are integrated governed executors; broader graph/memory extensions remain deferred/fail-closed.
- The reference external channel runtime, subagent/team executors, and local container executor are integrated and governed.
- Remote/cloud command execution remains no-executor/fail-closed.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.

| `/workspace-view` safe terminal snapshot command | `implemented_verified` | `raiker/cli/commands.py`, `tests/test_phase_3_workspace_views.py` |

## 2026-06-18 Phase 3 Slice E — approval-preview UX/contracts

Status: `implemented_verified` locally for the Slice E contract surface only; full Phase 3 is not complete.

Slice E adds preview-only approval contracts for future graph/codemap indexing and semantic memory writes. The implementation exposes deterministic preview rendering, redaction of secret-like memory text, CLI preview commands, and workspace inspection summary fields.

Safety status:

- Legacy preview surfaces do not execute graph writes; the current graph indexing runtime is a separate governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic/vector runtimes are governed real executors.
- Previews are not approvals to execute; approving for later does not write memory or run indexing.
- No embeddings, vectors, background indexers, watchers, daemons, plugins, channels, remote execution, or container execution are activated.
- GitHub Actions remain paused due quota exhaustion; local validation evidence is mandatory and full CI must be re-enabled later when quota is available.

## Phase 3 Slice F — Approval Audit and Rollback Planning

Slice F adds preview-only approval audit and rollback planning contracts for future graph indexing and semantic memory writes. Full Phase 3 is not complete.

Safety invariants for this slice:

- Approval audit records do not execute actions.
- Rollback plans do not execute rollback.
- Legacy preview surfaces do not execute graph writes; the current graph indexing runtime is a separate governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic memory and vector embedding/search runtimes are separate governed real executors.
- Plugin slices, the reference external channel, subagent/team executors, and local container runtime are governed real executors; remote/cloud command execution remains no-executor/fail-closed.
- GitHub Actions remain paused due quota exhaustion; local/cloud validation evidence is mandatory.
- CI must be re-enabled later when quota is available and must not be claimed as passed while Actions are paused.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

## Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Legacy lifecycle/preview surfaces do not write graph data directly; current graph indexing is a governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic/vector runtimes are governed real executors.
- Rollback execution remains disabled.
- Plugin slices, the reference external channel, subagent/team executors, and local container runtime are governed real executors; remote/cloud command execution remains no-executor/fail-closed.
- GitHub Actions remain paused due quota/run-limit exhaustion; local/cloud validation evidence is mandatory and GitHub CI must be re-enabled later when quota is available.

## Phase 3 Slice H lifecycle retention status

Slice H is `implemented_verified` locally for metadata-only retention policies, cleanup previews, approval-handoff planning, read-only summaries, and SQLite metadata tables. Full Phase 3 is still incomplete. Keep detailed contract and safety requirements in `docs/IMPLEMENTATION_STATUS.md`; this document records only the status summary. Slice H does not execute cleanup, graph/codemap indexing, semantic/vector memory writes, embeddings, rollback, plugins, channels, subagents, approval relay, or remote/container/cloud execution.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/IMPLEMENTATION_STATUS.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Phase 3 Slice J — Graph/Codemap Indexing Readiness Metadata

Slice J is `implemented_verified` for metadata-only readiness surfaces: deterministic contract, registry create/list/get/summary, read-only CLI, optional SQLite metadata table, workspace inspection/view fields, docs, and tests.

Slice J did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked. Graph/codemap runtime indexing, graph writes, workers, schedulers, file watchers, daemons, and runtime jobs remain disabled.


## Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only
- Adds deterministic metadata-only semantic memory readiness contracts, registry, optional SQLite metadata table, CLI, and workspace surfaces.
- Semantic memory writes, vector writes, embeddings, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled.
- Reserved Slice K metadata-only events: `phase3.semantic_memory_readiness.metadata_created`, `phase3.semantic_memory_readiness.summary_viewed`, `phase3.semantic_memory_readiness.exported`. No runtime memory write events are enabled.
- Slice K did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice L — Approval Preview Persistence Readiness — Metadata Only

Slice L is implemented as metadata-only readiness for future durable approval preview persistence. It adds `/approval-readiness [--summary|--json]`, deterministic `appr_` readiness contracts, optional `phase3_approval_preview_persistence_readiness` SQLite metadata storage, and workspace inspection/view fields. Approval execution, approval relay runtime, durable approval queues, approval workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice L did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.


## Phase 3 Slice M — Storage Cleanup Execution Readiness — Metadata Only

Implemented deterministic metadata-only readiness contracts, registry, optional SQLite metadata table, CLI surface, and workspace summaries for storage cleanup execution readiness. Cleanup execution, deletion, purge, tombstone, rollback, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice M did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice O — External Channels/Notifications Readiness — Metadata Only

Implemented metadata-only readiness contracts, registry operations, optional SQLite persistence, read-only `/channel-readiness` CLI output, and workspace summary fields for future external channels and notifications. No external channels, notifications, push notifications, share links, webhook dispatch, relay runtime, hosted channels/routines, workers, schedulers, watchers, daemons, or runtime execution are enabled. Slice O did not by itself mark Phase 3 complete. Phase 3 is complete (see `docs/IMPLEMENTATION_STATUS.md`). Phase 4 remains blocked.

## Phase 3 Slice P — Remote/Container/Cloud Execution Readiness — Metadata Only

Added metadata-only readiness contracts, registry operations, optional SQLite persistence, read-only `/remote-readiness` CLI output, and workspace summary fields for future remote/container/cloud execution. No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, or runtime execution are enabled.

## Phase 5 Governed Enterprise Status

Phase 5 adds managed governance, org roles, audit export, plugin marketplace, hosted routines, budget controls, retention, and backup. Integrated real-executor capabilities are governed runtime; no-executor capabilities remain disabled/fail-closed.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-5001 Managed policy model | `implemented_verified` | `raiker/policy/engine.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_5_managed_policy.py` |
| RAIKER-5101 Org/home-lab roles | `implemented_verified` | `raiker/cli/commands.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_5_org_roles.py` |
| RAIKER-5201 Audit export and event integrity | `implemented_verified` | `raiker/events/export.py`, `raiker/events/integrity.py`, `raiker/cli/commands.py` | `tests/test_phase_5_audit_export.py` |
| RAIKER-5301 Plugin marketplace and signed trust | `implemented_verified` | `raiker/plugins/verify.py`, `raiker/plugins/policy.py`, `raiker/plugins/registry.py` | `tests/test_phase_5_plugin_marketplace.py` |
| RAIKER-5401 Hosted routines | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_5_hosted_budget_retention.py` |
| RAIKER-5501 Budget records | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_5_hosted_budget_retention.py` |
| RAIKER-5601 Retention and backup | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_5_hosted_budget_retention.py` |

Integrated real-executor capabilities are governed runtime; no-executor capabilities remain disabled/fail-closed.

## Phase 6 Channels, Subagents, Remote Execution Status

Phase 6 adds external channel profiles, approval relay, subagent contracts, multi-agent team ledgers, remote execution profiles, and execution budgets. Integrated real-executor capabilities default enabled and governed per action; no-executor capabilities remain disabled/fail-closed.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-6001 External channel connectors | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6101 Channel approval relay | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6201 Subagent contracts | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6301 Multi-agent teams | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6401 Remote/container execution | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |
| RAIKER-6501 Execution budget | `implemented_verified` | `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/cli/commands.py` | `tests/test_phase_6_channels_subagents_remote.py` |

Disabled runtime flags remain false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled, vector_writes_enabled, embedding_creation_enabled, cleanup_execution_enabled, rollback_execution_enabled, external_channels_enabled, notifications_enabled, remote_execution_enabled, container_execution_enabled, cloud_execution_enabled, process_execution_enabled, shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.
Executor enablement status: real local executors in `REAL_EXECUTOR_CAPABILITIES` are governed-flippable; deferred sensitive/external capabilities fail closed. See `docs/RUNTIME_EXECUTORS_SPEC.md`.

## Phase 3 Completion Status

All Phase 3 slices A through P are implemented, tested, and documented. Phase 3 is now marked `implemented_verified` (this ledger is the canonical completion record; the former standalone `PHASE_3_COMPLETION_AUDIT.md` has been folded in here). **Phase 3 can be marked complete.** Integrated real-executor capabilities default enabled and governed per action; no-executor capabilities remain disabled/fail-closed. Phase 4 memory MVP is implemented. Phase 4 production rollout is now in progress under the sandboxed-first plan (see "Phase 4 production rollout" below). Landed slices: Slice 1 — `subagents` and `multi_agent_teams` (bounded governed in-process executors); Slice 4 — `external_channel_runtime` and `channel_approval_relay` (one reference webhook channel + untrusted inbound receiver); Slice 3 — `container_execution_cap` (local sandboxed Docker); Slice 2 — `scheduled_routines` (local on-demand routine runner, no daemon); Slice 5 — REST API hardening for single-user internet access (see the REST/API row above); Slice 7 — `hosted_model_runtime` + `private_network_model_runtime` (owner-allowlisted off-machine model endpoints with gate-derived chat-path policy); Slice 8 — `plugin_install` (local plugin manifest validation + install-record creation only); Slice 9 — `plugin_execution_cap` (installed-plugin brokered read-only ToolBroker invocation only). Their capability gates are integrated real-executor gates: default `enabled_runtime`, owner/`runtime_gate_manager`-changeable only, and governed per action (default `ask`). Slice 6: remote/cloud command execution stays **fail-closed by design** with documented per-integration opt-in requirements (`docs/threat-models/remote-cloud.md`). Unrestricted/in-process plugin code execution and broader plugin automation stay deferred/fail-closed.

## Phase 4 production rollout (sandboxed-first)

Phase 4 is being brought to production-ready state in individually-validated slices. Each slice promotes a capability to a real executor only with a per-capability threat model (`docs/threat-models/`) + acceptance tests (executes-when-governed and fails-closed-when-disabled), and every promoted gate now defaults `enabled_runtime` when integrated and remains owner/`runtime_gate_manager`-changeable only. All no-executor runtime flags remain false; integrated executors are governed per action (default `ask`).

### Phase 4 Slice 1 — Subagents & Multi-Agent Teams (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `subagents` real executor (bounded, governed, read-only, in-process) | `implemented_policy_gated` | `raiker/agents/orchestration.py`, `raiker/runtime/executors/orchestration.py` | `tests/test_phase_4_subagent_orchestration.py` |
| `multi_agent_teams` real executor (≤5 sequential subagents) | `implemented_policy_gated` | `raiker/agents/orchestration.py`, `raiker/runtime/executors/orchestration.py` | `tests/test_phase_4_subagent_orchestration.py` |

Scope and boundaries (metadata-only events; this is bounded delegated execution, **not** autonomous model-driven recursion):

- Subagents run a fixed caller-supplied list of **read-only** tool steps, each routed through the existing `ToolBroker → PolicyEngine` path; mutating/egress tools fail closed (`subagent_tool_not_allowed`).
- Depth, step count, runtime, and team size are bounded; any breach fails closed and never fabricates success.
- Gates default `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/subagents.md`), and a confirmation token. AI principals can never run or enable them.
- No model calls, no OS process spawn, no network. No no-executor runtime flag changes. Approval resolution remains metadata-only.

Evidence: `tests/test_phase_4_subagent_orchestration.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 4 — Reference channel (`implemented_verified`)

The single reference channel (webhook transport) for the sandboxed-first rollout. Other transports (Slack/Signal/Teams/Discord native) and multi-connector fan-out remain disabled/deferred.

| Capability | Status | Source | Tests |
|---|---|---|---|
| `external_channel_runtime` real executor (bounded outbound webhook) | `implemented_policy_gated` | `raiker/runtime/executors/channels.py`, `raiker/runtime/executors/sandbox.py` | `tests/test_phase_4_channels.py` |
| `channel_approval_relay` real executor (metadata-only pending relay) | `implemented_policy_gated` | `raiker/runtime/executors/channels.py` | `tests/test_phase_4_channels.py` |
| Inbound receiver (always untrusted, owner-secret-gated, quarantined) | `implemented_verified` | `raiker/api/routes_channels.py` | `tests/test_phase_4_channels.py` |

Scope and boundaries:

- Outbound delivery requires a paired+enabled connector and an owner-controlled egress allowlist (`RAIKER_CHANNEL_EGRESS_ALLOWLIST`); empty allowlist fails closed. Events are metadata-only — never the message text or target URL.
- The approval relay records a `pending` relay only; approval resolution remains metadata-only/owner-only.
- Inbound traffic (`POST /api/channels/{connector_id}/inbound`) is authenticated by an owner channel secret (`RAIKER_CHANNEL_INBOUND_SECRET`, fail-closed when unset), requires a sender on the pairing allowlist, and is **always** labelled `untrusted` + quarantined with instructions inert (the Phase 8 "webhook injection labelled untrusted" gate). It executes nothing.
- Gates default `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/channels.md`), and a confirmation token. AI principals can never run or enable them. No no-executor runtime flag changes; the integrated executor remains governed per action.

Evidence: `tests/test_phase_4_channels.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 3 — Local container execution (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `container_execution_cap` real executor (local sandboxed Docker) | `implemented_policy_gated` | `raiker/runtime/executors/containers.py` | `tests/test_phase_4_container.py` |

Scope and boundaries:

- Runs an **owner-allowlisted** image (`RAIKER_CONTAINER_IMAGE_ALLOWLIST`; empty = fail closed) via `docker run` with `--network none`, no host mounts, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--read-only`, memory/cpu/pid limits, `--rm`, and a capped timeout. The container runner's command allowlist is exactly `{docker}`.
- Missing daemon fails closed (`docker_unavailable`); non-zero exit is reported as failure. Artifacts are metadata only (exit code + byte counts) — never stdout/stderr content.
- Local only: remote/container-over-SSH/Kubernetes/cloud stay fail-closed. Gate defaults `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/container.md`), and a confirmation token. AI principals can never run or enable it.
- CI exercises governance + fail-closed + flag-set construction via an injected runner; a live-daemon successful run is verified manually. No no-executor runtime flag changes; the integrated executor remains governed per action.

Evidence: `tests/test_phase_4_container.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 2 — Scheduled routines (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `scheduled_routines` real executor (local, on-demand, no daemon) | `implemented_policy_gated` | `raiker/runtime/executors/scheduled.py`, `raiker/storage/migrations.py` (`scheduled_routines` table) | `tests/test_phase_4_scheduled_routines.py` |

Scope and boundaries:

- A routine bundles an interval with a bounded **read-only** subagent payload. Operations: `define`, `run_due`, `run`. There is **no background daemon/thread/watcher** — routines run only when an explicit governed `run_due`/`run` action is invoked.
- Routine work executes via the Slice 1 `SubagentExecutor`, so mutating/egress tools fail closed (`subagent_tool_not_allowed`). Minimum interval 60s; at most 50 routines per tick; malformed payload/op fails closed.
- Gate defaults `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/scheduled-routines.md`), and a confirmation token. AI principals can never run or enable it. The integrated executor remains governed per action (default `ask`).

Evidence: `tests/test_phase_4_scheduled_routines.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 6 — Remote/cloud egress (fail-closed by design)

`remote_execution_cap` and `cloud_execution_cap` remain **fail-closed (no executor)** per the sandboxed-first decision. Their executors return `not_implemented:<capability>`, the registry refuses to register them, and activation is blocked with `activation_blocked:no_executor`. The per-integration opt-in requirements (credential injection, egress allowlist, budgets, threat model, tests) are documented in `docs/threat-models/remote-cloud.md`. Disabled/deferred. Remote/container/cloud execution remains disabled/deferred at runtime. (`hosted_model_runtime` / `private_network_model_runtime` completed that opt-in checklist in Slice 7 below.)

### Phase 4 Slice 7 — Hosted & private-network model runtime (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `hosted_model_runtime` real executor (allowlisted HTTPS metadata-only probe) + gate-derived chat-path policy | `implemented_policy_gated` | `raiker/runtime/executors/models_runtime.py`, `raiker/models/policy_state.py`, `raiker/models/endpoint_policy.py` | `tests/test_phase_4_hosted_model_runtime.py` |
| `private_network_model_runtime` real executor (allowlisted home-lab probe) + gate-derived chat-path policy | `implemented_policy_gated` | `raiker/runtime/executors/models_runtime.py`, `raiker/models/policy_state.py` | `tests/test_phase_4_hosted_model_runtime.py` |
| `advisor_model_runtime` real executor + governed `consult_advisor` tool (advisor model for local-model turns; default-ask withholds, provider policy re-checked per call, metadata-only audit) | `implemented_policy_gated` | `raiker/runtime/advisor.py`, `raiker/runtime/executors/models_runtime.py`, `raiker/tools/advisor_tools.py`, `raiker/tools/broker.py` | `tests/test_advisor_model.py` |
| Uploaded image attachments (web-app task 3): governed local attachment store (media-type allowlist + 5 MB cap + magic-byte sniff, fail closed), `supports_vision` capability, image blocks delivered only to vision-capable profiles (withheld honestly otherwise; metadata-only audit — image bytes never enter events or text context) | `implemented_verified` | `raiker/runtime/attachments.py`, `raiker/api/routes_attachments.py`, `raiker/storage/sqlite.py` (`RAIKER-1006`), `raiker/runtime/orchestrator.py`, `raiker/models/providers/*` | `tests/test_uploaded_image_attachments.py` |
| Uploaded document attachments (web-app task 3, DONE): same governed store, document allowlist (plain text / markdown / csv / PDF / Word .docx) + 32 MB cap (matches Claude's document limit) + per-type sniff (UTF-8/NUL for text, `%PDF-`+pypdf-parseable+not-encrypted for PDF, OOXML zip for .docx). Local-only extraction (decode / pypdf / stdlib zip+XML, ≤100 PDF pages, no bytes leave the box) folded into context as a bounded `untrusted_external` item; metadata-only load never carries bytes. Image cap stays 5 MB (matches the Anthropic image API). **Live-verified** 2026-07-11: real PDF + docx + JPEG through hosted Anthropic Haiku 4.5 (correct extractions/vision; `docs/WEB_APP_LIVE_TEST.md`) | `implemented_verified` | `raiker/runtime/attachments.py`, `raiker/api/routes_attachments.py`, `raiker/api/app.py`, `raiker/context/gatherer.py`, `pyproject.toml` (`pypdf`) | `tests/test_document_attachments.py` |

Scope and boundaries:

- The production `ModelRouter` (gateway + `/model` CLI) derives its `ProviderRuntimePolicy` from the persisted capability gates (`raiker/models/policy_state.py`). If either gate is deliberately disabled, the corresponding hosted/private model profile cannot be constructed at all; no silent local→hosted fallback exists.
- Every off-machine provider construction re-checks the owner egress allowlist (`RAIKER_MODEL_EGRESS_ALLOWLIST`, comma-separated host globs); empty allowlist fails closed (`model_egress_denied:no_allowlist`) even when the gate is enabled. Local endpoints are never subject to this allowlist.
- Credentials come only from owner env vars named by the profile's `api_key_env` — never from model/action arguments; never written to storage, events, or artifacts.
- The executors support a single bounded operation, `connectivity_check`: an allowlisted, size/time-capped reachability probe. Artifacts are metadata only (endpoint kind, HTTP status, byte counts) — never URLs, hosts, response bodies, headers, or keys. Hosted probes require HTTPS and `remote_hosted` endpoints; private probes require `private_network` endpoints.
- Gates default `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/hosted-models.md`), and a confirmation token. AI principals can never run or enable them. Remote/cloud command execution stays fail-closed (Slice 6). No no-executor runtime flag changes; the integrated executor remains governed per action.

Evidence: `tests/test_phase_4_hosted_model_runtime.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 8 — Plugin manifest install (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `plugin_install` real executor (local manifest validation + install-record creation only) | `implemented_policy_gated` | `raiker/runtime/executors/tier4_plugins.py`, `raiker/plugins/policy.py`, `raiker/plugins/verify.py`, `raiker/plugins/registry.py` | `tests/test_phase_4_plugin_install_runtime.py` |

Scope and boundaries:

- This slice records a validated local plugin manifest in `plugin_install_records`. It does not fetch, unpack, import, execute, enable, or sandbox plugin code.
- The action accepts `manifest_path` only and requires the manifest to resolve inside the workspace. Escapes fail closed (`outside_workspace:manifest_path`).
- The plugin registration policy must return `planned`: checksum verification must pass, the signature field must be present, trust level must be known, and permissions must be safe read-only. Risky/unknown permissions and invalid supply-chain metadata fail closed and create no install record.
- Signature verification is layered (see the current-truth banner at the top and `docs/threat-models/plugins.md`): a presence marker in the local-dev baseline, cryptographic HMAC-SHA256 when the owner sets `RAIKER_PLUGIN_SIGNING_KEY` (slice 12), and asymmetric Ed25519 against an owner-trusted `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` (slice 13). Each configured check fails closed and creates no install record on failure.
- Gate defaults `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/plugins.md`), and a confirmation token. AI principals can never run or enable it.
- `plugin_execution_cap` is a separate implemented governed executor for installed-plugin brokered read-only ToolBroker invocation only. Plugin install itself only validates and records a local manifest; it does not execute plugin code. Broader plugin tools/hooks/MCP/LSP/monitors/panels, unrestricted imports/network, and unrestricted plugin automation remain deferred/fail-closed.

Evidence: `tests/test_phase_4_plugin_install_runtime.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 9 — Plugin brokered read-only execution (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `plugin_execution_cap` real executor (installed-plugin brokered read-only tool invocation only) | `implemented_policy_gated` | `raiker/runtime/executors/tier4_plugins.py`, `raiker/tools/broker.py`, `raiker/policy/engine.py` | `tests/test_phase_4_plugin_execution_runtime.py` |

Scope and boundaries:

- This slice lets an installed plugin invoke only `read_file`, `list_directory`, `glob`, or `grep` through the existing `ToolBroker` and `PolicyEngine`.
- It requires an `installed` plugin record and the exact installed permission (`tool:<tool_name>`). Missing install records, missing permissions, unknown tools, write tools, shell/process/network tools, and memory mutation fail closed before invocation.
- The executor never imports plugin files, runs plugin scripts, starts processes, opens network connections, writes files, enables hooks, starts MCP/LSP/monitors, or activates UI panels.
- The broker is created without an event writer so plugin read outputs are not emitted into plugin-execution runtime events. Executor artifacts are metadata only and include `output_redacted=true` on success.
- Gate defaults `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/plugin-execution.md`), and a confirmation token. AI principals can never run or enable it.
- Arbitrary plugin code execution remains deferred until a separate sandbox/import/process model and runtime permission enforcement exist. Cryptographic signature validation (HMAC slice 12, Ed25519 slice 13) and revocation (slice 10) are now implemented, but code execution stays fail-closed pending the sandbox/import/process model.

Evidence: `tests/test_phase_4_plugin_execution_runtime.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 4 Slice 14 — Plugin code runtime (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `plugin_runtime_cap` real executor (bounded subprocess execution of an installed, owner-allowlisted plugin entrypoint) | `implemented_policy_gated` | `raiker/runtime/executors/tier4_plugins.py`, `raiker/runtime/executors/sandbox.py` | `tests/test_phase_4_plugin_runtime.py` |

Scope and boundaries:

- This is the first capability that runs **arbitrary plugin code**. It executes an installed plugin's declared entrypoint as a bounded subprocess via the shared sandbox (`run_command`): interpreter allowlist (`python3`/`python`/`node`), workspace-scoped script path, default 30s / max 120s timeout, 200 KB output caps.
- Runtime authorization comes from the **owner**, not the manifest: the plugin must have a non-revoked `installed` record **and** be named in `RAIKER_PLUGIN_RUNTIME_ALLOWLIST` (comma-separated; empty = fail closed). The install slice only records safe read-only permissions, so the owner allowlist is the separate, explicit grant for code execution.
- Fails closed on: missing/invalid `plugin_id` or `entrypoint`, disallowed interpreter (`interpreter_not_allowed`), non-list/oversized args, uninstalled (`plugin_not_installed`) or revoked (`plugin_revoked`) plugin, un-allowlisted plugin (`plugin_runtime_not_allowlisted`), workspace escape (`outside_workspace:entrypoint`), missing script (`entrypoint_not_found`), and sandbox/timeout errors (`plugin_runtime_sandbox:*`). Non-zero exit surfaces as `plugin_runtime_exit:<code>`.
- Commands run as an argv list (never a shell), so shell metacharacters are inert. Runtime artifacts are metadata only (execution id, plugin id, interpreter, return code, byte counts, `output_redacted=true`); plugin stdout/stderr is never captured into events or artifacts. Every attempt writes a `plugin_execution_records` row.
- Isolation posture equals `shell_execution`/`process_execution` (separate process, resource + timeout bounds). It does **not** import plugin modules in-process and does **not** provide a network-namespace jail — a plugin subprocess has the host's ambient network, so the owner allowlist is the trust anchor. Kernel-isolated network-off execution stays in the `container_execution_cap` path.
- Gate defaults `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime` mode, the registered executor, a `threat_model_acks` row (`docs/threat-models/plugin-runtime.md`), and a confirmation token. AI principals can never run or enable it.
- Deferred: in-process import isolation, runtime permission enforcement beyond the owner allowlist, and network-namespace/kernel sandboxing for plugin code.

Evidence: `tests/test_phase_4_plugin_runtime.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_local_single_user_runtime.py`.

### Phase 4 Slice 15 — Per-plugin runtime scope (`implemented_verified`)

Extends `plugin_runtime_cap` (no new capability). The owner may narrow a plugin's filesystem reach below the whole workspace with `RAIKER_PLUGIN_RUNTIME_SCOPES` (comma-separated `<plugin_id>:<subpath>`), so the owner grant is not all-or-nothing. A scoped plugin's entrypoint must resolve inside `<workspace>/<subpath>` or fail closed (`entrypoint_outside_plugin_scope`); a subpath that escapes the workspace fails closed (`plugin_scope_invalid`); a plugin without an entry keeps slice-14 behavior. The scope constrains which entrypoint path may run — it does not OS-jail the subprocess's own filesystem access (that is slice 16). Evidence: `tests/test_phase_4_plugin_runtime.py` (scope cases), `docs/threat-models/plugin-runtime.md`.

### Phase 4 Slice 16 — Sandboxed (network-isolated) plugin runtime (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `plugin_sandboxed_runtime_cap` real executor (network-isolated container plugin runtime) | `implemented_policy_gated` | `raiker/runtime/executors/tier4_plugins.py`, `raiker/runtime/executors/containers.py`, `raiker/runtime/executors/sandbox.py` | `tests/test_phase_4_plugin_sandboxed_runtime.py` |

Scope and boundaries:

- The stronger-isolation counterpart to `plugin_runtime_cap`: runs the installed plugin's entrypoint **inside a container** with `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, and memory/cpu/pid limits. Only the single entrypoint file is bind-mounted read-only at `/plugin/<name>`; the workspace is never mounted.
- `plugin_sandbox_image_pull_cap` is the governed pull-only acquisition path for that image. It requires the exact image in `RAIKER_CONTAINER_IMAGE_ALLOWLIST` and its registry in `RAIKER_PLUGIN_IMAGE_REGISTRY_ALLOWLIST`, invokes only `docker pull <image>`, and records metadata only. It does not build, execute, or inspect images; Docker daemon registry networking remains an operator boundary. Evidence: `tests/test_phase_4_plugin_image_pull.py`, `docs/threat-models/plugin-sandbox-image-pull.md`.
- Reuses the owner plugin allowlist (`RAIKER_PLUGIN_RUNTIME_ALLOWLIST`) and per-plugin scopes, and additionally requires an owner-selected image `RAIKER_PLUGIN_RUNTIME_IMAGE` that is also in the shared `container_image_allowlist()` (`RAIKER_CONTAINER_IMAGE_ALLOWLIST`). Fails closed on `plugin_not_installed`, `plugin_revoked`, `plugin_runtime_not_allowlisted`, `plugin_runtime_image_unset`, `image_not_allowed`, `interpreter_not_allowed:*`, workspace/scope escapes, `plugin_sandbox:*` (e.g. `docker_unavailable`), and `plugin_sandbox_exit:<code>`.
- Artifacts are metadata only (execution id, plugin id, image, interpreter, `network_isolated=true`, return code, byte counts, `output_redacted=true`); container stdout/stderr never leaks. Every attempt records a `plugin_execution_records` row.
- Gate defaults `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires a HUMAN `runtime_gate_manager`, `local_single_user_runtime`, the registered executor, a `threat_model_acks` row (`docs/threat-models/plugin-sandboxed-runtime.md`), and a confirmation token.
- Deferred: in-process import isolation of plugin code in the host, and image build/pull management (the owner supplies and allowlists the image out of band).

Evidence: `tests/test_phase_4_plugin_sandboxed_runtime.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`, `scripts/validate_local_single_user_runtime.py`.

### Phase 5 Slice 1 — Capability decision modes (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| Ask / Deny / Allow / Auto decision modes (per-capability, layered on gates) | `implemented_policy_gated` | `raiker/runtime/authority/decision_modes.py`, `raiker/runtime/authority/router.py`, `raiker/control/service.py`, `raiker/storage/migrations.py` (`capability_decision_mode`), `raiker/cli/commands.py` (`/capability-mode`) | `tests/test_phase_5_decision_modes.py` |

- Adds a per-capability decision mode — **`ask` (default) / `deny` / `allow` / `auto`** — layered on top of the existing capability gate. The gate still governs *whether* a capability is enabled (integrated gates default enabled; no-executor gates disabled/fail-closed); the mode governs *how* an AI-proposed action on an enabled capability is treated. See `docs/DECISION_MODES_SPEC.md`.
- **Safety floors preserved:** PolicyEngine hard-denies still block first; critical-risk actions always require a human (`allow`/`auto` can never let an AI take a critical action); `auto` is deterministic and auditable (risk-keyed, no opaque model call in the trust decision); human principals self-authorize as before.
- **Governance:** setting a mode is human `runtime_gate_manager`-only (AI refused), audited via `capability_decision_mode_set`, persisted in the `capability_decision_mode` table (separate from `capability_gate_state`, so gate transitions never clobber the mode). Permissive modes (`allow`/`auto`) require a real executor — sensitive/no-executor domains are refused with `decision_mode_requires_executor` and can never be relaxed into acting.
- Approval resolution remains metadata-only; this slice adds no new capability and no new executor.

Evidence: `tests/test_phase_5_decision_modes.py`, `scripts/validate_repo_truthfulness.py`.

### Phase 6 Slice 1 — Local Tier-6 executors: reminder, calendar, email (`implemented_verified`)

| Capability | Status | Source | Tests |
|---|---|---|---|
| `reminder_runtime` (local reminder store: create/list) | `implemented_policy_gated` | `raiker/runtime/executors/reminders.py`, `raiker/storage/migrations.py` (`reminders`) | `tests/test_phase_6_reminder_runtime.py` |
| `calendar_runtime` (local calendar: create/list, no external sync/invite) | `implemented_policy_gated` | `raiker/runtime/executors/tier6_local.py`, `raiker/storage/migrations.py` (`calendar_events`) | `tests/test_phase_6_calendar_email_runtime.py` |
| `email_runtime` (local email drafts: draft/list/queue-send, never transmits) | `implemented_policy_gated` | `raiker/runtime/executors/tier6_local.py`, `raiker/storage/migrations.py` (`email_drafts`) | `tests/test_phase_6_calendar_email_runtime.py` |

- The first Tier-6 domains promoted to real executors — promoted **because** they are purely local personal-data stores (rows in the workspace `reminders` / `calendar_events` / `email_drafts` tables) with no network, no external sync/notification/delivery, and no device/hardware access. `email_runtime` **never transmits** — a `send` action only marks a draft `queued_for_send` (default `ask` mode asks the human first) so a human sends it; nothing leaves the machine. See `docs/threat-models/reminders.md`, `calendar.md`, `email.md`.
- **The remaining Tier-6 domains (finance, investment, medical, pregnancy/baby, cctv, home security, hardware) stay fail-closed** (`not_implemented`) until each has a real external integration and its own threat model — no fake executors.
- Each fails closed on missing/oversized required fields, bad argument types, and unknown actions. Create/list (and draft/list) only — no edit/delete, no outbound delivery, no OS scheduler/calendar registration. Runtime artifacts are metadata-only (ids/counts/flags); titles, locations, notes, subjects, recipients, and bodies are never emitted into events. Gates default `enabled_runtime`; re-enabling from a disabled/persisted non-default state requires HUMAN `runtime_gate_manager` + `local_single_user_runtime` + a `threat_model_acks` row + a confirmation token, and AI-proposed actions are further governed by the capability decision mode (default `ask`).

Evidence: `tests/test_phase_6_reminder_runtime.py`, `tests/test_phase_6_calendar_email_runtime.py`, `tests/test_executor_default_registry.py`, `scripts/validate_runtime_enablement_readiness.py`.

### Current launchable UI & runtime truth

The launchable local UIs are (1) the plain local terminal client (`RAIKER_TUI=plain`, `--prompt`,
or non-interactive stdin; Rich/native TUI is Phase 8 deferred) and (2) the local web dashboard —
the `apps/web` Svelte SPA served over the `raiker-web` loopback API (single-user, `127.0.0.1`
only). The web dashboard provides read-only governed views, the same governed
prompt/turn/approval/runtime-mutation flows as the CLI (approval resolution is metadata-only,
`executes_action=false`), and a step-up-gated Security Settings. Both surfaces route through the
Agent Gateway, ToolBroker, RuntimeAuthority, and PolicyEngine and add no runtime authority of their
own. Web dashboard parity for hosted/private model runtime is implemented: `/api/models`, the
Models view, and Security Settings surface hosted/private model gate state, off-machine profile
count, and whether `RAIKER_MODEL_EGRESS_ALLOWLIST` is configured, while never displaying allowlist
values or provider API keys and never probing network reachability on read. Desktop/Mobile apps, IDE extension, Voice, Browser Extension, and hosted/multi-user REST/API
remain specified/deferred, not implemented as launchable apps. Phase 3 is `implemented_verified`
only for safe foundation/readiness slices A-P; integrated real executors are governed per action and no-executor capabilities remain disabled/fail-closed. Phase 4 memory
MVP is implemented.

Integrated real executors are governed per action and default-ask; no-executor capabilities remain disabled/fail-closed.

### Phase 3 Slice A & B consolidated safety markers

These single-line markers are the canonical safety guarantees for the proposal-lifecycle (Slice A) and approval-planning-preview (Slice B) surfaces. They are intentionally unwrapped so tooling can assert them verbatim:

- Phase 3 Slice A proposal lifecycle foundation: implemented_verified. It is metadata-only and proposal-only with no proposal execution, no auto-fix, no patch application, no file mutation, no staging/unstaging, no test execution, no GitHub PR automation, no UI/API/IDE/dashboard/mobile, no approval execution, and no Phase 4; disabled runtime flags remain false.
- Phase 3 Slice B approval planning preview: implemented_verified. It is preview-only with no approval execution, no proposal execution, no auto-fix, no patch application, no file mutation, no staging/unstaging, no test execution, no GitHub PR automation, no UI/API/IDE/dashboard/mobile, and no Phase 4; disabled runtime flags remain false.

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter, OpenAI (`openai-hosted`), Google Gemini (`gemini-hosted-openai-compatible`, OpenAI-compatible endpoint), and Anthropic (`anthropic-hosted`, native Messages API adapter `raiker/models/providers/anthropic_messages.py` over raw httpx — no SDK) are hosted profiles requiring the `hosted_model_runtime` gate, the owner model-egress allowlist, an owner env API key, and budget policy metadata; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback. Every hosted profile requires an `api_key_env` with the key present (`hosted_api_key_missing` otherwise); Anthropic auth uses `x-api-key` + `anthropic-version`, OpenAI-compatible hosted providers use `Authorization: Bearer`.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled unless explicitly policy-enabled. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.

Manual e2e evidence (2026-07-04, local machine): `/model use --provider ollama --model gemma4:31b-cloud` persisted the selection and `raiker --prompt` completed a real gateway turn on that model (response returned; session events JSONL + checkpoint written). Ollama native OpenAI-compatible tool calls are enabled for the `ollama-local-openai-compatible` profile (`supports_tool_calls=true`, `tool_call_mode=native_or_text_json`); a live localhost probe against `qwen3.5:9b` returned `finish_reason=tool_calls`, `tool_call_count=1`, `first_tool_name=list_directory`, and Raiker's provider factory parsed the tool arguments as `{"path": "."}`. Hosted-provider live verification (2026-07-06, operator key): `anthropic-hosted` (`claude-opus-4-8`, native Messages adapter) is now `implemented_verified` against a live key. A governed turn ran through the real path — `hosted_model_runtime` gate enabled via the control plane (threat-model ack + confirmation token), provider policy derived from the persisted gates (`provider_runtime_policy_from_gates` → `allow_hosted_provider=true`), and the owner egress allowlist `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` enforced — and returned a completion (`finish_reason=stop`, usage `input_tokens=29 / output_tokens=17`). The egress guard was confirmed fail-closed in the same run: with an allowlist that excludes the host, provider construction raised `ProviderPolicyError: model_egress_denied:api.anthropic.com` (no call made). Only safe metadata is recorded here — no API key, prompt, or completion text. The remaining hosted profiles (`openai-hosted`, `gemini-hosted-openai-compatible`) stay offline/mock-verified (`implemented_unverified`) until an operator supplies their keys.

Config packaging fix (verified 2026-07-04): `ModelProfileRegistry.load()` and `ConnectorRegistry.load()` preserve workspace-local `config/` overrides, then fall back to bundled `raiker.config` JSON resources for non-editable installs and foreign working directories. `pyproject.toml` ships the packaged JSON as package data. Evidence: `tests/test_config_path_resolution.py` covers foreign cwd loading, packaged-resource fallback, and top-level/package resource drift; a local `pip wheel --no-deps --no-build-isolation` check confirmed the wheel contains `raiker/config/model-profiles.json` and `raiker/config/channel-connectors.json`.


## Async model runtime status (verified)

Status labels used by Raiker are `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Raiker now uses the real `httpx` package (`httpx.AsyncClient`) for async OpenAI-compatible provider transport. The repository-local `httpx.py` shim was removed and must not be restored. The OpenAI SDK and Pydantic are not used by this runtime.

Dependency decision: `httpx` is required and used. `fastapi` is deferred because this change does not implement a Raiker API/server surface. `langchain` is deferred because no governed adapter is implemented and it must not bypass Raiker tool, policy, approval, or event contracts. `llama-index` is deferred because no governed retrieval/indexing adapter is implemented and it must not bypass Raiker memory or provenance policy.

llama.cpp, Ollama, LM Studio, vLLM, generic OpenAI-compatible endpoints, and OpenRouter are represented through Raiker-owned async model-provider contracts. llama.cpp is the local-first native profile via the async OpenAI-compatible path. OpenRouter is hosted and policy-gated: it requires explicit hosted policy, egress and budget policy metadata, HTTPS, and a non-empty API key environment variable.

The deterministic provider is `test_only`; production gateways and normal CLI runtime do not fall back to it. If no real provider is configured or usable, runtime fails safely with a `no_real_model_provider_available`/provider-policy style error instead of silently switching to a mock or hosted backend. No silent local-to-hosted fallback is implemented. Provider support is offline-tested with `httpx.MockTransport`; real provider validation requires an operator-provided server or API key and was not performed here.

Model selection is session-scoped and persisted in the workspace SQLite store, and the selected profile is what subsequent prompts actually run on: the gateway resolves the persisted selection per turn and falls back to the native llama.cpp profile when none is set. `/model use` writes the selection, `/model current` reads it, and `/models` marks it. For local OpenAI-compatible providers that ship without a fixed model (Ollama, LM Studio), `/model use` auto-detects the served model from `/v1/models` when exactly one is available, or accepts an explicit `--provider/--model`; the resolved model is persisted (`model_session_state.model`). Reasoning controls are capability-gated. Private chain-of-thought is never exposed; any reasoning summary must be labeled as a summary, not raw reasoning. Model events use safe metadata only and must not include prompts, completions, stream chunks, Authorization headers, API keys, file contents, or tool outputs.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Plain terminal client | Line-oriented terminal client with `/help`, `/commands`, slash-command routing, and prompt submission. Rich/native TUI is Phase 8 deferred. | Yes | No direct tool authority; prompts route through gateway/broker/policy. | Implement richer clients only in Phase 8. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Launchable local web dashboard: `apps/web` Svelte SPA over the `raiker-web` loopback API. Read-only governed views + governed prompt/turn/approval/runtime-mutation flows (approval resolution metadata-only); single-user, `127.0.0.1` only. | Yes | No direct tool authority; routes through gateway/RuntimeAuthority/broker exactly as the CLI. | Keep API-contract + frontend test parity; broader clients stay deferred. |
| Dashboard | Read-only governed views are delivered as part of the local web dashboard above (capabilities, runtime mode, models, diagnostics). Standalone native/mobile dashboards remain Phase 8 deferred. | Yes (web) | None beyond the governed API. | Implement standalone dashboard apps after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Single-user, internet-accessible REST API (`raiker-web` / `apps.api`): bearer-token owner auth, configurable bind behind an explicit `--allow-public` opt-in (requires `RAIKER_OWNER_TOKEN`; TLS via reverse proxy), security headers, per-IP rate limit, body-size limit. Prompts tagged `web_ui` (bundled SPA) or `rest` (external clients); a CLI turn and a REST prompt sharing a `session_id` land in the same session. **Not** multi-user/hosted — every request authenticates as the one owner. | Yes | No direct tool authority; routes through gateway/RuntimeAuthority/broker exactly as the CLI. | Hosted/multi-user/tenant isolation stays deferred. |



Disabled runtime flags remain false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled, vector_writes_enabled, embedding_creation_enabled, cleanup_execution_enabled, rollback_execution_enabled, external_channels_enabled, notifications_enabled, remote_execution_enabled, container_execution_enabled, cloud_execution_enabled, process_execution_enabled, shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.
Executor enablement status: real local executors in `REAL_EXECUTOR_CAPABILITIES` are governed-flippable; deferred sensitive/external capabilities fail closed. See `docs/RUNTIME_EXECUTORS_SPEC.md`.


## Plain terminal client (implemented); Rich/native TUI deferred

Plain terminal client is `implemented_verified`: `raiker`, `raiker --prompt`, and `RAIKER_TUI=plain` route slash commands through `handle_slash_command()` and normal prompts through `submit_terminal_prompt()`. Rich/native TUI is Phase 8 deferred; the active Textual implementation and tests have been removed. All disabled runtime flags remain false.

---

## Phase 9 Advanced Memory & Graph Status

Phase 9 adds advanced memory and graph features: vector index, AST-based symbol extraction and dependency discovery, project-level graph extraction, and procedural-memory-to-skill-candidate conversion. Integrated execution remains policy-gated/default-ask; no-executor capabilities remain disabled/fail-closed.

| Task | Status | Source | Tests |
|---|---|---|---|
| RAIKER-9001 Vector index (upsert, search, chunk, flush) | `implemented_verified` | `raiker/vector/__init__.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| RAIKER-9101 Graph indexer (AST symbol extraction, import deps) | `implemented_verified` | `raiker/graph/indexer.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| RAIKER-9201 Project graph extractor (module map, dep graph, skill suggestions) | `implemented_verified` | `raiker/graph/project_graph.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| RAIKER-9301 Skill candidate store (propose, review, generate) | `implemented_verified` | `raiker/skills/__init__.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | `tests/test_phase_9_advanced_memory_graph.py` |
| CLI commands (`/vector-index`, `/symbol-graph`, `/project-graph`, `/skill-candidates`) | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_9_advanced_memory_graph.py` |

All features are in-memory runtime modules with SQLite persistence for records. No external vector DB or LLM calls are required. All disabled runtime flags remain false.
