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

Open defects originally found while executing
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

Evidence: `screenshots/not-working/` (defects),
`screenshots/working/` (verified behaviour).

**Only unresolved BUG entries are indexed below.** Closed bugs and completed memory/governance reviews are recorded in [`FIXED_ITEMS.md`](FIXED_ITEMS.md), with historical rationale in Git history. The separate [Build/Chat capability gap ledger](GAP_BUILD_CHAT.md) is not a BUG list.

**Historical ID collision:** `BUG-280` was reused for two unrelated findings. The closed Observability empty-state defect is [FIXED-391](FIXED_ITEMS.md#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line); the *open* `BUG-280` row below is the weather/provider live-evidence remainder. Its closed clock sub-scope is [FIXED-539](FIXED_ITEMS.md#fixed-539--a-real-turn-now-answers-from-raikers-clock-and-the-weather-half-still-cannot-be-measured-here). The closed UI defect is not reopened.

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced again 2026-08-21; foreground SSH/Daytona and safeguarded egress/credential/trust foundations ship, while live container and external trust-anchor proofs remain |
| [BUG-226](#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Low | Hooks / handlers | Open remainder — reduced again 2026-09-04; `prompt` closed as FIXED-303 and `http` as [FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two), while `mcp_tool` and `agent` stay refused with their reasons |
| [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Low | Plugins / web UI | Open — raised 2026-08-22, split out of BUG-221 |
| [BUG-234](#bug-234--the-remainder-what-raiker-does-not-use-of-the-mcp-revision-it-now-speaks) | Medium → Low | MCP / interoperability | Open — reduced twice on 2026-09-04 ([FIXED-378](FIXED_ITEMS.md#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport), [FIXED-387](FIXED_ITEMS.md#fixed-387--a-tool-result-had-one-shape-and-the-revision-defines-six)) and twice again on 2026-09-05 ([FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own), [FIXED-412](FIXED_ITEMS.md#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped)). The transport conforms, the card names what a server offers and Raiker does not use, every content-block shape reaches the model, a server-initiated request is answered rather than mistaken for a response, and an event stream is read and resumed correctly; **incremental** delivery, remote OAuth, MCP Apps and elicitation's owner-facing half remain |
| [BUG-248](#bug-248--twenty-seven-live-specs-still-sign-in-inside-a-test-body) | Low | Live test harness | Open remainder — reduced again 2026-09-29 by four (`composer-parity-and-turn-honesty`, `fts5-mem03-bug194`, `mem04-bug194-observations`, `bug-37-39-40-41`), each re-run live and brought up to the product; converting them found [FIXED-632](FIXED_ITEMS.md#fixed-632--an-approval-card-covered-settings-save-changes) and [FIXED-633](FIXED_ITEMS.md#fixed-633--choosing-the-default-density-closed-the-panel-it-was-chosen-in). Ten sign in on their own: three must, and seven need a provider this host cannot reach ([BUG-290](#bug-290--three-of-the-four-providers-this-round-was-given-keys-for-cannot-be-reached-from-this-host)) |
| [BUG-280](#bug-280--weather-and-the-environment-clock-are-unmeasured-against-a-real-provider-and-a-real-model) | Low | Weather / live provider evidence | **Open remainder** — clock/model round trip verified in [FIXED-539](FIXED_ITEMS.md#fixed-539--a-real-turn-now-answers-from-raikers-clock-and-the-weather-half-still-cannot-be-measured-here); external Open-Meteo request still unverified due host egress |
| [BUG-287](#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider) | Medium | Design / image runtime / live evidence | Open — the same egress limit as [BUG-290](#bug-290--three-of-the-four-providers-this-round-was-given-keys-for-cannot-be-reached-from-this-host); since [FIXED-542](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all) a live round has a second thing to prove — that turning **Image generation** off refuses a generation |
| [BUG-290](#bug-290--three-of-the-four-providers-this-round-was-given-keys-for-cannot-be-reached-from-this-host) | Low | Live evidence / providers | Open — the same egress limit as [BUG-273](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more), reconfirmed 2026-09-13 with three keys |
| [BUG-312](#bug-312--one-windows-test-run-ended-in-an-interpreter-crash-dump) | Low | Tests / Windows | Open — one of 28 runs of the instance-lifecycle and internal-path tests printed a crash dump; not reproduced since |
| [BUG-313](#bug-313--an-instruction-in-the-prompt-stops-recall-finding-the-memory-it-asks-about) | Medium | Memory / recall | Open — a question carrying an instruction ("Answer in one sentence") recalls nothing, because the lexical leg needs every content word in the record |
| [BUG-314](#bug-314--a-model-chosen-by-search-is-judged-by-the-defaults-readiness-and-window) | Low | Composers / models | Open — Chat, Build and Tasks look the chosen pair up among the quick list, so a model reached by search is judged by the default's readiness and context window until the server checks it |
| [BUG-315](#bug-315--a-telegram-turns-answer-never-goes-back-over-telegram) | Medium | Messaging / Telegram | Open — a routed Telegram message runs its turn and the answer stays in Raiker; the page now says so (FIXED-711, FIXED-712), but nothing delivers it |
| [BUG-316](#bug-316--builds-working-in-names-a-project-whose-folder-build-does-not-work-in) | Medium | Build / Projects | Open — Build says *Working in <project>*, while its reads, writes and commands are relative to the workspace and the project's own folder is protected |
| [BUG-318](#bug-318--the-ollama-journey-is-proven-against-a-loopback-stand-in-not-a-real-ollama) | Low | Models / Ollama / evidence | Open — the 2026-10-04 round could not download Ollama, so detection, choice, the watch and a turn were driven against `scripts/live_ollama_standin.py` |
| [BUG-319](#bug-319--the-models-pages-connection-lifecycle-still-lives-in-the-page) | Low | Models / maintainability | Open — UX-MODEL-01 split the tabs and dialogs out; the Add tab's connection lifecycle and sign-in dialog are still the page's own state |
| [BUG-324](#bug-324--deleting-a-project-a-task-or-a-picture-is-not-journalled-so-a-restore-brings-it-back) | Low | Storage / restore | Open — FIXED-802 journals forgotten and purged memories and deleted conversations; a project, task or Design picture deleted after a backup still comes back with a restore |
| [BUG-325](#bug-325--a-routine-runs-spend-is-counted-again-from-zero-after-an-approval-pause) | Low | Tasks / cost limit | Open — a run's spend is counted per orchestrator, and a run continued after an approval starts counting again |
| [BUG-326](#bug-326--importing-the-runtime-orchestrator-first-fails-on-a-circular-import) | Low | Maintainability | Open — `import raiker.runtime.orchestrator` on its own fails on a `models.connections` ↔ `runtime.executors` cycle; every entry point imports something else first |
| [BUG-330](#bug-330--five-tests-fail-on-windows-and-pass-on-linux-ci) | Low | Tests / Windows | Open — CRLF fixtures, a `\\?\` path prefix and a receipt race; not caused by a code change |
| [BUG-331](#bug-331--setups-model-step-waits-on-every-providers-check-before-it-shows-anything) | Low | First run / Models | Open — found 2026-10-11; about five seconds of *Preparing your setup…* on a reload |
| [BUG-332](#bug-332--setup-calls-an-identity-linked-anthropic-key-connected-and-offers-models-it-cannot-list) | Low | First run / Models | Open — found 2026-10-11; the key is stored, the workspace ID is missing, and the recommendation says *choose one of its models* |
| [BUG-333](#bug-333--a-stopped-openai-compatible-stream-records-no-usage) | Low | Models / usage | Open — found 2026-10-11 closing FIXED-872; those providers report usage only when the stream ends |
| [BUG-337](#bug-337--a-standing-git-writes-decision-still-covers-local-branches-and-commits-without-a-delegation) | Low | Build / Git writes | Open — found 2026-10-12 building GH-50; pushes and GitHub writes need a delegation, local branch and commit do not yet |
| [BUG-338](#bug-338--a-delegations-repository-identity-is-checked-against-the-last-discovery-not-asked-of-github-at-each-step) | Low | Build / delegations | Open — found 2026-10-12 building GH-52; the router re-checks Raiker's records, not GitHub, before each delegated step |
| [BUG-339](#bug-339--the-issue-to-pull-request-routine-has-a-template-and-no-runner) | Low | Tasks / routines | Open — found 2026-10-12 building GH-55; scheduled routines run read-only subagents, so the template's write steps cannot run unattended |

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

## BUG-234 — The remainder: what Raiker does not use of the MCP revision it now speaks

**Severity: Low (was Medium). Area: MCP / interoperability.
Status: Open — reduced 2026-08-23, twice on 2026-09-04 (transport, result
shapes), and twice again on 2026-09-05 (server-initiated requests, event-stream
framing).**

**Reduced again 2026-09-05, and the first of the two was a defect rather than a
gap.** Reading this entry's *streaming* bullet led to the code that reads a
stream, and two things there were wrong rather than merely unbuilt:

* **[FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own)
  — a server that asked Raiker anything could not be connected at all.** Both
  transports filed every message carrying an `id` into the response map, and a
  server-initiated request carries an id from the *server's* numbering space.
  One numbered 1 — the ordinary choice — landed on top of the `initialize`
  answer, and the connection failed as `mcp_initialize_failed`: Raiker's own
  request named, and the server blamed for not answering it. Reproduced on
  unmodified `main`. Direction is read from `method` now, `ping` is answered,
  and everything else is refused with `-32601` and **named on the card** rather
  than met with silence.
* **[FIXED-412](FIXED_ITEMS.md#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped)
  — an event stream was read one line at a time.** One event's payload may span
  several `data:` lines, which is what a server that pretty-prints its JSON-RPC
  produces; each line was parsed alone, failed, and was dropped. `id:` was
  dropped too, so the single re-handshake after a dropped session restarted from
  nothing. There is a real event-stream parser now, and `Last-Event-ID` on the
  one request that resumes.

Neither closes the *streaming* bullet below, and neither pretends to: Raiker
still reads a bounded response whole and holds no connection between turns, and
the card still says so.

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
  delivery. A server that answers this way is **named as such on its card**
  rather than silently degraded. **Two of the four things this bullet listed are
  now done** — the framing is read correctly and resumably
  ([FIXED-412](FIXED_ITEMS.md#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped))
  and server-initiated messages are answered rather than mis-filed
  ([FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own)).
  Incremental delivery and a connection that outlives the turn are what is left,
  and both are a different object from a bounded governed read: a stream held
  open between turns is a standing inbound channel, and it needs its own answer
  to what may arrive on it while nobody is looking.
* **Remote OAuth.** The authorisation flow the current revision defines. Raiker's
  remote transport takes an owner token from an env var named by `auth_ref`.
* **MCP Apps ([SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp)).**
  Sandboxed server-contributed UI, and the better answer to
  [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract).
  Carried as [ADD-24](TO_BE_ADDED.md).
* ~~**Structured tool output and resource links.**~~ **Done 2026-09-04 —
  [FIXED-387](FIXED_ITEMS.md#fixed-387--a-tool-result-had-one-shape-and-the-revision-defines-six).**
  Raiker read one of the six shapes a result may carry: the `text` of every
  block. All five block types and `structuredContent` now reach the model, with
  two rules that are governance rather than formatting — a `resource_link` is
  *named and never followed*, because a tool result must not cause a read the
  owner's policy never saw; and an inline image is named by media type and size
  rather than decoded into the turn.
* **Elicitation.** Its blocker is gone — the mid-turn question surface shipped as
  [FIXED-308](FIXED_ITEMS.md#fixed-308--raiker-could-ask-permission-and-could-not-ask-what-you-meant)
  — and it is still not built. What it needs is an answer to *whose* question a
  server's elicitation is: `ask_owner_question` carries no authority because
  Raiker's own runtime raised it, and a question a connected server composes is a
  different object. **The wire half is now in place and deliberately stops
  short**: since
  [FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own)
  an `elicitation/create` reaches Raiker as the request it is, is answered
  `-32601`, and is named on the server's card — so an owner can see a server
  asking and see that it was refused. Wiring it to a person is the part that
  still needs the answer above, and `sampling/createMessage` needs the same one
  about a turn the owner's policy never reviewed.
* **`server/discover`.** Not implemented, and not urgent: every server an owner
  can add today is added by the owner naming it.

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

## BUG-248 — Twenty-seven live specs still sign in inside a test body

**Severity: Low. Area: live test harness. Status: Open remainder — raised
2026-08-30 while closing [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in),
reduced from twenty-seven to twenty the same day
([FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite)),
to **twelve** on 2026-09-04, to eleven on 2026-09-21 and to **nine** on
2026-09-28.**

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
`review-provider-matrix` each need OpenRouter, OpenAI, Gemini or Ollama, which
this host cannot reach — so they cannot be re-run here, and the rule below says
they are not converted blind.

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
([the second 2026-09-28 round](LIVE_TEST_ROUNDS.md#2026-09-28-second--code-says-where-it-runs-and-three-review-documents-close)).

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
5174; they are recorded in FIXED-328. **Nine are left** after the 2026-09-28 pass, and the reason they
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

## BUG-280 — Weather and the environment clock are unmeasured against a real provider and a real model

**Severity: Low. Area: runtime / environment context, weather. Raised while
implementing ENV-01…05 and WEATHER-01…03.**

**Half of this closed 2026-09-15 as
[FIXED-539](FIXED_ITEMS.md#fixed-539--a-real-turn-now-answers-from-raikers-clock-and-the-weather-half-still-cannot-be-measured-here).**
The clock half was measurable the moment a host had a working key: a real
Anthropic turn names the runtime's date and day, and follows the owner's zone
when it changes. The spec reads the expectation from `/api/environment` rather
than hardcoding a date, so it measures agreement between the runtime and the
model rather than agreement with whatever day it was written on.

**The weather half is still open, and still for the same reason.** Every attempt
to reach `api.open-meteo.com` from this host is cut by the environment's egress
policy — verified again on 2026-09-15, `curl` returns no status through the
proxy's tunnel — so the tool answers `weather_provider_unavailable`, which is the
correct typed answer to an unreachable provider and is not evidence that a
reachable one is read correctly. Closing it needs a host with egress, not a
change to Raiker.

**Observed.** The 2026-09-07 round proved the whole of the environment and
weather contract against the runtime: the bundle a turn is given, the event it
records, the precedence, the DST behaviour, the stale-refresh note, and every
governed refusal. Two halves of it were not measured, and neither is a code gap.

*No model reasoned from the bundle.* The round's key is identity-linked, as the
previous six were, and this host has no local runtime, so no provider on it can
complete a turn. The bundle is asserted against the messages the orchestrator
builds — which is the right place, since it is derived before any provider is
called — but "the model answered `tomorrow` correctly" is a claim only a real
turn can support.

*No weather request left the machine.* The provider path is asserted against a
stand-in that answers as Open-Meteo does, and every governed refusal is asserted
against the real gate, decision mode and blocklist. What is unmeasured is the
real HTTP round trip. `api.open-meteo.com` resolves from this host and every
attempt to reach it — with or without the environment's proxy — is refused with
`403` by that environment's own egress policy, so the tool returns
`weather_provider_unavailable`. That is the correct typed answer to an
unreachable provider; it is not evidence that a reachable one is read correctly.

**Why it was left.** Both need something the round did not have — a working
provider credential and outbound egress — rather than something Raiker is
missing. Recording it here is what stops the plan's `Done` reading as a claim
about evidence that was never taken.

**Proposed check.** On a host with egress and a working model: ask *"what day is
it, and what is the weather here?"* in Chat, and confirm the answer names today's
real date in the owner's zone and cites the weather provider with its observation
time. Then set the timezone to another continent and ask *"what time is it?"*
again.

**Interface outcome that has to be true before this closes.** A real turn
answers a relative-time question from the runtime's clock rather than from
training knowledge, and a real weather answer names its provider and how old the
reading is.

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

**Observed.** The lineage runtime and the canvas were built and verified, but
no picture has been generated or edited through a real provider from this host.
The egress policy answers 403 to `CONNECT api.openai.com`, and a live generate
run through the product's own composer refuses with `fetch_failed:URLError`,
which is the environment rather than the code.

**What *was* exercised against the running server.** The governed route, the
owner-scoped subject resolution, the count bound and its zero case, lineage
recorded on refusals, `project_id` carried from the composer through to the
stored row, and the canvas composing real rows read back through `GET /api/images`.
The multipart wire format is proven against a real socket — a live HTTP server
parses the body with Python's own MIME parser and the image comes back byte for
byte (`tests/test_multipart_egress.py`).

**What is not known.** What OpenAI's `/v1/images/edits` and Gemini's inline-data
edit actually return: the response shape on success, how a provider refusal reads
when the *source* image is the thing refused rather than the prompt, and whether
a request for four pictures comes back as four images or as one with a count the
decoder has to split. `_decode_images` handles the shapes the providers document;
none of them has been seen.

**Proposed fix.** One live round against a reachable image provider. Gemini is
the cheaper route — `generativelanguage.googleapis.com` is reachable from this
host, so a Gemini API key alone would close it — covering generate, edit,
variations and a provider refusal of a source image, with the lineage read back
through `GET /api/images`.

**Interface outcome that has to be true before this closes.** A picture generated
through a real provider, edited into a second version, and both shown on the
canvas as the chain they are — with the captures to prove it.

---

## BUG-290 — Three of the four providers this round was given keys for cannot be reached from this host

**Severity: Low. Area: Live evidence / providers. Raised 2026-09-13. The same
limit as [BUG-273](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more),
reconfirmed with three fresh keys.**

**Observed.** The 2026-09-13 release-readiness round was given working keys for
Anthropic, OpenAI and OpenRouter, and asked to use a local Ollama cloud model as
a fourth. Only Anthropic answered:

| Provider | Outcome on this host |
|---|---|
| Anthropic | **Real round trip.** Connected, Haiku 4.5 pinned, readiness confirmed, and a real turn answered — the evidence behind [FIXED-501](FIXED_ITEMS.md#fixed-501--raiker-knew-its-owners-authorisation-key-and-not-their-name). |
| OpenAI | `connect_rejected` — the egress proxy denies `CONNECT api.openai.com`. |
| OpenRouter | `connect_rejected` — the egress proxy denies `CONNECT openrouter.ai`. |
| Ollama (cloud model) | No Ollama on this machine, and no way to install one from here. |

**What was proven anyway.** Raiker's half, for all three. Each key was entered
through the product's own dialog, each connection was stored, and each readiness
check reported its own outcome as a sentence rather than as a bare status or a
wrong diagnosis — which is [FIXED-388](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network)'s
rule holding under three more keys. `web/e2e/owner-identity-live.spec.ts` runs all
three and skips with the reason when a key is absent.

**What is still unverified.** A real turn through OpenAI, OpenRouter or a local
Ollama cloud model, and therefore the identity block, the citation ledger and the
tool loop against any provider but Anthropic.

**Interface outcome that has to be true before this closes.** The same question
the owner reported — *who is the owner of this workspace* — asked and answered
through each of the four providers, with a capture of each answer.

---

## BUG-312 — One Windows test run ended in an interpreter crash dump

**Severity: Low. Area: Tests / Windows. Status: Open — raised 2026-10-01.**

**Observed.** One of 28 consecutive runs of `tests/test_instance_runtime_lifecycle.py`
with `tests/test_windows_internal_paths.py` on the Windows development host
ended with a fault-handler dump (`File "<frozen runpy>", line 198 in
_run_module_as_main`) instead of the pass line. The dump was cut off before its
first frame, and 22 further runs, each checked for the dump, were clean.

**Likely cause, not confirmed.** A native SQLCipher or sandbox-runner handle
torn down while a test thread is still exiting; both files start background
threads.

**Proposed fix.** Run the pair under `-X faulthandler` in a loop with the full
output kept, and fix what the first complete dump names.

**Required user-interface outcome.** None; test harness only unless the dump
names product code.

## BUG-313 — An instruction in the prompt stops recall finding the memory it asks about

**Severity: Medium. Area: Memory / recall. Status: Open — raised 2026-10-02, found by this run's live round.**

**Observed.** With the approved memory *My favourite tea is Assam with a splash
of oat milk.*, a real Anthropic turn asked *What is my favourite tea? Answer in
one sentence.* was given no memory — no **Remembered** strip, and the answer
said it had no information. *What is my favourite tea?* recalls it.

**Root cause.** `SQLiteStore._match_terms` keeps every non-stopword of three or
more letters and `_match_expression` joins them as an implicit **AND**, so
`favourite tea answer one sentence` requires *answer*, *one* and *sentence* in
the record. BUG-243 dropped function words for the same reason; instruction
words about the *shape of the answer* are the same failure from a different
vocabulary. On a default install the vector leg is the lexical hashing
fallback, which does not rescue it.

**Proposed fix (needs the owner's decision on ranking).** When the full AND
finds nothing, retry with the longest prefix-free subsets that do match, or run
an OR query ranked by `bm25()` and admit a row only when it matches a stated
share of the content terms. Either changes which memories reach a model's
context, which is why it is not done in passing; the acceptance test is the
sentence above recalling the tea memory while *the* alone, or an unrelated
two-word overlap, still recalls nothing.

**Required user-interface outcome.** None new: the **Remembered** strip and the
memory's *Turns it was given to* (FIXED-691) show it working once fixed.

---

## BUG-314 — A model chosen by search is judged by the default's readiness and window

**Severity: Low. Area: Composers / models. Status: Open — raised 2026-10-03, found
while fixing FIXED-723.**

**Observed.** Chat, Build and Tasks each derive `activeProfile` as the quick-list
profile whose id *and* model match the bound pair, falling back to the global
default. A model reached through **Search all models** is not in that list, so
the composer's readiness line, *Send* gating and context-window meter describe
the default while the turn names the searched model. The server's readiness gate
still judges the pair actually sent, so no turn runs on an unchecked model; what
is wrong is what the composer says before Send.

**Proposed fix.** Derive the active pair the way the picker now does (provider
from the profile, model from the binding) in one shared helper, and read its
readiness by `(profile_id, model)`; a pair with no observation reads as *checked
when you send* rather than as the default's state.

**Required user-interface outcome.** After choosing a searched model, the
context line and readiness strip name that model, and Send's state is that
model's.

---

## BUG-315 — A Telegram turn's answer never goes back over Telegram

**Severity: Medium. Area: Messaging / Telegram. Status: Open — raised 2026-10-03.**

**Observed.** A Telegram message on a *New turn* or *Side question* route runs a
governed turn, and the answer is returned in the HTTP response to Telegram's
webhook call, which Telegram ignores. The owner reads the answer only in Raiker.
Since FIXED-711 and FIXED-712 the page says so — *Replies: kept in Raiker* and
*Processed — no reply sent over the channel* — rather than implying a reply.

**Why it is not fixed in passing.** Delivering it is a new outbound path:
`external_channel_runtime` has one entry path today (the owner's control plane,
`entry_paths.py`), and a reply sent on the router's initiative needs its own
entry, its own receipt stage (*reply queued → delivered*), the DEC-14 retry
ledger with deduplication, and a decision on whether a reply waits for the
owner's approval mode.

**Required user-interface outcome.** A routed Telegram message's receipt reaches
*delivered*, and *What this route does* says replies go back to the chat.

---

## BUG-316 — Build's "Working in" names a project whose folder Build does not work in

**Severity: Medium. Area: Build / Projects. Status: Open — raised 2026-10-03 by
the live round.**

**Observed.** The first closed-loop attempt (UX-BUILD-04) put its module and
test in the new project's own folder and told the model to run them "in this
project". The command ran at the workspace root and could not find the file. A
managed project's root is `.raiker/projects/<slug>`, which is a protected
workspace path, and a managed project's path authority is the workspace itself
(`authority_for_project`): Build reads, writes and runs commands relative to the
workspace whichever project is chosen. Meanwhile the composer says **Working in
*project***, and the boundary inspector names the project first.

**Why it is not fixed in passing.** Either the wording changes — the project is
where the conversation is *filed*, and the repository (or the workspace) is
where the work happens — or a managed project gains a working folder commands
start in, with the authority and checkpoint rules that implies. That is DEC-04
and DEC-06 step 1's server-issued boundary, and it is the owner's choice which.

**Required user-interface outcome.** What the composer and the boundary say a
turn works in is the folder its reads, writes and commands are relative to.

---

## BUG-318 — The Ollama journey is proven against a loopback stand-in, not a real Ollama

**Severity: Low. Area: Models / Ollama / evidence. Status: Open — raised
2026-10-04 by the live round.**

**Observed.** [FIXED-737](FIXED_ITEMS.md#fixed-737--an-ollama-model-nobody-chose-was-shipped-as-everyones-default)
to [FIXED-739](FIXED_ITEMS.md#fixed-739--a-chosen-ollama-model-was-ready-until-somebody-stopped-looking)
were driven live end to end — detection with no binary on PATH, the choice in
setup, Ready at once, a Chat turn answered by the chosen model, the service
stopped and started under an open page — but this host's egress refuses both
`ollama.com` and GitHub releases, so the service on 11434 was
`scripts/live_ollama_standin.py`, which serves Ollama's catalogue and
OpenAI-compatible paths and answers with a fixed sentence. The probe, the
readiness check and the turn all speak the real protocol; the answers do not
come from a model.

**Required evidence before this closes.** The same round
(`round-2026-10-04-ollama-and-readiness-live.spec.ts`) run on a host with the
Ollama desktop app and at least two pulled models — including one the app
serves while `ollama` is not on PATH — with a real answer to the Chat turn.

---

## BUG-319 — The Models page's connection lifecycle still lives in the page

**Severity: Low (maintainability). Area: Models. Status: Open — the remainder
of UX-MODEL-01, recorded 2026-10-04.**

**Observed.** [FIXED-744](FIXED_ITEMS.md#fixed-744--the-models-page-owned-every-state-machine-on-it)
split `ModelsView.svelte` by tab and dialog. UX-MODEL-01 also asks for
connection lifecycle and global selection in shared stores or services; the
Add tab's sign-in dialog, saving and disconnecting a credential, the provider
test, and the global selection are still the page's own state, about 2,500
lines with the provider sections they drive.

**Proposed fix.** A `ProviderConnections` controller (sign-in, save, test,
disconnect, workspace refusal) shared by Models and first-run setup, which
today implements the same lifecycle a second time in `ProviderMatrix.svelte`.
Behaviour unchanged; the two surfaces' tests are the characterization suite.

## BUG-324 — Deleting a project, a task or a picture is not journalled, so a restore brings it back

**Severity: Low. Area: Storage / restore. Status: Open — recorded 2026-10-05 by
the (fifth) round's work on FIXED-802.**

**Observed.** [FIXED-802](FIXED_ITEMS.md#fixed-802--a-restore-brought-back-what-had-been-deleted-since-the-backup)
journals three kinds of deletion — a forgotten memory, a purged memory and a
deleted conversation — and replays them into a restore. A project, a task, an
attachment or a Design picture deleted after the backup was taken is not
journalled, so restoring that backup brings it back.

**Proposed fix.** Journal each owner-initiated permanent deletion through the
store method that performs it (kind, id, owner, time — no content), and replay
it with journaling off, as FIXED-802 does. A project deletion that removed
managed files cannot recreate them from a database backup either way; the
replay only has to keep the row deleted.

---

## BUG-325 — A routine run's spend is counted again from zero after an approval pause

**Severity: Low. Area: Tasks / cost limit. Status: Open — recorded 2026-10-05
with FIXED-804.**

**Observed.** [FIXED-804](FIXED_ITEMS.md#fixed-804--one-run-of-a-routine-had-no-cost-limit-of-its-own)
meters a run's spend on the orchestrator that runs the turn. A routine run that
parks on an approval and is continued is resumed on a new orchestrator: the
limit rides with the turn, the spend before the pause does not, so a run that
pauses can spend up to its limit again after each approval.

**Proposed fix.** Seed the meter on resume from the usage ledger's rows for the
run's thread since the run started (FIXED-810 made those rows include cached
tokens), so the boundary check sees the whole run.

---

## BUG-326 — Importing the runtime orchestrator first fails on a circular import

**Severity: Low. Area: Maintainability. Status: Open — found 2026-10-05 while
building FIXED-804; pre-existing.**

**Observed.** `python -c "import raiker.runtime.orchestrator"` fails:
`raiker.models.connections` imports `runtime.connector_ecosystem`, which imports
`runtime.executors`, whose image executor imports
`models.connections.get_model_connection` while that module is half-loaded.
Every real entry point (the app, the CLI, the tests) happens to import
something that breaks the cycle first, so nothing ships broken; a new script or
test that imports the orchestrator first does.

**Proposed fix.** Move the image executor's `get_model_connection` import into
the function that uses it, and add an import-each-module-alone test.

## BUG-330 — Five tests fail on Windows and pass on Linux CI

**Severity: Low. Area: Tests / Windows. Status: Open — found 2026-10-10 running
the full suite on Windows 11; the same five fail at `38c9da5` without this
run's change.**

**Observed.**

- `tests/test_mcp_stdio_bounds.py` (2): the stand-in MCP server writes `
`
  on Windows and the tests compare against `
`.
- `tests/test_project_lifecycle.py::TestDeletion::test_preview_counts_what_the_delete_removes`:
  the fixture's `write_text("hello
")` writes seven bytes on Windows, so the
  folder is 17 bytes, not 16.
- `tests/test_workspace_backups.py::test_the_routes_need_an_owner_and_say_what_they_did`:
  the restore path comes back with the `\\?\` long-path prefix and Windows
  separators, and the assertion expects `/`.
- `tests/test_background_execution.py::test_a_lapsed_lease_is_reclaimed_with_an_honest_receipt_not_left_running`:
  the reclaim writes a receipt that is already final (`command_receipt_immutable`).

**Effect.** The suite is not green on the platform the desktop build ships for;
CI runs Linux only, so nothing flags it. The first three are fixture
assumptions; the fourth needs a look, because a receipt race is product
behaviour.

**2026-10-11.** The full suite on Windows again failed the first three
(four tests); the lease-reclaim test passed this time, and
`tests/test_mcp_remote_transport_trust.py::test_the_real_transport_does_not_follow_a_redirect_itself`
failed once under full-suite load (`mcp_remote_unreachable`) and passed alone —
a timing dependency worth the same look.

**Proposed fix.** Write fixtures with `newline="
"` / bytes, compare paths
through `Path`, and trace the lease reclaim's double write on Windows. Consider
a Windows job for the Python suite.

## BUG-331 — Setup's model step waits on every provider's check before it shows anything

**Severity: Low. Area: First run / Models. Status: Open — found 2026-10-11 in
the live round.**

**Observed.** Reloading `#/model-setup` with one hosted provider connected and
twelve Ollama models served showed *Preparing your setup…* for about five
seconds before the step appeared. The view loads `/api/setup` and `/api/models`
together and renders nothing until both answer; the models read is the slow
one.

**Effect.** A blank first-run screen for seconds reads as a hang. Nothing is
lost and the step is correct once it appears.

**Proposed fix.** Render the step from `/api/setup` at once and fill the
provider rows as `/api/models` answers, with each row's own loading state;
measure where `/api/models` spends the time (local runtime probes, catalogue
reads) before deciding whether any of it belongs in the background.

## BUG-332 — Setup calls an identity-linked Anthropic key connected and offers models it cannot list

**Severity: Low. Area: First run / Models. Status: Open — found 2026-10-11 in
the live round.**

**Observed.** With the identity-linked `sk-ant-usr-…` key entered through
setup's Anthropic field, the model step's recommendation read *Anthropic is
connected — Choose one of its models as your default*. **Choose a model** opened
the Anthropic row, which correctly said the key needs its workspace ID before
it can act; no model could be chosen. The row explains the key correctly, as
the 2026-10-10 round also found; only the recommendation disagrees.

**Effect.** The first thing the step recommends cannot be done. The owner has
to read the row below to learn why.

**Proposed fix.** Derive the recommendation from the connection's readiness,
not from a stored key: a connection whose last check is
`anthropic_workspace_required` recommends *Add the workspace ID* with the
field focused, and offers another provider beside it.

**Owner input needed for the live check.** The workspace ID for the supplied
key, so a round can prove an Anthropic turn end to end.

## BUG-333 — A stopped OpenAI-compatible stream records no usage

**Severity: Low. Area: Models / usage. Status: Open — found 2026-10-11 closing
FIXED-872.**

**Observed.** FIXED-872 records what a provider had counted when the owner
stops a streamed turn. Anthropic says the input cost as the stream opens.
OpenAI, OpenRouter and Ollama report usage only in the final chunk
(`stream_options.include_usage`), so a turn stopped before it is still recorded
as nothing.

**Effect.** Every spending limit under-counts a stopped turn on those providers
by the prompt it was sent and the part of the answer it produced.

**Proposed fix.** On a stopped stream with no provider count, record the input
as an *estimate* from the request (marked as such in the ledger so it is never
read as settled), and reconcile it if the provider's usage endpoint later
reports the call. Requires an `estimated` column and a decision on whether
estimated spend counts against the owner-wide limit (DEC-24 step 2 says to
separate estimated from settled usage).

## BUG-337 — A standing *Git writes* decision still covers local branches and commits without a delegation

**Severity: Low. Area: Build / Git writes. Status: Open — found 2026-10-12
building ADD-27 GH-50.**

**Observed.** Since GH-50 a push and a GitHub write run without a per-step
approval only under a repository delegation that covers them
([FIXED-886](FIXED_ITEMS.md#fixed-886--a-standing-grant-or-allow-mode-alone-let-an-agent-push-or-write-to-github)). Creating a local branch and
committing on it (`git_write_execution`) are the specification's other two
delegable operations (§8.2), and they still follow the capability's decision
mode and any standing grant alone.

**Effect.** Small: neither leaves the machine, and the push that would carry
them off still needs a delegation or an approval. But an owner reading
*Delegations* could expect a branch pattern to limit where the agent commits,
and it does not yet.

**Proposed fix.** Give `GitWriteExecutor` a `repository_target` (the selected
repository's origin, the branch named or current) so the router applies the
same rule; a repository with no GitHub remote keeps today's behaviour, since
there is no repository to delegate.

## BUG-338 — A delegation's repository identity is checked against the last discovery, not asked of GitHub at each step

**Severity: Low. Area: Build / delegations. Status: Open — found 2026-10-12
building ADD-27 GH-52.**

**Observed.** `DelegationService.revalidate` re-checks the delegation, the
credential, the account, the installation and the repository id before every
delegated step. The repository id and installation are compared with what
Raiker last discovered (`github_repositories`, `github_installations`). It asks
GitHub (`GET /repos/{owner}/{name}`) only when the caller passes a client, and
the router does not.

**Effect.** A repository transferred or deleted and re-created since the last
*Refresh from GitHub* is not seen until the next refresh — the push itself still
goes only to the bound remote, and the installation token is still narrowed to
the recorded id, so authority is not redirected; the step just is not refused
as early as §9 asks.

**Proposed fix.** Pass the broker's client to `revalidate` from the router for
pushes and pull requests, with a short per-delegation cache so a burst of steps
asks once; treat *could not reach GitHub* as *blocked — needs owner*.

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

## Decision statements added 2026-10-05

**Basis:** repository snapshot `2898b247c9e02d537c6f61e866ed670578e49b42`.
These statements supply missing implementation direction. **Recommended** means
a proposed choice, not an owner approval or a verified fix. The original BUG
entries retain their status and acceptance evidence.

### BUG-313 — Bounded recall fallback
**Decision — recommended; ranking choice pending owner acceptance.** Keep the
strict lexical query first. On no match, prefer a bounded OR/BM25 candidate
query with a minimum content-term coverage rule over enumerating progressively
smaller subsets. Apply existing owner, project, active-revision, suppression and
retrieval-budget checks before any candidate reaches model context. Do not use
an unrestricted OR match or silently add a model call to rewrite every query.

**Reason and alternatives.** All-term matching makes answer-format instructions
part of the factual question. A ranked fallback can recover relevant facts;
subset enumeration can grow combinatorially and makes query cost harder to
bound. A permissive OR alone trades missing memories for unrelated disclosure.
The exact coverage threshold remains a measured choice, not an invented
production constant.

**Code review.** `MemoryStore.search_approved_memory` already ranks FTS5
matches with `bm25()` and uses recency on FTS4; this recommendation changes
candidate matching, not the existence of ranking. Preserve the FTS4 fallback
and disclose its weaker ordering, or explicitly decide a supported-engine
change before requiring BM25. `retrieve_hybrid_memory` merges lexical, vector
and graph evidence and re-reads active approved records: changing lexical
matching must not bypass those final eligibility checks.
References: [memory store](../../raiker/storage/stores/memory.py),
[search-engine posture](../../raiker/storage/sqlite.py).

**Acceptance and consequence.** Compare strict matching and the proposed
fallback on the tea example, instruction variants, unrelated two-word overlaps,
stopword-only queries, cross-owner/project records, forgotten records and large
corpora. Record recall quality, false positives and query cost before choosing
the threshold. Preserve provenance in the Remembered strip. No data migration
is intended; an index/schema change would require its own migration decision.
References: [BUG-313](#bug-313--an-instruction-in-the-prompt-stops-recall-finding-the-memory-it-asks-about),
[retrieval service](../../raiker/memory/retrieval.py),
[existing retrieval hardening tests](../../tests/test_memory_retrieval_hardening.py).

### BUG-315 — Reply delivery is a separate governed effect
**Decision — recommended; outbound approval policy pending owner acceptance.**
Prepare a reply to the authenticated, paired conversation, then govern delivery
as its own outbound action. Receiving a message, running a turn or approving a
tool in that turn does not approve sending its answer. Use the effective
capability/decision mode; a narrowly scoped standing grant may permit delivery
only if the owner explicitly created it. Add the automated delivery entry path
before enabling the sender.

**Reason and alternatives.** The webhook HTTP response is not a delivered
Telegram message. Unconditional auto-replies would introduce an authority and
data-disclosure path that the present entry inventory does not describe.
Forcing an additional prompt even under an applicable owner grant would also
misrepresent the existing decision-mode contract.

**Code review.** `TelegramAdapter.outbound` already constructs a token-bound
`sendMessage` request. The missing part is automatic reply orchestration:
`_route_inbound_message` returns `response.message`, while `_settle_receipt`
deliberately withholds delivered status for Telegram. Reuse the adapter through
governed execution; do not add a direct HTTP send inside the inbound route.
References: [channel adapters](../../raiker/channels/adapters.py),
[inbound router and receipts](../../raiker/api/routes_channels.py).

**Acceptance and consequence.** Bind the intent to owner, channel, recipient,
source event and payload; distinguish queued, awaiting approval, delivered,
failed and outcome-unknown. Exercise revoked grants, duplicate events,
restart-before/after-send, provider failure and bot-loop protection. Retry
automatically only when reconciliation or provider deduplication makes it safe.
Durable outbox/receipt changes need versioned schema and recovery fixtures.
References: [BUG-315](#bug-315--a-telegram-turns-answer-never-goes-back-over-telegram),
[DEC-14](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#dec-14--make-messaging-a-guided-durable-channel-service),
[entry-path registry](../../raiker/runtime/authority/entry_paths.py).

### BUG-316 — Separate filing from execution location
**Decision — recommended; working-folder policy pending owner acceptance.**
For the first corrective slice, label the Project as where the conversation is
filed and show the actual server-resolved repository/workspace as the execution
location. Do not move commands into a managed Project directory merely to make
the existing wording true.

**Reason and alternatives.** A wording/projection correction resolves the false
promise without changing filesystem authority. Making every managed Project a
working directory changes protected-path handling, command cwd, checkpoints and
existing task behavior; that is a separate architecture change. FIXED-740 made
the boundary server-issued but does not itself settle BUG-316's semantics.

**Code review.** `authority_for_project` returns workspace-only authority for
a managed Project and adds a granted root for an attached Project.
`PathAuthority._resolve` resolves relative paths against `workspace_root`;
an additional allowed root does not automatically become command cwd.
References: [Project root resolver](../../raiker/control/project_roots.py),
[boundary contract tests](../../tests/test_build_boundary.py).

**Acceptance and consequence.** For a managed Project and an attached repository,
compare the displayed root with reads, writes and command cwd after selection,
reload and a slow/out-of-order boundary response. An unavailable boundary must
say unknown/unavailable. No storage migration is intended for this slice; a
future Project-root migration must define compatibility and rollback.
References: [BUG-316](#bug-316--builds-working-in-names-a-project-whose-folder-build-does-not-work-in),
[DEC-04](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#dec-04--make-project-continuity-explicit-and-typed),
[FIXED-740](FIXED_ITEMS.md#fixed-740--builds-boundary-line-was-the-browsers-opinion-of-where-a-turn-would-run),
[path authority](../../raiker/tools/path_authority.py),
[turn-boundary tests](../../tests/test_turn_path_authority.py).

### BUG-226 and BUG-228 — Do not create alternate execution contracts
**Decision — retained deferral for hooks; recommended convergence for UI.**
Keep `mcp_tool` and `agent` hook types unsupported until each has bounded,
non-escalating authority, its own resource budget, recursion limits and
execution-time revalidation. For contributed UI, follow ADD-24's one MCP Apps
contract instead of implementing a second `panels.json` renderer. BUG-228 may
eventually close as superseded only when the replacement scope is accepted and
its obsolete promises are reconciled; it is not implemented by this note.

**Reason and acceptance.** A hook must not call a tool the originating turn
cannot call. Two contributed-UI models duplicate permission, isolation and
accessibility work. Test denial/revocation and recursion for hooks, and
per-app grants, message validation, iframe isolation and keyboard access for UI.
A sandboxed iframe still runs third-party code; the product must describe its
boundary accurately rather than claim that no browser code runs.
References: [hook type contract](../../raiker/hooks/contracts.py),
[ADD-24](TO_BE_ADDED.md#add-24--mcp-apps-sandboxed-server-contributed-interactive-ui),
[DEC-23](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#135-dec-23--govern-extension-learning-lifecycle-and-contributed-ui).

## Competitive evidence attached to existing defects — 2026-10-05

**Decision.** Link competitive consequences to existing defects rather than create duplicate BUGs. [COMPETITIVE_READINESS_DEMONSTRATION_AND_EVIDENCE.md](COMPETITIVE_READINESS_DEMONSTRATION_AND_EVIDENCE.md) supplies the shared thresholds and evidence record. The rows below add acceptance detail; they do not change the current open/closed status above.

| Existing item | What Raiker must demonstrate | Evidence required |
|---|---|---|
| BUG-313 | Relevant authorised memory survives instruction-heavy phrasing without broadening recall authority | CR-04: original reproduction plus paraphrases, distractors, another owner/project, expired/deleted records; retrieval IDs, supplied context, labelled relevance scores and a real post-restart answer |
| BUG-315 | An inbound Telegram request produces an authorised reply to the correct destination or a truthful delivery failure | CR-03: real test-account round trip, exact outbound approval/grant, destination message ID/readback, denied send, timeout, lost ACK and restart behavior; a processed receipt cannot stand in for delivery |
| BUG-316 | Build's displayed project and effective filesystem/command root have explicit, consistent semantics | CR-08/10: attached and managed project fixtures, actual cwd/resolved paths, confined read/write/command outcomes and UI explanation; no silent widening of granted roots |
| BUG-194 | Claimed execution modes have observable lifecycle, stop and recovery behavior | CR-01/07/11: actual foreground/interactive/background/remote modes where supported, process and durable-state evidence, cancellation and reattachment after restart; label unsupported modes |
| BUG-318 | Supported Ollama setup and tool use work against a real service/model | CR-02: install/version, served model, readiness, tool-using task, restart/reconnect and inference location; existing stand-in results retain only protocol scope |
| BUG-226 / BUG-228 / BUG-234 | Each claimed hook/plugin/MCP capability has a reachable governed contract | CR-06: independent fixture, install/discover/use/update/revoke/uninstall, unsupported-mode behavior and contribution-to-effect trace |

**Closure rule.** Add a reproducible failing case, implementation reference and executed regression result, plus live evidence where the claim concerns a live user/service path. Reuse earlier valid evidence by link and revision; do not relabel a closed defect open merely because comparative testing is missing. Unrun benchmark work is an evidence gap unless a product failure is reproduced.

## Personal-agent direction — 2026-10-07

The owner accepted the [personal-agent architecture](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
inspired by Meta Muse, Claude.ai, OpenClaw and Hermes Agent. New durable goals,
context, proactivity, outcome verification and reviewed learning work is owned
by [PAA-01–PAA-11](PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md). Existing items in
this ledger keep their status, dependencies and evidence; accepting the target
does not close a defect or mark an ADD shipped. Browser ADD-23, off-machine
ADD-11, memory ADD-25 and self-improvement ADD-05/06 retain their own boundaries.

Personal-agent release claims require the relevant PA-S scenarios and existing
CR evidence gates. Preserve capability defaults, quiet-hours DEC-21a, accepted
Git OAuth scope, model choice and coding quality. New observations go to the
proper defect/evidence ledger; do not duplicate the PAA backlog here.
