# Raiker Visual UI/UX Review — 2026-09-06

## Review state

This document now contains **two visual-review passes**.

- **Pass 1** reviewed Raiker at `371ccdddcf6ac1e82da4771b513dec64015f263a` and produced `VIS-01` through `VIS-24`.
- Most Pass-1 items were subsequently implemented and verified on `main` during 2026-09-06.
- **Pass 2** reviews the **post-fix product** at `main` commit `ac32915101de6b6562b09b1e09c4f76a24b00878` and adds a new set of recommendations, `VIS2-01` onward.

The purpose of Pass 2 is not to reopen completed work. It asks a harder question:

> Now that the basic information architecture and Control Deck system are substantially improved, what still stops Raiker from feeling as visually calm, intentional and premium as the strongest current AI products?

Evidence reviewed in Pass 2:

- the current screenshot catalogue under `docs/plans/screenshots/pages/`, including the 390 px mobile, 1080p, 4K and 8K light/dark sweeps;
- the latest visual-verification commit and current page/component catalogue;
- `apps/web/src/app.css` and current design tokens;
- current `Sidebar.svelte`, `Topbar.svelte`, `Composer.svelte`, `PostureControl.svelte`, `nav.ts` and representative view/component structures;
- the implemented output/work components such as `BuildSidePanel`, `DiffView`, `FileInspector`, `CommandOutputPane`, `ImageViewport`, `LifecycleTrack`, `ToolActivity`, `SourceChips`, `EmptyState`, `CommandPalette` and related controls;
- current public product patterns from ChatGPT Projects, Perplexity Projects, Cursor 3/Design Mode and Gemini's 2026 Neural Expressive redesign.

This remains a visual/product-design review, not a request to imitate another product. Raiker's differentiated value is **governed agency**. The design goal is to make that depth feel understandable and reassuring without making ordinary work look like system administration.

---

# Executive assessment — Pass 2

## What improved materially

The first review's main structural criticism was valid at the time: Raiker exposed too much architecture at once. That is **no longer the dominant problem**.

The post-fix interface now has several strong product-level improvements:

- a visible global **Chat | Build** mode distinction;
- a smaller permanent navigation rail;
- Approvals moved to a counted global affordance instead of a permanent navigation row;
- a command palette for low-frequency navigation and actions;
- a compact governance posture control instead of multiple permanent governance controls;
- a shared Chat/Build composer frame;
- Build's file explorer and third work zone;
- fewer card walls and more neutral healthy states;
- improved approval information order;
- better empty states;
- grouped Settings;
- an already-spatial Knowledge Map;
- a richer component vocabulary for diffs, terminals, files, sources, plans, images and tool activity;
- explicit visual-quality and responsive regression coverage.

This moves Raiker from **“polished control plane containing an assistant”** toward **“assistant/agent product with a governed control plane underneath.”**

## The new visual problem

The remaining gap is now **optical and compositional rather than architectural**.

Raiker has many correct controls, correct surfaces and correct states, but some screens can still communicate *all of them with similar visual weight*. The result risks being technically clean but visually busy.

The next target should be:

> **One dominant thing per screen, one obvious next action, and governance that becomes visually prominent only when it changes the user's decision.**

The design system should now optimize for **quiet confidence**, not additional visible structure.

## Updated product-direction statement

The first pass said:

> Conversation-first and work-first in normal use; Control Deck precision only when the user enters governance, diagnostics or advanced configuration.

That remains correct, but Pass 2 sharpens it:

> **Work should occupy the foreground. Context should sit one layer behind it. Governance should become foreground only at a decision boundary. Infrastructure should stay another layer deeper.**

That four-level hierarchy should govern every new screen and component.

---

# Pass-1 status summary

The old implementation-order section is superseded. These findings are retained as historical design decisions, not as an active backlog.

