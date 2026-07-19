# Execution Breadth & User-Centric Zero Trust Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every slice follows the repo slice discipline: policy → contracts → storage → events → executor → tests → threat model → activation, with failing tests written first and `docs/IMPLEMENTATION_STATUS.md` updated only after verification.

**Goal:** Close the five execution-breadth gaps between the current runtime and the product vision — (A) approval relay beyond file writes, (B) checkpoint restore, (C) subagents, (D) richer surfaces, (E) external send/sync — under a User-Centric, Zero Trust operating model (F) in which verification is continuous and background-first, and human interaction is reserved for genuinely high-risk decisions.

**Architecture:** Every new capability is an executor behind an existing capability gate, routed through the existing `AgentGateway` → `RuntimeAuthority`/`ToolBroker` path. No new authority surfaces. Friction is reduced by widening the deterministic `DecisionMode.AUTO` path, adding scoped standing approvals with expiry, and adding asynchronous (non-blocking) approval delivery — never by removing verification, audit, or the critical-risk human-confirmation floor.

**Tech Stack:** Python 3.11, SQLite, FastAPI, httpx.AsyncClient, pytest, Svelte 5, TypeScript, Vitest.

---

## Security model mapping (User-Centric Zero Trust → Raiker primitives)

The owner's security policy is: Zero Trust ("never trust, always verify"), applied through a user-centric lens — controls run continuously and invisibly in the background, and security is an enabler, not a barrier. This maps onto Raiker as follows:

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
- [ ] A1. **Immutable approval intent.** Store a SHA-256 of the proposed action's canonical arguments at creation; the relay refuses to execute if the stored hash no longer matches (TOCTOU defense). Add `expires_at` to approvals (default 24h); expired approvals resolve `expired`, never execute.
- [ ] A2. **Executor dispatch.** Relay resolves the approved action's `action_type` → capability gate → registered executor via `ExecutorRegistry`; execution runs under the *target* capability's gate state, decision mode, and PolicyEngine review at execution time (re-verified, not trusted from approval time). Single-execution enforced by an atomic `pending → executing → executed` state transition in SQLite.
- [ ] A3. **Coverage.** Extend beyond `write_file` to `edit_file`, `apply_patch`, `memory_write`, `memory_forget`, then Tier-2 `shell`/`process`/`web_fetch`/`network` (Tier-2 execution additionally requires the existing threat-ack + human confirmation token — unchanged).
- [ ] A4. **Zero-trust hooks.** Emit `approval_executed` events with posture snapshot (principal, session, interface, MFA age); deny with `posture_degraded` if the approving session was revoked between approval and execution.

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
- [ ] B1. **Capture.** On each mutation executed through the broker/relay, record pre-image blobs (content-addressed, workspace-scoped, size-capped) into `.raiker/checkpoints/objects/`; checkpoint manifests reference blob hashes. Metadata-only events (no file content in the log).
- [ ] B2. **Restore executor.** `checkpoint_restore` is an approval-required governed action (it is itself a mutation): dry-run diff preview first (metadata-only), then restore only files recorded in the manifest, refusing paths outside the workspace. A restore writes its *own* pre-image first, so restores are themselves reversible.
- [ ] B3. **Fork.** `plan_fork` materializes a new session seeded from the checkpoint's state summary + memory candidates; no file mutation.
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
- [ ] C1. **Budgets.** Per-spawn budget record (max steps, max tool calls, wall-clock cap, token cap) persisted and enforced by `SubagentRunner`; exceeding a budget fails the subagent closed, never silently truncates.
- [ ] C2. **Capability subsetting.** A subagent's principal is created with an explicit capability subset ⊆ parent's; mutation proposals from subagents are routed into the *parent's* approval queue (subagents never approve, never relay).
- [ ] C3. **Planner integration.** Classifier/planner can emit a `subagent_plan` for decomposable read/research tasks; gate flip (`subagents` → enabled) stays owner-only; decision mode default `ask`, with `auto` allowing read-only subagents unprompted (low risk).
- [ ] C4. **Teams.** Enable `multi_agent_teams` for sequential teams only (existing `MAX_TEAM_MEMBERS` bound); aggregate outcomes remain metadata-only.

**Does NOT cover:** recursive spawning (subagents spawning subagents), parallel team execution, or cross-workspace subagents.

---

## Workstream D — Richer surfaces (Phase 8, brought forward incrementally)

The launchable surfaces are the plain terminal client and the web dashboard. Ordered by leverage-per-effort, each new surface is a *client* of the existing loopback API — surfaces add zero authority (the invariant that made the web dashboard safe).

**Slices:**
- [ ] D1. **Rich TUI.** Textual-based client behind `RAIKER_TUI=rich` (Rich/Textual become optional extras, not runtime deps for the plain path): streaming turn phases, inline approval queue with redacted previews, model/status bar. Reuses the gateway exactly like the plain client. (`raiker/terminal/`, new `tests/test_rich_tui.py`.)
- [ ] D2. **Async approval notifications.** Dashboard notification center + OS-level notification hook so approvals never block a flow: the agent parks the turn (`WAITING_FOR_APPROVAL` already exists), the user approves from any surface, Workstream A's relay resumes execution. This is the single highest-impact friction reducer.
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

