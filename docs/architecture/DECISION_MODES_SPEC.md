# Capability Decision Modes (Ask / Deny / Allow / Auto)

> Enforcement: strict non-allow blocking, role revoke governed, capability gate
> per action. Approval resolution **executes** the fourteen capabilities in
> `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`) and stays
> decision-only for every other capability — see
> [Implementation status](IMPLEMENTATION_STATUS.md).
>
> Decision modes are **standing per-capability policy**, not a one-action
> approval. The shared prompt approval modes are `manual`, `sandbox` and
> `dont_ask` (`APPROVAL_MODES` in `raiker/contracts/models.py`). Legacy prompt
> `auto` normalizes to `sandbox`; `skip` normalizes to `manual`. Build's internal
> `auto` turn-mode ID means Run within limits and supplies no extra authority.
>
> Sandbox preparation is authorized through the shared broker/runtime checks
> in `raiker/runtime/authority/preparation.py`: owner/session-bound task copy,
> fresh measured containment, enabled capabilities and no overriding restriction.
> Local task drafts have a narrowly bounded internal-preparation path. Sending,
> applying, pushing, scheduling and other consequential effects retain their
> ordinary authority. Explicit saved Ask/Deny and critical confirmation win.
> See the [approval contract](../plans/APPROVAL_REDESIGN.md#contract).

Decision modes are a per-capability control layered **on top of** the capability
gate. The gate still governs *whether* a capability is enabled at all: integrated
real-executor capabilities default to `enabled_runtime`, while no-executor
capabilities default to `disabled` and fail closed; the decision mode governs *how* an AI-proposed action on
an enabled capability is treated. This is Raiker's equivalent of a per-tool
permission policy, with an owner-controlled four-way choice.

## The four modes

| Mode | Meaning | AI-proposed action outcome |
|---|---|---|
| **`ask`** (default) | Prompt the owner before acting | Requires human approval (`needs_approval`) |
| **`deny`** | Never allowed | Blocked (`denied_by_decision_mode`) |
| **`allow`** | Run without prompting | Executes — subject to the safety floors below |
| **`auto`** | "Let Raiker decide" | Deterministic by risk: low runs, medium/high ask, critical floored |

> The canonical mode name is **`allow`** (enum `DecisionMode.ALWAYS_ALLOW = "allow"`).
> `always_allow` is still accepted everywhere as a backward-compatible alias
> (`parse_decision_mode`).

`ask` is the default for every capability, so enabling a gate does **not** by
itself authorize every effect. A saved `ask` remains restrictive; eligible
sandbox preparation can satisfy an ordinary policy pause only through the
separate runtime-derived scope check, not merely because a gate is enabled.

## Safety floors (always enforced, regardless of mode)

- **PolicyEngine hard-denies** are evaluated first; a denied action never reaches
  the decision-mode layer.
- **Critical-risk actions always require a human.** `allow`/`auto` can
  never let an AI principal take a `critical`-risk action — it is denied for AI
  and requires human confirmation otherwise.
- **`auto` is deterministic and auditable** — it keys off the action's risk level
  (`raiker/runtime/authority/decision_modes.py::auto_requires_approval`), not an
  opaque model call. Only `low`-risk actions run unprompted.
- **Preparation is established by runtime scope and fresh containment proof.**
  Prompt text, model risk labels and caller-provided sandbox flags cannot grant
  it. The old composer Auto alignment-bypass path is no longer used. Ordinary
  review does not execute or spend a grant; dispatch revalidates and grant use
  is atomically claimed against reviewed limits, expiry and revocation.
- **Human principals** self-authorize as before; decision modes primarily govern
  **AI-proposed** actions.

## Governance of the setting

- Set via `RuntimeControlService.set_capability_decision_mode(...)` /
  `RuntimeAuthority.set_capability_decision_mode(...)` / the `/capability-mode`
  CLI command, or over REST. **Human `runtime_gate_manager` only** — AI principals
  are refused (at the API this is the gate-operation authorization boundary; at
  the service layer `ai_cannot_manage_runtime_gates`). Every change appends a
  `capability_decision_mode_set` event.
- **REST surface** (`raiker/api/routes_control.py`): `GET
  /api/capability-modes/{capability}` reads the current mode; the four setters
  `POST /api/capability-modes/{capability}/{ask|allow|auto|deny}` set it (body:
  optional `{"reason": ...}`). These are distinct from the approval-inbox routes
  `GET/POST /api/approvals/...`: the approval routes resolve **one pending
  action** (a single queued proposal), while the decision-mode routes set the
  **standing per-capability policy** that shapes every future AI-proposed action.
- **Permissive modes require a real executor.** `allow` and `auto` may only
  be set on a capability in `REAL_EXECUTOR_CAPABILITIES`; a sensitive/no-executor
  domain (medical, cctv, finance, home-security, hardware, remote/cloud, …) is
  refused with `decision_mode_requires_executor:<cap>` and can never be relaxed
  into acting. `ask`/`deny` only ever tighten behavior and are always selectable.
- Persisted in the `capability_decision_mode` table (separate from
  `capability_gate_state`, so gate transitions never clobber the mode). Unset →
  `ask`.

## Interaction with capability gates

Decision mode is orthogonal to the gate: a capability must still be enabled to
runtime before any action runs. Integrated real-executor gates may already be
`enabled_runtime` by default; explicit activation is still used to re-enable a
disabled/persisted non-default gate and for requirements such as runtime mode,
threat-model ack, or confirmation token where applicable. The decision
mode then shapes each subsequent AI-proposed action. Disabling the gate stops all
execution regardless of mode.

## Acceptance evidence

`tests/test_phase_5_decision_modes.py`: default `ask`; human-only setter and AI
refusal; permissive-mode-requires-executor; invalid mode / unknown capability;
and the four router behaviors — `ask` → approval, `allow` → executes, `deny` →
blocked, `auto` → runs low / asks high — plus the critical-risk floor that
`allow` cannot bypass.

`tests/test_api_decision_modes.py`: the REST surface — default `ask` on read,
owner can set all four modes (`ask`/`allow`/`auto`/`deny`) and they round-trip,
permissive-mode-requires-executor returns `403`, `deny` is always selectable on a
no-executor domain, an AI principal is refused `403` (mode unchanged), and both
read and set require authentication.
