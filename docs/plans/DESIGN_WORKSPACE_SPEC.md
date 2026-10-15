# Design workspace

## Authority, purpose and status

**Owner-approved direction, 2026-10-15.** This is the canonical requirements
and workspace specification for Raiker Design. The target is **a unified design
workspace that can create governed visual assets and turn them into editable,
branded, exportable design documents through an agent-assisted structured
canvas.**

This is a target contract, not a claim that every capability below is shipped.
The existing Design surface is an implemented, governed image-generation and
lineage workspace. It does not yet provide the structured composition or agent
layers described here. Current implementation availability and live evidence
remain authoritative over target wording.

Raiker Design serves one owner and their projects. It uses the shared personal
agent runtime, governance, storage and audit model; it does not introduce a
separate collaboration product, permission system or ungoverned creative
executor.

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

The current one-image canvas is an Asset-layer viewer, not the future
Composition canvas.

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
painting tools, or claiming Claude Design/ChatGPT Images parity before matched
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

Today Design provides prompt-to-image generation, selected-image editing,
variations, lineage, a one-image canvas, project filing, opt-in research
references sent with a prompt, downloads, restore/delete, owner-scoped storage,
provider/credential/egress checks and refusal records. These are Asset-layer
foundations, not evidence that the Composition or Agent layers are implemented.

The next implementation planning cycle must decompose this contract without
creating a parallel authority model or a second asset store. It must define the
structured document schema, canvas operation protocol, design-system source and
version rules, provider capability matrix, validation rules, export formats,
Build handoff contract, migrations and the test/evidence matrix before any
capability is advertised as delivered.

## Consolidated Design delivery register

This register replaces Design-related review and roadmap material formerly held
in `docs/plans/`. It records the objective, reason, accepted decision and
closure evidence for every active Design workstream.

| ID / status | Objective | Reason | Accepted decision and closure evidence |
|---|---|---|---|
| DW-D01 / Open evidence | Prove real-provider image generation and editing through the product. | Unit/socket coverage cannot prove provider response shapes, source-image refusals, lineage or the owner-facing flow. | Keep [BUG-287](../plans/TO_BE_FIXED.md#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider) open until a reachable approved provider completes generate, edit, variation/refusal and lineage read-back. |
| DW-D02 / Planned | Introduce a structured composition document and editable canvas. | A one-image viewer cannot create a reusable layout, preserve text/vector semantics or support direct design editing. | Implement the DW-01–03 document, frame, layer, layout and responsive-variant contracts; close with reload/restore/export fidelity and keyboard/zoom tests. |
| DW-D03 / Planned | Add governed visual editing primitives. | Users need reference/image import, targeted edits, crop/resize, masks and transforms without controls that overpromise provider support. | Surface only runtime-supported capability-matrix operations; retain asset lineage, refusal and provider disclosure. Close with supported and unsupported-provider fixtures. |
| DW-D04 / Planned | Apply owner-selected brand/design systems. | A design agent must produce coherent reusable work rather than untraceable one-off visuals. | Store tokens/components/source/version; document selection is explicit and changes preview before applying. Close with conflicting-brand, missing-font and component-version tests. |
| DW-D05 / Planned | Make the agent edit typed canvas operations. | Conversational output alone cannot safely preserve unrelated direct owner edits. | Use stable layer IDs, bounded patches, conflict detection and structured undo/redo. Close with concurrent/stale proposal, selective acceptance and direct-edit preservation scenarios. |
| DW-D06 / Planned | Export and hand off truthful deliverables. | A finished design must remain editable, validate known limitations and reach Build without granting code authority. | Record source version/hash and validation for each export; Build receives bounded context only. Close with image/PDF/structured-export checks and a no-code-write handoff test. |
| DW-D07 / Implemented foundation | Preserve governed image assets, lineage, project filing, research references, storage and deletion/restore. | This is the safe asset base for the larger workspace. | Keep image capability/egress/credential checks and owner-scoped storage; current behavior remains documented in the Design guide. |
