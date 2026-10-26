# Design workspace

## Authority, purpose and status

**Owner-approved direction, 2026-10-15.** This is the canonical requirements
and workspace specification for Raiker Design. The target is **a unified design
workspace that can create governed visual assets and turn them into editable,
branded, exportable design documents through an agent-assisted structured
canvas.**

This is a target contract, not a claim that every capability below is shipped.
Design is a governed image-generation and lineage workspace (**Images**) and,
since 2026-10-19, a structured composition workspace (**Documents**) with the
first slice of the Agent layer: typed, owner-accepted proposals. Since
2026-10-20 the canvas is edited by pointer as well as keyboard, and a design can
carry imported pictures, reusable components and notes. The register
at the end says which requirements are delivered and which remain partial
([BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial)).
Current implementation availability and live evidence remain authoritative
over target wording.

Raiker Design serves one owner and their projects. It uses the shared personal
agent runtime, governance, storage and audit model; it does not introduce a
separate collaboration product, permission system or ungoverned creative
executor.

## Composer owner decisions (2026-10-26)

The following direction supersedes older composer-placement proposals. The
implementation is being validated; these decisions are not a production-readiness claim.

- **DEC-COMPOSER-01 — Shared adaptive architecture:** Home, Chat, Build and Design share the composer interaction pattern with surface-specific context and independent workspace drafts.
- **DEC-COMPOSER-02 — Minimal Design composer:** Attachment, Voice, Model and Send are the primary controls. Image size and output count belong outside the composer.
- **DEC-COMPOSER-03 — Design templates:** The empty image workspace offers visual starters that prepare editable prompts, preserve selected assets and ask before replacing a non-empty draft.
- **DEC-COMPOSER-04 — Active Design state:** The selected canvas and revision history take priority; templates are available through a compact entry, with edit suggestions only for declared edit support.
- **DEC-COMPOSER-05 — Execution-aware interaction:** Chat and Build retain actual steering, queue, approval and interruption behavior and must not invent progress.
- **DEC-COMPOSER-06 — Permission preservation:** Composer presentation does not grant or bypass runtime authority or approvals.

The image-import and starter interactions have mocked browser coverage. Live
provider generation, the complete responsive matrix and end-to-end execution
flows still require verification.

## Document boundaries and precedence

