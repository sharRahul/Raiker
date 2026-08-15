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
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | High | Shell / sandbox / recovery | Open — reduced; the OS boundary is closed as FIXED-195 |
| [BUG-196](#bug-196--a-successful-turn-reports-that-it-could-not-continue) | Medium | Build / Chat turn resume | Open |
| [BUG-197](#bug-197--a-command-runs-backend-column-is-never-written) | Low | Command store | Open |
| [BUG-205](#bug-205--a-plain-pytest-tests-run-fails-because-cipher_memory_security-is-a-one-way-latch) | Low | Test isolation / SQLCipher posture | Open |
| [BUG-206](#bug-206--a-tool-call-is-invisible-in-chat) | High | Chat / streaming surface | Open |
| [BUG-207](#bug-207--the-models-real-reasoning-is-requested-discarded-and-replaced-with-three-canned-sentences) | Medium | Chat / streaming honesty | Open |
| [BUG-208](#bug-208--the-product-explains-itself-on-every-screen-and-the-guide-it-should-be-explaining-from-is-unreachable) | Medium | UI density / documentation surface | Open |
| MEM-03 … MEM-09 | High → Low | Memory reliability | Open — see [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md) |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B9, B11, B12, B17 complete; 10 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (14 items remain) |

The memory audit of **2026-08-11** has its own document,
[`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md), written to this
standard. Its MEM-01 and MEM-02 are closed in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md) as FIXED-187 and FIXED-188; MEM-03 through
MEM-09 are open there rather than duplicated here.

---

## BUG-194 — The governed shell has an OS boundary, but no interactive, background or remote execution

**Severity: High. Area: shell / sandbox / recovery. Status: Open — reduced.**

**What changed.** The 2026-08-15 work closes the largest item on this entry: a
governed command now runs inside a real operating-system boundary, and what that
boundary enforces is **measured rather than declared**. Closed as
[FIXED-195](FIXED_ITEMS.md). The rest of this entry is what remains, with the
reason each item was not attempted rather than a schedule.

**Still observed.** Select `native_sandbox` and request interactive, background,
network, credential, SSH or Daytona execution and the backend fails closed with
the corresponding named reason. Restart Raiker during an active command: the
durable run is reconciled to `lost`, because no authenticated backend handle can
be reattached. The container path is still a per-run `docker exec` client rather
than a session supervisor, and Docker's daemon was reachable on the 2026-08-15
host but the container row was not re-proven in that round.

**Root cause, per item.** Each of these is a component rather than a flag, which
is why none of them was half-built:

| Remaining item | Why it is not built |
|---|---|
| **Background start/poll/wait/log/kill** | A background run outlives the turn, so it needs an enforcer that outlives the turn: a lease the runner owns, a runner that dies with Raiker, a durable runner identity that distinguishes "still running" from "pid reused", and a reconciliation path that works while the vault is locked. Shipping the flag without them creates an orphan process holding a Job Object and a sandbox grant that nothing ever reclaims — strictly worse than refusing. The agent-facing half is a second missing piece: a `process` tool that can poll, log and kill what the agent started, without which `background` makes an agent re-run commands it cannot observe. |
| **PTY and raw input** | `CreatePseudoConsole` builds its console objects in the caller's context; they are not reachable from an AppContainer token without an explicit capability, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. A PTY that only works outside the sandbox is not the control the row describes. |
| **Restart reattachment** | Requires the process handle to live in a detached supervisor with an authenticated control channel — a second, larger component. Building it on an unproven boundary would have made both unfalsifiable. Restart continues to produce an honest `lost` receipt, and the runner is now bound to a runtime-owned Job Object so a hard kill of Raiker is reaped by the kernel rather than orphaning a sandboxed process. |
| **Persistent environment** | Per-run AppContainer profiles are created and deleted around each command, deliberately: a predictable container name is a hole, because the container SID is a pure function of the name. Retaining a boundary is a container-session change, not a Windows one. |
| **Filtered domain egress** | The AppContainer loopback exemption needs elevation, and a Linux proxy-only namespace is a separate netns build. Refused with a named reason on every backend rather than partially claimed. |
| **Credential delivery and delta quarantine; SSH; Daytona** | Unchanged. None is a Codex or Claude Code control; all three remain storage contracts and selectable-but-refused profiles. |
| **Container session supervisor** | The per-run `docker exec` client named in the original root cause is unchanged. |
| **Signature verification of the runner** | The runner's SHA-256 is recorded at build time, checked before use, and carried into the receipt. That detects corruption and casual replacement; it is **not** protection against an attacker with write access to the install directory, who could replace Raiker itself. Authenticode chain verification is not implemented. |

**Required fix.** Unchanged for each remaining row: a packaged backend-resident
supervisor with an authenticated control channel and an encrypted restart-safe
handle; background start/poll/wait/log/input/kill with a lease the runner owns;
PTY once the ConPTY/AppContainer question is settled by a spike; an
authenticated domain proxy with DNS/address checking and active revocation;
purpose-bound credential delivery plus two-pass delta quarantine; persistent
container/SSH/Daytona supervisor adapters; and owner-authorised reset/recreate.
Prove every backend independently and preserve the no-fallback and honest-`lost`
rules.

**Required user-interface outcome.** Unchanged, and partly met: Runtime shows
the exact probed boundary and its six measured observations, and Build shows the
boundary a command ran in plus failure navigation. Background, PTY, filtered
network, persistence and reset controls remain **absent** rather than disabled —
an absent control is the honest projection of an unbuilt capability, where a
disabled one implies it is a setting away. No row may turn green from
configuration or specification alone.

---

## BUG-196 — A successful turn reports that it could not continue

**Severity: Medium. Area: Build / Chat turn resume. Status: Open.**

**Observed.** On 2026-08-15, in every one of the four provider rounds, a Build
turn that approved a shell command executed it, streamed the model's answer
containing the command's real output, and then rendered
**"The turn could not continue (409)."** directly beneath that answer. The turn
had in fact completed. The message is the only failure signal on screen, so a
successful governed execution reads as a failed one.

**Reproduce.** Build → send a prompt that proposes a `shell` action → **Accept**.
The answer arrives; the error line arrives with it. Seen with Anthropic Haiku
4.5, OpenRouter Gemini 3.7 Flash, OpenAI GPT-4o Mini and Ollama
gemma4:31b-cloud, so it is not provider-specific.

**Root cause.** `BuildView`/`ChatView` treat any 409 from the resume route as a
failure unless `alreadyResumedElsewhere(code)` matches, and that helper matches
exactly one reason code, `suspended_turn_already_resumed`
(`apps/web/src/lib/approvalResume.ts`). The resume route can answer 409 with
`approval_not_resolved` and `suspended_turn_unreadable` as well
(`raiker/api/routes_approvals.py::_RESUME_ERRORS`), and a second resume attempt —
the approval click and the approvals poller both make one — loses the race. The
BUG-24 comment beside the helper already states the principle: losing the race is
a success, and saying "error" there would be a lie. The set of codes it accepts
is what did not keep up.

**Proposed fix.** Decide the outcome from the turn's state rather than from the
race: if the turn has a completed response, a later 409 is a lost race and is
silent. Widen the helper to the codes that mean "already done", and add a
regression test that resolves one approval twice and asserts no error is shown.

**Required user-interface outcome.** A turn that completed shows no error. A
turn that genuinely could not continue still says so, with its reason.

---

## BUG-197 — A command run's `backend` column is never written

**Severity: Low. Area: command store. Status: Open.**

**Observed.** Every row in `command_runs` carries `backend = ''`, including runs
that completed inside the native sandbox. The receipt records the backend
correctly (`evidence.backend = "native"`), so the two surfaces disagree: the
immutable record knows what ran the command and the list the owner browses does
not.

**Reproduce.** Run any governed command and read `command_runs.backend`, or the
`backend` field of `GET /api/command-runs`.

**Root cause.** `CommandStore.create` never populates the column and nothing
updates it later; `CommandService` computes `backend_name` for the receipt only
(`raiker/execution/commands/service.py`).

**Proposed fix.** Write it at start, beside the existing `record_isolation` call,
so a run in flight already names its backend.

**Required user-interface outcome.** The run list names the backend for every
run, matching its receipt.

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

---

## BUG-205 — A plain `pytest tests/` run fails, because `cipher_memory_security` is a one-way latch

**Severity: Low. Area: test isolation / SQLCipher posture. Status: Open.**

**Observed.** `python -m pytest tests/` — the command a contributor runs — fails:

```
FAILED tests/test_sqlcipher_memory_security.py::
       test_the_pragma_is_set_explicitly_to_off_without_an_unsafe_parent_probe
E       - 0
E       + 1
```

CI is green on the same commit because `.github/workflows/ci.yml` sets
`RAIKER_SQLCIPHER_MEMORY_SECURITY: "off"` for the whole job, so nothing in that
process ever turns the pragma on. The gate therefore cannot see this, and the
failure lands only on whoever runs the suite the documented way.

**Reproduce.** Two files are enough, and the pairing is what matters rather than
any one test:

```
python -m pytest tests/test_memory_sqlcipher.py tests/test_sqlcipher_memory_security.py   # fails
RAIKER_SQLCIPHER_MEMORY_SECURITY=off python -m pytest <same two files>                    # passes
python -m pytest tests/test_sqlcipher_memory_security.py                                  # passes alone
```

Confirmed **pre-existing**: the same pairing fails identically with `raiker/` and
`tests/` checked out at `ad3d84c`, before the 2026-08-15 memory work.

**Root cause.** `PRAGMA cipher_memory_security` is process-global in the bundled
SQLCipher build, and it latches one way. Measured directly:

| Sequence in one process | Pragma reads |
|---|---|
| resolve `off` → open store | `0` |
| resolve `off` → open → resolve `on` → open | `1` — the raise takes effect |
| resolve `on` → open → resolve `off` → open | `1` — **the drop does not** |

The test assumes the pragma is a per-connection property that each new
connection sets from the resolved posture, so it opens a store on a fresh
`tmp_path` after `close_cached_connections()` and expects `0`. A new connection
and a new workspace do not help: once any connection in the process has enabled
it, the process keeps it.

**Security note, so this is not read as worse than it is.** The latch only sticks
in the *safe* direction. A run that asks for `on` can never silently end up
`off`; the failure mode is memory security remaining enabled after a request to
disable it, which costs performance rather than protection. Nothing here weakens
the posture FIXED-150 records.

**Required fix.** The test is asserting a property the platform does not offer,
so fix the test rather than the pragma. Either run it in its own process
(`pytest-forked`, a subprocess, or a session-scoped marker that isolates the
SQLCipher posture tests), or assert what is actually per-connection — that Raiker
*issues* `PRAGMA cipher_memory_security = 0` on a connection it resolved `off`
for — and assert the read-back value only in a process that has never enabled it.
Whichever is chosen, the CI job should stop setting the env var globally, or
should keep setting it and additionally run the posture file in a second,
unset job: an env var that hides an order dependency is the reason this reached
`main`.

**Required user-interface outcome.** None directly — no shipped surface changes.
The one product-facing consequence to keep honest: `GET /api/health` reports the
posture Raiker *resolved*, not the pragma in force. Those can disagree only after
a re-resolution inside one process, which today only tests do, so health stays
truthful for a normal run. If re-resolution ever becomes a runtime feature, health
must read the pragma back rather than report the intent.

---

## BUG-206 — A tool call is invisible in Chat

**Severity: High. Area: Chat / streaming surface. Status: Open.**

**Observed.** Chat never shows that a tool ran. A turn that lists a directory,
reads a file, fetches a page or writes a document renders exactly like a turn
that did none of those: prompt bubble, answer bubble. The only tool a
conversation ever mentions is one that policy **refused** (`refusal-card`,
BUG-52). Success is silent.

The intended shape — an icon, the tool, and what it did on one line, the way a
class-leading assistant renders it — has nowhere to attach, because the data
never reaches the client.

**Reproduce.** Run any tool-using turn in Chat and read the transcript. Captured
on 2026-08-15 for an ordinary turn, every element the turn produced was:

```
message-group · message-bubble · bubble-text · reaction · markdown · copy-message
```

No tool row exists in that list because none can.

**Root cause.** Two halves, and the backend one is the blocker.

1. **The broker has no stream sink.** `raiker/tools/broker.py` emits
   `tool_started`, `tool_completed` and `tool_failed` through `self._event(...)`,
   which appends to the durable log via `self.writer` and nothing else. Compare
   `raiker/runtime/orchestrator.py::_emit`, which appends to the writer *and* to
   `self._sink` as a `StreamEvent`. The broker has no `_sink` at all, so its
   events are readable afterwards on the Audit log and never during the turn.
2. **The stream kind exists and is unused.** `raiker/contracts/streaming.py`
   defines `TOOL = "tool"` — *"tool proposal/decision/result activity"* — and no
   code path in `raiker/` ever constructs a `StreamEvent` with it. The web client
   types `StreamKind` accordingly and has no branch for it.

So the contract anticipated this surface, the runtime records the facts, and the
two were never joined.

**Required fix, in slices that each land on their own.**

| Slice | Work | Why it is separable |
|---|---|---|
| **A — carry tool events on the stream** | Give `ToolBroker` the same optional sink the orchestrator has, and emit `StreamEvent(kind=TOOL, event_type=…, payload=…)` beside each durable `tool_started` / `tool_completed` / `tool_failed`. | Backend only. Provable with a stream test asserting the three events arrive in order, with no UI change. |
| **B — decide what a tool row may say** | The payload must pass the same redaction the durable event does. `_event_safe_arguments` already drops content for metadata-only tools and redacts the rest; the row needs a short, safe **action phrase** (`read_file` → the path; `web_fetch` → the host, never the URL's query) resolved server-side, never assembled in the client from raw arguments. | This is the governance question, and it is the one that must not be rushed. A leak here is a leak in every conversation. |
| **C — an icon per tool** | Extend the existing `Icon` set with one glyph per tool family (file read, file write, shell, web, repository, connector, memory, subagent) and a neutral fallback, so an unknown tool renders as a tool rather than as nothing. | Pure asset + mapping work, testable in isolation. |
| **D — the row component** | `[icon] [tool] [action]` on one line, in the transcript, in call order: pending while running, settled when it finishes, and the failure reason inline when it fails. Grouped when several run in a batch, so three reads are three lines and not three cards. | Frontend only, drivable from a fixture once A and B exist. |
| **E — retrofit the refusal card** | Once every call has a row, a refused call is that same row in a refused state rather than a separate block at the bottom of the turn. | Removes a surface instead of adding one; do it last so nothing regresses while D lands. |

**Required user-interface outcome.** A tool-using turn reads as a sequence of
what happened: each call one line, the icon telling you the kind at a glance, the
tool named in the owner's language rather than its identifier, and the action
naming the object it acted on. A call still running says so; a call that failed
says why on its own line. No raw argument JSON, no tool identifier, and no
surface that is silent about work that ran. The Audit log stays the full record —
the transcript is the summary, not a second copy of it.

---

## BUG-207 — The model's real reasoning is requested, discarded, and replaced with three canned sentences

**Severity: Medium. Area: Chat / streaming honesty. Status: Open.**

**Observed.** While a turn streams, Chat offers a disclosure labelled **"See what
Raiker is thinking"**. Opening it shows, in every turn, some subset of exactly
three fixed strings:

```
Understanding what you need.
Reviewing the available context.
Putting together a response.
```

They are not the model's thinking. They are a lookup table on three lifecycle
event types (`chatPresentation.ts` → `THINKING_COPY`), identical for a one-word
question and a twenty-tool build. Mid-stream capture of a real turn on
2026-08-15 shows the whole Raiker side of the transcript being:

```
Raiker is thinking…
See what Raiker is thinking
```

**And the real thing is being thrown away.** When reasoning is enabled,
`anthropic_messages.py:292` sends `payload["thinking"] = {"type": "adaptive"}` —
so the provider is asked for extended thinking and, when the profile supports it,
a summarized display. The stream parser then handles `text_delta` and
`input_json_delta` only (`anthropic_messages.py:404-413`); there is no
`thinking_delta` branch. Raiker pays for reasoning tokens, receives them, and
drops them on the floor while showing the owner a fixed list.

**Root cause.** The canned copy is deliberate and its motive is sound — the test
that covers it is named *"turns recognised lifecycle events into **safe**
conversational thinking steps"*, and it asserts that raw internal text is not
surfaced. The defect is not that Raiker was careful; it is that a careful
placeholder is **labelled as the model's thinking**, which is the one thing it is
not. The same product refuses to call an unmeasured backend "Connected"
(FIXED-204); this is that rule applied to the other side of the turn.

**Required fix, in slices.**

| Slice | Work |
|---|---|
| **A — stop the false claim now** | Either drop the disclosure while a turn is streaming, or relabel it as what it is (progress, not thinking). One-line change, no backend work, and it can land before anything below. |
| **B — consume `thinking_delta`** | Add the branch to the Anthropic stream parser and carry it as its own `StreamEvent` kind (or a `text_delta` variant tagged as reasoning) so the runtime can tell reasoning from answer. Mirror it for any other provider that streams reasoning. |
| **C — render real reasoning** | A collapsed "Thinking" block above the answer that fills in as reasoning streams and collapses once the answer starts, shown only when the turn actually produced reasoning. Prefer the provider's **summarized** display where available, which is what the request already asks for. |
| **D — the streaming indicator** | With B and C, "Raiker is thinking…" / "Raiker is typing…" both stop earning their place: streamed text is its own progress. Reduce to a single quiet indicator that ends the moment the first token lands. |

**Required user-interface outcome.** A turn shows the model's own reasoning or it
shows none — never a fixed list presented as reasoning. Where reasoning is shown
it is the provider's, it is collapsed by default, and it never becomes the thing
the eye lands on before the answer. Where reasoning is off or unsupported, the
turn simply streams its answer with no chrome above it.

---

## BUG-208 — The product explains itself on every screen, and the guide it should be explaining from is unreachable

**Severity: Medium. Area: UI density / documentation surface. Status: Open.**

**Observed.** Raiker teaches on the page instead of showing state. Counted across
the component tree on 2026-08-15 — static sentences only, nothing interpolated,
comments and styles excluded:

> **23,236 characters of explanatory prose, 216 sentences, in 53 components.**

Roughly 3,700 words of documentation compiled into the interface. The heaviest
surfaces, by characters of static prose:

| Component | Chars | Sentences |
|---|---|---|
| `ModelsView.svelte` | 2,783 | 20 |
| `SecurityLogin.svelte` | 1,342 | 11 |
| `ProjectsView.svelte` | 1,220 | 9 |
| `Runtime.svelte` | 1,149 | 7 |
| `ExtensionsView.svelte` | 1,122 | 6 |
| `CheckpointsView.svelte` | 927 | 9 |

It reads as documentation because it is documentation:

> *"A project is a named scope for an ongoing piece of work: its own folder inside
> the workspace, plus the sessions and checkpoints created while it is active."*
> — `ProjectsView`, above the list of projects

> *"The recorder timeline: metadata snapshots taken at safe points as sessions
> run. Nothing here executes a restore — every entry is a record of where the
> workspace stood."* — `CheckpointsView`, page header

> *"The model profiles Raiker can talk to. The choice of backend belongs to you —
> local, home-lab, or hosted — and there is never a silent fallback between
> them."* — `ModelsView`, page header

Each is well written and true. None of it is state, and none of it is a next
action; a returning owner reads the same paragraph on every visit to learn
nothing they did not know the first time.

**The blocker, and why the order matters.** `docs/guide/` already holds exactly
this material in eight documents — `getting-started`, `connecting-a-model`,
`permissions-and-runtime-modes`, `working-in-chat`, `tasks-and-projects`,
`extensions-and-mcp`, `troubleshooting`. **The product cannot reach any of it.**
There is no guide route, no help surface, no API that serves it, and no component
that links to it; the only path in is the README's Documentation list, which a
person running the app is not reading. So the prose is on the page because the
page is the only place it can be.

That fixes the sequence: **give the product somewhere to send people, then take
the paragraphs off the screen.** Stripping first would delete the only copy an
owner can actually get to.

**Required fix, in slices.**

| Slice | Work | Why it is separable |
|---|---|---|
| **A — the guide becomes part of the product** | Ship `docs/guide/` with the app and serve it read-only over the governed API, rendered with the `Markdown` component the transcript already uses. One route, `#/guide`, plus deep links to a section. | Pure addition. Nothing is removed, so it cannot regress a surface. Also fixes that a packaged install has no help at all. |
| **B — one contextual entry point** | A single quiet control per page — the `Details` disclosure pattern that already exists — resolving to that page's guide section. `Models` → `connecting-a-model`, `Permissions` → `permissions-and-runtime-modes`, `Projects`/`Tasks` → `tasks-and-projects`. | Needs A, and nothing else. Testable per route. |
| **C — move, do not delete** | For each page header paragraph: confirm the sentence exists in the guide section, move it there if it does not, and only then remove it from the component. The guide gains what the UI loses, so the total stays truthful. | The discipline that keeps this from being a copy cull. Do it page by page, heaviest first — Models, Security, Projects, Runtime, Extensions, Checkpoints. |
| **D — the rule, written down** | A component may carry: the state, the next action, and a failure's reason with its remediation. Everything else lives in the guide. Add it to `VISUAL_DESIGN_SPEC.md` so the next surface is built to it. | Independent of the code; without it the prose returns one card at a time. |
| **E — the density that is not prose** | The provider card still renders five status chips, a three-clause cost sentence and five controls, thirteen times over on one page. Collapse the posture chips into one capability line, show cost only where there is cost, and demote three controls into `Details`. | Layout rather than words; separable from A–D. |
| **F — the auto emoji reaction** | Raiker appends an emoji to the **owner's own message** by regex on its text (`"Thanks!"` → ❤️). It is not a reaction to anything Raiker did, and it is the one element of the transcript that is neither state nor content. Decide deliberately whether it stays. | A product call, not a cleanup; deliberately last. |

**Required user-interface outcome.** A page says what is true right now and what
the owner can do next. Anything that begins *"A project is…"* or *"The recorder
timeline is…"* lives in the guide, one click away from the surface it describes,
and the app can open it without a browser tab or a repository checkout. The
measure to hold this to is the one that produced the finding: re-run the count,
and the static prose in `apps/web/src/lib` should be a small fraction of 23,236
characters, with the difference **present in `docs/guide/`** rather than gone.