| Finding | Pass-1 conclusion | Current disposition |
|---|---|---|
| VIS-01 | Simplify permanent sidebar | Done |
| VIS-02 | Make Chat/Build top-level modes | Done |
| VIS-03 | Reduce work-surface chrome | Done |
| VIS-04 | Standardize surface archetypes | Done |
| VIS-05 | Reduce card walls | Done |
| VIS-06 | Reduce uppercase/tracking dependence | Done |
| VIS-07 | Distinctive Raiker identity through behaviour | Owner/product-design decision; still optional |
| VIS-08 | Contextual governance posture | Done |
| VIS-09 | Premium approval hierarchy | Done |
| VIS-10 | Stronger Build workbench | Core layout done; artifact half remains a Pass-2 opportunity |
| VIS-11 | Chat visually simpler than Build | Done |
| VIS-12 | Better empty states | Done |
| VIS-13 | Make Home useful or remove it | Done |
| VIS-14 | Unify Threads/Tasks/Projects vocabulary | Done at component-vocabulary level; deeper project continuity remains a Pass-2 opportunity |
| VIS-15 | Reduce status colour | Done |
| VIS-16 | De-emphasize technical IDs | Done |
| VIS-17 | Regroup Settings | Done |
| VIS-18 | Spatial Knowledge Map | Already satisfied |
| VIS-19 | Rich typed output vocabulary | Most presentation components exist; typed output channel/chart remain incomplete |
| VIS-20 | Motion only for meaningful state change | Done |
| VIS-21 | Theme-specific depth | Done |
| VIS-22 | Command palette | Done |
| VIS-23 | Clear page-level actions | Done |
| VIS-24 | Visual-quality rubric | Done |

---

# Competitive reference update — September 2026

The point of these references is not visual copying. They show where product interfaces are converging.

## ChatGPT — persistent work context

Current ChatGPT Projects keep chats, files, instructions, memory/context and tools around one ongoing body of work. The visual lesson is that **project context can reduce navigation**, because the user does not need separate top-level places for every artifact type.

Raiker implication:

- continue making Project the place where threads, tasks, files and instructions visibly belong together;
- retain global aggregate views, but make project-scoped work feel like one coherent workspace rather than several linked apps.

## Perplexity — Projects and unified work history

Perplexity's current Projects combine search conversations, Computer tasks, files, instructions, connected tools and persistent context. Its desktop history also presents Ask threads and Computer tasks together rather than forcing users to understand execution taxonomy first.

Raiker implication:

- Threads and Tasks can remain different object types, but the visual shell should increasingly present them as **work sessions inside a project**;
- distinguish by state and affordance, not by entirely different page languages.

## Cursor 3 / Design Mode — agent-first spatial work

Cursor's 2026 Agents Window intentionally centers agent work while preserving IDE depth, and Design Mode lets users select/draw on the actual UI so the agent receives spatial context.

Raiker implication:

- Build's third pane should become a first-class artifact/preview/diff surface rather than mainly a terminal/background-work area;
- Design should eventually become canvas-first and selection-aware rather than only prompt-first;
- agent work benefits from a visible object of focus.

## Gemini Neural Expressive — response composition

Gemini's 2026 redesign explicitly moves away from long text-only answers toward dynamically composed imagery, timelines and interactive response modules.

Raiker implication:

- finish the typed presentation channel already anticipated by VIS-19;
- Raiker should use richer response composition **without arbitrary provider HTML**;
- rich output should still look like Raiker and remain governed, inspectable and deterministic.

---

# Pass-2 findings

## VIS2-01 — Repair the dead type-scale step and strengthen optical hierarchy

**Priority: P1 — Effort: Low — Visual impact: High**

### Observation

The current type tokens define:

```css
--text-base: 1rem;
--text-lg:   1rem;
--text-xl:   1.22rem;
--text-2xl:  1.49rem;
--text-display: 1.82rem;
```

`--text-lg` is therefore not a scale step at all. A semantic token that produces no visual change encourages components to reach for weight, caps, colour or local pixel values instead.

Raiker's hierarchy has improved, but the overall interface still tends toward similar-sized text with different weights.

### Recommendation

Make every named type step visually meaningful. A restrained scale is still appropriate, for example:

```text
base      1.00rem
large     1.10–1.125rem
xl        1.25rem
2xl       1.50rem
display   2.00–2.20rem
```

Do **not** make operational pages oversized. Spend the larger display size only on:

- Home/first-run moments;
- empty-state hero moments;
- Project identity;
- major artifact title/preview moments.

### Acceptance

