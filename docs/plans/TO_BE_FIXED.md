## Goal

Make Raiker a secure AI product that combines an AI assistant, a governed AI
agent, and an extensible agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a platform, Raiker should
provide the governed runtime foundation for models, tools, plugins, interfaces,
memory, approvals, audit events, checkpoints, and integrations.

Raiker must support user-owned model choice across LLM backends — local models
such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM;
private-network providers; and hosted API providers such as Anthropic, OpenAI,
Gemini, and OpenRouter. No model, interface, plugin, or capability should
bypass governance. Every action must remain policy-aware, observable,
auditable, approval-driven where required, human-governed, user-controlled, and
fail-closed by design.

## Security posture (read before adding any restriction)

Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
Security is not restricting the user; it is a frictionless system that lets the
owner operate securely without having their access taken away. Do **not** put a
hard block in front of the owner's legitimate choices (e.g. connecting a remote
MCP server) by default — **allow, monitor, surface anomalies as findings +
notifications, and give the owner an instant stop plus an automatic revocable
pause for the irreversible/high-severity cases.** Reserve hard prevention for a
last resort and justify it against this posture. Full statement:
`docs/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Every deferred item found by the FIXED-01 through FIXED-48
audit is an explicit BUG with a required user-interface outcome, so closing
backend work cannot leave an invisible or misleading product surface.

**Closed entries live in [`FIXED_ITEMS.md`](FIXED_ITEMS.md).** They are still
evidence — what was observed, the root cause, and the user-interface outcome that
had to be true before it could be called closed — but they are no longer mixed in
with the open work, so this document answers one question: what is left.

docs/GAP_BUILD_CHAT.md — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

| ID | Severity | Area | Status |
|---|---|---|---|
| BUG-46 | Medium | Storage / Windows locked memory | Open (found while verifying FIXED-91) |
| BUG-48 | Medium | Distribution / setup wizard and native tray | Open (split out of BUG-44) |
| BUG-49 | Low | CI / release workflow action pinning | Open (found while building the release workflow) |
| BUG-51 | Low | Policy / dead `denied_actions` configuration | Open (found while implementing B6/B7) |
| BUG-53 | Low | Chat / multi-call answer text runs together | Open (found while verifying FIXED-99) |
| BUG-54 | Medium | Web e2e / the live stub model is not in the repository | Open (found while writing FIXED-99's live scenario) |
| BUG-55 | Low | Chat / a disabled transcript block reads as live code | Open (found while verifying FIXED-99) |
| BUG-59 | Low | Runtime / a governed refusal names a page that does not exist | Open (found while verifying FIXED-103) |
| BUG-60 | Low | Chat / a withheld call is narrated by the model, not disclosed | Open (found while verifying FIXED-103) |
| BUG-64 | Low | Chat / a task the agent creates is queued for a run nobody asked for | Open (found while verifying FIXED-106) |
| BUG-65 | Low | Export / a transcript keeps citation markers it cannot resolve | Open (found while verifying FIXED-107) |
| BUG-88 | Low | Web / the API rate limit is easy to trip with ordinary navigation | Open (found while running the 2026-08-10 live round) |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B9, B11, B12, B17 complete; 10 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (14 items remain) |

---

## BUG-46 — SQLCipher cannot lock key-bearing pages on this Windows host

**Status: open; found while verifying FIXED-91.**

**Observed.** The Windows SQLCipher wheel repeatedly reports
`sqlcipher_mlock: VirtualLock() returned 0 LastError=1453` while opening test
workspaces. Database encryption, reads, writes, and key-cache invalidation all
pass, so this is not an at-rest confidentiality or correctness failure. It does
mean SQLCipher could not prove that key-bearing memory stayed out of the page
file on this host.

**Required fix.** Reproduce on clean supported Windows 10 and 11 runners, record
the installed wheel/SQLite build and process memory-lock limits, and either ship
a SQLCipher build whose secure-memory lock succeeds or surface a durable degraded
posture with an actionable platform remedy. Do not suppress the warning unless a
test proves key pages are locked.

**UI when closed.** Settings → Security reports database encryption and locked
memory separately. A host whose key pages cannot be locked says **Degraded** and
links to the precise remediation; a healthy host says **Locked in memory**.

---

## BUG-48 — There is still no setup wizard and no native tray icon

**Status: open; split out of BUG-44 (see FIXED-92).**

**Observed.** FIXED-92 makes a signed release buildable and an update
verifiable, and FIXED-88 put the tray control's *behaviour* in the top bar. Two
rows of `docs/DESKTOP_DISTRIBUTION_DESIGN.md` are still specification. The
**First-run experience** section describes a wizard that creates the instance,
selects or defers a model, explains local/hosted privacy and tests the
connection, chooses a backup target, and then opens the workspace — none of it
exists as a guided flow; a new owner meets the login screen and finds the rest.
And the tray/menu-bar icon itself needs a packaged binary with a platform GUI
toolkit, which no artifact currently contains.

**Required fix.** A first-run wizard in the web app, entered automatically on an
instance that has never completed setup, whose every step is skippable and whose
model step can defer. Then a native tray/menu-bar binary per platform, bundled
into the installers FIXED-92 builds, whose only unique action is **Open Raiker**
— every other action already exists in the Host control and must call the same
`/api/host/*` routes rather than growing a second implementation.

**UI when closed.** A non-technical owner installs Raiker, is walked through
creating an instance and connecting or deferring a model without ever seeing a
terminal, and afterwards finds Raiker in the tray/menu bar with its state and
Pause / Restart / Quit.

---

## BUG-49 — Two release-workflow actions are pinned by tag, not by digest

**Status: open; found while building `.github/workflows/release.yml`.**

**Observed.** Every other action in this repository is pinned to a commit SHA.
`actions/upload-artifact` and `actions/download-artifact` in
`.github/workflows/release.yml` are pinned to `@v4`, because the commit digests
could not be resolved from the environment the workflow was written in. A tag is
mutable: whoever controls it can change what those steps run, and those steps
handle the release artifacts.

**Required fix.** Resolve both actions' commit digests and pin them, with the
version in a comment beside each, exactly as `actions/checkout`,
`actions/setup-python` and `actions/setup-node` are pinned. Then check no other
workflow has acquired a tag pin.

**UI when closed.** None — this is supply-chain hygiene for the pipeline that
produces what owners install.

---

## BUG-51 — `denied_actions` is dead policy configuration

**Status: open; found while implementing B6/B7.**

**Observed.** `raiker/policy/config.py::StaticPolicyConfig.denied_actions` is
never read by `PolicyEngine` or anything else. It lists `write_file`,
`edit_file`, `delete_file`, `network_request`, `web_fetch`, `plugin_execute`,
`remote_execute`, `process` and `network` — a set that reads like a hard block
and enforces nothing. A reviewer auditing the policy layer would reasonably
conclude that file writes are denied outright.

**Required fix.** Either delete the field, or make it authoritative and
reconcile it with `approval_required_actions` (which currently governs those
same tools). Do not leave a third policy set that looks load-bearing and is not.

**UI when closed.** No user-visible change; this is an auditability defect.

---

## BUG-53 — A multi-call turn's answer text runs together in Chat

**Status: open; found while verifying FIXED-99.**

**Observed.** A turn in which the model speaks more than once — every turn that
calls a tool and then answers — renders as one unbroken paragraph with no space
between the two utterances:

> Reading ../escape.md and listing the workspace.I could not read ../escape.md —
> policy refused that one call…

`working/bug-52-chat-refusal-does-not-end-the-turn.png` shows it.

**Root cause.** `collectText` in `apps/web/src/lib/turnPhases.ts` joins every
streamed `text_delta` with `""`, which is right *within* one model response and
wrong *between* two of them: the deltas of the second response begin a new
sentence, and nothing marks the seam.

**Required fix.** Separate the text of successive model responses in a turn —
either by paragraph, matching how the model itself wrote them, or by carrying a
response boundary through the stream so `collectText` can break on it. Do not
insert whitespace blindly between deltas; inside one response that would break
words in the middle.

**UI when closed.** A turn that reads a file and then answers reads as two
statements rather than one run-on sentence, in Chat and in Build.

---

## BUG-54 — The live end-to-end stub model is not in the repository

**Status: open; found while writing FIXED-99's live scenario.**

**Observed.** Two live specs —
[`e2e/add-02-batched-approval-queue-live.spec.ts`](../../apps/web/e2e/add-02-batched-approval-queue-live.spec.ts)
and [`e2e/bug-52-first-pass-denial-live.spec.ts`](../../apps/web/e2e/bug-52-first-pass-denial-live.spec.ts)
— name `python <scratch>/stub_model.py` as a prerequisite. That file exists only
in the scratch directory of the session that wrote each spec, so neither
scenario can be re-run by anyone else, and the exact batch each one asserts on
is recorded nowhere but in prose.

**Why it matters.** These two specs are the evidence behind ADD-02 and FIXED-99.
Evidence that cannot be reproduced is a claim. Every other live spec drives a
real provider the reader can also connect; these two do not, and the thing that
replaces the provider is missing.

**Required fix.** Commit the stub under `apps/web/e2e/` (or `scripts/`) as a
checked-in fixture with its own README line, and point both specs at it by
repository path. It is a local, loopback-only HTTP server with no credential and
no network, so it introduces no new boundary — it is the *input* to the run, and
it belongs beside the specs that depend on it.

**UI when closed.** None — this is reproducibility of the evidence behind two
entries in this document.

---

## BUG-55 — A disabled block in the Chat transcript reads as live code

**Status: open; found while verifying FIXED-99.**

**Observed.** `apps/web/src/lib/views/ChatView.svelte` wraps roughly ninety lines
of the transcript — a phase line, an answer paragraph, an error line, a response
metadata row and a **complete second approval card** — in `{#if false}`. All of
it is dead. The live approval card is a separate, later block, and the two say
different things: the disabled one tells the owner to "Review it in the Approvals
inbox", while the live one carries the batch position, the cross-tab resume state
and the **Continue now** control.

**Why it matters.** Someone changing the approval copy will reasonably edit the
first card they find and see no change in the product; a reviewer auditing what
Chat tells an owner about a governed action will read the wrong text. It is the
same failure mode as BUG-51 — configuration that looks load-bearing and is not.

**Required fix.** Delete the disabled block, or, where a fragment is genuinely
being kept for a planned redesign, move it out of the component and say so.
Nothing that renders governance copy should exist twice with two different
wordings.

**UI when closed.** No user-visible change; this is a maintainability and
auditability defect.

---

## BUG-59 — A governed refusal sends the owner to a page that does not exist

**Status: open; found while verifying FIXED-103.**

**Observed.** With the `web_fetch` gate off — the shipped default — the refusal
in `raiker/runtime/web_access.py:309` reads:

> Web fetch denied: the web_fetch capability gate is disabled (fail closed).
> **Enable it in Settings → Capabilities.**

There is no Capabilities section under Settings. The control is its own
destination, **Permissions** (`#/capabilities`, labelled `Permissions` in
`apps/web/src/lib/nav.ts`), and Settings is a separate one. `working/bug-58-web-fetch-withheld.png`
and `working/bug-58-web-search-unconfigured.png` show the owner being sent
there, in the model's own words.

**Why it matters.** This is FIXED-01's defect in miniature and the reason
FIXED-101 promised "a withheld call tells the owner *which control* would change
it". Naming the wrong control is worse than naming none: the owner goes to
Settings, does not find it, and concludes the gate cannot be turned on from the
app. It is the only route-naming string of its kind in the runtime, so the fix is
one line — but the same string is what the model reads and relays, so it is also
the only thing standing between the refusal and the owner acting on it.

**Required fix.** Name the destination the product ships: **Permissions**. A
test should assert the refusal text against the nav's own label rather than a
hand-written string, so a future rename cannot re-open this.

**UI when closed.** A withheld web call names Permissions, and following it
reaches the control that changes the outcome.

---

## BUG-60 — A withheld tool call is narrated by the model, not disclosed by the runtime

**Status: open; found while verifying FIXED-103.**

**Observed.** FIXED-99 added `model_tool_call_refused` and, with it, Chat's
**Policy refused one call in this turn** card, so an owner watching a transcript
learns of a refusal from the runtime rather than from the model's goodwill. A
*withheld* governed result — the `web_gate_disabled` and
`web_search_not_configured` refusals above — does not travel that path. It comes
back as an ordinary tool result, so no card renders and the only thing that told
the owner anything in `working/bug-58-web-fetch-withheld.png` is that the prompt
had explicitly asked the model to report what the tool returned. A model that
answered "I couldn't reach that page" would have left a governed refusal with no
disclosure anywhere in the conversation.

The same screenshot shows the second half: because the model quotes the tool's
JSON payload verbatim, the owner reads `Settings → Capabilities` — the
escape sequence, not the arrow. The payload is serialised with `ensure_ascii`
and nothing between the tool and the bubble un-escapes it.

**Why it matters.** The distinction between "denied by policy" and "withheld by a
gate" is one the runtime makes internally and the owner has no reason to know.
Both are the product refusing on the owner's behalf, and FIXED-99's argument —
that a refusal only the model can see is a refusal that can silently disappear —
applies to both.

**Required fix.** Emit the same streamed refusal event for a withheld governed
tool result, so Chat and Build disclose it the way they disclose a policy denial;
and render tool-result text as text, so an owner never reads a `\uXXXX` escape.

**UI when closed.** A withheld call raises the same **Policy refused** card as a
denied one, naming the tool and its reason, whatever the model chooses to say.

---

## BUG-64 — Approving a proposed task also schedules a turn nobody asked for

**Status: open; found while verifying FIXED-106.**

**Observed.** Approving a **Create task** proposal creates the task and leaves it
**queued** for immediate execution: `working/bug-62-task-in-tasks.png` shows the
new row already *queued* and *"Scheduled for 8/4/2026, 2:48:11 PM"* — the moment
it was approved. `DashboardService.create_task` stamps `scheduled_at = utc_now()`
for any task with no explicit time ("an unscheduled task is work requested now"),
and `TaskScheduler.run_due` claims it on the resident host's next tick and runs
it as a governed agent turn.

**Why it matters.** It is the right default for **Tasks → Plan work**, where the
owner is deliberately asking for work to start. It is a different thing when the
decision on screen says *"Approving this creates the task above in Tasks, once"*:
the owner approves a **creation** and gets a **run**. Nothing escapes governance
— the run's own tool calls are brokered exactly as any other turn's, and it can
be stopped from Tasks — but the consequence is larger than the sentence, and this
document's own standard is that the owner is told what approving does before they
press it, not after.

**Required fix.** Say it, or stop doing it. Either the approval detail states
that the task will start on the next scheduler tick and offers the owner the
choice, or a task created through an approval is parked rather than queued and
starts when the owner starts it. Do not leave the sentence and the effect
disagreeing.

**UI when closed.** The **Create task** decision names both consequences — the
row and the run — or approving creates a row that waits for the owner.

---

## BUG-65 — An exported transcript keeps citation markers it cannot resolve

**Status: open; found while verifying FIXED-107.**

**Observed.** FIXED-107 makes an answer carry `[s1]` markers, and the transcript
resolves them against the turn's source ledger. The conversation export
(FIXED-54, FIXED-19) carries the answer *text*, so an exported Markdown or PDF
transcript contains `[s1]` with nothing anywhere in the file that says what `s1`
was.

**Why it matters.** The export is what leaves the machine — it is the copy that
gets mailed, filed, or read six months later, and it is the copy where "where did
this come from" is hardest to answer any other way. A marker with no referent is
worse than no marker: it looks like a citation and resolves to nothing, which is
exactly the failure mode FIXED-61 and FIXED-107 exist to end.

**Required fix.** The export writes each turn's ledger alongside its answer — a
numbered source list per turn, carrying title, locator and kind — or it strips the
markers on the way out. Do not export a citation the document cannot resolve. The
passage itself should stay behind: an export is a transcript, not a copy of the
owner's mail.

**UI when closed.** An exported conversation either explains its markers or does
not carry them.

---

## BUG-88 — Ordinary navigation can trip the API rate limit

**Status: open. Found on 2026-08-10 while running the known-limits live round.**

**Observed.** Sweeping the eleven secondary destinations back to back in a live
browser produced, on Models:

```
Couldn't load models
Too many requests in the last minute. Raiker throttled this read; wait a moment
and press Refresh.
```

The message is correct and the recovery works, but nothing the owner did was
unreasonable — they navigated.

**Root cause.** `RateLimitMiddleware` allows 120 requests a minute per client IP
across the whole `/api` surface
(`raiker/api/security.py:118`). That budget is shared by every page load *and*
every background poll, and several surfaces poll: the operation tray every five
seconds, the notification centre, and — until this round — the model activity
panel once a second, which alone spent half the budget while showing nothing.
That last one is fixed (FIXED-162's cadence follows the work), but the shape of
the problem is not: a per-IP fixed window cannot tell a page load from a poll,
so a burst of legitimate navigation is indistinguishable from abuse.

**Impact.** Low and self-correcting — the window is sixty seconds and every
surface offers Refresh — but it presents a governed product as flaky, and it is
the owner's own loopback traffic being throttled by a control written for an
exposed bind.

**Required fix.** Separate the budgets rather than raising the number: exempt
loopback reads from the DoS guard, or give polling routes their own smaller
allowance so a burst of navigation cannot exhaust the interactive one. Whichever
is chosen, `--allow-public` must keep the current bound unchanged, because that
is the bind the control exists for.

**UI when closed.** Navigating the whole workspace at speed never produces a
throttled read on a loopback bind, and an exposed bind is still bounded.

---
## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline. Re-verified end
to end on **2026-08-08** against hosted Anthropic (see
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) for the full round):

first-run bootstrap and owner sign-in; **all 14 routes and 22 hub tabs with 0
console errors**; connecting a hosted provider from the web app and pinning a
model from the live catalogue; **all ten Anthropic models answering a live turn**;
a real streamed turn with sanitised Markdown (headings, lists, GFM tables,
fenced code); conversation memory within a chat and isolation between chats;
per-chat and provider all-time cost; recent-chat list; chat search over titles
and message text; the four task types (immediate, scheduled, daily routine,
background agent) with parent nesting, priority, counters and stop; the approval
lifecycle end to end — proposal, unified diff, **Approve and execute once**, the
file on disk, and the resumed turn; the file inspector for a generated Markdown
file and for a generated PDF; **Export conversation… in HTML, Markdown and PDF**
plus **Print / Save as PDF**; markdown → PDF through `create_document`; document
and image attachments reaching the model with source citations; MCP server
create / connect / discover / **call from Chat** under the owner's decision mode,
with the result marked untrusted; Build repository connect, code-map build and
`code_map_search`; `update_plan` checklists and `spawn_subagent`; capability
step-up (reason required, Confirm disabled until supplied); the deferred domains
CCTV, finance, medical and home security offering no row at all; Observability's
seven tabs on real data; Settings' six tabs; theme cycling system → light → dark;
the notification centre and Mark all read; the STOP switch; and adaptive
navigation at 375 / 768 / 1024 / 1440 px with no horizontal overflow, correct
`aria-expanded`, and focus returned to the trigger.