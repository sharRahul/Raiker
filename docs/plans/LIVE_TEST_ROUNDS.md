# Live test rounds — the record

**This document is the evidence. It is append-only, and it never says what to
do.** The procedure lives in
[`RAIKER_LIVE_MANUAL_TEST_PLAN.md`](RAIKER_LIVE_MANUAL_TEST_PLAN.md); a step
there states what *must* be true, and a round here states what *was* true on one
day, on one machine, against one set of providers.

Keeping them apart is the point. They used to be one document, and a step read
"click **Test** — on 2026-08-08 this returned Ready", which meant a person
re-running it could not tell the expectation from one morning's observation. A
round that has been folded into the procedure has stopped being evidence.

## How to add a round

1. Run a tier from the plan — **Smoke** or **Full sweep** — and record which.
2. Add a section here, newest first, with: the date, the tier, the build, the
   providers, what it proved, what it found, and the screenshot prefix.
3. Put screenshots under [`screenshots/working/`](screenshots/working) with that
   prefix, and defects under
   [`screenshots/not-working/`](screenshots/not-working) named for their entry
   in [`TO_BE_FIXED.md`](TO_BE_FIXED.md).
4. Add the prefix to the rounds table in
   [`screenshots/README.md`](screenshots/README.md).
5. **Never edit an earlier round.** If it recorded something that later turned
   out to be wrong, add a note to the *new* round saying so. A record rewritten
   after the fact is not a record.

**Never commit an API key.** Keys go into the Connect dialog or the server
process environment, for the duration of the round only.

## Rounds at a glance

| Date | Tier | Prefix | Providers | What it covered |
|---|---|---|---|---|
| 2026-09-04 (fourth) | Targeted + measured four-width sweep | `pages/` | — (no model needed) | Two tabs folded out of the nav, 244 words moved to the guide, and three mobile bleeds the width sweep found only because the workspace had been worked in |
| 2026-09-04 (third) | Targeted + measured four-width sweep + full page sweep | `bug-276-`, `bug-277-`, `bug-278-`, `pages/` | Anthropic, a third **identity-linked** key entered through the interface | A telemetry cadence that runs without a button, and three defects the round found in the product by using it: a valid key answered with "check your network", twenty-six connectors that said they were installed, and a "next run" printed as a full timestamp |
| 2026-09-04 (second) | Targeted + measured four-width sweep | `widths/`, `anthropic-identity-linked-key` | Anthropic, the same **identity-linked** key entered through the interface | Five priority items landed and measured live, and two interface defects the sweep itself found: a model picker that called a provider unreachable after it had answered, and a control that drew nothing |
| 2026-09-04 | Targeted + full responsive sweep | `bug-274-`, `pages/` | Anthropic, an **identity-linked** key entered through the interface | A key Raiker previously had no way to use, the field that makes it usable reached from where the refusal is read, and every route measured at four widths in both themes |
| 2026-09-03 | Targeted + full responsive sweep | `bug-256-`, `pages/` | Anthropic, key entered through the interface | Dictation running with nothing leaving the machine, a locked load that refuses nothing, and every page measured at four widths in both themes |
| 2026-08-30 | Targeted + measured responsive sweep | `b13-`, `bug-239-`, `bug-245-`, `ui-sweep-` | Anthropic (`claude-haiku-4-5-20251001`), key entered through the interface | The repository on screen in Build, Permissions telling the truth about an untouched gate, a cited exchange that opens — and every route *measured* at three widths rather than photographed |
| 2026-08-29 | Targeted | `bug-244-`, `bug-246-` | — (no model needed) | An import that says what is already stored before it writes, and the authority matrix readable at a phone width |
| 2026-08-29 | Targeted + full responsive audit | `b18-`, `mem08-` | Anthropic | Rewind asked for at the turn that caused the change, a turn coordinate that opens the exchange, and every route measured at four widths |
| 2026-08-29 | Targeted + responsive | `fixed-309-` … `fixed-312-`, `r0829-` | Anthropic | Build's conversation surviving a reload, the memory integrity report reaching a page, recall named and correctable in the answer it shaped, an inline diff in Build — and a question that could not recall the memory answering it |
| 2026-08-29 | Targeted | `real-work-` | Anthropic | **What Chat and Build actually do**: a scheduled task, a project, a dashboard that renders, and a program Build wrote that this round executed |
| 2026-08-29 | Targeted | `fixed-306-` | Anthropic | Owner-guided compaction: a summarised range, and a transcript that kept every turn |
| 2026-08-28 | Targeted | `fixed-305-` | Anthropic, OpenAI, OpenRouter, Ollama — every key entered through the interface | The last three lifecycle hook events, on a real tool-using turn and across four providers |
| 2026-08-28 | Full sweep + targeted | `pages/`, `fixed-299-`, `bug-225-` | Anthropic, OpenAI, OpenRouter, Ollama — existing credentials managed through the Raiker interface | All 26 route/tab states at mobile, 1080p, 4K and 8K in both themes; channel routing and approval-relay controls; owner skill commands in Chat and Build; four-provider readiness from the Models UI |
| 2026-08-25 | Targeted | `r0825-` | Anthropic, OpenAI, OpenRouter, Ollama — every key entered through the interface | A semantic space built against a real embedding call — **and measured, which found the read half missing** — the retention sweep, task cadences, delegated-task ownership, tool rows after a reload, and a responsive sweep at five widths |
| 2026-08-24 | Targeted | `r0824-` | Anthropic (`claude-haiku-4-5-20251001`) | What each capability switch actually decides, Agent Skills conformance on the Skills tab, and Auto's alignment check against a real turn |
| 2026-08-23 | Targeted | `r0823-` | Anthropic, OpenAI, OpenRouter | The checkpoint rewind end to end, the audit export, the deleted second egress path, and two defects the rewind exposed |
| 2026-08-22 | Targeted | `bug-219-`, `bug-221-`, `bug-223-`, `bug-225-` | Anthropic, OpenAI, OpenRouter, Ollama | Hooks off switch and lifecycle events, plugin-contributed skills and MCP offers, channel owner surface, the fourth approval mode |
| 2026-08-21 | Targeted | `r0821b-`, `r0821c-`, `2026-08-21-` | Anthropic | Governed voice, Build modes and operating protocol, the two composers, the Hooks tab, responsive sweeps |
| 2026-08-17 | Targeted | `r0817-`, `r0817b-` | Anthropic Haiku 4.5 | FTS5 retrieval, owner-selected recall backend, background execution and a POSIX terminal, eidetic capture, restart reattachment, persistent environment |
| 2026-08-15 | Targeted | `r0815-` | Anthropic, OpenAI, OpenRouter, Ollama | The native OS sandbox and its measured boundary |
| 2026-08-11 | Targeted | — | Anthropic, OpenAI, OpenRouter, Ollama | Multi-provider usage and compaction; memory recall |
| 2026-08-10 | Targeted | `r0810-` | Anthropic Haiku 4.5 | Known limits; closing the 2026-08-08 round's four defects |
| 2026-08-09 | Targeted | `208-`–`214-` | Anthropic, OpenRouter, Ollama, Hugging Face | BUG-69 closure — first-run model setup and acquisition |
| **2026-08-08** | **Full sweep** | `r0808-` | Anthropic, all ten catalogue models | **The last full sweep.** Every surface in a real Chromium session |
| 2026-07-26 → 08-04 | Targeted | numeric, `b*`, `c*` | Anthropic, Ollama | Earlier rounds, kept where their evidence is still the best record |

**The last full sweep was 2026-08-08.** Everything since has been targeted at a
specific change. That is the honest state of coverage, and it is why the plan now
carries a tier that says which one a round ran.

---

## 2026-08-29 — An import that counts what it changes, and a matrix that fits a phone

**Tier: Targeted. Build: production `npm run build`. Providers: none — neither
scenario needs a model, which is the honest reason this round has no key
recorded against it. Prefixes: `bug-244-`, `bug-246-`.**

Spec: `apps/web/e2e/bug-244-246-import-duplicates-and-narrow-authority-live.spec.ts`.

1. Memory → *Advanced memory management* → **Review import** with a two-record
   file the workspace has never seen. Confirm the review step says **2 new**
   before anything is written, import them, and confirm the notice reports
   *"Imported 2 records."* *(FIXED-319.)*
2. Choose **the same file again**. Confirm it says all 2 records are already
   stored, that the ordinary import button is **absent** rather than disabled,
   and that **Import anyway** is still offered — an owner who means to hold the
   same sentence at a second scope is doing something legitimate. *(FIXED-319.)*
3. Permissions at 390 px. Confirm every capability's owner control and agent
   verdict are readable as labelled pairs, that no row is cut mid-word (the
   literal string `Unavail` appears nowhere), and that the page does not scroll
   sideways. *(FIXED-320.)*

**Result: ✅ two entries closed** — FIXED-319 and FIXED-320.

