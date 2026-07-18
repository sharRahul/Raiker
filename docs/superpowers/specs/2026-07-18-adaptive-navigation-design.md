# Adaptive navigation design

## Goal

Replace the permanent phone icon rail with navigation that adapts immediately
when the browser crosses phone, tablet, and desktop widths.

## Scope

- Phone, below 640px: show a fixed bottom bar for New Chat, Sessions, Tasks,
  Projects, and More. More opens the complete grouped route navigation in a
  drawer; no left rail consumes phone content width.
- Tablet, from 640px through 1023px: show a compact menu trigger in the top
  bar. It opens the same complete grouped route drawer without reserving a
  permanent side rail.
- Desktop, 1024px and wider: preserve the existing full sidebar.
- CSS media queries own the layout. A live window resize therefore changes the
  shell without route reloads or persisted device state.

## Components and behaviour

`Sidebar.svelte` remains the one source of the grouped route list, recent-chat
actions, and active-route state. It gains a drawer state shared by the phone
More button and tablet menu trigger. Selecting any route, pressing Escape, or
using the scrim closes the drawer and returns focus to the trigger. Desktop
never renders an overlay state.

`App.svelte` reserves safe bottom space for the phone bar. `Topbar.svelte`
makes room for the tablet menu trigger. The app keeps its current top bar,
theme control, stop switch, notification panel, API calls, and route model.

## Accessibility and error handling

- Primary phone links retain clear accessible names and identify the active
  route with `aria-current`.
- The drawer trigger exposes `aria-expanded`; the drawer has a named navigation
  landmark, a close control, and a keyboard Escape path.
- The scrim is a labelled button. Drawer action errors remain inside the
  existing recent-chat action UI.
- Reduced-motion preferences continue to suppress the drawer transition.

## Out of scope

No new router, dependency, API contract, persisted preference, or redesign of
individual route bodies. The full destination list remains reachable through
the existing grouped navigation; it is not duplicated in a new data model.

## Verification

- Add a Sidebar component test proving the More control opens and closes the
  grouped drawer, preserves every route link, and reports expanded state.
- Run web type-check, lint, full Vitest suite, and production build.
- Run a disposable-workspace browser check at 375px, 768px, 1024px, and 1440px;
  resize a live session across the boundaries, use the menu/drawer, capture
  screenshots, and inspect browser errors.

## Outcome

Implemented on 2026-07-18 with the specified 640px and 1024px boundaries. The
drawer regression test was observed failing before implementation and passes
afterward. A disposable authenticated browser session resized across
375/768/1024/1440px with no horizontal overflow or console errors; phone,
tablet, and desktop navigation each matched this design.
