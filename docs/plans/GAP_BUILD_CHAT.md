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

| ID | GAP | Tier| Status |
|---|---|---|---|
| B1 | BUILD | TIER 0 | Done |
| B2 | BUILD | TIER 0 | Done |
| B3 | BUILD | TIER 0 | Complete |
| B4 | BUILD | TIER 1 | Done |
| B5 | BUILD | TIER 1 | Done |
| B6 | BUILD | TIER 1 | Done |
| B7 | BUILD | TIER 1 | Done |
| B8 | BUILD | TIER 1 | Complete |
| B9 | BUILD | TIER 2 | Done |
| B11 | BUILD | TIER 2 | Complete |
| B12 | BUILD | TIER 2 | Done |
| B17 | BUILD | TIER 2 | Done |
| B19 | BUILD | TIER 3 | Done — composer commands, `@` mentions, keyboard map, message actions (FIXED-220) |
| C1 | BUILD | TIER 0 | Done |
| C2 | BUILD | TIER 0 | Complete |
| C3 | BUILD | TIER 0 | Done |
| C4 | CHAT | TIER 1 | Complete |
| C6 | CHAT | TIER 1 | Done |
| C7 | BUILD | TIER 0 | Done |
| C8 | BUILD | TIER 0 | Done |
| C13 | BUILD | TIER 0 | Done |
| C14 | CHAT | TIER 3 | Done — copy, edit-and-resend, retry (FIXED-220); branch-from-here remains open |

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

**B1. An approved action must actually execute.** ✅ **Done — see FIXED-08.**
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

**B2. The turn resumes after an approval.** ✅ **Done — see FIXED-09.** The loop
parks its working state against the approval and picks the same turn up on
resolution, with the real result (or an honest refusal) appended as the tool
result. Build no longer stops dead at its first write.

**B3. Real patch application.** ✅ **Complete — see FIXED-23, FIXED-29, and
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

**B4. Parallel tool calls are silently dropped.** ✅ **Done — see FIXED-39.**
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

**B5. Test/command feedback channel.** ✅ **Done — see FIXED-44, FIXED-47, and
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

**B6. No task/plan state across the loop.** ✅ **Done — see FIXED-94.**
`update_plan` writes an ordered checklist — one status per step, at most one
`in_progress` — into an owner-scoped, session-keyed row that outlives the turn.
It is streamed live as `agent_plan_updated` and rendered as a checklist above the
transcript in **both** Chat and Build, and it is re-injected into every later
turn (`agent_plan_replayed`), which is what makes it a recovery point rather than
a progress bar. Validation is fail-closed and names every rejection, so a
malformed plan never replaces a good one. It grants nothing: every step it names
is governed again when it is actually attempted.

**B7. No subagents at the model's disposal.** ✅ **Done — see FIXED-95.**
`spawn_subagent` runs a bounded, read-only investigation under its own principal
and contract and returns a bounded digest, so a wide search no longer sits in the
parent's context for the rest of the conversation. Only read-only, local,
non-egress tools are delegable; a write, a command, a connector, an MCP tool or a
nested spawn is refused before the subagent is created, with the offending tool
named. Every step is re-brokered through the same policy engine and gates, and
the findings reach the calling model as untrusted data and the audit trail as
counts.

**B8. MCP tools are unreachable.** ✅ **Complete — see FIXED-17 and FIXED-96.**
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

**B9. No repository index.** ✅ **Done — see FIXED-113.** A bounded, deterministic
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

**B10. No language intelligence.** No symbol lookup, no
definition/reference navigation, no type or lint feedback loop. **Work:** an
LSP-backed read tool set (`find_definition`, `find_references`,
`document_symbols`, `diagnostics`) — read-only, so it needs no approval path.

**B11. No git write path.** ✅ **Complete — see FIXED-109, FIXED-110 and
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

