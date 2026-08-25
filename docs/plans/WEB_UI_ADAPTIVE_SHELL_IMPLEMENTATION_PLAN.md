# Adaptive Workspace Shell Implementation Plan

## Status

**Complete — 2026-08-25.** The independently approved design was implemented
and verified as one release candidate. The procedural checklist below is kept
as the reproducible build record; completion evidence is summarized at the end.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved low-saturation palette, desktop reflow/focus
state, small-screen overlay drawers, memory guide, Linux/macOS installation
guidance, and a complete light/dark screenshot catalogue at mobile, 1080p, 4K,
and 8K.

**Architecture:** `App.svelte` owns persistent desktop navigation visibility and
passes a controlled contract to `Topbar` and `Sidebar`. A focused drawer utility
owns modal keyboard/focus/scroll behavior for the compact left rail and Build's
right rail. Existing route components and runtime APIs remain unchanged; theme
and responsive behavior are implemented in shared shell/token layers.

**Tech Stack:** Svelte 5 runes, TypeScript, CSS custom properties, Vitest,
Testing Library, Playwright, FastAPI guide assets, Markdown.

## Global constraints

- Do not change runtime permissions, routing, data ownership, or API contracts.
- Desktop begins at 1024 CSS pixels. The left rail is 256 pixels when open.
- Below 1024 pixels, left and Build-right rails overlay content and never change
  its width.
- Support and visually verify `390 × 844`, `1920 × 1080`, `3840 × 2160`, and
  `7680 × 4320`; keep assertion coverage at 768/834, 1024, and 1440 widths.
- Preserve every supplied light/dark palette value. Because dark `#64748B` on
  `#12161F` is below 4.5:1, expose it as `--palette-secondary` for non-text or
  independently conforming large-text use and use `#94A3B8` for normal muted
  text (`--text-2`).
- Use text/icons/luminance in addition to hue for allowed and blocked states.
- Respect reduced motion and preserve keyboard focus/restoration.
- `docs/plans/screenshots/pages/` is replaceable current-state evidence;
  `working/` and `not-working/` are immutable historical evidence.
- Do not describe unsigned installers as published or signed releases.

---

### Task 1: Pin the semantic palette and shell motion contract

**Files:**
- Modify: `apps/web/src/app.css`
- Modify: `apps/web/src/lib/appCss.test.ts`

**Interfaces:**
- Consumes: existing component aliases such as `--bg`, `--surface`, `--ok`, and
  `--danger-soft`.
- Produces: exact semantic tokens plus `--ease-shell` and `--motion-shell` for
  Tasks 3 and 4.

- [ ] **Step 1: Add failing exact-token tests**

Add a table-driven test that extracts the light and dark theme blocks and
asserts these mappings verbatim:

```ts
const expected = {
  light: { "--bg": "#F8FAFC", "--surface": "#FFFFFF", "--border": "#E2E8F0",
    "--text-1": "#0F172A", "--text-2": "#475569", "--ok-soft": "#E6F4EA",
    "--ok": "#137333", "--danger-soft": "#FCE8E6", "--danger": "#C5221F" },
  dark: { "--bg": "#0B0D10", "--surface": "#12161F", "--border": "#1F242F",
    "--text-1": "#E2E8F0", "--palette-secondary": "#64748B",
    "--text-2": "#94A3B8", "--ok-soft": "#142E24",
    "--ok": "#A7F3D0", "--danger-soft": "#3E1F11", "--danger": "#FFEDD5" },
};
```

- [ ] **Step 2: Run the focused test and verify the old palette fails**

Run: `npm --prefix apps/web run test -- src/lib/appCss.test.ts`

Expected: failure showing the existing `#f4f4f5`/`#000000` palette.

- [ ] **Step 3: Replace source tokens and derive secondary surfaces**

Map every exact role, keep `#64748B` out of normal-size text, define nearby
`--sunken`, `--raised`, strong borders, a
restrained non-status accent, transient-only shadows, `--ease-shell`, and
`--motion-shell`. Duplicate the dark values in the system-preference fallback,
as the existing parity test requires.

