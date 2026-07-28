# Composer unified experience and mode stabilization

## Purpose

Give Chat and Build the same clear, durable control over governed agent work.
Both composers retain their existing Context control, show the active project
scope and approval posture in matching pills, and surface active background
work without requiring a separate navigation change.

## Approval policy

The composer owns an account-scoped approval policy with three values:

| UI label | Stored value | Behaviour |
|---|---|---|
| **Manually approve** | `manual` | Stop before every governed tool action and show an inline approval request. |
| **Automatically approve** | `auto` | Run eligible non-critical actions immediately and report progress inline. |
| **Skip all approvals** | `skip` | Run eligible non-critical actions immediately without generating an approval preview. |

The selected value is read when either composer opens, persisted for the
account, included in each prompt envelope, and retained with a suspended turn
so an approval-resumed turn keeps its original policy.

`skip` is deliberately a zero-friction UI choice, not a capability grant.
Every mode continues to enforce workspace containment, managed-policy denials,
tool argument validation, hunk/context matching, transactional patch failure
handling, capability gates, and critical-risk holds. A policy denial or a
critical hold cannot be converted into execution by the composer.

The runtime applies the policy where it has enough information to decide: after
a tool call has been validated and policy-reviewed, before it is executed or
parked for a user decision. `manual` turns otherwise executable governed calls
into an approval request. `auto` and `skip` execute a normal user-approval
request only when the action is eligible; the former emits the ordinary status
and preview evidence, while the latter omits the preview. Existing policy and
hook decisions remain authoritative.

## Composer interface

Chat and Build use one reusable approval selector. It appears next to the
project/folder scope control in the bottom composer toolbar and follows the
same compact rounded pill styling.

- **Manually approve** uses a hand icon.
- **Automatically approve** uses a fast-forward icon.
- **Skip** uses a warning triangle icon.

The trigger updates its label, icon, tint, and accessible label with the active
policy. Its menu exposes all three choices and marks the current choice with a
checkmark. It supports mouse, keyboard, and screen-reader interaction.

Chat gains the same project scope selector as Build. Scope remains organisation
and bounded context only; selecting it grants no capability. Long project names
truncate gracefully, and toolbar controls wrap in predictable groups on narrow
layouts without obscuring model, attachment, voice, or send controls.

Build continues to expose Plan, Edit, and Auto execution modes. Their
explanations are no longer permanently visible: a tooltip is available on mouse
hover and keyboard focus, referenced through `aria-describedby` so the mode
meaning remains available without consuming composer height. Mode changes must
remain server-accepted before the interface claims that they are active.

## Inline background work

The existing Background Work panel is embedded beside the conversation in both
Chat and Build. It shows queued, running, paused, and approval-blocked work,
including current step and progress when reported by the runtime. The panel can
refresh and collapse, preserves its responsive stacked layout at small widths,
and exposes a direct **Review approval** action for approval-blocked work.
That action opens the scoped Approvals surface rather than inventing a second
approval execution route.

## Runtime mode acceptance

Plan, Edit, and Auto remain real governed postures rather than UI labels:

| Mode | Runtime posture |
|---|---|
| **Plan** | Planning always enabled; write/patch/shell/process capabilities are denied. |
| **Edit** | Write/patch/shell/process capabilities require a decision. |
| **Auto** | The runtime applies its automatic-risk floor and reports background progress. |

The API validates accepted planning and approval-policy values at prompt
construction, preserves them through streaming and resume paths, and returns a
truthful failure instead of leaving the composer in a mismatched state.

## Error handling and privacy

- A rejected preference update leaves the previously confirmed policy visible
  and gives a concise error.
- Loading failure never fabricates a policy; the selector remains disabled or
  states that the policy cannot be read.
- Inline work uses existing task and approval records. It does not expose tool
  arguments, raw model reasoning, or sensitive process output.
- A skipped preview never skips tool validation, policy review, auditing, or
  safety checks.

## Verification

- Backend tests cover valid/invalid policies, persistence, request and resume
  propagation, manual interception, auto execution, skip-without-preview, and
  immutable runtime protections.
- Web tests cover pill state, checkmarks, persistence on reload, tooltip
  accessibility, narrow-toolbar layout, project scope parity, and inline work
  panel approval routing.
- Plan/Edit/Auto tests confirm server acceptance and runtime behaviour.
- A headed Playwright flow uses Ollama `gemma4:31b-cloud` to exercise the
  composed UI and captures screenshots in the existing documentation location.
- The final gate runs web type checks, linting, tests, production build, backend
  tests, documentation checks, and the relevant GitHub workflow checks.

## Non-goals

- No approval mode disables managed policy, workspace containment, capability
  gates, critical-risk holds, validation, or rollback.
- No duplicate approval engine exists in the web client.
- No Context control is removed or changed into an approval control.
