# Build workspace

> **Canonical Build requirements and workspace specification.** This document
> defines the target contract and current interaction design. Current
> implementation status and evidence remain in the documents it links.

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Build is Raiker's coding surface in the local web dashboard: one conversation,
pointed at one repository, with the agent's latitude stated on the composer
instead of buried in settings. It lives under **Work** in the navigation, beside
Chat.

Build adds **no new authority**. It composes surfaces that already exist — the
governed prompt stream, per-capability decision modes, the approval inbox, the
task scheduler, and projects — into one place. Every claim the page makes about
what the agent may do is a claim the runtime will keep, because the page sets the
runtime's own controls rather than describing an intention.

The shared composer also has an **approval policy** pill: **Manually approve**,
**Automatically approve**, or **Skip all approvals**. This is deliberately a
different control from Plan/Edit/Auto: the runtime modes choose the planning and
decision-mode posture for a coding turn, while the approval policy chooses
whether an otherwise eligible action waits for a user interaction. In particular,
Skip omits only that interaction and generated preview; it never bypasses
project/path confinement, hunk/context validation, rollback, managed policy,
sandbox or security boundaries, restricted command policy, or critical holds.

## The three modes

The composer's mode picker is the centre of the page. Each mode is a concrete,
**turn-scoped** posture assembled from two per-turn controls sent with the
prompt: `planning_mode`, and a `capability_modes` map covering the capabilities a
coding turn acts through (`file_write_execution`, `patch_apply_execution`,
`shell_execution`, `process_execution`).

| Mode | Turn posture sent | Planning | What the runtime does |
|---|---|---|---|
| **Plan** | `deny` on the four | `always` | Research and propose only. A write proposed anyway is refused by the runtime under `denied_by_turn_posture`, not by prompt wording. |
| **Edit** | `ask` on the four | default | Every file write, patch, and command becomes a pending approval you accept or reject, and the unattended approval modes cannot swallow it. |
| **Auto** | none | default | The turn adds no restriction of its own and runs under the owner's standing permissions. |

Mode help is available on hover and keyboard focus, rather than occupying
permanent composer space. This keeps the explanation accessible without
competing with the project scope, approval policy, model, and action controls.

Notes that keep the mapping honest:

- **A mode may only tighten.** `ask` and `deny` are the only values a turn may
  name for itself; the prompt contract refuses `allow` and `auto`, and the broker
  refuses them again independently. A turn can therefore never grant itself
  authority the owner has not already given it, which is why no ceremony is
  required to select one (BUG-70 / FIXED-155).
- **A mode changes no standing permission.** The chips issue no
  `/api/capability-modes/` write at all. Widening a capability stays on the
  Permissions page, under the step-up — a recorded reason, and a threat-model
  acknowledgement where the capability demands one.
- **Auto therefore does exactly as much as the owner already allowed**, so the
  composer reads the standing modes (read-only) and states what it found rather
  than implying unprompted execution: *"Every write capability is set to Ask, so
  every change will still be proposed to you."*, with **Change in Permissions →**.
- Read capabilities are deliberately excluded from the set a mode covers, so
  Plan stays useful — it removes the ability to act, not the ability to look.
- The posture is persisted with a turn parked on an approval, so a resume
  continues under the posture it was sent with rather than under whatever the
  standing modes say by then.
- `Shift+Tab` cycles Plan → Edit → Auto without leaving the prompt.
- **Build opens in Auto.** Auto is the only mode that sends no override, so a new
  conversation runs under exactly the owner's standing permissions. Opening in
  Edit — as Build used to — meant the surface silently tightened *below* what the
  owner had set on the Permissions page, on every new conversation, with nothing
  saying so. Choosing Plan or Edit stays a deliberate act of tightening.

## The operating protocol

A Build turn carries a second system message that a Chat turn does not: the
compressed operating protocol from
[`RAIKER_BUILD_PROCESS.md`](../architecture/RAIKER_BUILD_PROCESS.md). Build is where a turn
changes a repository, and the failures that matter there are process failures
rather than knowledge failures — committing to the first plausible story, editing
a file from memory instead of reading it, reporting a success that was never
confirmed.