- [ ] **Step 4: Add contrast and reduced-motion coverage**

Add a small WCAG relative-luminance/contrast helper in the test. Assert at
least 4.5:1 for normal-size `--text-2` on `--surface`, allowed text on allowed
background, and blocked text on blocked background in light and dark themes.
Assert `--palette-secondary` is not in the normal-text eligibility table, and
record its sub-4.5 dark ratio, so a future alias cannot silently promote it.
Also assert the shell transition tokens resolve to no travel under
`prefers-reduced-motion: reduce`.

Run: `npm --prefix apps/web run test -- src/lib/appCss.test.ts src/lib/theme.test.ts`

Expected: all tests pass.

- [ ] **Step 5: Commit the token change**

```bash
git add apps/web/src/app.css apps/web/src/lib/appCss.test.ts
git commit -m "Adopt the subtle semantic dashboard palette"
```

---

### Task 2: Build one accessible overlay-drawer controller

**Files:**
- Create: `apps/web/src/lib/modalDrawer.ts`
- Create: `apps/web/src/lib/modalDrawer.test.ts`

**Interfaces:**
- Produces:

```ts
export interface ModalDrawerOptions {
  id: "navigation" | "build-background";
  container: HTMLElement;
  returnFocusTo: HTMLElement | null;
  backgroundElements: HTMLElement[];
  onDismiss: () => void;
}
export type DeactivateModalDrawer = (restoreFocus?: boolean) => void;
export function activateModalDrawer(options: ModalDrawerOptions): DeactivateModalDrawer;
```

The returned function removes listeners, restores the previous body overflow
and every background element's prior `inert`/`aria-hidden` state, and optionally
restores focus when the caller closes the drawer. The default is `true` for
Escape, scrim, and close-button dismissal; route changes call it with `false`
before `App.svelte` focuses `main`. A module-level coordinator
allows exactly one active drawer.

- [ ] **Step 1: Write failing tests for focus, Tab wrap, Escape, and cleanup**

Create a container with first/last buttons and explicit background siblings.
Verify activation focuses the first,
Tab from last wraps to first, Shift+Tab from first wraps to last, Escape calls
`onDismiss`, background scrolling is locked, background siblings become
`inert`/`aria-hidden`, and cleanup restores their exact prior states and body
style. Test cleanup's default trigger-focus restoration and its `false`
no-restore branch. Activate navigation then Build and verify navigation
is dismissed and completely cleaned before Build installs its trap. Cover
repeated cleanup, container unmount, and caller/route-change cleanup. Assert
route-change cleanup does not focus the trigger and allows route focus to remain
on `main`.

- [ ] **Step 2: Run the focused test and verify the module is missing**

Run: `npm --prefix apps/web run test -- src/lib/modalDrawer.test.ts`

Expected: failure because `modalDrawer.ts` does not exist.

- [ ] **Step 3: Implement the minimal controller**

Use `querySelectorAll` with the standard focusable selector, one keydown
listener, captured previous attributes/body overflow, and one module-local
active cleanup record. Activation dismisses and cleans the current drawer
before installing the next. Cleanup is idempotent and clears the singleton only
when it owns it. Do not create a history entry, portal, global Svelte store, or
animation API.

- [ ] **Step 4: Run the test and commit**

Run: `npm --prefix apps/web run test -- src/lib/modalDrawer.test.ts`

```bash
git add apps/web/src/lib/modalDrawer.ts apps/web/src/lib/modalDrawer.test.ts
git commit -m "Add accessible modal drawer behavior"
```

---

### Task 3: Make the left rail controlled, collapsible, and header-anchored

**Files:**
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/App.test.ts`
- Modify: `apps/web/src/lib/components/Topbar.svelte`
- Modify: `apps/web/src/lib/components/Sidebar.svelte`
- Modify: `apps/web/src/lib/components/Sidebar.test.ts`
- Modify: `apps/web/src/lib/components/ResponsivePage.svelte`
- Modify: `apps/web/src/lib/components/ResponsivePage.test.ts`

**Interfaces:**
- Consumes: `activateModalDrawer()` from Task 2 and shell tokens from Task 1.
- Produces controlled props:

```ts
// Sidebar
{ current: string; desktopOpen: boolean; drawerOpen: boolean;
  compact: boolean; onDrawerOpen: (trigger: HTMLElement) => void;
  onDrawerClose: (restoreFocus?: boolean) => void; }
