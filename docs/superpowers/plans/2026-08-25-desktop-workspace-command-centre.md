# Desktop Workspace Command Centre Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a noticeable desktop refresh with a fully hideable, better-organized navigation, a consistent layout/type/control system, individually reviewed views, and a freshly verified desktop screenshot catalogue.

**Architecture:** Keep route ownership and the App-controlled binary sidebar intact. Add disclosure state to the sidebar, extend `ResponsivePage` into named reading/workspace/operational/work-surface planes, and move conversation browsing into Search chats. Apply shared tokens first, then targeted owning-view fixes, and verify the result through unit/a11y tests plus the real-host desktop sweep.

**Tech Stack:** Svelte 5, TypeScript 5.7, CSS custom properties, Vitest/Testing Library, Playwright, real Raiker loopback host.

## Global Constraints

- Preserve route identifiers and keep every existing route reachable.
- Preserve the light/dark slate palette, steel-blue accent, governance gold, and bundled offline fonts/icons.
- Sidebar behavior remains binary: fully shown or fully hidden; no compact icon rail.
- Core routes stay visible; Knowledge, Manage, Observe, and Support are accessible disclosures that auto-open for the active route.
- Search chats must browse all chat sessions recent-first when its query is empty.
- Desktop type and controls never scale with viewport width.
- Reading prose stays near 68 characters; operational width is bounded near 112rem.
- Regenerate only the 156 desktop files in `docs/plans/screenshots/pages/`; preserve all 52 mobile files.
- No remote assets, new icon dependency, route removal, or unrelated runtime behavior change.

---

## File and responsibility map

- `apps/web/src/app.css`: palette relationships, spacing/type/control/grid tokens, shared hover/focus/menu contracts.
- `apps/web/src/App.svelte`: route-to-layout mapping, shell gutters, work-surface height, sidebar shown/hidden centering.
- `apps/web/src/lib/components/ResponsivePage.svelte`: reading/workspace/operational/work-surface layout interface.
- `apps/web/src/lib/nav.ts`: user-facing information architecture and stable group ids.
- `apps/web/src/lib/components/Sidebar.svelte`: accessible disclosure groups and removal of recent-chat data/menu behavior.
- `apps/web/src/lib/views/SearchChatView.svelte`: recent-first browsing plus query search.
- `apps/web/src/lib/views/SettingsView.svelte`: correct local grouping and grid-aligned local rail/save bar.
- `apps/web/src/lib/views/settings/*.svelte`: remove viewport-scaled padding/type and align settings sections to shared tokens.
- Hub and route view files: targeted page anatomy, grid span, card, table, and action alignment fixes found by the named route audit.
- `apps/web/e2e/ui-sweep-responsive-live.spec.ts`: desktop bounds, sidebar-state, icon, overflow, page/tab audit, and capture assertions.
- `docs/plans/screenshots/README.md` and `docs/plans/screenshots/pages/*.png`: current desktop evidence contract and output.

---

### Task 1: Establish the desktop layout and visual tokens

**Files:**
- Modify: `apps/web/src/app.css`
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/lib/components/ResponsivePage.svelte`
- Modify: `apps/web/src/lib/components/ResponsivePage.test.ts`
- Modify: `apps/web/src/lib/appCss.test.ts`
- Modify: `apps/web/src/lib/surfaceModel.test.ts`

**Interfaces:**
- Produces `type PageLayout = "reading" | "workspace" | "operational" | "work-surface"`.
- Produces `ResponsivePage` prop `layout?: PageLayout` and data attribute `data-layout`.
- Produces CSS tokens `--page-reading`, `--page-workspace`, `--page-operational`, `--prose-measure`, `--grid-columns`, `--grid-gap`, and desktop gutter tokens.

- [ ] **Step 1: Extend the failing bounds tests**

Assert the component accepts all four layouts, reading prose is `68ch`, workspace and operational maxima are named tokens, operational is `112rem`, and `work-surface` uses the shell's `--content-h` rather than a viewport clamp.

```ts
expect(source).toContain('"operational" | "work-surface"');
expect(css).toContain("--page-operational: 112rem");
expect(css).toContain("--prose-measure: 68ch");
expect(source).toContain("data-layout={layout}");
```

- [ ] **Step 2: Run the focused tests and record the expected failures**

Run: `npm --prefix apps/web run test -- src/lib/components/ResponsivePage.test.ts src/lib/appCss.test.ts src/lib/surfaceModel.test.ts`

Expected: FAIL because only reading/workspace exist and the named grid tokens are absent.

- [ ] **Step 3: Implement the tokens and component contract**

Use a single centered page grid:

```svelte
<section class={`page ${layout}`} data-layout={layout} data-testid="responsive-page">
  <div class="page-grid"><slot /></div>
