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

docs/TO_BE_FIXED.md — are defects. Defects found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Fixed entries remain as evidence; every deferred item
found by the FIXED-01 through FIXED-48 audit is now an explicit BUG with a
required user-interface outcome, so closing backend work cannot leave an
invisible or misleading product surface.

docs/GAP_BUILD_CHAT.md — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

| ID | GAP | Tier | Status |
|---|---|---|---|
| [B1](#b1--an-approved-action-must-actually-execute) | BUILD | TIER 0 | Done |
| [B2](#b2--the-turn-resumes-after-an-approval) | BUILD | TIER 0 | Done |
| [B3](#b3--real-patch-application) | BUILD | TIER 0 | Done |
| [B4](#b4--parallel-tool-calls-are-silently-dropped) | BUILD | TIER 1 | Done |
| [B5](#b5--testcommand-feedback-channel) | BUILD | TIER 1 | Done |
| [B6](#b6--no-taskplan-state-across-the-loop) | BUILD | TIER 1 | Done |
| [B7](#b7--no-subagents-at-the-models-disposal) | BUILD | TIER 1 | Done |
| [B8](#b8--mcp-tools-are-unreachable) | BUILD | TIER 1 | Done |
| [B9](#b9--no-repository-index) | BUILD | TIER 2 | Done |
| [B10](#b10--no-language-intelligence) | BUILD | TIER 2 | Open |
| [B11](#b11--no-git-write-path) | BUILD | TIER 2 | Done |
| [B12](#b12--no-web-access) | BUILD | TIER 2 | Done |
| [B13](#b13--no-file-tree-and-no-editor) | BUILD | TIER 3 | Open |
| [B14](#b14--no-diff-review-surface-in-build) | BUILD | TIER 3 | Partial |
| [B15](#b15--terminaloutput-pane) | BUILD | TIER 3 | Partial |
| [B16](#b16--tool-activity-is-buried) | BUILD | TIER 3 | Done |
| [B17](#b17--no-way-to-stop-or-steer-a-running-turn) | BUILD | TIER 3 | Done |
| [B18](#b18--no-checkpoint-or-rewind-control-where-the-work-happens) | BUILD | TIER 3 | Done |
| [B19](#b19--composer-ergonomics) | BUILD | TIER 3 | Done |
| [B20](#b20--sandboxed-execution-environment) | BUILD | TIER 3 | Partial |
| [C1](#c1--first-class-document-output) | CHAT | TIER 0 | Done |
| [C2](#c2--acting-in-the-owners-tools) | CHAT | TIER 0 | Done |
| [C3](#c3--recall-outside-the-current-chat) | CHAT | TIER 0 | Done |
| [C4](#c4--file-inspector) | CHAT | TIER 1 | Done |
| [C5](#c5--chat-file-output--done) | CHAT | TIER 1 | Done |
| [C6](#c6--no-citations-on-tool-derived-answers) | CHAT | TIER 1 | Done |
| [C7](#c7--no-web-access) | CHAT | TIER 1 | Done |
| [C8](#c8--mcp-tools-unreachable) | CHAT | TIER 1 | Done |
| [C9](#c9--no-skills-or-reusable-procedures) | CHAT | TIER 1 | Done |
| [C10](#c10--the-assistant-lives-in-one-browser-tab) | CHAT | TIER 2 | Open |
| [C11](#c11--background-work-is-not-conversational) | CHAT | TIER 2 | Open |
| [C12](#c12--no-collaboration) | CHAT | TIER 2 | Open |
| [C13](#c13--no-stop-or-steer) | CHAT | TIER 3 | Done |
| [C14](#c14--no-message-level-actions) | CHAT | TIER 3 | Done |
| [C15](#c15--attachments-are-one-way) | CHAT | TIER 3 | Open |
| [C16](#c16--governed-turn-based-voice) | CHAT | TIER 3 | Done |
| [C17](#c17--recall-is-invisible) | CHAT | TIER 3 | Done |
| [C18](#c18--no-cross-chat-surface) | CHAT | TIER 3 | Open |

**2026-08-21 compatibility update.** BUG-216 and MEM-06 are closed. Build now
has foreground SSH/Daytona command adapters, a persistent container boundary,
background run control and explicit runner-trust posture. Filtered egress and
credential delta controls are **partial**, not complete: their policy,
quarantine and UI paths ship, but live container bypass/copy-on-write proof is
still required before either capability can be selected. This keeps the gap
table aligned with the measured runtime rather than with configuration.

---

## GAP-BUILD — What Build needs to stand against a class-leading coding agent

**Status: analysis, not a defect.** Nothing below is broken; this is the
distance between what Build ships today and the bar set by the best autonomous
coding agents — the ones that read a repository, make the change, run the tests,
read the failure, and iterate until it is green, in one uninterrupted session.

Build already clears part of that bar. It runs a genuine agentic loop
(`raiker/runtime/orchestrator.py`, model → tool call → broker → model, capped by
`max_tool_calls`, default `10_000` in `raiker/contracts/models.py`), its read
tools really execute, and its Plan/Edit/Auto modes are enforced by the runtime
rather than by prompt wording (`apps/web/src/lib/buildModes.ts` sets the
per-capability decision mode server-side, so a write proposed in Plan mode is
refused by the policy engine). The governance, audit and checkpoint story is
*ahead* of the field, not behind it.

The gap is that **Build cannot close a loop.** Everything below follows from
that, and the order is the order they should be done in — each tier is worthless
without the one above it. B1 (FIXED-08), B2 (FIXED-09), and B3's defined core
scope (FIXED-23) have since been completed:
an approved file change is really written, and the turn continues through the
approval instead of ending at it; Build can now make a narrow, hunk-level edit.

### Tier 0 — the blocking three (without these, nothing else matters)

#### B1 — An approved action must actually execute

✅ **Done — see FIXED-08.**
The Approvals resolution path now invokes `ApprovalExecutionRelay` for
`file_write_execution` and `patch_apply_execution`, so an approved file change
is genuinely written, re-governed at execution time, and checkpointed first.
Build is no longer a proposal generator for file work.

**B1 shell closure (2026-08-14):** approved `shell` and `process` actions now
execute through the same durable `CommandService` as a standing-grant
`run_command`. There is no owner-callable command-create API. Every accepted run
stores the approval or standing-grant identity, bounded redacted output, exact
selected environment, terminal outcome, and immutable receipt; a missing
authority or unavailable selected backend fails closed. The executed/refused
outcome is threaded back into the transcript as a real tool result by B2
(FIXED-09).

#### B2 — The turn resumes after an approval

✅ **Done — see FIXED-09.** The loop
parks its working state against the approval and picks the same turn up on
resolution, with the real result (or an honest refusal) appended as the tool
result. Build no longer stops dead at its first write.

#### B3 — Real patch application

✅ **Complete — see FIXED-23, FIXED-29, and
FIXED-34.** `edit_file` now replaces
`old_text` only when it occurs exactly once, and `apply_patch` calculates a
unified-diff candidates from exact hunk context before the approval is
displayed or an execution is allowed. A missing, ambiguous, or stale match
fails closed with a machine-readable error; rejected patch hunks are named and
no partial candidate is written.

**B3 expansion scope.** ✅ **Done — see FIXED-29 and FIXED-34.**
Create/delete patches, coordinate-guided context offsets, empty-context
insertions, and `\\ No newline at end of file` are supported with the same
all-or-nothing candidate used for preview and execution. Multi-file diffs now
use one combined approval, an atomic execution transaction, and per-path
checkpoint evidence under the same governed action.

### Tier 1 — loop mechanics

#### B4 — Parallel tool calls are silently dropped

✅ **Done — see FIXED-39.**
Every validated read-only proposal in a model response now runs concurrently
and every result is returned under its matching call id in one provider-valid
batch. Mutations remain serial and stop at the first approval boundary.
Budget-deferred calls emit `model_tool_calls_dropped` with
proposed/accepted/dropped counts, so no call disappears without evidence.
ADD-02 has since closed the boundary half: the calls behind an approval are
parked with the turn as an ordered queue (`model_tool_calls_queued`) and walked
one decision at a time on resume, so they are deferred rather than dropped.
FIXED-99 closed the last of it: a *policy refusal* now ends its own call rather
than the batch, wherever in the batch it falls, and reaches the transcript as
`model_tool_call_refused` — so `model_tool_calls_dropped` is left meaning only
what it says.

#### B5 — Test/command feedback channel

✅ **Done — see FIXED-44, FIXED-47, and
the governed-shell implementation commits dated 2026-08-14.**
A standing, expiring, revocable per-session
command-prefix grant now returns bounded stdout/stderr and exit status with the
workspace as cwd and a wall-clock cap. Anything outside the grant falls back to
the approval-gated shell path. Both paths converge on the same durable run and
receipt lifecycle. The owner's selected environment is authoritative: a ready,
pinned container runs there with no network and no host fallback; explicit
`local_native` uses the narrow argv-only host runner and is labelled reduced
isolation. Unsupported container, SSH, or Daytona features are refused rather
than substituted.

#### B6 — No task/plan state across the loop

✅ **Done — see FIXED-94.**
`update_plan` writes an ordered checklist — one status per step, at most one
`in_progress` — into an owner-scoped, session-keyed row that outlives the turn.
It is streamed live as `agent_plan_updated` and rendered as a checklist above the
transcript in **both** Chat and Build, and it is re-injected into every later
turn (`agent_plan_replayed`), which is what makes it a recovery point rather than
a progress bar. Validation is fail-closed and names every rejection, so a
malformed plan never replaces a good one. It grants nothing: every step it names
is governed again when it is actually attempted.

#### B7 — No subagents at the model's disposal

✅ **Done — see FIXED-95.**
`spawn_subagent` runs a bounded, read-only investigation under its own principal
and contract and returns a bounded digest, so a wide search no longer sits in the
parent's context for the rest of the conversation. Only read-only, local,
non-egress tools are delegable; a write, a command, a connector, an MCP tool or a
nested spawn is refused before the subagent is created, with the offending tool
named. Every step is re-brokered through the same policy engine and gates, and
the findings reach the calling model as untrusted data and the audit trail as
counts.

#### B8 — MCP tools are unreachable

✅ **Complete — see FIXED-17 and FIXED-96.**
FIXED-17 made a connected server's tools callable as `mcp__<server>__<tool>`.
Reviewing this entry against the running product found the *surface* had not
caught up, and FIXED-96 closes that: discovery now answers the capability gate
and the decision mode together, so a mode that would withhold every call projects
nothing instead of offering the model a tool the runtime would refuse; and
Extensions → MCP servers states whether the agent can actually call a connected
server, names the exact reason when it cannot, and links to the control that
changes it. Verified live end to end — withheld, then raised, then a real
`mcp__echo__echo` call answering in Chat with the payload kept out of the audit
trail.

### Tier 2 — what the agent can see

#### B9 — No repository index

✅ **Done — see FIXED-113.** A bounded, deterministic
scan (`raiker/graph/codemap.py`) records what each file is and what it declares —
Python exactly via `ast`, fifteen other languages approximately via bounded
patterns, with each file recording which extractor produced it. It is built when
a repository is connected, when one that has never been indexed is selected, and
on the owner's own **Rebuild index** control — never on a turn, because indexing
the owner's tree is their decision. After an approved file mutation really lands,
the relay re-parses exactly the paths it touched, so a line number the map hands
out is the line the declaration is on now.

`code_map_search` puts it in front of the model as **coordinates, not code**, and
a `code_map` context item carries the ranked files and their declarations into
the turn as `untrusted_external` — a symbol name and a docstring come out of
repository files, which is exactly where an injected instruction would sit.
Reading the code still goes through `read_file`, workspace containment and the
policy engine, so the map grants nothing.

The switch is `code_map_indexing` (Permissions → Workspace → **Code map**), with
a real executor and an activation requirement. It is deliberately **not**
`graph_codemap_indexing`: that capability names the Phase-3 durable governed
graph store — nodes and edges with provenance, approval previews, rollback plans
— which is still the dry-run planner in `raiker/graph/planner.py`. Making one
switch mean both a derived cache and a governed record store is the "two lists
that have to agree" defect this document keeps recording, so that capability and
every readiness flag under it are left exactly as they were.

**What B9 did not do.** The embeddings half. There is no vector index over the
tree and no semantic retrieval of code: ranking is lexical over an index of real
declarations, which is what makes it find a *definition* rather than a mention.
`retrieve_hybrid_memory` remains what it always was — retrieval over approved
memories, and it is called on every turn by the context gatherer, not only by the
evaluation harness as this entry used to claim.

#### B10 — No language intelligence

✅ **Done — see [FIXED-366](FIXED_ITEMS.md#fixed-366--build-could-read-a-repository-and-not-understand-it), 2026-09-03.**
`document_symbols`, `find_definition` and `diagnostics` ship under their own
`language_intelligence` capability, read-only and with no approval path, exactly
as this entry asked. The fourth name here, `find_references`, already shipped as
`code_map_references` (B9 / FIXED-113) and is deliberately not duplicated.

Two deviations from the wording above, both deliberate. It is **not LSP-backed**:
BUG-227's first question was whether Raiker wants a language-server client, and
the answer is no — a long-running subprocess reading the workspace would need
`CommandService`'s boundary, its own lifecycle and a crash-recovery story, and
everything Build needed is obtainable without one. And the feedback loop is
**parse-level, not type-level**: a file in a language this runtime cannot parse
is reported as *not checked*, never as clean, because a clean bill from a check
that did not happen is trusted the same as a real one and is wrong.

#### B11 — No git write path

✅ **Complete — see FIXED-109, FIXED-110 and
FIXED-111.** `git_branch` and
`git_commit` are governed, approval-required proposals whose preview *is* the
computation the execution re-derives: for a commit the exact file list and the
whole diff — including files git does not track yet — and for a branch the two
refs it moves between, because there is no diff to show and pretending otherwise
would be worse than saying so. Both answer to one owner switch,
`git_write_execution` (Permissions → Workspace → **Git writes**), and both fail
closed with a named reason on every case a later execution could not honour.
Execution stages exactly the reviewed paths rather than `git add --all`, so
`.raiker/` — the vault key, the encrypted store, the audit log — can never be
swept into a commit, and repository hooks are disabled for the invocation so a
governed write cannot become an un-governed code-execution path. `github_write`
proposes the work outward (`create_pull_request`, `create_comment`) under the
existing `connector_github_runtime` gate, owner credential and egress allowlist.

**B11 is now complete — see FIXED-110 and FIXED-111.** The push landed as its
own capability, `git_push_execution` (Permissions → Network → **Git push**),
because publishing is egress carrying repository content off the machine and an
owner who let the agent commit has not thereby let it publish. It answers to two
boundaries the gate cannot substitute for — the remote's host on the owner's
connector egress allowlist, and the owner's own credential — refuses any host
that credential does not belong to, computes its preview without touching the
network, and never forces or deletes a ref. `github_write` now has a head to
open a pull request against. The git tools also resolve against the repository
the owner *selected* in Build rather than always the workspace root, and every
git approval names the repository the change lands in.

#### B12 — No web access

✅ **Done — see FIXED-101.** `web_fetch` returns one page
as bounded, sanitised text framed as untrusted data, governed by the `web_fetch`
capability gate, the per-capability decision mode (default `ask` withholds), and
the owner **blocklist** `RAIKER_WEB_EGRESS_BLACKLIST` plus the rules stored in
Settings → Web access. *(Superseded 2026-08-22: this originally named an
allowlist that shipped empty.)* Because the URL is model-supplied it is checked
as well as the host — HTTPS only, no embedded credentials, a destination that
resolves to a public address, and every redirect hop re-checked, none of which
the owner can switch off. `web_search` sits behind the same gate and works
against a keyless default endpoint until the owner points
`RAIKER_WEB_SEARCH_ENDPOINT` at their own.

### Tier 3 — the workspace surface (UI/UX)

Build's transcript is a chat column plus a background-work rail
(`BuildSidePanel.svelte`) and a "Waiting on you" decisions block. A coding agent
needs a workbench.

#### B13 — No file tree and no editor

✅ **Complete — see
[FIXED-321](FIXED_ITEMS.md#fixed-321--build-could-change-a-repository-and-never-show-it)
(2026-08-30).** **Files** on the Build header opens the connected repository
beside the conversation: a resizable, lazily-expanded tree and a read-only viewer
with the transcript's own locally-shipped highlighter. Two new reads sit behind
it, `GET /api/code/repos/{id}/browse` and `.../file`, both resolved through the
same `PathAuthority` a turn writes through and then re-checked against the
repository's own root, so a repository reference cannot become a workspace-wide
file browser. Below the split it is a sheet from the left, mirroring the
background-work rail on the opposite edge; **@** puts the open file's path into
the composer.

**Deliberately still read-only.** Promoting it to an editor would give the
browser a write path to the repository that does not pass through a proposal the
owner accepts, which is the one property Build's whole approval story rests on.
A change to a file is still a change the owner decides.

#### B14 — No diff review surface in Build

🟡 **The review half is complete (2026-08-29, [FIXED-312](FIXED_ITEMS.md#fixed-312--the-core-act-of-code-review-was-a-route-change-away)).**
The unified diff used to live only in the Approvals inbox, in a different route,
so the core act of coding review was a context switch away. Build now renders the
same governed preview inline between a pending decision and its Accept/Reject
buttons, through a shared reader that gives added and removed lines the hunk's
own line numbers and a screen-reader label rather than colour alone; Approvals
uses the same component, so a change looks the same wherever it is decided.

**Per-hunk accept/reject landed 2026-09-03, as
[FIXED-369](FIXED_ITEMS.md#fixed-369--a-reviewer-could-accept-a-change-or-reject-it-and-nothing-between).**
The decision the runtime can record is a *narrowing*: hunk positions in the
approved diff, validated against it, applied after the immutable-intent hash
check, and only ever able to remove hunks from what runs.

**Still open: "edit then accept".** It did not come with the other half because
it is not a smaller version of it — an edit is a **different action**, whose
bytes no human approved, so it cannot ride that hash and needs its own proposal
path. Tracked as [BUG-271](TO_BE_FIXED.md#bug-271--a-reviewer-can-narrow-a-change-and-cannot-correct-one).

#### B15 — Terminal/output pane

🟡 **Partly complete (2026-08-14).** Build now has
a responsive governed-terminal pane with selected-environment posture, durable
redacted output catch-up, live status, process-tree stop, authority evidence,
and immutable receipt inspection. It survives a browser reload because output
and receipts are owner-scoped database records. PTY input, background-process
controls, stream filters, failure-coordinate navigation, credential-delta
review, and backend restart reattachment remain open and are tracked in the
compatibility matrix and `TO_BE_FIXED.md`; the UI does not advertise them.

#### B16 — Tool activity is buried

✅ **Done — closed by BUG-206 slice D, recorded here 2026-08-29.** This entry was
still marked Open after the work that closes it had shipped, which is the same
defect the entries themselves are about: a claim about the product that the
product had outgrown. `ToolActivity.svelte` renders every call a turn made as a
first-class transcript row — a family glyph, the owner's word for the tool, and
the object it acted on — outside any disclosure, in call order, in **both** Chat
and Build. A running call carries the composer's own pulse; a refused one is the
same row in a refused state, in the place it was refused, with the route that
would change it. Every field is resolved in `raiker/tools/presentation.py` and
arrives already redacted, so a row cannot say more than the audit log does.

#### B17 — No way to stop or steer a running turn

✅ **Done — see FIXED-102.**
While a turn streams, the composer becomes its control surface: **Stop** ends the
turn at its next safe boundary and it reports as `stopped` — a decision, not a
failure — keeping the text it had already produced, and a steer field queues the
owner's own words into the running turn, where they arrive as a user message
before the model is asked anything else. Both go through the same governed
`POST /api/interrupts` the top-bar STOP switch uses.

#### B18 — No checkpoint or rewind control where the work happens

✅ **Done — see [FIXED-315](FIXED_ITEMS.md#fixed-315--the-one-control-that-makes-an-agent-safe-to-leave-running-was-in-another-route), 2026-08-29.**
Every part of the governed rewind already existed and was reachable from exactly
one route, so undoing the turn that broke something meant leaving the
conversation and recognising a snapshot by its id. **Rewind to before this** now
sits on the turn in Chat and Build, resolves *that turn's* checkpoint rather than
the latest, and opens the same preflight the Checkpoints page opens — one
component, so a rewind reads identically wherever it is asked for. It restores
nothing: the panel reads a metadata-only plan and the ask goes through
`POST /api/checkpoints/{id}/restore`, which recomputes its own plan, records the
proposal and returns an approval id; a cross-principal rewind is named as an
escalation before the ask.

Branch, Summarise and Rewind moved behind one **More** handle in the same change,
so the row under a message is three short words rather than six long ones at
every window width.

#### B19 — Composer ergonomics

✅ **Done — see FIXED-220.** Both composers share
one module (`apps/web/src/lib/composerCommands.ts`), so the assistant composer
and the coding-agent composer cannot drift into two different keyboards. Build
carries `/plan-mode`, `/edit-mode`, `/auto-mode`, `/terminal` and `/repos`
alongside the shared set; `@` completes workspace paths out of the code map the
owner built, through `GET /api/code/map/paths` under the same `code_map_indexing`
gate — never a filesystem scan, and paths only. Copy, **Edit** and **Retry** sit
on the owner's own message, and an edit adds a turn rather than rewriting the
transcript. The prompt box grows with what is written, and `/shortcuts` opens a
per-surface keyboard map built from the bindings the handlers implement.

Syntax highlighting in transcript code remains deferred in FIXED-06;
per-code-block copy already ships. Owner-authored slash commands closed as
FIXED-299: an active skill may have one owner-scoped trigger, and invoking it
loads instructions without changing any capability, decision, or approval mode.

#### B20 — Sandboxed execution environment

🟡 **Partly complete (2026-08-14).**
The selected container command path is real rather than record-only: it requires
a digest-pinned image, creates a non-networked read-only/capability-dropped
worker with bounded CPU, memory, and PIDs, masks `.raiker`, mounts `.git`
read-only, streams through the shared redactor, and never falls back to the
host. Readiness probes the CLI, daemon, and exact image before selection is
reported ready. The current test host had no reachable Docker daemon, so this
path is automated-test proven but not live-container proven in this run.
`local_native` is deliberately described as host access with reduced isolation;
native OS sandboxing, persistent supervisor reattachment, filtered egress,
SSH, and Daytona remain open and are not claimed as shipped.

### Found while closing B6, B7 and B8

Three defects surfaced during this work that are not gaps — they are things that
were already broken, in the same class as the gaps around them: a capability the
product advertised and could not deliver. All are recorded in
`docs/plans/TO_BE_FIXED.md`; the first two are fixed, the third is open.

**A declared-event gap silently killed turns (FIXED-97).** `AgentEvent`
validates `event_type` against a fixed set and raises inside the streaming turn
otherwise, surfacing as *stream ended* with no stated cause. B4's own
`model_tool_calls_dropped` — the event that proves no tool call disappeared
without a record — had shipped undeclared, so **any turn that actually dropped a
call died at the moment it tried to say so.** The unit tests missed it because
they assert on results rather than on the durable log; a static scan of every
emitted event type against the declared set now guards it.

**Four advertised tools had no policy verdict (FIXED-98).** `PolicyEngine.review`
hard-denies anything in neither policy set. `create_task`,
`assign_session_project`, `remote_execute` and `cloud_execute` were all in the
model's advertised schema and in neither set, so each was answered
`unknown_or_denied_tool` rather than reaching the approval it was built for. The
remote/cloud pair is the more instructive one: the policy sets listed the
*capability* names (`remote_execution_cap`) while the model proposes *tool* names
(`remote_execute`), and nothing held the two vocabularies together. A test now
asserts the invariant directly — no model-exposed tool may fall through to a
hard deny.

**`denied_actions` is dead policy configuration (BUG-51, open).**
`StaticPolicyConfig.denied_actions` is read by nothing and lists `write_file`,
`edit_file` and `web_fetch` among others. A reviewer auditing the policy layer
would reasonably read it as a hard block that does not exist. Either delete it or
make it authoritative; a third policy set that looks load-bearing and is not is
an auditability defect in its own right.

**The pattern.** Each is the same failure mode the gaps themselves describe: two
lists that have to agree — schema and policy, emitted events and declared
events, configured denials and enforced ones — with nothing holding them
together. Each is now held together by a test rather than by care.

> **This ordering covers one pillar.** The order that spans all four — and the
> reason two items here are outranked by work in other documents — is
> [`PILLAR_MAP.md`](PILLAR_MAP.md) → *The order to work in*.

### Suggested order

B1 → B2 → B3 make Build an agent. **B1, B2, and B3's defined core scope are
now landed**: an approved change is really made, the turn continues through
it, and B3 uses strict, hunk-level editing instead of a whole-file rewrite.
B3's multi-file patch transaction has landed. **B4–B8 are now complete**, so the
loop is efficient, legible, and reaches the ecosystem. **B11, B12 and B17 have
since landed too** — the agent can commit the change it made and propose it, it
can read a page it is told to read, and the owner can stop or correct a turn
while it runs rather than waiting it out. **B9 has landed**: the agent can find
where something is defined instead of guessing a search pattern, and the index
follows the code as the agent changes it. B10 is the natural next step in the
same tier — a code map says where a declaration *is*, an LSP says what refers to
it. **B19 has landed**, which is the tier-3 item that changes daily use most: the
composer has commands, `@`-mention completion over the code map, a keyboard map,
and per-message edit and retry. **B16 was already closed** by BUG-206 slice D and is recorded as such above; **B18 has
now landed**, which is the tier-3 item that changes what an owner dares leave
running. **B13 landed 2026-08-30** — the repository is on screen beside the
conversation about it, which is the tier-3 item an owner meets on every turn.
**B10 and B14's per-hunk half landed 2026-09-03**: the agent can ask where a name
is declared and whether its own edit still parses, and a reviewer can accept part
of a change instead of all or none. What is left of B14 is *edit then accept*,
which is a different action rather than a smaller one and is tracked as
BUG-271. Everything else is depth. B20 is a *policy* decision before it
is an engineering one and belongs to the owner, not to an implementer.

---

## GAP-CHAT — What Chat needs to work as a class leading - agentic work assistant

**Status: analysis, not a defect.** Chat is intended to be more than a chat box:
an assistant that works across the owner's documents, mail, calendar, chat
tools and schedule, produces real files, and keeps working while the owner is
away. This entry states the distance to that bar.

Chat already clears real parts of it. Turns stream with conversational status;
conversation memory within a chat works (FIXED-04); documents and images upload
and reach the model; projects carry instructions and approved memory; chat
search covers titles and message text; and — genuinely ahead of the field —
`raiker/tasks/scheduler.py` runs *due tasks as governed turns* on `continuous`
(20 min), `hourly`, `daily` and `weekly` cadences, re-arming after each cycle,
so standing routines are already real rather than aspirational.

Three things stop it being a work assistant: it cannot produce an artifact, it
cannot act on the tools it can read, and it cannot remember across the work.

### Tier 0 — the blocking three

#### C1 — First-class document output

✅ **Done — see FIXED-40 and FIXED-43.**
`create_document` creates Markdown, DOCX, XLSX, and PDF artifacts locally
without a file-creation approval prompt. The completed document is preserved in
the owner-scoped attachment store, bound to its exact trusted session/turn, and
shown by the existing Chat inspector.

#### C2 — Acting in the owner's tools

✅ **Complete for repeated manifest-driven
execution — see FIXED-37 and FIXED-41.**
This is the one place the approval loop is already closed end to end, and it
should be read as the precedent for C1 rather than as a gap in itself:
`github_read`, `gmail_read`, `gcal_read`, `slack_read` and `connector_read`
execute directly; a `connector_write` proposed by the model is parked as a
`connector_write_intents` row (`raiker/tools/broker.py`) with the honest
`expected_effect` *"Approving executes this exact connector mutation once"*, and
resolving that approval really does call `ConnectorInvoker.invoke`, returning
`"status": "executed", "executes_action": true`
(`raiker/api/routes_approvals.py`). Approved connector mutations are sent.

Only manifest-declared operations of an enabled, credentialed connector are
reachable. That boundary is now visible: the Connector Store publishes each
registered read/write operation and its confirmation posture, and approvals
show the exact redacted outbound arguments before execution. The existing
standing-grant manager supports connector/operation-shaped scope patterns, and
FIXED-38 adds explicit manifest compensation metadata without inventing undo for
operations that do not declare it. Multiple read calls execute together; write
calls remain ordered and each consumes its own approval exactly once.

#### C3 — Recall outside the current chat

✅ **Done — see FIXED-42.** The
read-side `memory_search`, `memory_list`, and `memory_get` tools are model-visible
without approval. Context gathering runs owner-scoped hybrid retrieval and adds
bounded, attributed metadata for old Chat and Build sessions and Projects,
including archived work; approved memory text is labelled untrusted. Incognito
is an absolute opt-out. Durable writes retain the existing privacy posture, and
FIXED-156 made them reachable: `memory_write` and `memory_forget` are now
model-visible behind their own gates, so the model proposes the exact text and
the owner accepts it rather than Raiker silently remembering — or, with the gate
off, nothing can be proposed and every surface says so.

**Extended 2026-08-25 by
[FIXED-289](FIXED_ITEMS.md#fixed-289--uploaded-files-had-nowhere-to-live-and-build-inherited-a-project-nothing-on-screen-named).**
Two changes to what "owner-scoped" means here. Recall now also reaches the
owner's **managed knowledge files** — documents kept under `.raiker/memory-files/`
for the account and under each project's managed root — as bounded passages with
provenance back to the exact file and revision. And the boundary is now **stated
by the turn** rather than inherited from an account-level active project: Chat
stays owner-wide, while Build declares one project and can reach only account
memory, account files, that project's memory and files, and the conversations
assigned to it. The backend enforces both — the prompt API refuses a Build turn
with no project, and the gatherer re-checks ownership and fails closed — so the
boundary no longer depends on which selector a page happened to show.

### Tier 1 — working with the owner's material

#### C4 — File inspector

✅ **Complete — see FIXED-107.** FIXED-10
shipped the first two tasks of the chat file inspector: chips are buttons and
open a session-authorized, view-only pane, reusing the sanitising renderer from
FIXED-06 for the Markdown case. FIXED-19 and FIXED-20 record a supported,
newly generated file against its exact session and turn so it uses that same
pane. FIXED-45 revalidated uploaded and newly generated files across supported,
unsupported, unavailable, cross-account, and cross-session cases. The last of it
— *showing and highlighting the passage the assistant used* — landed with C6: a
citation chip opens the source **at the run the citing sentence rests on**,
located by exact match against the source's own text, and every case that cannot
be located says which one it is instead of marking something near it.

#### C5 — Chat file output — done

FIXED-19 keeps per-response copy but removes
per-chat Markdown download and browser print/Save as PDF. Generated artifacts
and stored attachments use the right-hand inspector rather than a general
download surface; FIXED-20/FIXED-22 preserve artifacts once without automatic
deletion. FIXED-45 adds the response-linked generated-document card and explicit
preview action.

#### C6 — No citations on tool-derived answers

✅ **Done — see FIXED-107.** Every
governed call that really returned material, and every file the owner attached,
enters a per-turn **source ledger** and is handed to the model as a `cite_as`
marker (`[s1]`). The transcript shows the ledger under the answer as clickable
provenance chips, and a marker the model wrote inside the answer renders as the
same chip inline. The two claims are kept apart on purpose: the ledger is a fact
the runtime recorded, a citation is the model's claim about which sentence rests
on it, and a marker the ledger does not know stays the characters it is.

#### C7 — No web access

✅ **Done — as B12 (FIXED-101).** `web_fetch` and
`web_search` are callable in Chat under the same gate, decision mode, egress
allowlist and audit path, and what they return is untrusted data. Verified live:
withheld with its reason, then — once the owner enabled the capability and raised
the mode — a real page read and quoted back, with a non-allowlisted host still
refused.

#### C8 — MCP tools unreachable

✅ **Done — as B8 (FIXED-17, FIXED-96).** A
connected server's tools are callable in Chat under the same gate, decision mode,
containment and audit path, and the Extensions page states whether the agent can
reach them. Verified live: the model called `mcp__echo__echo` in Chat and quoted
its answer back.

#### C9 — No skills or reusable procedures

✅ **Done — FIXED-299.** Installed and built skills are model-selectable through
progressive `skill_load`; an active skill can also carry an owner-authored slash
trigger in Chat and Build. The trigger is a convenience handle for the same
reviewed instructions and explicitly grants no capability or approval bypass.

### Tier 2 — presence and continuity

#### C10 — The assistant lives in one browser tab

`raiker/config/channel-connectors.json`
declares cli, tui, rest, web_ui, desktop, dashboard, ide, apple_mobile,
android_mobile and webhooks — but `external_channels_enabled` and
`notifications_enabled` are both hardcoded `False`
(`raiker/channels/readiness.py`), so there is no mail, chat-tool or mobile surface
where the assistant reaches the owner. Scheduled routines therefore run and
finish with nobody told. **Work:** enable the notification path first (it is the
cheapest and it makes routines useful), then one external channel end to end.

#### C11 — Background work is not conversational

✅ **Done — see [FIXED-367](FIXED_ITEMS.md#fixed-367--background-work-finished-into-a-status-line), 2026-09-03.**
Each task owns a durable conversation, titled after it; every cycle runs in that
thread; and the card links to it. The reply steers rather than merely records
because the next cycle runs in the same conversation the reply is in — nothing
new had to be built for that, it is conversation memory (FIXED-04) applied to a
thread that now exists.

The entry understated the defect slightly, and the correction is worth keeping:
the output did reach a *session* — but every task for a principal shared one
`sess_inbox_<principal>` transcript that Chat deliberately hides, so the nightly
run and the hourly check interleaved in a thread nobody could open.

#### C12 — No collaboration

No sharing of a chat, a project, or a document; no
second participant; no per-recipient scoping. Governance is built for a single
owner, so this is a genuine architectural decision rather than a missing screen —
`docs/architecture/NESTED_BOUNDARIES_ARCHITECTURE.md` is the place it has to be answered.

### Tier 3 — conversation surface (UI/UX)

#### C13 — No stop or steer

✅ **Done — as B17 (FIXED-102).** Chat's composer
carries the same Stop and steer controls as Build's, on the same governed
endpoint, and a stopped turn says so in the transcript instead of simply ending.

#### C14 — No message-level actions

✅ **Complete — see FIXED-220 and FIXED-227.** Copy, **Edit** and **Retry** are on the owner's own
message in both Chat and Build. Edit puts the prompt back in the composer and
**does not rewrite the transcript**: the original turn stays and the edited one
is a new turn beneath it — ChatGPT and Claude replace the edited message and
discard what followed it, which for a governed agent would mean a record that
quietly changes what was asked.

**Branch-from-here has since landed — see FIXED-227.** It was the one part of this
entry that was not a composer change, and it was built the way this entry
described: a conversation fork over the existing checkpoint manifest (`plan_fork`
/ `execute_fork`, previously CLI-only) exposed as
`GET|POST /api/checkpoints/{id}/branch`, plus the surface that makes two branches
legible — **Branch** on a completed turn, and a lineage band on the branch naming
and linking the conversation it grew from. The conversation branched *from* keeps
every turn it had, which is the same reason Edit does not rewrite history.

Per-message feedback is not planned — there is no model to send it to, and a
control that files a rating nowhere is the kind of surface this document exists
to prevent.

#### C15 — Attachments are one-way

The composer uploads; the transcript cannot
hand a file back (C1), preview one (C4), or let the owner drag one out.

#### C16 — Governed turn-based voice

✅ **Complete — see FIXED-247, re-verified
2026-08-21 and corrected by FIXED-249.** The re-verification checked all ten
claims against the code rather than against the closure note: nine held as
written, and the tenth did not. "Listening stops on a route change" was
implemented in the views' unmount teardown, but Chat and Build stay *mounted*
across route visits, so the microphone kept running behind a hidden composer.
Both surfaces now release the audio owner on visibility. Chat and
Build now share a real **Dictate** control: browser speech recognition writes
into the ordinary editable composer, **Done** finalises without sending,
**Cancel** restores the exact pre-dictation draft, and only the existing
**Send** action can create a turn. The backend accepts only `typed`, `dictated`
or `mixed` provenance and records that metadata without retaining audio or a
second transcript. A completed assistant response has a manual **Read aloud** /
**Stop speaking** control; it never auto-plays, never reads code bodies or raw
URLs, and shares one audio owner with dictation across both surfaces. The owner
chooses one of the browser-supported speech languages in Settings.

**Future improvement — full-duplex live conversation.** Continuous listening,
speaking, interruption and hands-free task control remain deliberately absent.
They are not a safe extension of C16: each spoken task-control command needs an
explicit state model, visible transcript, wake/stop affordance, action-bound
confirmation for consequential work, barge-in cancellation, one global audio
owner, and the same gateway/policy/audit route as a typed control. This is
**meaningful parity**, because ChatGPT and Claude already offer live voice; it
would go beyond them only if every accepted or refused spoken control carried
visible authority, confirmation and receipt evidence.

#### C17 — Recall is invisible

✅ **Complete — see [FIXED-311](FIXED_ITEMS.md#fixed-311--recall-was-invisible-at-the-moment-it-was-used), 2026-08-29.**
C6 had closed the *reading* half for one class of recall: a `memory_search` that
really returned rows is a citable source like any other. The other kind — the
ambient recall that happens on every turn — reaches the model through the context
bundle and left nothing to click, so the Memory route could say what Raiker
remembers and nothing could say which memories shaped *this answer*.

A settled answer now carries a collapsed **Remembered *n*** strip naming the
sentences the turn was given, each with **Correct** and **Forget** going through
the same governed actions the Memory page uses. The sentences are read live, so a
memory corrected since the turn ran reads as it is now and a forgotten one stops
appearing. Verifying it live surfaced [FIXED-314](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it):
a normally-phrased question recalled nothing at all, which had made the whole
feature invisible for a different reason than this entry recorded.

#### C18 — No cross-chat surface

✅ **Done — see [FIXED-368](FIXED_ITEMS.md#fixed-368--where-did-i-say-that-was-answered-what-am-i-working-on-was-not), 2026-09-03.**
All three: `GET /api/work-threads` answers "what am I working on" across chats
and routines, names the project each sits in, and — because C11 gave each task a
conversation first — makes the threads a routine is advancing resumable at all.
The rail's **Threads** destination is that board with an empty box and the search
it always was as soon as anything is typed.

> **This ordering covers one pillar.** The order that spans all four — and the
> reason two items here are outranked by work in other documents — is
> [`PILLAR_MAP.md`](PILLAR_MAP.md) → *The order to work in*.

### Suggested order

C1 and C2 make Chat capable of work — C1's blocking half has landed (FIXED-08),
leaving document output; C3 makes it feel like it knows the owner;
C10/C11 make it present when the owner is not watching — **C11 landed
2026-09-03**, so a routine now owns a thread the owner can read and reply into,
and **C18 with it**, so those threads are findable beside the owner's own
conversations. C4–C6 and C13–C16 are
the daily-use polish that determines whether any of it gets used; **C4, C6, C7,
C13, C14 and C16 have landed** — an answer says what it was drawn from and opens it at
the passage used, Chat can look something up instead of guessing, a turn can be
stopped or steered while it runs, and a prompt can be corrected and re-run
without retyping it; both composers can take an editable dictated draft and
completed answers can be read aloud only when the owner asks. C2, C3(3), C10 and C12 are owner policy
decisions before they are implementation tasks.

---

## Verified working (no action needed)

> **This is a dated observation, not a live status.** It records what a browser
> round found on the day it was run, so the gaps above are read against the right
> baseline. **Two counts in it have since moved** and are corrected inline below;
> the rest is left as observed. For current numbers read
> [`IMPLEMENTATION_STATUS.md`](../architecture/IMPLEMENTATION_STATUS.md) and
> [`RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md), which are
> maintained against the code.

Recorded so the fixes above are read against the right baseline: first-run
bootstrap; all 15 routes and 10 hub tabs with **0 console errors**; owner
sign-in; vault key generate/save with elevated re-auth; capability gates
(~~62 listed~~ **67 as of 2026-08-23**, four decision modes, step-up enforced,
~~42 deferred domains~~ **22 capabilities with no executor**, of which the seven
sensitive Tier-6 domains offer no enable path at all); runtime-mode activation; hosted-provider connection, live
provider model catalogue, and model selection; a real streamed Anthropic turn;
recent-chat list with row menu; chat search over titles and message text;
sessions, checkpoints, audit log, diagnostics, notifications, work-in-action;
all four task types (immediate, scheduled, daily routine, background agent) with
nesting, priority, and stop; project creation and session assignment; document
and image attachment upload reaching the model; MCP server create/connect/
monitor; theme toggle across all views; notification centre; STOP switch;
and adaptive navigation at 375/768/1024/1440 px with no horizontal overflow.
