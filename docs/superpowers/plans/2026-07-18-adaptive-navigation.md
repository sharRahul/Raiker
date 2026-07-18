# Adaptive Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the phone icon rail with adaptive phone, tablet, and desktop navigation while retaining every governed route.

**Architecture:** Keep `Sidebar.svelte` as the sole renderer of the grouped route list. CSS media queries select a bottom bar plus drawer on phones, a trigger plus drawer on tablets, and the existing sidebar on desktop; a small local state machine opens and closes the drawer without changing routing or calling an API.

**Tech Stack:** Svelte 5, TypeScript, CSS media queries, Vitest, Testing Library, Vite.

## Global Constraints

- Phone: below 640px; tablet: 640px through 1023px; desktop: 1024px and wider.
- Keep `NAV_GROUPS` and `NAV_ITEMS` as the only route definitions; add no dependency or persisted preference.
- The drawer closes on route selection, scrim click, Escape, and returns focus to the opening control.
- Preserve all current API calls, recent-chat actions, theme controls, notifications, stop switch, and reduced-motion behaviour.

---

## File Structure

- Modify: `apps/web/src/lib/components/Sidebar.svelte` — drawer state, tablet trigger, phone bottom bar, and responsive CSS.
- Modify: `apps/web/src/lib/components/Sidebar.test.ts` — interaction regression for opening and closing the drawer.
- Modify: `apps/web/src/App.svelte` — bottom safe area for the phone bar.
- Modify: `apps/web/src/lib/components/Topbar.svelte` — tablet left clearance for the menu trigger.
- Modify: `apps/web/src/app.css` — extend touch-target coverage through tablet width.
- Modify: `docs/plans/2026-07-16-raiker-control-deck-implementation.md`, `docs/HANDOFF.md`, and `docs/IMPLEMENTATION_STATUS.md` — record the adaptive-navigation follow-up and only actual verification evidence.

### Task 1: Replace the narrow icon rail with adaptive navigation

**Files:**
- Modify: `apps/web/src/lib/components/Sidebar.svelte`
- Modify: `apps/web/src/lib/components/Sidebar.test.ts`

**Consumes:** `NAV_GROUPS`, `NAV_ITEMS`, and the existing sidebar’s recent-chat state.

**Produces:** A responsive primary navigation with a phone bottom bar and an accessible drawer for phone/tablet route discovery.

- [x] **Step 1: Write the failing interaction regression**

```ts
import { fireEvent, render, screen } from "@testing-library/svelte";

it("opens More navigation and closes it with Escape", async () => {
  render(Sidebar, { current: "new-chat" });
  const more = screen.getByRole("button", { name: "More navigation" });
  expect(more).toHaveAttribute("aria-expanded", "false");

  await fireEvent.click(more);
  expect(more).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("navigation", { name: "All navigation" })).toBeInTheDocument();

  await fireEvent.keyDown(window, { key: "Escape" });
  expect(more).toHaveAttribute("aria-expanded", "false");
  expect(more).toHaveFocus();
});
```

- [x] **Step 2: Run the focused test to verify RED**

Run: `npm --prefix apps/web run test -- --run src/lib/components/Sidebar.test.ts`

Expected: FAIL because there is no More navigation control or drawer state.

- [x] **Step 3: Implement one local drawer state machine and reuse the existing route list**

```ts
const PHONE_NAV_IDS = new Set(["new-chat", "sessions", "tasks", "projects"]);
let navigationOpen = $state(false);
let returnFocusTo: HTMLButtonElement | null = null;

function openNavigation(event: MouseEvent) {
  returnFocusTo = event.currentTarget as HTMLButtonElement;
  navigationOpen = true;
}

function closeNavigation() {
  navigationOpen = false;
  returnFocusTo?.focus();
  returnFocusTo = null;
}

$effect(() => {
  if (!navigationOpen) return;
  const onKeydown = (event: KeyboardEvent) => {
    if (event.key === "Escape") closeNavigation();
  };
  window.addEventListener("keydown", onKeydown);
  return () => window.removeEventListener("keydown", onKeydown);
});
```

Render four `NAV_ITEMS` links in a `.phone-nav` landmark and add the More
button. Keep the existing grouped links inside `.sidebar`, label that landmark
`All navigation`, and bind `class:open={navigationOpen}`. Each route anchor
calls `closeNavigation()` only while the drawer is open. Render a labelled
scrim button only while open and use the same `closeNavigation()` function.

