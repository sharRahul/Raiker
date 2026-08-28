# Working in Chat

Chat is a normal conversation: your prompt right-aligned in a teal bubble,
Raiker's reply left-aligned in a quiet neutral one, with one quiet *Working…*
indicator that ends as soon as there is something real to show. Governance
panels, phase labels, and event traces deliberately stay out of the transcript —
they live in **Sessions**, **Approvals**, and **Observability**.

## The composer

| Control | `aria-label` | What it does |
|---|---|---|
| **Attach → Image…** | `Add attachment` | Upload `png`, `jpeg`, `webp`, `gif` for vision-capable models |
| **Attach → Document…** | `Add attachment` | Upload `txt`, `md`, `csv`, `pdf`, `docx`, `xlsx`; text is extracted server-side |
| **New chat** | — | Start a fresh conversation. Disabled while the current chat is still empty. |
| **⋯** | `Conversation actions` | **Export conversation…** and **Print / Save as PDF**. Both are also in Build. |
| **Model** | `Model for this turn: <name>` | Only *configured* profiles. No free-text model ids. The menu also carries **Effort** — this model's own thinking levels and a **Thinking** switch — when the model publishes any. |
| **Context** | `Context window` | Opens a read-only popover. It never compacts the conversation. |
| **Background work** | `Background work` | Hands the turn to the background queue instead of waiting on it |
| **Project or folder** | — | Organises the chat and supplies bounded project context. It does not grant filesystem or tool access. |
| **Approval** | `Approval mode: …` | **Manually approve**, **Automatically approve**, or **Skip all approvals** for otherwise eligible governed actions. |
| **Dictate** | `Dictate` | Starts browser speech recognition and writes the result into the ordinary editable draft. It never sends. The same control ships in Build. |

Every control lives on one bar under the prompt: `+` and the scope controls on
the left, the model chip and **Send** on the right. The bar is deliberately
short: Chat is the knowledge-work surface, so it carries no way to switch into
Build and no capacity chip repeating what **Context** already reports.

There is no planning chip in Chat. While dictation is listening, **Done** or the
first `Enter` stops listening and keeps focus in the draft; **Cancel** restores
the exact draft from before dictation began. A later `Enter` or **Send** is the
only way to submit. Outside dictation, `Enter` sends and `Shift+Enter` adds a
line.

Speech recognition and read-aloud use browser and operating-system services;
the selected service may process speech online. Settings → General stores the
owner's speech language. Raiker stores the normal prompt and its
`typed`/`dictated`/`mixed` provenance, never microphone audio or a second copy of
the transcript.

The approval setting controls the interaction, not the runtime's protections:

- **Manually approve** pauses before every otherwise eligible governed action.
- **Automatically approve** proceeds without a user pause and retains normal
  status plus preview/evidence.
- **Skip all approvals** proceeds without the user prompt or generated preview,
  but still enforces project/path confinement, edit hunk/context validation,
  atomic rollback, managed policy, sandbox and security boundaries, restricted
  command policy, and critical holds.

The selected policy is shared with Build and is remembered for the next
composer session. It is not the same as Build's Plan/Edit/Auto runtime modes.

### Slash commands

Typing `/` at the **start** of the prompt opens the command menu. Every entry is
a control you already have; none of them sends anything to the model, and none
grants anything:

| Command | What it does |
|---|---|
| `/new` | Start a fresh conversation |
| `/model` | Open the model menu for this surface |
| `/attach` | Open the attachment panel |
| `/context` | Open the read-only context popover |
| `/approvals` | Open the approvals inbox |
| `/plan` | Show the agent's current plan |
| `/schedule` | Open **Tasks**, where a one-off schedule, a daily routine or a background agent is created |
| `/tasks` | Open **Tasks** to see schedules and runs already under way |
| `/export` | Export this conversation |
| `/stop` | Stop the running turn at its next safe boundary |
| `/shortcuts` | Show the keyboard map |

`/schedule` and `/tasks` open the governed **Tasks** surface; neither creates or
starts anything on its own. Asking Raiker in prose — *"run this every morning"* —
goes through the `create_task` approval instead, which names exactly what it
would create before you decide. See
[Tasks and projects](tasks-and-projects.md).