- no two adjacent semantic type tokens resolve to the same size;
- normal operational pages remain compact;
- hierarchy can be read in greyscale without relying on bold alone.

---

## VIS2-02 — Remove developer/project metadata from the permanent sidebar footer

**Priority: P1 — Effort: Low — Visual impact: High**

### Observation

The permanent sidebar footer still renders:

- `Local & loopback-only`
- `Apache License, Version 2.0`

The first is a real runtime/data-boundary fact, but it is already represented more contextually through governance posture. The second is project/legal metadata, not something a normal user needs during every interaction.

This small footer disproportionately makes Raiker feel like an open-source admin console rather than a finished product.

### Recommendation

- move Apache licence information to **Settings → About/Updates** or an About dialog;
- remove the permanent runtime sentence or replace it with one small host/workspace status affordance that opens detail;
- allow the bottom of the sidebar to breathe.

### Acceptance

The persistent navigation contains only navigation, current work/account context and genuinely actionable state.

---

## VIS2-03 — Reduce top-bar control saturation and create explicit control clusters

**Priority: P1 — Effort: Low/Medium — Visual impact: Very high**

### Observation

The top bar currently needs to accommodate, depending on width/state:

- Chat | Build switch;
- command/search;
- approvals counter;
- notifications counter;
- all-pages/settings entry;
- host control;
- stop switch.

Every control is individually defensible. Together they can turn the quiet top bar back into a compact control plane.

### Recommendation

Create three visual clusters:

```text
[ Work mode ]      [ Search ]      [ Attention ] [ Settings ]   |   [ Runtime safety ]
Chat | Build                        Approvals
                                     Activity
```

Rules:

- **Search/navigation cluster** is neutral.
- **Attention cluster** only gains colour/count when something needs action.
- **Runtime safety cluster** is visibly separate from ordinary navigation.
- Emergency stop remains immediately available where safety requires it, but should not use high-alert styling while there is nothing active to stop.

Consider whether passive Notifications belong inside an **Attention** popover with Approvals while keeping Approvals individually reachable when pending.

### Acceptance

At rest, the top bar has one dominant mode control and no more than one visually loud status.

---

## VIS2-04 — Render platform-appropriate shortcut labels

**Priority: P1 — Effort: Low — Visual impact: Low/medium, polish impact: High**

### Observation

The command control currently presents `Ctrl K` in the desktop chrome even though the implementation comments and command model support Ctrl/Cmd concepts.

On macOS, a hard-coded Windows shortcut is an immediate premium-polish miss.

### Recommendation

Render platform-aware notation:

- macOS: `⌘K`
- Windows/Linux: `Ctrl K`

Use the same shortcut-label component everywhere, including the shortcut sheet.

---

## VIS2-05 — Keep model and context recognisable on compact layouts

**Priority: P1 — Effort: Medium — Visual impact: High**

### Observation

Below the desktop breakpoint the shared Composer intentionally removes labels to protect space. However:

- the selected model becomes primarily a **provider logo**;
- scope/context controls can disappear entirely;
- approval/model controls become similar circular icon buttons.

A provider logo does not identify a model when several models come from the same provider. Hiding context completely also weakens the user's ability to answer “what is this turn using?” precisely when screen space is limited.

### Recommendation

Use a **compact context affordance**, not silent removal.

Possible mobile/tablet composer:

```text
[ + ] [ Model short-name ] [ Context 3 ] [ Protected ]                [ Send ]
```

or, at the narrowest width:

```text
[ + ] [ Model glyph ] [ Context ring ] [ Shield ]                     [ Send ]
```

Requirements:

- model identity must distinguish two models from the same provider;
- context/scope must remain inspectable in one tap;
- the compact shape must still explain itself through tooltip/accessible label;
- do not add another permanent row.

---

## VIS2-06 — Make the composer feel less like a bordered form with toolbars

**Priority: P1 — Effort: Medium — Visual impact: Very high**

### Observation

The shared Composer is a major improvement, but its composition still uses:

- an outer bordered card;
- shadow/elevation on focus;
- a full-width top border before each composer bar;
- potentially a separate running-turn bar and the normal control bar.

This is structurally clear, but the composer can read as a form panel with toolbar rows rather than the natural “floor” of the conversation.