// Topbar
{ navigationOpen: boolean; compactNavigation: boolean;
  onNavigationToggle: (trigger: HTMLElement) => void; /* existing props remain */ }
// ResponsivePage
{ layout?: "reading" | "workspace"; /* default: workspace */ }
```

- [ ] **Step 1: Add failing shell tests**

Verify the desktop toggle updates `aria-expanded`, sets
`data-navigation-open="false"` on `.app-shell`, persists
`raiker.navigation.desktop`, and restores it on mount. Verify compact mode opens
the same navigation as an inert overlay, focus enters it, Escape closes it, and
the trigger regains focus. Verify no phone bottom navigation is rendered.
Verify opening compact Build work closes compact navigation before its modal
controller activates, and route/unmount cleanup leaves no inert background.

- [ ] **Step 2: Run focused tests and record the failures**

Run:
`npm --prefix apps/web run test -- src/App.test.ts src/lib/components/Sidebar.test.ts`

Expected: missing controlled toggle/state behavior and the old phone bar still
present.

- [ ] **Step 3: Move breakpoint and visibility state into `App.svelte`**

Use `matchMedia("(max-width: 1023px)")`, a validated local-storage Boolean, and
separate `desktopOpen`/`drawerOpen` states. Route changes close only the compact
drawer; they do not overwrite the desktop preference.

- [ ] **Step 4: Put the only navigation trigger in `Topbar.svelte`**

Render a named icon button before `.page-id` inside an explicit 48 × 48 CSS-pixel
top-left reveal hit region; at compact widths it reads “Open
navigation”, and on desktop it toggles “Hide navigation”/“Show navigation”. Keep
it subdued when the desktop rail is closed, but fully visible on hover and
`:focus-visible`. Test pointer entry on the reveal region and keyboard focus
both raise the toggle to full opacity without changing layout.

- [ ] **Step 5: Convert `Sidebar.svelte` to the controlled contract**

Delete `phoneNavItems`, `.phone-nav`, `.phone-link`, `.phone-more`, and the fixed
tablet toggle. Keep the scrim and close button only for compact mode. Apply
`activateModalDrawer` while open, `inert`/`aria-hidden` while closed, and close
after a route selection without changing the saved desktop state.

- [ ] **Step 6: Implement desktop reflow and high-resolution canvas bounds**

Set `--sidebar-w: 256px`. Animate rail width/transform with shell tokens; remove
layout width when closed. Keep `.content` and `.sidebar` as independent
scrollers. Add `ResponsivePage.layout`, with 72 rem for `reading` and 90 rem for
`workspace`; map Chat/New Chat, Search Chat, and Guide to reading and all other
routes to workspace in `App.svelte`. At 1080p/4K/8K measure centering against
the `.content` inner box while the rail is open, and against both `.content` and
the viewport in collapsed focus state. Never scale type or controls.

- [ ] **Step 7: Run focused tests, type-check, and commit**

Run:

```bash
npm --prefix apps/web run test -- src/App.test.ts src/lib/components/Sidebar.test.ts
npm --prefix apps/web run check
```

```bash
git add apps/web/src/App.svelte apps/web/src/App.test.ts apps/web/src/lib/components/Topbar.svelte apps/web/src/lib/components/Sidebar.svelte apps/web/src/lib/components/Sidebar.test.ts apps/web/src/lib/components/ResponsivePage.svelte apps/web/src/lib/components/ResponsivePage.test.ts
git commit -m "Add the adaptive left workspace rail"
```

---

### Task 4: Turn the Build right rail into a small-screen drawer

**Files:**
- Modify: `apps/web/src/lib/views/BuildView.svelte`
- Modify: `apps/web/src/lib/views/BuildView.test.ts`
- Modify: `apps/web/src/lib/components/BuildSidePanel.svelte`

**Interfaces:**
- Consumes: `activateModalDrawer()` and the existing `railOpen` state.
- Produces: unchanged `BuildSidePanel` data props and `onclose`, with overlay
  semantics below 1024 pixels.

- [ ] **Step 1: Add failing responsive rail tests**

Stub compact `matchMedia`, open **Background work**, and assert the panel is a
right drawer with a scrim, `role="dialog"`, `aria-modal="true"`, focus trap,
Escape close, and focus restoration. In desktop mode, assert it remains an
`aside` and the Build grid gains its second column.

- [ ] **Step 2: Run the focused test and verify stacked behavior fails**

Run: `npm --prefix apps/web run test -- src/lib/views/BuildView.test.ts`

- [ ] **Step 3: Implement the overlay without changing the panel data flow**

Below 1024 pixels, position `.rail-slot` fixed at the right, add a sibling
scrim, and use the modal controller. Remove the old stacked/min-height rules.
At desktop widths retain `grid-template-columns: minmax(0, 1fr) 21rem` and no
modal attributes.

- [ ] **Step 4: Run tests and commit**

```bash
npm --prefix apps/web run test -- src/lib/views/BuildView.test.ts src/lib/modalDrawer.test.ts
npm --prefix apps/web run check
git add apps/web/src/lib/views/BuildView.svelte apps/web/src/lib/views/BuildView.test.ts apps/web/src/lib/components/BuildSidePanel.svelte
git commit -m "Make Build background work adaptive"
```

---

### Task 5: Add and enforce the memory user guide

**Files:**
- Create: `docs/guide/memory.md`
- Modify: `docs/guide/README.md`
- Modify: `docs/guide/working-in-chat.md`
- Modify: `raiker/guide/__init__.py`
- Modify: `tests/test_guide_surface.py`
- Modify: `docs/architecture/HYBRID_MEMORY_IMPLEMENTATION_PLAN.md`

**Interfaces:**
- Produces the in-product guide slug `memory` and a maintenance contract for
  future memory behavior changes.

- [ ] **Step 1: Add a failing guide-order test**

Assert `list_sections()` places `memory` after `working-in-chat`, and
`read_section("memory")` returns a page covering approval, recall provenance,
archive, forget, purge, incognito, retention, correction, and current semantic
fallback behavior.

- [ ] **Step 2: Run the guide test and verify `memory` is absent**

Run: `python -m pytest tests/test_guide_surface.py -q`

- [ ] **Step 3: Write the owner-facing guide**

Use the existing guide voice and structure. Explain what Raiker captures, what
requires approval, what enters a turn automatically versus through tools, how
scope/incognito/sensitivity filtering works, how sources appear, and what each
lifecycle action changes. Separate current behavior from post-Stage-J plans.

- [ ] **Step 4: Add navigation and the synchronization rule**

Add `memory` to `_READING_ORDER`, the guide index, and Chat cross-links. Add this
architecture requirement: changes to capture, candidate approval, retrieval,
ranking, correction, retention, tiering, archive, forget, purge, projections,
or privacy must update `docs/guide/memory.md` in the same change.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_guide_surface.py -q
git add docs/guide/memory.md docs/guide/README.md docs/guide/working-in-chat.md raiker/guide/__init__.py tests/test_guide_surface.py docs/architecture/HYBRID_MEMORY_IMPLEMENTATION_PLAN.md
git commit -m "Explain Raiker memory in the user guide"
```

