# Live test rounds — the record

**This document is the evidence. It is append-only, and it never says what to
do.** The procedure lives in
[`RAIKER_LIVE_MANUAL_TEST_PLAN.md`](RAIKER_LIVE_MANUAL_TEST_PLAN.md); a step
there states what *must* be true, and a round here states what *was* true on one
day, on one machine, against one set of providers.

Keeping them apart is the point. They used to be one document, and a step read
"click **Test** — on 2026-08-08 this returned Ready", which meant a person
re-running it could not tell the expectation from one morning's observation. A
round that has been folded into the procedure has stopped being evidence.

## How to add a round

1. Run a tier from the plan — **Smoke** or **Full sweep** — and record which.
2. Add a section here, newest first, with: the date, the tier, the build, the
   providers, what it proved, what it found, and the screenshot prefix.
3. Put screenshots under [`screenshots/working/`](screenshots/working) with that
   prefix, and defects under
   [`screenshots/not-working/`](screenshots/not-working) named for their entry
   in [`TO_BE_FIXED.md`](TO_BE_FIXED.md).
4. Add the prefix to the rounds table in
   [`screenshots/README.md`](screenshots/README.md).
5. **Never edit an earlier round.** If it recorded something that later turned
   out to be wrong, add a note to the *new* round saying so. A record rewritten
   after the fact is not a record.

**Never commit an API key.** Keys go into the Connect dialog or the server
process environment, for the duration of the round only.

## Rounds at a glance

| Date | Tier | Prefix | Providers | What it covered |
|---|---|---|---|---|
| 2026-08-24 | Targeted | `r0824-` | Anthropic (`claude-haiku-4-5-20251001`) | What each capability switch actually decides, Agent Skills conformance on the Skills tab, and Auto's alignment check against a real turn |
| 2026-08-23 | Targeted | `r0823-` | Anthropic, OpenAI, OpenRouter | The checkpoint rewind end to end, the audit export, the deleted second egress path, and two defects the rewind exposed |
| 2026-08-22 | Targeted | `bug-219-`, `bug-221-`, `bug-223-`, `bug-225-` | Anthropic, OpenAI, OpenRouter, Ollama | Hooks off switch and lifecycle events, plugin-contributed skills and MCP offers, channel owner surface, the fourth approval mode |
| 2026-08-21 | Targeted | `r0821b-`, `r0821c-`, `2026-08-21-` | Anthropic | Governed voice, Build modes and operating protocol, the two composers, the Hooks tab, responsive sweeps |
| 2026-08-17 | Targeted | `r0817-`, `r0817b-` | Anthropic Haiku 4.5 | FTS5 retrieval, owner-selected recall backend, background execution and a POSIX terminal, eidetic capture, restart reattachment, persistent environment |
| 2026-08-15 | Targeted | `r0815-` | Anthropic, OpenAI, OpenRouter, Ollama | The native OS sandbox and its measured boundary |
| 2026-08-11 | Targeted | — | Anthropic, OpenAI, OpenRouter, Ollama | Multi-provider usage and compaction; memory recall |
| 2026-08-10 | Targeted | `r0810-` | Anthropic Haiku 4.5 | Known limits; closing the 2026-08-08 round's four defects |
| 2026-08-09 | Targeted | `208-`–`214-` | Anthropic, OpenRouter, Ollama, Hugging Face | BUG-69 closure — first-run model setup and acquisition |
| **2026-08-08** | **Full sweep** | `r0808-` | Anthropic, all ten catalogue models | **The last full sweep.** Every surface in a real Chromium session |
| 2026-07-26 → 08-04 | Targeted | numeric, `b*`, `c*` | Anthropic, Ollama | Earlier rounds, kept where their evidence is still the best record |

**The last full sweep was 2026-08-08.** Everything since has been targeted at a
specific change. That is the honest state of coverage, and it is why the plan now
carries a tier that says which one a round ran.

---

## 2026-08-24 — what each switch decides, skills against a standard, and Auto's second check

**Tier:** targeted. **Providers:** Anthropic (`claude-haiku-4-5-20251001`),
connected through the product's own Connect dialog with
`RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` on the host. No other provider
was exercised. **Prefix:** `r0824-`.

**Build:** the FIXED-279 … FIXED-282 change set, `apps/web` rebuilt, a **fresh
workspace** at `/tmp/raiker-live` with the owner account created in-session, so
every capability gate started at its per-account fail-closed default.

