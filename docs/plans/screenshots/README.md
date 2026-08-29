# Manual test evidence

Browser screenshots captured while executing
[the live manual test plan](../RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a
running `raiker-web` in Chromium. What each round found is written up in
[`../LIVE_TEST_ROUNDS.md`](../LIVE_TEST_ROUNDS.md); this directory is the
evidence those write-ups point at.

| Folder | Contents |
|---|---|
| [`working/`](working) | Verified behaviour — every surface that did what it claims. Round-stamped: a file here is evidence of what was true on the day its prefix names, and is **not** re-captured later, because a defect that no longer reproduces cannot be photographed again |
| [`not-working/`](not-working) | Reproduced defects, one per file, named for its entry in [To be fixed](../TO_BE_FIXED.md) |
| [`pages/`](pages) | The **current** state of every application page. Unlike the two above this folder is not an archive — it is re-captured in full by [`ui-sweep-responsive-live.spec.ts`](../../../apps/web/e2e/ui-sweep-responsive-live.spec.ts), so a file here is always the latest version and a stale one is a bug in the sweep |

## Current adaptive-shell catalogue — 2026-08-28

The mutable `pages/` catalogue contains 208 viewport-only PNG files:

```text
26 route/tab states × 4 display classes × 2 themes = 208
```

| Prefix | Viewport | Purpose |
|---|---:|---|
| `mobile-{light,dark}-` | 390 × 844 | Compact header and overlay navigation without squeezed content |
| `1080p-{light,dark}-` | 1920 × 1080 | Standard full-HD desktop reflow and focus canvas |
| `4k-{light,dark}-` | 3840 × 2160 | Bounded high-resolution workspace canvas |
| `8k-{light,dark}-` | 7680 × 4320 | Maximum declared display class without scaled controls or unbounded prose |

Each filename ends with the stable route/tab name, for example
`4k-dark-observe-diagnostics.png`. The live sweep sets the chosen theme before
application mount, checks the theme control state, waits for the page to settle,
parks the pointer away from hover targets, rejects console errors and horizontal
overflow, and reads the PNG header to prove its dimensions equal the viewport.
Tablet widths, the exact 1024-pixel breakpoint, and 1440-pixel desktop remain
automated layout assertions rather than additional committed screenshot classes.

**All 208 files were recaptured on 2026-08-28**, against a real host serving the
current build. Mobile and all three desktop classes were generated in the same
run, from the same build, so every image in `pages/` comes from one instance at
one moment. The sweep itself reads every PNG header and refuses a capture whose
dimensions do not exactly match its declared viewport.

They record the binary hide/show navigation model, direct Core routes,
collapsible Knowledge/Manage/Observe/Support groups, recent-first Search chats,
fixed desktop type and controls, the bounded reading/workspace/operational/
work-surface canvases, the managed document libraries on Memory and Projects,
Build's required project selector, the compact Skills list, and the channel
routing surface. The selected hub tab remains visible at mobile width even when
its strip scrolls.

The same run also exercises all seven Models tabs and all nine Settings sections
as rendered audit states. Those extra deep links are assertions rather than new
committed capture names, so the catalogue remains exactly 208 PNGs.

Only `pages/` is replaced by this sweep. `working/` and `not-working/` retain
round-specific evidence and must never be deleted during a catalogue refresh.

**Part of `working/` was pruned, and the write-ups still name what it held.**
Forty-seven captures from the 2026-07-26 → 2026-08-10 rounds were removed from
the repository to keep its size down. [Fixed items](../FIXED_ITEMS.md) still
records each filename, because the filename is the evidence record — but it
names them as plain text rather than as links, since a link to a file that was
deliberately removed reads as a broken document rather than a closed one. A
`working/` filename in a write-up that does not resolve here is one of those
forty-seven, not a missing capture.

## Rounds

| Prefix | Round | Provider |
|---|---|---|
| `real-work-` | **2026-08-29**, the first round that ends at facts outside the transcript: a scheduled task, a created project, a dashboard opened in a browser, and a program Build wrote that the round ran | Anthropic (`claude-haiku-4-5-20251001`) |
| `fixed-306-` | **2026-08-29**, the owner summarising a range through a chosen turn, with every turn still in the transcript afterwards | Anthropic (`claude-haiku-4-5-20251001`) |
| `fixed-305-` | **2026-08-28**, the last three lifecycle hook events in the catalogue, two of them fired by a real tool-using turn, and the turn-end event across four providers | Anthropic (`claude-haiku-4-5-20251001`), OpenAI, OpenRouter, local Ollama (`gemma4:31b-cloud`) |
| `pages/`, `fixed-299-`, refreshed `bug-225-` | **2026-08-28**, full responsive catalogue, owner skill commands in both composers, stored channel routes and exact approval-relay opt-in | Anthropic, OpenAI, OpenRouter and local Ollama, using credentials already managed through the interface |
| `r0825-` | **2026-08-25**, a semantic space built against a real embedding call and then measured, the retention sweep, task cadences, delegated-task ownership, tool rows after a reload, and a responsive sweep at 390/768/1024/1440/1920 | Anthropic, OpenAI, OpenRouter and Ollama, every key entered through the interface |
| `r0824-` | **2026-08-24**, what each capability switch actually decides, Agent Skills standard conformance on the Skills tab, and Auto's alignment check against a real turn | hosted Anthropic (`claude-haiku-4-5-20251001`) |
| `r0823-` | **2026-08-23**, the checkpoint rewind end to end, the audit export, and the Permissions surface after `network_execution` was deleted | hosted Anthropic, OpenAI, OpenRouter |
| `bug-221-`, `bug-223-`, `bug-225-` | **2026-08-22**, plugin contributions (skills, MCP-server offers), turn-end hooks across four providers, and the channel owner surface | hosted Anthropic, OpenAI, OpenRouter, local Ollama |
| `bug-219-` | **2026-08-22**, the fourth approval mode (*Decline, don't ask*) | hosted Anthropic |
| `r0821b-`, `r0821c-` | **2026-08-21**, Build composer and operating protocol; the Hooks tab | hosted Anthropic |
| `2026-08-21-` | **2026-08-21**, Memory, Brain, runtime and diagnostics at three viewport widths | hosted Anthropic |
| `r0817b-` | **2026-08-17 (second pass)**, eidetic capture wired into the runtime (MEM-04) and BUG-194's restart reattachment plus persistent environment | hosted Anthropic `claude-haiku-4-5-20251001`, connected through the product's own dialog |
| `r0817-` | **2026-08-17**, FTS4 → FTS5 (RAIKER-2025), the owner-selected recall backend (MEM-03), and background execution with a POSIX terminal (BUG-194) | hosted Anthropic `claude-haiku-4-5-20251001`, connected through the product's own dialog |
| `r0815-` | **2026-08-15**, the native OS sandbox | hosted Anthropic, OpenAI, OpenRouter, local Ollama |
| `r0810-` | **2026-08-10**, closing the 2026-08-08 round's four open defects plus BUG-82 | hosted Anthropic `claude-haiku-4-5-20251001` |
| `r0808-` | **2026-08-08**, the last full round | hosted Anthropic, all ten catalogue models |
| `01`–`207`, `b*`, `c*`, `bug*`, `add-*`, `skills-*` | 2026-07-26 → 2026-08-04 | hosted Anthropic `claude-haiku-4-5-20251001`, local Ollama `gemma4:31b-cloud` |

---

## The 2026-08-23 round

Six screenshots, prefix `r0823-`, driven through a real Chromium session against
`raiker-web --workspace . --port 8765`, signed in as the existing owner account
whose gates were all still at their per-account fail-closed defaults.

| File | Shows |
|---|---|
| `r0823-bug230-restore-preflight.png` | FIXED-270 — the restore preflight for a checkpoint with nothing after it. **Request this restore** is disabled and the panel says why: *"There is nothing to rewind, so there is nothing to approve."* |
| `r0823-bug230-preflight-with-files.png` | FIXED-270 / FIXED-275 — the same panel for a checkpoint that *does* have a captured mutation after it: **1 to rewrite**, the file named, and the acknowledgement gating the request. Before FIXED-275 this read zero, because the capture was filed under the API session |
| `r0823-bug230-restore-approval.png` | FIXED-270 — the approval a restore raises: the restore-specific notice (*"The restore captures its own pre-image first"*), and the per-file plan recomputed server-side rather than taken from the caller |
| `r0823-bug231-audit-export.png` | FIXED-271 / FIXED-276 — the audit log's **Export** panel with a produced export listed by event count and manifest hash, and the export itself in the log below it as *"Exported 271 audit events … redacted"* |
| `r0823-permissions-audit-export-row.png` | FIXED-272 — Permissions after `network_execution` was deleted, with **Audit export** expanded showing its real description, and **Checkpoint restore** grouped under Workspace instead of falling into *Other tools* |
| `r0823-bug234-mcp-protocol.png` | FIXED-274 — a locally built stdio MCP server after a real handshake, its card reading **PROTOCOL 2026-07-28**. Before this the client offered `2024-11-05` and nothing in the product said which revision it spoke |
| `r0823-bug238-unavailable-still-prompts.png` | FIXED-278 — the half that had to keep working. A model marked `authentication_failed` still blocks **Send**, names *"The provider rejected the credential"*, and offers **Set up model**. A model whose check merely aged out gets none of that |
| `r0823-mobile-audit-export.png` | The export panel at 390 × 844. Fourteen routes were swept at that width with zero horizontal overflow |

---

## The 2026-08-17 round, second pass

Two screenshots, prefix `r0817b-`, from
[`apps/web/e2e/mem04-bug194-observations-live.spec.ts`](../../../apps/web/e2e/mem04-bug194-observations-live.spec.ts),
against a fresh workspace with the Anthropic credential entered through
Raiker's own connect dialog.

| File | Shows |
|---|---|
| `r0817b-01-memory-observations-captured.png` | FIXED-237 — Memory's **Observations** section after a real governed turn read a real file. This is the exact query MEM-04 reproduced with: before this change the count was zero on every workspace, and here the page reads **1 captured · 0 not captured** with the row's retention, expiry and checksum beside it |
| `r0817b-02-runtime-environment-capabilities.png` | FIXED-238 / FIXED-239 — Settings → Runtime stating what each boundary really does between commands, built from the backend's own capabilities. **Local strict** carries *Runs work in the background* and *Survives a Raiker restart*; the native sandbox carries neither and gets no reset control at all |

The whole `pages/` sweep was re-captured in the same round, with zero console
errors across all 23 pages.

**On re-capturing the other two folders.** `pages/` is the folder that is meant
to be replaced wholesale, and it was. `working/` and `not-working/` are not
refreshable in the same way and deliberately so: a `working/` file is evidence
of what was true on the day its prefix names, and 110 links in
[`FIXED_ITEMS.md`](../FIXED_ITEMS.md) and [`TO_BE_FIXED.md`](../TO_BE_FIXED.md)
cite specific files there; a `not-working/` file photographs a defect, and a
defect that has since been fixed cannot be photographed again. Replacing either
folder would delete the evidence those documents read against and leave the
claims uncheckable. New rounds therefore *add* their prefix rather than
replacing what came before.

---

## The 2026-08-17 round

Five screenshots, prefix `r0817-`, captured against fresh workspaces. The first
three come from
[`apps/web/e2e/fts5-mem03-bug194-live.spec.ts`](../../../apps/web/e2e/fts5-mem03-bug194-live.spec.ts),
with the Anthropic credential entered through Raiker's own connect dialog rather
than an environment variable; the last two are the Knowledge Map, from
[`knowledge-map-work-live.spec.ts`](../../../apps/web/e2e/knowledge-map-work-live.spec.ts)
and
[`reference-graph-live.spec.ts`](../../../apps/web/e2e/reference-graph-live.spec.ts).

| File | Shows |
|---|---|
| `r0817-01-memory-recall-backend.png` | FIXED-230 — Memory's **Recall backend** card naming the embedding space recall searches, and saying in one sentence that this one matches words rather than meaning |
| `r0817-02-anthropic-connected-via-ui.png` | The provider connected and its pinned model reporting reachable, from the credential typed into the product |
| `r0817-03-chat-search-bm25-ranked.png` | FIXED-231 — chat search answered by the FTS5 index, each hit carrying a snippet quoting the matched term |
| `r0817-04-knowledge-map-work-graph.png` | FIXED-235 — the Knowledge Map's filter row naming the owner's own material, where it once listed six types for a graph that was mostly event rows |
| `r0817-05-knowledge-map-unresolved-reference.png` | FIXED-236 — a cited file that has since been deleted, drawn hollow with a dashed outline and reading **Missing** in the inspector. Before the fix it was indistinguishable from a file still on disk |

The whole `pages/` sweep was re-captured in the same round, with zero console
errors across all 23 pages.

**Removed in this round.** `03-route-*.png` — an early fifteen-file route sweep
whose successor is `pages/`, which is now re-captured every round. Nothing else
was deleted: the rest of `working/` is round-stamped per-defect evidence that
[`FIXED_ITEMS.md`](../FIXED_ITEMS.md) reads against, and a defect that has been
fixed cannot be re-photographed.

---

## The 2026-08-10 round

Ten screenshots, prefix `r0810-`, captured by
[`apps/web/e2e/bug-68-71-73-82-live.spec.ts`](../../../apps/web/e2e/bug-68-71-73-82-live.spec.ts)
against a fresh workspace. Each one is the "after" for a defect the 2026-08-08
round left open; the "before" is named beside it in
[To be fixed](../TO_BE_FIXED.md).

| File | Shows |
|---|---|
| `r0810-bug68-context-meter-real-io-counts.png` | FIXED-154 — the context popover reading `326 input · 5 output` where it read `NaN input · NaN output` |
| `r0810-bug70-build-auto-changes-nothing-standing.png` | FIXED-155 — **Auto** selected, reporting what the owner's standing permissions actually allow, with **Change in Permissions →** |
| `r0810-bug70-permissions-unchanged.png` | FIXED-155 — Permissions after a full Plan → Edit → Auto cycle, every capability still where it was |
| `r0810-bug70-plan-mode-refuses-the-write.png` | FIXED-155 — a Build turn in **Plan** asked to write a file, refused by the runtime with no approval raised |
| `r0810-bug71-memory-says-the-gate-is-off.png` | FIXED-156 — Memory stating the gate is off instead of promising proposals it cannot produce |
| `r0810-bug71-memory-says-the-gate-is-on.png` | FIXED-156 — the same page once **Memory store** is enabled |
| `r0810-bug71-chat-proposes-a-memory-write.png` | FIXED-156 — a Chat turn proposing `memory_write`, and FIXED-157's parked-state wording in the same bubble |
| `r0810-bug73-approval-waiting.png` | FIXED-157 — the approval the parked turn is waiting on |
| `r0810-bug73-parked-turn-states-its-state.png` | FIXED-157 — the parked conversation after a reload, with no claim that nothing ran |
| `r0810-bug82-advisor-readiness.png` | FIXED-158 — the advisor selector carrying a readiness chip, the exact model, and **Check advisor** |

---

## The 2026-08-08 round

158 screenshots, prefix `r0808-`. Reading order:

| Range | Covers |
|---|---|
| `01`–`02c` | First run, registration, reload behaviour, sign-in as an existing owner |
| `03-route-*`, `03-tab-*` | All 14 routes and all 22 hub tabs, 0 console errors each |
| `04`–`08` | Models: the Connect dialog, a real key, the live catalogue, pinning a model |
| `09`–`19` | Chat: composer inventory, a live streamed turn, context memory, the context/cost popover, the model picker, the ten-model sweep, the unconfigured-provider path |
| `20`–`26` | Permissions: 67 gates, search, an expanded row, the step-up dialog, 16 gates enabled, the deferred domains |
| `27`–`38` | The approval lifecycle: proposal → inbox → detail with diff → execute → the file on disk → the resumed turn |
| `39`–`43` | Conversation actions, Markdown → PDF, the PDF inspector, Export conversation in HTML / Markdown / PDF |
| `44`–`47` | Attachments: the menu, a document reaching the model, an image described |
| `48`–`49` | Chat search over titles and message text |
| `50`–`53` | All four task types, created and run |
| `54`–`59` | MCP: create, connect, discover, raise the decision mode, call the tool from Chat |
| `60`–`64` | Build: the repository connector, code-map build, `code_map_search`, the mode chips |
| `65`–`66` | Projects |
| `69`–`72` | Memory and Knowledge Map, and the memory tools actually offered to a turn |
| `73` | Observability's seven tabs on real data |
| `74` | Settings' six tabs |
| `75`–`79` | Theme cycle, notification centre, STOP switch, Host control |
| `80`–`81` | Responsive layout at 375 / 768 / 1024 / 1440 px, and the drawer |
| `82`–`83` | Extensions tabs (including the new Skills tab) and the Workbench |
| `84`–`86` | Web fetch withheld at `ask`, the `update_plan` checklist, `spawn_subagent` |

### not-working — the 2026-08-08 defects

| File | Defect |
|---|---|
| `BUG-r0808-01-context-popover-NaN-io-tokens.png` | **BUG-68** — the context meter reads `NaN input · NaN output` |
| `BUG-r0808-02-post-approval-answer-says-not-executed.png` | **BUG-73** — a resumed turn denies an execution that happened |
| `BUG-r0808-03-build-chip-set-file-writes-auto-without-stepup.png` | **BUG-70** — Build's Auto chip set File writes to Auto globally, with no step-up |
| `BUG-r0808-04-memory-store-capability-has-no-executor.png` | **BUG-71** — "Memory store" can be enabled but nothing can ever write a memory |
| `BUG-r0808-05-fresh-workspace-defaults-to-absent-ollama.png` | **BUG-69** — a pristine workspace presents an unreachable model as ready |
| `BUG-r0808-05-models-claims-one-provider-set-up.png` | **BUG-69** — "1 of 10 providers set up" with nothing reachable |
| `BUG-r0808-05-first-turn-raw-reason-code.png` | **BUG-69** — the first message ever sent fails with a bare reason code |
| `BUG-r0808-06-web-fetch-turn-fails-with-raw-reason-code.png` | **BUG-72** — enabling Web fetch broke every turn that used it. Closed by **FIXED-142**; kept as the record of the reported failure |

No screenshot contains a credential: keys were entered into `type="password"`
fields and the response-redaction layer never returns a stored value.

---

## Earlier rounds

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

`b12-*` and `b17-*` are the live evidence for FIXED-101 and FIXED-102, and were
re-captured on **2026-08-10** as the evidence for FIXED-142 and FIXED-143 — the
same six scenarios, run again once a tool call stopped occupying the event loop
and once the spec could reach the provider cards again. Originally captured on
**2026-08-04** by
[`apps/web/e2e/web-access-turn-control-live.spec.ts`](../../../apps/web/e2e/web-access-turn-control-live.spec.ts)
against a running `raiker-web` holding an owner-entered Anthropic credential and
answering live `claude-haiku-4-5-20251001` turns. The page the agent reads is
fetched from the real internet; that host was started with
`RAIKER_WEB_EGRESS_ALLOWLIST=pypi.org`, which was an owner setting and not a
shipped default — the allowlist shipped empty. **That variable no longer exists:
web egress now answers to an owner blocklist plus a non-optional
public-address guard (`raiker/runtime/web_policy.py`), so a run reproducing this
evidence today needs no egress variable at all.** The screenshots are kept as the
record of what was observed on the day, not as current instructions.

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

`201`–`207` are the live evidence for **ADD-03** per-turn machine identity,
captured on **2026-08-08** by
[`apps/web/e2e/add-03-machine-identity-providers-live.spec.ts`](../../../apps/web/e2e/add-03-machine-identity-providers-live.spec.ts)
against an isolated real `raiker-web` on `127.0.0.1:8765`. Anthropic and
OpenRouter credentials were entered through the Models UI and closed before
screenshots; Ollama used the local `gemma4:31b-cloud` catalogue entry. All seven
images were inspected at original resolution and contain no credential value.

| File | Records |
|---|---|
| `201-ADD-03-owner-agent-authority-live.png` | Permissions separates editable Owner controls from the signed turn's derived, read-only authority |
| `202-ADD-03-anthropic-identity-live.png` | A real Anthropic turn's issued/deactivated identity, with literal event actors and contextual turn identities shown separately |
| `203-ADD-03-openrouter-identity-live.png` | The same identity contract on a real OpenRouter turn |
| `204-ADD-03-ollama-identity-live.png` | The same identity contract on local Ollama `gemma4:31b-cloud` |
| `205-ADD-03-anthropic-approval-attribution-live.png` | Anthropic proposed a governed file write as the machine actor; the human owner denied it |
| `206-ADD-03-openrouter-approval-attribution-live.png` | OpenRouter proposed a governed file write as the machine actor; the human owner denied it |
| `207-ADD-03-ollama-approval-attribution-live.png` | Ollama proposed a governed file write as the machine actor; the human owner denied it |


## BUG-69 closure — 2026-08-09

All seven images were reviewed at rendered resolution and contain no credential
value.

| File | Records |
|---|---|
| `208-BUG-69-first-run-model-setup-live.png` | Fresh-owner provider/local setup prompt and acquisition choices |
| `209-BUG-69-workbench-readiness-gate-live.png` | No-model Workbench state with disabled Start build and Models remedy |
| `210-BUG-69-openrouter-ready-live.png` | Exact OpenRouter readiness and a governed turn parked for approval |
| `211-BUG-69-anthropic-account-block-live.png` | Authenticated catalogue but refused execution account, with draft preserved and Send disabled |
| `212-BUG-69-local-library-live.png` | Approved-root GGUF discovery with name, architecture, quantization, and Deploy |
| `213-BUG-69-huggingface-catalogue-live.png` | Live Hub results with immutable revision, licence, format, size, and GGUF variant choices |
| `214-BUG-69-huggingface-download-deploy-live.png` | A tiny immutable Hub GGUF downloaded into an approved root and the newest managed llama.cpp deployment completed |

## BUG-69 reference-platform parity review — 2026-08-09

A second live round on a fresh workspace, driving the Models UI with a real
Anthropic key entered only through the connect dialog. Both images were reviewed
at rendered resolution and contain no credential value. The key holds no credit,
which is what makes it an exact fixture for `quota_exhausted`: the catalogue call
succeeds and every inference call is refused for billing.

| File | Records |
|---|---|
| `bug69-models-quota-readiness-live.png` | FIXED-138 and FIXED-140 — the card reads **No credit** after Test ran the exact-model readiness check, the headline reads **0 models ready · 1 of 10 connected**, and every other card carries its own state chip |
| `bug69-chat-quota-readiness-live.png` | The same verdict on the Chat surface: the billing sentence, the draft preserved, and Send disabled |

## Models information architecture — 2026-08-09

The Models page split by where a model comes from, replacing the single
Providers scroll. Same live workspace as the round above.

| File | Records |
|---|---|
| `bug69-models-tab-local-live.png` | The Local tab: readiness and the global default above the strip, then runtime install/pull, the on-device runtimes, and the GGUF library |
| `bug69-models-tab-hosted-live.png` | The Hosted tab: provider accounts and advanced routers only, with no local runtime or installer in sight |
| `bug69-models-tab-huggingface-live.png` | The Hugging Face tab: search-first download and conversion |
| `bug69-models-tab-local-375-live.png` | The Local tab at 375 pixels — the strip and panel stay above the fold, no horizontal page overflow |

## Several local models and a model per surface — 2026-08-09

| File | Records |
|---|---|
| `bug69-local-llama-slots-live.png` | The Local tab listing four managed llama.cpp slots as separate selectable models |
| `bug69-surface-default-build-live.png` | Build holding its own model (Local GGUF 4) while Chat holds another (Local GGUF 2), after a reload and a fresh sign-in |

## Known-limits round — 2026-08-10

A fresh isolated workspace driven through the production build in real Chromium
with one Anthropic credential entered only through the Models connect dialog. All
eleven images were reviewed at rendered resolution and contain no credential
value.

| File | Records |
|---|---|
| `round0810-01-first-run-model-setup.png` | The first-run "Choose how to run models" sheet on a brand-new owner |
| `round0810-02-code-split-routes-mount.png` | FIXED-161 — the last of the eleven code-split destinations mounted with content and no console error |
| `round0810-03-plugin-signing-posture.png` | FIXED-166 — the workspace signing posture stated in words, naming both variables that would raise it, and saying installs are unaffected |
| `round0810-04-capability-containment.png` | FIXED-164 — **Monitored capabilities** on an empty workspace: what is watched, and that nothing has failed often enough to appear yet |
| `round0810-05-readiness-window-setting.png` | FIXED-169 — the readiness window at 30 minutes after **Save changes**, with its bounds and what still invalidates a check regardless |
| `round0810-06-model-activity.png` | FIXED-162 — the durable operations surface, stating that failed work is never silently retried |
| `round0810-07-anthropic-connected.png` | Anthropic connected through the UI, with the model pinned from the live catalogue |
| `round0810-08-readiness-chip-confirmed.png` | FIXED-169 — `Ready · confirmed just now`, naming the exact model the provider reached, and **1 model ready** |
| `round0810-09-live-turn-answered.png` | FIXED-133 — a live Haiku 4.5 turn answering with the exact requested marker, no raw reason code anywhere |
| `round0810-10-contained-subject.png` | FIXED-163 — a connector contained after three consecutive failures, with its reason, streak, last failure code, the matching high-severity finding above it, and a **Resume** control |
| `round0810-11-containment-resumed.png` | FIXED-163 — the same subject back to active after one press, offering **Pause** and **Stop** again |

## Multi-provider usage and compaction round — 2026-08-11

Captured from an isolated production-build workspace. Anthropic, OpenAI, and
OpenRouter credentials were entered only through Models; Ollama used the local
`gemma4:31b-cloud` connection. Credential dialogs were closed before every
capture. The managed server could not obtain outbound network access, so the
hosted screenshot records the genuine fail-closed readiness result rather than
claiming a hosted turn succeeded.

| File | Records |
|---|---|
| `bug-52-chat-refusal-does-not-end-the-turn.png` | BUG-53 — two successive model answer passes remain separate paragraphs after a first-pass tool refusal |
| `round0811-ollama-live-turn.png` | A real Ollama turn answering the exact requested marker through Chat |
| `round0811-hosted-provider-readiness.png` | Anthropic, OpenAI, and OpenRouter connected with their exact pinned models retained after restart, each honestly marked **Unreachable** in this network-restricted run |
| `round0811-provider-usage-connected.png` | All four connected providers only; Raiker-observed and provider-reported sources separated; genuine provider API limitations stated; persisted owner budgets; Ollama at 5,405 tokens and one request with no API cost |
| `round0811-provider-usage-top.png` | The ordinary 1600 × 900 Activity viewport with the rolling seven-day headline and live Ollama ledger row |
| `round0811-provider-usage-compact.png` | The settled 900 × 700 Activity layout after the tablet Menu/title overlap fix, with no horizontal page overflow |

All retained images were inspected at rendered resolution and contain no
credential value.