- [ ] F1. **Posture snapshot on every governed action:** principal, session age, auth strength, MFA freshness, interface, decision-mode/grant used — appended to the existing event payloads (metadata-only). Powers A4/B4 escalation rules.
- [ ] F2. **Background integrity sweep:** a scheduled routine (existing `scheduled_routines` executor) that re-verifies the event hash chain, session validity, gate/decision-mode drift vs. the owner's saved baseline, and egress-allowlist changes. Silent when green; raises a dashboard notification (D2) only on deviation — "invisible until it matters."
- [ ] F3. **Scoped standing approvals engine:** one grant model shared by A/C/E — `(principal, action shape, scope pattern, risk ceiling, expires_at)`; grants can only *narrow* from a human-made decision, are always listed in Security Settings, and expire by default in 7 days. Replaces repeated identical prompts (the actual "frictionless" mechanism).
- [ ] F4. **Step-up verification:** when a grant or `auto` decision would cover an action whose computed risk exceeds the grant's ceiling (posture degraded, new recipient, out-of-scope path), require fresh TOTP/re-auth instead of failing outright — verify harder, not block harder.
- [ ] F5. **Truthfulness gates:** extend `scripts/validate_runtime_enablement_readiness.py` so every new gate above must have executor + tests + threat model before `allow`/`auto` becomes selectable (mechanically enforcing "documentation never runs ahead of code").
- [ ] F6. **Production critical-risk classification.** Today `RiskLevelValue.CRITICAL` is assigned only in tests — the router floor (`raiker/runtime/authority/router.py`) has no production callers routing to it. Land a canonical, in-code classification table (new `raiker/runtime/authority/critical.py`, consumed by the router's risk resolution) so `critical` is a real production tier. Initial criteria — an action is critical when it matches any of:
  - (a) enabling or relaxing Tier-2 execution (shell / process / network / web-fetch), including threat-model acknowledgments and confirmation-token issuance;
  - (b) an external send or calendar invite to any recipient/attendee not on the account's allowlist (Workstream E);
  - (c) a checkpoint restore that would overwrite changes made by a different principal since the checkpoint (Workstream B);
  - (d) creating or broadening a standing approval grant (F3) — grants are born from a critical, human-decided action, which is what makes their later unprompted use legitimate;
  - (e) any operation on vault/credential material or on an egress allowlist.
  The table is data, not scattered conditionals; it ships with tests proving each criterion routes to the floor, and it may only be *extended* (never narrowed) without a threat-model note — enforced by the F5 validator.
- [ ] F7. **Critical approval lifecycle: notify → manual human decision → default deny.** Replace the router's current silent flat-deny of AI-proposed critical actions with a parked `pending_critical` approval that always notifies the owner (D2: dashboard notification center, OS notification via the desktop shell, channel relay where enabled). Resolution rules, enforced in `RuntimeAuthority` and covered by tests:
  - Only a live human principal may resolve it, and approval requires step-up verification (fresh TOTP/re-auth when MFA is stale) before the Workstream A relay executes it with execution-time re-verification and posture check.
  - Manual reject, TTL expiry (default 24 h), revocation of the approving session, or any resolution attempt by a non-human principal resolves to **deny**.
  - No decision mode, standing grant, scheduled routine, or subagent can resolve or pre-authorize a critical approval; the resting state of every critical action is deny, and absence of an explicit human approval always means deny.
  - Every transition (`created → notified → resolved/expired`) is an audit event carrying the posture snapshot (F1), so "who was in control, when" is reconstructable from the log alone.

---

## Sequencing & milestones

| Milestone | Contents | Exit criteria |
|---|---|---|
| M1 | A1–A2, F1, F3 (grant model), F6 (critical classification), D2 (notifications) | An approved non-file action executes end-to-end; grants visible/revocable; every F6 criterion provably routes to the critical floor; full suite + validators green |
| M2 | A3–A4, B1–B2, F7 (critical lifecycle) | Tier-2 approve-and-run behind threat-ack; restore with pre-image undo proven by tests; critical actions notify + resolve only by manual human decision, defaulting to deny |
| M3 | C1–C3, B3–B4, F2 | Read-only subagents runnable under budget; background sweep shipping |
| M4 | E1–E3, D1 | First real external email send + calendar push through draft→approve→send; rich TUI launchable |
| M5 | D3, E4, C4, F4 | Desktop shell with keychain vault; step-up flows; teams enabled |
| M6 | D4, F5, docs/ledger reconciliation | IDE surface; `docs/IMPLEMENTATION_STATUS.md`, `docs/GAP_AND_TODO_ANALYSIS.md`, `README.md` updated to the new truthful state |

Each milestone ends with the full local validation gate (`ruff`, `mypy`, `pytest`, both truthfulness validators, licensing check, web lint/check/test/build) and a recorded verification entry in `docs/IMPLEMENTATION_STATUS.md`.

## Explicit non-goals

- Hosted/multi-tenant Raiker, remote/cloud command execution, and the finance/investment/medical/pregnancy/CCTV/home-security/hardware domains stay fail-closed (each needs its own per-domain threat model first).
- No removal of the critical-risk human-confirmation floor, PolicyEngine hard-denies, egress allowlists, or append-only audit — the Zero Trust layer tunes *when* a human is asked, never *whether* verification happens.
