# Raiker Visual UI/UX Review — 2026-09-06

## Scope

This pass reviews the current Raiker web UI at `main` commit `371ccdddcf6ac1e82da4771b513dec64015f263a` for visual quality, hierarchy, product coherence, information density, navigation, interaction design, theming and perceived polish.

Evidence reviewed:

- current screenshot catalogue under `docs/plans/screenshots/pages/` and its responsive/theme sweep documentation;
- `apps/web/src/app.css` and the Control Deck design tokens;
- `App.svelte`, `Sidebar.svelte`, `nav.ts` and representative view/component structure;
- current product patterns from ChatGPT, Claude, Gemini, Perplexity and Cursor as reference points, not templates to copy.

This is a design review, not a request to make Raiker imitate another product. Raiker's differentiation is governed agency. The goal is to make that capability feel calmer, more premium and easier to understand.

---

# Executive assessment

Raiker already has the foundations of a real design system: consistent spacing/radius tokens, Manrope + JetBrains Mono + Source Serif 4, bounded canvases, dual-theme support, responsive sweeps, density controls, semantic state colours and a deliberately limited palette.

The main visual problem is **not lack of styling**. It is that too much of Raiker's internal architecture remains visible at once.

The interface often behaves like a polished control plane. That is appropriate for Permissions, Observability and advanced runtime configuration, but it leaks into ordinary Chat, Build, Projects and Tasks. As a result, Raiker can feel more like an administration console with an assistant inside it than an assistant/agent product with governance available when needed.

The target should be:

> **Conversation-first and work-first in normal use; control-deck precision only when the user enters governance, diagnostics or advanced configuration.**

Raiker should look quieter than it is powerful.

---

# Competitive patterns worth borrowing

## ChatGPT

Useful pattern: simplify the primary workspace and move model/thinking controls into the composer. Recent desktop changes also make Chat/Work separation clearer while unifying recents/projects.

Raiker implication:

- Chat and Build should feel like primary modes, not two rows among many navigation destinations;
- model, execution context and approval mode belong close to the composer;
- infrastructure should recede until it affects the current turn.

## Claude

Useful pattern: keep conversation visually calm while opening substantial work in a side-by-side artifact/work surface.

Raiker implication:

- Build should lean harder into a dual-pane or three-pane workbench when code/files/diffs are active;
- generated documents, code previews and rich outputs should not have to compete with conversation width.

## Gemini

Useful pattern: stronger expressive typography, motion and visual response modules without filling the chrome with decoration.

Raiker implication:

- Raiker can feel more alive through restrained transitions, richer empty states and better output presentation while keeping control surfaces sober;
- the current palette discipline is good, but the product can use more depth through typography, scale and motion rather than more colours.

## Perplexity

Useful pattern: persistent Projects unify threads, tasks, files, instructions and tools into a work context; session history is unified instead of fragmented by execution type.

Raiker implication:

- Projects should become a stronger contextual home;
- Threads and Tasks should feel like two states of work rather than unrelated app destinations;
- sidebar hierarchy can be flatter.

## Cursor

Useful pattern: coding/agent work becomes spatial when the UI understands files, selected regions, diffs and visual context.

Raiker implication:

- Build should prioritize repository/file/diff context visually over general dashboard cards;
- future Design/Build workflows should allow selecting the object being discussed rather than making every interaction begin as free text.

---

# Findings

## VIS-01 — The sidebar exposes too many peer destinations

**Priority: P0/P1 — Impact: Very high**

**Status: Done 2026-09-06.** The rail carries eight rows, down from eleven. Approvals is a counted button in the top bar — visible from every route, which is strictly more available than a sidebar row; Design and Messaging keep their routes and are reached from the gear's window or the palette. `SIDEBAR_ITEM_IDS` separates *what the rail draws* from the route registry, so nothing became unreachable.

The Core group contains Workbench, Chat, Build, Design, Threads, Tasks, Projects, Approvals and Messaging. Knowledge adds Memory and Knowledge Map. Even though Manage/Observe/Support were moved behind the gear, the primary rail still asks the user to understand many product nouns before starting work.

### Recommendation

Promote only the most frequent destinations:

```text
New / Chat
Build
Tasks / Work
Projects
Recents
```

Treat the rest contextually:

- Approvals → persistent badge/inbox button in top bar;
- Design → composer capability or a mode under Create unless proven high-frequency;
- Messaging → Settings/Connections unless it becomes high-frequency;
- Memory / Knowledge Map → Project/Knowledge contextual areas plus advanced navigation;
- Workbench → either true Home or remove if it duplicates recent/tasks/project summaries.

The user should not need a taxonomy lesson to use Raiker.

---

## VIS-02 — Make Chat and Build unmistakable top-level modes

**Priority: P0/P1 — Impact: Very high**

**Status: Done 2026-09-06.** A segmented `Chat | Build` control in the top bar, marking the current mode, in the same place on every route.

Raiker's product story is fundamentally Assistant + Agent/Build. The shell should communicate that immediately.

### Recommendation

Use a compact global mode switch near the top-left/top-center:

```text
Chat | Build
```

Workbench, Tasks and Projects can remain navigational objects, but Chat/Build should feel like operating modes.

---

## VIS-03 — Reduce top-level chrome on work surfaces

**Priority: P1 — Impact: High**

The shell combines sidebar + top bar + page lead + tabs + cards on many operational pages. This is structurally clear but can make the interface feel layered before the user reaches the work.

### Recommendation

On Chat and Build:

- use a very quiet top bar;
- hide descriptive route hints after first use or move them to tooltips;
- avoid repeating route/page explanations;
- reserve vertical space for transcript, files and work output.

Operational screens can retain richer headers.

---

## VIS-04 — Reduce the number of visual surface archetypes

**Priority: P2 — Impact: Medium**

**Status: Partly done 2026-09-06.** The `.head-row` consolidation under VIS-23 removed one whole class of per-view divergence. The five-archetype catalogue itself is not written down yet.

The design system is mature, but cards/panels/sunken/raised/operational surfaces can make different subsystems feel visually distinct simply because they are implemented differently.

### Recommendation

Standardize around five recurring surface archetypes:

1. page background;
2. primary work surface;
3. secondary panel;
4. interactive entity card/row;
5. transient overlay.

---

## VIS-05 — Use fewer cards on information-heavy pages

**Priority: P1 — Impact: High**

Raiker's governance/status concepts naturally tend toward "card walls".

### Recommendation

Prefer:

- one page section with rows over five sibling cards;
- tables/lists for repeated entities;
- cards only for independently actionable objects;
- whitespace/dividers instead of borders around every semantic unit.

A premium interface generally has fewer visible containers.

---

## VIS-06 — Strengthen hierarchy through size and space, not uppercase

**Priority: P1 — Impact: High**

**Status: Partly done 2026-09-06.** Table headings, navigation group labels and the wordmark are sentence-cased or de-tracked; the kicker keeps its caps at reduced tracking, which is the tiny-metadata case the finding allows. Roughly sixty component-local `text-transform: uppercase` declarations remain and are the rest of this item.

The type scale is better than earlier iterations, but sidebar groups and control-plane labels still rely heavily on uppercase/tracking.

### Recommendation

- keep uppercase for tiny metadata/status only;
- use sentence case for most navigation and section labels;
- reduce letter-spacing in functional UI text;
- let larger headings and whitespace establish hierarchy;
- reserve Source Serif 4 for a few high-value moments, not normal operational screens.

---

## VIS-07 — Make the Raiker identity more distinctive through behaviour

**Priority: P2 — Impact: Medium/high**

The gold/blue/neutral palette is recognizable, but brand should not depend mainly on logo + letter-spaced RAIKER + Control Deck language.

### Recommendation

Develop two or three signature behaviours:

- the eye/lock identity in unlock and agent-active moments;
- a subtle gold authority trace around approvals/agent actions;
- a distinctive plan/progress visualization for governed work.

Brand should emerge through behaviour and composition, not ornamental chrome.

---

## VIS-08 — Make governance contextual rather than permanently visible

**Priority: P0/P1 — Impact: Very high**

**Status: Done 2026-09-06.** `PostureControl` is one chip — *Protected · Local · Ask first* — that opens the approval control and the environment badge unchanged, so nothing moved further away than one click, and the full gate matrix stays on Permissions.

Governance is Raiker's strongest differentiator, but showing every gate/state on normal work surfaces can make ordinary tasks feel bureaucratic.

### Recommendation

Use progressive disclosure.