The prompt envelope carries `surface`, validated against a closed set
(`chat` / `build`) at the HTTP schema, in the envelope builder, and again in the
gateway, which writes it into `prompt_received`. So the audit trail states which
protocol a turn ran under rather than leaving it to be inferred, and an unknown
value is refused (`invalid_prompt_surface`) rather than read as Build.

**The surface selects a working method and never authority.** Every capability
gate, decision mode, approval and boundary is identical with or without it; the
tool set offered to the model is asserted identical on both surfaces
(`tests/test_build_operating_protocol.py`).

Accepting a proposed change from the transcript uses the ordinary approval
route, and the action is **re-governed before anything runs** — the capability
gate, decision mode, policy review and the resolver's posture are all re-checked
at execution time, so a recorded decision is never treated as permission it
already had. Accepting a proposed **file change** then applies it once, with the
previous contents checkpointed first; accepting anything else records the
decision and executes nothing. The decisions rail reports which happened after
the fact, so "Accept" is never read as "already applied".

Accepting also **continues the turn**. The conversation that proposed the change
kept its working state, so the decision is handed back to the model as the result
of its own tool call — the real result when the change was applied, an explicit
refusal when it was rejected — and the same turn streams on from there, in place.
Nothing has to be re-asked, and the transcript shows one exchange rather than
two. A turn continues at most once per decision.

## Repositories

A coding chat can be pointed at one repository. Connecting one is bookkeeping,
not access:

- **Local folder** — a subpath that resolves inside the Raiker workspace.
  Anything resolving outside it fails closed. The selected folder's path rides
  each turn as a workspace-path attachment, so its contents reach the model as
  bounded, untrusted-labelled context through the existing governed attachment
  path.
- **GitHub `owner/repo`** — the coordinate is validated locally and stored. The
  connect route makes **no network call**. Content is read through the brokered
  `github_read` tool under the `connector_github_runtime` gate and its decision
  mode; that gate is disabled/fail-closed until the owner enables it, and the
  repository panel reports the gate's real state, decision mode, and whether an
  owner token is configured rather than implying that connecting granted reads.
  Because there is no attachment handle for a remote repository, the coordinate
  is stated as a one-line preamble in the prompt itself — composed in the browser
  so the transcript shows exactly what was sent.

References are per account. One account cannot list, select, or disconnect
another's. Disconnecting forgets the reference and never touches the folder or
the remote. Both transitions append `code_repo_connected` /
`code_repo_disconnected` audit events.

Connecting the **first** repository also selects it. An owner who has just named
the folder they want to work in has said which repository this is, and leaving
Build on *No repository* until they find a second control reads as the connect
having failed. It is deliberately only the first: an existing active repository
is a choice, and adding a second must never silently move the work onto it.

### Requirements contract: verified issue-to-PR work

**Owner-approved direction, 2026-10-15. This is the Build target, not a claim
that the whole workflow is shipped today.** Build is Raiker's repository-focused
coding agent for one owner. Its first competitive milestone is a bounded,
isolated, independently verified issue-to-PR loop: take one owner-authorised
repository issue, make and validate a focused change in an isolated execution
target, then open a reviewable PR when that exact authority was granted. It
must never manufacture a successful completion from a plausible-looking patch.

The target is outcome quality comparable to a leading coding agent, not a
marketing parity claim. Raiker may claim equivalence or class-leading quality
only after matched, independently evaluated outcome evidence exists.

#### Requirement boundaries and precedence

This section owns Build requirements. The following documents own adjacent
concerns and must not be contradicted:

| Need | Authoritative source |
|---|---|
| Turn-level coding method | [Raiker Build process](../architecture/RAIKER_BUILD_PROCESS.md) |
| Runtime authority, decisions and tool mediation | [Decision modes](../architecture/DECISION_MODES_SPEC.md) and [tools and permissions](../architecture/TOOLS_AND_PERMISSIONS_SPEC.md) |
| Current implementation availability and limits | [Implementation status](../architecture/IMPLEMENTATION_STATUS.md) and [known limits](../architecture/KNOWN_LIMITS.md) |
| Requirement delivery, status and evidence | [Build/Chat gap ledger](BUILD_WORKSPACE_SPEC.md), [PAA-12](PERSONAL_AUTONOMOUS_AGENT_SPEC.md), and [competitive evidence](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) |
| Candidate release qualification | [Release acceptance scenarios](../plans/TESTING.md) |

