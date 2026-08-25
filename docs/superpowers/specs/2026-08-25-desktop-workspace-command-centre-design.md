# Desktop Workspace Command Centre Design

**Date:** 2026-08-25  
**Status:** Approved by the user and independent design review

## Objective

Refresh Raiker's desktop interface so it feels more deliberate, spacious, and
coherent while preserving its existing visual identity. The work covers grid
alignment, typography, icons, contrast, spacing, hover and focus states, menus,
navigation, and structural alignment across every desktop view.

The canonical current-state catalogue at `docs/plans/screenshots/pages/` will be
regenerated for the three desktop display classes in both themes after the UI is
verified. The mobile catalogue is outside this refresh and must not be replaced.

## Design direction

The interface becomes a **workspace command centre**: calm by default, explicit
about location and authority, and capable of yielding the full canvas when the
owner hides navigation. The visual refresh comes primarily from hierarchy,
alignment, surface separation, and navigation behavior rather than a new brand
palette.

The signature element is a restrained governance spine: the selected navigation
row and the current workspace status share a narrow structural marker. It uses
steel blue for ordinary selection, gold only when a decision is required, and
red only for failure or Stop. It encodes state rather than decorating the page.

## Palette and typography

The current hues remain the foundation:

| Token role | Value | Use |
|---|---:|---|
| Canvas | `#F8FAFC` | Light application background |
| Surface | `#FFFFFF` | Light cards, menus, and controls |
| Ink | `#0F172A` | Primary light-theme text |
| Steel | `#365F7D` | Primary action, selection, and focus |
| Governance gold | `#ECD06F` | Pending decisions and the brand mark |
| Night canvas | `#0B0D10` | Dark application background |

Existing dark-theme slate surfaces and the light/dark semantic status colours
remain. Contrast improvements come from clearer canvas, inset, surface, raised,
border, and interactive relationships. No additional brand hue is introduced.

Typography has three explicit roles:

- **Source Serif 4**: high-value page statements and focused empty states only.
- **Manrope**: page titles, interface headings, body copy, labels, and controls.
- **JetBrains Mono**: code, identifiers, timestamps, command output, and machine
  state only.

The shared type scale is the only source of interface sizes. Desktop typography
does not grow with viewport width; page-specific viewport units and clamps are
removed where they violate that contract. Reading prose is bounded to roughly
68 characters per line.

## Shell and navigation

The left sidebar keeps the existing binary behavior: fully shown or fully
hidden. Hiding it removes its entire width and maximizes the canvas. The top-left
reveal control remains available, keyboard reachable, and visibly focused.
The top bar always retains the current page title and short description, so the
owner never loses location context when navigation is hidden.

When shown, the sidebar contains:

- **Core**, always visible: Workbench, Chat, Build, Search chats, Tasks, Projects.
- **Knowledge**, collapsible: Memory and Knowledge Map.
- **Manage**, collapsible: Approvals, Permissions, Models, and Extensions.
- **Observe**, collapsible: all observability destinations.
- **Support**, collapsible: Guide and Settings.

Recent Chats is removed. Search Chat is renamed **Search chats** and becomes the
single conversation-discovery surface. Its initial state lists all conversations
recent-first; a query filters/searches that list. Empty-query, populated,
no-result, project-scoped, untitled, and empty-session states remain useful, and
opening a result still reaches the conversation.

Each group heading is a real button with a visible chevron, `aria-expanded`, and
`aria-controls`. Keyboard activation matches pointer activation. A group that
contains the current route opens automatically and has a visible active cue.
Other expanded states persist locally, but persisted state can never hide the
active route.

## Desktop grid and canvas

The shell uses named layout tokens instead of page-specific widths:

- **Reading**: bounded page with prose constrained to about `68ch`.
- **Workspace**: ordinary forms, cards, and mixed-content pages.
- **Operational**: tables, dashboards, graphs, and multi-panel surfaces, with a
  recommended maximum near `112rem`.
- **Work surface**: explicit full-height contract for Chat and Build between the
  top bar and viewport edge.

All variants are centered within the actual content box in both sidebar states.
The shared desktop layout uses a twelve-column grid with named gaps and gutters.
Components may span those columns but may not create unrelated outer margins.
At 4K and 8K, operational pages gain more usable width than today while reading
measure and control sizes stay fixed.