**B12. No web access.** ✅ **Done — see FIXED-101.** `web_fetch` returns one page
as bounded, sanitised text framed as untrusted data, governed by the `web_fetch`
capability gate, the per-capability decision mode (default `ask` withholds), and
the owner egress allowlist `RAIKER_WEB_EGRESS_ALLOWLIST` (empty ⇒ fail closed).
Because the URL is model-supplied it is checked as well as the host — HTTPS only,
no embedded credentials, a destination that resolves to a public address, and
every redirect hop re-checked. `web_search` sits behind the same gate and is off
until the owner configures an endpoint.

### Tier 3 — the workspace surface (UI/UX)

Build's transcript is a chat column plus a background-work rail
(`BuildSidePanel.svelte`) and a "Waiting on you" decisions block. A coding agent
needs a workbench.

**B13. No file tree and no editor.** `ProjectTreeNode.svelte` exists but Build
mounts no explorer, so a user cannot see the repository the agent is working in,
open a file, or read the result of a change without leaving the app.
**Work:** a resizable left explorer over the connected repository plus a
read-only viewer with syntax highlighting, promoted to an editor once B1 lands.

**B14. No diff review surface in Build.** The unified diff lives in the
Approvals inbox, in a different route — so the core act of coding review is a
context switch away, and it is all-or-nothing: no per-hunk accept, no edit
before accept, no partial rejection. **Work:** an inline side-by-side diff in
the Build transcript with per-hunk accept/reject and an "edit then accept" path,
resolving straight into the existing approval record.

**B15. Terminal/output pane.** 🟡 **Partly complete (2026-08-14).** Build now has
a responsive governed-terminal pane with selected-environment posture, durable
redacted output catch-up, live status, process-tree stop, authority evidence,
and immutable receipt inspection. It survives a browser reload because output
and receipts are owner-scoped database records. PTY input, background-process
controls, stream filters, failure-coordinate navigation, credential-delta
review, and backend restart reattachment remain open and are tracked in the
compatibility matrix and `TO_BE_FIXED.md`; the UI does not advertise them.

**B16. Tool activity is buried.** Tool events render inside a collapsed
governance `details`, so during a long turn the transcript looks idle.
**Work:** promote tool calls to first-class transcript rows — file read, files
matched, command started — with a progress affordance, keeping the full
governed record in the disclosure.

**B17. No way to stop or steer a running turn.** ✅ **Done — see FIXED-102.**
While a turn streams, the composer becomes its control surface: **Stop** ends the
turn at its next safe boundary and it reports as `stopped` — a decision, not a
failure — keeping the text it had already produced, and a steer field queues the
owner's own words into the running turn, where they arrive as a user message
before the model is asked anything else. Both go through the same governed
`POST /api/interrupts` the top-bar STOP switch uses.

**B18. No checkpoint or rewind control where the work happens.** Checkpoints are
recorded and browsable in their own route, but Build offers no "rewind to before
this turn" — the one control that makes an autonomous agent safe to let run.
**Work:** a per-turn rewind in the transcript, restoring workspace and
conversation state from the existing checkpoint manifest.

**B19. Composer ergonomics.** ✅ **Done — see FIXED-220.** Both composers share
one module (`apps/web/src/lib/composerCommands.ts`), so the assistant composer
and the coding-agent composer cannot drift into two different keyboards. Build
carries `/plan-mode`, `/edit-mode`, `/auto-mode`, `/terminal` and `/repos`
alongside the shared set; `@` completes workspace paths out of the code map the
owner built, through `GET /api/code/map/paths` under the same `code_map_indexing`
gate — never a filesystem scan, and paths only. Copy, **Edit** and **Retry** sit
on the owner's own message, and an edit adds a turn rather than rewriting the
transcript. The prompt box grows with what is written, and `/shortcuts` opens a
per-surface keyboard map built from the bindings the handlers implement.

Two pieces of the original entry are deliberately still open and are *not*
claimed here: syntax highlighting in transcript code (deferred in FIXED-06 —
per-code-block copy already ships) and owner-authored custom slash commands,
which is a governance design task rather than a parser change, because an
honest custom command has to state what authority it carries.

