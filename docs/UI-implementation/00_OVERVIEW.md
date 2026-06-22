# Raiker Governed-Agent UI — Overview

> **Status of this document:** planning/specification for the local single-user web UI.
> It describes intended behaviour. No capability is "implemented" until code, tests, and the
> repo validation gate prove it. Where the backend does not support something, the UI must show
> it as **disabled**, **deferred**, **metadata-only**, or **not implemented** — never as working.

## What this is

A **local-first "mission control" web UI** for Raiker's governed agent runtime. It is a
**view/controller over the existing governed backend**, not a privileged interface. Every read
and every mutation goes through the same contracts, `RuntimeAuthority`, policy, capability gates,
approvals, audit events, and checkpoints that the CLI uses.

Target: the **current production-ready local single-user runtime**. Hosted SaaS, multi-user
admin, cloud orchestration, and external channels are **out of scope** and only ever shown as
future/deferred.

## Core principles (non-negotiable)

1. **No privileged interface.** The UI uses the same governed runtime core as the CLI. All
   prompts, actions, approvals, denials, gate/mode changes, checkpoints, and diagnostics route
   through existing contracts/services/API surfaces (`RuntimeControlService`, `AgentGateway`,
   `ApprovalInbox`, `RuntimeAuthority`). No direct SQLite access. No frontend policy engine.
2. **No silent runtime.** The user always sees what Raiker is doing, what is blocked, what needs
   approval, what is disabled, and *why*. Policy decisions, failed gates, deferred runtimes,
   approval requirements, and risk warnings are never hidden.
3. **Fail closed.** Disabled/deferred capabilities appear disabled/unavailable. The UI never
   implies email, calendar, finance, medical, CCTV, hosted/multi-user/cloud, plugins, or external
   channels work unless the backend has real implemented support. No fake runtime success.
4. **Local-first, single-user first.** Bind to `127.0.0.1`. One human owner principal.
5. **Documentation truthfulness.** UI labels and docs match the real backend. Nothing is marked
   implemented unless code, tests, and validation prove it.

## Backend reality (verified) the UI must honor

- **Approval resolution is `metadata_only`** — approving/denying records a decision; it does
  **not** execute the action. The UI states this explicitly on every approval surface.
- **Tier 2–6 runtimes are `disabled_deferred` / fail-closed**: shell/process/network/web-fetch,
  plugins, graph/semantic/vector/embeddings, external channels/notifications,
  remote/container/cloud, hosted/scheduled model runtimes, and all sensitive domains
  (email, calendar, reminders, finance, investments, medical, pregnancy_baby, cctv, home_security,
  hardware). They render disabled/deferred and cannot be enabled where no executor exists.
- **AI principals can never** flip gates/modes or self-approve. Human-only roles are enforced
  server-side; the UI hides/disables controls when `can_current_principal_change=false`.
- **STOP is safe-boundary cancel, not hard-kill** (`InterruptController.apply_at_safe_boundary`).
- **No secret storage exists** (only redaction/deny-secrets). Secret Settings is read-only.

## Existing governed surfaces reused

| Concern | Reuse |
|---|---|
| Read/mutate runtime mode & gates | `raiker/control/service.py::RuntimeControlService` + `raiker/api/routes_control.py` |
| Action governance | `raiker/runtime/authority/router.py::RuntimeAuthority` |
| Prompt turns + streaming | `raiker/gateway/agent_gateway.py::AgentGateway` (`submit_prompt_async`, `astream_prompt`) |
| Approvals | `raiker/approvals/__init__.py::ApprovalInbox` (`list_pending`, `resolve`) |
| Events (append-only) | `raiker/events/` + `events_index` |
| Checkpoints | `raiker/checkpoints/service.py::CheckpointService` |
| Models | `raiker/models/registry.py`, `raiker/models/router.py` |
| Interrupts/STOP | `raiker/runtime/interrupts.py::InterruptController`, `raiker/tasks/manager.py::TaskManager` |
| Auth | `raiker/api/auth.py::AuthMiddleware`, `raiker/api/sessions.py::ApiSessionStore` |
| Response redaction | `raiker/api/redaction.py` (`RedactionMiddleware`) |

## Stack & placement

- **Frontend:** Vite + Svelte + TypeScript SPA in `apps/web/`. Talks only to the local Raiker API.
  Token held in memory (never localStorage). Served as static assets by FastAPI (single origin,
  no CORS surface).
- **Backend:** extend the existing FastAPI control plane (`raiker/api/`) with the minimal governed
  routes in `03_API_CONTRACTS.md`. Add `uvicorn` + a `127.0.0.1` launcher (`apps/api/main.py`).

## Truthfulness obligations when shipping

Adding a launchable web UI changes the project's "launchable surface" truth. The validator marker
`"current launchable UI is the plain local terminal client only"` and related docs
(`README.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_STATUS.md`,
`docs/SECURITY_ARCHITECTURE.md`, `docs/GAP_AND_TODO_ANALYSIS.md`,
`docs/LOCAL_VALIDATION_GATE.md`, `scripts/validate_repo_truthfulness.py`) are updated to state
both the terminal client **and** the local web dashboard are launchable. This is an **alignment**,
not a loosening: every `metadata_only` / `disabled_deferred` / risk marker stays enforced.

## Document map

- `01_INFORMATION_ARCHITECTURE.md` — navigation, screens, Security Settings flow, STOP switch.
- `02_SECURITY_UX.md` — status badges, real `reason_code` catalog, step-up auth, deferred treatments.
- `03_API_CONTRACTS.md` — every endpoint: request/response schema + concrete JSON examples, governed path, events, tests.
- `04_FLOWS.md` — ASCII flow diagrams (prompt-turn, governed-mutation, STOP) + low-fi wireframes.
- `05_TEST_MATRIX.md` — security invariants → regression tests → owning milestone.
- `06_FUNCTIONAL_TESTS.md` — end-to-end functional UI test scenarios + deterministic seed/fixtures.
- `MILESTONES.md` — detailed M0–M7 (scope, deliverables, acceptance criteria, validation).
- `prompts/M1.md … M7.md` — a self-contained implementation prompt per milestone.