Normal state:

```text
Protected • Local project • Ask before external actions
```

Expanded state:

```text
Model
Execution environment
Network posture
Approval policy
Data boundary
```

Only show the full matrix on Permissions/Observability.

---

## VIS-09 — Turn approval into a premium interaction

**Priority: P1 — Impact: High**

Approval is core to Raiker, so it should be one of the best-designed interactions.

### Recommendation

An approval should answer visually, in this order:

1. **What is Raiker trying to do?**
2. **Why?**
3. **What changes/leaves the machine?**
4. **What is the blast radius?**
5. **Approve / edit / deny**

Use a concise action sentence, destination chip, affected-files/data summary, risk badge and expandable technical details. Do not lead with policy/schema detail.

---

## VIS-10 — Build needs a stronger IDE/workbench composition

**Priority: P0/P1 — Impact: Very high**

Build is a defining surface. A chat-shaped page with repository controls will not visually compete with Cursor, Codex or artifact-style workflows.

### Recommendation

Desktop Build should converge on a flexible three-zone composition:

```text
Repository / files | Conversation + plan | Artifact / diff / terminal
```

Panels should collapse intelligently. When a diff, generated file, terminal or preview is active, give it more screen area than explanatory cards.

---

## VIS-11 — Chat should be visibly simpler than Build

**Priority: P1 — Impact: High**

Chat and Build can share design primitives without sharing density.

### Recommendation

Chat:

- generous conversational measure;
- simple composer;
- minimal side information;
- model/project/approval controls integrated into composer chrome;
- tool activity summarized inline and expandable.

Build:

- denser controls;
- file/diff/terminal affordances;
- persistent plan/progress;
- repository context.

---

## VIS-12 — Improve empty states

**Priority: P1 — Impact: High**

**Status: Done 2026-09-06.** The component had carried an `action` slot for a while and not one of the thirteen call sites used it. Projects, Tasks, Sessions, Checkpoints, Threads and Models now each carry one sentence and one primary action. Models also stopped naming a file Raiker no longer reads.

A complex agent platform has many zero-data screens: no projects, tasks, memories, model, approvals or connected tools.

### Recommendation

Every major empty state should contain:

- one clear sentence;
- one primary action;
- optionally 2–4 examples;
- no diagnostic jargon unless the absence is actually an error.

Examples:

**Projects** — "Keep chats, tasks and files for one goal together." → New project

**Tasks** — "Give Raiker work that can continue after you leave." → New task

**Memory** — "Raiker only remembers what is approved here." → Explain memory

---

## VIS-13 — Make Workbench a real command centre or remove it

**Priority: P1 — Impact: High**

Workbench must earn being the default route. If it mostly repeats cards linking elsewhere, it adds another layer.

### Recommendation

Show only high-signal items:

- Continue recent work
- Approvals requiring attention
- Active/background tasks
- Recent Projects
- Runtime issue only when action is required

Do not show healthy subsystem status by default.

If Workbench cannot be reduced to a genuinely useful start page, make Chat/new work the default.

---

## VIS-14 — Unify Threads, Tasks and Projects visually

**Priority: P1 — Impact: High**

These are different views of work but should feel related.

### Recommendation

Use one consistent object vocabulary:

- title;
- Project;
- state;
- last activity;
- model/runtime only when relevant;
- primary continuation action.

A Task thread should look related to a Chat thread rather than belonging to another application.

---

## VIS-15 — Use status colour more sparingly

**Priority: P1/P2 — Impact: Medium/high**

**Status: Partly done 2026-09-06.** The two controls added in this pass follow the rule — the approvals button and the posture chip are neutral at rest and colour only when something actually wants attention. The existing chips and status backgrounds across the operational pages are the rest of it.

Raiker legitimately needs success/warn/deny/read-only states, but repeated coloured chips/backgrounds/borders can make the product look like monitoring software.

### Recommendation

- colour exceptions and actions, not every normal state;
- healthy/allowed can often be neutral text + icon;
- reserve red for true denial/destructive/error states;
- use gold primarily for pending/authority/brand moments;
- use blue primarily for selection/action.

---

## VIS-16 — Reduce prominence of technical identifiers

**Priority: P2 — Impact: Medium**

Provider/model/tool/protocol identifiers should not dominate normal cards.

### Recommendation