**B20. Sandboxed execution environment.** 🟡 **Partly complete (2026-08-14).**
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
and per-message edit and retry. B13–B16 make the result reviewable and are the
remaining tier-3 work. Everything else is depth. B20 is a *policy* decision before it
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

**C1. First-class document output.** ✅ **Done — see FIXED-40 and FIXED-43.**
`create_document` creates Markdown, DOCX, XLSX, and PDF artifacts locally
without a file-creation approval prompt. The completed document is preserved in
the owner-scoped attachment store, bound to its exact trusted session/turn, and
shown by the existing Chat inspector.

**C2. Acting in the owner's tools.** ✅ **Complete for repeated manifest-driven
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

**C3. Recall outside the current chat.** ✅ **Done — see FIXED-42.** The
read-side `memory_search`, `memory_list`, and `memory_get` tools are model-visible
without approval. Context gathering runs owner-scoped hybrid retrieval and adds
bounded, attributed metadata for old Chat and Build sessions and Projects,
including archived work; approved memory text is labelled untrusted. Incognito
is an absolute opt-out. Durable writes retain the existing privacy posture, and
FIXED-156 made them reachable: `memory_write` and `memory_forget` are now
model-visible behind their own gates, so the model proposes the exact text and
the owner accepts it rather than Raiker silently remembering — or, with the gate
off, nothing can be proposed and every surface says so.

### Tier 1 — working with the owner's material

**C4. File inspector.** ✅ **Complete — see FIXED-107.** FIXED-10
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

**C5. Chat file output — done.** FIXED-19 keeps per-response copy but removes
per-chat Markdown download and browser print/Save as PDF. Generated artifacts
and stored attachments use the right-hand inspector rather than a general
download surface; FIXED-20/FIXED-22 preserve artifacts once without automatic
deletion. FIXED-45 adds the response-linked generated-document card and explicit
preview action.

**C6. No citations on tool-derived answers.** ✅ **Done — see FIXED-107.** Every
governed call that really returned material, and every file the owner attached,
enters a per-turn **source ledger** and is handed to the model as a `cite_as`
marker (`[s1]`). The transcript shows the ledger under the answer as clickable
provenance chips, and a marker the model wrote inside the answer renders as the
same chip inline. The two claims are kept apart on purpose: the ledger is a fact
the runtime recorded, a citation is the model's claim about which sentence rests
on it, and a marker the ledger does not know stays the characters it is.

**C7. No web access.** ✅ **Done — as B12 (FIXED-101).** `web_fetch` and
`web_search` are callable in Chat under the same gate, decision mode, egress
allowlist and audit path, and what they return is untrusted data. Verified live:
withheld with its reason, then — once the owner enabled the capability and raised
the mode — a real page read and quoted back, with a non-allowlisted host still
refused.

**C8. MCP tools unreachable.** ✅ **Done — as B8 (FIXED-17, FIXED-96).** A
connected server's tools are callable in Chat under the same gate, decision mode,
containment and audit path, and the Extensions page states whether the agent can
reach them. Verified live: the model called `mcp__echo__echo` in Chat and quoted
its answer back.

**C9. No skills or reusable procedures.** `raiker/skills/` holds a candidate
store and nothing else; `docs/SELF_IMPROVEMENT_MODEL.md` describes procedural
memory that is never consulted at turn time. A work assistant should learn "how
we do the weekly report here" once. **Work:** promote approved procedural
memories into a named, model-selectable skill set, injected only when relevant.

### Tier 2 — presence and continuity

**C10. The assistant lives in one browser tab.** `raiker/config/channel-connectors.json`
declares cli, tui, rest, web_ui, desktop, dashboard, ide, apple_mobile,
android_mobile and webhooks — but `external_channels_enabled` and
`notifications_enabled` are both hardcoded `False`
(`raiker/channels/readiness.py`), so there is no mail, chat-tool or mobile surface
where the assistant reaches the owner. Scheduled routines therefore run and
finish with nobody told. **Work:** enable the notification path first (it is the
cheapest and it makes routines useful), then one external channel end to end.