## Reading a reply

Raiker's replies are rendered as Markdown: headings, lists, tables, links, and
fenced code. **Your own messages are shown exactly as you typed them, and this
is deliberate** — a prompt is an instruction whose exact characters matter, so
Chat never re-formats one. If you write `**bold**` in a prompt, the model
receives those asterisks and you see those asterisks.

A completed reply also has **Read aloud**. It is manual: Raiker never starts
speaking because a response arrived. **Stop speaking** interrupts playback, and
starting dictation anywhere stops it. The spoken form keeps readable prose but
omits fenced-code bodies, Markdown/citation syntax and raw URL text. Streaming
or incomplete replies cannot be read aloud.

Every code block in a reply carries:

- **the language**, named conventionally (a ```` ```ts ```` fence reads
  *TypeScript*). A language Raiker does not ship a grammar for is still labelled,
  just not coloured — a wrong colour would be a claim about the code;
- **Copy code**, reachable by keyboard, which copies the source the model wrote
  with the highlighting stripped. It announces *Code copied to the clipboard*, or
  says so plainly if your browser blocks clipboard access.

Highlighting is produced entirely on your machine from a grammar shipped inside
Raiker. Nothing is fetched to colour a keyword, and a code block can never
execute — the renderer escapes every character of model output before it emits
any markup.

### What Raiker did

When a turn uses a tool, each call gets one line above the answer, in the order
the model asked for it:

| Part | What it tells you |
|---|---|
| The icon | The kind of work — a file, a command, the web, the repository, one of your connected accounts, memory, a subagent, or the plan |
| The name | The tool in plain words: *Read file*, *Run command*, *Search the web* |
| The rest | What it acted on: the path, the host, the program, the search you asked for |

A call still running shows a small pulse. A call waiting on your decision says
*waiting for your decision*, beside the card where you make it. A call that
failed or was refused says why on its own line, with a link to the page that
would let it through where one exists.

**The line is deliberately a summary.** A page it fetched is named by its host
and never its full address, and a command by the program it ran and never its
arguments — both can carry a credential in a place that looks ordinary. The
whole of each is kept in the audit record, where it is evidence rather than
something on your screen. **Observability → Audit log** is where you read that.

### What Raiker was thinking

Some models can think before they answer. The setting belongs to the model, so it
lives inside the **model menu** as an **Effort** section: the levels are the exact
ones that model publishes, and a **Thinking** switch decides whether any effort is
sent at all. Leave the switch off and Raiker asks for nothing. A model that
publishes no levels has no Effort section — the control is absent rather than
present and useless.

Turn it on and a collapsed **Thinking** block appears above the answer, filling
in as the model works and closing as soon as the answer starts. You can open it
again afterwards.

Two things it is not. It is never a summary Raiker wrote — it is the model's
own working, in the model's own words, and where the provider can return a
summary of that working rather than its raw notes, that is what Raiker asks for.
And when a turn produces no reasoning, there is **no block at all**: nothing
stands in for it.

Thinking is shown while the turn runs and is not kept. Re-open the conversation
later and you will see the answer, not the working.

### Where the answer came from

When a turn reads something — a file in your workspace, an email, a calendar
entry, a page it fetched, a memory, or a document you attached — a **Sources**
strip appears under the reply naming each one, and Raiker asks the model to mark
the sentences that rest on them with a small numbered chip.

Two different things are on screen, and Raiker keeps them apart on purpose:

- **The strip is a fact.** Every source in it is something the runtime really
  ran and recorded. It is listed whether or not the model mentioned it.
- **A chip is the model's claim.** A source the model actually cited is marked
  as cited. Raiker cannot verify that the sentence beside it was drawn from that
  source — only the model knows that — so it is shown as a claim rather than
  promoted to a fact.

A number the runtime never recorded is not a citation. If a reply contains
`[s7]` and no seventh source exists, it stays those five characters: nothing
becomes clickable, and no source is invented to match it.

**Click any of them to open the source at the passage that was used.** A file or
an attached document opens in the file preview with the passage marked; a page
or an email — which Raiker holds no second copy of — is shown as the exact text
that reached the model. What happens when it cannot be marked is stated rather
than guessed:

| What you see | What it means |
|---|---|
| *Located by matching this answer's own words* | The sentence you clicked from occurs verbatim in the source, and that run is marked |
| *The whole of this source was read* | The turn read all of it, so marking every character would say nothing |
| *Exactly what this turn received* | Material that lives outside Raiker, shown as the text the model actually got |
| *The source no longer contains this passage* | The file changed since the turn read it, so it is shown **without** a highlight rather than with one near where the passage used to be |

Only the ids and counts reach the durable event log. The titles and the passages
are content: they stay in the encrypted store and are served only to the account
that owns the conversation.

**Build does the same thing**, except that a cited source opens *inline* under
the answer rather than in a side pane — Build does not have one yet.

## Exporting a conversation

The `⋯` menu above the transcript offers **Export conversation…** in both Chat
and Build. It opens a review first: how many messages, exactly which files, and
what redaction is applied — before you pick a format.

| Format | Use it for |
|---|---|
| **HTML** | One self-contained page. No scripts, no remote assets; it opens offline. |
| **Markdown** | Plain text you can edit, diff, or commit. |
| **PDF** | A paginated document for filing or sending on. |

Secret-shaped values — API keys, tokens, credentials — are replaced with
`***REDACTED***` in every message before anything is rendered. Attached files are
**listed** by name, type, and size; their contents are never embedded.

**Print / Save as PDF** uses your browser's own print dialog against a dedicated
print layout: the sidebar, topbar, composer, and controls are dropped, and a turn
never splits across a page. Every export is recorded in the event log with its
format and counts — never its text.

## Your conversations

Every chat appears under **RECENT CHATS** in the sidebar with its title and a
relative timestamp. The `⋯` menu offers Copy local link, Rename, Move to
project, Pin, Archive, and Delete.

**Search Chat** searches conversation titles *and* message text across every
conversation you have had, however old. Each result shows the exchange that
matched beneath its title — so you can tell which chat it is before opening it —
groups results by the day they happened, and offers *"Open conversation →"* to
resume exactly where you left off.

**Observability → Sessions** is the complete record: every conversation with its
turn count, status, tags, and the governed events behind each turn. Task runs
live there too, which is why they are not in RECENT CHATS.

## Attachments

Upload a document, then ask about it — the extracted text goes into the model's
context for that turn. Images go to vision-capable models as image blocks; a
profile without vision support has the image withheld before any provider
contact rather than silently dropped.

Attachment content never enters the durable event log — only the id, media type,
size, and hash.

### Looking at a file again

An uploaded file's chip in the transcript is a button. Clicking it opens a
**view-only file preview** beside the conversation — a right-side pane on a wide
window, a dismissible sheet on a narrow one. `Esc` or **Close file preview**
closes it and returns focus to the chip.

| File | What the preview shows |
|---|---|
| `md` | Rendered Markdown (raw HTML in the file is shown as text, never executed) |
| `txt`, `csv` | The text as written |
| `docx` | The document's extracted text |
| `xlsx` | The first sheet's cell values as a table |
| `pdf` | The PDF itself, in your browser's viewer |
| `png`, `jpeg`, `webp`, `gif` | The picture, fitted to the pane |

The pane is read-only: there is no edit, upload, or download control, and long
files say so rather than pretending to show everything. A preview is scoped to
the conversation the file was attached to — the same file id opened from another
chat, or by another account, is a 404.

PDFs and images are the only previews served as raw bytes, and both are checked
again on the way out: the response carries the content type the bytes were just
re-validated against, with `nosniff`, so a file can only ever be interpreted as
what it actually is. A picture whose contents do not match its type is not
displayed at all — the pane says so instead.

Chips survive a reload: resuming a conversation restores them, and they open the
same previews.

Preview text goes through the same response redaction as everything else the API
returns, so a credential-shaped string inside a file shows as
`[REDACTED_SECRET]` in the pane. The stored file is untouched — only the view is
masked.

## Approvals

An approval names two identities when both exist: the Raiker machine turn that
proposed the action and the human owner who approved or denied it. The machine
label includes its turn for audit correlation. Approval never transfers your
identity to the agent, and a resumed turn receives a fresh short-lived token
before it continues.

When Raiker proposes a gated action, the reply says *"Your approval is needed to
continue"* with a **Review approval** link. **Approvals** shows the proposal —
for a file write, the exact unified diff — with the capability, risk, session,
and expiry.

Approving resumes the waiting turn. Where the governed action is eligible for
execution, Raiker re-checks its runtime protections and executes it once; other
approvals are record-only and show `executes_action: false`. Filters (Pending /
Approved / Denied) and sorting (highest risk / newest) are on the same page.

### Deciding in another tab

A turn that is waiting shows **Waiting for approval**. You do not have to decide
in the tab that raised it: record the decision in the Approvals inbox, in Build,
or in another window, and the waiting conversation changes to **Approved —
continuing…** on its own and picks up exactly where it stopped — same
conversation, same session, no re-prompt.

If Raiker cannot currently watch for a decision made elsewhere, the card says so
and offers **Continue now** instead of leaving you guessing. A turn is continued
exactly once even if several tabs react at the same moment; a tab that loses that
race says **Continued in another tab** rather than reporting an error.

## Background work

Chat shows the same inline **Background Work** panel as Build. It keeps active
agent operations, background tasks, and approval-blocked work beside the
conversation so you do not need to change surfaces to discover why work paused.
An approval-blocked item includes **Review approval**, which opens the relevant
approval for that task.

## Conversation memory

For the full owner-facing lifecycle—proposal approval, source provenance,
scope, Incognito, retention, correction, archive, forget, and purge—see
[How Raiker memory works](memory.md).

Raiker replays the prior completed turns of the conversation to the model, so a
follow-up question works: tell it a codeword and ask for it two turns later and
it has it.

- Only **completed** exchanges are replayed. A turn still running, failed, or
  waiting on an approval is skipped — a prompt with no answer would read to the
  model as an unanswered question.
- History is bounded by the model's context window (half of a known capacity,
  or a conservative default when it publishes none). When it will not all fit,
  the **oldest** exchanges are dropped, because a follow-up depends on what was
  said recently.
- History never crosses conversations. A new chat starts genuinely empty.

The replay is recorded as a `conversation_history_replayed` audit event carrying
counts only — how many messages and how many characters — never the transcript.

### Recalling an older conversation

History never crosses conversations, but **recall** does. When you refer to
something from an earlier chat — *"the approach we settled on"*, *"that error
last year"* — Raiker can search your own past conversations and quote what was
actually said, rather than reconstructing it from memory.

- Say roughly when, if you know: *"back in 2022"*, *"before we moved off
  Postgres"*, *"some time last spring"*. A date narrows the search to that
  period, which is what makes a conversation from years ago reachable instead of
  losing it behind everything more recent.
- What comes back is cited: the conversation's title, the date, and the exchange
  itself. Ask for the quote if you want to check it — *"quote the sentence"*.
- It searches **your** conversations only, and reads them as data rather than as
  instructions. An old message that said "always do X" is evidence about what
  was said, not an order carried into today's turn.
- **Incognito** (Memory → Incognito session) switches the whole path off. With it
  on, nothing is recalled from anywhere.

This is separate from **Memory**, which holds facts you approved for Raiker to
keep. Recall reads the transcript; Memory reads what was deliberately
remembered. You can use either, and Raiker will say which one an answer came
from.

### Recall backend

Recall compares your question against exactly **one** embedding space at a time.
Comparing two different embeddings produces a similarity that means nothing, so
mixing them is refused rather than averaged. The choice applies both to the
memories Raiker attaches to a turn on its own and to the ones the assistant looks
up while it works.

**Memory → Recall backend** states which space is in force:

- **`raiker-local-hash-v1` — matches words, not meaning.** The default, computed
  offline with no model and no network. It finds a memory that shares words with
  your question and misses a paraphrase of it.
- **A provider or local model, once you build one.** Your approved memories are
  stored as learned embeddings in a space named for the model you chose.

A workspace only offers a space it actually holds vectors in, which is why a new
install can offer nothing but the fallback. **Build a meaning-based index** is how
the first real space comes to exist: pick an embedding model and Raiker sends the
text of each approved memory to it, once, as one governed action you approve.

When a semantic space is selected, Raiker embeds the question once through the
same governed provider or local path and uses it for both ambient and explicit
recall. If you deny provider egress or the backend fails, the read continues with
the lexical fallback and says which retrieval path produced each source.

- Memories marked **secret-like** or **credential-like** are never sent.
- Re-running it embeds only what has been approved since, so keeping the index
  current does not cost what building it did.
- A local model (llama.cpp, Ollama) keeps the text on the machine. A hosted one
  sends it to that provider — the confirmation says which, and how many memories,
  before anything leaves.

### Retention

Every observation Raiker records carries a retention class, and the classes with
a time limit — `turn_only`, `short_term_7_days`, `short_term_30_days` — are swept
by **you**, not by a background worker. Raiker deliberately runs no cleanup daemon:
**Memory → Observations** says how many records are past their class and gives you
one control that removes exactly those and reports what it removed. The other
three classes (`project_lifetime`, `until_forget`, `legal_hold`) have no automatic
expiry by design.

## Known limits

Raiker's documentation does not run ahead of its code. As of 2026-08-21, these
are the edges a Chat user can still hit:

- **Voice is turn-based, not a hands-free live conversation.** Dictation stays
  in an editable draft and response playback is manual. Continuous listening,
  spoken replies, interruption and hands-free task control are future work; a
  consequential spoken control will require visible, action-bound confirmation
  and the same gateway receipt as its typed equivalent before it can ship.

- **What a turn did is shown while it runs, and is not kept in the transcript.**
  The tool lines and the Thinking block are built from the live turn. Re-open the
  conversation later and you see your prompt, the answer, and the sources — the
  lines and the working are not rebuilt. The full record of every call is in
  **Observability → Audit log**, which is permanent.

- **An approved network or process action is recorded, not run.** Approving a
  proposed file change, patch, bounded `shell` command, or an owner-configured
  SSH/Daytona command carries it out once. `network` and `process` approvals
  record your decision and execute nothing, and the approval detail says which
  you are about to do **before** you decide. The turn continues either way — the
  model is handed an honest "approved, but not executed" result to react to.
- **A batch of tool calls runs in parallel only when nothing in it needs a
  decision.** Several reads in one turn run concurrently. The moment one call in
  the batch requires approval, the batch is walked one call at a time and pauses
  there; nothing behind the pause is lost, but a turn proposing three edits is
  three decisions.
- **Web reads work, and you say what they may not reach.** A turn can fetch a
  page and quote it, and search the web, with nothing configured first. Add
  anything you want refused under **Settings → Web access** — a domain, a
  wildcard, an IP, a range, or a pattern — and check a host there without
  contacting it. Your own network is never reachable and that is not a setting:
  a private, loopback or link-local destination is refused however it is spelled
  and wherever a redirect leads. What comes back is the page as text with the
  hidden parts removed, and it is data you can act on — never an instruction the
  page gets to give.
- **Remembering something is a decision, and it starts off.** With **Memory
  store** turned on in Permissions, a turn can propose a durable fact or
  preference to keep; you see the exact sentence before you approve, and
  approving really stores it. Until you turn the capability on, no conversation
  can propose one — the Memory page states which of the two you are in.
- **Approving task creation parks the task; it does not run it.** The approved
  task appears in Tasks with no schedule. **Run now** is a separate execution
  decision. See
  [Tasks and projects](tasks-and-projects.md) → Known limits.
- **A tool that keeps failing stops being tried, and says so.** Three failures
  in a row on the same tool or the same provider contain it: the next call is
  refused with the reason and the failure count instead of being retried, and one
  call a minute later is let through to see whether it has recovered. Nothing is
  taken away permanently — Settings → Security & sign-in lists what is contained
  and clears it in one press.
- **A suspicious page is flagged, not withheld.** If a page, message or file this
  turn read contains text shaped like an attempt to redirect Raiker, you get a
  finding naming that exact source. The content is still used — as data, never as
  instructions, which is what actually keeps it harmless — so treat the finding
  as provenance rather than as a block.
- **Send waits for a model check, and the check expires.** A surface will not
  send until the exact model has passed a reachability check. That check is good
  for five minutes by default (Settings → Runtime, 1–120 minutes), and while a
  work surface is open Raiker re-confirms it quietly in the background before it
  lapses. Changing model, endpoint or credential invalidates it immediately
  whatever the window says.

Three limits this section used to list have shipped and are gone from it:
Markdown rendering (**FIXED-06**), conversation export (**FIXED-12**, superseded
by **FIXED-19** and **FIXED-54**), and — the one that mattered most — an
approved file write really reaching the disk (**FIXED-08**). Where a limit above
is tracked as work rather than a deliberate boundary, it has a reproduction and
a proposed fix in [To be fixed](../plans/TO_BE_FIXED.md); the closed ones keep
their full record in [Fixed items](../plans/FIXED_ITEMS.md).

## Context, compaction, and API cost

The **Context** control opens a read-only panel with independently sourced
capacity, usage, cost, and the latest automatic-compaction outcome. The same
control is in the **Build** composer and reads the same data.

```
Context window                    2.9K / 200.0K (1%)
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Provider-reported usage. Capacity provider-reported.

This chat                                   $0.0030
anthropic, all time                         $0.0059
claude-haiku-4-5-20251001 — list price, as of 2026-07
```

**Context window.** Once a turn has run, the used figure is the provider's own
reported prompt tokens. Before that, Raiker falls back to a coarse local
estimate and says *"Estimated from this chat's text"*. Capacity is pulled from
the provider where one publishes it — Anthropic reports `max_input_tokens` per
model — so the meter is correct for every model rather than assuming one number
for a whole family. A model whose capacity nobody publishes says *"Context
capacity is not configured for this model"* instead of guessing.

**Automatic compaction.** At 90 % of a known capacity, Raiker asks the selected
model to summarize older completed exchanges in a separate request with tools
and reasoning disabled. It keeps the newest two exchanges verbatim and carries
forward the active plan plus pending approval, checkpoint, and source IDs. The
full transcript stays unchanged. The panel shows **Earlier context compacted**
with before/after estimates, or **Recent history retained** when the provider or
a `PreCompact` hook made compaction unavailable. An unknown capacity uses bounded
recent history and never pretends the 90 % boundary was measured.

**API cost.** Shown only for providers Raiker authenticates with an API key and
reaches off this machine. A local runtime says *"Runs on this machine — no API
cost"*, because it costs nothing per token however many it burns. Two figures
are given: what this conversation has cost, and your running total on that
provider — the same total the Models page shows.

Prices resolve from three sources, in this order, and the winner is always named
under the figures:

| Source | Shown as | Where it comes from |
|---|---|---|
| Owner | "administrator override" | A rate an administrator set, with a reason, on the Models → **Pricing** tab. Always wins. |
| Provider | "provider-reported" | Published by the provider's own API. OpenRouter does this; most do not. |
| Config | "list price, as of 2026-07" | A documented list price shipped in `raiker/config/model-profiles.json`. |

If none applies the panel says **Unknown** and offers **Configure →** rather
than showing `$0.00` — a zero always means "this was free", never "we do not
know". Costs are stored as counts, not money, so correcting a price re-prices
your history immediately.

The panel lists each rate component it actually has: input, output, and — where
a provider publishes them separately — cache write and cache read. A component
nobody published is simply not listed; Raiker never derives one rate from
another, because an inferred figure would be indistinguishable from a stated one.
When a cache rate is unknown, cached tokens fall back to the full input rate,
which over-states rather than under-states: a bill should never surprise you in
the expensive direction.

Every rate lives in an effective-dated registry, so what a turn cost on the day
it ran stays reproducible after a provider changes its prices. The **Models**
page is split by what you came to do — **Providers**, **Routing**, **Pricing**,
**Posture** — and its **Pricing** tab shows the whole registry: the exact model id each rate belongs to, its
source, when it took effect, its full change history, and — per provider — when
prices were last synchronised, when the next refresh is due, and whether the
current reading is stale. Recording an override needs the runtime gate-manager
role and a reason; both are kept with the rate.
