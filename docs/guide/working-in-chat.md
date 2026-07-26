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

## Known limits

Three things do not work yet. They are tracked in
[To be fixed](../plans/TO_BE_FIXED.md):

- **No conversation memory (BUG-02).** Prior turns are shown on screen but are
  not sent to the model. Ask a follow-up question and Raiker will say it has no
  record of what you just told it. Put everything a turn needs into that turn.
- **Markdown is not rendered (BUG-03).** Headings, tables, lists, and fenced
  code blocks appear as raw text.
- **No export (BUG-08).** There is no download, PDF, or print control, and an
  approved file write does not create a file on disk (BUG-06).

## Context and token usage

The **Context** control shows what the current chat is using against the
selected profile's configured capacity — for example `16 / 200.0K (0%)`. It is
labelled **"Estimated from this chat's text"** because Raiker does not yet read
provider-reported prompt usage; the label is the honest source, not decoration.
A profile with no configured capacity says *"Context capacity is not configured
for this model"* rather than guessing.

Automatic compaction at 90 %, real provider token accounting, and cost/quota
display are specified but not shipped — see
`docs/superpowers/plans/2026-07-26-chat-composer-context-controls.md`.