---

### Task 6: Document Linux and macOS installation truthfully

**Files:**
- Modify: `README.md`
- Modify: `docs/guide/getting-started.md`
- Create: `scripts/validate_markdown_links.py`
- Create: `tests/test_validate_markdown_links.py`

**Interfaces:** The validator accepts one or more Markdown files/directories,
checks repository-relative Markdown links (ignoring HTTP, mail, and fragment-only
targets), prints each missing target, and exits non-zero on failure.

- [ ] **Step 1: Verify commands against current entry points and installers**

Confirm `raiker-app`, `raiker-web`, service commands, Python/Node floors, and
the source-build steps from `pyproject.toml`, `package.json`,
`scripts/build_installer.py`, and the host guide.

- [ ] **Step 2: Add concise README platform paths**

Keep the common quick start, then add Linux and macOS subsections with platform
prerequisites, virtual-environment activation, `npm ci`, dashboard build, and
`raiker-app`. State that current source installs are supported and generated
`.deb`/AppImage/`.pkg` artifacts are unsigned unless a release says otherwise.

- [ ] **Step 3: Expand Getting Started with operational details**

Linux covers distro package names, `python3 -m venv`, shell activation, loopback
launch, and user-service commands. macOS covers Homebrew prerequisites,
`python3.11 -m venv`, activation, launch, LaunchAgent service behavior, and
Gatekeeper expectations for unsigned local builds. Do not invent a Homebrew
formula or downloadable release URL.