### Recommendation

Reduce visible framing:

- keep one soft outer shell;
- use tonal separation or spacing for the utility row instead of a full-width rule in the normal state;
- when a live-turn steering row exists, give **that** row the separator/emphasis;
- prefer grouped icon/text affordances over many independently outlined controls;
- preserve strong focus visibility through a subtle focus ring/edge, not necessarily more shadow.

### Acceptance

At a glance, the prompt area is the largest visual region of the composer and controls feel attached to it rather than stacked underneath it.

---

## VIS2-07 — Make governance wording state-aware, not only governance colour

**Priority: P1 — Effort: Low — Visual impact: Medium/high**

### Observation

`PostureControl` correctly changes to warning colour for relaxed modes, but its summary always begins with `Protected`:

```text
Protected · Local · Auto-approve
Protected · Local · Skip prompts
```

The colour says “pay attention,” while the first word says the same reassuring thing as the stricter mode.

### Recommendation

Use state-aware lead copy while remaining factual, for example:

```text
Protected · Local · Ask first
Protected · Local · Decline unattended
Auto approval · Local
Reduced prompts · Local
```

or another wording that accurately reflects the runtime semantics.

Do not imply “unsafe” if other controls remain enforced. The goal is simply to prevent reassurance copy from visually cancelling the warning state.

---

## VIS2-08 — Simplify the sidebar's active-state language

**Priority: P1 — Effort: Low — Visual impact: Medium/high**

### Observation

The selected navigation location can currently be communicated by several simultaneous cues:

- group-level accent bar;
- active row background;
- active row accent text;
- stronger font weight;
- `Current` group text for an active collapsible group.

The redundancy is accessible, but visually it is more signalling than a calm rail needs.

### Recommendation

Keep two cues maximum:

- active row tonal background;
- one accent cue (icon/text or edge marker).

Remove `Current` and/or the group-level accent bar once the active row remains visible.

---

## VIS2-09 — Give top-level destinations distinct icon identities

**Priority: P1 — Effort: Low/Medium — Visual impact: High**

### Observation

Several conceptually different destinations reuse the same visual metaphor, including `spark` across multiple creation/knowledge surfaces and chat-like symbols across communication surfaces.

Repeated icons force users back to labels and weaken the collapsed rail, where icons are the only visible navigation language.

### Recommendation

Establish a semantic icon map with no duplication among permanent rail destinations:

```text
Home          house / workspace
Chat          message
Build         code / terminal brackets
Threads       history / conversation stack
Tasks         check / clock
Projects      folder / workspace
Memory        memory / bookmark / layers
Knowledge Map graph / nodes
```

Reserve the Raiker spark/eye identity for **AI/agent action** rather than generic navigation.

### Acceptance

A user familiar with Raiker should be able to recognise all permanent-rail destinations with labels hidden.

---

## VIS2-10 — Make Models, Extensions, Observability and Settings feel composed, not tab-warehoused

**Priority: P1 — Effort: Medium — Visual impact: High**

### Observation

The current grouping solved the old flat-navigation problem, but the secondary hubs are still large:

- Models: 6 tabs;
- Extensions: 5 tabs;
- Observability: 6 tabs;
- Settings: 10 sections.

The organisation is logical, yet a large tab strip can still feel like configuration software rather than a deliberately composed workspace.

### Recommendation

Use **task-oriented hub landings** and subsection navigation.

Examples:

**Models landing**

```text
Active model
Ready alternatives
Recent model operation

Manage
  Local
  Hosted
  Hugging Face
  Routing
  Pricing
```

**Observability landing**

```text
Needs attention
Active work
Recent approvals/denials
Last integrity check

Inspect
  Sessions
  Activity
  Checkpoints
  Work
  Notifications
```

On mobile, prefer a drill-in list or segmented grouped navigation rather than a long horizontally scrolling tab strip.

---

## VIS2-11 — Continue the move toward Project as the persistent visual context

**Priority: P1 — Effort: Medium/High — Visual impact: Very high**

### Observation

VIS-14 successfully unified metadata vocabulary, but Threads, Tasks and Projects remain separate top-level concepts. Current competitors increasingly make Project the persistent context that holds multiple work types.

