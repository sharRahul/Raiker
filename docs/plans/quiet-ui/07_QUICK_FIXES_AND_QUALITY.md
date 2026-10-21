# 07 Quick fixes and quality

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

## Quick fixes

Small changes to what is on screen today. Each is independent of the larger
redesign and can ship on its own.

| ID | Where | Now | Change | Status |
|---|---|---|---|---|
| QUI-Q01 | Home (`WorkbenchView.svelte`) | A tile reading "Runtime issues · 1": a large number and "Review configuration and readiness evidence before critical work." On a fresh workspace the one issue is "No model profile is selected." | Name each gap as a sentence with the action that fixes it. No model: "No model is set up" with **Set up model**, which opens the model setup dialog. Any other gap: its own sentence with **Open diagnostics**. No big number. | Done in this branch |
| QUI-Q02 | Home | Five start cards (conversation, build, design, task, projects) repeating the sidebar and the mode switch | Replaced by the Home composer and first-day starters | Covered by [QUI-H01](03_WELCOME_HOME_AND_CHAT.md#qui-h01--layout); not a quick fix |
| QUI-Q03 | Chat composer | Placeholder "How can I help you today?" | "What would you like Raiker to do?" | Done in this branch |
| QUI-Q04 | Chat composer | With no usable model, Send is disabled next to "Not selected" | Send stays enabled. Pressing it (or Enter) with no usable model opens the model setup dialog and keeps the draft | Done in this branch |
| QUI-Q05 | Chat header | A disabled, faded "New chat" on an empty conversation, and a "Background" toggle shown even when nothing runs | "New chat" appears once there is something to leave. The Background toggle appears only when background work is running, waiting, failed, or its panel is open; it stays reachable from the conversation menu | Done in this branch |
| QUI-Q06 | Top bar | Search, approvals, notifications and More are icons with accessible names but no visible tooltip | A tooltip on each icon-only control, using the same words as its accessible name | Done in this branch |
| QUI-Q07 | Home, Approvals count | Approvals icon always present | Keep it: it is Approvals' only top-level entry. The count already appears only when something waits | No change |
| QUI-Q08 | Colour | The proposed attention colour `#B8871B` fails contrast | Not a code fix: the shipped `--warn` (`#866412`) already passes. The palette decision is recorded in [QUI-V01](08_BRAND_AND_VISUAL_SYSTEM.md#qui-v01--colour-tokens) | No change |

## Quality foundations

### QUI-G01 — Size budgets in CI

Extend `web/e2e/all-pages-live.spec.ts` (it already walks every destination
from `destinations.ts`) to measure scroll height and visible controls:

* a destination page fits in one screen at 1440×900 and 1.25 screens at
  1280×800 with an empty workspace;
* a Settings sub-page fits in 1.5 screens;
* at most 60 interactive controls visible at once, excluding list rows.

Start as a report, then make it fail once the long pages are rebuilt.

### QUI-G02 — Word list

`web/src/lib/quietUiCopy.test.ts` already checks copy. Extend it to fail on
user-facing uses of: Observability, MCP (outside Connections › Advanced),
runtime (outside Settings › Advanced), journey, destination, expedition,
waypoint, trail, quest, arrived.

### QUI-G03 — State gallery

A development-only route that renders every shared component in its empty,
loading, working, needs-permission, error and done states, in light and dark.

### QUI-G04 — Speed

Typing never lags; a 1,000-message conversation scrolls smoothly (render only
visible messages); direct actions paint before their request returns and roll
back visibly on failure.

### QUI-G05 — Accessibility beyond axe

Axe already runs in `composer.spec.ts`. Add a keyboard-only walk through every
destination, and a 200% zoom check at 1280×800 where Send stays visible.

### QUI-G06 — Errors that say what to do

Review every user-facing error once: each names what failed, what it affected,
and one safe next step.

### QUI-G07 — Five people, five tasks

Before and after the redesign, watch five people: ask a question, compare
options, approve an email, connect Gmail, find last week's result. Measure time
to first useful result and where they hesitate.
