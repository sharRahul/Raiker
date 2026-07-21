# Execution Breadth & User-Centric Zero Trust Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every slice follows the repo slice discipline: policy → contracts → storage → events → executor → tests → threat model → activation, with failing tests written first and `docs/IMPLEMENTATION_STATUS.md` updated only after verification.

**Goal:** Close the five execution-breadth gaps between the current runtime and the product vision — (A) approval relay beyond file writes, (B) checkpoint restore, (C) subagents, (D) richer surfaces, (E) external send/sync — under a User-Centric, Zero Trust operating model (F) in which verification is continuous and background-first, and human interaction is reserved for genuinely high-risk decisions.

**Architecture:** Every new capability is an executor behind an existing capability gate, routed through the existing `AgentGateway` → `RuntimeAuthority`/`ToolBroker` path. No new authority surfaces. Friction is reduced by widening the deterministic `DecisionMode.AUTO` path, adding scoped standing approvals with expiry, and adding asynchronous (non-blocking) approval delivery — never by removing verification, audit, or the critical-risk human-confirmation floor.

**Tech Stack:** Python 3.11, SQLite, FastAPI, httpx.AsyncClient, pytest, Svelte 5, TypeScript, Vitest.

---

## Security model mapping (User-Centric Zero Trust → Raiker primitives)

The owner's security policy is: Zero Trust ("never trust, always verify"), applied through a user-centric lens — controls run continuously and invisibly in the background, and security is an enabler, not a barrier. The canonical, normative policy text and its numbered requirements (ZT-1 … ZT-12) live in [`docs/USER_CENTRIC_ZERO_TRUST_POLICY.md`](../USER_CENTRIC_ZERO_TRUST_POLICY.md); slices in this plan cite those IDs. It maps onto Raiker as follows:

| Zero Trust policy element | Raiker mechanism (existing → planned) |
|---|---|
| Never trust, always verify | Every action already passes gate → policy → risk → decision mode → event log. **Planned:** the same path for approved-action execution, restore, subagent steps, and external sends — no bypass lanes. |
| Continuous, invisible verification | Hash-chained event log + integrity verifier exist. **Planned:** a background integrity/posture sweep (event chain, session validity, egress-allowlist drift) that runs per turn and per schedule, surfacing only on failure. |
| Identity & device posture | Local accounts, Argon2id/scrypt, TOTP MFA, server-authoritative session state exist. **Planned:** per-session posture snapshot (auth strength, MFA freshness, interface) recorded on each governed action; step-up (re-auth/TOTP) required only when risk elevates. |
| Frictionless by default | `DecisionMode.AUTO` already runs low-risk actions unprompted deterministically. **Planned:** scoped standing approvals ("allow this action shape for this session/project until *expiry*") so users answer a class of prompt once, not per action. |
| No arbitrary administrative barriers | All grants are user-owned (owner/`runtime_gate_manager`), reversible, and inspectable in the dashboard; nothing requires an external administrator. |
| Security at the point of interaction | Approval prompts carry redacted, metadata-only previews at the moment of the action; asynchronous delivery (dashboard notification / channel relay) replaces modal blocking. |
| Human in control at the top of the risk ladder | **Planned (F6–F7):** critical-risk actions are classified in production code, always notify the owner, and resolve only by a live human's manual approve/reject. Their resting state is deny: silence, expiry, delegation, or any non-human resolution denies. |

**Invariants that this plan does not relax (design decision, stated up front):** the critical-risk human-confirmation floor, PolicyEngine hard-denies (secret-like memory, workspace boundary), fail-closed no-executor capabilities, environment-only credentials + egress allowlists, and append-only hash-chained audit. "Frictionless" is implemented as *fewer, better-scoped, asynchronous* decisions — not as silent execution of high-risk actions. Where the policy's "invisible" language meets a critical-risk action, visibility wins.

