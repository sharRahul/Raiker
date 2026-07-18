# Raiker Control Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver a governed, responsive rebuild of every Raiker Svelte route with complete session lifecycle actions, real local MCP build/connect capabilities, resilient credential security controls, and verified green workflows.

**Architecture:** Preserve the FastAPI and governed-runtime boundary; Svelte remains a typed view/controller. Add session metadata and security records through additive SQLite migrations. Scope model selection, fallback/advisor state, capability gates, and decision modes per principal, migrating legacy global control state only to the original owner. Register MCP builder/connector executors in the existing authority and decision-mode paths. Surface health and security findings through authenticated API reads and the shared notification UI.

**Tech Stack:** Python 3.11+, FastAPI, SQLCipher SQLite, Svelte 5, TypeScript, Vite, Vitest, pytest, Playwright CLI, HIBP range API.

**Assumptions:**
- Active local accounts are administrators of their own isolated control plane. This will NOT permit one account to alter another account's model, capability, fallback, or decision-mode state.
- Current provider API keys have no configured provider-admin lifecycle API and therefore use verified manual replacement, not automatic provider-side issuance/revocation.
- HIBP checks are opt-in and require the existing egress policy to allow the public HIBP range endpoint; they will NOT run in offline or policy-denied mode.
- MCP supports local stdio servers in this slice. **Superseded (2026-07-17):** the
  original "will NOT connect to remote MCP endpoints" stance was a conservative
  default, not a requirement, and is replaced by the monitored-connections
  posture — remote MCP endpoints are **allowed when owner-added and monitored**
  (recorded, anomaly-checked, findings + notifications, instant stop + revocable
  auto-pause), never silent or unmonitored. See
  `docs/plans/2026-07-17-monitored-mcp-connections.md` and
  `docs/SECURITY_AND_POLICY.md` → "Security Philosophy".

---

## File Structure

- `raiker/storage/migrations.py`: additive session, MCP, credential-lifecycle, finding, and notification schema migrations.
- `raiker/storage/sqlite.py`: owner-scoped CRUD for session metadata, MCP profiles, credential lifecycle records, findings, and notifications.
- `raiker/control/dashboard.py`: DTO assembly and authenticated control operations.
- `raiker/api/schemas.py`, `raiker/api/routes_dashboard.py`: strict request contracts and routes.
- `raiker/runtime/executors/mcp.py`: governed MCP builder and local-stdio connector executors.
- `raiker/runtime/executors/__init__.py`, `raiker/phase_gates.py`, `raiker/runtime/authority/router.py`: registered MCP capabilities and authority routing.
- `raiker/security/credentials.py`, `raiker/security/monitoring.py`: rotation, local exposure scan, HIBP range check, health checks, redacted findings.
- `apps/web/src/lib/api.ts`, `apps/web/src/lib/apiTypes.ts`: typed API calls and DTOs.
- `apps/web/src/lib/components/`: shared route shell, toast/notification, menu, and responsive layout primitives.
- `apps/web/src/lib/views/`: rebuilt all route views and settings sections.
- `tests/`, `apps/web/src/lib/**/*.test.ts`: API, storage, executor, security, and UI regression coverage.

### Task 1: Restore Runtime Baseline and Legacy Account Authorization

**Files:**
- Modify: `raiker/auth/accounts.py`
- Modify: `raiker/api/auth.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `tests/test_accounts.py`
- Modify: `tests/test_api_model_selection.py`
- Modify: `pyproject.toml` only if the installed environment still lacks its declared `sqlcipher3-wheels` package

**Security flag:** `security`

**Does NOT cover:** This does not restore a role after a later intentional revocation, elevate non-human/inactive principals, or permit a session for an inactive account.

- [x] **Step 1: Write failing regression tests** proving a one-time bootstrap migration grants legacy active credential-backed human accounts the admin, approver, and runtime-gate-manager roles; preserves exactly one assignment record for each added role; never changes AI/non-account/inactive principals; and rejects inactive account login/API sessions.

```python
def test_bootstrap_backfills_legacy_active_account_roles_once(tmp_path: Path) -> None:
    principal_id = _create_legacy_account_without_roles(tmp_path)
    SQLiteStore(tmp_path)  # Applies the one-time migration.
    assert set(SQLiteStore(tmp_path).get_principal(principal_id)["role_ids"]) >= {
        ADMIN_ROLE_ID, APPROVER_ROLE_ID, RUNTIME_GATE_MANAGER_ROLE_ID,
    }
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_accounts.py tests/test_api_model_selection.py -q`

Expected: the migration and inactive-session protections are absent.

- [x] **Step 3: Implement the smallest repair** with a new migration marker that backfills only active credential-backed human accounts once. Keep `_ensure_bootstrap_roles` limited to role definitions; do not mutate roles during password login or MFA verification.

```python
if account_principal_is_active(connection, principal_id):
    add_missing_legacy_account_roles(connection, principal_id)