- human label first;
- technical ID in mono secondary line or detail drawer;
- protocol/version only where troubleshooting requires it;
- shorten repetitive provider/model naming in normal conversation chrome.

---

## VIS-17 — Regroup Settings

**Priority: P2 — Impact: Medium**

Settings has many sections and reads as a flat list.

### Recommendation

Group visually:

```text
Experience
  General
  Notifications
  Personalisation

Security & data
  Security
  Privacy
  Account

Developer & runtime
  Web access
  Git credentials
  Runtime
  Updates
```

---

## VIS-18 — Give Knowledge Map a spatial visual grammar

**Priority: P2 — Impact: Medium/high**

Knowledge Map is inherently spatial and should not look like an admin page surrounding a graph.

### Recommendation

- graph/canvas as hero;
- filters/provenance in collapsible side panels;
- selection inspector instead of permanent cards;
- subtle relationship-focus animation.

---

## VIS-19 — Introduce richer inline output components

**Priority: P1 — Impact: High**

Modern assistants increasingly render structured modules rather than Markdown plus generic tool rows.

### Recommendation

Create a governed presentation vocabulary:

- key-value summary;
- comparison table;
- cited source row;
- file/artifact card;
- plan/progress block;
- approval block;
- diff block;
- terminal block;
- chart/visual block;
- generated asset preview.

These should be typed Raiker UI components, not arbitrary provider HTML.

---

## VIS-20 — Spend motion only on state changes

**Priority: P2 — Impact: Medium**

The design system already defines thoughtful motion tokens and reduced-motion behavior.

### Recommendation

Animate only meaningful transitions:

- approval arrives because work is blocked;
- plan step completes;
- task changes state;
- Build artifact panel opens;
- model/runtime state changes;
- navigation rail expands/collapses.

Avoid ambient dashboard animation.

---

## VIS-21 — Refine dark/light through depth, not more colours

**Priority: P2 — Impact: Medium**

Dark can remain flagship while light stays first-class.

### Recommendation

Dark:

- deeper neutral layering instead of many borders;
- gold used as sparse authority/action highlight;
- terminal/diff surfaces integrated into the surrounding workbench.

Light:

- reduce grey-outline accumulation;
- rely more on whitespace/subtle elevation;
- keep blue quieter than conventional enterprise dashboards.

---

## VIS-22 — Add a global command palette

**Priority: P1/P2 — Impact: High for advanced users**

**Status: Done 2026-09-06.** `Ctrl/Cmd+K` from anywhere, including from inside a text field. Finds commands, every page on the rail or off it, and each settings section by its own name. This is what allows the rail to be short.

The All Pages dialog and Threads search already provide pieces of this.

### Recommendation

`Cmd/Ctrl+K` should find:

- pages;
- threads;
- projects;
- tasks;
- settings;
- models;
- commands such as New task/Open approvals.

This allows permanent navigation to shrink without harming discoverability.

---

## VIS-23 — Standardize page-level action placement

**Priority: P2 — Impact: Medium**

**Status: Done 2026-09-06.** `.head-row` is one rule in `app.css` rather than eight byte-identical private copies, at the breakpoint all eight already used. Nothing had to disagree for the surfaces to drift — only to be edited separately.

A product with many management surfaces looks assembled if New/Add/Connect/Export/Repair actions move around unpredictably.

### Recommendation

Use one header contract:

```text
Title                           Primary action
One-line purpose                Secondary actions / overflow
```

Entity-level actions stay with entities; page-wide actions stay in the header.

---

## VIS-24 — Add a visual-quality rubric to screenshot sweeps

**Priority: P1 — Impact: High over time**

**Status: Done 2026-09-06.** The mechanisable half is `apps/web/src/lib/visualRubric.test.ts` — rail length, reachability, the header contract, empty-state actions, and stale configuration paths in copy — and each rule is one that was actually broken rather than one invented to have a test. The human half is seven questions in `VISUAL_DESIGN_SPEC.md` → "The visual rubric", to be answered out loud on any shell, composer or navigation change.

Raiker already has unusually strong responsive screenshot coverage. The catalogue documents 26 route/tab states across four display classes and both themes, plus separate width assertions.

### Recommendation

Add human-review criteria:

