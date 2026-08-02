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

| ID | GAP | Tier| Status |
|---|---|---|---|
| B1 | BUILD | TIER 0 | Complete |
| B2 | BUILD | TIER 0 | Complete |
| B3 | BUILD | TIER 0 | Complete |
| B4 | BUILD | TIER 1 | Complete |
| B5 | BUILD | TIER 1 | Complete |
| B6 | BUILD | TIER 1 | Complete |
| B7 | BUILD | TIER 1 | Complete |
| B8 | BUILD | TIER 1 | Complete |
| C1 | BUILD | TIER 0 | Complete |
| C2 | BUILD | TIER 0 | Complete |
| C3 | BUILD | TIER 0 | Complete |

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

**What is left of B1:** `shell` is still metadata-only on resolution, and that
is deliberate — a command is neither local-only nor reversible, so it belongs
with B5 (a narrow, owner-defined command allowlist under its own capability)
rather than with the file relay. The executed/refused outcome is now threaded
back into the transcript as a real tool result by B2 (FIXED-09).

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
batch. Mutations remain serial and stop at the first approval or policy
boundary. Budget- or boundary-deferred calls emit `model_tool_calls_dropped`
with proposed/accepted/dropped counts, so no call disappears without evidence.

**B5. Test/command feedback channel.** ✅ **Done — see FIXED-44 and FIXED-47.**
A standing, expiring, revocable per-session
command-prefix grant now returns bounded stdout/stderr and exit status with the
workspace as cwd and a wall-clock cap. Anything outside the grant falls back to
the approval-gated shell path. Granted commands execute in a no-network,
resource-bounded container and never fall back to the host.

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

**B9. No repository index.** Every turn starts cold: no symbol index, no code
map, no embeddings over the tree. `graph_indexing_enabled` and
`semantic_memory_writes_enabled` are hardcoded `False`
(`raiker/context/gatherer.py`), and `retrieve_hybrid_memory` — lexical + vector
+ graph, already written in `raiker/memory/retrieval.py` — is called only by the
evaluation harness. On a large repository the agent greps blind.
**Work:** build the code map described in
`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` on repository connect, refresh it
incrementally on approved writes, and inject the top-ranked slices into the turn
bundle as scoped, untrusted context.

**B10. No language intelligence.** No symbol lookup, no
definition/reference navigation, no type or lint feedback loop. **Work:** an
LSP-backed read tool set (`find_definition`, `find_references`,
`document_symbols`, `diagnostics`) — read-only, so it needs no approval path.

**B11. No git write path.** `git_status`, `git_diff` and `git_log` are exposed;
branch, commit, push and pull-request creation are not. The agent can describe a
change it can neither commit nor propose. **Work:** governed
`git_branch` / `git_commit` (high risk, approval, diff preview) and a
`github_write` bound to the existing connector credential and egress allowlist.

**B12. No web access.** No fetch and no search anywhere in `_TOOL_RISK`, so the
agent cannot read the documentation for a library it is being asked to use.
**Work:** an egress-allowlisted `web_fetch` returning sanitised text as
untrusted data; search behind the same gate, off by default.

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

**B15. No terminal or output pane.** Command output, once B5 lands, has nowhere
to stream. **Work:** a collapsible output pane with live streaming, exit status,
and a jump-to-failure affordance.

**B16. Tool activity is buried.** Tool events render inside a collapsed
governance `details`, so during a long turn the transcript looks idle.
**Work:** promote tool calls to first-class transcript rows — file read, files
matched, command started — with a progress affordance, keeping the full
governed record in the disclosure.

**B17. No way to stop or steer a running turn.** `POST /api/interrupts` exists
and `api.interrupt` is already in `apps/web/src/lib/api.ts`, but no view calls
it. A turn heading the wrong way must be waited out. **Work:** a Stop control on
the composer while streaming, and a queued-steer input that appends to the
running turn at the next safe boundary.

**B18. No checkpoint or rewind control where the work happens.** Checkpoints are
recorded and browsable in their own route, but Build offers no "rewind to before
this turn" — the one control that makes an autonomous agent safe to let run.
**Work:** a per-turn rewind in the transcript, restoring workspace and
conversation state from the existing checkpoint manifest.

