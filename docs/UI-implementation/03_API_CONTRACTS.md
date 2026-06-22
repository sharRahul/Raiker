# API Contracts (UI backend surface)

> Planning document. Each endpoint below MUST: require Bearer auth, reuse an existing governed
> service (no direct SQLite, no new policy engine), emit the existing event types, and ship with
> tests. Request/response bodies are dataclasses in `raiker/api/schemas.py` serialized via the
> existing `serialize_dto`. Unknown request fields are rejected (Phase-1 contract rule).

## Conventions

- **Auth:** `Authorization: Bearer <token>`. Resolved by `raiker/api/auth.py::AuthMiddleware`
  into `(ApiSession, Principal)`.
- **Denials:** mutating routes return `403 {"ok": false, "reason_code": "<code>"}` (matches
  existing control routes).
- **Redaction:** all JSON responses pass through `RedactionMiddleware`.
- **Origin:** SPA served from the same FastAPI app (no CORS). Server binds `127.0.0.1`.

## Existing routes (already implemented — reuse as-is)

| Method | Path | Service | Notes |
|---|---|---|---|
| GET | `/api/health` | — | liveness |
| GET | `/api/runtime-mode` | `RuntimeControlService.get_runtime_mode` | read |
| POST | `/api/runtime-mode/activate` | `RuntimeControlService.activate_runtime_mode` | human-only, RGM role |
| POST | `/api/runtime-mode/disable` | `RuntimeControlService.disable_runtime_mode` | human-only |
| GET | `/api/capability-gates` | `RuntimeControlService.list_capability_gates` | per-principal visibility |
| GET | `/api/capability-gates/{cap}` | `RuntimeControlService.get_capability_gate` | read |
| POST | `/api/capability-gates/{cap}/set` | `RuntimeControlService.set_capability_state` | governed |
| POST | `/api/capability-gates/{cap}/disable` | `RuntimeControlService.disable_capability` | governed |
| GET | `/api/runtime-readiness` | `RuntimeControlService.get_runtime_readiness` | read |

Security Settings → Runtime Mutations uses these directly; the step-up window supplies `reason`
and (where required) the confirmation token / threat-model ack before the call.

## New routes (to add)

### Auth
**`POST /api/auth/session`** — mint a local API token for the resolved owner principal.
- Service: `cli/principal_resolver.resolve_local_principal` + `ApiSessionStore.create_session`.
- Request: `{ "as_principal": string | null }` (defaults to resolved local owner).
- Response: `{ "token": string, "session_id": string, "principal_id": string, "expires_at": string|null }`.
- Rules: local-only; **human principals only** (reject AI/automation); no token in logs (redacted).
- Tests: success for owner; reject when no owner bootstrapped; reject AI principal.

### Sessions / Turns
**`GET /api/sessions`**, **`GET /api/sessions/{session_id}`** — read-only session/turn lists.
- Service: `SQLiteStore` session/turn read methods (via a thin read accessor, not raw SQL in route).
- Response: list of `{session_id, title, created_at, turn_count, last_status}` / detail with turns.
- Note: this is an **API read view**; the deferred `/sessions` **CLI** command stays deferred.

**`GET /api/turns/{turn_id}`** — turn detail: ordered events, plan/steps, proposals, policy
decisions, verification result.
- Service: `EventViewer` (filter by turn) + checkpoint/plan reads.
- Response: `{turn_id, session_id, status, phases:[{name, status, timestamp, events:[...]}], proposals:[...], policy_decisions:[...]}`.

### Prompts (turn execution)
**`POST /api/prompts`** — submit one governed turn.
- Service: build full `PromptEnvelope` with `ClientMetadata(type="web_ui", ...)`, call
  `AgentGateway.submit_prompt_async`.
- Request: `{ "text": string, "session_id": string|null, "options": {planning_mode?, approval_mode?, model_profile?, max_tool_calls?} }`.
- Response: serialized `AgentResponse` (`status`, `message`, `events_path`, `checkpoint_path`,
  `approval?`, `last_event_id`, `turn_id`, `session_id`).
- Tests: valid prompt → `prompt_received`…`turn_closed` events; invalid envelope → `failed`.

