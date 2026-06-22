# Security UX

> Planning document. The UI makes Raiker **more transparent, not more magical.** Every
> security-relevant state below is derived from real backend data and rendered honestly.

## Status badges

Use a consistent badge component. **Never rely on colour alone** — each badge has a text label
and an icon/shape, with an accessible name.

| Badge | Meaning | Typical source |
|---|---|---|
| `Safe` | Low-risk, auto-allowed | policy decision `allow`, low risk |
| `Needs approval` | Requires human approval | `GovernedActionResult.decision = needs_approval` |
| `Approval-required` | Action/capability gated on approval | capability label `implemented_approval_required` |
| `Blocked` | Denied by policy/authority | `decision = deny`, `blocked_reason_code` |
| `Disabled` | Gate currently disabled | `CapabilityGateView.state = disabled` |
| `Deferred` | Future/not-yet-built | `disabled_deferred`, Phase 8 backlog |
| `Implemented` | Real, working capability | `implemented_*` labels |
| `Metadata-only` | Records, does not execute | approvals; `metadata_only` |
| `Read-only` | View only | `implemented_read_only` |
| `Risk-acceptance required` | One-time/reusable risk ack needed | `decision = needs_risk_acceptance` |

Capability-matrix labels mirror backend statuses exactly: `implemented_read_only`,
`implemented_policy_gated`, `implemented_approval_required`, `metadata_only`, `readiness_only`,
`dry_run_only`, `contract_only`, `disabled_deferred`, `test_only`.

## `reason_code` → plain-English copy map

The backend returns machine `reason_code` / message strings on denial (403 `{ok:false,
reason_code}`) and inside `PolicyDecision` / `GovernedActionResult.message`. The codes below are
**transcribed verbatim from source** (not invented) — keep this table in sync with code; the M7
anti-drift test asserts every code listed here exists in the codebase.

### Decision values — `GovernedActionResult.decision` (`raiker/runtime/authority/router.py`)
The UI renders each decision distinctly: `allow`, `deny`, `disabled_by_capability_gate`,
`needs_human_confirmation`, `needs_approval`, `needs_risk_acceptance`.

### Principal / role / scope denials — `router.py`
| reason_code | Plain English | Remediation | Source |
|---|---|---|---|
| `principal_not_active` | "Your account/principal is not active." | "A human owner must re-activate it." | `check_principal_active` |
| `principal_expired` | "Your principal has expired." | "Re-bootstrap or renew the principal." | `check_principal_active` |
| `cannot_assign_human_role_to_ai:{role}` | "An AI principal can't hold a human-only role." | "Only a human can hold this role." | `check_ai_role_assignment` |
| `domain_scope_denied:{scope}` | "This action's domain isn't in your granted scopes." | "Grant the domain scope to the principal." | `check_domain_scope` |
| `ai_cannot_approve_own_action` | "An AI can't approve its own action." | "Another authorised human must approve." | `check_self_approval` |
| `ai_cannot_grant_roles` | "An AI can't grant/assign roles." | "A human owner must grant roles." | `check_self_grant` |
| `ai_cannot_manage_runtime_gates` | "An AI can't change runtime modes/gates." | "A human `runtime_gate_manager` must do this." | `_check_human_runtime_gate_manager` |
| `only_runtime_gate_manager_can_manage_gates` | "You lack the runtime-gate-manager role." | "Use an owner/`runtime_gate_manager` principal." | `_check_human_runtime_gate_manager` |
| `ai_cannot_enable_runtime_gate` | "An AI can't enable a runtime gate." | "A human `runtime_gate_manager` must do this." | `check_runtime_gate_enable` |
| `only_runtime_gate_manager_can_enable_gates` | "You lack the role to enable gates." | "Use a `runtime_gate_manager` principal." | `check_runtime_gate_enable` |

### Capability-gate / mode / transition denials — `router.py`
| reason_code | Plain English | Remediation | Source |
|---|---|---|---|
| `disabled_by_capability_gate` | "This capability is turned off." | "Enable it in Security Settings → Runtime Mutations (if supported)." | `check_capability_gate` |
| `unknown_capability_gate` | "This capability isn't recognised." | "No such gate; nothing to enable." | `check_capability_gate` |
| `unknown_runtime_mode:{mode}` | "That runtime mode doesn't exist." | "Pick a valid mode." | `activate_runtime_mode` |
| `unknown_capability:{cap}` | "That capability doesn't exist." | "Pick a valid capability." | `request_capability_transition` |
| `invalid_target_state:{state}` | "That target state isn't allowed." | "Choose an allowed transition." | `request_capability_transition` |

