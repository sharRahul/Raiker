# Pillar map

**Canonical** for *which open work blocks which part of the product*. Every other
plan in this directory is organised by where a problem was found — a defect, a
parity gap, a memory audit, a proposal. None of them answers the question an
owner or a builder actually starts from: **what is standing between Raiker and
the thing it is trying to be?**

Written **2026-08-23**, revised through **2026-08-26**. It adds no new
work; it re-cuts what already exists.

---

## The four pillars

Raiker is one product wearing four faces. The first three are surfaces; the
fourth is what the other three run on.

| # | Pillar | What "done" means |
|---|---|---|
| [**P1**](#p1--a-polished-ai-assistant) | **A polished AI assistant** | Chat is the surface someone chooses over a hosted assistant for daily work — not because it is governed, but because it is good |
| [**P2**](#p2--a-governed-ai-agent) | **A governed AI agent** | Every action is policy-aware, observable, auditable, approval-driven, least-privileged, human-governed, recoverable, verifiable and fail-closed — as properties of the runtime, never as a layer around it |
| [**P3**](#p3--a-capable-codingbuild-agent) | **A capable coding/build agent** | Build reads a repository, makes the change, runs the tests, reads the failure and iterates to green, in one governed session |
| [**P4**](#p4--an-extensible-governed-agent-platform) | **An extensible governed agent platform** | Tools, skills, plugins, hooks, channels, MCP and models extend Raiker **without any of them gaining a route around governance** |

Cutting across all four, and never traded against any of them:

> **User-owned model choice** — local, private-network, home-lab and hosted —
> with no model, tool, skill, plugin, interface, runtime or execution path
> bypassing governance.

That last clause is P2's, and it is why
[`GOVERNANCE_ENTRY_PATHS.md`](GOVERNANCE_ENTRY_PATHS.md) exists: it is the only
document that makes the claim checkable rather than asserted.

---

## Where each pillar stands

Honest one-line assessments, each backed by the items below it.

| Pillar | State | The thing in the way |
|---|---|---|
| [**P1**](#p1--a-polished-ai-assistant) Assistant | **Class-leading governed recall.** Streaming, attachments, citations, search, export, branching, voice, incognito, projects, local/hosted semantic memory, and managed libraries whose exact file revisions can be recalled by meaning | No blocker. Linear vector scan remains the next scale limit, not a correctness gap |
| [**P2**](#p2--a-governed-ai-agent) Governed agent | **Ahead of the field, and now delivering what it claims.** Re-governance at execution time, machine identity, measured sandbox boundaries and per-capability threat models are all things no compared platform has — and as of 2026-08-23 *recoverable* and *auditable* are reachable rather than asserted. As of 2026-08-24 the owner's switches are checked to actually be switches, and as of 2026-08-25 a task cannot report done over work it delegated | GEP-01, GEP-04, BUG-218 and BUG-220 are closed. What remains is composition — one brief that splits into routed children (backlog #23) — and the two owner decisions GEP-02 and ADD-14/15 |
| [**P3**](#p3--a-capable-codingbuild-agent) Coding agent | **Closes the loop, and can now undo.** Real patches, real commits, real pushes, a governed terminal in a measured OS boundary, a code map, code review, and a governed rewind | Execution inside the sandbox is foreground-only: no interactive PTY on Windows, no background run that outlives the turn, no reattachment after a restart (BUG-194) |
| [**P4**](#p4--an-extensible-governed-agent-platform) Platform | **Governed, and narrower than the reference set.** Hooks, skills, plugins, channels and MCP all extend without an execution surface of their own | The MCP client now negotiates the current revision, but implements a subset of it: no streamable-HTTP session semantics, no remote OAuth, no `server/discover`, no MCP Apps |

**The single highest-value observation across all four:** three of the four
pillars were blocked by the *same two items* — checkpoint rewind and audit
export — and both were things Raiker had already built and never routed. Both
closed on 2026-08-23, together with the two other High/Low rows beside them and
the MCP revision that was blocking three P4 rows at once. **The backlog's
High-priority, Low-effort section is now empty.**

**The 2026-08-25 pass found it a fourth time, and this one had been invisible for
the longest.** `model_provider_runtime` — a registered, gated, threat-modelled,
acceptance-tested executor that turns a memory into a real semantic vector — had
never been called by anything. The surface that depended on it, Memory → Recall
backend, read as *correct*: it said plainly that the fallback matches words and
not meaning, and it offered every space the workspace held. It held none, and
nothing in the product could make one. **A missing control is a hole in the
implementation; an inert switch is a hole in what the owner believes; a
capability that is built, honest about its absence, and unreachable is a hole
nobody is looking for.** Routing it also found three breakages in its only
unmocked path — a config path, an event loop, and a credential — none of which
any test could reach, because the tests correctly injected past the part that had
never run. See [FIXED-283](FIXED_ITEMS.md).

**The 2026-08-24 pass found the same shape a third time, in the place it is worst
for this product.** Checkpoint rewind and audit export were controls Raiker had
built and never routed. GEP-04 found fifteen *switches* an owner could hold on or
off that decided nothing — subagents ran with the switch off, and the terminal
could install a plugin with the switch off. A control that is missing is a hole
in the implementation; a control that is *shown and inert* is a hole in what the
owner believes. Closing it also closed GEP-01, whose shared admission helper the
two new call sites needed. ~~**MEM-10 (P1) is now the largest honest gap left.**~~
MEM-10's binding leg closed on 2026-08-25.

---

## P1 — A polished AI assistant

| Item | Where | State |
|---|---|---|
| Semantic memory — the write half | [FIXED-283](FIXED_ITEMS.md#fixed-283--semantic-recall-was-selectable-and-nothing-could-ever-produce-a-space-to-select), [FIXED-293](FIXED_ITEMS.md#fixed-293--local-semantic-recall-was-declared-and-blocked-by-a-remote-egress-check) | **Closed 2026-08-26** — one governed action builds a real space from approved memories and managed passages through hosted or local llama.cpp embeddings |
| Semantic memory — the read half | [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | **Closed 2026-08-26** — ambient recall and `memory_search` embed once per turn through the governed provider action; Ask falls back without parking the turn |
| Vector recall is linear | [MEM-10 remainder](MEMORY_RELIABILITY_PLAN.md#mem-10--semantic-recall-is-selectable-but-a-default-install-has-nothing-to-select) | Open — ~431 ms at 3 000 memories, paid every turn |
| A natural-language question drops the lexical leg | [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | **Closed 2026-08-26** |
| Retention sweep | [FIXED-284](FIXED_ITEMS.md#fixed-284--nothing-expired-because-the-sweep-the-retention-classes-describe-was-never-offered) | **Closed 2026-08-25** — what is due is shown and the owner confirms it. No daemon, by design |
| Owner-guided summarisation of a range | [backlog #9](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-low-effort) | Proposed |
| Post-Stage-J temporal tiers and bounded graph context | [ADD-25](TO_BE_ADDED.md#add-25--post-stage-j-memory-expansion), [FME-02/FME-03](MEMORY_RELIABILITY_PLAN.md#post-stage-j-expansion-backlog) | Future — begins only after Stage J evidence and atomic snapshot publication |
| Premium responsive workspace shell | [ADD-26](TO_BE_ADDED.md#add-26--a-premium-responsive-workspace-shell) | **Closed 2026-08-25** — semantic palette, desktop reflow, compact overlay drawers, and 208 light/dark captures through 8K |
| The owner's own documents | [FIXED-289](FIXED_ITEMS.md#fixed-289--uploaded-files-had-nowhere-to-live-and-build-inherited-a-project-nothing-on-screen-named), [FIXED-294](FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words) | **Closed 2026-08-26** — managed files have lexical and semantic passages with provenance to the exact active revision |
| A structured question to the owner mid-turn | [backlog #17](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-medium-effort), [ADD-22](TO_BE_ADDED.md#add-22--a-structured-question-to-the-owner-mid-turn) | Proposed — the model cannot ask *which did you mean* |
| Tool rows do not survive a reload | [FIXED-287](FIXED_ITEMS.md#fixed-287--a-reopened-transcript-showed-the-answer-and-nothing-about-how-it-was-reached) | **Closed 2026-08-25** — rebuilt from `tool_actions` through the presentation function the live stream uses |
| GAP-CHAT remainder | [GAP-CHAT](GAP_BUILD_CHAT.md#gap-chat--what-chat-needs-to-work-as-a-class-leading---agentic-work-assistant) | 7 items; C2, C3(3), C10 and C12 are **owner policy decisions**, not implementation tasks |

**No blocking item.** BUG-240's final managed-file leg closed on 2026-08-26 as
[FIXED-294](FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words).
The question embedding is cached once per turn and now searches both approved
memory and exact-revision managed-file projections without widening owner or
project scope. Vector scan scale is the next P1 item.

## P2 — A governed AI agent

| Item | Where | State |
|---|---|---|
| Checkpoint rewind | [FIXED-270](FIXED_ITEMS.md#fixed-270--checkpoint-rewind-was-built-registered-tested-and-unreachable) | **Closed 2026-08-23** — a route, a Checkpoints action and a terminal command raise the approval |
| Audit export | [FIXED-271](FIXED_ITEMS.md#fixed-271--the-audit-log-could-not-be-taken-out-of-the-product) | **Closed 2026-08-23** — an executor, a route, a listing and a download, redacted and account-scoped |
| The second, weaker egress path | [FIXED-272](FIXED_ITEMS.md#fixed-272--two-egress-implementations-existed-and-the-weaker-one-was-registered) | **Closed 2026-08-23** — deleted; `web_fetch` routes through `WebAccessService` |
| An oversize checkpoint promised a rewind | [FIXED-273](FIXED_ITEMS.md#fixed-273--an-approval-promised-a-rewind-it-could-not-give-for-a-file-over-8-mib) | **Closed 2026-08-23** — the approval notice says so before you decide |
| Eight modules re-implement the gate check | [FIXED-279](FIXED_ITEMS.md#fixed-279--eight-copies-of-one-governance-check-and-two-of-them-had-already-drifted) | **Closed 2026-08-24** — one shared admission helper; two drifts found by reading the copies together, one of them live and pointed at the model |
| The stop switch's scope is undefined for read paths | [GEP-02](GOVERNANCE_ENTRY_PATHS.md#gep-02--the-stop-switchs-scope-is-undefined-for-read-paths) | Open — **an owner decision**, and the shared admission helper now carries the answer at no cost |
| An empty gate table means three different things | [BUG-239](TO_BE_FIXED.md#bug-239--an-empty-gate-table-means-three-different-things) | Open — **an owner decision**, raised 2026-08-24. The fork is one named table now; unifying it either loosens seven paths or tightens one |
| `NESTED_BOUNDARIES_ARCHITECTURE.md` overstates the architecture | [GEP-03](GOVERNANCE_ENTRY_PATHS.md#gep-03--nested_boundaries_architecturemd278-overstates-the-architecture) | Open |
| Fifteen capabilities have no traced governed-action path | [FIXED-280](FIXED_ITEMS.md#fixed-280--fifteen-capability-switches-that-governed-nothing-and-one-that-should-have) | **Closed 2026-08-24** — not one of the two readings it offered: fifteen switches governed nothing. `plugin_install` was a real gap, `subagents` an inert switch, and what every gate decides is now a checked field |
| Auto mode has no alignment check | [FIXED-282](FIXED_ITEMS.md#fixed-282--auto-promised-a-review-it-did-not-perform) | **Closed 2026-08-24** — a deterministic check over the turn's own record, with no model in the authority path |
| Nothing owns a set of delegated child tasks | [FIXED-286](FIXED_ITEMS.md#fixed-286--a-task-reported-done-while-the-work-it-delegated-was-still-open) | **Closed 2026-08-25** — a parent parks as `waiting_for_children` and settles on the last child; nothing is inherited downward |
| One brief that splits into routed children | [backlog #23](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort) | Open — the composition half of what BUG-220 raised |
| OpenTelemetry export | [backlog #18](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-medium-effort) | Proposed |
| Deterministic replay | [backlog #20](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort) | Proposed — [ADD-08](TO_BE_ADDED.md#add-08--event-sourced-deterministic-replay) |
| Credential masking with sentinel substitution | [backlog #19](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-medium-effort) | Proposed — [ADD-10](TO_BE_ADDED.md#add-10--credential-cloaking-and-ast-level-sanitisation) |
| WebAuthn step-up, hardware root of trust | [ADD-14](TO_BE_ADDED.md#add-14--a-hardware-root-of-trust), [ADD-15](TO_BE_ADDED.md#add-15--webauthn-step-up-instead-of-a-typed-phrase) | Proposed — **owner decisions** |

**No blocking item.** *Recoverable* and *auditable* were the two properties
Raiker's own documentation claimed and an owner could not reach; both closed on
2026-08-23. GEP-04 turned out to be a third of the same kind — *controllable*:
fifteen switches an owner could hold that decided nothing — and closed on
2026-08-24 along with GEP-01, which was designed with GEP-04's two new call sites
in view exactly as GEP-04 said it should be. Everything left in P2 is Raiker being
ahead and wanting to be further ahead. BUG-218 — the only mode where an action
runs with no human in the loop — closed on 2026-08-24 with a check that is
deterministic in both halves. BUG-220 — a parent that reported done while a child was parked — closed on
2026-08-25. **Backlog #23 is next**: the composition half, one brief that splits
into children routed to Chat or Build, under the same ownership.

## P3 — A capable coding/build agent

| Item | Where | State |
|---|---|---|
| Checkpoint rewind | [FIXED-270](FIXED_ITEMS.md#fixed-270--checkpoint-rewind-was-built-registered-tested-and-unreachable) | **Closed 2026-08-23** — shared with P2, and this is where an owner feels it |
| Interactive, background and remote execution in the sandbox | [BUG-194](TO_BE_FIXED.md#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Open — POSIX-only PTY and reattachment |
| Filtered domain egress unproven | [backlog #6](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-high-effort) | Open |
| Remote supervisor install lifecycle | [backlog #22](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort) | Open |
| No resolved call graph; textual find-references | [B10](GAP_BUILD_CHAT.md#b10--no-language-intelligence) | Open by design, stated |
| Polyglot linker rules and polymorphic resolution | [ADD-25](TO_BE_ADDED.md#add-25--post-stage-j-memory-expansion), [FME-04](MEMORY_RELIABILITY_PLAN.md#fme-04--polyglot-linker-rules-and-polymorphic-resolution) | Future — evidence-labelled Python/Rust and TypeScript/service boundaries after snapshot isolation |
| LSP surface | [BUG-227](TO_BE_FIXED.md#bug-227--there-is-no-lsp-surface-for-a-plugin-to-contribute-to) | Open — **decide whether Raiker wants one at all** |
| Worktrees for parallel work | [backlog #27](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md) | Rejected — checkpoints answer the same need better for undo |
| GAP-BUILD remainder | [GAP-BUILD](GAP_BUILD_CHAT.md#gap-build--what-build-needs-to-stand-against-a-class-leading-coding-agent) | 7 items (5 open, 2 partial) |

**No blocking item.** A coding agent that could write but not undo made the owner
the undo mechanism; the rewind closed on 2026-08-23. The largest remaining item
is BUG-194 — interactive, background and remote execution inside the sandbox.

## P4 — An extensible governed agent platform

| Item | Where | State |
|---|---|---|
| MCP protocol revision | [FIXED-274](FIXED_ITEMS.md#fixed-274--the-mcp-client-was-five-protocol-revisions-behind) | **Closed 2026-08-23** — `2026-07-28` offered, three older revisions accepted, the negotiated one shown. What Raiker *uses* of it is still the bounded session |
| Streamable-HTTP session semantics, remote OAuth, `server/discover` | [BUG-234 remainder](TO_BE_FIXED.md#bug-234--the-remainder-what-raiker-does-not-use-of-the-mcp-revision-it-now-speaks) | Open — no longer blocked by the revision, now their own work |
| Channel routing modes and approval relay | [FIXED-298](FIXED_ITEMS.md#fixed-298--a-paired-channel-could-still-only-record-a-message) | **Closed 2026-08-27** — record-only, new turn, tool-free side question, interrupt/steer, and exact owner approval response ship |
| Four hook handler types refused | [BUG-226](TO_BE_FIXED.md#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Open — `prompt` first; it needs no new surface |
| Hook lifecycle coverage | [backlog #14](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-medium-effort) | Open — four of the fifteen worth adding; `ConfigChange` is the differentiator |
| Agent Skills standard conformance | [backlog #13](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-low-effort), [ADD-21](TO_BE_ADDED.md#add-21--conformance-to-the-agent-skills-open-standard) | Proposed — interoperability with ~40 products for very little work |
| MCP Apps (SEP-1865) | [backlog #28](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#low-priority-medium-effort), [ADD-24](TO_BE_ADDED.md#add-24--mcp-apps-sandboxed-server-contributed-interactive-ui) | Proposed — **and it supersedes plugin panels**; build at most one |
| Plugin panels | [BUG-228](TO_BE_FIXED.md#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Open, and **reassessed**: the row above is the better answer |
| MCP tool search / deferred tool schemas | [backlog #16](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-medium-effort) | Proposed |
| Owner-authored slash commands | [FIXED-299](FIXED_ITEMS.md#fixed-299--skills-had-no-owner-authored-command-handle) | **Closed 2026-08-27** — active skills can have owner-scoped command handles that grant nothing |
| Autonomous skill creation with a review gate | [ADD-06](TO_BE_ADDED.md#add-06--a-zero-trust-gate-for-self-authored-skills) | Proposed |
| Governed browser control | [backlog #24](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort), [ADD-23](TO_BE_ADDED.md#add-23--governed-browser-control-as-a-narrow-tool-set) | Proposed — **an owner decision** |
| Live-spec sign-in | [BUG-229](TO_BE_FIXED.md#bug-229--most-live-specs-sign-in-only-on-an-empty-workspace) | Open |

**No blocking item.** The protocol upgrade landed on 2026-08-23 and unblocked
three rows at once; each is now ordinary work rather than a dependency. The
highest-leverage item left is MCP Apps, which supersedes plugin panels — build at
most one of the two.

---

## Model choice — the cross-cutting requirement

Not a pillar; a constraint on all four. It is **met today** and the open items
are quality rather than reach.

| Item | State |
|---|---|
| Three adapters over ten provider families, local to hosted | **Met** |
| Exact-model readiness proven before a turn | **Met** — and ahead of the reference set |
| Owner-ordered fallback with no silent hosted fallback | **Met** |
| No mock or test provider can be constructed | **Met**, and deliberately |
| Shipped list prices are unverified defaults | Open, stated, low severity |

---

## The order to work in

Derived from the pillar analysis, not from the backlog's own ordering — the
backlog sorts by priority and effort, this sorts by *how many pillars an item
unblocks*.

| Order | Item | Unblocks | Why here |
|---|---|---|---|
| 1 | **Trace the fifteen** ([FIXED-280](FIXED_ITEMS.md#fixed-280--fifteen-capability-switches-that-governed-nothing-and-one-that-should-have)) | P2 | **Done 2026-08-24.** Cheap, and it did reclassify: the finding was not an ungoverned action but fifteen inert switches, which is a different defect and a worse one for this product |
| 2 | **Checkpoint rewind** ([#1](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | **P2 + P3** | The only item that blocks two pillars, and the executor already exists |
| 3 | **Audit export** ([#2](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | P2 | Same shape: built, never routed |
| 4 | **Remove the second egress path** ([#3](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | P2 | Deleting code, and it removes a live liability |
| 5 | **Oversize checkpoint honesty** ([#4](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | P2 + P3 | Makes an approval stop promising what it cannot deliver |
| 6 | **MCP protocol revision** ([#9](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-medium-effort)) | P4 | One change, three rows |
| 7 | **Semantic memory** ([MEM-10](MEMORY_RELIABILITY_PLAN.md#mem-10--semantic-recall-is-selectable-but-a-default-install-has-nothing-to-select)) | P1 | **Provider path done 2026-08-26** ([FIXED-283](FIXED_ITEMS.md), [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered)): both halves reused the governed executor rather than adding a shortcut. The keyless curated-GGUF leg remains |
| 8 | **Shared admission helper** ([FIXED-279](FIXED_ITEMS.md#fixed-279--eight-copies-of-one-governance-check-and-two-of-them-had-already-drifted)) | P2 + P4 | **Done 2026-08-24**, and moved up rather than waiting: GEP-04 added two call sites that needed it, so designing it once meant designing it now |

**Every item in the top group is closed.** Item 7 — semantic memory — closed on
2026-08-25, and the way it closed is the finding: it was priced as the expensive
one and turned out to be items 2 and 3 again, a capability built and never
routed. Four of the eight rows above were that same shape.

Items 2–5 were all **High priority, Low effort**, and together they closed the
gap between what Raiker's documentation says it is and what an owner can
actually reach. Items 1 and 8 closed the gap between what an owner is *shown*
they control and what they do.

**The lesson to carry forward.** Five of these were built code with no route to
it. That is not a coincidence and it is not laziness: a capability with an
executor, a gate, a threat model and a passing acceptance suite reads as *done*
in every artefact a builder checks. The only artefact that would have caught it
is the one an owner uses. Before pricing the next hard item, look for its
executor.

---

## Keeping this honest

This document is a re-cut, so it has no content of its own to go stale — but it
can go **incomplete**, which is worse, because it reads as a complete picture.

When an item is opened or closed in [`TO_BE_FIXED.md`](TO_BE_FIXED.md),
[`TO_BE_ADDED.md`](TO_BE_ADDED.md),
[`GAP_BUILD_CHAT.md`](GAP_BUILD_CHAT.md),
[`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md),
[`GOVERNANCE_ENTRY_PATHS.md`](GOVERNANCE_ENTRY_PATHS.md) or
[`REFERENCE_PLATFORM_COMPATIBILITY.md` §5](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog),
it belongs in exactly one pillar here.

**The canonical priority order stays in the backlog.** This document says what an
item is *for*; the backlog says what it *costs* and in what order. Where the two
orderings differ — as they do above — the difference is the point, and the reason
is stated in the last column.