**`GET /api/prompts/{turn_id}/stream`** — Server-Sent Events over `AgentGateway.astream_prompt`.
- Emits text deltas + lifecycle `StreamEvent`s, terminating with `FINAL` (the `AgentResponse`).
- Same authority as `POST /api/prompts` (durable log, checkpoint, turn close identical).

### Approvals
**`GET /api/approvals`**, **`GET /api/approvals/{id}`** — pending list + detail.
- Service: `ApprovalInbox.list_pending` + detail (payload preview + diff for file mutations).
- Response: `{approval_id, action_id, capability, risk_level, age, source_turn_id, status, preview, diff?}`.

**`POST /api/approvals/{id}/resolve`** — record a decision.
- Service: `ApprovalInbox.resolve(approval_id, approve, resolved_by)`.
- Request: `{ "approve": boolean, "reason": string }`.
- Response: `{ "approval_id": string, "status": "approved"|"denied", "executes_action": false }`.
- **`executes_action` is always `false`** and echoed so the UI cannot imply execution.
- Tests: approve → `approval_received` event, `executes_action=false`; deny → `approval_denied`;
  tampered payload hash → rejected.

### Events / Checkpoints
**`GET /api/events`** — filtered append-only events.
- Service: `EventViewer`. Query: `session_id?, turn_id?, event_type?, limit?, offset?`.
- Response: list of `AgentEvent` dicts (read-only). Append-only; no write route.

**`GET /api/checkpoints`**, **`GET /api/checkpoints/{id}`** — checkpoint metadata + rewind metadata.
- Service: `CheckpointService`.
- Response: `{checkpoint_id, session_id, turn_id, summary, last_event_id, created_at, rewind_metadata?}`.

### Models
**`GET /api/models`** — profiles, current, health, capabilities.
- Service: `ModelProfileRegistry` / `ModelRouter`. Response includes `no_silent_hosted_fallback: true`.

**`POST /api/models/use`** — governed profile switch.
- Request: `{ "profile_id": string }`. Response: `{ "ok": boolean, "current": {...}, "reason_code"? }`.
- Hosted/private model runtimes remain deferred and are shown un-selectable for runtime enable.

### Diagnostics
**`GET /api/diagnostics`** — readiness + validator-status surface.
- Service: `RuntimeControlService.get_runtime_readiness` + readiness reports. **Does not run shell**;
  returns stored/derived status only.
- Response: `{readiness:{...}, disabled_capabilities:[...], missing_config:[...], provider_health:[...]}`.

### Tasks / Interrupts (STOP switch)
**`GET /api/tasks`** — active/recent tasks.
- Service: `TaskManager.list_tasks`. Response: `[{task_id, session_id, status, summary, updated_at}]`.

**`POST /api/interrupts`** — governed interrupt; powers the STOP switch.
- Service: build `InterruptAction`, call `InterruptController.apply_at_safe_boundary`
  (and/or `TaskManager.cancel_task`).
- Request: `{ "session_id": string, "task_id": string|null, "all": boolean, "action_type": "cancel"|"pause"|"resume"|"steer", "reason": string, "steer_text"?: string }`.
- Response: `{ "applied": [{task_id, result}], "safe_boundary": true }`.
- **Human-only.** Emits `interrupt_received`, `safe_boundary_reached`, and `task_cancelled`/
  `task_steered`. Semantics: applied at next safe boundary, **not** an instant kill.
- Tests: cancel-all cancels active tasks at safe boundary + emits events; AI principal rejected.

## Server wiring & launch

- `raiker/api/app.py::create_app` includes the new routers and mounts the built SPA
  (`apps/web/dist`) as static files at `/`.
- `apps/api/main.py` runs `uvicorn` bound to `127.0.0.1` (new `uvicorn` dependency); optional
  console script (e.g. `raiker-web`) added in `pyproject.toml`.

## Test obligations (every new route)

1. Auth required (401 without Bearer).
2. Happy path returns the documented schema.
3. Governance preserved: denials still fire (403 + `reason_code`); AI principal blocked on
   human-only routes; approval `executes_action=false`; disabled/deferred caps not enableable.
4. Events emitted as documented.
5. Contract test: response schema matches the dataclass (`to_dict`) and rejects unknown request
   fields.
