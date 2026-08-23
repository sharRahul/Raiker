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

**This list holds only what is still open.** A row marked *Fixed* is kept in the
index so a reader arriving with that number is not left wondering; its full
record — observation, root cause, and the interface outcome that had to be true
first — is in [`FIXED_ITEMS.md`](FIXED_ITEMS.md) under the FIXED number the row
names.

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced again 2026-08-21; foreground SSH/Daytona and safeguarded egress/credential/trust foundations ship, while live container and external trust-anchor proofs remain |
| BUG-216 | High | Checkpoints / Windows paths | **Fixed 2026-08-21 — FIXED-240** |
| BUG-217 | Low | Test isolation / SQLCipher posture | **Fixed 2026-08-21 — FIXED-244** |
| MEM-06 … MEM-14 | Medium → Low | Memory reliability | Open: MEM-07 … MEM-10. MEM-06 closed 2026-08-21 (FIXED-241); MEM-11/12 remain regression-proven. See [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md) |
| [BUG-218](#bug-218--auto-mode-has-no-alignment-check-of-its-own) | Medium | Decision modes / Build / Chat | Open — raised 2026-08-21 |
| BUG-219 | Low | Approval modes | **Fixed 2026-08-22 — FIXED-262** |
| [BUG-220](#bug-220--nothing-owns-a-set-of-delegated-child-tasks) | Medium | Tasks / delegation | Open — raised 2026-08-21 |
| BUG-221 | Medium → Low | Plugins / extensibility | **Closed 2026-08-22 — FIXED-256, FIXED-259, FIXED-260.** Hooks, skills and MCP-server offers all contribute; panels continue as [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) |
| BUG-222 | Low | Hooks | **Fixed 2026-08-22 — FIXED-254** |
| BUG-223 | Medium | Hooks / lifecycle | **Fixed 2026-08-22 — FIXED-255** |
| BUG-224 | Low | Web tests / environment | **Fixed 2026-08-22 — FIXED-258** |
| [BUG-225](#bug-225--a-channel-can-be-described-and-never-reached) | Medium → Low | Channels / extensibility | Open — reduced three times 2026-08-22 (FIXED-261, FIXED-265, FIXED-267). **The premise was wrong**: the transport existed and had no owner surface. Contract, surface and rate limits ship; routing modes and approval-relay resolution remain |
| [BUG-226](#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Low | Hooks / handlers | Open — raised 2026-08-22 |
| [BUG-227](#bug-227--there-is-no-lsp-surface-for-a-plugin-to-contribute-to) | Low | Plugins / language intelligence | Open — raised 2026-08-22 |
| [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Low | Plugins / web UI | Open — raised 2026-08-22, split out of BUG-221 |
| [BUG-229](#bug-229--most-live-specs-sign-in-only-on-an-empty-workspace) | Low | Live test harness | Open — raised 2026-08-22 |
| [BUG-230](#bug-230--checkpoint-rewind-is-built-registered-tested-and-unreachable) | **High** | Checkpoints / recovery | Open — raised 2026-08-23 |
| [BUG-231](#bug-231--the-audit-log-cannot-be-taken-out-of-the-product) | **High** | Observability / evidence | Open — raised 2026-08-23 |
| [BUG-232](#bug-232--two-egress-implementations-exist-and-the-weaker-one-is-registered) | **High** | Egress / governance | Open — raised 2026-08-23 |
| [BUG-233](#bug-233--an-approval-promises-a-rewind-it-cannot-give-for-a-file-over-8-mib) | Medium | Checkpoints / approvals | Open — raised 2026-08-23 |
| [BUG-234](#bug-234--the-mcp-client-is-five-protocol-revisions-behind) | Medium | MCP / interoperability | Open — raised 2026-08-23 |
| [GEP-01 … GEP-04](GOVERNANCE_ENTRY_PATHS.md#6-open-items) | Low → Unknown | Governance architecture | Open — raised 2026-08-23 in [`GOVERNANCE_ENTRY_PATHS.md`](GOVERNANCE_ENTRY_PATHS.md), not duplicated here |
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

* ~~**Rate limits.**~~ Closed the same day as FIXED-267: a fixed window per
  `(connector, sender)`, 60/min by default, with the refusal recorded.
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
5. ~~**Rate limits**~~ — raised by this work and closed by it (FIXED-267).

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
the right failure.

**The title undercounts: it is four, not three** — `http`, `mcp_tool`, `prompt`
and `agent`. The title is left as raised so the anchor other documents link to
keeps working; the count here is the accurate one.

**Corrected 2026-08-22.** This entry used to say `command` is the only handler
type Claude Code's own hooks have, and that the gap was therefore against
Raiker's own reference document rather than against Claude Code. That was wrong:
[the Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
documents and specifies all five — `command`, `http`, `mcp_tool`, `prompt` and
`agent` — with per-type fields. **This is a real gap against Claude Code.** It
stays Low because each missing type needs a resource the hook path deliberately
does not have (below), not because the reference lacks them.

This is the remainder of the hooks gap after BUG-223 — and the *events* are not
at parity either: Raiker emits sixteen of the thirty-one Claude Code documents.
See
[`../REFERENCE_PLATFORM_COMPATIBILITY.md`](../REFERENCE_PLATFORM_COMPATIBILITY.md#25-extensibility--hooks).

**Root cause.** Each of the four needs a resource the hook path deliberately
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

Not urgent, and deliberately not done in bulk this round: each older spec is the
evidence behind a closed FIXED entry, and re-running one is how that evidence is
refreshed — a sweeping edit across thirty of them is a change to thirty pieces of
evidence, which deserves its own pass rather than being smuggled into another.

---

## BUG-230 — Checkpoint rewind is built, registered, tested, and unreachable

**Severity: High. Area: checkpoints / recovery. Status: Open — raised 2026-08-23.**

**Observed.** `README.md` and `SECURITY_ARCHITECTURE.md` both list **recoverable**
as a property of the runtime. An owner cannot recover anything. Capture is
automatic and complete before every approved single-file mutation; nothing puts
it back.

**Reproduction.** Approve a `write_file`. Open **Observability → Checkpoints**,
select the checkpoint, and read the preflight: it names the files a restore
*would* touch. There is no control that performs one. `/checkpoints restore` in
the terminal client does the same thing — computes a preflight, performs nothing.

**Root cause.** `CheckpointRestoreExecutor`
(`raiker/runtime/executors/tier1_checkpoint.py`) is implemented, is in
`REAL_EXECUTOR_CAPABILITIES`, is registered by
`build_default_executor_registry`, has a critical-classification rule
(`raiker/runtime/authority/critical.py:207`) and is covered by tests. What does
not exist is a caller: **no route, terminal command or model tool constructs a
`checkpoint_restore` action.** `GET /api/checkpoints/{id}/restore-plan`
(`raiker/api/routes_dashboard.py:2073`) is read-only by design, and
`checkpoint_restore_execution` is deliberately not in `EXECUTABLE_ON_APPROVAL`.
It is one of three registered-but-unreachable executors recorded in
[`GOVERNANCE_ENTRY_PATHS.md` §3.5](GOVERNANCE_ENTRY_PATHS.md).

**Proposed fix.** A `POST /api/checkpoints/{id}/restore` that raises an ordinary
approval for `checkpoint_restore_execution`, plus the Checkpoints action and the
terminal command that call it. The executor already writes its own pre-image, so
a restore is itself reversible, and the critical-classification rule already
routes a cross-principal restore to the human-only lifecycle. Nothing new has to
be designed — only routed.

**Interface outcome that has to be true before this closes.** From
**Observability → Checkpoints**, an owner selects a checkpoint, reads the
preflight naming exactly which files change, approves, and the workspace really
goes back — with the restore itself appearing as a new checkpoint. A restore of a
file whose pre-image is `oversize` (see BUG-233) must say so in the preflight
rather than failing at execution.

**Why High.** Every other severity in this document is measured against what the
product claims. This is the largest distance between a claim and the product in
the repository, it blocks two of the four pillars
([`PILLAR_MAP.md`](PILLAR_MAP.md) → P2 and P3), and the work is routing code that
already exists.

---

## BUG-231 — The audit log cannot be taken out of the product

**Severity: High. Area: observability / evidence. Status: Open — raised 2026-08-23.**

**Observed.** Raiker keeps an append-only, account-scoped audit log and describes
it as evidence. Evidence that cannot leave the product is evidence that cannot be
used anywhere it matters — a review, an incident write-up, a second tool.

**Reproduction.** There is no route to reproduce against; that is the defect.
`GET /api/memory/export` exists and works (`raiker/api/routes_memory.py`), which
is what makes the absence conspicuous rather than an oversight of principle.

**Root cause.** `raiker/events/export.py` produces a **redacted export manifest**
and the store keeps it. `audit_export` is a capability in `ALL_CAPABILITIES` with
**no executor**, so it is one of the twenty-two that cannot be activated, and no
REST route surfaces the manifest the code already builds.

**Proposed fix.** Give `audit_export` a real executor that returns the existing
manifest, and a route behind it, scoped to the acting principal and passing the
same redaction the log itself passes. The redaction is the hard part and it is
already written.

**Interface outcome.** **Observability → Audit log** offers an export; what comes
out carries the same redaction the on-screen record does, is scoped to the
owner's own account, and the export itself is an audited event.

---

## BUG-232 — Two egress implementations exist, and the weaker one is registered

**Severity: High. Area: egress / governance. Status: Open — raised 2026-08-23.**

**Observed.** Raiker has two different implementations of "reach the network",
and they do not enforce the same controls. The one an owner is told about is the
guarded one. The other is registered in the default executor registry.

**Root cause.** The model-facing path — `web_fetch` and `web_search` through the
broker — is `WebAccessService` (`raiker/runtime/web_access.py`): HTTPS only, no
credential in the URL, every resolved address must be public, every redirect hop
re-governed, the connection pinned to an address that already passed.

`WebFetchExecutor` and `NetworkExecutor`
(`raiker/runtime/executors/tier2_web.py`) call
`raiker.runtime.executors.sandbox.fetch_url`, which enforces **one** control: a
hard-coded four-host `fnmatch` against `parsed.netloc` (`api.github.com`,
`raw.githubusercontent.com`, `pypi.org`, `files.pythonhosted.org`). No HTTPS
requirement. No public-address check. No pinning. `urllib` follows redirects
freely, so a redirect from an allowlisted host to anywhere is followed unchecked.
The allowlist is not owner-editable.

**Nothing currently routes to either.** There is no `network` tool, neither
capability is in `EXECUTABLE_ON_APPROVAL`, and no route constructs the action —
they are exercised only by `tests/test_vertical_slice_e2e.py`. That is why no
test failed and no defect was raised for months.

**Proposed fix.** Delete `WebFetchExecutor`, `NetworkExecutor`, the
`network_execution` capability and the `fetch_url` allowlist path; or, if a
capability-level egress executor is wanted later, route it through
`WebAccessService` so there is one implementation. Decide the same question for
`process_execution`, whose lifecycle `shell_execution` already covers.

**Interface outcome.** **Permissions** stops offering a `network` gate that
changes nothing when opened, and there is exactly one answer to "what happens
when Raiker reaches the internet".

**Why High despite being unreachable.** Severity here is not "can it be exploited
today" — it cannot. It is that Raiker's central claim is that no path bypasses
governance, and a registered executor with a weaker guard is one call site away
from making that false. Written up in
[`../threat-models/network-execution.md`](../threat-models/network-execution.md).

---

## BUG-233 — An approval promises a rewind it cannot give, for a file over 8 MiB

**Severity: Medium. Area: checkpoints / approvals. Status: Open — raised 2026-08-23.**

**Observed.** The approval notice for a file mutation reads: *"The previous file
contents are checkpointed first, so it can be rewound."* For a file larger than
8 MiB that sentence is false, and the owner reads it **before** deciding.

**Root cause.** `MAX_PRE_IMAGE_BYTES` is 8 MiB
(`raiker/checkpoints/capture.py`). A file above it is still written; its
pre-image is recorded with `capture_status: oversize`, which means *not
restorable*. The notice in `raiker/control/dashboard.py` is a constant for the
whole file-mutation class and does not consult the capture outcome — and it
cannot, because capture happens after the decision.

**Proposed fix.** Compute the target's size when building the approval preview
and, above the cap, replace the rewind sentence with one that says the change
will not be reversible and why. The preview already resolves the path, so this is
a `stat` and a branch.

**Interface outcome.** An owner approving a large-file change is told, before
approving, that this particular change cannot be rewound.

**Related.** The same `capture_status` distinction should surface in the restore
preflight built for BUG-230.

---

## BUG-234 — The MCP client is five protocol revisions behind

**Severity: Medium. Area: MCP / interoperability. Status: Open — raised 2026-08-23.**

**Observed.** Raiker negotiates Model Context Protocol revision **`2024-11-05`**.
The current revision is
[**`2026-07-28`**](https://modelcontextprotocol.io/specification/versioning). A
server that implements only the current revision cannot be connected at all, and
nothing in the product or the documentation said which revision Raiker speaks.

**Root cause.** `MCP_PROTOCOL_VERSION = "2024-11-05"` and
`PROTOCOL_VERSION = "2024-11-05"` in `raiker/runtime/executors/mcp.py`. The
bounded stdio session Raiker runs — `initialize`, `tools/list`, `tools/call` — is
valid for that revision and interoperates with servers still accepting the
handshake-based negotiation.

**What being behind costs.** Everything the specification added since is out of
reach, and three of them are already recorded as separate gaps that share this
single cause:

* **Streamable HTTP session semantics** — Raiker's `http` transport is its own
  bounded client, not the spec's transport.
* **Remote OAuth** — the authorisation flow the current revision defines.
* **MCP Apps ([SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp))**
  — sandboxed server-contributed UI, which is also the better answer to BUG-228.
* Structured tool output, resource links, elicitation, per-request `_meta`
  version declaration, and the mandatory `server/discover` RPC.

**Proposed fix.** Negotiate `2026-07-28`, keeping the `2024-11-05` handshake for
older servers — the specification's backward-compatibility section provides for
exactly this. Fail-closed behaviour is unaffected either way: the interpreter
allowlist, workspace-relative args, containment and redacted metadata-only events
are Raiker's own and do not come from the protocol.

**Interface outcome.** **Extensions → MCP** states the revision a connected
server negotiated, and a server that speaks only the current revision connects.

**Why Medium and not High.** Nothing is broken for servers Raiker can already
talk to, and no governance property depends on the version. It is here because
one change unblocks three separate rows, which makes it the highest-leverage item
on the platform pillar ([`PILLAR_MAP.md`](PILLAR_MAP.md) → P4).