```css
@media (max-width: 1023px) {
  .sidebar { position: fixed; inset: 0 auto 0 0; width: min(19rem, 84vw); transform: translateX(-100%); z-index: 100; }
  .sidebar.open { transform: translateX(0); }
  .tablet-toggle { display: inline-flex; position: fixed; top: 0.5rem; left: var(--space-3); z-index: 70; }
}
@media (max-width: 639px) {
  .tablet-toggle { display: none; }
  .phone-nav { display: grid; grid-template-columns: repeat(5, 1fr); position: fixed; inset: auto 0 0; z-index: 70; }
}
@media (min-width: 1024px) {
  .phone-nav, .tablet-toggle, .drawer-scrim { display: none; }
}
```

- [x] **Step 4: Run focused test to verify GREEN**

Run: `npm --prefix apps/web run test -- --run src/lib/components/Sidebar.test.ts`

Expected: PASS; all route links remain labelled, the active route remains
identified, and More opens/closes through keyboard input.

- [ ] **Step 5: Commit the isolated navigation change**

```powershell
git add apps/web/src/lib/components/Sidebar.svelte apps/web/src/lib/components/Sidebar.test.ts
git commit -m "Adapt control deck navigation by viewport"
```

### Task 2: Make the shell safe at tablet and phone widths

**Files:**
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/lib/components/Topbar.svelte`
- Modify: `apps/web/src/app.css`

**Consumes:** The fixed 40px touch target and the phone navigation created in Task 1.

**Produces:** Content that is never hidden beneath the phone bar and a tablet top bar that does not overlap the menu trigger.

- [x] **Step 1: Apply the three breakpoint-only shell rules**

```css
/* App.svelte */
@media (max-width: 639px) {
  .content { padding-bottom: calc(var(--space-5) + 4rem + env(safe-area-inset-bottom)); }
}

/* Topbar.svelte */
@media (min-width: 640px) and (max-width: 1023px) {
  .topbar { padding-left: calc(var(--space-3) + 2.75rem); }
}

/* app.css */
@media (max-width: 1023px) {
  .btn, .input, .select { min-height: 40px; }
}
```

- [x] **Step 2: Run the full web gates**

Run: `npm --prefix apps/web run check; npm --prefix apps/web run lint; npm --prefix apps/web run test; npm --prefix apps/web run build`

Expected: all commands exit 0 with no Svelte, TypeScript, lint, test, or production-build failures.

- [ ] **Step 3: Commit shell rules**

```powershell
git add apps/web/src/App.svelte apps/web/src/lib/components/Topbar.svelte apps/web/src/app.css
git commit -m "Protect adaptive shell at phone and tablet widths"
```

### Task 3: Verify live behaviour and record the handoff

**Files:**
- Modify: `docs/plans/2026-07-16-raiker-control-deck-implementation.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/superpowers/plans/2026-07-18-adaptive-navigation.md`

**Consumes:** The responsive shell and local web gate results from Tasks 1-2.

**Produces:** Disposable-workspace browser evidence and truthful implementation status.

- [x] **Step 1: Run a disposable-workspace browser session**

```powershell
npm --prefix apps/web run build
python -m apps.api.main --workspace C:\Temp\raiker-adaptive-navigation --port 8777 --no-browser
```

At 375px, verify the bottom bar and More drawer; at 768px, verify the topbar
menu trigger and drawer; at 1024px and 1440px, verify the full sidebar. Resize
one authenticated page across 375px, 768px, and 1024px without reload, use
Escape and the scrim, inspect browser console output, and save screenshots
under the existing untracked `output/playwright/` evidence directory.

- [ ] **Step 2: Run repository proof and review the diff**

```powershell
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/validate_runtime_enablement_readiness.py
python scripts/validate_local_single_user_runtime.py
python scripts/validate_documentation_truthfulness.py
git diff --check
git status --short
```

Expected: every validator and `git diff --check` exits 0; untracked existing
Playwright artifacts remain unstaged.

- [ ] **Step 3: Update only verified documentation and mark this plan**

Record the exact viewport evidence, commands, commit IDs, and workflow URLs in
the existing control-deck plan, handoff, and implementation status. Mark only
completed checkboxes in this plan; do not claim a GitHub workflow is green
until its exact commit has finished successfully.

- [ ] **Step 4: Push and verify exact-tip workflows**

```powershell
git add -f docs/superpowers/plans/2026-07-18-adaptive-navigation.md
git add docs/plans/2026-07-16-raiker-control-deck-implementation.md docs/HANDOFF.md docs/IMPLEMENTATION_STATUS.md
git commit -m "Record adaptive navigation verification"
git push origin main
gh run list --commit HEAD --limit 10
```

Expected: pushed commit has a green CI workflow, green Web UI workflow when a
web-path change triggers it, and green phase-status validation. Investigate and
fix any failed workflow before handoff.
