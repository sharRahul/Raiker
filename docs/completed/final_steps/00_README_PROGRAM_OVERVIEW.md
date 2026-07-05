# Final Steps — Backend Runtime Enablement Program

> Status: planning / build-spec. This folder contains the task breakdown and the
> per-task build prompts for making the Raiker backend **completely ready for an
> out-of-process UI to flip every capability gate on/off, with a real executor
> behind each gate**. UI app development happens *after* this program lands.

This document is the entry point. Read it first, then the workstream docs
(`01`–`04`), the first vertical slice (`05`), the capability registry (`07`),
and finally the build prompts (`06`).

---

## 1. Goal (decided requirements)

A future **out-of-process** client (web/desktop/mobile) must be able to:

1. **Authenticate** and resolve to a real governed `Principal`.
2. **View** every capability gate, its effective state, allowed transitions, and
   whether the acting principal is authorized to change it.
3. **Flip** any gate (and the runtime mode) on/off through the existing
   `RuntimeAuthority` governance — persisted, reversible, audited.
4. Have a **real executor** behind each capability so that a flipped-on gate
   performs the actual runtime action under policy + approval + risk acceptance
   + audit (decision: *full executors per capability*).

This is intentionally the maximal scope. It is built **capability-by-capability
behind a finished control plane**, not all at once.

---

## 2. Non-negotiable safety invariants (apply to every task)

These must remain true at every commit. A task that breaks one is rejected.

- **Default-disabled.** Every capability gate ships `disabled`. Enabling is an
  explicit, governed, owner/`runtime_gate_manager` action. AI principals can
  never flip a gate or activate a runtime mode.
- **Single chokepoint.** All mutation/execution routes through
  `RuntimeAuthority.route_action()` / `ActionRouter.route()`. No UI, API handler,
  CLI handler, or executor may bypass it, the `PolicyEngine`, approvals, or the
  event log.
- **No silent runtime.** If a capability is not fully wired (policy + storage +
  events + executor + tests), it must **fail closed** with a clear reason code —
  never silently no-op or silently succeed.
- **Reversible.** Every enable has a corresponding disable; state is persisted in
  SQLite (`runtime_mode_state`, `capability_gate_state`) and survives restart.
- **Audited.** Every transition and every executed action emits append-only
  events with redaction (no secrets, raw prompts, raw tool output, file contents,
  Authorization headers, or API keys in payloads).
- **Truthful docs.** When a capability genuinely moves `disabled → enabled_*`,
  update `docs/IMPLEMENTATION_STATUS.md` and the validators in the **same** PR.
  Do not mark `implemented_verified` without code + tests + recorded validation.

---

## 3. Current code reality (verified 2026-06-21)

| Area | File(s) | Reality |
|---|---|---|
| Governance core | `raiker/runtime/authority/router.py` (`RuntimeAuthority`, `ActionRouter`) | Implemented, persisted, governed, audited. Clean primitives exist. |
| Capability model | `raiker/phase_gates.py` (`ALL_CAPABILITIES`, `CapabilityState`, `default_capability_gates()`) | ~53 capabilities, all default-disabled. |
| Gate/mode persistence | `raiker/storage/sqlite.py` (`upsert_capability_gate_state`, `get_active_runtime_mode`, …) | Persisted + reversible. |
| Toggle logic | `raiker/cli/commands.py` (`handle_capability_gate_enable`, `handle_runtime_mode_*`, …) | **String-in / string-out CLI handlers only.** No interface-agnostic facade. |
| Prompt path | `raiker/gateway/agent_gateway.py` (`submit_prompt`, `astream_prompt`) | Prompt turns only; **no control-plane methods**. |
| Hard refusal | `raiker/runtime/authority/router.py:314–324` | `request_capability_transition()` **unconditionally refuses ~30 runtime capabilities** ("requires a future explicit activation task") — even for the owner. |
| Executors | `raiker/tools/broker.py`, `raiker/runtime/orchestrator.py` | Safe read tools + approval-gated proposals only. **No executor registry behind `route_action()`** for runtime capabilities. |
| API server | — | **Does not exist.** No transport, no auth, no session→principal model. |

**Conclusion:** the governance core (~70%) is ready. The control-plane facade,
the API+auth layer, the removal of the in-code denylist, and the per-capability
executors are not. This program builds those four things.

---

## 4. Workstreams

| ID | Workstream | Doc | Summary |
|---|---|---|---|
| A | Control-plane facade | `01_WORKSTREAM_A_CONTROL_PLANE_FACADE.md` | Interface-agnostic `RuntimeControlService` returning typed DTOs; refactor CLI handlers onto it. |
| B | API server + auth | `02_WORKSTREAM_B_API_SERVER_AND_AUTH.md` | HTTP API, session→principal auth, redaction, event stream, security tests. |
| C | Governed activation path | `03_WORKSTREAM_C_GOVERNED_ACTIVATION_PATH.md` | Replace the hard-coded denylist with a per-capability `ActivationRequirement` registry. |
| D | Executors per capability | `04_WORKSTREAM_D_EXECUTORS_PER_CAPABILITY.md` | Executor registry behind `route_action()`; build by risk tier. |
| — | First vertical slice | `05_FIRST_VERTICAL_SLICE.md` | A + B-core-auth + C + one executor (approval/file execution) proving the whole loop end-to-end. |
| — | Capability registry | `07_CAPABILITY_REGISTRY_AND_RISK_TIERS.md` | All capabilities with risk tier, executor target, activation requirements. |
| — | Build prompts | `06_DEEPSEEK_BUILD_PROMPTS.md` | Copy-paste prompts per task for the coding model. |

### Critical path

```
A  ──►  B-core-auth ─┐
       │             ├──►  Vertical slice (D1: approval/file execution)  ──►  D2 … D7 by risk tier
C  ────┘             │
                     └──►  Phase 8 UI apps (separate, after this program)
```

Do **A** first (everything depends on the facade). **B-core-auth** and **C** can
proceed in parallel after A. Land the **vertical slice** (`05`) before scaling
out executors — it proves *authenticate → flip → execute → audit* end-to-end.

---

## 5. Definition of done (per task and per capability)

A task is done only when **all** are true:

1. Code maps to the task ID in its workstream doc.
2. The safety invariants in §2 hold.
3. New/updated tests exist and pass (`pytest`).
4. `ruff check .` and `mypy raiker apps tests` pass for changed files.
5. The repo validators pass:
   - `python scripts/validate_repo_truthfulness.py`
   - `python scripts/validate_phase_status.py`
   - `python scripts/validate_runtime_enablement_readiness.py`
   - `python scripts/validate_local_single_user_runtime.py`
6. `docs/IMPLEMENTATION_STATUS.md` reflects the real new status (and the Phase 7
   table overclaim noted in `docs/GAP_AND_TODO_ANALYSIS.md` is corrected when its
   capability is genuinely enabled).

A **capability** is done only when it has: an `ActivationRequirement` entry
(Workstream C), a registered executor (Workstream D), policy rules, storage,
events, a recorded threat-model review, and acceptance tests — and only then may
its default state advance past `disabled`.

---

## 6. How to use the build prompts

`06_DEEPSEEK_BUILD_PROMPTS.md` contains one self-contained prompt per task,
sized for a coding model (Deepseek Flash V4). Each prompt: names the files to
read, the exact change, the constraints (the §2 invariants), the tests to write,
the validation commands, and an explicit "do not" list. Run them **in the order
of the critical path**. After each prompt, run the §5 validation gate before
moving on.
</content>
</invoke>
