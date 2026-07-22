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

## Security posture (read before adding any restriction)

Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
Security is not restricting the user; it is a frictionless system that lets the
owner operate securely without having their access taken away. Do **not** put a
hard block in front of the owner's legitimate choices (e.g. connecting a remote
MCP server) by default — **allow, monitor, surface anomalies as findings +
notifications, and give the owner an instant stop plus an automatic revocable
pause for the irreversible/high-severity cases.** Reserve hard prevention for a
last resort and justify it against this posture. Full statement:
`docs/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

## Non-negotiable runtime rules

- Fail closed: a missing gate, policy, credential, allowlist, executor, or
  approval denies the action. (This is honesty — no fabricated success — not a
  wall in front of the owner.)
- Route every model and tool action through the existing governance, policy,
  approval, and typed-event paths. Do not add a side-door.
- Keep credentials in owner-controlled storage/environment only. Never render,
  log, or commit them.
- Add a typed event to `EVENT_TYPES` before emitting it.

## Current state — 2026-07-18 (doc reconciliation)

This section reconciles the handoff with the committed tree. Read it first; the
older dated sections below remain accurate for their own slices but predate the
Control Deck commit.

- **Control Deck Task 6 — shared web primitives and shell migration is
  implemented locally.** Reused `Sidebar`/`NotificationCenter` remain the sole
  shared instances; notification copy is source-neutral and the Sidebar uses
  the approved Manrope uppercase wordmark. `PageState`, `ResponsivePage`,
  `SessionMenu`, `ToolControlBoard`, and the loopback-only share predicate are
  presentational/callback-only; no Svelte code decides authority. `App.svelte`
  now wraps only the active route in `ResponsivePage`, preserving bootstrap,
  auth, routing, projects, skip link, and main landmark. At 390px the shell
  uses a labelled icon rail and compact padding. A live screenshot first found
  the full sidebar crushing mobile content; that defect was fixed and the final
  desktop/mobile authenticated screenshots live in
  `.tmp/task6-live-20260718/`. SessionMenu is deliberately unconsumed until
  Task 8, so its six actions and generic notification state are component-tested
  rather than claimed as a live route flow. The Python Playwright package and
  downloaded Node browser were unavailable; the authenticated drive used Node
  Playwright with installed system Chrome. Full web (151 passed, one existing
  skip), two uncached Python batches, ruff, mypy (429 files), compileall, and
  all five validators passed. Implementation commit `66037db` passed CI (Python
  3.11/3.12), Web UI, and Phase Status Validation.

- **Adaptive navigation follow-up is implemented locally.** Phone widths below
  640px use a five-item bottom bar with a More drawer instead of a permanent
  icon rail. Tablet widths 640-1023px use a compact Menu trigger and the same
  drawer; desktop widths 1024px and wider retain the full sidebar. The existing
  grouped route list remains the sole navigation source. The drawer supports
  route selection, Escape, scrim dismissal, and trigger-focus restoration.
  `Sidebar.test.ts` was RED then GREEN; the full web gate is clean (35 files,
  196 passed, 1 skipped; check/lint/build passed). A disposable live session
  resized through 375/768/1024/1440px without reload: no horizontal overflow,
  correct adaptive controls, a working Diagnostics drawer route, and no browser
  console errors/warnings. Screenshots are untracked evidence at
  `output/playwright/adaptive-navigation-*.png`. Implementation commit
  `2e90eb2` is on `main`; its [CI](https://github.com/sharRahul/Raiker/actions/runs/29661755519),
  [Web UI](https://github.com/sharRahul/Raiker/actions/runs/29661755538), and
  [Phase Status Validation](https://github.com/sharRahul/Raiker/actions/runs/29661755521)
  workflows are green.

- **Monitored MCP connections — Phase D (Connections UI + live monitor) is
  implemented in the current worktree.** Every Connections catalogue card now
  has a governed **Connect via MCP** flow for a local starter or a remote HTTP
  endpoint. Remote auth retains only an owner-controlled token environment
  variable reference. The MCP Servers page polls its owner-scoped telemetry
  every ten seconds and shows connection state, redacted recent sessions, open
  findings, notifications, and pause/resume actions. New read-only route:
  `GET /api/mcp/servers/{server_id}/sessions`; it returns no payloads,
  credentials, or principal identifier. Component and API contract tests were
  driven RED then GREEN. A live authenticated browser drive created local and
  mock-remote servers, tripped a tool-set anomaly into auto-pause plus finding /
  notification, and resumed it; screenshots are retained with the task artifacts.
  `ruff` (source roots), `mypy`, `compileall`, all five repository validators,
  web check/lint/test/build, and the full Python suite pass. The former Windows
  `WinError 1312` came from the WindowsApps `python3` execution alias after a
  long-lived test run; `PluginRuntimeExecutor` now defaults to direct `python`
  on Windows, while retaining `python3` elsewhere. The Phase D backend/API tests pass.

- **Control Deck Task 5 — credential lifecycle, breach detection, and
  self-monitoring is implemented in the current worktree.** Migration
  `RAIKER-1021-credential-security` adds owner-scoped lifecycle and monitor-state
  rows. The Security & Login page exposes 75/90-day lifecycle status, verified
  replacement only when encrypted connector credential metadata exists, redacted
  configured-path scans, explicit vault-health checks, and a breach check that
  requires both user consent and an owner allowlist for
  `api.pwnedpasswords.com`. Task 5 uses the existing `security_findings` and
  `notifications` substrate for deduplicated alert/recovery evidence. It stores
  and renders no raw secret, password, full hash, local match, or breach-body
  content. The later bounded-detector backlog is dependency/OS advisories,
  auth/session anomalies, audit-policy violations, configuration drift, secret
  exposure, runtime egress, and integrity checks; every addition must include a
  redacted finding, deduplicated notification, remediation, and tests.
  Focused lifecycle/monitor/API tests, the complete web gate (145 passed, one
  existing skipped), both full Python batches (two existing skips total), ruff,
  mypy, compileall, and all five validators pass. A disposable authenticated
  browser drive recorded a redacted local finding plus vault-health failure and
  an opt-in breach request; screenshots are in `C:\Temp\raiker-task5-live`.
  The active Python environments lack Playwright, so that browser drive used the
  installed Node Playwright runtime with system Chrome after that limitation was
  verified. GitHub CI initially caught missing annotations in the new monitoring
  test; follow-up commit `e92882c` fixes that and its CI Python 3.11/3.12 matrix
  plus Phase Status Validation are green.

- **The 2026-07-16 "dirty worktree" is now committed.** The Control Deck pause
  point below told the next session to preserve an uncommitted worktree. That
  work has since landed as commit `f97e6ce`
  ("Isolate users by instance and scope control state per principal"). The
  working tree is clean — do not go looking for uncommitted Control Deck changes.
- **Plan Tasks 1 and 2 are implemented and committed.** Task 1 (legacy-account
  role backfill + inactive-session fail-closed) and Task 2 (one-user-per-instance
  boundary, local password recovery, per-principal control state, owner-scoped
  data) are both on this branch. Task 1 added migration
  `RAIKER-2021-legacy-account-bootstrap-roles`. Task 2 added
  `RAIKER-2022-principal-control-scope`, `RAIKER-2022-owned-context-data`,
  `RAIKER-2023-owned-memory-metadata`,
  `RAIKER-2023-owner-brain-sources`, the `principal_model_control` /
  `principal_capability_gate_state` / `principal_capability_decision_mode` /
  `instance_account_guard` / `brain_sources` tables, and
  `SQLiteStore.account_scope()` as the single principal-scope predicate.
- **Plan Task 3 (safe session rename + archive lifecycle) is now implemented and
  committed** as `52d6c5e` (merged in PR #120). Migration
  `RAIKER-1015-session-archive-lifecycle` adds `sessions.archived` /
  `sessions.archived_at` plus `idx_sessions_owner_archived_updated` via the
  idempotent `_skip_existing_add_columns` path; `SQLiteStore._update_owned_session`
  is the shared owner-check behind `rename_session` and `set_session_archived`;
  `list_sessions` gained an `include_archived` flag (default active-only; the
  event-visibility filter passes `include_archived=True` so archiving never hides
  a session's events). `DashboardService.rename_session` normalizes titles (trim,
  collapse whitespace, 200-char cap, 422 on invalid) and `set_session_archived`
  toggles the reversible soft-archive state — both human-only and owner-scoped.
  New event types `session_renamed` / `session_archived` / `session_unarchived`;
  routes `PUT /api/sessions/{id}/rename|archive|unarchive` and an owner-scoped
  `include_archived` query flag on `GET /api/sessions`. Archive never deletes
  transcripts, events, checkpoints, or permissions. `tests/test_session_lifecycle.py`
  (14 tests) covers it. A code review of the diff found no correctness defects;
  one design note recorded below.
- **Plan Task 4 (governed local MCP builder + connector) is now implemented on
  this branch.** `raiker/runtime/executors/mcp.py` adds two real, fail-closed
  executors: `McpBuilderExecutor` (`mcp_server_create`) writes a reviewed,
  dependency-free stdio MCP server template to a validated workspace-relative
  path (absolute/`..` rejected) and records an owner-scoped `mcp_servers` row;
  `McpConnectorExecutor` (`mcp_connect` / `mcp_list_tools` / `mcp_call_tool`)
  validates the interpreter allowlist (`python`/`python3`/`node`,
  owner-extensible; shells never accepted) + workspace-relative args, then runs a
  bounded `subprocess.Popen`+`communicate` JSON-RPC stdio session (≤60 s,
  ≤200 KB) and returns **redacted metadata only** — tool names/count and content
  length + redaction flag, never raw tool output. The MCP wire protocol is
  spoken directly (no third-party `mcp` SDK, so the runtime stays hermetic;
  `pyproject.toml` unchanged). Wiring: `mcp_builder_runtime` /
  `mcp_connector_runtime` in `REAL_EXECUTOR_CAPABILITIES` +
  `RUNTIME_DOMAIN_CAPABILITIES` + Tier-5 executed caps (ship `ENABLED_RUNTIME`),
  `activation.py` requirements (threat_ack + human_confirm), `CAPABILITY_GATE_MAP`
  (4 action types + 2 self-maps), policy `approval_required_actions` (4 action
  types), new id prefix `mcp_`, migration `RAIKER-1016-mcp-server-profiles` +
  owner-scoped storage CRUD, `McpServerView` + owner-scoped `GET /api/mcp/servers`
  read (building/connecting stays a governed runtime action, not a REST
  mutation), and threat models `docs/threat-models/mcp-builder.md` /
  `mcp-connector.md`. Tests: `tests/test_mcp_runtime.py` (22). A live end-to-end
  drive (build → connect → redacted tool call → three fail-closed paths →
  owner-scoped API isolation) passed, and the running web app was screenshotted
  (no regression).
- **Task 4b (MCP server management web page) is now implemented on this branch**
  (owner-requested amendment; pulled forward from the Task 9 route rebuild). A
  dedicated **MCP Servers** page (Steering nav) creates, tests, renames, and
  deletes local MCP servers end-to-end, showing each server's status, discovered
  tools, and command. Governance split, no side-door: **create** and
  **test/connect** run the real capability through `route_action` (gate + policy
  + decision mode + audit; a disabled gate surfaces `disabled_by_capability_gate`
  and the page points the owner at Capabilities); **rename** and **delete** are
  owner-scoped, human-only metadata ops (delete also removes the generated
  template file under `.raiker/mcp/servers/`). Backend: migration
  `RAIKER-1017-mcp-server-runtime-state` (`tools` / `tool_count`), storage
  `delete_mcp_server` / `rename_mcp_server` + tool persistence,
  `RuntimeControlService.{create,connect,rename,delete}_mcp_server`, executor
  persists discovered tools on connect, routes `POST /api/mcp/servers`,
  `POST /api/mcp/servers/{id}/connect`, `PUT`/`DELETE /api/mcp/servers/{id}`.
  Frontend: `McpView.svelte`, api client + `McpServer` type, `nav.ts` +
  `App.svelte`. Tests: 9 new API cases in `tests/test_mcp_runtime.py` (31 total)
  + `McpView.test.ts` (4). Full suite 1918 passed; web check/lint/test/build
  green; live browser drive screenshotted (create → test → connected with tools).
- **Monitored MCP connections — Phase A (remote HTTP transport) is implemented
  on this branch.** Following the Security Philosophy (allow + monitor, not
  block), `McpConnectorExecutor` gained an `http` transport: `mcp_connect` /
  `mcp_list_tools` / `mcp_call_tool` run a bounded JSON-RPC-over-HTTP session
  against an owner-added `endpoint_url` via `sandbox.post_json_rpc` (bounded
  body/timeout, returns headers for `Mcp-Session-Id`; injectable `http_fn`). The
  owner token is read from the env var named by `auth_ref` at call time — only
  the reference is stored, never the token; artifacts/events stay redacted.
  Migration `RAIKER-1018-mcp-remote-endpoint` (`endpoint_url`, `auth_ref`);
  `update_mcp_server_runtime` refreshes only runtime fields (no endpoint wipe);
  `RuntimeControlService.create_remote_mcp_server` (human-only, emits
  `mcp_connection_added`) + transport-aware `connect_mcp_server`; route
  `POST /api/mcp/servers/remote`; `McpServerView` carries `endpoint_url`/`auth_ref`.
  Tests: 8 new in `tests/test_mcp_runtime.py` (39 total). Full suite 1926 passed;
  ruff/mypy clean; five validators pass; a live real-HTTP drive (local MCP server
  on 127.0.0.1) verified connect/list/redacted-call/token-never-stored/fail-closed.
  Threat model `docs/threat-models/mcp-remote.md`.
- **Monitored MCP connections — Phase B (per-session monitoring + anomaly
  detection) is implemented** (commit `ec05ae4`, merged PR #123). New
  `raiker/security/mcp_monitor.py` (`McpSessionMonitor` + redacted
  `McpSessionTelemetry` + `shape_sensitivity`); migration
  `RAIKER-1019-mcp-monitoring` adds the redacted `mcp_session_log` and the shared
  `security_findings` tables; the executor emits per-session telemetry (stdio +
  HTTP, on success and failure). Five deterministic rules (new-host, volume-spike,
  tool-set-swap, sensitive-shape, error-burst) each raise a redacted finding +
  `mcp_anomaly_detected` event; no raw payload/token/host secret is ever stored.
  Tests: `tests/test_mcp_monitor.py` (14).
- **Monitored MCP connections — Phase C (notify + instant kill switch + revocable
  auto-pause) is implemented on this branch** (commit `4b2848d`, draft PR #124).
  Findings become owner action: every finding raises a `notifications` row, and a
  **high-severity** finding trips a revocable auto-pause circuit breaker. New
  `McpContainment` helper (shared by the monitor's automatic breaker and the
  owner's manual controls) writes `mcp_servers.monitor_state`
  (`active`/`paused`/`killed`) + redacted `paused_reason`/`paused_at`, emits
  `mcp_connection_paused`/`resumed`/`killed`, and raises a notification per
  transition. The connector executor gained a **containment gate** — a
  paused/killed connection fails closed before the session runs
  (`mcp_connection_paused` / `mcp_connection_killed`, honest missing-prerequisite,
  not a ban). Migration `RAIKER-1020-mcp-containment-notifications` (the three
  `mcp_servers` columns + the shared `notifications` table); id prefix `ntf_`;
  control-service `pause_mcp_server`/`kill_mcp_server`/`resume_mcp_server`
  (human-only, owner-scoped); routes `POST /api/mcp/servers/{id}/pause|resume|kill`,
  `GET /api/mcp/servers/{id}/findings`, `GET /api/notifications`,
  `POST /api/notifications/{id}/read`. Kill and pause are both revocable via
  resume. Tests: `tests/test_mcp_containment.py` (20). Full suite 1960 passed;
  ruff clean; mypy 425 files clean; five validators pass; two live drives (real
  governed runtime + a real-browser authenticated HTTP drive with a screenshot).
  Threat model `docs/threat-models/mcp-monitoring.md`. **Phase D (Connections
  "Connect via MCP" UI + live monitor panel with browser screenshots) is now
  implemented in the current worktree** — see
  `docs/plans/2026-07-17-monitored-mcp-connections.md`.
- **Control Deck Tasks 7–10 are implemented locally and await commit/push.**
  The route bodies now use compact loading, error,
  and empty states without changing typed API authority; Sessions consumes
  `SessionMenu` for rename/archive/project/pin/delete operations and
  Checkpoints is explicitly metadata-only. Models, Connections, Capabilities,
  Settings, Activity, Diagnostics, login, and the responsive shell now share
  the Control Deck tokens. The disposable authenticated browser pass selected
  the local llama.cpp profile, opened the notification panel, visited all 17
  routes, and confirmed no console errors/warnings or 375px horizontal
  overflow. Screenshots are under `output/playwright/task7-10-*.png`. The fresh
  Python 3.12 gate passed 1969 tests with two existing skips; Ruff, mypy (429
  files), compileall, all five validators, web lint/check/test/build, and
  `git diff --check` passed. The only emitted warning is an upstream FastAPI /
  Starlette `TestClient` deprecation notice from the current dependency set.
  Commit `37f681b` is pushed to `main`; its CI (Python 3.11/3.12), Web UI, and
  Phase Status Validation workflows are green.
- **Task 3 review note (design, not a bug).** The new
  `list_sessions(include_archived=False)` default excludes archived sessions from
  every internal caller that does not opt in. The event-visibility path was
  deliberately updated to `include_archived=True`, but `get_project`
  (project-detail session list and `session_count`), `brain_view`, the workspace
  stats count, and the CLI session list now show active-only. This is defensible
  ("archived is out of the default active list") and no test regressed, but if a
  project-scoped archived-session view is later wanted, those call sites need an
  explicit `include_archived` pass-through — the mechanism already exists.
- **Task 2 acceptance note.** The code is committed, but the recorded acceptance
  gate for Task 2 is a re-run of both independent reviews against the fixed tree
  (see the per-defect record below). The checkbox in the plan is marked done
  because the implementation and its self-tests landed; treat the dual re-review
  as the remaining formal sign-off, not as blocking work on Task 3.

Python gates re-run on the Task 4 + 4b tree (2026-07-17, deps installed fresh):

```text
python -m pytest -o addopts="" -q     # exit 0, 1918 passed
python -m ruff check .                # All checks passed!
python -m mypy raiker apps tests      # Success: no issues found in 421 source files
python scripts/validate_documentation_truthfulness.py     # PASSED
python scripts/validate_repo_truthfulness.py              # PASSED
python scripts/validate_phase_status.py                   # PASSED
python scripts/validate_runtime_enablement_readiness.py   # PASSED
python scripts/validate_local_single_user_runtime.py      # PASSED
```

Web gates (from `apps/web`) on the Task 4b tree:

```text
npm run check     # 0 errors, 0 warnings
npm run lint      # clean
npm test -- --run # 141 passed, 1 skipped (McpView 4/4)
npm run build     # exit 0
```

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
  entity extraction/review, and runtime hybrid integration; same-device
  cross-instance isolation and recovery drills; user-controlled NAS/mounted-drive/
  NAS backup first, with mounted-drive/cloud destinations optional; real encrypted
  backup and restore/erasure drills; monitoring, daemon/worker operation, load/soak/chaos
  evidence; and independent security, privacy, and pilot/benchmark evidence.
- The next memory program is staged in `HYBRID_MEMORY_IMPLEMENTATION_PLAN.md`
  (Stages F–J): retrieval-authority/evaluation, gated semantic + entity
  retrieval, self-hosted multi-user encryption/backup operations, reliability/scale, then
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
  vectors, and graph rows using a workspace-derived key; local workspace
  isolation, telemetry, and operational proof remain required.
- The first maintenance-job primitive is now present: idempotent `reconcile`
  and `integrity_scan` jobs have SQLite leases, retries, and dead-letter state,
  per-workspace rate limits, and lifecycle audit rows, but no daemon, telemetry,
  or load/chaos proof exists yet.
- SQLCipher is provided by `sqlcipher3-wheels` (imported as `sqlcipher3`).
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
- **External agent frameworks:** persistent memory, self-created/reused skills, command
  approval/container isolation, cron delivery, and a messaging gateway make
  memory controls, bounded automation, and transport governance product-level
  concerns. This informs items 3, 4, 8, and 10.
- **OpenClaw:** a single self-hosted gateway owns channel routing, sessions,
  device pairing, typed events, health, and idempotent side effects. This
  informs item 10.

Primary sources: [Claude support collection](https://support.claude.com/en/collections/4078531-claude), [Claude Projects](https://support.claude.com/en/articles/9517075-what-are-projects), [Claude chat search and memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context), [Claude memory import/export](https://support.claude.com/en/articles/12123587-import-and-export-your-memory-from-claude), [Cowork support collection](https://support.claude.com/en/collections/19667525-claude-cowork), [Cowork project tasks](https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork), [Cowork computer use](https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork), [Cowork OpenTelemetry](https://support.claude.com/en/articles/14477985-monitor-claude-cowork-activity-with-opentelemetry), [Claude Code documentation](https://code.claude.com/docs/en/), [Claude Code extensions](https://code.claude.com/docs/en/features-overview), [Claude Code hooks](https://code.claude.com/docs/en/agent-sdk/hooks), [OpenAI Codex manual](https://developers.openai.com/codex/codex-manual.md), [OpenClaw overview](https://docs.openclaw.ai/), and [OpenClaw gateway architecture](https://docs.openclaw.ai/concepts/architecture).

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

## Control Deck Pause Point — 2026-07-16

The approved Control Deck work is tracked in:

- `docs/specs/2026-07-16-raiker-control-deck-design.md`
- `docs/plans/2026-07-16-raiker-control-deck-implementation.md`

**Status (2026-07-17): this pause is resolved.** The worktree that this section
warned against discarding has been committed as `f97e6ce`; the tree is clean.
The instruction below is retained for history only — there is no longer a dirty
worktree to preserve. See "Current state — 2026-07-17" above for what landed and
what remains (Tasks 3–11).

### Product policy: one user per instance

Raiker is **one user per instance**. Additional users get their own separate
Raiker instance. Multi-account workspaces are not a supported state.

The code permits what the policy forbids, so do not infer the policy from the
code: `instance_account_guard` blocks only new *registration*, `login` has no
guard check, and `_migrate_legacy_controls_to_original_owner` claims the guard
for the oldest account without deactivating the others. A pre-existing active
account can therefore still log in. There is no multi-account API surface and
none should be built.

Owner scoping is still live and load-bearing — a deactivated recovered-from
owner, a CLI-bootstrapped owner, and non-human/delegated principals all coexist
in one database. `tests/conftest.py::seed_account` seeds an extra
credential-backed account directly into the tables (bypassing the guard claim)
so isolation invariants can still be proven. That fixture is the sanctioned way
to test owner isolation; a second web registration is not.

### Plan Task 2 — implemented, reviewed, fixed, NOT yet accepted

Task 2 implements the one-user-per-new-instance boundary, local recovery,
per-principal controls, and owner-scoped data access:

- Atomic initial-account and CLI-owner bootstrap transitions.
- Atomic forced recovery with owner-scoped data/control transfer and old-session
  revocation.
- Atomic single-use MFA/recovery-ticket claiming and backup-code consumption.
- Owner-scoped brain sources, prompt context, attachments, memory/vector
  retrieval, projects, tasks, approvals, interrupts, model selection, and
  capability controls.
- Owner-isolated purge that removes target durable artifacts without deleting
  another owner's records.

**The two independent reviews ran on 2026-07-16. Both returned Fail**, with
7 critical defects — each reproduced against a real workspace, not merely read.
All 7 are now fixed:

1. **CLI turns silently lost all context.** `gatherer.py` tested
   `owner_principal_id` for truthiness rather than "is this a real account".
   The CLI sends `UserMetadata`'s default `local_user`, which is truthy but is
   not a principal, so project context, model profile, connector status, and
   memory were dropped. Fixed with one shared predicate,
   `SQLiteStore.account_scope()`, applied at the gather entry point.
2. **`purge_account` did not purge.** `approved_memory_fts` and
   `memory_projections` are keyed by `memory_id` only, so the owner-scoped
   delete never matched them; plaintext also survived in `.raiker/memory/*.md`.
   Both now deleted/unlinked.
3. **Recovery orphaned the original-owner pointer.**
   `_original_owner_from_connection` had no `is_active` filter, so it kept
   resolving to the deactivated old owner and filed all later unattributed data
   against a dead principal. The guard row is now the authority and every
   fallback branch filters `is_active = 1`.

   **This fix was initially only half done, and this file claimed otherwise.**
   `_backfill_owned_context_data` — the function that actually *writes* the
   attribution, and the one the pointer fix exists to protect — kept its own
   inline copy of the resolution with no guard check and no `is_active` filter,
   while its sibling `_backfill_owned_memory_metadata` correctly delegated. Both
   independent re-reviews caught it; one reproduced it end-to-end through the
   real `save_attachment` API. The duplicate query is deleted and
   `test_context_data_backfill_files_unowned_rows_to_the_live_owner` fails
   without the fix. Lesson: a fix landing on the read path is not the same as a
   fix, and the accompanying test asserted the helper rather than the caller its
   own docstring named as the reason the fix mattered.
4. **CLI-bootstrapped owners could never be recovered.** `bootstrap_owner`
   creates no credentials, but recovery required a credential-backed owner —
   so the documented lost-access path always denied. The credential owner is
   now nullable and the principal/guard/data transfer runs without it.
5. **A non-idempotent migration was suppressed and marked applied.**
   `_apply_migration` swallowed `OperationalError` then recorded success;
   `OWNED_CONTEXT_DATA_SQL` is three `ADD COLUMN` statements and `executescript`
   commits implicitly, so a crash mid-migration permanently denied
   `vector_records` and `attachments` their `owner_principal_id` columns.
   Suppression removed; `_skip_existing_add_columns` makes re-runs safe.
6. **Connection leak blocked the plaintext-DB conversion on Windows.**
   `with self.connect()` commits but does not close, and Windows refuses to
   replace a file with an open handle. Closed explicitly at that one site.
   NOTE: this one **pre-dated Task 2** — it fails at HEAD too. It is not a
   Task 2 regression, contrary to the review that reported it.
7. **22 test regressions** across 14 files, plus fixture reconciliation.

Verified gates on the current worktree — full suite, run unpiped:

```text
python -m pytest -q                     # PYTEST_EXIT=0, 0 failed (was 23)
python -m ruff check .                  # All checks passed!
python -m mypy raiker apps tests        # Success: no issues found in 418 source files
python -m compileall -q raiker tests    # exit 0
```

**Task 2's checkbox is still unchecked, deliberately.** Both reviews rated the
underlying engineering sound — atomicity verified under 8-way concurrency
(exactly one success every time), isolation tests confirmed to fail when the
owner predicate is stripped — and both called this "re-review after fixes, not
a redesign". But both verdicts were issued against the pre-fix code. **Re-run
both reviews against the fixed tree before checking Task 2 off.** Review scope:
atomic registration/recovery, MFA ticket replay, brain-source isolation,
recovery data/control transfer, account purge, and all owner-scoped APIs.

### Verification lessons — do not repeat these

- **A focused suite is not an acceptance gate.** The previous handoff recorded
  `pytest` on four files (101 passed) as evidence. Those four files did pass —
  while 23 tests failed elsewhere. A gate that runs only the files you changed
  cannot detect the regressions you caused elsewhere. Run the full suite.
- **`pytest -q | tail` returns tail's exit code, not pytest's.** It reported
  success over 23 failures in this session. Redirect to a file instead.
- **Use `python -m pytest -o addopts="" -q > file 2>&1`.** `pyproject.toml:42`
  already sets `addopts = "-q"`, so the obvious `pytest -q` is really `-qq`,
  which suppresses the summary line entirely — the output file is dots and no
  `N passed`. A "0 failed" claim read from that file's text is not evidence; only
  the exit code carries it. Two independent reviewers flagged this.
- **Synthetic fixtures are not real data.** `purge_account` passed every test and
  both reviews, then failed on the first real workspace — three separate defects,
  because no fixture had a conversation in it. Drive the real thing.
- **A fix on the read path is not a fix.** The dead-owner hardening landed on the
  resolver and not on the backfill that consumes it, and the test asserted the
  resolver — so it passed while the bug stayed live on the write path.
- **The previous handoff claimed `mypy` passed. It did not** — `mypy raiker
  apps tests` had 6 errors, two of which were real runtime `TypeError`s from a
  signature change whose callers were never updated.
- **Every critical here shipped because no test covered the path** (CLI gather,
  CLI recovery, crash-resume migration). A fix without a test that fails before
  it is not done.
- **Reviewer claims need independent verification.** One review asserted "all
  23 failures pass on HEAD"; a baseline run disproved it (defect 6 above). The
  findings that held up were the ones with reproduction transcripts attached.

### Deferred security work

Deliberately deferred to the credential/security task rather than silently
treated as complete:

- Encrypt or otherwise protect durable `.raiker/memory/*.md` content at rest;
  SQLCipher protects the database but not standalone memory files. (Purge now
  unlinks these files — that is not the same as encrypting them at rest.)
- Complete entity-graph ownership hardening/migration beyond the owner predicate
  on graph-neighborhood reads.
- The general SQLite migration error/recovery policy. The specific
  suppress-and-mark-applied defect is fixed (see 5 above); a broader review of
  migration failure handling is still outstanding.

Known remaining review findings, not yet actioned:

- `begin_password_recovery` leaks account existence **by timing**, contradicting
  its own docstring: measured 28.5 ms (existing username) vs 5.8 ms
  (nonexistent), distributions non-overlapping, so one sample distinguishes. The
  hit branch writes a session row; the miss branch returns
  `secrets.token_hex(32)`. Response *shape* is identical; timing is not.
- Owner-scope parameters default to `None`/`""`, so a forgotten argument fails
  open. No live fail-open on the API surface today — but this is the mechanism
  that let the backfill defect above become reachable.
- Recovery duplicates role assignments (verified 2x per role; duplicates only,
  no escalation).
- `login` has a residual ~27 ms timing gap; the hashing equalization is correct,
  the remainder is `_account_principal_is_active` opening a connection twice.

**Corrected — do not carry these forward as findings:**

- `_transfer_owner_scoped_data`'s docstring was previously recorded here as
  false. It is **true**: a reviewer enumerated all swept tables and no audit or
  event table carries an owner/principal/user column (they key on `session_id`),
  so audit history is not rewritten. The real risk is future schema drift
  silently opting a new audit table in.
- `complete_password_recovery` had **no attempt lockout** — previously rated
  Important here. Measured, it was Critical: 339 guesses/sec, the ticket
  survived 300 failures, and `valid_window=1` keeps three TOTP codes live at
  once, giving ~30% account takeover per 5-minute ticket against a freely
  re-mintable ticket. **Now fixed** — recovery shares `login`'s
  `LOCKOUT_THRESHOLD` counter, and the failure count is committed before the
  raise so an attempt cannot roll back its own evidence.
  `test_password_recovery_locks_out_after_repeated_wrong_codes` covers it.
- `_check_mfa` consumed backup codes with no transaction, so a single-use code
  granted **8 of 8 concurrent elevations** and a stale write could restore a
  spent code for replay. Pre-existing, not a Task 2 regression — but Task 2
  rewrote `verify_mfa` to consume transactionally and left the two sibling
  callers (`/api/auth/elevate`, `routes_vault`) on the old path. **Now fixed** in
  the shared function, which covers both callers.

### `purge_account` — three defects found only by running it on real data

Neither review caught these; both verified purge against synthetic fixtures with
no conversation history. All three surfaced the first time it ran against a real
workspace, and all three are fixed with tests that fail without the fix:

- **Foreign-key ordering.** The sweep walks `sqlite_master`, which is
  table-creation order — parent before child. `turns.session_id` references
  `sessions`, so purge raised `FOREIGN KEY constraint failed` on any account that
  ever held a conversation. Fixed with `PRAGMA defer_foreign_keys = ON` inside an
  explicit `BEGIN IMMEDIATE`; the pragma is silently undone if set outside a
  transaction.
- **Silent no-op on a NULL delegation link.** Principals from older bootstraps
  carry a NULL `delegated_by_user_id` and are linked to their user only by the
  `principal_<user_id>` convention. Resolving from the column alone yielded NULL,
  so every user-keyed and session-keyed delete matched nothing and purge returned
  success having deleted nothing. Fixed by sharing one resolver,
  `_principal_user_id_from_connection`.
- **Rows orphaned by its own deletes.** The sweep can only match tables carrying
  an owner/session/project column. Five FK edges have children that carry none —
  `policy_decisions` and `approvals` -> `tool_actions`, `gist_memories` ->
  `eidetic_observations`, and both `*_relationship*` tables -> `approved_memory` —
  so they were left pointing at deleted parents and failed the deferred check at
  COMMIT. `_delete_rows_orphaned_by_purge` lets SQLite name the orphans its own
  deletes created rather than hardcoding a list that rots on schema drift.

### Safe next-session sequence

> Updated 2026-07-17: steps 1–2 below described a pre-commit state. The Control
> Deck worktree is now committed (`f97e6ce`) and the tree is clean, so there are
> no uncommitted changes to preserve. Task 2's code has landed; the dual
> re-review is a formal sign-off that can run in parallel and does not block
> Task 3. Start at step 3.

1. Read this handoff, the design spec, and the implementation plan. Inspect
   `git status --short` (expected: clean).
2. (Sign-off, non-blocking) Re-run both independent reviews against the committed
   Task 2 tree and record any findings. Do not treat green gates alone as
   acceptance — the gates were green when 7 criticals were still present.
3. Plan Tasks 3 and 4 are done (session rename/archive lifecycle committed as
   `52d6c5e`; governed local stdio MCP builder + connector on this branch).
   Execute Plan Task 5 next: credential lifecycle, local scans, opt-in HIBP range
   checks, monitoring, notifications, and the deferred durable-memory security
   concerns above where applicable — with tests before implementation.
4. Then execute UI Tasks 6–10 (the web Control Deck rebuild), which include the
   MCP builder/connector rows that sit on the Task 4 runtime.
5. Execute UI Tasks 6-10 in plan order. Preserve the current dark, compact
   Control Deck visual system, use typed API contracts, and do not expose a UI
   control without a supported backend operation.
6. Run Plan Task 11's full Python/web/browser/static validators before any
   commit. Only then inspect `git diff`, stage all intended changes, commit, and
   push `origin/main` as requested.