```

- [x] **Step 4: Verify GREEN and runtime import**

Run: `python -m pip install -e ".[dev]"; python -m pytest tests/test_accounts.py tests/test_api_model_selection.py -q`

Expected: dependency imports and both suites pass; legacy accounts receive their local administrator roles once, later revocations persist, and inactive sessions fail closed.

### Task 2: Isolate Users by Instance, Add Password Recovery, and Scope Control State

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/auth/accounts.py`
- Modify: `raiker/api/routes_auth.py`
- Modify: `raiker/api/schemas.py`
- Modify: `apps/web/src/lib/views/LoginView.svelte`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/control/service.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/gateway/agent_gateway.py`
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/models/*` only where a provider policy currently reads global gate state
- Create: `tests/test_per_account_control_state.py`
- Modify: `tests/test_accounts.py`
- Modify: `tests/test_api_auth.py`
- Create: `apps/web/src/lib/views/LoginView.test.ts`
- Modify: `tests/test_api_model_selection.py`
- Modify: `tests/test_api_decision_modes.py`

**Security flag:** `security`

**Does NOT cover:** Existing global preferences are not copied to every account. They are migrated only to the original owner; other accounts begin from the fail-closed defaults. Password recovery never uses email, security questions, or username-only verification.

- [x] **Step 1: Write failing integration and recovery tests** proving the current instance cannot register a second user, instance creation opens a separately initialized workspace, password reset requires valid TOTP or a one-time recovery code, and account A cannot read or change account B's selected model, fallback/advisor state, capability gate, or decision mode.

> **Landed elsewhere than planned.** `tests/test_per_account_control_state.py` was never created; its coverage is folded into `tests/test_accounts.py:566` (legacy controls migrate only to the original account), `:590` (a legacy secondary does not inherit a global enabled gate), and `:607` (the retrieval helper does not inherit the legacy global gate). Recovery/atomicity coverage lives in `tests/test_identity_transactions.py`; owner isolation in `tests/test_owner_context_isolation.py`. Step 2/6 commands below are corrected to the files that exist.

```python
assert client_a.put("/api/model-selection", json={"profile_id": "ollama-local-openai-compatible", "model": "qwen2.5"}).status_code == 200
assert client_b.get("/api/models").json()["current_model"] is None

with pytest.raises(AuthError):
    service.reset_password_with_recovery("owner", "invalid-code", "new-password")
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_accounts.py tests/test_api_model_selection.py tests/test_api_decision_modes.py -q`

Expected: a second in-instance registration is accepted, password recovery endpoints are missing, and account B observes the same global state as account A.

- [x] **Step 3: Make the account boundary explicit**. The current instance accepts its initial user only; the login screen creates additional users through the existing separate-instance endpoint. Add password-recovery tickets that verify TOTP or consume a backup recovery code before a new password is stored, with generic failure messages and short expiry.

```python
def complete_password_recovery(self, ticket_token: str, verification_code: str, new_password: str) -> None:
    ticket = self._sessions.get_by_token(ticket_token)
    if ticket is None or ticket.revoked or ticket.is_expired() or ticket.scope != "password_recovery":
        raise AuthError(GENERIC_AUTH_ERROR)
    account = self._store.get_account(ticket.principal_id)
    if account is None or not self._check_mfa(account, verification_code):
        raise AuthError(GENERIC_AUTH_ERROR)
    encoded, algo = passwords.hash_password(new_password)
    self._store.set_account_password(ticket.principal_id, encoded, algo, utc_now())
    self._sessions.revoke_others_for_principal(ticket.principal_id, ticket.session_id)
    self._sessions.revoke_session(ticket.session_id)
```

- [x] **Step 4: Add principal-keyed control tables and owner-only legacy migration** for model selection, fallback/advisor, capability state, and decision modes. Route all reads and mutations through the authenticated principal ID.

```sql
CREATE TABLE IF NOT EXISTS principal_capability_decision_modes (
  principal_id TEXT NOT NULL REFERENCES principals(principal_id),
  capability TEXT NOT NULL, decision_mode TEXT NOT NULL,
  set_at TEXT NOT NULL, PRIMARY KEY (principal_id, capability)
);
```

- [x] **Step 5: Pass principal context through model routing and capability policy** so a turn uses only the caller's controls and never falls back to a different account's selection.

> Principal context is normalized once at the boundary by `SQLiteStore.account_scope()` (`raiker/storage/sqlite.py`), which returns the principal id only when it names a real local account. The terminal client sends `UserMetadata`'s default `local_user` — truthy, but not a principal — so scoping on mere truthiness silently hid the CLI's own project, connectors, memory, and model selection. Use that predicate, never a truthiness test.

- [x] **Step 6: Verify GREEN**

Run: `python -m pytest tests/test_accounts.py tests/test_api_model_selection.py tests/test_api_decision_modes.py tests/test_async_model_runtime.py -q`

Expected: each user is created in a separate local instance, password recovery works only through an enrolled recovery factor, and each account independently administers its own controls without MFA; no principal can observe or change another principal's control state.

Result 2026-07-16: `EXIT=0`, 60 passed. Full-suite and static gates on the same tree:

