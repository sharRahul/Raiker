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

The backend returns machine `reason_code`s on denial (403 `{ok:false, reason_code}`) and inside
`PolicyDecision`/`GovernedActionResult`. The UI maps each to a human explanation **and** a
"what would be required" remediation. Representative mapping (extend as backend codes are
enumerated during M5/M7):

| reason_code (pattern) | Plain English | Remediation shown |
|---|---|---|
| `capability_gate_disabled:*` | "This capability is turned off." | "Enable it in Security Settings → Runtime Mutations (if supported)." |
| `activation_blocked:no_executor:*` | "No runtime exists for this yet — it's deferred." | "Not available in the local single-user runtime." |
| `activation_blocked:runtime_mode_not_active:*` | "The required runtime mode isn't active." | "Activate the runtime mode first (Security Settings)." |
| `activation_blocked:no_threat_model_ack:*` | "A threat-model acknowledgement is required." | "Provide the acknowledgement in the step-up window." |
| `activation_blocked:needs_human_confirmation:*` | "Human confirmation token required." | "Enter the confirmation token (Tier 2)." |
| `*human_only*` / AI role denial | "An AI principal can't perform this human-only action." | "A human owner must do this." |
| `policy_denied:*` | "Policy blocked this action." | Show policy reason; no override in UI. |
| `risk_acceptance_required:*` | "You must accept the risk first." | "Review and accept the risk in the action detail." |
| `self_approval_denied` | "You can't approve your own action." | "Another authorised human must approve." |
| `secret_like_content_denied` | "Looks like a secret/credential — blocked before storage." | "Remove sensitive content." |

If a `reason_code` is unknown to the UI, show the raw code plus a generic explanation — **never
hide it**.

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