</section>
```

```css
--page-reading: 72rem;
--page-workspace: 90rem;
--page-operational: 112rem;
--prose-measure: 68ch;
--grid-columns: 12;
--grid-gap: var(--space-4);
```

Map Chat and Build to `work-surface`, Guide and Search chats to `reading`, the hub/table/dashboard routes to `operational`, and remaining forms/mixed content to `workspace`. Tighten desktop content gutters without changing compact breakpoints. Remove global desktop viewport-dependent type sizing.

- [ ] **Step 4: Run focused tests and type-check**

Run:

```bash
npm --prefix apps/web run test -- src/lib/components/ResponsivePage.test.ts src/lib/appCss.test.ts src/lib/surfaceModel.test.ts
npm --prefix apps/web run check
```

Expected: PASS with no Svelte diagnostics.

- [ ] **Step 5: Commit the layout foundation**

```bash
git add apps/web/src/app.css apps/web/src/App.svelte apps/web/src/lib/components/ResponsivePage.svelte apps/web/src/lib/components/ResponsivePage.test.ts apps/web/src/lib/appCss.test.ts apps/web/src/lib/surfaceModel.test.ts
git commit -m "Add desktop workspace layout planes"
```

---

### Task 2: Reorganize the fully hideable sidebar

**Files:**
- Modify: `apps/web/src/lib/nav.ts`
- Modify: `apps/web/src/lib/nav.test.ts`
- Modify: `apps/web/src/lib/components/Sidebar.svelte`
- Modify: `apps/web/src/lib/components/Sidebar.test.ts`
- Modify: `apps/web/src/App.test.ts`

**Interfaces:**
- Changes `NavGroup` to `{ id: "core" | "knowledge" | "manage" | "observe" | "support"; label: string; collapsible: boolean; items: NavItem[] }`.
- Persists disclosure state under `raiker.navigation.groups` as a validated JSON string array.
- Keeps App's existing `desktopOpen`, `drawerOpen`, and `compact` props unchanged.

- [ ] **Step 1: Write failing information-architecture tests**

Assert Core contains Workbench, Chat, Build, Search chats, Tasks, and Projects; no Recent chats region or sessions/projects request is made; the other four groups expose buttons with `aria-expanded`/`aria-controls`; the active route's group is open; and an inactive group can toggle and persist.

```ts
expect(within(nav).getByRole("link", { name: "Search chats" })).toBeVisible();
expect(within(nav).queryByLabelText("Recent chats")).toBeNull();
expect(screen.getByRole("button", { name: "Manage" })).toHaveAttribute("aria-expanded", "true");
```

- [ ] **Step 2: Run the focused navigation tests**

Run: `npm --prefix apps/web run test -- src/lib/nav.test.ts src/lib/components/Sidebar.test.ts src/App.test.ts`

Expected: FAIL against the old Home/Work/Control/Utilities groups and recent-chat loader.

- [ ] **Step 3: Implement stable groups and accessible disclosures**

Delete Sidebar's recent session/project state, loaders, drag behavior, and menus. Render Core items directly. Render the other groups with a button and controlled list id. Validate persisted ids, make active-group expansion take precedence, and keep compact drawer route-close behavior.

```ts
const activeGroup = NAV_GROUPS.find((group) => group.items.some((item) => item.id === current));
const isOpen = (id: NavGroup["id"]) => id === activeGroup?.id || expanded.includes(id);
```

Style the active route with the governance-spine marker, one restrained hover cue, and a separate visible focus state. Keep the current binary desktop hide/show transition.

- [ ] **Step 4: Run navigation tests and accessibility checks**

Run:

```bash
npm --prefix apps/web run test -- src/lib/nav.test.ts src/lib/components/Sidebar.test.ts src/App.test.ts src/a11y.test.ts
npm --prefix apps/web run check
```

Expected: PASS; every route is reachable and the active group cannot remain collapsed.

- [ ] **Step 5: Commit navigation**

```bash
git add apps/web/src/lib/nav.ts apps/web/src/lib/nav.test.ts apps/web/src/lib/components/Sidebar.svelte apps/web/src/lib/components/Sidebar.test.ts apps/web/src/App.test.ts
git commit -m "Consolidate desktop navigation groups"
```

---

### Task 3: Turn Search chats into the conversation browser

**Files:**
- Modify: `apps/web/src/lib/views/SearchChatView.svelte`
- Modify: `apps/web/src/lib/views/SearchChatView.test.ts`

**Interfaces:**
- Empty trimmed query calls `api.sessions(undefined, false, "chat")` once and sorts by `updated_at` descending.
- Non-empty query debounces and calls the existing `api.searchChats(query)`.
- Both modes render the same session-row component and open `#/new-chat?session=<id>`.