**Critical-risk rule (owner decision, 2026-07-19):** the critical floor is strengthened from today's flat deny into an explicit human-decision lifecycle. A critical action's **resting state is deny**; the only event that can change its outcome is a notified human manually approving it. No decision mode (`allow`/`auto`), standing grant, scheduled routine, subagent, or relay may ever resolve a critical approval — grants carry a risk ceiling strictly below critical by construction. Silence, TTL expiry, session revocation, or any non-human resolution attempt resolves to deny. This is deliberately *more* visible than the current router behavior (which denies AI-proposed critical actions without telling the owner): the human always sees the request, always decides it, and nothing executes until they do.

**Assumptions:**
- Assumes the local single-user / multi-account-per-machine deployment model — this plan does NOT cover hosted multi-tenant Raiker.
- Assumes standing approvals are scoped grants with mandatory expiry — there is NO permanent "always allow everything" grant.
- Assumes external send/sync starts with one governed connector per domain (SMTP-less: Gmail connector send; CalDAV-less: Google Calendar connector sync) before generalizing.

---

## Workstream A — Generalized approval execution relay (approve → execute for all executed capabilities)

Today `ApprovalExecutionRelay` (`raiker/runtime/executors/tier1_approval.py`) executes only `write_file`-shaped approvals; `/approve` and the dashboard queue are metadata-only. This workstream makes "execute approved actions" true for every capability that already has a real executor.