```text
python -m pytest -q                     # EXIT=0, 0 failed (was 23)
python -m ruff check .                  # All checks passed!
python -m mypy raiker apps tests        # Success: no issues found in 418 source files
python -m compileall -q raiker tests    # exit 0
```

> **Acceptance history.** Two independent reviews (spec + quality) ran against the first implementation and **both returned Fail** — 7 criticals, each reproduced against a real workspace: CLI turns silently losing all context; `purge_account` leaving plaintext in `approved_memory_fts` and on disk; recovery orphaning the original-owner pointer to a deactivated principal; CLI-bootstrapped owners being unrecoverable; a non-idempotent migration suppressed and marked applied (permanently wedging owner isolation); a pre-existing connection leak; and 22 test regressions. All are fixed — see `docs/HANDOFF.md` for the per-defect record. Both reviews rated the underlying engineering sound (atomicity verified under 8-way concurrency; isolation tests confirmed to fail when the owner predicate is stripped) and called this "re-review after fixes, not a redesign". The re-reviews against the fixed tree are the acceptance gate; do not treat green gates alone as acceptance — the gates were green when the 7 criticals were still present.

> **Status (2026-07-17): Task 2 committed as `f97e6ce`.** Tasks 1 and 2 are
> implemented and on the branch (migrations, per-principal control tables,
> `SQLiteStore.account_scope()`, password recovery, owner-scoped data). Python
> gates re-verified green on that commit: `pytest` 1870 passed, `ruff` clean,
> `mypy` 418 files clean, and all five repo validators pass. **Tasks 3–11 below
> are not started** — verified against the tree, not the checkboxes. Task 3 is
> the next slice.

### Task 3: Add Safe Session Rename and Archive Lifecycle

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `tests/test_api_dashboard.py`
- Create: `tests/test_session_lifecycle.py`

**Security flag:** `security`

**Does NOT cover:** Archive does not delete transcripts, events, checkpoints, or permissions; delete remains separately confirmed and destructive.

- [x] **Step 1: Write failing API tests** for owner-scoped rename, archive, unarchive, list filtering, and cross-account refusal.

```python
response = client.put("/api/sessions/sess_a/archive", headers=_auth(owner_token))
assert response.json() == {"ok": True, "session_id": "sess_a", "archived": True}
assert "sess_a" not in [item["session_id"] for item in client.get("/api/sessions", headers=_auth(owner_token)).json()]
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_session_lifecycle.py -q`

Expected: 404 because archive/rename endpoints and storage state do not exist.

Result 2026-07-17: RED confirmed — 13 of 14 tests failed (missing endpoints/columns/`rename_session`). The one green test (`test_archive_does_not_delete_turns`) only asserts the transcript is preserved, which holds trivially while archive is a no-op.

- [x] **Step 3: Add an idempotent migration and owner-checked operations**.

```sql
ALTER TABLE sessions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sessions ADD COLUMN archived_at TEXT;
CREATE INDEX IF NOT EXISTS idx_sessions_owner_archived_updated ON sessions(user_id, archived, updated_at DESC);
```

```python
def set_session_archived(self, session_id: str, archived: bool, user_id: str) -> bool:
    return self._update_owned_session(session_id, user_id, {"archived": int(archived), "archived_at": utc_now() if archived else None})
```

Landed as migration `RAIKER-1015-session-archive-lifecycle` (applied via the idempotent `_apply_migration`/`_skip_existing_add_columns` path, so a partial or repeated run resumes cleanly), plus `SQLiteStore._update_owned_session`, `rename_session`, `set_session_archived`, and an `include_archived` flag on `list_sessions` (default active-only, matching the `list_project_tree` convention). The event-visibility filter passes `include_archived=True` so archiving never hides a session's events.

- [x] **Step 4: Add strict request/response routes and audit events** for rename/archive; list endpoints default to active sessions and accept `include_archived` only for the owner.

`PUT /api/sessions/{id}/rename` (strict `RenameSessionRequest`, `extra="forbid"`, server-side title normalization → 422 on invalid), `PUT /api/sessions/{id}/archive`, and `PUT /api/sessions/{id}/unarchive`. Mutations are human-only and owner-scoped; audit events `session_renamed`, `session_archived`, and `session_unarchived` are appended and added to the `EVENT_TYPES` registry. `GET /api/sessions` gains an owner-scoped `include_archived` query flag.

- [x] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_session_lifecycle.py tests/test_api_dashboard.py -q`

Expected: active and archived records remain isolated per account; archive is reversible.

Result 2026-07-17: `EXIT=0`, 44 passed. A live end-to-end drive (rename → archive → active/`include_archived` listings → unarchive, migration idempotency over repeated opens, 422 on empty/overlong/extra-field input, audit events, 403 on unknown/foreign sessions) all passed. Static/regression gates on the same tree: `ruff` clean, `mypy` 419 files clean, `compileall` exit 0.

### Task 4: Implement Governed Local MCP Builder and Connector

**Files:**
- Modify: `pyproject.toml`
- Modify: `raiker/phase_gates.py`
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/runtime/executors/__init__.py`
- Create: `raiker/runtime/executors/mcp.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_dashboard.py`
- Create: `tests/test_mcp_runtime.py`
- Modify: `docs/IMPLEMENTATION_STATUS.md`