### What it proved

* **A capability switch says whether it decides anything.** Permissions renders
  **GOVERNED ELSEWHERE** beside *Scheduled routines*, *Semantic memory*, *Plugin
  execution*, *Container execution* and *Multi-agent teams*, and **NO ROUTE YET**
  beside the nine with no path — *Plugin runtime*, *Plugin sandbox image pull*,
  *Plugin sandbox runtime*, *Reminders (local)* and the rest. Opening a marked
  card states what really governs the work: *"A scheduled task runs as one whole
  governed turn through the Agent Gateway, so every action inside it answers to
  that action's own gate and decision mode."* Shell, File writes and Subagents
  carry no tag, because their switches mean what they say
  (`r0824-gate-reality-governed-elsewhere`).
* **Delegation has a switch that is real.** `Subagents` reads as an ordinary
  capability rather than an inert one — `spawn_subagent` answers to it now.
* **Every shipped skill reports against the Agent Skills standard.** Extensions →
  Skills shows **STANDARD** on all six built-ins, and opening **Details** gives
  the *Agent Skills standard* block, a link to the published specification, and
  *"This skill matches the Agent Skills standard and should install in any tool
  that reads it."* (`r0824-skill-standard-conformance`.)
* **Auto states the promise it now keeps.** The composer's mode menu reads
  *"Approvals are granted for you, unless a change lands on a file this turn
  never looked at — then it waits."* Skip's line is unchanged
  (`r0824-auto-alignment-promise`).
* **Auto does not obstruct the work that was asked for.** Under Auto, with a real
  Haiku turn: creating `alignment-notes.md` ran unprompted, and so did changing
  the *existing* `ops/deploy.sh` when the prompt named it. This is the half that
  decides whether an owner leaves Auto switched on
  (`r0824-auto-aligned-write-ran`).
* **And it withholds when the turn established nothing.** In the *next* turn of
  the same conversation — *"Do exactly that again, with text repeated"* — the
  model repeated the write, Auto declined to grant it, and the file stayed
  `named`. The approval that appeared opens with *"Automatic approval was
  withheld: ops/deploy.sh already exists and this turn has not read, listed or
  been asked about it, so changing it is outside what you asked for."* above the
  ordinary notice, with the diff `-named +repeated`
  (`r0824-auto-withheld-approval`). **Establishment is scoped to the turn**, and
  this is what that looks like from the owner's side.

### What it found

**One UI defect, fixed in the round.** Rendering skill conformance as a `Badge`
put two pills side by side on every skill row — `► active` and `► standard` —
identical in glyph and tone and meaning nothing alike, because `active` is the
lifecycle badge for *"in flight"*. Conformance is a property of the document, not
a state, so it now renders as a quiet tag and escalates to a real badge only when
there is a portability issue to act on. Covered by
`apps/web/src/lib/skillConformance.test.ts::"keeps conformance a quiet tag unless
there is something to act on"`.

**One test defect, in this round's own spec.** The first version of the
withholding scenario instructed the model with `path "ops/deploy.sh"` in the
prompt — which *establishes* the path, so Auto correctly granted the write and
the spec asserted something impossible. The rule is not a bug; naming a file is
asking about it. Rewritten around turn scoping, which reproduces the
unestablished case deterministically with a real model. Recorded because a live
spec that asserts an impossible state is worse than no spec.

### Deliberately not covered

* **A model choosing an unrelated file on its own.** No prompt that instructs a
  write can also be the unestablished case, and a live spec that waits for a
  model to volunteer one would be flaky. That shape is proven deterministically
  at the broker level instead —
  `tests/test_model_tool_call_loop.py::test_auto_withholds_a_write_to_an_existing_file_the_turn_never_looked_at`.
* **The other providers.** Only Anthropic was connected on this host.
* This was a **targeted** round. The last full sweep remains 2026-08-08.

---

## 2026-08-23 — the rewind, the audit export, and two defects the rewind exposed

**Tier:** targeted. **Providers:** Anthropic (`claude-sonnet-5`), OpenAI
(`gpt-4`), OpenRouter (`nvidia/nemotron-3.5-lightning:free`) — all three
confirmed reachable in-session. Ollama Cloud was **not connected** on this
machine and was not exercised. **Prefix:** `r0823-`.