### Policy / execution outcomes — `route_action` (`router.py`)
| reason_code / message | Plain English | Remediation | Source |
|---|---|---|---|
| `denied_by_policy` | "Policy blocked this action." | Show the `PolicyDecision` reason; no UI override. | `route_action` |
| `critical_action_requires_human_confirmation` | "Critical action needs a human." | "A human must confirm; AI is blocked." | `route_action` |
| `approval_required` | "This needs human approval first." | "Route to Approvals (resolution is metadata-only)." | `route_action` |
| `risk_acceptance_required` | "You must accept the risk first." | "Review and accept the risk in the action detail." | `route_action` |
| `execution_failed:{reason_code}` | "The executor failed." | Show the inner `reason_code`. | `route_action` |
| `execution_unavailable:no_executor` | "No runtime exists for this — it's deferred." | "Not available in the local single-user runtime." | `route_action` / executors |

### Activation blocks — `raiker/runtime/authority/activation.py`
| reason_code | Plain English | Remediation |
|---|---|---|
| `activation_blocked:no_executor` | "No runtime exists for this yet — deferred." | "Not available in the local single-user runtime." |
| `activation_blocked:no_threat_model_ack` | "A threat-model acknowledgement is required." | "Provide the acknowledgement in the step-up window." |
| `activation_blocked:runtime_mode_not_active` | "The required runtime mode isn't active." | "Activate the runtime mode first (Security Settings)." |
| `activation_blocked:needs_human_confirmation` | "Human confirmation token required (Tier 2)." | "Enter the confirmation token." |
| `activation_blocked:no_requirement_entry` | "No activation requirement entry — can't enable." | "Capability is not flippable in this runtime." |

If a `reason_code` is unknown to the UI, show the **raw code** plus a generic explanation —
**never hide it**.

## Step-up auth window (Security Settings)

- Triggered before opening Runtime Mutations and before each mutation call.
- Re-confirms the acting **human** principal (via the existing session/principal resolution) and
  collects the backend-required inputs: `reason`, Tier-2 `confirmation_token`, threat-model ack.
- Grants nothing the backend wouldn't already require — it only *collects and forwards* them to
  the existing governed control routes. On failure: plain-English denial, no partial state.

## STOP switch

- Always visible in the top bar; high-contrast round red button; `aria-label="Stop all tasks"`.
- Confirm dialog text: *"Cancel all active tasks at the next safe boundary. This is not an instant
  force-kill; in-flight safe operations finish first."*
- Issues `POST /api/interrupts {all:true, action_type:"cancel", reason}`; renders resulting
  `interrupt_received` / `safe_boundary_reached` / `task_cancelled` events as confirmation.

## Specific security treatments (required)

1. **Capability gate disabled** → `Disabled` badge + "why" + enable path (if supported).
2. **Runtime mode disabled** → banner note; mutations blocked.
3. **Approval required** → `Needs approval` badge; routes to Approvals.
4. **Risk acceptance required** → `Risk-acceptance required` badge; show risk summary.
5. **AI principal not allowed** → controls hidden/disabled; explain human-only.
6. **Action denied by policy** → `Blocked` badge + policy reason.
7. **Executor not implemented** → `Deferred` badge + "no runtime exists".
8. **Metadata-only approval resolution** → persistent banner on approval surfaces.
9. **Shell/network/web-fetch Tier 2 warnings** → strong warning + confirmation-token requirement.
10. **Secret/credential-like memory content blocked** → show the deny reason, never the secret.
11. **Deferred sensitive domains** (email/calendar/finance/medical/cctv/home_security/hardware)
    → always `Deferred`/`Disabled`; never interactive; `DisabledCapabilityExplainer` shows what
    would be required before enablement and that it is future/deferred, not implemented-but-gated.

## Accessibility

Keyboard navigable; screen-reader labels on every control and badge; never colour-only for
risk/status; visible focus states; sufficient contrast; responsive for laptop screens.
