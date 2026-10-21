# 06 Features and improvements

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

Features taken from the reference products (F01–F14), then product gaps found in
the review (F15–F23). Each adds behaviour without adding a page.

## First: the four that change everyday use

### QUI-F01 — Quick Entry (Hermes)

A global shortcut, Ctrl/Cmd+Shift+Space, opens a 560×120 floating window from
anywhere on the computer: one input and a "send to" picker (new chat or a recent
conversation). Esc closes it. Sending creates the task without bringing the main
window forward. Desktop app only. Hermes builds this as a separate minimal
window (`quick-entry`) that shares the main bundle.

### QUI-F02 — Clarifying questions as cards (Hermes)

A mid-task question arrives as a card: pick one, pick several, or type an
answer, with **Skip** and **Confirm and continue**, and "1 of 2" when there are
several. The answer goes back exactly as chosen. The status line reads "Waiting
for your answer". Hermes calls this *clarify*.

### QUI-F03 — Goals noticed in conversation (Muse)

When the same aim comes up across conversations, Raiker offers: "This looks like
an ongoing goal. Track it?" Once per aim, never again after Not now. Tracked
goals live in Work › Goals with their next step and feed Home's Continue and This
week. Depends on the goal contracts in
[PERSONAL_AUTONOMOUS_AGENT_SPEC.md](../PERSONAL_AUTONOMOUS_AGENT_SPEC.md) and
BUG-355 (goal intake from Chat).

### QUI-F04 — Live work line (Muse)

One line in the top bar while something runs, visible from every page: the real
current step ("Drafting reply to Anna · waiting for you"), or "2 tasks running"
with a menu. Clicking opens the task. Hidden when nothing runs.

## Trust, control and desktop polish

| ID | Feature | From | Raiker version | Lives in |
|---|---|---|---|---|
| QUI-F05 | Notifications by event | Hermes | Switches for Approval needed, Input needed, Response ready, Task failed, Background task finished; fire only while Raiker is in the background | Settings › Notifications |
| QUI-F06 | Schedule templates | Hermes | Start from "Morning brief", "Weekly inbox tidy", "Watch this page"; choose where results go: Home, a chat, or a connected channel | Work › Tasks › New |
| QUI-F07 | Named accounts per service | Hermes | "Work Gmail", "Personal Gmail"; approval cards always name the account | Connection detail |
| QUI-F08 | Approval time limit | Hermes | See [02, QUI-P06](02_PERMISSIONS_AND_APPROVALS.md#qui-p06--approval-time-limit) | Settings › Security |
| QUI-F09 | Undo what Raiker learned | Both | "What Raiker has learned to do" and "Approvals you've given", each with Undo | Memory › Controls |
| QUI-F10 | One confirmation, one loading style | Hermes | One "Are you sure" dialog (Enter confirms, Esc cancels); no bare "Loading…"; no invented progress | Design rules |
| QUI-F11 | Minimize to tray | Hermes | Hidden windows keep working; the tray icon shows a dot when a decision waits | Settings › General (desktop) |
| QUI-F12 | Separate chat text size | Hermes | Chat text size (default 110%) separate from interface size | Settings › Personalisation |
| QUI-F13 | Project in its own window | Hermes | Open a project in a second window | Project menu (desktop) |
| QUI-F14 | Companion on the desktop | Hermes | Later, opt-in, off by default: a small transparent window that reacts only to "needs your decision" and "done" | Settings › Personalisation |

Left out on purpose: achievements and badges (a Hermes plugin), the feed and
Ideas tab (Muse), window glass effects (Hermes), and asking for full-disk or
screen access during setup (Muse).

## Product gaps

### QUI-F15 — Library

Everything Raiker has made in one place: drafts, documents, images, charts
(pinned answer blocks), diffs and downloads. Filter by project and type; each
item opens the conversation it came from. A tab in Work and a section in each
project. Muse has a Files tab for the same reason.

### QUI-F16 — Task receipt

At the end of every task, one expandable line: model · approximate cost · what
was read · what changed or was sent, with the approval time · what left this
computer. For example: "Claude Sonnet · ≈ $0.04 · 2 files read · 1 email sent
(approved 10:41) · nothing else left this computer". This makes the governed
promise visible on every task. Built from the audit events the runtime already
records.

### QUI-F17 — Where your data goes, while typing

A quiet label in the composer: "Stays on this computer" or "Sent to Anthropic".
It updates as soon as the model changes or an attachment would leave. Uses the
existing inference-location logic (`web/src/lib/inferenceLocation.ts`).

### QUI-F18 — Make this repeatable

After a task goes well: **Save as routine**. Raiker writes the steps, the inputs
that change and the approvals needed; the owner reviews and saves; it can then be
scheduled (QUI-F06). Nothing is saved without sign-off.

### QUI-F19 — Undo windows

For actions that can be held (sending email, posting a message): "Sending in
10 s · Undo" in the status line. An addition to approval, not a replacement.

### QUI-F20 — Corrections become memory

When the owner says "that's wrong" or edits a draft, Raiker offers a memory
suggestion ("Remember: Anna prefers short replies?" Save · Dismiss).

### QUI-F21 — Projects hold everything

A project holds its chats, files, memories, schedules and its own permission
limits ("may push to this one repository only"). Choosing a project in the
composer sets all of it.

### QUI-F22 — One search for everything

Ctrl/Cmd+K searches chats, tasks, memories, Library items, settings and help,
with type filters. Slash commands in the composer (`composerCommands.ts`) show a
one-line description each.

### QUI-F23 — What's new

See [03, QUI-H04](03_WELCOME_HOME_AND_CHAT.md#qui-h04--whats-new).

## Order

F04, F01, F02, F03 first. Then F16, F17, F15, F18. Then the rest.