- [ ] **Step 4: Add and test a repository-relative link validator**

Write focused tests for a valid relative file, a valid heading fragment, an
ignored external URL, a missing target, and a directory argument. Keep parsing
limited to ordinary inline Markdown links used by this repository.

Run: `python -m pytest tests/test_validate_markdown_links.py -q`

- [ ] **Step 5: Validate relative links and commit**

Run:

```bash
python scripts/validate_markdown_links.py README.md docs/guide docs/plans/WEB_UI_ADAPTIVE_SHELL_DESIGN.md docs/plans/WEB_UI_ADAPTIVE_SHELL_IMPLEMENTATION_PLAN.md
git diff --check
```

```bash
git add README.md docs/guide/getting-started.md scripts/validate_markdown_links.py tests/test_validate_markdown_links.py
git commit -m "Document Linux and macOS source installation"
```

---

### Task 7: Expand the page sweep and replace current screenshots

**Files:**
- Modify: `apps/web/e2e/ui-sweep-responsive-live.spec.ts`
- Modify: `docs/plans/screenshots/README.md`
- Replace: `docs/plans/screenshots/pages/*`

**Interfaces:**
- Consumes: existing 26-entry `ROUTES`, owner sign-in helper, and live host.
- Produces eight current-state images per route/tab: mobile, 1080p, 4K, and 8K,
  each in light and dark.

- [ ] **Step 1: Refactor matrices without changing route coverage**

Define:

```ts
const CAPTURES = [
  ["mobile", { width: 390, height: 844 }],
  ["1080p", { width: 1920, height: 1080 }],
  ["4k", { width: 3840, height: 2160 }],
  ["8k", { width: 7680, height: 4320 }],
] as const;
const THEMES = ["light", "dark"] as const;
```

Use a fresh context/page or `addInitScript` to set `raiker.theme` before the app
mounts for each theme, then navigate/reload. Assert `html[data-theme]` and the
ThemeToggle label (`Theme: light. Switch to dark.` or
`Theme: dark. Switch to system.`) agree before capture. Name files
`${size}-${theme}-${page}.png`.

- [ ] **Step 2: Add assertions for centered high-resolution bounds**

At 1080p/4K/8K, assert the responsive page width is no greater than its declared
72-rem/90-rem maximum, left/right free space inside `.content` differs by at
most one pixel when the desktop rail state is fixed, and collapsed focus state
is also viewport-centred. Assert text/control computed font sizes do not scale
with the viewport. Preserve overflow, icon, selected-tab, and console assertions.

- [ ] **Step 3: Run the black-box server helper help command**

Run:
`python C:/Users/1niki/.codex/skills/webapp-testing/scripts/with_server.py --help`

Use its documented interface to run a production build plus the real Raiker host
needed by the live spec. Do not duplicate server lifecycle code.

- [ ] **Step 4: Safely replace only the mutable page catalogue**

Resolve `docs/plans/screenshots/pages` to its absolute path, verify it is inside
the repository and exactly the intended directory, then remove its current
contents. Never remove files from `working/` or `not-working/`.

- [ ] **Step 5: Capture the complete matrix**

