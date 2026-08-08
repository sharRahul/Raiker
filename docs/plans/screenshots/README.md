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

`bug-50-*` are the live evidence for FIXED-100, captured on **2026-08-03** by
[`apps/web/e2e/bug-50-connection-cache-live.spec.ts`](../../../apps/web/e2e/bug-50-connection-cache-live.spec.ts)
against a running `raiker-web` made to serve 30 further instance workspaces
through `POST /api/instances` — the endpoint behind the login screen's instance
form. FIXED-100 bounds a connection cache, so its real measurement is the host
process's descriptor count rather than anything a browser can show; what these
record is the claim beside it, that a host which has served many instances is
unchanged for the owner using it.

| File | Records |
|---|---|
| `bug-50-host-before-many-instances.png` | The owner's Workbench on the host before it serves any of them |
| `bug-50-instance-creation-surface.png` | The login screen's instance form — the product surface behind the endpoint the run drives |
| `bug-50-host-after-many-instances.png` | The same Workbench after 30 more instance workspaces: every route still rendering, 0 console errors, status resolved from the database the cache was evicting around |

`b12-*` and `b17-*` are the live evidence for FIXED-101 and FIXED-102, captured
on **2026-08-04** by
[`apps/web/e2e/web-access-turn-control-live.spec.ts`](../../../apps/web/e2e/web-access-turn-control-live.spec.ts)
against a running `raiker-web` holding an owner-entered Anthropic credential and
answering live `claude-haiku-4-5-20251001` turns. The page the agent reads is
fetched from the real internet; that host was started with
`RAIKER_WEB_EGRESS_ALLOWLIST=pypi.org`, which is an owner setting and not a
shipped default — the allowlist ships empty.

| File | Records |
|---|---|
| `b12-web-fetch-withheld.png` | The first `web_fetch` call, refused with `gate_disabled` and the control that changes it |
| `b12-web-fetch-capability.png` | Permissions → Web fetch after the owner turned it on and set it to Allow |
| `b12-web-fetch-live-page.png` | The same request answering from a real page — the model quotes pypi.org's own summary of httpx back |
| `b12-web-fetch-egress-denied.png` | A host that is not on the owner allowlist, refused before any packet leaves the machine |
| `b17-turn-control-visible.png` | The composer while a turn streams: it becomes the turn's Stop and steer surface |
| `b17-steer-queued.png` | One instruction queued for the running turn, with what happens to it stated |
| `b17-steered-answer.png` | The model obeying the mid-turn correction — it answers **STEERED MIDTURN**, which was never in the original prompt |
| `b17-stop-requested.png` | Stop pressed mid-turn: a request applied at a safe boundary, never claimed as already done |
| `b17-turn-stopped.png` | The turn ended as **stopped** — a decision, not a failure — keeping what it had already produced |

`b9-*` is the live evidence for **FIXED-113** (GAP-BUILD B9 — the repository code
map), captured on **2026-08-08** by
[`apps/web/e2e/b9-repository-code-map-live.spec.ts`](../../../apps/web/e2e/b9-repository-code-map-live.spec.ts)
against a running `raiker-web` holding an owner-entered Anthropic credential and
answering live `claude-haiku-4-5-20251001` turns. Nothing here reaches the
network on the agent's behalf: the repository is a folder inside the workspace,
and the index is derived from it locally.

| File | Records |
|---|---|
| `b9-model-connected.png` | The credential added through Models, Haiku 4.5 selected |
| `b9-code-map-off-by-default.png` | The resting state — indexing off, Build saying so, and nothing to press |
| `b9-code-map-built-on-connect.png` | **Code map · ledger-app — 2 files, 3 declarations**, built by connecting the repository, with **Rebuild index** beside it |
| `b9-code-map-search-answer.png` | The gap itself, closed — *"`reconcile_meridian_ledger` is defined in `services/ledger.py` at lines 11–13"*, cited to the code map in the answer's own source ledger |
| `b9-code-map-gate-off.png` | The owner's off switch, quoted back verbatim by the model: `{"type": "code_map_gate_disabled", …}` |
| `b9-code-map-refreshed-after-write.png` | An approved `write_file`, then the same tool finding `audit_meridian_trail` in `services/audit.py` — the index caught up with the change the agent made |

`201`–`204` are the live evidence for **ADD-03** per-turn machine identity,
captured on **2026-08-08** by
[`apps/web/e2e/add-03-machine-identity-providers-live.spec.ts`](../../../apps/web/e2e/add-03-machine-identity-providers-live.spec.ts)
against an isolated real `raiker-web` on `127.0.0.1:8765`. Anthropic and
OpenRouter credentials were entered through the Models UI and closed before
screenshots; Ollama used the local `gemma4:31b-cloud` catalogue entry. All four
images were inspected at original resolution and contain no credential value.

| File | Records |
|---|---|
| `201-ADD-03-owner-agent-authority-live.png` | Permissions separates editable Owner controls from the signed turn's derived, read-only authority |
| `202-ADD-03-anthropic-identity-live.png` | A real Anthropic turn's issued/deactivated identity and machine-attributed audit rows |
| `203-ADD-03-openrouter-identity-live.png` | The same identity contract on a real OpenRouter turn |
| `204-ADD-03-ollama-identity-live.png` | The same identity contract on local Ollama `gemma4:31b-cloud` |
