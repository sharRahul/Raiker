# Information Architecture & Screens

> Planning document. Behaviour described here is binding on the implementation, but no screen is
> "done" until its milestone's tests + the repo validation gate pass.

## Global chrome

- **Left navigation** (persistent): Home · Tasks & Plans · Approvals · Capabilities ·
  Runtime Gates · Models · Events/Audit Log · Checkpoints · Diagnostics · Settings.
- **Top bar** (persistent on every screen):
  - **RuntimeStatusBanner** — runtime mode, local/single-user status, readiness, active principal,
    and any blocked/deferred warnings.
  - **STOP switch** — round red button. Opens a confirm dialog, then issues governed `cancel`
    interrupts for active tasks. Copy: *"Ends all active tasks at the next safe boundary. This is
    not an instant force-kill."* Keyboard reachable; screen-reader labelled.

## Mutation funnel (security model)

All **runtime mutation** (enabling/disabling runtime modes and capability gates) happens in
**one** place: **Settings → Security Settings → Runtime Mutations**, behind a **step-up auth
window**. The top-level **Capabilities** and **Runtime Gates** screens are **read-only status
views**. This gives a single, auditable, gated mutation path.

```
Settings
├── Local UI preferences        (theme, density, reduced-motion — no runtime effect)
└── Security Settings           (behind step-up auth/confirmation window)
    ├── Runtime Mutations        (enable/disable modes & gates; governed; fail-closed aware)
    └── Secret Settings          (READ-ONLY: redaction/deny policy; secret storage = deferred)
```

## Screen specifications

For each: **Purpose · Components · Empty · Loading · Error · Security warnings · Backend data ·
Allowed · Not allowed.**

### Home (Chat)
- **Purpose:** submit prompts; watch the gather→plan→act→verify turn timeline.
- **Components:** prompt box, `ChatTurnTimeline`, `ActionProposalCard`(s).
- **Empty:** "No turns yet. Submit a prompt to start a governed turn."
- **Loading:** streaming indicator on the active turn (SSE).
- **Error:** show `AgentResponse.status=failed` + message; policy denials inline.
- **Security:** proposals requiring approval are badged `Approval-required`; nothing executes
  without going through the governed path.
- **Backend:** `POST /api/prompts`, `GET /api/prompts/{turn_id}/stream`, `GET /api/turns/{id}`.
- **Allowed:** submit prompt, view timeline, open a proposal.
- **Not allowed:** execute tools directly, bypass approval, edit a proposal payload.

### Tasks & Plans
- **Purpose:** view tasks and per-turn plan/steps.
- **Components:** task list (status), plan/step viewer (read-only; plans are `dry_run_only`).
- **Empty / Loading / Error:** standard.
- **Backend:** `GET /api/tasks`, `GET /api/turns/{id}`.
- **Allowed:** view; trigger STOP (top bar). **Not allowed:** run/execute steps.

### Approvals
- **Purpose:** review and resolve approval-required actions.
- **Components:** `ApprovalQueue` (risk, age, source turn, capability, status), detail with
  metadata preview + diff.
- **Empty:** "No pending approvals."
- **Security:** persistent banner — *"Approval resolution is metadata-only. Recording a decision
  does NOT execute the action."*
- **Backend:** `GET /api/approvals`, `GET /api/approvals/{id}`, `POST /api/approvals/{id}/resolve`.
- **Allowed:** approve/deny **with a reason**. **Not allowed:** edit payload, force execution.

### Capabilities  *(read-only)*
- **Purpose:** show all capabilities grouped by domain/tier with honest status labels.
- **Components:** `CapabilityMatrix` (labels: `implemented_read_only`, `implemented_policy_gated`,
  `implemented_approval_required`, `metadata_only`, `readiness_only`, `dry_run_only`,
  `contract_only`, `disabled_deferred`, `test_only`), `DisabledCapabilityExplainer`.
- **Backend:** `GET /api/capability-gates`.
- **Allowed:** view; "Enable in Security Settings →" link. **Not allowed:** inline enable.

### Runtime Gates  *(read-only)*
- **Purpose:** runtime-mode + gate state view (`state`, `runtime_enabled`, `allowed_transitions`,
  `blocked_reason_code`).
- **Backend:** `GET /api/runtime-mode`, `GET /api/capability-gates`, `GET /api/runtime-readiness`.
- **Allowed:** view. **Not allowed:** client-side gate logic, inline mutation.

### Models
- **Purpose:** provider/profile status, health, capabilities; governed profile switch.
- **Security:** show "No silent fallback to hosted providers."
- **Backend:** `GET /api/models`, `POST /api/models/use`.
- **Allowed:** view, switch profile (governed). **Not allowed:** enable hosted runtime (deferred).

### Events / Audit Log
- **Purpose:** append-only event timeline.
- **Components:** `EventLogViewer` with filters: session, turn, action, policy, approval,
  capability gate, checkpoint, error, interrupt.
- **Backend:** `GET /api/events`.
- **Allowed:** view/filter/export-view. **Not allowed:** edit/delete (append-only).

### Checkpoints
- **Purpose:** checkpoint metadata + related task/session/turn + rewind metadata.
- **Components:** `CheckpointViewer`.
- **Backend:** `GET /api/checkpoints`, `GET /api/checkpoints/{id}`.
- **Allowed:** view. **Not allowed:** imply executable rewind unless backend supports it.

### Diagnostics
- **Purpose:** local readiness, validator results, missing config, disabled caps, provider health.
- **Components:** `DiagnosticsPanel`.
- **Backend:** `GET /api/diagnostics`, `GET /api/runtime-readiness`.
- **Security:** never claim production readiness beyond local single-user runtime.
- **Allowed:** view. **Not allowed:** run shell/validators from the browser.

### Settings → Security Settings → Runtime Mutations
- **Purpose:** the only place to enable/disable runtime modes & capability gates.
- **Flow:** `StepUpAuthDialog` re-confirms the acting human principal and collects backend-required
  inputs (reason; Tier-2 confirmation token; threat-model ack) **before** any mutation call.
- **Components:** `SecuritySettingsPanel` (gate rows with current state, `allowed_transitions`,
  enable/disable controls **disabled** unless `can_current_principal_change=true`; fail-closed /
  deferred caps shown un-enableable with `DisabledCapabilityExplainer`).
- **Backend:** existing `POST /api/runtime-mode/{activate,disable}`,
  `POST /api/capability-gates/{cap}/{set,disable}`.
- **Security:** denials rendered in plain English from `reason_code`; AI principals fully blocked.
- **Allowed:** governed enable/disable of supported caps. **Not allowed:** enabling unsupported /
  fail-closed runtimes; client-side authority.

### Settings → Security Settings → Secret Settings  *(read-only)*
- **Purpose:** show redaction/deny-secrets policy that already exists.
- **Components:** redaction policy view; prominent **"Secret storage is not implemented
  (deferred)"** notice.
- **Allowed:** view policy. **Not allowed:** enter or store secrets.

### Settings → Local UI preferences
- **Purpose:** theme, density, reduced-motion. **No runtime effect, no secrets, no mutation.**

## Cross-cutting states

- **Empty:** plain, explanatory ("nothing here yet" + why), never a spinner-forever.
- **Loading:** skeletons; SSE stream indicators on active turns.
- **Error:** show backend `reason_code` + human explanation; offer remediation where known.
- **Unsupported/deferred:** explicit "unavailable / not implemented / deferred" — never faked data.