**Build:** `main` at the FIXED-270 … FIXED-276 change set, `apps/web` rebuilt,
`raiker-web --workspace . --port 8765`, signed in as the existing owner account
*Rahul* — an account created before any of this work, with every capability gate
still at its per-account fail-closed default.

### What it proved

* **The rewind is reachable, and it is a request.** Observability → Checkpoints →
  *Preview restore impact* named the one file a restore would rewrite;
  acknowledging and pressing **Request this restore** answered *"Raised as
  approval appr_830aa…. Nothing has changed yet."* and the file on disk was still
  the agent's version. Approving it in Approvals put `live-rewind-probe.txt` back
  to `original contents before the rewind`. The restore's own pre-image was
  captured, so the rewind is itself rewindable. (`r0823-bug230-restore-preflight`,
  `r0823-bug230-preflight-with-files`, `r0823-bug230-restore-approval`.)
* **The approval for a restore reads as a restore.** The detail pane carried the
  restore-specific notice — *"The restore captures its own pre-image first, so it
  appears as a new checkpoint"* — and the per-file plan, recomputed server-side,
  rather than the file-mutation wording.
* **The audit log leaves the product.** Observability → Audit log → **Export**
  produced 271 events as a redacted JSONL, downloaded it, and listed it with its
  manifest hash. The export appears in the log it exported, as *"Action executed
  — Exported 271 audit events (2026-08-19T11:40:27Z → 2026-08-23T16:35:07Z),
  redacted."* Spot-checked: 24 redactions in the file, and no `sk-` string.
  (`r0823-bug231-audit-export`.)
* **A restart no longer asks for a model that is already set up.** With every
  stored observation aged three hours and the server restarted, Chat opens with
  no strip, **Send** enabled, and a real answer from the provider — the server
  re-takes the aged-out observation while admitting the turn. Marking the
  selected model `authentication_failed` brings the prompt straight back, naming
  the credential rather than the expiry
  (`r0823-bug238-unavailable-still-prompts`).
* **The MCP revision is current, and the card says so.** A server built from the
  bundled echo template, connected over a real stdio session, reports
  **PROTOCOL 2026-07-28** on its card — the template answers the handshake, and
  the negotiated revision is what is shown, not what Raiker offered
  (`r0823-bug234-mcp-protocol`).
* **`network_execution` is gone from Permissions.** The Network group now lists
  Web fetch, Git push, External channels and Channel approval relay, and nothing
  else. Web fetch's description states the guard that actually applies.
* **Every governed step still failed closed first.** On an account with the
  gates at their defaults, the export returned `403` until `audit_export` was
  turned on, and enabling `hosted_model_runtime` required a threat-model
  acknowledgement *and* a typed confirmation token. Both refusals are correct
  behaviour and were re-confirmed here rather than assumed.
* **Responsive.** Fourteen routes at 390 × 844 with **zero** horizontal overflow
  on any of them, including the new export panel, which wraps rather than
  clipping (`r0823-mobile-audit-export`).
* **Every route at 1440 × 900, re-swept after each fix.** Twenty-one routes,
  checked for horizontal overflow and for `NaN`, `undefined`, `[object Object]`,
  `[REDACTED_SE…` and load errors in the rendered text. The final sweep is clean;
  the sweep before it is what found the third redaction defect.

### What it found

Four defects, all raised and closed in the same round. Three were **only
observable because the rewind was finally routed**; the fourth was hit simply by
using the product across restarts:

* **BUG-235 → [FIXED-275](FIXED_ITEMS.md).** A file write approved from the
  inbox filed its pre-image under the *API session* that resolved the approval,
  while the checkpoints it must be restorable from belong to the *chat*. Every
  restore plan for that conversation reported zero files. The blob existed and
  nothing could reach it — which is the same shape as BUG-230 itself, one layer
  down, and is why nobody had found it: without a caller for the restore, no plan
  was ever acted on.
* **BUG-238 → [FIXED-278](FIXED_ITEMS.md).** Hit three times while trying to
  send anything at all: after a restart — and after any five idle minutes — the
  composer said *"The last model check has expired"*, offered **Set up model**,
  and disabled **Send**, for a model that was connected and working. The
  readiness TTL, which exists to bound how *old* an observation may be, was also
  deciding whether the model was **configured**. Staleness is not
  unavailability.
