# 03 Welcome, Home and Chat

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

## Status

**First round shipped 2026-10-21** ([FIXED-1057](../FIXED_ITEMS.md#fixed-1057--home-had-no-way-to-start-work-by-asking-qui-h01)
to [FIXED-1074](../FIXED_ITEMS.md#fixed-1074--home-said-no-model-is-set-up-while-a-chat-was-answering);
live cases RT-QUI-01 to RT-QUI-09). **Second round shipped 2026-10-21**
([FIXED-1080](../FIXED_ITEMS.md#fixed-1080--home-offered-five-threads-to-continue-instead-of-the-one-with-its-next-step-qui-h01)
to [FIXED-1094](../FIXED_ITEMS.md#fixed-1094--setup-had-no-way-to-skip-it-qui-w06);
live cases RT-QUI-10 to RT-QUI-13 and RT-QUI-16). Both in
[WEB_APP_LIVE_TEST.md](../../architecture/WEB_APP_LIVE_TEST.md).

| Item | State |
|---|---|
| QUI-H01 | **Done**, with the profile chip on Home's composer since 2026-10-22 ([FIXED-1130](../FIXED_ITEMS.md#fixed-1130--a-conversation-could-not-say-how-careful-raiker-should-be-qui-p02)). Greeting with one true fact, composer with Attach, one Continue card with its next step, one decision row, at most two in-progress rows, This week, and one 980 px column. |
| QUI-H02 | **Done**, without the companion: the companion's art does not exist yet ([08, QUI-V05](08_BRAND_AND_VISUAL_SYSTEM.md#qui-v05--companion)). |
| QUI-H03 | **Done.** Home is the default and Settings → General can choose Chat; the option now reads Home. |
| QUI-H04 | **Done.** The line names the version; a count of changes needs release notes the host can read. |
| QUI-H05 | **Done.** Stale means the newest *verified* backup is seven days old, the same window as *This week*. |
| QUI-C01 | **Done**: editable title, project chip, search in conversation, Context toggle. |
| QUI-C02 | Already true before this round; unchanged. |
| QUI-C03 | **Done**: the status line, follow-ups queued from the prompt and Stop safely in Send's place (2026-11-07, [execution states](#2026-11-07--composer-execution-states)), the outcome line, and the task receipt at the end of each turn (2026-10-24, [QUI-F16, FIXED-1153](../FIXED_ITEMS.md#fixed-1153--a-tasks-end-did-not-say-what-it-used-read-changed-or-sent-qui-f16); per task in Tasks, [FIXED-1261](../FIXED_ITEMS.md#fixed-1261--a-background-task-had-no-receipt-qui-f16-found-this-round)). |
| QUI-C04 | **Partly done.** Done: the placeholder, the data label and the profile chip (QUI-P02, 2026-10-22); answer style is in Settings › General until *More* exists (04, closed; [FIXED-1145](../FIXED_ITEMS.md#fixed-1145--there-was-no-way-to-ask-for-fewer-or-more-visuals-04-answer-style), 2026-10-23). Open: *More* (schedule, research depth). |
| QUI-C05 | **Done.** |
| QUI-C06 | **Done.** |
| QUI-C07 | **Done.** Tabs: Context (files in use), Plan, Sources, Activity. Memories in use are not listed yet: a turn's recall reports a count, not the records. |
| QUI-C08 | **Done.** |
| QUI-C09 | Already true before this round: Edit and Retry make a new turn and keep the earlier one. |
| QUI-C10 | **Done**, without the companion. |
| QUI-C11 | **Done** in the composer's **Tools** menu, because *More* does not exist yet (QUI-C04). The task shows in Background work and Home's In progress. |
| QUI-C12 | **Done.** Below 1,920 px the panel opens over the transcript and ends above the composer; from 1,920 px it sits beside it. |
| QUI-W01 | **Done.** The owner chose the open ring on 2026-10-25 ([QUI-V04](08_BRAND_AND_VISUAL_SYSTEM.md#qui-v04--app-mark-the-open-ring), [FIXED-1168](../FIXED_ITEMS.md#fixed-1168--the-app-mark-was-the-eye-orb-qui-w01-qui-v03-qui-v04)); it is on the lock screen, the sidebar and every icon. |
| QUI-W02 | **Done**, without the companion pick (no art yet). The stored `welcome` stage is the Hello step; the name is saved to Settings › Account. |
| QUI-W03 | **Done.** On this computer shows what this device can run; keys go in the provider card's secure field. |
| QUI-W04 | **Done.** |
| QUI-W05 | **Done.** The first message opens Chat and the conversation is renamed *Getting started*. |
| QUI-W06 | **Done**: Skip setup, Run setup again, and a progress line of real steps (Name · Model · Privacy · Start on a desktop install). |

**Starters.** The four are *Summarise a document*, *Plan my week*, *Fix a bug
in a repository* and *Make an image* (`web/src/lib/starters.ts`). The first two
fill the composer; the last two open Build and Design.

## Reference products

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

## Welcome (first run)

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

## Home

### QUI-H01 — Layout

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

### QUI-H02 — First day

On an empty first day Home shows the companion (96–128 px), the composer and the
four starters, nothing else.

### QUI-H03 — Startup page

Home by default; can be set to Chat in Settings › General.

### QUI-H04 — What's new

After an update, one dismissible line ("Updated to 1.4 · 3 changes") linking to
About & updates. Never a modal.

### QUI-H05 — Backups

Backup is recommended on Home only when there is none or it is stale.

## Chat

### QUI-C01 — Layout

Layout A. Transcript and composer 680–760 px wide. Top strip: editable title,
project chip, search in conversation, Context toggle. Chat, Build and Design
switch in the top bar and keep the draft.

### QUI-C02 — Messages

| Type | Presentation |
|---|---|
| Your message | Right-aligned muted bubble, at most 640 px |
| Raiker's answer | Left-aligned reading surface, at most 680 px |
| Tool step | 36 px row, grouped ("2 steps") and expandable |
| Plan | Checklist card with real states and the path line |
| Result | Bordered card with one action (Open draft, View diff, Open image) |
| Approval | Raiker Safety card ([02, QUI-P05](02_PERMISSIONS_AND_APPROVALS.md#qui-p05--the-approval-card-raiker-safety)) |
| Question | Clarifying-question card ([QUI-F02, FIXED-1151](../FIXED_ITEMS.md#fixed-1151--a-question-asked-mid-task-was-offered-as-an-approval-in-chat-build-and-the-floating-card-qui-f02)) |
| Visual answer | Answer blocks ([Chat guide](../../guide/working-in-chat.md#tables-charts-and-other-answer-blocks)) |

### QUI-C03 — A turn, step by step

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
   unknown, linking to its activity, with the task receipt ([QUI-F16, FIXED-1153](../FIXED_ITEMS.md#fixed-1153--a-tasks-end-did-not-say-what-it-used-read-changed-or-sent-qui-f16)).
8. **Memory.** Anything worth remembering appears as a suggestion (Save ·
   Dismiss). Never saved silently.

### QUI-C04 — Composer

| Element | Decision |
|---|---|
| Placeholder | "What would you like Raiker to do?" |
| Input | Grows to five lines, measured from its own line height, then scrolls (owner decision 2026-11-07; briefly about eighteen lines that day, 180 px before) |
| Action row | 44 px: Attach · Project · Profile chip · context count when relevant · More · Send (40×40, far right) |
| More | Schedule, research depth, model, work mode, answer style |
| Data label | "Stays on this computer" / "Sent to Anthropic" ([QUI-F17, FIXED-1154](../FIXED_ITEMS.md#fixed-1154--homes-composer-did-not-say-where-a-message-would-go-qui-f17)) |
| Model | Shown as a small label only when it is not the default |
| Bottom spacing | 24 px |

### QUI-C05 — No model

The composer stays usable. One line above it: "No model is set up · Set up".
Send stays enabled; sending opens the Add model dialog with the message kept and
sends it once a model is ready.

### QUI-C06 — Conversations

One conversation per topic. The sidebar's Chat row lists the five most recent
chats beneath it. The full list is Work › Threads. New chat: Ctrl/Cmd+N.

### QUI-C07 — Context panel

Closed by default, 320 px. Tabs only when they have content: Context (files and
memories in use), Plan, Sources, Activity.

### QUI-C08 — Streaming and scrolling

Answers stream. The view follows only while at the bottom; scrolling up stops
following and shows **Jump to latest**.

### QUI-C09 — Editing

Edit your last message or retry an answer. Earlier versions are kept, not
overwritten.

### QUI-C10 — Empty chat

Brief greeting, one sentence on what Raiker can do, at most four starter prompts,
an optional small companion (96–128 px). No hero image.

### QUI-C11 — Background work

"Run in background" lives in More. A background task appears in the live work
line and on Home › In progress.

### QUI-C12 — Window sizes

At 1,280 px the context panel opens over the transcript. At 1,920 px and up it
sits beside it and the transcript stays 720 px.

## Acceptance

* Setup can be completed or skipped without ever typing a secret into the
  transcript.
* No progress indicator shows a step that has not actually started.
* Home with nothing to show renders only the greeting, composer and starters.
* A chat with no model accepts and keeps the message.

## 2026-11-07 — Composer control deck

**Owner decisions, 2026-11-07.** The owner supplied an AI-agent composer
brief and decided four open questions:

* **Shape:** a floating glass capsule. This reverses the 2026-11-06 rejection
  of the idle capsule recorded in
  [VISUAL_DESIGN_SPEC.md](../../architecture/VISUAL_DESIGN_SPEC.md). The card
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
  [TO_BE_FIXED](../TO_BE_FIXED.md#composer-agent-personas-for-).

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

Evidence: [FIXED-1304](../FIXED_ITEMS.md#fixed-1304--the-composer-was-a-short-solid-box-with-no-context-guardrails-qui-c04)
and the [Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-composer-control-deck).

## 2026-11-07 — Composer execution states

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

Evidence: [FIXED-1306](../FIXED_ITEMS.md#fixed-1306--a-running-turn-had-a-second-stop-button-a-separate-steer-field-and-no-step-view-qui-c03-qui-c04).
The live round found that a stopped turn never reached the model's history,
so a continuation had nothing to continue
([FIXED-1307](../FIXED_ITEMS.md#fixed-1307--a-stopped-turn-was-left-out-of-the-conversation-the-model-saw-found-this-round)).
See the [Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-composer-execution-states).
The editor layer (in-composer code blocks, ghost text, `{variable}` injectors),
*More* (QUI-C04) and `@` personas remain open
([TO_BE_FIXED](../TO_BE_FIXED.md#composer-agent-personas-for-)).
