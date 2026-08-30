## Goal

Make Raiker a secure AI product that combines **four** things: a polished AI
assistant, a governed AI agent, **a capable coding/build agent**, and an
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

> **Which open work blocks which pillar is in [`PILLAR_MAP.md`](PILLAR_MAP.md),
> and how an action reaches an executor at all is in
> [`GOVERNANCE_ENTRY_PATHS.md`](GOVERNANCE_ENTRY_PATHS.md).** This preamble is
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

[`GAP_BUILD_CHAT.md`](GAP_BUILD_CHAT.md) — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

**This list holds only what is still open.** A row marked *Fixed* is kept in the
index so a reader arriving with that number is not left wondering; its full
record — observation, root cause, and the interface outcome that had to be true
first — is in [`FIXED_ITEMS.md`](FIXED_ITEMS.md) under the FIXED number the row
names.

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced again 2026-08-21; foreground SSH/Daytona and safeguarded egress/credential/trust foundations ship, while live container and external trust-anchor proofs remain |
| [MEM-08](FIXED_ITEMS.md#fixed-316--every-turn-coordinate-was-a-dead-end) | Medium | Memory reliability | **Closed 2026-08-29 (FIXED-316)** — a turn coordinate opens the exchange. With it, every MEM entry raised by the 2026-08-11 memory audit is closed: MEM-06 as FIXED-241, MEM-07 as FIXED-284, MEM-09 as FIXED-310, MEM-10 as FIXED-283/292/293/294. |
| [BUG-220](FIXED_ITEMS.md#fixed-286--a-task-reported-done-while-the-work-it-delegated-was-still-open) | Medium | Tasks / delegation | **Closed 2026-08-25 (FIXED-286)** — a parent parks as `waiting_for_children` and settles on the last child. Its routing half is now [backlog #23](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort) |
| [BUG-225](FIXED_ITEMS.md#fixed-298--a-paired-channel-could-still-only-record-a-message) | Medium → Low | Channels / extensibility | **Closed 2026-08-27 (FIXED-298)** — owner-stored routing and exact, single-use approval responses now ship; record-only remains the default |
| [BUG-226](#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Low | Hooks / handlers | Open remainder — reduced 2026-08-28; `prompt` closed as FIXED-303, while `http`, `mcp_tool` and `agent` remain refused |
| [BUG-227](#bug-227--there-is-no-lsp-surface-for-a-plugin-to-contribute-to) | Low | Plugins / language intelligence | Open — raised 2026-08-22 |
| [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Low | Plugins / web UI | Open — raised 2026-08-22, split out of BUG-221 |
| [BUG-229](#bug-229--most-live-specs-sign-in-only-on-an-empty-workspace) | Low | Live test harness | Open remainder — reduced 2026-08-29: the shared `signInAsOwner` exists and accepts either greeting; the other live specs still inline their own |
| [BUG-234](#bug-234--the-remainder-what-raiker-does-not-use-of-the-mcp-revision-it-now-speaks) | Medium → Low | MCP / interoperability | Open — reduced 2026-08-23 (FIXED-274). The revision is current; streamable HTTP, remote OAuth, MCP Apps and `server/discover` remain |
| [GEP-02](GOVERNANCE_ENTRY_PATHS.md#gep-02--the-stop-switchs-scope-is-undefined-for-read-paths), [GEP-03](GOVERNANCE_ENTRY_PATHS.md#gep-03--nested_boundaries_architecturemd278-overstates-the-architecture) | Low | Governance architecture / documentation | Open — not duplicated here. GEP-02 is **an owner decision** and the helper now carries the answer at no cost |
| [BUG-239](#bug-239--an-empty-gate-table-means-three-different-things) | Low | Capability gates / owner decision | Open — raised 2026-08-24 while closing GEP-01. **An owner decision**: unifying it either loosens seven paths or tightens one |
| [BUG-240](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | Medium → Low | Memory / retrieval | **Closed 2026-08-26 (FIXED-292, FIXED-294)** — both the provider half and the managed-file half ship; the row is kept so a reader arriving with the number is not left wondering |
| [BUG-241](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport) | Low | Live test harness / evidence | **Closed 2026-08-29 (FIXED-313)** — one shared capture helper; all 56 live specs go through it |
| [BUG-242](FIXED_ITEMS.md#fixed-309--build-opened-an-empty-conversation-after-a-reload) | Medium | Build / web UI | **Closed 2026-08-29 (FIXED-309)** — the conversation rides in the URL and Build restores it |
| [BUG-243](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it) | High | Memory / retrieval | **Closed 2026-08-29 (FIXED-314)** — raised while verifying FIXED-311: a question was being used as a filter |
| [BUG-244](#bug-244--importing-the-same-memory-twice-stores-it-twice) | Low | Memory / import | Open — raised 2026-08-29 while seeding a memory for the FIXED-311 round |
| [BUG-245](#bug-245--a-cited-conversation-names-its-exchanges-and-cannot-open-one) | Low | Memory / citations | Open — raised 2026-08-29 while closing MEM-08 as FIXED-316 |
| [BUG-246](#bug-246--the-authority-matrix-is-a-scrollable-table-on-a-phone-and-truncates-its-own-verdicts) | Low | Permissions / web UI | Open — raised 2026-08-29 during the four-width audit |
| [GAP-BUILD](GAP_BUILD_CHAT.md#gap-build--what-build-needs-to-stand-against-a-class-leading-coding-agent) | — | Build — coding-agent parity | Analysis (15 complete, 3 partial, 2 open; B18 closed 2026-08-29 as FIXED-315, and B16 recorded as already closed by BUG-206 slice D) |
| [GAP-CHAT](GAP_BUILD_CHAT.md#gap-chat--what-chat-needs-to-work-as-a-class-leading---agentic-work-assistant) | — | Chat — work-assistant parity | Analysis (13 complete, 5 open; C17 recall visibility closed 2026-08-29 as FIXED-311) |

The memory audit of **2026-08-11** has its own document,
[`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md), written to this
standard. Its MEM-01 and MEM-02 are closed in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md) as FIXED-187 and FIXED-188, and MEM-03 and
MEM-05 as FIXED-230 and FIXED-231, MEM-11, MEM-12 and MEM-13 as FIXED-232,
FIXED-233 and FIXED-234, MEM-14 as FIXED-236, and MEM-04 as FIXED-237. Two were
raised in their place. MEM-10: closing MEM-03 built the *selection* of an
embedding space, and a default install still has nothing semantic to select.
MEM-06, the binding constraint on the graph leg MEM-12 made reachable, closed
2026-08-21 as FIXED-241. MEM-07 closed 2026-08-25 as FIXED-284, and MEM-10's
first leg — the one that made a semantic space *producible* rather than only
selectable — as FIXED-283. **As of 2026-08-29 that document holds no open
entry**: MEM-09 closed as FIXED-310, MEM-10's remainder as FIXED-301, and MEM-08
— the last of them — as FIXED-316. It stays as the record of the audit and of
how each entry closed, not as open work.

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

## BUG-239 — An empty gate table means three different things

**Severity: Low. Area: capability gates / owner decision. Status: Open — raised
2026-08-24 while closing [GEP-01](GOVERNANCE_ENTRY_PATHS.md).**

**Observed.** On a workspace where nothing has been persisted for a capability,
three different answers are given to *is this on?*, and which one applies depends
on the capability:

| Resolution | Nothing persisted means | Used by |
|---|---|---|
| `off` | Off. Nothing decided is not consent | Everything not named below |
| `shipped_default_unscoped` | An account is fail-closed; a caller with no account gets the shipped table | `code_map_indexing`, `subagents` |
| `shipped_default` | Any caller gets the shipped table | `web_fetch` |

So on a **fresh account** with an untouched gate table, `web_fetch` is on and
`shell_execution` is off, and nothing on the Capabilities page explains why the
two behave differently.

**Why it is recorded rather than fixed.** Each resolution is individually
justified and two of them are documented in the entries that introduced them —
`web_fetch`'s is RAIKER-2021 (*an owner who turns web access off writes a row; an
empty table on a fresh install is not a refusal*), and the code map's matches
`RuntimeAuthority.check_capability_gate` exactly. Collapsing them is not a
refactor:

* Making everything `off` **tightens `web_fetch`** for the terminal client and
  for a fresh account, and reintroduces the defect RAIKER-2021 closed.
* Making everything fall back **loosens seven paths**, including three egress
  ones, on any workspace whose owner has not yet visited Permissions.

Both are owner-visible behaviour changes, and neither is an implementer's call.

**What did ship (FIXED-279).** The fork is a named table,
`CAPABILITY_UNSET_RESOLUTION` in
[`raiker/runtime/authority/admission.py`](../../raiker/runtime/authority/admission.py),
read by the enforcing path *and* by every surface that describes a gate. That
closed the live half of this: the context bundle used to tell the model
`web_fetch: disabled` on an install where the tool would have fetched. What is
left is the inconsistency itself, which is now visible in one place instead of
spread across eight.

**Proposed work, once the question is answered.** Pick one resolution, change the
table, and say on the Capabilities page what an untouched gate means — a single
sentence, in the same place the gate's state is shown. The **user-interface
outcome** is the point: an owner should never have to know which of three rules
a capability uses to predict what happens before they touch it.

---

## BUG-220 — Nothing owns a set of delegated child tasks

**Severity: Medium. Area: tasks / delegation. Status: closed 2026-08-25 as
[FIXED-286](FIXED_ITEMS.md#fixed-286--a-task-reported-done-while-the-work-it-delegated-was-still-open),
raised 2026-08-21 while reviewing Cowork Dispatch.**

**What closed.** The ownership: a parent no longer reports `completed` over an
open child. It parks as `waiting_for_children` and settles when the last child
lands — completed if all completed, failed if any did not — and a child still
carries its own approvals, which was the first of the three requirements below.

**What is left, and where it lives now.** The other two — a visible,
re-decidable Chat-or-Build routing decision per child, and one conversation that
briefs the split — are the *composition* half of Dispatch rather than the
ownership half, and they are tracked as
[backlog #23](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort).
The original entry is kept below because its governance requirements still bind
that work.

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

## BUG-225 — A channel can be described and never reached

**Closed 2026-08-27 as
[FIXED-298](FIXED_ITEMS.md#fixed-298--a-paired-channel-could-still-only-record-a-message).**
The full observation, authority contract, anti-phishing controls, UI outcome,
and evidence moved to the closed-work ledger.

---

## BUG-226 — Three of the five hook handler types do not exist

**Severity: Low. Area: hooks / handlers. Status: Open remainder — reduced
2026-08-28 (FIXED-303).**

**Observed.** The hooks reference Raiker maps itself against documents five
handler types: `command`, `http`, `mcp_tool`, `prompt` and `agent`. Before
FIXED-303, `HANDLER_TYPES` accepted only `command` and Raiker's own `builtin`.
It now also accepts a bounded `prompt`; a rule naming `http`, `mcp_tool` or
`agent` is still refused at parse time, which is the right failure until each
has a governed resource path.

The title originally undercounted four missing types. After FIXED-303 it is now
accurate: three remain — `http`, `mcp_tool` and `agent`.

**Corrected 2026-08-22.** This entry used to say `command` is the only handler
type Claude Code's own hooks have, and that the gap was therefore against
Raiker's own reference document rather than against Claude Code. That was wrong:
[the Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
documents and specifies all five — `command`, `http`, `mcp_tool`, `prompt` and
`agent` — with per-type fields. **This is a real gap against Claude Code.** It
stays Low because each missing type needs a resource the hook path deliberately
does not have (below), not because the reference lacks them.

This is the remainder of the hooks gap after BUG-223 — and the *events* are not
at parity either: Raiker emits seventeen of the thirty-one Claude Code documents.
See
[`../REFERENCE_PLATFORM_COMPATIBILITY.md`](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#25-extensibility--hooks).

**Root cause.** Each originally missing type needs a resource the hook path deliberately
does not have:

* `http` needs egress. A hook has no implicit network access by design, and
  giving one an outbound request is a capability decision, not a handler type.
* `mcp_tool` needs the MCP broker inside the hook path, which would let a hook
  reach a tool the turn's own policy might have refused — the exact inversion the
  hook model forbids.
* `agent` needs a multi-turn model loop and tools, which means its own budget,
  capability set and answer to inherited authority. The single-turn `prompt`
  case no longer shares that blocker.

**Completed first slice.** FIXED-303 adds `prompt` with a per-handler token
budget and timeout, the owner-selected governed provider, no tools, no nesting,
redacted bounded event data and advisory-only output. `http` follows only once a
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

**Observed.** `docs/architecture/PLUGIN_MANIFEST_SCHEMA.md` and `docs/architecture/PLUGIN_SYSTEM_SPEC.md`
both list **LSP servers** among what a plugin declares, and both say the
declaration stays inert until trust and approval gates pass. Grepping the runtime
for a language-server path returns nothing: there is no LSP client, no server
lifecycle, and no consumer of a `contributes.lsp_servers` block. The other three
deferred kinds each had a real surface waiting behind a gate; this one has a
manifest field and no destination.

Claude Code plugins do bundle LSP servers, and Build uses language intelligence
for navigation and diagnostics. So this is a genuine Claude Code gap — it is just
a *smaller* one than it looks, because Raiker's graph/codemap layer
(`docs/architecture/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`) already answers part of what an LSP
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

---

## BUG-229 — Most live specs sign in only on an empty workspace

**Severity: Low. Area: live test harness. Status: Open — raised 2026-08-22 while
running the round's own specs.**

**Observed.** The Workbench greets a fresh instance with *"Welcome to your Work
Dashboard"* and a returning owner with *"Welcome back"*, and a workspace turns
from the first into the second the moment it holds any work. Almost every live
spec's `signIn` waits for the first string. So a suite passes on an empty
instance and fails on a used one — **at sign-in**, before it reaches anything it
was written to test, and reporting a missing heading rather than the thing under
test.

**Reproduction.** Run any live spec against a workspace that has one
conversation in it. It fails at `signIn` with
`waiting for getByRole('heading', { name: 'Welcome to your Work Dashboard' })`.

It surfaced mid-round exactly this way: the plugin specs passed, the provider
spec then created a chat session, and the next spec could not sign in.

**Root cause.** `signIn` is copy-pasted into each spec rather than shared, and
each copy encodes an assumption about the *state* of the instance that has
nothing to do with what the spec asserts. `hosted-provider.ts` exists precisely
to hold the steps every live spec must take — and sign-in is not in it.

**Proposed fix.** Move `signIn` into `e2e/hosted-provider.ts` beside
`dismissFirstRunModelSetup` and `openHostedProviders`, accepting either greeting,
and have every live spec call it. The four specs added on 2026-08-22 already
accept both, which is the shape to lift.

**Half of it landed 2026-08-29**, and it landed because the defect bit again in
exactly the documented way: the B18/MEM-08 round's first run created work in the
workspace, and its own second run then failed at sign-in on the empty-workspace
heading. `signInAsOwner(page, base, {user, password})` is now in
`e2e/hosted-provider.ts`, creates the account when there is none, unlocks when
there is, and accepts either greeting. **The remainder is the migration**: the
other live specs still carry their own copy, so each is still one workspace state
away from failing on its first step.

Not urgent, and deliberately not done in bulk this round: each older spec is the
evidence behind a closed FIXED entry, and re-running one is how that evidence is
refreshed — a sweeping edit across thirty of them is a change to thirty pieces of
evidence, which deserves its own pass rather than being smuggled into another.

---

## BUG-234 — The remainder: what Raiker does not use of the MCP revision it now speaks

**Severity: Low (was Medium). Area: MCP / interoperability.
Status: Open — reduced 2026-08-23.**

**What changed.** Raiker negotiated revision `2024-11-05` for five revisions,
which meant a server implementing only the current one could not be connected at
all. It now offers
[`2026-07-28`](https://modelcontextprotocol.io/specification/versioning), accepts
`2025-06-18`, `2025-03-26` and `2024-11-05` when a server answers with one, and
refuses a revision it does not implement rather than continuing on a framing it
cannot trust. **Extensions → MCP** states the revision each server negotiated.
Closed as [FIXED-274](FIXED_ITEMS.md).

**What is left.** Negotiating a revision is not implementing it. Each of the
following was previously *blocked* by the version pin and is now ordinary work:

* **Streamable HTTP session semantics.** Raiker's `http` transport is its own
  bounded JSON-RPC client. It carries `Mcp-Session-Id` and the
  `MCP-Protocol-Version` header, and it is not the specification's transport: no
  SSE stream, no resumability, no server-initiated messages.
* **Remote OAuth.** The authorisation flow the current revision defines. Raiker's
  remote transport takes an owner token from an env var named by `auth_ref`.
* **MCP Apps ([SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp)).**
  Sandboxed server-contributed UI, and the better answer to
  [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract).
  Carried as [ADD-24](TO_BE_ADDED.md).
* **Structured tool output, resource links, elicitation, `server/discover`.**
  Elicitation in particular has nowhere to land until the mid-turn question
  surface exists ([ADD-22](TO_BE_ADDED.md)).

**Why Low.** Nothing is broken and nothing is unreachable: every server Raiker
could talk to before, it can still talk to, and a current-revision server now
connects. What remains is capability Raiker has chosen not to build yet, stated
rather than implied.

**Interface outcome that has to be true before this closes.** A connected server
that offers a `ui://` resource, an SSE stream, or an OAuth authorisation
requirement is either supported or **named on its card as unsupported** — never
silently degraded.

---

## BUG-240, BUG-241, BUG-242 and BUG-243 — closed

Their full records — what was observed, the root cause, and the interface
outcome that had to be true before each could be called closed — are in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md):

* **BUG-240** — a semantic space could be built and the question was never
  embedded into it. Closed 2026-08-26 as
  [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered)
  (approved memory) and
  [FIXED-294](FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words)
  (managed knowledge files). The index row above was still marked open after the
  second half landed; that was a stale row, not remaining work.
* **BUG-241** — `fullPage` evidence captures stopped at the first viewport.
  Closed 2026-08-29 as
  [FIXED-313](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport).
* **BUG-242** — Build opened an empty conversation after a reload. Closed
  2026-08-29 as
  [FIXED-309](FIXED_ITEMS.md#fixed-309--build-opened-an-empty-conversation-after-a-reload).
* **BUG-243** — a question could not recall the memory that answered it. Raised
  and closed 2026-08-29 as
  [FIXED-314](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it),
  found while verifying FIXED-311 against a live turn.

---

## BUG-244 — Importing the same memory twice stores it twice

**Severity: Low. Area: memory / import. Status: Open — raised 2026-08-29.**

**Observed.** Memory → *Advanced memory management* → **Review import** was used
four times with the same one-record file while seeding the FIXED-311 round. The
result was four approved memories with identical text, identical scope and
identical provenance, and the recall strip under the next answer named all four.
Nothing warned, and nothing offered to reconcile them.

**Why.** `import_memories` writes each reviewed record through the ordinary
governed write path, which is right — an import must not be a second way into
the store. What it does not do is ask whether the workspace already holds that
sentence. Every other correction path in memory has an answer for this: editing
records a correction, and supersession links let retrieval prefer the valid
record over its predecessor. Import has neither, so a re-import is the one way to
create a contradiction-free duplicate.

**Why it matters more than a tidy list.** Recall is budgeted. Four copies of one
sentence occupy four of the slots a turn has for remembering anything, and the
[FIXED-311](FIXED_ITEMS.md#fixed-311--recall-was-invisible-at-the-moment-it-was-used)
strip now shows that cost to the owner rather than hiding it — which is how this
was noticed at all.

**Proposed fix.** Compare each reviewed record's `content_checksum` against the
owner's live memories before writing. A match is reported in the review step —
"3 of 4 records are already stored" — and skipped rather than written, with the
owner able to import anyway if they intend a second scope. The checksum already
exists and is already computed on write; nothing new has to be stored.

**Required user-interface outcome.** The review step states how many of the
records are new before anything is written, and the import count afterwards
matches what actually changed.

---

## BUG-245 — A cited conversation names its exchanges and cannot open one

**Severity: Low. Area: memory / citations. Status: Open — raised 2026-08-29
while closing [MEM-08](FIXED_ITEMS.md#fixed-316--every-turn-coordinate-was-a-dead-end).**

**Observed.** [FIXED-317](FIXED_ITEMS.md#fixed-317--three-tools-declared-a-source-and-produced-none)
made `conversation_search` a citable source, and
[FIXED-316](FIXED_ITEMS.md#fixed-316--every-turn-coordinate-was-a-dead-end) made a
turn coordinate openable. The two do not meet. Opening a **Past conversations**
chip shows the passage with each exchange's conversation title and date above its
text — which is what makes it checkable at all — but the exchanges are text, not
links, so verifying one still means retyping the title into chat search.

**Why.** The ledger's rule is *one source per executed call*: a call is the unit
the runtime governed and audited, so it is the unit whose provenance can be
stated honestly. A search that returned ten exchanges is therefore one row in
`turn_sources`, and that row has one `locator`. The coordinates of the ten are in
the tool result the runtime saw and are not carried into the ledger.

**Proposed fix.** One nullable `anchors` column on `turn_sources` — a JSON list
of `{session_id, turn_id, title, created_at}` built from the tool result the
runtime read, never from anything the model wrote — and a source panel that
renders each as a link through `conversationLink`. The rule survives: the ledger
still holds one source per call, and the anchors are that source's own contents
rather than ten sources. `turn_sources` already has a migration of its own
(`RAIKER-1038-turn-sources`), so a second is the ordinary path rather than a new
mechanism.

**Deliberately not half-built.** The alternative — writing the links into the
stored `passage` as markup — would put runtime-authored markup into a field the
inspector renders escape-first, which is the one property that keeps a source's
text from being able to say more than it is.

**Required user-interface outcome.** A cited past conversation lists the
exchanges it returned, and each one opens at that exchange, with the same mark a
search hit gets.

---

## BUG-246 — The authority matrix is a scrollable table on a phone, and truncates its own verdicts

**Severity: Low. Area: Permissions / web UI. Status: Open — raised 2026-08-29
during the four-width audit that produced
[FIXED-318](FIXED_ITEMS.md#fixed-318--a-checkbox-was-thirteen-pixels-in-five-places).**

**Observed.** At 390 px, Permissions → *Delegated authority* renders as a
four-column table inside a horizontal scroller. The first two columns fit; the
third is cut mid-word, so the page reads *"Unavail"* under **Raiker agent** for
every row. Nothing is lost — the container scrolls, the page itself does not, and
the audit confirmed the responsive contract holds — but the column that carries
the *verdict* is the one off screen, and a matrix whose answers are the part you
have to scroll for is not doing its job on that width.

**Why it is Low rather than a defect of the contract.** The information is
reachable and correct; this is a layout that was designed for a wide screen and
degraded honestly rather than one that lies. It is filed because "reachable by
scrolling" and "legible" are different bars, and this table is the one place in
the app where the difference is visible.

**Proposed fix.** Below the shell's own 1024 px breakpoint, stack each capability
as a card — the capability name as the heading, owner control and agent verdict
as a two-item definition list — rather than as a row. `AuthorityMatrix.svelte`
already receives the whole row per capability, so this is a second rendering of
the same data and needs no new read.

**Required user-interface outcome.** At a phone width, each capability's owner
control and agent verdict are readable without a sideways scroll, and the words
are whole.
