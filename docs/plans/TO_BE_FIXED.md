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
| [BUG-216](#bug-216--checkpoint-capture-fails-silently-on-a-deep-windows-path-and-only-logs-it) | High | Checkpoints / Windows paths | Open — root cause identified 2026-08-16 |
| [BUG-217](#bug-217--test_the_posture_reports_the_pragma_in_force_not_only_the_one_resolved-overflows-the-stack-on-windows) | Low | Test isolation / SQLCipher posture | Open |
| MEM-03 … MEM-09 | High → Low | Memory reliability | Open — see [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md) |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B9, B11, B12, B17, B19 complete; 9 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (C14 **complete** — branch-from-here closed as FIXED-227; 13 items remain) |

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

**Reviewed again on 2026-08-16 and deliberately not advanced.** The round that
closed BUG-196, BUG-197, BUG-215 and the composer parity work touched the command
store — a run now names its backend from the moment it starts
([FIXED-217](FIXED_ITEMS.md)) — but attempted none of the rows below, and the
reason is the reason each row states: every one of them is a **component**, not a
flag. The smallest of them, background execution, needs a supervisor that outlives
the turn together with the agent-facing `process` tool that makes a background run
observable; shipping either half alone is worse than refusing, because it leaves
an orphan process holding a sandbox grant nothing reclaims, or an agent that
starts work it cannot poll. Doing that properly is its own round with its own live
proof, and pretending otherwise here would be the exact failure mode the rest of
this document records. The rows stay red, and the controls stay **absent** from
the interface rather than disabled.

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