| Need | Authoritative source |
|---|---|
| Current Design user workflow | [Design guide](../guide/design.md) |
| Global visual language, components and responsive behavior | [Visual Design Specification](../architecture/VISUAL_DESIGN_SPEC.md) |
| Image-generation threat model and current egress/credential controls | [Image-generation threat model](../threat-models/image-generation.md) |
| Shared decision, approval and tool rules | [Decision modes](../architecture/DECISION_MODES_SPEC.md) and [tools and permissions](../architecture/TOOLS_AND_PERMISSIONS_SPEC.md) |
| Current implementation availability and limits | [Implementation status](../architecture/IMPLEMENTATION_STATUS.md) and [known limits](../architecture/KNOWN_LIMITS.md) |
| Open image-provider evidence gap | [BUG-287](../plans/TO_BE_FIXED.md#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider) |
| Personal-agent target and delivery evidence | [Personal autonomous-agent architecture](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) and [delivery plan](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) |

This document owns the Design product target. The guide owns accurate current
instructions; the visual specification owns how Design is drawn; the threat
model owns the security contract. When they differ, the current-state evidence
governs what may be claimed today, while this document governs future work.

## Product outcome

One Design project holds a structured design document, its visual assets,
brand/design-system material, agent work and export history. The owner can
start with a prompt, a brief, an existing image, a logo, a screenshot, a brand
guide, or a blank canvas and arrive at a usable visual outcome without losing
editability or provenance.

The core journey is:

`brief and references → plan → governed asset creation → structured composition → review and refine → validate → export or Build handoff`

Every arrow is visible, reversible where possible, and backed by an inspectable
record. The owner can switch freely between direct canvas edits and agent-led
changes without either path flattening the other into a screenshot.

## Coordinated layers

### 1. Asset layer

The asset layer creates, imports, stores and transforms visual material. It
includes generated raster images, uploaded images, logos, illustrations, icons,
photos, vector assets, colour palettes, fonts and reusable components.

Assets are owner-scoped and project-scoped where selected. Each retains
provenance: source/import, prompt and approved references where applicable,
provider/model, operation, parent asset, request time, content hash, license or
usage note when known, and outcome/refusal. Variations and edits form an honest
lineage graph; no operation rewrites history in place.

Asset operations that invoke a hosted provider remain governed effects. They
require the appropriate image/design capability, configured provider,
credential and egress allowance, and retain the existing refusal and audit
behavior. Importing or selecting an owner asset does not transmit it to a
provider; a separate, reviewable request does.

### 2. Composition layer

The composition layer is a structured, editable design document—not a bitmap
editor disguised as a canvas. A document contains pages or frames. A frame
contains an ordered, nested layer tree whose nodes can be text, shapes, vectors,
images, groups, components, layout containers or supported interactive
elements. Every node has a stable identifier, geometry, style, visibility,
locking state, parent/order relationship and provenance.

The canvas supports direct manipulation: select, multi-select, move, resize,
rotate, crop, align, distribute, reorder, group, lock and duplicate. It exposes
grids, guides, snapping, constraints and responsive frame variants. Text stays
real text, vectors stay editable paths/shapes, and placed images remain linked
to their asset/version rather than becoming opaque pixels.

### 3. Agent layer

The Design agent turns an owner goal into a proposed design plan and structured
canvas changes. It can analyse approved references, propose a hierarchy and
layout, generate or select assets, apply an owner-selected design system, write
or revise text, and make targeted changes to named frames or layers.

The agent never treats a model response as the document of record. It emits
typed design operations against stable node identifiers; the workspace applies,
previews, versions and validates those operations. The owner may accept a whole
proposal, inspect and accept individual changes, or edit directly. An agent
request must identify its intended frames/layers and preserve unrelated content.

The one-image canvas under **Images** is the Asset-layer viewer; the
Composition canvas is **Documents**.

## Functional requirements

### DW-01 — structured design documents

Design must persist an owner-scoped document with a stable identifier, project
association, pages/frames, layer/component tree, document metadata, version
history and export history. A document may remain unfiled, but filing it to a
project must be explicit and never move unrelated assets or conversations.

### DW-02 — editable canvas and layer model

The canvas must render and directly edit the structured model described above.
It must support text, shape/vector, image, group, layout-container and
component nodes; z-order, nesting, constraints, visibility and locking; and
selection/keyboard interactions that are accessible without pointer precision.
Text, vectors and layout constraints must survive save, restore, export and
agent revision as structured data.

### DW-03 — frames, layouts and responsive variants

Owners can create named frames/pages from blank, templates or agent proposals.
Frames define dimensions, background, grid and target context (for example
social post, document page, presentation, mobile or desktop screen). Layout
containers, alignment, spacing and responsive constraints make changes
systematic rather than manually repositioning every child. A variant is linked
to its source frame without implying that it automatically stays identical.

### DW-04 — governed visual asset creation and editing

Design must support prompt-driven creation, owner asset import, reference-image
use, targeted image editing, variations and supported transforms. Region or
mask-based edits, crop/resize, transparency, expansion/outpainting and
upscaling are exposed only when the selected provider/runtime actually supports
them. Unsupported controls are absent or clearly unavailable; they never become
an inert promise.

### DW-05 — asset lineage and reuse

Every generated, imported or transformed asset records its source and parent
relationships. The owner can browse, compare, reuse, restore or remove an asset
without deleting a dependent design silently. Refused provider attempts are
visible as attempts with their honest reason, not represented as a missing asset
or a successful operation.

### DW-06 — brand and design-system contracts

An owner may create or import a design system from selected brand material,
tokens, reusable components, logos, fonts, screenshots, approved files or a
codebase. The system stores colours, typography, spacing, grids, components,
usage rules and source/provenance. A design chooses its system explicitly;
changing it previews the affected nodes and never silently rewrites another
document. Agent-created work uses the selected system and reports any departure
or unknown rule.

### DW-07 — agent-assisted composition

For a design brief, the agent must propose a bounded plan identifying target
frames, intended hierarchy, copy/content assumptions, assets to create or reuse,
brand system, proposed operations and validation plan. The agent may create or
change only the named document/frame/layers within the current authority and
budget. It cannot replace a design, delete a large layer subtree, publish,
export externally or transmit assets without the applicable separate decision.

### DW-08 — direct editing and agent co-existence

Direct edits, comments/annotations and agent operations all create document
versions with actor, time, scope and reversible delta. Undo/redo must operate on
the structured document state, not regenerate an image. Before applying a stale
agent proposal, the workspace detects conflicting edits and offers a targeted
rebase, comparison or refusal; it never overwrites later owner work.

### DW-09 — references, provenance and privacy

Research references, screenshots, uploaded assets and brand material stay
separate from the brief and only leave the device/provider boundary when the
owner includes them in a disclosed request. The inspector shows what was sent,
what provider/model received it, what source supports an agent assertion, and
whether an element was generated, imported, copied or manually edited. Secrets,
unselected private files and unrelated project assets cannot be added by a
design prompt or a referenced page.

### DW-10 — validation and accessibility

Design validates document structure before export and can check declared
constraints such as missing assets, overflowing text, contrast, alt-text,
font availability, frame dimensions, broken component references and required
brand tokens. Checks report verified pass, failure, unsupported or unknown;
they do not imply visual quality or accessibility compliance from model prose.
The owner can review a human-readable findings list and affected layers.

### DW-11 — export, delivery and Build handoff

Design must export a selected frame/document in supported structured and visual
formats with the export settings, source version, validation outcome and file
hash recorded. Target formats are image and PDF first, then SVG/vector where
the content permits, presentation/document formats where supported, and a
structured web/prototype handoff. Export never flattens the stored working
document. A Build handoff names the source document/version, selected frames,
assets, design-system tokens and intended implementation target; it is context,
not permission to edit code.

### DW-12 — truthful progress and recovery

Design reports distinct planned, generating, editing, validating, exporting,
completed, partially completed, blocked, refused, failed and outcome-unknown
states. It retains durable operation receipts and can resume only after
revalidating the selected document, assets, provider/credential/egress state,
authority and budget. Ambiguous external operations are reconciled before retry;
an interrupted operation never becomes a silent success.

## Interaction model

The workspace has three coordinated regions, responsive to available space:

- **Brief and agent rail:** goal, plan, references, selected design system,
  proposed operations, approvals, status and findings.
- **Canvas:** the active page/frame, direct controls, guides, selection and
  responsive preview. It is the visual source of truth, not a preview image.
- **Assets and inspector rail:** searchable assets, pages/layers, component
  library, lineage, properties, export/history and contextual validation.

At narrower widths, rails become accessible drawers and preserve selection,
draft, unsaved direct edits and active operation status. The global visual rules
in `VISUAL_DESIGN_SPEC.md` govern typography, colour, responsive layout, focus,
motion and controls. The workspace must offer keyboard selection/navigation,
non-colour status cues, screen-reader names for layers and operations, 200% zoom
support and reduced-motion behavior.

## Safety, authority and non-goals

Design reuses Raiker's capability gates, decision modes, approval policy,
credential isolation, egress policy, budget controls and audit events. A
provider connection or API key is not permission to generate an asset, transmit
a reference, spend a budget, export to an external service, share a document or
change a codebase. References and canvas content are untrusted data: neither
can select a credential, redirect a request, change a decision mode or authorise
an effect.

This document does not authorise a multi-user design administration product,
unbounded cloud storage, public sharing by default, automated publication,
automatic code changes, hidden provider fallback, general-purpose raster
painting tools, or claiming the Anthropic assistant Design/ChatGPT Images parity before matched
outcome evidence exists.

## Acceptance and delivery evidence

The Design target is earned through representative end-to-end scenarios, not
screenshots or model claims alone:

1. Create a branded multi-frame design from an owner brief and selected system;
   directly change text/vector/layout; confirm the structured revision survives
   reload and export.
2. Import a logo and reference image; generate or edit an asset through a
   reachable approved provider; verify provenance, lineage, capability refusal
   and egress/credential boundaries.
3. Ask the agent to revise named components; inspect the typed patch; preserve
   unrelated owner edits; inject a conflict and verify no overwrite occurs.
4. Validate an export with deliberate contrast, overflow, missing-alt-text and
   unsupported-font faults; report each limitation honestly.
5. Hand a selected design version to Build; verify exact frames/assets/tokens
   are available as bounded context and that no code write occurs without Build
   authority.

Each run records Raiker revision, platform, model/provider/version, selected
capabilities and grants, budget, fixtures and content hashes, document/version
IDs, operation/approval trace, provider receipts, exports, validator version,
fault injection and result. `BUG-287` remains open until real provider generation
and editing have been observed through the product with the required denial and
lineage checks.

## Current foundation and delivery boundary

**Asset layer.** Prompt-to-image generation, selected-image editing,
variations, lineage, a one-image canvas, project filing, opt-in research
references sent with a prompt, downloads, restore/delete, owner-scoped storage,
provider/credential/egress checks, refusal records, and a per-provider
operations matrix (`IMAGE_OPERATIONS`) so only controls a provider path honours
are drawn.

**Composition layer** (`raiker/design/`, `/api/design/*`, **Design → Documents**).
Owner-scoped documents of frames and a nested layer tree (text, rectangle,
ellipse, image, group, stack) with stable ids; typed operations applied all or
nothing; numbered versions with actor, scope and snapshot; stale changes
rebased or refused; structured undo, redo and go back; pointer drag, resize and
rotate handles, multi-select, align, distribute and snapping with guides, each
gesture one version; frame presets, grid, stack layout and linked responsive
variants; image layers linked to their asset with non-destructive crop and fit,
including the owner's own imported pictures; components placed as linked,
editable instances; notes on layers and frames; versioned design systems typed,
read from a tokens file or a picture's colours, and applied through a preview;
ten validation checks with honest states; PNG, raster and vector PDF, SVG and
JSON exports pinned to version, validation and hash; and a Build handoff that is
context, never authority.

**Agent layer.** One named frame and the owner's brief go to the owner's chosen
chat model through their own router, gates and egress allowlist, with no tools.
The typed operations that come back are vetted against the version they were
made from, bounded to that frame, and applied only when the owner accepts all or
some of them — never over a layer the owner changed since. The proposal's
receipt is written before the model is asked, so one the host did not survive
reads as outcome unknown rather than vanishing.

What remains partial is tracked in
[BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial);
the real-provider image evidence in BUG-287.

## Consolidated Design delivery register

This register replaces Design-related review and roadmap material formerly held
in `docs/plans/`. It records the objective, reason, accepted decision and
closure evidence for every active Design workstream.

| ID / status | Objective | Reason | Accepted decision and closure evidence |
|---|---|---|---|
| DW-D01 / Open evidence | Prove real-provider image generation and editing through the product. | Unit/socket coverage cannot prove provider response shapes, source-image refusals, lineage or the owner-facing flow. | Keep [BUG-287](../plans/TO_BE_FIXED.md#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider) open until a reachable approved provider completes generate, edit, variation/refusal and lineage read-back. |
| DW-D02 / Implemented 2026-10-19 | Introduce a structured composition document and editable canvas. | A one-image viewer cannot create a reusable layout, preserve text/vector semantics or support direct design editing. | Implement the DW-01–03 document, frame, layer, layout and responsive-variant contracts; close with reload/restore/export fidelity and keyboard/zoom tests. **Closed ([FIXED-979](FIXED_ITEMS.md#fixed-979--a-design-was-one-picture-never-a-document-of-layers-dw-01-dw-02), [FIXED-982](FIXED_ITEMS.md#fixed-982--there-were-no-frames-layouts-or-responsive-variants-to-design-into-dw-03), [FIXED-983](FIXED_ITEMS.md#fixed-983--nothing-could-be-edited-directly-on-a-design-dw-02))**: documents of frames and a nested layer tree with stable ids and typed operations; frame presets, grid, stack layout and linked responsive variants; **Design → Documents** with canvas, layers, inspector and keyboard editing, reflowing to a phone width. Pointer drag, resize and rotate handles, multi-select, align/distribute and snapping followed on 2026-10-20 ([FIXED-998](FIXED_ITEMS.md#fixed-998--a-layer-could-only-be-moved-with-the-arrow-keys-dw-02-bug-348) to [FIXED-1001](FIXED_ITEMS.md#fixed-1001--a-drag-snapped-to-nothing-and-showed-no-guides-dw-02-bug-348)); selecting inside a group on the canvas remains in [BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial). |
| DW-D03 / Partly implemented 2026-10-19 | Add governed visual editing primitives. | Users need reference/image import, targeted edits, crop/resize, masks and transforms without controls that overpromise provider support. | Surface only runtime-supported capability-matrix operations; retain asset lineage, refusal and provider disclosure. Close with supported and unsupported-provider fixtures. **Slice ([FIXED-984](FIXED_ITEMS.md#fixed-984--a-picture-used-in-a-design-could-be-deleted-without-a-word-dw-05), [FIXED-985](FIXED_ITEMS.md#fixed-985--image-controls-could-not-say-which-provider-supported-them-and-there-was-no-crop-dw-03-dw-04))**: `IMAGE_OPERATIONS` says what each provider path does and Images draws only those controls (masks, outpainting and upscaling stay absent); image layers link to their asset with non-destructive crop and fit, and deleting a placed picture asks first. Owner image import followed on 2026-10-20 ([FIXED-1002](FIXED_ITEMS.md#fixed-1002--the-owners-own-picture-or-logo-could-not-be-brought-into-design-dw-04-bug-348)): an `import` asset with no provider, the governed source-image path BUG-287 needs. Provider-side mask, outpainting and upscaling stay absent until a provider path supports them. |
| DW-D04 / Implemented 2026-10-19 | Apply owner-selected brand/design systems. | A design agent must produce coherent reusable work rather than untraceable one-off visuals. | Store tokens/components/source/version; document selection is explicit and changes preview before applying. Close with conflicting-brand, missing-font and component-version tests. **Closed ([FIXED-986](FIXED_ITEMS.md#fixed-986--a-design-had-no-brand-to-follow-dw-06), [FIXED-987](FIXED_ITEMS.md#fixed-987--changing-a-designs-brand-would-have-rewritten-it-unseen-dw-06))**: versioned systems of colour, font and spacing variables, rules, required variables and a source note; choosing one previews every layer change and missing variable, then applies to that document only as one undoable version; Check reports off-system colours, unresolved and unused required variables. Tokens-file and picture-palette import and document components followed on 2026-10-20 ([FIXED-1004](FIXED_ITEMS.md#fixed-1004--a-design-system-could-only-be-typed-in-by-hand-dw-06-bug-348), [FIXED-1006](FIXED_ITEMS.md#fixed-1006--nothing-in-a-design-could-be-reused-dw-06-dw-10-bug-348)); brand-guide import and components shared through a system remain ([BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial)). |
| DW-D05 / Implemented 2026-10-19 | Make the agent edit typed canvas operations. | Conversational output alone cannot safely preserve unrelated direct owner edits. | Use stable layer IDs, bounded patches, conflict detection and structured undo/redo. Close with concurrent/stale proposal, selective acceptance and direct-edit preservation scenarios. **Closed ([FIXED-980](FIXED_ITEMS.md#fixed-980--a-change-made-against-an-old-copy-of-a-design-would-have-overwritten-newer-work-dw-08), [FIXED-981](FIXED_ITEMS.md#fixed-981--undo-meant-regenerating-a-picture-not-stepping-back-through-the-design-dw-08), [FIXED-988](FIXED_ITEMS.md#fixed-988--there-was-no-design-agent-only-an-image-prompt-dw-07), [FIXED-989](FIXED_ITEMS.md#fixed-989--accepting-an-agents-work-could-not-be-partial-and-could-overwrite-the-owners-dw-08-dw-d05))**: changes name their base version and are rebased or refused; undo/redo/go back are versions; the agent proposes typed operations for one frame, vetted and bounded, applied only by owner selection and never over a layer changed since. Live with Anthropic Haiku 4.5. Notes on layers and frames, and receipts that read *outcome unknown* after a host restart, followed on 2026-10-20 ([FIXED-1007](FIXED_ITEMS.md#fixed-1007--a-layer-could-not-carry-a-note-dw-08-bug-348), [FIXED-1009](FIXED_ITEMS.md#fixed-1009--a-proposal-whose-host-stopped-mid-call-left-no-record-dw-12-bug-348)). |
| DW-D06 / Implemented 2026-10-19 | Export and hand off truthful deliverables. | A finished design must remain editable, validate known limitations and reach Build without granting code authority. | Record source version/hash and validation for each export; Build receives bounded context only. Close with image/PDF/structured-export checks and a no-code-write handoff test. **Closed ([FIXED-990](FIXED_ITEMS.md#fixed-990--nothing-checked-a-design-before-it-left-raiker-dw-10), [FIXED-991](FIXED_ITEMS.md#fixed-991--a-design-could-not-be-exported-and-an-export-would-not-have-said-what-it-was-dw-11), [FIXED-992](FIXED_ITEMS.md#fixed-992--a-finished-design-could-not-reach-build-except-as-a-screenshot-dw-11), [FIXED-993](FIXED_ITEMS.md#fixed-993--a-build-handoffs-file-name-reached-the-page-as-redacted_secret), [FIXED-994](FIXED_ITEMS.md#fixed-994--png-and-pdf-exports-drew-a-box-for-an-em-dash-and-for-accented-letters))**: nine checks stating pass, fail, unsupported or unknown; PNG, raster PDF, SVG and JSON exports recording version, settings, validation and SHA-256; **Hand to Build** puts a bounded Markdown handoff in Build's composer and writes no code. Vector PDF followed on 2026-10-20 ([FIXED-1008](FIXED_ITEMS.md#fixed-1008--a-pdf-export-was-a-picture-of-the-frame-dw-11-bug-348)); presentation formats remain ([BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial)). |
| DW-D07 / Implemented foundation | Preserve governed image assets, lineage, project filing, research references, storage and deletion/restore. | This is the safe asset base for the larger workspace. | Keep image capability/egress/credential checks and owner-scoped storage; current behavior remains documented in the Design guide. |
