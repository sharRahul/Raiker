# Manual test evidence

Browser screenshots captured while executing
[the live manual test plan](../RAIKER_LIVE_MANUAL_TEST_PLAN.md) on
**2026-07-26** against a running `raiker-web` (Chromium, hosted Anthropic
`claude-haiku-4-5-20251001`), plus the focused B3 approval run on **2026-07-27**
against a disposable local workspace.

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
| `98`–`101` | FIXED-23: reviewed and executed exact edit plus unified patch |
| `102`–`104` | Focused re-check: Ollama `gemma4:31b-cloud` approved write and reloaded session-file chip |

No screenshot contains a credential: keys were entered into `type="password"`
fields and the response-redaction layer never returns a stored value.

`106-live-chat-model-picker.png` and `107-live-build-model-picker.png` record
the Playwright visual check for the shared provider-mark model menu, concise
model labels, and the per-model effort control.

`120`–`127` are the live evidence for FIXED-53 through FIXED-56, captured on
**2026-07-31** by
[`apps/web/e2e/chat-build-composer-bugs-live.spec.ts`](../../../apps/web/e2e/chat-build-composer-bugs-live.spec.ts)
against a real `raiker-web` on `127.0.0.1:8765` — the actual FastAPI runtime
serving the built SPA, not a route-mocked shell. No model provider was connected,
so every figure shown is the honest-gap path rather than a live model turn.

| File | Records |
|---|---|
| `120-BUG-21-pricing-registry-live.png` | Models → Pricing: exact model ids, source, all four rate components, effective dates, expanded price history, and per-provider sync state |
| `121-BUG-21-context-price-unknown-live.png` | The context popover on a model with no exact rate — no fabricated `$0.00` |
| `122-BUG-22-chat-conversation-menu-live.png` | Chat's conversation menu: Export conversation… and Print / Save as PDF |
| `123-BUG-22-build-conversation-menu-live.png` | The same menu in Build, in the same place |
| `124-BUG-23-code-block-controls-live.png` | A real stored transcript: language labels, Copy code, and locally-shipped highlighting |
| `125-BUG-24-parked-turn-live.png` | The Chat surface whose parked-turn continuation is driven by `/api/approvals/resumable` |
| `126-build-composer-parity-live.png` | Build's composer carrying the same context, conversation, and approval controls as Chat |
| `127-workbench-composer-parity-live.png` | The Workbench composer stating what it actually offers per work mode |
| `130-models-providers-tab-live.png` | Models → Providers: connect a provider and choose the exact model |
| `131-models-routing-tab-live.png` | Models → Routing: the fallback sequence and the advisor model |
| `132-models-posture-tab-live.png` | Models → Posture: the read-only off-machine gate status |
| `133-visual-refresh-workbench-{light,dark}.png` | BUG-37 token pass: depth ladder, tracking, scrollbars, focus halo — Workbench, both themes |
| `134-visual-refresh-models-{light,dark}.png` | The same pass on a dense table surface, both themes |

The Models page is split by action category — Providers, Routing, Pricing,
Posture — so each panel is one errand and a shareable location
(`#/models?tab=pricing`).

`197`–`200` are the live evidence for FIXED-92 and FIXED-93, captured on
**2026-08-02** by
[`apps/web/e2e/bug-44-47-live.spec.ts`](../../../apps/web/e2e/bug-44-47-live.spec.ts)
against two real `raiker-web` hosts. `197` and `198` come from a source checkout
holding an owner-entered Anthropic credential that answered a live
`claude-haiku-4-5-20251001` turn in the same run. `200` comes from a host started
**from inside a release artifact** built by `raiker-release`, with `PYTHONPATH`
and `RAIKER_INSTALL_ROOT` pointing at the extracted payload, so the code
answering is the artifact's own copy.

| File | Records |
|---|---|
| `197-BUG-47-local-result-under-ollama-live.png` | The Ollama row holding its own test result, and the llama.cpp and LM Studio rows holding none |
| `198-BUG-47-hosted-cards-keep-their-own-live.png` | Anthropic's own result under Anthropic; OpenAI, Gemini and OpenRouter unaffected |
| `199-BUG-44-source-checkout-live.png` | Host control → Install & updates on a source checkout: no signature claimed, no channel configured, no outbound request |
| `200-BUG-44-packaged-unsigned-build-live.png` | The same panel on a host running from a real release artifact: `0.1.0 · linux-x86_64`, reported as an **unsigned build** because that build did not run platform signing |
