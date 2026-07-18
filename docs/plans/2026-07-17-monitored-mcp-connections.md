# Monitored MCP Connections — Design & Implementation Plan

> **Status:** design approved 2026-07-17. **Phases A, B, C implemented**
> (remote transport, per-session monitoring + anomaly findings, and
> notify + kill switch + revocable auto-pause); **Phase D (Connections UI +
> live monitor) is the remaining slice.** Supersedes the "no remote MCP
> endpoints" stance in `docs/plans/2026-07-16-raiker-control-deck-implementation.md`.
> Grounded in `docs/SECURITY_AND_POLICY.md` → "Security Philosophy".

## Goal

Let the owner connect **any** MCP server — local (stdio, already shipped) or
**remote (HTTP)** — from the Connections page, the way Claude/ChatGPT let you
add a connector, and make every connection **monitored**: each session is
recorded and watched for unusual activity, anomalies are surfaced to the owner
as findings + notifications, and the owner can **stop** a connection instantly
while a **revocable auto-pause** contains the irreversible/high-severity cases
when the owner is away.

This replaces prevention-by-restriction with visibility + owner control +
containment. The runtime does not block the owner's chosen connections; it
observes them and keeps them instantly controllable.

## What this is NOT (honest scope)

- It is **not** 26 real one-click brand integrations. Most catalog entries
  (Uber, Booking, …) have no official MCP server; Raiker cannot fabricate those.
  Each connector becomes a launcher for "Connect via MCP (local or remote)"; the
  owner supplies the endpoint/token where a real one exists.
- It does **not** add a full OAuth authorization-code redirect flow in the first
  cut. Remote servers authenticate with an **owner-supplied token** (reusing the
  existing owner-credential model). OAuth is a later, additive phase.
- It does **not** weaken fail-closed on *missing prerequisites* (missing
  credential/executor/approval still denies — that is honesty, not restriction),
  and it does **not** loosen AI/non-owner governance.

## Architecture

Build on what already exists:

- **Runtime:** `raiker/runtime/executors/mcp.py` — `McpConnectorExecutor` speaks
  JSON-RPC. Today it runs a **stdio** session. We add a **remote HTTP** session
  (streamable HTTP / JSON-RPC over POST) behind the same executor, selected by
  the stored connection's `transport`.
- **Storage:** the owner-scoped `mcp_servers` table (migration `RAIKER-1016/1017`)
  already holds a connection profile (command, transport, status, tools). We
  extend it with remote fields and a monitoring/lifecycle state.
- **Audit:** the append-only event log (`EventLogWriter` + `EVENT_TYPES`) already
  records `action_executed` / `action_failed` with redacted artifacts. We add
  connection-scoped telemetry and monitoring events.
- **Findings & notifications:** this plan delivers the redacted-**findings** +
  **notification** substrate that Control Deck **Task 5** (self-monitoring) also
  needs. The two should share one findings/notification model — build it here,
  reuse it there.
- **Governance:** the `mcp_connector_runtime` capability gate, decision modes,
  and approval path stay in force. Remote egress is **recorded and monitored**,
  not blocked by an empty allowlist; the owner's act of adding a server is the
  authorization, and monitoring + containment is the safety net.

### Data model additions (additive migrations only)

`mcp_servers` (extend):
- `transport` already exists (`stdio` | add `http`).
- `endpoint_url TEXT` — remote server URL (null for stdio).
- `auth_ref TEXT` — reference to the owner credential/token store entry (never
  the token itself).
- `monitor_state TEXT NOT NULL DEFAULT 'active'` — `active` | `paused` |
  `killed`.
- `paused_reason TEXT`, `paused_at TEXT`.

New tables:
- `mcp_session_log` — one row per session: `session_row_id`, `server_id`,
  `principal_id`, `started_at`, `ended_at`, `tool_calls`, `hosts_json`,
  `bytes_in`, `bytes_out`, `error_count`, `outcome`. Redacted; no payloads.
