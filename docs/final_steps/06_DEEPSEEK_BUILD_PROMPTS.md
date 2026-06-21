# Deepseek Flash V4 — Build Prompts

> One self-contained prompt per task. Run them **in the order below** (the critical
> path). Each prompt assumes the model has the repo checked out and can read files,
> edit code, and run commands. After every prompt, run the **Validation gate** and
> do not proceed until it is green.

## Global system preamble (prepend to EVERY prompt)

```
You are a senior Python engineer working in the Raiker repository (Python 3.11+,
asyncio, SQLite, httpx; ruff + mypy enforced; no provider SDKs). Work ONLY on the
branch you are told to. Make the smallest change that satisfies the task.

NON-NEGOTIABLE INVARIANTS (a change that breaks any is wrong):
1. Every capability gate ships `disabled`. Enabling is an explicit, governed,
   owner/runtime_gate_manager action. AI principals can NEVER flip a gate or
   activate a runtime mode.
2. All mutation/execution routes through RuntimeAuthority.route_action() /
   ActionRouter.route() and the PolicyEngine, approvals, and event log. Never
   bypass them from a UI, API, CLI, or executor.
3. No silent runtime: if a capability is not fully wired, FAIL CLOSED with a clear
   reason code. Never silently no-op or silently succeed.
4. Everything is reversible and persisted in SQLite; state survives restart.
5. Every transition and execution emits an append-only, REDACTED event — never log
   secrets, raw prompts, raw tool output, file contents, API keys, or Authorization
   headers.
6. When a capability genuinely moves disabled→enabled, update
   docs/IMPLEMENTATION_STATUS.md and the validators in the SAME change.

VALIDATION GATE (must all pass before you report done):
  python -m ruff check .
  python -m mypy raiker apps tests
  python -m pytest
  python scripts/validate_repo_truthfulness.py
  python scripts/validate_phase_status.py
  python scripts/validate_runtime_enablement_readiness.py
  python scripts/validate_local_single_user_runtime.py

Read the referenced files before editing. Do not invent file paths. If a doc and
the code disagree, follow the code and note it.
```

---

## Prompt A1 — Control DTOs (RAIKER-A001)

```
TASK: Create raiker/control/dtos.py with the typed control-plane DTOs.

READ FIRST: raiker/runtime/authority/router.py (methods get_runtime_mode,
get_effective_capability_gate, request_capability_transition); raiker/phase_gates.py
(CapabilityState, default_capability_gates); raiker/runtime/authority/models.py
(Principal, HUMAN_ONLY_ROLES).

DO:
- Add frozen dataclasses with to_dict(): ControlPrincipalRef, CapabilityGateView,
  RuntimeModeView, ControlResult, RuntimeReadinessView (fields per
  docs/final_steps/01_WORKSTREAM_A_CONTROL_PLANE_FACADE.md §A.1).
- Add a ReasonCode constant set reusing the authority's existing denial strings
  (not_runtime_gate_manager, unknown_capability, invalid_target_state,
  runtime_mode_not_activated, capability_requires_activation_task, etc.).
- to_dict() must not expose secret-like fields.

TESTS: tests/test_control_dtos.py — assert to_dict() shapes and that no DTO carries
secrets/file-contents/headers.

DO NOT: add any governance logic here; touch the authority; enable any capability.
```

## Prompt A2 — RuntimeControlService read methods (RAIKER-A002)

```
TASK: Create raiker/control/service.py with RuntimeControlService and its READ
methods: resolve_principal, get_runtime_mode, list_capability_gates,
get_capability_gate, get_runtime_readiness.

READ FIRST: raiker/cli/commands.py (handle_runtime_mode_status,
handle_capability_gates, handle_capability_gate_detail, handle_runtime_readiness,
resolve_local_principal); raiker/runtime/authority/router.py; raiker/control/dtos.py.

DO:
- Construct SQLiteStore + EventLogWriter + RuntimeAuthority internally from
  workspace_root (mirror the CLI handlers).
- Return DTOs with the SAME data the CLI handlers currently print.
- Compute allowed_transitions and can_current_principal_change by querying the
  authority (dry-run gate-manager check + transition validity) — do NOT duplicate
  the rules.

TESTS: tests/test_control_service.py (read half) — values match authority primitives.

DO NOT: mutate state; enable capabilities; format display strings (return DTOs).
```

## Prompt A3 — RuntimeControlService mutate methods (RAIKER-A003)

```
TASK: Add MUTATE methods to RuntimeControlService: activate_runtime_mode,
disable_runtime_mode, set_capability_state, disable_capability.

READ FIRST: raiker/runtime/authority/router.py (activate_runtime_mode,
disable_runtime_mode, request_capability_transition); raiker/cli/commands.py
(handle_runtime_mode_activate/disable, handle_capability_gate_enable/disable).

DO:
- Delegate every governed decision to RuntimeAuthority. Map its `str | None`
  denial into ControlResult(ok=False, reason_code=...). Success → ControlResult(ok=True).
- Resolve the acting principal via resolve_principal; if None, return the resolve error.

TESTS: extend tests/test_control_service.py — owner allowed, AI principal refused,
unknown capability, invalid state, runtime_mode_not_activated; assert the authority
still emits the transition events.

DO NOT: add or relax any authority rule; enable any capability by default.
```