**C11. Background work is not conversational.** Scheduled and background tasks
run as isolated turns; their output lands in a task record, not in a thread the
owner can reply to. **Work:** file each routine's cycle into a durable
conversation, so "what did the overnight run find?" is answerable in Chat and a
reply steers the next cycle.

**C12. No collaboration.** No sharing of a chat, a project, or a document; no
second participant; no per-recipient scoping. Governance is built for a single
owner, so this is a genuine architectural decision rather than a missing screen —
`docs/NESTED_BOUNDARIES_ARCHITECTURE.md` is the place it has to be answered.

### Tier 3 — conversation surface (UI/UX)

**C13. No stop or steer.** ✅ **Done — as B17 (FIXED-102).** Chat's composer
carries the same Stop and steer controls as Build's, on the same governed
endpoint, and a stopped turn says so in the transcript instead of simply ending.

**C14. No message-level actions.** ✅ **Done — see FIXED-220**, with one part
deliberately left open. Copy, **Edit** and **Retry** are on the owner's own
message in both Chat and Build. Edit puts the prompt back in the composer and
**does not rewrite the transcript**: the original turn stays and the edited one
is a new turn beneath it — ChatGPT and Claude replace the edited message and
discard what followed it, which for a governed agent would mean a record that
quietly changes what was asked.

**Branch-from-here is still open**, and it is the one part of this entry that is
not a composer change: it needs a conversation fork over the existing checkpoint
manifest plus a surface that makes two branches of one conversation legible.
Per-message feedback is not planned — there is no model to send it to, and a
control that files a rating nowhere is the kind of surface this document exists
to prevent.

**C15. Attachments are one-way.** The composer uploads; the transcript cannot
hand a file back (C1), preview one (C4), or let the owner drag one out.

**C16. Voice is a label.** The control is present and marked "(coming soon)" —
honest, but a work assistant used from a phone needs dictation and, ideally,
read-back.

**C17. Recall is invisible.** Once C3 lands, the owner must be able to see what
was remembered, why it was injected, and correct or forget it inline. The
Memory route exists for management; the *moment of use* is in Chat. C6 has since
closed the *reading* half for one class of recall — a `memory_search` that really
returned rows is a citable source like any other — but correcting or forgetting a
memory from the transcript is still only available on the Memory route.

**C18. No cross-chat surface.** Chat search covers titles and message text only.
There is no "what am I working on", no cross-project view, no resumption of the
threads a routine is advancing.

### Suggested order

C1 and C2 make Chat capable of work — C1's blocking half has landed (FIXED-08),
leaving document output; C3 makes it feel like it knows the owner;
C10/C11 make it present when the owner is not watching. C4–C6 and C13–C15 are
the daily-use polish that determines whether any of it gets used; **C4, C6, C7,
C13 and C14 have landed** — an answer says what it was drawn from and opens it at
the passage used, Chat can look something up instead of guessing, a turn can be
stopped or steered while it runs, and a prompt can be corrected and re-run
without retyping it. C2, C3(3), C10 and C12 are owner policy
decisions before they are implementation tasks.

---

## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline: first-run
bootstrap; all 15 routes and 10 hub tabs with **0 console errors**; owner
sign-in; vault key generate/save with elevated re-auth; capability gates
(62 listed, four decision modes, step-up enforced, 42 deferred domains offering
no enable path); runtime-mode activation; hosted-provider connection, live
provider model catalogue, and model selection; a real streamed Anthropic turn;
recent-chat list with row menu; chat search over titles and message text;
sessions, checkpoints, audit log, diagnostics, notifications, work-in-action;
all four task types (immediate, scheduled, daily routine, background agent) with
nesting, priority, and stop; project creation and session assignment; document
and image attachment upload reaching the model; MCP server create/connect/
monitor; theme toggle across all views; notification centre; STOP switch;
and adaptive navigation at 375/768/1024/1440 px with no horizontal overflow.
