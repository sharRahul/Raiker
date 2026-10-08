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
| [**P2**](#p2--a-governed-ai-agent) | **A governed personal autonomous agent** | Durable goals, personal context, bounded proactive work and verified outcomes; every action is policy-aware, observable, auditable, approval-driven, least-privileged, human-governed, recoverable, verifiable and fail-closed — as properties of the runtime, never as a layer around it |
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

Implementation assessments, each backed by the items below it. **Competitive qualification added 2026-10-05:** historical “no blocker” and completion wording below refers to the recorded implementation scope, not proof of parity. Use [the competitive outcomes](#competitive-outcomes-by-pillar--2026-10-05) and the linked acceptance contract for present competitive claims.

| Pillar | State | The thing in the way |
|---|---|---|
| [**P1**](#p1--a-polished-ai-assistant) Assistant | **Governed recall implemented; comparative quality unverified.** Streaming, attachments, citations, search, export, branching, voice, incognito, projects, local/hosted semantic memory, and managed libraries whose exact file revisions can be recalled by meaning | No blocker. Revision-checked approximate vector lookup now scales recall without reusing an ineligible candidate set |
| [**P2**](#p2--a-governed-ai-agent) Governed agent | **Governance mechanisms implemented; comparative advantage unverified.** Re-governance at execution time, machine identity, measured sandbox boundaries and per-capability threat models are implementation strengths, not evidence that competitors lack controls — and as of 2026-08-23 *recoverable* and *auditable* are reachable rather than asserted. As of 2026-08-24 the owner's switches are checked to actually be switches, and as of 2026-08-25 a task cannot report done over work it delegated | GEP-01, GEP-02, GEP-03, GEP-04, BUG-218 and BUG-220 are closed — GEP-02 by the owner's decision on 2026-09-27 that Stop halts all work in progress. What remains is composition — one brief that splits into routed children (backlog #23) — and the owner decision ADD-14/15 |
| [**P3**](#p3--a-capable-codingbuild-agent) Coding agent | **Closes the loop, and can now undo.** Real patches, real commits, real pushes, a governed terminal in a measured OS boundary, a code map, code review, and a governed rewind | Execution inside the sandbox is foreground-only: no interactive PTY on Windows, no background run that outlives the turn, no reattachment after a restart (BUG-194) |
| [**P4**](#p4--an-extensible-governed-agent-platform) Platform | **Governed, and narrower than the reference set.** Hooks, skills, plugins, channels and MCP all extend without an execution surface of their own | The MCP client negotiates the current revision and now conforms to its transport and reads every shape a tool result may carry ([FIXED-378](FIXED_ITEMS.md#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport), [FIXED-387](FIXED_ITEMS.md#fixed-387--a-tool-result-had-one-shape-and-the-revision-defines-six)). What is left is capability rather than conformance: no incremental SSE streaming, no remote OAuth, no `server/discover`, no MCP Apps, no elicitation |

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
| Vector recall is linear | [FIXED-301](FIXED_ITEMS.md#fixed-301--every-memory-recall-rebuilt-and-linearly-scanned-the-entire-vector-space) | **Closed 2026-08-28** — revision-checked cache, exact ranking below 512 vectors, then bounded approximate lookup with exact re-ranking |
| A natural-language question drops the lexical leg | [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | **Closed 2026-08-26** |
| Retention sweep | [FIXED-284](FIXED_ITEMS.md#fixed-284--nothing-expired-because-the-sweep-the-retention-classes-describe-was-never-offered) | **Closed 2026-08-25** — what is due is shown and the owner confirms it. No daemon, by design |
| Owner-guided summarisation of a range | [FIXED-306](FIXED_ITEMS.md#fixed-306--compaction-was-the-thresholds-decision-and-the-owner-had-no-say) | **Closed 2026-08-29** — **Summarise up to here** on any owner message, sharing the turn path's summarise-and-record step so `PreCompact` governs both |
| Post-Stage-J temporal tiers and bounded graph context | [ADD-25](TO_BE_ADDED.md#add-25--post-stage-j-memory-expansion), FME-02/FME-03 | Future — begins only after Stage J evidence and atomic snapshot publication |
| Premium responsive workspace shell | [ADD-26](TO_BE_ADDED.md#add-26--a-premium-responsive-workspace-shell) | **Closed 2026-08-25** — semantic palette, desktop reflow, compact overlay drawers, and 208 light/dark captures through 8K |
| The owner's own documents | [FIXED-289](FIXED_ITEMS.md#fixed-289--uploaded-files-had-nowhere-to-live-and-build-inherited-a-project-nothing-on-screen-named), [FIXED-294](FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words) | **Closed 2026-08-26** — managed files have lexical and semantic passages with provenance to the exact active revision |
| A structured question to the owner mid-turn | [FIXED-308](FIXED_ITEMS.md#fixed-308--raiker-could-ask-permission-and-could-not-ask-what-you-meant) | **Closed 2026-08-29** — the model can ask *which did you mean*, and the answer carries no authority. Its prerequisite, [FIXED-307](FIXED_ITEMS.md#fixed-307--four-risk-bands-no-definitions-and-two-of-them-unreachable), gave the four risk bands definitions and made `low` and `critical` reachable |
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
| The stop switch's scope is undefined for read paths | [FIXED-603](FIXED_ITEMS.md#fixed-603--the-stop-switch-could-not-see-the-answer-it-was-pressed-to-stop) | **Closed 2026-09-28** — the owner decided: Stop halts every answer, Build turn, routine, task and command in progress, whether or not it leaves the machine |
| An empty gate table means three different things | [FIXED-544](FIXED_ITEMS.md#fixed-544--a-new-account-was-fail-closed-about-reading-its-owners-own-repository) | **Closed 2026-09-15** — the owner decided the three resolutions stay; fresh accounts gained a selective, versioned baseline instead |
| `NESTED_BOUNDARIES_ARCHITECTURE.md` overstates the architecture | [FIXED-612](FIXED_ITEMS.md#fixed-612--the-architecture-named-one-chokepoint-and-the-code-has-two) | **Closed 2026-09-28** — the section names both chokepoints and which kind of action takes which |
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
| No resolved call graph; textual find-references | [B10](GAP_BUILD_CHAT.md#b10--no-language-intelligence) | Closed 2026-09-03 as [FIXED-366](FIXED_ITEMS.md#fixed-366--build-could-read-a-repository-and-not-understand-it). Matching stays textual by design and says so; symbols, exact-name definitions and parse diagnostics ship |
| Polyglot linker rules and polymorphic resolution | [ADD-25](TO_BE_ADDED.md#add-25--post-stage-j-memory-expansion), FME-04 | Future — evidence-labelled Python/Rust and TypeScript/service boundaries after snapshot isolation |
| LSP surface | [BUG-227](FIXED_ITEMS.md#fixed-366--build-could-read-a-repository-and-not-understand-it) | Closed 2026-09-03 — **decided: no**. B10's tool set delivers what Build needed without a language-server subprocess, and both plugin specs state what that costs |
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
| Three hook handler types refused | [BUG-226 remainder](TO_BE_FIXED.md#bug-226--three-of-the-five-hook-handler-types-do-not-exist), [FIXED-303](FIXED_ITEMS.md#fixed-303--prompt-hooks-needed-a-model-call-without-a-private-authority-path) | Open remainder — bounded tool-free `prompt` handlers ship; `http`, `mcp_tool` and `agent` remain refused pending their named governed surfaces |
| Hook lifecycle coverage | [FIXED-304](FIXED_ITEMS.md#fixed-304--owner-setting-changes-had-no-hookable-governance-boundary), [FIXED-305](FIXED_ITEMS.md#fixed-305--the-three-remaining-worth-adding-hook-events-had-no-call-site) | **Closed 2026-08-28** — `ConfigChange` decides on authenticated owner-setting writes; `Notification`, `PostToolBatch` and `InstructionsLoaded` observe with content-free payloads. Twenty of the reference's thirty-one, which is the ceiling the spec assessed as worth reaching |
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
| 2 | **Checkpoint rewind** ([#1](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | **P2 + P3** | The only item that blocks two pillars, and the executor already exists. **Fully closed 2026-08-29**: the route landed first, and [FIXED-315](FIXED_ITEMS.md#fixed-315--the-one-control-that-makes-an-agent-safe-to-leave-running-was-in-another-route) put the ask on the turn that caused the change, which is the half P3 actually needed |
| 3 | **Audit export** ([#2](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | P2 | Same shape: built, never routed |
| 4 | **Remove the second egress path** ([#3](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | P2 | Deleting code, and it removes a live liability |
| 5 | **Oversize checkpoint honesty** ([#4](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-low-effort)) | P2 + P3 | Makes an approval stop promising what it cannot deliver |
| 6 | **MCP protocol revision** ([#9](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#high-priority-medium-effort)) | P4 | One change, three rows |
| 7 | **Semantic memory** (MEM-10) | P1 | **Provider path done 2026-08-26** ([FIXED-283](FIXED_ITEMS.md), [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered)): both halves reused the governed executor rather than adding a shortcut. The keyless curated-GGUF leg remains |
| 8 | **Shared admission helper** ([FIXED-279](FIXED_ITEMS.md#fixed-279--eight-copies-of-one-governance-check-and-two-of-them-had-already-drifted)) | P2 + P4 | **Done 2026-08-24**, and moved up rather than waiting: GEP-04 added two call sites that needed it, so designing it once meant designing it now |

**Every item in the top group is closed.** Item 7 — semantic memory — closed on
2026-08-25, and the way it closed is the finding: it was priced as the expensive
one and turned out to be items 2 and 3 again, a capability built and never
routed. Four of the eight rows above were that same shape.

Items 2–5 were all **High priority, Low effort**, and together they closed the
gap between what Raiker's documentation says it is and what an owner can
actually reach. Items 1 and 8 closed the gap between what an owner is *shown*
they control and what they do.

**A sixth, on 2026-08-29.** The rewind route that closed item 2 was reachable
from the Checkpoints page and nowhere else, so undoing the turn that broke
something still meant leaving the conversation — a route to the capability, but
not from where the capability is needed. Closed as
[FIXED-315](FIXED_ITEMS.md#fixed-315--the-one-control-that-makes-an-agent-safe-to-leave-running-was-in-another-route),
with the same finding one level in: **a route is not the same as a route from
the place the owner is standing.** The turn-coordinate work beside it
([FIXED-316](FIXED_ITEMS.md#fixed-316--every-turn-coordinate-was-a-dead-end)) was
the same shape a third time — three surfaces already carried the coordinate, one
of them all the way into the web app's own types, and nothing accepted one.

**A seventh, on 2026-08-30, and it is the same shape a fourth time.**
[FIXED-321](FIXED_ITEMS.md#fixed-321--build-could-change-a-repository-and-never-show-it)
— the file explorer Build never mounted — was one component away from existing:
`ProjectExplorer` was built, tested, and rendered on Projects, and Build showed
its owner nothing of the repository it was changing. What was genuinely missing
was two reads, not a panel.

[FIXED-322](FIXED_ITEMS.md#fixed-322--permissions-said-off-about-a-capability-that-would-have-run)
is the *inverse* of the lesson and worth stating separately: not a capability
with no route, but a **route that described the capability wrongly**. FIXED-279
had already put the one rule in one place; it just had not reached the read the
Permissions page is built from, so the page an owner decides from said **Off**
about a capability the runtime would have run. Looking for the executor would not
have caught it. Only using the page would.

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
[`GOVERNANCE_ENTRY_PATHS.md`](GOVERNANCE_ENTRY_PATHS.md) or
[`REFERENCE_PLATFORM_COMPATIBILITY.md` §5](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog),
it belongs in exactly one pillar here.

**The canonical priority order stays in the backlog.** This document says what an
item is *for*; the backlog says what it *costs* and in what order. Where the two
orderings differ — as they do above — the difference is the point, and the reason
is stated in the last column.

## Decision statement — use pillars for dependencies (2026-10-05)

**Decision — documentation authority clarification.** Use this map to explain
which user outcome an item serves; use current canonical ledger rows and
verified closure records to decide whether it is open. Preserve the historical
ordering above. Do not restart closed work or select a new expansion merely
because an old pillar summary still calls it a blocker.

**Reason and alternatives.** The map deliberately repeats references, not the
full evidence. Promoting its old counts or policy labels to a separate backlog
would create competing priorities. In particular, GAP-CHAT C2/C3 already record
completed governed connector/memory behavior, and ADD-24 records that its
protocol-version prerequisite was lifted.

**Implementation consequence.** Prioritize current boundary and release-evidence
gaps by severity, then dependencies and effort. Future collaboration/browser/TEE
scope stays a proposal; the map cannot approve it. Review the dependent pillar
when a ledger item closes, but retain the original rationale as history.
References: [current plan index](README.md),
[Build/Chat clarification](GAP_BUILD_CHAT.md#decision-statements-added-2026-10-05),
[proposal decisions](TO_BE_ADDED.md#decision-statements-added-2026-10-05),
[release sign-off](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#139-decision-sign-off-and-definition-of-complete).

## Competitive outcomes by pillar — 2026-10-05

**Decision and reason.** Treat the state descriptions above as scoped implementation history. Competitive leadership requires [COMPETITIVE_READINESS_DEMONSTRATION_AND_EVIDENCE.md](COMPETITIVE_READINESS_DEMONSTRATION_AND_EVIDENCE.md); neither “no blocker” in an old row nor closed infrastructure work proves parity. This qualifies unsupported superiority language without withdrawing recorded fixes.

| Pillar | What Raiker must demonstrate | Evidence required |
|---|---|---|
| P1 Assistant | Complete research/document work; accurate scoped recall across restart; clear first-run and error journeys | CR-03/04/09/10/12: source-grounded artifact validators, actual recall context/provenance, lifecycle exclusions, user observations and interaction captures |
| P2 Governed agent | Finish multistep work under declared authority; pause, resume, cancel and recover with truthful state | CR-01/05/07/11: real entry-point traces, approval-to-effect correlations, fault barriers, denied-effect checks and durable terminal records |
| P3 Coding/build | Independently solve bug, feature, refactor and test tasks in the correct repository and produce a usable handoff | CR-08/09/11: frozen repositories, withheld validators, full diffs, failure-to-green logs, restart/rewind evidence and unrelated-change review |
| P4 Platform | Install and use supported integrations/extensions, then revoke or update them without alternate authority | CR-03/06/07: independent extension fixtures, destination receipts, trust-change review, disabling/uninstall tests and complete initiator coverage |
| Model choice | Same supported workflows across declared local/private/hosted configurations | CR-02: support matrix, real tool-using completions, routing/egress records and failures/fallbacks; distinguish cloud-backed Ollama from local inference |

Map work to existing canonical BUG/ADD/DEC records. Prioritise completed work and recovery, then reliable integrations/memory/scheduling and declared model coverage; do not use this order to bypass earlier security or runtime dependencies. Attach evidence levels per scenario, not a single maturity label to the whole pillar.

## Personal-agent outcomes and dependencies — 2026-10-07

The four pillars now serve the [personal-agent direction](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md).
New work is tracked in the [PAA plan](PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md),
not silently inserted into older “done” assessments.

| Pillar | Added outcome responsibility | PAA dependencies |
|---|---|---|
| P1 Assistant | Relevant inspectable personal context and usable progress/results | PAA-03/07 |
| P2 Personal autonomous agent | Durable goals, bounded proactivity, safe recovery and independently verified outcomes | PAA-01/02/04/08 |
| P3 Coding/build agent | Coding is a personal-goal workflow with repository validation and clear handoff | PAA-02/07/08; existing GAP-BUILD |
| P4 Platform | Confirmed connector effects, isolated browser, channels and reviewed reusable procedures | PAA-05/06/09/10; existing ADD dependencies |

PAA-11 verifies the advertised host/model configurations and competitive claims.
Work in phase dependency order without bypassing unresolved release defects or
existing deployment/security decisions. A target acceptance does not supersede
historical evidence or imply feature completion.

## Personal-agent usability task ownership — 2026-10-08

[UX-01–UX-12](PERSONAL_AGENT_UX_IMPLEMENTATION_PLAN.md) link reasons and decisions
to implementable experience work. P1 owns understandable intake, personal
context, progress and usable results (UX-02/03/07/08). P2 owns accurate goal and
approval/recovery/control views (UX-04/05/06/09). P3 retains coding continuity
and usable Build results (UX-07/10). P4 supplies shared read models and extension
availability without new authority (UX-01). UX-11/12 apply accessibility and
observed usability across all pillars. PAA-07 owns the resulting experience;
backend dependencies and RR qualification are not bypassed by frontend polish.
