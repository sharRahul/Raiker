# Manual test evidence

Browser screenshots captured while executing
[the live manual test plan](../RAIKER_LIVE_MANUAL_TEST_PLAN.md) on
**2026-07-26** against a running `raiker-web` (Chromium, hosted Anthropic
`claude-haiku-4-5-20251001`).

One exception, marked where it appears:
`working/83-FIXED-06-chat-markdown-rendered.png` is a Chromium render of the
shipped `Markdown.svelte` inside the chat bubble markup rather than a live model
turn — it was captured in an environment with no provider credential.

| Folder | Contents |
|---|---|
| [`working/`](working) | Verified behaviour — every surface that did what it claims |
| [`not-working/`](not-working) | Reproduced defects, one per file, named for its entry in [To be fixed](../TO_BE_FIXED.md) |

## not-working

| File | Defect |
|---|---|
| `BUG-01-context-window-NaN.png` | Context popover read `0 / NaN (NaN%)` — **fixed**, see `80-FIXED-…` and `81-FIXED-…` in `working/` |
| `BUG-02-no-conversation-memory.png` | The model denies having seen the previous turn in the same chat |
| `BUG-03-chat-markdown-not-rendered.png` | Headings, tables, and fenced code render as raw text — **fixed**, see `83-FIXED-…` in `working/` |
| `BUG-04-response-text-over-redacted.png` | Prose containing "secret" replaced with `***REDACTED***`; chat title became `***REDACTED***` — **fixed**, see `TO_BE_FIXED.md` FIXED-07 |
| `BUG-05-model-connect-raw-reason-code.png` | Connect failed with a bare reason code — **fixed**, see `82-FIXED-…` in `working/` |
| `BUG-06-approval-never-executes.png` | Approving a file write records the decision but writes no file |

## working — reading order

| Range | Covers |
|---|---|
| `01`–`03` | First run, workbench, every route |
| `04`–`16` | Models: connect, gate step-up, vault key, provider catalogue, selection |
| `17`–`28` | Chat turns, multi-chat behaviour, recent chats, search, sessions |
| `29`–`33` | Permissions and the approval lifecycle |
| `34`–`35` | All four task types |
| `40`–`52` | Extensions and Observability tabs, Projects, Memory, Brain |
| `53`–`57` | MCP server create, connect, and tool discovery |
| `55`–`56` | Runtime-mode activation |
| `60`–`65` | Theme, notification centre, STOP switch |
| `70`–`71` | Responsive layout at 375 / 768 / 1024 / 1440 px |
| `72`–`77` | Attachments and project creation |
| `80`–`83` | Verified fixes from the first round |
| `90`–`93` | Context and API-cost panel in Chat and Build; Models provider count and spend bars |

No screenshot contains a credential: keys were entered into `type="password"`
fields and the response-redaction layer never returns a stored value.
