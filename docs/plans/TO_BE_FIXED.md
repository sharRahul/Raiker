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
| [BUG-219](#bug-219--there-is-no-deny-unless-preapproved-posture) | Low | Approval modes | **Fixed 2026-08-22 — FIXED-262** |
| [BUG-220](#bug-220--nothing-owns-a-set-of-delegated-child-tasks) | Medium | Tasks / delegation | Open — raised 2026-08-21 |
| BUG-221 | Medium → Low | Plugins / extensibility | **Closed 2026-08-22 — FIXED-256, FIXED-259, FIXED-260.** Hooks, skills and MCP-server offers all contribute; panels continue as [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) |
| [BUG-222](#bug-222--there-is-no-way-to-turn-every-hook-off) | Low | Hooks | **Fixed 2026-08-22 — FIXED-254** |
| [BUG-223](#bug-223--twenty-two-lifecycle-events-are-specified-and-never-emitted) | Medium | Hooks / lifecycle | **Fixed 2026-08-22 — FIXED-255** |
| [BUG-224](#bug-224--the-node-25-web-test-run-cannot-see-jsdoms-localstorage) | Low | Web tests / environment | **Fixed 2026-08-22 — FIXED-258** |
| [BUG-225](#bug-225--a-channel-can-be-described-and-never-reached) | Medium → Low | Channels / extensibility | Open — reduced twice 2026-08-22 (FIXED-261, FIXED-265). **The premise was wrong**: the transport existed and had no owner surface. It has one now; rate limits and approval-relay resolution remain |
| [BUG-226](#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Low | Hooks / handlers | Open — raised 2026-08-22 |
| [BUG-227](#bug-227--there-is-no-lsp-surface-for-a-plugin-to-contribute-to) | Low | Plugins / language intelligence | Open — raised 2026-08-22 |
| [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Low | Plugins / web UI | Open — raised 2026-08-22, split out of BUG-221 |
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

**Severity: Low. Area: approval modes. Status: Fixed 2026-08-22 — see
FIXED-262.**

**Observed.** The approval chip offers Manual, Auto and Skip. Claude Code also
offers `dontAsk`, which auto-**denies** anything not already allowed by a rule
instead of prompting for it. That is the posture for unattended work where an
interruption is worse than a refusal — a scheduled routine, a background agent —
and Raiker has no way to express it.

**Root cause.** `APPROVAL_MODES` in `raiker/contracts/models.py` and
`apps/web/src/lib/approvalMode.ts` list three modes. The enforcement it would
need already exists: `deny` is a decision mode the runtime honours today.

**Fixed.** `dont_ask` is the fourth mode. It resolves any otherwise-eligible
governed action to `deny` rather than to a prompt, before the decision is
recorded — so the audit log never describes a queue entry that did not exist. The
refusal carries its own reason, `denied_no_one_to_ask`, distinct from every other
denial: *"the owner refused this"* and *"nobody was there to ask"* call for
different follow-ups, and only the second means re-running attended would have
worked. It can only ever refuse more; an action policy already allowed is
untouched, and one policy already denied keeps policy's own reason.

A per-turn `ask` posture normally forces `manual` so the unattended modes cannot
swallow it. `dont_ask` is the deliberate exception: there is nobody to show it
to, so forcing `manual` would park the turn on a queue entry that is never read —
the exact outcome the mode exists to avoid.

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

---

## BUG-225 — A channel can be described and never reached

**Severity: Medium. Area: channels / extensibility. Status: Open — reduced
2026-08-22 (FIXED-261). Raised 2026-08-22 while closing the hooks and plugin
halves of the same gap.**

**2026-08-22 update — the premise was wrong, and the surface now exists
(FIXED-265).** This entry said *"nothing consumes them for delivery"*. Building
delivery started by reading `raiker/channels/` and found that it was already
built: `ExternalChannelExecutor` does bounded outbound webhook delivery against
the channel egress allowlist, `POST /api/channels/{id}/inbound` receives messages
behind an owner secret with sender allowlisting and marks every one untrusted and
quarantined, and `ChannelApprovalRelayExecutor` can only ever queue a *pending*
relay. The capability is registered, gated, phase-gated and audited.

What was missing was **any way for the owner to pair a connector**. With no
pairing the executors refuse and the receiver 404s, so the tab's "channels do not
exist" was true in effect and wrong about the cause — and it is the failure this
document's own standard forbids: backend work that leaves an invisible surface.

Pairing, enable/disable, sender allowlist, unpair and a governed test delivery
now exist, and the tab reports the three fail-closed gates separately. See
FIXED-265.

**What is actually left**, restated against the code rather than the original
guess:

* **Rate limits.** `CHANNELS_SPEC.md` lists a per-channel inbound budget. There
  is none: an allowlisted sender can post as fast as they like.
* **Approval-relay resolution.** The queue exists and is deliberately
  pending-only. Resolving an approval over a channel still has no anti-phishing
  story, and should stay refused until it does.
* **Routing modes.** An inbound message is recorded and quarantined; none of the
  routing modes in the spec (`new_turn`, `side_question`, `interrupt`, …) is
  implemented, so a channel message never becomes work on its own. That is the
  safe default and it is *not* what the spec's Channel Type Matrix implies.

**2026-08-22 update — step 1 is done (FIXED-261).** The decision this entry named
as the blocker is written down and accepted: a channel message is **untrusted
content with a named sender who is not the owner**, in `docs/CHANNELS_SPEC.md` →
*What a channel message is in a turn*, with the matching rows in
`docs/THREAT_MODEL.md`. Five enforceable rules follow — never a prompt, trust from
the pairing record rather than from the message, no raising of the turn's
authority, outbound-is-a-capability vs inbound-is-a-boundary, and nothing
implicit. Extensions → Channels states the contract and the four steps with the
state of each, so an accepted spec cannot be mistaken for a shipped feature.

**Steps 2, 3 and 4 remain open**, and the code below now has a contract to
satisfy. Outbound delivery is next.

**Observed.** `config/channel-connectors.json` describes channel connectors in
detail — transport, auth method, whether pairing is required, whether a sender
allowlist is required, whether network is required, the capability policy
template — and `ConnectorRegistry` validates every one of those fields at
startup, refusing a profile that omits any. Then nothing consumes them for
delivery. Extensions → **Channels** says so:

> Inbound and outbound delivery needs an accepted contract and threat model
> before Raiker offers controls for it.

That is honest, and it is now the largest remaining piece of the hooks →
plugins → channels gap: hooks reached parity 2026-08-22 (FIXED-255) and plugins
took their first contribution kind (FIXED-256).

**Root cause.** Not the registry, which already models the right things. What is
missing is a decision about the boundary: a channel is the point at which
**content Raiker did not ask for enters a turn**. Every other input path has an
answer for that — a prompt is the owner speaking, a tool result is data the model
is told to distrust, a subagent digest is quoted as untrusted. A channel message
has no such framing yet, and neither has the sender.

**What the reference set does.** OpenClaw leads here; its own documentation
treats channels as where external input enters. Claude Code has no equivalent.
This is therefore the one part of the three-way gap where being behind is not
automatically a defect — shipping delivery without the framing would be worse
than not shipping it.

**Proposed fix, in the order the authority story has to be written.**

1. ~~**Decide what a channel message *is* in a turn.**~~ **Done — FIXED-261.** It
   is untrusted content with a named sender, and the sender is not the owner.
   Written down in `docs/CHANNELS_SPEC.md` and the threat model, so the code
   below now has a contract to satisfy.
2. ~~**Outbound first.**~~ **Already existed; reachable since FIXED-265.** The
   executor, the capability gate, the egress allowlist and the audit path were
   built. What it lacked was a pairing the owner could create.
3. ~~**Then inbound, paired and allowlisted.**~~ **Already existed; reachable
   since FIXED-265.** `requires_pairing` and `requires_sender_allowlist` were
   enforced by the receiver and unreachable for the same reason.
4. **Permission relay last** — still open, and still for the original reason: a
   channel that can raise an approval is a channel that can be used to *ask for
   one*, and the anti-phishing story for that does not exist. The relay queue is
   deliberately pending-only until it does.
5. **Rate limits** — raised by this work rather than closed by it. There is no
   per-channel inbound budget, so an allowlisted sender is unbounded.

The tab now states the contract, offers the controls, and reports each
fail-closed gate separately — so "nothing has been delivered" and "nothing can be
delivered" stop looking the same.

---

## BUG-226 — Three of the five hook handler types do not exist

**Severity: Low. Area: hooks / handlers. Status: Open — raised 2026-08-22.**

**Observed.** The hooks reference Raiker maps itself against documents five
handler types: `command`, `http`, `mcp_tool`, `prompt` and `agent`. `HANDLER_TYPES`
in `raiker/hooks/contracts.py` accepts two — `command` and `builtin`, the second
being Raiker's own in-process code rather than one of the five. A rule naming
`http` is refused at parse time with `unsupported_handler_type:http`, which is
the right failure but leaves three of the reference set unavailable.

This is the remainder of the hooks gap after BUG-223. The *events* are at parity;
the *handlers* are not.

**Root cause.** Each of the three needs a resource the hook path deliberately
does not have:

* `http` needs egress. A hook has no implicit network access by design, and
  giving one an outbound request is a capability decision, not a handler type.
* `mcp_tool` needs the MCP broker inside the hook path, which would let a hook
  reach a tool the turn's own policy might have refused — the exact inversion the
  hook model forbids.
* `prompt` and `agent` need a model call, which means a token budget, a timeout
  that is not the handler's 5-second one, and an answer to what happens when the
  model call itself triggers hooks.

**Proposed fix.** `prompt` is the cheapest and the least dangerous: it makes no
outbound request of its own and its output is context, not a decision. Take it
first, with its own budget and a hard refusal to nest. `http` follows only once a
hook can be given a named, revocable egress grant of the kind the container work
already built. `mcp_tool` and `agent` should stay refused until there is a stated
answer to a hook reaching authority the turn did not have.

**Not a regression, and visible today.** A rule naming an unsupported type is
refused at parse time rather than accepted and ignored, and the Hooks tab reports
the file as failed with the reason — so an owner writing one is told, rather than
believing a guard is in place.

---

## BUG-227 — There is no LSP surface for a plugin to contribute to

**Severity: Low. Area: plugins / Build / language intelligence. Status: Open —
raised 2026-08-22 while closing BUG-221 steps 2 and 3.**

**Observed.** `docs/PLUGIN_MANIFEST_SCHEMA.md` and `docs/PLUGIN_SYSTEM_SPEC.md`
both list **LSP servers** among what a plugin declares, and both say the
declaration stays inert until trust and approval gates pass. Grepping the runtime
for a language-server path returns nothing: there is no LSP client, no server
lifecycle, and no consumer of a `contributes.lsp_servers` block. The other three
deferred kinds each had a real surface waiting behind a gate; this one has a
manifest field and no destination.

Claude Code plugins do bundle LSP servers, and Build uses language intelligence
for navigation and diagnostics. So this is a genuine Claude Code gap — it is just
a *smaller* one than it looks, because Raiker's graph/codemap layer
(`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`) already answers part of what an LSP
would be asked for.

**Root cause.** The manifest schema was written against the reference platform's
component list rather than against Raiker's own surfaces, so it names a component
kind Raiker has no surface for. That is the opposite of the rule BUG-221 settled
on: a plugin contributes **through a surface that already governs the thing
contributed**, and there is no such surface here to contribute through.

**Proposed fix, and the order.**

1. **Decide whether Raiker wants an LSP client at all**, or whether the codemap
   plus the governed read tools already cover the need. This is a scope decision
   and it comes first; building a client to satisfy a manifest field would be the
   tail wagging the dog.
2. If yes: an LSP server is a **long-running subprocess that reads the
   workspace**, so it belongs behind the same execution boundary
   `CommandService` already enforces, with its own capability and lifecycle —
   not a new one.
3. Only then a `contributes.lsp_servers` path, and it should be an **offer** in
   the FIXED-260 sense rather than an install: a language server is a tool source.

**Until then**, the manifest schema should say plainly that the field is
accepted-and-inert *because there is no surface*, rather than *because a gate has
not opened* — the two are different promises and only one of them is true.

---

## BUG-228 — A plugin panel has no route, permission or accessibility contract

**Severity: Low. Area: plugins / web UI. Status: Open — raised 2026-08-22, split
out of BUG-221 as the last remaining contribution kind.**

**Observed.** Extensions → Plugins lists four contribution kinds. Three are now
available (hooks, skills, MCP-server offers). **Panels** is the fourth and reads
"Not yet — needs a route, permission and accessibility contract that does not
exist", which is accurate and has been the stated blocker since BUG-221 was
raised. Splitting it out means BUG-221 can close when the reasoning it carries is
no longer needed, and this can be worked on its own terms.

**Root cause.** Unlike the other three, there is no existing surface that already
governs "a page a plugin drew". A hook had an execution model; a skill had a
validator; an MCP server had a create path. A panel needs all of the following to
be decided before any code:

* **A route.** Where a plugin's page lives in the hash router, how it is
  addressed, and what stops two plugins claiming one path.
* **A rendering boundary.** Raiker renders no third-party code in the browser
  today, and "no plugin code runs in this browser" is a claim the Plugins tab
  makes in those words. A panel either breaks that claim or is declarative —
  a described layout Raiker renders — and that choice decides everything else.
* **A permission model.** What data a panel may read, and how it asks; a panel
  that can read the session list is a very different object from one that cannot.
* **An accessibility contract.** Every other surface meets the same keyboard,
  contrast and landmark bar. A plugin-supplied page cannot be exempt from it, so
  it has to be *checkable*, which is easiest if it is declarative.

**Proposed fix.** Take the declarative route: a panel is a described layout from
a fixed component vocabulary, rendered by Raiker, reading only data the plugin's
own contributions produced. That keeps "no plugin code runs in this browser"
literally true, makes the accessibility contract enforceable at render time
rather than by review, and matches the pattern the other three kinds established.

**Not blocking anything.** No other work depends on this, and the surface already
states it is unavailable rather than offering a control that does nothing.