* **BUG-237 → [FIXED-277](FIXED_ITEMS.md).** Exercising the *terminal* half of
  the rewind found that `/checkpoints restore <id>` dies with
  `UnicodeEncodeError` when its output is redirected under a legacy Windows code
  page — the preflight prints an empty-set sign for a file with no pre-image, and
  nothing reconfigured the stream. `raiker … > out.txt` was a different program
  than `raiker …`.
* **BUG-236 → [FIXED-276](FIXED_ITEMS.md).** The export list rendered every
  manifest hash as `[REDACTED_SE…`. The response redactor's high-entropy fallback
  ate the 64-hex digest, so the one field that makes an export verifiable outside
  Raiker could not be read.

### What it did not cover

* **Ollama** — not connected on this host; the local-runtime path was not
  exercised.
* **A cross-principal restore** — a single-owner instance has no second principal
  to overwrite, so the critical path was verified by classification test rather
  than live.
* **An oversize file mutation** — the >8 MiB approval notice was verified by
  test, not by writing an 8 MiB file through a live turn.
* This was a **targeted** round. The last full sweep remains 2026-08-08.

---

## 2026-08-22 — hooks, plugin contributions, channels, the fourth approval mode

**Tier:** targeted. **Providers:** Anthropic, OpenAI, OpenRouter, Ollama.
**Prefixes:** `bug-219-`, `bug-221-`, `bug-223-`, `bug-225-`.

> **Reconstructed from committed evidence, 2026-08-23.** This round was run and
> its screenshots and `FIXED-*` entries were committed, but it was never written
> up here — the plan's last recorded round was 2026-08-15. What follows is read
> from the evidence and the closure entries, not transcribed from a live session.
> Treat the screenshot filenames and the `FIXED-*` entries as authoritative and
> this summary as an index to them.