- `security_findings` — `finding_id`, `principal_id`, `source` (e.g.
  `mcp_monitor`), `severity`, `code`, `summary`, `redacted_detail_json`,
  `state` (`open`|`acknowledged`|`resolved`), `created_at`. **Shared with Task 5.**
- `notifications` — `notification_id`, `principal_id`, `kind`, `title`, `body`,
  `finding_id?`, `read`, `created_at`. **Shared with Task 5.**

New `EVENT_TYPES`: `mcp_connection_added`, `mcp_connection_removed`,
`mcp_session_started`, `mcp_session_completed`, `mcp_anomaly_detected`,
`mcp_connection_paused`, `mcp_connection_resumed`, `mcp_connection_killed`.

---

## Phase A — Remote MCP transport (owner-added, recorded)

**Files:** `raiker/runtime/executors/mcp.py`, `raiker/runtime/executors/sandbox.py`
(reuse `post_json_url`/`get_url`), `raiker/storage/migrations.py`,
`raiker/storage/sqlite.py`, `raiker/api/schemas.py`,
`raiker/api/routes_dashboard.py`, `raiker/control/service.py`,
`tests/test_mcp_runtime.py`, `docs/threat-models/mcp-remote.md`.

**Security flag:** `security`

- [x] **A1. Failing tests first** — 8 cases in `tests/test_mcp_runtime.py`
  (remote connect + tools/list over HTTP via an injectable transport; token sent
  as bearer but never in artifacts/events/rows; invalid-URL / missing-token /
  unreachable fail closed; redacted tool output; API create-remote + owner
  isolation + bad-URL 422).
- [x] **A2. Verify RED.**
- [x] **A3. Implement** — an HTTP JSON-RPC session in `McpConnectorExecutor`
  selected when `transport == "http"`, via `sandbox.post_json_rpc` (bounded
  body/timeout, returns headers so `Mcp-Session-Id` carries; injectable `http_fn`
  for tests). Migration `RAIKER-1018-mcp-remote-endpoint` adds `endpoint_url` +
  `auth_ref`; `update_mcp_server_runtime` refreshes only runtime fields so a
  re-test never wipes the endpoint. The token is read from the env var named by
  `auth_ref` at call time — only the reference is stored, never the token.
- [x] **A4. Routes/service** — `RuntimeControlService.create_remote_mcp_server`
  (human-only, owner-scoped, emits `mcp_connection_added`); `connect_mcp_server`
  is transport-aware; `POST /api/mcp/servers/remote`; `McpServerView` carries
  `endpoint_url`/`auth_ref`.
- [x] **A5. Verify GREEN** + `docs/threat-models/mcp-remote.md`.

