# Workstream D — Executors Per Capability

> Goal: behind each capability gate, a **real executor** that performs the actual
> runtime action — but only when the gate is enabled (Workstream C) and only
> through `RuntimeAuthority.route_action()` (policy + approval + risk acceptance +
> audit). Built **by risk tier**, lowest risk first. Each executor is its own
> named task with its own threat model and tests.

Depends on: Workstream C (`ActivationRequirement.requires_executor`).
This is the largest workstream; it is the rest of the product's runtime.

---

## D.0 Current reality

- `RuntimeAuthority.route_action()` (`router.py:373`) already runs the full
  decision pipeline and returns a `GovernedActionResult` with decision
  `allow / deny / needs_approval / needs_risk_acceptance /
  needs_human_confirmation / disabled_by_capability_gate`.
- **But nothing executes on `allow`.** There is no executor registry; `route_action`
  returns `allow` and the caller stops. Safe read tools + approval-gated *proposals*
  exist in `raiker/tools/broker.py`; there is no runtime executor for the gated
  capabilities.
- `/approve` and `/deny` are metadata-only — they do not perform the approved
  action (`approval_execution_relay` is in the denylist).

---

## D.1 Target architecture

New module: `raiker/runtime/executors/`.

```
raiker/runtime/executors/
  __init__.py
  registry.py     # ExecutorRegistry: capability -> Executor
  base.py         # Executor protocol + ExecutionResult DTO
  <tier_x>_*.py   # one module per capability/group
```

```python
class Executor(Protocol):
    capability: str
    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult: ...

@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    capability: str
    action_id: str
    reason_code: str | None
    summary: str          # safe, redacted
    artifacts: dict       # safe metadata only — never raw secrets/file contents
```

### Execution flow (single chokepoint, unchanged governance)

```
caller → ActionRouter.route(...) → RuntimeAuthority.route_action()
         → decision == "allow"?  → ExecutorRegistry.get(capability).execute(action, principal)
                                  → emit "action_executed" event (redacted)
         → any other decision    → return as-is (deny/needs_*); DO NOT execute
```

- Wire the registry call **only on `allow`**, inside (or immediately after)
  `route_action`, so no path can execute without passing every gate.
- If `allow` but no executor registered → fail closed with
  `execution_unavailable:no_executor` (never silent success).
- Every execution emits a redacted `action_executed` (or `action_failed`) event.

### Per-capability requirements (each executor task)

policy rules · storage (if it persists) · events · executor impl ·
`ActivationRequirement` made satisfiable · threat-model ack doc · acceptance tests
· status update in `docs/IMPLEMENTATION_STATUS.md`.

---

## D.2 Build order by risk tier

See `07_CAPABILITY_REGISTRY_AND_RISK_TIERS.md` for the full capability→tier map.

### Tier 1 — Local, reversible, high-leverage (build first)
- `approval_execution_relay` — execute an approved proposal (turns `/approve` real).
- `file_write_execution`, `patch_apply_execution` — apply previously-proposed file
  changes (reuse `raiker/tools/filesystem.py` write/edit/apply_patch under the gate).
- `memory_write_execution`, `memory_forget_execution` — durable memory mutation.

### Tier 2 — Local execution with blast radius (sandbox required)
- `shell_execution`, `process_execution` — sandboxed, allowlisted, timeouts, output
  caps, no secret env leakage.
- `web_fetch`, `network_execution` — egress allowlist, no SSRF, redacted bodies.

### Tier 3 — Code intelligence runtime
- `graph_indexing_runtime`, `semantic_memory_runtime`, `vector_embedding_runtime` —
  storage migrations, retention, redaction; reuse Phase 9 `raiker/graph/`,
  `raiker/vector/`, `raiker/memory/` record modules behind real write paths.

### Tier 4 — Extensibility runtime (isolation required)
- `plugin_install`, `plugin_execution_cap` — signature/checksum verify (reuse
  `raiker/plugins/verify.py`), sandbox, permission diff + approval, revocation.

