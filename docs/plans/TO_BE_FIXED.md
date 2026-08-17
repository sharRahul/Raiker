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
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced three times; the OS boundary is FIXED-195, background execution and POSIX PTY are FIXED-229, restart reattachment and the persistent environment are FIXED-238 and FIXED-239 |
| [BUG-216](#bug-216--checkpoint-capture-fails-silently-on-a-deep-windows-path-and-only-logs-it) | High | Checkpoints / Windows paths | Open — root cause identified 2026-08-16 |
| [BUG-217](#bug-217--test_the_posture_reports_the_pragma_in_force_not_only_the_one_resolved-overflows-the-stack-on-windows) | Low | Test isolation / SQLCipher posture | Open |
| MEM-06 … MEM-14 | Medium → Low | Memory reliability | Open: MEM-06 … MEM-10. Closed 2026-08-17: MEM-03/MEM-05 (FIXED-230/231), MEM-11/12/13 (FIXED-232/233/234), MEM-14 (FIXED-236) and MEM-04 (FIXED-237). See [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md) |
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
MEM-06 is now the binding constraint on the graph leg, which MEM-12 made
reachable and which nothing populates. MEM-06 through MEM-10 are open there
rather than duplicated here.

---

## BUG-194 — The governed shell has an OS boundary, but no interactive, background or remote execution

**Severity: Low (was Medium, was High). Area: shell / sandbox / recovery.
Status: Open — reduced three times.**

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

**Severity: High. Area: checkpoints / Windows paths. Status: Open — root cause
identified, not fixed in this round.**

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

**Severity: Low. Area: test isolation / SQLCipher posture. Status: Open.**

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

**Required fix.** Establish whether the overflow is in the bundled SQLCipher build's
pragma read or in how the posture probe re-enters it, and isolate the posture test
into its own process (as CI already does for its second step) so a contributor's
documented `pytest` run cannot be aborted by it. Do not silence it with an env var:
that is precisely what hid FIXED-218.

**Required user-interface outcome.** None — this is a test-isolation defect on one
platform. The product's memory-security posture is reported from a real probe and
is unaffected.
