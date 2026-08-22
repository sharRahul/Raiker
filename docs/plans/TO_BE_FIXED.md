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
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced again 2026-08-21; foreground SSH/Daytona and safeguarded egress/credential/trust foundations ship, while live container and external trust-anchor proofs remain |
| [BUG-216](#bug-216--checkpoint-capture-fails-silently-on-a-deep-windows-path-and-only-logs-it) | High | Checkpoints / Windows paths | **Fixed 2026-08-21 — FIXED-240** |
| [BUG-217](#bug-217--test_the_posture_reports_the_pragma_in_force_not_only_the_one_resolved-overflows-the-stack-on-windows) | Low | Test isolation / SQLCipher posture | **Fixed 2026-08-21 — FIXED-244** |
| MEM-06 … MEM-14 | Medium → Low | Memory reliability | Open: MEM-07 … MEM-10. MEM-06 closed 2026-08-21 (FIXED-241); MEM-11/12 remain regression-proven. See [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md) |
| [BUG-218](#bug-218--auto-mode-has-no-alignment-check-of-its-own) | Medium | Decision modes / Build / Chat | Open — raised 2026-08-21 |
| [BUG-219](#bug-219--there-is-no-deny-unless-preapproved-posture) | Low | Approval modes | Open — raised 2026-08-21 |
| [BUG-220](#bug-220--nothing-owns-a-set-of-delegated-child-tasks) | Medium | Tasks / delegation | Open — raised 2026-08-21 |
| [BUG-221](#bug-221--a-plugin-is-recorded-and-then-provides-nothing) | Medium → Low | Plugins / extensibility | Open — reduced 2026-08-22 (FIXED-256): hooks are contributable; skills, MCP servers and panels remain |
| [BUG-222](#bug-222--there-is-no-way-to-turn-every-hook-off) | Low | Hooks | **Fixed 2026-08-22 — FIXED-254** |
| [BUG-223](#bug-223--twenty-two-lifecycle-events-are-specified-and-never-emitted) | Medium | Hooks / lifecycle | **Fixed 2026-08-22 — FIXED-255** |
| [BUG-224](#bug-224--the-node-25-web-test-run-cannot-see-jsdoms-localstorage) | Low | Web tests / environment | **Fixed 2026-08-22 — FIXED-258** |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B9, B11, B12, B17, B19 complete; 9 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (C14 **complete** — branch-from-here closed as FIXED-227; 13 items remain) |

The memory audit of **2026-08-11** has its own document,
[`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md), written to this
standard. Its MEM-01 and MEM-02 are closed in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md) as FIXED-187 and FIXED-188, and MEM-03 and
MEM-05 as FIXED-230 and FIXED-231, MEM-11, MEM-12 and MEM-13 as FIXED-232,
FIXED-233 and FIXED-234, MEM-14 as FIXED-236, and MEM-04 as FIXED-237. Two were
raised in their place. MEM-10: closing MEM-03 built the *selection* of an
embedding space, and a default install still has nothing semantic to select.
MEM-06, the binding constraint on the graph leg MEM-12 made reachable, closed
2026-08-21 as FIXED-241. MEM-07 through MEM-10 remain open there rather than
being duplicated here.

---

## BUG-194 — The governed shell has an OS boundary, but no interactive, background or remote execution

**Severity: Low (was Medium, was High). Area: shell / sandbox / recovery.
Status: Open — reduced three times.**

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
| ~~**Background start/poll/wait/log/kill**~~ | **Closed 2026-08-17** as [FIXED-229](FIXED_ITEMS.md) on the `local_native` backend, with the lease, the reclaim path and the `background_run` tool shipped together. Not claimed for `native_sandbox`, whose capabilities come from the host probe. |
| ~~**PTY and raw input**~~ | **Closed on POSIX 2026-08-17** as [FIXED-229](FIXED_ITEMS.md). Windows unchanged: `CreatePseudoConsole` builds its console objects in the caller's context; they are not reachable from an AppContainer token without an explicit capability, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. A PTY that only works outside the sandbox is not the control the row describes. |
| ~~**Restart reattachment**~~ | **Closed on POSIX 2026-08-17** as [FIXED-238](FIXED_ITEMS.md), with the detached supervisor, the authenticated `AF_UNIX` control channel and the encrypted restart-safe handle shipped together. Windows unchanged and refused by name: a named pipe is reachable by name from any session on the machine, so the equivalent needs its own design and its own proof rather than the same code with a different transport. |
| ~~**Persistent environment**~~ | **Closed for the container backend 2026-08-17** as [FIXED-239](FIXED_ITEMS.md), together with the owner's reset and reset-and-clear-cache controls. Per-run AppContainer profiles are still created and deleted around each command, deliberately: a predictable container name is a hole, because the container SID is a pure function of the name. |
| **Filtered domain egress** | The AppContainer loopback exemption needs elevation, and a Linux proxy-only namespace is a separate netns build. Refused with a named reason on every backend rather than partially claimed. |
| **Credential delivery and delta quarantine; SSH; Daytona** | Unchanged. None is a Codex or Claude Code control; all three remain storage contracts and selectable-but-refused profiles. |
| ~~**Container session supervisor**~~ | **Closed 2026-08-17** as part of [FIXED-239](FIXED_ITEMS.md): the session's container is created once and reused, liveness is asked of the runtime rather than assumed, and the backend is held for the life of the service so there is somewhere to remember it. |
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
seven tabs on real data; Settings' sections; theme cycling system → light → dark;
the notification centre and Mark all read; the STOP switch; and adaptive
navigation at 375 / 768 / 1024 / 1440 px with no horizontal overflow, correct
`aria-expanded`, and focus returned to the trigger.

---

## BUG-216 — Checkpoint capture fails silently on a deep Windows path, and only logs it

**Severity: High. Area: checkpoints / Windows paths. Status: Fixed 2026-08-21
as FIXED-240.**

**Resolution.** All Raiker-owned internal writers now use one idempotent
extended-length path boundary on Windows, including UNC paths. A regression
creates a workspace beyond 260 characters and proves bootstrap, event,
checkpoint and pre-image I/O. Capture failures persist structured health and
appear in Diagnostics and approval receipts while the approved mutation remains
best-effort. See FIXED-240.

**Observed.** Running the documented `python -m pytest` on Windows fails:

```
FAILED tests/test_approval_execution_wiring.py::TestApprovedWriteExecutes::
       test_the_previous_contents_are_checkpointed_before_the_overwrite
E   AssertionError: assert 'checkpoint_captured' in {…, 'checkpoint_capture_failed', …}
```

The approved write *executes* — `notes.md` really does contain `replaced` — but the
pre-image that makes it reversible was never stored. The event log says
`checkpoint_capture_failed` and nothing else in the product says anything at all.

**Confirmed pre-existing** against a pristine worktree at `33cfe9b`, so it is not a
consequence of this round's work.

**Root cause: `MAX_PATH`.** The failure is a function of how deep the workspace
sits, not of the code path. Reproduced deterministically by pointing the same flow
at a 175-character workspace root:

```
FileNotFoundError: [Errno 2] No such file or directory:
'…\\test_the_previous_contents_are_checkpointed_before_the_overwrite0\\ws\\.raiker
\\events\\.locks\\c2e3adc6715dca5d203f9296c39e7d96eb298aa62f49af4c2b2a93580e197253.lock'
```

`.raiker\events\.locks\<64 hex>.lock` is ~86 characters on its own. Add a workspace
root over ~170 characters and the absolute path crosses Windows' 260-character
limit, so the open fails with `FileNotFoundError` rather than anything that names
the real problem. `pytest`'s `tmp_path` is derived from the *test function name*,
which is why a long test name is what exposes it, and why CI — Linux, with no such
limit — is green on the same commit.

**Why it is more than a test problem.** `RuntimeAuthority._commit_pre_image` is
deliberately best-effort: a capture failure is recorded as a metadata event and
never propagates into the mutation result, so the write proceeds. That is the right
call for a transient failure and the wrong one for a systematic one — on an install
whose workspace is nested deeply enough, **every** governed write is irreversible
and the only trace is an event type nothing surfaces. Checkpointing before a write
is a promise the product makes; a promise that fails closed silently is worse than
one that is absent.

**Required fix.** Two parts, and neither is a one-line change, which is why this is
recorded rather than half-done:

1. **Reach the path.** Apply the Windows extended-length prefix (`\\?\`) at the
   point Raiker opens files it constructs itself under `.raiker` — the event-log
   locks, the checkpoint blob store, the operation store. Applying it to some of
   those and not others would leave the class open while appearing to close it, so
   it needs one audited helper and every internal writer moved onto it.
2. **Stop it being silent.** A capture failure that is *systematic* rather than
   transient must reach the owner: a diagnostics readiness row, and a named reason
   on the approval receipt for the write that could not be checkpointed. The
   best-effort behaviour stays — a write the owner approved should not be lost to a
   bookkeeping failure — but "this change is not reversible, and here is why" is a
   fact the owner is entitled to before they approve the next one.

**Required user-interface outcome.** Runtime/diagnostics shows a readiness row that
fails when pre-image capture is failing, naming the path limit as the reason; and an
approval whose pre-image could not be captured says so on the receipt rather than
presenting as an ordinary reversible write.

---

## BUG-217 — `test_the_posture_reports_the_pragma_in_force_not_only_the_one_resolved` overflows the stack on Windows

**Severity: Low. Area: test isolation / SQLCipher posture. Status: Fixed
2026-08-21 — FIXED-244.**

**Observed.** A full `python -m pytest` run on Windows aborts the whole process at
~87%:

```
Windows fatal exception: stack overflow

Current thread (most recent call first):
  File "raiker\storage\sqlite.py", line 832 in bootstrap
  File "raiker\storage\sqlite.py", line 733 in __init__
  File "tests\test_sqlcipher_memory_security.py", line 230 in
       test_the_posture_reports_the_pragma_in_force_not_only_the_one_resolved
```

Deselecting that one test makes the entire suite pass. **Confirmed pre-existing**
against a pristine worktree at `33cfe9b`.

**Relationship to FIXED-218.** That entry closed the *ordering* half of this file's
SQLCipher story — `cipher_memory_security` is a process-global one-way latch. This
is a different failure with the same neighbours: opening a store that reads the
pragma back, in a process where it has already been exercised, overflows the stack
in the bundled Windows SQLCipher build rather than returning a value.

**Why CI cannot see it.** The `python` job sets
`RAIKER_SQLCIPHER_MEMORY_SECURITY=off` for the whole process, and its second step
re-runs only `tests/test_sqlcipher_memory_security.py` and `test_memory_sqlcipher.py`
in a *fresh* process where nothing has latched the pragma on. The overflow needs the
combination this test only meets in a full local run: Windows, the bundled build,
and a process that has already opened many stores.

**Resolution.** The real child-process probe already classified this Windows build
as `host_crash`; the test then replaced that answer with `supported` and performed
the native operation that the probe had refused. The regression now exercises the
process-global posture latch directly, without overriding the safety probe. The
ordinary suite and the pristine-process 17-test SQLCipher gate both pass. See
FIXED-244.

**Required user-interface outcome.** None — this is a test-isolation defect on one
platform. The product's memory-security posture is reported from a real probe and
is unaffected.

---

## BUG-218 — Auto mode has no alignment check of its own

**Severity: Medium. Area: decision modes / Build / Chat. Status: Open — raised
2026-08-21 while reviewing Claude Code and Cowork permission modes.**

**Observed.** Raiker's **Auto** approval mode, and Build's **Auto** composer
mode, both mean "do not add a restriction of my own" — the turn runs under the
owner's standing permissions and nothing looks at whether a particular action is
what the owner actually asked for.

The reference set does more than that.
[Claude Code's `auto`](https://code.claude.com/docs/en/permissions)
"auto-approves tool calls with background safety checks that verify actions align
with your request", and
[Cowork's Auto](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)
"reviews each action for safety" and blocks what it judges unsafe. An owner
moving from either product to Raiker will read Raiker's **Auto** as the same
promise, and it is not.

**Reproduction.** Set every write capability to allow, choose Auto, and ask for a
change to a file unrelated to the request. It runs. Nothing records that the
action and the request disagreed.

**Root cause.** There is no reviewer between a permitted action and its
execution. `raiker/tools/broker.py` decides on the gate and the decision mode
only; alignment is not a concept the runtime has.

**Proposed fix, and the constraint that makes it worth building.** A classifier
that quietly approves is worse than none — it makes Auto *feel* safer without
being safer, and it puts a model in the authority path. Any implementation must:

- record its verdict as **evidence on the decision**, visible in the approval and
  in the audit record, never as a silent grant;
- be able to **withhold** an action into the ordinary approval queue, and never to
  widen a gate or skip one;
- state, where it withheld, which part of the request the action did not match,
  so the owner is answering a question rather than a mood;
- fail closed when the reviewer itself is unavailable — an unreachable reviewer
  means Auto behaves as Manual, not as Skip.

Until it is built, Raiker's Auto should keep saying exactly what it does, which
the Build composer already does through `standingPostureNote`.

---

## BUG-219 — There is no deny-unless-preapproved posture

**Severity: Low. Area: approval modes. Status: Open — raised 2026-08-21.**

**Observed.** The approval chip offers Manual, Auto and Skip. Claude Code also
offers `dontAsk`, which auto-**denies** anything not already allowed by a rule
instead of prompting for it. That is the posture for unattended work where an
interruption is worse than a refusal — a scheduled routine, a background agent —
and Raiker has no way to express it.

**Root cause.** `APPROVAL_MODES` in `raiker/contracts/models.py` and
`apps/web/src/lib/approvalMode.ts` list three modes. The enforcement it would
need already exists: `deny` is a decision mode the runtime honours today.

**Proposed fix.** Add a fourth mode that resolves any otherwise-eligible governed
action to `deny` rather than to a prompt, with the refusal recorded and visible
in the transcript like any other. It is a mode-list addition rather than new
enforcement, which is why the severity is Low and the value is real — a routine
that runs at 06:00 cannot answer a prompt, and today it parks instead of
proceeding within what it was allowed.

---

## BUG-220 — Nothing owns a set of delegated child tasks

**Severity: Medium. Area: tasks / delegation. Status: Open — raised 2026-08-21
while reviewing Cowork Dispatch.**

**Observed.** Raiker has every component of
[Cowork's Dispatch](https://claude.com/docs/cowork/guide/dispatch): read-only
subagents (`spawn_subagent`), background agents, nested tasks with a parent id,
per-task sessions, and a live work board in Observability. What is missing is the
one conversation that briefs the work, decides how to split it, and owns the
children — and the routing decision that sends each child to Chat or to Build.

Today the owner does the splitting by hand, one task form at a time, and nothing
connects the resulting runs to the intent that produced them.

**Root cause.** `parent_task_id` records structure but no surface composes it. No
route lists a task's children as a group, and no turn can create more than one
task at a time.

**Proposed fix, with the governance requirements that are not optional.**

- The routing decision (Chat or Build, and which project or repository) must be
  **visible and re-decidable** before the child starts, not inferred silently.
- Each child must carry **its own approvals**. A child inheriting the parent
  conversation's approvals would turn one decision into an unbounded number, which
  is the exact failure the per-turn capability envelope exists to prevent.
- A forwarded approval must not expire silently. Cowork auto-denies an unanswered
  prompt after ten minutes; if Raiker adopts that, the expiry has to be a
  **recorded decision with its reason**, not a dropped request.

---

## BUG-221 — A plugin is recorded and then provides nothing

**Severity: Medium → Low. Area: plugins / extensibility. Status: Open — reduced
2026-08-22.**

**2026-08-22 update — the first contribution kind ships (FIXED-256).** A plugin
that declares `event:hook` and a `contributes.hooks` block now contributes real
hook rules: they are written to `.raiker/plugins/<plugin_id>/hooks.json`, loaded
at `plugin` scope below every scope the owner controls, listed on Extensions →
Hooks credited to the plugin that wrote them, and deleted when the plugin is
revoked. The plan and the CLI state what would be contributed before the install,
and the Plugins tab states what each installed plugin provides — read from the
files the runtime loads, not from the manifest that described them.

`execution_enabled` stays `False`, deliberately: a plugin still runs no code of
its own, and a contributed rule runs as a **hook**, under the hook's rules.

**What is left**, in the order the original analysis set out — steps 2, 3 and 4:

* **Skills.** They run nothing and need only provenance, which makes this the
  next one to take. The blocking piece is where a plugin-contributed `SKILL.md`
  lives and how the Skills tab distinguishes it from an uploaded one.
* **MCP servers.** Already brokered and gated; what is missing is a manifest →
  server-profile path that goes through the existing trust gate rather than
  around it.
* **Plugin panels.** Still last, and still for the same reason: a route,
  permission and accessibility contract that does not exist.

The Plugins tab now names all four with their state, so this gap is visible on
the surface rather than only in this document.

**Observed.** Installing a plugin validates its manifest, checks its supply
chain, resolves its signature to `verified` / `present_only` / `unsigned`, writes
a `PluginInstallRecord`, and shows all of that on Extensions → Plugins. Then
nothing happens. `PluginRegistrationPlan.execution_enabled` is `False` by
construction, so a plugin contributes no skill, no agent, no hook, no MCP server
and no panel. The tab says so, which is right — but the surface as a whole reads
as an install flow for something that cannot be installed.

Claude Code plugins bundle skills, agents, hooks, MCP servers and LSP servers;
Cowork installs them from **Customize**. This is the largest remaining piece of
the hooks → plugins → channels gap.

**Root cause.** Not packaging — `raiker/plugins/` already does the hard parts of
that. The blocking question is what a plugin's *code* is allowed to be. Every
other extension surface answers it: a skill is instructions and runs nothing, a
connector is a brokered tool with a capability gate, a hook is argv resolved
inside the workspace under a bounded timeout. A plugin has no such answer yet.

**The constraint that decides the shape of the rest.** Step 1 is done and proved
the approach: each contribution arrives through a surface that **already governs
it**, so no new execution surface is invented. Steps 2 to 4 are held to the same
bar. What must not happen is a general "plugin code runs" step — that would need
its own authority story, and none of the remaining three requires one.

---

## BUG-222 — There is no way to turn every hook off

**Severity: Low. Area: hooks. Status: Fixed 2026-08-22 — see FIXED-254.**

**Observed.** Hooks are loaded from `config/managed-hooks.json`,
`config/hooks.json` and `.raiker/hooks.json`. The only way to stop them is to
edit or delete the files. Claude Code has `disableAllHooks` in settings and
`--settings '{"disableAllHooks": true}'` for a single run.

This matters more here than there. `config/hooks.json` travels with a
repository, so cloning a project can bring rules that run commands on the owner's
machine — bounded and workspace-resolved, but still theirs to refuse. The owner
should be able to say no without editing someone else's file.

**Root cause.** `HookDispatcher.is_active()` reads only whether the registry has
rules. There is no owner-scoped setting above it.

**Proposed fix.** An owner setting that makes `is_active()` return `False`, shown
on Extensions → Hooks with the rules still listed and marked as disabled — off is
a state to display, not a reason to hide what would otherwise run. It belongs in
owner settings rather than in any of the three config files, because a file a
project ships must not be able to re-enable itself.

---

## BUG-223 — Twenty-two lifecycle events are specified and never emitted

**Severity: Medium. Area: hooks / lifecycle. Status: Fixed 2026-08-22 — see
FIXED-255.**

**Observed.** `docs/HOOKS_SPEC.md` listed roughly the same event surface Claude
Code documents. Nine were dispatched. `SessionEnd` was accepted by the config
schema and had no call site at all, so a rule written for it parsed cleanly and
never ran; the rest were not in `HOOK_EVENTS`, so a rule naming one was refused
at parse time.

**Fixed.** Seven events gained call sites — `Stop`, `StopFailure`,
`SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted` and
`SessionEnd` — each at a boundary the runtime already knew about. `HOOK_EVENTS`
and `DISPATCHED_HOOK_EVENTS` are now equal, and the machinery that reports a dead
event is kept and still tested, because what makes a *future* gap visible is
worth more than the fact that there is not one today.

`docs/HOOKS_SPEC.md` now separates the target catalogue from what this build
accepts and emits, so the two can never be read as the same list again.

**BUG-224** — the Node 25 web-test environment — was raised while verifying this.

---

## BUG-224 — The Node 25 web test run cannot see jsdom's `localStorage`

**Severity: Low. Area: web tests / environment. Status: Fixed 2026-08-22 — see
FIXED-258.**

**Observed.** `npx vitest run` under Node 25.6.1 failed `src/lib/theme.test.ts`
(5 tests) and `src/lib/views/LoginView.test.ts` (15) with
`TypeError: window.localStorage.clear is not a function`, alongside a Node
warning: `` `--localstorage-file` was provided without a valid path ``. The
LoginView failures were the same cause one step downstream — cleanup never ran,
so the next test found two of every button and failed on
`Found multiple elements`.

**Root cause.** Node 25 ships a built-in `localStorage` global. It shadows the
one jsdom installs, and the built-in is inert unless the process was started with
a valid `--localstorage-file`. Nothing in the repository was wrong; the
environment changed underneath it.

**Fixed.** `src/test-setup.ts` restores the storage jsdom promises when what is
present is not a working `Storage`. Rather than pinning harder — which only
defers the same break to the next Node release — the shim is a real map, because
the code under test persists a theme choice and reads it back; a no-op stub would
pass the type check and fail the behaviour.
