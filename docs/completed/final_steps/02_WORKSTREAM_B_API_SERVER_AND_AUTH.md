# Workstream B — API Server + Auth (Out-of-Process UI)

> Goal: expose the control plane (Workstream A) and the prompt path over an
> authenticated HTTP API so a separate-process web/desktop/mobile client can drive
> Raiker. Every request must resolve to a real governed `Principal`; no endpoint
> may bypass `RuntimeAuthority` / `PolicyEngine` / approvals / events.

Depends on: Workstream A (the API maps over `RuntimeControlService`).
Note: **B-core-auth** (B001–B004) is on the vertical-slice critical path; the rest
(B005+) can follow.

---

## B.0 Current reality

- There is **no** API server, no transport, and **no authentication / session →
  principal model**. `docs/GAP_AND_TODO_ANALYSIS.md` lists this as
  `missing/deferred` and security-critical.
- Principal resolution today is local single-user only:
  `resolve_local_principal(workspace_root, explicit_principal_id)` (CLI) backed by
  the owner-bootstrap flow (`/bootstrap-owner`, `raiker/...` owner principal).
- `httpx` is a runtime dep; `fastapi` is recorded as **deferred** in
  `docs/IMPLEMENTATION_STATUS.md` — this workstream activates it.

---

## B.1 Target architecture

New package: `raiker/api/` (the only network-facing surface).

```
raiker/api/
  __init__.py
  app.py          # FastAPI app factory create_app(workspace_root)
  auth.py         # session + token model, principal resolution
  sessions.py     # ApiSession store (SQLite-backed)
  schemas.py      # request/response pydantic-free dataclasses or pydantic models
  routes_control.py   # /runtime-mode, /capability-gates, /readiness
  routes_prompt.py    # /prompt (maps to AgentGateway), /events (stream)
  redaction.py    # response redaction guard
```

### Auth model (`raiker/api/auth.py`, `sessions.py`)

- **Session → Principal binding is the core requirement.** An authenticated API
  session resolves to a real `Principal` (same type used by `RuntimeAuthority`),
  so all existing governance (owner / `runtime_gate_manager`, AI-refused,
  domain scopes, risk acceptance) applies unchanged.
- First-run: bind to the bootstrapped owner principal. Token issuance is an
  owner/`runtime_gate_manager` action (a session can never escalate its own
  principal).
- Tokens: opaque, hashed at rest in SQLite (`api_sessions` table:
  `session_id, principal_id, token_hash, scopes, created_at, expires_at,
  revoked`). No JWT secret sprawl; rotation + revocation supported.
- Middleware extracts the token → resolves `ApiSession` → resolves `Principal`.
  Missing/expired/revoked → `401`. Authenticated-but-unauthorized (e.g. AI
  principal trying to flip a gate) → `403` with the authority reason code.
- **CSRF/CORS**: same-origin default; explicit allowlist for the UI origin.
  State-changing routes require a CSRF token for cookie-based sessions.
- **Rate limits** per session/principal on mutate + prompt routes.

### Control routes (`routes_control.py`)

Thin HTTP mappings over `RuntimeControlService` (Workstream A). They do **no**
business logic — resolve principal from session, call the service, serialize the
DTO, run the redaction guard.

| Method + path | Service call |
|---|---|
| `GET /api/runtime-mode` | `get_runtime_mode()` |
| `POST /api/runtime-mode/activate` | `activate_runtime_mode(mode, principal, reason)` |
| `POST /api/runtime-mode/disable` | `disable_runtime_mode(principal, reason)` |
| `GET /api/capability-gates` | `list_capability_gates(principal)` |
| `GET /api/capability-gates/{capability}` | `get_capability_gate(...)` |
| `POST /api/capability-gates/{capability}/set` | `set_capability_state(...)` |
| `POST /api/capability-gates/{capability}/disable` | `disable_capability(...)` |
| `GET /api/runtime-readiness` | `get_runtime_readiness(principal)` |

### Prompt + events routes (`routes_prompt.py`)

- `POST /api/prompt` → `AgentGateway.submit_prompt` / `astream_prompt`.
- `GET /api/events/stream` → Server-Sent Events / WebSocket projection of the
  append-only event log for the session, **redacted** (no raw prompts, tool
  output, file contents, secrets). Drives live gate/audit updates in the UI.

### Redaction guard (`redaction.py`)

A single function every response passes through that strips/asserts-absent:
secrets, API keys, Authorization headers, raw prompts/completions/stream chunks,
file contents, raw tool output. Reuse existing event-redaction patterns from
`raiker/events/`.

---

## B.2 Task breakdown

| Task ID | Title | Files | Acceptance |
|---|---|---|---|
| RAIKER-B001 | App factory + dependency wiring | `raiker/api/app.py` | `create_app(workspace_root)` returns a FastAPI app; health route; no business logic in routes. |
| RAIKER-B002 | Session store + token model | `raiker/api/sessions.py`, `raiker/storage/sqlite.py` (`api_sessions` table + migration) | Create/issue/rotate/revoke sessions; tokens hashed at rest; owner/gate-manager-only issuance. |
| RAIKER-B003 | Auth middleware → Principal | `raiker/api/auth.py` | Token → `ApiSession` → `Principal`; 401/403 semantics; AI principal cannot self-escalate. |
| RAIKER-B004 | Control routes over Workstream A | `raiker/api/routes_control.py`, `raiker/api/schemas.py` | All control endpoints return service DTOs as JSON; denials map to 403 + reason code; no logic beyond serialization. |
| RAIKER-B005 | Prompt route | `raiker/api/routes_prompt.py` | `POST /api/prompt` maps to `AgentGateway`; redacted responses. |
| RAIKER-B006 | Event stream | `raiker/api/routes_prompt.py` | Redacted SSE/WS projection of the event log per session. |
| RAIKER-B007 | Redaction guard | `raiker/api/redaction.py` | Every response filtered; test asserts no secret-like field escapes. |
| RAIKER-B008 | CSRF/CORS/rate-limit | `raiker/api/app.py`, `raiker/api/auth.py` | Same-origin default + UI-origin allowlist; CSRF on mutate; rate limits enforced. |
| RAIKER-B009 | Security regression suite | `tests/test_api_security.py` | Covers: unauth → 401, AI principal flip → 403, approval bypass attempt, cross-session leakage, redaction, CSRF, rate limit, token revocation. |
| RAIKER-B010 | Threat model record | `docs/THREAT_MODEL.md` (append API section) | Documented threat model for the API/auth surface before it is enabled by default. |

---

## B.3 Safety gates (must hold)

- The API is a **transport only**. No route may call a tool, store, or executor
  directly — only `RuntimeControlService` and `AgentGateway`.
- A session can never change which `Principal` it maps to, nor grant itself roles.
- AI/automation principals are refused control-plane mutations (authority enforces;
  API surfaces 403).
- The API server **ships disabled / not auto-started**. Running it is an explicit
  operator action; document it like other gated runtime.
- Redaction guard is mandatory and tested; no endpoint returns raw secrets.
- All `*_enabled` runtime flags remain `False`; this workstream does not enable any
  capability — it only lets an authorized principal *request* flips that
  Workstream C governs.

## B.4 Validation

Full §5 gate, plus `tests/test_api_security.py` must pass. Add a smoke test that
boots `create_app(tmp_workspace)` with a bootstrapped owner and exercises
`GET /api/capability-gates` (200) and an AI-principal flip (403).
</content>
