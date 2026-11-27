# Quiet UI redesign plan

## Status

**Proposed, 2026-10-21. Nothing in this folder has shipped unless an item says
so.** Shipped so far: the quick fixes and most quality checks in
[07](#07-quick-fixes-and-quality), two rounds of
[03](#status-2) (2026-10-21), and the layouts and the
Permissions, Connections, Models, Settings and help-panel plans in
[01](#status-1) (2026-10-21; L11 to L13 open), and
the approvals round of 02 (2026-10-22) and its Allow-with-limits round
(2026-11-08; 02 is closed and its open note is in [TO_BE_FIXED](TO_BE_FIXED.md#quiet-ui-permissions-and-approvals--open-items-document-closed-2026-11-08)), the visual answers
of 04 (2026-10-23, Pin 2026-10-26, diagrams 2026-11-08; 04 is closed and its
open notes are in [TO_BE_FIXED](TO_BE_FIXED.md#quiet-ui-visual-answers--open-items-document-closed-2026-11-08)), and the features and improvements of 06 in two rounds (2026-10-24 and
2026-10-26; 06 is closed and its one remaining item, the desktop companion, is
in [TO_BE_FIXED](TO_BE_FIXED.md#quiet-ui-features-and-improvements--open-items-document-closed-2026-10-26)), and on 2026-10-25 the brand of
[08](#status-3) (open ring, palette, Inter; the
companion open), Diagnostics as issue cards, Recovery, the pages that already
fit and Build and Design in [01](#status-1), and the
open items of earlier rounds (BUG-357, notices, expiry, streaming, the
conversation's profile). These documents record the UI/UX direction agreed in the October 2026
design review and turn it into numbered, testable work items. They extend
[Personal-agent UI and UX](PERSONAL_AUTONOMOUS_AGENT_SPEC.md#personal-agent-ui-and-ux); where the two
disagree on layout or presentation, this folder is the newer decision. Neither
changes what Raiker is allowed to do: authority, approvals and lifecycle stay
owned by the runtime.

**Scope: laptop and desktop screens, in the web app and the Electron desktop
app.** Phones get a separate mobile app with its own layout later. Nothing in
these documents is designed for phone width.

**2026-11-06 refinements:** connection-recovery work is recorded in
[07](#2026-11-06--qui-g06-connection-recovery),
the owner's cog/Models simplification in
[01](#2026-11-06--owner-requested-models-simplification),
and the cross-page shared UI pass in
[08](#2026-11-06--shared-ui-refinement-across-pages-and-subpages).
Projects error recovery is tracked in
[07](#2026-11-06--qui-g06-projects-recovery).
Approvals, Library and Sessions recovery is tracked in
[07](#2026-11-06--qui-g06-approvals-library-and-sessions-recovery).
On 2026-11-07 the owner chose a floating glass capsule for the composer and
its input-and-context slice shipped; see
[03](#2026-11-07--composer-control-deck). Its
execution-state slice (Stop and Queue in Send's place, follow-up pills, the
step drawer, Continue from last step) shipped the same day; see
[03](#2026-11-07--composer-execution-states).
Their implemented slices have live evidence; the unrelated open items and
release acceptance gates retain their status.

**2026-11-27 refinement:** Permissions now separates standing access from
action approvals and discloses routine summaries and technical details. Work
history uses Chats; Build target evidence is under Work details. The completed
design and verification record is [Permissions and work-page simplification](../architecture/PERMISSIONS_UI_REFINEMENT.md).

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
| [01 Layout system and pages](#01-layout-system-and-pages) | The page audit, five page layouts, screen sizes, a new layout for every long page, size budgets | QUI-L01 – L14 |
| 02 Permissions and approvals (closed 2026-11-08) | How permissions are set, asked and audited; the approval card; connection detail. Shipped as [FIXED-1125](FIXED_ITEMS.md#fixed-1125--an-unanswered-approval-waited-a-day-and-the-wait-could-not-be-set-qui-p06) to [FIXED-1135](FIXED_ITEMS.md#fixed-1135--nothing-checked-that-a-model-could-not-draw-an-approval-card-qui-p05-acceptance) and [FIXED-1360](FIXED_ITEMS.md#fixed-1360--an-approval-could-only-be-allowed-once-or-forever-qui-p03-qui-p05) to [FIXED-1365](FIXED_ITEMS.md#fixed-1365--approvals-hid-allow-for-this-task-when-accepting-only-records-found-this-round); the rest is in [TO_BE_FIXED](TO_BE_FIXED.md#quiet-ui-permissions-and-approvals--open-items-document-closed-2026-11-08) | QUI-P01 – P09 |
| [03 Welcome, Home and Chat](#03-welcome-home-and-chat) | First run as a setup conversation, Home, the anatomy of a chat turn | QUI-W01 – W06, QUI-H01 – H05, QUI-C01 – C12 |
| 04 Visual answers (closed 2026-11-08) | Charts, comparisons, key figures, diagrams and other answer blocks. Shipped as [FIXED-1136](FIXED_ITEMS.md#fixed-1136--a-turn-could-not-say-these-are-the-headline-numbers-qui-a04) to [FIXED-1149](FIXED_ITEMS.md#fixed-1149--a-chart-in-a-transcript-bubble-was-too-small-to-read-and-its-legend-had-no-colours-04-screenshot-review), [FIXED-1255](FIXED_ITEMS.md#fixed-1255--an-answer-block-could-not-be-pinned-to-a-project-04-pin-to-project) and [FIXED-1348](FIXED_ITEMS.md#fixed-1348--a-flow-or-a-structure-could-only-be-described-in-words-qui-a08); the rest is in [TO_BE_FIXED](TO_BE_FIXED.md#quiet-ui-visual-answers--open-items-document-closed-2026-11-08) | QUI-A01 – A08 |
| [05 Raiker Browser](#05-raiker-browser) | A built-in browser in the desktop app, using the Chromium Electron already ships | QUI-B01 – B04 |
| 06 Features and improvements (closed 2026-10-26) | Features taken from the reference products, and product gaps. Shipped as [FIXED-1150](FIXED_ITEMS.md#fixed-1150--nothing-outside-chat-said-that-work-was-running-qui-f04) to [FIXED-1167](FIXED_ITEMS.md#fixed-1167--two-long-transcript-tests-ran-at-their-time-limit-quality-found-this-round) and [FIXED-1252](FIXED_ITEMS.md#fixed-1252--the-same-aim-across-conversations-was-never-offered-as-a-goal-qui-f03) to [FIXED-1263](FIXED_ITEMS.md#fixed-1263--key-figures-read-1200-where-1200-was-meant-found-this-round); the rest is in [TO_BE_FIXED](TO_BE_FIXED.md#quiet-ui-features-and-improvements--open-items-document-closed-2026-10-26) | QUI-F01 – F23 |
| [07 Quick fixes and quality](#07-quick-fixes-and-quality) | Small fixes visible today, and the checks that keep quality from slipping | QUI-Q01 – Q08, QUI-G01 – G07 |
| [08 Brand and visual system](#08-brand-and-visual-system) | Colours, type, the app mark, the companion | QUI-V01 – V08 |

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
7. Visual answers: key figures, comparison, horizontal bar, callout first (04). Shipped 2026-10-23; diagrams 2026-11-08, and 04 closed.
8. Live work line, Quick Entry, goals noticed in conversation (06). Shipped 2026-10-24; goals noticed 2026-10-26.
9. Task receipt, data label in the composer, Library, Make this repeatable (06). Shipped 2026-10-24; the Library 2026-10-26.
10. Brand: tokens, mark, companion (08). Tokens and the mark shipped 2026-10-25; the companion waits for its art.
11. Raiker Browser, step 1 (05), once the core workspace feels polished.

## How measurements were taken

The current `main` build was run against a fresh, empty workspace and every
destination in `web/e2e/destinations.ts` was captured at 1440×900. Heights are
full scroll heights. The capture spec was a throwaway and is not committed; the
existing `all-pages-live.spec.ts` sweep covers the same destinations and is
where the size budgets belong (QUI-G01).

## 01 Layout system and pages

> Merged from `docs/plans/QUIET_UI_PLAN.md` on 2026-11-16; the original file was removed.

Part of the [Quiet UI redesign plan](QUIET_UI_PLAN.md). Proposed, 2026-10-21.

### Status

**Layouts and four page plans shipped 2026-10-21**
([FIXED-1101](FIXED_ITEMS.md#fixed-1101--the-shell-was-wider-and-looser-than-the-layout-system-qui-l01-qui-l14)
to [FIXED-1123](FIXED_ITEMS.md#fixed-1123--chats-readiness-steps-disappeared-with-the-models-overview-qui-l08);
live cases RT-QUI-17 to RT-QUI-25 in
[WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md)). **Diagnostics,
Recovery, the pages that already fit, and Build and Design shipped 2026-10-25**
([FIXED-1170](FIXED_ITEMS.md#fixed-1170--diagnostics-opened-on-seven-tiles-reading-ready-and-0-qui-l11)
to [FIXED-1175](FIXED_ITEMS.md#fixed-1175--design-had-no-revision-strip-and-builds-postures-said-edit-and-auto-qui-l13);
live cases RT-QUI-61 to RT-QUI-63 and RT-QUI-67).

| Item | State |
|---|---|
| Shell | **Done.** Sidebar 232 px, 40 px rows, one 1,180 px page width, 2rem gutter (1.5rem below 1,280 px). |
| QUI-L01 | **Done** through the shell sizes; Chat, Build and Design use the shared adaptive composer with surface-specific controls (03, L13; see DEC-COMPOSER-01). |
| QUI-L02 | **Done.** `ListDetail.svelte`, used by Connections, Channels, Permissions and My models. |
| QUI-L03 | **Done** for Security, Account, Privacy and General: rows, with forms in dialogs (`FormDialog.svelte`) and explanations in disclosures. Advanced › Runtime shows one line per environment with its detail on request. Other Settings sections keep their cards. |
| QUI-L04 | **Done.** `AddDialog.svelte`: Add connection, Add channel, Add model. It is a page-level layer, not a top-layer modal, so a sign-in window a step opens draws above it. |
| QUI-L05 | **Done.** The help panel. |
| QUI-L06 | **Done.** Category rail, policy in words, the detail pane, **Select several** and **Group by technical area** in **⋯**. A **Schedules** category was added. Deviation: *Not decided here* and *How your permissions apply* stay as read-only disclosures under **Advanced** rather than help articles, because they show this account's live data. |
| QUI-L07 | **Done.** |
| QUI-L08 | **Done.** Deviation: the global spending limit lives in **Settings → Advanced → Usage and spending**, beside spend across providers, rather than on Models. |
| QUI-L09 | **Done.** Deviation: Account is part of **General** rather than its own section. |
| QUI-L10 | **Done.** The Guide page is gone; `#/guide…` opens the panel. |
| QUI-L11 | **Partly done.** Overview is *What needs attention* with one card per issue and healthy systems folded (FIXED-1170); Checkpoints is **Recovery**, and a restore first says what will be undone and what stays, with Restore never the dominant button (FIXED-1171). Recovery from the affected task shipped 2026-11-17 ([FIXED-1498](FIXED_ITEMS.md#fixed-1498--recovery-could-not-be-reached-from-the-task-that-changed-files-qui-l11)). Sessions moved to Work › Threads and each project lists its activity and opens its own Recovery (2026-11-18, [FIXED-1509](FIXED_ITEMS.md#fixed-1509--sessions-lived-in-diagnostics-instead-of-work--threads-qui-l11), [FIXED-1510](FIXED_ITEMS.md#fixed-1510--a-project-had-no-activity-of-its-own-and-its-recovery-link-opened-everything-qui-l11)); a task's activity is its History. Open: live work on Home only. |
| QUI-L12 | **Done**, except Projects, which stays a card grid. Work pages after 50 rows with 64 px thread and goal rows (FIXED-1172); Memory's map opens from Memories and Recall folds into Controls (FIXED-1173); Approvals' evidence is closed below 1,600 px (since 2026-10-22); Connections › Advanced is one segmented list. |
| QUI-L13 | **Done.** Design's revision strip of three 56 px thumbnails; Build's postures are Plan · Suggest changes · Run within limits (FIXED-1175). Build's rail and side panel were already closed by default, and Design's export already existed only once a picture did. |
| QUI-L14 | **Done.** 1,024–1,279 px shows the icon rail. |
| Acceptance | **Partly met.** No destination shows a catalogue; old addresses forward. Size: every destination fits its budget at 1440×900, and the budgets are a failing check since 2026-11-15 ([FIXED-1460](FIXED_ITEMS.md#fixed-1460--tasks-ran-9-px-past-one-screen-and-the-size-budgets-were-only-a-report-qui-g01)). |

### The problem, measured

Work surfaces already fit on one screen at 1440×900 with an empty workspace:
Home, Chat, Build, Design, Work, Memory and Approvals. They hold the owner's
data, so they will grow; they need list and search patterns, not new layouts.

The setup and settings pages do not fit, and they are long **without any data**.
Their length comes from catalogues, forms and explanations:

| Page (route) | Height | Notes |
|---|---:|---|
| Guide (`guide`) | 11,797 px | 4,011 words, 13 screens |
| Extensions › Channels (`extensions?tab=channels`) | 4,313 px | |
| Extensions › Connectors (`extensions?tab=connectors`) | 4,198 px | 27 status rows, then the same 27 as install cards; 156 controls |
| Models › Add model (`models?tab=add`) | 3,779 px | 16 providers, local setup and Hugging Face at once |
| Permissions (`capabilities`) | 3,712 px | 294 controls; 38 rows × 4 inline buttons |
| Models › Runtime & routing | 2,941 px | |
| Settings › GitHub | 2,524 px | |
| Settings › Security | 2,424 px | Five forms open at once |
| Settings › Privacy | 2,064 px | |
| Models › My models | 2,021 px | |
| Settings › Runtime configuration | 1,816 px | |
| Models › Usage | 1,662 px | |
| Observability › Overview | 1,278 px | |

### How the reference products keep pages short

**Hermes** (from `apps/desktop/DESIGN.md` and `src/app/master-detail.tsx`):

* List and detail everywhere. Capabilities, Skills, MCP and Messaging share one
  scaffold: a 14rem rail of dense, same-height rows and a roomy centred detail
  pane (`max-w-2xl`). Long lists never become long pages.
* Short tasks are overlays. Settings, Cron, Profiles and Agents open as overlay
  cards and return to the previous route on close.
* Settings are short sub-pages. A parent label opens its first child, never an
  overview. Each row is a label, a description and one control (`ListRow`).
* Flat, not boxed: no card inside a card, no dividers between rows, spacing over
  borders. Empty lists hide their search field.

**Muse:** few top-level places (chat, goals, files, plus a feed and ideas tab
Raiker does not copy). Setup is not a destination. Connectors are recognisable
apps with an access level each.

Together: **a page shows what you have; adding something new happens in a
dialog.** Raiker currently puts the whole catalogue of what you could add on the
page itself, which is why Connections, Channels and Add model are 4–5 screens.

### Shell

| Element | Decision |
|---|---|
| Sidebar | 232 px. Rows 40 px. Home, Chat, Build, Design, Work, Memory, then More. (Now 256 px: `--sidebar-w` in `web/src/app.css`.) |
| Top bar | 56 px: page context, search, approvals count (only when something waits), notifications, live work line (06, QUI-F04) |
| Content gutter | 32 px desktop, 24 px narrow window |
| Standard content max width | 1,180 px |
| Reading / transcript width | 680–760 px |
| Side panel (context rail) | 320 px, at most 360 px, closed by default |

### Screen sizes (QUI-L14)

| Size | Behaviour |
|---|---|
| Desktop, 1920×1080 and up | Content keeps its maximum widths. Extra space becomes margin, never longer lines. Two side panels may be open together (for example Build's files and checks). |
| Laptop, 1440×900 | The reference size. Every budget is measured here. List and detail side by side; one side panel open at a time. |
| Small laptop, 1280×800 | Sidebar stays 232 px. A side panel opens over the content instead of squeezing it. Approvals' evidence panel opens on request. |
| Narrow window, 1024–1279 px | Sidebar becomes a 64 px icon rail. 1024×680 is the desktop app's minimum window size. |
| Web, below 1024 px | A single readable column with no separate design. Phones get the mobile app. |

### The five layouts

Every page uses exactly one.

#### QUI-L01 — A · Workspace

Rail, work column, context panel, composer anchored at the bottom of the work
column. Used by Chat, Build and Design. Already in place; rails closed by
default.

#### QUI-L02 — B · List and detail

Header with tabs and search; a list of 56–72 px rows on the left; the selected
item on the right, at most 680 px wide. Used by Permissions, Connections,
Models, Work, Memory and Approvals. A shared Svelte component, with a draggable
split that cannot shrink the list below a readable row (Hermes clamps at
180 px list, 320 px detail).

Acceptance: keyboard up/down moves selection; Enter opens; the selected item has
its own address so it can be linked; an empty list hides its search field.

#### QUI-L03 — C · Settings

Section rail (224 px) and a content column (at least 680 px). Every setting is a
row: label, current value, one action. Forms (change password, vault key, breach
check, standing grant) open in a dialog, not inline. A sub-page is at most 1.5
screens. A Save bar appears only after a change.

#### QUI-L04 — D · Add dialog

A 640 px centred dialog: search, categories, one card per option, then the
chosen option's steps. Used by Add connection, Add channel, Add model, Add
memory. Choose the source first; later steps show only that source.

#### QUI-L05 — E · Help panel

A 360 px panel opened from **?**, starting on the article for the current page,
with search. The command palette searches the same articles under a Help group.
Replaces the Guide page.

### Page plans

#### QUI-L06 — Permissions

Target: one screen, about 50 controls (from 3,712 px and 294 controls).

* Header: active profile in one line ("Standard · Raiker researches and
  prepares; it asks before sending, deleting or paying").
* Layout B with a category rail: Overview, Files & code, Web, Messages &
  services, Memory, Schedules, then **Advanced** (collapsed).
* **Overview** keeps only "What Raiker can do for you" (the seven plain
  sentences) and the Set up for Build card.
* Rows show the current policy as text. The four-way choice (Ask me, Allow,
  Automatic, Never) moves into the detail pane: one control at a time instead of
  152 inline buttons.
* The 16 "System and runtimes" rows move under Advanced.
* "Common permissions" is removed; it repeats rows that exist.
* Bulk select and Group by move into an overflow menu.
* "Not decided here" and "How your permissions apply" become help articles.

Details of the permission model: [Permissions guide](../guide/permissions-and-runtime-modes.md) (plan 02, closed 2026-11-08).

#### QUI-L07 — Connections (renamed from Extensions)

Target: one screen (from 4,198 px).

* The page lists only what is connected. With nothing connected: one sentence
  and **Add connection**.
* **Add connection** opens the catalogue in layout D. This removes 54 repeated
  blocks from the page.
* The four readiness tiles are removed. The one that matters, a missing vault
  key, becomes one attention row shown only when true.
* Seven tabs become three: **Services**, **Channels**, **Advanced** (MCP
  servers, skills, hooks, plugins as one segmented list). Overview is removed.
* Channels uses the same pattern: connected channels plus an Add channel dialog.
* GitHub moves here from Settings, because it is a service you connect.
* Connection detail: QUI-P04, [FIXED-1363](FIXED_ITEMS.md#fixed-1363--a-connection-was-on-or-off-with-nothing-between-qui-p04).

#### QUI-L08 — Models

Target: one screen (from 3,779 px on Add model).

* One page, no tabs. The top card is the current execution profile: model, ready
  or not, local or hosted, the main privacy and cost trade-off, and Change.
* Below it, **My models** in layout B.
* **Add model** is a three-step dialog. Step 1: On this computer · An account I
  have · Hugging Face · Custom endpoint. Step 2 shows only the chosen source.
  Step 3: review privacy, cost, default and readiness.
* **Usage** becomes a panel in each model's detail.
* **Runtime & routing** moves to Settings › Advanced.
* "Model setup" and "Global model" stop repeating above every tab; the profile
  card replaces both.

#### QUI-L09 — Settings

Target: each sub-page at most 1.5 screens.

Rail: General, Personalisation, Notifications, Security, Privacy, Execution
profiles, Web access, Advanced, About & updates.

* Account folds into General. Runtime configuration and Memory engine move to
  Advanced. GitHub moves to Connections.
* Security as rows: Password (changed 3 weeks ago · Change), Two-step sign-in
  (off · Turn on), Devices (1 signed in · Manage), Vault key (missing · Set up),
  Encryption (on · Details), Standing access (none · Manage).
* Developer detail (the Fernet key command, the SQLCipher version) moves behind
  "Technical details" inside the vault dialog.

#### QUI-L10 — Guide becomes the help panel

Target: no page (from 11,797 px).

* Each current Guide heading becomes one article with its own address, so old
  links still land somewhere.
* **?** opens the help panel on the current page's article.
* The explanations removed from Permissions, Models and Settings become articles.

#### QUI-L11 — Observability becomes Diagnostics and Recovery

* Overview becomes **Diagnostics**: "What needs attention", one card per issue
  (observed problem, impact, last check, safe fix, technical details), healthy
  systems collapsed. With no issues, one line.
* Sessions move to Work › Threads (searchable). Activity appears inside each
  task or project. Checkpoints become **Recovery**, reached from the affected
  task or project. Live work moves to Home › In progress. Notifications is the
  top-bar centre.
* The word Observability leaves navigation. Old addresses forward
  (`ROUTE_ALIASES` in `web/src/lib/nav.ts`). **Done 2026-10-21**: the
  destination is called Diagnostics ([FIXED-1095](FIXED_ITEMS.md#fixed-1095--user-facing-copy-used-words-the-plan-retires-qui-g02));
  the rest of this item is open.

Recovery, before restore, shows: checkpoint source and time, affected items,
what will be undone, what remains, Create safety checkpoint, and Restore.
Restore is never the dominant button.

#### QUI-L12 — Pages that already fit

| Page | Layout | Change |
|---|---|---|
| Home | Single column, 980 px | See [03](#03-welcome-home-and-chat). |
| Chat, Build, Design | A | Composer specs in 03. No size change. |
| Work (Threads, Goals, Tasks, Projects) | B | 64 px rows with the selected item beside them. Paginate after 50 rows. |
| Memory | B | Knowledge map leaves the tabs and opens from search results. Recall folds into Controls. |
| Approvals | B | Queue and decision side by side; evidence panel closed below 1,600 px. |
| Connections › Advanced | B | One segmented list instead of four tabs. |

#### QUI-L13 — Build and Design specifics

Kept from the October decision record:

* **Build**: repository rail 248 px (hidden without a repository), centre
  640–800 px, right panel 320 px (Plan, Checks, Approvals, Evidence, closed by
  default). Diff review is its own state, 60/40 diff and file list on wide
  screens. Postures above the composer: Plan · Suggest changes · Run within
  limits, with the chosen posture's consequence in one line.
* **Design**: asset rail 224 px, canvas (560 px minimum), inspector 304 px,
  composer 560–720 px centred under the canvas. Export disabled until a result
  exists. After output exists, a revision strip of up to three 56 px thumbnails
  above the composer.

### Acceptance for this document

* Every destination fits its budget at 1440×900 and 1280×800 with an empty
  workspace ([07, QUI-G01](#07-quick-fixes-and-quality)).
* No destination shows a catalogue of things that could be added.
* Every removed page's old address opens its new home.

### 2026-11-06 — Owner-requested Models simplification

The owner requested a cog in place of the top-bar settings dropdown's three
dots, and simpler Models and all its subpages. This supersedes the earlier
REM-POPUP-01 icon choice; the dropdown keeps its existing destinations.
The following refinement applies QUI-L03/L04/L08 and the Quiet UI principles:
short pages, one next action, technical detail on request, truthful status.

1. [x] Restore the settings cog without changing the dropdown destinations.
2. [x] Remove duplicate first-use Add actions and irrelevant comparison controls.
3. [x] Keep model defaults and usage available without showing every edit at once.
4. [x] Make Add's provider privacy/network details a disclosure.
5. [x] Remove repeated source headings and decorative eyebrows.
6. [x] Make hosted/custom provider choices compact rows.
7. [x] Keep provider connection/readiness and consequential privacy facts visible.
8. [x] Separate optional local installation/pull tools from choosing a local server.
9. [x] Make local rows fit the Add dialog without squeezing text into a sliver.
10. [x] Fit Hugging Face's catalogue to its actual panel, including search and review.
11. [x] Reduce Hugging Face's repeated introductory content.
12. [x] Keep model details short; put telemetry and context overrides on request.
13. [x] Separate serving, library, activity and advanced model settings.
14. [x] Keep Work defaults/fallback disclosures visible outside tuning controls.
15. [x] Verify keyboard navigation, both themes and supported laptop widths;
    update retained tests, guide, fixed-item evidence and CI.

Implementation and running-host evidence are recorded in
[Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-models-simplification-and-settings-cog).

No model/provider choice, capability, permission, fallback, credential scope or
billing rule changes. Existing addresses remain supported. This document stays
open for its unrelated QUI-L11 and acceptance work.

## 03 Welcome, Home and Chat

> Merged from `docs/plans/QUIET_UI_PLAN.md` on 2026-11-16; the original file was removed.

Part of the [Quiet UI redesign plan](QUIET_UI_PLAN.md). Proposed, 2026-10-21.

### Status

**First round shipped 2026-10-21** ([FIXED-1057](FIXED_ITEMS.md#fixed-1057--home-had-no-way-to-start-work-by-asking-qui-h01)
to [FIXED-1074](FIXED_ITEMS.md#fixed-1074--home-said-no-model-is-set-up-while-a-chat-was-answering);
live cases RT-QUI-01 to RT-QUI-09). **Second round shipped 2026-10-21**
([FIXED-1080](FIXED_ITEMS.md#fixed-1080--home-offered-five-threads-to-continue-instead-of-the-one-with-its-next-step-qui-h01)
to [FIXED-1094](FIXED_ITEMS.md#fixed-1094--setup-had-no-way-to-skip-it-qui-w06);
live cases RT-QUI-10 to RT-QUI-13 and RT-QUI-16). Both in
[WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md).

| Item | State |
|---|---|
| QUI-H01 | **Done**, with the profile chip on Home's composer since 2026-10-22 ([FIXED-1130](FIXED_ITEMS.md#fixed-1130--a-conversation-could-not-say-how-careful-raiker-should-be-qui-p02)). Greeting with one true fact, composer with Attach, one Continue card with its next step, one decision row, at most two in-progress rows, This week, and one 980 px column. |
| QUI-H02 | **Done**, without the companion: the companion's art does not exist yet ([08, QUI-V05](#qui-v05--companion)). |
| QUI-H03 | **Done.** Home is the default and Settings → General can choose Chat; the option now reads Home. |
| QUI-H04 | **Done.** The line names the version; a count of changes needs release notes the host can read. |
| QUI-H05 | **Done.** Stale means the newest *verified* backup is seven days old, the same window as *This week*. |
| QUI-C01 | **Done**: editable title, project chip, search in conversation, Context toggle. |
| QUI-C02 | Already true before this round; unchanged. |
| QUI-C03 | **Done**: the status line, follow-ups queued from the prompt and Stop safely in Send's place (2026-11-07, [execution states](#2026-11-07--composer-execution-states)), the outcome line, and the task receipt at the end of each turn (2026-10-24, [QUI-F16, FIXED-1153](FIXED_ITEMS.md#fixed-1153--a-tasks-end-did-not-say-what-it-used-read-changed-or-sent-qui-f16); per task in Tasks, [FIXED-1261](FIXED_ITEMS.md#fixed-1261--a-background-task-had-no-receipt-qui-f16-found-this-round)). |
| QUI-C04 | **Partly done.** Done: the placeholder, the data label and the profile chip (QUI-P02, 2026-10-22); answer style is in Settings › General until *More* exists (04, closed; [FIXED-1145](FIXED_ITEMS.md#fixed-1145--there-was-no-way-to-ask-for-fewer-or-more-visuals-04-answer-style), 2026-10-23). *More* decided 2026-11-17: the composer's **Tools** menu is *More* (Schedule it and Run in background are there); research depth waits for a research mode with depths. |
| QUI-C05 | **Done.** |
| QUI-C06 | **Done.** |
| QUI-C07 | **Done.** Tabs: Context (files in use), Memories (2026-11-17, [FIXED-1491](FIXED_ITEMS.md#fixed-1491--chats-context-panel-did-not-list-the-memories-a-turn-was-given-qui-c07)), Plan, Sources, Activity. |
| QUI-C08 | **Done.** |
| QUI-C09 | Already true before this round: Edit and Retry make a new turn and keep the earlier one. |
| QUI-C10 | **Done**, without the companion. |
| QUI-C11 | **Done** in the composer's **Tools** menu, because *More* does not exist yet (QUI-C04). The task shows in Background work and Home's In progress. |
| QUI-C12 | **Done.** Below 1,920 px the panel opens over the transcript and ends above the composer; from 1,920 px it sits beside it. |
| QUI-W01 | **Done.** The owner chose the open ring on 2026-10-25 ([QUI-V04](#qui-v04--app-mark-the-open-ring), [FIXED-1168](FIXED_ITEMS.md#fixed-1168--the-app-mark-was-the-eye-orb-qui-w01-qui-v03-qui-v04)); it is on the lock screen, the sidebar and every icon. |
| QUI-W02 | **Done**, without the companion pick (no art yet). The stored `welcome` stage is the Hello step; the name is saved to Settings › Account. |
| QUI-W03 | **Done.** On this computer shows what this device can run; keys go in the provider card's secure field. |
| QUI-W04 | **Done.** |
| QUI-W05 | **Done.** The first message opens Chat and the conversation is renamed *Getting started*. |
| QUI-W06 | **Done**: Skip setup, Run setup again, and a progress line of real steps (Name · Model · Privacy · Start on a desktop install). |

**Starters.** The four are *Summarise a document*, *Plan my week*, *Fix a bug
in a repository* and *Make an image* (`web/src/lib/starters.ts`). The first two
fill the composer; the last two open Build and Design.

### Reference products

* **Hermes**: chat is the home surface. First run is a guided setup
  conversation ("Hi, I'm Hermes. Let's set things up for you. Then we'll get
  something cool done.") with steps for name, appearance, apps, a tour and a
  first task, and **Skip setup** always available. It recommends a local model
  when the hardware fits. Status never fabricates progress; a resumed
  conversation is never replaced by a greeting.
* **Muse**: onboarding asks your name and lets you name the agent, then suggests
  connecting accounts. Its design write-up keeps conversation for what
  conversation does well and uses fixed UI for approvals and credentials. A
  snippet of current work shows under the agent's avatar.

### Welcome (first run)

The first run **is a chat**: setup happens in a setup conversation. Every choice
is a card with buttons. Typing works, but nothing secret is ever typed into the
transcript. The existing secure opening boundary (runtime reachability,
encrypted store, owner registration or unlock) is unchanged; this replaces the
configuration wizard that follows it (`web/src/lib/firstRun.ts`).

| ID | Step | Content |
|---|---|---|
| QUI-W01 | Unlock | Create the owner account or unlock. The open-ring mark replaces the eye-orb. |
| QUI-W02 | Hello | "Hi, I'm Raiker. Let's set up three things, then do something useful. What should I call you?" Then an optional companion pick (Skip allowed). |
| QUI-W03 | Model | "Where should I think?" Cards: On this computer (recommended when hardware fits, with model and size), An account I have, Decide later. API keys go in a secure field on the card. |
| QUI-W04 | How I'll ask | One card for the profile ("I'll research and prepare on my own. I'll ask before I send, delete, pay or share anything." Standard · Change) and one for where data goes. **No connection requests.** |
| QUI-W05 | First task | Four starters (one each for Chat, Work, Build, Design) and the composer. The conversation is kept in Threads as "Getting started". |
| QUI-W06 | Controls | **Skip setup** always visible, opening a plain new chat. A progress line (Name · Model · Privacy · Start) shows real steps only. Setup can be re-run from Settings › General. |

Installer-covered stages (This device, Check) stay skipped for packaged desktop
installs, as today.

### Home

#### QUI-H01 — Layout

Single column, 980 px. In order:

1. Greeting with one fact only when true ("Good morning, Rahul · 1 decision
   waiting").
2. **Composer** ("Ask Raiker anything…", Attach, profile chip, Send). Typing here
   opens a new Chat with the message.
3. **Continue where you left off**: the last thread or task and its real next step.
4. **Needs your decision**: at most one row (72–96 px), then View all.
5. **In progress**: at most two cards (112–136 px), then View all.
6. **This week**: finished outcomes named, not counted ("Sent the proposal ·
   merged the login fix · saved 3 memories").
7. **Upcoming**: compact rows (48–56 px).

Sections with nothing in them are not drawn. No zero-count tiles. No health
widgets unless something needs attention. Every item opens the exact task,
result, conversation, approval or schedule.

#### QUI-H02 — First day

On an empty first day Home shows the companion (96–128 px), the composer and the
four starters, nothing else.

#### QUI-H03 — Startup page

Home by default; can be set to Chat in Settings › General.

#### QUI-H04 — What's new

After an update, one dismissible line ("Updated to 1.4 · 3 changes") linking to
About & updates. Never a modal.

#### QUI-H05 — Backups

Backup is recommended on Home only when there is none or it is stale.

### Chat

#### QUI-C01 — Layout

Layout A. Transcript and composer 680–760 px wide. Top strip: editable title,
project chip, search in conversation, Context toggle. Chat, Build and Design
switch in the top bar and keep the draft.

#### QUI-C02 — Messages

| Type | Presentation |
|---|---|
| Your message | Right-aligned muted bubble, at most 640 px |
| Raiker's answer | Left-aligned reading surface, at most 680 px |
| Tool step | 36 px row, grouped ("2 steps") and expandable |
| Plan | Checklist card with real states and the path line |
| Result | Bordered card with one action (Open draft, View diff, Open image) |
| Approval | Raiker Safety card (QUI-P05, [Chat guide](../guide/working-in-chat.md)) |
| Question | Clarifying-question card ([QUI-F02, FIXED-1151](FIXED_ITEMS.md#fixed-1151--a-question-asked-mid-task-was-offered-as-an-approval-in-chat-build-and-the-floating-card-qui-f02)) |
| Visual answer | Answer blocks ([Chat guide](../guide/working-in-chat.md#tables-charts-and-other-answer-blocks)) |

#### QUI-C03 — A turn, step by step

1. **Send.** Enter sends; Shift+Enter adds a line.
2. **Working.** One status line shows the real current activity ("Reading 2
   emails from Anna"). The composer becomes *Add instruction* with **Stop
   safely**. Follow-ups queue and are shown as queued.
3. **Steps.** Tool calls collapse into a group. Expanding shows what was read or
   changed. Red only for real failures; ambiguous results are neutral.
4. **Plan.** For multi-step work: done steps solid, the current step a point,
   later steps dotted.
5. **Decision.** Work pauses at an approval; the status line reads "Waiting for
   your decision".
6. **Result.** A result card, then a short answer with source chips.
7. **Outcome line.** Completed · Partially completed · Not done · Outcome
   unknown, linking to its activity, with the task receipt ([QUI-F16, FIXED-1153](FIXED_ITEMS.md#fixed-1153--a-tasks-end-did-not-say-what-it-used-read-changed-or-sent-qui-f16)).
8. **Memory.** Anything worth remembering appears as a suggestion (Save ·
   Dismiss). Never saved silently.

#### QUI-C04 — Composer

| Element | Decision |
|---|---|
| Placeholder | "What would you like Raiker to do?" |
| Input | Grows to five lines, measured from its own line height, then scrolls (owner decision 2026-11-07; briefly about eighteen lines that day, 180 px before) |
| Action row | 44 px: Attach · Project · Profile chip · context count when relevant · More · Send (40×40, far right) |
| More | Schedule, research depth, model, work mode, answer style |
| Data label | "Stays on this computer" / "Sent to Anthropic" ([QUI-F17, FIXED-1154](FIXED_ITEMS.md#fixed-1154--homes-composer-did-not-say-where-a-message-would-go-qui-f17)) |
| Model | Shown as a small label only when it is not the default |
| Bottom spacing | 24 px |

#### QUI-C05 — No model

The composer stays usable. One line above it: "No model is set up · Set up".
Send stays enabled; sending opens the Add model dialog with the message kept and
sends it once a model is ready.

#### QUI-C06 — Conversations

One conversation per topic. The sidebar's Chat row lists the five most recent
chats beneath it. The full list is Work › Threads. New chat: Ctrl/Cmd+N.

#### QUI-C07 — Context panel

Closed by default, 320 px. Tabs only when they have content: Context (files and
memories in use), Plan, Sources, Activity.

#### QUI-C08 — Streaming and scrolling

Answers stream. The view follows only while at the bottom; scrolling up stops
following and shows **Jump to latest**.

#### QUI-C09 — Editing

Edit your last message or retry an answer. Earlier versions are kept, not
overwritten.

#### QUI-C10 — Empty chat

Brief greeting, one sentence on what Raiker can do, at most four starter prompts,
an optional small companion (96–128 px). No hero image.

#### QUI-C11 — Background work

"Run in background" lives in More. A background task appears in the live work
line and on Home › In progress.

#### QUI-C12 — Window sizes

At 1,280 px the context panel opens over the transcript. At 1,920 px and up it
sits beside it and the transcript stays 720 px.

### Acceptance

* Setup can be completed or skipped without ever typing a secret into the
  transcript.
* No progress indicator shows a step that has not actually started.
* Home with nothing to show renders only the greeting, composer and starters.
* A chat with no model accepts and keeps the message.

### 2026-11-07 — Composer control deck

**Owner decisions, 2026-11-07.** The owner supplied an AI-agent composer
brief and decided four open questions:

* **Shape:** a floating glass capsule. This reverses the 2026-11-06 rejection
  of the idle capsule recorded in
  [VISUAL_DESIGN_SPEC.md](../architecture/VISUAL_DESIGN_SPEC.md). The card
  floats with margins over the work surface, uses a translucent surface with a
  backdrop blur and a 1 px border, and lets the transcript pass beneath it.
  Where the browser cannot blur, or the owner asks for reduced transparency,
  it falls back to the solid surface.
* **First slice:** input and context (below). Execution states (morphing send,
  follow-up pills while running, a step drawer, Resume from last step) and the
  editor/trigger layer (rich code blocks, ghost text, `{variable}` injectors)
  come later.
* **Token counts:** a labelled estimate (≈), never presented as exact. Text is
  estimated at four characters per token; a PDF, Word or spreadsheet file shows
  its size only, because its text is not read until the turn.
* **`@`:** will route a prompt to named agent personas. Personas are a new
  product concept that needs its own design (what each may do, how it maps to
  execution profiles and permissions), so this slice keeps `@` for files and
  records personas as planned work in
  [TO_BE_FIXED](TO_BE_FIXED.md#composer-agent-personas-for-).

QUI-C04's input row changes: the input grows to five lines before it scrolls
(revised the same day from 432 px, about eighteen lines, at the owner's
request; 180 px before).

The 15-item checklist:

1. [x] Floating glass capsule in the shared composer frame (Chat, Build, Design).
2. [x] Solid fallback without backdrop-filter support or with reduced transparency.
3. [x] Chat's transcript passes beneath the capsule, and the last turn stays readable.
4. [x] The input grows to five lines before scrolling (revised from 432 px the same day).
5. [x] Settings › Personalisation: **Send with** Enter (default) or Ctrl/⌘ + Enter.
6. [x] The send key applies in Chat, Build, Design and Home, and the hint says which.
7. [x] Pick several files at once in Attach.
8. [x] `.json` documents accepted, validated and read like plain text.
9. [x] A token estimate helper, labelled as an estimate.
10. [x] Each attachment chip shows its size and, for text, ≈ tokens.
11. [x] Each chip has a type mark (PDF, sheet, text, data, image) with its label, not colour alone.
12. [x] Uploading is shown on a chip while it happens; no invented later stages.
13. [x] Above 80 % of the model's context window the card turns amber with a warning line.
14. [x] The drop state is a visible dashed zone that says what can be dropped.
15. [x] **Add to prompt** on an answer pins it into the composer as a context chip.

Evidence: [FIXED-1304](FIXED_ITEMS.md#fixed-1304--the-composer-was-a-short-solid-box-with-no-context-guardrails-qui-c04)
and the [Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-composer-control-deck).

### 2026-11-07 — Composer execution states

The second slice of the composer control deck, under the owner's 2026-11-07
decision that execution states come after input and context: a morphing send,
follow-up pills while running, a step drawer and Resume from last step. It
keeps QUI-C03's rules: every status comes from the turn's own events, Stop is
the same governed interrupt the top bar uses, and a follow-up grants nothing.
Chat and Build share it; Design's composer starts a background image job, not
a streamed turn, so it has nothing to stop.

The 15-item checklist:

1. [x] While a turn runs, Send becomes **Stop safely** in the same place (no second Stop button) while the prompt is empty.
2. [x] The change of shape is instant under reduced motion.
3. [x] The prompt stays editable while a turn runs; the send key queues what is typed as a follow-up.
4. [x] The placeholder and the button name say that it queues: *Add an instruction* and **Queue**.
5. [x] Each follow-up is a pill above the input with its own words and *Queued* (*Sending…* while a new chat waits for its id).
6. [x] A pill turns *Read* only when the runtime reports `turn_steered` for it.
7. [x] A follow-up the turn ended before reading says *Not read* and offers **Use as next message**.
8. [x] The working line shows the elapsed time of the turn, counted from Send.
9. [x] A **Steps** toggle in the running bar names the count and opens the step drawer.
10. [x] Each drawer row says its state in words (Done, Running, Waiting for you, Failed, Refused), not colour alone.
11. [x] The drawer is a disclosure (`aria-expanded`, keyboard reachable) and closes when the turn ends.
12. [x] A stopped turn offers **Continue from last step**, which sends a continuation the transcript shows.
13. [x] The same running bar, morphing send and pills in Build.
14. [x] Attach, the model and the other bar controls stay disabled while running; only text can be queued.
15. [x] The shortcut sheet and tooltips say what the send key does while a turn runs.

Evidence: [FIXED-1306](FIXED_ITEMS.md#fixed-1306--a-running-turn-had-a-second-stop-button-a-separate-steer-field-and-no-step-view-qui-c03-qui-c04).
The live round found that a stopped turn never reached the model's history,
so a continuation had nothing to continue
([FIXED-1307](FIXED_ITEMS.md#fixed-1307--a-stopped-turn-was-left-out-of-the-conversation-the-model-saw-found-this-round)).
See the [Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-composer-execution-states).
The editor layer (in-composer code blocks, ghost text, `{variable}` injectors),
*More* (QUI-C04) and `@` personas remain open
([TO_BE_FIXED](TO_BE_FIXED.md#composer-agent-personas-for-)).

## 05 Raiker Browser

> Merged from `docs/plans/QUIET_UI_PLAN.md` on 2026-11-16; the original file was removed.

Part of the [Quiet UI redesign plan](QUIET_UI_PLAN.md). Proposed, 2026-10-21.

### Starting point

The desktop app is an Electron 44 shell (`desktop/package.json`), and Electron
is Chromium. A built-in browser needs no new engine and no extra download. Today
the shell deliberately sends every outside link to the system browser
(`desktop/src/main.ts`, `shell.openExternal` in `route()`) and blocks embedded
web views (`will-attach-webview`). Web reads in the runtime go through
`raiker/runtime/web_access.py` (`WebAccessService`: HTTPS, private-address
guard, blocklist, checked redirects) via `tier2_web.py`.

The browser is a controlled browsing surface inside a task, not a second general
browser product and not an import of the owner's personal browser profile.

### Layout

* Opens as a **tab inside the task**, beside the conversation. The chat keeps
  running; the browser takes the work area. At 1,280 px the chat collapses to a
  360 px column.
* Top bar, always visible: site identity, **Temporary session** or **Signed in
  (kept)**, and who is in control: **Raiker is browsing** / **You are browsing**,
  with **Take over** / **Hand back**.
* Activity list beside the page: every step ("Opened search", "Typed …",
  "Waiting: sign-in needed"). It becomes part of the task's activity.
* Hand-off banner when Raiker must stop: "You need to sign in to booking.com.
  Raiker never sees your password. Sign in myself."

### How it works

* **One isolated session per site.** Each site gets its own Electron session
  partition: in memory by default, persisted only after "Keep me signed in on
  this site". Nothing is shared with or imported from the owner's Chrome, Edge
  or Safari: no cookies, passwords, history, extensions or profiles.
* **Same network rules as web reads.** Browser partitions route through the
  host's egress controls, so the browser cannot reach anything `web_fetch`
  cannot.
* **Driven by the shell, governed by the host.** The shell drives the page
  through Chromium's DevTools protocol (`webContents.debugger`). Each action is a
  governed action, so profiles, permissions and approval cards apply exactly as
  in chat. Reading, scrolling, searching and filling fields within limits
  proceed; submitting, buying, posting and sending ask first.
* **Hard limits, enforced in the shell.** No reading of password fields; no
  filling of payment details; stop and hand over at sign-in, multi-factor
  prompts, CAPTCHAs, account recovery and checkout. Third-party pages get no
  preload, no Node integration and no access to the app.
* **Take over** stops Raiker's actions at once. **Hand back** records what the
  owner changed.
* **Downloads** go to a per-task folder and are listed in the activity before
  Raiker opens them.
* **Site permissions** (camera, microphone, location, notifications) are refused
  unless the owner allows them for that site.

### Where the system browser stays

* **Connecting accounts** (Google, GitHub, ChatGPT sign-in). Google blocks OAuth
  in embedded browsers, and RFC 8252 (OAuth for native apps) requires the system
  browser so the app never handles the password. The sign-in returns to Raiker
  automatically.
* **The web app** (Raiker in the owner's own browser, or on a VPS) cannot show
  other sites inside its page, because most sites forbid embedding. There the
  browser runs on the host with a live view streamed into Raiker: an optional,
  heavier add-on (a host-side Chromium, roughly 150 MB), delivered after the
  desktop version.

### Delivery

| ID | Step | Scope |
|---|---|---|
| QUI-B01 | View only | Open a page inside a task and browse it yourself, in a temporary session. Links in answers open here instead of the system browser. |
| QUI-B02 | Raiker browses | Read, scroll, search and fill fields with limits; the activity list; Take over. Submit and send go through approval cards. |
| QUI-B03 | Kept sign-ins | Encrypted per-site sessions after explicit consent; "Clear this site" in Settings › Web access. |
| QUI-B04 | Web app and VPS | Host-side Chromium with a streamed view, as an optional add-on. |

A credential broker backed by the OS keychain comes only if a real need appears
after B03.

### Acceptance

* No browser session shares storage with another site or with the app's own
  session.
* Every browser action appears in the task activity with the approval that
  allowed it.
* The shell refuses any DOM read of a password field, whatever the request.
* Take over stops automation within one action.

## 07 Quick fixes and quality

> Merged from `docs/plans/QUIET_UI_PLAN.md` on 2026-11-16; the original file was removed.

Part of the [Quiet UI redesign plan](QUIET_UI_PLAN.md). Proposed, 2026-10-21.

### Quick fixes

Small changes to what is on screen today. Each is independent of the larger
redesign and can ship on its own.

| ID | Where | Now | Change | Status |
|---|---|---|---|---|
| QUI-Q01 | Home (`WorkbenchView.svelte`) | A tile reading "Runtime issues · 1": a large number and "Review configuration and readiness evidence before critical work." On a fresh workspace the one issue is "No model profile is selected." | Name each gap as a sentence with the action that fixes it. The default-model gap reads "No default model is chosen." with **Choose a model** (Models): it is the default model, which a Chat with its own model does not set ([FIXED-1074](FIXED_ITEMS.md#fixed-1074--home-said-no-model-is-set-up-while-a-chat-was-answering)). Any other gap: its own sentence with **Open diagnostics**. No big number. | Done ([FIXED-1075](FIXED_ITEMS.md#fixed-1075--home-showed-a-runtime-issues-count-instead-of-the-problem-qui-q01)) |
| QUI-Q02 | Home | Five start cards (conversation, build, design, task, projects) repeating the sidebar and the mode switch | Replaced by the Home composer and first-day starters | Done with QUI-H01 ([FIXED-1058](FIXED_ITEMS.md#fixed-1058--five-start-cards-repeated-the-sidebar-and-a-first-day-had-nothing-to-start-from-qui-q02-qui-h02)) |
| QUI-Q03 | Chat composer | Placeholder "How can I help you today?" | "What would you like Raiker to do?" | Done ([FIXED-1076](FIXED_ITEMS.md#fixed-1076--chats-placeholder-was-a-generic-chatbot-line-qui-q03)) |
| QUI-Q04 | Chat composer | With no usable model, Send is disabled next to "Not selected" | Send stays enabled. Pressing it (or Enter) with no usable model opens the model setup dialog and keeps the draft | Done ([FIXED-1077](FIXED_ITEMS.md#fixed-1077--send-was-a-dead-button-with-no-model-qui-q04)) |
| QUI-Q05 | Chat header | A disabled, faded "New chat" on an empty conversation, and a "Background" toggle shown even when nothing runs | "New chat" appears once there is something to leave. The Background toggle appears only when background work is running, waiting, failed, or its panel is open; it stays reachable from the conversation menu | Done ([FIXED-1078](FIXED_ITEMS.md#fixed-1078--new-chat-and-background-were-shown-with-nothing-behind-them-qui-q05)) |
| QUI-Q06 | Top bar | Search, approvals, notifications and More are icons with accessible names but no visible tooltip | A tooltip on each icon-only control, using the same words as its accessible name | Done ([FIXED-1079](FIXED_ITEMS.md#fixed-1079--the-top-bars-icon-buttons-had-no-visible-tooltip-qui-q06)) |
| QUI-Q07 | Home, Approvals count | Approvals icon always present | Keep it: it is Approvals' only top-level entry. The count already appears only when something waits | No change |
| QUI-Q08 | Colour | The proposed attention colour `#B8871B` fails contrast | Not a code fix: the shipped `--warn` (`#866412`) already passes. The palette decision is recorded in [QUI-V01](#qui-v01--colour-tokens) | No change |

### Quality foundations

| Item | State |
|---|---|
| QUI-G01 | **Report done** ([FIXED-1096](FIXED_ITEMS.md#fixed-1096--page-size-was-not-measured-anywhere-qui-g01)). 29 of 94 measurements over budget at first. 2026-11-14: Memory › Controls now fits at 1440×900 ([FIXED-1433](FIXED_ITEMS.md#fixed-1433--memory--controls-ran-past-its-one-screen-budget-qui-g01)) and Tasks' docked composer no longer pushes the page 9 px over. Still over: Observe › Activity (a log, by design long) and Settings › Notifications and Advanced at 1280×800. |
| QUI-G02 | **Done** ([FIXED-1095](FIXED_ITEMS.md#fixed-1095--user-facing-copy-used-words-the-plan-retires-qui-g02)). |
| QUI-G03 | **Done** ([FIXED-1097](FIXED_ITEMS.md#fixed-1097--there-was-no-single-place-to-see-every-shared-state-qui-g03)), at `#/state-gallery` in development builds. |
| QUI-G04 | **Done.** Long transcripts ([FIXED-1100](FIXED_ITEMS.md#fixed-1100--a-long-conversation-rendered-every-turn-qui-g04)); rename, pin and archive paint first and roll back visibly ([FIXED-1432](FIXED_ITEMS.md#fixed-1432--rename-pin-and-archive-waited-for-the-server-before-painting-qui-g04)). |
| QUI-G05 | **Done** ([FIXED-1098](FIXED_ITEMS.md#fixed-1098--keyboard-use-and-zoom-were-not-checked-qui-g05)). |
| QUI-G06 | **Partly done** ([FIXED-1099](FIXED_ITEMS.md#fixed-1099--stop-steer-and-continue-errors-blamed-the-local-runtime-qui-g06)): the helper and the Chat, Build and Tasks errors, followed by the Memory, Models, Connections, Settings, Projects, and Approvals, Library and Sessions slices below. Other views still need their audit. |
| QUI-G07 | Open: needs five people, not code. |

#### QUI-G01 — Size budgets in CI

Extend `web/e2e/all-pages-live.spec.ts` (it already walks every destination
from `destinations.ts`) to measure scroll height and visible controls:

* a destination page fits in one screen at 1440×900 and 1.25 screens at
  1280×800 with an empty workspace;
* a Settings sub-page fits in 1.5 screens;
* at most 60 interactive controls visible at once, excluding list rows.

Start as a report, then make it fail once the long pages are rebuilt.

#### QUI-G02 — Word list

`web/src/lib/quietUiCopy.test.ts` already checks copy. Extend it to fail on
user-facing uses of: Observability, MCP (outside Connections › Advanced),
runtime (outside Settings › Advanced), journey, destination, expedition,
waypoint, trail, quest, arrived.

#### QUI-G03 — State gallery

A development-only route that renders every shared component in its empty,
loading, working, needs-permission, error and done states, in light and dark.

#### QUI-G04 — Speed

Typing never lags; a 1,000-message conversation scrolls smoothly (render only
visible messages); direct actions paint before their request returns and roll
back visibly on failure.

#### QUI-G05 — Accessibility beyond axe

Axe already runs in `composer.spec.ts`. Add a keyboard-only walk through every
destination, and a 200% zoom check at 1280×800 where Send stays visible.

#### QUI-G06 — Errors that say what to do

Review every user-facing error once: each names what failed, what it affected,
and one safe next step.

#### QUI-G07 — Five people, five tasks

Before and after the redesign, watch five people: ask a question, compare
options, approve an email, connect Gmail, find last week's result. Measure time
to first useful result and where they hesitate.

### 2026-11-06 — QUI-G06 Memory error recovery

This run takes one document at a time. The following 15-item slice implements
the existing QUI-G06 decision: name the failure, its affected object and one
safe next step. Completed implementation checklist:

1. [x] Memory use: refresh and verify the setting before retrying.
2. [x] Recall mode: refresh and verify the selected mode.
3. [x] Pin: identify the pin change and verify its saved state.
4. [x] Edit: copy the draft before refreshing the saved text.
5. [x] Forget: verify the current record status before retrying.
6. [x] Archive: verify status before retrying.
7. [x] Restore: verify status before retrying.
8. [x] Relationship scan: check Suggestions before scanning again.
9. [x] History: close and reopen the history panel.
10. [x] Review and expiry dates: verify the saved dates.
11. [x] Permanent deletion: check whether the record still exists.
12. [x] Export: retry, then check browser download permissions.
13. [x] Import: check imported records before selecting the file again.
14. [x] Observation deletion: check whether the observation still exists.
15. [x] Proposed gist discard: check whether it is still waiting.

Evidence and limitations are recorded in
[WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md).
QUI-G06 remains partial: other views still need their error audit. QUI-G01,
QUI-G04 and QUI-G07 also remain open, so this document is retained.

### 2026-11-06 — QUI-G06 Model recovery

The next 15-item implementation slice applies the same error-recovery decision
to local model management and Hugging Face discovery:

1. [x] Local-library read: name the stale list and offer reopening the panel.
2. [x] Add folder: check the approval list before repeating the write.
3. [x] Scan folders: name the stale model list and offer **Scan now**.
4. [x] Remove folder: catch the failure and check approval before retrying.
5. [x] Activity read: offer **Retry status**.
6. [x] Cancel job: catch the failure without claiming cancellation succeeded.
7. [x] Retry job: preserve the action error across successful status polling.
8. [x] Inspect partial files: show the error outside an unopened confirmation.
9. [x] Delete partial files: retain the review and check what remains; do not
   describe every network/server failure as an unsafe-path refusal.
10. [x] Clear job record: catch the failure and retain the row.
11. [x] Save context limit: preserve entries and advise checking the saved limit.
12. [x] Check local server: explain unconfirmed tool support and the next check.
13. [x] Hugging Face search: name the failed search and connection recovery.
14. [x] Inspect repository: name the missing file/folder information and access check.
15. [x] Estimate download: explain unconfirmed size/placement and destination check.

The shared error helper retains HTTP/refusal evidence. Mutation messages avoid
claiming a failed response proves that nothing changed on the server. Activity
now keeps read errors and action errors separately so polling does not hide
the failed owner action. Evidence:
[Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-model-recovery)
and [FIXED-1287](FIXED_ITEMS.md#fixed-1287--model-management-errors-were-hidden-misleading-or-had-no-recovery-step-qui-g06).
The remaining quality foundations above keep this plan open.

### 2026-11-06 — QUI-G06 Connection recovery

This run applies the existing QUI-G06 decision to Connections and its Advanced
servers. Each item names the failed action and affected object, preserves the
owner's input and provides a safe recovery step. Writes with an ambiguous
response require checking saved state before retrying.

1. [x] Read connections: distinguish an unavailable list from an empty one.
2. [x] Add a service: check whether it was added before repeating the request.
3. [x] Save credentials: retain the entry and check sign-in before retrying.
4. [x] Change session access: verify the saved state before using the service.
5. [x] Disconnect: do not claim that credentials were removed on failure.
6. [x] Read Advanced servers: retain rows, expose retry and stop false loading.
7. [x] Create a server: retain the name and check for an existing profile.
8. [x] Add a plugin's offered server: check the list before adding it again.
9. [x] Test a server: explain unconfirmed connectivity and how to retest.
10. [x] Accept tools: verify accepted declarations before retrying.
11. [x] Rename a server: retain the draft and resolve stale-name conflicts.
12. [x] Delete a server: retain the row and verify whether it still exists.
13. [x] Give a server a secret: retain the entry without echoing its value.
14. [x] Remove a server secret: verify its name before claiming removal.
15. [x] Stop or resume a server: report unconfirmed state and failed checks.

Validation covers failed reads and mutations, periodic refresh retaining
an action error, recovery after refresh, and running-host Playwright captures
in both themes at supported laptop sizes. The round also fixes Add losing its
sign-in step after installation, the account editor's false rollback claim and
manifest error feedback, and the clipped Cancel button found during zoom
review. Evidence:
[Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-connection-recovery),
[FIXED-1288](FIXED_ITEMS.md#fixed-1288--connection-failures-claimed-rollback-or-lost-their-recovery-message-qui-g06)
[FIXED-1289](FIXED_ITEMS.md#fixed-1289--adding-a-service-lost-its-sign-in-step-after-installation)
and [FIXED-1290](FIXED_ITEMS.md#fixed-1290--the-server-rename-row-clipped-cancel-at-200-percent-zoom).
Other quality foundations remain open; this document is retained until those
requirements are met.

### 2026-11-06 — QUI-G06 Settings recovery

This 15-item slice applies the existing QUI-G06 decision to Settings. Errors
identify the failed action, the affected state and a safe recovery step. An
unconfirmed response to a write does not prove that the server rejected it.

1. [x] Read execution profiles: explain that saved boundaries are unconfirmed.
2. [x] Create a profile: check the list before creating a duplicate.
3. [x] Save a profile: retain the draft and check the current version.
4. [x] Activate a profile: verify the active boundary before new work.
5. [x] Bind a project: verify its saved boundary before starting work.
6. [x] Read update status: stop false loading and offer Retry update status.
7. [x] Check updates: say release availability is unknown and offer a channel check.
8. [x] Start an update: account for a helper that may already have started.
9. [x] Read execution status: do not claim the agent accepts work.
10. [x] Save an environment: retain entries and check for an existing configuration.
11. [x] Reset an environment: verify session and cache state before repeating.
12. [x] Probe a boundary: explain unconfirmed readiness and check connectivity.
13. [x] Toggle an environment: verify saved state and running commands.
14. [x] Remove an environment: check the list before repeating removal.
15. [x] Select an environment: verify the default target instead of assuming it is unready.

HTTP status and refusal codes remain visible. Known version conflicts and
in-use environment refusals keep their specific remediation. The update-status
retry clears the error after a successful read. No composer shape changes are
included. The remaining quality foundations keep this document open.

Evidence: [Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-settings-recovery)
and [FIXED-1297](FIXED_ITEMS.md#fixed-1297--settings-errors-hid-uncertainty-and-offered-no-recovery-qui-g06).

### 2026-11-06 — QUI-G06 Projects recovery

This run applies QUI-G06 to Projects. The implementation plan is to preserve
owner drafts, distinguish failed reads from empty content, provide safe recovery
for uncertain writes, then validate with component tests and a running-host
Playwright round in both themes. The 15-item checklist:

1. [x] Read projects: retain known rows and offer Retry projects.
2. [x] Create: retain the name and check for an existing project before retrying.
3. [x] Attach a new folder: retain entries and check the list before retrying.
4. [x] Attach to an existing project: check its saved root before retrying.
5. [x] Save instructions and checks: keep the draft and compare saved state.
6. [x] Move a chat: check its saved project before repeating the move.
7. [x] Read project details: name the unavailable content and how to reopen it.
8. [x] Read file history: distinguish it from the separately loaded explorer.
9. [x] Read tasks: show unavailable instead of claiming there are no tasks.
10. [x] Read images: show unavailable instead of claiming there are no images.
11. [x] Export: check downloads and browser permissions before retrying.
12. [x] Archive: check Active and Archived before repeating the write.
13. [x] Restore: check saved status and retain specific refusal guidance.
14. [x] Move a project: retain the destination and check the saved hierarchy.
15. [x] Read deletion preview: explain why deletion is unavailable and offer retry.

Other quality foundations above remain open, so this document is retained.

Implementation and evidence: [FIXED-1299](FIXED_ITEMS.md#fixed-1299--projects-failures-hid-missing-content-or-offered-no-safe-recovery-qui-g06),
[FIXED-1300](FIXED_ITEMS.md#fixed-1300--project-limits-stayed-loading-after-failure-and-claimed-rollback)
and [Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-projects-recovery).
The related live setup helper repair is
[FIXED-1301](FIXED_ITEMS.md#fixed-1301--live-setup-preparation-consumed-the-helpers-navigation-budget).

### 2026-11-06 — QUI-G06 Approvals, Library and Sessions recovery

This run applies QUI-G06 to Approvals, the Library and Sessions. A decision,
unpin, move or delete whose answer is lost may still have been recorded, so
each such error asks the owner to check saved state before repeating it.
Governed refusals keep their explained reason; reads keep the rows already on
screen. The 15-item checklist:

1. [x] Read the queue or History: keep known rows and offer Retry approvals.
2. [x] Open an approval: say nothing was decided and offer Open it again.
3. [x] Allow or decline: say it may have been recorded and to check History first.
4. [x] Answer a question: keep the choices and check whether it is still waiting.
5. [x] Propose your own version: keep the edit and look for a waiting replacement.
6. [x] Continue the turn: open the conversation and check its latest turn first.
7. [x] Critical decision: tell a refused step-up (nothing decided) from a lost answer after it.
8. [x] Undo a held send: report a failure that is not a closed window, outside the countdown too.
9. [x] Read the Library: keep known items and offer Retry Library.
10. [x] Download: a missing file may have been deleted; any other failure says no file was saved.
11. [x] Unpin: keep the row and check whether it is still pinned; errors no longer vanish after 3 s.
12. [x] Move a pin: put the picker back to the saved project and check before moving again.
13. [x] Read Sessions: keep known rows and offer Retry sessions.
14. [x] Open a session or turn: name what is unavailable and offer to open it again.
15. [x] Delete one or many: keep the selection and check what is still listed first.

Found during the live round and fixed: an open Approvals queue did not show a
decision raised after it loaded, while the top bar's count already did. The
queue now re-reads when that count changes
([FIXED-1303](FIXED_ITEMS.md#fixed-1303--an-open-approvals-queue-missed-a-decision-raised-after-it-loaded)).

Implementation and evidence: [FIXED-1302](FIXED_ITEMS.md#fixed-1302--approvals-library-and-sessions-errors-hid-uncertain-writes-qui-g06)
and [Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-approvals-library-and-sessions-recovery).
QUI-G01, QUI-G04, QUI-G07 and the remaining QUI-G06 views stay open, so this
document is retained.

### 2026-11-09 — QUI-G06 Skills, Goals, Rewind and GitHub recovery

Plan: preserve drafts and diagnostic evidence, name the affected action, and
verify saved state before retrying uncertain writes. Reuse existing tokens and
inline alerts; no new modal interruption.

1. [x] Skills list read.
2. [x] Skill upload.
3. [x] Skill URL import.
4. [x] Skill build.
5. [x] Skill rename.
6. [x] Skill activation.
7. [x] Skill command.
8. [x] Skill download.
9. [x] Skill deletion.
10. [x] Goals list read.
11. [x] Goal detail read.
12. [x] Goal plan save.
13. [x] Goal lifecycle action.
14. [x] Goal criterion confirmation.
15. [x] Goal polling preserves action errors.
16. [x] Rewind preflight.
17. [x] Rewind approval request.
18. [x] GitHub connection read.
19. [x] GitHub action failure.
20. [x] GitHub unreachable outcome.

### 2026-11-09 — Beta recovery follow-through on this PC

Plan: complete the remaining Messaging and Design image recovery audit (QUI-G06).
Keep drafts and last-known reads, distinguish unavailable from empty, and avoid
repeating uncertain sends or destructive writes without checking saved state.
Test with component fault injection and running-host browser checks on Linux.
Native signing, GPU and other-machine evidence stay outside this PC run.

1. [x] Messaging list: retain known profiles and offer retry.
2. [x] Pair channel: preserve allowed-sender input on failure.
3. [x] Save destination: retain the address editor on failure.
4. [x] Save senders: retain the allowlist editor on failure.
5. [x] Save routing: retain routing selections on failure.
6. [x] Conversation lookup: distinguish unavailable from empty and retry.
7. [x] Enable channel: explain uncertain switch state.
8. [x] Pause channel: explain uncertain pause state.
9. [x] Unpair channel: verify pairing before retrying.
10. [x] Test delivery: check receipts before sending again.
11. [x] Held reply: check receipts before resending.
12. [x] Review receipt: verify reviewed state before retrying.
13. [x] Design image import: explain uncertainty and preserve context.
14. [x] Design image history: retain known images and offer retry.
15. [x] Design model lookup: show unavailable state with retry.
16. [x] Image generation: preserve prompt and check history before retrying.
17. [x] Delete image: verify Recently deleted before repeating.
18. [x] Restore image: verify saved state before repeating.
19. [x] Revert image: check versions before creating another.
20. [x] Purge image: verify permanent deletion before repeating.

## 08 Brand and visual system

> Merged from `docs/plans/QUIET_UI_PLAN.md` on 2026-11-16; the original file was removed.

Part of the [Quiet UI redesign plan](QUIET_UI_PLAN.md). Proposed, 2026-10-21.
[VISUAL_DESIGN_SPEC.md](../architecture/VISUAL_DESIGN_SPEC.md) remains the
owner of tokens; this records the decisions to apply to it.

### Status

**Applied 2026-10-25**
([FIXED-1168](FIXED_ITEMS.md#fixed-1168--the-app-mark-was-the-eye-orb-qui-w01-qui-v03-qui-v04)
and [FIXED-1169](FIXED_ITEMS.md#fixed-1169--the-palette-and-type-were-not-the-ones-08-decided-qui-v01-qui-v02);
live cases RT-QUI-57 and RT-QUI-70).

| Item | State |
|---|---|
| QUI-V01 | **Done.** Both themes use these roles in `web/src/app.css` and the desktop shell; soft fills were set so success and risk text stay at 4.5:1 on them (`appCss.test.ts`). |
| QUI-V02 | **Done** for type: Inter everywhere, bundled. Body stays 15 px. Radius and spacing were already on this scale. |
| QUI-V03 | **Done.** The eye-orb is gone from the app, the lock screen, the icons, the desktop Setup window and the installer art. |
| QUI-V04 | **Done.** The owner chose the open ring on 2026-10-25. `Logo.svelte` draws it; `scripts/render_brand_icons.py` renders every PNG from the same geometry. No route cue on one end. |
| QUI-V05 | **Open.** The companion's art does not exist. |
| QUI-V06 | **Done** earlier (Home's Continue and This week, the path line in plans and steps). |
| QUI-V07 | **Unchanged.** |
| QUI-V08 | **Done** earlier (QUI-Q06); this round also replaced the last glyph icons (a star and a cross in Threads) with drawn ones. |

### QUI-V01 — Colour tokens

| Role | Light | Dark | Use |
|---|---|---|---|
| Background | `#F7F6F2` | `#101216` (was `#121212`) | App canvas |
| Surface | `#FFFFFF` | `#1C2027` (was `#1B1B1B`) | Cards, panels, sheets, the composer |
| Main text | `#1C1C1A` | `#F2F4F7` (was `#F4F1EA`) | Reading text |
| Secondary text | `#686761` | `#C1C7D0` (was `#B7B4AC`); muted `#A0A7B2` (was `#8C8A84`) | Metadata, descriptions, placeholders |
| Primary action | `#2F6F8F` | gold `#E0B64A` with `#101216` text (`--action`, 2026-11-07) | Primary actions and key highlights |
| Interactive accent | `#2F6F8F` | `#78B7D5` | Secondary interaction, selection, focus |
| Attention | `#B8871B` fill / **`#8A6411` text** | amber `#EE9A4D` (2026-11-08; gold is the primary action) | Decisions required |
| Success | `#2F7D5C` | `#62B68D` | Verified completion |
| Risk | `#B5453C` | `#E47B70` | Destructive and error |

**Contrast check (WCAG 2.x).** Every token passes 4.5:1 on its background except
the light attention colour: `#B8871B` on `#F7F6F2` is 2.98:1, below even the
3:1 minimum for UI components. Use `#8A6411` (4.96:1) for attention text and
icons, and keep `#B8871B` only for fills with dark text on top. Success is the
tightest of the rest at 4.61:1.

### QUI-V02 — Type and spacing

* Inter for all interface text. Source Serif 4 deferred: add only if a welcome or
  reflection moment truly needs it.
* Body 15–16 px (now about 14.4 px, `--text-md: 0.9rem`; raising it touches
  every page, so it is its own change). Metadata 12–13 px. Page headings
  24–30 px semibold.
* Radius 10–14 px. Spacing scale 4, 8, 12, 16, 24, 32, 40, 48, 64.
* Default theme: follow the system.

### QUI-V03 — Remove the eye-orb

Remove it from the app icon, favicon, lock screen, loading and empty states,
avatar picker, copy and animation. Today `web/src/lib/components/Logo.svelte`
renders `raiker-mark.png` (the sphere with the prompt eye).

### QUI-V04 — App mark: the open ring

The owner does not want an R. Recommended mark: a rounded ring with one
deliberate gap.

* It reads as one bounded workspace with a single deliberate opening, which fits
  an approval-driven product without explanation.
* It echoes a snow-leopard rosette (a broken ring) without a face, so the mark
  and the companion stay separate but related.
* At 16 px it is one thick stroke and one gap.
* Optional route cue: one end of the gap slightly heavier, suggesting forward
  motion.
* Rules: never rotate or animate it (it would read as a spinner). Place the gap
  around 1–2 o'clock so it does not read as a "C" or a power icon.
* The wordmark is lowercase "raiker" in Inter at a tuned weight.

Alternatives considered: a threshold (rounded square open on one side; more
literal, colder) and two dots joined by a bend (warmer, drifts toward map
imagery).

### QUI-V05 — Companion

The companion gives personality inside Raiker; it is not the logo.

* Default: snow leopard. Collection later: bear, panda, penguin, wolf, tiger,
  cat, dog. Fox deliberately excluded (widely used by other products).
* Small accessories only: scarf, headphones, glasses, satchel, hat, route patch.
  No explorer costumes, maps, tents, globes or hiking imagery.
* **First release: one companion, static art, three moments**: empty or welcome,
  completed, blocked. The selector and animated states come later. Eight animals
  × six accessories × seven states is an illustration pipeline, not a first
  release.
* Never shown on risk or destructive errors.
* Never a loading spinner, never pretends to reveal reasoning, never on every page.
* Reduced motion: static art.

### QUI-V06 — Journey layer, without travel words

Four touches only:

1. **Continue where you left off** first on Home.
2. **The path line** in plans and step lists: done solid, current a point, later
   dotted. Only for plans that exist.
3. **Forward motion**: going deeper slides content in from the right, going back
   slides it left. Reduced motion swaps instantly.
4. **This week** on Home: finished outcomes named.

Words: Continue, Next step, Pick up, Ready for you, In progress, Needs your
decision, Completed, Partially completed, Outcome unknown, Scheduled. Never:
journey, destination, expedition, waypoint, trail, quest, arrived.

### QUI-V07 — Motion

Functional transitions around 100–240 ms. Hover paints instantly; only the
return eases. Motion follows state and never delays it. Everything beyond a fade
respects `prefers-reduced-motion`.

### QUI-V08 — Icons

Every icon has an accessible name. An icon-only control also gets a tooltip,
except where hover would teach nothing new (Hermes's rule): menu triggers, close
buttons, and controls whose visible label already says it.

### 2026-11-06 — Shared UI refinement across pages and subpages

The owner requested the macOS design references across all UI pages. Apply
QUI-V01/V02/V07/V08 through shared primitives, then inspect the complete routed
catalogue. The [Apple reviewer](https://github.com/dickwu/apple-design-skill),
[macOS skill](https://github.com/ceorkm/macos-design-skill), its
[Build with Claude version](https://github.com/davepoon/buildwithclaude/tree/main/plugins/all-skills/skills/macos-design)
(linked by HappyCapy and SkillRepo), and Impeccable inform this refinement.
Raiker's adopted palette, Inter, desktop target sizes, native window controls
and truthful completion/authority rules take precedence over sample recipes.

1. [x] Simplify shared empty-state decoration while keeping its title/action.
2. [x] Keep shared form-dialog headings and Close reachable while content scrolls.
3. [x] Bound confirmation dialogs and wrap long actions within the viewport.
4. [x] Let shared page headings and action groups wrap without squeezing content.
5. [x] Give native disclosures a consistent, keyboard-visible interaction floor.
6. [x] Apply immediate hover feedback and eased return to shared controls.
7. [x] Highlight a table row containing keyboard focus as well as pointer hover.
8. [x] Make shared tabs compact rounded rectangles with unclipped keyboard focus.
9. [x] Give explicitly invalid fields a consistent semantic error outline.
10. [x] Distinguish readonly text fields from disabled controls without dimming text.
11. [x] Replace the Permissions attention stripe with a quiet complete boundary.
12. [x] Remove the thick answer-callout edge; retain its icon, label and tone.
13. [x] Use fine quote rules consistently in transcript, file and source previews.
14. [x] Remove decorative side accents from reasoning and recalled-memory content.
15. [x] Cover nested Advanced/model settings and Add sources in the page catalogue;
    repair tab/panel associations, capture both themes/laptop widths, reconcile
    the visual specification, and run regressions and GitHub workflows.

Implementation and screenshot evidence are recorded in
[Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-shared-ui-refinement)
and [FIXED-1293/1294](FIXED_ITEMS.md#fixed-1293--shared-ui-primitives-drifted-across-pages-and-subpages).

This refinement does not supply QUI-V05 companion art or qualify native macOS,
Windows, screen-reader or five-person usability acceptance. Keep this document
until its remaining work is complete.

### 2026-11-06 — Icon and option-control scale

The owner asked for larger icons and option sliders, then reviewed and rejected
the proposed long-pill composer shape, asking to restore the previous design.
Chat, Build and Design therefore retain their existing rounded-card geometry
and action sizes. The accepted blend pairs Muse's quieter spacing and
progressive disclosure with Apple's legible icon scale, familiar slider thumb
and clear switch state. This is a design direction, not a pixel-for-pixel copy:
Raiker keeps the QUI-V01 palette, Inter, and restrained surfaces. Do not add
Liquid Glass or replace the existing brand colors. *(Superseded for the
composer on 2026-11-07: the owner chose a glass capsule, see
[03](QUIET_UI_PLAN.md#2026-11-07--composer-control-deck); and the
dark palette below.)*

The accepted changes use shared icon roles and consistent switch/range controls
across every page. The composer proposal was removed from source and its former
shape/size rules were restored from the previous revision.

| Item | State |
|---|---|
| UI-SCALE-01 | [x] Raise the small icon role to 16 px for legible inline actions. |
| UI-SCALE-02 | [x] Raise the medium icon role to 18 px for controls and navigation. |
| UI-SCALE-03 | [x] Raise the large icon role to 22 px for headings and nav emphasis. |
| UI-SCALE-04 | [x] Raise the empty-state icon role to 28 px. |
| UI-SCALE-05 | [x] Assert the four icon sizes remain ordered and fixed in the icon regression. |
| UI-SCALE-06 | [x] Give range sliders a taller 28 px interaction box and a useful minimum width. |
| UI-SCALE-07 | [x] Use a clear 6 px track and a 12×20 px lozenge thumb across browser engines. |
| UI-SCALE-08 | [x] Enlarge the Model picker Thinking switch to 48×28 px with a 22 px thumb. |
| UI-SCALE-09 | [x] Give the Privacy switch the same dimensions, focus ring and reduced-motion behavior. |
| UI-SCALE-10 | [x] Review the long-pill proposal; the owner rejected it. Keep the existing desktop/mobile card radii. |
| UI-SCALE-11 | [x] Preserve the existing 20 px focus radius; do not add a new focus shape. |
| UI-SCALE-12 | [x] Preserve the existing rounded-card draft shape, including after blur. |
| UI-SCALE-13 | [x] Keep attachment, drop and running states on the existing shared card surface. |
| UI-SCALE-14 | [x] Restore the existing 40 px desktop composer actions and 44 px narrow-window targets. |
| UI-SCALE-15 | [x] Review Chat, Build and Design, plus Privacy and Knowledge Map controls, in both themes and narrow layouts; retain screenshots and live cases. |

The slider thumb uses Apple's linear-slider lozenge shape, while the track and
switches inherit Raiker's accent and semantic tokens. The composer pill was
captured and reviewed, but the owner rejected it; those screenshots are
exploratory only. Final evidence uses the restored rounded-card shape.

### 2026-11-07 — Dark theme luminance ladder

**Owner decision, 2026-11-07.** The owner reviewed the dark theme and supplied
the palette and priorities below. They apply to the dark theme; light keeps its
QUI-V01 values, including blue primary actions, until the owner decides
otherwise.

| Role | Was | Now | Token |
|---|---|---|---|
| Main background | `#121212` | `#101216` | `--bg` |
| Sidebar | `#1B1B1B` (as cards) | `#15181E` | `--sidebar-bg` |
| Cards, panels, composer | `#1B1B1B` | `#1C2027` | `--surface` |
| Hover and wells | `#161616` (darker than cards) | `#232832` | `--sunken` |
| Raised surfaces, menus, dialogs | `#222222` | `#272D36` | `--raised`, `--dialog-bg` |
| Borders | `#2A2A2A` | `#343B46` (strong `#4A5361`) | `--border`, `--border-strong` |
| Composer edge | as borders | `#5A6474` (3.1:1 on the canvas) | `--composer-edge` |
| Primary text | `#F4F1EA` | `#F2F4F7` | `--text-1` |
| Secondary text | `#B7B4AC` | `#C1C7D0` | `--text-2` |
| Muted text | `#8C8A84` (`--text-3` aliased secondary) | `#A0A7B2` | `--text-3` |
| Primary actions | blue (kept 2026-11-08: the light gold fails as text) | gold `#E0B64A`, `#101216` text | `--action` |
| Attention | `#8A6411` text, `#B8871B` fill | amber `#EE9A4D`, 6.2:1 on `--raised` (2026-11-08) | `--warn` |
| Selected navigation | blue at 13 % | blue at 20 % | `--nav-selected` |

The 15-item checklist:

1. [x] Canvas, sidebar, cards, hover wells and menus form one ordered ladder.
2. [x] The sidebar is its own step between the canvas and the cards.
3. [x] Dialog shells (Add, form and confirm dialogs) sit on the raised step.
4. [x] Primary, secondary and muted text use the supplied values; muted is its own step again.
5. [x] Borders and strong borders use the supplied values.
6. [x] Hover moves up the ladder in dark: `--sunken` was darker than a card, so hovers barely showed.
7. [x] Selected navigation is a clearer tint than hover.
8. [x] Focus stays a blue 2 px ring with its halo, at least 3:1 on every step.
9. [x] The composer has its own edge token at 3:1 against the workspace.
10. [x] Gold is the primary action (`.btn-primary`, Send, Run, the model-setup primaries); blue stays for secondary interaction.
11. [x] Semantic status colours are unchanged.
12. [x] A unit test keeps the ladder ordered and every text role at AA on every step.
13. [x] axe colour-contrast runs on every destination in dark and light against a running host.
14. [x] Dark screenshots of every destination are kept for review.
15. [x] All composers stop growing at five lines (owner decision, same day), and Build shows dictation beside Run.

Evidence: [FIXED-1305](FIXED_ITEMS.md#fixed-1305--the-dark-theme-had-no-surface-ladder-and-hover-was-invisible)
and the [Live Test docs](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-dark-ladder-and-five-line-composer).
