# Adaptive Workspace Shell Design

## Status

Approved product direction, awaiting independent design and implementation-plan
review before code changes begin. This document turns
[`ADD-26`](TO_BE_ADDED.md#add-26--a-premium-responsive-workspace-shell) and the
responsive acceptance contract in
[`RAIKER_LIVE_MANUAL_TEST_PLAN.md`](RAIKER_LIVE_MANUAL_TEST_PLAN.md#43-responsive-s)
into a buildable design for the current Svelte shell.

## Goal

Make Raiker feel like a quiet engineering workspace at every width. Desktop
navigation shares the viewport and reflows the work. Small-screen navigation
floats above the work without changing its line length. Theme, status, motion,
focus, and scrolling behave consistently across all routes.

This change does not redesign individual product pages, alter runtime authority,
or add a new navigation hierarchy. It improves the shared frame around the
existing fifteen routes and their tabbed views.

## Existing baseline

- `App.svelte` owns the viewport-height shell and the independently scrolling
  main content column.
- `Sidebar.svelte` is a fixed 232-pixel desktop column and a left drawer below
  1024 pixels. Phones also render a five-item bottom navigation bar.
- `Topbar.svelte` owns route identity and global controls, but not navigation.
- `BuildView.svelte` owns the only right rail. It reflows Build above 1024
  pixels and stacks below the composer at smaller widths.
- `app.css` centralizes themes, but the current black/gold “Control Deck” palette
  does not match the approved low-saturation obsidian/slate system.
- `ui-sweep-responsive-live.spec.ts` visits 26 route/tab states at mobile,
  tablet, and desktop sizes, but it does not cross those pages with both themes.

## Approaches considered

### A. App-owned shell state — selected

`App.svelte` owns whether the desktop left rail is open. `Topbar` receives the
state and toggle callback; `Sidebar` receives the controlled state and its
drawer controls. Build continues to own its right rail because that panel exists
only on Build.

This creates one explicit layout authority, supports state persistence without a
global store, and makes the button, rail, and `aria-expanded` relationship easy
to test.

### B. CSS-only checkbox or `:has()` shell

This would minimize TypeScript, but focus restoration, Escape handling,
small-screen mode changes, local persistence, and accessible expanded state
would become indirect or browser-dependent. It is rejected.

### C. Global Svelte shell store

A global store would support future plugin panels and multiple rails, but the
current product has one global left rail and one Build-only right rail. It would
add lifecycle and synchronization work without serving the requested behavior.
It is deferred until a second global rail actually exists.

## Visual system

### Palette

The approved values become the semantic source tokens. Existing component
aliases continue to work, but resolve through these values rather than retaining
the old black/gold hues.

| Role | Dark | Light |
|---|---|---|
| app background | `#0B0D10` | `#F8FAFC` |
| surface/card | `#12161F` | `#FFFFFF` |
| muted border | `#1F242F` | `#E2E8F0` |
| primary text | `#E2E8F0` | `#0F172A` |
| supplied secondary palette value | `#64748B` | `#475569` |
| normal-size muted text | `#94A3B8` | `#475569` |
| allowed background | `#142E24` | `#E6F4EA` |
| allowed text | `#A7F3D0` | `#137333` |
| blocked background | `#3E1F11` | `#FCE8E6` |
| blocked text | `#FFEDD5` | `#C5221F` |

`--bg`, `--surface`, `--border`, `--text-1`, `--text-2`, `--ok-soft`,
`--ok`, `--danger-soft`, and `--danger` map to the accessible semantic roles.
The supplied dark secondary value remains available as
`--palette-secondary: #64748B`, but is limited to decorative/inactive marks and
large text that independently meets AA. It is not used for normal-size text:
its contrast on `#12161F` is below 4.5:1. Normal muted dark text therefore uses
`--text-2: #94A3B8`; light mode uses the supplied `#475569`. Raised and
sunken surfaces use nearby slate values or `color-mix()` derived from the base
roles. Interactive accent remains a restrained steel/slate blue in light mode
and a soft desaturated blue in dark mode; it is not reused as a status color.

The signature is the **focus canvas**: collapsing the left rail exposes a
centered, wide-margin reading plane instead of merely stretching every line to
the viewport edge. It is specific to Raiker's long code, logs, and audit prose.

### Depth and typography

The base/surface luminance step and a one-pixel muted border create separation.
The navigation and desktop right rail use no heavy shadow. Shadows remain only
for transient overlays, where elevation is information.

Raiker's existing Manrope, Source Serif, and JetBrains Mono roles remain. The
change is a shell treatment, not a typographic rebrand. Main prose retains a
bounded readable width while data-heavy views may use the larger workspace.

## Layout contract

### Desktop — 1024 pixels and above

```text
left rail open                         focus state
┌────────────┬─────────────────────┐   ┌──────────────────────────────┐
│ nav 256 px │ control header      │   │ control header              │
│ own scroll ├─────────────────────┤   ├──────────────────────────────┤
│            │ centered canvas     │   │     centered canvas         │
│            │ own scroll          │   │     own scroll              │
└────────────┴─────────────────────┘   └──────────────────────────────┘
```

- The left rail is 256 pixels, participates in flex layout, and transitions its
  width/transform using the shared shell easing curve.
- Hiding it removes its layout width and recenters the canvas. The state is a
  presentation preference stored locally; it grants no authority.
- The header contains the rail toggle. When closed, the toggle becomes visually
  quiet until hover, pointer proximity to the top-left region, or keyboard
  focus. It never becomes inaccessible or fully invisible.
- The left rail and content keep independent vertical scrolling.
- Build's right rail remains a fixed 21-rem column and reflows only Build's
  central workspace. Its own toggle and scroll remain independent.
- High-resolution desktops are first-class targets: 1080p at `1920 × 1080`,
  4K UHD at `3840 × 2160`, and 8K UHD at `7680 × 4320`. The navigation and
  controls keep their physical CSS-pixel scale; the central page remains
  bounded and centered, so added pixels become useful breathing room rather
  than multi-metre lines of prose. Data-heavy canvases may use a wider bounded
  variant, but no route grows without a declared maximum.

### Small screens — below 1024 pixels

```text
closed                                drawer open
┌──────────────────────────────┐      ┌──────────────┬───────────────┐
│ ☰  control header            │      │ navigation   │ darkened work │
├──────────────────────────────┤      │ overlay      │               │
│ workspace canvas             │      │ own scroll   │ unchanged     │
│ unchanged width              │      │              │ width         │
└──────────────────────────────┘      └──────────────┴───────────────┘
```

- The bottom navigation is removed. The menu trigger lives in the control
  header at phone and tablet widths.
- The left rail is an overlay drawer. Opening it never changes the width or
  wrapping of the workspace beneath it.
- The scrim uses the theme overlay token. The drawer uses the surface and muted
  border, with only a restrained transient shadow.
- The drawer closes on navigation, close button, Escape, or scrim activation.
- While open, focus stays within the drawer, background scrolling is locked,
  and Escape, scrim, or close-button dismissal restores focus to the header
  trigger. Navigation-triggered close does not restore trigger focus;
  `App.svelte` moves focus to `main` after the new route renders, and that route
  focus action wins.
- Build's right rail becomes a right-side overlay drawer under the same
  breakpoint instead of stacking below the transcript. It follows the same
  scrim, focus, Escape, scroll-lock, and restoration contract.
- Only one compact drawer may be active. Opening Build background work closes
  navigation first (and vice versa), completes its cleanup, then activates the
  requested drawer. This prevents two scrims, two focus traps, or ambiguous
  Escape handling.
- While either drawer is active, the explicit application background regions
  are `inert` and `aria-hidden`; cleanup restores their previous attributes.

## Component boundaries

### `App.svelte`

- Owns `leftRailOpen` for desktop and supplies the controlled contract.
- Restores the saved desktop preference on mount.
- Applies a shell state class/data attribute used only for layout.
- Continues to own the main content scroller and route focus movement.

### `Topbar.svelte`

- Renders the navigation toggle as the first control.
- Receives `navigationOpen`, `compactNavigation`, and `onNavigationToggle`.
- Keeps route title, hint, project, notification, theme, and host controls in
  their existing order after the navigation anchor.

### `Sidebar.svelte`

- Renders navigation content and manages only transient compact-drawer behavior:
  focus trap, Escape, scrim, scroll lock, and focus restoration.
- Receives desktop visibility and toggle callbacks instead of deciding desktop
  layout itself.
- Removes the phone bottom bar and its duplicated route subset.
- Preserves every route, recent chat, project action, and footer disclosure.

### `BuildView.svelte` and `BuildSidePanel.svelte`

- Preserve the current desktop grid.
- Replace the small-screen stacked rail with a controlled right drawer.
- Reuse the shell overlay/focus behavior through a small shared drawer utility
  or focused component rather than duplicating keyboard logic.

### `ResponsivePage.svelte`

- Adds `layout: "reading" | "workspace"` (default `workspace`). Reading pages
  have a 72-rem maximum; data-dense workspace pages retain 90 rem.
- `App.svelte` maps Chat/New Chat, Search Chat, and Guide to `reading`; Build,
  Workbench, Tasks, Projects, Memory, Brain, Approvals, Capabilities, Models,
  Extensions, Observe, and Settings use `workspace`.
- Centering is measured within `.content`, the actual independently scrolling
  content box. Only the collapsed desktop focus state is also viewport-centred.

## Motion and interaction

- One `--ease-shell` custom curve drives left rail, right rail, and scrim entry.
- Desktop transitions use width/transform without animating content properties.
- Hover shifts use adjacent surface/luminance values only.
- `prefers-reduced-motion: reduce` removes travel and fading, leaving the final
  open/closed state immediate.
- No bounce, neon glow, flashing state, or decorative animation is introduced.

## Accessibility

- All rail toggles have names, `aria-controls`, and accurate `aria-expanded`.
- Closed overlay drawers are `inert` and `aria-hidden`. While one is open, its
  explicitly supplied application-background siblings are also `inert` and
  `aria-hidden`, then restored on cleanup.
- Open drawers trap Tab/Shift+Tab. Escape, scrim, and explicit close restore
  trigger focus; navigation cleanup does not, so route focus lands on `main`.
- Allowed/blocked states continue to include icon/text labels; hue is never the
  only signal.
- Exact palette mappings receive automated assertions and contrast checks in
  both themes.
- Keyboard-only users can reveal the hidden desktop toggle through focus.

## Screenshot and evidence contract

`docs/plans/screenshots/pages/` is the mutable current-state catalogue. The
historical `working/` and `not-working/` folders are evidence archives and are
not overwritten.

The page sweep visits its existing 26 route/tab states and commits eight
viewport-only captures per state (not full-page documents):

- `mobile-light-<page>.png` at 390 × 844;
- `mobile-dark-<page>.png` at 390 × 844;
- `1080p-light-<page>.png` at 1920 × 1080;
- `1080p-dark-<page>.png` at 1920 × 1080;
- `4k-light-<page>.png` at 3840 × 2160;
- `4k-dark-<page>.png` at 3840 × 2160;
- `8k-light-<page>.png` at 7680 × 4320;
- `8k-dark-<page>.png` at 7680 × 4320.

Tablet and the exact 1024-pixel breakpoint remain assertion-only coverage for
overflow, selected tabs, layout state, and rail behavior. The screenshot sweep
sets the theme in local storage before application mount, reloads into that
theme, and asserts both `html[data-theme]` and the theme control's accessible
state. It waits for content to settle, parks the pointer away from hover targets,
and fails on console errors. Each PNG's IHDR width/height must exactly equal its
declared viewport. High-resolution captures also assert that the bounded page
does not exceed its declared maximum and remains centered within one pixel of
the `.content` inner box (and of the viewport in collapsed focus state).

## Documentation changes

- Add `docs/guide/memory.md` as the owner-facing lifecycle and retrieval guide.
- Add it to the guide index and in-product reading order.
- State a maintenance contract in the memory architecture plan: any change to
  capture, approval, retrieval, tiering, correction, retention, archive,
  forget, purge, projection, or privacy behavior must update the guide in the
  same change.
- Expand source-checkout installation in `README.md` and
  `docs/guide/getting-started.md` with separate Linux and macOS prerequisites,
  activation, dashboard build, launch, service behavior, and current unsigned
  release boundary.

## Verification

1. Unit tests for desktop state, compact drawer focus/scroll behavior, Build
   overlay behavior, and exact token mappings.
2. Svelte type-check, ESLint, Vitest, and production build.
3. Mocked Playwright regression suite.
4. Live responsive assertions at 390, 768/834, 1024, 1440, 1920 × 1080,
   3840 × 2160, and 7680 × 4320.
5. Visual review of every committed page capture in light and dark, desktop and
   mobile—including the 1080p, 4K, and 8K catalogues—plus independent scrolling
   and both rail states.
6. Python guide tests and Markdown relative-link validation.

## Non-goals

- No page-specific redesign or content rewrite.
- No new global right rail outside Build.
- No hosted/mobile-native client work.
- No deletion or replacement of historical defect/evidence screenshots.
- No claim that unsigned `.deb`, AppImage, or `.pkg` artifacts are published
  releases; installation documentation describes the supported source checkout.
