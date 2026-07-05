# Capability Decision Modes (Ask / Deny / Always Allow / Auto)

> Runtime enablement candidate. Enforcement: strict non-allow blocking, role
> revoke governed, capability gate per action. Approval resolution is
> metadata-only.

Decision modes are a per-capability control layered **on top of** the capability
gate. The gate still governs *whether* a capability is enabled at all (default
disabled, fail-closed); the decision mode governs *how* an AI-proposed action on
an enabled capability is treated. This is Raiker's equivalent of a per-tool
permission policy, with an owner-controlled four-way choice.

## The four modes

| Mode | Meaning | AI-proposed action outcome |
|---|---|---|
| **`ask`** (default) | Prompt the owner before acting | Requires human approval (`needs_approval`) |
| **`deny`** | Never allowed | Blocked (`denied_by_decision_mode`) |
| **`always_allow`** | Run without prompting | Executes — subject to the safety floors below |
| **`auto`** | "Let Raiker decide" | Deterministic by risk: low runs, medium/high ask, critical floored |

`ask` is the default for every capability, so enabling a gate does **not** by
itself let an AI act unattended — the owner must explicitly choose `always_allow`
or `auto`.

## Safety floors (always enforced, regardless of mode)

- **PolicyEngine hard-denies** are evaluated first; a denied action never reaches
  the decision-mode layer.
- **Critical-risk actions always require a human.** `always_allow`/`auto` can
  never let an AI principal take a `critical`-risk action — it is denied for AI
  and requires human confirmation otherwise.
- **`auto` is deterministic and auditable** — it keys off the action's risk level
  (`raiker/runtime/authority/decision_modes.py::auto_requires_approval`), not an
  opaque model call. Only `low`-risk actions run unprompted.
- **Human principals** self-authorize as before; decision modes primarily govern
  **AI-proposed** actions.

## Governance of the setting

- Set via `RuntimeControlService.set_capability_decision_mode(...)` /
  `RuntimeAuthority.set_capability_decision_mode(...)` / the `/capability-mode`
  CLI command. **Human `runtime_gate_manager` only** — AI principals are refused
  (`ai_cannot_manage_runtime_gates`). Every change appends a
  `capability_decision_mode_set` event.
- **Permissive modes require a real executor.** `always_allow` and `auto` may only
  be set on a capability in `REAL_EXECUTOR_CAPABILITIES`; a sensitive/no-executor
  domain (medical, cctv, finance, home-security, hardware, remote/cloud, …) is
  refused with `decision_mode_requires_executor:<cap>` and can never be relaxed
  into acting. `ask`/`deny` only ever tighten behavior and are always selectable.
- Persisted in the `capability_decision_mode` table (separate from
  `capability_gate_state`, so gate transitions never clobber the mode). Unset →
  `ask`.

## Interaction with capability gates

Decision mode is orthogonal to the gate: a capability must still be enabled to
runtime through the normal governed activation path (human gate manager, runtime
mode, threat-model ack, confirmation token) before any action runs. The decision
mode then shapes each subsequent AI-proposed action. Disabling the gate stops all
execution regardless of mode.

## Acceptance evidence

`tests/test_phase_5_decision_modes.py`: default `ask`; human-only setter and AI
refusal; permissive-mode-requires-executor; invalid mode / unknown capability;
and the four router behaviors — `ask` → approval, `always_allow` → executes,
`deny` → blocked, `auto` → runs low / asks high — plus the critical-risk floor
that `always_allow` cannot bypass.
