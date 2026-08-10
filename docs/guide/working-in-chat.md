# Working in Chat

Chat is a normal conversation: your prompt right-aligned in a teal bubble,
Raiker's reply left-aligned in a quiet neutral one, with *"Raiker is thinking…"*
then *"Raiker is typing…"* while it works. Governance panels, phase labels, and
event traces deliberately stay out of the transcript — they live in **Sessions**,
**Approvals**, and **Observability**.

## The composer

| Control | `aria-label` | What it does |
|---|---|---|
| **Attach → Image…** | `Add attachment` | Upload `png`, `jpeg`, `webp`, `gif` for vision-capable models |
| **Attach → Document…** | `Add attachment` | Upload `txt`, `md`, `csv`, `pdf`, `docx`, `xlsx`; text is extracted server-side |
| **New chat** | — | Start a fresh conversation. Disabled while the current chat is still empty. |
| **⋯** | `Conversation actions` | **Export conversation…** and **Print / Save as PDF**. Both are also in Build. |
| **Model** | `Model for this turn: <name>` | Only *configured* profiles. No free-text model ids. |
| **Context** | `Context window` | Opens a read-only popover. It never compacts the conversation. |
| **Background work** | `Background work` | Hands the turn to the background queue instead of waiting on it |
| **Project or folder** | — | Organises the chat and supplies bounded project context. It does not grant filesystem or tool access. |
| **Approval** | `Approval mode: …` | **Manually approve**, **Automatically approve**, or **Skip all approvals** for otherwise eligible governed actions. |

There is **no** planning chip and **no** voice-input control in the shipped
composer; earlier drafts of this guide listed both.

`Enter` sends, `Shift+Enter` adds a line.

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

## Reading a reply

Raiker's replies are rendered as Markdown: headings, lists, tables, links, and
fenced code. **Your own messages are shown exactly as you typed them, and this
is deliberate** — a prompt is an instruction whose exact characters matter, so
Chat never re-formats one. If you write `**bold**` in a prompt, the model
receives those asterisks and you see those asterisks.

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

**Search Chat** searches conversation titles *and* message text, and each result
offers *"Open conversation →"* to resume exactly where you left off.

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

## Known limits

Raiker's documentation does not run ahead of its code. As of 2026-08-08, these
are the edges a Chat user can still hit:

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
- **Web fetch is off until you turn it on, twice.** `web_fetch` is disabled by
  default and still withholds at its default `ask` decision mode, so reaching
  the open internet takes both the capability gate and a raised decision mode.
  Once it is at **Allow**, a turn fetches the page and quotes it, and a host
  outside `RAIKER_WEB_EGRESS_ALLOWLIST` is refused by name. `web_search` answers
  the same gate but has no endpoint shipped with Raiker: it reports
  `web_search_not_configured` until you point it at one.
- **Remembering something is a decision, and it starts off.** With **Memory
  store** turned on in Permissions, a turn can propose a durable fact or
  preference to keep; you see the exact sentence before you approve, and
  approving really stores it. Until you turn the capability on, no conversation
  can propose one — the Memory page states which of the two you are in.
- **Asking for a task in Chat gets you an approval, not a task.** See
  [Tasks and projects](tasks-and-projects.md) → Known limits.
- **An exported conversation carries citation numbers it cannot explain.** The
  transcript resolves `[s1]` against the turn's sources; an export carries the
  answer text only, so the numbers travel without the list they refer to.
- Automatic context compaction at 90 % and weekly quota display are specified
  but not shipped.

Three limits this section used to list have shipped and are gone from it:
Markdown rendering (**FIXED-06**), conversation export (**FIXED-12**, superseded
by **FIXED-19** and **FIXED-54**), and — the one that mattered most — an
approved file write really reaching the disk (**FIXED-08**). Where a limit above
is tracked as work rather than a deliberate boundary, it has a reproduction and
a proposed fix in [To be fixed](../plans/TO_BE_FIXED.md).

## Context and API cost

The **Context** control opens a read-only panel with two independent facts, each
labelled with where it came from. The same control is in the **Build** composer
and reads the same data.

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
| Config | "list price, as of 2026-07" | A documented list price shipped in `config/model-profiles.json`. |

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
