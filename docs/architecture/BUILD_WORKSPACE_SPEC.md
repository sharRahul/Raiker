# Build workspace

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
[`RAIKER_BUILD_PROCESS.md`](RAIKER_BUILD_PROCESS.md). Build is where a turn
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

- [Decision modes](DECISION_MODES_SPEC.md) — the `ask`/`deny`/`allow`/`auto`
  semantics and safety floors the modes rely on.
- [API and contracts](API_AND_CONTRACT_SCHEMAS.md) — the `/api/code/repos`
  routes and task cadences.
- [Tools and permissions](TOOLS_AND_PERMISSIONS_SPEC.md) — the capabilities a
  coding turn acts through.
- [Event catalog](EVENT_CATALOG.md) — the repository reference events.