Result 2026-07-17: `EXIT=0`, 39 MCP tests pass (8 new). Full suite **1926 passed**;
`ruff` clean; `mypy` 421 files clean; all five repo validators PASS. A **live
end-to-end drive over real HTTP** (a local stdlib MCP server on `127.0.0.1` +
Raiker's default transport) connected, listed tools, called a tool with a secret
(redacted — only the length surfaced), confirmed the bearer token reached the
server but never entered any stored row, and failed closed on missing-token and
invalid-endpoint. **Phases B–D (monitoring, notify/kill/auto-pause, Connections
UI) are next.**

## Phase B — Monitoring & anomaly detection

**Files:** new `raiker/security/mcp_monitor.py`, `raiker/storage/*`,
`raiker/runtime/executors/mcp.py` (emit per-session telemetry),
`tests/test_mcp_monitor.py`.

- [x] **B1. Failing tests** for: each session writes a redacted `mcp_session_log`
  row (tool-call count, hosts, byte counts, errors — never payloads); a baseline
  forms per connection; deviations raise an `mcp_anomaly_detected` event + a
  redacted `security_findings` row. Cover the anomaly rules below.
- [x] **B2. Verify RED.**
- [x] **B3. Implement** the monitor: after each governed MCP session the executor
  hands redacted telemetry to `mcp_monitor`, which updates the per-connection
  baseline and evaluates rules:
  - **New host** contacted by a connection that never used it before.
  - **Volume spike** — tool-call count or bytes far above the connection's
    rolling baseline.
  - **New/changed tools** — a server starts advertising tools it did not before
    (possible server swap / rug-pull).
  - **Sensitive-data pattern** in an argument/result *shape* — reuse
    `classify_memory_sensitivity` on lengths/patterns (never store the value).
  - **Error/refusal burst** — repeated auth failures or errors.
  Each hit → redacted finding (severity by rule) + `mcp_anomaly_detected` event.
- [x] **B4. Verify GREEN.** Prove no raw payload/token/host-secret is ever stored
  in a finding, event, or session-log row.

Result 2026-07-18: implemented `raiker/security/mcp_monitor.py` (per-session
`McpSessionMonitor` + redacted `McpSessionTelemetry` + `shape_sensitivity`),
migration `RAIKER-1019-mcp-monitoring` adding the `mcp_session_log` and shared
`security_findings` tables, storage accessors, the `mcp_session_completed` /
`mcp_anomaly_detected` event types, and per-session telemetry emission from
`McpConnectorExecutor` (both stdio + remote HTTP, on success and on session
failure). The five anomaly rules (new-host, volume-spike, tool-set-swap,
sensitive-shape, error-burst) each raise a redacted finding + audit event;
tool-set-swap / error-burst are high-severity, sensitive-shape escalates to high
when it coincides with a new host. `tests/test_mcp_monitor.py` adds 14 cases
(RED first, then GREEN). Full suite passes; `ruff` clean; `mypy` 424 files clean;
`compileall` clean; all five repo validators PASS. A **live drive through the
real governed runtime** (`RuntimeAuthority.route_action` → a real local stdio MCP
server) established a baseline, tripped the sensitive-shape rule on a
credential-shaped tool argument, wrote two redacted `mcp_session_log` rows, one
`security_findings` row, and two `mcp_session_completed` + one
`mcp_anomaly_detected` audit events — and confirmed the secret value appears in
**no** log row, finding, or event. **Phases C–D (containment/kill/auto-pause,
Connections UI) are next.**

## Phase C — Notify, kill switch, auto-pause circuit breaker

**Files:** `raiker/security/mcp_monitor.py`, `raiker/control/service.py`,
`raiker/api/routes_dashboard.py`, `raiker/api/schemas.py`,
`tests/test_mcp_containment.py`.

- [x] **C1. Failing tests** for: a **high-severity** finding auto-transitions the
  connection to `paused` (revocable) and blocks further sessions until the owner
  resumes; a **kill** sets `killed` and refuses all sessions; **resume** clears
  `paused`; every transition emits its event and a notification; an owner-present
  **stop** works from one call; pause/kill/resume are owner-scoped + human-only.
- [x] **C2. Verify RED.**
- [x] **C3. Implement** the containment gate in the connector path: before a
  session runs, check `monitor_state` (`killed`/`paused` → refuse with a clear,
  non-fabricated reason); on a high-severity anomaly, set `paused` +
  `paused_reason`, emit `mcp_connection_paused`, and raise a notification.
  Endpoints: `POST /api/mcp/servers/{id}/pause|resume|kill`. A notification is
  raised for every finding and every containment transition.
- [x] **C4. Verify GREEN.** Include an async scenario: an unattended session that
  trips a high-severity rule is auto-paused and cannot continue until resumed.

Result 2026-07-18: implemented the `McpContainment` helper in
`raiker/security/mcp_monitor.py` (shared by the monitor's automatic circuit
breaker and the owner's manual controls) and wired it into `McpSessionMonitor`:
every finding now raises an owner-facing notification, and a **high-severity**
finding (tool-set swap, error/auth-failure burst, or sensitive-shape coinciding
with a new host) auto-pauses the connection — once, without churning an ongoing
incident. Migration `RAIKER-1020-mcp-containment-notifications` adds the
`monitor_state` / `paused_reason` / `paused_at` columns and the shared
`notifications` table (also for Task 5), with storage accessors
(`set_mcp_monitor_state`, `insert/list/mark` notifications). The connector
executor gained a **containment gate**: a `paused`/`killed` connection fails
closed before the session runs (`mcp_connection_paused` / `mcp_connection_killed`
— honest missing-prerequisite refusal, not an owner-facing ban). New event types
`mcp_connection_paused` / `mcp_connection_resumed` / `mcp_connection_killed`;
control-service `pause_mcp_server` / `kill_mcp_server` / `resume_mcp_server`
(human-only, owner-scoped); endpoints `POST /api/mcp/servers/{id}/pause|resume|kill`,
`GET /api/mcp/servers/{id}/findings`, `GET /api/notifications`,
`POST /api/notifications/{id}/read`. Kill and pause are both **revocable** —
resume returns either to `active`. `tests/test_mcp_containment.py` adds 20 cases
(RED first, then GREEN). Full suite **1960 passed**; `ruff` clean; `mypy` 425
files clean; `compileall` clean; all five repo validators PASS. Two live drives:
(1) through the **real governed runtime** (`RuntimeAuthority.route_action` → a
real local stdio MCP server) — an unattended session tripped the high-severity
rule, the connection auto-paused, the next governed session was refused, resume
restored it, kill refused again, and the secret appeared in **no** finding,
notification, or session-log row; (2) a **real browser** (screenshot) driving the
running API server over authenticated HTTP through connect → pause → refuse →
resume → kill → refuse and listing the three transition notifications. **Phase D
(Connections UI + live monitor) is next.**

## Phase D — Connections page: "Connect via MCP" + live monitor

**Files:** `apps/web/src/lib/views/ConnectionsView.svelte`,
`apps/web/src/lib/views/McpView.svelte`, `apps/web/src/lib/api.ts`,
`apps/web/src/lib/apiTypes.ts`, `apps/web/src/lib/components/NotificationCenter.svelte`
(from Task 6), `*.test.ts`.

- [ ] **D1. Failing component tests** for: every connector row offers **"Connect
  via MCP"** (local template or remote URL + token); a connection card shows
  status, recent tool calls, and any open findings; **Stop** and **Resume**
  controls; a paused/killed banner; a notification appears on anomaly.
- [ ] **D2. Verify RED.**
- [ ] **D3. Implement** the unified connect flow (reuse the MCP page's create/test
  patterns), a live monitor panel per connection, and wire findings +
  notifications into the shared notification center. Plain-English copy
  throughout (owner preference).
- [ ] **D4. Verify GREEN** + a live browser drive with screenshots (connect a
  local and a mock remote MCP server, trip an anomaly, see the notification,
  Stop and Resume).

---

## Verification (every phase)

`python -m pytest`, `ruff`, `mypy`, `compileall`, the five repo validators;
web `check`/`lint`/`test`/`build`; and a live drive with screenshots for any
phase with a runtime or UI surface. No fabricated success anywhere — a remote
server that is unreachable or misbehaving fails closed with a redacted reason,
and monitoring/containment is proven with real (mock-server) sessions.

## Open decisions to confirm before building

1. **OAuth**: token-first now, OAuth redirect flow deferred to a later phase —
   OK?
2. **Findings/notifications ownership**: build the shared substrate here and have
   Task 5 reuse it (recommended), vs. build a minimal MCP-only version now.
3. **Auto-pause severity threshold**: which rules are "high-severity → auto-pause"
   vs. "notify only". Proposed high-severity: new-host + sensitive-shape together,
   server tool-set swap, auth-failure burst. Everything else notifies without
   pausing.

## Self-review

- Aligns with the Security Philosophy (monitor + contain + owner control, not
  prevention); the only hard refusals are missing-prerequisite fail-closed and
  the owner's own kill/pause — not owner-facing bans.
- Reuses existing substrate (MCP runtime, audit log, capability gate) and
  delivers the findings/notification layer Task 5 also needs.
- Honest scope: no fabricated brand integrations; remote auth is owner-supplied;
  containment is revocable.