- [ ] **Step 1: Replace the old empty-state test with failing browse tests**

Cover recent-first empty query, chat-origin request, untitled/zero-turn rows, populated query, no matches, project-scoped sessions, and opening a result.

```ts
expect(await screen.findByText("Most recent")).toBeInTheDocument();
expect(screen.getAllByRole("link", { name: /open conversation/i })[0]).toHaveAttribute(
  "href", "#/new-chat?session=sess_newest",
);
```

- [ ] **Step 2: Run the route test and verify the old prompt fails**

Run: `npm --prefix apps/web run test -- src/lib/views/SearchChatView.test.ts`

Expected: FAIL because an empty query currently clears `sessions`.

- [ ] **Step 3: Implement browse/search states and desktop hierarchy**

Load chat sessions on mount/empty query, use request ids to prevent stale results, group browse results by day, and change copy to sentence-case Search chats. Use the reading plane's prose/control alignment and a divider-row result treatment rather than one card per result.

- [ ] **Step 4: Run focused tests and type-check**

Run:

```bash
npm --prefix apps/web run test -- src/lib/views/SearchChatView.test.ts src/lib/components/Sidebar.test.ts
npm --prefix apps/web run check
```

Expected: PASS.

- [ ] **Step 5: Commit conversation discovery**

```bash
git add apps/web/src/lib/views/SearchChatView.svelte apps/web/src/lib/views/SearchChatView.test.ts
git commit -m "Make Search chats browse conversation history"
```

---

### Task 4: Align Settings and audit all nine sections

**Files:**
- Modify: `apps/web/src/lib/views/SettingsView.svelte`
- Modify: `apps/web/src/lib/views/SettingsView.test.ts`
- Modify: `apps/web/src/lib/views/settings/General.svelte`
- Modify: `apps/web/src/lib/views/settings/Personalisation.svelte`
- Modify: `apps/web/src/lib/views/settings/Privacy.svelte`
- Modify: `apps/web/src/lib/views/settings/Account.svelte`
- Modify: `apps/web/src/lib/views/settings/Runtime.svelte`
- Modify: `apps/web/src/lib/views/settings/Notification.svelte`
- Modify: `apps/web/src/lib/views/settings/SecurityLogin.svelte`
- Modify: `apps/web/src/lib/views/settings/WebAccess.svelte`
- Modify: `apps/web/src/lib/views/settings/GitCredential.svelte`

**Interfaces:**
- Settings local navigation remains page-owned and uses Personal/System group arrays derived from `SECTIONS`.
- Save bar occupies the content columns through the settings grid; it has no fixed `margin-left`.
- All section cards use fixed token padding, never `vw`-based `clamp()`.

- [ ] **Step 1: Add failing group/grid/type tests**

