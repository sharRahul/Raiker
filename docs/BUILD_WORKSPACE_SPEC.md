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

## The three modes

The composer's mode picker is the centre of the page. Each mode is a concrete
posture assembled from two governed controls: the per-turn `planning_mode` sent
with the prompt, and the standing **decision mode** on the capabilities a coding
turn acts through (`file_write_execution`, `patch_apply_execution`,
`shell_execution`, `process_execution`).

| Mode | Decision mode applied | Planning | What the runtime does |
|---|---|---|---|
| **Plan** | `deny` | `always` | Research and propose only. A write proposed anyway is blocked by the runtime, not by prompt wording. |
| **Edit** | `ask` | default | Every file write, patch, and command becomes a pending approval you accept or reject. |
| **Auto** | `auto` | default | Only low-risk actions run unprompted; medium and high still ask, and critical always requires a human. |

Notes that keep the mapping honest:

- No mode reaches the permissive `allow` decision mode. `Auto` stops at the
  deterministic risk floor described in
  [decision modes](DECISION_MODES_SPEC.md); `ask` and `deny` only ever tighten
  behaviour.
- Read capabilities are deliberately excluded from the set a mode changes, so
  Plan stays useful — it removes the ability to act, not the ability to look.
- Setting a decision mode is a **human `runtime_gate_manager`** operation,
  enforced server-side. If the runtime refuses the change, the composer reverts
  to the previous mode and says so rather than displaying a posture that is not
  in effect.
- On open, the page reads the live decision modes back. If the four capabilities
  disagree with each other (they were set individually in Permissions), no mode
  is claimed — the composer states that permissions are set individually.
- `Shift+Tab` cycles Plan → Edit → Auto without leaving the prompt.

Accepting a proposed change from the transcript uses the ordinary approval
route, and the action is **re-governed before anything runs** — the capability
gate, decision mode, policy review and the resolver's posture are all re-checked
at execution time, so a recorded decision is never treated as permission it
already had. Accepting a proposed **file change** then applies it once, with the
previous contents checkpointed first; accepting anything else records the
decision and executes nothing. The decisions rail reports which happened after
the fact, so "Accept" is never read as "already applied".

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