Raiker's architecture already has the right ingredients. The visual hierarchy can go further.

### Recommendation

Inside a Project, treat these as sections of one workspace:

```text
Project name / goal / posture

Overview
Threads
Tasks
Files
Memory / context
Instructions
Activity
```

Global Threads and Tasks remain useful as **cross-project aggregate views**, but entering one Project should reduce the need to jump among global destinations.

Add restrained project identity:

- icon/glyph;
- optional accent choice drawn from approved theme tokens;
- project title + goal at the top of relevant work surfaces;
- consistent breadcrumb/project switcher.

Do not create a second navigation tree. The Project context should simplify orientation, not add more chrome.

---

## VIS2-12 — Complete Build's artifact half: third pane should be the object of work

**Priority: P1 — Effort: Medium — Visual impact: Very high**

### Observation

VIS-10 moved terminal/background work into the third zone, but its own status note left the artifact half open. Since then, Raiker already has components for:

- `DiffView`;
- `FileInspector`;
- `ImageViewport`;
- `CommandOutputPane`;
- source/file presentation.

The primitives now exist to finish the composition.

### Recommendation

Turn the third pane into a **contextual work inspector**:

```text
Changes | Preview | Terminal | Runs
```

Behaviour:

- opening a changed file selects **Changes**;
- generated code/file selects **Preview** or file inspector;
- command execution selects **Terminal** only when relevant;
- background task selects **Runs**;
- user can pin the pane open;
- pane collapses when no object warrants it.

This makes Build visually communicate “the agent is working on *this object*,” which is stronger than showing all artifacts inline in a transcript.

---

## VIS2-13 — Establish a badge/chip budget

**Priority: P2 — Effort: Low/Medium — Visual impact: High**

### Observation

Raiker now has a rich set of good status primitives: badges, model capacity, readiness, subscription limits, identity chips, source chips, posture, work metadata and state labels.

The risk is no longer bad individual badges. It is **chip accumulation**.

### Recommendation

Add a design-rubric rule:

- one primary status token per repeated row/card;
- at most one additional contextual token before overflow/detail;
- healthy/default facts should usually be plain text/icon;
- chips are for things the eye should scan as discrete state;
- never put a chip around a value merely because a component exists for chips.

Example:

Bad:

```text
[Ready] [Local] [Safe] [Implemented] [Ask] [Owner]
```

Better:

```text
Ready                      Local · Ask first · Owner
```

with detail on expansion.

---

## VIS2-14 — Add a theme-specific optical pass, not another palette redesign

**Priority: P2 — Effort: Medium — Visual impact: Medium/high**

### Observation

VIS-21 correctly let dark surfaces rely more on luminance than outlines. The next step should not be adding more colours.

Light and dark themes need slightly different **optical composition** even when they share semantic tokens.

### Recommendation

Light:

- let larger blank areas remain blank rather than filling them with cards;
- use subtle tonal section separation before adding borders;
- keep shadows very restrained;
- avoid making every white entity float on a near-white page.

Dark:

- keep borders rare;
- prevent gold + warning + active colours from appearing simultaneously in one cluster;
- rely on surface luminance and spacing for normal grouping;
- ensure terminal/code surfaces do not visually merge into the page background.

### Acceptance

A screenshot converted to greyscale should still show the same reading order in both themes.

---

## VIS2-15 — Treat 4K/8K as composition classes, not only bounded-width validation

**Priority: P2 — Effort: Medium — Visual impact: Medium**

### Observation

Raiker has unusually strong high-resolution screenshot coverage. Fixed reading/workspace/operational maxima prevent content from becoming absurdly wide, which is correct.

However, a bounded central island on 4K/8K can still look visually small even when it is technically readable.

### Recommendation

At very large widths:

- keep prose measure fixed;
- allow operational pages to use more simultaneous columns where useful;
- let Build/Knowledge Map/Observability exploit extra horizontal room;
- increase **inter-region whitespace**, not font size;
- consider a subtle max-canvas background/surface treatment so the work area feels intentionally framed rather than stranded.

Do not scale controls with resolution.

---

## VIS2-16 — Make normal state quieter than successful state

**Priority: P2 — Effort: Low — Visual impact: Medium**