**B19. Composer ergonomics.** No `@`-mention autocomplete for workspace files
(attaching a path means typing it exactly), no slash commands, no keyboard
shortcut map, no copy button on code blocks, no syntax highlighting in
transcript code (deliberately deferred in FIXED-06), no message edit-and-resend,
no regenerate. Each is small; together they are most of the felt difference in
daily use.

**B20. Sandboxed execution environment.** review codebase and live test before marking this complete - 
The local container slice is implemented; remote and cloud execution remain separate future capabilities.
Owner-granted B5 commands now use the same Docker boundary principles with
networking disabled and fail closed when its approved image is unavailable.

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
loop is efficient, legible, and reaches the ecosystem. B13–B16 make the result
reviewable. Everything else is depth. B20 is a *policy* decision before it is an
engineering one and belongs to the owner, not to an implementer.

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
is an absolute opt-out. Durable writes retain the existing privacy posture: the
model proposes a candidate and the owner accepts it rather than Raiker silently
remembering.

### Tier 1 — working with the owner's material

**C4. File inspector — done for attachments and generated files.** FIXED-10 shipped Tasks 1–2 of
`docs/superpowers/plans/2026-07-26-chat-file-inspector.md`: chips are buttons and
open a session-authorized, view-only pane, reusing the sanitising renderer from
FIXED-06 for the Markdown case. FIXED-19 and FIXED-20 record a supported,
newly generated file against its exact session and turn so it uses that same
pane. FIXED-45 revalidated uploaded and newly generated files across supported,
unsupported, unavailable, cross-account, and cross-session cases. **Remaining
work:** an assistant that reads a document should also be able to show and
highlight *the passage it used*.

**C5. Chat file output — done.** FIXED-19 keeps per-response copy but removes
per-chat Markdown download and browser print/Save as PDF. Generated artifacts
and stored attachments use the right-hand inspector rather than a general
download surface; FIXED-20/FIXED-22 preserve artifacts once without automatic
deletion. FIXED-45 adds the response-linked generated-document card and explicit
preview action.

**C6. No citations on tool-derived answers.** When an answer comes from an
email, a calendar entry or an attached document, the transcript does not say
which one. For an assistant acting on the owner's real data this is a
correctness feature, not a nicety. **Work:** carry source ids through the tool
result into the response and render an inline, clickable provenance chip.

**C7. No web access.** As B12 — the assistant cannot look anything up. For a
work assistant this is the difference between answering and guessing.

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

**C10. The assistant lives in one browser tab.** `config/channel-connectors.json`
declares cli, tui, rest, web_ui, desktop, dashboard, ide, apple_mobile,
android_mobile and webhooks — but `external_channels_enabled` and
`notifications_enabled` are both hardcoded `False`
(`raiker/context/gatherer.py`), so there is no mail, chat-tool or mobile surface
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

**C13. No stop or steer.** As B17: `POST /api/interrupts` and `api.interrupt`
exist; nothing calls them. A long turn cannot be stopped.

**C14. No message-level actions.** No copy, no edit-and-resend, no regenerate,
no branch-from-here, no per-message feedback. Editing a prompt and re-running is
the most-used control in an assistant of this kind.

**C15. Attachments are one-way.** The composer uploads; the transcript cannot
hand a file back (C1), preview one (C4), or let the owner drag one out.

**C16. Voice is a label.** The control is present and marked "(coming soon)" —
honest, but a work assistant used from a phone needs dictation and, ideally,
read-back.

**C17. Recall is invisible.** Once C3 lands, the owner must be able to see what
was remembered, why it was injected, and correct or forget it inline. The
Memory route exists for management; the *moment of use* is in Chat.

**C18. No cross-chat surface.** Chat search covers titles and message text only.
There is no "what am I working on", no cross-project view, no resumption of the
threads a routine is advancing.

### Suggested order

C1 and C2 make Chat capable of work — C1's blocking half has landed (FIXED-08),
leaving document output; C3 makes it feel like it knows the owner;
C10/C11 make it present when the owner is not watching. C4–C6 and C13–C15 are
the daily-use polish that determines whether any of it gets used. C2, C3(3),
C10 and C12 are owner policy decisions before they are implementation tasks.

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