- no page with excessive primary cards above the fold;
- one obvious primary action per empty state;
- no more than two accent colours in normal non-status areas;
- no technical identifier at primary hierarchy unless user-selected;
- heading hierarchy visibly distinct;
- top routes reviewed at 1440/light and 1440/dark on every shell/composer redesign;
- screenshot-diff threshold plus explicit visual approval for shell/composer/nav changes.

Automated overflow/a11y tests prove the interface works. They do not prove it looks calm or intentional.

---

# Recommended visual direction

## Product personality

**Calm, capable, governed, technical when requested.**

Avoid both extremes:

- not a colourful consumer chatbot;
- not a cyber-security SIEM dashboard.

Raiker should look like a premium work tool whose safety system is deeply integrated rather than constantly announced.

## Visual hierarchy

```text
1. User's current work
2. Agent response / artifact / task state
3. Context and next action
4. Governance summary
5. Technical evidence and configuration
```

The current product sometimes visually promotes levels 4 and 5 too early.

## Shell proposal

```text
┌─────────────────────────────────────────────────────────────┐
│ Raiker    Chat | Build             [Project]  [Approvals 2] │
├──────────────┬──────────────────────────────────────────────┤
│ New          │                                              │
│ Recents      │            current work surface              │
│ Projects     │                                              │
│ Tasks        │                                              │
│              │                                              │
│ ───────────  │                                              │
│ More / ⚙     │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

## Composer proposal

```text
┌──────────────────────────────────────────────────────┐
│ Ask Raiker…                                          │
│                                                      │
│ +  Project  Model · Auto   Protected        🎙  Send │
└──────────────────────────────────────────────────────┘
```

Expanded `Protected` reveals execution/data/approval posture. Normal users get assurance; advanced users get exact controls.

## Build proposal

```text
┌──────────────┬───────────────────────┬─────────────────────┐
│ Files        │ Conversation / Plan   │ Diff / Preview      │
│              │                       │ Terminal / Artifact │
│ repo tree    │ agent progress        │                     │
└──────────────┴───────────────────────┴─────────────────────┘
```

Collapse any column when it is not useful. Do not keep empty panels merely to preserve symmetry.

---

# Implementation order

## Wave 1 — highest visual return, modest engineering effort

1. VIS-01 simplify sidebar.
2. VIS-02 create clear Chat/Build mode switch.
3. VIS-08 compact governance posture on work surfaces.
4. VIS-12 redesign empty states.
5. VIS-15 reduce routine status colour.
6. VIS-23 standardize page header/action placement.
7. VIS-22 add global command/search launcher.

## Wave 2 — work-surface redesign

1. VIS-10 Build three-zone layout.
2. VIS-11 differentiate Chat density from Build.
3. VIS-19 structured inline output components.
4. VIS-09 approval interaction redesign.
5. VIS-13 simplify Workbench.
6. VIS-14 visually unify Threads/Tasks/Projects.

## Wave 3 — polish

1. VIS-05 reduce card walls.
2. VIS-06 typography cleanup.
3. VIS-07 signature Raiker behaviours.
4. VIS-17 Settings regrouping.
5. VIS-18 Knowledge Map spatial treatment.
6. VIS-20 functional motion pass.
7. VIS-21 theme refinement.
8. VIS-24 visual-regression rubric.

---

# Design acceptance criteria

A successful redesign should make the following true:

- a first-time user can identify Chat, Build and Projects in under five seconds;
- a normal chat does not require understanding Permissions, Models, MCP, hooks or runtime terminology;
- governance is always available but normally summarized in one compact posture control;
- Build visually prioritizes files/diffs/artifacts when they exist;
- Approvals explain proposed effect before technical detail;
- the default route contains actionable work rather than healthy-system telemetry;
- repeated entities use lists/tables instead of walls of cards;
- dark and light modes share hierarchy and density;
- mobile navigation remains task-oriented, not a compressed desktop control plane;
- every advanced control remains available after the user asks for or needs it.

---

# Final judgement

Raiker does **not** need a wholesale visual rebrand. The current Control Deck system is a good foundation.

It needs an information-hierarchy redesign.

The most important change is to make the product look simpler than its architecture: Chat and Build first, current work second, governance summarized contextually, infrastructure behind progressive disclosure. That would preserve Raiker's technical seriousness while moving its perceived quality much closer to the best modern AI products.