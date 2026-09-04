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
| [BUG-226](#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Low | Hooks / handlers | Open remainder — reduced again 2026-09-04; `prompt` closed as FIXED-303 and `http` as [FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two), while `mcp_tool` and `agent` stay refused with their reasons |
| [BUG-227](FIXED_ITEMS.md#fixed-366--build-could-read-a-repository-and-not-understand-it) | Low | Plugins / language intelligence | **Closed 2026-09-03 (FIXED-366)** — its first question was a scope decision, and the answer is no: Raiker does not want an LSP client. B10's tool set ships without one and both plugin specs state what that costs |
| [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Low | Plugins / web UI | Open — raised 2026-08-22, split out of BUG-221 |
| [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in) | Low | Live test harness | **Closed 2026-08-30 (FIXED-324)** — every live spec with a sign-in function delegates to the shared helper. The per-spec password that stops two specs sharing a workspace is a different defect, [BUG-247](#bug-247--every-live-spec-brings-its-own-owner-password) |
| [BUG-234](#bug-234--the-remainder-what-raiker-does-not-use-of-the-mcp-revision-it-now-speaks) | Medium → Low | MCP / interoperability | Open — reduced again 2026-09-04 ([FIXED-378](FIXED_ITEMS.md#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport)). The transport conforms and the card names what a server offers and Raiker does not use; SSE streaming, remote OAuth, MCP Apps and `server/discover` remain |
| [GEP-02](GOVERNANCE_ENTRY_PATHS.md#gep-02--the-stop-switchs-scope-is-undefined-for-read-paths), [GEP-03](GOVERNANCE_ENTRY_PATHS.md#gep-03--nested_boundaries_architecturemd278-overstates-the-architecture) | Low | Governance architecture / documentation | Open — not duplicated here. GEP-02 is **an owner decision** and the helper now carries the answer at no cost |
| [BUG-239](#bug-239--an-empty-gate-table-means-three-different-things) | Low | Capability gates / owner decision | Open remainder — the live half closed 2026-08-30 as [FIXED-322](FIXED_ITEMS.md#fixed-322--permissions-said-off-about-a-capability-that-would-have-run): Permissions now reports what the enforcing path answers. Unifying the three resolutions is still **an owner decision** |
| [BUG-240](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | Medium → Low | Memory / retrieval | **Closed 2026-08-26 (FIXED-292, FIXED-294)** — both the provider half and the managed-file half ship; the row is kept so a reader arriving with the number is not left wondering |
| [BUG-241](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport) | Low | Live test harness / evidence | **Closed 2026-08-29 (FIXED-313)** — one shared capture helper; all 56 live specs go through it |
| [BUG-242](FIXED_ITEMS.md#fixed-309--build-opened-an-empty-conversation-after-a-reload) | Medium | Build / web UI | **Closed 2026-08-29 (FIXED-309)** — the conversation rides in the URL and Build restores it |
| [BUG-243](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it) | High | Memory / retrieval | **Closed 2026-08-29 (FIXED-314)** — raised while verifying FIXED-311: a question was being used as a filter |
| [BUG-244](FIXED_ITEMS.md#fixed-319--importing-the-same-memory-twice-stored-it-twice) | Low | Memory / import | **Closed 2026-08-29 (FIXED-319)** — the review step says what is new before anything is written, and the import reports what it changed |
| [BUG-245](FIXED_ITEMS.md#fixed-323--a-cited-past-conversation-named-its-exchanges-and-could-not-open-one) | Low | Memory / citations | **Closed 2026-08-30 (FIXED-323)** — one `anchors` column, built from the tool result the runtime read, and a link per exchange |
| [BUG-246](FIXED_ITEMS.md#fixed-320--the-authority-matrix-hid-its-own-verdicts-on-a-phone) | Low | Permissions / web UI | **Closed 2026-08-29 (FIXED-320)** — raised and closed in the same run; a narrow window gets the same verdicts as stacked cards |
| [BUG-247](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite) | Low | Live test harness | **Closed 2026-08-30 (FIXED-328)** — `OWNER_CREDENTIALS` is the only owner credential in the suite |
| [BUG-273](#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun) | Low | Live test harness / evidence | Open — raised 2026-09-03. The round's supplied key is identity-linked ([FIXED-370](FIXED_ITEMS.md#fixed-370--a-valid-key-was-reported-as-a-bare-http-status)), so no provider turn could run; three scenarios are written and are waiting on a key that authenticates |
| [BUG-271](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one) | Low | Build / Approvals / code review | **Closed 2026-09-04 ([FIXED-375](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one))** — an edit is a new proposal with its own preview, hash and approval; the original resolves as denied with the replacement named. Closes GAP-BUILD B14 |
| [BUG-274](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one) | Medium | Models / provider connection | **Closed 2026-09-04 ([FIXED-372](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one))** — raised and closed in this round: FIXED-370 classified the refusal and left the owner a dead end. The connection now carries the workspace |
| [BUG-248](#bug-248--twenty-seven-live-specs-still-sign-in-inside-a-test-body) | Low | Live test harness | Open remainder — reduced 2026-08-30 to twenty; seven converted and re-run, three must keep their own |
| [BUG-249](FIXED_ITEMS.md#fixed-326--a-fixed_items-link-pointed-at-a-heading-that-does-not-exist) | Low | Documentation / CI | **Closed 2026-08-30 (FIXED-326)** — one line, and `test_docs_consistency` is green |
| [BUG-250](#bug-250--a-shared-live-workspace-carries-state-between-specs) | Low | Live test harness | Open — raised 2026-08-30, the first thing found by actually running a round against one workspace |
| [BUG-251](FIXED_ITEMS.md#fixed-352--every-path-an-owner-typed-was-a-path-they-had-to-know) | Medium | Web UI / file and folder selection | **Closed 2026-09-03 (FIXED-352)** — the host lists directory names and one `PathPicker` serves all four fields |
| [BUG-252](FIXED_ITEMS.md#fixed-350--dropping-a-file-worked-in-one-place-and-was-ignored-in-four) | Low | Web UI / attachments | **Closed 2026-09-03 (FIXED-350)** — one drop target, on every surface that already accepted an upload |
| [BUG-253](FIXED_ITEMS.md#fixed-353--reloading-the-page-signed-the-owner-out) | Medium | Authentication / web UI | **Closed 2026-09-03 (FIXED-353)** — an HttpOnly session cookie with a double-submit CSRF token and an origin check |
| [BUG-254](FIXED_ITEMS.md#fixed-354--a-subscriptions-own-usage-and-limits-were-not-shown) | Medium | Models / Observability | **Closed 2026-09-03 (FIXED-354)** — the limit windows a provider volunteers with a turn, and nothing when it volunteers none |
| [BUG-255](FIXED_ITEMS.md#fixed-351--a-decision-raised-while-raiker-was-in-the-background-reached-nobody) | Low | Approvals / notifications | **Closed 2026-09-03 (FIXED-351)** — the already-permissioned browser notification, only while Raiker is not the visible window |
| [BUG-256](FIXED_ITEMS.md#fixed-363--dictation-was-the-last-surface-that-was-not-local) | Medium | Voice / privacy posture | **Closed 2026-09-03 (FIXED-363)** — a speech runtime on this machine, and a security header that had been denying the microphone to Raiker's own page all along |
| [BUG-266](FIXED_ITEMS.md#fixed-364--a-live-round-could-start-on-the-previous-rounds-data) | Low | Live test harness / host lifecycle | **Closed 2026-09-03 (FIXED-364)** — the reset waits for the process, not the response, and reads the directory back |
| [BUG-267](FIXED_ITEMS.md#fixed-362--an-expected-answer-was-written-to-the-console-as-a-failure) | Low | Authentication / web UI | **Closed 2026-09-03 (FIXED-362)** — the boot question gets a route that answers it rather than refusing it |
| [BUG-269](FIXED_ITEMS.md#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local) | Low | Voice / privacy posture | **Closed 2026-09-04 ([FIXED-373](FIXED_ITEMS.md#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local))** — Raiker speaks only with a voice it can see is on this device, and names the language when there is none |
| [BUG-270](FIXED_ITEMS.md#fixed-365--a-fresh-install-named-a-model-nobody-had) | Medium | Models / first-run default | **Closed 2026-09-03 (FIXED-365)** — option **B**, detect before claiming: a PATH lookup cached in a row, never a connection. Option A was declined because it removes the runtime's out-of-box fallback |
| [BUG-268](FIXED_ITEMS.md#fixed-361--the-folder-picker-handed-back-redacted_secret-instead-of-a-path) | High | Web UI / redaction | **Closed 2026-09-03 (FIXED-361)** — found by Linux CI; the picker returned `[REDACTED_SECRET]` for an ordinary folder |
| [BUG-257](FIXED_ITEMS.md#fixed-355--a-rejected-key-was-reported-as-a-network-failure) | Medium | Models / provider errors | **Closed 2026-09-03 (FIXED-355)** — raised while verifying BUG-251 against live providers |
| [BUG-258](FIXED_ITEMS.md#fixed-356--a-picker-offered-and-defaulted-to-a-model-that-cannot-answer) | High | Models / every picker | **Closed 2026-09-03 (FIXED-356)** — the default was `text-embedding-ada-002` |
| [BUG-259](FIXED_ITEMS.md#fixed-357--a-fresh-raiker-adopted-whichever-chatgpt-account-codex-was-signed-in-to) | High | Models / ChatGPT subscription | **Closed 2026-09-03 (FIXED-357)** — a status *read* was performing a connection |
| [BUG-260, BUG-263, BUG-264](FIXED_ITEMS.md#fixed-358--choosing-among-four-hundred-models-was-a-dropdown-with-no-search) | High | Models / web UI | **Closed 2026-09-03 (FIXED-358)** — no dropdown; one picker with a search, on both surfaces |
| [BUG-261, BUG-262](FIXED_ITEMS.md#fixed-359--first-run-could-detect-a-missing-runtime-and-not-offer-to-install-it) | Medium | Models / first run | **Closed 2026-09-03 (FIXED-359)** — install a runtime and choose a model without leaving first run |
| [BUG-265](FIXED_ITEMS.md#fixed-360--a-policy-refusal-was-reported-as-a-wrong-password) | Medium | Authentication / web UI | **Closed 2026-09-03 (FIXED-360)** — "Authentication failed." for a one-owner-per-instance refusal |
| [GAP-BUILD](GAP_BUILD_CHAT.md#gap-build--what-build-needs-to-stand-against-a-class-leading-coding-agent) | — | Build — coding-agent parity | Analysis (18 complete, 2 partial; B14 closed 2026-09-04 as [FIXED-375](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one), B10 2026-09-03 as FIXED-366, B13 2026-08-30 as FIXED-321, B18 2026-08-29 as FIXED-315, B16 by BUG-206 slice D. B15 and B20 remain partial on [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution)) |
| [GAP-CHAT](GAP_BUILD_CHAT.md#gap-chat--what-chat-needs-to-work-as-a-class-leading---agentic-work-assistant) | — | Chat — work-assistant parity | Analysis (16 complete, 1 partial, 1 open; C15 closed by C1/C4, C11 2026-09-03 as FIXED-367, C18 as FIXED-368, C17 2026-08-29 as FIXED-311. C10 is partial — the notification half ships as [FIXED-374](FIXED_ITEMS.md#fixed-374--a-routine-ran-all-night-and-told-nobody); C12 stays an architecture decision) |

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

**What shipped first (FIXED-279).** The fork is a named table,
`CAPABILITY_UNSET_RESOLUTION` in
[`raiker/runtime/authority/admission.py`](../../raiker/runtime/authority/admission.py),
read by the enforcing paths and by the model's context bundle — which used to be
told `web_fetch: disabled` on an install where the tool would have fetched.

**What shipped on 2026-08-30
([FIXED-322](FIXED_ITEMS.md#fixed-322--permissions-said-off-about-a-capability-that-would-have-run)).**
The table had not reached `get_effective_capability_gate`, which is what the gate
*view* is built from — so **Permissions**, the one surface an owner decides from,
still said *Web fetch* was **Off** while the tool would have run. The view now
reports `unset_resolution` and `enforced_enabled` beside `state`, the page reads
**On by default** where they disagree, the card names which rule applies, and the
only action such a row offers is **Turn off**. Nothing was loosened or tightened;
the behaviour is described rather than changed.

**What is left, and it is the whole of the owner's question.** Whether the three
resolutions should be one. Collapsing them is not a refactor — the two paragraphs
above this say what each direction costs — and it stays an owner decision. It is
no longer *invisible*, which was the part an implementer could fix.

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
It now also accepts a bounded `prompt` and, since
[FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two),
an `http` handler behind a named, revocable egress grant. A rule naming
`mcp_tool` or `agent` is still refused at parse time, which is the right failure
until each has a governed resource path.

The title has undercounted twice and is kept as raised. After FIXED-303 three
remained; after FIXED-380, **two** — `mcp_tool` and `agent`.

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
redacted bounded event data and advisory-only output.

**Completed second slice (2026-09-04).**
[FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two)
adds `http` behind exactly the grant this entry named:
`RAIKER_HOOK_EGRESS_ALLOWLIST`, empty by default, revoking every `http` rule at
once when cleared, read live by the Hooks page, and refusing with the host in the
reason. It sends the same bounded, redacted event body the `prompt` handler
already sends, from the same function; a remote responder can deny or ask and can
never permit, and a non-2xx is not a deny.

`mcp_tool` and `agent` stay refused until there is a stated answer to a hook
reaching authority the turn did not have.

**Not a regression, and visible today.** A rule naming an unsupported type is
refused at parse time rather than accepted and ignored, and the Hooks tab reports
the file as failed with the reason — so an owner writing one is told, rather than
believing a guard is in place.

---


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

**Closed 2026-08-30 as
[FIXED-324](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in).**
Every live spec that had a sign-in *function* delegates to
`signInAsOwner`, and two robustness steps only one spec carried — waiting for the
username field to become enabled, and accepting the navigation rail as proof of a
session — are now the helper's, so all of them get them.

The record stays here rather than moving, because what is left is a *different*
defect and reads best against the one it came out of: each spec still hardcodes
its own owner password, so two specs cannot share one workspace. That is
[BUG-247](#bug-247--every-live-spec-brings-its-own-owner-password).

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

**Reduced again 2026-09-04**
([FIXED-378](FIXED_ITEMS.md#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport)).
The transport now conforms where a real server would have refused it: `Accept`
carries both framings (a conformant server may answer 406 to a POST offering only
JSON), a session is released with `DELETE`, a dropped session re-handshakes once,
and a `401` with `WWW-Authenticate` is named as the OAuth requirement it is
rather than as a network failure. **The interface outcome below is met**: what a
connected server offers and Raiker does not use is named on its card.

**What is left.** Negotiating a revision is not implementing it. Each of the
following was previously *blocked* by the version pin and is now ordinary work:

* **Streamable HTTP streaming.** Raiker's `http` transport is its own bounded
  JSON-RPC client. It reads an `text/event-stream` answer whole rather than
  streaming it, and holds no open connection between turns: no incremental
  delivery, no resumability, no server-initiated messages. A server that answers
  this way is **named as such on its card** rather than silently degraded.
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
silently degraded. **Met 2026-09-04 (FIXED-378):** the server's own `initialize`
capabilities and what its transport was observed doing are stored as feature
names and rendered as one sentence each, and a capability Raiker has never heard
of is still named by its own key rather than dropped for not being on a list.

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

## BUG-245 — A cited conversation names its exchanges and cannot open one

**Closed 2026-08-30 as
[FIXED-323](FIXED_ITEMS.md#fixed-323--a-cited-past-conversation-named-its-exchanges-and-could-not-open-one).**
One nullable `anchors_json` column on `turn_sources`, built from the tool result
the runtime read and never from anything the model wrote, and a link per exchange
in both source panels. The ledger's rule survives: one source per executed call,
with the anchors as that source's own contents rather than as ten sources.

---

## BUG-247 — Every live spec brings its own owner password

**Closed 2026-08-30 as
[FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite).**
`OWNER_CREDENTIALS` is the only owner credential in the live suite. Thirty specs
stopped passing an explicit credential to `signInAsOwner`; the twenty-two that
still sign in inline point their own constants at it, so *who* a spec signs in as
and *how* it signs in stayed separate changes. The three specs that are about
signing in keep their own.

Closing it found the thing that had actually been stopping a whole round from
running against one workspace:
[FIXED-327](FIXED_ITEMS.md#fixed-327--the-setup-wizard-trapped-every-live-spec-after-the-first-one),
a shared helper that knew one of the setup wizard's five stages.

---

## BUG-248 — Twenty-seven live specs still sign in inside a test body

**Severity: Low. Area: live test harness. Status: Open remainder — raised
2026-08-30 while closing [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in),
reduced from twenty-seven to twenty the same day
([FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite)).**

**Observed.** Thirty-seven live specs delegate to `signInAsOwner`. Twenty-seven
others sign in *inline* in a test body, and those copies are the ones BUG-229
described: several still key on the empty-workspace greeting.

**Seven are done, each re-run as it was converted** — `all-pages`,
`all-pages-theme`, `observability`, `default-ollama`, `memory-knowledge-context`,
`memory-semantic` and `memory-vector-index`. That found three pieces of drift
nothing else would have, including a spec still driving a Vite dev server on port
5174; they are recorded in FIXED-328. **Twenty are left**, and the reason they
are left is unchanged.

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

## BUG-249 — A FIXED_ITEMS link points at a heading that does not exist

**Closed 2026-08-30 as
[FIXED-326](FIXED_ITEMS.md#fixed-326--a-fixed_items-link-pointed-at-a-heading-that-does-not-exist).**
One line, and `test_docs_consistency` is green. The guard did its job: an anchor
written from memory is exactly the drift it exists to catch.

---

## BUG-250 — A shared live workspace carries state between specs

**Severity: Low. Area: live test harness. Status: Open — raised 2026-08-30, and
it is the first thing found by actually running a round against one workspace
rather than re-seeding one per spec.**

**Observed.** With
[FIXED-327](FIXED_ITEMS.md#fixed-327--the-setup-wizard-trapped-every-live-spec-after-the-first-one)
and [FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite)
in, a round finally *can* share a workspace — and three specs then failed for a
reason none of them is about. Every one is a spec asserting the state a first
run leaves rather than the behaviour it is named for:

* `bug-74-84-known-limits-live` asserted the readiness window still reads `5`,
  the shipped default, in a spec that sets it to `30`. Fixed here: it asserts
  the bound the control states and round-trips a value that differs from the
  stored one, the same re-runnable shape the readiness chip beside it already
  used.
* `bug-74-84-known-limits-live` also clicked **Connect**/**Reconnect** on the
  provider card. Reconnect moved into Details (BUG-208 slice E), so a card that
  is already connected offers neither and the spec hung for its full ten-minute
  timeout. Fixed here by going through `connectHostedProvider`, which knows both
  routes.
* `bug-58-known-limits-live` needs three seeded marker files and, in its own
  preamble, a fresh workspace: two of its claims are about what a gate does
  *before the owner has touched it*, and the run itself turns `web_fetch` on.
  That one is correct as written and simply cannot share a workspace.

**And one that is the product working as designed.** `read_file` was contained
after three consecutive `not_found` failures from an earlier spec's turns, so a
later spec's read batch met a paused tool. Containment is owner-visible,
persistent and exactly what it should be; what is missing is that the harness
has no notion of *resetting the workspace's earned state* between specs that
need a clean one.

**Proposed fix.** Not one flag. Two separate things, in this order:

1. Mark the specs that genuinely require a first-run workspace, so a round can
   run them in their own instance rather than discovering it by failing.
   `bug-58-known-limits-live`, `default-ollama-live` and the three sign-in specs
   BUG-248 names are the known set.
2. For the rest, make each assertion re-runnable the way the two above now are:
   assert the behaviour and the stated bounds, not the value a fresh install
   happens to hold.

**Why this is not a defect in the product.** Nothing here is Raiker behaving
wrongly. It is the suite having been written, spec by spec, against a workspace
that was always new — which is the assumption BUG-229, BUG-247 and BUG-248 have
been peeling away one layer at a time, and this is the layer under them.

**Required user-interface outcome.** None; harness-only.

---

## BUG-251 — Every path an owner types is a path they have to know

**Closed 2026-09-03 as
[FIXED-352](FIXED_ITEMS.md#fixed-352--every-path-an-owner-typed-was-a-path-they-had-to-know).**
A host-side `GET /api/host/paths` lists directory names, and one `PathPicker`
dialog serves all four fields. The record — including why a browser cannot
answer this on its own — is in `FIXED_ITEMS.md`.

---

## BUG-252 — Attaching by drag and drop works in one place only

**Closed 2026-09-03 as
[FIXED-350](FIXED_ITEMS.md#fixed-350--dropping-a-file-worked-in-one-place-and-was-ignored-in-four).**
One drop target, used by every surface that already accepted an upload.

---

## BUG-253 — Reloading the page signs the owner out

**Closed 2026-09-03 as
[FIXED-353](FIXED_ITEMS.md#fixed-353--reloading-the-page-signed-the-owner-out).**
An `HttpOnly`, `SameSite=Strict` session cookie, paired with a double-submit
CSRF token and an origin check on every state-changing request. The bearer
header path is unchanged and exempt.

---

## BUG-254 — A subscription's own usage and limits are not shown

**Closed 2026-09-03 as
[FIXED-354](FIXED_ITEMS.md#fixed-354--a-subscriptions-own-usage-and-limits-were-not-shown).**
Raiker records the limit windows a provider volunteers as part of a turn, and
shows nothing at all for a provider that volunteers none.

---

## BUG-255 — Nothing announces an approval outside the browser

**Closed 2026-09-03 as
[FIXED-351](FIXED_ITEMS.md#fixed-351--a-decision-raised-while-raiker-was-in-the-background-reached-nobody).**
The already-permissioned browser notification, raised only while Raiker is not
the window the owner is looking at.

---

## BUG-256 — Dictation sends audio to the browser's speech service

**Closed 2026-09-03 as
[FIXED-363](FIXED_ITEMS.md#fixed-363--dictation-was-the-last-surface-that-was-not-local).**
A local speech-to-text runtime, configured beside the other local runtimes and
used automatically when it is there. Fixing it also uncovered that
`Permissions-Policy: microphone=()` had been denying the microphone to Raiker's
own page, so the control could never have worked in a served build.

---

## BUG-266 — A live workspace directory cannot be deleted while the host holds it

**Closed 2026-09-03 as
[FIXED-364](FIXED_ITEMS.md#fixed-364--a-live-round-could-start-on-the-previous-rounds-data).**
`scripts/reset_live_workspace.py` waits for the process to exit, retries the
removal, reads the directory back, and refuses the round if any of the three
fails.

---

## BUG-267 — The boot session probe logs a 401 to the console on every locked load

**Closed 2026-09-03 as
[FIXED-362](FIXED_ITEMS.md#fixed-362--an-expected-answer-was-written-to-the-console-as-a-failure).**
`GET /api/auth/session-state` answers the page's boot question with `200` both
ways, and clears the stale cookie so the next load does not ask at all.

---

## BUG-269 — Read aloud is the half of voice that is still not local

**Severity: Low. Area: voice / privacy posture. Status: Closed 2026-09-04 as
[FIXED-373](FIXED_ITEMS.md#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local).
The filter turned out to be enough; no local synthesis runtime was needed.**

**Observed.** Dictation can now be made to run entirely on this machine.
**Read aloud** cannot: it calls the browser's `speechSynthesis`, and nothing in
the product lets an owner keep it on the device the way a transcription runtime
now does for the microphone.

**Why it is lower than BUG-256 was.** What crosses the boundary is the
*response text*, not a recording of the owner, and on most platforms the browser
speaks with an OS voice that never leaves the device at all. But "most" is doing
work in that sentence: Chrome ships remote voices for several languages and
picks one without saying so, and Raiker cannot tell which kind it got. The
asymmetry is also its own defect — an owner who has just set on-device
transcription up has no reason to expect the other direction to behave
differently, and nothing tells them it does.

**Proposed fix.** The same shape as BUG-256, one size smaller. `speechSynthesis`
exposes `voice.localService`; a *Use only on-device voices* choice in
Raiker could prefer those and say plainly when a language has none, rather than
silently using a remote one — with no setting, exactly as dictation now works. A local
synthesis runtime — Piper or equivalent, pointed at the way the transcription
server now is — is the fuller answer and is worth doing only if the filter turns
out not to be enough.

**Required user-interface outcome.** Read-aloud either uses a voice that stays on
this machine or says that it could not find one, without asking the owner to
configure anything.

---

## BUG-271 — A reviewer can narrow a change, and cannot correct one

**Severity: Low. Area: Build / Approvals / code review. Status: Closed 2026-09-04
as [FIXED-375](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one),
which is what "What it would take" below describes; GAP-BUILD B14 closes with
it.**

**Observed.** Per-hunk accept and reject ship. *Edit then accept* — the reviewer
changing a line in the proposed diff and approving the result — does not, and is
still not offered rather than being shown as a control the server would refuse.

**Why it did not come with the other half.** A narrowing and an edit are
different kinds of thing, and the difference is exactly the one the approval
boundary is built on:

* A **narrowing** is a subset of what was approved. `select_hunks` copies bytes
  out of the approved patch and copies nothing else in, so the A1 immutable-intent
  hash still covers the whole approved change and the executed change is provably
  inside it.
* An **edit** is a *different action*. Its bytes were never approved, so it
  cannot ride that hash — and the one thing the relay must never do is execute
  arguments no human read. `ResolveApprovalRequest` sets `extra="forbid"`
  precisely to stop an edited payload arriving on a resolve.

**What it would take.** An edit has to become a **new proposal** rather than an
amended one: the owner's edited patch is submitted as a fresh action, gets its
own preview, its own hash and its own approval, and the original resolves as
rejected-with-a-replacement so the audit trail says what happened. That is a
proposal path, not a field on the decision — which is why it is a separate entry
rather than the unfinished tail of FIXED-369.

**Required user-interface outcome.** Either an edit control that produces a
second decision the owner makes on their own text, or nothing. What must not
appear is a control that looks like an amendment to the approval in front of it.

---

## BUG-273 — Three live scenarios of the 2026-09-03 round are written and unrun

**Severity: Low. Area: live test harness / evidence. Status: Open — raised
2026-09-03.**

**Observed.** `priority-round-real-turn-live.spec.ts` covers the three claims of
that round which need a model to actually answer:

* the setup meter reading **1 model ready** once a provider is connected, which
  is the other half of [FIXED-365](FIXED_ITEMS.md#fixed-365--a-fresh-install-named-a-model-nobody-had)
  — the *no* case is proven, the *yes* case is not;
* a routine's cycle running **inside its own conversation**
  ([FIXED-367](FIXED_ITEMS.md#fixed-367--background-work-finished-into-a-status-line));
* that same thread appearing on the board
  ([FIXED-368](FIXED_ITEMS.md#fixed-368--where-did-i-say-that-was-answered-what-am-i-working-on-was-not)).

None of the three ran. The key supplied for the round is identity-linked and
cannot authenticate without a workspace id — which is
[FIXED-370](FIXED_ITEMS.md#fixed-370--a-valid-key-was-reported-as-a-bare-http-status),
raised from this very attempt — so no turn could be sent.

**What *is* proven meanwhile**, and it is not nothing: all three behaviours are
covered by unit and API tests
(`test_task_conversation_thread.py`, `test_work_threads.py`,
`TasksView.test.ts`, `SearchChatView.test.ts`, `WorkbenchView.test.ts`), and the
surfaces themselves were walked live at four widths with no console error. What
is missing is the end-to-end evidence a FIXED entry is normally held to: a real
turn, in a real thread, on a real provider.

**Reduced 2026-09-04.** The fix is still not code *in the product* — that half
is done. [FIXED-372](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one)
gives the connection a **Workspace ID**, so the identity-linked key supplied for
that round is now usable by Raiker; what is still missing is the id itself, which
only the key's owner has. Set `RAIKER_LIVE_ANTHROPIC_KEY` to a key that
authenticates — a standard console key, or an identity-linked one **with**
`RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID` set to its workspace — and run:

```
npx playwright test --project=live e2e/priority-round-real-turn-live.spec.ts
```

The spec skips itself when the variable is unset, so it neither fails CI nor
claims a scenario it did not run.
