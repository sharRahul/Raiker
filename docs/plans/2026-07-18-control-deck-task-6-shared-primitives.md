# Control Deck Task 6 Shared Web Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the reusable Control Deck shell and small, authority-neutral web primitives that later route work can consume.

**Architecture:** Reuse the existing `Sidebar` and `NotificationCenter`; add four focused Svelte components. `App.svelte` consumes `ResponsivePage` while retaining routing/auth/bootstrap. `SessionMenu` exposes callbacks only, and `ToolControlBoard` filters server DTOs rather than deciding authority.

**Tech Stack:** Svelte 5, TypeScript, Vitest/Testing Library, existing FastAPI contracts.

## Global Constraints

- Do not add dependencies or backend routes.
- Keep all authority server-side; controls render only supplied server truth.
- Share copies only a current loopback hash URL; it never grants access.
- Rebuild no route body in Task 6; Tasks 7-9 consume the primitives.
- Preserve existing `Sidebar` and `NotificationCenter`; do not create duplicates.

---

### Task 1: Complete session contract coverage and prove component behavior

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/components/SessionMenu.test.ts`

**Interfaces:**
- `api.renameSession(id, title) -> Promise<{ ok: boolean; session_id: string; title: string }>`
- `api.archiveSession(id) -> Promise<{ ok: boolean; session_id: string; archived: boolean }>`
- `SessionMenu` consumes `{ sessionId, title, projectOptions, onRename, onMove, onPin, onArchive, onDelete }`.

- [ ] Write a failing component test that opens the menu, invokes rename/move/pin/archive/delete callbacks, and asserts copied share text starts with `window.location.origin + "/#"`.

```ts
it("keeps share local and forwards the six session actions", async () => {
  render(SessionMenu, { sessionId: "ses_1", title: "Brief", onRename, onMove, onPin, onArchive, onDelete });
  await fireEvent.click(screen.getByRole("button", { name: /session actions/i }));
  await fireEvent.click(screen.getByRole("button", { name: /copy local link/i }));
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/#/new-chat?session=ses_1"));
});
```

- [ ] Run `npm.cmd run test -- SessionMenu.test.ts` from `apps/web`; confirm RED because `SessionMenu` and the two typed methods do not exist.
- [ ] Add the two minimal methods to the existing `api` object. Do not add DTOs already represented by the backend response shape.
- [ ] Run the focused test again; it must remain RED until Task 2 adds the component.

### Task 2: Add focused shared primitives

**Files:**
- Create: `apps/web/src/lib/components/PageState.svelte`
- Create: `apps/web/src/lib/components/ResponsivePage.svelte`
- Create: `apps/web/src/lib/components/SessionMenu.svelte`
- Create: `apps/web/src/lib/components/ToolControlBoard.svelte`
- Modify: `apps/web/src/lib/components/NotificationCenter.svelte`
- Modify: `apps/web/src/lib/components/Sidebar.svelte`
- Modify: `apps/web/src/lib/components/SessionMenu.test.ts`

**Interfaces:**
- `PageState({ state: "loading" | "error" | "empty", title, detail? })`
- `ResponsivePage({ lead? })` provides named `title`, `actions`, and default slots.
- `ToolControlBoard({ gates, onDecision })` consumes `CapabilityGate[]`, renders only `!isDeferred(gate) && gate.can_current_principal_change`, and reports `(capability, mode)` through `onDecision`.

- [ ] Write failing tests for generic unread notifications and omission of a `blocked_reason_code: "activation_blocked:no_executor"` gate.

```ts
it("omits a gate without an executor", () => {
  render(ToolControlBoard, { gates: [makeGate({ capability: "finance_runtime", blocked_reason_code: "activation_blocked:no_executor" })], onDecision });
  expect(screen.queryByRole("group", { name: /decision mode/i })).not.toBeInTheDocument();
});
```

- [ ] Run `npm.cmd run test -- SessionMenu.test.ts`; confirm RED for the missing primitives.
- [ ] Implement only presentational components and callback plumbing. Reuse `isDeferred`, `DECISION_MODES`, `DECISION_MODE_COPY`, `Icon`, and existing CSS tokens. Rename `MCP notifications` to source-neutral `Notifications`; unread filtering remains unchanged.
- [ ] Apply the approved Manrope uppercase wordmark treatment to the existing sidebar `.brand-name` rule.
- [ ] Run `npm.cmd run test -- SessionMenu.test.ts`; confirm GREEN.

### Task 3: Migrate the shared shell and document the result

**Files:**
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/a11y.test.ts`
- Modify: `docs/plans/2026-07-16-raiker-control-deck-implementation.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/HANDOFF.md`
- Modify: `apps/web/README.md`

**Interfaces:**
- `App` keeps its existing hash route selection, authentication/bootstrap, project selection, sidebar, topbar, skip link, and main landmark while placing the active view inside `ResponsivePage`.

- [ ] Write a failing app test asserting the authenticated shell contains `ResponsivePage`'s lead wrapper and preserves the main landmark/skip link.
- [ ] Run `npm.cmd run test -- a11y.test.ts`; confirm RED because the shell does not yet use the primitive.
- [ ] Wrap the existing active-view conditional in `ResponsivePage`; add only responsive content padding/width CSS needed by the shared shell.
- [ ] Update Task 6 checkboxes and handoff/status/readme truth, including the explicit boundary that route-body migration is deferred to Tasks 7-9.
- [ ] Run `npm.cmd run check`, `npm.cmd run lint`, `npm.cmd run test`, and `npm.cmd run build` from `apps/web`; confirm GREEN.

### Task 4: Final evidence and release

**Files:**
- Modify: `docs/plans/2026-07-18-control-deck-task-6-shared-primitives.md`
- Modify: `docs/HANDOFF.md`

- [ ] Run the full Python suite in two alphabetical batches with `-p no:cacheprovider`; run ruff, mypy over `raiker apps tests`, compileall, all five validators, and `git diff --check`.
- [ ] Run an authenticated disposable-workspace browser drive: open the responsive shell, inspect the generic notification state, use every SessionMenu action against controlled test data, and capture screenshots.
- [ ] Record results and any tool/runtime limitation honestly in this plan and handoff; do not claim universal responsiveness beyond the verified viewport.
- [ ] Commit Task 6 on `main`, push `origin/main`, and wait for the exact pushed commit's CI and applicable Web UI workflow to be green.

## Plan Self-Review

- Coverage: Task 1 completes the missing typed endpoints and session behavior; Task 2 supplies every missing primitive while reusing existing components; Task 3 applies the approved shell rewrite; Task 4 supplies required validation and release evidence.
- Scope: no backend mutation, generic settings framework, duplicate sidebar/notification component, or route-body rewrite is included.
- Consistency: all later consumers use the interfaces named above; no server authority is moved into Svelte.
