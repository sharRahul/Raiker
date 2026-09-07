# Raiker Visual UI/UX Review — 2026-09-06

## Pass-2 implementation status — 2026-09-07

Wave 1 is complete, and the parts of Wave 2 that the composer redesign carries
are complete with it. Waves 2 (remainder) and 3 are open.

| Item | State |
|---|---|
| VIS2-01 dead type-scale step | Done — [FIXED-444](FIXED_ITEMS.md#fixed-444--a-named-type-step-that-resolved-to-its-neighbour) |
| VIS2-02 licence/runtime prose off the rail | Done — [FIXED-445](FIXED_ITEMS.md#fixed-445--two-lines-of-standing-prose-under-every-page-of-the-product) |
| VIS2-03 Chat \| Build \| Design as Work modes | Done — [FIXED-446](FIXED_ITEMS.md#fixed-446--design-was-a-work-mode-the-shell-did-not-draw) |
| VIS2-04 platform shortcut labels | Done — [FIXED-447](FIXED_ITEMS.md#fixed-447--ctrl-k-printed-to-a-keyboard-that-has-no-ctrl-there) |
| VIS2-05 model and context on compact layouts | Done for Chat, Build and Design through the composer's context line |
| VIS2-06 quieter composer primitives | Done — [FIXED-454](FIXED_ITEMS.md#fixed-454--the-composer-grew-one-permanent-button-at-a-time) |
| VIS2-07 state-aware governance wording | Done — [FIXED-448](FIXED_ITEMS.md#fixed-448--the-posture-chip-said-protected-while-its-colour-said-otherwise) |
| VIS2-08 sidebar active-state cues | Done — [FIXED-449](FIXED_ITEMS.md#fixed-449--five-ways-of-saying-which-row-you-are-on) |
| VIS2-09 unique destination icons | Done — [FIXED-446](FIXED_ITEMS.md#fixed-446--design-was-a-work-mode-the-shell-did-not-draw) |
| VIS2-10 composed secondary hubs | Partly — Models is a composed hub now; Extensions, Observability and Settings are still tab strips |
| VIS2-11 Project as persistent context | Partly — the Project is named in every Work composer's context line; a shared workspace shell is not built |
| VIS2-12 Build artifact pane | Open |
| VIS2-13 badge/chip budget | Done for the Models inventory and the composer; not swept product-wide |
| VIS2-14 theme-specific optical passes | Open |
| VIS2-15 4K/8K composition classes | Open |
| VIS2-16 neutral persistent normal state | Done — [FIXED-450](FIXED_ITEMS.md#fixed-450--success-colour-as-the-standing-state-of-everything-that-is-merely-fine) |
| VIS2-17 standardised overlay composition | Partly — `--shadow-3` is a real elevation tier and the Models modals answer to Escape ([FIXED-456](FIXED_ITEMS.md#fixed-456--three-models-modals-that-escape-could-not-close)); the full vocabulary is not defined |
| VIS2-18 attention vs information | Done on the Models Overview and the composer; not swept product-wide |
| VIS2-19 Design as a canvas workspace | Open — needs an image runtime beyond one-shot generation |
| VIS2-20 component extraction in large views | Partly — `ModelsOverview`, `MyModels`, `WorkDefaults` and `RowOverflow` came out of `ModelsView` |
| VIS2-21 shared Work-surface contract | Done for the composer; the surrounding page shells are still per-view |

---

## Review state

This document contains two visual-review passes.

- **Pass 1** reviewed Raiker at `371ccdddcf6ac1e82da4771b513dec64015f263a` and produced `VIS-01` through `VIS-24`.
- Most Pass-1 items were subsequently implemented and verified on `main` during 2026-09-06.
- **Pass 2** reviews the post-fix product at `main` commit `ac32915101de6b6562b09b1e09c4f76a24b00878` and adds `VIS2-01` onward.
- **Correction incorporated in Pass 2:** Design is a first-class **Work** surface. The product model is **Chat | Build | Design**, not Chat | Build with Design treated as a later secondary page.

The purpose of Pass 2 is not to reopen completed work. It asks a harder question:

> Now that the basic information architecture and Control Deck system are substantially improved, what still stops Raiker from feeling as visually calm, intentional and premium as the strongest current AI products?

Evidence reviewed in Pass 2:

- the current screenshot catalogue under `docs/plans/screenshots/pages/`, including mobile, 1080p, 4K and 8K light/dark sweeps;
- the latest visual-verification commit and current page/component catalogue;
- `apps/web/src/app.css` and current design tokens;
- current `Sidebar.svelte`, `Topbar.svelte`, `Composer.svelte`, `PostureControl.svelte`, `nav.ts` and representative view/component structures;
- Chat, Build and **Design** as the three primary Work surfaces;
- output/work components such as `BuildSidePanel`, `DiffView`, `FileInspector`, `CommandOutputPane`, `ImageViewport`, `LifecycleTrack`, `ToolActivity`, `SourceChips`, `EmptyState` and `CommandPalette`;
- current public product patterns from ChatGPT Projects, Perplexity Projects, Cursor 3/Design Mode and Gemini's 2026 Neural Expressive redesign.

This remains a visual/product-design review, not a request to imitate another product. Raiker's differentiated value is **governed agency**. The design goal is to make that depth understandable and reassuring without making ordinary work look like system administration.

---

# Executive assessment — Pass 2

The first review's main structural criticism was valid at the time: Raiker exposed too much architecture at once. That is no longer the dominant problem.

The post-fix interface now has several strong product-level improvements:

- a clearer Work-mode model;
- a smaller permanent navigation rail;
- Approvals moved to a counted global affordance;
- a command palette for low-frequency navigation/actions;
- compact governance posture rather than multiple permanent governance controls;
- a shared composer foundation;
- Build's file explorer and third work zone;
- fewer card walls and more neutral healthy states;
- improved approval information order;
- better empty states;
- grouped Settings;
- an already-spatial Knowledge Map;
- richer components for diffs, terminals, files, sources, plans, images and tool activity;
- strong responsive/theme screenshot coverage.

This moves Raiker from **“polished control plane containing an assistant”** toward **“assistant, coding agent and creative agent product with a governed control plane underneath.”**

## The Work model must be explicit

Raiker should treat these as peer Work modes:

```text
Chat | Build | Design
```

They share governance, model selection, context, Projects and common composer primitives, but they should not share the same spatial composition.

### Chat

Primary object: **conversation / answer**.

```text
Conversation
Composer
```

### Build

Primary object: **code / files / changes / execution**.

```text
Repository | Conversation + plan | Changes / Preview / Terminal / Runs
```

### Design

Primary object: **visual asset / canvas / selected region / variation**.

```text
Assets / history | Canvas / selected object | Inspector / variations
                         Composer / create bar
```

Design must therefore not be hidden as a low-frequency route merely because it is currently less mature than Chat or Build. If Design is part of Raiker Work, the shell, Project model, responsive rules and visual rubric must all account for it.

## The new visual problem

The remaining gap is primarily **optical and compositional rather than architectural**.

Raiker has many correct controls, surfaces and states, but some screens still communicate too many of them with similar visual weight.

The next target should be:

> **One dominant thing per screen, one obvious next action, and governance that becomes visually prominent only when it changes the user's decision.**

The design system should optimize for **quiet confidence**, not additional visible structure.

## Updated product-direction statement

> **Work should occupy the foreground. Context should sit one layer behind it. Governance should become foreground only at a decision boundary. Infrastructure should stay another layer deeper.**

That hierarchy applies equally to Chat, Build and Design.

---

# Pass-1 status summary

The old implementation-order section is superseded. These findings remain historical design decisions, not the active backlog.

| Finding | Pass-1 conclusion | Current disposition |
|---|---|---|
| VIS-01 | Simplify permanent sidebar | Done |
| VIS-02 | Make Work modes unmistakable | Partly superseded: Chat/Build done; Pass 2 expands this to Chat/Build/Design |
| VIS-03 | Reduce work-surface chrome | Done |
| VIS-04 | Standardize surface archetypes | Done |
| VIS-05 | Reduce card walls | Done |
| VIS-06 | Reduce uppercase/tracking dependence | Done |
| VIS-07 | Distinctive Raiker identity through behaviour | Owner/product-design decision |
| VIS-08 | Contextual governance posture | Done |
| VIS-09 | Premium approval hierarchy | Done |
| VIS-10 | Stronger Build workbench | Core layout done; artifact pane remains |
| VIS-11 | Chat visually simpler than Build | Done; Pass 2 extends density contracts to Design |
| VIS-12 | Better empty states | Done |
| VIS-13 | Make Home useful or remove it | Done |
| VIS-14 | Unify Threads/Tasks/Projects vocabulary | Done at component level; project continuity remains |
| VIS-15 | Reduce status colour | Done |
| VIS-16 | De-emphasize technical IDs | Done |
| VIS-17 | Regroup Settings | Done |
| VIS-18 | Spatial Knowledge Map | Already satisfied |
| VIS-19 | Rich typed output vocabulary | Most components exist; typed channel/chart incomplete |
| VIS-20 | Motion only for meaningful state change | Done |
| VIS-21 | Theme-specific depth | Done |
| VIS-22 | Command palette | Done |
| VIS-23 | Clear page-level actions | Done |
| VIS-24 | Visual-quality rubric | Done |

---

# Competitive reference update — September 2026

## ChatGPT — persistent work context

Projects show the benefit of keeping chats, files, instructions, context and tools around one goal.

Raiker implication:

- Project should become the persistent context across **Chat, Build and Design**;
- switching Work modes should not force users to reconstruct context;
- a Design asset created inside a Project should remain part of the same project history as the thread/task/build work that produced or uses it.

## Perplexity — unified work history

Threads and tasks can remain different object types while still looking like work sessions inside one project.

Raiker implication:

- global aggregate views remain useful;
- project-scoped work should feel like one coherent workspace rather than linked mini-apps.

## Cursor / Design Mode — agent-first spatial work

The visual lesson is that an agent product becomes much stronger when the object being changed is visible and selectable.

Raiker implication:

- Build should focus files/diffs/terminal objects;
- Design should focus canvas/assets/selections/variations;
- conversation is an instruction channel, not always the largest object on screen.

## Gemini Neural Expressive — richer response composition

Raiker should continue toward typed rich output without arbitrary provider HTML.

That applies to Design too: generated media, versions, comparisons and metadata should be Raiker-owned presentation types with deterministic rendering and governed actions.

---

# Pass-2 findings

## VIS2-01 — Repair the dead type-scale step and strengthen optical hierarchy

**Priority: P1 — Effort: Low — Visual impact: High**

`--text-lg` currently resolves to the same size as `--text-base`. Make each named type token visually meaningful. Spend display sizing selectively on Home, Project identity and major artifact/canvas moments rather than operational pages.

---

## VIS2-02 — Remove developer/project metadata from permanent sidebar chrome

**Priority: P1 — Effort: Low — Visual impact: High**

Move Apache licence/build information into Settings/About. Runtime locality belongs in a compact status/posture surface, not permanent prose at the bottom of navigation.

---

## VIS2-03 — Make Work mode explicit as Chat | Build | Design and reduce top-bar saturation

**Priority: P0/P1 — Effort: Medium — Visual impact: Very high**

### Observation

The implemented top bar treats Chat and Build as the global mode pair. Design remains reachable, but visually that says it is a destination rather than a peer Work mode.

That is the wrong product hierarchy if Raiker Work includes visual creation/editing.

The top bar also accommodates search, approvals, notifications, settings, host control and stop, so adding Design cannot simply mean adding another unrelated button.

### Recommendation

Use one compact Work-mode control:

```text
Chat | Build | Design
```

or, if width becomes constrained:

```text
Work: Chat ▾
```

where the selector contains Chat, Build and Design with strong keyboard shortcuts/command-palette access.

Then create explicit clusters:

```text
[ Work mode ]      [ Search ]      [ Attention ] [ Settings ]   |   [ Runtime safety ]
Chat Build Design                  Approvals
                                   Activity
```

Rules:

- Work mode is the dominant neutral control;
- Attention gains colour/count only when action is required;
- runtime safety is visually separated from navigation;
- emergency stop remains immediately available where required;
- Design is never hidden in Settings/All Pages as its primary discovery path.

### Acceptance

- a new user can identify Chat, Build and Design as the three ways to work with Raiker without opening secondary navigation;
- switching modes preserves Project/work context where applicable;
- mobile collapses the three-mode control intelligently rather than removing Design.

---

## VIS2-04 — Render platform-appropriate shortcut labels

**Priority: P1 — Effort: Low — Polish impact: High**

Render `⌘K` on macOS and `Ctrl K` on Windows/Linux using one shared shortcut-label component.

---

## VIS2-05 — Keep model and context recognisable on compact layouts

**Priority: P1 — Effort: Medium — Visual impact: High**

A provider logo alone does not identify a selected model. Context/scope must remain inspectable in one tap on narrow screens rather than disappearing.

This applies to **all three Work modes**. In Design, compact context should additionally expose the selected asset/version/selection state when relevant.

---

## VIS2-06 — Make shared composer primitives quieter, with mode-specific composition

**Priority: P1 — Effort: Medium — Visual impact: Very high**

Keep common composer behaviour/tokens, but do not force identical composer composition across Work modes.

### Chat composer

- largest emphasis on text input;
- minimum controls;
- model/context/posture integrated quietly.

### Build composer

- supports repository, mode, execution and agent controls;
- can tolerate more density.

### Design create bar

- should be visually attached to the canvas;
- size/aspect/count/model/style controls belong in a compact create/edit bar;
- selection/crop/version context should be close to the canvas, not represented as generic chat chips.

Reduce full-width separator lines and toolbar stacking across all variants.

---

## VIS2-07 — Make governance wording state-aware

**Priority: P1 — Effort: Low — Visual impact: Medium/high**

Avoid reassuring copy such as `Protected · Local · Auto-approve` where the colour simultaneously signals a relaxed posture. Use factual state-aware wording without implying that other protections disappeared.

---

## VIS2-08 — Simplify sidebar active-state language

**Priority: P1 — Effort: Low — Visual impact: Medium/high**

Keep no more than two active-state cues. Avoid simultaneous group bar, row background, accent text, heavier weight and `Current` text.

---

## VIS2-09 — Give permanent destinations unique icon identities

**Priority: P1 — Effort: Low/Medium — Visual impact: High**

Permanent rail destinations should remain recognisable with labels hidden. Reserve Raiker's spark/eye identity for agent/AI action rather than generic navigation.

Because Design is a Work mode, give it an unmistakable visual-creation identity (canvas/image/pen/shape) distinct from Chat and Build.

---

## VIS2-10 — Make Models, Extensions, Observability and Settings composed hubs

**Priority: P1 — Effort: Medium — Visual impact: High**

Move beyond long equal-weight tab strips. Lead with the user's current state/next action and place lower-level sections behind grouped navigation.

---

## VIS2-11 — Make Project the persistent context across Chat, Build and Design

**Priority: P1 — Effort: Medium/High — Visual impact: Very high**

Inside a Project, treat work as one coherent workspace:

```text
Project name / goal / posture

Overview
Chat / Threads
Build work
Design assets
Tasks
Files
Memory / context
Instructions
Activity
```

This does **not** mean duplicating the main sidebar. It means that Project context persists while the user switches Work mode.

### Design-specific Project behaviour

- generated images/assets belong to the Project automatically when created there;
- visual versions/iterations are project artifacts, not isolated chat attachments;
- a Build task can reference a Design asset and vice versa;
- Project Activity should show creation/edit/export actions consistently with other governed actions.

---

## VIS2-12 — Complete Build's contextual artifact pane

**Priority: P1 — Effort: Medium — Visual impact: Very high**

Use the existing primitives to make the third pane the object of work:

```text
Changes | Preview | Terminal | Runs
```

Auto-focus the pane on the object currently being reviewed, and collapse it when no object warrants the space.

---

## VIS2-13 — Establish a badge/chip budget

**Priority: P2 — Effort: Low/Medium — Visual impact: High**

Use one primary status token per repeated entity and at most one additional contextual token. Healthy/default facts should usually be plain metadata.

This is particularly important in Design, where model, aspect ratio, dimensions, count, version, status and selection can otherwise become a row of chips.

---

## VIS2-14 — Add theme-specific optical passes

**Priority: P2 — Effort: Medium — Visual impact: Medium/high**

Do not redesign the palette. Tune light/dark composition separately through luminance, whitespace and border restraint.

For Design specifically, ensure the canvas boundary remains obvious in both themes without surrounding the asset with excessive card chrome.

---

## VIS2-15 — Treat 4K/8K as composition classes

**Priority: P2 — Effort: Medium — Visual impact: Medium**

Keep prose measure fixed, but let spatial surfaces exploit large displays.

High-resolution priority order:

1. Design canvas/variations;
2. Build multi-pane workbench;
3. Knowledge Map;
4. Observability operational layouts.

Do not scale controls merely because the monitor is larger.

---

## VIS2-16 — Persistent normal state is neutral

**Priority: P2 — Effort: Low — Visual impact: Medium**

Success colour should be temporal or confirmatory rather than the default representation of ready/connected/implemented/allowed.

---

## VIS2-17 — Standardise overlay/popover composition

**Priority: P2 — Effort: Medium — Visual impact: Medium/high**

Define consistent visual roles for popovers, pickers, inspectors, decision dialogs and command palette surfaces.

Design additionally needs a consistent treatment for:

- asset picker;
- variation picker;
- crop/selection inspector;
- export dialog;
- full-screen/lightbox preview.

---

## VIS2-18 — Separate attention from information

**Priority: P1 — Effort: Medium — Visual impact: High**

Use one hierarchy everywhere:

```text
Needs action     explicit action / count / exception tone
Worth knowing    neutral summary
Evidence/detail  collapsed or lower weight
```

In Design, generation failures, blocked exports or approval-required external actions are attention; dimensions/model/version metadata are information.

---

## VIS2-19 — Design must be a first-class canvas workspace, not a third chat variant

**Priority: P0/P1 — Effort: Medium/High — Visual impact: Very high**

### Problem

A simple prompt → image → prompt loop would technically work, but it would visually underuse Raiker and make Design feel like Chat with image output.

Design should be a peer to Build: both are object-centric Work modes.

- Build's object is code/files/diffs/processes.
- Design's object is an image/canvas/selection/version/asset.

### Desktop target composition

```text
┌───────────────┬──────────────────────────────────────┬────────────────────┐
│ Assets        │ Canvas / active asset                │ Inspector           │
│ Variations    │                                      │                    │
│ History       │      selected region/object          │ Properties          │
│               │                                      │ Versions            │
│               │                                      │ Export / details     │
├───────────────┴──────────────────────────────────────┴────────────────────┤
│ Create / edit composer: prompt · model · aspect · size · selection · Run │
└───────────────────────────────────────────────────────────────────────────┘
```

The exact pane count can adapt, but the **canvas must dominate** whenever an asset exists.

### Empty Design state

Do not show an admin/configuration page.

Show:

- one strong creation prompt;
- useful starting examples/presets;
- recent Project assets if available;
- import/upload as a peer starting action;
- model/setup guidance only if required to proceed.

### Asset state

When an asset exists:

- canvas becomes the hero;
- prompt history becomes secondary;
- generation metadata moves to inspector/detail;
- controls attach to the object they affect.

### Selection-aware editing

Long-term interaction model:

1. select/draw/crop/point at part of the image;
2. Raiker records the spatial selection as structured context;
3. user asks for an edit;
4. the new version appears beside/over the previous version;
5. diff/compare/version history remains reversible and auditable.

### Variations and compare

Support a visual comparison grammar instead of a list of outputs:

- 2-up / 4-up variation grid;
- before/after slider where appropriate;
- version strip;
- pin/favourite candidate;
- compare metadata only on demand.

### Governance in Design

Governance should remain contextual:

- local generation/editing does not need permanent warning chrome;
- uploading an external source, sending an asset to a hosted model, exporting externally or invoking a plugin can surface the relevant data/authority boundary at the moment it matters;
- provenance, model, source asset and transformation history should be inspectable without occupying the canvas permanently.

### Mobile/tablet Design

Do not squeeze three desktop panes onto a small screen.

Use:

```text
Canvas
Create/edit bar
Bottom sheet: Assets | Variations | Inspector
```

Canvas remains the primary object.

### Accessibility

Design must not become mouse-only:

- keyboard focus for asset/version selection;
- textual description of active selection/crop where possible;
- accessible labels for canvas tools;
- non-colour-only version/selection states;
- zoom controls with keyboard equivalents.

### Acceptance

- Design is visible as a first-class Work mode alongside Chat and Build;
- with an asset open, the canvas is the largest intentional region;
- a user can understand which asset/version/selection the next instruction affects;
- Design assets persist naturally inside Projects;
- metadata and governance remain inspectable but do not compete with the canvas;
- responsive layouts preserve the object of work rather than collapsing back into generic chat.

---

## VIS2-20 — Use the component system to prevent visual drift in largest views

**Priority: P2 — Effort: Medium — Visual impact: Medium/high**

Extract visual regions when touching large views. In addition to Build/Approvals/Knowledge Map, Design should converge on explicit regions such as:

```text
DesignWorkspaceShell
DesignAssetRail
DesignCanvasRegion
DesignInspector
DesignCreateBar
DesignVariationGrid
```

This is a visual consistency measure, not a LOC target.

---

## VIS2-21 — Define a shared Work-surface contract without making the three modes identical

**Priority: P1 — Effort: Medium — Visual impact: Very high**

### Why this is needed

Once Design is correctly promoted, Raiker needs a common Work contract so Chat, Build and Design feel like one product without becoming one layout.

### Shared Work contract

Every Work mode should share:

- Project/context identity;
- selected model identity;
- governance posture;
- attachment/import entry points appropriate to the mode;
- run/stop/steer semantics where applicable;
- consistent command-palette discoverability;
- common loading/error/approval visual language;
- keyboard and responsive principles.

Every Work mode should differ in its **primary object**:

| Mode | Primary object | Secondary context | Normal density |
|---|---|---|---|
| Chat | conversation/answer | sources, files, memory | low |
| Build | code/file/diff/process | repo, plan, terminal | high |
| Design | canvas/asset/selection/version | variations, properties, history | medium/spatial |

### Rule

> **Shared controls should look related; primary workspaces should look purpose-built.**

Do not solve consistency by putting every feature in the same composer row or by turning Design and Build back into Chat-shaped screens.

---

# Page-by-page Pass-2 observations

## Home

- make **Continue work** the strongest normal-state region;
- make **Needs attention** dominant only when non-empty;
- recent work should identify whether it resumes in Chat, Build or Design without creating three unrelated card styles;
- allow recent Design assets/projects to appear naturally beside other work.

## Chat

- lowest chrome and lowest control density of the three Work modes;
- preserve model/context identity on compact widths;
- keep ToolActivity collapsed unless expanded;
- ordinary assistant prose should not be boxed unnecessarily;
- rich typed blocks only when structure materially helps.

## Build

- complete `Changes | Preview | Terminal | Runs` artifact pane;
- let selected file/diff become visual focus;
- keep conversation readable while using three panes;
- show plan/progress near the work object;
- remember pane state per Project.

## Design

Design is not an auxiliary creation page. It is the visual Work mode.

### Hierarchy

1. **Canvas / current asset**
2. **Current selection or version**
3. **Create/edit instruction**
4. **Variations / history / assets**
5. **Technical generation metadata**

### What should dominate

- with no asset: creation prompt + recent/import starting points;
- with an asset: canvas;
- while comparing: variation grid/compare surface;
- during a consequential external action: approval/governance decision.

### What should not dominate

- provider/model IDs;
- dimensions as multiple badges;
- generation job internals;
- explanatory onboarding copy after the first successful creation;
- generic card walls.

### Recommended controls

Compact create/edit bar:

```text
[Attach/Import] [Model] [Aspect] [Size] [Selection]     Prompt...     [Generate/Edit]
```

On narrower widths, collapse low-frequency settings into one `Options` control rather than adding rows.

### Asset rail

Prefer thumbnails and visual grouping over filenames/IDs. Show:

- current asset;
- variations;
- prior versions;
- imported references;
- generated outputs.

Use text/metadata on hover/focus/selection or inspector.

### Inspector

Inspector should hold:

- dimensions/aspect;
- model/provider;
- source/provenance;
- version lineage;
- export details;
- governance/data-boundary facts when relevant.

It should be collapsible and must not permanently steal canvas width on smaller screens.

### Project continuity

A Design session inside a Project should inherit that Project's files/context/instructions where permitted. Assets created there should remain available to Chat and Build in the same Project without manual reattachment.

### Visual identity

Design may be slightly more expressive than Build, but it should still use Control Deck tokens. Do not introduce a separate neon/gradient creative-app aesthetic.

## Threads

- list-first presentation;
- quiet date/group separators;
- identify Chat/Build/Design origin/state with one small semantic cue where useful;
- Project identity should not become coloured-chip noise.

## Tasks

- dense list rows over cards;
- state, next run and Project form the scan line;
- logs/evidence open in inspector;
- tasks that produce Design assets should link directly to the resulting asset/canvas state.

## Projects

Projects should become more visually important over time.

- clear Project identity and goal;
- Chat, Build, Design, Tasks, Files and context belong to the same Project;
- global views remain aggregates;
- no duplicated full sidebar inside Project.

## Memory

Orient normal users around **what Raiker remembers and why**. Keep embedding/vector/backend detail in advanced diagnostics.

## Knowledge Map

Canvas-first direction is already strong. Improve focus, progressive labels and selection fading rather than adding surrounding cards.

## Approvals

Keep decision object first, provenance/evidence collapsed, and give diffs/assets/destinations more area than policy metadata. Design-related approvals should preview the actual asset/target when possible.

## Permissions

Search/filter prominence should grow with the list. Default healthy states remain neutral. Explain capabilities in plain language before schemas.

## Models

Lead with the model currently answering/creating and ready alternatives. Provider management remains secondary. Design should be able to indicate which models support image generation/editing without turning Models into a badge matrix.

## Extensions

Separate Installed/Connected from Available. Permission/data-boundary consequences appear prominently during connection/first use, not repeated on every card.

## Observability

Exceptions-first. Active/failing work before healthy telemetry. Include Design generation/edit/export events in the same evidence language as Chat/Build rather than creating a separate monitoring sub-product.

## Settings

Keep three-group structure. Move licence/about/build metadata here. Do not make each preference a card.

---

# Updated visual-system rules

## Rule A — One dominant visual task per viewport

At normal desktop width, one region should read first. Split workspaces are deliberate exceptions.

## Rule B — Two active-state cues maximum

Do not combine background, edge, colour, bold and label for one selection.

## Rule C — One primary status token per repeated entity

Additional state becomes metadata/detail.

## Rule D — Persistent normal state is neutral

Success colour is temporal or confirmatory.

## Rule E — Compact does not mean contextless

Important turn/asset/project identity remains inspectable in one tap.

## Rule F — Governance foregrounds only at a decision boundary

At rest, posture is summary. At approval/risk transition, governance may become dominant.

## Rule G — The object of work wins the screen

- Chat: answer/conversation wins.
- Build: file/diff/preview/terminal wins when active.
- Design: canvas/asset/selection wins when active.

## Rule H — Legal/build metadata belongs in About/Settings

Persistent workspace chrome contains work, navigation and actionable state only.

## Rule I — Work modes are peers, not routes of unequal legitimacy

Chat, Build and Design share the Work-level shell contract. Maturity differences may affect feature depth, not discoverability or product hierarchy.

## Rule J — Shared controls, purpose-built workspaces

Use shared primitives for model/context/governance/run states, but preserve mode-specific spatial composition.

---

# Updated implementation order

Priority first, then effort.

## Wave 1 — Correct the Work model and small polish

1. **VIS2-03** — promote Design into the global Work-mode model and reorganise top-bar clusters.
2. **VIS2-02** — remove licence/runtime prose from permanent sidebar footer.
3. **VIS2-04** — platform-aware shortcut labels.
4. **VIS2-08** — simplify sidebar active-state cues.
5. **VIS2-09** — unique Work/permanent-nav icon identities including Design.
6. **VIS2-01** — repair type-scale dead step.
7. **VIS2-07** — state-aware posture wording.
8. **VIS2-16** — codify normal-state neutrality.

## Wave 2 — Everyday Work-surface refinement

9. **VIS2-21** — shared Work-surface contract for Chat/Build/Design.
10. **VIS2-05** — compact model/context/asset recognisability.
11. **VIS2-06** — quieter, mode-aware composer/create-bar composition.
12. **VIS2-13** — badge/chip budget.
13. **VIS2-18** — action vs information hierarchy.
14. **VIS2-17** — standard overlay vocabulary.

## Wave 3 — Object-centric workspaces

15. **VIS2-19** — first-class canvas Design workspace.
16. **VIS2-12** — complete Build artifact pane.
17. **VIS2-11** — persistent Project continuity across Chat/Build/Design.
18. **VIS2-10** — compose secondary hubs beyond flat tab strips.
19. **VIS2-14** — theme-specific optical pass.
20. **VIS2-15** — high-resolution compositional refinement.
21. **VIS2-20** — extract large-view visual regions opportunistically.

---

# What should not change

Pass 2 does not recommend replacing the Control Deck identity.

Keep:

- restrained gold/steel/neutral palette;
- Manrope as main UI face;
- JetBrains Mono for technical evidence;
- Source Serif 4 only for selective high-value display/editorial moments;
- dual first-class light/dark themes;
- bounded reading widths;
- density controls;
- reduced-motion behaviour;
- semantic warning/error states;
- explicit approval/governance model;
- strong responsive screenshot/rubric discipline;
- typed, governed presentation components rather than arbitrary provider HTML.

Do not chase “premium” with gradients, glass, neon status colours, unnecessary animation or decorative dashboards.

Design can be more spatial and visual without becoming stylistically disconnected from Raiker.

---

# Final Pass-2 judgment

The hierarchy redesign has largely happened, but the Work hierarchy needed one correction: **Design belongs beside Chat and Build.**

The correct product shape is:

```text
Raiker Work
├── Chat      understand, reason, decide, communicate
├── Build     plan, code, change, execute, verify
└── Design    create, inspect, select, iterate, compare

Shared beneath all three
├── Projects and context
├── models
├── governance / approvals
├── memory
├── tools / extensions
├── audit / observability
└── host/runtime safety
```

The remaining visual refinement is therefore not only “make Build better.” It is to make **each Work mode feel purpose-built while unmistakably belonging to the same governed product**.

The desired end state:

> **Raiker should look simpler than the architecture underneath it, calmer than the authority it controls, and more focused as the work becomes more complex.**

For Design specifically:

> **The canvas is the work; conversation is the instruction channel; governance appears when the action crosses a boundary.**

That puts Design where it belongs: a first-class part of Raiker Work, not an accessory page.