```text
Sidebar shown                         Sidebar hidden
+----------+-----------------------+  +-------------------------------+
| Core     | Top bar: page identity|  | Top bar: reveal + page identity|
| Groups   +-----------------------+  +-------------------------------+
|          |  12-column canvas     |  |       12-column canvas        |
|          |  reading/workspace/   |  |       full available width    |
|          |  operational/work     |  |                               |
+----------+-----------------------+  +-------------------------------+
```

Settings and other pages with local navigation keep it inside the page grid.
Local navigation aligns with content and never competes with the application
sidebar. The Settings save bar follows the grid rather than a fixed left offset.
Web access and Git credential appear under the System heading, matching their
declared classification.

## Components and interaction

Pages follow a common anatomy: optional context label, title, concise lead,
primary actions, then content. Dense operational pages may use a compact header
but keep the same alignment baseline.

Controls and menus use shared height, padding, radius, icon, and typography
tokens. Desktop controls target 40 CSS pixels, with 44-pixel targets where the
interaction or compact layout requires them. Dropdowns align to their trigger,
remain inside the viewport, expose selection state, support keyboard traversal,
dismiss on Escape/outside interaction, and restore focus appropriately.

One hover cue is used per component: either a restrained surface tint/lift or a
border change. Focus remains independent and clearly visible. Reduced-motion and
forced-colour behavior remain supported.

The inline SVG icon system remains self-contained and offline-capable. Icons use
the shared optical scale and a unique glyph for distinct meanings. Decorative
icons are hidden from assistive technology; informative SVGs have accessible
names; icon-only controls have explicit button names and tooltips. Empty visible
SVGs remain an automated failure.

Related information is grouped with panels, dividers, and aligned rows instead
of excessive standalone cards. Card removal is selective: elevation still
communicates overlays, interactive choices, or genuinely separate objects.

## Page-by-page scope

Every current route/tab state receives an individual desktop review for grid
spans, header anatomy, whitespace, local navigation, table/form density, action
placement, empty/loading/error states, menu behavior, and viewport use.

The canonical 26-state screenshot matrix is necessary but not sufficient. The
audit also covers every Models tab and all nine Settings sections, even though
only their canonical default states are committed to the page catalogue. Fixes
belong in the owning component or shared primitive; broad overrides are used only
for true system-wide contracts.

## Data flow and compatibility

Navigation grouping changes presentation only. Existing route identifiers and
destinations remain stable. Sidebar visibility continues to use its existing
owner preference. Group expansion preferences are additive and tolerate missing
or invalid local storage. Route changes always take precedence by opening the
active group.

Search chats reuses the existing session source and opening behavior. It changes
the blank-query presentation from instructional emptiness to a recent-first
browse state; it does not change conversation ownership or deletion semantics.

## Verification and acceptance

Acceptance requires:

- Unit coverage for navigation grouping, persistence, active-route expansion,
  Search chats browse/filter states, Settings grouping, and layout variants.
- Accessibility checks for disclosure controls, icon naming, focus visibility,
  menu keyboard behavior, Escape dismissal, focus restoration, landmarks, and
  colour contrast.
- Desktop browser checks at 1920x1080, 3840x2160, and 7680x4320 in light and
  dark themes, with the sidebar both shown and hidden.
- Bounds assertions for reading, workspace, operational, and work-surface
  layouts; no horizontal overflow; no viewport-scaled text or controls.
- Individual automated or manual inspection of every Models tab and every
  Settings section in addition to all 26 canonical route/tab states.
- Fresh viewport-only captures for the 156 desktop catalogue files:
  `26 states x 3 desktop sizes x 2 themes`. PNG dimensions and expected names
  must be verified. The 52 mobile files remain untouched.
- Visual inspection through desktop contact sheets plus original-resolution
  samples for Workbench, Chat, Build, Memory, Models, Observability, Guide, and
  Settings. Any defect requires fixing and recapturing the affected desktop
  matrix.
- Fresh lint, type-check, unit-test, build, relevant Playwright, documentation,
  and diff-whitespace checks before completion is reported.

## Out of scope

- Mobile visual redesign or mobile screenshot replacement.
- New routes, removed routes, or renamed route identifiers.
- New brand colours, icon libraries, or remotely hosted fonts/assets.
- Runtime, governance, or model-provider behavior unrelated to conversation
  discovery in Search chats.