Assert Personal has six items, System has Web access/Git credential/Runtime, all nine deep links render their named heading, the save bar has a grid-aligned class, and settings sources contain no `clamp(...vw...)`.

```ts
expect(within(system).getByRole("button", { name: "Web access" })).toBeVisible();
expect(source).not.toMatch(/clamp\([^)]*vw/);
```

- [ ] **Step 2: Run Settings tests and record failures**

Run: `npm --prefix apps/web run test -- src/lib/views/SettingsView.test.ts src/lib/views/settings`

Expected: FAIL on current System heading placement, fixed save-bar offset, and viewport-scaled padding/title.

- [ ] **Step 3: Implement the local two-column grid**

Split sections by their declared group, render one labelled group at a time, align the sticky rail and content to shared columns, and place the save bar in the content column using the same grid. Replace settings-card clamps with `var(--card-pad-y)`/`var(--card-pad-x)`. Normalize local headings and controls to shared type/control tokens.

- [ ] **Step 4: Exercise every section and run type-check**

Run:

```bash
npm --prefix apps/web run test -- src/lib/views/SettingsView.test.ts src/lib/views/settings
npm --prefix apps/web run check
```

Expected: PASS for all nine section ids.

- [ ] **Step 5: Commit Settings alignment**

```bash
git add apps/web/src/lib/views/SettingsView.svelte apps/web/src/lib/views/SettingsView.test.ts apps/web/src/lib/views/settings
git commit -m "Align every desktop settings section"
```

---

### Task 5: Standardize controls, icons, menus, and interaction states

**Files:**
- Modify: `apps/web/src/app.css`
- Modify: `apps/web/src/lib/components/Icon.svelte`
- Modify: `apps/web/src/lib/icons.test.ts`
- Modify: `apps/web/src/a11y.test.ts`
- Modify: `apps/web/src/lib/components/ApprovalModeControl.svelte`
- Modify: `apps/web/src/lib/components/BuildModePicker.svelte`
- Modify: `apps/web/src/lib/components/ComposerMenu.svelte`
- Modify: `apps/web/src/lib/components/ModelPicker.svelte`
- Modify: `apps/web/src/lib/components/SessionMenu.svelte`
- Modify: `apps/web/src/lib/components/TabStrip.svelte`
- Modify their existing component tests.

**Interfaces:**
- Shared `.control`, `.menu-surface`, `.menu-item`, `.icon-button`, and `.tab-control` contracts use named size/type/hover/focus tokens.
- Existing component props and emitted actions remain unchanged.

- [ ] **Step 1: Add failing semantic and interaction tests**

Pin non-empty icon geometry, presentation vs labelled SVG semantics, explicit names for icon-only buttons, menu selection state, Escape dismissal, focus restoration, and visible focus styles. Add a source assertion that shared controls do not use viewport-sized fonts.

- [ ] **Step 2: Run focused component/a11y tests**

Run: `npm --prefix apps/web run test -- src/lib/icons.test.ts src/a11y.test.ts src/lib/components/ApprovalModeControl.test.ts src/lib/components/BuildModePicker.test.ts src/lib/components/ComposerMenu.test.ts src/lib/components/ModelPicker.test.ts src/lib/components/SessionMenu.test.ts src/lib/components/TabStrip.test.ts`

Expected: at least the new shared-token and focus-restoration assertions fail.

- [ ] **Step 3: Apply the shared contracts**

Retain the existing inline SVG paths and optical sizes. Normalize desktop controls to 40px, keep required 44px hit areas, align menu chevrons/checks, constrain menus to the viewport, and use one hover cue plus independent `:focus-visible`. Preserve reduced-motion and forced-colours behavior.

- [ ] **Step 4: Run focused tests, lint, and type-check**

Run:

```bash
npm --prefix apps/web run test -- src/lib/icons.test.ts src/a11y.test.ts src/lib/components
npm --prefix apps/web run lint
npm --prefix apps/web run check
```

Expected: PASS with no empty icon or keyboard/menu regressions.

- [ ] **Step 5: Commit interaction standards**

