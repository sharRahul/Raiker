# Raiker-informed web experience - Phase 1 evidence

> **Verification date:** 2026-07-23
> **Decision:** Phase 1 (shell, navigation, and visual cleanup) is complete.
> This phase changes presentation and accessibility only; it introduces no API,
> capability, authorization, persistence, or network contract.

## Delivered shell safeguards

- The wide sidebar, tablet drawer, and 375px bottom navigation preserve the
  Home, Work, Knowledge, Control, and Observe information architecture.
- A compact drawer is `inert` and `aria-hidden` until it is explicitly opened,
  so visually hidden drawer controls cannot intercept the keyboard route.
- Opening the compact drawer moves focus to its Close control; Escape restores
  focus to the invoking Menu/More control. The notification panel likewise
  dismisses with Escape and restores focus to its trigger.
- Shared compact shell controls meet a 44px touch-target floor. Light, dark,
  and system theme choices remain presentation-only. Reduced-motion mode also
  disables animated scrolling and collapses animations/transitions.

## Automated evidence

The focused RED/GREEN additions are retained in the normal web suite:

- `Sidebar.test.ts` verifies a closed compact drawer is inert/hidden and becomes
  reachable only after More is invoked.
- `Topbar.test.ts` verifies notification Escape dismissal and focus return.
- `appCss.test.ts` guards the 44px shell target and reduced-motion scrolling.
- `theme.test.ts` verifies light, dark, and system theme resolution without
  storing credentials or tokens.

The full web suite, type check, lint, and production build are required before
commit; their final command output is recorded with the commit handoff.

## Local-browser evidence

An authenticated disposable loopback workspace was inspected in a real browser
against the production build at 1280x800 and 375x812. The Workbench rendered
without horizontal overflow at 375px; the persistent STOP control and primary
bottom navigation remained visible. The initial narrow-screen keyboard route
entered the visible primary navigation rather than the closed drawer, and the
browser console reported zero errors and zero warnings.

The desktop/mobile captures and browser state were intentionally created under
the ignored `output/playwright/` directory for review, then removed before the
commit. They are verification artifacts, not source assets or release content.
