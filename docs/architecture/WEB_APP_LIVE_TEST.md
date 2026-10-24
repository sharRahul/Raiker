# Web App Live Test — model backends

> A repeatable procedure + results matrix for exercising the Raiker web app
> against a real model backend. One round was run against **hosted Anthropic
> (Haiku 4.5)**; the same steps apply to every other backend (see the matrix).
> **Never commit an API key.** A test round either enters it through Raiker's
> encrypted Models UI or reads it from the owner's environment for that run;
> credentials never belong in a spec, command, log or screenshot.

## What this verifies

The full served web stack end to end: `raiker-web` (FastAPI + the built SPA) →
owner session mint → governed read endpoints → a **streamed prompt turn** →
the model provider → the audit event log. It also exercises the two features in
PR #106: the **user-owned fallback sequence** and **prompt caching + normalised
cache-hit metrics**.

## Result — 2026-10-24 (Quiet UI features and improvements, hosted Anthropic Haiku 4.5)

Fifteen features of the [Quiet UI plan, 06](../plans/quiet-ui/06_FEATURES_AND_IMPROVEMENTS.md#status)
([FIXED-1150](../plans/FIXED_ITEMS.md#fixed-1150--nothing-outside-chat-said-that-work-was-running-qui-f04)
to [FIXED-1167](../plans/FIXED_ITEMS.md#fixed-1167--two-long-transcript-tests-ran-at-their-time-limit-quality-found-this-round)).
Fresh workspaces served by `raiker-web` at 1440×900. Anthropic was connected
through **Add model**, with the key and workspace ID typed from the run's
environment; neither appears in a spec, command, document, screenshot or the
server log. Spec: `web/e2e/quiet-ui-features-live.spec.ts`, developed against
two workspaces, then run on a third fresh workspace: RT-QUI-44 to 50 in one
run, and RT-QUI-51 to 56 after a fix to the spec's own reload — **13/13**. The
desktop-only parts (the tray, a project in its own window, Quick Entry's global
shortcut) are proved by `desktop/e2e/shell.spec.ts` under Xvfb: **12/12**.

| Case | Check | Result |
|---|---|---|
| RT-QUI-44 | Anthropic connects through **Add model → An account I have**, Haiku 4.5 kept and made the default | ✅ |
| RT-QUI-45 | Home's composer reads *Sent to Anthropic*, and *Sent to Anthropic, with 1 file* once a document is attached | ✅ |
| RT-QUI-46 | While a turn runs the top bar reads *New chat · Writing the answer*, and the line is gone when it ends; the turn ends with *Haiku 4.5 · ≈ $0.0128 · 1 file read · nothing else left this computer*, which opens to *Model*, *Cost*, *Read*, *Changed or sent* and *Left this computer: The conversation, to Anthropic* | ✅ after fixes found in this round: the provider read *anthropic* in lower case |
| RT-QUI-47 | Haiku calls `ask_owner_question`: a card reads *Waiting for your answer* and *1 of 2*, the row *waiting for your answer*, and there is no **Allow once**; Hi, then Tue and Wed, **Confirm and continue**, and the answer reads *Hi! I'm available to help you on Tuesday and Wednesday* under *Completed · 1 step* | ✅ after fixes found in this round ([FIXED-1152](../plans/FIXED_ITEMS.md#fixed-1152--an-answered-question-read-as-a-failed-step-qui-f02-found-live)): the answered question read *failed* and the turn *Partially completed*; the parked turn also said *Waiting for your decision* |
| RT-QUI-48 | *That's wrong — Anna prefers short replies. Reply with one short sentence…* is answered and followed by *Remember: Anna prefers short replies?*; **Save** puts it in Memory › Memories | ✅ after a fix found in this round ([FIXED-1162](../plans/FIXED_ITEMS.md#fixed-1162--a-correction-was-forgotten-as-soon-as-it-was-made-qui-f20)): the offer took the follow-up instruction too and read *replies.?* |
| RT-QUI-49 | Ctrl+K, *Anna*: **Chats** and **Memories** groups; the **Memories** filter hides the chats; choosing the memory opens Memory › Memories with its details open | ✅ |
| RT-QUI-50 | **Save as routine** opens Work › Tasks with the request and *Last time this took these steps: …*, on **Repeating**; **Morning brief** fills the instruction, *Daily* and *Results appear on Home and in this task's own conversation*; nothing is created | ✅ |
| RT-QUI-51 | Memory › Controls: an active built skill under *What Raiker has learned to do*, *Approvals you've given* empty; **Undo** turns the skill off | ✅ |
| RT-QUI-52 | Settings › Personalisation › **Chat text size** reads 110%; 140% sets `--chat-text-scale` to 1.4 | ✅ |
| RT-QUI-53 | Settings › Notifications lists *Approval needed*, *Input needed*, *Response ready*, *Task failed* and *Background task finished*, all on; *Input needed* off is kept across a reload | ✅ |
| RT-QUI-54 | Work › Threads › Organise › **Archive** asks in the one dialog (**Cancel** / **Archive**); Esc closes it with nothing archived | ✅ |
| RT-QUI-55 | `#/quick-entry` at 560×120: the input has focus, *Send to* is **New task**; Enter files the task and the top bar shows *Write a three-line haiku…* | ✅ after a fix found in this round: the long title pushed the stop switch off the top bar |
| RT-QUI-56 | In a browser, Settings › General has no *Desktop window* section | ✅ |
| Suites | Python suite; web unit suite, `svelte-check`, ESLint, design tokens, build; desktop unit tests, lint, type-check and shell end-to-end; ruff, mypy | ✅ |
| Visual review | `docs/screenshots/2026-10-24-quiet-ui-features/` (45–55), inspected at original resolution: the live line overflow, Memory › Controls' spacing, the lower-case provider and the doubled *Ask owner question* on the floating card were found from the images and fixed. Still seen: a question's notice stays after it is answered ([TO_BE_FIXED](../plans/TO_BE_FIXED.md#2026-10-24-quiet-ui-features-round--what-is-still-open)). Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-23 (Quiet UI visual answers, hosted Anthropic Haiku 4.5)

The visual answers of the [Quiet UI plan](../plans/quiet-ui/04_VISUAL_ANSWERS.md#status)
([FIXED-1136](../plans/FIXED_ITEMS.md#fixed-1136--a-turn-could-not-say-these-are-the-headline-numbers-qui-a04)
to [FIXED-1149](../plans/FIXED_ITEMS.md#fixed-1149--a-chart-in-a-transcript-bubble-was-too-small-to-read-and-its-legend-had-no-colours-04-screenshot-review)).
Fresh workspaces served by `raiker-web` at 1440×900. Anthropic was connected
through **Add model**, with the key and workspace ID typed from the run's
environment; neither appears in a spec, command, document, screenshot or the
server log. Spec: `web/e2e/quiet-ui-visual-answers-live.spec.ts`, developed
against two workspaces, then run whole on a third fresh workspace: **9/9 in
3.6 min**. Most cases ask the model to send back blocks the spec wrote, so they
check Raiker's validation and drawing rather than what a model chooses;
RT-QUI-37 and RT-QUI-43 let the model choose.

| Case | Check | Result |
|---|---|---|
| RT-QUI-35 | Anthropic connects through **Add model → An account I have**, Haiku 4.5 kept and made the default | ✅ |
| RT-QUI-36 | **Settings → General → Answers**: *Answer style* reads *Auto*; *Visual where it helps* is kept across a reload | ✅ |
| RT-QUI-37 | Asked to compare three laptops from figures given in the prompt, Haiku answers with key figures, a comparison and a verdict callout; Raiker marks *Best* on 18 h, 1.09 kg and £999 — three marks, none chosen by the model. Above three blocks the answer offers **Create document** | ✅ after fixes found in this round ([FIXED-1148](../plans/FIXED_ITEMS.md#fixed-1148--a-block-whose-json-opened-on-the-fence-line-was-drawn-as-code-qui-a-rules), FIXED-1136, FIXED-1144): blocks with their JSON on the fence line were drawn as code, then refused as one invalid block; prices read *999 £*; the comparison came without a source and was shown as text until the instructions said how to cite figures the user gave; key figures came as three blocks until they said *all in one block* |
| RT-QUI-38 | Key figures (*≈ estimate*, *Source: …*), a measure (*31 of 40*, a `<meter>` named *Checks passed: 31 of 40*), a warning callout, pros and cons (*Pros*, *Cons*) and three steps on the path line | ✅ |
| RT-QUI-39 | Horizontal bars, 100% stacked bars and a scatter draw; **Table** shows the stacked shares (*60%*) and **Chart** brings the drawing back; **CSV** downloads `battery-life.csv` with *ThinkPad X1 Carbon,15*; **PNG** downloads a real PNG; **Show as text** reads *MacBook Air 13 · 18*; **Copy** says *Copied* and the clipboard holds the rows | ✅ after a fix found in the screenshot review ([FIXED-1149](../plans/FIXED_ITEMS.md#fixed-1149--a-chart-in-a-transcript-bubble-was-too-small-to-read-and-its-legend-had-no-colours-04-screenshot-review)): charts rendered at about 6 px text and the legend had no colours |
| RT-QUI-40 | Figures with no source read *Longest battery: 18 h (MacBook Air 13)* with *No source was given for these numbers, so Raiker shows them as text*; a figure with no unit is **Not rendered** with *figures_unit_missing*; the prose either side survives | ✅ |
| RT-QUI-41 | Four blocks: *This answer has 4 blocks* with **Create document**, which puts *…into a document I can keep* in the composer without sending it | ✅ |
| RT-QUI-42 | **Export conversation → Markdown** carries the comparison as a table with *18 — Best*, and no `raiker:compare` fence in Raiker's section | ✅ |
| RT-QUI-43 | On *Mostly text*, a question with three comparable weights is answered in prose with no block | ✅ after a fix found in this round (FIXED-1145): Haiku drew a comparison until the style sentence said it overrides the general guidance |
| Suites | Python suite (3 workers), `tests/test_visual_answers.py`; web unit suite, `svelte-check`, ESLint, design tokens, build; ruff, mypy | ✅ |
| Visual review | `docs/screenshots/2026-10-23-quiet-ui-visual-answers/` (36–43), inspected at original resolution; FIXED-1149 was found from the images. Still seen: the Plan card covers the *Completed · N steps* line ([TO_BE_FIXED](../plans/TO_BE_FIXED.md#2026-10-23-quiet-ui-visual-answers-round--what-is-still-open)). Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-22 (Quiet UI permissions and approvals, hosted Anthropic Haiku 4.5)

The approvals round of the [Quiet UI plan](../plans/quiet-ui/02_PERMISSIONS_AND_APPROVALS.md#status)
([FIXED-1125](../plans/FIXED_ITEMS.md#fixed-1125--an-unanswered-approval-waited-a-day-and-the-wait-could-not-be-set-qui-p06)
to [FIXED-1135](../plans/FIXED_ITEMS.md#fixed-1135--nothing-checked-that-a-model-could-not-draw-an-approval-card-qui-p05-acceptance)).
Fresh workspaces served by `raiker-web` at 1440×900 (1680×1000 for the wide
Approvals check). Anthropic was connected through **Add model**, with the key and
workspace ID typed from the run's environment; neither appears in a spec,
command, document, screenshot or the server log. Spec:
`web/e2e/quiet-ui-permissions-live.spec.ts`, developed against one workspace,
then run whole on a second fresh workspace: **9/9 in 3.6 min**. RT-QUI-31 moves a
waiting approval's expiry into the past through the store
(`RAIKER_LIVE_WORKSPACE`, `RAIKER_LIVE_PYTHON`) instead of waiting 30 minutes.

| Case | Check | Result |
|---|---|---|
| RT-QUI-26 | **Settings → Security** has *Approvals and standing access* with **Unanswered approvals expire after** at *30 minutes*; *1 hour* is kept across a reload, then set back | ✅ |
| RT-QUI-27 | Anthropic connects through **Add model → An account I have**, Haiku 4.5 kept and made the default | ✅ |
| RT-QUI-28 | Chat's profile chip reads **Standard**; its menu offers **Careful** and **Standard** with their consequences and no Skip, Off, Always allow or Within limits; **Permissions → Advanced** opens with *When something needs your decision*. File writes and the approval relay are turned on (Ask me) for the next cases | ✅ after a fix found in this round: the approval mode sat below the sixteen Advanced rows, and now leads them |
| RT-QUI-29 | In a **Careful** chat, *create careful-live.txt* stops on the **Raiker Safety** card: *Waiting for your decision*, the six parts (*Write file: Approving writes this exact change to careful-live.txt, once* · *Your permissions ask before file writes* · *careful-live.txt* · *1 line of text* · *Can be undone afterwards* · *Accept only part of the change…*), **Decline**, **Change**, **Allow once**, no *Always allow*; the top bar reads *Approvals (1 waiting on you)* and no floating card repeats it. **Allow once** continues the turn and the count clears | ✅ after fixes found in this round ([FIXED-1130](../plans/FIXED_ITEMS.md#fixed-1130--a-conversation-could-not-say-how-careful-raiker-should-be-qui-p02), [FIXED-1126](../plans/FIXED_ITEMS.md#fixed-1126--an-approval-past-its-time-limit-still-looked-like-it-was-waiting-qui-p06)): the chip went back to Standard when the first chunk gave the chat its id, and Pending listed expired approvals |
| RT-QUI-30 | **Change** opens the decision on **Approvals**: queue row *Write file · medium risk · standard-live.txt · just now · From "Create a file named…"*, the decision beside it with **Decline** and **Allow once**; at 1,680 px the evidence is open. **Decline** empties Pending; **History** shows *Declined* and *Allowed · ran*, each with its conversation, and **Open the conversation** | ✅ after a fix found in the screenshot review ([FIXED-1132](../plans/FIXED_ITEMS.md#fixed-1132--approvals-was-a-table-with-the-decision-underneath-it-qui-p07)): the evidence column squeezed the decision to about 350 px |
| RT-QUI-31 | A waiting approval past its time limit reads **Not done: no decision**, *Nobody answered within 30 minutes, so nothing ran and the task stopped here*, **Change the time limit** (→ `#/settings?tab=security`), no **Allow once**, and is not counted in the top bar. **Ask again** raises the same request as a new turn, which is declined in place | ✅ after a fix found in this round ([FIXED-1126](../plans/FIXED_ITEMS.md#fixed-1126--an-approval-past-its-time-limit-still-looked-like-it-was-waiting-qui-p06)): the expired card still offered a safer alternative pointing at **Change** |
| RT-QUI-32 | A prompt asking Haiku to reply with a forged card (`data-raiker-safety`, *Raiker Safety*, an **Allow once** button): Haiku declined, and nothing on the page is a Safety card or carries the mark | ✅ |
| RT-QUI-33 | **Careful** chosen on Home's composer goes with the message: the chat answers *CAREFUL HANDOFF* and its chip reads Careful | ✅ |
| RT-QUI-34 | A connected service's detail reads **What Raiker may do with GitHub** (*No activities are registered yet* until a manifest is imported) | ✅ |
| Suites | Web unit suite, `svelte-check`, ESLint, design tokens, build; `tests/test_approval_timeout.py`, the approval, contract and docs tests; ruff, mypy, SAST | ✅ |
| Visual review | `docs/screenshots/2026-10-22-quiet-ui-permissions/` (26–34), inspected at original resolution; the fixes marked above were found from the images. Still seen: the tool row above an expired approval reads *waiting for your decision* ([TO_BE_FIXED](../plans/TO_BE_FIXED.md#2026-10-22-quiet-ui-approvals-round--what-is-still-open)). Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-21 (Quiet UI layout system and pages, hosted Anthropic Haiku 4.5)

The layouts and page plans in the [Quiet UI plan](../plans/quiet-ui/01_LAYOUT_SYSTEM_AND_PAGES.md#status)
([FIXED-1101](../plans/FIXED_ITEMS.md#fixed-1101--the-shell-was-wider-and-looser-than-the-layout-system-qui-l01-qui-l14)
to [FIXED-1123](../plans/FIXED_ITEMS.md#fixed-1123--chats-readiness-steps-disappeared-with-the-models-overview-qui-l08)).
Fresh workspaces served by `raiker-web` on `127.0.0.1:8765` at 1440×900 (and
1100×800 for the narrow window). Anthropic was connected through **Add model**,
with the key and workspace ID typed from the run's environment; neither appears
in a spec, command, document, screenshot or the server log. Spec:
`web/e2e/quiet-ui-layout-live.spec.ts`, run twice on fresh workspaces, the
second time after the readiness fix below.

| Case | Check | Result |
|---|---|---|
| RT-QUI-17 | The sidebar is 232 px with 40 px rows; at 1,100 px wide it is a 64 px icon rail; a page is at most 1,180 px wide | ✅ |
| RT-QUI-18 | **Connections** opens on **Services** with *Nothing is connected yet*; **Add connection** shows the catalogue with search and categories; choosing a service shows only its steps; **GitHub sign-in** opens its sign-in window above the dialog; Advanced is one segmented list | ✅ after fixes found in this round ([FIXED-1115](../plans/FIXED_ITEMS.md#fixed-1115--sign-in-for-a-connection-opened-under-the-add-dialog-qui-l04), [FIXED-1116](../plans/FIXED_ITEMS.md#fixed-1116--add-connection-offered-github-twice-qui-l07), [FIXED-1118](../plans/FIXED_ITEMS.md#fixed-1118--the-list-separator-had-no-value-for-assistive-technology-qui-l02)) |
| RT-QUI-19 | **Channels** lists linked channels only; **Add channel** lists every channel and opens one's pairing steps | ✅ |
| RT-QUI-20 | **Permissions**: the category rail, rows saying their policy in words, one permission's detail beside the list with the four-way choice; the category and permission are in the address; **⋯ → Select several** turns the list into a checklist | ✅ |
| RT-QUI-21 | **Models** on a fresh workspace: no tabs, *No default model is chosen*, Chat's four readiness steps with *Provider connected* marked and **Connect a provider**. **Add model** → **An account I have** → Anthropic → key → Haiku 4.5 → **Make default**; the profile card names Haiku 4.5 and My models lists it with its usage | ✅ after fixes found in this round ([FIXED-1119](../plans/FIXED_ITEMS.md#fixed-1119--a-rows--menu-was-cut-off-inside-a-dialog-qui-l04), [FIXED-1120](../plans/FIXED_ITEMS.md#fixed-1120--make-default-in-add-model-had-no-model-to-choose-qui-l08), [FIXED-1123](../plans/FIXED_ITEMS.md#fixed-1123--chats-readiness-steps-disappeared-with-the-models-overview-qui-l08)) |
| RT-QUI-22 | A Chat turn answers on the model Add model made the default | ✅ |
| RT-QUI-23 | **Settings**: Account inside General (*Signed in as Rahul*); **Advanced** with Runtime, Memory engine, Model serving and Usage and spending; **Security** as rows, each action opening its form in a dialog; `#/settings?tab=github` opens Connections on GitHub sign-in | ✅ after a fix found in this round ([FIXED-1117](../plans/FIXED_ITEMS.md#fixed-1117--an-old-github-settings-link-did-nothing-while-settings-was-open-qui-l09)) |
| RT-QUI-24 | **?** opens Help beside the page on that page's article; search finds an article; a link inside opens the other article in the panel; **Escape** closes it; `#/guide?section=…` opens the panel on that article | ✅ |
| RT-QUI-25 | Heights at 1440×900: Connections Services and Channels, Permissions, Models and Security 844 px each; Settings General 1,326 px | ✅ after a fix found in this round ([FIXED-1121](../plans/FIXED_ITEMS.md#fixed-1121--settings-general-was-twice-the-page-budget-qui-l09-qui-g01)): General was 2,117 px |
| QUI-G01 | Size report: 8 of 70 measurements over budget (29 of 94 before), all on pages this round did not rebuild (listed in [TO_BE_FIXED](../plans/TO_BE_FIXED.md#2026-10-21-quiet-ui-round-2--what-is-still-open)) | Report, as planned |
| Re-run | RT-QUI-14 and RT-QUI-15 (keyboard walk and 200% zoom) on the new pages; `all-pages-live` | ✅ |
| Suites | Web unit suite; mocked `composer.spec.ts` 16/16; `svelte-check`, ESLint, design tokens, build; the Python tests that read web source and the docs | ✅ |
| Visual review | `docs/screenshots/2026-10-21-quiet-ui-layout/` (17–25), inspected at original resolution. Found from the images: a doubled focus box on search fields ([FIXED-1122](../plans/FIXED_ITEMS.md#fixed-1122--search-fields-drew-a-second-focus-box-qui-l02)) and the readiness steps sitting outside the profile card, moved inside it. Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-21 (Quiet UI round 2: Home, Chat, setup and quality checks, hosted Anthropic Haiku 4.5)

The second round of the [Quiet UI plan](../plans/quiet-ui/03_WELCOME_HOME_AND_CHAT.md#status)
and [07](../plans/quiet-ui/07_QUICK_FIXES_AND_QUALITY.md)
([FIXED-1080](../plans/FIXED_ITEMS.md#fixed-1080--home-offered-five-threads-to-continue-instead-of-the-one-with-its-next-step-qui-h01)
to [FIXED-1100](../plans/FIXED_ITEMS.md#fixed-1100--a-long-conversation-rendered-every-turn-qui-g04)).
Fresh workspaces served by `raiker-web` on `127.0.0.1:8765`. The round-1 spec
ran first on the same workspace and connected Anthropic through the Models
dialog, with the key and workspace ID typed from the run's environment; neither
appears in a spec, command, document, screenshot or the server log. Specs:
`quiet-ui-round-2-live.spec.ts`, `first-launch-live.spec.ts`,
`quiet-ui-accessibility-live.spec.ts`, and the size report in `all-pages-live.spec.ts`.

| Case | Check | Result |
|---|---|---|
| RT-QUI-10 | Home after work shows one **Continue where you left off** card — the latest thread, *1 turn · updated 1m ago*, **Continue**, **All threads (3)** — in one column no wider than 980 px | ✅ |
| RT-QUI-11 | A text file attached with **Add attachment → Upload document** on Home rides the message into Chat; the turn shows the file and Haiku answers with the code word inside it (*PELICAN*) | ✅ |
| RT-QUI-12 | In that chat **Search in conversation** for *pelican* reads *1 of 1* and marks the turn. **Context** opens the panel with *code-word.txt* under Context and a Sources tab; at 1,280 px it opens over the transcript and ends above Send, at 1,920 px it sits beside the transcript | ✅ after a fix found in this round ([FIXED-1088](../plans/FIXED_ITEMS.md#fixed-1088--the-context-panel-covered-chats-send-at-laptop-width-qui-c12)): at 1,280 px the panel covered the model picker and Send |
| RT-QUI-13 | **Tools → Run in background** files the draft as a task: *Running in the background. Open the task*, the composer is empty, and the task page shows it. The task then ran on Haiku and its notification arrived while RT-QUI-12 was rerun | ✅ |
| RT-QUI-14 | Tab through every destination at 1440×900: focus never lands on an invisible control and is always marked | ✅ |
| RT-QUI-15 | Chat at 200% zoom on a 1280×800 screen (640×400 CSS px): the prompt and **Send** stay in view | ✅ |
| RT-QUI-16 | A fresh workspace opens setup as a conversation: *Hi, I'm Raiker…* with **Skip setup** and the progress line *Name · This device · Model · Privacy · Check · Start* (source install). The name *Rahul* is saved; *Where should I think?* offers **On this computer** (*About 3B–8B parameters fits here*), **An account I have** and **Decide later**, with the earlier answer kept above; *Here is how I'll work for you.* shows the ask-before card; the last step says *Setup is saved. Chat and Build need a model before they can answer.* with **Choose a model**, the four starters and a composer kept as *Getting started*; **Go to Home** greets *Good afternoon, Rahul* | ✅ |
| QUI-G01 | Size report at 1440×900 and 1280×800: 29 of 94 measurements over budget, all on pages the layout plan rebuilds (listed in [TO_BE_FIXED](../plans/TO_BE_FIXED.md#2026-10-21-quiet-ui-round-2--what-is-still-open)) | Report, as planned |
| Re-run | Round 1 (`quiet-ui-home-chat-live`) 9/9 again on the new Home, setup and copy | ✅ |
| Suites | Web unit suite (2,436); mocked `composer.spec.ts` 16/16; `svelte-check`, ESLint, design tokens, build; docs consistency tests | ✅ |
| Visual review | `docs/screenshots/2026-10-21-quiet-ui-round-2/` (10–19), inspected at original resolution; the overlay defect above was found from the 1,280 px image. Still seen: Home's *No default model is chosen.* beside a Chat answering on Haiku (BUG-357, open). Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-21 (Quiet UI Home and Chat, hosted Anthropic Haiku 4.5)

QUI-H01 to QUI-W06 from the [Quiet UI plan](../plans/quiet-ui/03_WELCOME_HOME_AND_CHAT.md)
([FIXED-1057](../plans/FIXED_ITEMS.md#fixed-1057--home-had-no-way-to-start-work-by-asking-qui-h01)
to [FIXED-1079](../plans/FIXED_ITEMS.md#fixed-1079--the-top-bars-icon-buttons-had-no-visible-tooltip-qui-q06)).
A fresh workspace served by `raiker-web` on `127.0.0.1:8765` at 1440×900. The
identity-linked Anthropic key and workspace ID were typed into the Models dialog
by the spec from the run's environment; neither appears in a spec, command,
document, screenshot or the server log. Spec: `web/e2e/quiet-ui-home-chat-live.spec.ts`.

| Case | Check | Result |
|---|---|---|
| RT-QUI-01 | A first-day Home reads *Welcome, Rahul*, opens with **Ask Raiker**, has no start cards, shows the four starters, and its rail names *No default model is chosen · Choose a model* and *There is no backup of this workspace yet · Make a backup* | ✅ after a fix found in this round ([FIXED-1074](../plans/FIXED_ITEMS.md#fixed-1074--home-said-no-model-is-set-up-while-a-chat-was-answering)) |
| RT-QUI-02 | Anthropic connects through **Models → Connect** (key and workspace ID), Haiku 4.5 kept; Chat's composer reads *Sent to Anthropic*; an empty conversation shows four starters and **Plan my week** fills the composer without sending | ✅ |
| RT-QUI-03 | A message typed on Home opens Chat and is answered there (*HOME HANDOFF*); **New chat** appears; no setup dialog remains | ✅ after a fix found in this round ([FIXED-1072](../plans/FIXED_ITEMS.md#fixed-1072--a-message-from-home-opened-a-stale-set-up-a-model-dialog-over-its-own-answer)): a stale *Set up a model* dialog stayed over the answer |
| RT-QUI-04 | The sidebar lists the chat under **Chat**; opening it shows its title; **Rename conversation** → *Quiet UI live check* updates the header and the sidebar | ✅ after a fix found in this round ([FIXED-1073](../plans/FIXED_ITEMS.md#fixed-1073--long-chat-titles-ran-past-the-sidebars-edge)): long titles ran past the sidebar |
| RT-QUI-05 | A 120-line answer; scrolling to the top shows **Jump to latest**; pressing it returns to the bottom and the button goes | ✅ |
| RT-QUI-06 | A long answer running: **Stop safely** and **Add instruction** are shown; Stop says the turn stopped at a safe boundary | ✅ |
| RT-QUI-07 | Home after work reads *Good morning, Rahul*, without starters | ✅ |
| RT-QUI-08 | With an older version recorded in this browser, Home shows *Raiker was updated to 0.0.0.* with **What's new** → Settings → About & updates; **Dismiss** removes it and it stays gone after a reload | ✅ |
| RT-QUI-09 | **Settings → General** offers **Home** as a startup page; **Run setup again** opens setup on its model step (*Choose how Raiker should think*, now *Where should I think?*) | ✅ |
| Suites | `quiet-ui-home-chat-live` 9/9 in one run (3.8 min); web unit suite; mocked `composer.spec.ts` 16/16 | ✅ |
| Seen in passing | A model that chose to write a document ended its turn with *Completed · 1 step* (QUI-C03) | ✅ |
| Visual review | `docs/screenshots/2026-10-21-quiet-ui-home-chat/` (01–09), inspected at original resolution; the three defects above were found from the images. Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-20 (Goals and execution profiles, hosted Anthropic Haiku 4.5)

PA-D01, PA-D02 and PA-D06's first slices
([FIXED-1039](../plans/FIXED_ITEMS.md#fixed-1039--an-outcome-could-live-only-in-a-chat-transcript-there-was-no-durable-goal-goal-01-pa-d01)
to [FIXED-1056](../plans/FIXED_ITEMS.md#fixed-1056--goal-and-profile-audit-events-would-have-been-dropped-without-a-word)).
A fresh workspace served by `raiker-web` on `127.0.0.1:8765`. The
identity-linked Anthropic key and workspace ID were typed into the Models dialog
by the spec from the run's environment; neither appears in a spec, command,
document, screenshot or the server log. Spec: `web/e2e/goals-execution-profiles-live.spec.ts`.

| Case | Check | Result |
|---|---|---|
| RT-GOAL-01 | Anthropic connects through **Models → Connect** (key and workspace ID), Haiku 4.5 kept, a Chat turn answers | ✅ |
| RT-GOAL-02 | **Work → Goals** says *No execution profile yet*; a goal drafted with two criteria and one step on Haiku reads *Steps run on claude-haiku-4-5-20251001*, offers no **Start**, and **Accept plan** answers *Choose an execution profile in Settings…* | ✅ after a fix found in this round ([FIXED-1055](../plans/FIXED_ITEMS.md#fixed-1055--a-criterions-text-box-and-a-steps-counts-toward-box-had-the-same-name)): two controls were both named *Criterion 1* |
| RT-GOAL-03 | **Settings → Execution profiles → Create Private local** becomes *Active*; the goal is accepted (*Ready to start*); **Start** is refused naming *anthropic (hosted)*; nothing is filed | ✅ after a fix found in this round ([FIXED-1054](../plans/FIXED_ITEMS.md#fixed-1054--a-goals-steps-ran-on-whatever-an-empty-model-selection-resolved-to)): the step had no model, so Start was judged — and the step run — on the empty selection's local placeholder |
| RT-GOAL-04 | **Create Balanced → Make active**; **Start** adopts Balanced (recorded as `goal_profile_repinned`), the host's tick runs the step on Haiku — a real three-item packing list — and the goal reads **Partly done**: *A packing list exists — Its steps finished*, *I am happy with it* open; *Answered by: anthropic — all within the profile*; the step's start event records `memory_withheld: true` | ✅ |
| RT-GOAL-05 | Home's **Goals** board lists it under **Needs you** with *Partly done*; its link opens the goal; **Confirm met** with a note reads **Completed** and *Confirmed by you: Checked the list* | ✅ |
| RT-GOAL-06 | A second goal started and stopped at once: **Stop goal** asks again (*Stop every step now*), then *Stopped. 0 steps had finished; 1 running task was stopped.*; its task stays `cancelled` although its in-flight model call completed | ✅ |
| RT-GOAL-07 | Editing Balanced's step runs writes *version 2*, shown on the card and in *Saved version 2.* | ✅ |
| Suites | `goals-execution-profiles-live` 7/7 (2.8 min); `tests/test_goals_and_execution_profiles.py`; goal and profile contract cases; `GoalsView.test.ts`, `goalPresentation.test.ts`, `ExecutionProfiles.test.ts`, `WorkbenchView.test.ts` | ✅ |
| Visual review | 01–08 inspected at original resolution. Two defects found and fixed from the images: the list card still read *Working* beside a detail reading *Partly done*, and the budget line read *not priced: claude-haiku-4-5-20251001* because the shipped price block was not consulted (now $0.0103 for the step). Dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-20 (Memory Brief and recall mode, hosted Anthropic Haiku 4.5)

The SQLCipher memory decision's MEM-BRIEF-01 and MEM-MODE-02
([FIXED-1031](../plans/FIXED_ITEMS.md#fixed-1031--a-durable-preference-reached-a-turn-only-when-the-prompt-shared-its-words-mem-brief-01),
[FIXED-1032](../plans/FIXED_ITEMS.md#fixed-1032--ambient-recall-could-not-be-turned-down-and-no-answer-said-which-recall-it-ran-under-mem-mode-02)).
A fresh workspace served by `raiker-web` on `127.0.0.1:8765`. The
identity-linked Anthropic key and workspace ID were typed into the Models dialog
by the spec from the run's environment; neither appears in a spec, command,
document, screenshot or the server log. Spec: `web/e2e/mem-brief-recall-mode-live.spec.ts`.

| Case | Check | Result |
|---|---|---|
| RT-MEM-01 | Anthropic connects through **Models → Connect** (key and workspace ID), Haiku 4.5 kept, **Test** reads *can reach* | ✅ |
| RT-MEM-02 | A memory imported through **Recall & indexing → Review import**; the **Recall mode** card opens on *Search when relevant* | ✅ |
| RT-MEM-03 | *Search when relevant*: *What is my favourite tea?* → `Oolong.`; the strip reads **Remembered 1 · Brief + search** and, opened, *Recall mode: Search when relevant · searched sqlite-fts5 + raiker-local-hash-v1* | ✅ after a fix found in this round ([FIXED-1038](../plans/FIXED_ITEMS.md#fixed-1038--the-answers-recall-backend-read-redacted_secret)): the backend first read *searched [REDACTED_SECRET]* |
| RT-MEM-04 | *Brief only*: *Which drink do I like best?* — no word shared with the memory — still answers *oolong* from the brief; the strip reads **Remembered 1 · Brief only** and *no search* | ✅ |
| RT-MEM-05 | *Off*: the same question gets no memory; the answer carries the quiet line *Memory off for this answer* and no **Remembered** strip | ✅ |
| RT-MEM-06 | Incognito on over *Search when relevant*: the card says no mode recalls anything; the answer reads *Memory not used: Incognito is on*; the card at 390 px in dark has no horizontal overflow; Incognito turned off afterwards | ✅ |
| Suites | `mem-brief-recall-mode-live` 6/6 (3.2 min); `tests/test_memory_brief_and_recall_mode.py`, `test_memory_history_boundary.py`, `test_memory_adapter_contract.py`, `test_memory_key_never_leaves.py`, `test_memory_recall_evaluation_v2.py` | ✅ |
| Visual review | `docs/screenshots/2026-10-20-memory-brief-recall-mode/` (01–06), inspected at original resolution; dated folders are local evidence and not committed | ✅ |

## Result — 2026-10-20 (model transport guard, hosted Anthropic Haiku 4.5)

BUG-349 ([FIXED-1021](../plans/FIXED_ITEMS.md#fixed-1021--a-hosted-model-name-was-dialled-wherever-its-dns-answer-pointed-was-bug-349)
to [FIXED-1030](../plans/FIXED_ITEMS.md#fixed-1030--a-refused-dial-and-other-classified-denials-read-as-enable-its-gate)):
model requests are now checked at dial time. A fresh workspace served by
`raiker-web` on `127.0.0.1:8765`, on a host whose outbound HTTPS goes through
a proxy at `127.0.0.1:33773` with `api.anthropic.com` in `NO_PROXY`. The test
name `models.raiker-live.example` was given the answer `10.0.0.5` in
`/etc/hosts` for the round (removed afterwards) and added to the server's
`NO_PROXY`, because a proxied name is resolved by the proxy and the guard
would not see it. The identity-linked Anthropic key and workspace ID were typed
into the Models dialog by the spec from the run's environment; neither appears
in a spec, command, document, screenshot or the server log.

| Case | Check | Result |
|---|---|---|
| MT-01 | A hosted provider is dialled directly, pinned, and says so | ✅ real catalogue and one-token preflight; Anthropic's card reads *Direct connection*, the fourteen proxied hosted cards *Through your proxy (127.0.0.1:33773)*, the posture *Yes — 14 hosted profiles via 127.0.0.1:33773* |
| MT-02 | A real turn answers through the pinned connection | ✅ *Reply with exactly the word: pinned* → `pinned`, Haiku 4.5 |
| MT-03 | A hosted name that resolves to a private address is refused by name | ✅ the OpenAI-compatible card, saved for `https://models.raiker-live.example/v1` with a sentinel key, reads *Raiker refused to connect: this hosted provider's name resolved to a private, loopback or link-local address … a policy refusal, not a network fault*; neither *enable its gate* nor *could not be reached* appears |
| MT-04 | A link-local endpoint needs the owner's tick | ✅ `http://169.254.10.10:8000/v1` is refused as link-local; ticked, the same address is dialled and the card reports the server (nothing listens there), not a policy refusal |
| MT-05 | A cloud metadata address is never a destination | ✅ saving `http://169.254.169.254/v1`, even ticked, is refused in the Connect dialog with `model_dial_refused:metadata_address` |
| MT-06 | The opt-in in the dialog, dark theme at 390 px | ✅ prefilled from the saved connection, no horizontal overflow; the endpoint was disconnected afterwards |
| Suites | `model-transport-guard-live` 6/6 on a fresh workspace (7.8 min); `tests/test_model_transport_guard.py` 34/34 (NET-01 … NET-12) | ✅ |
| Visual review | `docs/screenshots/2026-10-20-model-transport-guard/` (01–08), inspected at original resolution; dated folders are local evidence and not committed | ✅ — found [BUG-352](../plans/TO_BE_FIXED.md#bug-352--a-custom-endpoint-saved-off-the-machine-shows-no-route-on-its-card): the custom endpoint saved off the machine shows no route line |

## Result — 2026-10-20 (model connection authorization, hosted Anthropic Haiku 4.5)

[ADR-0004](../adr/ADR-0004-connection-bound-model-authorization.md) retired
`RAIKER_MODEL_EGRESS_ALLOWLIST`: a saved connection authorizes its own origin,
and nothing else is set up. A fresh workspace served by `raiker-web` on
`127.0.0.1:8765`, started with `RAIKER_MODEL_EGRESS_ALLOWLIST` set to an
unrelated host (to prove it is ignored), `OPENAI_API_KEY` set to a sentinel
value, and no Anthropic variable. The identity-linked Anthropic key and its
workspace ID were typed into the Models dialog by the spec from the run's own
environment; neither appears in a spec, command, document or screenshot.

| Case | Check | Result |
|---|---|---|
| LC-01 | Connecting Anthropic in the UI is the whole setup — key and workspace ID in **Connect**, no allowlist, Haiku 4.5 pinned, **Test** reads *can reach* | ✅ real catalogue and one-token preflight through the saved connection |
| LC-02 | A real turn answers through the saved connection | ✅ *Reply with exactly the word: connected* → `connected`, Haiku 4.5 |
| LC-03 | **Permissions → Hosted models** says why it is on, and turning it off refuses the connected provider | ✅ found and fixed in this round ([FIXED-1020](../plans/FIXED_ITEMS.md#fixed-1020--permissions-said-hosted-models-was-off-above-a-provider-that-had-just-answered)): the row read *Off* and offered only **Turn on**; it now reads *On by connection*, *Yes — on because you connected a provider in Models* and offers **Turn off**. After it, the Models posture reads *Off* and the card reads **Policy blocked** — a policy refusal, not a connection failure |
| LC-04 | Disconnecting takes the provider away | ✅ the card returns to *Not connected* and the posture's connected count drops |
| LC-05 | An environment key becomes a connection with one owner decision | ✅ the dialog offers **Use the key from `OPENAI_API_KEY`**, the key field disappears, *Connection saved*; `/api/models` reports the connection, no allowlist field, and never the key |
| LC-06 | The dialog in the dark theme and at 390 px | ✅ no horizontal overflow |
| LC-07 | The retired variable is ignored and never echoed | ✅ one log line names it; neither its value, the sentinel key nor the Anthropic key appears in the server log |
| Suites | `model-connection-anthropic-live` 4/4 and `model-connection-authorization-live` 2/2 in one run on a fresh workspace (7.8 min); `composer.spec.ts` (mocked) 16/16 | ✅ |
| Visual review | `docs/screenshots/2026-10-20-model-connection-anthropic/` (01–06, 04a) and `docs/screenshots/2026-10-20-model-connection-authorization/` (01–04, 06, 07), inspected at original resolution; dated folders are local evidence and not committed | ✅ |

## Result — 2026-09-03 (on-device dictation, the boot session probe, a three-width sweep)

A workspace reset with `scripts/reset_live_workspace.py` — the checked reset
BUG-266 asked for, not `rm -rf` — and a built SPA served by `raiker-web` on
`127.0.0.1:8765`. The Anthropic key was entered through the Models reconnect
dialog by the spec and appears in no command, document or screenshot. The
transcription runtime was a stand-in HTTP server the spec starts on loopback:
what is being proved is the path, and the words come from a service Raiker
reaches only because the owner pointed it there.

| Check | Result |
|---|---|
| A locked load makes no refused request | ✅ `ui-sweep-live.spec.ts` watched every response and asserted **no 401** and no console error before sign-in — the outcome BUG-267 asked for, and one the browser's own log could not be told to ignore |
| The microphone is allowed to Raiker's own page | ✅ `Permissions-Policy: microphone=(self)`; it was `microphone=()`, which denied the feature to this origin too and made dictation inert in **any** served build |
| A speech runtime is configured beside the other local ones | ✅ **Models → Local** shows *Not set up*, accepts a loopback address, and reports *Answered. Dictation can run on this device.* after transcribing generated silence |
| An address off this machine is refused where it is typed | ✅ `speech_endpoint_not_local` for both a hosted host and a private-network one, before anything is contacted |
| The runtime in use is stated, and nothing is asked | ✅ no mode selector: adding a runtime is the whole decision, and the note under the microphone says which one dictation will use |
| The disclosure matches the runtime in use | ✅ the note under the microphone reads "transcribed by the speech runtime on this machine" once the owner chooses on-device, in place of the browser sentence |
| Words dictated on this machine reach the composer | ✅ with a fake capture device, `speech-runtime-live.spec.ts` recorded, converted to 16 kHz mono WAV in the page, posted to `/api/speech/transcribe`, and asserted the transcript in the Chat draft — the runtime confirmed it received the clip |
| Every page at four widths, both themes | ✅ `ui-sweep-responsive-live.spec.ts` over 27 route/tab states at 390, 1920, 3840 and 7680 in light and dark: no overflow, no glyphless icon, no selected tab off its strip, no control under 24px, no console error |
| An address typed before the read resolved survives it | ✅ found in this round — the Models speech row adopted the stored value unconditionally, FIXED-85's defect in a new place; fixed and guarded |
| Every control meets the minimum touch target | ✅ found in this round — the new Voice radios measured 13x24 on a phone, under WCAG 2.2's 24px; the sweep measured it rather than photographing it |
| A settings deep link opens the section it names | ✅ found in this round — `#/settings?tab=updates` had always opened General, because the guard for exactly that compared the rail against a hand-copied list with the same omission |
| Suites | ✅ `speech-runtime-live` 1/1, `ui-sweep-responsive-live` 9/9, `composer.spec.ts` (mocked) 9/9 |
| Visual review | ✅ `docs/plans/screenshots/working/bug-256-voice-settings.png`, `bug-256-speech-runtime-models.png`, `bug-256-dictated-on-device.png`, and the re-captured `docs/plans/screenshots/pages/` catalogue inspected at original resolution |

This round proves dictation can run with nothing leaving the machine, and that
the control which claims so is reachable at all — the second half was not true
before it, in any released build.

## Result — 2026-08-22 (plugin contributions, MCP offers, the channel surface, the unattended posture, responsive sweep)

The running built SPA was unlocked with Rahul's existing account. The Anthropic
credential was entered through the Models reconnect dialog — never a source file,
a command line, or the server's environment — and `claude-haiku-4-5-20251001` was
pinned and readiness-checked through the product's own **Test** control before
any turn was sent. No credential appears in these results, the specs, or the
screenshots.

Specs:
[`bug-221-225-plugin-skills-mcp-channels-live.spec.ts`](../../web/e2e/bug-221-225-plugin-skills-mcp-channels-live.spec.ts)
(9 tests),
[`plugin-contributions-provider-live.spec.ts`](../../web/e2e/plugin-contributions-provider-live.spec.ts)
(3 tests),
[`ui-sweep-responsive-live.spec.ts`](../../web/e2e/ui-sweep-responsive-live.spec.ts)
(3 tests),
[`bug-219-decline-mode-live.spec.ts`](../../web/e2e/bug-219-decline-mode-live.spec.ts)
(3 tests),
[`bug-225-channels-live.spec.ts`](../../web/e2e/bug-225-channels-live.spec.ts)
(6 tests). 24 tests, 24 passed.

| Check | Result |
|---|---|
| A plugin's skill is credited to it on the row | ✅ *from plugin* chip and *"Provided by plugin acme-toolkit"* |
| It arrives switched off | ✅ **inactive**, with **Activate** offered — proved against an *absent* starting state, not assumed |
| Rename and Delete are not offered on it | ✅ neither rendered; **Download** and **Manage plugin** are |
| The owner's on/off choice survives a reconcile | ✅ switched on, navigated away and back, still on |
| Revoking withdraws the skill **and** the offer | ✅ both surfaces empty after the directory was deleted |
| An offered MCP server is offered, not connected | ✅ listed under *Offered by your plugins*, credited, **Add server** offered, no server profile created |
| An offer names a variable, never a token | ✅ *"Reads its token from `ACME_MCP_TOKEN`. The token is never stored here."* |
| The Plugins tab states three kinds available, one not | ✅ Hooks / Skills / MCP servers **Available**; Panels **Not yet** |
| Channels states the contract and the four steps | ✅ *"untrusted content with a named sender who is not you"*, step 1 **Done**, step 2 **Next** |
| Anthropic credential entered through the UI | ✅ connection saved into the encrypted instance vault |
| Anthropic readiness | ✅ `claude-haiku-4-5-20251001` — *can reach* |
| **An active contributed skill reaches a real turn** | ✅ the live Haiku 4.5 turn listed `acme-live-on` among its skills |
| **An inactive one does not** | ✅ `acme-live-off` absent from the same answer — the second consent holding across a real provider turn |
| Every page fits at 390 / 834 / 1440 px | ✅ 26 pages × 3 widths: zero horizontal overflow |
| Every icon renders a glyph | ✅ zero empty `<svg>` across the same 78 captures |
| The selected hub tab is on screen | ✅ at every width (FIXED-257 holding) |
| The posture menu tells Skip and Decline apart in words | ✅ *"No approval is raised at all"* vs *"anything needing approval is refused, not queued"* |
| Every posture is reachable, at 1440 px and at 390 px | ✅ all four `toBeInViewport()`; no horizontal overflow at either width |
| **Decline, don't ask** persists across a visit | ✅ chosen, navigated away and back, still selected |
| The Channels tab states the contract | ✅ *"untrusted content with a named sender who is not you"* |
| Three fail-closed gates reported separately | ✅ **Capability off**, **None allowlisted**, **Refusing everything** — each with its own remedy named |
| The inbound budget is stated | ✅ **60/min** per sender; allowlisting says who, the budget says how often |
| Pairing links without switching on | ✅ *"It is switched off until you turn it on"*; row reads **Linked, off · 2 senders** |
| A profile that needs senders cannot be paired without them | ✅ the pairing form asks, and the control service refuses `sender_allowlist_required` |
| A test delivery runs the governed path | ✅ refused with a readable reason — the owner's own capability gate, not a shortcut that would have "worked" |
| Unpairing is what stops it | ✅ row returns to **Not linked**; Turn on is gone |
| Channels tab at 390 / 834 / 1440 px | ✅ no horizontal overflow at any width |
| Visual review | ✅ `docs/plans/screenshots/working/bug-221-*`, `bug-225-*`, `bug-219-approval-modes*.png`, and `docs/plans/screenshots/pages/` |

Five defects were found by this round's live work rather than by a feature test,
and all five are fixed here:

* On a touch device the phone navigation's `:hover` background stuck after a tap,
  so the last item touched kept a highlight that read as *"you are here"* and
  contradicted the accent colour on the item that actually was. Now behind
  `@media (hover: hover)`.
* The approval-posture menu opened **downwards** from a trigger pinned to the
  bottom of the viewport, so its last option was in the fold on a page that does
  not scroll. It opens upward now (FIXED-263).
* Every live spec's sign-in waited for the *fresh-instance* Workbench greeting,
  so a suite passed on an empty workspace and failed on a used one — at sign-in,
  before reaching what it was written to test (FIXED-264).
* The API's key-based redaction filter replaced the **boolean**
  `inbound.secret_configured` with `"***REDACTED***"` — truthy — so the Channels
  tab read **"Secret set"** while the receiver was refusing every message. Caught
  by comparing the rendered chip against the served payload, which the live spec
  now does on every run (FIXED-266).
* And the round's premise itself: channel delivery was recorded as unbuilt, and
  reading `raiker/channels/` found the transport, the gate, the egress boundary
  and the inbound receiver all present and **unreachable** — nothing let the owner
  pair a connector. The fix was a surface, not a transport (FIXED-265).

## Result — 2026-08-21 (governed turn-based voice, preserved owner workspace)

The running built SPA was unlocked with Rahul's existing account and every
supplied hosted credential was entered through the Models reconnect dialog —
never a source file, process command or server environment. Browser speech was
driven through a deterministic Playwright recognition adapter because a
headless browser has no trustworthy physical-microphone path; the prompt itself
and the provider turn used the live FastAPI service, owner store, gateway and
configured Ollama model.

| Check | Result |
|---|---|
| Chat dictation is an editable draft | ✅ recognition produced `Reply with only: voice verified`; zero prompt requests before **Done** and zero before explicit **Send** |
| Prompt provenance crosses the real HTTP boundary | ✅ the sole prompt request carried `input_mode: dictated`; the live Ollama `gemma4:31b-cloud` turn returned exactly `voice verified` |
| Manual response playback | ✅ only the completed answer exposed **Read aloud**; activation exposed **Stop speaking**, and stopping restored the idle control |
| Build rollback | ✅ the draft changed from `keep this exact draft` while listening and **Cancel** restored that exact original text |
| Provider credentials entered through UI | ✅ Anthropic, OpenAI and OpenRouter reconnect dialogs accepted the supplied credentials into the encrypted instance vault |
| Anthropic readiness | ✅ `claude-sonnet-5` ready |
| OpenRouter readiness | ✅ `nvidia/nemotron-3.5-lightning:free` ready |
| OpenAI readiness | ⚠️ the supplied account could not execute pinned `gpt-5.4`; Raiker reported credential/access/billing guidance and did not claim readiness |
| Ollama readiness and execution | ✅ model row was ready and the real governed turn completed; a repeated readiness click exceeded the 30-second browser-control bound, while execution itself completed normally |
| Mocked browser regression | ✅ 5/5 Playwright tests, including desktop, 390×844 mobile, Settings persistence and zero Axe violations |
| Visual review | ✅ `output/playwright/voice-live-chat.png`, `voice-live-complete.png`, `voice-live-build.png`, plus the mocked desktop/mobile/Settings captures inspected at original resolution |

The OpenAI result is an external account/model-access limitation, not a Raiker
defect: the control failed closed and gave the owner an actionable reason. No
credential appears in these results or screenshots.

## Result — 2026-08-16 (first-run provider matrix, the Workbench board, both composers)

Fresh workspace, owner registered through the browser, **every credential typed
into the wizard's own field** — never given to the server as environment — so what
this round proves is the product's store-key → catalogue → pin → readiness → turn
chain from the very first screen. Spec:
[`web/e2e/wizard-workbench-composer-live.spec.ts`](../../web/e2e/wizard-workbench-composer-live.spec.ts)
(3 tests, 3 passed). Ollama was running locally; LM Studio was not installed, which
is a *result* the rows are required to state.

| Check | Result |
|---|---|
| One row per provider on the first-run model stage | ✅ Local GGUF, Ollama, LM Studio, OpenAI-compatible, Ollama Cloud, OpenRouter, Hugging Face, Anthropic, OpenAI, Gemini |
| Local runtimes are asked without being clicked | ✅ **9 models from Ollama**, `gemma4:31b-cloud` pre-selected |
| A runtime that is not running says so | ✅ *"LM Studio is not running on this device"*, and the same for OpenAI-compatible — no empty dropdown, no invented name |
| No GGUF in an approved root is its own state | ✅ *"No complete GGUF found"* with **Scan**; no false `Selected:` line for the slot alias (FIXED-223) |
| A key stored in the wizard produces that provider's own catalogue | ✅ Anthropic **10**, OpenRouter **413–414** (the catalogue moves), OpenAI **124** models, each read from the provider |
| A catalogue too long to scroll carries a filter | ✅ `Filter 414 models` / `Filter 124 models`; absent on Anthropic's 10 |
| No credential is rendered back into the page | ✅ asserted absent from `page.content()` after every save |
| A model pinned from a real catalogue | ✅ `Haiku 4.5` → *"Selected: Haiku 4.5"*, and `PUT /api/model-selection` recorded |
| Workbench has no composer | ✅ the prompt box, its mode tabs and its Start control are absent (FIXED-225) |
| The board's three groups | ✅ **Running now** / **Standing agents** / **Scheduled runs**, each stating its own emptiness |
| A real standing agent lands in the right group | ✅ a live daily routine reads `Runs daily · next cycle …` under **Standing agents**, and is **absent** from **Running now** — an armed cadence is not a running one |
| Safe-boundary stop from the board | ✅ **Stop** on every row, on the same governed `POST /api/interrupts` |
| Chat composer control set | ✅ `+`, `Chat \| Build`, approval mode, execution environment, context capacity, model chip, context ring, Send — one bar under a full-width prompt |
| Build composer control set | ✅ the same, with the posture as one chip and a **Mode** menu offering Plan / Edit / Auto |
| The thinking budget lives in the model menu | ✅ **Effort** section with a **Thinking** switch; absent for a model that publishes no levels |
| The restructured composer still sends | ✅ a real governed turn on `claude-haiku-4-5-20251001` returned the exact marker |
| A completed turn offers **Branch** | ✅ FIXED-227, the last open row of GAP-CHAT C14 |
| Both themes | ✅ light and dark captured; dark is `#000` ground, `#ffffff` ink, `#ecd06f` accent |
| Console | ✅ 0 errors across all three tests |
| Visual review | ✅ `docs/plans/screenshots/working/r0816b-01-first-run-provider-matrix.png`, `r0816b-02-first-run-catalogues-listed.png`, `r0816b-03-first-run-model-pinned.png`, `r0816b-04-workbench-board.png`, `r0816b-05-workbench-standing-agent.png`, `r0816b-06-chat-composer.png`, `r0816b-07-chat-live-turn.png`, `r0816b-08-build-composer-mode.png`, `r0816b-09-chat-dark.png` inspected at original resolution |

**Two defects this round found and fixed, both of which a fixture could not have
found.** OpenRouter's catalogue read returned 200 OK and the row still said
"Asking OpenRouter…" forever, because the redaction layer had flattened three
41-character model ids into one identical `[REDACTED_SECRET]` and the duplicate
crashed a keyed render ([FIXED-224](../plans/FIXED_ITEMS.md)). And the readiness
dialog's **Check again** reported "Check complete" having checked nothing
([FIXED-226](../plans/FIXED_ITEMS.md)).

**One defect found and left open.** On Windows, a workspace nested deeper than
~170 characters cannot open its checkpoint locks, so pre-image capture fails and
the only trace is an event nothing displays —
[BUG-216, closed as FIXED-240](../plans/FIXED_ITEMS.md#fixed-240--deep-windows-paths-silently-made-approved-writes-irreversible). Confirmed pre-existing against a pristine
worktree.

---

## Result — 2026-08-15 (cross-provider review round, hosted Anthropic Haiku 4.5)

Fresh workspace, owner registered through the browser, every credential typed
into the Models connect dialog — never given to the server as environment — so
what this round proves is the product's connect → catalogue → readiness → turn
chain rather than a fixture. Spec:
[`web/e2e/review-provider-matrix-live.spec.ts`](../../web/e2e/review-provider-matrix-live.spec.ts).

| Check | Result |
|---|---|
| Owner registers and reaches the workbench | ✅ five-stage first-run wizard completed |
| Anthropic key stored through the connect dialog | ✅ card shows `Connected`; the key is asserted absent from the DOM |
| Live catalogue from the real provider | ✅ 11 models listed |
| **Test** resolves the pinned model | ✅ `Anthropic can reach claude-haiku-4-5-20251001`; chip `Ready · confirmed just now`; `POST /api/model-readiness/check` → 200 |
| Real governed turn in Chat | ✅ Raiker's own bubble returned `REVIEW CHAT OK` from Haiku 4.5 |
| Browser console errors | ✅ 0 across both scenarios |
| First-run wizard names unreachable local backends `Connected` | ❌ as found → ✅ fixed in this round as [FIXED-204](../plans/FIXED_ITEMS.md#fixed-204--the-first-screen-an-owner-sees-called-five-unreachable-backends-connected); stage 02 now reads `Not checked yet` / `Choose a model first`, and the spec asserts `Connected` appears nowhere |

**Not exercisable in this environment, and not a Raiker result.** The sandbox
this round ran in answers `403` to `CONNECT` for every host except
`anthropic.com`, verified against the proxy directly
(`curl -v https://openrouter.ai/…` → `CONNECT tunnel failed, response 403`). So:

| Backend | Outcome |
|---|---|
| OpenRouter | Credential stored and accepted; catalogue unreachable. The card degraded honestly — *"Provider unreachable — type a model id if you know it"* — but simultaneously read `Connected`, the second half of BUG-198. After FIXED-204 the same state reads `Connection saved · Not checked · Provider unreachable` |
| OpenAI | Same egress denial; not reached |
| Ollama `gemma4:31b-cloud` | No Ollama binary and nothing on `11434` on this host; `ollama.com` also denied. This is what surfaced BUG-198: the wizard offered it as `Connected` |

Re-run on a host with open egress to complete the OpenRouter, OpenAI and Ollama
rows. Nothing in this round distinguishes those three backends' code paths — only
that the network they need was refused before Raiker was involved.

Evidence: `docs/plans/screenshots/working/review-01-signed-in.png`,
`review-02-anthropic-readiness.png`, `review-03-chat.png`,
`review-04-chat-answer.png`.

## Result — 2026-08-09 (BUG-69 reference-platform parity review, hosted Anthropic Haiku 4.5)

Fresh temporary workspace, owner registered through the browser, one Anthropic
key entered **only** through the Models connect dialog. The key holds no credit,
which makes it an exact fixture for the billing state added in this round: the
catalogue call succeeds and every inference call returns HTTP 400
`credit_balance_too_low`. Token generation was therefore **not** exercised; every
other link in the readiness chain was.

| Check | Result |
|---|---|
| First run routes a new owner to `#/model-setup` | ✅ `Choose how to run models`, resumable, Skip explains the consequence |
| Chat / Build / Tasks refuse to submit with no ready model | ✅ primary action disabled, draft preserved (the Workbench has no composer to gate — it is the board over work already running) |
| Connect dialog stores the key; value never rendered back | ✅ card shows `Connected`, no credential in the DOM |
| Live catalogue from the real provider | ✅ 10 Anthropic models listed, `claude-haiku-4-5-20251001` pinned |
| **Test** on the provider card runs the exact-model readiness check | ✅ FIXED-140 — was a catalogue listing that proved nothing |
| An empty account balance is its own state, not "unreachable" | ✅ FIXED-138 — card chip **No credit**, remediation names credit and quota |
| Models headline counts proven readiness | ✅ FIXED-140 — **0 models ready · 1 of 10 connected**, was "1 of 10 providers set up" |
| Chat repeats the same verdict and keeps the draft | ✅ Send stays disabled, sentence identical to the card |
| Browser console errors | ✅ 0 |

Evidence: `bug69-models-quota-readiness-live.png` and
`bug69-chat-quota-readiness-live.png` — **not retained in the repository**;
the round's committed evidence is under
`plans/screenshots/working/`.

## Result — 2026-07-11 (Task 4: Gmail read-only connector, hosted Anthropic Haiku 4.5)

Second read connector, replicating the GitHub reference slice. Verified against
the **real** `gmail.googleapis.com` egress boundary. We hold no real Gmail OAuth
token in this environment, so the fully-governed path fails closed at the auth
boundary (`http_error:401`) — which still proves the whole gate → mode →
credential → egress chain, that the request reaches the fixed host with the
token in the header (never the URL/output), and that the tool is wired into the
real hosted-model turn. A real `RAIKER_GMAIL_TOKEN` would return the message
snippet + headers as untrusted data.

| Check | Result |
|---|---|
| Gate disabled (fresh workspace) fails closed | ✅ `connector_gate_disabled` |
| Default `ask` withholds the read (no network contact) | ✅ `connector_withheld_ask` |
| Decision mode `deny` blocks | ✅ `connector_denied_by_decision_mode` |
| Fail-closed without a credential | ✅ `connector_not_configured` (`RAIKER_GMAIL_TOKEN` unset) |
| Fail-closed without egress | ✅ `connector_egress_denied` (`gmail.googleapis.com` not allowlisted) |
| Argument validation, URL built server-side (`format=metadata`) | ✅ `unsupported_resource` / `invalid_message_id` |
| Fully governed (gate on + `allow` + token + egress): **real** GET to `gmail.googleapis.com` | ✅ reached Gmail → `connector_fetch_failed:http_error:401` (fake token); token **not** in output (`token in output: False`) |
| **End-to-end model turn**: hosted Haiku 4.5 given the `gmail_read` tool | ✅ `model_request_started → provider: anthropic, model: claude-haiku-4-5-20251001`; model called `gmail_read(message, msg_abc123)` (`tool_started`/`tool_failed gmail_read`); model reported the exact governed error type back to the user |
| Durable event log is metadata-only | ✅ owner token absent (0 hits) and fetched content absent; the non-secret `message_id` identifier retained (1 hit) |
| Browser: **Connections** view renders Gmail **Ready** | ✅ dark-theme card — capability gate / decision mode / owner credential (`***REDACTED***`) / egress (`gmail.googleapis.com`) all ✓; actions `read_message, read_thread`; shown next to a GitHub "Fail-closed" card |
| Browser: Gmail honest **Fail-closed** with remediation | ✅ light-theme card — credential + egress ✗ with per-check guidance; egress-allowlist warning banner; credential value never shown |
| Browser console errors | ✅ 0 (both states) |

The read-only Connections surface never reaches the network and never shows a
credential value (at the time of this run the response redaction layer scrubbed
even the env-var *name* to `***REDACTED***`; since `TO_BE_FIXED.md` FIXED-07 the
name is returned as-is — it is remediation guidance, not a credential — and the
value is still never read into a response). Enabling a connector stays on the
capability-gate + decision-mode control plane, gate-manager only.

## Result — 2026-07-11 (uploaded-document attachments: PDF + docx + image, hosted Anthropic Haiku 4.5)

Run with a 1-hour operator key held in the server process env only, against
three **real** user-supplied files. This round live-verifies Task 3's document
attachments (PDF + Word .docx text extraction) and re-confirms image vision,
end to end through the served stack, bound to `anthropic-hosted` /
`claude-haiku-4-5-20251001`.

| Check | Result |
|---|---|
| `POST /api/attachments` stores a real 2-page PDF (156 KB) | ✅ `att_…`, `kind: document` |
| `POST /api/attachments` stores a real .docx (202 KB) | ✅ `att_…`, `kind: document` |
| `POST /api/attachments` stores a real 1.76 MB JPEG | ✅ `att_…`, `kind: image`, metadata-only |
| Governed turn, PDF document → extracted text in context → real Haiku answer | ✅ document facts were extracted from the uploaded sample; the content remains only inside that document |
| Governed turn, .docx document → extracted text → real Haiku answer | ✅ document facts were extracted from the uploaded sample; the content remains only inside that document |
| Governed turn, JPG image (vision) → image block → real Haiku answer | ✅ correctly identified an **HAL Tejas** aircraft cutaway diagram (illustrator, publisher, maiden-flight date — all read from the image) |
| `model_request_started` bound model | ✅ `provider: anthropic, model: claude-haiku-4-5-20251001` |
| `model_request_completed` normalised usage | ✅ `{input_tokens: 2694, output_tokens: 37, cache_*: 0}` |
| `attachment_image_included` event | ✅ id + `image/jpeg` + `1761205` bytes + sha256; **no image base64 anywhere in the event log** (checked) |
| Browser (Chromium): composer "Document…" upload + image chip render; turn completes on Hosted · Anthropic | ✅ top bar "Hosted · Anthropic · egress open"; turn `completed`; **0 console errors** |

**Honest note:** in the browser round the model, given both a PDF and an image
and asked to read the CV, opened with "I'll read the CV document…" and finished
`completed` (the document text was already in context; the model's agentic
phrasing is model behaviour, not an attachment-path defect). The per-attachment
API turns above are the definitive content proof — each answer states facts that
exist only inside the uploaded file.

## Result — 2026-07-11 (uploaded-image vision turn + agentic tool loop, hosted Anthropic Haiku 4.5)

Run with a 1-hour operator key held in the server process env only. This round
verified the two changes on PR #108 live: **uploaded image attachments (vision)**
and the **effectively-unbounded tool loop**, and caught + fixed a real bug the
unit suite could not see (below).

| Check | Result |
|---|---|
| `POST /api/attachments` stores a real 2.2 MB JPEG (owner auth; metadata-only response) | ✅ `att_…`, `image/jpeg`, `2217857` bytes, sha256 returned |
| Vision turn: prompt + `{type:"image", attachment_id}` on the selected `anthropic-hosted` profile | ✅ real Haiku answer correctly describing the photographed dessert; `RAIKER_VISION_OK` |
| `attachment_image_included` event (id, media type, size, sha256) | ✅ present; **no image bytes/base64 anywhere in the event log** (checked) |
| Withheld path: same image bound to non-vision `raiker-local-llama-cpp` | ✅ `attachment_image_withheld` (`model_profile_lacks_vision_support`) before any provider contact; turn then failed honestly (`provider_connection_failed`, no local server running) |
| Agentic tool loop ("list files, read mission-brief.txt, tell me the codeword") | ✅ 3 model calls + 2 governed tool executions (`list_directory`, `read_file`); correct codeword extracted; `RAIKER_AGENT_OK`; the turn ended because the **model finished**, not a budget |
| Browser (Chromium): upload the image through the composer "+" → Image…, chip renders, streamed vision turn through the UI | ✅ `RAIKER_UI_VISION_OK`; **0 console errors** |

**Bug found live and fixed (tool round-trip):** the first agentic run failed on
the second model call with HTTP 400 → `provider_connection_failed`. Cause: the
orchestrator appended only the `role="tool"` result message — never the
assistant message carrying the model's `tool_use` — and the Anthropic Messages
API rejects a `tool_result` with no matching `tool_use` in a prior assistant
turn (strict OpenAI endpoints do the same for `tool_calls`). Earlier live
rounds were single-shot Q&A, so this had never been exercised against a hosted
provider. Fix: `ModelMessage.tool_calls` + the orchestrator now appends the
assistant tool-call message before each tool result; the Anthropic adapter
serializes `tool_use` blocks and `to_dict()` emits the OpenAI `tool_calls`
field (`test_tool_round_trip_carries_assistant_tool_call_message`,
`test_assistant_tool_calls_serialize_for_both_protocols`). Re-run: the loop
completed end-to-end (table above).

## Result — 2026-07-11 (Task 4: GitHub read-only connector, hosted Anthropic Haiku 4.5)

Reference slice for governed service connectors. Real owner GitHub token
(`RAIKER_GITHUB_TOKEN`, server env), `api.github.com` on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, `connector_github_runtime` enabled via the
control plane (threat ack + confirm), decision mode raised to `allow`.

| Check | Result |
|---|---|
| Default `ask` withholds the read (no network contact) | ✅ `connector_withheld_ask` |
| With mode `allow`: `GithubConnectorService.read` fetches a **real** PR | ✅ a configured test repository pull request was retrieved with its title, state, body, and untrusted-data framing |
| Owner token never appears in the tool output | ✅ verified (`token in output: False`) |
| **End-to-end model turn**: hosted Haiku 4.5 given the `github_read` tool | ✅ model called `github_read` for the pull request; tool action recorded `success` |
| Model answered from the fetched untrusted content | ✅ replied with the exact PR title + an accurate one-sentence summary |
| Fail-closed without a credential | ✅ `connector_not_configured` (token env unset) |
| Fail-closed without egress | ✅ `connector_egress_denied` (`api.github.com` not allowlisted) |
| Argument validation (bad repo/resource/number) fails closed, URL built server-side | ✅ `invalid_repo` / `unsupported_resource` / `invalid_number` |
| Browser: **Connections** view renders connector status | ✅ "Ready" card — capability gate / decision mode / owner credential (`***REDACTED***`) / egress allowlist all ✓; actions `read_issue, read_pull_request` |
| Browser: fresh workspace shows honest **fail-closed** with remediation | ✅ "Fail-closed" card — decision mode / credential / egress ✗ with per-check guidance; egress-allowlist warning banner |
| Browser console errors | ✅ 0 (both states) |

The read-only Connections surface never reaches the network and never shows a
credential value (at the time of this run the response redaction layer scrubbed
even the env-var *name* to `***REDACTED***`; since `TO_BE_FIXED.md` FIXED-07 the
name is returned as-is — it is remediation guidance, not a credential — and the
value is still never read into a response). Enabling a connector stays on the
capability-gate + decision-mode control plane, gate-manager only.

## Result — 2026-07-10 (hosted Anthropic, Haiku 4.5)

| Check | Result |
|---|---|
| `raiker-web` boots; `/api/health` 200 with `store: ok` | ✅ |
| Owner session mint (`POST /api/auth/session`) | ✅ |
| `GET /api/models` — `anthropic-hosted` selected, hosted gate `enabled_runtime`, fallback shows `raiker-local-llama-cpp`, cache `5m` | ✅ |
| Streamed turn (`POST /api/prompts/stream`) returns a real answer | ✅ `"The capital of Japan is Tokyo. RAIKER_WEB_OK"` |
| Turn bound to the requested model | ✅ `model_request_started → provider: anthropic, model: claude-haiku-4-5-20251001` |
| Normalised cache metrics on `model_request_completed` (streamed path) | ✅ `{input_tokens: 2013, output_tokens: 19, cache_read_tokens: 0, cache_write_tokens: 0, cache_hit: 0}` |
| Browser (Chromium): Models page renders selected card + "Cache 5m" chips + fallback editor | ✅ |
| Browser: live chat turn through the UI | ✅ `"6 times 7 is 42. RAIKER_UI_OK"` |
| Top-bar model chip | ✅ `Hosted · Anthropic · egress open` |
| Browser console errors | ✅ 0 |

**Honest note on caching:** the stable prefix (system prompt + workspace context)
was **2013 tokens** — just under Haiku's ~2048-token minimum cacheable size — so
no cache write occurred this round (`cache_write_tokens: 0`). The mechanism is
verified working: the `cache_control` breakpoint was sent, Anthropic returned the
cache accounting fields, and the streamed usage was captured and normalised into
the event. To observe a non-zero `cache_read_tokens`, use a model/prefix over the
minimum (Opus/Sonnet: ~1024; Haiku: ~2048) and send two turns in the same session.

## Result — 2026-07-10 (Task 3: path attachments, local stub backend)

The operator keys had expired by this round, so the model end of the turn ran
against a **local OpenAI-compatible stub** on the llama.cpp profile's endpoint
(`127.0.0.1:8080`) that answers based on what actually arrived in the request —
an honest end-to-end probe of the served path (raiker-web → gateway → context
gatherer → orchestrator → provider request) with no fabrication.

| Check | Result |
|---|---|
| `POST /api/prompts` with `attachments: [{type:"path", path:"mission-brief.txt"}]` | ✅ turn completed; the model's request contained the file's content (stub echoed the codeword back) |
| `context_gathered` event lists the `attachment` source | ✅ |
| Outside-workspace attachment (`/etc/passwd`) | ✅ denial note reached the model, **no file content did** (checked for distinctive passwd markers) |
| Invalid attachment shape (`type: "upload"`) | ✅ prompt rejected before a turn starts (`invalid_attachment_type`) |
| Browser: attach row adds a chip; sent bubble shows the attachment chip; input clears | ✅ |
| Browser: Models "Advisor model" section renders with the persisted advisor | ✅ `anthropic-hosted` |
| Browser console errors | ✅ 0 |

## Result — 2026-07-10 (Task 2: advisor model, hosted Anthropic)

| Check | Result |
|---|---|
| `advisor_model_runtime` gate enabled via control plane (threat ack + token) | ✅ |
| `PUT /api/model-advisor` persists `anthropic-hosted`; `GET /api/models` reflects it | ✅ |
| Decision mode default `ask` withholds the consult (no provider contact) | ✅ `advisor_withheld_ask` |
| With mode `allow`: `AdvisorService.consult` returns a real advisor answer | ✅ `claude-opus-4-8` answered; untrusted-data framing |
| Brokered `consult_advisor` tool through PolicyEngine + ToolBroker | ✅ policy `allow`, tool `success`, real answer returned to the caller |
| Durable event log is metadata-only (no question/answer text; lengths present) | ✅ verified against the session JSONL |
| Provider policy re-checked per call (hosted gate off ⇒ denied before network) | ✅ `advisor_provider_denied:provider_requires_explicit_policy_approval` |

## Result — 2026-07-10 (Task 7: provider model selection, hosted Anthropic)

| Check | Result |
|---|---|
| `GET /api/models/anthropic-hosted/provider-models` returns the provider's live catalogue | ✅ 10 models (claude-sonnet-5, claude-fable-5, claude-opus-4-8, …, claude-haiku-4-5-20251001) |
| Same endpoint with the hosted gate disabled | ✅ `status: policy_denied`, empty list, no network contact |
| Same endpoint for an unreachable local provider (llama.cpp) | ✅ `status: unavailable`, empty list — never fabricated |
| `PUT /api/model-selection` (`anthropic-hosted` + `claude-haiku-4-5-20251001`) | ✅ persisted; `GET /api/models` shows `current_model` + concrete model on the selected card |
| Streamed turn binds the selected model | ✅ `model_request_started → model: claude-haiku-4-5-20251001` |
| Per-turn override (`model_profile` + `model: claude-sonnet-4-6` on the prompt) | ✅ turn ran on `claude-sonnet-4-6`, exact answer returned |
| Browser: Models card picker lists the 10 live models; "Use model" re-selects through the UI | ✅ |
| Browser: Chat → Options → Provider populates a Model select from the live catalogue | ✅ 10 models |
| Browser: unreachable provider shows honest manual-entry fallback | ✅ "Provider unreachable — type a model id if you know it." |
| "Development preview" pill removed from the top bar | ✅ |
| Browser console errors | ✅ 0 |

## Result — 2026-07-29 (Chat / Build composer and persistence regression)

| Check | Result |
|---|---|
| Production web build | ✅ Vite build completed (242 modules) |
| Playwright Chat composer at 1440×1000 | ✅ prompt, model, effort, approval, context, and send controls visible |
| Playwright Build composer at 1440×1000 | ✅ repository, Plan/Edit/Auto, model, approval, context, and send controls visible |
| Keyboard guidance | ✅ inside both composer cards; Build and Chat share vertical rhythm |
| API-key restart regression | ✅ vault key restored from the workspace key file before model reads |
| Node 25.6.1 Storage warning | ✅ focused test passes with no warning |

Evidence: `docs/plans/screenshots/working/bug15-chat-composer.png` and
`docs/plans/screenshots/working/bug15-build-composer.png`. The Playwright test serves the
production bundle and mocks only authenticated API data, so it exercises the
real compiled Svelte UI without requiring live provider credentials.

## Result — 2026-07-29 (Settings / Models and expanded agent contracts)

| Check | Result |
|---|---|
| Vite 8 / Vitest 4 dependency audit | ✅ zero npm advisories |
| Multi-file unified patch | ✅ one preview/approval, two files changed, per-path checkpoint capture |
| Stale second file in a patch set | ✅ whole change rejected before the first write |
| Chat and Build model menus | ✅ menu opens and selection closes it on both pages |
| Settings at 1440×1000 | ✅ focused five-section rail; no redundant Storage page |
| Models at 1440×1000 | ✅ provider-backed model selector; no internal profile id visible |
| English browser checking | ✅ `spellcheck` and `en-US` active in both composers |
| Optional local LanguageTool adapter | ✅ authenticated, bounded, fail-soft when the operator-installed GPL/Java service is absent |

Evidence: `docs/plans/screenshots/working/settings-redesign.png` and
`docs/plans/screenshots/working/models-redesign.png`. The same committed Playwright suite
opens the real dropdown controls instead of checking only that their triggers
exist.

## Result — 2026-07-29 (Knowledge Map force-graph redesign)

| Check | Result |
|---|---|
| Production web build | ✅ Vite build completed with bundled `d3-force` and no external assets |
| Real force-directed layout | ✅ centre, repulsion, link, distance, collision, damping, and low-energy ambient motion |
| Graph-first surface at 1440×1000 | ✅ Raiker light-theme full-workspace canvas; no dotted dashboard grid or graph card boundary |
| Global/local graph interactions | ✅ global scope, node-centred local scope, relationship depth 1–3, hover neighbours, select/inspect, double-click centre, drag/pin, context menu, pan, zoom, and multi-select wiring |
| Floating settings | ✅ filters, search-driven colour groups, display controls, five physical-force controls, and Paused / Activity only / Always alive motion modes |
| Empty workspace guidance | ✅ instructional You → Workspace → Add first source topology replaces the single-node dead end |
| Governed live data | ✅ served `/api/brain` records and relationships remain the only persisted graph data; instructional starter nodes are explicitly virtual |
| Playwright live route and settings interaction | ✅ passed against the built SPA served by real FastAPI on `127.0.0.1:8765` |
| Application-wide theme sweep | ✅ all 23 pages/hub tabs rendered in explicit light and dark themes with distinct shared token palettes and zero console/page errors |

Evidence: `docs/plans/screenshots/working/knowledge-map-redesign-live.png`.
The first browser pass exposed and then verified the FIXED-51 reactive
simulation-loop correction; visual review then exposed and verified FIXED-52's
shared-theme integration. Both are recorded in `docs/plans/TO_BE_FIXED.md`.

## Result — 2026-08-01 (governance, execution, persistence, and attachment layout)

| Check | Result |
|---|---|
| Governed memory lifecycle | ✅ owner-scoped proposals, decisions, history, scope changes, expiry, edit, pin, forget, and purge controls exercised |
| Knowledge Map source review | ✅ bounded browse/review flow hides protected internals and persists owner graph preferences |
| Execution environments | ✅ local, container, SSH, and Daytona profiles render consistently; unavailable prerequisites fail closed |
| Local model capacity | ✅ `gemma4:31b-cloud` runtime capacity, scheduled refresh state, history, and owner override controls render |
| Reloaded approval | ✅ a parked file-write approval is restored after opening its persisted conversation and reloading the page |
| Chat and Build attachments | ✅ attached-file cards are sibling elements outside their user-message bubbles |
| Live model path | ✅ Anthropic and OpenRouter credentials connected through the UI; a real Ollama `gemma4:31b-cloud` Chat and Build turn completed |
| Browser assertions | ✅ `bug-29-34-live.spec.ts` passed in Chrome with no credential material written to the repository |

Evidence: `docs/plans/screenshots/working/173-BUG-33-capacity-admin-live.png`
through `179-BUG-34-reloaded-approval-live.png`. The source-review pass exposed
and verified protected-path filtering. Verification also identified the
cumulative Daytona billing reconciliation and accessibility diagnostics tracked
as BUG-42 and BUG-43 in `docs/plans/TO_BE_FIXED.md`.

## Result — 2026-08-08 (ADD-01 containerised tool execution)

| Check | Result |
|---|---|
| Real Docker bridge | ✅ `python:3.12-alpine` read `README.md` through the bounded JSON bridge with no network, read-only repository, read-only rootfs, dropped capabilities, and action-workspace cleanup |
| Container governance | ✅ `container_execution_cap` enabled through Permissions step-up; runtime, image, and tools selected only from server-advertised allowlists |
| Runtime settings | ✅ Docker profile persisted, showed `Docker · python:3.12-alpine`, `2 tools`, and `Read-only repository → writable output`, then became the selected Ready environment |
| Anthropic | ✅ credential entered through the password field in Models, Haiku 4.5 selected, real Chat response `ADD01 ANTHROPIC LIVE` |
| OpenRouter | ✅ credential entered through the password field in Models, provider catalogue used, real Chat response `ADD01 OPENROUTER LIVE` |
| Ollama | ✅ local `gemma4:31b-cloud` selected from the live catalogue, real Chat response `ADD01 OLLAMA LIVE` |
| Browser suite | ✅ `add-01-container-providers-live.spec.ts`; provider and Ollama response assertions plus container configuration, selection, and badge readiness |
| Visual review | ✅ five 1440×1000 screenshots inspected; no credential value visible, no clipped controls blocking the tested flow |

Evidence: `docs/plans/screenshots/working/add01-providers-connected-live.png`,
`add01-anthropic-turn-live.png`, `add01-openrouter-turn-live.png`,
`add01-ollama-turn-live.png`, and `add01-container-profile-live.png`. Live work
also exposed and closed FIXED-117 (cold import / stdin), FIXED-118 (broken Runtime
deep link), and FIXED-119 (ambient Ollama in offline tests).

## Repeatable procedure

## Result — 2026-08-08 (ADD-03 per-turn machine identity)

| Check | Result |
|---|---|
| Isolated host | ✅ fresh workspace, built SPA, real FastAPI runtime on `127.0.0.1:8765` |
| Owner/agent authority | ✅ Permissions rendered distinct Owner control and Raiker agent columns plus the Owner → Signed turn delegation rail |
| Anthropic | ✅ credential entered through Models UI; real Haiku 4.5 turn returned the exact acceptance text, proposed a governed file write as the machine actor, and recorded the human owner's denial separately |
| OpenRouter | ✅ credential entered through Models UI; real `openai/gpt-oss-20b:free` turn passed the same response, proposal, and denial contract |
| Ollama | ✅ local `gemma4:31b-cloud` passed the same response, proposal, and denial contract |
| Lifecycle evidence | ✅ `machine_identity_issued` and `machine_identity_deactivated` visible for each terminal turn; Activity shows the literal event actor separately from the contextual turn identity |
| Browser suite | ✅ Permissions plus all three provider cases passed individually in `add-03-machine-identity-providers-live.spec.ts`; a final combined retry run was provider-throttled after the already-green cases and did not replace those results |
| Visual review | ✅ seven 1440×1000 screenshots inspected at original resolution; no credential dialog/value or bearer material visible, and approval metadata remains readable without overlap |

The first screenshot pass exposed FIXED-120: full turn IDs made every machine
chip dominate the Activity actor column. A failing component regression was
added before the chip was changed to a compact visible turn ID; the complete
principal remains in the title and API. Focused component/view tests, Svelte
check, ESLint, production build, and each live provider case then passed. The
suite uses bounded page refreshes only for local API `429` responses; response,
identity, proposal, and authorization assertions are never retried away.

Evidence:
`docs/plans/screenshots/working/201-ADD-03-owner-agent-authority-live.png`
through `207-ADD-03-ollama-approval-attribution-live.png`.

The repeatable command shape is
`RAIKER_LIVE_ANTHROPIC_KEY=<ephemeral> RAIKER_LIVE_OPENROUTER_KEY=<ephemeral> npm --prefix web run test:e2e:live -- e2e/add-03-machine-identity-providers-live.spec.ts`.
Values are supplied only to the Playwright process and entered into password
fields; they are never written to source, docs, screenshots, or test fixtures.

1. **Bootstrap + enable the backend's gate** (human owner). For a hosted
   provider this means: activate `local_single_user_runtime`, record the
   threat-model ack, and enable the runtime gate with a confirmation token. See
   `docs/architecture/HANDOFF.md` → "How a user turns on a hosted provider". Local backends
   (llama.cpp/Ollama/LM Studio) need no hosted gate.
2. **Connect the provider** on the Models page (paste the key, or set the
   provider key env for the server process only — never a file — and tick
   **Use the key from `<VARIABLE>`**). The saved connection authorises that
   provider's address; there is no separate egress variable.
3. **Select the model:** `/model use …` (CLI), or persist a `ModelSessionState`
   for `TERMINAL_MODEL_SESSION_ID` with the profile id and a concrete model.
4. **Run:** `python -m raiker.api.serve --workspace <ws> --port 8765`, then mint a
   session and `POST /api/prompts/stream`. Confirm the answer, and read
   `GET /api/events?session_id=…` (or the store) for the
   `model_request_started` (bound model) and `model_request_completed`
   (`usage`) events.

## Per-model test matrix

`Verified` = a live governed turn has been run through the web app.
`Ready` = code path implemented; run the procedure above when a key/endpoint is
available. Each provider is reached only through the owner's saved connection for it.

| Provider | Profile id | Type | Egress host | Key env | Prompt caching | Status |
|---|---|---|---|---|---|---|
| Anthropic | `anthropic-hosted` | hosted | `api.anthropic.com` | `ANTHROPIC_API_KEY` | client `cache_control` breakpoint (5m/1h) | ✅ Verified (Haiku 4.5, 2026-08-08) |
| OpenAI | `openai-hosted` | hosted | `api.openai.com` | `OPENAI_API_KEY` | automatic server-side cache + `stream_options.include_usage`; no non-standard cache fields | ✅ Verified (`gpt-4o-mini` governed Build command, 2026-08-14) |
| Gemini | `gemini-hosted-openai-compatible` | hosted | `generativelanguage.googleapis.com` | `GEMINI_API_KEY` | automatic server-side | 🟡 Ready — egress blocked in this environment |
| OpenRouter | `openrouter-policy-gated` | hosted | `openrouter.ai` | `OPENROUTER_API_KEY` | automatic server-side | ✅ Verified (`openai/gpt-oss-20b:free` governed Build command, 2026-08-14) |
| llama.cpp | `raiker-local-llama-cpp` | local | `127.0.0.1:8080` | — | `cache_prompt: true` (server KV cache) | 🟡 Ready — needs a running llama.cpp server |
| Ollama | `ollama-local-openai-compatible` | local | `127.0.0.1:11434` | — | automatic server-side | ✅ Verified (`gemma4:31b-cloud` governed Build command, 2026-08-14) |
| LM Studio | `lm-studio-local-openai-compatible` | local | `127.0.0.1:1234` | — | automatic server-side | 🟡 Ready — needs LM Studio + a concrete model |
| Custom OpenAI-compatible | `generic-openai-compatible` | local or home-lab | user-selected | user vault | provider-dependent | 🟡 Ready — configure the endpoint and model in Raiker |

**Selecting a concrete model.** Profiles that ship a placeholder `<model>`
(Ollama/LM Studio/Custom OpenAI-compatible/OpenAI/Gemini/OpenRouter) take the concrete model at
selection time (`/model use --provider <p> --model <m>`). `anthropic-hosted`
also takes a concrete model at selection time; this test used
`claude-haiku-4-5-20251001`.

## Fallback sequence — how to test

Configure a sequence (Models → "Model fallback sequence", or `PUT
/api/model-fallback`), then make the primary provider fail (e.g. select a hosted
model with the gate on but no reachable key/host). The turn should emit
`model_fallback_engaged` and complete on the next reachable candidate; if every
candidate fails it fails closed with `model_unavailable`. Fallback never opens a
policy-denied provider — a denied candidate is skipped, not opened.


## Result — 2026-08-09 (BUG-69 universal model readiness)

A fresh isolated workspace was exercised through the built SPA in real Chromium.
Credentials were entered only through Models and were not persisted in evidence.

| Check | Result |
|---|---|
| First-run setup | ✅ Provider/local setup is prompted before model-backed work |
| Universal gate | ✅ Chat, Build, Tasks, and Schedule share the exact readiness gate; actions are disabled and drafts preserved |
| Ollama | ✅ Local `gemma4:31b-cloud` answered a bounded direct request and passed exact catalogue readiness |
| OpenRouter | ✅ `openai/gpt-4o-mini` passed catalogue plus execution preflight; a full governed turn parked its local action for approval without execution |
| Anthropic | ✅ Live catalogue/authentication succeeded; the account's insufficient-credit execution refusal was classified and Send remained disabled |
| Local library | ✅ An owner-approved root was scanned and GGUF name, architecture, and quantization were shown; no ambient path was scanned |
| Hugging Face | ✅ Live Hub search showed licence, immutable revision and GGUF-first choices; a tiny permissive GGUF downloaded into an approved root and reached completed managed llama.cpp deployment |
| Browser console | ✅ No application errors in the BUG-69 specs |

Specs: `bug-69-model-readiness-live.spec.ts`,
`bug-69-local-model-library-live.spec.ts`, and
`bug-69-huggingface-live.spec.ts`. Screenshots 208–213 are indexed in
`docs/plans/screenshots/README.md` (208–214).

## Result — 2026-08-10 (known-limits round, FIXED-161 to FIXED-170)

A fresh isolated workspace was exercised through the built SPA in real Chromium.
The Anthropic credential was entered only through Models and is not in evidence.

| Check | Result |
|---|---|
| Code-split routes | ✅ All eleven secondary destinations mount with content and no console error; the entry chunk is 237 kB (was 690 kB) and the build reports no size warning |
| Plugin supply chain | ✅ Extensions → Plugins states the workspace signing posture in words and names the two variables that raise it; installs are unaffected |
| Monitored capabilities | ✅ Settings → Security & sign-in lists containment for every capability family, not only MCP, and says so on an empty workspace rather than showing nothing |
| Circuit breaker | ✅ Three consecutive connector failures contained the subject as `paused` with its reason, streak and last failure code, raised a matching high-severity finding, and **Resume** cleared it in one press |
| Readiness window | ✅ The default reads 5 minutes, 30 survived Save changes and a navigation round trip, and the server resolved 30 for that owner |
| Readiness chip | ✅ `Ready · confirmed just now`, naming the exact model the provider reached |
| Model activity | ✅ Durable operations surface loads and states that failed work is never silently retried |
| Live turn | ✅ Anthropic Haiku 4.5 answered with the exact requested marker |
| Browser console | ✅ No application errors in either spec |

Specs: `bug-74-84-known-limits-live.spec.ts` and
`containment-surface-live.spec.ts`, both re-runnable against an already-driven
workspace. Screenshots `round0810-01` to `round0810-11` in
`docs/plans/screenshots/working/`.

## Result — 2026-08-14 (governed shell and provider matrix)

A disposable loopback workspace was exercised through the built SPA in real
Chromium. Each credential was entered through Models, was never placed in a
command or document, and is absent from screenshots and repository state. The
service and browser were stopped after the run.

| Check | Result |
|---|---|
| Governed terminal | ✅ A real exact-argv `git --version` command produced durable redacted output and an immutable receipt from the final rebuilt SPA; the earlier `git status --short` output/receipt also survived two app reloads |
| Authority path | ✅ Direct `POST /api/command-runs` is unavailable; approved `shell`/`process` and standing-grant `run_command` use the shared service and store their authority identity |
| Selected environment | ✅ Local host access was explicit and labelled reduced isolation; an unavailable selected backend failed closed with no host fallback |
| Build navigation recovery | ✅ Returning from Approvals refreshes both collapsed and already-open terminals; starting a new Build session replaces a stale selected run id with that session's newest run |
| Container readiness | 🟡 Docker CLI was present but its daemon named pipe was unreachable, so the digest-pinned command backend remained unavailable and no live container-execution claim is made |
| Ollama | ✅ `gemma4:31b-cloud` proposed and completed `git --version` through Build, approval, local execution, redacted output, and receipt |
| Anthropic | ✅ `claude-sonnet-4-6` completed the same governed Build command path |
| OpenAI | ✅ `gpt-4o-mini` completed the same governed Build command path after removing unsupported explicit cache fields; OpenAI caching remains automatic |
| OpenRouter | ✅ `openai/gpt-oss-20b:free` completed the same governed Build command path |
| Browser suite | ✅ `governed-shell-provider-matrix-live.spec.ts`: 4/4 provider cases passed serially in 38.5 seconds |
| Visual review | ✅ `docs/plans/screenshots/working/governed-shell-{anthropic,openrouter,openai,ollama}-live.png` were inspected at original resolution for command/provider identity, authority, isolation, output, receipt, clipping, and secret absence |

This run proves the foreground local shell, durability, governance evidence,
and the complete four-provider model-to-command path. It does not prove PTY/background input,
service-restart reattachment, filtered egress, credential quarantine, SSH,
Daytona, or live Docker execution; those remain BUG-194.

## Result — 2026-08-15 (BUG-206 tool rows, BUG-207 model reasoning)

A disposable loopback workspace was created for each run and destroyed after it.
The Anthropic credential was entered through Models by the spec, was never placed
in a command, a document or a screenshot, and is absent from repository state.
The service and browser were stopped after the run.

| Check | Result |
|---|---|
| Tool rows in Chat | ✅ A two-call turn rendered `List folder · the workspace root · done` then `Read file · README.md · done`, one line each, in the model's proposal order |
| Proposal order under concurrency | ✅ Independent reads run in parallel (B4) and settled out of order; the rows still read in the order the model asked, because they are opened from the validated proposals |
| Nothing raw reaches the row | ✅ The turn's `.tool-activity` text contained no `{`, no `read_file` and no `list_directory` — no argument JSON and no tool identifier |
| The element list BUG-206 found empty | ✅ `tool-activity`, `tool-row`, `tool-glyph`, `tool-label`, `tool-action` are now in it |
| A call waiting on a decision | ✅ `Write file · notes.md · waiting for your decision`, beside its approval card; the phrase appears exactly once, so a screen reader hears it once |
| A refused call (batching stub) | ✅ `Read file · ../escape.md` with `refused — workspace_boundary_denied, outside_workspace:path`, directly above the `List folder` row that succeeded in the same batch; the old `.refusal-card` is absent |
| Model reasoning, live | ✅ With **Thinking: adaptive**, `claude-haiku-4-5-20251001` streamed its own working for 17 × 23 into the collapsed block; it names the numbers the owner typed, which no fixed string could |
| The thinking spelling negotiated | ✅ Haiku 4.5 refuses `thinking.type.adaptive`; the provider read the alternative out of the refusal, re-issued once, and the turn thought rather than failing with a 400 |
| The three canned sentences | ✅ Absent, as is the "See what Raiker is thinking" label |
| Collapse on answer | ✅ `aria-expanded="false"` once the answer starts, still openable |
| Reasoning off | ✅ No reasoning section at all, and no tool activity for a turn that called nothing |
| Build parity | ✅ Same rows, same reasoning block, same collapse, from the same components and data path |
| A decided call settles | 🟡 **Not proven live.** The approved call is not re-brokered on resume, so the runtime settles the row from the recorded outcome and the client merges rather than replaces — asserted in `test_turn_model_binding.py`, `resumed_call_row_status` and `chatPresentation.test.ts`, but watching it settle needs the running tab to stay mounted while the decision is made elsewhere, and that step was flaky rather than evidential |
| Browser suites | ✅ `bug-206-207-tool-rows-and-reasoning-live.spec.ts` 6/6; `bug-52-first-pass-denial-live.spec.ts` 4/4 against the batching stub; `composer.spec.ts` (mocked) 4/4 |
| All-pages sweep | ✅ `all-pages-live.spec.ts` captured all 24 routes with **0 console errors**, after the sweep's own stale sign-in was fixed (FIXED-215) |
| Visual review | ✅ `docs/plans/screenshots/working/bug-206-live-tool-rows-{streaming,settled}.png`, `bug-206-live-tool-row-waiting.png`, `bug-207-live-reasoning-{streaming,settled}.png`, `bug-207-live-no-reasoning.png`, `bug-206-207-live-build-turn.png` inspected at original resolution for row order, wrapping, state colour, and secret absence |

This run proves the live transcript surface end to end on hosted Anthropic: what
a turn did, what it thought, and what it refused. It does **not** prove that
either survives a reload — neither is persisted, which is
[BUG-215](../plans/FIXED_ITEMS.md#fixed-219--reasoning-was-shown-live-and-then-forgotten-was-bug-215).

## Release candidate qualification

Historical provider rounds above prove their named scenarios/configurations.
They are not a full release verdict. Use
[RR-01–RR-36](../plans/TESTING.md) and the
[manual release procedure](../plans/TESTING.md)
for a candidate: real streamed work, approval/resume/Stop, goal/task lineage,
source/destination verification, provider failures, reload/concurrent tabs,
first-use accessibility and artifact opening. Record browser/client/host/model
separately, plus all interventions and faults. A mocked API/UI pass or a screenshot
cannot substitute for real-provider completion. Planned personal-agent/browser
controls remain unrun until their production paths exist.