**What this round did not need, and why that is the point.** Neither scenario
sends a turn. BUG-244 was found *because* [FIXED-311](FIXED_ITEMS.md#fixed-311--recall-was-invisible-at-the-moment-it-was-used)
made recall visible and four identical sentences showed up under one answer —
but proving the fix needs only the import path, and pretending otherwise would
have made the round slower without making it stronger.

---

## 2026-08-29 — Rewind at the turn, an openable turn coordinate, and a four-width audit of every page

**Tier: Targeted + full responsive audit. Build: production `npm run build`.
Providers: Anthropic `claude-haiku-4-5-20251001`, key entered through Models.
Prefixes: `b18-`, `mem08-`.**

Spec: `apps/web/e2e/b18-mem08-rewind-and-turn-anchor-live.spec.ts`.

1. Sign in and connect Anthropic through Models, pinning an exact model. This
   round signed in on a workspace that **already held work**, which is where it
   started: the shared helper asserted the empty-workspace heading, so a round
   re-run against the workspace its own first run created failed on step one and
   the failure looked like a product defect. `signInAsOwner` now accepts either
   heading — the first repair BUG-229 has had.
2. Send a real Chat turn, open the per-message overflow, and confirm **Rewind to
   before this** is offered. Open it: the preflight names *this turn's*
   checkpoint, states what would be rewritten, deleted and skipped, and says in
   words that it asks for a rewind rather than performing one. Confirm no
   `POST …/restore` was made by opening it. *(FIXED-315.)*
3. Send two turns with distinct markers, search chat history for one, and
   confirm the result links to `…?session=…&turn=…`, lands on that exchange with
   it marked, marks **only** that one, and drops `turn=` from the address after
   landing. *(FIXED-316.)*
4. Repeat step 2 at 390 px. Confirm the overflow menu and the preflight both
   work, and that the page does not scroll sideways.
5. Repeat step 2 in **Build**, which has a different workspace grid and is the
   surface whose turns actually change files. Confirm the panel takes a column
   of its own rather than stacking under the composer.
6. Observability → Checkpoints: confirm a snapshot's **Turn** field links back to
   the exchange it was taken at. *(FIXED-316.)*
7. **Every route and tab state — thirty of them — at 390, 834, 1440 and 2560 px,
   measured rather than eyeballed**: page-level horizontal overflow, elements
   escaping their own scroller, control hit sizes, and console and page errors.

**Result: ✅ two entries closed** — FIXED-315 and FIXED-316 — **and two raised
and closed in the same round.**

Step 7 is the reason the round is worth more than the two it set out to prove.
The responsive contract held completely: **no route scrolled the page
horizontally at any of the four widths, nothing escaped its own scroll
container, and not one route logged a console or page error.** What it did find
was measurable and invisible to the eye: every checkbox in the app was the user
agent's own 13x13 box — under WCAG 2.2's 24 px minimum target — on five
different routes, and the Hooks tab had set its own 16 px size, so they were not
even consistent with each other. That is
[FIXED-318](FIXED_ITEMS.md#fixed-318--a-checkbox-was-thirteen-pixels-in-five-places).

The second was found in the code while closing MEM-08: three tools declare a
`source_kind` and produced no source at all, so an answer drawn from a past
conversation, a code-map reference lookup or the memory graph cited nothing.
That is [FIXED-317](FIXED_ITEMS.md#fixed-317--three-tools-declared-a-source-and-produced-none),
and it is the third instance of the same failure mode — two lists that have to
agree with nothing holding them together — so it is now held by an invariant
test rather than by care.

Two smaller defects were found by looking at the evidence rather than at the
assertions, and both are fixed in FIXED-315: the preflight rendered its whole
funnel around a change that did not exist (a chat turn writes no workspace file,
so the honest answer is one sentence), and a preflight left open across a
conversation load described a checkpoint from a conversation no longer on
screen.

**What this round did not prove.** Nothing was actually restored: every scenario
stops at the raised approval, because a chat turn's checkpoint has no file
changes to rewind. The execution half is the same governed path
[the 2026-08-23 round](#2026-08-23--the-rewind-the-audit-export-and-two-defects-the-rewind-exposed)
drove end to end.

---

## 2026-08-29 — Build restore, memory integrity, recall visibility and inline diff

**Tier: Targeted + responsive sweep. Build: production `npm run build`.
Providers: Anthropic `claude-haiku-4-5-20251001`, key entered through Models.
Prefixes: `fixed-309-`, `fixed-310-`, `fixed-311-`, `fixed-312-`, `r0829-`.**

Specs: `apps/web/e2e/bug-242-build-restore-mem-09-live.spec.ts` and
`apps/web/e2e/c17-b14-recall-and-inline-diff-live.spec.ts`.

1. Bootstrap a fresh owner account, dismiss the setup wizard, connect Anthropic
   through Models and pin an exact model. *(FIXED-133 re-verified.)*
2. Create a project, run a real Build turn, and confirm the address bar now
   carries the conversation. Reload. Sign in again — the control session lives
   in memory, so a reload always asks — and confirm Build comes back to the
   prompt, the answer and the project it was filed under, rather than to an
   empty conversation. *(FIXED-309.)*
3. Observability → Diagnostics. Confirm a **Memory integrity** card reporting
   `clean`, with **Rescan** beside it and no repair offered where there is
   nothing to repair. *(FIXED-310.)*
4. Every route at 375, 768, 1024 and 1440 px: confirm each renders, that no
   route scrolls the page sideways at any width, and that the round ends with
   **zero console errors**. *(Responsive sweep.)*
5. Import one approved memory through Memory → Advanced, ask a question in Chat
   that the memory answers, and confirm the reply carries a **Remembered**
   strip naming the sentence, with **Correct** and **Forget** on it.
   *(FIXED-311.)*
6. Ask Build to write a file. Confirm the parked decision shows the unified diff
   under it — the file, `+1 −0`, the hunk and the added line — with **Accept**
   and **Reject** beneath. *(FIXED-312.)*

**Result: ✅ four entries closed** — FIXED-309 through FIXED-312 — **and one
raised and closed in the same round.** Step 5 first failed with the memory
approved, searchable and never recalled: `Where do my nightly backups go?`
returned nothing against a memory reading *"My nightly backups go to the
encrypted NAS in the garage."* while `backups` returned it. The full-text join
is an AND, so every word of the question had to appear in the stored sentence.
That is [FIXED-314](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it),
and it is the reason this round is worth more than the four entries it set out to
prove: the recall strip would have shipped correct and empty.

**A note on the evidence itself.** Every capture in this round went through the
new `apps/web/e2e/capture.ts`, which is
[FIXED-313](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport).
`fixed-310-memory-integrity-card.png` is 2097 px tall on a 1000 px viewport —
under the old `fullPage: true` it would have been the first 1000 px, and the card
it is named for sits below that line.

---

## 2026-08-29 — what Chat and Build actually do

**Tier: Targeted, and a different kind of targeted.** Chromium via Playwright at
1440 × 1000, light. **Provider:** Anthropic (`claude-haiku-4-5-20251001`). The
key was supplied to the runner as an environment variable for the length of the
round and entered through the product's own Connect dialog; none was placed in
source, a test fixture, or this document. **Prefix:** `real-work-`.

Every earlier round proves a *control* works: a rule loaded, an event fired, a
card rendered. This one asks whether the product can be used to get work done,
and every scenario ends at a fact outside the transcript.

### What it proved

* **The fail-closed default is real.** On a fresh workspace the first attempt to
  create a task was refused with `disabled_by_capability_gate` — the model called
  `create_task` correctly, `auto` granted it correctly, and the capability gate
  stopped it. The round now turns the capability on through Permissions first,
  the way an owner does, which is a better test than assuming it was on.
* **Chat created and scheduled a task.** "Rotate the staging credentials" exists
  with `recurrence: weekly`, read back from the owner's own Tasks page
  (`real-work-chat-scheduled-task.png`).
* **Chat created a project**, through the Projects surface, and Build then worked
  inside it (`real-work-project-created.png`).
* **Chat built a dashboard that renders.** `status-dashboard.html` — 6.4 KB, no
  external requests — was written to the workspace, and the round opened it in a
  browser and asserted its three headings are visible
  (`real-work-chat-dashboard-renders.png`). A file that parses is not a page.
* **Build wrote a program, and the program runs.** `fizz/fizzbuzz.py` appeared in
  the workspace folder, and the round *executed it* and asserted its output line
  by line — `1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz`. This is
  the assertion the whole round exists for: a written file that does not work is
  the failure a transcript cannot show.

### What it found

**[BUG-242](FIXED_ITEMS.md#fixed-309--build-opened-an-empty-conversation-after-a-reload)
— Build opens an empty conversation after a reload.** A seventh scenario was
written to assert that Build's record survives a reload, and it does not:
`sessionId` in `BuildView` is only ever set from the streaming response and is
never restored from the URL. Nothing is lost — the session and its tool rows are
stored and Search chats finds them — but the page the owner was working on does
not come back. Chat restores; Build does not. The scenario was removed rather
than weakened, and the defect raised.

Four harness defects were fixed in the same pass, each of which had been quietly
making a scenario test the wrong thing:

* **A hash-only `page.goto` does not re-render this app.** A scenario that ran a
  turn in Chat and then "navigated" to Tasks was still looking at the Chat
  transcript — it failed for the right reason and the wrong cause, while the task
  had in fact been created correctly. Navigation now goes through the rail, which
  is also the path an owner takes.
* **Sign-in waited for a first-run heading**, so a workspace the round had
  already configured could never be signed into a second time. That is
  [BUG-229](TO_BE_FIXED.md#bug-229--most-live-specs-sign-in-only-on-an-empty-workspace)
  behaving as recorded; the helper now waits for the navigation rail, which is
  what "there is a session here" actually means.
* **Two locators matched hidden elements** — a project name inside a `<select>`
  option, and Chat's textarea sitting behind Build's. Both had passed a
  visibility assertion on `.first()` and then failed on use.
* **Build refuses to send without a project selected**, which is correct and was
  a silent failure in the round: the composer's project picker is now part of the
  scenario.

The workspace was also destroyed while a server still had it open, which left an
unopenable store and a login form disabled by `store_open_failed`. The product
reported it accurately; the round's own setup order was wrong.

---

## 2026-08-29 — the owner's own compaction

**Tier: Targeted.** Chromium via Playwright at 1440 × 1000, light. **Provider:**
Anthropic (`claude-haiku-4-5-20251001`). The key was supplied to the runner as an
environment variable for the length of the round and entered through the
product's own Connect dialog; none was placed in source, a test fixture, or this
document. **Prefix:** `fixed-306-`.

### What it proved

* **Summarise up to here** appears on the owner's own message beside Copy, Edit,
  Retry and Branch, and summarising through the first of two real turns reported
  "Summarised 1 earlier exchange for the model. Nothing was removed from this
  transcript."
* Both exchanges were still on screen afterwards, which is the half of the claim
  a person would not think to check and the half that makes the control safe to
  offer (`fixed-306-summarise-up-to-here.png`).
* Marking the same point a second time answered "Everything up to that point is
  already summarised" rather than compacting again or failing.

### What it found

Nothing this round. The control was exercised on the path an owner takes and
behaved as the entry records it.

---

## 2026-08-28 — the last three lifecycle hook events, on four providers

**Tier: Targeted.** Chromium via Playwright at 1440 × 1000, light. **Providers:**
Anthropic (`claude-haiku-4-5-20251001`), OpenAI, OpenRouter, and local Ollama
(`gemma4:31b-cloud`). Every key was supplied to the runner as an environment
variable for the length of the round and entered through the product's own
Connect dialog; none was placed in source, a test fixture, or this document.
**Prefix:** `fixed-305-`.

### What it proved

* `Notification`, `PostToolBatch` and `InstructionsLoaded` appear in the
  Extensions → Hooks event catalogue, each tagged **Observes**, with no event in
  the catalogue marked **Never fires**
  (`fixed-305-lifecycle-event-catalogue.png`).
* A `config/hooks.json` naming `InstructionsLoaded` and `PostToolBatch` loaded on
  a running host, and both rules were reported as **Observes only** before any
  turn ran.
* One real tool-using Anthropic turn fired both events. The durable record
  carries `hook_matched`, `hook_executed` and `hook_decision` for each, under the
  turn's own id, with `no_decision` from the observing handler
  (`fixed-305-lifecycle-hooks-fired-on-a-real-turn.png`).
* The turn-end lifecycle event fired on a turn answered by each of Anthropic,
  OpenAI, OpenRouter and Ollama, on a workspace per provider matrix — so the
  lifecycle events are a property of the runtime rather than of one adapter.

### What it found

Two defects, both fixed in the same pass.

**Recent hook activity named neither the event nor the handler.** Every row read
as its verb and a relative time — "matched, just now" — which was legible while
the build emitted a handful of events and is not at twenty: an owner watching for
one rule could not tell whether the row that appeared was theirs. Both facts were
already in the payload the row is built from, so the row now carries them as a
label. Nothing is read from a hook's input or output, so the label cannot carry
the content those payloads deliberately exclude.

**A `fullPage` capture does not reach past the shell's own scroll container.**
The first two captures of this round were byte-identical because both showed the
top of the Hooks page, and the section each was named for was inside an inner
scroll area the capture never reached. A screenshot that does not contain the
thing it is named for is not evidence; the specs now scroll the section into view
before capturing. Other live specs passing `fullPage: true` against this shell
have the same limitation and are recorded in
[`TO_BE_FIXED.md`](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport).

Sign-in against a workspace an earlier spec had already configured failed twice
during this round, which is [BUG-229](TO_BE_FIXED.md#bug-229--most-live-specs-sign-in-only-on-an-empty-workspace)
behaving exactly as recorded rather than a new defect. Each spec was given its
own empty workspace.

---

## 2026-08-28 — channel routes, skill commands, and a complete responsive catalogue

**Tier: Full sweep plus targeted.** Chromium via Playwright. **Providers:**
Anthropic, OpenAI, OpenRouter, and local Ollama, using the credentials and model
selection already stored through Raiker's interface. No credential was placed in
source, a test fixture, or this document. **Prefixes:** mutable `pages/`,
`fixed-299-`, and refreshed `bug-225-` evidence.

### What it proved

* Every one of the 26 route/tab states rendered in light and dark at 390 × 844,
  1920 × 1080, 3840 × 2160, and 7680 × 4320: 208 captures, with no horizontal
  overflow, empty icon, off-screen selected tab, console error, or PNG dimension
  mismatch.
* Anthropic, OpenAI, OpenRouter, and Ollama were each opened on the appropriate
  Models tab and exercised with that provider card's **Test** control. Every card
  produced its own non-empty terminal result; the run did not infer provider
  health from a stored credential.
* A command was assigned to the shipped `algorithm-creator` skill through
  Extensions → Skills, appeared in both Chat and Build command menus, and was
  removed through the same owner surface after the assertion
  (`fixed-299-chat-skill-command.png`).
* Webhooks were paired with an allowlist, left off until a separate owner action,
  configured for **New turn** with an exact owner and approval-relay opt-in,
  exercised through the governed delivery path, then unpaired. The route and
  relay state remained visible on the closed card (`bug-225-channel-paired.png`).
* The Channels view fit at 390, 834, and 1440 pixels after the state badges were
  added; the refreshed page catalogue additionally proves it at the declared
  4K and 8K display classes.

### What it found

The approval-response endpoint initially shared authentication and exact-owner
binding with inbound messages but not their rate budget. It now uses the same
per-connector/per-sender limiter. Visual review also found that a saved route
became invisible when its editor closed; the connector card now keeps a quiet
route badge and, when enabled, an approval-relay badge. No open defect remains
from this round.

---

## 2026-08-25 — a semantic space built, measured, and found to be half a feature

**Tier: Targeted.** Chromium via Playwright at 1920, 1440, 1024, 768 and 390 CSS
pixels. **Providers:** Anthropic (`claude-haiku-4-5-20251001`, the turn),
OpenAI (`text-embedding-3-small`, the index), OpenRouter (417 models listed) and
Ollama (`gemma4:31b-cloud`, detected locally) — all four keys entered **through
the interface**, none in the process environment. `RAIKER_MODEL_EGRESS_ALLOWLIST`
carried the four hosts. **Prefix:** `r0825-`.

**Build:** the FIXED-283 … FIXED-288 change set, `apps/web` rebuilt, a **fresh
workspace** with the owner account created in-session, so every capability gate
started at its per-account fail-closed default.

### What it proved

* **A key entered in the interface reaches every path that needs it.** Anthropic
  answered with 10 models, OpenAI with 124, OpenRouter with 417, and Ollama
  reported the one model this device has pulled — from the setup wizard, with no
  environment variable for any of them (`r0825-workbench`).
* **A real governed turn, end to end.** *"Remember that my backup target is the
  encrypted NAS in the garage"* against live Haiku 4.5: the model proposed
  `memory_write`, the turn parked, the transcript showed the tool row *Save
  memory · global scope · waiting for your decision*, the Approvals queue held
  it at **high** risk attributed to `Raiker agent · turn_f3e0a…`, and the
  proposed arguments were shown redacted before the decision
  (`r0825-chat-turn`).
* **Semantic recall can now be built, and the owner is told what it costs.**
  With one approved memory, Memory → Recall backend offered **Build a
  meaning-based index…** listing seven embedding models — four llama.cpp slots
  and Ollama as *on this machine*, Gemini and OpenAI by provider — beside a
  button reading **Embed 1**. Confirming asked: *"Send the text of 1 approved
  memory to openai to be embedded as text-embedding-3-small? Memories marked
  secret-like or credential-like are never sent."*
  (`r0825-memory-index`, `r0825-memory-approved`.)
* **And the space it built is the space recall then selects.** The run returned
  `indexed_count: 1`, `embedding_model: openai:text-embedding-3-small`, 1536
  dimensions; `auto` resolved to it over the fallback, and the build control
  **disappeared**, because nothing was left to build (`r0825-memory-recall-state`). A second approved memory and a second run returned
  `indexed_count: 1` — only the new one — and a third refused with
  `no_memories_to_index`, so keeping the index current costs only what is new.
  **The card in those two screenshots reads "matches meaning", and that sentence
  was wrong**; see the first finding below.
* **Every page holds at every width tested.** All fifteen routes measured zero
  horizontal overflow at 390, 1024 and 1920. At 768 the shell collapses to a
  **Menu** control; at 390 to a bottom tab bar (`r0825-tasks-768`,
  `r0825-tasks-390`, `r0825-workbench-1920`, `r0825-memory-768`).
* **Every cadence is reachable from the page that plans work.** Tasks → Plan work
  offers **Task / Once / Routine / Background**, and Routine reveals **Repeat**
  (Keep going, Hourly, Daily, Weekly) and **First run** (`r0825-tasks-routine`).

### What it found

**The claim the round set out to prove, disproved by measuring it.** With the
space built and selected, retrieval was run directly against it:

```
'where should backups go'   -> []
'encrypted NAS'             -> [('mem_19c1146bc9', 3.0)]
'when do releases ship'     -> []
```

The one hit is the lexical leg matching shared words; the vector leg contributed
nothing. `_embed_query` drops it for a semantic backend unless a caller supplies
a `query_embedder`, and none does — so the **write** half of semantic recall
shipped and the **read** half was never connected. Two consequences, both taken
in this round:

* The Memory card was saying *"Searching … — matches meaning"* for a recall the
  runtime does not perform. It now distinguishes three states rather than two,
  and reads *"Stored in … Recall still matches words: a question is not embedded
  into this space yet."* Every surface that makes the claim reads
  `query_embedding_available()`, so the sentence tracks the behaviour.
* The read leg is raised as [BUG-240](TO_BE_FIXED.md) rather than fixed here. The
  shortest fix is a helper that calls the provider straight from the retrieval
  path, which is a second route into a governed action — the thing
  `GOVERNANCE_ENTRY_PATHS.md` exists to prevent. Embedding a query is provider
  egress, on a read path, once per search.

**This is the round's most useful result**, and it is worth naming why it was
nearly missed: every artefact a builder checks — the executor, the gate, the
threat model, the acceptance suite, the artifacts the run returned — said the
feature worked. Only running a query said otherwise.

**Three latent breakages in one capability that had never been run.**
`model_provider_runtime` was registered, gated, threat-modelled and
acceptance-tested, and nothing had ever invoked it. Its acceptance suite injects
an embedder — correctly, to exercise the governed persistence path — so nothing
had entered the function that does the real work. All three are in
[FIXED-283](FIXED_ITEMS.md): a registry loaded with a workspace root instead of a
config path, an `asyncio.run` inside the API's running event loop, and a provider
factory that saw only the process environment while the owner's key sat in the
vault. Each surfaced as `model_provider_error:…` or `provider_api_key_missing:…`
— reason codes that read like a provider fault for a bug that never left the
process.

**Three interface defects, all fixed in the round**
([FIXED-288](FIXED_ITEMS.md)):

* **"Turn on" beside "Turn off" on the same enabled capability.** After enabling
  *Provider embeddings*, its card offered both, and **Turn on** would have set
  the gate to the state it was already in (`r0825-cap-enabled`).
* **A permission list that could not be scanned for what is on.** The decision
  mode showed on every row whether the capability was on or off, and the on/off
  state was discoverable only by opening the card.
* **A successful readiness check titled "Repair model connection."** The dialog
  said *"Anthropic can reach claude-haiku-4-5-20251001"* and *"Check complete"*
  under a heading claiming something was broken (`r0825-readiness2`).

**Text removed from four surfaces**, and moved to the guide rather than deleted:
the Workbench's three standing board explanations, the Tasks composer's
paragraph, the Memory page's duplicate title and its repeated
memory-store-is-off sentence. Removing the Tasks paragraph also stopped the chip
row wrapping onto two lines at 1440 (`r0825-workbench`,
`r0825-workbench-trimmed`).

### Deliberately not covered

* **Retrieval *quality* on a real corpus.** Two memories are not a corpus, so
  nothing here measures how well a semantic space ranks. What the round measured
  instead is whether the vector leg contributes at all — and it does not, which
  is the finding above.
* **Gemini and the llama.cpp slots.** Offered and listed; only OpenAI was used to
  embed, and only Anthropic to run a turn.
* This was a **targeted** round. The last full sweep remains 2026-08-08.

---

## 2026-08-24 — what each switch decides, skills against a standard, and Auto's second check

**Tier:** targeted. **Providers:** Anthropic (`claude-haiku-4-5-20251001`),
connected through the product's own Connect dialog with
`RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` on the host. No other provider
was exercised. **Prefix:** `r0824-`.

**Build:** the FIXED-279 … FIXED-282 change set, `apps/web` rebuilt, a **fresh
workspace** at `/tmp/raiker-live` with the owner account created in-session, so
every capability gate started at its per-account fail-closed default.

### What it proved

* **A capability switch says whether it decides anything.** Permissions renders
  **GOVERNED ELSEWHERE** beside *Scheduled routines*, *Semantic memory*, *Plugin
  execution*, *Container execution* and *Multi-agent teams*, and **NO ROUTE YET**
  beside the nine with no path — *Plugin runtime*, *Plugin sandbox image pull*,
  *Plugin sandbox runtime*, *Reminders (local)* and the rest. Opening a marked
  card states what really governs the work: *"A scheduled task runs as one whole
  governed turn through the Agent Gateway, so every action inside it answers to
  that action's own gate and decision mode."* Shell, File writes and Subagents
  carry no tag, because their switches mean what they say
  (`r0824-gate-reality-governed-elsewhere`).
* **Delegation has a switch that is real.** `Subagents` reads as an ordinary
  capability rather than an inert one — `spawn_subagent` answers to it now.
* **Every shipped skill reports against the Agent Skills standard.** Extensions →
  Skills shows **STANDARD** on all six built-ins, and opening **Details** gives
  the *Agent Skills standard* block, a link to the published specification, and
  *"This skill matches the Agent Skills standard and should install in any tool
  that reads it."* (`r0824-skill-standard-conformance`.)
* **Auto states the promise it now keeps.** The composer's mode menu reads
  *"Approvals are granted for you, unless a change lands on a file this turn
  never looked at — then it waits."* Skip's line is unchanged
  (`r0824-auto-alignment-promise`).
* **Auto does not obstruct the work that was asked for.** Under Auto, with a real
  Haiku turn: creating `alignment-notes.md` ran unprompted, and so did changing
  the *existing* `ops/deploy.sh` when the prompt named it. This is the half that
  decides whether an owner leaves Auto switched on
  (`r0824-auto-aligned-write-ran`).
* **And it withholds when the turn established nothing.** In the *next* turn of
  the same conversation — *"Do exactly that again, with text repeated"* — the
  model repeated the write, Auto declined to grant it, and the file stayed
  `named`. The approval that appeared opens with *"Automatic approval was
  withheld: ops/deploy.sh already exists and this turn has not read, listed or
  been asked about it, so changing it is outside what you asked for."* above the
  ordinary notice, with the diff `-named +repeated`
  (`r0824-auto-withheld-approval`). **Establishment is scoped to the turn**, and
  this is what that looks like from the owner's side.

### What it found

**One UI defect, fixed in the round.** Rendering skill conformance as a `Badge`
put two pills side by side on every skill row — `► active` and `► standard` —
identical in glyph and tone and meaning nothing alike, because `active` is the
lifecycle badge for *"in flight"*. Conformance is a property of the document, not
a state, so it now renders as a quiet tag and escalates to a real badge only when
there is a portability issue to act on. Covered by
`apps/web/src/lib/skillConformance.test.ts::"keeps conformance a quiet tag unless
there is something to act on"`.

**One test defect, in this round's own spec.** The first version of the
withholding scenario instructed the model with `path "ops/deploy.sh"` in the
prompt — which *establishes* the path, so Auto correctly granted the write and
the spec asserted something impossible. The rule is not a bug; naming a file is
asking about it. Rewritten around turn scoping, which reproduces the
unestablished case deterministically with a real model. Recorded because a live
spec that asserts an impossible state is worse than no spec.

### Deliberately not covered

* **A model choosing an unrelated file on its own.** No prompt that instructs a
  write can also be the unestablished case, and a live spec that waits for a
  model to volunteer one would be flaky. That shape is proven deterministically
  at the broker level instead —
  `tests/test_model_tool_call_loop.py::test_auto_withholds_a_write_to_an_existing_file_the_turn_never_looked_at`.
* **The other providers.** Only Anthropic was connected on this host.
* This was a **targeted** round. The last full sweep remains 2026-08-08.

---

## 2026-09-03 — the last surface that was not local, and a console that stays quiet

**Tier: targeted, plus a measured responsive sweep.**
Anthropic, connected through Models in the running app. Workspace: a fresh
instance, reset with `scripts/reset_live_workspace.py` rather than `rm -rf` —
the first round to use the checked reset it was closed with.

### What it verified

* **Dictation can run with nothing leaving the machine.** A transcription server
  on loopback, configured on **Models → Local** beside the other local runtimes
  and proved by asking it to transcribe generated silence. With a fake capture
  device, the browser recorded, converted to 16 kHz mono WAV in the page, posted
  the clip to Raiker, and the words arrived in the Chat draft from a service
  Raiker reaches only because the owner pointed it there
  (`bug-256-speech-runtime-models`, `bug-256-dictated-on-device`).
* **The interface says which runtime is in use, and asks nothing.** The note
  under the microphone reads "transcribed by the speech runtime on this machine"
  once a runtime is set up, in place of the sentence that always assumed the
  browser. The round's first cut carried a three-way selector in a Settings
  section; it was removed as one decision too many, and the evidence recaptured.
* **An address that is not on this machine is refused where it is typed** — a
  hosted host and a private-network one both answered `speech_endpoint_not_local`
  before anything was contacted.
* **A locked load refuses nothing.** Every response before sign-in was watched:
  no `401`, no console error. That is BUG-267's outcome stated as an assertion
  rather than as an absence somebody has to notice.
* **Every page, at four widths, in both themes.** The canonical sweep —
  `ui-sweep-responsive-live.spec.ts` — over 27 route/tab states at 390, 1920,
  3840 and 7680 in light and dark: no horizontal overflow, no icon rendering
  without a glyph, no selected tab scrolled off its own strip, no control under
  WCAG 2.2's 24px target, and no console error, across all eight passes. The
  catalogue in [`screenshots/pages/`](screenshots/pages) was re-captured in full.

### What it found

**The microphone could never have worked in a served build.**
`SecurityHeadersMiddleware` sent `Permissions-Policy: microphone=()`, and the web
UI is served by the same app, so the header landed on the document carrying the
control. A bare `()` denies the feature to *every* origin, including this one.
Every previous voice round drove a Playwright recognition adapter injected into
the page, which is why none of them touched the real capture path and none of
them saw it. Closed in the round as
[FIXED-363](FIXED_ITEMS.md#fixed-363--dictation-was-the-last-surface-that-was-not-local);
the header is now `microphone=(self)`.

**A control under the minimum touch target, in the section this round added.**
The Voice radios measured 13x24 on a phone. The sweep found it the same way it
found FIXED-318: by measuring, because nothing about it looked wrong. The cause
was a full-width rule meant for the address field, and then an `auto` that
overrode the shell's own control sizing while undoing it.

**Two more, both closed here:**

* The Models speech row adopted its stored address unconditionally, so an owner
  typing before the read resolved lost what they had typed — FIXED-85's defect in
  a new place, found because the spec types faster than a person.
* `#/settings?tab=updates` had always opened General. BUG-215 added a guard for
  exactly that, but it compared the rail against a hand-copied third list which
  carried the same omission. The rail now lives in one module and the guard reads
  it.

## 2026-08-30 — the repository on screen, an honest gate, a citation that opens

**Tier: targeted, plus the first *measured* responsive sweep.**
Anthropic `claude-haiku-4-5-20251001`, connected through Models in the running
app. Workspace: a fresh instance, then the same instance again with the work its
own first run had created.

### What it verified

* **Build shows the repository it is changing.** **Files** on the Build header
  opens the connected `demo-repo` beside the conversation. `src` is not walked
  until it is expanded — asserted by counting the browse calls, not by looking —
  and opening `src/main.py` renders it highlighted with **PYTHON** on the header.
  **@** put `@src/main.py` into the composer. `logo.png` answered *"This file is
  not text, so there is nothing to show here."* rather than an empty pane. At
  390px the same panel arrived as a dialog from the left
  (`b13-build-file-explorer`, `b13-build-file-explorer-narrow`).
* **Permissions stopped saying Off about a capability that would have run.**
  *Web fetch* reads **ON BY DEFAULT** on a fresh account, its card explains that
  an empty table on a new install is not a refusal, and its only action is
  **Turn off**. *Shell commands* still reads **OFF** and still offers **Turn
  on** — the ordinary case is untouched (`bug-239-unset-gate-honesty`).
* **A cited past conversation opens the exchange it names.** On a real Haiku
  turn: a first chat recorded a fact, a second chat searched for it, and the
  **Past conversations** chip listed the exchanges it returned as links. Each
  `href` carried `session=` *and* `turn=`; following one landed on that exchange
  with the anchor mark (`bug-245-cited-exchanges`).
* **Every route, at three widths, measured.** All 26 routes at 390, 1024 and
  1440, asserting that nothing reaches past the window that nothing scrolls or
  clips on purpose — and zero uncaught console errors across all 78 loads.

### What it found

**Three responsive defects that several previous rounds photographed and did not
see**, all closed in the round as
[FIXED-325](FIXED_ITEMS.md#fixed-325--a-phone-was-clipping-the-models-page-and-the-knowledge-map-never-resized):

* **Models clipped its own body text at 390.** *"Simple local model service for
  Windows, macO…"* — a grid column left at `auto` was sized by one unwrappable
  descendant to 416px inside a 366px page, and every sibling stretched to match.
* **The Knowledge Map canvas never resized.** Its `ResizeObserver` attached in
  `onMount` to an element that only exists on the `{:else}` branch of a load
  state, so it observed nothing and never ran again. The canvas stayed 900px
  wide on every window.
* **"Fit" did not fit.** It reset the transform to the identity and then
  re-agitated the layout it had just measured.

**And two more found while verifying the work above.** Connecting the first
repository did not select it, so Build sat on *No repository* afterwards; and the
Build header's two toggles carried their label only in a `<span>` the narrow
layout hides, so below the split neither button had an accessible name. Both are
recorded in
[FIXED-321](FIXED_ITEMS.md#fixed-321--build-could-change-a-repository-and-never-show-it).

**The lesson.** The sweep that missed all three was a set of screenshots somebody
had to look at. It is a measurement now
(`apps/web/e2e/ui-sweep-clipping-live.spec.ts`), and the three defects are its
first three assertions.

---

## 2026-08-23 — the rewind, the audit export, and two defects the rewind exposed

**Tier:** targeted. **Providers:** Anthropic (`claude-sonnet-5`), OpenAI
(`gpt-4`), OpenRouter (`nvidia/nemotron-3.5-lightning:free`) — all three
confirmed reachable in-session. Ollama Cloud was **not connected** on this
machine and was not exercised. **Prefix:** `r0823-`.

**Build:** `main` at the FIXED-270 … FIXED-276 change set, `apps/web` rebuilt,
`raiker-web --workspace . --port 8765`, signed in as the existing owner account
*Rahul* — an account created before any of this work, with every capability gate
still at its per-account fail-closed default.

### What it proved

* **The rewind is reachable, and it is a request.** Observability → Checkpoints →
  *Preview restore impact* named the one file a restore would rewrite;
  acknowledging and pressing **Request this restore** answered *"Raised as
  approval appr_830aa…. Nothing has changed yet."* and the file on disk was still
  the agent's version. Approving it in Approvals put `live-rewind-probe.txt` back
  to `original contents before the rewind`. The restore's own pre-image was
  captured, so the rewind is itself rewindable. (`r0823-bug230-restore-preflight`,
  `r0823-bug230-preflight-with-files`, `r0823-bug230-restore-approval`.)
* **The approval for a restore reads as a restore.** The detail pane carried the
  restore-specific notice — *"The restore captures its own pre-image first, so it
  appears as a new checkpoint"* — and the per-file plan, recomputed server-side,
  rather than the file-mutation wording.
* **The audit log leaves the product.** Observability → Audit log → **Export**
  produced 271 events as a redacted JSONL, downloaded it, and listed it with its
  manifest hash. The export appears in the log it exported, as *"Action executed
  — Exported 271 audit events (2026-08-19T11:40:27Z → 2026-08-23T16:35:07Z),
  redacted."* Spot-checked: 24 redactions in the file, and no `sk-` string.
  (`r0823-bug231-audit-export`.)
* **A restart no longer asks for a model that is already set up.** With every
  stored observation aged three hours and the server restarted, Chat opens with
  no strip, **Send** enabled, and a real answer from the provider — the server
  re-takes the aged-out observation while admitting the turn. Marking the
  selected model `authentication_failed` brings the prompt straight back, naming
  the credential rather than the expiry
  (`r0823-bug238-unavailable-still-prompts`).
* **The MCP revision is current, and the card says so.** A server built from the
  bundled echo template, connected over a real stdio session, reports
  **PROTOCOL 2026-07-28** on its card — the template answers the handshake, and
  the negotiated revision is what is shown, not what Raiker offered
  (`r0823-bug234-mcp-protocol`).
* **`network_execution` is gone from Permissions.** The Network group now lists
  Web fetch, Git push, External channels and Channel approval relay, and nothing
  else. Web fetch's description states the guard that actually applies.
* **Every governed step still failed closed first.** On an account with the
  gates at their defaults, the export returned `403` until `audit_export` was
  turned on, and enabling `hosted_model_runtime` required a threat-model
  acknowledgement *and* a typed confirmation token. Both refusals are correct
  behaviour and were re-confirmed here rather than assumed.
* **Responsive.** Fourteen routes at 390 × 844 with **zero** horizontal overflow
  on any of them, including the new export panel, which wraps rather than
  clipping (`r0823-mobile-audit-export`).
* **Every route at 1440 × 900, re-swept after each fix.** Twenty-one routes,
  checked for horizontal overflow and for `NaN`, `undefined`, `[object Object]`,
  `[REDACTED_SE…` and load errors in the rendered text. The final sweep is clean;
  the sweep before it is what found the third redaction defect.

### What it found

Four defects, all raised and closed in the same round. Three were **only
observable because the rewind was finally routed**; the fourth was hit simply by
using the product across restarts:

* **BUG-235 → [FIXED-275](FIXED_ITEMS.md).** A file write approved from the
  inbox filed its pre-image under the *API session* that resolved the approval,
  while the checkpoints it must be restorable from belong to the *chat*. Every
  restore plan for that conversation reported zero files. The blob existed and
  nothing could reach it — which is the same shape as BUG-230 itself, one layer
  down, and is why nobody had found it: without a caller for the restore, no plan
  was ever acted on.
* **BUG-238 → [FIXED-278](FIXED_ITEMS.md).** Hit three times while trying to
  send anything at all: after a restart — and after any five idle minutes — the
  composer said *"The last model check has expired"*, offered **Set up model**,
  and disabled **Send**, for a model that was connected and working. The
  readiness TTL, which exists to bound how *old* an observation may be, was also
  deciding whether the model was **configured**. Staleness is not
  unavailability.
* **BUG-237 → [FIXED-277](FIXED_ITEMS.md).** Exercising the *terminal* half of
  the rewind found that `/checkpoints restore <id>` dies with
  `UnicodeEncodeError` when its output is redirected under a legacy Windows code
  page — the preflight prints an empty-set sign for a file with no pre-image, and
  nothing reconfigured the stream. `raiker … > out.txt` was a different program
  than `raiker …`.
* **BUG-236 → [FIXED-276](FIXED_ITEMS.md).** The export list rendered every
  manifest hash as `[REDACTED_SE…`. The response redactor's high-entropy fallback
  ate the 64-hex digest, so the one field that makes an export verifiable outside
  Raiker could not be read.

### What it did not cover

* **Ollama** — not connected on this host; the local-runtime path was not
  exercised.
* **A cross-principal restore** — a single-owner instance has no second principal
  to overwrite, so the critical path was verified by classification test rather
  than live.
* **An oversize file mutation** — the >8 MiB approval notice was verified by
  test, not by writing an 8 MiB file through a live turn.
* This was a **targeted** round. The last full sweep remains 2026-08-08.

---

## 2026-08-22 — hooks, plugin contributions, channels, the fourth approval mode

**Tier:** targeted. **Providers:** Anthropic, OpenAI, OpenRouter, Ollama.
**Prefixes:** `bug-219-`, `bug-221-`, `bug-223-`, `bug-225-`.

> **Reconstructed from committed evidence, 2026-08-23.** This round was run and
> its screenshots and `FIXED-*` entries were committed, but it was never written
> up here — the plan's last recorded round was 2026-08-15. What follows is read
> from the evidence and the closure entries, not transcribed from a live session.
> Treat the screenshot filenames and the `FIXED-*` entries as authoritative and
> this summary as an index to them.

| Area | Evidence | Closed as |
|---|---|---|
| Turn-end hooks fire on every backend, not just the one that was tested | `bug-223-stop-anthropic.png`, `bug-223-stop-openai.png`, `bug-223-stop-openrouter.png`, `bug-223-stop-ollama.png`, `bug-223-stop-fired-on-a-real-turn.png` | [FIXED-255](FIXED_ITEMS.md#fixed-255--seven-lifecycle-events-were-specified-and-never-emitted) |
| The hook event catalogue the tab publishes | `bug-223-hook-event-catalogue.png` | FIXED-253, FIXED-255 |
| A plugin contributes a skill, and it arrives switched off | `bug-221-plugin-skill-inactive.png`, `bug-221-live-skill-in-turn.png`, and desktop/tablet/mobile at `bug-221-plugin-skill-*.png` | FIXED-259 |
| A plugin offers an MCP server, and an offer is not a server | `bug-221-plugin-mcp-offer.png` | FIXED-260 |
| What a plugin may contribute, stated as three kinds | `bug-221-contribution-kinds-three.png`, `bug-221-plugin-contribution-kinds.png`, `bug-221-plugin-contributed-rules.png` | FIXED-256, FIXED-259, FIXED-260 |
| Hooks and Plugins tabs at three widths | `bug-221-223-hooks-{desktop,tablet,mobile}.png`, `bug-221-223-plugins-{desktop,tablet,mobile}.png` | FIXED-257 |
| Channels gain an owner surface: paired, and the four facts shown as four things | `bug-225-channel-surface.png`, `bug-225-channel-paired.png`, `bug-225-channel-contract.png`, `bug-225-channel-delivery-refused.png` | FIXED-261, FIXED-265 |
| Channels tab at three widths | `bug-225-channels-{desktop,tablet,mobile}.png` | FIXED-265 |
| The fourth approval mode — *Decline, don't ask* | `bug-219-approval-modes.png`, `bug-219-approval-modes-mobile.png` | FIXED-262, FIXED-263 |
| A live model was ready for the turns above | `bug-221-live-anthropic-ready.png` | — |

Also closed in this round without a manual screenshot: FIXED-254 (the owner off
switch for hooks), FIXED-258 (web tests on a current Node), FIXED-264 (a live
spec's sign-in), FIXED-266 (a redacted boolean), FIXED-267 (a bounded channel
sender), FIXED-268 (signing outbound deliveries).

---

## 2026-08-21 — governed voice, Build modes and protocol, the Hooks tab

**Tier:** targeted. **Provider:** Anthropic.
**Prefixes:** `r0821b-`, `r0821c-`, `2026-08-21-`.

> **Reconstructed from committed evidence, 2026-08-23**, on the same basis as the
> round above.

| Area | Evidence | Closed as |
|---|---|---|
| Chat and Build composers at 375 px, and Build at 768 px | `r0821b-01-chat-composer-375.png`, `r0821b-02-build-composer-375.png`, `r0821b-07-build-composer-768.png` | FIXED-250 |
| Build opens in **Auto**, the mode that overrides nothing | `r0821b-03-build-auto-default.png` | FIXED-248 |
| The Build mode menu | `r0821b-04-build-mode-menu.png` | FIXED-248, FIXED-250 |
| `/schedule` from the composer | `r0821b-05-schedule-command.png` | FIXED-250 |
| The Build operating protocol, live, and the record of which one ran | `r0821b-06-build-operating-protocol-live.png` | FIXED-251 |
| The Hooks tab: rules, the events it dispatches, and recent activity | `r0821c-01-hooks-tab.png`, `r0821c-02-hooks-events-and-activity.png` | FIXED-253 |
| A hooks file that does not parse is named and survived | `r0821c-03-hooks-broken-config.png` | FIXED-252 |
| Hooks turned off, with the rules still listed | `r0821c-06-hooks-turned-off.png` | FIXED-254 |
| Hooks tab at 375 px and 768 px | `r0821c-04-hooks-375.png`, `r0821c-05-hooks-768.png` | FIXED-257 |
| Memory at 375 px and 768 px; Knowledge Map, Diagnostics and Runtime at width | `2026-08-21-memory-375.png`, `2026-08-21-memory-768.png`, `2026-08-21-brain-1440.png`, `2026-08-21-diagnostics-1440.png`, `2026-08-21-runtime-1024-full.png` | FIXED-242, FIXED-245, FIXED-257 |

Voice was closed the same day as FIXED-247 (governed input rather than labels)
and FIXED-249 (dictation stops when the owner leaves the page); its evidence is
in the `voice-*` Playwright output rather than under `screenshots/working/`.

---

## 2026-08-15 — Native OS sandbox round
The round that closed the OS-boundary half of BUG-194 as **FIXED-195**. Run
against the production web build on Windows 11, with all four providers
connected **through the Models dialog**, never through the CLI.

The question this round exists to answer: **is the boundary real, and does
Raiker only claim what it measured?**

| # | Step | Expected | Result |
|---|---|---|---|
| 24.1 | Register a fresh owner, take Balanced through setup, open the dashboard | Lock screen, then the dashboard mounts | ✅ |
| 24.2 | Settings → **Runtime configuration** | **Native OS sandbox** is listed with `AppContainer · network denied` and six observations | ✅ `r0815-runtime-native-sandbox-observations.png` |
| 24.3 | Read the six observations | Command output reaches Raiker / can write inside the workspace / cannot write outside it / cannot read Raiker's own state / cannot reach the network / stopping ends every descendant — all **Enforced** | ✅ `r0815-native-sandbox-card.png` |
| 24.4 | Read what the card says it does *not* do | "Foreground commands only. PTY, background execution, network grants and persistence are not built for this boundary and are not offered." | ✅ |
| 24.5 | Read the re-measure disclosure | "Re-measuring opens one connection to this host's default gateway on a closed port." | ✅ |
| 24.6 | **Select** the native sandbox | The card reads **Selected**; `execution_environment_selection` records `native_sandbox` | ✅ |
| 24.7 | Permissions → enable **Shell commands** and **Approval execution relay**, each with a reason and a confirmation token | Both gates record `enabled_runtime` against the principal | ✅ |
| 24.8 | Models → Hosted → **Connect** Anthropic, OpenRouter and OpenAI, pasting each key in the dialog; **Test** each | Each card reads **Connected**, then "«provider» can reach «model»" | ✅ |
| 24.9 | Build → send "Use the shell tool to run exactly: `git --version`" | The turn proposes a `shell` action and parks: "Waiting for your decision. Nothing has run yet." | ✅ |
| 24.10 | **Accept** | The command runs inside a per-run AppContainer; `git version 2.55.0.windows.4` comes back through the relay; the model answers from it | ✅ `r0815-build-governed-terminal-appcontainer.png` |
| 24.11 | Read the governed terminal | `AppContainer · network denied` · "OS boundary · foreground only · no PTY, background or network grant" · the output · **Immutable receipt** with outcome, exit, isolation and authority | ✅ |
| 24.12 | Repeat 24.9–24.10 with **OpenRouter** (Gemini 3.7 Flash), **OpenAI** (GPT-4o Mini) and **Ollama** (gemma4:31b-cloud) | Each provider drives the same path to the same executed command | ✅ six `succeeded` runs in `command_runs` |
| 24.13 | Run `echo x > ..\escape.txt` through the runner directly | **"Access is denied."** from the OS, exit 1 — not a policy refusal | ✅ |
| 24.14 | Run `dir .raiker` through the runner directly | **"Access is denied."** from the OS | ✅ |
| 24.15 | Read the receipt evidence for a completed run | `boundary_constructed` names this run's profile, `network_capability: false`, the protected paths and the runner digest; `probe_observations` carries the six host measurements **and** the time they were taken | ✅ |

> 24.13 and 24.14 are the steps that separate this from the argv policy. The
> allowlist would refuse those commands anyway; running them through the runner
> directly is what shows the *operating system* refusing them.

**Result: passed, after two defects this round found and fixed.** Every
sandboxed command initially failed with `native_sandbox_launch_failed:203` while
the same command run by hand succeeded: an AppContainer is created with a
redirected local profile and `CreateProcessW` resolves it from the environment
block, which Raiker's deliberately minimal environment did not carry. And
`portable_command` rewrote `echo` into the interpreter Raiker itself runs on,
which lives outside the boundary, so the child died with `STATUS_DLL_NOT_FOUND`
— an exit code rather than an error. Both are in **FIXED-195**.

One defect found and **not** fixed this round: every turn rendered
**"The turn could not continue (409)."** beneath its own successful answer, in
all four provider rounds. Filed as **BUG-196**.
---

## 2026-08-11 — Memory recall round
The round that verified [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md)
MEM-01 and MEM-02, closed as FIXED-187 through FIXED-189. Run against the
production web build with Anthropic connected through the Models dialog.

The question this round exists to answer is the one memory is actually asked:
**can Raiker pick up a conversation from years ago and quote it exactly?**

| # | Step | Expected | Result |
|---|---|---|---|
| 23.1 | Register a fresh owner, take the Anthropic path through setup, finish the wizard | Lock screen, then the dashboard mounts; 0 console errors | ✅ `r0811b-01-lock-screen.png`, `r0811b-04-setup-complete.png` |
| 23.2 | Models → Hosted → **Connect** on Anthropic; paste the key in the dialog | Card reads **Connected**; the field is masked and the key is never echoed | ✅ `r0811b-05-models-hosted.png`, `r0811b-06-connect-dialog.png`, `r0811b-07-anthropic-connected.png` |
| 23.3 | **Choose model…**, pick a model from the live catalogue, **Use model** | The catalogue is the provider's own list | ✅ `r0811b-08-model-picker.png` |
| 23.4 | **Test** on the Anthropic card | "1 model ready · Anthropic can reach `claude-haiku-4-5-20251001`" | ✅ `r0811b-09-model-readiness.png` |
| 23.5 | In a new chat, state a fact worth recalling (a host name and an interval) and ask for a one-word acknowledgement | A live streamed turn; the reply is stored as the conversation record | ✅ `r0811b-11-chat-first-turn.png` |
| 23.6 | In a **separate** chat, ask what was said earlier and require a citation | The turn calls `conversation_search`, quotes the sentence **verbatim**, and cites the conversation, its date and its id | ✅ `r0811b-12-recall-across-chats.png` |
| 23.7 | Seed a conversation dated **three or four years back**, then ask about it with a period in the question ("back in 2022", "before 2023") | The turn narrows by date, finds the old conversation, and returns the exact figure, the quoted sentence, the date and the stated reason | ✅ `r0811b-13-recall-2022-conversation.png` |
| 23.8 | Search Chat for a term that appears only in a message body | Each result shows the exchange that matched beneath its title, and an old conversation is grouped under its own date | ✅ `r0811b-14-search-chat.png` |
| 23.9 | Turn **Incognito** on and repeat 23.6 | No recall item is assembled at all — the opt-out is absolute, ahead of every recall path | — written for the next round |
| 23.10 | Sign in as a second local principal and search for the first's conversation | Nothing is returned; the index narrows candidates, `sessions.user_id` still decides visibility | Covered by `test_another_owner_never_sees_the_conversation` |

> 23.6 is the step that distinguishes recall from a long context window. Start a
> genuinely separate conversation — not a new turn in the same one — or the model
> can answer from history it still has.

**Result: passed.** The first pass of 23.6 found the right conversation and still
could not answer, because the tool returned the index's own ~18-token snippet and
the model was handed "…we rotate the SQLCipher key every…". That is **FIXED-189**,
fixed and re-run in the same round; the regression test is written from the live
transcript. 23.7 then recalled an 18 April 2022 conversation with the exact
retention window, the verbatim sentence, the date and the reason.

---
---

## 2026-08-11 — Multi-provider usage and compaction round
Run against the production web build. Enter every credential through Models;
never seed a connection through the CLI, environment, fixture, or direct API.
Close credential and connection dialogs before taking screenshots. Use a fresh
conversation per provider so provider attribution and model readiness are
unambiguous.

1. Run the checked-in loopback fixture and both deterministic batch specs.
   Confirm the refusal scenario renders successive model passes as separate
   paragraphs, and both specs use `e2e/fixtures/stub_model.py`.
2. Connect Anthropic in Models, choose a live catalog model, complete readiness,
   and send a bounded marker prompt in Chat.
3. Connect OpenRouter the same way and complete a live turn. Refresh Models →
   Activity and verify the **Provider reported** key-level weekly metric appears
   separately from **Raiker observed**.
4. Connect OpenAI through Models and complete a live turn. Without a separate
   organization admin key, verify provider data says it needs one rather than
   presenting an invented quota.
5. Select and check Ollama `gemma4:31b-cloud`, then complete a live turn. Verify
   the provider side says no compatible account-quota API while Raiker-observed
   local tokens and turns remain present with no API cost.
6. Disconnect or stop one provider and verify a provider that is no longer
   connected/ready is absent from the rolling view.
7. Set an owner weekly token budget in each visible row. Confirm its label says
   **Advisory Raiker control — not a provider subscription limit**, survives a
   reload, and can be cleared.
8. Exercise a known small owner context capacity in the deterministic runtime.
   Confirm the extra compaction model request has no tools, the next turn sees
   the compacted summary plus recent exchanges, and the Context popover says the
   transcript is unchanged. Repeat with a failed compaction and confirm bounded
   recent history is retained.
9. Capture provider and Context screenshots only after all credential dialogs
   are closed. Inspect the committed image set for key-shaped strings before
   keeping it.

The automated evidence for this round includes the compaction, usage adapter,
ledger/API, Svelte component, checked-in fixture, and live Playwright suites.

**Result: deterministic and local-provider paths passed; hosted execution was
environment-blocked.** The checked-in stub scenarios passed against the real
FastAPI runtime, including the two-paragraph multi-call answer assertion. All
four requested connections were entered through Models with the connection
dialogs closed before capture. Anthropic, OpenAI, and OpenRouter then failed
closed as **Unreachable** because this managed run could not grant the server
outbound network access; no hosted response is represented as a live turn.
OpenRouter's ordinary-key usage request therefore reports temporarily
unavailable, while Anthropic and OpenAI correctly request separate organization
admin credentials instead of inventing account limits.

Ollama `gemma4:31b-cloud` passed exact-model readiness and returned both bounded
markers in Chat. Its streamed OpenAI-compatible response exposed a live defect:
the request omitted `stream_options.include_usage`, so the first turn did not
reach the ledger. The adapter now requests those metrics for Ollama streams;
the repeated turn recorded **5,405 tokens, 1 turn, 1 model request**, with **No
API cost — local runtime**. All four connected rows accepted owner weekly token
budgets and retained them after a server restart. The same restart exposed and
closed a second defect: placeholder-provider cards now retain each configured
model instead of showing `no model pinned` whenever another provider is the
global selection. A compact 900 px pass also fixed the tablet Menu/title
overlap and finished with no horizontal overflow.

Screenshots: `bug-52-chat-refusal-does-not-end-the-turn.png`,
`round0811-ollama-live-turn.png`,
`round0811-hosted-provider-readiness.png`,
`round0811-provider-usage-connected.png`, and
`round0811-provider-usage-compact.png` in
[`screenshots/working/`](screenshots/working). Every retained image was reviewed
after dialogs closed; none contains a credential value.


---
---

## 2026-08-10 — Known-limits round
Run against a fresh isolated workspace (`/tmp/raiker-live`), the production web
build, and one hosted provider credential entered through Models only. The
credential is absent from screenshots, source, and logs committed here.

Automated as `apps/web/e2e/bug-74-84-known-limits-live.spec.ts` and
`apps/web/e2e/containment-surface-live.spec.ts`, both re-runnable against an
already-driven workspace.

1. Register a fresh owner. Confirm the model setup prompt opens, then skip it.
2. Visit every code-split destination — Search Chat, Memory, Approvals, Tasks,
   Knowledge Map, Projects, Permissions, Models, Extensions, Observability,
   Settings — and confirm each mounts with content and no console error.
   *(FIXED-161.)*
3. Extensions → Plugins. Confirm the workspace signing posture is stated in
   words, names the two environment variables that would raise it, and says
   installs are unaffected. *(FIXED-166.)*
4. Settings → Security & sign-in → **Monitored capabilities**. Confirm the
   section explains that every capability family is watched the same way
   monitored MCP connections are, and that an empty workspace says so rather
   than showing nothing. *(FIXED-163, FIXED-164.)*
5. Settings → Runtime configuration → **How long a model check stays good for**.
   Confirm the default reads 5, change it to 30, **Save changes**, navigate away
   and back, and confirm 30 survives the round trip. *(FIXED-169.)*
6. Models → Activity. Confirm the durable operations surface loads and states
   that failed work is never silently retried. *(FIXED-162.)*
7. Models → Hosted. Connect Anthropic through the UI, pin a model from the live
   catalogue, and press **Test**. Confirm the card reaches
   `Ready · confirmed just now` and names the exact model it reached.
   *(FIXED-133, FIXED-169.)*
8. Chat. Send one bounded prompt and confirm the model answers with the exact
   requested marker. *(FIXED-133.)*
9. Record three consecutive failures for one connector through the same
   `CapabilityBreaker` the runtime uses (the command is in the spec's header —
   a browser cannot make a healthy provider fail on demand). Reload Settings →
   Security & sign-in and confirm the subject is listed as **paused** with its
   stated reason, its failure count and its last failure code, that a matching
   high-severity finding appears above it, and that **Resume** returns it to
   active in one press. *(FIXED-163, FIXED-164.)*

**Result: ✅ eleven entries closed** — FIXED-133 re-verified and FIXED-161
through FIXED-170. Screenshots: `round0810-01-first-run-model-setup.png` through
`round0810-11-containment-resumed.png` in
[`screenshots/working/`](screenshots/working). The production build reports no
chunk-size warning: the entry chunk is 237 kB against the previous 690 kB, and
the largest route chunk is Models at 82 kB.
---

## 2026-09-04 (fifth) — Two lines the owner asked to lose, and what one of them was actually saying

**Tier: targeted + measured four-width sweep.** Production web build, the same
workspace the third and fourth rounds used, signed in as the existing owner. Both
items came from the owner in one sentence each.

**What it proved.**

1. **Models → Hosted carries no pinning placeholder.** Eight cards, none of them
   reading *"no model pinned"*, and the local rows no longer read *"model chosen
   at selection"*. Each card still states its connection, its readiness chip, and
   **Select models…**; a card with a chosen model still names it. Guarded from
   both directions in `ModelsView.test.ts` — neither placeholder anywhere on the
   tab, **Haiku 4.5** still on the connected card, and exactly one `.pc-model`
   element for two profiles. Closed as
   [FIXED-396](FIXED_ITEMS.md#fixed-396--eight-provider-cards-printed-the-same-placeholder-about-pinning).
2. **Nothing in Observability claims a capability is disabled.** The overview
   reads *Ready*, *49 closed capability gates* with "18 more have no executor and
   stay closed", and one missing-configuration item — each linking to where the
   owner acts. Closed as
   [FIXED-397](FIXED_ITEMS.md#fixed-397--a-chip-list-of-disabled-capabilities-that-named-the-page-it-was-drawn-on).
3. **Every route still fits at 390, 768, 1280 and 1920** after the card layout
   lost a row — `ui-sweep-widths-live.spec.ts` green in 1.1 minutes.

**What it found, and it is the more useful half.** The Observability card was
asked to be removed for information-architecture reasons; reading what it
rendered made it a truthfulness defect. It printed
`phase_gates.list_disabled_capabilities()` — the *shipped registry's* build-out
flags, fourteen entries including `dashboard` and `web_ui`. It was telling an
owner, in the dashboard, in a browser, that the dashboard and the web UI were
disabled. It was never showing the deferred domains its heading implied, which
are a different set arrived at a different way. Both facts now live in
[Capabilities with no enable path](../guide/permissions-and-runtime-modes.md#capabilities-with-no-enable-path),
which names the deferred domains, enumerates the fourteen phase gates by phase,
says what a phase gate is *not*, and points at `/capabilities` for the live set.
Four guide pages that pointed at the removed card were corrected in the same
edit.

**Screenshots:** `round0904-models-hosted-no-pinning-placeholder.png` and
`round0904-observe-overview-no-disabled-chips.png` in
[`screenshots/working/`](screenshots/working). No dialog was open in either and
neither contains a credential value.

---

## 2026-09-04 (fourth) — Two tabs that were copies, and three bleeds an empty page hid

**Tier: targeted + measured four-width sweep.** Production web build, the same
workspace the third round used — which is the whole reason this round found
anything.

**What it proved.**

1. **Every route still fits at 390, 768, 1280 and 1920**, and every page renders,
   after two hub tabs were folded away. `#/models?tab=posture` opens Hosted,
   `#/diagnostics` and `#/observe?tab=diagnostics` open Overview; `nav.test.ts`
   asserts each, so a bookmark that named either lands on the panel that owns its
   content rather than on the hub's first tab.
2. **Four read-only facts read above the cards they explain.** The off-machine
   posture is a strip at the top of Models → Hosted, where it answers *why did
   this provider refuse*, instead of a tab of its own one click away.
3. **Observability lost a tab and kept everything it said.** *Is the runtime
   itself healthy?* carries the health transitions, the memory integrity report
   and its Rescan; the four cards that restated Overview's own tiles are gone.

**What it found, and it is the more useful half.** The width sweep had passed
that morning and failed that afternoon at 390px. Stashing every source change and
rebuilding reproduced it identically on unmodified `main` — so it was never the
day's work. Three genuine mobile bleeds, each needing *content* to exist:

* seven controls on an approved memory in a flex row that could not wrap
  (511px in a 366px card);
* a `<select>` claiming the width of its longest option inside a label that was
  allowed to shrink;
* a `display:grid` whose implicit `auto` column sized to max-content and refused
  to shrink below it, plus a `minmax(300px, 1fr)` with a hard floor.

The morning run had none of them because the workspace had no memory and no
indexed model. **A responsive check against an empty page is a check of the empty
state.** That is the layer under [BUG-250](TO_BE_FIXED.md#bug-250--a-shared-live-workspace-carries-state-between-specs):
not that a spec can re-run against a used workspace, but that running against one
finds what an empty one hides. Closed as
[FIXED-395](FIXED_ITEMS.md#fixed-395--three-mobile-bleeds-that-only-existed-once-the-workspace-held-anything).

---

## 2026-09-04 (third) — A wire with a clock, and three defects found by using the product

**Tier: targeted + measured four-width sweep + full page sweep.** Production web
build, a fresh workspace, and one provider: Anthropic, with a third
**identity-linked** key entered through the Connect dialog. No key appears in
this repository.

**What it proved.**

1. **A collector delivered to on a cadence, without anybody pressing a button.**
   A destination was added through **Observability → Overview**, put on **Hourly**
   through the select on its own card, and the card then read *"Next in 58m"*.
   Setting it back to **On demand only** cleared the claim. The interface outcome
   [BUG-276](TO_BE_FIXED.md#bug-276--governed-events-only-leave-when-somebody-presses-a-button)
   required is met: the card states which of the two it is on, always. Evidence:
   `bug-276-delivery-cadence.png`. Closed as
   [FIXED-386](FIXED_ITEMS.md#fixed-386--governed-events-only-left-when-somebody-pressed-a-button).
2. **And the schedule was then measured against a real collector, twice, with
   the failure first.** A local OTLP/HTTP receiver was started on
   `127.0.0.1:4318` and the destination's next run was moved into the past so the
   host tick would claim it. Both halves were observed on the running host,
   without a browser and without anybody pressing anything:

   * **With nothing listening**, the row recorded
     `telemetry_delivery_failed:fetch_failed:URLError`, the **cursor did not
     move** (`cursor_event_id` stayed `NULL`, so nothing was lost), the schedule
     still advanced to the next whole hour anchored to the claimed slot
     (`20:00:00Z`, not "an hour from now"), and exactly one notification was
     raised: *"Telemetry delivery is failing."*
   * **With the receiver up**, the next tick delivered **247 governed events**,
     moved the cursor to `evt_c0582d4a…`, and raised exactly one more notice:
     *"Telemetry delivery recovered."* The received records carry `event_id`,
     `event_type`, `actor` and `session_id` and **no summary and no path** —
     metadata-only asserted against the wire rather than against the encoder,
     the same standard the 2026-09-04 (second) round held the on-demand path to.

   Two notices for two transitions, across four ticks. The rule that a failing
   wire says so once rather than once per cycle is the part a unit test can only
   assert and this round watched happen.
3. **Twenty-six connector rows that can be read in greyscale.** Every condition
   on a row carries `✓` or `○` and says which for a screen reader, so a row can
   no longer be read as *installed* when the card above it says none are.
   Evidence: `bug-278-connector-facts.png`. Closed as
   [FIXED-389](FIXED_ITEMS.md#fixed-389--twenty-six-connectors-said-they-were-installed-under-a-card-saying-none-were).
4. **All 26 route/tab states captured again** into
   [`screenshots/pages/`](screenshots/pages), and the thirteen existing
   width/clipping/responsive specs re-run green at 390, 768, 1280, 1920, 4K and
   8K in both themes.
5. **Eight live specs converted to the shared sign-in and each re-run against a
   *used* workspace** — which is what made the conversions evidence rather than
   substitutions, because three of them then failed for reasons that were nothing
   to do with signing in. See below.

**What it found, and this is the larger half of the round.**

* **A valid key answered with "check your network."** The first live press of
  **Test** with this round's key produced *"Anthropic could not be reached. Check
  that it is running and reachable from this device."* The provider had answered
  in under a second: *"This API key is not scoped to a workspace, so this request
  must include the anthropic-workspace-id header…"*. The classifier matched three
  exact strings, none of which appear in that body — they had been written from
  the header name and the concept, and the fixture that exercised them had been
  written the same way, so **every literal was matched only by the test that
  invented it**. Two rounds of repair (FIXED-370, FIXED-372) were unreachable for
  the message the provider actually sends. Closed as
  [FIXED-388](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network);
  evidence `bug-277-workspace-repair-live.png` and
  `bug-274-workspace-answer-live.png`.
* **A "next run" printed as a full timestamp.** Verifying the cadence card showed
  *"Next 9/4/2026, 7:17:29 PM"* beside *"Last run ok · 2m ago"* — `relativeTime`
  is a past formatter and falls through for a future instant. Two Workbench
  surfaces had the same thing. Closed as
  [FIXED-390](FIXED_ITEMS.md#fixed-390--three-surfaces-said-next-and-printed-a-full-timestamp).
* **One tab answering an empty list with a grey line.** Observability →
  Notifications, alone among eleven list surfaces. Closed as
  [FIXED-391](FIXED_ITEMS.md#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line).
* **A docstring that described the shipped gate table and called it the product.**
  `telemetry_export` "ships enabled" in `default_capability_gates()` and resolves
  **off** for an account, which is what the live round met. Closed as
  [FIXED-392](FIXED_ITEMS.md#fixed-392--the-source-said-a-gate-ships-enabled-the-product-said-it-was-off).
* **Three harness defects, each found by re-running a converted spec against a
  workspace that had been used.** A seeding step written as a shell comment for a
  person to run by hand; an assertion scoped to the page instead of to the
  inventory it was about, which passed exactly once and then failed as a
  strict-mode violation naming four elements; and a missing network precondition
  reported as a three-minute timeout on a click. All three are recorded under
  [BUG-248](TO_BE_FIXED.md#bug-248--twenty-seven-live-specs-still-sign-in-inside-a-test-body)
  and [BUG-250](TO_BE_FIXED.md#bug-250--a-shared-live-workspace-carries-state-between-specs).

**What it could not run, for the third round in a row.** The three scenarios of
[BUG-273](TO_BE_FIXED.md#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun)
need a model to answer, and this round's key is identity-linked like the last
two. `/v1/organizations/me`, `/v1/organizations/workspaces` and
`/v1/organizations/api_keys` all answer it `403`, so the workspace id is again
not recoverable from the credential — only its owner has it. One conversion,
`c17-b14-recall-and-inline-diff-live`, was **reverted rather than committed
unverified** for the same reason.

The attempt was still worth making: FIXED-388 exists only because a third key was
pasted into the product and the answer was read.

---

## 2026-09-04 (second) — Five priority items, and two defects the sweep found in itself

**Tier: targeted + measured four-width sweep.** Production web build, a workspace
reset through `scripts/reset_live_workspace.py`, and one provider: Anthropic,
with the same **identity-linked** key entered through the Connect dialog. No key
appears in this repository.

**What it proved.**

1. **Every route at 390, 768, 1280 and 1920**, measured rather than photographed
   — and the check learned one thing about its own scope on the way: SVG has its
   own layout model, so `clientWidth` on a graph label is not a content box and
   comparing it to `scrollWidth` reported the knowledge map's own rendering as a
   page-layout defect. The bleed check is HTML-only, stated in the spec:
   the document never scrolls sideways, no element bleeds out of a `visible` box,
   every control has an accessible name, and — new this round — **no control
   draws nothing**. `e2e/ui-sweep-widths-live.spec.ts` is that check; the two
   extremes are captured to [`screenshots/widths/`](screenshots/widths).
2. **The round's key connected through the interface**, and the refusal read as
   itself. `e2e/anthropic-key-live.spec.ts` connects it, opens the model picker,
   and asserts the dialog names the workspace requirement rather than
   reachability.
3. **Declared MCP tool arguments, on the card.** The reviewed echo template was
   built and connected through the interface; the card reads `echo · text` and
   `workspace_ping · Takes no arguments`, negotiated on revision `2026-07-28`.
   Before this round the same card was a row of name chips and the model had to
   guess `text`. Evidence: `backlog-16-mcp-declared-arguments.png`.
4. **Governed events reaching a real OpenTelemetry collector.** A local OTLP/HTTP
   receiver on `127.0.0.1:4318` was added through **Observability → Overview**,
   and three **Deliver now** runs landed **166 records**. The last run carried 5
   — only what was new — which is the cursor doing its job. Every record carried
   identifiers and an event type; the received bodies contain **no summary and no
   path**, which is metadata-only asserted against the wire rather than against
   the encoder. Evidence: `backlog-18-otlp-collector.png`.
5. **An `http` hook, granted and refused, on one card.** The host ran with
   `RAIKER_HOOK_EGRESS_ALLOWLIST=127.0.0.1:*` and a project rule declaring two
   `http` handlers. Both parse and both match; the Hooks tab shows the granted
   destination as `advisory` and says of the other *"this host is not in
   RAIKER_HOOK_EGRESS_ALLOWLIST — it will refuse every time it matches"*. The
   grant is read live, so revoking it needs no file edit and no restart.
   Evidence: `bug-226-http-hook-grant.png`.
6. **The working-method control appears only where Build can work.** On Tasks
   outside a project there is no *How to work* group at all, because Build's
   method is a repository it can read. Evidence:
   `backlog-23-task-surface.png`.
7. Each of the five items also carries its own unit and API coverage, and every
   surface they changed was walked at all four widths with no console error.

**What it found**, all fixed in this change rather than deferred:

* **The model picker said "Provider unreachable" about a provider that had just
  answered in full.** `testNote` has read the server's classification since
  BUG-272; `pickerNote` switched on status alone and threw it away — and the
  picker is the control on the path an owner actually walks. Closed as
  [FIXED-382](FIXED_ITEMS.md#fixed-382--the-model-picker-said-unreachable-about-a-provider-that-had-just-answered).
* **Settings named itself twice, and the round's own new switch named itself not
  at all.** Settings opened with a heading and a sentence the topbar had already
  said; `telemetry_export` landed on Permissions with no `CAPABILITY_COPY` entry,
  so a gate that reaches the network read as *"Governed capability."* in **Other
  tools**. Both closed as
  [FIXED-385](FIXED_ITEMS.md#fixed-385--two-surfaces-named-themselves-twice-and-a-new-switch-named-itself-not-at-all),
  the second with a test: the label map is prose and cannot be derived from the
  registry, so it is the pair that drifts, and the first capability added after
  the pair existed drifted it.
* **A hook rule pushed its own card past a 390px window.** A grid item's default
  `min-width: auto` refuses to shrink below its content, so one unbreakable
  string — an `http` handler's URL — carried the card four pixels wide. Found by
  the sweep on the very rule this round added, which is the sweep doing its job
  on new work rather than on old.
* **Two path fields taught a shape that cannot exist on this host.** `D:\Models`
  and `D:\Raiker Backups` were hardcoded placeholders on a product that ships for
  three platforms. Caught by reading the sweep's own screenshots, which is what
  capturing them is for — no assertion can tell a wrong example from a right one.
  Closed as
  [FIXED-384](FIXED_ITEMS.md#fixed-384--two-path-fields-taught-a-shape-that-cannot-exist-on-two-of-three-platforms).
* **The composer's model control was a blank circle below 1024px whenever no
  model was chosen** — which is the state a fresh install is always in. The
  narrow-width rule hides the label and the chevron and leaves the provider logo;
  with no model there is no logo. Closed as
  [FIXED-383](FIXED_ITEMS.md#fixed-383--the-model-control-was-an-empty-circle-whenever-no-model-was-chosen),
  and the sweep now fails on the whole class rather than on this instance:
  reverting the one-line fix makes it fail on Chat and Build at 390 and 768.

**What it could not prove.** A real provider *turn*. The key is identity-linked
and authenticating needs the workspace id itself, which only the key's owner has
— and the key cannot be asked for it: `/v1/organizations/*` answers a key of this
kind with `403`.
[BUG-273](TO_BE_FIXED.md#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun)
stays open for that reason, unchanged: it is waiting on a value, not on code.

**Screenshots:** [`screenshots/widths/`](screenshots/widths) — every route at 390
and 1920 — and `anthropic-identity-linked-key.png` in
[`screenshots/working/`](screenshots/working).

---

## 2026-09-04 — Identity-linked key, and the sweep at four widths

**Tier: targeted + full responsive sweep.** Production web build, a workspace
reset through `scripts/reset_live_workspace.py` before each attempt, and one
provider: Anthropic, with an **identity-linked** key entered through the Connect
dialog. No key appears in this repository.

**What it proved.**

1. A fresh instance, owner registered, Anthropic connected with the supplied key.
   The save succeeds — saving a credential contacts nothing.
2. **Test** on that card reaches the provider and the refusal comes back as a
   repair: *"This key is identity-linked, so it acts inside one workspace. Add
   the workspace ID to this connection — it is beside the key in the provider's
   console — then connect again. The key you pasted is fine."* Not a status code,
   and not an instruction to go and find a different key.
   *(BUG-274 / [FIXED-372](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one).)*
3. **Add workspace ID** on that same answer opens the connection dialog with
   **Advanced** already expanded and the field visible.
4. A workspace id that could not safely become an HTTP header is refused before
   anything is stored.
5. Every route measured at **four** widths — 390, 768, 1024, 1440 — with nothing
   reaching past the window that is not inside something that scrolls on
   purpose, and no console error. 768 was added this round: it is where several
   views hand a two-column grid over to one, and a sweep that stepped 390 → 1024
   stepped over it.
6. Every route captured and rendered in explicit light and dark themes, no
   console error, no page repeating the topbar's own sentence.

**What it found**, all fixed in this change rather than deferred:

* The guidance for a workspace refusal was wired to the *save*, which never
  contacts the provider. Two paths actually meet it — the readiness check with a
  model pinned, and the catalogue read without one — and the fresh-connection
  case, which is where an owner meets it first, was the one not covered.
* **Reconnect** is reached through **Model details**, and saving left that modal
  over the card it had just changed. The live harness had been closing it by
  hand since FIXED-141 with a comment saying so, which had made an interface
  defect look like a test concern.

**What it could not prove.** A real provider *turn* on this key: authenticating
still needs the workspace id itself, which only the key's owner has.
[BUG-273](TO_BE_FIXED.md#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun)
stays open for that reason and is now waiting on a value rather than on a
product change.

**Screenshots:** `bug-274-workspace-answer-live.png` and
`bug-274-workspace-field-live.png` in [`screenshots/working/`](screenshots/working);
the page sweep refreshed [`screenshots/pages/`](screenshots/pages) in full.

## 2026-08-09 — BUG-69 closure round
Run against a fresh isolated workspace and the production web build. Provider
credentials were entered through Models only and are absent from screenshots,
source, and logs committed to the repository.

1. Register a fresh owner. Confirm the model setup prompt opens.
2. Skip setup, visit Workbench, Chat, Build, Tasks, and Schedule, and confirm
   each model-backed primary action is disabled with a Models link.
3. In Models, select local Ollama `gemma4:31b-cloud` and run **Check**. Confirm
   exact-model Ready. A direct bounded generation returned the requested marker.
4. Connect OpenRouter through the UI, select `openai/gpt-4o-mini`, and confirm
   catalogue plus one-token execution readiness. A real governed turn reached
   the approval boundary and executed no command.
5. Connect Anthropic through the UI and select `claude-opus-4-8`. The live
   catalogue authenticated, but the account rejected execution for insufficient
   credit. Confirm the readiness result names current-account execution, links
   remediation, preserves the draft, and keeps Send disabled.
6. Add one exact local folder under **Local library**, rescan, and confirm its
   GGUF name, llama architecture, Q4_K_M quantization, and Deploy action.
7. Search Hugging Face for a GGUF repository. Confirm immutable revision,
   licence, gated status, size, format, and Q4_K_M choices are visible before
   download confirmation. Download the tiny permissive TinyStories GGUF into an
   approved root, deploy it, and wait for the newest Activity row to reach
   `complete`.

**Result: ✅ BUG-69 closed.** No raw provider reason code became the first
assistant reply. Screenshots: `208-BUG-69-first-run-model-setup-live.png` through
`214-BUG-69-huggingface-download-deploy-live.png`. The Anthropic refusal is an
expected external account state and proved the new fail-closed execution
preflight; OpenRouter and Ollama supplied successful execution evidence.
