# Raiker Unified Composer Redesign — 2026-09-06

## Implementation status — 2026-09-07

Waves 1 to 4 are implemented and verified against a live runtime holding real
Anthropic, OpenAI and OpenRouter credentials. Recorded as
[FIXED-454](FIXED_ITEMS.md#fixed-454--the-composer-grew-one-permanent-button-at-a-time),
with the two defects the work surfaced as
[FIXED-455](FIXED_ITEMS.md#fixed-455--two-reads-whose-shape-nothing-checked-took-the-page-down).

| Item | State |
|---|---|
| COMPOSER-01 shared shell | Done — `Composer.svelte` plus `ComposerActionMenu`, `ComposerContext` |
| COMPOSER-02 minimal default state | Done — `[+] [Tools] … model … Send` |
| COMPOSER-03 one Add menu | Done |
| COMPOSER-04 one Tools menu | Done, derived from the typed registry |
| COMPOSER-05 model identity, hidden management | Done — picker ends in one link to Models |
| COMPOSER-06 one context line | Done — the meter is composed into its inspector |
| COMPOSER-07/08/09 per-surface composition | Done; Design's Tools control is deliberately absent, see below |
| COMPOSER-10 Tasks/Schedule composer | Partial — Tasks keeps its own model picker; the shared shell is not applied there yet |
| COMPOSER-11 Project continuity | Partial — the Project is carried and shown per surface; a shared draft across modes is not implemented |
| COMPOSER-12 governance near the action | Done — the posture chip renders only as an exception |
| COMPOSER-13 slash and `@` accelerators | Already satisfied; `+` now makes the same actions discoverable without the syntax |
| COMPOSER-14 paste/drop intelligence | Partial — drag/drop and paste attach as before; large-paste-to-attachment is not implemented |
| COMPOSER-15 adaptive primary action | Done for Chat, Build and Design's single actions; Build's `Run ▾` intents are not implemented |
| COMPOSER-16 mobile bottom sheet | Done |
| COMPOSER-17 keyboard behaviour | Done — Escape closes a menu, the composer's own bindings are unchanged |
| COMPOSER-18 no duplicated page actions | Done |
| COMPOSER-19 typed capability registry | Done — `composerCapabilities.ts` |
| COMPOSER-20 visual quality rules | Done; rules 3 and 12 are pinned by `visualRubric.test.ts` |

**What is deliberately not built, and why.** COMPOSER-09 describes edit,
variations, outpaint, reference images and version compare. Raiker's governed
image endpoint takes a prompt, a size and a model and returns one picture, so
those controls have no runtime to reach. This document's own acceptance test 19
settles what to do about that — *every exposed composer action reaches an actual
backend/runtime path or is omitted* — so they are absent rather than present and
inert, and the missing runtime is recorded in
[`TO_BE_FIXED.md`](TO_BE_FIXED.md).

---

## Goal

Create one coherent composer system across Raiker that feels as visually simple as the strongest current AI products while supporting substantially more governed capability underneath.

The composer should follow one rule:

> **Simple at rest, powerful on demand.**

Raiker should not expose every available action as a permanent button. The normal state should make writing or giving an instruction feel immediate. Attachments, tools, model choice, context, agent controls, design options, execution controls and governance should appear through progressive disclosure, contextual controls and mode-specific panels.

This applies to every user-facing Work surface and every page that allows the user to issue an instruction:

- Chat
- Build
- Design
- Project workspaces
- Task creation
- Schedule creation
- model/setup workflows that invoke an agent action
- future plugin/MCP-assisted work surfaces

It does **not** mean every page gets an identical composer. The shell and interaction grammar are shared; the controls shown are determined by the object of work.

---

# Competitive design principle

Current leading AI products increasingly use a restrained prompt field with attachments/tools hidden behind one or two entry points rather than permanent rows of controls. Recent ChatGPT changes also explicitly move large pasted content into attachments to keep the composer clean, while Gemini groups file inputs and specialist capabilities under Add files / More tools instead of exposing every option at once.

Raiker should adopt the same **interaction principle**, not copy another product's exact appearance:

1. one dominant text/instruction field;
2. one compact attachment/context entry point;
3. one compact tools/actions entry point;
4. visible model identity without a large model-management UI;
5. primary Send/Run/Generate action;
6. secondary capability revealed only when requested or contextually required.

Raiker's differentiation remains governed agency. The composer must make that power feel quieter, not weaker.

---

# COMPOSER-01 — One shared composer shell

**Priority: P0/P1 — Effort: Medium — Impact: Very high**

Create a shared visual and behavioral shell rather than separately evolving Chat, Build and Design composers.

Suggested component architecture:

```text
ComposerShell
├── ComposerInput
├── ContextTray
├── AttachmentTray
├── ComposerActionMenu
├── ModelControl
├── ModeContext
├── RunAction
├── StopAction
└── ComposerStatusLine
```

Mode-specific components plug into that shell rather than duplicating the entire composer.

The shared contract should cover:

- multiline text input;
- drag/drop/paste;
- attachment previews;
- model indicator/picker;
- current Project/context indicator;
- tool/capability launcher;
- command/mention grammar;
- send/run/stop semantics;
- keyboard shortcuts;
- loading/progress states;
- approval-required state;
- errors/refusals;
- accessibility;
- compact/mobile behavior.

---

# COMPOSER-02 — Minimal default visual state

**Priority: P0/P1 — Effort: Low/Medium — Impact: Very high**

Default desktop composer should look approximately like:

```text
┌───────────────────────────────────────────────────────────────┐
│ Ask Raiker…                                                   │
│                                                               │
│ [+]   [Tools]                 Claude Sonnet 4.6      [ Send ] │
└───────────────────────────────────────────────────────────────┘
```

or even more compact where appropriate:

```text
[ + ]  Ask Raiker anything…                           [ ↗ ]
       Project Raiker · Claude Sonnet 4.6
```

Do not permanently show separate buttons for:

```text
Upload
Image
File
Web
Search
MCP
Plugin
Memory
Project
Model
Reasoning
Plan
Commands
Terminal
Browser
Agent
Approval mode
Context
Voice
```

Those may all be available, but not all visible at once.

### Rule

At rest, the composer should normally expose no more than:

- Add/context control;
- optional Tools control;
- compact current model/context identity;
- Send/Run/Generate.

Everything else is progressive disclosure.

---

# COMPOSER-03 — One Add menu for inputs and context

**Priority: P1 — Effort: Medium — Impact: High**

The `+` control should open a context-aware menu such as:

```text
Add to this turn

Upload file
Upload image/media
Choose from Project files
Choose from Raiker Library
Add code/repository context        Build
Add current canvas/selection       Design
Add URL
Add source/connector
Use camera / screenshot            supported platforms
```

Only relevant options appear.

### Important behavior

- drag/drop and paste remain direct shortcuts;
- large pasted content may become an attachment instead of making the composer visually enormous;
- attachments appear in a compact tray above the input;
- attachments show filename/preview/status and one remove control;
- detailed metadata appears only on inspect.

---

# COMPOSER-04 — One Tools menu for capabilities

**Priority: P1 — Effort: Medium — Impact: Very high**

Use one compact Tools/action launcher instead of permanent capability buttons.

Example:

```text
Tools

Search web
Use connected app
Use MCP tool
Run command                     Build only / governed
Open browser                    when available
Create task
Schedule follow-up
Generate image                  Design / multimodal models
Analyse files
Use memory/context
More…
```

The menu must be generated from the capabilities the current principal and surface may actually use.

A disabled capability should not clutter the normal composer. If discoverability is useful, show it in the Tools menu with an explanation such as:

```text
Run command
Requires approval / capability disabled
```

rather than adding another permanent toolbar control.

---

# COMPOSER-05 — Keep model identity visible, management hidden

**Priority: P1 — Effort: Low/Medium — Impact: High**

The current model should remain identifiable at a glance, but the composer should not reproduce the Models administration page.

Recommended compact control:

```text
Claude Sonnet 4.6 ▾
```

or on narrow layouts:

```text
Sonnet 4.6 ▾
```

Opening it shows only models valid for this surface and current context:

```text
Recommended
Claude Sonnet 4.6        Selected
GPT-5.6
Gemini 3 Pro

Local
Qwen 3 30B               Stopped

Manage models →
```

Rules:

- selected model persists independently of runtime health;
- unavailable selected model remains visible with state;
- effective fallback is shown if different;
- Chat, Build and Design use their own persisted defaults;
- the composer does not expose provider API-key configuration.

---

# COMPOSER-06 — Context should be one compact, inspectable line

**Priority: P1 — Effort: Medium — Impact: High**

Avoid rows of context chips.

Prefer:

```text
Project Raiker · 4 files · Repo main · 62% context
```

Click/tap opens a contextual inspector:

```text
Context
Project: Raiker
Repository: sharRahul/Raiker @ main
Files: 4
Memory: Project + account
Selected design asset: hero-v7.png
Estimated context: 82k / 128k

[ Manage context ]
```

Only facts relevant to the current mode appear.

---

# COMPOSER-07 — Chat composer

**Priority: P1 — Effort: Medium — Impact: Very high**

Chat should have the lowest density.

Target:

```text
┌─────────────────────────────────────────────────────────────┐
│ Message Raiker…                                             │
│                                                             │
│ [+] [Tools]            Project Raiker · GPT-5.6      [Send] │
└─────────────────────────────────────────────────────────────┘
```

Capabilities available through progressive disclosure may include:

- files/images/audio/video;
- web/search;
- connected apps;
- plugins/MCP;
- tasks/scheduling;
- memory/context;
- deep research/work handoff if supported;
- voice/dictation;
- model/reasoning choice.

Do not make Chat look like an IDE toolbar simply because Raiker can perform agent actions.

---

# COMPOSER-08 — Build composer

**Priority: P1 — Effort: Medium — Impact: Very high**

Build may expose slightly more operational context because the object of work is code and execution.

Target:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Ask Raiker to change, review, test or explain…                     │
│                                                                     │
│ [+] [Tools]  Repo: Raiker/main  Claude Sonnet 4.6     [Run ▾]      │
└─────────────────────────────────────────────────────────────────────┘
```

`Run ▾` can expose execution intent when needed:

```text
Plan only
Propose changes
Implement
Implement + test
Review only
```

But this should not become five permanent buttons.

Build-specific Tools may include:

- repository/file selection;
- terminal/command;
- test target;
- browser preview;
- diff/reference selection;
- issue/PR context;
- connected GitHub actions;
- plan/checkpoint controls.

### Contextual controls

When a file/diff/terminal selection exists, show a small contextual token such as:

```text
Editing: raiker/models/router.py ×
```

Do not add another toolbar.

---

# COMPOSER-09 — Design composer / create bar

**Priority: P0/P1 — Effort: Medium — Impact: Very high**

Design should use the same shell grammar but be visually attached to the canvas.

Target:

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Describe what to create or change…                                  │
│                                                                       │
│ [+] [Tools] [16:9] [1024]    GPT Image / selected model   [Generate] │
└───────────────────────────────────────────────────────────────────────┘
```

Only the most frequently changed visual parameters may remain visible.

Everything else belongs in `Options` / Tools:

```text
Aspect ratio
Resolution
Count
Style/reference strength
Transparent background
Seed if supported
Quality
Output format
Safety/provenance details
```

When an object/region is selected:

```text
Selection: subject mask ×
```

and the primary action changes from `Generate` to `Edit` automatically.

The composer should understand:

- create new asset;
- edit current asset;
- edit selection;
- create variations;
- extend/outpaint;
- remove/replace object;
- use reference image;
- compare versions.

Do not expose each as a separate permanent button.

---

# COMPOSER-10 — Tasks and Schedule composer

**Priority: P1/P2 — Effort: Medium — Impact: High**

Task/schedule creation should reuse the instruction composer rather than look like an unrelated admin form.

Example:

```text
What should Raiker do?
[ Summarise security news and surface important changes ]

[+] [Tools]                         [Schedule ▾] [Create]
```

Scheduling details expand only after requested:

```text
When
Every weekday · 08:00

Run with
Project context: Security research
Model: Project default
Tools: Web search

Notify only when
Meaningful changes found
```

Advanced recurrence syntax, exact backend identifiers and operation metadata should not be in the primary composer.

---

# COMPOSER-11 — Project composer continuity

**Priority: P1 — Effort: Medium — Impact: High**

A composer inside a Project inherits Project context visibly but quietly.

Switching:

```text
Chat → Build → Design
```

should retain:

- Project identity;
- allowed Project files/context;
- selected repository when applicable;
- model default for the new surface;
- applicable tools/capabilities;
- unfinished draft where product rules permit.

Do not duplicate the Project context as a permanent full-width toolbar on every Work page.

---

# COMPOSER-12 — Approval and governance states belong near the action, not permanently in the toolbar

**Priority: P1 — Effort: Medium — Impact: Very high**

Normal composer state should not contain multiple governance buttons.

If the next action crosses a policy/authority boundary, the composer transitions contextually:

```text
This run will send 2 project files to Anthropic.
Approval required.

[ Review ] [ Cancel ]
```

or:

```text
Command execution requires confirmation.
python scripts/rebuild_index.py

[ Review command ]
```

Keep the global governance posture inspectable, but do not force the user to understand the entire policy system before ordinary typing.

---

# COMPOSER-13 — Slash commands and @ mentions as accelerator, not requirement

**Priority: P2 — Effort: Medium — Impact: High**

Power users should be able to invoke context/tools without opening menus:

```text
@file
@project
@repo
@memory
@asset
@tool
```

and optionally commands such as:

```text
/plan
/test
/review
/schedule
```

But every important action must remain discoverable without memorising syntax.

Autocomplete should show only permitted/relevant entities.

---

# COMPOSER-14 — Paste, drag/drop and attachment intelligence

**Priority: P1/P2 — Effort: Medium — Impact: High**

The composer should intelligently handle input without becoming visually huge.

Examples:

- long pasted text → compact text attachment with “show inline” option;
- code paste → syntax-aware attachment/snippet;
- image paste → thumbnail;
- multiple files → horizontally scrollable/stacked compact tray;
- folder/repository drop in Build → structured repo/folder context if supported;
- asset drop in Design → reference/import asset.

All transformations must remain transparent and reversible.

---

# COMPOSER-15 — Adaptive primary action

**Priority: P1 — Effort: Low/Medium — Impact: High**

The right-side primary action should adapt to the surface and state:

```text
Chat          Send
Build         Run / Apply / Review depending mode
Design        Generate / Edit / Variations
Task          Create task
Schedule      Schedule
Running       Stop
Approval      Review
```

Do not show Send + Run + Stop + Approve simultaneously.

One state = one obvious next action.

---

# COMPOSER-16 — Mobile behavior

**Priority: P1 — Effort: Medium — Impact: High**

Mobile composer target:

```text
┌───────────────────────────────┐
│ Message Raiker…               │
│                               │
│ [+]   GPT-5.6 ▾        [Send] │
└───────────────────────────────┘
```

`+` opens a bottom sheet containing context/tools/actions.

Rules:

- do not horizontally squeeze desktop toolbar buttons;
- keep model identifiable;
- attachments become a compact scrollable tray;
- active Project/context is available in one tap;
- Design uses canvas + composer + bottom-sheet inspector;
- Build uses contextual drawers for repo/tools rather than miniature multi-row toolbars.

---

# COMPOSER-17 — Keyboard behavior

**Priority: P1 — Effort: Low/Medium — Impact: High**

Recommended baseline:

```text
Enter              Send/run when appropriate
Shift+Enter        New line
Cmd/Ctrl+Enter     Explicit run/send alternative where configured
Cmd/Ctrl+K         Command palette
@                  Context/entity picker
/                  Composer commands
Esc                Close popover / stop selection mode
```

Do not overload Enter unpredictably between surfaces. The composer should display a one-time/tooltip hint where behavior differs.

---

# COMPOSER-18 — Do not duplicate page-level actions in the composer

**Priority: P1 — Effort: Low — Impact: High**

Composer capabilities and page management actions must remain separate.

Examples:

- Models page: model/provider administration stays in the page; composer only changes the model for work when appropriate.
- Projects: rename/archive/share/manage context stay outside composer.
- Build: branch/repository management is not permanently duplicated beside the input.
- Design: export/download/version management belongs with canvas/inspector, not the prompt bar.

The composer is for **issuing work**, not administering every object on the page.

---

# COMPOSER-19 — Capability-aware composition from one typed registry

**Priority: P1/P2 — Effort: High — Impact: Very high**

Long-term, composer menus should be derived from typed capability metadata instead of manually duplicated button lists.

Conceptually:

```text
ComposerCapability
- id
- label
- surfaces
- required authority
- input kinds
- availability predicate
- action/picker
- approval behavior
- shortcut/mention
- presentation priority
```

This allows Raiker to add capabilities without turning every composer into another permanent toolbar.

Security rule:

> Composer visibility never grants authority. It only reflects capability that the runtime may still allow, ask, or deny when invoked.

---

# COMPOSER-20 — Visual quality rules

**Priority: P1 — Effort: Low — Impact: Very high**

1. One rounded composer surface, not nested card borders.
2. One primary action.
3. Maximum two permanent utility entry points before the model/action controls.
4. No permanent text labels where an established icon plus accessible tooltip is clearer.
5. No more than one line of passive metadata at rest.
6. Context chips appear only for active, removable turn-specific context.
7. Healthy governance/runtime status is neutral.
8. Errors/refusals appear inline near the relevant action.
9. Advanced controls open in popover/bottom sheet/inspector, not a second toolbar.
10. Composer grows vertically with text to a sensible limit, then scrolls internally.
11. Attachments never push the primary input out of the viewport.
12. Same spacing/radius/type system across Chat, Build and Design.

---

# Page-by-page composer requirement

| Page / surface | Composer role | Default visible controls |
|---|---|---|
| Chat | Ask/instruct | Add, Tools, model, Send |
| Build | Change/review/run | Add, Tools, repo/context, model, Run |
| Design | Create/edit visual | Add, Tools, essential visual option(s), model, Generate/Edit |
| Project Chat | Chat with inherited Project context | Add, Tools, Project summary, model, Send |
| Project Build | Build with inherited repo/files | Add, Tools, repo summary, model, Run |
| Project Design | Design with inherited assets/context | Add, Tools, selection/asset summary, model, Generate/Edit |
| Task creation | Describe recurring/one-shot work | Add, Tools, Schedule options, Create |
| Schedule | Define work + timing | Add, Tools, timing summary, Schedule |
| Models | No permanent general composer required | model-management UI; Work model picker links back to Work surfaces |
| Settings | None | no composer |
| Observability | Optional query/filter command field, not Work composer | Search/query only |
| Knowledge Map | Optional contextual ask/explore input | selected node context + Ask |
| Approvals | Decision controls, not composer | Approve/deny/revise only |

Not every page should receive a text box merely for consistency. “Composer on all pages” means **all instruction/work surfaces use the same composer language**, while admin/decision pages keep purpose-built controls.

---

# Implementation order

Priority first, then effort.

## Wave 1 — visual simplification

1. COMPOSER-02 minimal default state.
2. COMPOSER-15 adaptive single primary action.
3. COMPOSER-20 visual rules.
4. COMPOSER-05 compact model control.
5. COMPOSER-06 one-line context summary.
6. Remove duplicated permanent buttons from current Chat/Build/Design composers.

## Wave 2 — shared capability entry points

7. COMPOSER-03 unified Add menu.
8. COMPOSER-04 unified Tools menu.
9. COMPOSER-14 paste/drop intelligence.
10. COMPOSER-17 keyboard behavior.
11. COMPOSER-16 mobile bottom-sheet behavior.

## Wave 3 — mode-specific composition

12. COMPOSER-07 Chat.
13. COMPOSER-08 Build.
14. COMPOSER-09 Design.
15. COMPOSER-10 Tasks/Schedule.
16. COMPOSER-11 Project continuity.

## Wave 4 — governed extensibility

17. COMPOSER-12 approval/governance transitions.
18. COMPOSER-13 @ mentions/slash accelerators.
19. COMPOSER-19 typed capability registry.

---

# Acceptance tests

1. Chat default composer has no more than the agreed minimal permanent controls.
2. Build can access repository, terminal, test and agent functions without permanent buttons for each.
3. Design can create/edit/variation/reference without a large permanent image-generation toolbar.
4. Model identity remains visible on desktop and mobile.
5. Selected model persists across navigation/reload.
6. Selected-but-unavailable model remains visible and effective fallback is separately explained.
7. `+` exposes only relevant permitted input/context sources.
8. Tools menu exposes only relevant capabilities and does not itself grant authority.
9. Drag/drop and paste work without opening menus.
10. Long pasted content does not make the composer take over the viewport.
11. Multiple attachments remain manageable on mobile.
12. Approval-required action changes the composer/action state instead of adding permanent approval controls.
13. Chat → Build → Design inside a Project preserves Project identity.
14. Each mode loads its own model default.
15. Design selection changes Generate to Edit contextually.
16. Build execution state changes Run to Stop contextually.
17. Keyboard behavior is predictable across modes.
18. Admin pages do not get unnecessary generic chat composers.
19. Every exposed composer action reaches an actual backend/runtime path or is omitted.
20. Backend/refusal failures surface next to the action with a useful recovery path.

---

# Final design rule

The composer should be the simplest-looking part of Raiker even though it can invoke some of the most powerful parts of Raiker.

> **Do not display capability just because capability exists. Display intent, context and the next useful action. Reveal capability when the user asks for it.**

For the three first-class Work modes:

> **Chat should feel effortless, Build should feel capable, Design should feel spatial — but all three should clearly be the same Raiker composer system.**
