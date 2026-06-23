# Workstream A — Control-Plane Facade

> Goal: a single, **interface-agnostic** service that exposes every control-plane
> operation (runtime mode + capability gates + readiness) and returns **typed,
> structured results** — so the CLI, the future API, and the future UI all call
> the same code path. No behaviour change to governance; this is extraction +
> structuring.

Depends on: nothing. **Do this first.**
Blocks: Workstream B (API maps over this), the vertical slice, the UI.

---

## A.0 Current reality

- The toggle logic lives only in `raiker/cli/commands.py` as handlers that take a
  `command: str` and return a human display `str`:
  - `handle_runtime_mode_status`, `handle_runtime_mode_activate`,
    `handle_runtime_mode_disable`
  - `handle_capability_gates`, `handle_capability_gate_detail`,
    `handle_capability_gate_enable`, `handle_capability_gate_disable`
  - `handle_runtime_readiness`
- Each handler re-does: `shlex` parsing, `resolve_local_principal(...)`,
  constructs `SQLiteStore` / `EventLogWriter` / `RuntimeAuthority`, calls an
  authority primitive, then formats a string.
- `RuntimeAuthority` (`raiker/runtime/authority/router.py`) already has the clean
  primitives: `get_runtime_mode()`, `activate_runtime_mode()`,
  `disable_runtime_mode()`, `get_effective_capability_gate()`,
  `request_capability_transition()`, `evaluate_effective_permissions()`,
  `check_capability_gate()`, `route_action()`.
- `AgentGateway` (`raiker/gateway/agent_gateway.py`) handles prompt turns only.

**Problem:** the orchestration around the primitives (principal resolution,
intent → call, result shaping) is trapped in string handlers. A non-CLI caller
cannot reuse it and cannot get structured data.

---

## A.1 Target architecture

New module: `raiker/control/` (interface-agnostic service layer).

```
raiker/control/
  __init__.py
  dtos.py        # frozen dataclasses: typed inputs + results + reason codes
  service.py     # RuntimeControlService: the facade
```

- `RuntimeControlService` is constructed from a `workspace_root` (it builds the
  store, writer, authority internally, exactly like the CLI handlers do today).
- Every method takes typed inputs (incl. an already-resolved `Principal` or a
  principal id to resolve) and returns a **DTO**, never a display string.
- Reason codes are **enums/string constants**, not prose. Display strings are the
  *caller's* job (CLI renders DTO→text; API renders DTO→JSON).
- The service performs **no governance of its own** — it delegates to
  `RuntimeAuthority`. It only orchestrates: resolve principal → call authority →
  wrap result in a DTO.

### DTOs (`raiker/control/dtos.py`)

Frozen dataclasses with a `to_dict()` for JSON. At minimum:

- `ControlPrincipalRef(principal_id, display_name, principal_type, role_ids, is_authorized_gate_manager)`
- `CapabilityGateView(capability, phase, state, default_state, runtime_enabled, allowed_transitions: tuple[str,...], can_current_principal_change: bool, blocked_reason_code: str | None, readiness: dict)`
- `RuntimeModeView(mode_name, status, activated_by, activated_at, allowed_modes: tuple[str,...])`
- `ControlResult(ok: bool, reason_code: str | None, message_key: str | None, data: dict)` — generic mutation result
- `RuntimeReadinessView(mode: RuntimeModeView, gates: tuple[CapabilityGateView,...], summary: dict)`

`reason_code` values reuse the authority's existing denial strings (e.g.
`not_runtime_gate_manager`, `unknown_capability`, `invalid_target_state`,
`runtime_mode_not_activated`, `capability_requires_activation_task`) — define
them as constants in `dtos.py` so callers can branch on them.

### Service methods (`raiker/control/service.py`)

```python
class RuntimeControlService:
    def __init__(self, workspace_root: str | Path = ".") -> None: ...

    # read
    def resolve_principal(self, explicit_principal_id: str | None) -> tuple[ControlPrincipalRef | None, str | None]
    def get_runtime_mode(self) -> RuntimeModeView
    def list_capability_gates(self, acting_principal_id: str | None = None) -> list[CapabilityGateView]
    def get_capability_gate(self, capability: str, acting_principal_id: str | None = None) -> CapabilityGateView
    def get_runtime_readiness(self, acting_principal_id: str | None = None) -> RuntimeReadinessView

    # mutate (all governed via RuntimeAuthority)
    def activate_runtime_mode(self, mode_name: str, acting_principal_id: str | None, reason: str) -> ControlResult
    def disable_runtime_mode(self, acting_principal_id: str | None, reason: str) -> ControlResult
    def set_capability_state(self, capability: str, target_state: str, acting_principal_id: str | None, reason: str) -> ControlResult
    def disable_capability(self, capability: str, acting_principal_id: str | None, reason: str) -> ControlResult
```

- `can_current_principal_change` / `allowed_transitions` are computed by *asking
  the authority* (dry-run the gate-manager check + the transition validity), not
  by duplicating its rules.
- `set_capability_state` wraps `RuntimeAuthority.request_capability_transition()`
  and maps its `str | None` denial into a `ControlResult`.

---

## A.2 Task breakdown

| Task ID | Title | Files | Acceptance |
|---|---|---|---|
| RAIKER-A001 | Control DTOs | `raiker/control/dtos.py` | All DTOs + reason-code constants + `to_dict()`; unit tests for `to_dict()` shape and redaction (no secret-like fields). |
| RAIKER-A002 | `RuntimeControlService` read methods | `raiker/control/service.py` | `get_runtime_mode`, `list_capability_gates`, `get_capability_gate`, `get_runtime_readiness`, `resolve_principal` return DTOs identical in data to current CLI output; tests compare against authority primitives. |
| RAIKER-A003 | `RuntimeControlService` mutate methods | `raiker/control/service.py` | `activate_runtime_mode`, `disable_runtime_mode`, `set_capability_state`, `disable_capability` delegate to authority; denials surface as `ControlResult(ok=False, reason_code=...)`; events still emitted by authority. |
| RAIKER-A004 | Refactor CLI handlers onto the service | `raiker/cli/commands.py` | The 8 handlers listed in A.0 now call `RuntimeControlService` and only format DTO→text. **No change to user-visible CLI output** (existing CLI tests still pass unchanged). |
| RAIKER-A005 | Service test suite | `tests/test_control_service.py` | Covers authorization (owner allowed, AI principal refused, unknown capability, invalid state, runtime-mode-not-activated), reversibility, and event emission. |

---

## A.3 Safety gates (must hold)

- The service adds **no** new authority; it must call `RuntimeAuthority` for every
  governed decision. A test must assert that flipping via the service produces the
  **same** denial reason as flipping via the authority directly.
- AI principals must still be refused (reuse `_check_human_runtime_gate_manager`
  via the authority).
- All `*_enabled` runtime flags remain `False`; this workstream does **not**
  enable any capability or change `default_capability_gates()`.
- No DTO field may contain secrets, raw prompts, file contents, tool output, or
  Authorization headers.

## A.4 Validation

Run the full §5 gate from `00_README_PROGRAM_OVERVIEW.md`. Existing CLI tests
(`tests/test_*` covering runtime-mode/capability-gate commands) must pass with no
edits to their assertions — proving the refactor preserved behaviour.
</content>
