# Quiet UI redesign plan

## Status

**Proposed, 2026-10-21. Nothing in this folder has shipped unless an item says
so.** These documents record the UI/UX direction agreed in the October 2026
design review and turn it into numbered, testable work items. They extend
[PERSONAL_AGENT_UX_SPEC.md](../PERSONAL_AGENT_UX_SPEC.md); where the two
disagree on layout or presentation, this folder is the newer decision. Neither
changes what Raiker is allowed to do: authority, approvals and lifecycle stay
owned by the runtime.

**Scope: laptop and desktop screens, in the web app and the Electron desktop
app.** Phones get a separate mobile app with its own layout later. Nothing in
these documents is designed for phone width.

## Product identity

Raiker is a personal, governed AI workspace. It should feel calm and effortless
for everyday work, and stay capable, transparent and approval-driven when it
acts. Priority order: productivity, then personal companion, then a light sense
of progress.

The name means wanderer or traveller. That survives as a quiet emotional layer
only: forward motion, continuity, a thin path line on real plans, and a
companion. It never appears as travel vocabulary in navigation or status
(no journey, destination, expedition, waypoint, trail, quest or arrived).

## Documents

| Document | Covers | IDs |
|---|---|---|
| [01 Layout system and pages](01_LAYOUT_SYSTEM_AND_PAGES.md) | The page audit, five page layouts, screen sizes, a new layout for every long page, size budgets | QUI-L01 – L14 |
| [02 Permissions and approvals](02_PERMISSIONS_AND_APPROVALS.md) | How permissions are set, asked and audited; the approval card; connection detail | QUI-P01 – P09 |
| [03 Welcome, Home and Chat](03_WELCOME_HOME_AND_CHAT.md) | First run as a setup conversation, Home, the anatomy of a chat turn | QUI-W01 – W06, QUI-H01 – H05, QUI-C01 – C12 |
| [04 Visual answers](04_VISUAL_ANSWERS.md) | Charts, comparisons, key figures and other answer blocks | QUI-A01 – A08 |
| [05 Raiker Browser](05_RAIKER_BROWSER.md) | A built-in browser in the desktop app, using the Chromium Electron already ships | QUI-B01 – B04 |
| [06 Features and improvements](06_FEATURES_AND_IMPROVEMENTS.md) | Features taken from the reference products, and product gaps | QUI-F01 – F23 |
| [07 Quick fixes and quality](07_QUICK_FIXES_AND_QUALITY.md) | Small fixes visible today, and the checks that keep quality from slipping | QUI-Q01 – Q08, QUI-G01 – G07 |
| [08 Brand and visual system](08_BRAND_AND_VISUAL_SYSTEM.md) | Colours, type, the app mark, the companion | QUI-V01 – V08 |

## Reference products

Two products were studied, and each document says which ideas came from where.

* **Hermes Agent** (Nous Research): open source. Read from its repository:
  `apps/desktop/DESIGN.md`, `src/app/master-detail.tsx`, the approval card,
  approval modes, connectors, clarify, quick-entry and first-run code.
* **Muse** (Meta): closed. Read from Meta's launch posts and design write-up,
  and from published reviews and coverage from September 2026. Details that
  only secondary sources report are marked as such.

From Hermes Raiker takes structure: list-and-detail pages, short settings
sub-pages, overlays for short tasks, flat surfaces, a clear approval card. From
Muse it takes tone: services instead of plumbing, decisions where the work
happens, app-drawn approval prompts that a model cannot fake, goals noticed in
conversation. It takes neither product's weak points: Hermes's five layout
modes and "Off" approval mode, Muse's feed, up-front data requests and
"Allow Always".

## Principles (Quiet UI)

1. **A page shows what you have; adding something new happens in a dialog.**
2. One obvious next action per screen. Fewer cards, no dashboard noise.
3. Technical detail only when it affects outcome, privacy, cost, scope or safety.
4. A sentence only when something is wrong or a choice needs explaining. Longer
   explanations are help articles.
5. Every status is true. No invented progress, percentages or "thinking" animation.
6. Status never relies on colour alone.
7. The model can propose; only the app can ask for consent.

## Build order

1. Quick fixes (07, QUI-Q01 – Q08).
2. Shared pieces: list-and-detail layout, settings row, Add dialog shell, help
   panel (01, QUI-L01 – L05).
3. Connections, Permissions, Models, Settings (01, 02).
4. Guide to help panel; Observability to Diagnostics and Recovery (01).
5. Size budgets in CI (07, QUI-G01).
6. Welcome, Home and Chat; the approval card; clarifying-question cards (03, 02).
7. Visual answers: key figures, comparison, horizontal bar, callout first (04).
8. Live work line, Quick Entry, goals noticed in conversation (06).
9. Task receipt, data label in the composer, Library, Make this repeatable (06).
10. Brand: tokens, mark, companion (08). Token and eye-orb work may start earlier
    because it touches nothing else.
11. Raiker Browser, step 1 (05), once the core workspace feels polished.

## How measurements were taken

The current `main` build was run against a fresh, empty workspace and every
destination in `web/e2e/destinations.ts` was captured at 1440×900. Heights are
full scroll heights. The capture spec was a throwaway and is not committed; the
existing `all-pages-live.spec.ts` sweep covers the same destinations and is
where the size budgets belong (QUI-G01).