**Security flag:** `security`

**Does NOT cover:** Remote HTTP MCP transport, OAuth discovery, arbitrary shell commands, and execution of unreviewed MCP tools are excluded. Local stdio commands are owner-configured, workspace-scoped, allowlisted, and approval-governed.

- [x] **Step 1: Load `mcp-builder` and current official Python SDK documentation; write failing tests first** for disabled capability denial, command validation, owner isolation, safe server-template creation, and redacted audit metadata.

```python
def test_mcp_connector_denies_unapproved_command(workspace: Path) -> None:
    outcome = execute_mcp_connect(workspace, principal_id="principal_owner", command=["cmd.exe", "/c", "whoami"])
    assert outcome["error"]["type"] == "mcp_command_not_allowlisted"
```

> Landed as `tests/test_mcp_runtime.py` (22 tests). The MCP wire protocol is
> implemented **directly over the documented JSON-RPC stdio format**, with no
> third-party `mcp` SDK dependency, so the runtime stays hermetic/local-only and
> `pyproject.toml` was intentionally left unchanged. The generated
> `python-stdio-echo` template speaks the same wire format, making the
> builder+connector testable end-to-end with no network. Executors return the
> repo's `ExecutionResult` (not the illustrative `ExecutorResult.error`).

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_mcp_runtime.py -q`

Expected: imports/endpoints are missing.

Result 2026-07-17: RED confirmed — `ModuleNotFoundError: raiker.runtime.executors.mcp`.

- [x] **Step 3: Add `mcp_builder_runtime` and `mcp_connector_runtime` as real capabilities** and map `mcp_server_create`, `mcp_connect`, `mcp_list_tools`, and `mcp_call_tool` through `CAPABILITY_GATE_MAP`.

Append these exact entries to the existing `REAL_EXECUTOR_CAPABILITIES` literal:

```python
    "mcp_builder_runtime",
    "mcp_connector_runtime",
```

> Done: both caps added to `REAL_EXECUTOR_CAPABILITIES`, `RUNTIME_DOMAIN_CAPABILITIES`,
> the Tier-5 executed-caps group (full readiness → ship `ENABLED_RUNTIME`), the
> `activation.py` requirement registry (threat_ack + human_confirm), the four
> action types + two self-maps in `CAPABILITY_GATE_MAP`, and the four action
> types in the policy `approval_required_actions`. New id prefix `mcp_`. Threat
> models: `docs/threat-models/mcp-builder.md`, `docs/threat-models/mcp-connector.md`.

- [x] **Step 4: Implement local MCP server creation and connection** using the documented MCP SDK, validated workspace-relative output paths, a fixed allowlisted executable registry, bounded stdio payloads/timeouts, and redacted event fields.

```python
if not command or command[0] not in allowed_commands:
    return ExecutorResult.error("mcp_command_not_allowlisted")
if any(Path(part).is_absolute() for part in command[1:]):
    return ExecutorResult.error("mcp_argument_path_not_workspace_relative")
```

> Landed in `raiker/runtime/executors/mcp.py`: `McpBuilderExecutor`
> (`mcp_server_create`) writes a reviewed template to a workspace-relative path
> (absolute/`..` escape rejected) and records an owner-scoped `mcp_servers` row;
> `McpConnectorExecutor` (`mcp_connect`/`mcp_list_tools`/`mcp_call_tool`)
> validates the interpreter allowlist + workspace-relative args, then runs a
> bounded `subprocess.Popen`+`communicate` JSON-RPC stdio session (≤60 s, ≤200 KB)
> and returns **redacted metadata only** (tool names/count; content length +
> redaction flag — never raw content). Storage: migration
> `RAIKER-1016-mcp-server-profiles` + owner-scoped CRUD. Owner-scoped read:
> `GET /api/mcp/servers` (`McpServerView`); building/connecting stays a governed
> runtime action, not a REST mutation.

- [x] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_mcp_runtime.py tests/test_executor_default_registry.py tests/test_connector_tool_policy.py -q`

Expected: only authenticated owner-approved, capability-enabled local stdio MCP operations complete; all other paths fail closed.