### Observation

VIS-15 neutralised many healthy badges, but this principle should become stronger across pages:

- `ready` can be normal;
- `connected` can be normal;
- `implemented` can be normal;
- `allowed` can be normal.

Success colour should represent **something just completed** or something the user is actively verifying, not a permanent background condition.

### Recommendation

Add this explicit rule to the visual rubric:

> Persistent normal state is neutral. Success colour is temporal or confirmatory.

This helps Raiker avoid monitoring-dashboard aesthetics as more integrations are added.

---

## VIS2-17 — Standardise overlay/popover composition

**Priority: P2 — Effort: Medium — Visual impact: Medium/high**

### Observation

Raiker now has many transient surfaces:

- Command Palette;
- All Pages;
- Model picker;
- Posture popover;
- notifications;
- step-up/approval dialogs;
- attach panel;
- source/file inspectors.

Individually they are reasonable. As the product grows, they need one visual grammar.

### Recommendation

Define overlay classes by role:

1. **menu/popover** — small, anchored, immediate choices;
2. **picker** — searchable selection, medium width;
3. **inspector** — contextual details, side panel;
4. **decision dialog** — modal, one consequential action;
5. **command palette** — global search/action surface.

Standardise:

- header height;
- radius;
- border/shadow;
- title size;
- close affordance;
- action placement;
- maximum width;
- backdrop behaviour;
- mobile transformation (popover → bottom sheet/full-width panel where appropriate).

---

## VIS2-18 — Separate “attention” from “information” throughout the product

**Priority: P1 — Effort: Medium — Visual impact: High**

### Observation

Home, Observability, Models and governance pages all contain a mixture of:

- things the user must act on;
- things worth knowing;
- supporting evidence.

If those have similar card/header/badge treatment, the user must read everything to discover importance.

### Recommendation

Use a consistent three-level hierarchy:

```text
Needs action     explicit action / count / exception tone
Worth knowing    neutral summary
Evidence/detail  collapsed or lower visual weight
```

Apply this especially to:

- Home;
- Observability overview;
- Model readiness;
- Extensions health;
- Memory integrity;
- Approvals.

### Acceptance

A user should be able to identify all required actions from a page in a 2-second scan without reading explanatory paragraphs.

---

## VIS2-19 — Make Design canvas-first, not a third chat variant

**Priority: P2 — Effort: Medium/High — Visual impact: High**

### Observation

The overall shell correctly treats Design as a work surface, and `ImageViewport` already exists. Current agent/design tools are increasingly spatial: the object being changed is visible and selectable.

### Recommendation

As Design matures, use this hierarchy:

```text
Large image/canvas
Selected object / version / crop state
Compact prompt + controls
History / variations in a collapsible rail
```

Long-term direction:

- click/select the generated asset or region;
- send selection context with the next instruction;
- compare variants visually;
- keep generation metadata secondary.

This should look closer to a creative workspace than Chat with an image in it.

---

## VIS2-20 — Use the component system to prevent visual drift in the largest views

**Priority: P2 — Effort: Medium — Visual impact: Medium/high**

### Observation

Several major view files remain very large, particularly Build, Knowledge Map/Brain and Approvals. Large view components are not automatically visually poor, but they make it easier for spacing, headings, responsive behaviour and one-off state treatments to drift locally.

### Recommendation

When touching these views for product work, extract **visual regions**, not arbitrary code fragments:

```text
BuildWorkspaceShell
BuildConversationRegion
BuildArtifactRegion
ApprovalDecisionSummary
ApprovalEvidenceSection
KnowledgeMapToolbar
KnowledgeMapInspector
```

Each extracted region should consume the design tokens/surface vocabulary rather than re-declaring local visual rules.

This is a visual consistency measure, not a LOC target.

---

# Page-by-page Pass-2 observations

## Home

What is now strong:

- empty card walls were removed;
- attention content is conditional;
- Home has a clearer reason to exist.

Next polish:

- make **Continue work** the visually strongest normal-state region;
- make **Needs attention** visually strongest only when it is non-empty;
- avoid equal-weight headings for “recent”, “scheduled”, “standing” and “attention” if only one has useful content;
- use project identity sparingly so recent work is recognisable before the user reads every title.