## Prompt A4 — Refactor CLI onto the service (RAIKER-A004)

```
TASK: Refactor the 8 control handlers in raiker/cli/commands.py to call
RuntimeControlService and only format DTO→text. User-visible output MUST be byte
identical to current behaviour.

READ FIRST: raiker/cli/commands.py (the 8 handlers); raiker/control/service.py;
the existing CLI tests covering /runtime-mode and /capability-gate.

DO: replace the per-handler store/authority/parse/format duplication with a service
call + a thin text formatter. Keep the slash-command dispatch unchanged.

TESTS: existing CLI tests must pass WITHOUT editing their assertions. Add a test
asserting CLI text is derived from the service DTO.

DO NOT: change command names, usage strings, or output text.
```

---

## Prompt B1–B4 — API core + auth (RAIKER-B001..B004)

```
TASK: Build the out-of-process API core over RuntimeControlService.
Implement in this order, one commit each: B001 app factory, B002 session/token
store, B003 auth middleware→Principal, B004 control routes.

READ FIRST: docs/final_steps/02_WORKSTREAM_B_API_SERVER_AND_AUTH.md;
raiker/control/service.py; raiker/gateway/agent_gateway.py;
raiker/storage/sqlite.py (api_sessions table goes here + a migration);
raiker/runtime/authority/models.py (Principal); the owner-bootstrap path.

DO:
- raiker/api/app.py: create_app(workspace_root) -> FastAPI app + health route.
- raiker/api/sessions.py + migration: api_sessions(session_id, principal_id,
  token_hash, scopes, created_at, expires_at, revoked); tokens hashed at rest;
  issuance is owner/runtime_gate_manager only.
- raiker/api/auth.py: token -> ApiSession -> Principal. 401 missing/expired/revoked;
  403 authenticated-but-unauthorized (surface authority reason code). A session can
  NEVER change which Principal it maps to or grant itself roles.
- raiker/api/routes_control.py + schemas.py: map the 8 control endpoints in the doc
  to RuntimeControlService; serialize DTOs to JSON; denials -> 403 + reason_code.
  Routes contain NO business logic.

TESTS: tests/test_api_core.py — boot create_app(tmp) with bootstrapped owner; owner
token can GET /api/capability-gates (200); AI principal flip -> 403; unauth -> 401.

DO NOT: call any tool/store/executor directly from a route; auto-start the server;
enable any capability; use a JWT shared-secret sprawl (use hashed opaque tokens).
```

## Prompt B7 + B9 — Redaction guard + security suite (RAIKER-B007, B009)

```
TASK: Add raiker/api/redaction.py applied to every response, and the security
regression suite tests/test_api_security.py.

READ FIRST: raiker/events/ redaction patterns; raiker/api/routes_control.py.

DO: a single redaction function asserting absence of secrets/API keys/Authorization
headers/raw prompts/file contents/tool output in any response body. Wire it into the
app so every response passes through it.

TESTS (tests/test_api_security.py): unauth->401, AI-principal flip->403, approval
bypass attempt, cross-session leakage, redaction holds, token revocation works.

DO NOT: let any endpoint return raw secret-like data.
```

---

## Prompt C1–C4 — Activation requirement framework (RAIKER-C001..C004)

```
TASK: Replace the hard-coded capability denylist with a data-driven
ActivationRequirement framework.

READ FIRST: raiker/runtime/authority/router.py lines ~293-360
(request_capability_transition; the denylist is lines 314-324);
raiker/phase_gates.py (ALL_CAPABILITIES, transition_capability, CapabilityState);
docs/final_steps/03_WORKSTREAM_C_GOVERNED_ACTIVATION_PATH.md;
docs/final_steps/07_CAPABILITY_REGISTRY_AND_RISK_TIERS.md.

DO:
- raiker/runtime/authority/activation.py: ActivationRequirement dataclass +
  ACTIVATION_REQUIREMENTS dict with one entry per capability in ALL_CAPABILITIES.
  Default every entry UNSATISFIABLE (requires_executor=True; no executor exists yet).
  Tiers>=2, Tier 6, and gov set requires_human_confirmation_to_enable=True and
  requires_threat_model_ack=True per the registry doc.
- raiker/storage/sqlite.py + migration: threat_model_acks(capability, acked_by,
  acked_at, doc_ref); owner/security_admin only.
- evaluate_activation_requirement(capability, target_state, principal,
  confirmation_token) implementing the 5-step check in the doc; return SPECIFIC
  reason codes (activation_blocked:no_executor, :no_threat_model_ack,
  :runtime_mode_not_active, :needs_human_confirmation).
- In request_capability_transition(): DELETE the 314-324 denylist; call
  evaluate_activation_requirement instead.

CRITICAL: on a fresh workspace NO capability may reach enabled_runtime (all
requirements unsatisfiable). Add tests/test_capability_activation.py asserting this,
plus: AI refused; fixture capability with a stub executor+ack flips for owner,
fails without ack, fails without runtime mode, reverses.

ALSO UPDATE: scripts/validate_runtime_enablement_readiness.py to (a) assert no
generic "requires a future explicit activation task" bypass remains, and (b) assert
every ALL_CAPABILITIES member has an ACTIVATION_REQUIREMENTS entry. Keep it passing.

DO NOT: make any real capability enabled by default; weaken the gate-manager check.
```