### Tier 5 — Outbound + remote (egress + secrets + budget)
- `external_channel_runtime`, `channel_approval_relay` — connector auth, outbound
  allowlist, redacted delivery.
- `remote_execution_cap`, `container_execution_cap`, `cloud_execution_cap` —
  isolation, secret injection, artifact handling, egress + budget caps.
- `hosted_model_runtime`, `private_network_model_runtime` — egress + budget policy
  (reuse `raiker/models/` provider gates).
- `scheduled_routines` — scheduler storage, owner consent, budget/egress.

### Tier 6 — Sensitive personal/physical domains (per-domain threat model; build last)
- `email_runtime`, `calendar_runtime`, `reminder_runtime`
- `finance_runtime`, `investment_runtime`
- `medical_runtime`, `pregnancy_baby_runtime`
- `cctv_runtime`, `home_security_runtime`, `hardware_operator_runtime`

Each Tier 6 capability is its **own** task with: dedicated threat model, explicit
human confirmation to enable (`requires_human_confirmation_to_enable=True`),
domain-scope binding (`DomainScope`), and integration adapter. Do not batch them.

### Governance-mutation capabilities (special handling)
`admin_mutation`, `policy_mutation`, `role_mutation`, `audit_export` are already
partially governed via `_govern_admin_mutation`. Treat their "executor" as the
governed mutation path; ensure each routes through `route_action` + activation
requirement, not a side door.

---

## D.3 Task breakdown (template — one per capability)

| Task ID | Title | Files | Acceptance |
|---|---|---|---|
| RAIKER-D000 | Executor registry + base + wiring | `raiker/runtime/executors/registry.py`, `base.py`, `router.py` | Registry; execution only on `allow`; fail-closed when no executor; `action_executed`/`action_failed` events; tests prove no execution on any non-allow decision. |
| RAIKER-D1xx | Tier 1 executors | `raiker/runtime/executors/tier1_*.py`, policy/storage/events | Each: executes only when gate enabled + approved; reversible; redacted events; acceptance tests incl. denial paths. |
| RAIKER-D2xx | Tier 2 executors | `tier2_*.py` + sandbox utils | Sandbox limits enforced; SSRF/egress tests; output redaction. |
| RAIKER-D3xx | Tier 3 executors | `tier3_*.py` | Real graph/semantic/vector writes; retention + redaction; incremental tests. |
| RAIKER-D4xx | Tier 4 executors | `tier4_*.py` | Signature verify, sandbox, permission-diff approval, revocation tests. |
| RAIKER-D5xx | Tier 5 executors | `tier5_*.py` | Egress allowlist, secret injection, budget caps, cancellation tests. |
| RAIKER-D6xx | Tier 6 executors | `tier6_*.py` + per-domain threat models | Per-domain: human-confirm enable, domain-scope bind, integration + abuse tests. |

Assign concrete numbers per capability when scheduling (see registry doc).

---

## D.4 Safety gates (must hold)

- **No execution off the chokepoint.** Add a test that asserts executors are
  unreachable except via `route_action` returning `allow`.
- A disabled or not-yet-activated capability **never** executes (returns the gate
  reason, no side effects).
- Every executor redacts: no secrets, raw file contents, raw tool output, API keys,
  or Authorization headers in events/results/artifacts.
- Risk classification respected: `critical` actions require HUMAN confirmation;
  `requires_approval`/`requires_risk_acceptance` honored before execute.
- A capability's default state in `default_capability_gates()` advances past
  `disabled` **only** in the PR that delivers its executor + tests + threat-model
  ack + status update — never preemptively.

## D.5 Validation

Full §5 gate per task. For each capability enabled, add explicit
"executes-only-when-governed" and "fails-closed-when-disabled" tests, and update
`docs/IMPLEMENTATION_STATUS.md` (and correct the Phase 7 overclaim for
plugin/graph/semantic when those tiers land).
</content>
