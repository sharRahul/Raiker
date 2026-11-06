# 07 Quick fixes and quality

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

## Quick fixes

Small changes to what is on screen today. Each is independent of the larger
redesign and can ship on its own.

| ID | Where | Now | Change | Status |
|---|---|---|---|---|
| QUI-Q01 | Home (`WorkbenchView.svelte`) | A tile reading "Runtime issues · 1": a large number and "Review configuration and readiness evidence before critical work." On a fresh workspace the one issue is "No model profile is selected." | Name each gap as a sentence with the action that fixes it. The default-model gap reads "No default model is chosen." with **Choose a model** (Models): it is the default model, which a Chat with its own model does not set ([FIXED-1074](../FIXED_ITEMS.md#fixed-1074--home-said-no-model-is-set-up-while-a-chat-was-answering)). Any other gap: its own sentence with **Open diagnostics**. No big number. | Done ([FIXED-1075](../FIXED_ITEMS.md#fixed-1075--home-showed-a-runtime-issues-count-instead-of-the-problem-qui-q01)) |
| QUI-Q02 | Home | Five start cards (conversation, build, design, task, projects) repeating the sidebar and the mode switch | Replaced by the Home composer and first-day starters | Done with QUI-H01 ([FIXED-1058](../FIXED_ITEMS.md#fixed-1058--five-start-cards-repeated-the-sidebar-and-a-first-day-had-nothing-to-start-from-qui-q02-qui-h02)) |
| QUI-Q03 | Chat composer | Placeholder "How can I help you today?" | "What would you like Raiker to do?" | Done ([FIXED-1076](../FIXED_ITEMS.md#fixed-1076--chats-placeholder-was-a-generic-chatbot-line-qui-q03)) |
| QUI-Q04 | Chat composer | With no usable model, Send is disabled next to "Not selected" | Send stays enabled. Pressing it (or Enter) with no usable model opens the model setup dialog and keeps the draft | Done ([FIXED-1077](../FIXED_ITEMS.md#fixed-1077--send-was-a-dead-button-with-no-model-qui-q04)) |
| QUI-Q05 | Chat header | A disabled, faded "New chat" on an empty conversation, and a "Background" toggle shown even when nothing runs | "New chat" appears once there is something to leave. The Background toggle appears only when background work is running, waiting, failed, or its panel is open; it stays reachable from the conversation menu | Done ([FIXED-1078](../FIXED_ITEMS.md#fixed-1078--new-chat-and-background-were-shown-with-nothing-behind-them-qui-q05)) |
| QUI-Q06 | Top bar | Search, approvals, notifications and More are icons with accessible names but no visible tooltip | A tooltip on each icon-only control, using the same words as its accessible name | Done ([FIXED-1079](../FIXED_ITEMS.md#fixed-1079--the-top-bars-icon-buttons-had-no-visible-tooltip-qui-q06)) |
| QUI-Q07 | Home, Approvals count | Approvals icon always present | Keep it: it is Approvals' only top-level entry. The count already appears only when something waits | No change |
| QUI-Q08 | Colour | The proposed attention colour `#B8871B` fails contrast | Not a code fix: the shipped `--warn` (`#866412`) already passes. The palette decision is recorded in [QUI-V01](08_BRAND_AND_VISUAL_SYSTEM.md#qui-v01--colour-tokens) | No change |

## Quality foundations

| Item | State |
|---|---|
| QUI-G01 | **Report done** ([FIXED-1096](../FIXED_ITEMS.md#fixed-1096--page-size-was-not-measured-anywhere-qui-g01)). 29 of 94 measurements over budget at first; after the 2026-10-25 round only Memory › Controls (929 px) and Memory › Map (922 px) are, both at 1440×900. Becomes a failing check once they fit; RT-QUI-63 already fails on Settings › General, Privacy and Advanced and Diagnostics at 1280×800. |
| QUI-G02 | **Done** ([FIXED-1095](../FIXED_ITEMS.md#fixed-1095--user-facing-copy-used-words-the-plan-retires-qui-g02)). |
| QUI-G03 | **Done** ([FIXED-1097](../FIXED_ITEMS.md#fixed-1097--there-was-no-single-place-to-see-every-shared-state-qui-g03)), at `#/state-gallery` in development builds. |
| QUI-G04 | **Partly done** ([FIXED-1100](../FIXED_ITEMS.md#fixed-1100--a-long-conversation-rendered-every-turn-qui-g04)): long transcripts. Open: actions that paint first and roll back visibly. |
| QUI-G05 | **Done** ([FIXED-1098](../FIXED_ITEMS.md#fixed-1098--keyboard-use-and-zoom-were-not-checked-qui-g05)). |
| QUI-G06 | **Partly done** ([FIXED-1099](../FIXED_ITEMS.md#fixed-1099--stop-steer-and-continue-errors-blamed-the-local-runtime-qui-g06)): the helper and the Chat, Build and Tasks errors, followed by the Memory, Models, Connections, Settings, Projects, and Approvals, Library and Sessions slices below. Other views still need their audit. |
| QUI-G07 | Open: needs five people, not code. |

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

## 2026-11-06 — QUI-G06 Memory error recovery

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
[WEB_APP_LIVE_TEST.md](../../architecture/WEB_APP_LIVE_TEST.md).
QUI-G06 remains partial: other views still need their error audit. QUI-G01,
QUI-G04 and QUI-G07 also remain open, so this document is retained.

## 2026-11-06 — QUI-G06 Model recovery

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
[Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-model-recovery)
and [FIXED-1287](../FIXED_ITEMS.md#fixed-1287--model-management-errors-were-hidden-misleading-or-had-no-recovery-step-qui-g06).
The remaining quality foundations above keep this plan open.

## 2026-11-06 — QUI-G06 Connection recovery

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
[Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-connection-recovery),
[FIXED-1288](../FIXED_ITEMS.md#fixed-1288--connection-failures-claimed-rollback-or-lost-their-recovery-message-qui-g06)
[FIXED-1289](../FIXED_ITEMS.md#fixed-1289--adding-a-service-lost-its-sign-in-step-after-installation)
and [FIXED-1290](../FIXED_ITEMS.md#fixed-1290--the-server-rename-row-clipped-cancel-at-200-percent-zoom).
Other quality foundations remain open; this document is retained until those
requirements are met.

## 2026-11-06 — QUI-G06 Settings recovery

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

Evidence: [Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-settings-recovery)
and [FIXED-1297](../FIXED_ITEMS.md#fixed-1297--settings-errors-hid-uncertainty-and-offered-no-recovery-qui-g06).

## 2026-11-06 — QUI-G06 Projects recovery

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

Implementation and evidence: [FIXED-1299](../FIXED_ITEMS.md#fixed-1299--projects-failures-hid-missing-content-or-offered-no-safe-recovery-qui-g06),
[FIXED-1300](../FIXED_ITEMS.md#fixed-1300--project-limits-stayed-loading-after-failure-and-claimed-rollback)
and [Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-projects-recovery).
The related live setup helper repair is
[FIXED-1301](../FIXED_ITEMS.md#fixed-1301--live-setup-preparation-consumed-the-helpers-navigation-budget).

## 2026-11-06 — QUI-G06 Approvals, Library and Sessions recovery

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
([FIXED-1303](../FIXED_ITEMS.md#fixed-1303--an-open-approvals-queue-missed-a-decision-raised-after-it-loaded)).

Implementation and evidence: [FIXED-1302](../FIXED_ITEMS.md#fixed-1302--approvals-library-and-sessions-errors-hid-uncertain-writes-qui-g06)
and [Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-qui-g06-approvals-library-and-sessions-recovery).
QUI-G01, QUI-G04, QUI-G07 and the remaining QUI-G06 views stay open, so this
document is retained.