**Files:**
- Modify: `raiker/runtime/executors/tier1_approval.py` (generalize to an executor-dispatching relay)
- Modify: `raiker/storage/sqlite.py` (approval intent snapshot: immutable arguments hash, TTL, single-execution nonce)
- Modify: `raiker/runtime/authority/router.py` (route `approval_execute` through the target action's own gate + decision mode, not just the relay's)
- Modify: `raiker/api/routes_approvals.py`, `raiker/cli/commands.py` (`/approve --execute`, dashboard "Approve & run")
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte` (explicit two-step: record decision / approve-and-run)
- Test: `tests/test_api_approvals.py`, new `tests/test_approval_relay_general.py`
- Threat model: `docs/threat-models/approval-execution-relay.md` (new)

**Slices:**
- [x] A1. **Immutable approval intent.** Store a SHA-256 of the proposed action's canonical arguments at creation; the relay refuses to execute if the stored hash no longer matches (TOCTOU defense). Add `expires_at` to approvals (default 24h); expired approvals resolve `expired`, never execute. *(Done 2026-07-19: `insert_approval` sets a default 24h `expires_at` and the immutable `action_payload_sha256`; `ApprovalExecutionRelay` re-verifies the hash and TTL at execution time — `approval_payload_tampered` / `approval_expired`; `expire_approval` transitions pending→expired; `ApprovalInbox.resolve` + the API enforce the same TTL. Tests: `tests/test_approval_relay_general.py`, `tests/test_api_approvals.py::test_expired_approval_rejected`. Threat model: `docs/threat-models/approval-execution-relay.md`.)*
- [x] A2. **Executor dispatch.** Relay resolves the approved action's `action_type` → capability gate → registered executor via `ExecutorRegistry`; execution runs under the *target* capability's gate state, decision mode, and PolicyEngine review at execution time (re-verified, not trusted from approval time). Single-execution enforced by an atomic `pending → executing → executed` state transition in SQLite. *(Done 2026-07-20: the relay re-routes the approved action through `RuntimeAuthority.route_action` as the approving human, so the target runs under its own gate/mode/policy at execution time; `claim_approval_for_execution`/`finalize_approval_execution`/`release_approval_claim` implement the atomic state machine; a relay may never target another relay. Tests: `test_relay_dispatches_memory_write_end_to_end`, `test_relay_executes_at_most_once`, `test_relay_rejects_claimed_approval`, `test_relay_refuses_disabled_target_gate_and_releases`, `test_relay_cannot_target_another_relay`.)*
- [x] A3. **Coverage.** Extend beyond `write_file` to `edit_file`, `apply_patch`, `memory_write`, `memory_forget`, then Tier-2 `shell`/`process`/`web_fetch`/`network` (Tier-2 execution additionally requires the existing threat-ack + human confirmation token — unchanged). *(Done 2026-07-20: dispatch is generic — any mapped capability with a registered executor is reachable; Tier-2 targets still require their (threat-ack-gated) gate enabled, and critical-risk targets hit the human-confirmation floor and do not execute via the relay. Tests: `test_relay_dispatches_apply_patch`, `test_relay_dispatches_memory_write_end_to_end`, `test_relay_dispatches_tier2_shell`.)*
- [x] A4. **Zero-trust hooks.** Emit `approval_executed` events with posture snapshot (principal, session, interface, MFA age); deny with `posture_degraded` if the approving session was revoked between approval and execution. *(Done 2026-07-20: `raiker/runtime/authority/posture.py::capture_posture` builds a metadata-only snapshot recorded on `approval_executed`/`approval_execution_denied`; a revoked approving session denies with `posture_degraded:session_revoked` before any claim. MFA age is recorded as `mfa_enrolled` pending F1's richer freshness signal. Tests: `test_relay_emits_approval_executed_with_posture`, `test_relay_denies_revoked_session`.)*

**Does NOT cover:** approving actions for capabilities with no real executor (they stay `activation_blocked:no_executor`), or batch/blanket approval of heterogeneous actions.

---

## Workstream B — Checkpoint restore & rewind

`CheckpointService.plan_restore`/`plan_fork` return `can_execute: False`. This workstream makes checkpoints restorable, which also gives every other workstream a safety net (undo).

**Files:**
- Modify: `raiker/checkpoints/service.py` (content-addressed file snapshots + restore/fork execution)
- New: `raiker/runtime/executors/tier1_checkpoint.py` (`checkpoint_restore_execution` executor)
- Modify: `raiker/phase_gates.py` (new `checkpoint_restore_execution` gate, Tier 1, default per readiness)
- Modify: `raiker/storage/sqlite.py` (snapshot manifest tables), `raiker/cli/commands.py` (`/checkpoints restore`), `apps/web/src/lib/views/CheckpointsView.svelte`
- Test: new `tests/test_checkpoint_restore.py`; extend `tests/test_checkpoints.py`
- Threat model: `docs/threat-models/checkpoint-restore.md` (new)

**Slices:**
- [x] B1. **Capture.** On each mutation executed through the broker/relay, record pre-image blobs (content-addressed, workspace-scoped, size-capped) into `.raiker/checkpoints/objects/`; checkpoint manifests reference blob hashes. Metadata-only events (no file content in the log). *(Done 2026-07-20: `raiker/checkpoints/capture.py::CheckpointCaptureService` snapshots the target file's pre-image before a file-mutating executor runs and, on success, stores it as a content-addressed blob under `.raiker/checkpoints/objects/<aa>/<sha256>` (deduplicated, atomic write) plus a metadata-only `checkpoint_capture_manifest` row; `RuntimeAuthority.route_action` calls it at the single executor-dispatch chokepoint — covering both direct broker writes and the Workstream A relay — and emits a metadata-only `checkpoint_captured` event. `capture_status` ∈ {`captured`, `absent`, `oversize`}; capture is workspace-scoped, size-capped (8 MiB), best-effort (a failure records `checkpoint_capture_failed` and never blocks the mutation), and only the two file-mutating Tier-1 capabilities are eligible. Tests: `tests/test_checkpoint_restore.py`. Threat model: `docs/threat-models/checkpoint-restore.md`.)*
- [x] B2. **Restore executor.** `checkpoint_restore` is an approval-required governed action (it is itself a mutation): dry-run diff preview first (metadata-only), then restore only files recorded in the manifest, refusing paths outside the workspace. A restore writes its *own* pre-image first, so restores are themselves reversible. *(Done 2026-07-20: `raiker/runtime/executors/tier1_checkpoint.py::CheckpointRestoreExecutor` (capability `checkpoint_restore_execution`, Tier 1, real executor → gate enabled by default) rewinds a checkpoint by restoring each file's B1 pre-image; `CheckpointService.compute_restore_plan`/`plan_restore` produce a metadata-only per-file dry-run diff (op ∈ {`restore_content`,`delete`,`skip_oversize`}, content-addresses + sizes, no content). The executor re-derives the plan at execution time (trusts only `checkpoint_id`), re-resolves each path against the workspace (skips escapes), re-verifies each pre-image blob against its content-address (skips missing/tampered), and captures its *own* pre-image before overwriting/deleting so restores are reversible. `checkpoint_restore` is approval-required in the PolicyEngine + default-`ask` decision mode, so an AI only proposes it; a human approval runs it through the Workstream A relay. CLI `/checkpoints restore <id>` renders the dry-run preview. Tests: `tests/test_checkpoint_restore.py`, `tests/test_checkpoints.py`, `tests/test_phase_2_terminal_commands.py`. Threat model: `docs/threat-models/checkpoint-restore.md`.)*
- [x] B3. **Fork.** `plan_fork` materializes a new session seeded from the checkpoint's state summary + memory candidates; no file mutation. *(Done 2026-07-20: `CheckpointService.plan_fork` is now a metadata-only preview (`can_execute: True`, `requires_approval: False` — fork mutates no workspace files) and `CheckpointService.execute_fork` materializes a fresh session (`SessionManager`/`store.create_session`) seeded from the checkpoint's `_fork_seed` — its state summary + memory candidates read best-effort from the manifest (a missing/corrupt manifest degrades to an empty seed, never a failure). A metadata-only fork manifest under `.raiker/checkpoints/forks/<session_id>.json` records lineage + seed (`load_fork_seed` reads it back); no workspace file is written or overwritten. CLI `/checkpoints fork <id>` runs the fork directly (low-risk, non-approval) and reports the new session. Tests: `tests/test_checkpoints.py` (preview, materialize-and-seed, no-workspace-mutation, unknown-checkpoint), `tests/test_phase_2_terminal_commands.py` (CLI fork + unknown).)*
- [ ] B4. **Zero-trust hooks.** Restore counts as medium risk (auto-mode asks); a restore that would touch files modified by a *different* principal since the checkpoint escalates to high risk.

**Does NOT cover:** restoring state outside the workspace (global config, SQLite history rewrites — the event log is append-only and is never rewound), or cross-machine restore.

---

## Workstream C — Subagents & bounded teams activation

`SubagentRunner`/`TeamCoordinator` (`raiker/agents/orchestration.py`) already execute bounded read-only steps; the `subagents`/`multi_agent_teams` gates default disabled and `plan_subagent` returns `can_spawn=False`. This workstream wires planner-driven spawning with parent-inherited governance.

**Files:**
- Modify: `raiker/agents/subagents.py` (real spawn decision: budget + capability subset), `raiker/agents/orchestration.py`
- Modify: `raiker/runtime/planner.py`, `raiker/runtime/orchestrator.py` (planner may propose subagent steps; orchestrator runs them via TeamCoordinator)
- Modify: `raiker/runtime/authority/router.py` (subagent principals are AI principals with a *subset* of the parent's effective capabilities — never more)
- Modify: `raiker/cli/commands.py` (`/subagents run`), `apps/web/src/lib/views/WorkInActionView.svelte` (live subagent step stream)
- Test: extend `tests/test_advisor_model.py` patterns into new `tests/test_subagent_activation.py`
- Threat model: update `docs/threat-models/subagents.md`

**Slices:**
- [x] C1. **Budgets.** Per-spawn budget record (max steps, max tool calls, wall-clock cap, token cap) persisted and enforced by `SubagentRunner`; exceeding a budget fails the subagent closed, never silently truncates. *(Done 2026-07-20: `raiker/agents/orchestration.py::SubagentBudget` is the four-dimension per-spawn record — steps, tool calls, wall-clock, and estimated tokens — whose `effective()` clamps caller values *down* to the process-wide hard caps (`MAX_SUBAGENT_STEPS`/`MAX_SUBAGENT_TOOL_CALLS`/`MAX_SUBAGENT_TOKENS`) and never up. `SubagentRunner.run` enforces every dimension and fails closed on a breach — `subagent_step_budget_exceeded`, `subagent_tool_call_budget_exceeded` (checked before each dispatch), `subagent_time_budget_exceeded`, `subagent_token_budget_exceeded` (deterministic ~4-char/token estimate via `estimate_step_tokens`) — never silently truncating. The budget persists on the contract (`SubagentContract.max_steps/max_tool_calls/max_tokens`, migration `RAIKER-1303-subagent-budgets`) and rides the metadata-only outcome artifacts. Tests: `tests/test_subagent_activation.py` (clamping, parse defaults/overrides, persistence, within-budget, tool-call fail-closed, token fail-closed).)*
- [ ] C2. **Capability subsetting.** A subagent's principal is created with an explicit capability subset ⊆ parent's; mutation proposals from subagents are routed into the *parent's* approval queue (subagents never approve, never relay).
- [ ] C3. **Planner integration.** Classifier/planner can emit a `subagent_plan` for decomposable read/research tasks; gate flip (`subagents` → enabled) stays owner-only; decision mode default `ask`, with `auto` allowing read-only subagents unprompted (low risk).
- [ ] C4. **Teams.** Enable `multi_agent_teams` for sequential teams only (existing `MAX_TEAM_MEMBERS` bound); aggregate outcomes remain metadata-only.

**Does NOT cover:** recursive spawning (subagents spawning subagents), parallel team execution, or cross-workspace subagents.

---

## Workstream D — Richer surfaces (Phase 8, brought forward incrementally)

The launchable surfaces are the plain terminal client and the web dashboard. Ordered by leverage-per-effort, each new surface is a *client* of the existing loopback API — surfaces add zero authority (the invariant that made the web dashboard safe).

**Slices:**
- [ ] D1. **Rich TUI.** Textual-based client behind `RAIKER_TUI=rich` (Rich/Textual become optional extras, not runtime deps for the plain path): streaming turn phases, inline approval queue with redacted previews, model/status bar. Reuses the gateway exactly like the plain client. (`raiker/terminal/`, new `tests/test_rich_tui.py`.)
- [x] D2. **Async approval notifications.** Dashboard notification center + OS-level notification hook so approvals never block a flow: the agent parks the turn (`WAITING_FOR_APPROVAL` already exists), the user approves from any surface, Workstream A's relay resumes execution. This is the single highest-impact friction reducer. *(Done 2026-07-20: `raiker/notify/approval_notifier.py::notify_approval_pending` resolves the owner (AI/automation → the instance owner account) and inserts an owner-scoped `approval_pending` row into the existing `notifications` table (surfaced by the dashboard notification center / `GET /api/notifications`), then fires an optional OS-level hook — a best-effort, env-gated (`RAIKER_OS_NOTIFY_CMD`), fully-isolated shell-out passed only redacted metadata copy. Wired into the ToolBroker approval-creation path so every parked AI-proposed approval notifies the owner without blocking the turn; Workstream A's relay is the resume path. Tests: `tests/test_approval_notifications.py`.)*
- [ ] D3. **Desktop shell.** Package `raiker-web` + SPA in a desktop webview shell (`docs/DESKTOP_DISTRIBUTION_DESIGN.md` is the base): single binary, loopback-only, OS keychain for the vault key (replaces env-var-only credentials — also serves Workstream E).
- [ ] D4. **IDE surface.** VS Code extension speaking to the loopback API: read-only views + prompt submission first; workspace mutation stays in the governed relay path.
- [ ] D5. Mobile/voice/browser-extension remain deferred (documented, fail-closed) until D1–D4 are verified.

**Does NOT cover:** any surface authenticating with more privilege than a dashboard session, or remote (non-loopback) exposure of the API.

---

## Workstream E — External send/sync (email, calendar, reminders)

Tier-6 stores are local-only by design. This workstream adds *outbound* execution as governed connector actions, keeping the local store as the source of truth and the draft → approve → send lifecycle as the only path.

**Files:**
- Modify: `raiker/runtime/executors/tier6_local.py` + new `raiker/runtime/executors/tier6_external.py`
- Modify: `raiker/runtime/executors/connectors.py` (Gmail send, GCal event write, reminder push)
- Modify: `raiker/phase_gates.py` (new `email_send_execution`, `calendar_sync_execution`, `reminder_push_execution` gates — separate from the local-store gates so local use never silently gains egress)
- Modify: `apps/web/src/lib/views/ConnectionsView.svelte`, `config/channel-connectors.json`
- Test: new `tests/test_external_send.py`; extend `tests/test_gmail_connector.py`, `tests/test_gcal_connector.py`
- Threat models: update `docs/threat-models/email.md`, `docs/threat-models/calendar.md`, add `docs/threat-models/external-send.md`

**Slices:**
- [ ] E1. **Draft → approve → send.** Outbound email is only creatable from an existing local draft; the send action carries the draft's content hash (immutable intent, same defense as A1). Send requires: gate enabled + connector credential in vault + recipient on a per-account recipient allowlist (globs allowed, empty default = fail closed) + approval (decision mode `ask`; `auto` treats known-recipient, no-attachment sends as medium → still asks initially, owner can grant a scoped standing approval per E3).
- [ ] E2. **Calendar sync + invites.** Two-way sync via the GCal connector: pull is read-only (low risk, auto-run); push (create/update/invite) follows the E1 lifecycle. Invite sends to non-allowlisted attendees escalate to high risk.
- [ ] E3. **Scoped standing approvals** (shared with Workstream F): "allow sends to `*@my-company.com` for 30 days" — persisted grant with expiry, listed and revocable in Security Settings, every use logged with the grant id.
- [ ] E4. **Reminder push.** Local reminders can arm OS-level notifications through the desktop shell (D3); no third-party reminder service.

**Does NOT cover:** raw SMTP/IMAP, bulk send, contact scraping, or auto-reply loops (inbound mail never triggers outbound send without a human-approved rule).

---

## Workstream F — Continuous background verification (the Zero Trust layer)

Cross-cutting; starts immediately and lands with each workstream above.

- [x] F1 (ZT-3). **Posture snapshot on every governed action:** principal, session age, auth strength, MFA freshness, interface, decision-mode/grant used — appended to the existing event payloads (metadata-only). Powers A4/B4 escalation rules. *(Done 2026-07-20: `raiker/runtime/authority/posture.py::capture_posture` now derives `auth_strength` (mfa/password) alongside the existing identity/session/mfa/interface/session-age fields; `RuntimeAuthority._capture_action_posture` extends it with the decision path — the `decision_mode` that governed the action and the `grant_id` that authorized any unprompted run — and `route_action` attaches the snapshot to every `action_executed`/`action_failed` event and to `standing_grant_applied`. Metadata-only; never a token/secret/content. Tests: `tests/test_posture_snapshot.py`.)*
- [ ] F2 (ZT-4). **Background integrity sweep:** a scheduled routine (existing `scheduled_routines` executor) that re-verifies the event hash chain, session validity, gate/decision-mode drift vs. the owner's saved baseline, and egress-allowlist changes. Silent when green; raises a dashboard notification (D2) only on deviation — "invisible until it matters."
- [x] F3 (ZT-5). **Scoped standing approvals engine:** one grant model shared by A/C/E — `(principal, action shape, scope pattern, risk ceiling, expires_at)`; grants can only *narrow* from a human-made decision, are always listed in Security Settings, and expire by default in 7 days. Replaces repeated identical prompts (the actual "frictionless" mechanism). *(Done 2026-07-20: `raiker/runtime/authority/grants.py` holds the `StandingGrant` model + `build_grant_record`/`grant_covers` (human-created only, sub-critical ceiling by construction, mandatory 7-day default expiry, scope-glob + risk-ceiling matching, critical never covered); migration `RAIKER-1301-standing-grants` + `SQLiteStore` insert/list/find/revoke/use methods persist them; `RuntimeAuthority.{create,list,revoke}_standing_grant` + `find_matching_standing_grant` enforce the invariants, and `route_action` lets an active matching grant satisfy an AI-proposed sub-critical action's approval requirement (logging `standing_grant_applied` with the grant id + posture and bumping `use_count`); `RuntimeControlService` + `POST/GET /api/standing-grants[/revoke]` + a Standing-Grants panel in the Security & Login settings surface make them visible/revocable. Grant *creation* is F6 criterion (d) critical. Tests: `tests/test_standing_grants.py`, `tests/test_api_standing_grants.py`, `SecurityLogin.test.ts`.)*
- [ ] F4 (ZT-6). **Step-up verification:** when a grant or `auto` decision would cover an action whose computed risk exceeds the grant's ceiling (posture degraded, new recipient, out-of-scope path), require fresh TOTP/re-auth instead of failing outright — verify harder, not block harder.
- [ ] F5. **Truthfulness gates:** extend `scripts/validate_runtime_enablement_readiness.py` so every new gate above must have executor + tests + threat model before `allow`/`auto` becomes selectable (mechanically enforcing "documentation never runs ahead of code").
- [x] F6 (ZT-7). **Production critical-risk classification.** Today `RiskLevelValue.CRITICAL` is assigned only in tests — the router floor (`raiker/runtime/authority/router.py`) has no production callers routing to it. Land a canonical, in-code classification table (new `raiker/runtime/authority/critical.py`, consumed by the router's risk resolution) so `critical` is a real production tier. Initial criteria — an action is critical when it matches any of:
  - (a) enabling or relaxing Tier-2 execution (shell / process / network / web-fetch), including threat-model acknowledgments and confirmation-token issuance;
  - (b) an external send or calendar invite to any recipient/attendee not on the account's allowlist (Workstream E);
  - (c) a checkpoint restore that would overwrite changes made by a different principal since the checkpoint (Workstream B);
  - (d) creating or broadening a standing approval grant (F3) — grants are born from a critical, human-decided action, which is what makes their later unprompted use legitimate;
  - (e) any operation on vault/credential material or on an egress allowlist.
  The table is data, not scattered conditionals; it ships with tests proving each criterion routes to the floor, and it may only be *extended* (never narrowed) without a threat-model note — enforced by the F5 validator. *(Done 2026-07-20: `raiker/runtime/authority/critical.py::classify_critical` is the data-driven table (five stable criterion codes, each `zt_ref`-tagged, matched over frozen action-type/tool/argument sets); `RuntimeAuthority.route_action` calls it during risk resolution — before policy review and decision-mode resolution — so a matching action (or an explicitly-CRITICAL one) routes to the human-confirmation floor and dominates every other outcome (AI → deny, human → `needs_human_confirmation`), emitting `critical_action_classified`. No decision mode, standing grant, or subagent can resolve it. Tests: `tests/test_critical_classification.py` prove each of (a)-(e) routes to the floor and that near-misses do not. F5-validator enforcement of the extension-only invariant lands with F5 (M6).)*
- [x] F7 (ZT-7). **Critical approval lifecycle: notify → manual human decision → default deny.** Replace the router's current silent flat-deny of AI-proposed critical actions with a parked `pending_critical` approval that always notifies the owner (D2: dashboard notification center, OS notification via the desktop shell, channel relay where enabled). Resolution rules, enforced in `RuntimeAuthority` and covered by tests:
  - Only a live human principal may resolve it, and approval requires step-up verification (fresh TOTP/re-auth when MFA is stale) before the Workstream A relay executes it with execution-time re-verification and posture check.
  - Manual reject, TTL expiry (default 24 h), revocation of the approving session, or any resolution attempt by a non-human principal resolves to **deny**.
  - No decision mode, standing grant, scheduled routine, or subagent can resolve or pre-authorize a critical approval; the resting state of every critical action is deny, and absence of an explicit human approval always means deny.
  - Every transition (`created → notified → resolved/expired`) is an audit event carrying the posture snapshot (F1), so "who was in control, when" is reconstructable from the log alone.

  *(Done 2026-07-20: `RuntimeAuthority.route_action` now parks any critical action (F6 table match or explicit `CRITICAL` risk) as a `critical`-flagged approval (`_park_critical_action`) — immutable `action_payload_sha256` + 24 h TTL — always notifying the owner (`raiker/notify/approval_notifier.py::notify_critical_approval_pending`, distinct `critical_approval_pending` kind) and emitting `critical_approval_created`/`critical_approval_notified` with the F1 posture snapshot; the AI-proposed silent flat-deny is gone. `RuntimeAuthority.resolve_critical_approval` is the only path off the deny resting state: human-only (a non-human attempt resolves `denied`), TTL + TOCTOU + revoked-session re-checked, manual reject/expiry/tamper/degraded-posture → deny, and approval requires step-up (`step_up_verified`; MFA-enrolled ⇒ required pending F4's freshness signal — approval stays `pending`/`needs_step_up` otherwise). An approved+step-up decision issues a one-shot `CriticalConfirmation` and executes through the Workstream A relay, which carries it onto the re-governed target so it clears the deny floor exactly once while still running under the target's own gate/policy/decision-mode/posture at execution time; `_critical_confirmation_valid` (human principal + claimed-`executing` critical approval) blocks any forged or AI-supplied confirmation. Migration `RAIKER-1302-critical-approval-lifecycle` adds the `critical` approval column. Tests: `tests/test_critical_lifecycle.py`; classification/decision-mode/grant tests updated to the parked behavior. Threat model: `docs/threat-models/critical-approval-lifecycle.md`.)*

---

## Milestone 3 completion update (2026-07-21)

M3 is complete: C2 records a separate bounded AI principal and parks mutations
for parent approval; C3 emits low-risk read-only `subagent_plan` steps; B4
derives cross-principal restore escalation from capture manifests; F2 adds the
silent-on-green scheduled integrity sweep. Evidence is in
`tests/test_subagent_activation.py`, `tests/test_milestone_3.py`,
`tests/test_checkpoint_restore.py`, and `tests/test_integrity_sweep.py`.

## Sequencing & milestones

| Milestone | Contents | Exit criteria |
|---|---|---|
| M1 ✅ | A1–A2, F1, F3 (grant model), F6 (critical classification), D2 (notifications) | An approved non-file action executes end-to-end; grants visible/revocable; every F6 criterion provably routes to the critical floor; full suite + validators green — **complete 2026-07-20** |
| M2 ✅ | A3–A4, B1–B2, F7 (critical lifecycle) | Tier-2 approve-and-run behind threat-ack; restore with pre-image undo proven by tests; critical actions notify + resolve only by manual human decision, defaulting to deny — **complete 2026-07-20** |
| M3 | C1–C3, B3–B4, F2 | Read-only subagents runnable under budget; background sweep shipping |
| M4 | E1–E3, D1 | First real external email send + calendar push through draft→approve→send; rich TUI launchable |
| M5 | D3, E4, C4, F4 | Desktop shell with keychain vault; step-up flows; teams enabled |
| M6 | D4, F5, docs/ledger reconciliation | IDE surface; `docs/IMPLEMENTATION_STATUS.md`, `docs/GAP_AND_TODO_ANALYSIS.md`, `README.md` updated to the new truthful state |

Each milestone ends with the full local validation gate (`ruff`, `mypy`, `pytest`, both truthfulness validators, licensing check, web lint/check/test/build) and a recorded verification entry in `docs/IMPLEMENTATION_STATUS.md`.

## Explicit non-goals

- Hosted/multi-tenant Raiker, remote/cloud command execution, and the finance/investment/medical/pregnancy/CCTV/home-security/hardware domains stay fail-closed (each needs its own per-domain threat model first).
- No removal of the critical-risk human-confirmation floor, PolicyEngine hard-denies, egress allowlists, or append-only audit — the Zero Trust layer tunes *when* a human is asked, never *whether* verification happens.