| Area | Evidence | Closed as |
|---|---|---|
| Turn-end hooks fire on every backend, not just the one that was tested | `bug-223-stop-anthropic.png`, `bug-223-stop-openai.png`, `bug-223-stop-openrouter.png`, `bug-223-stop-ollama.png`, `bug-223-stop-fired-on-a-real-turn.png` | [FIXED-255](FIXED_ITEMS.md#fixed-255--seven-lifecycle-events-were-specified-and-never-emitted) |
| The hook event catalogue the tab publishes | `bug-223-hook-event-catalogue.png` | FIXED-253, FIXED-255 |
| A plugin contributes a skill, and it arrives switched off | `bug-221-plugin-skill-inactive.png`, `bug-221-live-skill-in-turn.png`, and desktop/tablet/mobile at `bug-221-plugin-skill-*.png` | FIXED-259 |
| A plugin offers an MCP server, and an offer is not a server | `bug-221-plugin-mcp-offer.png` | FIXED-260 |
| What a plugin may contribute, stated as three kinds | `bug-221-contribution-kinds-three.png`, `bug-221-plugin-contribution-kinds.png`, `bug-221-plugin-contributed-rules.png` | FIXED-256, FIXED-259, FIXED-260 |
| Hooks and Plugins tabs at three widths | `bug-221-223-hooks-{desktop,tablet,mobile}.png`, `bug-221-223-plugins-{desktop,tablet,mobile}.png` | FIXED-257 |
| Channels gain an owner surface: paired, and the four facts shown as four things | `bug-225-channel-surface.png`, `bug-225-channel-paired.png`, `bug-225-channel-contract.png`, `bug-225-channel-delivery-refused.png` | FIXED-261, FIXED-265 |
| Channels tab at three widths | `bug-225-channels-{desktop,tablet,mobile}.png` | FIXED-265 |
| The fourth approval mode — *Decline, don't ask* | `bug-219-approval-modes.png`, `bug-219-approval-modes-mobile.png` | FIXED-262, FIXED-263 |
| A live model was ready for the turns above | `bug-221-live-anthropic-ready.png` | — |

Also closed in this round without a manual screenshot: FIXED-254 (the owner off
switch for hooks), FIXED-258 (web tests on a current Node), FIXED-264 (a live
spec's sign-in), FIXED-266 (a redacted boolean), FIXED-267 (a bounded channel
sender), FIXED-268 (signing outbound deliveries).

---

## 2026-08-21 — governed voice, Build modes and protocol, the Hooks tab

**Tier:** targeted. **Provider:** Anthropic.
**Prefixes:** `r0821b-`, `r0821c-`, `2026-08-21-`.

> **Reconstructed from committed evidence, 2026-08-23**, on the same basis as the
> round above.

| Area | Evidence | Closed as |
|---|---|---|
| Chat and Build composers at 375 px, and Build at 768 px | `r0821b-01-chat-composer-375.png`, `r0821b-02-build-composer-375.png`, `r0821b-07-build-composer-768.png` | FIXED-250 |
| Build opens in **Auto**, the mode that overrides nothing | `r0821b-03-build-auto-default.png` | FIXED-248 |
| The Build mode menu | `r0821b-04-build-mode-menu.png` | FIXED-248, FIXED-250 |
| `/schedule` from the composer | `r0821b-05-schedule-command.png` | FIXED-250 |
| The Build operating protocol, live, and the record of which one ran | `r0821b-06-build-operating-protocol-live.png` | FIXED-251 |
| The Hooks tab: rules, the events it dispatches, and recent activity | `r0821c-01-hooks-tab.png`, `r0821c-02-hooks-events-and-activity.png` | FIXED-253 |
| A hooks file that does not parse is named and survived | `r0821c-03-hooks-broken-config.png` | FIXED-252 |
| Hooks turned off, with the rules still listed | `r0821c-06-hooks-turned-off.png` | FIXED-254 |
| Hooks tab at 375 px and 768 px | `r0821c-04-hooks-375.png`, `r0821c-05-hooks-768.png` | FIXED-257 |
| Memory at 375 px and 768 px; Knowledge Map, Diagnostics and Runtime at width | `2026-08-21-memory-375.png`, `2026-08-21-memory-768.png`, `2026-08-21-brain-1440.png`, `2026-08-21-diagnostics-1440.png`, `2026-08-21-runtime-1024-full.png` | FIXED-242, FIXED-245, FIXED-257 |

Voice was closed the same day as FIXED-247 (governed input rather than labels)
and FIXED-249 (dictation stops when the owner leaves the page); its evidence is
in the `voice-*` Playwright output rather than under `screenshots/working/`.

---

## 2026-08-15 — Native OS sandbox round
The round that closed the OS-boundary half of BUG-194 as **FIXED-195**. Run
against the production web build on Windows 11, with all four providers
connected **through the Models dialog**, never through the CLI.

The question this round exists to answer: **is the boundary real, and does
Raiker only claim what it measured?**

| # | Step | Expected | Result |
|---|---|---|---|
| 24.1 | Register a fresh owner, take Balanced through setup, open the dashboard | Lock screen, then the dashboard mounts | ✅ |
| 24.2 | Settings → **Runtime configuration** | **Native OS sandbox** is listed with `AppContainer · network denied` and six observations | ✅ `r0815-runtime-native-sandbox-observations.png` |
| 24.3 | Read the six observations | Command output reaches Raiker / can write inside the workspace / cannot write outside it / cannot read Raiker's own state / cannot reach the network / stopping ends every descendant — all **Enforced** | ✅ `r0815-native-sandbox-card.png` |
| 24.4 | Read what the card says it does *not* do | "Foreground commands only. PTY, background execution, network grants and persistence are not built for this boundary and are not offered." | ✅ |
| 24.5 | Read the re-measure disclosure | "Re-measuring opens one connection to this host's default gateway on a closed port." | ✅ |
| 24.6 | **Select** the native sandbox | The card reads **Selected**; `execution_environment_selection` records `native_sandbox` | ✅ |
| 24.7 | Permissions → enable **Shell commands** and **Approval execution relay**, each with a reason and a confirmation token | Both gates record `enabled_runtime` against the principal | ✅ |
| 24.8 | Models → Hosted → **Connect** Anthropic, OpenRouter and OpenAI, pasting each key in the dialog; **Test** each | Each card reads **Connected**, then "«provider» can reach «model»" | ✅ |
| 24.9 | Build → send "Use the shell tool to run exactly: `git --version`" | The turn proposes a `shell` action and parks: "Waiting for your decision. Nothing has run yet." | ✅ |
| 24.10 | **Accept** | The command runs inside a per-run AppContainer; `git version 2.55.0.windows.4` comes back through the relay; the model answers from it | ✅ `r0815-build-governed-terminal-appcontainer.png` |
| 24.11 | Read the governed terminal | `AppContainer · network denied` · "OS boundary · foreground only · no PTY, background or network grant" · the output · **Immutable receipt** with outcome, exit, isolation and authority | ✅ |
| 24.12 | Repeat 24.9–24.10 with **OpenRouter** (Gemini 3.7 Flash), **OpenAI** (GPT-4o Mini) and **Ollama** (gemma4:31b-cloud) | Each provider drives the same path to the same executed command | ✅ six `succeeded` runs in `command_runs` |
| 24.13 | Run `echo x > ..\escape.txt` through the runner directly | **"Access is denied."** from the OS, exit 1 — not a policy refusal | ✅ |
| 24.14 | Run `dir .raiker` through the runner directly | **"Access is denied."** from the OS | ✅ |
| 24.15 | Read the receipt evidence for a completed run | `boundary_constructed` names this run's profile, `network_capability: false`, the protected paths and the runner digest; `probe_observations` carries the six host measurements **and** the time they were taken | ✅ |

> 24.13 and 24.14 are the steps that separate this from the argv policy. The
> allowlist would refuse those commands anyway; running them through the runner
> directly is what shows the *operating system* refusing them.

**Result: passed, after two defects this round found and fixed.** Every
sandboxed command initially failed with `native_sandbox_launch_failed:203` while
the same command run by hand succeeded: an AppContainer is created with a
redirected local profile and `CreateProcessW` resolves it from the environment
block, which Raiker's deliberately minimal environment did not carry. And
`portable_command` rewrote `echo` into the interpreter Raiker itself runs on,
which lives outside the boundary, so the child died with `STATUS_DLL_NOT_FOUND`
— an exit code rather than an error. Both are in **FIXED-195**.

One defect found and **not** fixed this round: every turn rendered
**"The turn could not continue (409)."** beneath its own successful answer, in
all four provider rounds. Filed as **BUG-196**.
---

## 2026-08-11 — Memory recall round
The round that verified [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md)
MEM-01 and MEM-02, closed as FIXED-187 through FIXED-189. Run against the
production web build with Anthropic connected through the Models dialog.

The question this round exists to answer is the one memory is actually asked:
**can Raiker pick up a conversation from years ago and quote it exactly?**

| # | Step | Expected | Result |
|---|---|---|---|
| 23.1 | Register a fresh owner, take the Anthropic path through setup, finish the wizard | Lock screen, then the dashboard mounts; 0 console errors | ✅ `r0811b-01-lock-screen.png`, `r0811b-04-setup-complete.png` |
| 23.2 | Models → Hosted → **Connect** on Anthropic; paste the key in the dialog | Card reads **Connected**; the field is masked and the key is never echoed | ✅ `r0811b-05-models-hosted.png`, `r0811b-06-connect-dialog.png`, `r0811b-07-anthropic-connected.png` |
| 23.3 | **Choose model…**, pick a model from the live catalogue, **Use model** | The catalogue is the provider's own list | ✅ `r0811b-08-model-picker.png` |
| 23.4 | **Test** on the Anthropic card | "1 model ready · Anthropic can reach `claude-haiku-4-5-20251001`" | ✅ `r0811b-09-model-readiness.png` |
| 23.5 | In a new chat, state a fact worth recalling (a host name and an interval) and ask for a one-word acknowledgement | A live streamed turn; the reply is stored as the conversation record | ✅ `r0811b-11-chat-first-turn.png` |
| 23.6 | In a **separate** chat, ask what was said earlier and require a citation | The turn calls `conversation_search`, quotes the sentence **verbatim**, and cites the conversation, its date and its id | ✅ `r0811b-12-recall-across-chats.png` |
| 23.7 | Seed a conversation dated **three or four years back**, then ask about it with a period in the question ("back in 2022", "before 2023") | The turn narrows by date, finds the old conversation, and returns the exact figure, the quoted sentence, the date and the stated reason | ✅ `r0811b-13-recall-2022-conversation.png` |
| 23.8 | Search Chat for a term that appears only in a message body | Each result shows the exchange that matched beneath its title, and an old conversation is grouped under its own date | ✅ `r0811b-14-search-chat.png` |
| 23.9 | Turn **Incognito** on and repeat 23.6 | No recall item is assembled at all — the opt-out is absolute, ahead of every recall path | — written for the next round |
| 23.10 | Sign in as a second local principal and search for the first's conversation | Nothing is returned; the index narrows candidates, `sessions.user_id` still decides visibility | Covered by `test_another_owner_never_sees_the_conversation` |

> 23.6 is the step that distinguishes recall from a long context window. Start a
> genuinely separate conversation — not a new turn in the same one — or the model
> can answer from history it still has.

**Result: passed.** The first pass of 23.6 found the right conversation and still
could not answer, because the tool returned the index's own ~18-token snippet and
the model was handed "…we rotate the SQLCipher key every…". That is **FIXED-189**,
fixed and re-run in the same round; the regression test is written from the live
transcript. 23.7 then recalled an 18 April 2022 conversation with the exact
retention window, the verbatim sentence, the date and the reason.

---
---

## 2026-08-11 — Multi-provider usage and compaction round
Run against the production web build. Enter every credential through Models;
never seed a connection through the CLI, environment, fixture, or direct API.
Close credential and connection dialogs before taking screenshots. Use a fresh
conversation per provider so provider attribution and model readiness are
unambiguous.

1. Run the checked-in loopback fixture and both deterministic batch specs.
   Confirm the refusal scenario renders successive model passes as separate
   paragraphs, and both specs use `e2e/fixtures/stub_model.py`.
2. Connect Anthropic in Models, choose a live catalog model, complete readiness,
   and send a bounded marker prompt in Chat.
3. Connect OpenRouter the same way and complete a live turn. Refresh Models →
   Activity and verify the **Provider reported** key-level weekly metric appears
   separately from **Raiker observed**.
4. Connect OpenAI through Models and complete a live turn. Without a separate
   organization admin key, verify provider data says it needs one rather than
   presenting an invented quota.
5. Select and check Ollama `gemma4:31b-cloud`, then complete a live turn. Verify
   the provider side says no compatible account-quota API while Raiker-observed
   local tokens and turns remain present with no API cost.
6. Disconnect or stop one provider and verify a provider that is no longer
   connected/ready is absent from the rolling view.
7. Set an owner weekly token budget in each visible row. Confirm its label says
   **Advisory Raiker control — not a provider subscription limit**, survives a
   reload, and can be cleared.
8. Exercise a known small owner context capacity in the deterministic runtime.
   Confirm the extra compaction model request has no tools, the next turn sees
   the compacted summary plus recent exchanges, and the Context popover says the
   transcript is unchanged. Repeat with a failed compaction and confirm bounded
   recent history is retained.
9. Capture provider and Context screenshots only after all credential dialogs
   are closed. Inspect the committed image set for key-shaped strings before
   keeping it.

The automated evidence for this round includes the compaction, usage adapter,
ledger/API, Svelte component, checked-in fixture, and live Playwright suites.

**Result: deterministic and local-provider paths passed; hosted execution was
environment-blocked.** The checked-in stub scenarios passed against the real
FastAPI runtime, including the two-paragraph multi-call answer assertion. All
four requested connections were entered through Models with the connection
dialogs closed before capture. Anthropic, OpenAI, and OpenRouter then failed
closed as **Unreachable** because this managed run could not grant the server
outbound network access; no hosted response is represented as a live turn.
OpenRouter's ordinary-key usage request therefore reports temporarily
unavailable, while Anthropic and OpenAI correctly request separate organization
admin credentials instead of inventing account limits.

Ollama `gemma4:31b-cloud` passed exact-model readiness and returned both bounded
markers in Chat. Its streamed OpenAI-compatible response exposed a live defect:
the request omitted `stream_options.include_usage`, so the first turn did not
reach the ledger. The adapter now requests those metrics for Ollama streams;
the repeated turn recorded **5,405 tokens, 1 turn, 1 model request**, with **No
API cost — local runtime**. All four connected rows accepted owner weekly token
budgets and retained them after a server restart. The same restart exposed and
closed a second defect: placeholder-provider cards now retain each configured
model instead of showing `no model pinned` whenever another provider is the
global selection. A compact 900 px pass also fixed the tablet Menu/title
overlap and finished with no horizontal overflow.

Screenshots: `bug-52-chat-refusal-does-not-end-the-turn.png`,
`round0811-ollama-live-turn.png`,
`round0811-hosted-provider-readiness.png`,
`round0811-provider-usage-connected.png`, and
`round0811-provider-usage-compact.png` in
[`screenshots/working/`](screenshots/working). Every retained image was reviewed
after dialogs closed; none contains a credential value.


---
---

## 2026-08-10 — Known-limits round
Run against a fresh isolated workspace (`/tmp/raiker-live`), the production web
build, and one hosted provider credential entered through Models only. The
credential is absent from screenshots, source, and logs committed here.

Automated as `apps/web/e2e/bug-74-84-known-limits-live.spec.ts` and
`apps/web/e2e/containment-surface-live.spec.ts`, both re-runnable against an
already-driven workspace.

1. Register a fresh owner. Confirm the model setup prompt opens, then skip it.
2. Visit every code-split destination — Search Chat, Memory, Approvals, Tasks,
   Knowledge Map, Projects, Permissions, Models, Extensions, Observability,
   Settings — and confirm each mounts with content and no console error.
   *(FIXED-161.)*
3. Extensions → Plugins. Confirm the workspace signing posture is stated in
   words, names the two environment variables that would raise it, and says
   installs are unaffected. *(FIXED-166.)*
4. Settings → Security & sign-in → **Monitored capabilities**. Confirm the
   section explains that every capability family is watched the same way
   monitored MCP connections are, and that an empty workspace says so rather
   than showing nothing. *(FIXED-163, FIXED-164.)*
5. Settings → Runtime configuration → **How long a model check stays good for**.
   Confirm the default reads 5, change it to 30, **Save changes**, navigate away
   and back, and confirm 30 survives the round trip. *(FIXED-169.)*
6. Models → Activity. Confirm the durable operations surface loads and states
   that failed work is never silently retried. *(FIXED-162.)*
7. Models → Hosted. Connect Anthropic through the UI, pin a model from the live
   catalogue, and press **Test**. Confirm the card reaches
   `Ready · confirmed just now` and names the exact model it reached.
   *(FIXED-133, FIXED-169.)*
8. Chat. Send one bounded prompt and confirm the model answers with the exact
   requested marker. *(FIXED-133.)*
9. Record three consecutive failures for one connector through the same
   `CapabilityBreaker` the runtime uses (the command is in the spec's header —
   a browser cannot make a healthy provider fail on demand). Reload Settings →
   Security & sign-in and confirm the subject is listed as **paused** with its
   stated reason, its failure count and its last failure code, that a matching
   high-severity finding appears above it, and that **Resume** returns it to
   active in one press. *(FIXED-163, FIXED-164.)*

**Result: ✅ eleven entries closed** — FIXED-133 re-verified and FIXED-161
through FIXED-170. Screenshots: `round0810-01-first-run-model-setup.png` through
`round0810-11-containment-resumed.png` in
[`screenshots/working/`](screenshots/working). The production build reports no
chunk-size warning: the entry chunk is 237 kB against the previous 690 kB, and
the largest route chunk is Models at 82 kB.
---

## 2026-08-09 — BUG-69 closure round
Run against a fresh isolated workspace and the production web build. Provider
credentials were entered through Models only and are absent from screenshots,
source, and logs committed to the repository.

1. Register a fresh owner. Confirm the model setup prompt opens.
2. Skip setup, visit Workbench, Chat, Build, Tasks, and Schedule, and confirm
   each model-backed primary action is disabled with a Models link.
3. In Models, select local Ollama `gemma4:31b-cloud` and run **Check**. Confirm
   exact-model Ready. A direct bounded generation returned the requested marker.
4. Connect OpenRouter through the UI, select `openai/gpt-4o-mini`, and confirm
   catalogue plus one-token execution readiness. A real governed turn reached
   the approval boundary and executed no command.
5. Connect Anthropic through the UI and select `claude-opus-4-8`. The live
   catalogue authenticated, but the account rejected execution for insufficient
   credit. Confirm the readiness result names current-account execution, links
   remediation, preserves the draft, and keeps Send disabled.
6. Add one exact local folder under **Local library**, rescan, and confirm its
   GGUF name, llama architecture, Q4_K_M quantization, and Deploy action.
7. Search Hugging Face for a GGUF repository. Confirm immutable revision,
   licence, gated status, size, format, and Q4_K_M choices are visible before
   download confirmation. Download the tiny permissive TinyStories GGUF into an
   approved root, deploy it, and wait for the newest Activity row to reach
   `complete`.

**Result: ✅ BUG-69 closed.** No raw provider reason code became the first
assistant reply. Screenshots: `208-BUG-69-first-run-model-setup-live.png` through
`214-BUG-69-huggingface-download-deploy-live.png`. The Anthropic refusal is an
expected external account state and proved the new fail-closed execution
preflight; OpenRouter and Ollama supplied successful execution evidence.