When current-state evidence and this target contract differ, the current-state
evidence governs what may be claimed today; this contract governs what a future
Build implementation must satisfy. An open BUG or planned item remains open or
planned until its linked evidence closes it.

#### Product outcome

Build must make a coding task legible and controllable from delegation through
review. At every point the owner can answer: what issue and repository is being
changed, where code actually executes, what authority is active, what changed
and was checked, and which external action is awaiting approval or occurred.

The standard happy path is:

`delegation → bound target → inspect and plan → focused change → validate → review → authorised PR → verified receipt`

Each arrow represents durable, inspectable state rather than model prose. A
failure, revocation, budget limit or ambiguous external effect must leave the
owner with the actual state and a safe next action.

The completed workflow will:

1. capture the delegated issue, repository, allowed branch pattern, budget,
   allowed operations and explicit **no merge** rule;
2. name and validate one execution target before work begins: host, workspace
   root, repository identity/fingerprint, branch or worktree, and sandbox
   posture;
3. treat the issue and repository instructions as untrusted input, then plan
   the scoped change before invoking write-capable tools;
4. execute write-capable work only in the selected target. Parallel write work
   receives separate worktrees and branch ownership; commands, reads, diffs,
   checkpoints and receipts remain bound to that target;
5. revalidate authority, credentials and the target fingerprint on resume, and
   stop safely when the owner revokes or changes the grant;
6. run the declared test, lint, type-check and build evidence where applicable,
   with an independent validator or destination read-back before reporting
   `completed_verified`;
7. review the exact resulting patch with static, secret and repository-policy
   checks plus selected model review, storing deduplicated findings by patch
   fingerprint; and
8. push and create a PR only under the matching grant, retain the provider
   receipts, and leave merging to the owner.

