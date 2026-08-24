# Capability Decision Modes (Ask / Deny / Allow / Auto)

> Enforcement: strict non-allow blocking, role revoke governed, capability gate
> per action. Approval resolution **executes** the twelve capabilities in
> `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`) and stays
> decision-only for every other capability — see
> [Implementation status](IMPLEMENTATION_STATUS.md).
>
> Decision modes are the **per-capability** standing policy described here. They
> are not the same control as the **per-turn approval mode** a composer sends
> (`manual`, `auto`, `skip`, `dont_ask` — `APPROVAL_MODES` in
> `raiker/contracts/models.py`), which can only ever tighten a turn. Raiker has
> no equivalent of a mode that skips every check; see
> [Reference platform compatibility §4.1](REFERENCE_PLATFORM_COMPATIBILITY.md#41-a-mode-that-skips-every-check).
>
> **The two `auto`s are different controls with the same name, and both are
> deterministic.** The per-capability `auto` below is a risk lookup. The
> composer's `auto` approval mode grants an ordinary approval on the owner's
> behalf, and since 2026-08-24 it runs an **alignment check** first
> ([`raiker/runtime/alignment.py`](../raiker/runtime/alignment.py),
> [FIXED-282](plans/FIXED_ITEMS.md)): a change to an existing file the turn never
> read, listed or was asked about falls back to the ordinary approval queue with
> the path named. It can only withhold, and `skip` is not checked.

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
itself let an AI act unattended — the owner must explicitly choose `allow`
or `auto`.

## Safety floors (always enforced, regardless of mode)

- **PolicyEngine hard-denies** are evaluated first; a denied action never reaches
  the decision-mode layer.
- **Critical-risk actions always require a human.** `allow`/`auto` can
  never let an AI principal take a `critical`-risk action — it is denied for AI
  and requires human confirmation otherwise.
- **`auto` is deterministic and auditable** — it keys off the action's risk level
  (`raiker/runtime/authority/decision_modes.py::auto_requires_approval`), not an
  opaque model call. Only `low`-risk actions run unprompted.
- **The composer's `auto` approval mode adds a second deterministic check.** It
  answers "has this turn established the file this action is about to change?"
  from the turn's own `tool_actions` rows and its prompt, withholds into the
  ordinary approval queue when it has not, records
  `approval_auto_withheld` with the path, and fails closed on an unreadable
  record. It never widens a gate and never skips one.
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
