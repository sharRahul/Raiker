# Working in Chat

Chat is a normal conversation: your prompt right-aligned in a teal bubble,
Raiker's reply left-aligned in a quiet neutral one, with *"Raiker is thinking…"*
then *"Raiker is typing…"* while it works. Governance panels, phase labels, and
event traces deliberately stay out of the transcript — they live in **Sessions**,
**Approvals**, and **Observability**.

## The composer

| Control | What it does |
|---|---|
| **+ → Image…** | Upload `png`, `jpeg`, `webp`, `gif` for vision-capable models |
| **+ → Document…** | Upload `txt`, `md`, `csv`, `pdf`, `docx`; text is extracted server-side |
| **New chat** | Start a fresh conversation. Disabled while the current chat is still empty. |
| **Planning** | `auto`, `Always plan`, `Never plan` |
| **Model** | Only *configured* profiles. No free-text model ids. |
| **Context** | Opens a read-only popover. It never compacts the conversation. |
| **Permissions** | Ask / Approve safe actions / Custom permissions… |

`Enter` sends, `Shift+Enter` adds a line.

## Your conversations

Every chat appears under **RECENT CHATS** in the sidebar with its title and a
relative timestamp. The `⋯` menu offers Copy local link, Rename, Move to
project, Pin, Archive, and Delete.

**Search Chat** searches conversation titles *and* message text, and each result
offers *"Open conversation →"* to resume exactly where you left off.

**Sessions** is the complete record: every conversation with its turn count,
status, tags, and the governed events behind each turn.

## Attachments

Upload a document, then ask about it — the extracted text goes into the model's
context for that turn. Images go to vision-capable models as image blocks; a
profile without vision support has the image withheld before any provider
contact rather than silently dropped.

Attachment content never enters the durable event log — only the id, media type,
size, and hash.

## Approvals

When Raiker proposes a gated action, the reply says *"Your approval is needed to
continue"* with a **Review approval** link. **Approvals** shows the proposal —
for a file write, the exact unified diff — with the capability, risk, session,
and expiry.

Approving **records your decision; it does not run the action**
(`executes_action: false`). Filters (Pending / Approved / Denied) and sorting
(highest risk / newest) are on the same page.

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

Three things do not work yet. They are tracked in
[To be fixed](../plans/TO_BE_FIXED.md):

- **Markdown is not rendered (BUG-03).** Headings, tables, lists, and fenced
  code blocks appear as raw text.
- **No export (BUG-08).** There is no download, PDF, or print control, and an
  approved file write does not create a file on disk (BUG-06).

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
| Owner | "your configured price" | A rate you set yourself. Always wins. |
| Provider | "provider-reported" | Published by the provider's own API. OpenRouter does this; most do not. |
| Config | "list price, as of 2026-07" | A documented list price shipped in `config/model-profiles.json`. |

If none applies, the panel says no price is configured for that model rather
than showing `$0.00` — a zero always means "this was free", never "we do not
know". Costs are stored as counts, not money, so correcting a price re-prices
your history immediately.

Cache reads are billed at the full input rate here. Providers discount cached
input, so the figure is a deliberate slight over-estimate: a bill should never
surprise you in the expensive direction.

Automatic compaction at 90 % and weekly quota display remain specified but not
shipped — see
`docs/superpowers/plans/2026-07-26-chat-composer-context-controls.md`.