Until those checks exist, Build must report the truthful alternative:
`completed_unverified`, `partially_completed`, `blocked` or `outcome_unknown`.
The detailed delivery and evidence requirements are [PAA-12](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-01](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-02](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-04](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-05](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
and release scenarios [RR-39/RR-40](../plans/TESTING.md).

#### Functional requirements

| ID | Requirement |
|---|---|
| BR-01 | **Explicit task delegation.** Capture the repository identity, issue/task, allowed operations, branch pattern, budget/limits and whether push or PR creation is allowed. A read grant never writes, a PR grant never merges, and a schedule cannot create or widen authority. |
| BR-02 | **Bound execution target.** Before a write-capable turn starts, create or select a target containing host, workspace root, repository identity/fingerprint, branch/worktree and sandbox posture. The displayed project and path must match the actual executor; a missing, moved, stale or mismatched target fails closed. |
| BR-03 | **Isolated concurrent work.** Concurrent write-capable tasks use separate worktrees and owned branches. No task silently changes another task's checkout, branch, uncommitted owner work or diff. Cancellation and cleanup preserve owner work outside the task worktree. |
| BR-04 | **Untrusted repository input.** Issues, pull requests, comments, commits, repository files and tool output cannot select credentials, alter decision modes, bypass policy, widen scope or authorise an effect. Repository instructions may constrain the plan only within owner and Raiker policy. |
| BR-05 | **Inspect and plan before mutation.** Inspect sufficient repository context to state intended scope, files, validation approach and unresolved assumptions. Plan mode remains read/propose only; writes follow runtime decision and approval rules, not prompt instructions. |
| BR-06 | **Focused governed execution.** Mediate every file write, patch, command and process launch through runtime policy, capability gates and approvals. Bind commands, reads, patches, diffs, checkpoints and receipts to one target; do not treat a broad shell or Git credential as an implicit grant for unrelated actions. |
| BR-07 | **Durable recovery and revocation.** On resume, revalidate delegation, relevant credential/installation, permission, budget and target fingerprint. Stop, revocation, expiry or a material scope change prevents further work at a safe boundary; ambiguous consequential effects are reconciled before retry. |
| BR-08 | **Evidence-based validation.** Run declared relevant tests, lint, type checks, builds and repository validators. An independent validator or destination read-back must confirm acceptance conditions before `completed_verified`; model assertion, clean-looking diff or a started command is insufficient. |
| BR-09 | **Truthful outcomes.** Distinguish `completed_verified`, `completed_unverified`, `partially_completed`, `blocked`, `failed`, `stopped` and `outcome_unknown`. Name evidence, remaining work, failed/omitted checks and ambiguous effects; never collapse an unverified result into success. |
| BR-10 | **Exact-patch review.** Review the exact commit/diff with static and secret checks, repository-policy/architecture checks, independent validators and selected model review where configured. Findings carry severity, confidence, linked range, evidence and next step, and are stored by patch fingerprint to prevent duplicate noise. |
| BR-11 | **Bounded repair.** A repair stays within the original delegation and budget, uses a fresh identified target/branch where policy requires, then is revalidated and rereviewed. Build never enters an unbounded review–repair loop or merges automatically. |
| BR-12 | **Authorised GitHub completion.** Push and PR creation require live matching delegation and rechecked repository/installation identity. Record branch, commit, PR identifier, URL and provider confirmation; push output alone does not prove a PR exists. Merge, protected-branch changes, repository configuration and workflow changes remain human-controlled. |

#### Quality and evidence requirements

Build must fail closed on ambiguous authority, target or provider state; retain a
trace from delegation through target fingerprint, approvals, diff/commit,
validation, review and external receipt; and allow a reviewer to reproduce the
exact revision, target, checks, model/reviewer configuration, limits and result.
Credentials, tokens and unrelated local files must not enter prompts, traces,
diffs or outcome summaries. Owner-facing status must expose blockers, approvals,
budget and a safe next action without requiring raw logs. Target binding,
isolation, cancellation and recovery require evidence on supported Windows and
Linux paths.

No requirement is complete based only on unit tests or a model transcript. The
candidate workflow must meet [RCD-01](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-02](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-04](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[RCD-05](PERSONAL_AUTONOMOUS_AGENT_SPEC.md),
[PAA-12 and PA-S07](PERSONAL_AUTONOMOUS_AGENT_SPEC.md), and
[RR-39/RR-40](../plans/TESTING.md). Evidence includes
successful and negative cases: wrong repository, stale/moved target, branch
collision, concurrent same-file work, hidden failing tests, secret or
prompt-injection fixture, approval pause, owner revocation, interrupted push,
ambiguous provider result, retry and duplicate-trigger controls.

Build does not authorise automatic merge, protected-branch or repository-setting
changes, unattended authority expansion, an unrestricted shell, credentials in
model context, execution outside a selected target, or a competitor-parity
claim without matched evidence. Current Build capabilities are foundations, not
proof that this whole workflow is shipped; implementation work remains in the
referenced ledgers, including a governed scheduled issue-to-PR runner.

### The execution target (BR-D02)

A Build turn runs against a **target**, not a label: the selected repository's
folder, its identity (GitHub coordinate, or `origin` remote with credentials
stripped), branch and commit, and the command environment. The target is read
from the runtime's own sources (`raiker/control/build_target.py`) and reduced to
a fingerprint over identity, folder, branch and environment. The commit is
recorded but not fingerprinted, because a turn's own commit is not the target
moving; where code is placed is shown but not fingerprinted, because that is
re-measured on a timer.

The gateway records the target for every Build turn and refuses a Build turn
whose selected folder is gone, rather than letting the tools fall back to the
workspace root. The turn's outcome compares the recorded target with the current
one: a branch switched, a folder moved or an environment changed under the turn
is reported and keeps it short of `completed_verified`. The Build header states
the target (`main · 6e99715 · Sandbox`), and `GET /api/code/repos/{repo_id}/target`
returns it.

### Reviewing the patch (BR-D04)

**Changes → Review this patch** reviews the exact uncommitted diff — the change
set a commit would record — with deterministic rules (possible credential,
conflict marker, debugging left in, CI/workflow change, instruction-like text,
source without tests). Each finding names its file and line, evidence and next
step. The review is stored by the patch's SHA-256 fingerprint, so the same patch
returns the same review and any edit is a new one. It reads only; acting on a
finding is an ordinary governed change.

### Reading it (B13)

**Files** on the Build header opens the connected repository beside the
conversation: a resizable, lazily-expanded tree over
`GET /api/code/repos/{id}/browse`, and a read-only viewer over
`GET /api/code/repos/{id}/file`. Below the split it becomes a dismissible sheet
from the left, mirroring the background-work rail on the opposite edge.

Four properties define it, and each is a boundary rather than a rendering
choice:

- **Read-only, structurally.** There is no write path in the module behind it. A
  change to a file is still a proposal the owner accepts, which is what Build's
  whole approval story rests on. Promoting the viewer to an editor would give the
  browser a write path that does not pass through that decision.
- **Confined twice.** Every path resolves through the same `PathAuthority` a turn
  writes through, and is then re-checked against the repository's own root. The
  authority alone would serve anything inside the workspace; the second check is
  what keeps a *repository* reference from becoming a workspace file browser.
- **Lazy.** One directory is read when it is opened. Pointing Build at a large
  repository costs nothing until the owner looks.
- **It states which absence applies.** A GitHub coordinate has no checkout; a
  local folder may have moved. Both are said in words, because an empty tree
  reads as "no files".

Highlighting is the transcript's own locally-shipped, allowlisted scanner: no
CDN grammar, escaped at emit time, a closed tag set. A language the scanner does
not ship renders as plain text with no label — mis-highlighting is a claim about
what a file is, and a wrong claim is worse than none.

## Background work and scheduled agents

The right rail shows what is running and is collapsible, because background work
is context for the conversation beside it rather than a separate destination.
The same inline panel appears in Chat. Approval-blocked items expose a direct
**Review approval** action so the user can move from status to the relevant
approval without hunting through a separate view.

The **Agents** tab schedules standing work — "keep improving the landing page",
"watch the test suite", "surprise me by building a small app". A scheduled agent
is an ordinary task with a cadence:

| Cadence | Behaviour |
|---|---|
| `continuous` | One cycle roughly every 20 minutes, re-arming until stopped |
| `hourly` / `daily` / `weekly` | One cycle per interval, anchored to the first run |
| `background` | A single governed cycle that does not repeat |

Each cycle is **one discrete governed turn**, not an unbounded loop: policy,
capability gates, and approvals apply to cycle 40 exactly as they did to cycle 1,
and the resident scheduler claims due work atomically so two ticks cannot run the
same cycle twice. Re-arming steps forward from the original slot and skips every
elapsed one, so a host that was asleep does not wake up owing a backlog. Stopping
is the existing safe-boundary interrupt, and a stop recorded while a cycle is in
flight is never overwritten by that cycle's result. An unrecognised cadence is
refused server-side with `invalid_recurrence:<value>` rather than being stored as
a one-shot, which would make a "keep going" schedule silently stop after one run.

## Projects

A Build conversation can be filed into a project from the header. Choosing a
project before the first turn is remembered and applied as soon as the session
exists, so the choice never silently does nothing. A project is an organizing
scope: the move grants nothing and only changes the bounded context the chat
receives on its next turn.

## Related documents

- [Decision modes](../architecture/DECISION_MODES_SPEC.md) — the `ask`/`deny`/`allow`/`auto`
  semantics and safety floors the modes rely on.
- [API and contracts](../architecture/API_AND_CONTRACT_SCHEMAS.md) — the `/api/code/repos`
  routes and task cadences.
- [Tools and permissions](../architecture/TOOLS_AND_PERMISSIONS_SPEC.md) — the capabilities a
  coding turn acts through.
- [Event catalog](../architecture/EVENT_CATALOG.md) — the repository reference events.

## Consolidated Build delivery register

This register replaces the Build-specific roadmap and competitive-plan entries
formerly held in `docs/plans/`. Every record states the objective, the reason it
matters, the accepted decision and the evidence needed to close it. **Planned**
does not describe a shipped capability.

| ID / status | Objective | Reason | Accepted decision and closure evidence |
|---|---|---|---|
| BR-D01 / Implemented 2026-10-19 | Gate `completed_verified` on independent checks. | A plausible patch or final model statement is not a completed coding outcome. | Reuse the verification runtime; preserve `unverified`, partial, blocked and unknown outcomes. Close with hidden-test, wrong-path, timeout and read-back faults. **First slice ([FIXED-952](FIXED_ITEMS.md#fixed-952--a-build-change-read-as-done-whether-or-not-anything-checked-it-br-d01-first-slice))**: owner-declared project checks, an outcome read from the turn's own tool actions and command runs, shown under each settled Build turn; hidden-test, stale-check, lookalike-command and timeout faults in `tests/test_build_outcome.py`, and a live `gpt-oss:120b-cloud` turn after [FIXED-953](FIXED_ITEMS.md#fixed-953--an-accepted-build-write-wrote-nothing-and-its-row-read-failed-bug-346). **Closed ([FIXED-954](FIXED_ITEMS.md#fixed-954--a-build-check-counted-wherever-it-ran-and-a-written-file-was-never-read-back-br-d01))**: `run_command` takes a workspace-confined `cwd` stored in plain form on the run, a check run outside the turn's repository folder reads `wrong_directory`, and each written file is read back from disk — a missing destination keeps the turn **Not verified**. |
| BR-D02 / Partly implemented 2026-10-19 | Bind every write-capable turn to a named execution target. | A project label cannot substitute for the actual host, root, repository, branch/worktree and sandbox. | Require target fingerprint/revalidation and separate worktrees for concurrent writes. Close with Linux/Windows, stale target, cancel and same-file concurrency scenarios. **First slice ([FIXED-955](FIXED_ITEMS.md#fixed-955--a-build-turn-named-a-repository-not-the-target-it-ran-against-br-d02-first-slice))**: the target (folder, credential-free repository identity, branch, commit, command environment, code placement) is described with a fingerprint at `GET /api/code/repos/{repo_id}/target` and on the Build header, recorded for every Build turn, and compared by the outcome, so drift is reported rather than verified across; a Build turn whose selected folder is gone is refused before it starts. Still open: separate worktrees and branch ownership for concurrent write-capable turns, revalidation at resume/approval time, and Windows/cancel/same-file concurrency evidence. |
| BR-D03 / Planned | Deliver governed issue-to-PR completion. | A template or connection cannot itself fix an issue, validate it, push, and open a reviewable PR. | Use a stored repository delegation, dedicated branch/workspace, target-bound commands and provider receipts; never merge automatically. Close with the autonomous bug-fix and mid-run revocation scenarios in [Testing](../plans/TESTING.md). |
| BR-D04 / Partly implemented 2026-10-19 | Review an exact patch before PR-quality completion. | Human diff display alone cannot establish repeatable quality or detect duplicate findings. | Run static/secret/policy checks, independent validators and selected model review against a patch fingerprint; proposed repair is bounded and never auto-merges. Close with seeded correctness, regression, secret and prompt-injection cases plus false-positive controls. **First slice ([FIXED-956](FIXED_ITEMS.md#fixed-956--a-patch-was-shown-never-reviewed-and-every-look-was-a-new-look-br-d04-first-slice))**: deterministic secret, conflict-marker, debug-statement, CI/workflow-change, instruction-text and missing-test findings with file, line, evidence and next step, stored by patch fingerprint so the same patch is never reviewed twice; seeded and false-positive cases pass, and **Changes → Review this patch** shows them. Still open: independent validators and selected model review against the same fingerprint, and bounded repair. |
| BR-D05 / Planned | Provide code provenance and signed-review evidence where supported. | A recipient needs to identify what agent/workspace produced a change without trusting a model narrative. | Treat signatures/watermarks as optional evidence that never grants authority and never replaces ordinary Git/review controls. Close with provenance read-back and key/credential redaction tests. |
| BR-D06 / Partly implemented 2026-10-19 | Continuously exercise recovery and fault boundaries. | Coding autonomy that succeeds only in a happy path is not safe to leave running. | Add bounded chaos/fault fixtures to the common testing protocol; preserve run records and block false completion. Close with repeatable injected target, tool, provider and restart failures. **First slice ([FIXED-957](FIXED_ITEMS.md#fixed-957--nothing-proved-an-injected-fault-could-not-read-as-verified-br-d06-first-slice))**: thirteen injected tool, check, provider, folder, read-back and target faults never classify as `completed_verified` (`tests/test_build_fault_boundaries.py`). Still open: the same faults injected into a running host (a real restart mid-check, a provider failing mid-turn) rather than into the classifier's inputs. |
| BR-D07 / Implemented foundation | Retain governed modes, approvals, patch application, commands, repository context, checkpoints and human diff review. | These are the narrow foundations on which the verified loop is built. | Keep the existing shared runtime controls; they may tighten but never bypass the active execution profile or standing policy. Evidence remains current implementation status and the testing protocol. |
