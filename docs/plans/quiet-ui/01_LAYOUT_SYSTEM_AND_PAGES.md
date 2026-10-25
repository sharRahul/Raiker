# 01 Layout system and pages

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

## Status

**Layouts and four page plans shipped 2026-10-21**
([FIXED-1101](../FIXED_ITEMS.md#fixed-1101--the-shell-was-wider-and-looser-than-the-layout-system-qui-l01-qui-l14)
to [FIXED-1123](../FIXED_ITEMS.md#fixed-1123--chats-readiness-steps-disappeared-with-the-models-overview-qui-l08);
live cases RT-QUI-17 to RT-QUI-25 in
[WEB_APP_LIVE_TEST.md](../../architecture/WEB_APP_LIVE_TEST.md)). **Diagnostics,
Recovery, the pages that already fit, and Build and Design shipped 2026-10-25**
([FIXED-1170](../FIXED_ITEMS.md#fixed-1170--diagnostics-opened-on-seven-tiles-reading-ready-and-0-qui-l11)
to [FIXED-1175](../FIXED_ITEMS.md#fixed-1175--design-had-no-revision-strip-and-builds-postures-said-edit-and-auto-qui-l13);
live cases RT-QUI-61 to RT-QUI-63 and RT-QUI-67).

| Item | State |
|---|---|
| Shell | **Done.** Sidebar 232 px, 40 px rows, one 1,180 px page width, 2rem gutter (1.5rem below 1,280 px). |
| QUI-L01 | **Done** through the shell sizes; Chat, Build and Design keep their own composers (03, L13). |
| QUI-L02 | **Done.** `ListDetail.svelte`, used by Connections, Channels, Permissions and My models. |
| QUI-L03 | **Done** for Security, Account, Privacy and General: rows, with forms in dialogs (`FormDialog.svelte`) and explanations in disclosures. Advanced › Runtime shows one line per environment with its detail on request. Other Settings sections keep their cards. |
| QUI-L04 | **Done.** `AddDialog.svelte`: Add connection, Add channel, Add model. It is a page-level layer, not a top-layer modal, so a sign-in window a step opens draws above it. |
| QUI-L05 | **Done.** The help panel. |
| QUI-L06 | **Done.** Category rail, policy in words, the detail pane, **Select several** and **Group by technical area** in **⋯**. A **Schedules** category was added. Deviation: *Not decided here* and *How your permissions apply* stay as read-only disclosures under **Advanced** rather than help articles, because they show this account's live data. |
| QUI-L07 | **Done.** |
| QUI-L08 | **Done.** Deviation: the global spending limit lives in **Settings → Advanced → Usage and spending**, beside spend across providers, rather than on Models. |
| QUI-L09 | **Done.** Deviation: Account is part of **General** rather than its own section. |
| QUI-L10 | **Done.** The Guide page is gone; `#/guide…` opens the panel. |
| QUI-L11 | **Partly done.** Overview is *What needs attention* with one card per issue and healthy systems folded (FIXED-1170); Checkpoints is **Recovery**, and a restore first says what will be undone and what stays, with Restore never the dominant button (FIXED-1171). Open: Sessions into Work › Threads, activity inside each task and project, Recovery reached from the affected task, live work on Home only. |
| QUI-L12 | **Done**, except Projects, which stays a card grid. Work pages after 50 rows with 64 px thread and goal rows (FIXED-1172); Memory's map opens from Memories and Recall folds into Controls (FIXED-1173); Approvals' evidence is closed below 1,600 px (since 2026-10-22); Connections › Advanced is one segmented list. |
| QUI-L13 | **Done.** Design's revision strip of three 56 px thumbnails; Build's postures are Plan · Suggest changes · Run within limits (FIXED-1175). Build's rail and side panel were already closed by default, and Design's export already existed only once a picture did. |
| QUI-L14 | **Done.** 1,024–1,279 px shows the icon rail. |
| Acceptance | **Partly met.** No destination shows a catalogue; old addresses forward. Size: Memory › Controls (929 px) and Memory › Map (922 px) are still just over budget at 1440×900; every other destination fits (TO_BE_FIXED, QUI-G01 follow-up). |

## The problem, measured

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

## How the reference products keep pages short

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

## Shell

| Element | Decision |
|---|---|
| Sidebar | 232 px. Rows 40 px. Home, Chat, Build, Design, Work, Memory, then More. (Now 256 px: `--sidebar-w` in `web/src/app.css`.) |
| Top bar | 56 px: page context, search, approvals count (only when something waits), notifications, live work line (06, QUI-F04) |
| Content gutter | 32 px desktop, 24 px narrow window |
| Standard content max width | 1,180 px |
| Reading / transcript width | 680–760 px |
| Side panel (context rail) | 320 px, at most 360 px, closed by default |

## Screen sizes (QUI-L14)

| Size | Behaviour |
|---|---|
| Desktop, 1920×1080 and up | Content keeps its maximum widths. Extra space becomes margin, never longer lines. Two side panels may be open together (for example Build's files and checks). |
| Laptop, 1440×900 | The reference size. Every budget is measured here. List and detail side by side; one side panel open at a time. |
| Small laptop, 1280×800 | Sidebar stays 232 px. A side panel opens over the content instead of squeezing it. Approvals' evidence panel opens on request. |
| Narrow window, 1024–1279 px | Sidebar becomes a 64 px icon rail. 1024×680 is the desktop app's minimum window size. |
| Web, below 1024 px | A single readable column with no separate design. Phones get the mobile app. |

## The five layouts

Every page uses exactly one.

### QUI-L01 — A · Workspace

Rail, work column, context panel, composer anchored at the bottom of the work
column. Used by Chat, Build and Design. Already in place; rails closed by
default.

### QUI-L02 — B · List and detail

Header with tabs and search; a list of 56–72 px rows on the left; the selected
item on the right, at most 680 px wide. Used by Permissions, Connections,
Models, Work, Memory and Approvals. A shared Svelte component, with a draggable
split that cannot shrink the list below a readable row (Hermes clamps at
180 px list, 320 px detail).

Acceptance: keyboard up/down moves selection; Enter opens; the selected item has
its own address so it can be linked; an empty list hides its search field.

### QUI-L03 — C · Settings

Section rail (224 px) and a content column (at least 680 px). Every setting is a
row: label, current value, one action. Forms (change password, vault key, breach
check, standing grant) open in a dialog, not inline. A sub-page is at most 1.5
screens. A Save bar appears only after a change.

### QUI-L04 — D · Add dialog

A 640 px centred dialog: search, categories, one card per option, then the
chosen option's steps. Used by Add connection, Add channel, Add model, Add
memory. Choose the source first; later steps show only that source.

### QUI-L05 — E · Help panel

A 360 px panel opened from **?**, starting on the article for the current page,
with search. The command palette searches the same articles under a Help group.
Replaces the Guide page.

## Page plans

### QUI-L06 — Permissions

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

Details of the permission model: [02](02_PERMISSIONS_AND_APPROVALS.md).

### QUI-L07 — Connections (renamed from Extensions)

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
* Connection detail: [02, QUI-P04](02_PERMISSIONS_AND_APPROVALS.md#qui-p04--connection-detail).

### QUI-L08 — Models

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

### QUI-L09 — Settings

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

### QUI-L10 — Guide becomes the help panel

Target: no page (from 11,797 px).

* Each current Guide heading becomes one article with its own address, so old
  links still land somewhere.
* **?** opens the help panel on the current page's article.
* The explanations removed from Permissions, Models and Settings become articles.

### QUI-L11 — Observability becomes Diagnostics and Recovery

* Overview becomes **Diagnostics**: "What needs attention", one card per issue
  (observed problem, impact, last check, safe fix, technical details), healthy
  systems collapsed. With no issues, one line.
* Sessions move to Work › Threads (searchable). Activity appears inside each
  task or project. Checkpoints become **Recovery**, reached from the affected
  task or project. Live work moves to Home › In progress. Notifications is the
  top-bar centre.
* The word Observability leaves navigation. Old addresses forward
  (`ROUTE_ALIASES` in `web/src/lib/nav.ts`). **Done 2026-10-21**: the
  destination is called Diagnostics ([FIXED-1095](../FIXED_ITEMS.md#fixed-1095--user-facing-copy-used-words-the-plan-retires-qui-g02));
  the rest of this item is open.

Recovery, before restore, shows: checkpoint source and time, affected items,
what will be undone, what remains, Create safety checkpoint, and Restore.
Restore is never the dominant button.

### QUI-L12 — Pages that already fit

| Page | Layout | Change |
|---|---|---|
| Home | Single column, 980 px | See [03](03_WELCOME_HOME_AND_CHAT.md). |
| Chat, Build, Design | A | Composer specs in 03. No size change. |
| Work (Threads, Goals, Tasks, Projects) | B | 64 px rows with the selected item beside them. Paginate after 50 rows. |
| Memory | B | Knowledge map leaves the tabs and opens from search results. Recall folds into Controls. |
| Approvals | B | Queue and decision side by side; evidence panel closed below 1,600 px. |
| Connections › Advanced | B | One segmented list instead of four tabs. |

### QUI-L13 — Build and Design specifics

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

## Acceptance for this document

* Every destination fits its budget at 1440×900 and 1280×800 with an empty
  workspace ([07, QUI-G01](07_QUICK_FIXES_AND_QUALITY.md)).
* No destination shows a catalogue of things that could be added.
* Every removed page's old address opens its new home.