## Chat

What is now strong:

- low chrome;
- shared composer;
- compact posture;
- Chat is clearly less dense than Build.

Next polish:

- simplify composer separators per VIS2-06;
- preserve model/context identity on compact widths per VIS2-05;
- keep ToolActivity collapsed to one readable sentence unless the user expands it;
- avoid surrounding ordinary assistant text with unnecessary containers;
- use richer typed blocks only when the answer actually benefits from structure.

## Build

This remains the highest-value visual investment.

Next polish:

- complete the contextual artifact pane (`Changes | Preview | Terminal | Runs`);
- let selected file/diff become the visual focus automatically;
- keep the conversation readable rather than letting three dense panes compete at equal weight;
- show plan/progress near the work object, not as another dashboard card;
- remember pane widths and last useful pane per project.

## Design

Next polish:

- progressively become canvas-first;
- let the image/asset occupy more of the screen than explanatory controls;
- move size/count/model options into a compact creation bar;
- make iteration/history visual rather than a list of technical generation records.

## Threads

Next polish:

- keep list-first presentation;
- use date/group separators quietly;
- project should be recognisable without turning every project name into a coloured chip;
- if task-generated sessions appear here, distinguish with one icon/state—not a totally different card.

## Tasks

Next polish:

- favour dense list rows over cards;
- surface state, next run and project as the scan line;
- open full evidence/logs in a side inspector;
- distinguish “needs you” from “running normally” more strongly than different shades of badge.

## Projects

Projects should become more visually important over time.

Next polish:

- add clear project identity and goal at the top;
- bring Threads, Tasks, Files and context together inside a project workspace;
- allow global views to remain aggregates rather than the primary way to navigate a long-running goal;
- do not duplicate the entire main sidebar inside Projects.

## Memory

Next polish:

- orient the normal user around **what Raiker remembers and why**;
- keep embedding/vector/backend implementation detail in Advanced/diagnostic views;
- visually distinguish approved memory, observed context and recall evidence through hierarchy and labels, not three unrelated card styles.

## Knowledge Map

The canvas-first direction is already strong.

Next polish:

- default to a useful focus rather than “everything” when the graph is dense;
- fade unrelated nodes/edges on selection;
- show labels progressively by zoom/focus;
- keep inspector and filter panels dismissible;
- treat animation as relationship/state feedback, not ambient movement.

## Approvals

The decision ordering is much better.

Next polish:

- make destination/affected-files/data scope instantly scannable;
- keep provenance/evidence collapsed until requested;
- if a diff exists, give it more visual area than policy metadata;
- distinguish **Approve**, **Approve once**, **Edit**, **Deny** only when the runtime actually supports semantically distinct actions—do not add decorative choice.

## Permissions

The row/list treatment is appropriate.

Next polish:

- search/filter should be visually prominent once the list grows;
- group high-risk/external capabilities ahead of routine ones where useful;
- default enabled/implemented states remain neutral;
- allow an expanded row to explain “what this allows” in plain language before schema/technical details.

## Models

Next polish:

- lead with **the model currently answering** and ready alternatives;
- provider-management internals should sit below that goal;
- recent failed/download/conversion activity appears only when relevant;
- pricing/routing can remain advanced destinations rather than equal-weight first impressions.

## Extensions

Next polish:

- visually separate **Connected/Installed** from **Available**;
- use provider/tool identity consistently;
- avoid each extension category inventing a new card structure;
- make permission/data-boundary consequences visible on connection, not permanently repeated on every card.

## Observability

Next polish:

- exceptions-first rather than “dashboard because dashboards have tiles”;
- show active work and failed/degraded subsystems before healthy telemetry;
- use timeline/table structures for evidence;
- collapse normal integrity/readiness history;
- let one action-required issue dominate instead of giving six subsystem states equal weight.

## Settings

The three-group structure is better.

Next polish:

- maintain clear group headings in the settings rail;
- keep destructive/security-sensitive actions visually separated from ordinary preferences;
- move licence/about/build information here from persistent sidebar chrome;
- avoid turning each setting into its own bordered card.

---

# Updated visual-system rules

