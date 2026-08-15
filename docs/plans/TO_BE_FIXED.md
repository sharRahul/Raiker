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
