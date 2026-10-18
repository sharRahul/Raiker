## Goal

Make Raiker a secure AI product that combines **four** things: a polished AI
assistant, a governed **personal autonomous agent**, **a capable coding/build agent**, and an
extensible governed agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a coding agent, Raiker
should read a repository, make the change, run the tests, read the failure and
iterate to green, in one governed session. As a platform, Raiker should provide
the governed runtime foundation for models, tools, plugins, interfaces, memory,
approvals, audit events, checkpoints, and integrations.

Governance, observability, policy awareness, control and security are **inherent
properties** of that runtime, not optional layers added around the agent.

> **Which open work blocks which pillar is in [`PILLAR_MAP.md`](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
> and how an action reaches an executor at all is in
> [`GOVERNANCE_ENTRY_PATHS.md`](PERSONAL_AUTONOMOUS_AGENT_SPEC.md).** This preamble is
> repeated in several plans because each is read on its own; the pillar map is
> the one place that says what the whole set adds up to.

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
`docs/architecture/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

# To be fixed

Open defects originally found while executing
[the live manual test plan](TESTING.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Every deferred item found by the FIXED-01 through FIXED-48
audit is an explicit BUG with a required user-interface outcome, so closing
backend work cannot leave an invisible or misleading product surface.

**Closed entries live in [`FIXED_ITEMS.md`](FIXED_ITEMS.md).** They are still
evidence — what was observed, the root cause, and the user-interface outcome that
had to be true before it could be called closed — but they are no longer mixed in
with the open work, so this document answers one question: what is left.

[`GAP_BUILD_CHAT.md`](BUILD_WORKSPACE_SPEC.md) — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: `screenshots/not-working/` (defects),
`screenshots/working/` (verified behaviour).

**Only unresolved BUG entries are indexed below.** Closed bugs and completed memory/governance reviews are recorded in [`FIXED_ITEMS.md`](FIXED_ITEMS.md), with historical rationale in Git history. The separate [Build/Chat capability gap ledger](BUILD_WORKSPACE_SPEC.md) is not a BUG list.

**Historical ID collision:** `BUG-280` was reused for two unrelated findings. The closed Observability empty-state defect is [FIXED-391](FIXED_ITEMS.md#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line); the weather/provider live-evidence `BUG-280` closed in two halves, the clock as [FIXED-539](FIXED_ITEMS.md#fixed-539--a-real-turn-now-answers-from-raikers-clock-and-the-weather-half-still-cannot-be-measured-here) and the weather as [FIXED-926](FIXED_ITEMS.md#fixed-926--a-real-model-read-real-weather-from-open-meteo-was-bug-280).

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced again 2026-08-21; foreground SSH/Daytona and safeguarded egress/credential/trust foundations ship, while live container and external trust-anchor proofs remain |
| [BUG-248](#bug-248--twenty-seven-live-specs-still-sign-in-inside-a-test-body) | Low | Live test harness | Open remainder — reduced again 2026-09-29 by four (`composer-parity-and-turn-honesty`, `fts5-mem03-bug194`, `mem04-bug194-observations`, `bug-37-39-40-41`), each re-run live and brought up to the product; converting them found [FIXED-632](FIXED_ITEMS.md#fixed-632--an-approval-card-covered-settings-save-changes) and [FIXED-633](FIXED_ITEMS.md#fixed-633--choosing-the-default-density-closed-the-panel-it-was-chosen-in). Ten sign in on their own: three must, and seven provider scenarios can now be converted one at a time with reachable providers |
| [BUG-287](#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider) | Medium | Design / image runtime / live evidence | Open remainder — reduced 2026-10-18: real OpenAI generation, edit, four-result variation, lineage, permission-off refusal and empty-allowlist refusal passed; a source-image provider refusal and a live research-reference **Sent with** check remain |
| [BUG-339](#bug-339--the-issue-to-pull-request-routine-has-a-template-and-no-runner) | Low | Tasks / routines | Open remainder — reduced 2026-10-18 ([FIXED-950](FIXED_ITEMS.md#fixed-950--the-issue-to-pull-request-routine-can-now-be-scheduled-as-a-build-task-bug-339-reduced)): the template schedules a governed Build task from Settings → GitHub; RR-40 live evidence against a consented repository remains |
| [BUG-346](#bug-346--an-accepted-build-write-failed-as-an-invalid-tool-call-on-an-ollama-cloud-model) | Medium | Build / approvals / Ollama | Open — found 2026-10-18 driving BR-D01 live; reproduction below, root cause not yet known |

The open defects below retain their original reproductions and remediation contracts. Closed defect evidence is in [`FIXED_ITEMS.md`](FIXED_ITEMS.md); previously removed topic-review rationale remains in Git history.

---

## BUG-194 — The governed shell has an OS boundary, but no interactive, background or remote execution

**Severity: Low (was Medium, was High). Area: shell / sandbox / recovery.
Status: Open — reduced three times.**

**2026-08-28 verification.** Docker is installed but its daemon is unavailable
on this host, and Podman is not installed. Raiker therefore continues to refuse
container-network execution rather than claim unverified direct-DNS/direct-TCP
bypass, active-stream revocation, or copy-on-write credential-delivery proof.
The container proof and a production signing anchor remain open.

**2026-08-21 update.** Foreground SSH and Daytona now enter the same
`CommandService` lifecycle through a canonical length-prefixed envelope, exact
SSH host-key pin, Daytona cost reservation and fixed remote supervisor path;
neither falls back to the host. Container egress has normalized domain/port
policy, public-address pinning, HMAC-scoped grants, revocation state and a real
CONNECT proxy. Credential work has a disposable workspace/Git snapshot,
failure-closed scanner, discard-only quarantine API and review UI. Runner trust
distinguishes publisher-verified, package-relative and developer-unverified
postures, and placeholder supervisor digests were removed.

The item remains open for unproved parts: this host had no Docker/Podman daemon
for live direct-DNS/direct-TCP bypass, active-stream revocation or credential
copy-on-write delivery/merge tests, and no production signing anchor. Windows
PTY and restart reattachment remain explicitly unsupported. Configuration
never turns any of these capabilities on.

**What changed, 2026-08-15.** A governed command now runs inside a real
operating-system boundary, and what that boundary enforces is **measured rather
than declared**. Closed as [FIXED-195](FIXED_ITEMS.md).

**What changed, 2026-08-17.** The two rows this entry called the smallest are
closed as [FIXED-229](FIXED_ITEMS.md), and they were built the way the entry said
they had to be — as components, together, with the enforcer.

The 2026-08-16 review declined to advance them on the grounds that background
execution needs "a supervisor that outlives the turn together with the
agent-facing tool that makes a background run observable; shipping either half
alone is worse than refusing." That reasoning was right and is what this round
followed. Both halves shipped in one change:

* **The enforcer.** Every background run holds a lease. A thread renews it only
  while the process it is watching is alive and this runtime is up, so a lease
  that keeps moving forward *is* the evidence of a live run and a lease that
  stops is evidence of the opposite — including on a hard kill, where no handler
  of ours runs at all. `reconcile_leases` terminates and finalises any run whose
  lease lapsed, with a receipt naming `command_background_lease_expired`. A
  foreground run holds no lease and is never swept, so a missing lease is never
  read as an expired one. A background run is also bounded by a hard two-hour
  ceiling, because a run with no deadline is a run whose lease renews forever and
  the reclaim path would never fire.
* **The observing half.** `background_run` — `list`, `poll`, `log`, `wait`,
  `kill`, `input` — owner-scoped on every action, reading the durable run row and
  the already-redacted output chunks. It starts nothing and grants nothing: a run
  it can see is one the session's command grant already authorised.

**The tool is not called `process`, and that matters.** The original entry named
it `process`. That name already routes to the `process_execution` capability —
arbitrary host process control, which the runtime classifies as critical and the
policy holds for approval. Registering an observation tool under it would have
attached a read verdict to host process control. The collision surfaced as a
hard `policy actions cannot have conflicting verdicts: process` failure rather
than a silent widening, which is the invariant working.

**PTY and raw input are closed on POSIX and stay open on Windows.** `openpty`
gives the child a controlling terminal and `background_run action=input` types
into it; the proof is that the *program* read the bytes, not that the terminal
echoed them. Windows is unchanged and the reason is unchanged: `CreatePseudoConsole`
builds its console objects in the caller's context, unreachable from an
AppContainer token, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as
incompatible with the handle-list attribute the boundary requires.
`pty_supported()` reports the platform's real answer, and input to a run without
a terminal is refused as `command_input_requires_pty` rather than written to a
pipe where the bytes would arrive and the effect would not.

**What changed, 2026-08-17 (second pass).** The two rows this entry had left as
the largest components are closed as [FIXED-238](FIXED_ITEMS.md) and
[FIXED-239](FIXED_ITEMS.md), and they were built the way the entry said they had
to be — together, because each alone is worse than neither.

* **Restart reattachment.** A background run is started inside a detached
  supervisor that is a module of the Raiker package, so it is packaged by
  construction. It holds the child in its own session, the deadline that bounds
  it, the redactor, and an append-only journal, and it is reached over an
  `AF_UNIX` socket speaking the authenticated frames the protocol codec already
  had cross-language vectors for. The socket path and the instance key live
  encrypted in `command_runs.encrypted_backend_handle`, so **reattachment is an
  authentication rather than a pid lookup** — which is precisely the objection
  this entry raised against building it on a pid file. Every case the runtime
  cannot prove — no handle, a locked vault, a socket that is gone, a socket that
  fails the key — still produces the honest `lost` receipt.
* **Persistent environment.** The container's name is a function of owner,
  session and profile rather than of the run, so a session's second command
  lands in the boundary its first one left behind. Persistence shipped with its
  reset, because an environment that accumulates state and can never be cleared
  is worse than one that never persists.

**Still observed.** Select `native_sandbox` and request network, credential, SSH
or Daytona execution and the backend fails closed with the corresponding named
reason; the native sandbox additionally still refuses background, PTY and
persistence, because its capability set comes from the host probe and none has
been measured inside an AppContainer — and per-run AppContainer profiles stay
deliberate, since the container SID is a pure function of the name. On
**Windows**, restart reattachment is refused by name
(`command_supervisor_platform_unsupported`) and a background run is still
reconciled to `lost` across a restart.

**Root cause, per item.** Each of these is a component rather than a flag, which
is why none of them was half-built:

| Remaining item | Why it is not built |
|---|---|
| ~~**Background start/poll/wait/log/kill**~~ | **Closed 2026-08-17** as [FIXED-229](FIXED_ITEMS.md#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one) on the `local_native` backend, with the lease, the reclaim path and the `background_run` tool shipped together. Not claimed for `native_sandbox`, whose capabilities come from the host probe. |
| ~~**PTY and raw input**~~ | **Closed on POSIX 2026-08-17** as [FIXED-229](FIXED_ITEMS.md#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one). Windows unchanged: `CreatePseudoConsole` builds its console objects in the caller's context; they are not reachable from an AppContainer token without an explicit capability, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. A PTY that only works outside the sandbox is not the control the row describes. |
| ~~**Restart reattachment**~~ | **Closed on POSIX 2026-08-17** as [FIXED-238](FIXED_ITEMS.md#fixed-238--a-background-run-could-not-survive-the-restart-of-the-runtime-that-started-it), with the detached supervisor, the authenticated `AF_UNIX` control channel and the encrypted restart-safe handle shipped together. Windows unchanged and refused by name: a named pipe is reachable by name from any session on the machine, so the equivalent needs its own design and its own proof rather than the same code with a different transport. |
| ~~**Persistent environment**~~ | **Closed for the container backend 2026-08-17** as [FIXED-239](FIXED_ITEMS.md#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist), together with the owner's reset and reset-and-clear-cache controls. Per-run AppContainer profiles are still created and deleted around each command, deliberately: a predictable container name is a hole, because the container SID is a pure function of the name. |
| **Filtered domain egress** | The AppContainer loopback exemption needs elevation, and a Linux proxy-only namespace is a separate netns build. Refused with a named reason on every backend rather than partially claimed. |
| **Credential delivery and delta quarantine; SSH; Daytona** | Unchanged. None is a Codex or Claude Code control; all three remain storage contracts and selectable-but-refused profiles. |
| ~~**Container session supervisor**~~ | **Closed 2026-08-17** as part of [FIXED-239](FIXED_ITEMS.md#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist): the session's container is created once and reused, liveness is asked of the runtime rather than assumed, and the backend is held for the life of the service so there is somewhere to remember it. |
| **Signature verification of the runner** | The runner's SHA-256 is recorded at build time, checked before use, and carried into the receipt. That detects corruption and casual replacement; it is **not** protection against an attacker with write access to the install directory, who could replace Raiker itself. Authenticode chain verification is not implemented. |

**Required fix.** For each remaining row: Windows PTY and Windows restart
reattachment once the ConPTY/AppContainer and named-pipe-authorisation questions
are settled by a spike; an authenticated domain proxy with DNS/address checking
and active revocation; purpose-bound credential delivery plus two-pass delta
quarantine; and SSH/Daytona supervisor adapters. Prove every backend
independently and preserve the no-fallback and honest-`lost` rules.

**Required user-interface outcome.** Further met. Runtime shows the exact probed
boundary and its six measured observations, and Build shows the boundary a
command ran in plus failure navigation. Background and PTY are agent-facing
controls rather than interface ones — an agent starts and observes a background
run through `run_command`/`background_run`, and the run appears in the same
owner-visible command list, with the same receipt, as a foreground one. Each
environment card now lists the capabilities that boundary really has, built from
the backend's own `CommandFeatures` rather than from configuration, and carries
the **Reset environment** and **Reset and clear cache** controls where — and
only where — the boundary persists. **Filtered network remains absent** rather
than disabled: an absent control is the honest projection of an unbuilt
capability, where a disabled one implies it is a setting away. No row may turn
green from configuration or specification alone.

## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline. Re-verified end
to end on **2026-08-08** against hosted Anthropic (see
[the live manual test plan](TESTING.md) for the full round):

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
seven tabs on real data; Settings' sections; theme cycling system → light → dark;
the notification centre and Mark all read; the STOP switch; and adaptive
navigation at 375 / 768 / 1024 / 1440 px with no horizontal overflow, correct
`aria-expanded`, and focus returned to the trigger.

---

## BUG-248 — Twenty-seven live specs still sign in inside a test body

**Severity: Low. Area: live test harness. Status: Open remainder — raised
2026-08-30 while closing [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in),
reduced from twenty-seven to twenty the same day
([FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite)),
to **twelve** on 2026-09-04, to eleven on 2026-09-21 and to **nine** on
2026-09-28, then recounted as **ten** on 2026-09-29 under the stricter
test-body definition below.**

**2026-10-18, later — the seven type a key, so they are owner-run.** Each of
the seven fills a provider key from `RAIKER_LIVE_*_KEY` into the Models dialog.
An agent session must not enter a real provider key, so each conversion is
re-run by the owner with those variables set, or after the specs are taught to
reuse a connection the owner made through Models.

**2026-10-18 — provider access is no longer the reason to defer the seven.**
OpenAI, OpenRouter, Anthropic and Ollama each completed a real turn from this
host while closing [FIXED-944](FIXED_ITEMS.md#fixed-944--all-four-providers-answer-the-owner-identity-question-with-the-chosen-name).
The seven provider scenarios are still converted only one at a time and re-run,
as this entry requires. The same round also found that `signInAsOwner` rejected
the current exact **Welcome** heading; [FIXED-946](FIXED_ITEMS.md#fixed-946--the-live-sign-in-helper-rejected-the-current-welcome-heading)
repairs that shared precondition without changing the inline-sign-in count.

**2026-09-29 — four more, and two product defects behind them.**
`composer-parity-and-turn-honesty-live`, `fts5-mem03-bug194-live`,
`mem04-bug194-observations-live` and `bug-37-39-40-41-live` sign in through
`signInAsOwner`. Each signed in on its first run and then failed on the product
having moved — Memory's recall posture now on *Recall & indexing* with the picker
on Settings → Memory engine, Observations on *Suggestions*, the terminal button
named *Show the governed terminal*, Tasks opening on its composer, message search
an explicit **Search message text**, density under a disclosure — and each was
brought up to the product rather than relaxed. Two of the failures were the
product, not the spec, and are fixed:

* the retention step passed on one run and timed out on the next because an
  approval card covered Settings' **Save changes**
  ([FIXED-632](FIXED_ITEMS.md#fixed-632--an-approval-card-covered-settings-save-changes));
* choosing *Comfortable* closed the disclosure it was chosen in
  ([FIXED-633](FIXED_ITEMS.md#fixed-633--choosing-the-default-density-closed-the-panel-it-was-chosen-in)).

`checkModelReady` now takes the first outcome it finds: an exhausted account
says so twice, as a chip and as the outcome line. That is how the round found
the provided key's credit balance exhausted part-way through, confirmed against
the provider directly. Every step of the four was run live after its edit;
`fts5`'s second test could not be re-run end to end after that point, so its
corrected search step was driven on its own against the transcript its earlier
turn had written, and passed.

**The count, recounted.** This entry counted sign-ins inside a test body.
Counting every live spec that signs in without the shared helper gives ten after
this pass: `review-first-run-honesty`, `wizard-workbench-composer` and
`workbench` must keep their own, and `add-01-container-providers`,
`add-03-machine-identity-providers`, `bug-29-34`, `bug-36-38-42-43`,
`bug-69-model-readiness`, `governed-shell-provider-matrix` and
`review-provider-matrix` each need OpenRouter, OpenAI, Gemini or Ollama. Those
providers are now reachable here except for Gemini, so these scenarios can be
converted and re-run in later one-spec passes; the rule below still says they
are not converted blind.

**2026-09-28 — two more, and the one reverted on 2026-09-04 among them.**
`review-readiness-probe-live` and `c17-b14-recall-and-inline-diff-live`, run
against the second 2026-09-28 round's workspace with a key that answers. Both
signed in through the shared helper on the first run and then failed on the
product having moved, never on the sign-in:

* `review-readiness-probe` waited for a **Hosted** tab the Models redesign
  removed. It now reaches the card through `hostedProviderCard`, and asserts
  what its title claims — that **Test** settles on an outcome for the pinned
  model — through `checkModelReady` rather than only logging the card's text.
* C17's memory import is on *Recall & indexing* now, and a record shows on
  *Memories*. B14 met the same Build drift `bug-242-build-restore-mem-09-live`
  records — the project behind `+`, a model chosen for the turn, and **Run**
  rather than **Send** — and a reset workspace with no project, so it creates
  one first.

All three tests then passed live
([the second 2026-09-28 round](TESTING.md)).

**2026-09-04 — eight more, each re-run against a *used* workspace.**
`guide-surface`, `review-chat-surface`, `containment-surface`, `visual-refresh`,
`knowledge-map-work`, `reference-graph`, `bug-69-local-model-library` and
`bug-69-huggingface`. Re-running each against a workspace that already had an
owner, a scan and a connection is what made the conversions evidence rather than
substitutions: three of the eight failed *after* the sign-in, for reasons that
were nothing to do with it, and each of those is a defect this round fixed rather
than an assertion it relaxed —

* `containment-surface` documented its seeding as a shell block for a person to
  run by hand, so a round that did not run it met a red assertion about a list
  that was empty *because the product was behaving correctly*. It now performs
  its own precondition and skips with the reason when it cannot.
* `bug-69-local-model-library` asserted `getByText("Raiker Live GGUF")` against
  the whole page. Its own scan puts that name into every model picker on the
  screen, so the assertion passed exactly once — on a workspace where nothing had
  been scanned before — and then failed as a strict-mode violation naming four
  elements. Scoped to the inventory the test is about.
* `bug-69-huggingface` answered "no network to huggingface.co" with a
  three-minute timeout on a click, and blamed the click. It now states the
  precondition after the sign-in and the search have both actually happened, so
  what it still verifies on such a host is real.

**One conversion was reverted rather than committed unverified.**
`c17-b14-recall-and-inline-diff-live` needs a provider that answers, and this
round's key does not ([BUG-273](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more)).
The rule this entry states — *a blind bulk edit would replace verified sign-ins
with unverified ones* — applies to a careful edit that cannot be re-run just as
much as to a blind one.

**Observed.** Thirty-seven live specs delegate to `signInAsOwner`. Twenty-seven
others sign in *inline* in a test body, and those copies are the ones BUG-229
described: several still key on the empty-workspace greeting.

**Seven are done, each re-run as it was converted** — `all-pages`,
`all-pages-theme`, `observability`, `default-ollama`, `memory-knowledge-context`,
`memory-semantic` and `memory-vector-index`. That found three pieces of drift
nothing else would have, including a spec still driving a Vite dev server on port
5174; they are recorded in FIXED-328. **Ten are left** after the 2026-09-29
recount, and the reason they are left is unchanged.

**Why they were left.** They vary in a way the function-shaped ones did not —
different bases, different landing routes, some navigating to the route under
test *before* signing in. And `page.goto` with only the hash changed does not
re-render this app (recorded in `real-work-chat-build-live.spec.ts`), so
replacing "go to Models, sign in there" with "sign in on the workbench, then go
to Models" is a behaviour change per spec rather than a substitution. A blind
bulk edit would replace twenty-seven verified sign-ins with unverified ones.

**Three of them must keep their own.** `review-first-run-honesty-live`,
`wizard-workbench-composer-live` and `workbench-live` sign in *as the thing under
test*; sharing the helper there would hide the behaviour they exist to check.

**Proposed fix.** One spec at a time, each re-run as it is converted — which is
how the evidence behind its FIXED entry is refreshed rather than invalidated.

**Required user-interface outcome.** None; this is harness-only.

---

## BUG-287 — The image provider round trip is unverified against a real provider

> **2026-10-03 — and now references.** [FIXED-733](FIXED_ITEMS.md#fixed-733--research-could-only-reach-a-picture-by-being-pasted-into-the-prompt)
> lets a consented research reference travel with a prompt as its own audited
> argument, composed after the prompt by the executor. It is proven to the
> provider's request body with a stubbed transport, not against a real
> provider, and the research turn that makes a reference needs a search
> provider this host cannot reach either. The live round that closes this entry
> should send one reference and read it back in the inspector's **Sent with**.

> **2026-09-15 — what the round trip now has to prove changed.**
> [FIXED-542](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all)
> found that `image_generation` had no key in `CAPABILITY_GATE_MAP`, so the
> owner's switch reached no gate: the action was approval-required by policy and
> nothing else. The row is there now, which means a live round has a second thing
> to measure — that turning **Image generation** off actually refuses a
> generation, not only that a key produces an image.

**Severity: Medium. Area: Design / image runtime / live evidence. Raised while
closing [BUG-277](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network),
2026-09-13.**

**Observed.** Before 2026-10-18 the lineage runtime and canvas were verified only
with controlled transports because the host refused provider egress. That limit
is gone. A real OpenAI `gpt-image-1` round generated a cobalt-blue mug, edited it
to an emerald-green mug with a gold rim, and returned all four requested
variations. The canvas showed six assets, two versions for the edited chain,
**Edited from** lineage and the four assets under **From the same request**.

**What *was* exercised against the running server.** The governed route, the
owner-scoped subject resolution, the count bound and its zero case, lineage
recorded on refusals, `project_id` carried from the composer through to the
stored row, and the canvas composing real rows read back through `GET /api/images`.
The multipart wire format is proven against a real socket — a live HTTP server
parses the body with Python's own MIME parser and the image comes back byte for
byte (`tests/test_multipart_egress.py`).

**What is not known.** The real-provider shape is now known for OpenAI generation,
edit and four-result variation. Two contracts remain unverified: how a provider
refusal reads when the *source image itself* is refused, and whether a consented
research reference reaches the real provider and appears in the inspector's
**Sent with** list. Design currently edits generated assets; it does not expose
an arbitrary source-image upload that could honestly manufacture the first case.

**Proposed fix.** Add or identify the governed source-image path and exercise a
real provider refusal against it. Separately, create one consented research
reference with a reachable search provider, send it with a real image request,
and read it back under **Sent with**. Keep both as evidence tasks: the successful
real OpenAI round must not be repeated merely to prove already-observed shapes.

**2026-10-18 — real-provider evidence.** The owner entered the image-capable key
through Models. With **Image generation** off, Design disabled **Generate** and
named the gate. With it on and no allowed provider host, the attempt became a
recorded refusal naming the empty allowlist. After `api.openai.com` was allowed,
generation, edit, lineage and four variations completed and were inspected in
the running UI. The same pass fixed [FIXED-945](FIXED_ITEMS.md#fixed-945--design-offered-image-models-from-unconnected-providers),
found because the picker also offered an unconnected Gemini profile.

**Interface outcome that has to be true before this closes.** The two remaining
contracts above are observed through a real provider and shown in the inspector.

---

## BUG-339 — The issue-to-pull-request routine has a template and no runner

**Severity: Low. Area: Tasks / routines. Status: Open — found 2026-10-12
building ADD-27 GH-55.**

**Observed.** `raiker/github/routines.py` names the routine's steps and, given
its delegation, which would run and which would ask — read-only by default,
writes only under a delegation re-validated first, never merge. Scheduled
routines (`raiker/runtime/executors/scheduled.py`) run a bounded **read-only**
subagent, so nothing can yet carry the plan's write steps out unattended.

**Effect.** The issue-to-PR routine of PA-S07 / RR-40 is an owner-driven flow
today, not a scheduled one.

**Proposed fix.** A routine kind that runs a governed agent turn (not a
subagent) under the routine's delegation reference, with the plan's decisions as
its ceiling; live evidence is RR-40 against a consented repository.

**2026-10-18 — narrower than it reads.** A scheduled **Task** already runs a
governed agent turn (`raiker/tasks/scheduler.py`), and the authority router
already lets an AI-proposed repository write run unprompted only under a
covering, re-validated delegation (`_repository_delegation` in
`raiker/runtime/authority/router.py`); anything uncovered parks for approval.
What is missing is the binding: creating that Task from the issue-to-PR template
with the plan's steps as its instructions and `NEVER_IN_ROUTINE` as a refusal,
plus RR-40's live run, which needs a connected model and a consented GitHub
repository on this host.

**2026-10-18, later — the binding ships.** [FIXED-950](FIXED_ITEMS.md#fixed-950--the-issue-to-pull-request-routine-can-now-be-scheduled-as-a-build-task-bug-339-reduced)
adds `POST /api/github/routines/issue-to-pr` (a read-only plan plus the Build
task's instructions) and Settings → GitHub → *Issue to pull request*, which
schedules that task through Tasks. **What remains is RR-40:** one scheduled run
against a consented repository with a connected model and a delegation, read
back as a branch, a commit and a pull request receipt, with a merge never
attempted unprompted.

## BUG-346 — An accepted Build write failed as an invalid tool call on an Ollama cloud model

**Severity: Medium. Area: Build / approvals / Ollama. Status: Open — found
2026-10-18 while driving [BR-D01](BUILD_WORKSPACE_SPEC.md) live.**

**Observed.** On a fresh workspace with **File writes** and **Patch apply** on,
Ollama `gpt-oss:120b-cloud` chosen on Models, and a Build turn in a managed
project asked to create `notes.txt`, Build showed the proposed one-line diff in
*Waiting on you*. After **Accept** the turn resumed and its row read
**Write file notes.txt failed**; the answer said once that the capability still
required approval, and on a second run that *the requested tool call was
invalid*. No file was written. Of four runs, two reached the approval, one
answered with a JSON plan and called no tool, and one met the provider's 402 on
`deepseek-v4-pro:cloud`. After the turn the composer also said *No readiness
check exists for this exact model* and disabled **Run**, for a model kept
through the Ollama picker without **Check**.

**What is known.** The BR-D01 outcome read the turn correctly as `no_change`
(nothing was written, so nothing was claimed). The resumed call's row stays
`waiting` in `tool_actions` while the live row says failed, so the resolve
path's result is what to read first: `routes_approvals` → `approval_outcome`,
and whether the model's `write_file` arguments as validated at proposal match
what the executor accepts after approval.

**Proposed fix.** Reproduce with a stub model that proposes a fixed
`write_file` call so the model is out of the loop; read the resolve response and
the executor's refusal; fix the mismatch; then add the real-turn half of
`br-d01-build-outcome-live.spec.ts` (create a file, approve, read **Not
verified** with the declared check *not run after the last change*).

**Required user-interface outcome.** An accepted write is applied once and the
row says so, or the card states the exact reason it was not applied.

## Decision statements added 2026-10-05

**Basis:** repository snapshot `2898b247c9e02d537c6f61e866ed670578e49b42`.
These statements supply missing implementation direction. **Recommended** means
a proposed choice, not an owner approval or a verified fix. The original BUG
entries retain their status and acceptance evidence.

### BUG-226 and BUG-228 — Do not create alternate execution contracts
**Retired from this ledger 2026-10-18** ([FIXED-951](FIXED_ITEMS.md#fixed-951--three-open-entries-were-decided-boundaries-or-superseded-work-not-defects-bug-226-bug-228-bug-234));
the boundary they describe is kept in [KNOWN_LIMITS.md](../architecture/KNOWN_LIMITS.md#boundaries-raiker-chose).

**Decision — retained deferral for hooks; recommended convergence for UI.**
Keep `mcp_tool` and `agent` hook types unsupported until each has bounded,
non-escalating authority, its own resource budget, recursion limits and
execution-time revalidation. For contributed UI, follow the one MCP Apps
contract instead of implementing a second `panels.json` renderer. BUG-228 may
close as superseded once the replacement scope is accepted and its obsolete
promises are reconciled — both done 2026-10-18.

**Reason and acceptance.** A hook must not call a tool the originating turn
cannot call. Two contributed-UI models duplicate permission, isolation and
accessibility work. Test denial/revocation and recursion for hooks, and
per-app grants, message validation, iframe isolation and keyboard access for UI.
A sandboxed iframe still runs third-party code; the product must describe its
boundary accurately rather than claim that no browser code runs.
References: [hook type contract](../../raiker/hooks/contracts.py),
[MCP Apps in KNOWN_LIMITS](../architecture/KNOWN_LIMITS.md#boundaries-raiker-chose),
[DEC-23](TESTING.md).

## Personal-agent direction — 2026-10-07

The owner accepted the [personal-agent architecture](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
inspired by Meta Muse, Claude.ai, OpenClaw and Hermes Agent. New durable goals,
context, proactivity, outcome verification and reviewed learning work is owned
by [PAA-01–PAA-11](PERSONAL_AUTONOMOUS_AGENT_SPEC.md). Existing items in
this ledger keep their status, dependencies and evidence; accepting the target
does not close a defect or mark an ADD shipped. Browser ADD-23, off-machine
ADD-11, memory ADD-25 and self-improvement ADD-05/06 retain their own boundaries.

Personal-agent release claims require the relevant PA-S scenarios and existing
CR evidence gates. Preserve capability defaults, quiet-hours DEC-21a, accepted
Git OAuth scope, model choice and coding quality. New observations go to the
proper defect/evidence ledger; do not duplicate the PAA backlog here.