These rules should be added to or cross-referenced from the visual rubric/design spec.

## Rule A — One dominant visual task per viewport

At normal desktop width, a screen should have one region that clearly reads first.

Exceptions: deliberate split workspaces such as Build, where two/three regions are simultaneously necessary.

## Rule B — Two active-state cues maximum

Do not combine colour, background, border, marker, bold and label to express one selection.

## Rule C — One primary status token per repeated entity

Additional state becomes plain metadata or detail.

## Rule D — Persistent normal state is neutral

Success colour is temporal or confirmatory; warning/error colour is exceptional.

## Rule E — Compact does not mean contextless

At narrow widths, combine context into one inspectable affordance instead of silently removing important turn identity.

## Rule F — Governance foregrounds only at a decision boundary

At rest, posture is a summary. At approval/risk transition, governance may become the dominant visual object.

## Rule G — The object of work wins the screen

In Build/Design, a diff/file/image/terminal becomes larger than explanatory chrome when it is the thing the user is reviewing.

## Rule H — Legal/build metadata belongs in About/Settings

Persistent workspace chrome should not contain repository/project-development metadata.

---

# Updated implementation order

Priority first, then effort.

## Wave 1 — Small polish with immediate visual return

1. **VIS2-02** — remove licence/runtime prose from permanent sidebar footer.
2. **VIS2-04** — platform-aware shortcut labels.
3. **VIS2-08** — simplify sidebar active-state cues.
4. **VIS2-09** — unique permanent-nav icon identities.
5. **VIS2-01** — repair type-scale dead step.
6. **VIS2-07** — state-aware posture wording.
7. **VIS2-16** — codify normal-state neutrality.

## Wave 2 — Everyday work-surface refinement

8. **VIS2-03** — top-bar clustering and badge/attention hierarchy.
9. **VIS2-05** — compact model/context recognisability.
10. **VIS2-06** — quieter composer composition.
11. **VIS2-13** — badge/chip budget.
12. **VIS2-18** — action vs information hierarchy across Home/Observe/Models.
13. **VIS2-17** — standard overlay vocabulary.

## Wave 3 — Product-level composition

14. **VIS2-12** — complete Build artifact pane.
15. **VIS2-10** — compose secondary hubs beyond flat tab strips.
16. **VIS2-11** — stronger Project workspace continuity.
17. **VIS2-19** — canvas-first Design evolution.
18. **VIS2-14** — theme-specific optical pass.
19. **VIS2-15** — high-resolution compositional refinement.
20. **VIS2-20** — extract large-view visual regions opportunistically.

---

# What should not change

Pass 2 does **not** recommend replacing the Control Deck identity.

Keep:

- the restrained gold/steel/neutral palette;
- Manrope as the main UI face;
- JetBrains Mono for technical evidence;
- Source Serif 4 only for selective high-value display/editorial moments;
- dual first-class light/dark themes;
- bounded reading widths;
- density controls;
- reduced-motion behaviour;
- semantic warning/error states;
- the explicit approval/governance model;
- the current strong responsive screenshot/rubric discipline;
- typed, governed presentation components instead of arbitrary provider HTML.

Do **not** chase “premium” by adding gradients, glass effects, neon status colours, unnecessary animation or decorative dashboards.

Raiker should be visually richer through **composition, hierarchy and contextual depth**, not ornament.

---

# Final Pass-2 judgment

The first review concluded that Raiker needed an information-hierarchy redesign. That statement is now stale.

**The hierarchy redesign has largely happened.**

The post-fix product has a credible visual system and a much clearer product shape. The remaining work is the kind of refinement that separates a good technical product from a polished daily-use product:

- remove persistent developer residue;
- make the top bar and composer quieter;
- preserve context when compact rather than hiding it;
- reduce redundant active/status signalling;
- strengthen typographic hierarchy;
- make Projects more visibly persistent;
- make Build's artifact the object of focus;
- make complex hubs feel composed rather than merely categorized;
- finish richer governed response composition.

The desired end state remains:

> **Raiker should look simpler than the architecture underneath it, calmer than the authority it controls, and more focused as the work becomes more complex.**

That is the correct visual expression of a governed agent: power is present, but the interface only asks the user to look at the part that matters now.
