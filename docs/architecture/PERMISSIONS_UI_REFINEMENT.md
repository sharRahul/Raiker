# Permissions and work-page simplification

**Status:** implemented 2026-11-27 after owner approval. Extends [Quiet UI](../plans/QUIET_UI_PLAN.md)
and the approved [authorization contract](../plans/APPROVAL_REDESIGN.md#contract).

## Purpose

Help the owner understand what Raiker may access, when it asks, and what needs
attention. Chat, Build and Design should give most of their space to the work.
The audience is a personal-agent owner, not a runtime administrator.

## Findings before implementation

* Permissions repeated its state through a profile sentence, three posture
  choices, seven goal summaries, Build setup, category rows and advanced notes.
  These representations competed instead of guiding one decision.
* Build setup said every change and command asks first. That was inaccurate
  when verified sandbox preparation is selected.
* `permissionLanguage.ts` exposed Allow and Automatic with different promises,
  while the shared composer had a separate sandbox policy. The UI must
  describe the effective authority, not imply that a capability setting bypasses
  runtime restrictions.
* Build repeated repository, target, environment, approval mode and project/folder
  facts between its header and composer. Routine context competed with blockers.
* User-facing history mixed Threads, Session and Conversation; Sessions remained
  visible in errors and table headings. Technical identifiers belong in details.

These findings motivated the implementation. Desktop and compact-width, light
and dark captures were subsequently reviewed; verification is recorded below.

## Considered approaches

1. **Consolidate and disclose (selected).** Keep Raiker's established visual
   system and permission model. Reorganize common controls, shorten language,
   and disclose technical evidence. Reduces clutter while keeping every control
   and audit record reachable.
2. Copy-only pass. Low disruption, but repeated panels and competing controls
   would remain.
3. Replace all work-page navigation and settings. Larger migration and discovery
   cost; unnecessary for this task.

## Permissions layout

One page header, one compact current-mode section and a searchable list of
permission categories. Use existing Inter typography, semantic color tokens,
spacing, focus styles and restrained surfaces; avoid new decorative cards.

* **Default mode:** Ask first, Work in the sandbox, Read-only. Explain the selected
  choice in one short sentence. Keep measured sandbox unavailability visible
  with its setup action. Show pending changes and a concrete Save changes action.
* **Permissions:** task-oriented categories with concise names and truthful row
  summaries. Keep access availability separate from approval behavior: enabling
  a feature is not approval for every action. An unavailable feature must not
  appear usable because its saved approval setting says Allow.
* **Permission details:** access state, approval rule, applicable scope and
  restrictions, then advanced technical facts. Existing Ask/Deny restrictions,
  step-up requirements and confirmation behavior remain authoritative.
* **Needs attention:** only actionable problems, omitted when empty. Do not
  repeat the complete permission list as prose summaries.
* **Advanced:** registry identifiers, authority matrix, unusual decision modes
  and diagnostic explanations. Preserve direct links to existing categories
  and permission details. Keep task rules and their revocation discoverable
  through existing approval/rule controls; do not invent an unsupported editor.
* Build setup remains a contextual setup action, with a review of what enabling
  it changes. Replace claims that every copied edit/test always asks with the
  actual selected policy. No control silently enables broader access.

## Work-page hierarchy

The conversation or artifact is primary. Show its title and a compact project
or folder context once. Put secondary actions in the established overflow menu.

* **Chat:** messages, input and actions first. Put routine source/context usage,
  receipts and execution details behind clearly named controls. Preserve useful
  sources with the answer. Keep waiting decisions, failures and Stop visible.
* **Build:** show project/repository and branch once. Put commit hashes, target
  fingerprints, environment details and delegation limits in an accessible
  Work details disclosure. A changed target, remote execution, unavailable
  sandbox or active delegation must still be apparent before submission.
  Keep Changes, Review, Apply and failed/unverified checks visible when relevant.
  Never collapse a consequential approval into routine activity.
* **Design and other work pages:** use the same title, context, activity and
  details hierarchy, adapted to each page's main task. Inspect Home, Tasks and
  history too; change only clutter demonstrated by the audit.
* **History vocabulary:** use Chats for saved conversations and Chat for an
  individual conversation; use Task for background work and Activity for tool
  progress. Keep Build and Design as workspaces. Replace user-facing Session
  terminology consistently, including accessible names and errors. Preserve
  API names, IDs, stored records and existing deep links.
* **During work:** one compact status describes current activity. Completed
  routine steps fold into Activity. Errors, decisions and unknown outcomes stay
  explicit. Do not invent progress or use reassuring labels as security proof.

## Implementation and verification

The single-agent implementation reused the existing Svelte controls, runtime
read models, routes and permission mutations. No authorization policy or stored
rule was changed by the presentation migration. Unknown states and failed
saves retain their existing treatment. Needs-review badges remain actionable;
the complete summary is available on request.

Local verification: 313 frontend test files passed (2,975 tests, one skipped),
31 deterministic browser cases passed, Svelte reported zero errors/warnings,
and ESLint, production build and documentation contracts passed. Browser cases
cover real-account Permissions, a real local-model approval/refusal, default
and advanced rules, accessible details, doubled CSS zoom, desktop and 390 px,
both themes and source/target evidence. Existing rule, explicit-denial,
unavailable-sandbox, continuation and partial-save regressions remain in CI.

See the [live record](WEB_APP_LIVE_TEST.md#result--2026-11-27-permissions-and-work-page-refinement)
for screenshots, test scope and limitations. Delivery `82f0cf1d` passed [CI](https://github.com/sharRahul/Raiker/actions/runs/46026675533),
[llama.cpp](https://github.com/sharRahul/Raiker/actions/runs/46026675468) and
[Data safety](https://github.com/sharRahul/Raiker/actions/runs/46026675493). Full release qualification remains in the
[readiness plan](../plans/READY_TO_USE_PLAN.md), independently of this UI work.

## Reference decisions

Primary material reviewed 2026-11-27. Closed products are represented by public
documentation, not claims of access to their private source code.

| Reference | Applied decision |
|---|---|
| [Claude permissions](https://code.claude.com/docs/en/permissions) | Reviewable scoped rules; Deny and Ask retain precedence over Allow |
| [ChatGPT app permissions](https://help.openai.com/en/articles/20001495-managing-app-permissions-in-chatgpt) | Separate account access from approval settings and consequential confirmation |
| [Cursor security](https://cursor.com/docs/agent/security) | Sensitive actions require explicit approval; disclose actual access boundaries |
| [Meta Muse guidance and approval](https://www.meta.com/en-gb/help/superintelligence/1385290430137537/) | Task-local decisions with details on demand and centrally reviewable permissions |
| [Perplexity Personal Computer](https://www.perplexity.ai/personal-computer-setup) | Name connected folders/apps and the boundary of the requested task |
| [Hermes approval source](https://github.com/NousResearch/hermes-agent/blob/main/tools/approval.py) | Shared decision engine and explicit task/session scope across transports |
| [Apple Design skill](https://github.com/dickwu/apple-design-skill/blob/main/SKILL.md) | Apply layout hierarchy, settings, privacy, accessibility and disclosure guidance to Svelte/Electron |
| [Impeccable](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/SKILL.md), [distill](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/reference/distill.md), [clarify](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/reference/clarify.md), [site](https://impeccable.style/) | Remove repeated information, preserve decision-critical content, verify rendered results |

Apple reference files loaded: accessibility, layout, typography, color,
designing-for-macos, settings, privacy, disclosure-controls and cross-platform.
For example, `layout.md` under Visual hierarchy recommends progressive
disclosure; `privacy.md` under Best practices says "Request access only to data
that you actually need." The Impeccable launcher was unavailable; repository
context and its published playbooks were read directly. No remote binary or
design hook was installed.