```bash
git add apps/web/src/app.css apps/web/src/lib/components apps/web/src/lib/icons.test.ts apps/web/src/a11y.test.ts
git commit -m "Standardize desktop controls and menus"
```

---

### Task 6: Review and refine every route and hub panel

**Files:**
- Modify: `apps/web/e2e/ui-sweep-responsive-live.spec.ts`
- Modify: `apps/web/src/lib/views/WorkbenchView.svelte`
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/BuildView.svelte`
- Modify: `apps/web/src/lib/views/SearchChatView.svelte`
- Modify: `apps/web/src/lib/views/TasksView.svelte`
- Modify: `apps/web/src/lib/views/ProjectsView.svelte`
- Modify: `apps/web/src/lib/views/MemoryView.svelte`
- Modify: `apps/web/src/lib/views/BrainView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/CapabilitiesView.svelte`
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Modify: `apps/web/src/lib/views/models/LocalLibraryPanel.svelte`
- Modify: `apps/web/src/lib/views/models/HuggingFacePanel.svelte`
- Modify: `apps/web/src/lib/views/models/DownloadsPanel.svelte`
- Modify: `apps/web/src/lib/views/models/ProviderUsagePanel.svelte`
- Modify: `apps/web/src/lib/views/models/ProvidersPanel.svelte`
- Modify: `apps/web/src/lib/views/ExtensionsView.svelte`
- Modify: `apps/web/src/lib/views/ConnectionsView.svelte`
- Modify: `apps/web/src/lib/views/McpView.svelte`
- Modify: `apps/web/src/lib/views/SkillsView.svelte`
- Modify: `apps/web/src/lib/views/ObserveView.svelte`
- Modify: `apps/web/src/lib/views/ActivityView.svelte`
- Modify: `apps/web/src/lib/views/SessionsView.svelte`
- Modify: `apps/web/src/lib/views/CheckpointsView.svelte`
- Modify: `apps/web/src/lib/views/DiagnosticsView.svelte`
- Modify: `apps/web/src/lib/views/WorkInActionView.svelte`
- Modify: `apps/web/src/lib/views/GuideView.svelte`
- Test: the corresponding existing `*.test.ts` file beside each changed view or panel.

**Interfaces:**
- Adds audit matrices for all 26 canonical route/tab states, all seven Models tabs, and all nine Settings sections.
- Each audit state asserts its selected local tab/section, named layout plane, page heading, horizontal containment, and non-scaling computed type/control sizes.

- [ ] **Step 1: Add the failing complete-view audit matrix**

Define `AUDIT_STATES` as the canonical 26 states plus Models `local/hosted/huggingface/activity/routing/pricing/posture` and Settings `general/notification/personalisation/security/privacy/account/web-access/git-credential/runtime`. For each state, assert page identity, selected tab/section, expected `data-layout`, no overflow, no empty visible SVG, and one aligned page canvas.

- [ ] **Step 2: Run the mocked desktop audit and record route-specific failures**

Run: `npm --prefix apps/web run test:e2e:mocked -- --grep "desktop view audit"`

Expected: FAIL where local max-widths, card grids, title anatomy, or selected-state alignment conflict with the new contracts.

- [ ] **Step 3: Fix operational/dashboard views**

Review Workbench, Tasks, Projects, Memory, Knowledge Map, Approvals, Permissions, Models and every Models tab, Extensions and every Extensions tab, and Observability and every Observability tab. Move local outer widths to the assigned plane, align headers/actions to grid columns, widen useful tables/panels, replace fragmented cards with rows/dividers where objects are not independent, and keep semantic status colour intact.

- [ ] **Step 4: Fix reading/work-surface views**

Review Chat, Build, Search chats, and Guide. Make Chat/Build fill `--content-h` without page scroll fighting their internal scrollers; align composers and work rails; keep Guide/Search prose near `68ch`; and preserve all compact breakpoint rules.

- [ ] **Step 5: Run each changed owner's unit test, then the audit**

Run:

```bash
npm --prefix apps/web run test -- src/lib/views
npm --prefix apps/web run test:e2e:mocked -- --grep "desktop view audit"
npm --prefix apps/web run check
```

Expected: PASS across every canonical route, Models tab, and Settings section.

- [ ] **Step 6: Commit the page-by-page refinements**

```bash
git add apps/web/src/lib/views apps/web/e2e/ui-sweep-responsive-live.spec.ts
git commit -m "Refine every desktop workspace view"
```

---

### Task 7: Refresh and inspect the desktop screenshot catalogue

**Files:**
- Modify: `apps/web/e2e/ui-sweep-responsive-live.spec.ts`
- Modify: `docs/plans/screenshots/README.md`
- Replace in place: `docs/plans/screenshots/pages/{1080p,4k,8k}-{light,dark}-*.png`
- Preserve: `docs/plans/screenshots/pages/mobile-*.png`

**Interfaces:**
- `RAIKER_SWEEP_CAPTURE=1080p,4k,8k` selects exactly three desktop sizes.
- Produces 156 current desktop PNGs with existing stable names and exact IHDR dimensions.

- [ ] **Step 1: Verify the capture helper and immutable boundaries**

Run:

```bash
python C:/Users/1niki/.codex/skills/webapp-testing/scripts/with_server.py --help
git status --short docs/plans/screenshots/pages
```

Record hashes/names for the 52 `mobile-*.png` files so the refresh can prove they did not change.

- [ ] **Step 2: Run the real-host desktop sweep**

Use the helper's documented interface to start the production build and real host, then run the live spec with `RAIKER_SWEEP_CAPTURE=1080p,4k,8k`. The spec must exercise both sidebar shown/hidden bounds before each canonical capture and write viewport-only screenshots.

- [ ] **Step 3: Verify catalogue completeness and dimensions**

Assert exactly 52 files for each desktop prefix, 156 desktop files total, all expected names present, each PNG IHDR matches 1920x1080, 3840x2160, or 7680x4320, and every recorded mobile hash is unchanged.

- [ ] **Step 4: Generate and inspect desktop contact sheets**

Create temporary contact sheets for all six size/theme matrices. Inspect every route for clipping, accidental hover, stale loading, weak contrast, uneven gutters, misaligned headings/actions, and theme leakage. Inspect original-resolution Workbench, Chat, Build, Memory, Models, Observability, Guide, and Settings at each desktop size. Fix and recapture the complete affected size/theme matrix when any defect is found.

- [ ] **Step 5: Update screenshot documentation**

Record the refresh date, preserved mobile boundary, 156 refreshed desktop files, 26 route/tab states, three desktop viewports, two themes, binary sidebar verification, and the extra Models/Settings audit coverage.

- [ ] **Step 6: Commit the catalogue**

```bash
git add apps/web/e2e/ui-sweep-responsive-live.spec.ts docs/plans/screenshots/README.md docs/plans/screenshots/pages
git commit -m "Refresh every desktop page catalogue view"
```

---

### Task 8: Full verification and coherence review

**Files:**
- No planned source changes. A failing check returns to the task that owns the affected file, followed by that task's focused test and a fresh full gate.

**Interfaces:**
- Validates the design spec and all prior task outputs as one release candidate.

- [ ] **Step 1: Run the complete web gate**

```bash
npm run lint
npm run check
npm run test
npm run build
npm run test:e2e:mocked
```

- [ ] **Step 2: Run documentation and repository checks**

```bash
python scripts/validate_markdown_links.py docs/superpowers/specs/2026-08-25-desktop-workspace-command-centre-design.md docs/superpowers/plans/2026-08-25-desktop-workspace-command-centre.md docs/plans/screenshots/README.md
python scripts/validate_documentation_truthfulness.py
git diff --check
```

- [ ] **Step 3: Reconcile implementation against the spec**

Confirm binary sidebar behavior, all five navigation sections, recent-first Search chats, unchanged routes, minimal palette changes, fixed desktop typography, four layout planes, complete Models/Settings audit, 156 refreshed desktop images, and untouched mobile images.

- [ ] **Step 4: Record final evidence**

Run:

```bash
git status --short
git diff --check
git log -10 --oneline
```

Do not claim completion unless every failing gate has been fixed and rerun fresh.