---

## Prompt D0 — Executor registry + chokepoint wiring (RAIKER-D000)

```
TASK: Add the executor registry and wire execution to run ONLY on an `allow`
decision from RuntimeAuthority.route_action().

READ FIRST: raiker/runtime/authority/router.py (route_action, GovernedActionResult,
ActionRouter); docs/final_steps/04_WORKSTREAM_D_EXECUTORS_PER_CAPABILITY.md.

DO:
- raiker/runtime/executors/base.py: Executor protocol + ExecutionResult DTO
  (ok, capability, action_id, reason_code, summary, artifacts — all redacted/safe).
- raiker/runtime/executors/registry.py: ExecutorRegistry (register/get/has).
- Wire: after route_action returns decision=="allow", call the registered executor;
  emit redacted action_executed/action_failed events. If decision!="allow", DO NOT
  execute. If allow but no executor -> fail closed execution_unavailable:no_executor.

TESTS: tests/test_executor_registry.py — execution happens only on allow; every
non-allow decision (deny/needs_approval/needs_risk_acceptance/
needs_human_confirmation/disabled_by_capability_gate) produces NO execution; missing
executor fails closed.

DO NOT: register any real executor in this task; bypass route_action anywhere.
```

## Prompt D-Tier1 — Approval/file execution (vertical slice executors)

```
TASK: Implement Tier-1 executors: approval_execution_relay, file_write_execution,
patch_apply_execution. Make ONLY these three activation requirements satisfiable.

READ FIRST: raiker/tools/filesystem.py (write/edit/apply_patch); raiker/approvals/
(ApprovalInbox); raiker/review/lifecycle.py (proposals); raiker/runtime/executors/
registry.py; docs/final_steps/05_FIRST_VERTICAL_SLICE.md.

DO:
- raiker/runtime/executors/tier1_approval.py + tier1_files.py: executors that, only
  when the gate is enabled_runtime and the action is approved, perform the file
  change / apply the approved proposal via the existing filesystem tools UNDER the
  policy/approval path. Reversible; redacted events.
- Register them in ExecutorRegistry. Set requires_executor satisfiable for these
  three in ACTIVATION_REQUIREMENTS (executor now exists).
- Advance their default state ONLY as part of this change, with tests + status doc.

TESTS: tests/test_vertical_slice_e2e.py implementing the full scenario in
05_FIRST_VERTICAL_SLICE.md (happy path + all negative cases).

UPDATE: docs/IMPLEMENTATION_STATUS.md (these three now genuinely enabled; everything
else remains False); docs/THREAT_MODEL.md (short section for these three).

DO NOT: enable any other capability; execute when the gate is disabled; leak file
contents/secrets into events or ExecutionResult.
```

## Prompt D-TierN — Template for every later capability

```
TASK: Implement the executor for <CAPABILITY> (Tier <N>) per the registry doc.

READ FIRST: docs/final_steps/04_WORKSTREAM_D_EXECUTORS_PER_CAPABILITY.md;
docs/final_steps/07_CAPABILITY_REGISTRY_AND_RISK_TIERS.md (its row);
the relevant existing module (e.g. raiker/graph/, raiker/vector/, raiker/plugins/,
raiker/channels/, raiker/models/).

DO:
- Implement raiker/runtime/executors/tier<N>_<cap>.py; register it.
- Add policy rules, storage/migrations, events as the row requires.
- Make ACTIVATION_REQUIREMENTS[<CAPABILITY>] satisfiable (executor now exists;
  keep requires_human_confirmation_to_enable / requires_threat_model_ack per row).
- For Tier 2+: enforce the tier's isolation (sandbox / egress allowlist / signature
  verify / budget caps) and write abuse/negative tests.
- For Tier 6 (sensitive domains): add a dedicated threat model section, bind to the
  DomainScope, require human confirmation to enable. ONE capability per change.

TESTS: executes-only-when-governed; fails-closed-when-disabled; tier-specific abuse
tests. UPDATE docs/IMPLEMENTATION_STATUS.md status + evidence.

DO NOT: batch multiple Tier-6 domains; enable by default; skip the threat-model ack.
```

---

## Run order summary

1. A1 → A2 → A3 → A4
2. B1–B4 → B7+B9
3. C1–C4
4. D0 → D-Tier1 → **run the vertical-slice e2e test (05)**
5. Then D-TierN for Tier 2 → 3 → 4 → 5 → 6, strictly in tier order, one capability
   (or small group) per change, validation gate green each time.

After all executors land and the validators reflect the real enabled set, begin
the UI app program against the API from Workstream B.
</content>