Result 2026-07-17: `EXIT=0`, 31 passed (the referenced trio). Static/regression gates on the same tree: `ruff` clean, `mypy` 421 files clean, all five repo validators PASS. A live end-to-end drive against a fresh temp workspace (build → connect → list tools → redacted tool call with a secret payload → fail-closed on unallowlisted command / absolute-path arg / disabled gate → owner-scoped `GET /api/mcp/servers` hiding another principal's server) all behaved correctly; the running web app was screenshotted for regression. Full-suite result recorded in HANDOFF.

### Task 4b: MCP Server Management Web Page (create / manage / delete)

> **Plan amendment (2026-07-17), requested by the owner.** Task 4 delivered the
> governed runtime + a read-only `GET /api/mcp/servers`. This task pulls the
> dedicated MCP management surface forward from the Task 9 route rebuild into its
> own page so the owner can create, inspect, test, rename, and delete local MCP
> servers end-to-end from the web app.

**Files:**
- Modify: `raiker/storage/migrations.py` (tools/tool_count columns)
- Modify: `raiker/storage/sqlite.py` (delete/rename/tools CRUD)
- Modify: `raiker/runtime/executors/mcp.py` (persist discovered tools on connect)
- Modify: `raiker/control/service.py` (governed create/connect + owner-scoped rename/delete)
- Modify: `raiker/control/dashboard.py` (`McpServerView` carries tools/status)
- Modify: `raiker/api/schemas.py`, `raiker/api/routes_dashboard.py` (write routes)
- Create: `apps/web/src/lib/views/McpView.svelte`
- Modify: `apps/web/src/lib/api.ts`, `apps/web/src/lib/apiTypes.ts`, `apps/web/src/lib/nav.ts`, `apps/web/src/App.svelte`
- Modify: `tests/test_mcp_runtime.py`
- Create: `apps/web/src/lib/views/McpView.test.ts`

**Security flag:** `security`

**Does NOT cover:** No side-door around governance. **Create** and **Test/Connect**
run the real capability through `route_action` (capability gate + policy +
decision mode + audit); when the gate is disabled the page surfaces the governed
reason and points to Capabilities rather than bypassing it. **Rename** and
**Delete** are owner-scoped, human-only metadata operations (delete also removes
the generated template file inside the workspace). Editing a server's raw command
and calling its tools from the page are out of scope for this slice — tool calls
remain a governed runtime/agent action.

- [x] **Step 1: Write failing API tests** for create (governed), connect/test
  (persists discovered tools), rename, delete (removes profile + file), owner
  isolation, and capability-gate denial. Landed as 9 new cases in
  `tests/test_mcp_runtime.py` (+ `McpView.test.ts` for the page).
- [x] **Step 2: Verify RED.**
- [x] **Step 3: Backend.** Migration `RAIKER-1017-mcp-server-runtime-state` adds
  `tools` / `tool_count`; storage gains `delete_mcp_server`, `rename_mcp_server`,
  and tool persistence; `RuntimeControlService` gains governed `create_mcp_server`
  / `connect_mcp_server` and owner-scoped `rename_mcp_server` / `delete_mcp_server`;
  the connector executor persists discovered tools on connect; strict
  request/response routes `POST /api/mcp/servers`, `POST /api/mcp/servers/{id}/connect`,
  `PUT /api/mcp/servers/{id}`, `DELETE /api/mcp/servers/{id}`.
- [x] **Step 4: Frontend.** `McpView.svelte` — create form (name + template),
  server list with status pill, discovered tools, and command; test/rename/delete
  actions; a capability-gate banner. Wired into `nav.ts` + `App.svelte`
  (Steering → "MCP Servers").
- [x] **Step 5: Verify GREEN.**

Result 2026-07-17: `pytest` full suite **1918 passed** (exit 0); `ruff` clean;
`mypy` 421 files clean; all five repo validators PASS. Web: `npm run check` 0
errors, `npm run lint` clean, `npm test` 141 passed (McpView 4/4), `npm run build`
exit 0. Live browser drive against a registered account (caps enabled): the page
listed both servers with status + discovered tools, and clicking **Test** on the
un-connected server flipped it to Connected with its `echo` / `workspace_ping`
tools — screenshots captured. Create/connect run through the governed capability
(a disabled gate surfaces `disabled_by_capability_gate` and points to
Capabilities); rename/delete are owner-scoped and human-only.

### Task 5: Add Credential Lifecycle, Breach Detection, and Self-Monitoring

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Create: `raiker/security/credentials.py`
- Create: `raiker/security/monitoring.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_dashboard.py`
- Create: `tests/test_credential_security.py`
- Create: `tests/test_runtime_monitoring.py`

**Security flag:** `security`

**Does NOT cover:** Raw secret values are never stored in findings; HIBP is skipped without opt-in and permitted egress; provider-side rotation is not claimed for current providers.

- [x] **Step 1: Write failing tests** for 75/90-day status, verified manual replacement, redacted local finding, k-anonymous password range request, offline HIBP skip, deduplicated health alerts, and cleared recovery alerts.

```python
def test_hibp_only_sends_sha1_prefix(httpx_mock) -> None:
    check_password_breach("correct horse", enabled=True)
    assert httpx_mock.last_request.url.path.count("/") == 3
    assert len(httpx_mock.last_request.url.path.rsplit("/", 1)[-1]) == 5
```

- [x] **Step 2: Verify RED** â€” captured before the Task 5 service and route implementation.

Run: `python -m pytest tests/test_credential_security.py tests/test_runtime_monitoring.py -q`

Expected: security services and authenticated endpoints do not exist.

- [x] **Step 3: Add additive, owner-scoped records** for credential lifecycle, redacted security findings, health observations, and notifications. Migration `RAIKER-1021-credential-security` adds owner-scoped lifecycle and monitor-transition tables alongside the shared findings/notifications substrate.

```sql
CREATE TABLE IF NOT EXISTS credential_lifecycle (
  credential_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, provider TEXT NOT NULL,
  rotated_at TEXT NOT NULL, verified_at TEXT, due_at TEXT NOT NULL, status TEXT NOT NULL
);
```

- [x] **Step 4: Implement security services**: 75-day warning/90-day overdue status, verified replacement requiring encrypted credential metadata, configured workspace-relative local scans, opt-in SHA-1 prefix/range checks, and deduplicated alert/recovery transitions. The password, full hash, HIBP response, and local match never persist.

- [x] **Step 5: Add authenticated dashboard reads and explicit scan/check actions**; the Security & Login card renders lifecycle, redacted findings, last health state, replacement verification, local scan, explicit health check, and an explicit breach opt-in. `GET /api/security/health` is read-only; `POST /api/security/health-check` performs the check.

- [x] **Step 6: Verify GREEN** â€” focused lifecycle/monitor/API tests and the Security & Login Vitest suite pass; final repository and browser evidence is recorded in `docs/HANDOFF.md`.

Run: `python -m pytest tests/test_credential_security.py tests/test_runtime_monitoring.py tests/test_api_security.py -q`

Expected: no raw credential is present in the database finding, event payload, API response, or HTTP request URL beyond a five-character password hash prefix.

**Bounded next-security-detector roadmap (not implemented by Task 5):** Add one
source-bounded detector at a time for dependency/OS advisories, auth/session
anomalies, audit-policy violations, configuration drift, secret exposure,
runtime egress, and integrity checks. Each detector must emit only a redacted
finding, deduplicated notification, concrete remediation, and tests for alert,
deduplication, recovery, owner isolation, and redaction. Do not claim universal
or exhaustive system-security detection.

### Task 6: Extend Typed Web Contracts and Shared Control Deck Primitives

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/components/Sidebar.svelte`
- Modify: `apps/web/src/lib/components/Topbar.svelte`
- Modify: `apps/web/src/lib/components/NotificationCenter.svelte`
- Create: `apps/web/src/lib/components/PageState.svelte`
- Create: `apps/web/src/lib/components/SessionMenu.svelte`
- Create: `apps/web/src/lib/components/ToolControlBoard.svelte`
- Create: `apps/web/src/lib/components/ResponsivePage.svelte`
- Create: `apps/web/src/lib/loopback.ts`
- Modify: `apps/web/src/App.svelte`
- Create: `apps/web/src/lib/components/SessionMenu.test.ts`

**Security flag:** `security`

**Does NOT cover:** Components never decide authorization; they render server truth and show server remediation.

- [x] **Step 1: Write failing component tests** for all six session menu actions, loopback-only share copy, notification state, and hiding decision controls for non-executable tools.

```ts
it("does not render decision controls for a deferred capability", async () => {
  render(ToolControlBoard, { gates: [makeGate({ capability: "finance_runtime", blocked_reason_code: "activation_blocked:no_executor" })] });
  expect(screen.queryByRole("group", { name: /decision mode/i })).not.toBeInTheDocument();
});
```

- [x] **Step 2: Verify RED**

Run: `npm --prefix apps/web run test -- --run SessionMenu.test.ts`

Expected: shared components/imports are missing.

- [x] **Step 3: Add typed endpoint methods and DTOs**, then implement shared tokens and components. Use the login wordmark's Manrope uppercase tracking in `Sidebar`.

```css
.brand-name {
  font-family: var(--font-sans);
  font-weight: 800;
  letter-spacing: 0.45em;
  text-transform: uppercase;
}
```

- [x] **Step 4: Verify GREEN**

Run: `npm --prefix apps/web run check; npm --prefix apps/web run test -- --run SessionMenu.test.ts`

Expected: shared shell compiles, menu actions are keyboard reachable, and unavailable controls are absent.

**Result (2026-07-18):** `api.renameSession` and `api.archiveSession` cover the
already-supported owner-scoped lifecycle routes; their simple response shapes do
not need a duplicate `apiTypes.ts` DTO. `PageState`, `ResponsivePage`,
`SessionMenu`, and `ToolControlBoard` are presentational/callback-only. The
existing notification center is source-neutral, and the existing sidebar uses
the approved Manrope uppercase wordmark. `App.svelte` now uses the responsive
shell without rebuilding route bodies; Tasks 7-9 remain the consumers/migration
work. At 390px the shell uses an icon rail with labelled links and compact
topbar/content padding. Focused red/green tests, full web gates, two uncached
Python batches, static checks, and repository validators passed; the final
commit/push and exact-tip CI check are tracked in the Task 6 detail plan.

### Task 7: Rebuild Conversation, Search, Memory, Projects, Tasks, Approvals, Brain, and Work Routes

**Files:**
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/SearchChatView.svelte`
- Modify: `apps/web/src/lib/views/MemoryView.svelte`
- Modify: `apps/web/src/lib/views/ProjectsView.svelte`
- Modify: `apps/web/src/lib/views/TasksView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/BrainView.svelte`
- Modify: `apps/web/src/lib/views/WorkInActionView.svelte`
- Modify: corresponding existing `*.test.ts` files

**Security flag:** `none`

**Does NOT cover:** Route presentation changes do not alter approval execution semantics, task scheduling semantics, or memory policy.

- [x] **Step 1: Add failing route tests** for route-level loading/error/empty states and preserved actions.
- [x] **Step 2: Verify RED** with `npm --prefix apps/web run test -- --run <affected test files>`.
- [x] **Step 3: Rebuild each route with `ResponsivePage`, `PageState`, and compact tool-focused hierarchy**. Preserve each existing typed API call and semantic status label; do not add client-side authority.
- [x] **Step 4: Verify GREEN** with `npm --prefix apps/web run check; npm --prefix apps/web run test`.

### Task 8: Rebuild Sessions and Checkpoints

**Files:**
- Modify: `apps/web/src/lib/views/SessionsView.svelte`
- Modify: `apps/web/src/lib/views/SessionsView.test.ts`
- Modify: `apps/web/src/lib/views/CheckpointsView.svelte`
- Create: `apps/web/src/lib/views/CheckpointsView.test.ts`

**Security flag:** `none`

**Does NOT cover:** Checkpoint restore remains metadata-only until a governed restore executor exists.

- [x] **Step 1: Write failing tests** for select-all via keyboard, filtered-selection cleanup, rename/archive/unarchive, session resume link, and checkpoint filter/metadata labels.

```ts
await fireEvent.click(screen.getByRole("checkbox", { name: "Select all sessions" }));
expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
```

- [x] **Step 2: Verify RED**

Run: `npm --prefix apps/web run test -- --run SessionsView.test.ts CheckpointsView.test.ts`

Expected: new lifecycle controls and checkpoint test file are absent.

- [x] **Step 3: Rebuild Sessions** around a responsive conversation table/detail rail; use `SessionMenu` for share/rename/move/pin/archive/delete; clear hidden selections when scope/filter changes.
- [x] **Step 4: Rebuild Checkpoints** as a recorder timeline with explicit session/turn/task context and the text `Snapshot metadata only` instead of an implied restore action.
- [x] **Step 5: Verify GREEN**

Run: `npm --prefix apps/web run check; npm --prefix apps/web run test -- --run SessionsView.test.ts CheckpointsView.test.ts`

Expected: select-all works from pointer and keyboard; archived sessions are not accidentally deleted; checkpoints make their non-restoring status clear.

### Task 9: Rebuild Models, Connections, Capabilities, Settings, Activity, and Diagnostics

**Files:**
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Modify: `apps/web/src/lib/views/ConnectionsView.svelte`
- Modify: `apps/web/src/lib/views/CapabilitiesView.svelte`
- Modify: `apps/web/src/lib/views/CapabilitiesView.test.ts`
- Modify: `apps/web/src/lib/views/SettingsView.svelte`
- Modify: `apps/web/src/lib/views/settings/*.svelte`
- Modify: `apps/web/src/lib/views/ActivityView.svelte`
- Modify: `apps/web/src/lib/views/DiagnosticsView.svelte`
- Create: `apps/web/src/lib/views/SettingsView.test.ts`
- Create: `apps/web/src/lib/views/ModelsView.test.ts`

**Security flag:** `security`

**Does NOT cover:** Settings fields that have no active backend consumer are removed or marked unavailable; the UI does not simulate unsupported provider login/rotation.

- [x] **Step 1: Write failing tests** for the repaired Ollama selection, tool-domain grouping, no selector for non-executors, MCP builder/connector rows, serialized settings save/error feedback, credential status, breach alerts, and health recovery alerts.
- [x] **Step 2: Verify RED**

Run: `npm --prefix apps/web run test -- --run CapabilitiesView.test.ts ModelsView.test.ts SettingsView.test.ts`

Expected: new tool grouping, security cards, and test files are absent.

- [x] **Step 3: Rebuild Models and Connections** with provider truth, explicit repair guidance, lifecycle status, and manual credential replacement.
- [x] **Step 4: Rebuild Capabilities using `ToolControlBoard`**. Group executable tools by domain: Workspace, Local execution, Network, Models, Connectors, MCP, and Automation. Omit inherent/read-only/deferred capabilities entirely.
- [x] **Step 5: Rebuild Settings as supported preferences and security posture**. Implement a single queued `save()` that awaits confirmation, rolls back to the last server snapshot on failure, and exposes a page-level save/error status. Wire theme, spacing, font, and startup route into the shell; wire in-app/desktop notification preference into `NotificationCenter`; wire history/retention and attachment threshold into the request/storage paths only after backend support exists; keep the working vault, MFA, password, and device-session operations. Sensitive Settings mutations require password elevation; request an MFA code only if the account enrolled MFA and the specific sensitive control requires it. Never require MFA for models, capability choices, or routine use. Remove voice, emergency access, cloud/cache, export, and other unsupported interactive controls rather than presenting them as settings. Place credential lifecycle, breach scans, and self-monitoring controls in Security.
- [x] **Step 6: Rebuild Activity and Diagnostics** as the audit/operational evidence views, including redacted health and security transitions.
- [x] **Step 7: Verify GREEN**

Run: `npm --prefix apps/web run check; npm --prefix apps/web run test`

Expected: all controls reflect server data; selectors appear only for real tools; settings never silently lose a failed write.

### Task 10: Rebuild Login, Application Shell, and Mobile Behavior

**Files:**
- Modify: `apps/web/src/lib/views/LoginView.svelte`
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/lib/components/Sidebar.svelte`
- Modify: `apps/web/src/lib/components/Topbar.svelte`
- Modify: `apps/web/src/app.css`
- Create: `apps/web/src/lib/views/LoginView.test.ts`

**Security flag:** `security`

**Does NOT cover:** Authentication protocol and MFA verification remain server-owned; the redesign does not change password or session security semantics.

- [x] **Step 1: Write failing tests** for keyboard navigation, the login-aligned RAIKER mark, notification access, and mobile navigation without horizontal overflow.
- [x] **Step 2: Verify RED** with `npm --prefix apps/web run test -- --run LoginView.test.ts`.
- [x] **Step 3: Apply the shared Control Deck shell** across light/dark themes, 375/768/1024/1440 breakpoints, focus management, touch targets, and reduced-motion behavior.
- [x] **Step 4: Verify GREEN** with `npm --prefix apps/web run check; npm --prefix apps/web run test`.

**Responsive-navigation follow-up (2026-07-18):** The permanent phone icon
rail is replaced by a five-item bottom bar (New Chat, Sessions, Tasks,
Projects, More); More opens the existing full grouped navigation drawer. From
640px through 1023px, a compact top-bar Menu trigger opens that drawer without
reserving a rail; at 1024px and wider the full sidebar returns. The drawer
closes through route selection, Escape, or its scrim and restores trigger
focus for keyboard dismissal. `Sidebar.test.ts` was driven RED before the
drawer existed, then GREEN; `App.test.ts` scopes its grouped-route assertion to
the named drawer landmark because jsdom intentionally renders both responsive
structures without CSS breakpoint layout. Local web verification: `svelte-check`
0 errors/warnings, lint clean, 35 Vitest files / 196 passed / 1 skipped, and
production build passed. A disposable local account was live-tested at
375px, 768px, 1024px, and 1440px during one resize sequence: no horizontal
overflow, phone bottom bar and More drawer, tablet trigger/scrim drawer,
desktop full sidebar, Escape/scrim dismissal, and a drawer route selection all
passed with no browser console errors or warnings. Screenshots are intentionally
untracked under `output/playwright/adaptive-navigation-*.png`.

### Task 11: Browser Validation and Full Workflow Proof

**Files:**
- Modify: targeted test files only if browser validation exposes a reproducible regression

**Security flag:** `security`

**Does NOT cover:** Browser tests do not prove a third-party provider's external management API because no such integration is configured.

- [x] **Step 1: Build and start a temporary-workspace server** after dependencies are installed.

```powershell
npm --prefix apps/web run build
python -m apps.api.main --workspace C:\Users\1niki\AppData\Local\Temp\opencode\raiker-browser-audit --port 8766 --no-browser
```

- [x] **Step 2: Use the Playwright CLI wrapper** to register/login only against the temporary workspace, visit every route, exercise session menu and model selection, inspect MCP/security/notification states, and capture screenshots under `output/playwright/`.

```powershell
bash /mnt/c/Users/1niki/.codex/skills/playwright/scripts/playwright_cli.sh open http://127.0.0.1:8766
bash /mnt/c/Users/1niki/.codex/skills/playwright/scripts/playwright_cli.sh snapshot
```

- [x] **Step 3: Run the full local gates**.

```powershell
python -m pytest --collect-only -q
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python -m compileall -q raiker apps tests
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/validate_runtime_enablement_readiness.py
python scripts/validate_local_single_user_runtime.py
python scripts/validate_documentation_truthfulness.py
npm --prefix apps/web run lint
npm --prefix apps/web run check
npm --prefix apps/web run test
npm --prefix apps/web run build
```

- [x] **Step 4: Stub scan and final diff review**.

```powershell
rg -n "TODO|FIXME|placeholder|NotImplementedError|raise NotImplementedError" raiker apps tests --glob "*.py" --glob "*.ts" --glob "*.svelte"
git diff --check
git status --short
```

- [x] **Step 5: Commit and push all verified changes** only after every command exits successfully. Completed by `37f681b` (`Rebuild Raiker control deck routes`); exact-tip CI, Web UI, and Phase Status Validation are green.

```powershell
git add -A
git commit -m "Rebuild Raiker control deck and security controls"
git push origin main
```

## Plan Self-Review

- Spec coverage: Tasks 1-4 cover authorization, session lifecycle, MCP, rotation, breach checks, and self-monitoring. Tasks 5-9 cover every Svelte route and the shared shell. Task 10 covers browser, CI, web, phase, static, and commit/push verification.
- Type consistency: API DTO/client work precedes view work; capability names are defined before MCP UI grouping; session lifecycle endpoints precede `SessionMenu`.
- Scope check: current provider rotation is explicitly manual and verified. Remote MCP and provider-side automatic issuance are explicitly excluded rather than simulated.