Run the live sweep with a timeout sufficient for 208 screenshots. Verify the
output count equals `26 routes × 4 sizes × 2 themes = 208` and every expected
name exists. Use viewport-only `page.screenshot({ path })` (never
`fullPage: true`). Read each PNG IHDR and assert width/height exactly match the
active viewport before accepting it.

- [ ] **Step 6: Visually inspect contact sheets and sampled originals**

Generate read-only contact sheets for each size/theme, inspect every page for
clipping, unintended hover, stale loading state, poor margins, or theme leakage,
and inspect original 4K/8K captures for at least Workbench, Chat, Build, Memory,
Models, Observability, Guide, and Settings. Fix UI defects and recapture the
entire affected matrix before proceeding.

- [ ] **Step 7: Update screenshot documentation and commit**

Record the eight-variant naming scheme, viewports, capture date, route count,
and the immutable boundary for historical evidence.

```bash
git add apps/web/e2e/ui-sweep-responsive-live.spec.ts docs/plans/screenshots/README.md docs/plans/screenshots/pages
git commit -m "Refresh every page across themes and display classes"
```

---

### Task 8: Full verification and final coherence review

**Files:**
- Modify only files needed to fix a demonstrated failure.

**Interfaces:** Validates every earlier task as one release candidate.

- [ ] **Step 1: Run the web workflow locally**

```bash
npm run lint
npm run check
npm run test
npm run build
npm run test:e2e:mocked
```

Expected: zero lint/type errors, all unit tests pass, production build succeeds,
and mocked Playwright passes.

- [ ] **Step 2: Run Python and documentation checks**

```bash
python -m pytest -q
python -m pytest tests/test_sqlcipher_memory_security.py tests/test_memory_sqlcipher.py -vv
python scripts/validate_markdown_links.py README.md docs/guide docs/architecture docs/plans
python scripts/validate_phase_status.py
python scripts/licensing_check.py
python -m ruff check .
python -m mypy raiker apps tests
python -m compileall -q raiker apps tests
git diff --check
```

Run the native CI-equivalent gate from `native/` as well:

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --all
```

- [ ] **Step 3: Re-read design, plan, and owner-facing docs together**

Confirm exact palette values, breakpoints, screenshot count, memory behavior,
and install commands agree. Search for stale black/gold palette claims,
bottom-navigation claims, stacked Build rail claims, and 1440-only screenshot
language.

- [ ] **Step 4: Check the final repository state**

Only intended source, test, documentation, and 208 current-page screenshots may
be changed. Generated `dist/`, caches, temporary workspaces, credentials, and
historical evidence folders must not be staged.

- [ ] **Step 5: Record the verified terminal state**

Run `git status --short`, `git diff --check`, and `git log -8 --oneline`. If a
demonstrated failure required a fix, return to the task that owns that file,
repeat its focused test and commit step, then rerun Steps 1–4 here. Do not create
an empty completion commit.

## Completion evidence

| Area | Result |
|---|---|
| Independent gate | Design and implementation plan both approved after two revision cycles; implementation began only after approval. |
| Web unit/type/lint | ESLint and Svelte check clean; 111 Vitest files passed with 974 tests passing and one intentional skip. |
| Browser verification | Seven mocked Playwright scenarios passed; the real-host live sweep passed all eight size/theme matrices with zero overflow, icon, selected-tab, console, theme, or centering failures. |
| Screenshot catalogue | 208 viewport-only PNGs: 26 route/tab states × mobile/1080p/4K/8K × light/dark. PNG dimensions are asserted from IHDR. |
| Python | Full pytest suite passed with CI's SQLCipher memory-security override; the two SQLCipher posture files also passed separately with the override removed. Ruff, mypy, and compileall passed. |
| Native | `cargo fmt --check`, Clippy with warnings denied, and all Rust tests passed. |
| Documentation/governance | Repository documentation consistency, phase/status, relative-link, and licensing checks passed. The memory guide is in the in-product reading order and its same-change maintenance contract is in the architecture plan. |
| Visual review | Mobile Workbench, Memory, Build, and Settings plus 1080p Workbench and 8K Guide were inspected at rendered/original resolution. A narrow Memory posture-card defect was fixed and all eight Memory variants were re-captured. |
